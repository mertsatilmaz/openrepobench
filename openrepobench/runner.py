from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import time
import tempfile
from .schemas import Task, CommandResult, RunResult


def _run_command(name: str, command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return CommandResult(
        name=name,
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=time.time() - started,
    )


def _copy_workspace(task: Task, run_dir: Path) -> Path:
    src = Path(task.workspace).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Workspace does not exist: {src}")

    dst = run_dir / "workspace"
    ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", "node_modules")
    shutil.copytree(src, dst, ignore=ignore)

    subprocess.run(["git", "init"], cwd=dst, check=True, capture_output=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=dst, check=True)
    subprocess.run(["git", "config", "core.eol", "lf"], cwd=dst, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@example.com"], cwd=dst, check=True)
    subprocess.run(["git", "config", "user.name", "OpenRepoBench"], cwd=dst, check=True)
    subprocess.run(["git", "add", "."], cwd=dst, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=dst, check=True, capture_output=True)

    return dst


def _apply_patch(workspace: Path, patch_path: Path) -> tuple[bool, str]:
    patch_path = patch_path.resolve()
    if not patch_path.exists():
        return False, f"Patch does not exist: {patch_path}"

    text = patch_path.read_text(encoding="utf-8")
    if not text.strip():
        return True, "Empty patch."

    proc = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, proc.stderr
    return True, "Patch applied."


def _contains_forbidden_changes(workspace: Path, forbidden_paths: list[str]) -> list[str]:
    if not forbidden_paths:
        return []

    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    changed = set(line.strip() for line in diff.stdout.splitlines() if line.strip())
    violations = []
    for path in changed:
        for forbidden in forbidden_paths:
            if path == forbidden or path.startswith(forbidden.rstrip("/") + "/"):
                violations.append(path)
    return sorted(set(violations))


def run_task(task: Task, agent, output_root: Path) -> RunResult:
    started = time.time()
    run_dir = output_root / f"{task.id}__{agent.name}__{int(started)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    commands: list[CommandResult] = []
    patch_path: Path | None = None
    error: str | None = None
    resolved = False
    metadata = {}

    try:
        workspace = _copy_workspace(task, run_dir)
        agent_output = run_dir / "agent_output"
        agent_output.mkdir(exist_ok=True)

        patch_path = agent.run(task, workspace, agent_output)

        # Re-score from a clean copy, not the agent's dirty workspace.
        scoring_workspace = _copy_workspace(task, run_dir / "scoring")
        if patch_path is not None:
            ok, msg = _apply_patch(scoring_workspace, patch_path)
            metadata["patch_apply_message"] = msg
            if not ok:
                raise RuntimeError(f"Patch failed to apply: {msg}")

        forbidden = _contains_forbidden_changes(scoring_workspace, task.scoring.forbidden_paths)
        metadata["forbidden_path_violations"] = forbidden
        if forbidden:
            raise RuntimeError(f"Forbidden paths modified: {forbidden}")

        timeout = task.environment.timeout_seconds

        if task.commands.setup:
            commands.append(_run_command("setup", task.commands.setup, scoring_workspace, timeout))

        commands.append(_run_command("public_tests", task.commands.public_tests, scoring_workspace, timeout))

        if task.commands.hidden_tests:
            commands.append(_run_command("hidden_tests", task.commands.hidden_tests, scoring_workspace, timeout))

        if task.commands.regression_tests:
            commands.append(_run_command("regression_tests", task.commands.regression_tests, scoring_workspace, timeout))

        if task.commands.lint:
            commands.append(_run_command("lint", task.commands.lint, scoring_workspace, timeout))

        if task.commands.security:
            commands.append(_run_command("security", task.commands.security, scoring_workspace, timeout))

        status = {c.name: c.exit_code == 0 for c in commands}

        resolved = True
        if task.scoring.require_public_tests:
            resolved = resolved and status.get("public_tests", False)
        if task.scoring.require_hidden_tests:
            resolved = resolved and status.get("hidden_tests", False)
        if task.scoring.require_regression_tests:
            resolved = resolved and status.get("regression_tests", False)
        if task.scoring.require_lint:
            resolved = resolved and status.get("lint", False)
        if task.scoring.require_security:
            resolved = resolved and status.get("security", False)

    except Exception as exc:
        error = str(exc)

    result = RunResult(
        task_id=task.id,
        agent=agent.name,
        resolved=resolved,
        patch_path=str(patch_path) if patch_path else None,
        commands=commands,
        runtime_seconds=time.time() - started,
        error=error,
        metadata=metadata,
    )

    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result
