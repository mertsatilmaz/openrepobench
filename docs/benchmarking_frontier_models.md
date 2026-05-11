# Benchmarking Frontier Models

The fastest path to real results is the external command agent.

OpenRepoBench prepares a clean workspace, then runs your command inside that workspace. The command can call any model-backed coding agent. It should edit files in place, or write a unified diff to `OPENREPOBENCH_PATCH_PATH`.

The command receives these environment variables:

- `OPENREPOBENCH_TASK_ID`
- `OPENREPOBENCH_WORKSPACE`
- `OPENREPOBENCH_OUTPUT_DIR`
- `OPENREPOBENCH_TASK_PROMPT_FILE`
- `OPENREPOBENCH_TASK_JSON`
- `OPENREPOBENCH_PATCH_PATH`

If the command does not write a patch file, OpenRepoBench captures `git diff` from the workspace.

For OpenAI models, a ready-made adapter is available. See [openai_adapter.md](openai_adapter.md).

## Single task

```bash
openrepobench run \
  --task tasks/public/python/demo_bugfix/task.yaml \
  --agent command \
  --agent-name my-frontier-agent \
  --agent-command 'my-agent --prompt-file "$OPENREPOBENCH_TASK_PROMPT_FILE" --workspace "$OPENREPOBENCH_WORKSPACE"' \
  --model-config configs/example_model.yaml
```

## Task suite

```bash
openrepobench run-suite \
  --tasks "tasks/public/**/task.yaml" \
  --agent command \
  --agent-name my-frontier-agent \
  --agent-command 'my-agent --prompt-file "$OPENREPOBENCH_TASK_PROMPT_FILE" --workspace "$OPENREPOBENCH_WORKSPACE"' \
  --model-config configs/example_model.yaml \
  --output-dir runs
```

The suite summary reports:

- total tasks
- resolved tasks
- pass rate
- 95% Wilson confidence interval
- failure counts
- per-task result bundle paths

## Minimum disclosure

Before sharing results, fill out the model config with:

- provider
- exact model name and version
- sampling settings
- agent framework
- tool access
- internet access
- attempts per task
- date of run
- cost and token usage, when available

Do not compare different tracks in the same leaderboard. A no-internet single-attempt run is not comparable to an internet-enabled best-of-N run.
