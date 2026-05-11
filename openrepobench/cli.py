from __future__ import annotations

from pathlib import Path
import argparse
from .schemas import load_result, load_task
from .agents import get_agent
from .runner import run_task


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
    agent = get_agent(args.agent)
    result = run_task(task, agent, Path(args.output_dir))
    print(result.model_dump_json(indent=2))
    return 0 if result.resolved and result.error is None else 1


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
    p_run.add_argument("--agent", required=True, choices=["noop", "simple_patch"])
    p_run.add_argument("--output-dir", default="runs")
    p_run.set_defaults(func=run)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
