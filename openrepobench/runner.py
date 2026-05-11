from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time
import uuid
from .schemas import FailureKind, Task, CommandResult, RunResult


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _timeout_result(
    name: str,
    command: str,
    executor: str,
    started: float,
    timeout_seconds: int,
    exc: subprocess.TimeoutExpired,
) -> CommandResult:
    stderr = _as_text(exc.stderr)
    timeout_message = f"Command timed out after {timeout_seconds} seconds."
    if stderr:
        stderr = f"{stderr}\n{timeout_message}"
    else:
        stderr = timeout_message
    return CommandResult(
        name=name,
        command=command,
        executor=executor,
        exit_code=-1,
        stdout=_as_text(exc.stdout),
        stderr=stderr,
        duration_seconds=time.time() - started,
        timed_out=True,
    )


def _run_local_command(name: str, command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return _timeout_result(name, command, "local", started, timeout_seconds, exc)

    return CommandResult(
        name=name,
        command=command,
        executor="local",
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=time.time() - started,
    )


def _build_docker_args(task: Task, command: str, cwd: Path, container_name: str) -> list[str]:
    if not task.environment.docker_image:
        raise ValueError("Docker tasks must set environment.docker_image")

    network = "none" if task.environment.network == "disabled" else "bridge"
    args = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        network,
    ]
    if task.environment.cpus is not None:
        args.extend(["--cpus", str(task.environment.cpus)])
    if task.environment.memory:
        args.extend(["--memory", task.environment.memory])

    args.extend(
        [
            "-v",
            f"{cwd.resolve()}:/workspace",
            "-w",
            "/workspace",
            task.environment.docker_image,
            "sh",
            "-lc",
            command,
        ]
    )
    return args


def _run_docker_command(name: str, command: str, cwd: Path, task: Task) -> CommandResult:
    started = time.time()
    container_name = f"openrepobench-{uuid.uuid4().hex[:12]}"
    args = _build_docker_args(task, command, cwd, container_name)

    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=task.environment.timeout_seconds,
        )
    except FileNotFoundError:
        return CommandResult(
            name=name,
            command=command,
            executor="docker",
            exit_code=127,
            stdout="",
            stderr="Docker executable not found.",
            duration_seconds=time.time() - started,
        )
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)
        return _timeout_result(name, command, "docker", started, task.environment.timeout_seconds, exc)

    return CommandResult(
        name=name,
        command=command,
        executor="docker",
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=time.time() - started,
    )


def _run_command(name: str, command: str, cwd: Path, task: Task) -> CommandResult:
    timeout_seconds = task.environment.timeout_seconds
    if task.environment.kind == "docker":
        return _run_docker_command(name, command, cwd, task)
    return _run_local_command(name, command, cwd, timeout_seconds)


def _copy_workspace(task: Task, run_dir: Path) -> Path:
    src = Path(task.workspace).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Workspace does not exist: {src}")

    dst = run_dir / "workspace"
    ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", "node_modules")
    shutil.copytree(src, dst, ignore=ignore)

    subprocess.run(["git", "init"], cwd=dst, check=True, capture_output=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=dst, check=True)
    subprocess.run(["git", "config", "core.eol", "lf"], cwd=dst, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@example.com"], cwd=dst, check=True)
    subprocess.run(["git", "config", "user.name", "OpenRepoBench"], cwd=dst, check=True)
    subprocess.run(["git", "add", "."], cwd=dst, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=dst, check=True, capture_output=True)

    return dst


def _apply_patch(workspace: Path, patch_path: Path) -> tuple[bool, str]:
    patch_path = patch_path.resolve()
    if not patch_path.exists():
        return False, f"Patch does not exist: {patch_path}"

    text = patch_path.read_text(encoding="utf-8")
    if not text.strip():
        return True, "Empty patch."

    proc = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, proc.stderr
    return True, "Patch applied."


def _contains_forbidden_changes(workspace: Path, forbidden_paths: list[str]) -> list[str]:
    if not forbidden_paths:
        return []

    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    changed = set(line.strip() for line in diff.stdout.splitlines() if line.strip())
    violations = []
    for path in changed:
        for forbidden in forbidden_paths:
            if path == forbidden or path.startswith(forbidden.rstrip("/") + "/"):
                violations.append(path)
    return sorted(set(violations))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(run_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(run_dir).as_posix()
    except ValueError:
        return str(path)


def _required_failure_kind(task: Task, commands: list[CommandResult]) -> FailureKind | None:
    by_name = {command.name: command for command in commands}
    checks: list[tuple[str, bool, FailureKind]] = [
        ("public_tests", task.scoring.require_public_tests, "public_test_failure"),
        ("hidden_tests", task.scoring.require_hidden_tests, "hidden_test_failure"),
        ("regression_tests", task.scoring.require_regression_tests, "regression_test_failure"),
        ("lint", task.scoring.require_lint, "lint_failure"),
        ("security", task.scoring.require_security, "security_failure"),
    ]
    for name, required, failure_kind in checks:
        if not required:
            continue
        command = by_name.get(name)
        if command is None:
            return failure_kind
        if command.timed_out:
            return "timeout"
        if command.exit_code != 0:
            return failure_kind
    return None


def _infrastructure_error(commands: list[CommandResult]) -> str | None:
    for command in commands:
        if command.executor != "docker":
            continue
        if command.stderr == "Docker executable not found.":
            return command.stderr
        if command.exit_code == 125:
            return command.stderr or "Docker failed before the task command started."
    return None


def _write_run_artifacts(run_dir: Path, task: Task, result: RunResult, patch_path: Path | None) -> None:
    result_path = run_dir / "result.json"
    task_path = run_dir / "task.json"
    manifest_path = run_dir / "bundle_manifest.json"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    task_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")

    log_files = []
    for command in result.commands:
        stdout_path = logs_dir / f"{command.name}.stdout.txt"
        stderr_path = logs_dir / f"{command.name}.stderr.txt"
        stdout_path.write_text(command.stdout, encoding="utf-8")
        stderr_path.write_text(command.stderr, encoding="utf-8")
        log_files.extend([_artifact_path(run_dir, stdout_path), _artifact_path(run_dir, stderr_path)])

    artifact_files: dict[str, str | list[str] | None] = {
        "result": _artifact_path(run_dir, result_path),
        "task_snapshot": _artifact_path(run_dir, task_path),
        "manifest": _artifact_path(run_dir, manifest_path),
        "logs": log_files,
        "patch": _artifact_path(run_dir, patch_path) if patch_path else None,
    }
    hashes = {
        "task_snapshot": _sha256_file(task_path),
        "patch": _sha256_file(patch_path) if patch_path and patch_path.exists() else None,
    }

    result.run_dir = str(run_dir)
    result.result_path = str(result_path)
    result.bundle_path = str(run_dir)
    result.metadata["artifact_files"] = artifact_files
    result.metadata["sha256"] = hashes
    result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    manifest_hashes = dict(hashes)
    manifest_hashes["result"] = _sha256_file(result_path)
    manifest = {
        "schema_version": "0.1",
        "task_id": result.task_id,
        "agent": result.agent,
        "resolved": result.resolved,
        "failure_kind": result.failure_kind,
        "environment": task.environment.model_dump(),
        "files": artifact_files,
        "sha256": manifest_hashes,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def run_task(task: Task, agent, output_root: Path) -> RunResult:
    started = time.time()
    run_dir = output_root / f"{task.id}__{agent.name}__{int(started)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    commands: list[CommandResult] = []
    patch_path: Path | None = None
    error: str | None = None
    failure_kind: FailureKind | None = None
    resolved = False
    metadata = {}

    try:
        workspace = _copy_workspace(task, run_dir)
        agent_output = run_dir / "agent_output"
        agent_output.mkdir(exist_ok=True)

        patch_path = agent.run(task, workspace, agent_output)

        # Re-score from a clean copy, not the agent's dirty workspace.
        scoring_workspace = _copy_workspace(task, run_dir / "scoring")
        if patch_path is not None:
            ok, msg = _apply_patch(scoring_workspace, patch_path)
            metadata["patch_apply_message"] = msg
            if not ok:
                failure_kind = "patch_failure"
                raise RuntimeError(f"Patch failed to apply: {msg}")

        forbidden = _contains_forbidden_changes(scoring_workspace, task.scoring.forbidden_paths)
        metadata["forbidden_path_violations"] = forbidden
        if forbidden:
            failure_kind = "forbidden_change"
            raise RuntimeError(f"Forbidden paths modified: {forbidden}")

        if task.commands.setup:
            setup = _run_command("setup", task.commands.setup, scoring_workspace, task)
            commands.append(setup)
            if setup.timed_out:
                failure_kind = "timeout"
                error = "Setup command timed out."
            elif infra_error := _infrastructure_error([setup]):
                failure_kind = "harness_error"
                error = infra_error
            elif setup.exit_code != 0:
                failure_kind = "setup_failure"
                error = "Setup command failed."

        if failure_kind is None:
            commands.append(_run_command("public_tests", task.commands.public_tests, scoring_workspace, task))

            if task.commands.hidden_tests:
                commands.append(_run_command("hidden_tests", task.commands.hidden_tests, scoring_workspace, task))

            if task.commands.regression_tests:
                commands.append(_run_command("regression_tests", task.commands.regression_tests, scoring_workspace, task))

            if task.commands.lint:
                commands.append(_run_command("lint", task.commands.lint, scoring_workspace, task))

            if task.commands.security:
                commands.append(_run_command("security", task.commands.security, scoring_workspace, task))

        status = {c.name: c.exit_code == 0 for c in commands}

        resolved = True
        if task.scoring.require_public_tests:
            resolved = resolved and status.get("public_tests", False)
        if task.scoring.require_hidden_tests:
            resolved = resolved and status.get("hidden_tests", False)
        if task.scoring.require_regression_tests:
            resolved = resolved and status.get("regression_tests", False)
        if task.scoring.require_lint:
            resolved = resolved and status.get("lint", False)
        if task.scoring.require_security:
            resolved = resolved and status.get("security", False)

        infra_error = _infrastructure_error(commands)
        if infra_error and failure_kind is None:
            failure_kind = "harness_error"
            error = infra_error
        elif not resolved and failure_kind is None:
            failure_kind = _required_failure_kind(task, commands)

    except Exception as exc:
        if error is None:
            error = str(exc)
        if failure_kind is None:
            failure_kind = "harness_error"

    result = RunResult(
        task_id=task.id,
        agent=agent.name,
        resolved=resolved,
        failure_kind=failure_kind,
        patch_path=str(patch_path) if patch_path else None,
        commands=commands,
        runtime_seconds=time.time() - started,
        error=error,
        metadata=metadata,
    )

    _write_run_artifacts(run_dir, task, result, patch_path)
    return result
