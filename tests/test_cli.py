from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
