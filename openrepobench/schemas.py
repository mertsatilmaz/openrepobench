from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Literal
import yaml
from pydantic import BaseModel, Field, model_validator


TaskType = Literal[
    "bugfix",
    "feature",
    "refactor",
    "dependency_migration",
    "security_fix",
    "build_ci_fix",
    "performance_fix",
]


FailureKind = Literal[
    "setup_failure",
    "patch_failure",
    "forbidden_change",
    "public_test_failure",
    "hidden_test_failure",
    "regression_test_failure",
    "lint_failure",
    "security_failure",
    "timeout",
    "harness_error",
]


class EnvironmentSpec(BaseModel):
    kind: Literal["local", "docker"] = "local"
    docker_image: str | None = None
    cpus: float | None = Field(default=None, gt=0)
    memory: str | None = None
    timeout_seconds: int = Field(default=1800, gt=0)
    network: Literal["disabled", "enabled"] = "disabled"

    @model_validator(mode="after")
    def require_docker_image(self) -> "EnvironmentSpec":
        if self.kind == "docker" and not self.docker_image:
            raise ValueError("Docker environments must set docker_image.")
        return self


class CommandSpec(BaseModel):
    setup: str | None = None
    public_tests: str
    hidden_tests: str | None = None
    regression_tests: str | None = None
    lint: str | None = None
    security: str | None = None


class ScoringSpec(BaseModel):
    require_public_tests: bool = True
    require_hidden_tests: bool = False
    require_regression_tests: bool = False
    require_lint: bool = False
    require_security: bool = False
    forbidden_paths: list[str] = Field(default_factory=list)


class Task(BaseModel):
    id: str
    repo: str
    base_commit: str | None = None
    language: str
    task_type: TaskType
    difficulty: Literal["easy", "medium", "hard", "brutal"] = "medium"
    prompt: str
    workspace: str
    gold_patch: str | None = None
    environment: EnvironmentSpec
    commands: CommandSpec
    scoring: ScoringSpec

    @model_validator(mode="after")
    def require_scored_commands(self) -> "Task":
        required_commands = [
            (self.scoring.require_hidden_tests, self.commands.hidden_tests, "hidden_tests"),
            (self.scoring.require_regression_tests, self.commands.regression_tests, "regression_tests"),
            (self.scoring.require_lint, self.commands.lint, "lint"),
            (self.scoring.require_security, self.commands.security, "security"),
        ]
        missing = [name for required, command, name in required_commands if required and not command]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Required scoring commands are missing: {joined}.")
        return self


class CommandResult(BaseModel):
    name: str
    command: str
    executor: Literal["local", "docker"] = "local"
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


class RunResult(BaseModel):
    task_id: str
    agent: str
    resolved: bool
    failure_kind: FailureKind | None = None
    patch_path: str | None
    commands: list[CommandResult]
    runtime_seconds: float
    run_dir: str | None = None
    result_path: str | None = None
    bundle_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_task(path: str | Path) -> Task:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Task.model_validate(raw)


def load_result(path: str | Path) -> RunResult:
    return RunResult.model_validate_json(Path(path).read_text(encoding="utf-8"))
