from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "public" / "python" / "demo_bugfix" / "task.yaml"


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        python_dir = str(Path(sys.executable).resolve().parent)
        env["PATH"] = python_dir + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [sys.executable, "-m", "openrepobench.cli", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_noop_run_returns_nonzero_when_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(
                "run",
                "--task",
                str(TASK),
                "--agent",
                "noop",
                "--output-dir",
                tmp,
            )

        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('"resolved": false', proc.stdout)

    def test_simple_patch_run_returns_zero_when_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(
                "run",
                "--task",
                str(TASK),
                "--agent",
                "simple_patch",
                "--output-dir",
                tmp,
            )

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('"resolved": true', proc.stdout)

    def test_validate_result_accepts_generated_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_proc = self.run_cli(
                "run",
                "--task",
                str(TASK),
                "--agent",
                "simple_patch",
                "--output-dir",
                tmp,
            )
            self.assertEqual(run_proc.returncode, 0, run_proc.stdout + run_proc.stderr)
            result_path = json.loads(run_proc.stdout)["result_path"]

            validate_proc = self.run_cli("validate-result", result_path)

        self.assertEqual(validate_proc.returncode, 0, validate_proc.stdout + validate_proc.stderr)
        self.assertIn('"resolved": true', validate_proc.stdout)

    def test_validate_gold_accepts_demo_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(
                "validate-gold",
                str(TASK),
                "--output-dir",
                tmp,
            )

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('"passed": true', proc.stdout)

    def test_scaffold_task_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "new_task"
            proc = self.run_cli(
                "scaffold-task",
                "--root",
                str(root),
                "--id",
                "new_task_v1",
                "--language",
                "python",
                "--prompt",
                "Fix it.",
                "--public-tests",
                "python -m unittest",
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((root / "task.yaml").exists())
            self.assertTrue((root / "gold.patch").exists())

    def test_run_suite_summarizes_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(
                "run-suite",
                "--tasks",
                str(TASK),
                "--agent",
                "simple_patch",
                "--output-dir",
                tmp,
            )

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["total_tasks"], 1)
        self.assertEqual(summary["resolved_tasks"], 1)
        self.assertEqual(summary["harness_errors"], 0)

    def test_command_agent_can_be_used_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "fix_agent.py"
            script.write_text(
                "from pathlib import Path\n"
                "Path('calculator.py').write_text('def add(a, b):\\n    return a + b\\n', newline='\\n')\n",
                encoding="utf-8",
            )
            proc = self.run_cli(
                "run",
                "--task",
                str(TASK),
                "--agent",
                "command",
                "--agent-name",
                "fixture-command",
                "--agent-command",
                f'"{sys.executable}" "{script}"',
                "--output-dir",
                tmp,
            )

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('"agent": "fixture-command"', proc.stdout)
        self.assertIn('"resolved": true', proc.stdout)


if __name__ == "__main__":
    unittest.main()
