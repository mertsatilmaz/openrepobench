from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

from openrepobench.schemas import EnvironmentSpec, Task, load_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "public" / "python" / "demo_bugfix" / "task.yaml"


class SchemaTests(unittest.TestCase):
    def test_docker_environment_requires_image(self) -> None:
        with self.assertRaises(ValidationError):
            EnvironmentSpec(kind="docker")

    def test_required_scoring_commands_must_exist(self) -> None:
        raw = load_task(TASK).model_dump()
        raw["commands"]["hidden_tests"] = None
        raw["scoring"]["require_hidden_tests"] = True

        with self.assertRaises(ValidationError):
            Task.model_validate(raw)


if __name__ == "__main__":
    unittest.main()
