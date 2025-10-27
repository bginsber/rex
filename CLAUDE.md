# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RexLit is an offline-first UNIX litigation toolkit for secure discovery, indexing, and audit-ready document processing. It's designed for legal e-discovery workflows where network access may be restricted, legal defensibility requires deterministic processing, and tamper-evident audit trails are essential.

**Current Status:** Phase 1 (M0) complete, Phase 2 (M1) in development

## Essential Commands

### Setup and Installation
```bash
# Create virtual environment (Python 3.11 required)
python3.11 -m venv .venv
source .venv/bin/activate

# Install for development
pip install -e '.[dev]'
```

### Testing
```bash
# Run all tests (63 tests, expect 100% passing)
pytest -v --no-cov

# Run with coverage
pytest -v

# Run specific test suite
pytest tests/test_index.py -v
pytest tests/test_security_path_traversal.py -v

# Run single test
pytest tests/test_index.py::TestParallelProcessing -v
```

### Linting and Type Checking
```bash
# Run all quality checks
ruff check .
mypy rexlit/
black --check .

# Auto-format code
black .

# Check import rules (critical for architecture)
lint-imports
```

### Running RexLit CLI
```bash
# Ingest documents
rexlit ingest ./sample-docs --manifest out/manifest.jsonl

# Build index (with parallel processing)
rexlit index build ./sample-docs --index-dir out/index --workers 6

# Search
rexlit index search out/index --query "privileged AND contract"

# Verify audit trail
rexlit audit verify --ledger out/audit/log.jsonl
```

## Architecture

### Ports and Adapters (Hexagonal Architecture)

RexLit uses a strict ports-and-adapters architecture to maintain clean boundaries:

```
CLI (rexlit/cli.py)
  ↓ depends on
Bootstrap (rexlit/bootstrap.py) - wires dependencies
  ↓ creates
Application Services (rexlit/app/*.py) - orchestrates workflows
  ↓ depends on
Port Interfaces (rexlit/app/ports/*.py) - Protocol definitions
  ↑ implemented by
Adapters (rexlit/app/adapters/*.py) - concrete implementations
  and
Domain Modules (rexlit/audit/, rexlit/index/, rexlit/ingest/, etc.)
```

**Critical Import Rules (enforced by importlinter):**
- CLI can ONLY import `rexlit.app` and `rexlit.bootstrap`
- CLI CANNOT directly import domain modules or adapters
- Domain modules CANNOT import CLI
- Application services depend ONLY on port interfaces, never concrete adapters
- All dependency wiring happens in `bootstrap.py`

### Key Port Interfaces

Located in `rexlit/app/ports/`:
- `LedgerPort` - audit logging
- `OCRPort` - document OCR
- `BatesPlannerPort` - Bates numbering
- `RedactionPlannerPort` - redaction plans
- `DeduperPort` - deduplication
- `DiscoveryPort` - document discovery
- `StoragePort` - file storage
- `PackPort` - artifact packaging

### Core Principles

1. **Offline-First**: All operations offline by default. Network features require explicit `--online` flag or `REXLIT_ONLINE=1`. See ADR 0001.

2. **Deterministic Processing**: All file processing uses deterministic sorting by `(sha256_hash, path)` tuple to ensure reproducible outputs. Critical for legal defensibility. See ADR 0003.

3. **Tamper-Evident Audit**: SHA-256 hash chain in append-only JSONL ledger. Any modification breaks the chain.

4. **Path Traversal Defense**: All paths resolved with `.resolve()` and validated against allowed root. 13 dedicated security tests.

## Directory Structure

```
rexlit/
├── cli.py              # CLI entry point (Typer-based)
├── config.py           # Pydantic settings with XDG support
├── bootstrap.py        # Dependency wiring
├── app/                # Application layer
│   ├── m1_pipeline.py     # Main M1 orchestration
│   ├── redaction_service.py
│   ├── pack_service.py
│   ├── ports/             # Port interfaces (Protocols)
│   └── adapters/          # Concrete implementations
├── audit/              # Audit ledger domain
├── index/              # Tantivy search index
│   ├── build.py           # Parallel indexing with ProcessPoolExecutor
│   ├── search.py
│   └── metadata.py        # O(1) metadata cache
├── ingest/             # Document discovery and extraction
│   ├── discover.py        # Streaming discovery
│   └── extract.py         # PDF/DOCX text extraction
├── utils/              # Shared utilities
│   ├── deterministic.py   # Deterministic sorting helpers
│   ├── offline.py         # Online mode gate
│   ├── plans.py           # Plan persistence
│   └── jsonl.py           # JSONL operations
├── ocr/                # OCR providers
├── pdf/                # PDF manipulation
├── rules/              # Calendar/deadline rules
└── ediscovery/         # Production formats
```

## Configuration

RexLit uses Pydantic v2 for configuration with XDG Base Directory compliance:

- Data: `~/.local/share/rexlit/` or `$REXLIT_HOME`
- Config: `~/.config/rexlit/`
- Cache: `~/.cache/rexlit/`

Key environment variables:
- `REXLIT_HOME` - override data directory
- `REXLIT_ONLINE` - enable network features (default: false)
- `REXLIT_WORKERS` - parallel worker count (default: cpu_count - 1)
- `ISAACUS_API_KEY` - for dense embeddings (online mode only)

## Critical ADRs (Architecture Decision Records)

Located in `docs/adr/`:

- **ADR 0001**: Offline-First Gate - All operations offline by default, explicit opt-in for network
- **ADR 0002**: Ports/Adapters Import Contracts - Hexagonal architecture with enforced import rules
- **ADR 0003**: Determinism Policy - Stable sorting by (hash, path) for reproducible outputs
- **ADR 0004**: JSONL Schema Versioning - Backward-compatible schema evolution
- **ADR 0005**: Bates Numbering Authority - Sequential assignment from deterministic plans
- **ADR 0006**: Redaction Plan/Apply Model - Two-phase redaction workflow

## Performance Characteristics

Optimized for 100K+ document processing:
- **Parallel Processing**: ProcessPoolExecutor with cpu_count-1 workers
- **Streaming Discovery**: O(1) memory usage, yields documents one at a time
- **Metadata Cache**: O(1) lookups for custodians/doctypes (<10ms vs 5-10s full scan)
- **Batch Commits**: Tantivy commits every 1,000 docs for memory management

Benchmarks (8 cores):
- 100K docs indexed in 4-6 hours (≈20× faster than sequential)
- Memory: <10MB during discovery, ~2GB during indexing
- Search: <50ms for 100K doc index

## Testing Guidelines

- 63 integration and unit tests (100% passing required)
- Security: 13 path traversal regression tests
- Performance: `benchmark_metadata.py` for metadata cache validation
- Determinism: Verify identical outputs across multiple runs
- Use `pytest -v --no-cov` for faster development iteration

## Common Development Tasks

### Adding a New Port

1. Define Protocol in `rexlit/app/ports/your_port.py`
2. Create adapter in `rexlit/app/adapters/your_adapter.py`
3. Wire in `rexlit/bootstrap.py`
4. Update importlinter contracts if needed

### Adding a New CLI Command

1. Add command to `rexlit/cli.py` using Typer
2. Use `bootstrap.create_container()` for dependencies
3. Commands should only call application services, never domain modules directly
4. Add audit logging for significant operations

### Working with Deterministic Processing

Always use `deterministic_sort_paths()` or `deterministic_sort()` from `rexlit.utils.deterministic` when processing files or records. This ensures reproducible outputs required for legal defensibility.

## Code Style

- Line length: 100 characters (enforced by Black and Ruff)
- Python 3.11+ with full type annotations (mypy strict mode)
- Docstrings: Google style preferred
- Import order: stdlib, third-party, local (isort via Ruff)

## Security Considerations

- **Path Traversal**: Always use `resolve_safe_path()` when handling user-provided paths
- **Symlinks**: Follow only if explicitly allowed and validated against root boundary
- **Online Mode**: Network operations must check `require_online()` gate
- **Audit Trail**: Log all significant operations with SHA-256 hash chain
- **Secrets**: Never commit secrets; use environment variables

## Documentation

- `README.md` - Project overview, installation, quick start
- `ARCHITECTURE.md` - Detailed system design and components
- `CLI-GUIDE.md` - Complete CLI command reference
- `SECURITY.md` - Security posture and threat model
- `docs/adr/` - Architecture Decision Records
- `EXECUTIVE-SUMMARY.md` - High-level project status
