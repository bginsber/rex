# Kanon 2 Integration: Executive Summary

**Date:** 2025-10-27
**Purpose:** Quick reference for RexLit Kanon 2 dense vector integration
**Full Documentation:** See `KANON2_INTEGRATION_DOCS.md`

---

## TL;DR: Key Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Embeddings** | Kanon 2 (768 dims) | Best legal AI embedder (MLEB), 768 = sweet spot for quality/memory |
| **Vector Store** | hnswlib (M=16, ef_const=200) | Fast ANN, simple API, 20-40% memory overhead |
| **Fusion** | RRF (k=60) | No tuning needed, empirically validated |
| **Architecture** | Separate indexes | Tantivy (BM25) + hnswlib (dense), fused at query time |

---

## Installation & Versions

```bash
# All dependencies already installed in pyproject.toml:
pip install hnswlib>=0.7.0      # Installed: 0.8.0
pip install isaacus>=0.1.0      # Installed: 0.9.1
pip install numpy>=1.26.0       # Installed: 2.3.4
pip install tantivy>=0.22.0     # Installed: 0.25.0 (existing)
```

**Python Requirement:** 3.11+

---

## Quick Start Examples

### 1. Build Index with Dense Embeddings

```bash
# Export API key
export ISAACUS_API_KEY="your_key_here"

# Build index with dense vectors (requires --online)
rexlit index build ./docs --dense --dim 768 --online

# This creates:
# - index_dir/tantivy/     (BM25 index)
# - index_dir/hnsw/        (dense vectors)
```

### 2. Search with Hybrid Mode

```bash
# Hybrid search (BM25 + dense, requires dense index)
rexlit search "contract breach" --hybrid --top 10

# BM25-only (offline, works without dense index)
rexlit search "contract breach" --top 10
```

---

## Code Snippets

### hnswlib (Vector Store)

```python
import hnswlib
import numpy as np

# Create and build index
index = hnswlib.Index(space='l2', dim=768)
index.init_index(
    max_elements=100000,
    M=16,                 # Graph connectivity
    ef_construction=200,  # Build quality
    random_seed=42        # Deterministic
)

# Add vectors
vectors = np.random.rand(1000, 768).astype(np.float32)
ids = np.arange(1000)
index.add_items(vectors, ids, num_threads=-1)

# Save/Load
index.save_index('index.bin')
index.load_index('index.bin')
index.set_ef(100)  # Query accuracy (MUST set after load)

# Query
labels, distances = index.knn_query(query_vector, k=10)
```

### Isaacus (Kanon 2 Embeddings)

```python
from isaacus import Isaacus

client = Isaacus()  # Reads ISAACUS_API_KEY from env

# Embed documents (corpus)
response = client.embeddings.create(
    model="kanon-2-embedder",
    texts=["Doc 1", "Doc 2"],     # Max 128 texts/request
    dimensions=768,                # 256, 512, 768, 1024, 1792
    task="retrieval/document",     # Optimize for corpus
)

# Embed query
query_response = client.embeddings.create(
    model="kanon-2-embedder",
    texts="search query",
    dimensions=768,
    task="retrieval/query",        # Optimize for queries
)

# Extract vectors
embeddings = [emb.embedding for emb in response.embeddings]
```

### RRF (Hybrid Fusion)

```python
def reciprocal_rank_fusion(bm25_results, dense_results, k=60):
    """Fuse two ranked lists using RRF."""
    scores = {}

    for rank, doc_id in enumerate(bm25_results, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    for rank, doc_id in enumerate(dense_results, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

---

## Port Interfaces (Hexagonal Architecture)

### EmbeddingPort

```python
from typing import Protocol
import numpy as np
from numpy.typing import NDArray

class EmbeddingPort(Protocol):
    """Port for embedding generation."""

    def embed_documents(
        self,
        texts: list[str],
        *,
        dim: int = 768,
    ) -> NDArray[np.float32]:
        """Embed corpus documents (task=retrieval/document)."""
        ...

    def embed_query(
        self,
        query: str,
        *,
        dim: int = 768,
    ) -> NDArray[np.float32]:
        """Embed search query (task=retrieval/query)."""
        ...

    def is_online(self) -> bool:
        """Always True for Kanon 2."""
        ...
```

### VectorStorePort

```python
class VectorStorePort(Protocol):
    """Port for ANN vector storage."""

    def build(
        self,
        vectors: NDArray[np.float32],
        ids: list[int],
        *,
        M: int = 16,
        ef_construction: int = 200,
    ) -> None:
        """Build HNSW index."""
        ...

    def save(self, path: str) -> None:
        """Persist to disk."""
        ...

    def load(self, path: str, *, ef: int = 100) -> None:
        """Load from disk."""
        ...

    def query(
        self,
        vectors: NDArray[np.float32],
        k: int = 10,
    ) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
        """Query k nearest neighbors."""
        ...

    def is_online(self) -> bool:
        """Always False (offline storage)."""
        ...
```

---

## Parameter Recommendations

### HNSW Parameters

| Parameter | Recommended | Trade-off |
|-----------|-------------|-----------|
| **M** | 16 (100K docs), 24 (1M docs) | Higher = better recall, more memory |
| **ef_construction** | 200 (balanced), 400 (high quality) | Higher = better index, slower build |
| **ef** (query) | 100 (balanced), 200 (high recall) | Higher = better recall, slower queries |

**Memory Formula (768 dims, float32):**
- Per vector: ~3.2 KB (3 KB raw + 0.2 KB graph overhead @ M=16)
- 100K vectors: ~320 MB
- 1M vectors: ~3.2 GB

### Kanon 2 Parameters

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| **dimensions** | 768 | Balance quality/memory (1792 = max, 256 = min) |
| **task** | "retrieval/document" (corpus), "retrieval/query" (search) | Task-specific optimization |
| **overflow_strategy** | "drop_end" | Truncate if >16,384 tokens |

**Batch Limit:** 128 texts per request

### RRF Parameter

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| **k** | 60 | Empirically validated, no tuning needed |

---

## Performance Estimates

### Build Time (100K documents)

| Stage | Time | Notes |
|-------|------|-------|
| Embedding generation | 2-3 min | Network-bound, 128 texts/batch |
| HNSW build | 2-4 min | 8 cores, M=16, ef_construction=200 |
| **Total** | **4-7 min** | Offline BM25 build: ~5-6 min |

### Query Time (100K documents)

| Mode | Latency | Notes |
|------|---------|-------|
| BM25 only | <50 ms | Existing performance |
| Dense only | <10 ms | HNSW with ef=100 |
| Hybrid (RRF) | <100 ms | BM25 + dense + fusion |

### Memory (100K documents, 768 dims)

| Component | Size | Notes |
|-----------|------|-------|
| Tantivy (BM25) | ~500 MB | Existing |
| HNSW vectors | ~307 MB | Raw vectors |
| HNSW graph | ~130 MB | Graph overhead |
| **Total** | **~937 MB** | <1 GB total |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer                        │
│  rexlit index build --dense --online                │
│  rexlit search "query" --hybrid                     │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              Bootstrap (DI Container)               │
│  - Kanon2Adapter (EmbeddingPort)                   │
│  - HNSWAdapter (VectorStorePort)                   │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│           Application Services                      │
│  - M1Pipeline (index build orchestration)          │
│  - SearchService (hybrid search coordination)      │
└──────────────────┬──────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌─────────────┐         ┌─────────────┐
│  Tantivy    │         │  hnswlib    │
│  (BM25)     │         │  (Dense)    │
└─────────────┘         └─────────────┘
       │                       │
       └───────────┬───────────┘
                   ▼
            ┌─────────────┐
            │ RRF Fusion  │
            └─────────────┘
```

**Separation of Concerns:**
- Tantivy: BM25 lexical search (existing)
- hnswlib: Dense semantic search (new)
- RRF: Fusion layer (new)
- No modifications to Tantivy schema needed

---

## Files to Create

### Port Interfaces
- `/Users/bg/Documents/Coding/rex/rexlit/app/ports/embedding.py`
- `/Users/bg/Documents/Coding/rex/rexlit/app/ports/vector_store.py`

### Adapters
- `/Users/bg/Documents/Coding/rex/rexlit/app/adapters/kanon2_adapter.py`
- `/Users/bg/Documents/Coding/rex/rexlit/app/adapters/hnsw_adapter.py`

### Domain Modules
- `/Users/bg/Documents/Coding/rex/rexlit/index/hnsw_store.py` (HNSW wrapper)
- `/Users/bg/Documents/Coding/rex/rexlit/index/hybrid.py` (RRF logic)

### Configuration
- Update `/Users/bg/Documents/Coding/rex/rexlit/config.py` with:
  - `isaacus_api_key`
  - `embedding_dim`
  - `hnsw_m`, `hnsw_ef_construction`, `hnsw_ef_search`

### CLI
- Update `/Users/bg/Documents/Coding/rex/rexlit/cli.py`:
  - `index build` with `--dense`, `--dim`, `--online` flags
  - `search` with `--hybrid` flag

### Tests
- `/Users/bg/Documents/Coding/rex/tests/test_embedding_adapter.py`
- `/Users/bg/Documents/Coding/rex/tests/test_hnsw_adapter.py`
- `/Users/bg/Documents/Coding/rex/tests/test_hybrid_search.py`

---

## Offline-First Compliance

**Online Operations:**
- Embedding generation (Kanon 2 API calls)
- MUST check `require_online()` gate
- MUST emit audit ledger entries

**Offline Operations:**
- HNSW index build (from pre-computed embeddings)
- HNSW index load/query
- BM25 search (existing)
- RRF fusion

**Workflow:**
```bash
# Phase 1: Online (build with embeddings)
export REXLIT_ONLINE=1
rexlit index build ./docs --dense --online

# Phase 2: Offline (search with pre-built index)
unset REXLIT_ONLINE
rexlit search "query" --hybrid  # Uses existing HNSW index
```

**Fallback:**
If dense index not present or `--hybrid` not specified, fallback to BM25-only.

---

## Audit Logging

**Embedding Operation:**
```json
{
  "timestamp": "2025-10-27T10:00:00Z",
  "operation": "embed_documents",
  "inputs": ["1000 texts"],
  "outputs": ["1000 embeddings"],
  "args": {
    "model": "kanon-2-embedder",
    "dim": 768,
    "task": "retrieval/document",
    "latency_sec": 2.5,
    "tokens_used": 50000
  }
}
```

**HNSW Build:**
```json
{
  "timestamp": "2025-10-27T10:05:00Z",
  "operation": "hnsw_build",
  "inputs": ["1000 vectors"],
  "outputs": ["index.bin"],
  "args": {
    "dim": 768,
    "M": 16,
    "ef_construction": 200,
    "build_time_sec": 120
  }
}
```

---

## Error Handling

### Isaacus Client Errors

```python
from isaacus import (
    RateLimitError,
    AuthenticationError,
    IsaacusError,
)

try:
    embeddings = client.embeddings.create(...)
except RateLimitError:
    # Implement exponential backoff
    time.sleep(60)
    retry()
except AuthenticationError:
    # Check ISAACUS_API_KEY
    raise ValueError("Invalid API key")
except IsaacusError as e:
    # Log and fail gracefully
    logger.error(f"Embedding failed: {e}")
    # Fallback to BM25-only?
```

### hnswlib Errors

```python
# Common issues:
# 1. Index not initialized
if index.element_count == 0:
    raise ValueError("Index empty")

# 2. ef too small
if ef < k:
    raise ValueError(f"ef ({ef}) must be >= k ({k})")

# 3. Dimension mismatch
if query.shape[0] != index.dim:
    raise ValueError(f"Query dim {query.shape[0]} != index dim {index.dim}")
```

---

## Security Considerations

**API Key Management:**
- Store in `ISAACUS_API_KEY` environment variable
- Never commit to git
- Use `.env` files (excluded in `.gitignore`)

**Offline Gating:**
- All network operations check `require_online()`
- Audit trail logs all embedding API calls
- Self-hosting option via `base_url` parameter

**Path Safety:**
- HNSW index paths must resolve within index root
- Use `resolve_safe_path()` (existing RexLit utility)

---

## Testing Strategy

### Unit Tests
- Kanon2Adapter: Mock HTTP responses
- HNSWAdapter: In-memory index operations
- RRF: Fusion correctness with known results

### Integration Tests
- Dense index build: Small corpus (10 docs)
- Hybrid search: BM25 + dense + RRF
- Offline gating: Ensure raises when `--online` missing

### Performance Tests
- Memory usage: Track HNSW overhead
- Build time: Benchmark 10K docs
- Query latency: <100ms for hybrid search

### Regression Tests
- Deterministic ordering (hash + path sorting)
- Audit ledger integrity (hash chain)
- BM25 fallback when dense unavailable

---

## Success Criteria (from Next_plan.md)

- [ ] `rexlit index build PATH --dense --dim 768 --online` produces Tantivy + HNSW artifacts
- [ ] `rexlit search "query" --hybrid` returns higher Recall@10 than BM25-only
- [ ] Embedding calls refuse to run unless `--online` or `REXLIT_ONLINE=1`
- [ ] Structured audit entries for all embedding operations
- [ ] Tests pass: `pytest -v --no-cov` (100% passing)
- [ ] Documentation updated: README.md, CLI-GUIDE.md

---

## Next Steps

1. **Read Full Documentation:** `/Users/bg/Documents/Coding/rex/KANON2_INTEGRATION_DOCS.md`
2. **Review Next_plan.md:** Work breakdown for implementation
3. **Create Port Interfaces:** Start with `embedding.py` and `vector_store.py`
4. **Implement Adapters:** Kanon2Adapter and HNSWAdapter
5. **Test Incrementally:** One component at a time
6. **Wire in Bootstrap:** Dependency injection
7. **Update CLI:** Add flags
8. **Write Tests:** Achieve 100% passing
9. **Update Docs:** README, CLI-GUIDE

---

## Quick Links

- **Full Documentation:** `/Users/bg/Documents/Coding/rex/KANON2_INTEGRATION_DOCS.md`
- **Implementation Plan:** `/Users/bg/Documents/Coding/rex/Next_plan.md`
- **hnswlib GitHub:** https://github.com/nmslib/hnswlib
- **Isaacus Docs:** https://docs.isaacus.com
- **tantivy-py Docs:** https://tantivy-py.readthedocs.io
- **PEP 544 (Protocols):** https://peps.python.org/pep-0544/

---

**Document Version:** 1.0
**Last Updated:** 2025-10-27
**Compiled By:** Framework Documentation Researcher
