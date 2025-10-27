# Kanon 2 Integration: Comprehensive Framework Documentation

**Research Date:** 2025-10-27
**Python Version:** 3.11+
**Target Architecture:** RexLit Ports & Adapters (Hexagonal)

---

## Executive Summary

This document provides comprehensive technical documentation for integrating dense vector search (Kanon 2) into RexLit using a hexagonal architecture. The integration combines:

1. **hnswlib 0.8.0** - Local ANN (Approximate Nearest Neighbor) storage
2. **isaacus 0.9.1** - Kanon 2 embedding API client
3. **tantivy 0.25.0** - Full-text search engine (existing)
4. **numpy 2.3.4** - Vector operations and normalization
5. **Reciprocal Rank Fusion** - Hybrid ranking algorithm

All components are compatible with Python 3.11+ and follow RexLit's offline-first, audit-ready design principles.

---

## 1. hnswlib Documentation

### 1.1 Overview

**Package:** hnswlib 0.8.0
**License:** Apache 2.0
**Repository:** https://github.com/nmslib/hnswlib
**Type:** Header-only C++/Python library for fast ANN search

hnswlib implements the Hierarchical Navigable Small World (HNSW) algorithm, providing efficient approximate nearest neighbor search with excellent recall/speed trade-offs.

### 1.2 Python API Reference

#### Index Creation

```python
import hnswlib

# Create index
index = hnswlib.Index(space='l2', dim=768)

# Initialize with parameters
index.init_index(
    max_elements=100000,      # Maximum capacity (resizable)
    M=16,                     # Max bidirectional links per element
    ef_construction=200,      # Construction-time accuracy
    random_seed=100,          # Reproducibility
    allow_replace_deleted=False
)
```

**Space Metrics:**
- `'l2'` - L2 (Euclidean) distance
- `'ip'` - Inner product (for normalized vectors, equivalent to cosine)
- `'cosine'` - Cosine similarity (auto-normalized)

**Constructor Signatures:**
```python
Index(space: str, dim: int)                    # Standard construction
Index(params: dict)                            # Dict-based construction
Index(index: Index)                            # Copy constructor
```

#### Adding Items

```python
# Add single batch
index.add_items(
    data=embeddings,           # numpy array (N, dim) or (dim,)
    ids=doc_ids,              # numpy array (N,) or list, optional
    num_threads=-1,           # -1 = use all cores
    replace_deleted=False     # Allow reusing deleted slots
)
```

**Thread Safety:**
- `add_items` is thread-safe ONLY with other `add_items` calls
- NOT thread-safe with queries or pickling

**Auto ID Assignment:**
If `ids=None`, assigns sequential IDs starting from 0.

#### Querying

```python
labels, distances = index.knn_query(
    data=query_vectors,        # numpy array (N, dim) or (dim,)
    k=10,                      # Number of neighbors
    num_threads=-1,            # Parallelization
    filter=lambda label: True  # Optional predicate (slow in parallel)
)
```

**Returns:**
- `labels`: numpy array of document IDs, shape (N, k)
- `distances`: numpy array of distances, shape (N, k)

**Thread Safety:**
- `knn_query` is thread-safe ONLY with other `knn_query` calls
- NOT thread-safe with `add_items`

**Filter Constraints:**
- Filters are slow in multithreaded mode
- Recommend `num_threads=1` when using filters

#### Search Quality Control

```python
# Set query-time accuracy
index.set_ef(ef=100)  # Must be >= k, higher = slower but more accurate
```

**Important:** `ef` is NOT persisted and must be reset after loading.

#### Persistence

```python
# Save to disk
index.save_index('/path/to/index.bin')

# Load from disk
index.load_index(
    path_to_index='/path/to/index.bin',
    max_elements=0,           # 0 = keep current, >0 = resize
    allow_replace_deleted=False
)
```

**Pickle Support:**
```python
import pickle

# Serialize
with open('index.pkl', 'wb') as f:
    pickle.dump(index, f)

# Deserialize
with open('index.pkl', 'rb') as f:
    index = pickle.load(f)
```

**Warning:** Pickling is NOT thread-safe with `add_items`.

#### Metadata Access

**Read-Only Properties:**
```python
index.space              # 'l2', 'ip', or 'cosine'
index.dim                # Vector dimensionality
index.M                  # Max connections per element
index.ef_construction    # Construction-time parameter
index.max_elements       # Current capacity
index.element_count      # Current item count
```

**Read/Write Properties:**
```python
index.ef                 # Query-time accuracy (not persisted)
index.num_threads        # Parallelization control
```

#### Utility Methods

```python
# Get all IDs
ids = index.get_ids_list()  # Returns list[int]

# Retrieve vectors by ID
vectors = index.get_items(
    ids=[1, 2, 3],
    return_type='numpy'     # 'numpy' or 'list'
)

# Mark as deleted (soft delete)
index.mark_deleted(label=123)
index.unmark_deleted(label=123)

# Resize capacity
index.resize_index(new_size=200000)

# Get file size
size_bytes = index.index_file_size()
```

### 1.3 Parameter Tuning Guide

#### M (Bidirectional Links)

**Purpose:** Controls graph connectivity and memory usage

**Recommended Range:** 2-100
- **Low dimensional (dim=4):** M=6
- **High dimensional (dim=768):** M=16-48
- **Very high recall requirements:** M=48-64

**Trade-offs:**
- Higher M → Better recall, slower construction, more memory
- Lower M → Faster construction, less memory, lower recall

**Memory Cost:** ~8-10 bytes per element per M value

**Example Memory Calculation (768 dims, 100K vectors):**
- Raw vectors: 768 × 4 bytes × 100K = 307 MB
- HNSW graph (M=16): ~1.28 MB × 100K / 1000 = ~128 MB
- **Total: ~435 MB**

#### ef_construction (Index-Time Accuracy)

**Purpose:** Controls construction time vs. index quality

**Recommended Range:** 100-500
- **Fast build:** ef_construction=100
- **Balanced:** ef_construction=200 (default)
- **High quality:** ef_construction=400-500

**Trade-offs:**
- Higher ef_construction → Better index quality, slower build
- Lower ef_construction → Faster build, lower quality

**Quality Validation:**
```python
# After building, check recall with ef=ef_construction
index.set_ef(index.ef_construction)
labels, _ = index.knn_query(validation_queries, k=10)
recall = compute_recall(labels, ground_truth)

# If recall < 0.9, increase ef_construction and rebuild
```

**Relationship to M:**
The product `M × ef_construction` is roughly constant for similar quality levels.

#### ef (Query-Time Accuracy)

**Purpose:** Controls search speed vs. accuracy

**Recommended Range:** k to max_elements
- **Fast search:** ef=k to 2k
- **Balanced:** ef=50-100
- **High recall:** ef=200-500

**Trade-offs:**
- Higher ef → Better recall, slower queries
- Lower ef → Faster queries, lower recall

**Constraints:**
- Must be ≥ k (number of neighbors requested)
- Not persisted; must be set after loading

#### Tuning Strategy

**Step 1: Start with defaults**
```python
M = 16
ef_construction = 200
ef = 100
```

**Step 2: Benchmark recall**
```python
index.set_ef(ef)
recall = measure_recall(index, validation_set)
while recall < 0.95:
    ef += 50
    index.set_ef(ef)
    recall = measure_recall(index, validation_set)
```

**Step 3: Adjust construction**
```python
# If ef ended up > 1000, rebuild with higher M or ef_construction
if ef > 1000:
    ef_construction = ef  # Bake quality into index
    # Consider increasing M if memory permits
```

**RexLit-Specific Recommendations:**

For legal document corpus (<100K chunks, 768 dims):
```python
M = 16                    # Good recall, reasonable memory
ef_construction = 200     # Balanced build time
ef = 100                  # Fast queries, ~0.95 recall
```

For larger corpus (100K-1M chunks):
```python
M = 24                    # Better connectivity
ef_construction = 400     # Higher quality index
ef = 200                  # Better recall
```

### 1.4 Memory Requirements

**Formula (768 dimensions, float32):**
```
Per Vector:
  Raw data: 768 × 4 = 3,072 bytes
  Graph overhead (M=16): ~16 × 10 = 160 bytes
  Total: ~3,232 bytes (~3.2 KB)

For N vectors:
  Total memory: N × 3.2 KB

Examples:
  10K vectors: ~32 MB
  100K vectors: ~320 MB
  1M vectors: ~3.2 GB
```

**HNSW Graph Overhead:** 20-40% of raw vector data, depending on M.

**Chunking Guidance (from Next_plan.md):**
- Chunk size: 1-2K tokens
- Overlap: 10-15%
- Memory estimate: 768 dims ≈ 3 KB per chunk
- 1M chunks ≈ 3 GB vectors + 0.5-1 GB graph

### 1.5 Thread Safety Summary

| Operation | Thread-Safe With | NOT Thread-Safe With |
|-----------|------------------|----------------------|
| `add_items` | `add_items` | `knn_query`, pickle |
| `knn_query` | `knn_query` | `add_items`, pickle |
| `pickle.dump/load` | N/A | `add_items`, `knn_query` |

**Recommendation for RexLit:**
- Use single-threaded adds during index build (or sequential batches)
- Use multi-threaded queries during search (read-only phase)
- Never pickle during active operations

### 1.6 Integration with RexLit Architecture

**Port Interface (rexlit/app/ports/vector_store.py):**
```python
from typing import Protocol
import numpy as np
from numpy.typing import NDArray

class VectorStorePort(Protocol):
    """Port for ANN vector storage (e.g., HNSW)."""

    def build(
        self,
        vectors: NDArray[np.float32],
        ids: list[int],
        *,
        M: int = 16,
        ef_construction: int = 200,
    ) -> None:
        """Build index from vectors."""
        ...

    def save(self, path: str) -> None:
        """Persist index to disk."""
        ...

    def load(self, path: str, *, ef: int = 100) -> None:
        """Load index and set query accuracy."""
        ...

    def query(
        self,
        vectors: NDArray[np.float32],
        k: int = 10,
    ) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
        """Query k nearest neighbors."""
        ...
```

**Adapter (rexlit/app/adapters/hnsw_adapter.py):**
```python
import hnswlib
import numpy as np
from pathlib import Path

class HNSWAdapter:
    """Adapter for hnswlib-based vector storage."""

    def __init__(self, dim: int = 768, space: str = 'l2'):
        self.dim = dim
        self.space = space
        self.index: hnswlib.Index | None = None

    def build(self, vectors, ids, *, M=16, ef_construction=200):
        self.index = hnswlib.Index(space=self.space, dim=self.dim)
        self.index.init_index(
            max_elements=len(vectors),
            M=M,
            ef_construction=ef_construction,
            random_seed=42,  # Deterministic for legal defensibility
        )
        self.index.add_items(vectors, ids, num_threads=-1)

    def save(self, path: str):
        if self.index is None:
            raise ValueError("Index not built")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.index.save_index(path)

    def load(self, path: str, *, ef: int = 100):
        self.index = hnswlib.Index(space=self.space, dim=self.dim)
        self.index.load_index(path)
        self.index.set_ef(ef)  # Critical: set after loading

    def query(self, vectors, k=10):
        if self.index is None:
            raise ValueError("Index not loaded")
        return self.index.knn_query(vectors, k=k, num_threads=-1)
```

---

## 2. Isaacus Client Documentation (Kanon 2)

### 2.1 Overview

**Package:** isaacus 0.9.1
**API Base:** https://api.isaacus.com (default)
**Documentation:** https://docs.isaacus.com
**Model:** Kanon 2 Embedder (kanon-2-embedder)

The Isaacus client provides access to Kanon 2, the most accurate legal AI embedder on the Massive Legal Embedding Benchmark (MLEB).

### 2.2 Authentication

**Environment Variable (Recommended):**
```bash
export ISAACUS_API_KEY="your_api_key_here"
```

**Client Initialization:**
```python
from isaacus import Isaacus, AsyncIsaacus

# Synchronous client (auto-reads ISAACUS_API_KEY)
client = Isaacus()

# Or explicit API key
client = Isaacus(api_key="your_api_key_here")

# Async client
async_client = AsyncIsaacus()
```

**Custom Base URL:**
```python
client = Isaacus(
    api_key="...",
    base_url="https://custom-isaacus-endpoint.com"
)
```

**Configuration Options:**
```python
client = Isaacus(
    api_key="...",
    timeout=60.0,              # Request timeout (seconds)
    max_retries=2,             # Retry on failures
    default_headers={...},     # Extra headers
)
```

### 2.3 Embedding Generation API

#### Synchronous

```python
from isaacus import Isaacus

client = Isaacus()

response = client.embeddings.create(
    model="kanon-2-embedder",
    texts=["Legal document text..."],  # str or list[str]
    dimensions=768,                     # Optional: 256, 512, 768, 1024, 1792
    task="retrieval/document",          # or "retrieval/query"
    overflow_strategy="drop_end",       # or None (raise error)
)

# Access embeddings
for embedding in response.embeddings:
    vector = embedding.embedding        # list[float]
    index = embedding.index            # int (position in input)

# Usage stats
tokens_used = response.usage.input_tokens
```

#### Asynchronous

```python
from isaacus import AsyncIsaacus

async_client = AsyncIsaacus()

response = await async_client.embeddings.create(
    model="kanon-2-embedder",
    texts=corpus_texts,
    task="retrieval/document",
)
```

### 2.4 API Parameters

#### model
- **Type:** Literal["kanon-2-embedder"]
- **Required:** Yes
- **Description:** Model identifier

#### texts
- **Type:** str | list[str]
- **Required:** Yes
- **Constraints:**
  - Each text must contain at least one non-whitespace character
  - Maximum 128 texts per request (batch limit)

#### dimensions
- **Type:** int | None
- **Optional:** Yes
- **Default:** 1,792 (full dimensionality)
- **Supported:** 256, 512, 768, 1024, 1792
- **Description:** Output dimensionality (lower dims = faster search, less memory)

**RexLit Recommendation:** Use 768 for balance of quality and performance.

#### task
- **Type:** Literal["retrieval/query", "retrieval/document"] | None
- **Optional:** Yes
- **Default:** None (general-purpose embeddings)
- **Description:**
  - `"retrieval/document"`: Optimize for corpus documents (to be searched)
  - `"retrieval/query"`: Optimize for search queries
  - `None`: General-purpose (not task-optimized)

**Best Practice:**
```python
# During indexing (corpus)
doc_embeddings = client.embeddings.create(
    texts=document_chunks,
    task="retrieval/document"
)

# During search (queries)
query_embeddings = client.embeddings.create(
    texts=user_query,
    task="retrieval/query"
)
```

#### overflow_strategy
- **Type:** Literal["drop_end"] | None
- **Optional:** Yes
- **Default:** "drop_end"
- **Description:**
  - `"drop_end"`: Truncate tokens exceeding 16,384 token limit
  - `None`: Raise error if any text exceeds limit

### 2.5 Response Structure

```python
class EmbeddingResponse(BaseModel):
    embeddings: list[Embedding]
    usage: Usage

class Embedding(BaseModel):
    embedding: list[float]  # Vector of specified dimensionality
    index: int              # Position in input array (0-based)

class Usage(BaseModel):
    input_tokens: int       # Total tokens processed
```

**Order Guarantee:** Embeddings are returned in the same order as input texts.

### 2.6 Batch Processing

**Batch Limit:** 128 texts per request

**Strategy for Large Corpora:**
```python
def embed_corpus(texts: list[str], batch_size: int = 128):
    """Embed large corpus in batches."""
    embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        response = client.embeddings.create(
            model="kanon-2-embedder",
            texts=batch,
            dimensions=768,
            task="retrieval/document",
        )
        embeddings.extend([emb.embedding for emb in response.embeddings])

    return embeddings
```

### 2.7 Rate Limiting and Error Handling

**Rate Limits:** Not documented in API reference (check with Isaacus support)

**Error Types:**
```python
from isaacus import (
    IsaacusError,              # Base error
    APIConnectionError,         # Network issues
    APITimeoutError,           # Timeout
    RateLimitError,            # Rate limit exceeded
    AuthenticationError,       # Invalid API key
    BadRequestError,           # Invalid request
    InternalServerError,       # Server error
)

try:
    response = client.embeddings.create(...)
except RateLimitError as e:
    # Implement backoff
    time.sleep(60)
    retry()
except AuthenticationError:
    # Check API key
    raise
except IsaacusError as e:
    # Generic error handling
    logger.error(f"Isaacus error: {e}")
```

**Recommended Retry Logic:**
```python
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(RateLimitError),
)
def embed_with_retry(texts):
    return client.embeddings.create(model="kanon-2-embedder", texts=texts)
```

### 2.8 Self-Hosted Deployment

**Current Status:** Not documented in official API reference.

**AWS SageMaker Integration:**
The isaacus package includes `isaacus_sagemaker` module for AWS deployments:
```python
from isaacus.resources.isaacus_sagemaker import IsaacusSageMakerRuntimeHTTPClient

# SageMaker-hosted endpoint (requires AWS credentials)
client = IsaacusSageMakerRuntimeHTTPClient(endpoint_name="...")
```

**Self-Hosting Recommendations:**
- Contact Isaacus support for enterprise self-hosting options
- Provide escape hatch via custom `base_url` parameter
- Document fallback for air-gapped environments

### 2.9 Integration with RexLit

**Offline-First Constraint:**
```python
from rexlit.utils.offline import require_online

class Kanon2Adapter:
    """Adapter for Kanon 2 embedding generation."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        require_online("Kanon 2 embedding generation")  # Raises if offline

        from isaacus import Isaacus
        self.client = Isaacus(api_key=api_key, base_url=base_url)

    def embed_documents(self, texts: list[str], dim: int = 768):
        """Embed corpus documents."""
        return self._embed_batch(texts, task="retrieval/document", dim=dim)

    def embed_query(self, query: str, dim: int = 768):
        """Embed search query."""
        response = self.client.embeddings.create(
            model="kanon-2-embedder",
            texts=query,
            dimensions=dim,
            task="retrieval/query",
        )
        return response.embeddings[0].embedding

    def _embed_batch(self, texts, task, dim):
        all_embeddings = []
        for i in range(0, len(texts), 128):
            batch = texts[i:i+128]
            response = self.client.embeddings.create(
                model="kanon-2-embedder",
                texts=batch,
                dimensions=dim,
                task=task,
            )
            all_embeddings.extend([e.embedding for e in response.embeddings])
        return all_embeddings

    def is_online(self) -> bool:
        return True  # Always requires network
```

**Audit Logging:**
```python
from rexlit.app.ports.ledger import LedgerPort

def embed_with_audit(
    texts: list[str],
    adapter: Kanon2Adapter,
    ledger: LedgerPort,
):
    import time
    start = time.time()

    embeddings = adapter.embed_documents(texts)

    latency = time.time() - start
    ledger.log(
        operation="embed_documents",
        inputs=[f"{len(texts)} texts"],
        outputs=[f"{len(embeddings)} embeddings"],
        args={
            "model": "kanon-2-embedder",
            "dim": 768,
            "count": len(texts),
            "latency_sec": latency,
        }
    )

    return embeddings
```

### 2.10 Kanon 2 Model Specifications

**Architecture:** Kanon 2 (proprietary)
**Default Dimensions:** 1,792
**Supported Dimensions:** 256, 512, 768, 1024, 1792
**Context Window:** 16,384 tokens
**Normalization:** L2 normalized (unit vectors)

**Performance:**
- Ranked #1 on Massive Legal Embedding Benchmark (MLEB)
- Optimized for legal domain (cases, statutes, contracts)

**Use Cases:**
- Semantic search engines
- Document clustering
- Text classification
- Retrieval-augmented generation (RAG)

---

## 3. Tantivy Python Bindings Documentation

### 3.1 Overview

**Package:** tantivy 0.25.0
**Released:** September 9, 2025
**License:** MIT
**Repository:** https://github.com/quickwit-oss/tantivy-py
**Documentation:** https://tantivy-py.readthedocs.io

Tantivy is a full-text search engine library written in Rust, inspired by Apache Lucene. The Python bindings provide access to Tantivy's indexing and search capabilities.

### 3.2 Current RexLit Integration

RexLit already uses tantivy for BM25 full-text search. Review existing usage:

**Key Files:**
- `/Users/bg/Documents/Coding/rex/rexlit/index/build.py` - Index building
- `/Users/bg/Documents/Coding/rex/rexlit/index/search.py` - Search queries

### 3.3 Schema Definition

Tantivy requires strict schema definition before indexing.

**Schema Builder API:**
```python
import tantivy

schema_builder = tantivy.SchemaBuilder()

# Add fields
title_field = schema_builder.add_text_field(
    "title",
    stored=True,           # Retrieve original value
    tokenizer_name="en_stem",
    index_option="position"  # 'basic', 'freq', or 'position'
)

body_field = schema_builder.add_text_field(
    "body",
    stored=True,
    tokenizer_name="default"
)

doc_id_field = schema_builder.add_integer_field(
    "doc_id",
    stored=True,
    indexed=True,
    fast=False  # Fast field = columnar storage
)

schema = schema_builder.build()
```

### 3.4 Available Field Types

#### Text Fields
```python
schema_builder.add_text_field(
    name: str,
    stored: bool = False,      # Retrieve original text
    fast: bool = False,        # Columnar storage (for faceting)
    tokenizer_name: str = "default",  # Tokenizer choice
    index_option: str = "position"    # Indexing granularity
)
```

**Tokenizer Options:**
- `"default"` - Lowercase, whitespace split
- `"raw"` - No tokenization (exact match)
- `"en_stem"` - English stemming

**Index Options:**
- `"basic"` - Doc ID only
- `"freq"` - Doc ID + term frequency
- `"position"` - Doc ID + frequency + positions (full-text search)

#### Numeric Fields
```python
# Signed integers
schema_builder.add_integer_field(name, stored=False, indexed=False, fast=False)

# Unsigned integers
schema_builder.add_unsigned_field(name, stored=False, indexed=False, fast=False)

# Floating-point
schema_builder.add_float_field(name, stored=False, indexed=False, fast=False)
```

#### Other Field Types
```python
# Boolean
schema_builder.add_boolean_field(name, stored=False, indexed=False, fast=False)

# Date (i64 UTC timestamp)
schema_builder.add_date_field(name, stored=False, indexed=False, fast=False)

# IP Address
schema_builder.add_ip_addr_field(name, stored=False, indexed=False, fast=False)

# Facet (hierarchical categorization)
schema_builder.add_facet_field(name)

# Bytes (not searchable, storage only)
schema_builder.add_bytes_field(name, stored=False, indexed=False, fast=False)

# JSON Object
schema_builder.add_json_field(
    name,
    stored=False,
    fast=False,
    tokenizer_name="default",
    index_option="position"
)
```

### 3.5 Integration Patterns

**Current RexLit Schema (Assumed):**
```python
# Check rexlit/index/build.py for actual schema
schema_builder = tantivy.SchemaBuilder()
schema_builder.add_text_field("path", stored=True)
schema_builder.add_text_field("text", stored=False, tokenizer_name="en_stem")
schema_builder.add_text_field("custodian", stored=True, fast=True)
schema_builder.add_text_field("doctype", stored=True, fast=True)
# ... etc
schema = schema_builder.build()
```

**No Direct Vector Field Support:**
Tantivy does not natively support vector fields or ANN search. The integration strategy is:

1. **Tantivy:** BM25 lexical search (existing)
2. **hnswlib:** Dense vector search (new)
3. **Fusion Layer:** Combine results with RRF (new)

**Architecture:**
```
┌─────────────┐         ┌──────────────┐
│   Query     │────────▶│ BM25 Search  │
│             │         │  (Tantivy)   │
└─────────────┘         └──────────────┘
      │                        │
      │                        ▼
      │                  ┌──────────┐
      │                  │ BM25     │
      │                  │ Results  │
      │                  └──────────┘
      │                        │
      ▼                        │
┌──────────────┐               │
│ Dense Search │               │
│  (hnswlib)   │               │
└──────────────┘               │
      │                        │
      ▼                        │
┌──────────┐                   │
│ Dense    │                   │
│ Results  │                   │
└──────────┘                   │
      │                        │
      └────────┬───────────────┘
               ▼
        ┌─────────────┐
        │ RRF Fusion  │
        └─────────────┘
               │
               ▼
        ┌─────────────┐
        │ Final       │
        │ Results     │
        └─────────────┘
```

### 3.6 Tantivy + HNSW Coordination

**Index Build Phase:**
```python
# 1. Build Tantivy index (existing)
tantivy_index = build_tantivy_index(documents)

# 2. Build HNSW index (new, if --dense flag)
if dense_enabled:
    embeddings = embed_documents(documents)
    hnsw_index = build_hnsw_index(embeddings)

    # Save both
    tantivy_index.save()
    hnsw_index.save()
```

**Search Phase:**
```python
# 1. Query both indexes
bm25_results = tantivy_index.search(query_text)
dense_results = hnsw_index.search(query_embedding)

# 2. Fuse with RRF
final_results = reciprocal_rank_fusion(bm25_results, dense_results)
```

**Metadata Coordination:**
Store HNSW metadata alongside Tantivy index:
```
index_dir/
  ├── tantivy/          # Existing Tantivy files
  │   ├── meta.json
  │   └── ...
  └── hnsw/             # New HNSW files
      ├── vectors.bin   # hnswlib index
      └── metadata.json # Dim, M, ef_construction, etc.
```

---

## 4. Numpy Array Handling

### 4.1 Overview

**Package:** numpy 2.3.4
**RexLit Usage:** Vector operations, normalization, serialization

### 4.2 Vector Normalization

**L2 Normalization (Unit Vectors):**
```python
import numpy as np

# Single vector
vector = np.array([3.0, 4.0])
norm = np.linalg.norm(vector, ord=2)  # L2 norm = 5.0
normalized = vector / norm
# Result: [0.6, 0.8], norm = 1.0

# Batch of vectors (N, dim)
vectors = np.random.rand(1000, 768)
norms = np.linalg.norm(vectors, axis=1, keepdims=True)
normalized_vectors = vectors / norms
# Shape: (1000, 768), each row has L2 norm = 1.0
```

**Why Normalize:**
- Kanon 2 returns L2-normalized embeddings by default
- hnswlib `space='ip'` with normalized vectors = cosine similarity
- Ensures distance comparisons are meaningful

**Verification:**
```python
# Check if vectors are normalized
norms = np.linalg.norm(vectors, axis=1)
assert np.allclose(norms, 1.0, atol=1e-6)
```

### 4.3 Distance Calculations

**L2 Distance (Euclidean):**
```python
def l2_distance(a, b):
    return np.linalg.norm(a - b, ord=2)

# Batch distances
def batch_l2_distance(queries, documents):
    # queries: (N, dim), documents: (M, dim)
    # Returns: (N, M) distance matrix
    return np.linalg.norm(
        queries[:, None, :] - documents[None, :, :],
        axis=2
    )
```

**Cosine Similarity:**
```python
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# For normalized vectors: cosine = dot product
def cosine_similarity_normalized(a, b):
    return np.dot(a, b)

# Batch cosine (normalized vectors)
def batch_cosine_similarity(queries, documents):
    # queries: (N, dim), documents: (M, dim)
    # Returns: (N, M) similarity matrix
    return queries @ documents.T
```

### 4.4 Memory-Efficient Operations

**Avoid Copies:**
```python
# Bad: Creates copy
normalized = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

# Better: In-place (if you don't need original)
norms = np.linalg.norm(vectors, axis=1, keepdims=True)
vectors /= norms  # In-place division
```

**Use float32 Instead of float64:**
```python
# Kanon 2 returns list[float] (Python floats are float64)
embeddings_f64 = np.array(response.embeddings[0].embedding)  # float64
embeddings_f32 = embeddings_f64.astype(np.float32)  # Half the memory

# hnswlib accepts float32
index.add_items(embeddings_f32, ids)
```

### 4.5 Serialization

**Save/Load Numpy Arrays:**
```python
# Save single array
np.save('embeddings.npy', embeddings)

# Load
embeddings = np.load('embeddings.npy')

# Save multiple arrays (compressed)
np.savez_compressed('vectors.npz', embeddings=embeddings, ids=ids)

# Load
data = np.load('vectors.npz')
embeddings = data['embeddings']
ids = data['ids']
```

**Integration with hnswlib:**
```python
# hnswlib handles numpy arrays natively
index.add_items(data=embeddings_np, ids=ids_np)
labels, distances = index.knn_query(query_np, k=10)
```

### 4.6 Type Hints for Vectors

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
        """Embed documents.

        Returns:
            Array of shape (len(texts), dim)
        """
        ...

    def embed_query(
        self,
        query: str,
        *,
        dim: int = 768,
    ) -> NDArray[np.float32]:
        """Embed query.

        Returns:
            Array of shape (dim,)
        """
        ...
```

**RexLit Type Checking:**
Given RexLit uses `mypy` in strict mode, use `numpy.typing.NDArray` for proper type hints:
```python
from numpy.typing import NDArray

def process_vectors(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    """Type-safe vector processing."""
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
```

---

## 5. Reciprocal Rank Fusion (RRF)

### 5.1 Overview

RRF is a simple, effective algorithm for combining ranked results from multiple retrieval systems (e.g., BM25 + dense vectors).

**Key Advantages:**
- No parameter tuning required
- Works with heterogeneous rankers
- Robust to score scale differences
- Empirically outperforms complex fusion methods

### 5.2 Mathematical Formula

For a document `d` appearing in results from multiple queries/systems:

```
RRF_score(d) = Σ [ 1 / (k + rank(d, system_i)) ]
                i
```

Where:
- `k` = constant (typically 60)
- `rank(d, system_i)` = rank of document `d` in system `i` (1-based)

**Properties:**
- Documents ranked higher contribute more to the score
- Constant `k` prevents division by zero
- Scores are always positive
- Documents appearing in multiple systems get higher scores

### 5.3 Implementation

**Basic Implementation:**
```python
def reciprocal_rank_fusion(
    ranked_results: list[list[str]],  # Multiple ranked lists
    k: int = 60,
) -> list[str]:
    """Fuse multiple ranked result lists using RRF.

    Args:
        ranked_results: List of ranked document ID lists
        k: RRF constant (default 60)

    Returns:
        Fused ranked list of document IDs
    """
    scores: dict[str, float] = {}

    for result_list in ranked_results:
        for rank, doc_id in enumerate(result_list, start=1):
            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += 1.0 / (k + rank)

    # Sort by score descending
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in sorted_docs]
```

**RexLit-Specific Implementation:**
```python
from dataclasses import dataclass

@dataclass
class SearchResult:
    doc_id: str
    score: float
    source: str  # 'bm25' or 'dense'

def hybrid_search(
    query: str,
    bm25_searcher,
    dense_searcher,
    k: int = 10,
    rrf_k: int = 60,
) -> list[SearchResult]:
    """Hybrid search combining BM25 and dense retrieval.

    Args:
        query: Search query text
        bm25_searcher: Tantivy searcher
        dense_searcher: HNSW searcher
        k: Number of results to return
        rrf_k: RRF constant

    Returns:
        Top-k fused results
    """
    # 1. BM25 search
    bm25_results = bm25_searcher.search(query, limit=100)
    bm25_docs = [r.doc_id for r in bm25_results]

    # 2. Dense search
    query_embedding = embed_query(query)
    dense_labels, dense_distances = dense_searcher.query(query_embedding, k=100)
    dense_docs = [str(label) for label in dense_labels[0]]

    # 3. RRF fusion
    scores: dict[str, float] = {}

    # Add BM25 scores
    for rank, doc_id in enumerate(bm25_docs, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)

    # Add dense scores
    for rank, doc_id in enumerate(dense_docs, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)

    # 4. Sort and return top-k
    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        SearchResult(doc_id=doc_id, score=score, source='hybrid')
        for doc_id, score in sorted_results[:k]
    ]
```

### 5.4 Parameter Tuning

**k Value:**
- **Recommended:** k=60 (empirically validated)
- **Range:** 1-100
- **Effect:**
  - Lower k → More weight to top-ranked documents
  - Higher k → More uniform weighting across ranks

**Empirical Observation:**
From RRF literature: "k performs best when set to a small value, such as 60."

**No Tuning Required:**
Unlike weighted fusion methods, RRF doesn't require relevance scores or weights. The constant `k` is robust across different domains.

### 5.5 Integration with RexLit

**Module:** `rexlit/index/hybrid.py`

```python
"""Hybrid search combining BM25 and dense retrieval."""

from typing import Protocol
import numpy as np
from numpy.typing import NDArray

def rrf_score(
    doc_id: str,
    ranked_lists: list[list[str]],
    k: int = 60,
) -> float:
    """Compute RRF score for a document.

    Args:
        doc_id: Document ID
        ranked_lists: Multiple ranked lists
        k: RRF constant

    Returns:
        RRF score (higher = more relevant)
    """
    score = 0.0
    for ranked_list in ranked_lists:
        try:
            rank = ranked_list.index(doc_id) + 1  # 1-based rank
            score += 1.0 / (k + rank)
        except ValueError:
            # Document not in this list
            continue
    return score

def fuse(
    bm25_results: list[str],
    dense_results: list[str],
    k: int = 60,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """Fuse BM25 and dense results using RRF.

    Args:
        bm25_results: Ranked list from BM25
        dense_results: Ranked list from dense search
        k: RRF constant
        top_k: Number of results to return

    Returns:
        Top-k (doc_id, score) tuples
    """
    all_docs = set(bm25_results) | set(dense_results)
    scores = {
        doc_id: rrf_score(doc_id, [bm25_results, dense_results], k=k)
        for doc_id in all_docs
    }

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results[:top_k]
```

### 5.6 BM25 Fallback

**Offline Behavior:**
When dense search is unavailable (offline mode, no HNSW index), fallback to BM25-only:

```python
def search(
    query: str,
    bm25_searcher,
    dense_searcher=None,
    hybrid: bool = False,
) -> list[SearchResult]:
    """Search with optional hybrid mode.

    Args:
        query: Search query
        bm25_searcher: Tantivy searcher
        dense_searcher: Optional HNSW searcher
        hybrid: Use hybrid search if dense_searcher available

    Returns:
        Search results
    """
    if hybrid and dense_searcher is not None:
        # Hybrid search
        return hybrid_search(query, bm25_searcher, dense_searcher)
    else:
        # BM25-only fallback
        return bm25_searcher.search(query)
```

---

## 6. Python Type Hints and Protocols

### 6.1 Protocol Best Practices (PEP 544)

**Basic Protocol Definition:**
```python
from typing import Protocol

class Closeable(Protocol):
    """Protocol for objects with close() method."""

    def close(self) -> None:
        """Close the resource."""
        ...
```

**No Explicit Inheritance Required:**
```python
class File:
    def close(self) -> None:
        print("Closing file")

# File is a structural subtype of Closeable (no inheritance needed)
def close_resource(resource: Closeable) -> None:
    resource.close()

close_resource(File())  # Type-checks!
```

### 6.2 Generic Protocols

**Python 3.11 Syntax:**
```python
from typing import Protocol, TypeVar, Iterator

T = TypeVar('T')

class Iterable(Protocol[T]):
    """Protocol for iterable containers."""

    def __iter__(self) -> Iterator[T]:
        ...

# Usage
def sum_ints(items: Iterable[int]) -> int:
    return sum(items)
```

**Covariant Type Variables:**
```python
T_co = TypeVar('T_co', covariant=True)

class Container(Protocol[T_co]):
    """Covariant container protocol."""

    def get(self) -> T_co:
        ...

# Container[Dog] is a subtype of Container[Animal] if Dog <: Animal
```

**Contravariant Type Variables:**
```python
T_contra = TypeVar('T_contra', contravariant=True)

class Sink(Protocol[T_contra]):
    """Contravariant sink protocol."""

    def put(self, item: T_contra) -> None:
        ...

# Sink[Animal] is a subtype of Sink[Dog] if Dog <: Animal
```

### 6.3 Runtime Checking

**@runtime_checkable Decorator:**
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class SupportsClose(Protocol):
    def close(self) -> None:
        ...

# Enable isinstance checks
assert isinstance(open('file.txt'), SupportsClose)
```

**Limitations:**
- Only checks attribute/method presence, NOT signatures
- Does not validate return types or parameter types
- Use sparingly (static type checking is primary goal)

**When to Use:**
- Duck typing validation at runtime
- Plugin/adapter discovery
- Debugging type issues

**When NOT to Use:**
- Performance-critical code (overhead)
- Complex type signatures (unreliable)
- Security validation (not type-safe)

### 6.4 Protocol Composition

**Extending Protocols:**
```python
from typing import Protocol, Sized

class SizedCloseable(Sized, SupportsClose, Protocol):
    """Combines Sized and SupportsClose protocols."""
    pass

# Must have both __len__ and close()
def process_resource(resource: SizedCloseable) -> None:
    print(f"Size: {len(resource)}")
    resource.close()
```

**Important Rule:**
When `Protocol` is in base list, ALL bases must be protocols (can't mix protocols and regular classes).

### 6.5 RexLit Port Interface Patterns

**Standard Port Pattern:**
```python
from typing import Protocol
from pathlib import Path
from pydantic import BaseModel

class ResultDTO(BaseModel):
    """Data transfer object for results."""
    path: str
    score: float

class SomePort(Protocol):
    """Port interface for some operation.

    Adapters: AdapterA (offline), AdapterB (online).

    Side effects:
    - Writes to filesystem
    - May make network calls (if online)
    """

    def process(self, path: Path, *, flag: bool = False) -> ResultDTO:
        """Process a file.

        Args:
            path: Input file path
            flag: Optional processing flag

        Returns:
            Result DTO with metadata
        """
        ...

    def is_online(self) -> bool:
        """Check if adapter requires network.

        Returns:
            True if online adapter
        """
        ...
```

**Generic Port (If Needed):**
```python
from typing import Protocol, TypeVar, Generic

T = TypeVar('T')

class Repository(Protocol[T]):
    """Generic repository protocol."""

    def get(self, id: str) -> T:
        """Get item by ID."""
        ...

    def save(self, item: T) -> None:
        """Save item."""
        ...
```

### 6.6 Type Hints for Embeddings

**Embedding Port Interface:**
```python
from typing import Protocol
import numpy as np
from numpy.typing import NDArray

class EmbeddingPort(Protocol):
    """Port for dense embedding generation.

    Adapters: Kanon2Adapter (online).

    Side effects:
    - Network API calls (requires --online flag)
    - Audit ledger writes
    """

    def embed_documents(
        self,
        texts: list[str],
        *,
        dim: int = 768,
    ) -> NDArray[np.float32]:
        """Embed corpus documents.

        Args:
            texts: Document texts to embed
            dim: Embedding dimensionality

        Returns:
            Array of shape (len(texts), dim), L2-normalized
        """
        ...

    def embed_query(
        self,
        query: str,
        *,
        dim: int = 768,
    ) -> NDArray[np.float32]:
        """Embed search query.

        Args:
            query: Query text
            dim: Embedding dimensionality

        Returns:
            Array of shape (dim,), L2-normalized
        """
        ...

    def is_online(self) -> bool:
        """Check if adapter requires network."""
        ...
```

**Vector Store Port:**
```python
from typing import Protocol
import numpy as np
from numpy.typing import NDArray

class VectorStorePort(Protocol):
    """Port for ANN vector storage.

    Adapters: HNSWAdapter (offline storage).

    Side effects:
    - Writes index to filesystem
    """

    def build(
        self,
        vectors: NDArray[np.float32],
        ids: list[int],
        *,
        M: int = 16,
        ef_construction: int = 200,
    ) -> None:
        """Build index from vectors."""
        ...

    def save(self, path: str) -> None:
        """Persist index to disk."""
        ...

    def load(self, path: str, *, ef: int = 100) -> None:
        """Load index from disk."""
        ...

    def query(
        self,
        vectors: NDArray[np.float32],
        k: int = 10,
    ) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
        """Query k nearest neighbors.

        Returns:
            (labels, distances) arrays of shape (N, k)
        """
        ...

    def is_online(self) -> bool:
        """Always False (offline storage)."""
        ...
```

### 6.7 Mypy Configuration for RexLit

Current `pyproject.toml` settings are strict:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
disallow_untyped_defs = true
disallow_any_generics = true
```

**Ignore Missing Imports:**
```toml
[[tool.mypy.overrides]]
module = [
    "hnswlib.*",
    "isaacus.*",
    # ... existing modules
]
ignore_missing_imports = true
```

**Type Stubs:**
If type stubs are available, install them:
```bash
pip install types-numpy  # Already has stubs
# hnswlib, isaacus have no official stubs
```

---

## 7. Integration Checklist for RexLit

### 7.1 Files to Create

**Port Interfaces:**
- `rexlit/app/ports/embedding.py` - EmbeddingPort protocol
- `rexlit/app/ports/vector_store.py` - VectorStorePort protocol

**Adapters:**
- `rexlit/app/adapters/kanon2_adapter.py` - Isaacus client wrapper
- `rexlit/app/adapters/hnsw_adapter.py` - hnswlib wrapper

**Domain Modules:**
- `rexlit/index/hnsw_store.py` - HNSW index management
- `rexlit/index/hybrid.py` - RRF fusion logic

**Configuration:**
- Update `rexlit/config.py` with embedding settings:
  ```python
  class Settings(BaseSettings):
      # ... existing settings

      # Embedding settings
      isaacus_api_key: str | None = Field(default=None, alias="ISAACUS_API_KEY")
      isaacus_api_base: str = "https://api.isaacus.com"
      embedding_dim: int = 768

      # HNSW settings
      hnsw_m: int = 16
      hnsw_ef_construction: int = 200
      hnsw_ef_search: int = 100
  ```

**CLI Updates:**
- `rexlit/cli.py`:
  ```python
  @app.command()
  def index_build(
      path: Path,
      # ... existing args
      dense: bool = False,
      dim: int = 768,
      online: bool = False,
  ):
      """Build index with optional dense embeddings."""
      ...

  @app.command()
  def search(
      query: str,
      # ... existing args
      hybrid: bool = False,
      top: int = 10,
  ):
      """Search with optional hybrid mode."""
      ...
  ```

### 7.2 Bootstrap Wiring

Update `rexlit/bootstrap.py`:
```python
from rexlit.app.adapters.kanon2_adapter import Kanon2Adapter
from rexlit.app.adapters.hnsw_adapter import HNSWAdapter

def create_container(settings: Settings):
    # ... existing adapters

    # Embedding adapter (online)
    embedding_adapter = None
    if settings.isaacus_api_key:
        embedding_adapter = Kanon2Adapter(
            api_key=settings.isaacus_api_key,
            base_url=settings.isaacus_api_base,
        )

    # Vector store adapter (offline)
    vector_store_adapter = HNSWAdapter(
        dim=settings.embedding_dim,
        space='l2',
    )

    # ... wire into services
```

### 7.3 Audit Logging

Extend audit ledger schema for embedding operations:
```python
ledger.log(
    operation="embed_documents",
    inputs=[f"{len(texts)} texts"],
    outputs=[f"{len(embeddings)} embeddings"],
    args={
        "model": "kanon-2-embedder",
        "dim": 768,
        "task": "retrieval/document",
        "latency_sec": elapsed_time,
        "tokens_used": usage.input_tokens,
    }
)
```

### 7.4 Offline Gating

Ensure all online operations check:
```python
from rexlit.utils.offline import require_online

class Kanon2Adapter:
    def __init__(self, ...):
        require_online("Kanon 2 embedding generation")
        # Raises if REXLIT_ONLINE != 1
```

### 7.5 Testing

**New Test Files:**
- `tests/test_embedding_adapter.py` - Kanon 2 adapter tests (online)
- `tests/test_hnsw_adapter.py` - HNSW adapter tests (offline)
- `tests/test_hybrid_search.py` - RRF fusion tests
- `tests/test_dense_index_build.py` - Integration test

**Coverage Areas:**
- Embedding generation (mocked)
- HNSW index build/load/query
- RRF fusion correctness
- Offline gating (should raise when --online missing)
- Audit ledger entries
- Deterministic ordering

### 7.6 Documentation Updates

**README.md:**
Add section on dense/hybrid search:
```markdown
## Dense/Hybrid Search (Kanon 2)

RexLit supports optional dense vector search using Kanon 2 embeddings:

# Build index with dense embeddings (requires --online)
rexlit index build ./docs --dense --dim 768 --online

# Search with hybrid mode (BM25 + dense)
rexlit search "contract breach" --hybrid --top 10

# BM25-only search (offline, no dense index needed)
rexlit search "contract breach" --top 10
```

**Configuration:**
```markdown
### Environment Variables

- `ISAACUS_API_KEY` - Kanon 2 API key (required for --dense)
- `ISAACUS_API_BASE` - Custom Isaacus endpoint (optional)
- `REXLIT_ONLINE` - Enable network features (1 = online, 0 = offline)
```

**CLI-GUIDE.md:**
Document new flags and workflows.

**SECURITY.md:**
Note online dependency and self-hosting options.

---

## 8. Version-Specific Constraints

### 8.1 Package Versions

| Package | Installed | Required | Constraints |
|---------|-----------|----------|-------------|
| hnswlib | 0.8.0 | >=0.7.0 | Python 3.11+ compatible |
| isaacus | 0.9.1 | >=0.1.0 | Requires httpx, pydantic v2 |
| numpy | 2.3.4 | >=1.26.0 | Use numpy.typing for type hints |
| tantivy | 0.25.0 | >=0.22.0 | Latest release (Sep 2025) |

### 8.2 Python Version

**Target:** Python 3.11+

**Type Hints:**
- Use `typing.Protocol` (not `typing_extensions`)
- Use `list[T]` instead of `List[T]` (PEP 585)
- Use `X | Y` instead of `Union[X, Y]` (PEP 604)
- Use `numpy.typing.NDArray` for array hints

**Example:**
```python
from typing import Protocol
import numpy as np
from numpy.typing import NDArray

class Port(Protocol):
    def process(
        self,
        items: list[str],  # Not List[str]
        flag: bool | None = None,  # Not Optional[bool]
    ) -> NDArray[np.float32]:
        ...
```

### 8.3 Compatibility Notes

**hnswlib 0.8.0:**
- Stable API (no breaking changes expected)
- Thread safety constraints remain
- Pickling supported but not thread-safe

**isaacus 0.9.1:**
- Uses Pydantic v2 (compatible with RexLit)
- Max 128 texts per batch
- Auto-reads `ISAACUS_API_KEY` from environment

**tantivy 0.25.0:**
- Latest release as of Sep 2025
- No vector field support (use hnswlib separately)
- Rust-backed (fast, memory-safe)

**numpy 2.3.4:**
- Major version bump (2.x) from 1.x
- Backward compatible for most operations
- Use `numpy.typing.NDArray` for strict type hints

---

## 9. Performance Considerations

### 9.1 Memory Budgeting

**Example: 100K documents, 768 dims**

| Component | Memory | Notes |
|-----------|--------|-------|
| Raw vectors (float32) | ~307 MB | 100K × 768 × 4 bytes |
| HNSW graph (M=16) | ~130 MB | ~20-40% overhead |
| Tantivy index | ~500 MB | Text index, varies by corpus |
| **Total** | **~937 MB** | <1 GB for 100K docs |

**Scaling:**
- 1M documents: ~9.4 GB
- 10M documents: ~94 GB (consider sharding)

### 9.2 Build Time Estimates

**Embedding Generation (Kanon 2):**
- Network-bound (API latency)
- Batch size: 128 texts/request
- Estimate: ~100-200 ms/batch
- 100K docs: ~1,000 batches × 150 ms = **2.5 minutes**

**HNSW Index Build:**
- CPU-bound (graph construction)
- Parallelized with `num_threads=-1`
- Estimate: ~50-100 vectors/second (768 dims, M=16)
- 100K docs: **17-34 minutes** (single-threaded)
- With 8 cores: **2-4 minutes**

**Total for 100K docs:** ~5-7 minutes (embedding + HNSW)

### 9.3 Query Performance

**BM25 (Tantivy):**
- <50 ms for 100K docs
- Scales logarithmically

**Dense (HNSW):**
- <10 ms for 100K docs (ef=100)
- Scales sub-linearly

**Hybrid (RRF):**
- BM25 + Dense + Fusion
- <100 ms total for 100K docs

### 9.4 Optimization Tips

**Reduce Dimensions:**
```python
# Use 768 instead of 1792 for 2.3× memory savings
response = client.embeddings.create(texts=docs, dimensions=768)
```

**Lower HNSW Parameters:**
```python
# Faster build, slightly lower recall
index.init_index(M=12, ef_construction=100)
index.set_ef(50)  # Faster queries
```

**Batch Embedding Requests:**
```python
# Process in batches of 128 (max)
for i in range(0, len(texts), 128):
    batch = texts[i:i+128]
    embeddings = client.embeddings.create(texts=batch)
```

---

## 10. Reference Links

### 10.1 Official Documentation

**hnswlib:**
- GitHub: https://github.com/nmslib/hnswlib
- Parameter Guide: https://github.com/nmslib/hnswlib/blob/master/ALGO_PARAMS.md

**Isaacus:**
- Website: https://isaacus.com
- Docs: https://docs.isaacus.com
- Models: https://docs.isaacus.com/models/introduction
- Quickstart: https://docs.isaacus.com/quickstart

**Tantivy:**
- GitHub: https://github.com/quickwit-oss/tantivy-py
- Docs: https://tantivy-py.readthedocs.io
- PyPI: https://pypi.org/project/tantivy/

**Numpy:**
- Docs: https://numpy.org/doc/stable/
- Typing: https://numpy.org/doc/stable/reference/typing.html

**Python Protocols:**
- PEP 544: https://peps.python.org/pep-0544/
- Typing Docs: https://docs.python.org/3.11/library/typing.html

### 10.2 Research Papers

**HNSW:**
- "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs"
- Malkov & Yashunin, 2018
- https://arxiv.org/abs/1603.09320

**RRF:**
- "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"
- Cormack et al., 2009

### 10.3 Blog Posts & Guides

- "A practical guide to selecting HNSW hyperparameters" - OpenSearch
- "Implementing Reciprocal Rank Fusion (RRF) in Python" - safjan.com
- "Introducing Kanon 2 Embedder" - Isaacus blog

---

## Appendix A: Quick Reference

### A.1 hnswlib Cheat Sheet

```python
import hnswlib
import numpy as np

# Create index
index = hnswlib.Index(space='l2', dim=768)
index.init_index(max_elements=100000, M=16, ef_construction=200)

# Add vectors
vectors = np.random.rand(1000, 768).astype(np.float32)
ids = np.arange(1000)
index.add_items(vectors, ids)

# Save
index.save_index('index.bin')

# Load
index = hnswlib.Index(space='l2', dim=768)
index.load_index('index.bin')
index.set_ef(100)  # Set query accuracy

# Query
query = np.random.rand(768).astype(np.float32)
labels, distances = index.knn_query(query, k=10)
```

### A.2 Isaacus Cheat Sheet

```python
from isaacus import Isaacus
import os

# Initialize
client = Isaacus(api_key=os.getenv("ISAACUS_API_KEY"))

# Embed documents
response = client.embeddings.create(
    model="kanon-2-embedder",
    texts=["Document 1", "Document 2"],
    dimensions=768,
    task="retrieval/document",
)

embeddings = [emb.embedding for emb in response.embeddings]
tokens = response.usage.input_tokens
```

### A.3 RRF Cheat Sheet

```python
def rrf_fusion(bm25_results, dense_results, k=60):
    scores = {}

    for rank, doc in enumerate(bm25_results, 1):
        scores[doc] = scores.get(doc, 0) + 1 / (k + rank)

    for rank, doc in enumerate(dense_results, 1):
        scores[doc] = scores.get(doc, 0) + 1 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

---

## Appendix B: Troubleshooting

### B.1 Common Issues

**hnswlib:**
- **Issue:** "Index not initialized"
  - **Fix:** Call `init_index()` before `add_items()`

- **Issue:** "ef must be >= k"
  - **Fix:** Ensure `set_ef(ef)` where `ef >= k`

- **Issue:** Low recall
  - **Fix:** Increase `ef_construction` and rebuild, or increase `ef` at query time

**Isaacus:**
- **Issue:** "api_key client option must be set"
  - **Fix:** Set `ISAACUS_API_KEY` environment variable

- **Issue:** RateLimitError
  - **Fix:** Implement exponential backoff, reduce batch size

- **Issue:** "content exceeds maximum input length"
  - **Fix:** Use `overflow_strategy="drop_end"` or chunk texts

**RexLit Integration:**
- **Issue:** "Online mode required"
  - **Fix:** Use `--online` flag or `export REXLIT_ONLINE=1`

- **Issue:** Import linter failures
  - **Fix:** Ensure CLI doesn't directly import adapters, use bootstrap

---

**End of Document**

*Research compiled: 2025-10-27*
*For: RexLit Kanon 2 Integration (Phase 2, Task 2.1)*
*Next Steps: See Next_plan.md for implementation tasks*
