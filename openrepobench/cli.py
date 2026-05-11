from __future__ import annotations

from pathlib import Path
import argparse
import json
from .agents import CommandAgent, get_agent
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
