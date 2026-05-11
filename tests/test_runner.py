from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from openrepobench.agents import get_agent
from openrepobench.runner import _build_docker_args, _infrastructure_error, run_task
from openrepobench.schemas import CommandResult, load_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "public" / "python" / "demo_bugfix" / "task.yaml"


class RunnerTests(unittest.TestCase):
    def test_noop_agent_does_not_resolve_demo_task(self) -> None:
        task = load_task(TASK)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_task(task, get_agent("noop"), Path(tmp))

            self.assertFalse(result.resolved)
            self.assertEqual(result.failure_kind, "public_test_failure")
            self.assertIsNone(result.error)
            self.assertEqual(result.commands[0].name, "public_tests")
            self.assertEqual(result.commands[0].executor, "local")
            self.assertNotEqual(result.commands[0].exit_code, 0)
            self.assertTrue(Path(result.result_path or "").exists())
            self.assertTrue((Path(result.bundle_path or "") / "bundle_manifest.json").exists())

    def test_simple_patch_agent_resolves_demo_task(self) -> None:
        task = load_task(TASK)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_task(task, get_agent("simple_patch"), Path(tmp))

            self.assertTrue(result.resolved)
            self.assertIsNone(result.failure_kind)
            self.assertIsNone(result.error)
            self.assertEqual(result.metadata["patch_apply_message"], "Patch applied.")
            self.assertEqual(result.commands[0].exit_code, 0)

            bundle_path = Path(result.bundle_path or "")
            manifest = json.loads((bundle_path / "bundle_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "0.1")
            self.assertEqual(manifest["resolved"], True)
            self.assertTrue((bundle_path / manifest["files"]["task_snapshot"]).exists())
            self.assertTrue((bundle_path / manifest["files"]["patch"]).exists())

    def test_docker_args_encode_sandbox_policy(self) -> None:
        task = load_task(TASK)
        task = task.model_copy(
            update={
                "environment": task.environment.model_copy(
                    update={
                        "kind": "docker",
                        "docker_image": "python:3.11-slim",
                        "network": "disabled",
                        "cpus": 1.0,
                        "memory": "1g",
                    }
                )
            }
        )

        args = _build_docker_args(task, "python -m unittest", Path("repo"), "openrepobench-test")

        self.assertIn("--network", args)
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertIn("--cpus", args)
        self.assertEqual(args[args.index("--cpus") + 1], "1.0")
        self.assertIn("--memory", args)
        self.assertEqual(args[args.index("--memory") + 1], "1g")
        self.assertIn("python:3.11-slim", args)

    def test_docker_missing_is_infrastructure_error(self) -> None:
        command = CommandResult(
            name="public_tests",
            command="pytest",
            executor="docker",
            exit_code=127,
            stdout="",
            stderr="Docker executable not found.",
            duration_seconds=0.01,
        )

        self.assertEqual(_infrastructure_error([command]), "Docker executable not found.")


if __name__ == "__main__":
    unittest.main()
