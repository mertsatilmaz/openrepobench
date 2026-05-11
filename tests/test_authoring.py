from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from openrepobench.authoring import scaffold_task, validate_gold


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "public" / "python" / "demo_bugfix" / "task.yaml"


class AuthoringTests(unittest.TestCase):
    def test_validate_gold_accepts_demo_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = validate_gold(TASK, tmp)

            self.assertTrue(summary["passed"])
            self.assertTrue(summary["checks"]["baseline_required_failure_reproduced"])
            self.assertTrue(summary["checks"]["gold_required_commands_passed"])
            self.assertEqual(summary["baseline_required_failures"], ["public_tests"])

    def test_scaffold_task_writes_authoring_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = scaffold_task(
                root=Path(tmp) / "demo_task",
                task_id="demo_task_v1",
                language="python",
                task_type="bugfix",
                prompt="Fix the bug.",
                public_tests="python -m unittest",
            )

            self.assertTrue(Path(result["task_yaml"]).exists())
            self.assertTrue(Path(result["workspace"]).exists())
            self.assertTrue(Path(result["gold_patch"]).exists())


if __name__ == "__main__":
    unittest.main()
