# Task Authoring Guide

A good task is realistic, reproducible, and objectively scorable.

## A task must include

- Pinned repository state
- Natural-language prompt
- Deterministic setup command
- Public test command
- Hidden test command when available
- Scoring requirements
- Forbidden paths
- Timeout
- Gold patch

## Acceptance criteria

A task enters the benchmark only if:

- The workspace builds in a clean environment
- The failure reproduces before the fix
- The gold patch fixes the issue
- Hidden tests check behavior, not exact implementation
- Tests are not flaky
- The prompt contains enough information

## Fast workflow

Create a task scaffold:

```bash
openrepobench scaffold-task \
  --root tasks/public/python/my_task \
  --id my_task_v1 \
  --language python \
  --task-type bugfix \
  --prompt "Describe the maintenance task." \
  --public-tests "python -m unittest discover -s tests"
```

Then:

- Put the broken repository fixture in `repo/`.
- Add public tests under `repo/tests/`.
- Make the known-good fix locally.
- Save the fix as `gold.patch`.
- Revert the fixture back to its broken baseline.
- Run gold validation before committing.

```bash
openrepobench validate-gold tasks/public/python/my_task/task.yaml
```

Gold validation checks:

- `gold.patch` exists.
- setup passes before the fix, when configured.
- at least one required scoring command fails before the fix.
- the gold patch applies cleanly.
- the gold patch does not modify forbidden paths.
- setup passes after the fix, when configured.
- required scoring commands pass after the fix.

The command writes `gold_validation.json` under `runs/authoring/`.
