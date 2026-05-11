from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from openrepobench.agents import get_agent
from openrepobench.suite import expand_task_paths, run_suite, wilson_interval


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "public" / "python" / "demo_bugfix" / "task.yaml"


class SuiteTests(unittest.TestCase):
    def test_expand_task_paths_accepts_globs(self) -> None:
        paths = expand_task_paths([str(ROOT / "tasks" / "public" / "**" / "task.yaml")])

        self.assertIn(TASK, paths)

    def test_wilson_interval_bounds_rate(self) -> None:
        interval = wilson_interval(8, 10)

        self.assertLessEqual(interval["low"], 0.8)
        self.assertGreaterEqual(interval["high"], 0.8)
        self.assertEqual(interval["confidence"], 0.95)

    def test_run_suite_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_suite([TASK], get_agent("simple_patch"), Path(tmp), {"model": "fixture"})

            self.assertEqual(summary["total_tasks"], 1)
            self.assertEqual(summary["resolved_tasks"], 1)
            self.assertEqual(summary["failure_counts"], {"resolved": 1})
            self.assertTrue(Path(summary["summary_path"]).exists())


if __name__ == "__main__":
    unittest.main()
