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
openrepobench run-suite --tasks "tasks/public/**/task.yaml" --agent simple_patch
openrepobench validate-result runs/<run-id>/result.json
```

The demo task is intentionally tiny. It exists only to prove the harness works.

Each run writes a result bundle containing the normalized result, task snapshot, patch, logs, and manifest. See [docs/result_bundles.md](docs/result_bundles.md).

## Benchmark philosophy

This project is designed to evaluate whether AI coding agents can perform software maintenance in existing repositories under reproducible conditions.

It should not become another static toy coding benchmark.

## Project direction

See [ROADMAP.md](ROADMAP.md) for the path from this starter harness to a reproducible, contamination-aware frontier-model benchmark.

For benchmark-grade execution, tasks can run scoring commands inside Docker. See [docs/sandboxing.md](docs/sandboxing.md).

To benchmark a real model-backed coding agent, use the external command agent and suite runner. See [docs/benchmarking_frontier_models.md](docs/benchmarking_frontier_models.md).

## License

Apache-2.0.
