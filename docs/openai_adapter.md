# OpenAI Adapter

OpenRepoBench includes an optional OpenAI patch adapter for fast frontier-model smoke tests.

It uses the command-agent path:

```bash
openrepobench run-suite \
  --tasks "tasks/public/**/task.yaml" \
  --agent command \
  --agent-name openai-gpt-5.2 \
  --agent-command 'python -m openrepobench.adapters.openai_patch_agent --model gpt-5.2' \
  --model-config configs/openai_gpt52.yaml \
  --output-dir runs
```

On PowerShell:

```powershell
openrepobench run-suite `
  --tasks "tasks/public/**/task.yaml" `
  --agent command `
  --agent-name openai-gpt-5.2 `
  --agent-command "python -m openrepobench.adapters.openai_patch_agent --model gpt-5.2" `
  --model-config configs/openai_gpt52.yaml `
  --output-dir runs
```

Set your API key locally before running:

```bash
export OPENAI_API_KEY="..."
```

On PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
```

Install the optional dependency if needed:

```bash
python -m pip install -e ".[openai]"
```

The adapter reads the task prompt and a bounded snapshot of repository text files, calls the OpenAI Responses API, and asks the model for a structured JSON response containing a patch.

It accepts either a normal `git diff` patch or a Codex-style `*** Begin Patch` update block. If the model returns an update block, the adapter applies it to the agent workspace and emits a normalized `git diff` patch for OpenRepoBench scoring.

Useful options:

```bash
python -m openrepobench.adapters.openai_patch_agent \
  --model gpt-5.2 \
  --max-file-bytes 20000 \
  --max-total-bytes 120000
```

The adapter writes these files into the run's `agent_output/` directory:

- `agent.patch`
- `openai_notes.txt`
- `openai_patch_format.txt`
- `openai_raw_output.txt`
- `openai_usage.json`
- `workspace_snapshot.json`

For serious leaderboard results, keep one attempt per task, keep internet access disabled, and preserve the full result bundle.
