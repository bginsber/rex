# Project Setup

These notes cover the minimal steps required to stand up the RexLit workspace and run the new
Bun-based privilege API tests.

## Prerequisites

- Node.js 18+ with [Bun](https://bun.sh) 1.0 or newer installed locally.
- Python 3.11 for the existing test harnesses (see `AGENTS.md` for virtualenv details).
- The `REXLIT_HOME` directory should point to a writable location (defaults to
  `~/.local/share/rexlit`).

## Install Dependencies

```bash
# Python tooling (from the repository root)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
# or: uv sync --extra dev

# Bun API dependencies
cd api
bun install --frozen-lockfile
```

## Running Tests

```bash
# API security regression suite (68 cases)
cd api
bun test

# Full Python suite
cd ..
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
uv run pytest -v --no-cov
```

The Bun tests stub out `rexlit`, so they succeed without Groq keys or index data. Python
integration tests assume the usual sample corpus described in the repository guides.
