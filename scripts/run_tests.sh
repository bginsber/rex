#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

UV_CACHE_DIR="${UV_CACHE_DIR:-$REPO_ROOT/.uv-cache}"

if [ "${UV_SKIP_SYNC:-0}" != "1" ]; then
  UV_CACHE_DIR="$UV_CACHE_DIR" uv sync --extra dev >/dev/null
fi

export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
DEFAULT_CMD=(pytest -p pytest_cov -v --no-cov)

if [ "$#" -gt 0 ]; then
  if [[ "$1" == -* ]]; then
    CMD=(pytest -p pytest_cov "$@")
  else
    CMD=("$@")
  fi
else
  CMD=("${DEFAULT_CMD[@]}")
fi

UV_CACHE_DIR="$UV_CACHE_DIR" uv run "${CMD[@]}"
