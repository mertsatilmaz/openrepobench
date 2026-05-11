# OpenRepoBench

OpenRepoBench is an open-source benchmark harness for evaluating coding agents on real repository-maintenance tasks.

The core contract is simple:

```text
Task + Agent + Sandbox + Scorer = Result
```

A task defines a repository state, a prompt, test commands, and scoring rules. An agent receives the task and a workspace, edits code, and returns a patch. The scorer applies the patch in a clean environment and records whether the task was resolved.

This starter scaffold includes:

- Task schema
- Agent interface
- Local runner
- Patch application
- Test execution
- Result JSON format
- Demo task
- No-op baseline agent
- Simple patch baseline agent

## Quick start

```bash
python -m pip install -e .
openrepobench validate-task tasks/public/python/demo_bugfix/task.yaml
openrepobench run --task tasks/public/python/demo_bugfix/task.yaml --agent noop
openrepobench run --task tasks/public/python/demo_bugfix/task.yaml --agent simple_patch
```

The demo task is intentionally tiny. It exists only to prove the harness works.

## Benchmark philosophy

This project is designed to evaluate whether AI coding agents can perform software maintenance in existing repositories under reproducible conditions.

It should not become another static toy coding benchmark.
