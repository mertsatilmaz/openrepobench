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


if __name__ == "__main__":
    unittest.main()
