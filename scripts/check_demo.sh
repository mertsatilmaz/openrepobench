#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON="python"
  else
    PYTHON="python3"
  fi
fi

VENV_DIR="${OPENREPOBENCH_VENV:-.venv}"
if [[ ! -x "$VENV_DIR/bin/python" && ! -x "$VENV_DIR/Scripts/python.exe" ]]; then
  "$PYTHON" -m venv "$VENV_DIR"
fi

if [[ -x "$VENV_DIR/bin/python" ]]; then
  PYTHON="$VENV_DIR/bin/python"
else
  PYTHON="$VENV_DIR/Scripts/python.exe"
fi

VENV_BIN="$(cd "$(dirname "$PYTHON")" && pwd)"
export PATH="$VENV_BIN:$PATH"

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -e .
"$PYTHON" -m unittest discover -s tests
"$PYTHON" -m openrepobench.cli validate-task tasks/public/python/demo_bugfix/task.yaml
"$PYTHON" -m openrepobench.cli validate-gold tasks/public/python/demo_bugfix/task.yaml
"$PYTHON" -m openrepobench.cli run --task tasks/public/python/demo_bugfix/task.yaml --agent noop || true
"$PYTHON" -m openrepobench.cli run --task tasks/public/python/demo_bugfix/task.yaml --agent simple_patch
"$PYTHON" -m openrepobench.cli run-suite --tasks "tasks/public/**/task.yaml" --agent simple_patch --model-config configs/example_model.yaml
