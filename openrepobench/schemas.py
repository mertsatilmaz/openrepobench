from __future__ import annotations

from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field


TaskType = Literal[
    "bugfix",
    "feature",
    "refactor",
    "dependency_migration",
    "security_fix",
    "build_ci_fix",
    "performance_fix",
]


class EnvironmentSpec(BaseModel):
    kind: Literal["local", "docker"] = "local"
    docker_image: str | None = None
    timeout_seconds: int = 1800
    network: Literal["disabled", "enabled"] = "disabled"


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
    environment: EnvironmentSpec
    commands: CommandSpec
    scoring: ScoringSpec


class CommandResult(BaseModel):
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class RunResult(BaseModel):
    task_id: str
    agent: str
    resolved: bool
    patch_path: str | None
    commands: list[CommandResult]
    runtime_seconds: float
    error: str | None = None
    metadata: dict = Field(default_factory=dict)


def load_task(path: str | Path) -> Task:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Task.model_validate(raw)
