#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
PYTHON_BIN="${PYTHON_BIN:-3.11}"

if [[ ! -x "$UV_BIN" ]]; then
  echo "uv not found at $UV_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

if [[ ! -x .venv/bin/python ]]; then
  "$UV_BIN" venv --python "$PYTHON_BIN" .venv
fi
"$UV_BIN" pip install --python .venv/bin/python -e .

echo "Environment ready in $ROOT_DIR/.venv"
