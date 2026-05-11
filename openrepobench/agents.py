from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import os
import subprocess


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


class Agent(ABC):
    name: str

    @abstractmethod
    def run(self, task, workspace: Path, output_dir: Path) -> Path | None:
        """Run the agent and return a path to a unified diff patch, or None."""


class NoopAgent(Agent):
    name = "noop"

    def run(self, task, workspace: Path, output_dir: Path) -> Path | None:
        patch_path = output_dir / "noop.patch"
        patch_path.write_text("", encoding="utf-8")
        return patch_path


class SimplePatchAgent(Agent):
    """A deliberately dumb baseline.

    For the demo task only, this writes a known-good patch. Real benchmark
    submissions should implement the same Agent interface but call an actual
    model or coding agent.
    """

    name = "simple_patch"

    def run(self, task, workspace: Path, output_dir: Path) -> Path | None:
        if task.id != "demo_python_bugfix_v1":
            patch_path = output_dir / "simple_patch.patch"
            patch_path.write_text("", encoding="utf-8")
            return patch_path

        target = workspace / "calculator.py"
        original = target.read_text(encoding="utf-8")
        fixed = original.replace("return a - b", "return a + b")
        target.write_text(fixed, encoding="utf-8", newline="\n")

        patch_path = output_dir / "simple_patch.patch"
        diff = subprocess.run(
            ["git", "diff", "--no-ext-diff"],
            cwd=workspace,
            capture_output=True,
            check=False,
        )
        patch_path.write_bytes(diff.stdout)
        return patch_path


class CommandAgent(Agent):
    """Runs an external coding agent command against the workspace."""

    def __init__(self, name: str, command: str, timeout_seconds: int = 1800) -> None:
        self.name = name
        self.command = command
        self.timeout_seconds = timeout_seconds

    def run(self, task, workspace: Path, output_dir: Path) -> Path | None:
        prompt_path = output_dir / "task_prompt.md"
        task_path = output_dir / "task.json"
        patch_path = output_dir / "agent.patch"
        stdout_path = output_dir / "agent.stdout.txt"
        stderr_path = output_dir / "agent.stderr.txt"

        prompt_path.write_text(task.prompt, encoding="utf-8")
        task_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")

        env = os.environ.copy()
        env.update(
            {
                "OPENREPOBENCH_TASK_ID": task.id,
                "OPENREPOBENCH_WORKSPACE": str(workspace.resolve()),
                "OPENREPOBENCH_OUTPUT_DIR": str(output_dir.resolve()),
                "OPENREPOBENCH_TASK_PROMPT_FILE": str(prompt_path.resolve()),
                "OPENREPOBENCH_TASK_JSON": str(task_path.resolve()),
                "OPENREPOBENCH_PATCH_PATH": str(patch_path.resolve()),
            }
        )

        try:
            proc = subprocess.run(
                self.command,
                cwd=workspace,
                env=env,
                shell=True,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
            stdout_path.write_text(proc.stdout, encoding="utf-8")
            stderr_path.write_text(proc.stderr, encoding="utf-8")
            (output_dir / "agent_exit_code.txt").write_text(str(proc.returncode), encoding="utf-8")
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(_as_text(exc.stdout), encoding="utf-8")
            stderr_path.write_text(_as_text(exc.stderr), encoding="utf-8")
            (output_dir / "agent_exit_code.txt").write_text("-1", encoding="utf-8")

        if patch_path.exists():
            return patch_path

        diff = subprocess.run(
            ["git", "diff", "--no-ext-diff"],
            cwd=workspace,
            capture_output=True,
            check=False,
        )
        patch_path.write_bytes(diff.stdout)
        return patch_path


def get_agent(name: str) -> Agent:
    agents = {
        "noop": NoopAgent(),
        "simple_patch": SimplePatchAgent(),
    }
    if name not in agents:
        available = ", ".join(sorted(agents))
        raise ValueError(f"Unknown agent '{name}'. Available agents: {available}")
    return agents[name]
