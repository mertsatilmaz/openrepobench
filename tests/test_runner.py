from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from openrepobench.agents import get_agent
from openrepobench.runner import run_task
from openrepobench.schemas import load_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "public" / "python" / "demo_bugfix" / "task.yaml"


class RunnerTests(unittest.TestCase):
    def test_noop_agent_does_not_resolve_demo_task(self) -> None:
        task = load_task(TASK)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_task(task, get_agent("noop"), Path(tmp))

        self.assertFalse(result.resolved)
        self.assertIsNone(result.error)
        self.assertEqual(result.commands[0].name, "public_tests")
        self.assertNotEqual(result.commands[0].exit_code, 0)

    def test_simple_patch_agent_resolves_demo_task(self) -> None:
        task = load_task(TASK)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_task(task, get_agent("simple_patch"), Path(tmp))

        self.assertTrue(result.resolved)
        self.assertIsNone(result.error)
        self.assertEqual(result.metadata["patch_apply_message"], "Patch applied.")
        self.assertEqual(result.commands[0].exit_code, 0)


if __name__ == "__main__":
    unittest.main()
