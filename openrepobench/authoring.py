from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time

import yaml

from .runner import _apply_patch, _contains_forbidden_changes, _copy_workspace, _run_command, safe_name
from .schemas import CommandResult, Task, load_task


@dataclass
class CommandCheck:
    name: str
    required: bool
    command: str


def resolve_task_path(task_path: Path, path_value: str | None, default_name: str) -> Path:
    raw = path_value or default_name
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate

    task_relative = task_path.parent / candidate
    if task_relative.exists():
        return task_relative.resolve()
    return candidate.resolve()


def configured_command_checks(task: Task) -> list[CommandCheck]:
    candidates = [
        ("public_tests", task.scoring.require_public_tests, task.commands.public_tests),
        ("hidden_tests", task.scoring.require_hidden_tests, task.commands.hidden_tests),
        ("regression_tests", task.scoring.require_regression_tests, task.commands.regression_tests),
        ("lint", task.scoring.require_lint, task.commands.lint),
        ("security", task.scoring.require_security, task.commands.security),
    ]
    return [CommandCheck(name, required, command) for name, required, command in candidates if command]


def _run_setup(task: Task, workspace: Path) -> CommandResult | None:
    if not task.commands.setup:
        return None
    return _run_command("setup", task.commands.setup, workspace, task)


def _run_checks(task: Task, workspace: Path) -> list[CommandResult]:
    return [_run_command(check.name, check.command, workspace, task) for check in configured_command_checks(task)]


def _required_failures(task: Task, commands: list[CommandResult]) -> list[str]:
    required = {check.name for check in configured_command_checks(task) if check.required}
    return [command.name for command in commands if command.name in required and command.exit_code != 0]


def _required_success(task: Task, commands: list[CommandResult]) -> bool:
    required = {check.name for check in configured_command_checks(task) if check.required}
    passed = {command.name for command in commands if command.exit_code == 0}
    return required.issubset(passed)


def _commands_to_json(commands: list[CommandResult]) -> list[dict]:
    return [json.loads(command.model_dump_json()) for command in commands]


def validate_gold(task_path: str | Path, output_root: str | Path = "runs/authoring") -> dict:
    started = int(time.time())
    source = Path(task_path).resolve()
    task = load_task(source)
    gold_patch = resolve_task_path(source, task.gold_patch, "gold.patch")
    if not gold_patch.exists():
        raise FileNotFoundError(f"Gold patch does not exist: {gold_patch}")

    run_dir = Path(output_root) / f"validate_gold__{safe_name(task.id)}__{started}"
    baseline_dir = run_dir / "baseline"
    gold_dir = run_dir / "gold"
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline_workspace = _copy_workspace(task, baseline_dir)
    baseline_setup = _run_setup(task, baseline_workspace)
    baseline_commands = [] if baseline_setup and baseline_setup.exit_code != 0 else _run_checks(task, baseline_workspace)
    baseline_required_failures = _required_failures(task, baseline_commands)

    gold_workspace = _copy_workspace(task, gold_dir)
    patch_ok, patch_message = _apply_patch(gold_workspace, gold_patch)
    forbidden = _contains_forbidden_changes(gold_workspace, task.scoring.forbidden_paths) if patch_ok else []
    gold_setup = _run_setup(task, gold_workspace) if patch_ok and not forbidden else None
    gold_commands = []
    if patch_ok and not forbidden and (gold_setup is None or gold_setup.exit_code == 0):
        gold_commands = _run_checks(task, gold_workspace)

    checks = {
        "gold_patch_exists": gold_patch.exists(),
        "baseline_setup_passed": baseline_setup is None or baseline_setup.exit_code == 0,
        "baseline_required_failure_reproduced": bool(baseline_required_failures),
        "gold_patch_applies": patch_ok,
        "gold_forbidden_paths_clean": not forbidden,
        "gold_setup_passed": gold_setup is None or gold_setup.exit_code == 0,
        "gold_required_commands_passed": _required_success(task, gold_commands),
    }
    passed = all(checks.values())

    summary = {
        "schema_version": "0.1",
        "task_id": task.id,
        "task_path": str(source),
        "gold_patch": str(gold_patch),
        "run_dir": str(run_dir),
        "passed": passed,
        "checks": checks,
        "baseline_required_failures": baseline_required_failures,
        "forbidden_path_violations": forbidden,
        "patch_apply_message": patch_message,
        "baseline_setup": json.loads(baseline_setup.model_dump_json()) if baseline_setup else None,
        "baseline_commands": _commands_to_json(baseline_commands),
        "gold_setup": json.loads(gold_setup.model_dump_json()) if gold_setup else None,
        "gold_commands": _commands_to_json(gold_commands),
    }
    (run_dir / "gold_validation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def scaffold_task(
    root: str | Path,
    task_id: str,
    language: str,
    task_type: str,
    prompt: str,
    public_tests: str,
    repo: str = "local/scaffold",
    difficulty: str = "medium",
    timeout_seconds: int = 300,
) -> dict:
    task_dir = Path(root)
    repo_dir = task_dir / "repo"
    tests_dir = repo_dir / "tests"
    task_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    task_yaml = task_dir / "task.yaml"
    gold_patch = task_dir / "gold.patch"
    readme = task_dir / "README.md"

    task_data = {
        "id": task_id,
        "repo": repo,
        "base_commit": None,
        "language": language,
        "task_type": task_type,
        "difficulty": difficulty,
        "prompt": prompt,
        "workspace": str(repo_dir).replace("\\", "/"),
        "gold_patch": "gold.patch",
        "environment": {
            "kind": "local",
            "timeout_seconds": timeout_seconds,
            "network": "disabled",
        },
        "commands": {
            "setup": None,
            "public_tests": public_tests,
            "hidden_tests": None,
            "regression_tests": None,
            "lint": None,
            "security": None,
        },
        "scoring": {
            "require_public_tests": True,
            "require_hidden_tests": False,
            "require_regression_tests": False,
            "require_lint": False,
            "require_security": False,
            "forbidden_paths": ["tests"],
        },
    }

    if not task_yaml.exists():
        task_yaml.write_text(yaml.safe_dump(task_data, sort_keys=False), encoding="utf-8")
    if not gold_patch.exists():
        gold_patch.write_text("", encoding="utf-8")
    if not readme.exists():
        readme.write_text(
            "# Task Notes\n\n"
            "- Put the broken repository fixture in `repo/`.\n"
            "- Add public tests under `repo/tests/`.\n"
            "- Generate `gold.patch` from a known-good fix.\n"
            "- Run `openrepobench validate-gold task.yaml` before committing.\n",
            encoding="utf-8",
        )

    return {
        "task_dir": str(task_dir),
        "task_yaml": str(task_yaml),
        "workspace": str(repo_dir),
        "gold_patch": str(gold_patch),
    }
