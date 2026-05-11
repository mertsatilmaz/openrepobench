from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
from typing import Any


TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".go",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "patch": {
            "type": "string",
            "description": "A git-apply-compatible unified diff. Empty only if no change is needed.",
        },
        "notes": {
            "type": "string",
            "description": "Brief explanation of the change.",
        },
    },
    "required": ["patch", "notes"],
}


@dataclass
class WorkspaceSnapshot:
    file_tree: list[str]
    file_contents: dict[str, str]
    truncated: bool


def _run_git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )


def list_workspace_files(workspace: Path) -> list[str]:
    proc = _run_git(workspace, "ls-files")
    if proc.returncode == 0 and proc.stdout.strip():
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    files = []
    for path in workspace.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            files.append(path.relative_to(workspace).as_posix())
    return sorted(files)


def read_workspace_snapshot(
    workspace: Path,
    max_file_bytes: int = 20000,
    max_total_bytes: int = 120000,
) -> WorkspaceSnapshot:
    file_tree = list_workspace_files(workspace)
    file_contents: dict[str, str] = {}
    total = 0
    truncated = False

    for rel_path in file_tree:
        path = workspace / rel_path
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        size = path.stat().st_size
        if size > max_file_bytes or total + size > max_total_bytes:
            truncated = True
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            truncated = True
            continue
        file_contents[rel_path] = text
        total += len(text.encode("utf-8"))

    return WorkspaceSnapshot(file_tree=file_tree, file_contents=file_contents, truncated=truncated)


def build_prompt(task_prompt: str, snapshot: WorkspaceSnapshot) -> str:
    files = []
    for path, text in snapshot.file_contents.items():
        files.append(f"### {path}\n```text\n{text}\n```")

    truncation_note = ""
    if snapshot.truncated:
        truncation_note = "\nSome files were omitted because of size or encoding limits."

    return f"""You are solving an OpenRepoBench repository-maintenance task.

Task prompt:
{task_prompt}

Repository file tree:
{chr(10).join(snapshot.file_tree)}
{truncation_note}

Included file contents:
{chr(10).join(files)}

Return only a git-apply-compatible unified diff in the JSON field named patch.
Do not modify tests unless the task explicitly permits it.
"""


def extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    output_parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                output_parts.append(text)
    return "\n".join(output_parts)


def parse_patch_response(text: str) -> dict[str, str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            stripped = stripped.removeprefix("json").strip()
        parsed = json.loads(stripped)

    patch = parsed.get("patch", "")
    notes = parsed.get("notes", "")
    if not isinstance(patch, str) or not isinstance(notes, str):
        raise ValueError("OpenAI response must contain string fields: patch, notes.")
    return {"patch": patch, "notes": notes}


def create_response(client: Any, model: str, prompt: str, temperature: float | None = None) -> Any:
    params: dict[str, Any] = {
        "model": model,
        "instructions": (
            "You are a careful coding benchmark agent. Produce minimal, correct patches. "
            "Return JSON that matches the provided schema."
        ),
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "openrepobench_patch_response",
                "strict": True,
                "schema": PATCH_SCHEMA,
            }
        },
    }
    if temperature is not None:
        params["temperature"] = temperature
    return client.responses.create(**params)


def response_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {key: getattr(usage, key) for key in dir(usage) if key.endswith("_tokens")}


def is_apply_patch_block(patch: str) -> bool:
    stripped = patch.strip()
    return stripped.startswith("*** Begin Patch") and stripped.endswith("*** End Patch")


def _find_subsequence(lines: list[str], needle: list[str], start: int = 0) -> int:
    if not needle:
        return start
    limit = len(lines) - len(needle) + 1
    for index in range(start, max(start, limit)):
        if lines[index : index + len(needle)] == needle:
            return index
    return -1


def _apply_update_hunk(path: Path, hunk_lines: list[str]) -> None:
    old_lines: list[str] = []
    new_lines: list[str] = []
    for line in hunk_lines:
        if line.startswith("@@") or not line:
            continue
        marker = line[0]
        text = line[1:] + "\n"
        if marker == " ":
            old_lines.append(text)
            new_lines.append(text)
        elif marker == "-":
            old_lines.append(text)
        elif marker == "+":
            new_lines.append(text)
        else:
            raise ValueError(f"Unsupported apply_patch hunk line: {line}")

    current = path.read_text(encoding="utf-8").splitlines(keepends=True)
    index = _find_subsequence(current, old_lines)
    if index < 0:
        raise ValueError(f"Could not apply patch block to {path}: hunk context not found.")
    updated = current[:index] + new_lines + current[index + len(old_lines) :]
    path.write_text("".join(updated), encoding="utf-8", newline="\n")


def apply_patch_block(workspace: Path, patch: str) -> None:
    lines = patch.strip().splitlines()
    current_file: Path | None = None
    current_hunk: list[str] = []

    def flush_hunk() -> None:
        nonlocal current_hunk
        if current_file is not None and current_hunk:
            _apply_update_hunk(current_file, current_hunk)
            current_hunk = []

    for line in lines:
        if line in {"*** Begin Patch", "*** End Patch"}:
            continue
        if line.startswith("*** Update File: "):
            flush_hunk()
            rel_path = line.removeprefix("*** Update File: ").strip()
            current_file = workspace / rel_path
            if not current_file.exists():
                raise ValueError(f"Cannot update missing file from patch block: {rel_path}")
            continue
        if line.startswith("*** Add File: ") or line.startswith("*** Delete File: "):
            raise ValueError("Only Update File apply_patch blocks are supported by this adapter.")
        if current_file is None:
            raise ValueError(f"Patch block hunk found before file header: {line}")
        current_hunk.append(line)

    flush_hunk()


def normalize_patch(workspace: Path, patch: str) -> tuple[str, str]:
    if is_apply_patch_block(patch):
        apply_patch_block(workspace, patch)
        diff = _run_git(workspace, "diff", "--no-ext-diff")
        if diff.returncode != 0:
            raise ValueError(f"Failed to create normalized git diff: {diff.stderr}")
        return diff.stdout, "converted_apply_patch_block"
    return patch, "model_git_diff"


def run_adapter(
    workspace: Path,
    prompt_file: Path,
    patch_path: Path,
    output_dir: Path,
    model: str,
    max_file_bytes: int,
    max_total_bytes: int,
    temperature: float | None,
    client: Any | None = None,
) -> int:
    if client is None:
        try:
            from openai import OpenAI
        except ImportError:
            print("Install the optional adapter dependency with: python -m pip install -e .[openai]", file=sys.stderr)
            return 2
        client = OpenAI()

    task_prompt = prompt_file.read_text(encoding="utf-8")
    snapshot = read_workspace_snapshot(workspace, max_file_bytes=max_file_bytes, max_total_bytes=max_total_bytes)
    prompt = build_prompt(task_prompt, snapshot)

    response = create_response(client, model=model, prompt=prompt, temperature=temperature)
    output_text = extract_output_text(response)
    parsed = parse_patch_response(output_text)

    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_patch, patch_format = normalize_patch(workspace, parsed["patch"])
    patch_path.write_text(normalized_patch, encoding="utf-8", newline="\n")
    (output_dir / "openai_notes.txt").write_text(parsed["notes"], encoding="utf-8")
    (output_dir / "openai_raw_output.txt").write_text(output_text, encoding="utf-8")
    (output_dir / "openai_patch_format.txt").write_text(patch_format, encoding="utf-8")
    (output_dir / "openai_usage.json").write_text(json.dumps(response_usage(response), indent=2), encoding="utf-8")
    (output_dir / "workspace_snapshot.json").write_text(
        json.dumps(
            {
                "file_tree": snapshot.file_tree,
                "included_files": sorted(snapshot.file_contents),
                "truncated": snapshot.truncated,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openai-patch-agent")
    parser.add_argument("--model", default=os.getenv("OPENREPOBENCH_OPENAI_MODEL", "gpt-5.2"))
    parser.add_argument("--max-file-bytes", type=int, default=20000)
    parser.add_argument("--max-total-bytes", type=int, default=120000)
    parser.add_argument("--temperature", type=float, default=None)
    args = parser.parse_args(argv)

    workspace = Path(os.environ["OPENREPOBENCH_WORKSPACE"])
    prompt_file = Path(os.environ["OPENREPOBENCH_TASK_PROMPT_FILE"])
    patch_path = Path(os.environ["OPENREPOBENCH_PATCH_PATH"])
    output_dir = Path(os.environ["OPENREPOBENCH_OUTPUT_DIR"])

    return run_adapter(
        workspace=workspace,
        prompt_file=prompt_file,
        patch_path=patch_path,
        output_dir=output_dir,
        model=args.model,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
        temperature=args.temperature,
    )


if __name__ == "__main__":
    raise SystemExit(main())
