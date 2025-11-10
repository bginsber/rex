# RexLit Codebase - Quick Reference

## Project Status at a Glance

- **Phase:** 2 (M1) Complete, 3 (M2) In Planning
- **Total Python Code:** 13,259 lines
- **Test Coverage:** 130 collected tests, 146 passing (100%)
- **Architecture:** Hexagonal with strict import contracts (enforced via importlinter)

---

## Key Directory Structure

```
rexlit/
├── cli.py                  # CLI entry point (Typer)
├── bootstrap.py            # Dependency injection wiring
├── config.py              # Settings management
│
├── app/                   # Application layer
│   ├── m1_pipeline.py     # Main orchestration
│   ├── pack_service.py    # Production artifact generation
│   ├── redaction_service.py # PII redaction
│   ├── privilege_service.py # LLM + pattern-based privilege classification
│   ├── report_service.py  # Impact reports & methods appendix
│   ├── audit_service.py   # Ledger access
│   ├── ports/             # 18 port interfaces (DiscoveryPort, IndexPort, etc.)
│   └── adapters/          # 20+ adapter implementations
│
├── ingest/                # Document discovery & extraction
│   ├── discover.py        # Streaming filesystem walk (O(1) memory)
│   └── extract.py         # PDF/DOCX/TXT text extraction
│
├── index/                 # Tantivy search & dense retrieval
│   ├── build.py           # Parallel indexing (ProcessPoolExecutor)
│   ├── search.py          # Lexical + dense + hybrid search
│   ├── metadata.py        # O(1) custodian/doctype cache
│   ├── kanon2_embedder.py # Kanon 2 API integration (online)
│   └── hnsw_store.py      # Vector search
│
├── audit/                 # Append-only ledger
│   └── ledger.py          # SHA-256 hash chain with tampering detection
│
├── ocr/                   # OCR framework
│   └── (Tesseract adapter in app/adapters/)
│
├── rules/                 # Civil procedure deadline engine
│   ├── engine.py          # TX/FL rule evaluation
│   └── export.py          # ICS calendar generation
│
├── pdf/                   # PDF manipulation
│   └── (Stamping adapter in app/adapters/)
│
├── ediscovery/            # Production & PII management
│   └── pii_storage.py     # Encrypted vault for sensitive data
│
├── agent/                 # AI integration (placeholder for M2)
│
└── utils/                 # Shared utilities
    ├── deterministic.py   # Stable sorting (critical for reproducibility)
    ├── offline.py         # Network gate enforcement
    ├── paths.py           # Path traversal defense
    ├── jsonl.py           # Atomic JSONL operations
    └── ... (10+ more utility modules)
```

---

## Core Architecture Patterns

### Hexagonal (Ports & Adapters)

```
CLI → Bootstrap → Services (depend on Ports) → Adapters (implement Ports) → External Systems
```

**Key principle:** Services depend ONLY on abstract Ports, never concrete Adapters. All wiring happens in `bootstrap.py`.

### Three Critical Design Decisions (ADRs)

1. **Offline-First (ADR 0001):** Network features require `--online` flag or `REXLIT_ONLINE=1`
2. **Import Contracts (ADR 0002):** Enforced by `importlinter` in CI
3. **Determinism (ADR 0003):** Files sorted by `(sha256_hash, path)` for reproducibility

### CLI-as-API Pattern (ADR 0009)

```
React UI → Elysia API (35 lines) → subprocess calls to rexlit CLI → Filesystem
```

**Benefit:** API and CLI can never diverge because they call the exact same functions.

---

## M1 (Phase 2) Feature Summary

### Complete Features

| Feature | Key Files | Performance |
|---------|-----------|-------------|
| **Document Discovery** | `ingest/discover.py` | O(1) memory, streaming |
| **Full-Text Indexing** | `index/build.py` | 100K docs in 4-6 hrs (20× faster) |
| **BM25 Search** | `index/search.py` | <50ms for 100K docs |
| **Metadata Cache** | `index/metadata.py` | <10ms lookup (1000× faster than scan) |
| **OCR (Tesseract)** | `app/adapters/tesseract_ocr.py` | 2-5s/page, smart preflight |
| **Bates Stamping** | `app/adapters/pdf_stamper.py` | Layout-aware, deterministic |
| **Rules Engine** | `rules/engine.py` | TX/FL deadlines + ICS export |
| **Privilege Classification** | `app/privilege_service.py` | Pattern + Groq/OpenAI LLM |
| **Dense Search** | `index/kanon2_embedder.py` | Kanon 2 embeddings (optional, online) |
| **Audit Trail** | `audit/ledger.py` | SHA-256 hash chain with tampering detection |
| **Reports** | `app/report_service.py` | Impact + Methods appendix |
| **Web UI** | `api/` + `ui/` | React search + privilege decisions |

### Partial/Planned Features

| Feature | Status | Est. Effort |
|---------|--------|-------------|
| **Redaction** | 40% (interfaces defined) | 2 weeks |
| **Email Threading** | 0% (placeholder) | 3 weeks |
| **Claude Integration** | 0% (placeholder) | 2-3 weeks |
| **PaddleOCR** | 0% (placeholder) | 2 weeks |

---

## Port Interfaces (18 total)

Key ports in `rexlit/app/ports/`:

- `DiscoveryPort` - Document enumeration
- `IndexPort` - Search & indexing
- `StoragePort` - Filesystem I/O
- `LedgerPort` - Audit logging
- `OCRPort` - Document OCR
- `BatesPlannerPort` - Bates sequencing
- `StampPort` - PDF stamping
- `PackPort` - Artifact packaging
- `PrivilegePort` - Privilege classification
- `PIIPort` - PII detection
- `EmbeddingPort` - Dense embeddings (Kanon 2)
- `VectorStorePort` - Vector search (HNSW)
- `DeduperPort` - Document deduplication
- ... and 5 more

---

## Adapter Implementations (20+ total)

Key adapters in `rexlit/app/adapters/`:

- `IngestDiscoveryAdapter` - Streaming filesystem walk
- `TantivyIndexAdapter` - Full-text indexing
- `FileSystemStorageAdapter` - Atomic writes
- `TesseractOCRAdapter` - OCR wrapper
- `SequentialBatesPlanner` - Deterministic numbering
- `PDFStamperAdapter` - PDF manipulation
- `ZipPackager` - Artifact creation
- `GroqPrivilegeAdapter` - Groq LLM calls
- `Kanon2Adapter` - Embeddings API
- `HNSWAdapter` - Vector search
- `PrivilegePatternsAdapter` - Regex-based detection
- `PIIRegexAdapter` - PII regex patterns
- ... and 8+ more

---

## Testing Overview

### Test Framework
- **Framework:** pytest 8.3.0+
- **Coverage:** pytest-cov with term-missing
- **Commands:**
  ```bash
  pytest -v --no-cov                                  # Fast
  pytest -v                                           # With coverage
  pytest tests/test_security_path_traversal.py -v     # Security
  pytest tests/test_ocr_tesseract.py -v               # OCR
  ```

### Test Categories

- **Security (22+ tests):** Path traversal, audit chain, encryption
- **Core (70+ tests):** Ingest, index, search, audit
- **Production (30+ tests):** OCR, Bates, rules, reports
- **Advanced (20+ tests):** Privilege, dense search, redaction
- **Miscellaneous (15+ tests):** Config, sanitization, detection

---

## Web Layer (NEW in M1)

### API (Bun + Elysia)

**File:** `api/index.ts` (157 lines)

**Endpoints:**
- `POST /api/search` - Full-text search
- `GET /api/documents/:hash/meta` - Document metadata
- `GET /api/documents/:hash/file` - Document content
- `POST /api/reviews/:hash` - Record privilege decision
- `GET /api/stats` - Index statistics
- `GET /api/health` - Health check

**Security:** Path traversal defense via `ensureWithinRoot()`

### UI (React + Vite)

**Files:**
- `ui/src/App.tsx` - Search + privilege review interface
- `ui/src/api/rexlit.ts` - API client

**Features:**
- Full-text search with result listing
- Document viewer (HTML + iframe)
- Privilege decision recording
- Statistics panel

---

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `REXLIT_HOME` | `~/.local/share/rexlit` | Data directory |
| `REXLIT_WORKERS` | `cpu_count() - 1` | Parallel workers |
| `REXLIT_BATCH_SIZE` | 100 | Docs per batch |
| `REXLIT_ONLINE` | false | Enable network features |
| `REXLIT_LOG_LEVEL` | INFO | Logging level |
| `ISAACUS_API_KEY` | (required) | Kanon 2 token (dense search) |

### Directory Layout

```
~/.local/share/rexlit/
├── index/              # Tantivy index
│   ├── .metadata_cache.json
│   └── dense/          # Optional HNSW indices
├── audit/log.jsonl     # SHA-256 chain ledger
├── manifest.jsonl      # Document metadata
└── productions/        # DAT/Opticon exports
```

---

## Performance Benchmarks

| Operation | Scale | Time | Notes |
|-----------|-------|------|-------|
| Ingest | 100K docs | <10 min | Streaming |
| Index build | 100K docs | 4-6 hrs | 20× baseline |
| Search | 100K docs | <50ms | Tantivy BM25 |
| Metadata lookup | 100K docs | <10ms | Cached |
| Dense search | 100K docs | 2-5s | API + HNSW |
| Bates stamping | 1K PDFs | ~5 min | Per-PDF |
| OCR | 300 DPI page | 2-5s | Tesseract |

---

## Key Dependencies

**Core:**
- typer (CLI)
- pydantic (config)
- tantivy (search)
- pymupdf (PDF)
- cryptography (encryption)
- hnswlib (vector search)

**Optional (OCR):**
- pytesseract
- paddleocr

**Optional (Email):**
- extract-msg
- mail-parser

**Optional (AI):**
- anthropic (Claude)
- openai (GPT)

---

## Known Gaps (M2 Planning)

1. **Redaction (High):** PII detection + plan/apply workflow (40% done)
2. **Email Analytics (Medium):** Threading, custodian graph (0% done)
3. **Claude Integration (Medium):** Privilege reasoning (0% done)
4. **PaddleOCR (Low):** Multi-language support (0% done)

---

## Code Quality

- **Type Checking:** mypy strict mode
- **Linting:** ruff + black
- **Architecture:** importlinter enforces contracts
- **Tests:** pytest with 100% pass rate
- **Docstrings:** Google style, complete
- **Comments:** Minimal, high-signal (critical sections only)

---

## Documentation

**Excellent:**
- ✅ README.md
- ✅ ARCHITECTURE.md
- ✅ CLI-GUIDE.md
- ✅ SECURITY.md
- ✅ ADRs (0001-0009)

**Needed:**
- API documentation (Swagger)
- Deployment guide (Docker)
- Performance tuning guide

---

## Quick Start

### CLI

```bash
# Ingest documents
rexlit ingest ./docs --manifest out/manifest.jsonl

# Build index
rexlit index build ./docs --index-dir out/index

# Search
rexlit index search "privileged AND contract" --limit 20

# Verify audit
rexlit audit verify --ledger out/audit/log.jsonl
```

### Web UI

```bash
# Terminal 1: API
cd api && REXLIT_HOME=~/.local/share/rexlit bun run index.ts

# Terminal 2: UI
cd ui && VITE_API_URL=http://localhost:3000/api bun dev
```

---

## File Locations

- **Full Analysis:** `/Users/bg/Documents/Coding/rex/CODEBASE_ANALYSIS.md` (882 lines)
- **This Quick Ref:** `/Users/bg/Documents/Coding/rex/CODEBASE_QUICK_REFERENCE.md`

---

**Last Updated:** November 8, 2025
**Next Review:** After M2 phase completion
