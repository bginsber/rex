# RexLit

[![Status: M0 Ready](https://img.shields.io/badge/status-M0%20ready-brightgreen.svg)](#)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](#)
[![License: TBD](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#)

Offline-first UNIX litigation toolkit for secure discovery, indexing, and audit-ready timelines.

## Status

✅ **Phase 1 (M0) Complete** – Production-ready foundation with document ingest, parallel indexing, and tamper-evident audit trail.  
🚧 **Phase 2 (M1)** – OCR, Bates stamping, and redaction coming next.

**Latest Release:** v0.1.0-m0  
**Tests:** 63/63 passing (`pytest -v --no-cov`)  
**Performance:** 100K documents indexed in 4-6 hours (≈20× faster)

## Overview

RexLit packages the core tooling litigation teams need to process large evidence sets entirely offline:

- **Streaming ingest** guards the filesystem boundary while extracting metadata and text from PDFs, DOCX, and text files.
- **Tantivy-backed indexing** delivers sub-second full-text search across 100K+ documents with parallel workers.
- **Tamper-evident audit ledger** records every ingest and index action for defensible chain-of-custody.

The CLI wraps these services in an approachable workflow designed for laptops or air-gapped review rooms.

## Features

- Offline-first CLI with Typer-based UX and rich progress reporting.
- Secure path resolution and symlink handling to block traversal attacks.
- ProcessPoolExecutor-powered indexing with configurable batching.
- Metadata cache for instant custodian and document type lookups.
- Append-only audit log with SHA-256 hash chaining and fsync durability.

### Performance Benchmarks

| Metric | Achievement |
| --- | --- |
| 100K document indexing | 4-6 hours (≈20× faster than baseline) |
| Memory usage during ingest | <10 MB (≈8× reduction) |
| Metadata query latency | <10 ms (≈1000× faster) |
| CPU utilization | 80-90% with adaptive worker pools |
| Security regressions | 0 critical issues detected |

## Installation

### From PyPI (recommended)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install rexlit
```

### From source

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Run `pytest -v --no-cov` after installation to validate your environment.

## Quick Start

1. Prepare a working directory with your document corpus (for example `./sample-docs`).
2. Generate a manifest while ingesting:
   ```bash
   rexlit ingest ./sample-docs --manifest out/manifest.jsonl
   ```
3. Build the Tantivy index:
   ```bash
   rexlit index build ./sample-docs --index-dir out/index
   ```
4. Search across the corpus:
   ```bash
   rexlit index search out/index --query "privileged AND contract"
   ```
5. Verify the audit chain before handing evidence to counsel:
   ```bash
   rexlit audit verify --ledger out/audit/log.jsonl
   ```

## CLI Usage

### `rexlit ingest`

Stream documents from a root directory, enforce boundary checks, and emit a JSONL manifest.

```bash
rexlit ingest /evidence/incoming \
  --manifest out/manifest.jsonl \
  --follow-symlinks false \
  --ignore-hidden true
```

- `--manifest`: Path to write structured metadata per document.
- `--follow-symlinks`: Opt-in to follow safe symlinks (default: false).
- `--ignore-hidden`: Skip dotfiles and system directories.

### `rexlit index build`

Create or update a Tantivy index with parallel worker pools.

```bash
rexlit index build /evidence/incoming \
  --index-dir out/index \
  --workers 6 \
  --batch-size 100 \
  --commit-every 1000
```

- `--workers`: Override default worker pool (defaults to `cpu_count() - 1`).
- `--batch-size`: Number of documents processed per worker chunk.
- `--commit-every`: Frequency of persisting Tantivy writes.
- `--dense`: Enable Kanon 2 dense embeddings + HNSW (requires `--online` or `REXLIT_ONLINE=1`).
- `--dim`: Matryoshka dimension for Kanon 2 (`1792`, `1024`, `768`, `512`, `256`; default `768`).
- `--dense-batch`: Batch size for embedding RPCs (default `32`).
- `--isaacus-api-key`: Override `ISAACUS_API_KEY` for Kanon 2 access tokens.
- `--isaacus-api-base`: Point at a self-hosted Isaacus endpoint instead of the hosted API.

### `rexlit index search`

Query the index with rich boolean syntax and optional structured output.

```bash
rexlit index search out/index \
  --query '"duty to preserve" AND custodian:anderson' \
  --limit 20 \
  --json
```

- `--limit`: Maximum results to return (default: 10).
- `--json`: Emit machine-friendly JSON for automation.
- `--mode`: Choose `lexical`, `dense`, or `hybrid` scoring (dense/hybrid require online mode).
- `--dim`: Matryoshka dimension for dense and hybrid queries (default `768`).
- `--isaacus-api-key` / `--isaacus-api-base`: Optional overrides mirroring the index build flags.

#### Isaacus configuration

- `ISAACUS_API_KEY`: Kanon 2 access token used when `--dense`/`--mode dense|hybrid` is active.
- `ISAACUS_API_BASE`: Override API host when running a self-hosted Isaacus deployment.

### `rexlit audit show`

Inspect recent audit entries for ingest and index actions.

```bash
rexlit audit show --ledger out/audit/log.jsonl --tail 10
```

### `rexlit audit verify`

Validate the append-only hash chain and report integrity issues.

```bash
rexlit audit verify --ledger out/audit/log.jsonl
```

- Returns non-zero exit code if tampering or truncation is detected.

## Phase 1 Deliverables (M0)

### Core Infrastructure
- ✅ Typer-based CLI with intuitive subcommands
- ✅ Pydantic configuration layer with XDG + env overrides
- ✅ Structured logging and rich progress reporting

### Document Processing
- ✅ Parallel ingest pipeline (15-20× throughput gains)
- ✅ Streaming discovery with O(1) memory profile
- ✅ PDF, DOCX, TXT, and Markdown extraction
- ✅ Automatic custodian and document type metadata

### Search & Indexing
- ✅ Tantivy-backed full-text indexing
- ✅ Metadata cache for constant-time lookups
- ✅ Configurable worker pools and batching knobs
- ✅ 100K+ document capacity validated

### Security & Audit
- ✅ Root-bound path resolution with symlink defense
- ✅ Append-only audit ledger with SHA-256 hash chaining
- ✅ Fsync durability for legal defensibility
- ✅ 13 dedicated path traversal regression tests

### Quality Assurance
- ✅ 63 integration and unit tests (100% passing)
- ✅ Performance benchmarks automated via `benchmark_metadata.py`
- ✅ Attack simulations covering traversal and tampering
- ✅ Zero critical regressions outstanding

## Configuration

RexLit reads settings from `rexlit.config.AppConfig`, environment variables, and CLI flags. Key options:

| Setting | Description | Default | How to set |
| --- | --- | --- | --- |
| `REXLIT_HOME` | Base data directory for indices, manifests, and audit logs. | XDG state dir (e.g. `~/.local/state/rexlit`) | Env var or `--data-dir` flag |
| `REXLIT_WORKERS` | Maximum worker processes for `index build`. | `cpu_count() - 1` | Env var or `--workers` flag |
| `REXLIT_BATCH_SIZE` | Documents per batch when indexing. | `100` | Env var or `--batch-size` flag |
| `REXLIT_AUDIT_LOG` | Default ledger path for audit commands. | `<data_dir>/audit/log.jsonl` | Env var or `--ledger` flag |
| `REXLIT_ONLINE` | Enables optional network integrations; keep disabled for air-gapped ops. | `false` | Env var or `--online` flag |
| `REXLIT_LOG_LEVEL` | Python logging level for CLI runs. | `INFO` | Env var or `--log-level` flag |

## Troubleshooting

- **`PathOutsideRootError` during ingest**: Verify the supplied directory is within the allowed root and that symlinks resolve inside the boundary.
- **`tantivy` import failures**: Ensure system dependencies for Tantivy bindings are installed; reinstall with `pip install -e '.[dev]'`.
- **Slow indexing performance**: Increase `--workers` or reduce `--batch-size` to match available cores and memory; monitor disk throughput.
- **Audit verification fails**: Run `rexlit audit show --tail 20` to locate the first failing entry and regenerate the ledger from trusted manifests.
- **Permission errors on output directories**: Confirm RexLit has write access to `out/` paths or set `--data-dir` to a writable location.

## Testing

```bash
# Run the complete suite
pytest -v --no-cov

# Focus on security hardening
pytest tests/test_security_path_traversal.py -v

# Exercise indexing flows
pytest tests/test_index.py -v
```

## Performance Tuning

- Monitor CPU saturation with `htop` and adjust `--workers` to leave headroom.
- Reduce `--batch-size` if memory constrained; increase for faster SSD-backed runs.
- Commit more frequently (`--commit-every`) when indexing on slow disks.
- Use `benchmark_metadata.py` to compare metadata cache performance across versions.

## Contributing

1. Install tooling: `pip install -e '.[dev]'`
2. Lint and type-check: `ruff check . && mypy rexlit/`
3. Format: `black .`
4. Run tests: `pytest -v --no-cov`

## Documentation

- `CLI-GUIDE.md` – Detailed command reference and workflows.
- `ARCHITECTURE.md` – System design, components, and data flows.
- `SECURITY.md` – Security posture, path traversal defenses, threat model.
- `.cursor/plans/` – Historical implementation plans and design notes.

## Philosophy

**Offline-by-default.** Any networked feature stays behind `--online` and ships disabled. Validate filesystem roots before touching data, prefer deterministic pipelines, and keep audit trails verifiable.

## License

TBD
