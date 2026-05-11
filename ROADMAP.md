# Roadmap

OpenRepoBench should become a benchmark that frontier-model teams can take seriously: realistic repository work, reproducible scoring, clear disclosure rules, and a task pipeline that assumes public tasks will eventually be contaminated.

## Phase 0: Credibility baseline

- Keep the harness installable from a clean checkout.
- Keep CI green with both unit tests and the demo task.
- Publish license, result schema, evaluation protocol, leaderboard rules, and contamination policy.
- Preserve raw patches, command logs, and result JSON for every run.

## Phase 1: Harness hardening

- Add first-class Docker execution with pinned images, CPU and memory limits, network policy, and per-task timeouts.
- Store complete run artifacts: normalized logs, patch, task metadata snapshot, agent metadata, model metadata, cost, token usage, and environment fingerprint.
- Add schema validation for tasks and results in CI.
- Add failure taxonomy: setup failure, patch failure, test failure, forbidden change, timeout, harness error.
- Make reruns deterministic enough to compare agents fairly.

## Phase 2: Task pipeline

- Define a review checklist for accepting tasks.
- Require baseline failing reproduction, gold patch, public tests, hidden tests, and forbidden-path policy.
- Add canary strings and metadata for contamination tracking.
- Separate public seed tasks from private leaderboard tasks.
- Create retired task releases so the benchmark can be audited without exposing the active hidden set.

## Phase 3: Agent and model adapters

- Support patch-only submissions.
- Support local CLI agents with a strict input/output contract.
- Support hosted-model adapters through explicit configuration files.
- Record tool access, internet access, sampling settings, attempts, token usage, and cost.
- Keep single-attempt and best-of-N tracks separate.

## Phase 4: Leaderboard and verifier

- Build a local verifier that replays submitted artifacts before leaderboard acceptance.
- Publish separate tracks for no-internet, internet-enabled, public-test-feedback, and patch-only settings.
- Require public disclosure for all non-hidden submission metadata.
- Add signed result bundles for third-party reproducibility.

## Phase 5: Governance

- Create a task review process with at least two reviewers per leaderboard task.
- Rotate hidden tasks on a fixed cadence.
- Publish retired task waves after replacement.
- Maintain a clear policy for disputes, flaky tests, task removal, and score corrections.

## Immediate Next Tickets

- Implement Docker sandbox execution in `openrepobench.runner`.
- Add task/result schema validation commands to the CLI.
- Add a minimal result-bundle format with logs, patch, task snapshot, and metadata.
- Add one medium-difficulty public task from a real repository fixture.
- Add a hidden-test convention that can run locally without leaking hidden files.
