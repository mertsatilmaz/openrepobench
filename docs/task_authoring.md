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

## Acceptance criteria

A task enters the benchmark only if:

- The workspace builds in a clean environment
- The failure reproduces before the fix
- The gold patch fixes the issue
- Hidden tests check behavior, not exact implementation
- Tests are not flaky
- The prompt contains enough information
