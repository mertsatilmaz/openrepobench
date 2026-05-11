from __future__ import annotations

from pathlib import Path
import argparse
import json
from .agents import CommandAgent, get_agent
from .authoring import scaffold_task, validate_gold
from .schemas import load_result, load_task
from .runner import run_task
from .suite import expand_task_paths, load_metadata, run_suite


def build_agent(args):
    if args.agent == "command":
        if not args.agent_command:
            raise ValueError("--agent-command is required when --agent command is used.")
        return CommandAgent(
            name=args.agent_name or "command",
            command=args.agent_command,
            timeout_seconds=args.agent_timeout,
        )
    return get_agent(args.agent)


def validate_task(args) -> int:
    task = load_task(args.task)
    print(task.model_dump_json(indent=2))
    return 0


def validate_result(args) -> int:
    result = load_result(args.result)
    print(result.model_dump_json(indent=2))
    return 0


def validate_gold_command(args) -> int:
    summary = validate_gold(args.task, args.output_dir)
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def scaffold_task_command(args) -> int:
    result = scaffold_task(
        root=args.root,
        task_id=args.id,
        language=args.language,
        task_type=args.task_type,
        prompt=args.prompt,
        public_tests=args.public_tests,
        repo=args.repo,
        difficulty=args.difficulty,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2))
    return 0


def run(args) -> int:
    task = load_task(args.task)
    agent = build_agent(args)
    metadata = load_metadata(args.model_config)
    result = run_task(task, agent, Path(args.output_dir), metadata)
    print(result.model_dump_json(indent=2))
    return 0 if result.resolved and result.error is None else 1


def suite(args) -> int:
    task_paths = expand_task_paths(args.tasks)
    if not task_paths:
        raise ValueError("No task files matched.")
    agent = build_agent(args)
    metadata = load_metadata(args.model_config)
    summary = run_suite(task_paths, agent, Path(args.output_dir), metadata)
    print(json.dumps(summary, indent=2))
    return 1 if summary["harness_errors"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="openrepobench")
    sub = parser.add_subparsers(required=True)

    p_validate = sub.add_parser("validate-task", help="Validate and print a task file.")
    p_validate.add_argument("task")
    p_validate.set_defaults(func=validate_task)

    p_validate_result = sub.add_parser("validate-result", help="Validate and print a result file.")
    p_validate_result.add_argument("result")
    p_validate_result.set_defaults(func=validate_result)

    p_validate_gold = sub.add_parser("validate-gold", help="Validate baseline failure and gold patch success.")
    p_validate_gold.add_argument("task")
    p_validate_gold.add_argument("--output-dir", default="runs/authoring")
    p_validate_gold.set_defaults(func=validate_gold_command)

    p_scaffold = sub.add_parser("scaffold-task", help="Create a task.yaml, repo folder, and gold.patch placeholder.")
    p_scaffold.add_argument("--root", required=True, help="Task directory to create.")
    p_scaffold.add_argument("--id", required=True, help="Stable task id.")
    p_scaffold.add_argument("--language", required=True)
    p_scaffold.add_argument("--task-type", default="bugfix")
    p_scaffold.add_argument("--difficulty", default="medium")
    p_scaffold.add_argument("--repo", default="local/scaffold")
    p_scaffold.add_argument("--prompt", required=True)
    p_scaffold.add_argument("--public-tests", required=True)
    p_scaffold.add_argument("--timeout", type=int, default=300)
    p_scaffold.set_defaults(func=scaffold_task_command)

    p_run = sub.add_parser("run", help="Run one task with one agent.")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--agent", required=True, choices=["noop", "simple_patch", "command"])
    p_run.add_argument("--agent-command", help="Shell command for --agent command.")
    p_run.add_argument("--agent-name", help="Display name for --agent command.")
    p_run.add_argument("--agent-timeout", type=int, default=1800)
    p_run.add_argument("--model-config", help="YAML or JSON model metadata file.")
    p_run.add_argument("--output-dir", default="runs")
    p_run.set_defaults(func=run)

    p_suite = sub.add_parser("run-suite", help="Run a set of tasks and write a suite summary.")
    p_suite.add_argument("--tasks", nargs="+", required=True, help="Task YAML paths or glob patterns.")
    p_suite.add_argument("--agent", required=True, choices=["noop", "simple_patch", "command"])
    p_suite.add_argument("--agent-command", help="Shell command for --agent command.")
    p_suite.add_argument("--agent-name", help="Display name for --agent command.")
    p_suite.add_argument("--agent-timeout", type=int, default=1800)
    p_suite.add_argument("--model-config", help="YAML or JSON model metadata file.")
    p_suite.add_argument("--output-dir", default="runs")
    p_suite.set_defaults(func=suite)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
