# RexLit Codebase Overview

**Last Updated:** November 13, 2025  
**Version:** v0.2.0-m1 (Phase 2 Complete)

---

## Quick Start: Understand RexLit in 5 Minutes

**What is RexLit?**

An offline-first litigation toolkit for e-discovery. It handles the complete document workflow:
1. **Ingest**: Streaming import from PDFs, DOCX, emails
2. **Index**: Full-text search with Tantivy (100K+ docs in 4–6 hours)
3. **Review**: Privilege classification with pattern-based + LLM escalation
4. **Produce**: Bates stamping and DAT/Opticon exports
5. **Audit**: Tamper-evident SHA-256 ledger for legal defensibility

**Key Philosophy:**
- Offline-first by default (no network calls without explicit opt-in)
- Deterministic processing (same inputs → identical outputs, critical for legal defense)
- CLI-first, but with optional React web UI (v0.2.0-m1)
- Hexagonal architecture (ports & adapters, strict import rules)

---

## Directory Structure

### Root Level

```
/Users/benjaminginsberg/dev/rex/rex/
├── rexlit/              # Python CLI (core domain logic)
├── api/                 # TypeScript/Bun HTTP bridge
├── ui/                  # React/Vite frontend
├── tests/               # 146 integration & unit tests (100% passing)
├── docs/                # Architecture docs, ADRs
├── scripts/             # Helper scripts (setup, testing, benchmarking)
├── .claude/             # Claude Code context and sprints
├── README.md            # Project overview
├── ARCHITECTURE.md      # Detailed system design
├── CLAUDE.md            # Development guidelines
├── CLI-GUIDE.md         # CLI command reference
├── SECURITY.md          # Security posture
└── pyproject.toml       # Python project config
```

### Python CLI: `rexlit/`

**Purpose:** Core domain logic, offline-first processing, deterministic workflows.

```
rexlit/
├── cli.py                    # Typer CLI entry point (~400 lines)
├── bootstrap.py              # Dependency injection container
├── config.py                 # Pydantic settings (XDG Base Directory)
├── app/                      # Application layer (orchestration)
│   ├── m1_pipeline.py        # Main M1 workflow orchestrator
│   ├── privilege_service.py  # Privilege classification service
│   ├── redaction_service.py
│   ├── pack_service.py
│   ├── ports/                # Port interfaces (Protocols)
│   │   ├── ledger_port.py    # Audit logging interface
│   │   ├── ocr_port.py       # OCR interface
│   │   ├── bates_port.py     # Bates numbering interface
│   │   └── ... (8 ports total)
│   └── adapters/             # Concrete implementations
│       ├── privilege_patterns_adapter.py  # Fast pattern matching
│       ├── groq_privilege_adapter.py      # LLM via Groq
│       ├── openai_privilege_adapter.py    # LLM via OpenAI
│       └── ... (more adapters)
├── audit/                    # Audit ledger domain
│   ├── ledger.py             # SHA-256 hash-chained append-only log
│   └── model.py              # Pydantic models
├── index/                    # Tantivy search index
│   ├── build.py              # Parallel indexing with ProcessPoolExecutor
│   ├── search.py             # Query interface
│   └── metadata.py           # O(1) metadata cache
├── ingest/                   # Document discovery and extraction
│   ├── discover.py           # Streaming document discovery
│   └── extract.py            # PDF/DOCX/email text extraction
├── agent/                    # LLM orchestration
│   └── privilege_agent.py    # Chain-of-thought for privilege
├── ocr/                      # OCR providers
│   └── tesseract_adapter.py  # Tesseract integration
├── pdf/                      # PDF manipulation
│   └── bates.py              # Bates stamping logic
├── rules/                    # TX/FL civil procedure deadlines
│   ├── tx_rules.py
│   └── fl_rules.py
├── ediscovery/               # Production exports
│   ├── dat.py                # DAT load file generation
│   └── opticon.py            # Opticon format export
└── utils/                    # Shared utilities
    ├── deterministic.py      # Deterministic sorting (critical for reproducibility)
    ├── offline.py            # Online mode gate
    └── jsonl.py              # JSONL operations
```

**Key Files to Understand Privilege Classification:**

1. `rexlit/cli.py` — Commands for `privilege classify`, `privilege explain`, `privilege policy list/get/apply`
2. `rexlit/app/privilege_service.py` — Three-stage pipeline orchestrator
3. `rexlit/app/adapters/privilege_patterns_adapter.py` — Pattern matching (offline, fast)
4. `rexlit/app/adapters/groq_privilege_adapter.py` — LLM escalation (Groq API)
5. `rexlit/app/agents/privilege_agent.py` — Chain-of-thought reasoning

### TypeScript API: `api/`

**Purpose:** HTTP bridge between React frontend and Python CLI. CLI-as-API pattern.

```
api/
├── index.ts                  # Elysia REST API (~500 lines)
│   ├── POST /api/search
│   ├── GET /api/documents/:hash/meta
│   ├── GET /api/documents/:hash/file
│   ├── GET /api/reviews/:hash
│   ├── POST /api/reviews/:hash
│   ├── POST /api/privilege/classify
│   ├── POST /api/privilege/explain
│   ├── GET /api/privilege/policy/list
│   ├── GET /api/privilege/policy/:stage
│   ├── POST /api/privilege/policy/:stage
│   ├── POST /api/privilege/policy/validate/:stage
│   ├── GET /api/stats
│   └── GET /api/health
├── package.json
├── tsconfig.json
└── [No sub-modules; everything in index.ts for simplicity]
```

**Key Design Pattern:** Each endpoint calls `rexlit` CLI via `Bun.spawn()`, never duplicates logic.

### React UI: `ui/`

**Purpose:** Human-in-the-loop interface for search, review, and policy management.

```
ui/
├── src/
│   ├── App.tsx               # Main React component (761 lines, will be refactored)
│   ├── App.css               # Styling (10KB)
│   ├── main.tsx              # React entry point
│   ├── index.css             # Global styles
│   ├── api/
│   │   └── rexlit.ts         # TypeScript API client with type definitions
│   └── assets/               # Static assets
├── package.json              # React 19, Vite 7, TypeScript 5.9
├── vite.config.ts            # Vite config
└── tsconfig.json
```

**Current Features:**
- Search with full-text query
- Document preview (iframe, HTML-escaped)
- Privilege review with stage indicators, confidence, pattern matches
- Policy editor with 3-stage pipeline (Privilege, Responsiveness, Redaction)
- Audit trail (basic list, not yet prominent)

**Refactoring Plan:** See `ui/FRONTEND_DESIGN_BRIEF.md` for phased component extraction.

### Tests: `tests/`

**146 tests, 100% passing.** Organized by domain:

```
tests/
├── test_index.py                      # Indexing (parallel, metadata, search)
├── test_ingest.py                     # Document discovery and extraction
├── test_security_path_traversal.py    # 13 path traversal regression tests
├── test_privilege_*.py                # Privilege classification (patterns, LLM)
├── test_audit_*.py                    # Audit ledger and verification
├── test_ocr_tesseract.py              # OCR tests (optional, requires Tesseract)
├── test_bates_*.py                    # Bates stamping
├── test_rules_*.py                    # TX/FL deadline calculations
└── test_app_adapters.py               # Adapter integration tests
```

**Test Coverage:**
- Path traversal defense: 13 dedicated tests
- Deterministic processing: verified with multiple runs
- Privilege classification: unit + integration tests
- Audit trail: tamper-detection tests

---

## Architecture Highlights

### Hexagonal (Ports & Adapters) Pattern

```
CLI (rexlit/cli.py)
   ↓ depends on
Bootstrap (rexlit/bootstrap.py) [dependency wiring]
   ↓ creates
Application Services (rexlit/app/*.py)
   ↓ depends on
Port Interfaces (rexlit/app/ports/*.py) [Protocols]
   ↑ implemented by
Adapters (rexlit/app/adapters/*.py) [concrete implementations]
```

**Key Contracts:**
- CLI can ONLY import from `rexlit.app` (enforced by importlinter)
- Application services depend ONLY on port interfaces, never concrete adapters
- All dependency wiring in `bootstrap.py`
- Domain modules (audit, index, ingest, etc.) are fully decoupled

### Three-Stage Privilege Pipeline

1. **Stage 1: Pattern-Based Classification** (offline, fast, ≥85% confidence)
   - File: `rexlit/app/adapters/privilege_patterns_adapter.py`
   - Decision made without LLM call if high confidence

2. **Stage 2: LLM Escalation** (for uncertain cases, 50–84% confidence)
   - File: `rexlit/app/adapters/groq_privilege_adapter.py` or `openai_privilege_adapter.py`
   - Chain-of-thought reasoning hashed before audit logging (privacy-preserving)

3. **Stage 3: Redaction Planning** (future; placeholder in M1)
   - File: `rexlit/app/redaction_service.py`

### Offline-First Gate

```python
# In rexlit/utils/offline.py
def require_online():
    if not REXLIT_ONLINE:
        raise OfflineError("This operation requires network access. Set REXLIT_ONLINE=1.")
```

Any network operation must explicitly call `require_online()`. This makes it impossible to accidentally make network calls in an air-gapped environment.

### Deterministic Processing

**All file operations use deterministic sorting:**

```python
# In rexlit/utils/deterministic.py
def deterministic_sort_paths(paths: list[str]) -> list[str]:
    """Sort by (sha256_hash, path) tuple for reproducible outputs."""
    # Critical for legal defensibility
```

This ensures identical outputs across runs, which is essential for privilege log defensibility in court.

---

## Key Workflows

### 1. Search & Privilege Review (MVP in v0.2.0-m1)

```
User searches in UI
  ↓
API → rexlit index search --json
  ↓
API returns results (10 docs)
  ↓
User selects document
  ↓
API → rexlit privilege classify --json <hash>
  ↓
Pattern adapter (fast, offline) → 85%+ confidence? → Done
  ↓ else
LLM adapter (Groq) → chain-of-thought → decision
  ↓
UI displays: Classification, Confidence, Pattern Matches, Stage Status
  ↓
User clicks "Privileged" / "Not Privileged" / "Skip"
  ↓
API → rexlit audit log PRIVILEGE_DECISION …
  ↓
Decision logged with SHA-256 hash chain
```

### 2. Policy Management

```
User edits policy in Settings tab
  ↓
UI → POST /api/privilege/policy/:stage
  ↓
API → rexlit privilege policy apply --stage 1 < policy_text
  ↓
Policy written to ~/.config/rexlit/policies/
  ↓
UI → GET /api/privilege/policy/list
  ↓
UI displays list of stages with metadata (hash, version, modified time)
```

### 3. Audit Trail Verification

```
User clicks "Verify Chain" in Audit screen
  ↓
API → rexlit audit verify
  ↓
Ledger reads all events, verifies SHA-256 hash chain
  ↓
API returns: "✓ Chain is valid" or "✗ Chain broken at event #42"
```

---

## Configuration & Environment

### Environment Variables (Python)

```bash
# Offline-first gate
REXLIT_ONLINE=1                      # Enable network features (default: 0)

# Data directories (XDG Base Directory compliant)
REXLIT_HOME=~/.local/share/rexlit    # Data directory
REXLIT_CONFIG=~/.config/rexlit       # Config directory (policies, etc.)
REXLIT_CACHE=~/.cache/rexlit         # Cache directory

# Performance
REXLIT_WORKERS=6                     # Parallel workers (default: cpu_count - 1)

# API keys (for online mode)
GROQ_API_KEY=...                     # Groq LLM API
OPENAI_API_KEY=...                   # OpenAI LLM API
ISAACUS_API_KEY=...                  # Dense embeddings (future)
```

### Environment Variables (TypeScript API)

```bash
REXLIT_BIN=rexlit                    # Path to rexlit executable
REXLIT_HOME=~/.local/share/rexlit    # Must match Python config
PORT=3000                            # API listen port
```

---

## Testing & Development

### Running Tests

```bash
# Disable user-level pytest plugins for consistent runs
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# All tests
uv run pytest -v --no-cov

# Specific test file
uv run pytest tests/test_privilege_*.py -v

# With coverage
uv run pytest -v

# Security path traversal tests
uv run pytest tests/test_security_path_traversal.py -v
```

### Running the Full Stack Locally

```bash
# Terminal 1: Python CLI (optional, for testing CLI directly)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
# or: uv sync --extra dev
rexlit --help

# Terminal 2: TypeScript API
cd api
bun install
REXLIT_BIN=$(which rexlit) bun run index.ts
# API on http://localhost:3000

# Terminal 3: React UI
cd ../ui
npm install
npm run dev
# UI on http://localhost:5173
```

### Development Tools

```bash
# Type checking
mypy rexlit/ --strict

# Linting & formatting
ruff check .
black --check .

# Import rule enforcement (hexagonal arch validation)
lint-imports

# Benchmarking
python scripts/benchmark_metadata.py
python scripts/benchmark_idl.py --corpus medium --workers 6
```

---

## Important Files by Topic

### Understanding Privilege Classification

1. **Entry Point:** `rexlit/cli.py` → `privilege_classify()` function
2. **Service Orchestrator:** `rexlit/app/privilege_service.py`
3. **Pattern Matching:** `rexlit/app/adapters/privilege_patterns_adapter.py`
4. **LLM Integration:** `rexlit/app/adapters/groq_privilege_adapter.py`
5. **Chain-of-Thought:** `rexlit/app/agents/privilege_agent.py`
6. **Type Definitions:** `rexlit/app/models/privilege_models.py`

### Understanding Audit Trail

1. **Ledger Implementation:** `rexlit/audit/ledger.py` (SHA-256 hash chaining)
2. **Data Models:** `rexlit/audit/model.py` (Pydantic schemas)
3. **CLI Commands:** `rexlit/cli.py` → `audit_*()` functions
4. **Verification Logic:** `rexlit/audit/ledger.py` → `verify_chain()`

### Understanding Search & Indexing

1. **Search Entry:** `rexlit/cli.py` → `index_search()` function
2. **Index Builder:** `rexlit/index/build.py` (ProcessPoolExecutor, batching)
3. **Metadata Cache:** `rexlit/index/metadata.py` (O(1) lookups)
4. **Query Logic:** `rexlit/index/search.py`

### Understanding Web UI

1. **Main Component:** `ui/src/App.tsx` (761 lines, will be refactored)
2. **API Client:** `ui/src/api/rexlit.ts` (type definitions + fetch wrappers)
3. **Styling:** `ui/src/App.css` (10KB, blue SaaS default theme)
4. **Backend Bridge:** `api/index.ts` (Elysia routes, CLI-as-API pattern)

### Understanding Security

1. **Path Traversal Defense:** `rexlit/utils/deterministic.py` → `resolve_safe_path()`
2. **Security Tests:** `tests/test_security_path_traversal.py` (13 tests)
3. **API Security:** `api/index.ts` → `ensureWithinRoot()` function
4. **Offline Gate:** `rexlit/utils/offline.py` → `require_online()`

---

## Code Statistics

| Metric | Value |
|--------|-------|
| Python CLI LOC | ~3,500 (excluding tests) |
| TypeScript API LOC | ~500 |
| React UI LOC | ~1,200 (App.tsx alone: 761) |
| Test Coverage | 146 tests, 100% passing |
| Security Tests | 13 path traversal regression tests |
| Performance Benchmark | 100K docs indexed in 4–6 hours |

---

## Recent Changes (v0.2.0-m1)

1. **Privilege Classification Feature**
   - Pattern-based pre-filtering (fast, offline)
   - LLM escalation for uncertain cases (Groq/OpenAI)
   - Privacy-preserving audit (reasoning hashed before logging)

2. **Web UI & API Layer**
   - CLI-as-API pattern (subprocess wrapper, zero divergence)
   - React interface for search, review, policy editing
   - Security: Hash-based document access, path traversal protection

3. **Security Hardening**
   - Typed payload validation (eliminated `any` types)
   - Sanitized error responses (no filesystem info leakage)
   - Filtered pattern matches (no filesystem details exposed)
   - Timeout support for long-running operations

---

## Next Steps (Phase 3 / M2)

See `.claude/sprints/NEXT_PRIORITIES_DEEP_DIVE.md` for detailed roadmap:

1. **Redaction Planning** (RexLit-specific, not generic)
2. **Email Threading** (family grouping, conversation reconstruction)
3. **Advanced Analytics** (dedupe, custodian reports, proportionality metrics)
4. **UI Redesign** (see `ui/FRONTEND_DESIGN_BRIEF.md`)

---

## Documentation & Further Reading

- **`README.md`** — Project overview, installation, quick start
- **`ARCHITECTURE.md`** — Detailed system design
- **`CLI-GUIDE.md`** — Complete CLI command reference
- **`SECURITY.md`** — Security posture and threat model
- **`CLAUDE.md`** — Development guidelines (this file)
- **`ui/FRONTEND_DESIGN_BRIEF.md`** — Frontend redesign roadmap (NEW)
- **`docs/adr/`** — Architecture Decision Records (ADR 0001–0009)
- **`.claude/code-reviews/`** — Code review notes
- **`.claude/sprints/`** — Sprint planning and roadmaps

---

## Questions? 

If anything is unclear, check:

1. The relevant ADR in `docs/adr/`
2. The CLI-GUIDE in `CLI-GUIDE.md`
3. The actual code (it's well-commented and type-annotated)
4. The test files (they show usage patterns)

RexLit is designed to be readable and defensible. Every decision is documented.
