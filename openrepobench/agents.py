from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import subprocess
import tempfile
import os


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
        target.write_text(fixed, encoding="utf-8")

        patch_path = output_dir / "simple_patch.patch"
        diff = subprocess.run(
            ["git", "diff", "--no-ext-diff"],
            cwd=workspace,
            text=True,
            capture_output=True,
            check=False,
        )
        patch_path.write_text(diff.stdout, encoding="utf-8")
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
