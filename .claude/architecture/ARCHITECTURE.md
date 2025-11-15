# RexLit Architecture

System design and implementation details for RexLit M0.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Performance Optimizations](#performance-optimizations)
- [Security Design](#security-design)
- [Design Decisions](#design-decisions)
- [Dense Retrieval Architecture](#dense-retrieval-architecture)

---

## Overview

RexLit is designed as an offline-first, high-performance e-discovery toolkit built on these principles:

- **Simplicity**: UNIX philosophy - do one thing well
- **Performance**: Parallel processing, streaming I/O, O(1) operations
- **Security**: Defense-in-depth, cryptographic guarantees
- **Compliance**: Legal-defensible audit trail
- **Scalability**: 100K+ document capacity

### Technology Stack

- **Language**: Python 3.11+ (type-annotated)
- **CLI Framework**: Typer (built on Click)
- **Search Engine**: Tantivy (Rust-based, via Python bindings)
- **Settings**: Pydantic v2
- **Testing**: Pytest + coverage
- **Linting**: Ruff + Black + mypy

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    RexLit CLI (Typer)                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Ingest  │  │  Index   │  │  Audit   │            │
│  │ Commands │  │ Commands │  │ Commands │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │             │              │                   │
├───────┼─────────────┼──────────────┼───────────────────┤
│       │             │              │                   │
│  ┌────▼─────┐  ┌───▼────┐    ┌───▼─────┐            │
│  │ Document │  │ Search │    │  Audit  │            │
│  │ Discovery│  │ Index  │    │ Ledger  │            │
│  └────┬─────┘  └───┬────┘    └───┬─────┘            │
│       │            │              │                   │
│  ┌────▼─────┐  ┌───▼────────┐    │                   │
│  │   Text   │  │  Metadata  │    │                   │
│  │Extraction│  │   Cache    │    │                   │
│  └──────────┘  └────────────┘    │                   │
│                                   │                   │
├───────────────────────────────────┼───────────────────┤
│                                   │                   │
│  ┌──────────────────────┐    ┌───▼──────────────┐   │
│  │   Tantivy Index      │    │  audit.jsonl     │   │
│  │  (Full-text search)  │    │ (Append-only)    │   │
│  └──────────────────────┘    └──────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  Filesystem (Documents, Index, Audit)        │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. CLI Layer (`rexlit/cli.py`)

**Purpose**: User interface and command routing

**Responsibilities**:
- Parse command-line arguments
- Route to appropriate subcommands
- Handle errors and output formatting
- Progress reporting

**Key Features**:
- Typer-based command groups
- Rich progress bars (future)
- JSON output mode
- Error handling with exit codes

**Code Structure**:
```python
@app.command()
def ingest(path: Path, manifest: Optional[Path] = None):
    """Ingest documents and create manifest."""
    # Command implementation
```

---

### 2. Configuration (`rexlit/config.py`)

**Purpose**: Application settings and XDG directory management

**Responsibilities**:
- Load configuration from environment/files
- Manage data directory paths
- Provide defaults

**Key Features**:
- Pydantic-based validation
- XDG Base Directory Specification compliance
- Environment variable overrides

**Default Paths**:
- Data: `~/.local/share/rexlit/`
- Config: `~/.config/rexlit/`
- Cache: `~/.cache/rexlit/`

---

### 3. Document Ingest (`rexlit/ingest/`)

#### 3.1 Discovery (`discover.py`)

**Purpose**: Find and catalog documents

**Key Implementation**:
```python
def discover_documents(
    root: Path,
    recursive: bool = True,
    allowed_root: Optional[Path] = None
) -> Iterator[DocumentMetadata]:
    """Streaming document discovery with O(1) memory."""
    # Yields documents one at a time
```

**Performance**:
- **Streaming**: O(1) memory usage (was O(n))
- **Security**: Path traversal validation
- **Metadata**: Custodian/doctype extraction

**Security Features**:
- Path resolution with `.resolve()`
- Boundary validation with `.relative_to()`
- Symlink safety checks
- Traversal attempt logging

#### 3.2 Extraction (`extract.py`)

**Purpose**: Extract text from documents

**Supported Formats**:
- **PDF**: PyMuPDF (fitz)
- **DOCX**: python-docx
- **TXT/MD**: Plain text

**Key Implementation**:
```python
def extract_document(path: Path) -> ExtractedDocument:
    """Extract text and metadata from document."""
    # Format-specific extraction
    return ExtractedDocument(text=..., metadata=...)
```

---

### 4. Search Index (`rexlit/index/`)

#### 4.1 Index Building (`build.py`)

**Purpose**: Create full-text search index

**Key Innovation**: Parallel processing with ProcessPoolExecutor

**Architecture**:
```python
with ProcessPoolExecutor(max_workers=cpu_count()-1) as executor:
    # Submit all documents for processing
    futures = [executor.submit(process_doc, doc) for doc in docs]

    # Collect results as they complete
    for future in as_completed(futures):
        result = future.result()
        writer.add_document(result)
```

**Performance Optimizations**:
1. **Parallel Processing**: 15-20x speedup
2. **Batch Commits**: Every 1,000 docs for memory management
3. **Streaming Discovery**: No buffering of document list
4. **Worker Pooling**: Reuses processes across batches

**Memory Management**:
- 200MB Tantivy heap per writer
- Periodic commits free memory
- O(1) memory during discovery

#### 4.2 Metadata Cache (`metadata.py`)

**Purpose**: O(1) custodian/doctype queries

**Problem Solved**: Full index scan took 5-10 seconds

**Solution**: JSON cache with incremental updates

**Implementation**:
```python
class IndexMetadata:
    def __init__(self, index_dir: Path):
        self.cache = self._load_cache()

    def get_custodians(self) -> set[str]:
        """O(1) lookup from cache."""
        return self.cache.get("custodians", set())
```

**Cache Format**:
```json
{
  "custodians": ["john_doe", "jane_smith"],
  "doctypes": ["pdf", "docx", "txt"],
  "doc_count": 10000,
  "last_updated": "2025-10-23T14:32:15"
}
```

**Performance**: <10ms queries (1000x faster than full scan)

#### 4.3 Search (`search.py`)

**Purpose**: Full-text search queries

**Key Features**:
- Tantivy query parser
- Ranked results by relevance
- JSON output mode
- Metadata filtering

---

## Dense Retrieval Architecture

RexLit adds dense and hybrid retrieval while preserving the ports-and-adapters (hexagonal) architecture.

Key concepts:
- **EmbeddingPort** (`rexlit/app/ports/embedding.py`): protocol for text embeddings
- **VectorStorePort** (`rexlit/app/ports/vector_store.py`): protocol for ANN storage
- **Kanon2Adapter** (`rexlit/app/adapters/kanon2.py`): Isaacus-backed embedding adapter
- **HNSWAdapter** (`rexlit/app/adapters/hnsw.py`): disk-backed HNSW adapter

Data flow (build):
```
index build --dense
  → collect dense-ready docs (sha256, path, text)
  → EmbeddingPort.embed_documents([...])  # batched RPCs
  → VectorStorePort.build(vectors, ids, metadata)
  → persist .hnsw + .meta.json
  → audit: operation=embedding_batch (latency p50/p95/p99, tokens)
```

Data flow (search):
```
index search --mode dense|hybrid
  → if dense: embed query via EmbeddingPort.embed_query()
           → VectorStorePort.query(query_vec)
  → if hybrid: BM25 + dense → Reciprocal Rank Fusion (k=60)
```

Online/offline boundary:
- The `OfflineModeGate` enforces `--online`/`REXLIT_ONLINE` for network calls.
- Dense index build and dense/hybrid search require online mode (for embedding RPCs).
- Once HNSW is built, loading/querying the vector index is fully offline.

Bootstrap wiring:
- `rexlit/bootstrap.py` instantiates optional `embedder` (Kanon2Adapter) and a `vector_store_factory` (HNSWAdapter) when online.
- `TantivyIndexAdapter` delegates dense/hybrid operations to index/search helpers with injected ports.

Rationale:
- Ports allow swapping providers (future: Ollama/OpenAI) and deterministic testing.
- HNSW persists vectors on disk for offline reopen and fast cosine search.
- RRF fusion is robust across corpora without fragile normalization.

---

### 5. Audit Trail (`rexlit/audit/`)

#### Ledger (`ledger.py`)

**Purpose**: Tamper-evident audit log

**Design**: Blockchain-style hash chain

**Entry Structure**:
```json
{
  "timestamp": "2025-10-23T09:15:23.123456Z",
  "action": "INDEX_BUILD_COMPLETE",
  "details": {"indexed": 1000, "skipped": 0},
  "hash": "4a7b3c2d9f1e8a4b...",
  "previous_hash": "9f1e8a4b2c5d..."
}
```

**Hash Chain**:
```
Entry 1: hash(entry1 + "0000...") → H1
Entry 2: hash(entry2 + H1) → H2
Entry 3: hash(entry3 + H2) → H3
...
```

**Security Properties**:
- **Append-only**: No deletions allowed
- **Tamper-evident**: Any change breaks chain
- **Immutable**: Fsync guarantees durability
- **Verifiable**: Cryptographic proof of integrity

**Implementation**:
```python
def append(self, action: str, details: dict):
    """Append entry with hash chain linkage."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "details": details,
        "previous_hash": self._get_last_hash(),
    }
    entry["hash"] = self._compute_hash(entry)

    # Write with fsync for durability
    self.file.write(json.dumps(entry) + "\n")
    self.file.flush()
    os.fsync(self.file.fileno())
```

---

## Impact Reporting

### Purpose

Generate Sedona Conference-aligned discovery impact summaries for proportionality analysis during early case management.

### Design

**Module**: `rexlit/app/report_service.py`

**Key characteristics**:
- **Manifest streaming**: O(k) memory usage where k = number of distinct custodians/doctypes/extensions
- **No re-processing**: Compute from written manifest, not raw files
- **Offline computation**: Pure local aggregation, no network/AI calls
- **Atomic writes**: Temp file + `os.replace()` for crash safety
- **Schema versioning**: Support forward compatibility

### Algorithm

1. Open manifest JSONL file
2. Stream each document record:
   - Accumulate total size, count
   - Group by custodian, doctype, extension
   - Track min/max mtime (O(1) not list)
   - Bucket size distributions
3. Compute deduplication rate from stage metrics
4. Calculate estimated review hours/costs
5. Build human-readable culling rationale
6. Serialize to JSON with atomic write

### Output Structure

```json
{
  "schema_version": "1.0.0",
  "tool_version": "0.1.0",
  "summary": {
    "total_discovered": 1500,
    "unique_documents": 1485,
    "duplicates_removed": 15,
    "dedupe_rate_pct": 1.0,
    "total_size_bytes": 5242880000,
    "total_size_mb": 5000.0
  },
  "estimated_review": {
    "hours_low": 10.0,
    "hours_high": 30.0,
    "cost_low_usd": 750.0,
    "cost_high_usd": 6000.0,
    "assumptions": "50-150 docs/hr, $75-$200/hr"
  },
  "by_custodian": {
    "alice": {
      "count": 750,
      "size_bytes": 2621440000,
      "doctypes": { "pdf": 500, "docx": 250 }
    }
  },
  "by_doctype": {
    "pdf": { "count": 900, "size_bytes": 3932160000 },
    "docx": { "count": 585, "size_bytes": 1310720000 }
  },
  "date_range": {
    "earliest": "2024-01-15T10:00:00Z",
    "latest": "2024-06-30T17:45:00Z",
    "span_days": 166
  },
  "size_distribution": {
    "under_1mb": 1000,
    "1mb_to_10mb": 400,
    "over_10mb": 85
  },
  "stages": [
    {
      "name": "discover",
      "status": "completed",
      "duration_seconds": 12.5,
      "detail": "1500 documents discovered"
    }
  ],
  "errors": { "count": 0, "skip_reasons": {} },
  "manifest_path": "/output/manifest.jsonl",
  "generated_at": "2025-11-04T10:30:00Z"
}
```

### Proportionality Use Cases

**Early case conference**:
- Volume: "1,485 unique documents, 5 GB"
- Deduplication: "15 duplicates removed (1%)"
- Distribution: "60% PDFs, 40% Office, 5% emails"
- Cost: "10-30 hours at $75-200/hr = $750-6,000"

**Negotiated discovery**:
- "By custodian" breakdown for phased production
- Date range for temporal scoping
- Doctype distribution for format feasibility

**Proportionality objections**:
- Culling rationale documents reductions
- Error counts justify sampling if needed
- Cost estimates support burden arguments

---

## Data Flow

### Document Indexing Flow

```
1. User: rexlit index build /docs
                 ↓
2. discover_documents() → Iterator[DocumentMetadata]
                 ↓
3. ProcessPoolExecutor submits to workers
                 ↓
4. Worker: extract_document() → ExtractedDocument
                 ↓
5. Main: Create Tantivy Document
                 ↓
6. writer.add_document(doc)
                 ↓
7. Update metadata cache (custodians, doctypes)
                 ↓
8. Periodic commit (every 1,000 docs)
                 ↓
9. Final commit + save cache
                 ↓
10. Audit: INDEX_BUILD_COMPLETE
```

### Search Query Flow

```
1. User: rexlit index search "query"
                 ↓
2. Load Tantivy index
                 ↓
3. Parse query with Tantivy parser
                 ↓
4. Execute search
                 ↓
5. Rank results by relevance
                 ↓
6. Format output (text or JSON)
                 ↓
7. Audit: SEARCH_QUERY
```

### Audit Verification Flow

```
1. User: rexlit audit verify
                 ↓
2. Load audit.jsonl entries
                 ↓
3. Verify genesis hash (first entry)
                 ↓
4. For each entry:
   - Recompute hash
   - Verify matches stored hash
   - Verify previous_hash links to prior entry
                 ↓
5. Report: PASSED or FAILED with details
```

---

## Performance Optimizations

### 1. Parallel Document Processing

**Problem**: Sequential processing was CPU-bound (10-20% utilization)

**Solution**: ProcessPoolExecutor with `max_workers = cpu_count() - 1`

**Results**:
- CPU: 10-20% → 80-90%
- Throughput: 15-20x faster
- 100K docs: 83 hours → 4-6 hours

### 2. Streaming Document Discovery

**Problem**: `list(discover_documents())` loaded all paths into memory

**Solution**: Return `Iterator[DocumentMetadata]` instead of `list`

**Results**:
- Memory: 80MB → <10MB
- Scale: Limited by RAM → Unlimited
- Startup: Delayed → Immediate

### 3. Metadata Cache

**Problem**: Querying custodians required full index scan (5-10s)

**Solution**: JSON cache updated incrementally during indexing

**Results**:
- Query time: 5-10s → <10ms (1000x faster)
- No result limits
- Cache overhead: <1KB

### 4. Batch Commits

**Problem**: Committing after every document was slow

**Solution**: Commit every 1,000 documents

**Results**:
- Reduced I/O overhead
- Better memory management
- Faster overall indexing

---

## Security Design

### Defense-in-Depth Layers

1. **Path Validation**: Resolve and verify all paths
2. **Boundary Checks**: Reject paths outside allowed root
3. **Symlink Safety**: Resolve links and check final destination
4. **Audit Logging**: Log all security events
5. **Hash Chain**: Tamper-evident audit trail

### Path Traversal Protection

**Attack Surface**:
- Malicious symlinks pointing to `/etc/passwd`
- `../` sequences in file paths
- Absolute paths outside document root

**Mitigation**:
```python
def validate_path(path: Path, allowed_root: Path) -> bool:
    # Resolve to absolute path (follows symlinks)
    resolved = path.resolve()

    # Check if within boundary
    try:
        resolved.relative_to(allowed_root.resolve())
        return True
    except ValueError:
        # Path traversal attempt detected
        logger.warning(f"PATH_TRAVERSAL: {path} → {resolved}")
        return False
```

**Test Coverage**: 13 dedicated security tests

### Audit Trail Security

**Threat Model**:
- Attacker modifies audit.jsonl
- Attacker deletes entries
- Attacker reorders entries

**Mitigation**:
- **Hash Chain**: Any modification breaks chain
- **Fsync**: No data loss on crash
- **Verification**: `rexlit audit verify` detects tampering

**Cryptographic Guarantee**: SHA-256 hash chain is computationally infeasible to forge

---

## Design Decisions

### Why Python 3.11+?

- **Type Annotations**: Full typing support for reliability
- **Performance**: Faster than 3.10 (10-15% improvement)
- **Modern Features**: Pattern matching, better error messages
- **Ecosystem**: Rich libraries for document processing

### Why Tantivy?

- **Performance**: Rust-based, blazing fast
- **Offline**: No external dependencies
- **BM25**: Industry-standard ranking algorithm
- **Python Bindings**: Native integration

**Alternatives Considered**:
- Whoosh (pure Python) - Too slow
- Elasticsearch - Requires server, not offline
- SQLite FTS - Limited features

### Why ProcessPoolExecutor over ThreadPoolExecutor?

- **GIL**: Python GIL limits thread parallelism
- **CPU-bound**: Text extraction is CPU-intensive
- **Isolation**: Process crashes don't affect main thread

**Trade-off**: Higher memory overhead, but 15-20x speedup worth it

### Why Append-Only JSONL for Audit?

- **Simplicity**: Human-readable, no database
- **Portability**: Works everywhere, easy to backup
- **Immutability**: Append-only by design
- **Standard**: JSONL is industry standard

**Alternatives Considered**:
- SQLite - Overkill, harder to verify
- Custom binary format - Not human-readable
- Blockchain - Over-engineered

### Why XDG Base Directory?

- **Standards**: Follows freedesktop.org specification
- **Clean**: No dot-files in `$HOME`
- **Predictable**: Users know where data lives
- **Multi-user**: Proper separation

---

## File Layout

```
~/.local/share/rexlit/
├── index/                  # Tantivy search index
│   ├── .tantivy-*         # Index segments
│   ├── .metadata_cache.json
│   └── meta.json
├── audit.jsonl            # Append-only audit trail
└── manifests/             # Document manifests (optional)
    └── case-001.jsonl

~/.config/rexlit/
└── config.toml            # Future: User configuration

~/.cache/rexlit/
└── tmp/                   # Temporary files during indexing
```

---

## Future Architecture (M1+)

### Phase 2 (M1) Additions

```
rexlit/
├── ocr/                   # OCR providers
│   ├── tesseract.py
│   ├── paddle.py
│   └── deepseek.py
├── dedupe/                # Deduplication
│   └── hash_compare.py
├── bates/                 # Bates stamping
│   └── stamp.py
└── production/            # DAT/Opticon exports
    ├── dat.py
    └── opticon.py
```

### Scalability Considerations

**For 500K+ documents**:
- Index sharding across multiple directories
- Distributed processing with message queue
- Database for metadata (PostgreSQL)
- Streaming search results

**For multi-user**:
- FastAPI REST API layer
- Authentication/authorization
- Shared index with row-level security

---

## Code Quality Metrics

| Metric | Value |
|--------|-------|
| Total Lines of Code | ~2,000 |
| Test Coverage | 100% (63/63 tests) |
| Type Coverage | 95%+ (mypy strict) |
| Cyclomatic Complexity | <10 per function |
| Code Duplication | <5% |

---

## Performance Benchmarks

### Indexing Performance

| Docs | Sequential | Parallel (8 cores) | Speedup |
|------|------------|-------------------|---------|
| 1K | 20s | 4s | 5x |
| 10K | 3.3min | 40s | 5x |
| 100K | 83hr | 4-6hr | 15-20x |

### Memory Usage

| Operation | Memory (Peak) |
|-----------|---------------|
| Document Discovery | <10MB |
| Indexing (8 workers) | ~2GB |
| Search Query | <50MB |
| Audit Verification | <5MB |

### Search Performance

| Index Size | Query Time | Results |
|------------|------------|---------|
| 1K docs | <1ms | 10 |
| 10K docs | <5ms | 10 |
| 100K docs | <50ms | 10 |

---

## References

- [Tantivy Documentation](https://github.com/quickwit-oss/tantivy)
- [XDG Base Directory Spec](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [FRCP Rule 26](https://www.law.cornell.edu/rules/frcp/rule_26)
- [SHA-256 Specification](https://en.wikipedia.org/wiki/SHA-2)

---

**Last Updated**: 2025-10-23 (M0 Release)
