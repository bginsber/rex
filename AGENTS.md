# AGENTS instructions for /Users/bg/Documents/Coding/rex

# Repository Guidelines

## Project Structure & Module Organization
Core source code lives in `rexlit/`, split into focused packages: `ingest/` for document discovery and extraction, `index/` for Tantivy-backed indexing and metadata caching, `audit/` for the tamper-evident hash chain, plus `cli.py` as the offline-first entry point. Shared helpers belong in `rexlit/utils/`. Keep large fixtures and mock evidence sets inside `tests/data/` so production paths stay clean. The `tests/` suite mirrors the package layout (`test_ingest.py`, `test_index.py`, etc.) and should be updated alongside any module change.

## Build, Test, and Development Commands
Create a clean toolchain before hacking:
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
# or: uv sync --extra dev
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -v --no-cov
python -m build

# Optional: Initialize test data submodule (for CLI smoke tests)
./scripts/setup-test-data.sh
# Then use test data:
rexlit ingest ./rexlit/docs/sample-docs --manifest out.jsonl
rexlit index build ./rexlit/docs/sample-docs
```
The editable install keeps the CLI in sync while you work; run `pytest` before publishing any change. Use the CLI smoke commands above to validate streaming ingest, parallel index build, and audit behavior. **Note:** Test data is maintained as a git submodule (`rex-test-data`) to keep the main repository lean—you can work without it, but CLI smoke tests require it.

## Coding Style & Naming Conventions
Target Python 3.11 with strict typing (`from __future__ import annotations`, `typing.Iterator`). Modules, functions, and files stay `snake_case`; classes remain `PascalCase`. Prefer `pathlib.Path` over raw strings, early returns for validation, and rich dataclasses for metadata records. Keep concurrency primitives (`ProcessPoolExecutor`, batching helpers) isolated in `index/` and guard them with docstrings explaining CPU and I/O assumptions. Always validate resolved paths against their allowed root before touching the filesystem.

## Testing Guidelines
Write focused `pytest` cases that exercise streaming discovery, parallel indexing, and security boundaries. Name tests after the behavior under scrutiny (`test_discover_blocks_path_traversal`). Regenerate golden manifests in `tests/fixtures/` rather than editing inline constants. For long-running flows, add smoke tests that operate on the tiny sample corpus so CI stays fast while still covering the audit chain.

## Commit & Pull Request Guidelines
Follow the existing short, imperative commit style (`Fix path traversal guard`). Every PR must summarize intent, list affected commands, and note security implications when touching ingest or audit modules. Link planning documents (`todos/*.md`) for context, include `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -v --no-cov` output, and attach CLI snippets (`rexlit index build ...`) when manual validation was involved.

## Security & Configuration Tips
RexLit is offline-by-default—feature flags that require network access must stay behind `--online` toggles with explicit warnings. Secure builds by resolving symlinks, rejecting files outside the requested root, and logging `WARNING` events for any skipped path. Document new environment variables (e.g., OCR providers) in `README.md` and keep secrets out of the repo.
