# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RexLit is an offline-first UNIX litigation toolkit for secure discovery, indexing, and audit-ready document processing. It's designed for legal e-discovery workflows where network access may be restricted, legal defensibility requires deterministic processing, and tamper-evident audit trails are essential.

**Current Status:** Phase 1 (M0) complete, Phase 2 (M1) complete, Phase 3 (M2) in planning

**Latest Releases:**
- **v0.2.0-m1**: Web UI (Bun/Elysia API + React), privilege classification, security fixes
- **Tests:** 146/146 passing (100% compliance) with expanded coverage for new features

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
# Run all tests (146 tests, expect 100% passing)
pytest -v --no-cov

# Run with coverage
pytest -v

# Run specific test suite
pytest tests/test_index.py -v
pytest tests/test_security_path_traversal.py -v
pytest tests/test_app_adapters.py -v
pytest tests/test_ocr_tesseract.py -v

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

### Web UI & API (Bun/Elysia/React)
```bash
# API Server (Bun + Elysia)
cd api
bun install
REXLIT_BIN=$(which rexlit) bun run index.ts
# API runs on http://localhost:3000, wraps rexlit CLI via subprocess

# React UI (Vite)
cd ../ui
npm install  # or bun install
npm run dev  # or bun dev
# UI runs on http://localhost:5173
```

The API uses a "CLI-as-API" pattern: TypeScript wraps the Python CLI via subprocess, ensuring zero divergence between CLI and web UI behavior. See `docs/UI_ARCHITECTURE.md` for details.

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
RexLit Monorepo (Python CLI + TypeScript Web Layer)

rexlit/                # Python CLI (core domain logic)
├── cli.py              # CLI entry point (Typer-based)
├── config.py           # Pydantic settings with XDG support
├── bootstrap.py        # Dependency wiring
├── app/                # Application layer
│   ├── m1_pipeline.py     # Main M1 orchestration
│   ├── privilege_service.py  # Privilege classification orchestrator
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
├── agent/              # LLM orchestration for privilege classification
├── utils/              # Shared utilities
│   ├── deterministic.py   # Deterministic sorting helpers
│   ├── offline.py         # Online mode gate
│   └── jsonl.py           # JSONL operations
├── ocr/                # OCR providers (Tesseract)
├── pdf/                # PDF manipulation (Bates stamping)
├── rules/              # TX/FL civil procedure deadline rules
└── ediscovery/         # Production exports (DAT/Opticon)

api/                   # TypeScript Web API (Bun + Elysia)
├── index.ts            # REST API endpoints (search, documents, reviews)
├── package.json        # Bun dependencies (elysia, cross-fetch)
└── [wraps rexlit CLI via subprocess for zero divergence]

ui/                    # React Web UI (Vite)
├── src/
│   ├── App.tsx         # Main React component
│   ├── components/     # UI components
│   └── styles/         # CSS/Tailwind
├── package.json
└── vite.config.ts

tests/                 # Python test suite (146 tests)
docs/                  # Documentation and ADRs
└── adr/               # Architecture Decision Records
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

## Monorepo Structure & Component Interaction

RexLit is organized as a **Python-first monorepo** with a TypeScript web layer:

### Component Responsibilities

1. **Python CLI** (`rexlit/`) - Core domain logic
   - Offline-first, deterministic, legally defensible processing
   - Imports strictly enforced via `importlinter`
   - All business logic (discovery, indexing, OCR, Bates, privilege, audit)
   - Self-contained: runs offline by default

2. **Bun/Elysia API** (`api/`) - HTTP bridge
   - Wraps the Python CLI via subprocess (CLI-as-API pattern)
   - Zero divergence between CLI and web UI (same code paths)
   - Endpoints: `/api/search`, `/api/documents/:hash/file`, `/api/reviews/:hash`
   - Security: Hash-based document access, no path traversal vulnerabilities
   - **Never** duplicates CLI logic; always delegates to rexlit CLI

3. **React UI** (`ui/`) - Human-in-the-loop interface
   - Search, document viewing, privilege decision recording
   - Communicates with API, which calls Python CLI
   - Zero backend logic: all computation stays in Python

### Data Flow

```
User → React UI → Bun API → rexlit CLI → Domain Modules
                 (subprocess)      ↓
                                Audit Log
```

**Critical constraint:** The Bun API must NEVER duplicate CLI functionality. It acts only as a request router to the Python subprocess.

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

- **146 integration and unit tests** (100% passing required)
  - Python CLI: 130+ tests (ingest, index, OCR, Bates, rules, privilege, audit)
  - Web API: Bun/TypeScript integration tests
- **Security**: 13 path traversal regression tests + document endpoint access control
- **Performance**: `benchmark_metadata.py` for metadata cache validation
- **Determinism**: Verify identical outputs across multiple runs
- **Use `pytest -v --no-cov`** for faster development iteration

### Web API Testing (Node/Bun)

If adding tests for the API layer:
```bash
cd api
bun test  # Bun's native test runner
```

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

### Extending Privilege Classification

The privilege pipeline is modular with three stages:

1. **Pattern-based filtering** (fast, offline, ≥85% confidence → skip LLM)
   - File: `rexlit/app/adapters/privilege_patterns_adapter.py`
   - Add patterns in port method signatures

2. **LLM escalation** (uncertain cases, 50-84% confidence)
   - File: `rexlit/app/adapters/groq_privilege_adapter.py` (Groq) and `openai_privilege_adapter.py`
   - Chain-of-thought reasoning hashed before audit logging (privacy-preserving)

3. **Orchestration**
   - File: `rexlit/app/privilege_service.py`
   - Routes documents through pipeline stages

To add a new adapter:
1. Implement the `PrivilegePort` protocol
2. Wire in `rexlit/bootstrap.py` (strategy pattern based on config)
3. Add tests in `tests/test_privilege_*.py`

### Adding a Web API Endpoint

The API uses "CLI-as-API" pattern: never duplicate CLI logic.

1. Add endpoint in `api/index.ts`
2. Endpoint calls `execSync()` to shell out to `rexlit` CLI
3. Parse CLI output (JSON or structured text)
4. Return as REST response

Example:
```typescript
app.get("/api/my-endpoint", async () => {
  const result = execSync("rexlit my-command --json", { encoding: "utf-8" });
  return Response.json(JSON.parse(result));
});
```

Then update the React UI in `ui/src/App.tsx` to consume the new endpoint.

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

## Key Recent Updates

### Security Fix (v0.2.0-m1)
- **Vulnerability fixed**: Arbitrary file read in `/api/documents/:hash/file` endpoint
- **Issue**: Endpoint was trusting user-controlled `path` query parameter instead of validating against index
- **Fix**: Now relies on Tantivy index as authoritative source; path parameter ignored
- **Impact**: Essential for safe web UI deployment; prevents unauthorized document access

### Privilege Classification Feature (v0.2.0-m1)
- **Pattern-based pre-filtering**: Fast, offline, ≥85% confidence → skip LLM costs
- **LLM escalation**: Groq/OpenAI integration for uncertain cases (50-84% confidence)
- **Privacy-preserving audit**: Chain-of-thought reasoning hashed before logging
- **EDRM compliance**: Privilege log format validated against protocol standards
- **See**: `rexlit/app/privilege_service.py`, `rexlit/app/adapters/privilege_*.py`

### Web UI & API Layer (v0.2.0-m1)
- **CLI-as-API pattern**: API wraps Python CLI via subprocess, zero divergence
- **React interface**: Search, document viewer, privilege decision recording
- **Security**: Hash-based document access, root-bound path resolution
- **See**: `api/index.ts`, `ui/src/App.tsx`, `docs/UI_ARCHITECTURE.md`

## Documentation

- `README.md` - Project overview, installation, quick start
- `ARCHITECTURE.md` - Detailed system design and components
- `CLI-GUIDE.md` - Complete CLI command reference
- `SECURITY.md` - Security posture and threat model
- `docs/adr/` - Architecture Decision Records
  - `0008-privilege-log-protocol.md` - EDRM privilege logging
  - `0009-cli-as-api-pattern.md` - Web API architecture
- `docs/UI_*.md` - Web UI architecture and security documentation
- `.claude/code-reviews/CODEBASE_ANALYSIS.md` - Comprehensive 13K+ line code overview
- `.claude/code-reviews/CODEBASE_QUICK_REFERENCE.md` - Quick navigation guide
- `.claude/sprints/NEXT_PRIORITIES_DEEP_DIVE.md` - Phase 3 (M2) roadmap and priorities
- `.claude/summaries/EXECUTIVE-SUMMARY.md` - High-level project status
