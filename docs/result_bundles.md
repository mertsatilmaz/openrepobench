# Result Bundles

Every `openrepobench run` writes a result bundle under the selected output directory.

The bundle is a directory, not just a single JSON file. It contains:

- `result.json`: normalized run result.
- `task.json`: snapshot of the task definition used for the run.
- `bundle_manifest.json`: artifact index with file paths and SHA-256 hashes.
- `agent_output/`: patch files produced by the agent.
- `logs/`: stdout and stderr for each executed command.
- `workspace/`: the agent workspace.
- `scoring/workspace/`: the clean workspace used for scoring.

The result JSON includes:

- `resolved`: whether required scoring checks passed.
- `failure_kind`: machine-readable failure reason when unresolved.
- `commands`: command-level exit codes, output, executor, duration, and timeout flag.
- `metadata.artifact_files`: paths to important bundle files.
- `metadata.sha256`: hashes for replay-critical files.

Leaderboard submissions should preserve the whole bundle. A verifier can replay or inspect the bundle without trusting a model provider's summary.
