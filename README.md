# RexLit

[![Status: M1 Ready](https://img.shields.io/badge/status-M1%20ready-brightgreen.svg)](#)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](#)
[![License: TBD](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#)

Offline-first UNIX litigation toolkit for e-discovery, Bates stamping, OCR, deadline tracking, and production exports.

## Status

✅ **Phase 1 (M0) Complete** – Document ingest, parallel indexing, tamper-evident audit trail
✅ **Phase 2 (M1) Complete** – Bates stamping, OCR, TX/FL rules engine, production exports
🚧 **Phase 3 (M2)** – Redaction, email threading, advanced analytics

**Latest Release:** v0.2.0-m1
**Tests:** 146/146 passing (`pytest -v --no-cov`)
**Performance:** 100K documents indexed in 4-6 hours | OCR: 2-5s per page

## Overview

RexLit is a comprehensive e-discovery toolkit that handles the complete document processing lifecycle entirely offline:

- **Document Processing**: Streaming ingest with metadata extraction from PDFs, DOCX, emails, and text files
- **Search & Indexing**: Tantivy-backed full-text search with optional Kanon 2 dense/hybrid retrieval (100K+ docs)
- **OCR Processing**: Tesseract integration with smart preflight to skip pages with native text layers
- **Bates Stamping**: Layout-aware PDF stamping with rotation handling and safe-area detection
- **Rules Engine**: TX/FL civil procedure deadline calculations with ICS calendar export
- **Production Exports**: Court-ready DAT/Opticon load files for discovery productions
- **Audit Trail**: Tamper-evident ledger with SHA-256 hash chaining for defensible workflows

The CLI wraps these services in an intuitive workflow designed for solo practitioners, small firms, or air-gapped review rooms.

## Features

### Core Discovery
- **Offline-first CLI** with Typer-based UX and rich progress reporting
- **Streaming ingest** with secure path resolution and symlink validation
- **ProcessPoolExecutor indexing** with configurable workers and batching
- **Metadata cache** for instant custodian and document type lookups
- **Dense/hybrid search** via Kanon 2 embeddings (requires online mode)

### Production Workflows
- **Bates stamping** with layout-aware placement, rotation handling, and position presets
- **OCR processing** via Tesseract with preflight optimization and confidence scoring
- **DAT/Opticon exports** for court-ready production load files
- **Rules engine** for TX/FL civil procedure deadlines with ICS calendar integration
- **Privilege classification** with pattern-based pre-filtering and LLM escalation (Groq/OpenAI)

### Security & Audit
- **Path traversal defense** with root-bound resolution and 13 regression tests
- **Append-only audit log** with SHA-256 hash chaining and fsync durability
- **Deterministic processing** for reproducible outputs across runs
- **Privacy-preserving audit** with hashed chain-of-thought reasoning for privilege decisions

### Discovery & Case Management
- **Impact discovery reports** (Sedona Conference-aligned) with proportionality metrics, dedupe analysis, and estimated review costs
- **Methods appendix** for Cooperation Appendix compliance and defensible methodology documentation
- **EDRM privilege log** protocol compliance for court-ready privilege logging
- **Offline-first design** with no network/AI calls for data privacy
- **Court-friendly outputs** (manifests, audit logs) for early case conferences

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

### Optional: OCR Support

For Tesseract OCR functionality:

```bash
# Install Tesseract system binary
brew install tesseract  # macOS
# or
apt-get install tesseract-ocr  # Ubuntu

# Install Python dependencies
pip install -e '.[ocr-tesseract]'

# Verify installation
tesseract --version
```

Run `pytest -v --no-cov` after installation to validate your environment (69 tests require Tesseract).

## Quick Start

### Basic Discovery Workflow

```bash
# 1. Ingest documents with metadata extraction
rexlit ingest ./evidence --manifest out/manifest.jsonl

# 2. Build full-text search index
rexlit index build ./evidence

# 3. Search the corpus
rexlit index search "privileged AND contract" --limit 20

# 4. Verify audit trail
rexlit audit verify
```

### Production Workflow (Bates + OCR)

```bash
# 1. OCR scanned documents (preflight skips native text)
rexlit ocr run ./scans --output ./text --confidence

# 2. Apply Bates numbers to PDFs
rexlit bates stamp ./evidence --prefix ABC --width 7 --output ./stamped

# 3. Create court-ready production set
rexlit produce create ./stamped --name "Production_001" --format dat

# 4. Check audit trail
rexlit audit show --tail 10
```

### Deadline Tracking

```bash
# Calculate TX deadlines with ICS calendar export
rexlit rules calc \
  --jurisdiction TX \
  --event served_petition \
  --date 2025-11-01 \
  --service mail \
  --explain \
  --ics deadlines.ics

# Import deadlines.ics into Calendar app
```

## Web UI

A production-ready React UI wraps the CLI via the Bun/Elysia bridge using the CLI-as-API pattern.

```bash
# API (Bun + Elysia)
cd api
bun install
REXLIT_BIN=$(which rexlit) bun run index.ts

# UI (Vite + React)
cd ../ui
npm install  # or bun install
npm run dev  # or bun dev
```

**Features:**
- Full-text search with lexical/dense/hybrid modes
- Document viewer with formatted text display
- Privilege decision recording (Privileged/Not Privileged/Skip)
- Real-time statistics and index metadata
- Security: Hash-based document access (no path traversal)

**Architecture:** API calls `rexlit` CLI as subprocess, ensuring zero divergence between CLI and API behavior. See `docs/UI_*.md` for detailed architecture documentation.

## CLI Usage

### `rexlit privilege classify`

Classify documents for attorney-client privilege, work product, or common interest using pattern-based pre-filtering and optional LLM escalation.

```bash
# Basic classification with pattern matching only
rexlit privilege classify ./discovery/contract.pdf

# Detailed explanation with LLM reasoning (requires API key)
rexlit privilege explain ./discovery/email.txt --effort high

# Batch processing
find ./discovery -name "*.pdf" | xargs -I {} rexlit privilege classify {}
```

- `--effort`: Reasoning effort level (`low`, `medium`, `high`) for LLM invocation
- `--provider`: LLM provider (`groq` or `openai`)
- `--explain`: Show detailed chain-of-thought reasoning

**Features:**
- Pattern-based pre-filtering (≥85% confidence → skip LLM, save costs)
- Smart escalation to LLM for uncertain cases (50-84% confidence)
- Privacy-preserving audit: reasoning is SHA-256 hashed, not logged in plaintext
- Multi-stage pipeline: privilege detection → responsiveness → redaction spans
- EDRM privilege log compliance

**Environment Variables:**
- `GROQ_API_KEY` - Groq API key for Llama models
- `OPENAI_API_KEY` - OpenAI API key for GPT models

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
rexlit index build /evidence/incoming
```

- `--dense`: Enable Kanon 2 dense embeddings + HNSW (requires `--online` or `REXLIT_ONLINE=1`).
- `--dim`: Matryoshka dimension for Kanon 2 (`1792`, `1024`, `768`, `512`, `256`; default `768`).
- `--dense-batch`: Batch size for embedding RPCs (default `32`).
- `--isaacus-api-key`: Override `ISAACUS_API_KEY` for Kanon 2 access tokens.
- `--isaacus-api-base`: Point at a self-hosted Isaacus endpoint instead of the hosted API.

### `rexlit index search`

Query the index with rich boolean syntax and optional structured output.

```bash
rexlit index search '"duty to preserve" AND custodian:anderson' --limit 20 --json
```

- `--limit`: Maximum results to return (default: 10)
- `--json`: Emit machine-friendly JSON for automation
- `--mode`: Choose `lexical`, `dense`, or `hybrid` scoring (dense/hybrid require online mode)
- `--dim`: Matryoshka dimension for dense and hybrid queries (default `768`)
- `--isaacus-api-key` / `--isaacus-api-base`: Optional overrides mirroring the index build flags.

#### Isaacus configuration

- `ISAACUS_API_KEY`: Kanon 2 access token used when `--dense`/`--mode dense|hybrid` is active.
- `ISAACUS_API_BASE`: Override API host when running a self-hosted Isaacus deployment.

### `rexlit ocr run`

Perform OCR on scanned PDFs or images with optional preflight to skip native text layers.

```bash
rexlit ocr run ./scans/binder.pdf --output ./text/binder.txt --confidence
```

- `--provider`: `tesseract` (default) with future slots for Paddle/online adapters.
- `--output`: File or directory to persist extracted text (`.txt` mirrored for directories).
- `--preflight/--no-preflight`: Enable or disable text-layer detection (default: enabled).
- `--language`: Tesseract language code (default: `eng`).
- `--confidence`: Display average OCR confidence for QA workflows.

Every run records an `ocr.process` entry in the audit ledger containing page count, text length, and confidence metrics.

### `rexlit bates stamp`

Apply Bates numbers to PDF documents with layout-aware placement.

```bash
rexlit bates stamp ./documents --prefix ABC --width 7 --output ./stamped
```

- `--prefix`: Bates number prefix (e.g., `ABC`, `PROD001`)
- `--width`: Zero-padding width for numbers (default: 7, e.g., `ABC0000001`)
- `--output`: Output directory for stamped PDFs
- `--position`: Stamp placement (`bottom-right`, `bottom-center`, `top-right`)
- `--font-size`: Font size in points (default: 10)
- `--color`: RGB hex color (default: `000000` black)
- `--dry-run`: Preview Bates sequence without stamping

Features:
- **Layout-aware**: Detects page rotation and respects safe margins (0.5" bleed)
- **Deterministic**: Processes files in SHA-256 hash order for reproducible numbering
- **Audit trail**: Logs Bates assignments with coordinates for verification

### `rexlit produce create`

Generate court-ready production load files (DAT or Opticon format).

```bash
rexlit produce create ./stamped --name "Production_001" --format dat
```

- `--name`: Production set identifier
- `--format`: Output format (`dat` or `opticon`)
- `--output`: Output directory (default: `~/.local/share/rexlit/productions/`)
- `--bates-prefix`: Expected Bates prefix for validation

Outputs:
- **DAT format**: Delimited text file with document-level metadata
- **Opticon format**: Image-based production with page references
- Both formats include full audit provenance

### `rexlit rules calc`

Calculate litigation deadlines for Texas or Florida civil procedure rules.

```bash
rexlit rules calc \
  --jurisdiction TX \
  --event served_petition \
  --date 2025-11-01 \
  --service mail \
  --explain \
  --ics deadlines.ics
```

- `--jurisdiction` / `-j`: State rules (`TX` or `FL`)
- `--event` / `-e`: Triggering event (e.g., `served_petition`, `discovery_served`, `motion_filed`)
- `--date` / `-d`: Base date in YYYY-MM-DD format
- `--service` / `-s`: Service method (`personal`, `mail`, `eservice`)
- `--explain`: Show step-by-step calculation trace
- `--ics`: Export deadlines to ICS calendar file

Features:
- **Provenance**: Every deadline includes rule citation (e.g., `Tex. R. Civ. P. 99(b)`)
- **Service modifiers**: Mail service automatically adds 3 days per rule
- **Holiday awareness**: Skips weekends and US/state holidays
- **Calendar integration**: ICS export for drag-and-drop into Outlook/Calendar

Supported events:
- `served_petition`: Answer deadline, special exceptions
- `discovery_served`: Interrogatory/RFP response deadlines
- `motion_filed`: Response and hearing deadlines
- `trial_notice_served`: Pretrial conference requirements (FL)

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

## Dense/Hybrid Search (Kanon 2)

Dense retrieval augments BM25 with Kanon 2 embeddings and an HNSW vector index. Hybrid search fuses lexical and dense rankings using Reciprocal Rank Fusion (RRF).

Prerequisites:
- Online mode enabled: `--online` flag or `REXLIT_ONLINE=1`
- `ISAACUS_API_KEY` set (or pass `--isaacus-api-key`)

Build dense materials:
```bash
rexlit --online index build ./sample-docs --dense --dim 768
```

Search with hybrid scoring:
```bash
rexlit --online index search "privileged communication" --mode hybrid --dim 768
```

Artifacts:
- HNSW index: `~/.local/share/rexlit/index/dense/kanon2_<dim>.hnsw`
- Metadata JSON: adjacent `*.meta.json` with doc IDs and fields

Memory guidelines (approximate):
- 10K docs @ 768d ≈ 94 MB total (Tantivy + HNSW)
- 100K docs @ 768d ≈ 937 MB total

Notes:
- Dense build/search is network-bound and respects offline gate.
- Once built, searches can run offline using the persisted HNSW index for vector lookup (query embeddings still require online).

See also: `docs/SELF_HOSTED_EMBEDDINGS.md` and `docs/adr/0007-dense-retrieval-design.md`.

## Deliverables by Phase

### Phase 1 (M0) - Core Discovery Platform ✅

**Infrastructure:**
- ✅ Typer-based CLI with intuitive subcommands
- ✅ Pydantic configuration with XDG + env overrides
- ✅ Ports/adapters architecture with import linting

**Document Processing:**
- ✅ Parallel ingest pipeline (15-20× throughput gains)
- ✅ Streaming discovery with O(1) memory profile
- ✅ PDF, DOCX, TXT, Markdown extraction

**Search & Indexing:**
- ✅ Tantivy full-text indexing (100K+ docs)
- ✅ Kanon 2 dense/hybrid search (online mode)
- ✅ Metadata cache for O(1) lookups

**Security & Audit:**
- ✅ Root-bound path resolution + 13 traversal tests
- ✅ Append-only SHA-256 hash chain ledger
- ✅ Deterministic processing for reproducibility

**Testing:** 63 integration/unit tests (100% passing)

### Phase 2 (M1) - Production Workflows ✅

**OCR Processing:**
- ✅ Tesseract adapter with preflight optimization
- ✅ Confidence scoring and audit integration
- ✅ Directory batch processing
- ✅ 6 integration tests

**Bates Stamping:**
- ✅ Layout-aware PDF stamping with rotation handling
- ✅ Safe-area detection (0.5" margins)
- ✅ Position presets and color/font customization
- ✅ Deterministic sequencing by SHA-256 hash

**Rules Engine:**
- ✅ TX/FL civil procedure deadline calculations
- ✅ ICS calendar export for Outlook/Calendar
- ✅ Service method modifiers (mail +3 days)
- ✅ Holiday awareness (US + state holidays)
- ✅ Rule citations with provenance

**Production Exports:**
- ✅ DAT load file generation
- ✅ Opticon format support
- ✅ Bates prefix validation
- ✅ Full audit trail integration

**Privilege Classification (NEW):**
- ✅ Pattern-based pre-filtering (PrivilegePatternsAdapter) - fast, offline, high-confidence
- ✅ LLM escalation (GroqPrivilegeAdapter + OpenAI support) - deep reasoning for uncertain cases
- ✅ Privacy-preserving audit logging with hashed chain-of-thought reasoning
- ✅ Multi-stage classification: privilege detection (ACP/WP/CI), responsiveness, redaction spans
- ✅ Smart escalation strategy: high-confidence patterns (≥0.85) skip LLM, uncertain cases escalate
- ✅ EDRM privilege log protocol compliance

**Web UI + API (NEW):**
- ✅ Bun/Elysia API bridge with CLI-as-API pattern (subprocess wrapper)
- ✅ React search interface with document viewer and privilege decision recording
- ✅ Security: Path traversal defense in document endpoint
- ✅ Zero API/CLI divergence (shares same code paths)

**Testing:** 146 integration/unit tests (100% passing)

### Phase 3 (M2) - Redaction & Advanced Analytics 🚧

**Redaction (In Progress - 40% complete):**
- ✅ Port interfaces defined (RedactionPlannerPort, PIIPort, StampPort)
- ✅ Plan creation workflow with JSONL persistence
- 🚧 PIIPort adapter implementation (Presidio integration planned)
- 🚧 Redaction application (PDF coordinate-based black boxes)
- 🚧 Interactive redaction review UI

**Email Analytics (Planned):**
- 🚧 Email threading and family detection
- 🚧 Custodian communication graphs
- 🚧 Timeline visualization

**Advanced Features (Planned):**
- 🚧 Claude integration for privilege review (extended reasoning)
- 🚧 Paddle OCR provider (better accuracy for complex layouts)
- 🚧 Multi-language support (Spanish, French)

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

### Discovery & Indexing
- **`PathOutsideRootError` during ingest**: Verify the directory is within the allowed root and that symlinks resolve inside the boundary.
- **`tantivy` import failures**: Ensure system dependencies for Tantivy bindings are installed; reinstall with `pip install -e '.[dev]'`.
- **Slow indexing performance**: Increase `--workers` or reduce `--batch-size` to match available cores and memory; monitor disk throughput.
- **Audit verification fails**: Run `rexlit audit show --tail 20` to locate the first failing entry and regenerate the ledger from trusted manifests.

### OCR & Bates
- **`TesseractNotFoundError`**: Install Tesseract binary: `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Ubuntu).
- **Low OCR confidence (<60%)**: Check scan DPI (300+ recommended), use `--no-preflight` to force OCR, or try preprocessing (deskew, contrast).
- **Bates numbers not visible**: Increase `--font-size` or change `--position` to avoid page content overlap.
- **Wrong Bates sequence**: Files are processed in SHA-256 hash order (deterministic); check with `--dry-run` first.

### Rules & Production
- **Missing deadline events**: Check `rexlit/rules/{tx,fl}.yaml` for available events; only core civil procedure rules included in M1.
- **ICS file won't import**: Ensure `.ics` extension; some calendar apps require drag-and-drop instead of double-click.
- **DAT file encoding issues**: Production files use UTF-8; legacy tools may need Latin-1 conversion.

### General
- **Permission errors on output directories**: Confirm RexLit has write access to `out/` paths or set `--data-dir` to a writable location.
- **Import errors after upgrade**: Reinstall with `pip install -e '.[dev,ocr-tesseract]'` to pick up new dependencies.

## Testing

```bash
# Run the complete suite (146 tests)
pytest -v --no-cov

# Focus on security hardening
pytest tests/test_security_path_traversal.py -v

# Exercise indexing flows
pytest tests/test_index.py -v

# Test OCR adapter (requires Tesseract installed)
pytest tests/test_ocr_tesseract.py -v

# Test rules engine
pytest tests/test_rules_engine.py -v

# Test Bates stamping
pytest tests/test_app_adapters.py::test_sequential_bates_planner -v
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

### Core Guides
- `CLI-GUIDE.md` – Detailed command reference and workflows
- `ARCHITECTURE.md` – System design, components, and data flows
- `SECURITY.md` – Security posture, path traversal defenses, threat model
- `CLAUDE.md` – Project conventions and development guide

### Architecture Decision Records (ADRs)
- `docs/adr/0001-offline-first-gate.md` – Network operations gated by explicit flag
- `docs/adr/0002-ports-adapters-import-contracts.md` – Hexagonal architecture with import linting
- `docs/adr/0003-determinism-policy.md` – Stable sorting for reproducible outputs
- `docs/adr/0004-jsonl-schema-versioning.md` – Schema evolution and backward compatibility
- `docs/adr/0005-bates-numbering-authority.md` – Sequential assignment from deterministic plans
- `docs/adr/0006-redaction-plan-apply-model.md` – Two-phase redaction workflow
- `docs/adr/0007-dense-retrieval-design.md` – Kanon 2 embeddings with HNSW
- `docs/adr/0008-privilege-log-protocol.md` – EDRM compliance for privilege logging
- `docs/adr/0009-cli-as-api-pattern.md` – Web API wraps CLI to prevent divergence

### Web UI Documentation
- `docs/UI_ARCHITECTURE.md` – Bun/Elysia API + React UI design
- `docs/UI_SECURITY.md` – Path traversal defense and security model
- `docs/UI_DEPLOYMENT.md` – Production deployment guide

### Analysis & Planning
- `CODEBASE_ANALYSIS.md` – Comprehensive codebase overview (13K+ lines analyzed)
- `CODEBASE_QUICK_REFERENCE.md` – Quick navigation guide
- `NEXT_PRIORITIES_DEEP_DIVE.md` – M2 roadmap and implementation priorities

## Philosophy

**Offline-by-default.** Any networked feature stays behind `--online` and ships disabled. Validate filesystem roots before touching data, prefer deterministic pipelines, and keep audit trails verifiable.

## License

TBD
