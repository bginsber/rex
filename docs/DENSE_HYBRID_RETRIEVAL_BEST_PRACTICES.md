# Dense and Hybrid Retrieval Best Practices Research

**Research Date:** 2025-10-27
**Compiled for:** RexLit - Offline-First Legal E-Discovery Toolkit

## Table of Contents

1. [Dense Embedding Best Practices](#1-dense-embedding-best-practices)
2. [HNSW Parameter Tuning](#2-hnsw-parameter-tuning)
3. [Hybrid Search Fusion Techniques](#3-hybrid-search-fusion-techniques)
4. [Offline-First Embedding Architecture](#4-offline-first-embedding-architecture)
5. [Performance and Scalability](#5-performance-and-scalability)
6. [Security and Audit](#6-security-and-audit)
7. [Implementation Recommendations for RexLit](#7-implementation-recommendations-for-rexlit)
8. [References](#8-references)

---

## 1. Dense Embedding Best Practices

### 1.1 Document vs Query Embedding Differences

**Key Concept: Asymmetric Retrieval**

In asymmetric semantic search, you typically have a short query (like a question or keywords) and want to find a longer paragraph answering the query. This is fundamentally different from symmetric search where query and document share the same meaning.

**Implementation Approaches:**

- **Input Type Parameter**: Some APIs (e.g., Cohere) use an `input_type` parameter to distinguish between "document" and "query" embeddings
- **Prefix Method**: Other models (e.g., E5) use prefixes like "query:" and "passage:" prepended to the input text
- **Specialized Models**: Use models designed for asymmetric retrieval when implementing RAG or question-answering systems

**Authority Level:** Industry standard (OpenAI, Cohere, Sentence Transformers documentation)

**Sources:**
- https://acedev003.com/rand_bytes/symmetric-vs-asymmetric-semantic-search
- https://dtunkelang.medium.com/ai-powered-search-embedding-based-retrieval-and-retrieval-augmented-generation-rag-cabeaba26a8b

### 1.2 Optimal Chunk Sizes

**Recommended Range: 1-2K tokens with 10-20% overlap**

**Best Practices (2024-2025):**

- **Token Windows**: Use overlapping windows of 20-50 tokens to maintain context continuity between chunks
- **Overlap Rationale**: Ensures information at chunk boundaries is not lost or contextually isolated
- **Semantic Chunking**: Consider using semantic chunkers that analyze cosine similarity between adjacent embeddings to identify natural chunk boundaries

**Chunking Methods:**

1. **Fixed-Size Chunking**: Simple 512-1024 token chunks with 10-15% overlap
2. **Semantic Chunking**: Kamradt-Semantic-Chunker begins with sentence-level segmentation and identifies chunk boundaries at points of significant semantic discontinuity
3. **Late Chunking (2025)**: Advanced technique showing that overlap neither significantly improves nor harms retrieval performance
4. **Context-Aware**: Split on punctuation, paragraph breaks, or structural markers (markdown, HTML tags)

**Legal Document Considerations:**
- Preserve section boundaries (numbered paragraphs, exhibits)
- Keep citation context intact
- Respect privilege designations and Bates number ranges

**Authority Level:** Research-backed (arXiv 2024-2025) + industry practice

**Sources:**
- https://medium.com/@adnanmasood/optimizing-chunking-embedding-and-vectorization-for-retrieval-augmented-generation-ea3b083b68f7
- https://arxiv.org/html/2409.04701v3 (Late Chunking paper)
- https://stackoverflow.blog/2024/12/27/breaking-up-is-hard-to-do-chunking-in-rag-applications/

### 1.3 Dimensionality Choices

**The 1024 Sweet Spot:**

Setting 1024 dimensions appears to be the sweet spot for many embedding models (e.g., text-embedding-3-large), providing nearly the same performance as 3072 dimensions but using only 1/3 the storage (4KB vs 12KB per vector).

**Common Dimensionalities:**

| Dimensions | Model Examples | Storage/Vector | Use Case |
|------------|---------------|----------------|----------|
| 384 | all-MiniLM-L6-v2 | 1.5 KB | Fast, lightweight, good for millions of docs |
| 768 | BERT, Sentence-T5 | 3 KB | Industry standard, balanced performance |
| 1024 | text-embedding-3-large (truncated) | 4 KB | **Recommended sweet spot** |
| 1536 | text-embedding-ada-002 | 6 KB | Higher accuracy, slower retrieval |
| 3072+ | Latest large models | 12+ KB | Diminishing returns for most use cases |

**Tradeoffs:**

- **Higher Dimensions (1536+)**: Finer semantic distinctions, can differentiate subtle differences (e.g., "bank" as financial vs riverbank), but require 2-4x more storage and increase query latency
- **Lower Dimensions (384-768)**: Faster search (20ms vs 50ms), lower storage costs, but less semantic nuance
- **Matryoshka Representation Learning**: Modern models like OpenAI's embeddings train with "most important" concepts first, meaning 1024d might be as useful as 3072d if the first 1024 dimensions compress information efficiently

**Memory Impact for 100K Documents:**
- 384d: ~150 MB
- 768d: ~300 MB
- 1024d: ~400 MB
- 1536d: ~600 MB
- (Raw vector storage, not including HNSW index overhead)

**Recommendation for RexLit:**
Start with 1024 dimensions for optimal balance of accuracy and performance with 100K+ document corpora.

**Authority Level:** Industry consensus + empirical benchmarks

**Sources:**
- https://devblogs.microsoft.com/azure-sql/embedding-models-and-dimensions-optimizing-the-performance-resource-usage-ratio/
- https://supabase.com/blog/fewer-dimensions-are-better-pgvector
- https://vickiboykis.com/2025/09/01/how-big-are-our-embeddings-now-and-why/

### 1.4 Normalization and Preprocessing

**Controversial Area: Context-Dependent Decisions**

Modern transformer-based embedding models (BERT, E5, Sentence Transformers) are typically trained on raw text with minimal preprocessing. Over-preprocessing can harm performance.

**General Guidelines:**

1. **Lowercase Normalization**:
   - **When to use**: Case-insensitive search (most legal documents)
   - **When to skip**: Case-sensitive models, proper noun importance, stylometry analysis
   - **Verdict**: Use selectively based on model training data

2. **Punctuation Handling**:
   - **Caution**: Removing all punctuation may be detrimental if the model learned syntactic cues from it
   - **Legal context**: Preserve punctuation for citation parsing, dates, section numbers (e.g., "§ 1983")
   - **Verdict**: Normalize special characters but keep meaningful punctuation

3. **Best Practice Combination**:
   - Research shows lemmatization + punctuation splitting achieves highest accuracy (79.09%)
   - However, this applies to older NLP pipelines, not modern transformer embeddings

**Recommended Preprocessing Pipeline for Legal Documents:**

```python
# Minimal preprocessing for modern embedding models
def preprocess_for_embedding(text: str) -> str:
    # Normalize whitespace
    text = " ".join(text.split())

    # Preserve legal citations and Bates numbers
    # Do NOT lowercase, do NOT remove punctuation

    # Optional: remove OCR artifacts if present
    # text = remove_ocr_artifacts(text)

    return text
```

**Authority Level:** Mixed - depends heavily on specific embedding model and use case

**Sources:**
- https://procodebase.com/article/best-practices-for-text-preprocessing-in-embedding-generation
- https://community.openai.com/t/preprocessing-for-embeddings/295017
- https://stackoverflow.com/questions/44291798/how-to-preprocess-text-for-embedding

---

## 2. HNSW Parameter Tuning

### 2.1 Recommended M, ef_construction, ef_search Values

**Starting Point (Official Recommendation):**

Start with **M=16** and **ef_construction=200**, then tune based on empirical benchmarks.

**M (Maximum Connections per Node):**

| M Value | Use Case | Memory per Vector | Build Time | Query Speed |
|---------|----------|------------------|------------|-------------|
| 5-6 | Low-dimensional data (d<50) | Minimal | Fast | Moderate recall |
| 12-16 | **General purpose** | ~200 bytes | Moderate | Good recall |
| 32-48 | High-dimensional (d>512), high recall needs | ~400 bytes | Slow | Excellent recall |
| 64 | Maximum quality (face descriptors, etc.) | ~600 bytes | Very slow | Best recall |

**M determines memory consumption**: Approximately **M × 8-10 bytes per vector** (for storing neighbor references).

**ef_construction (Index Build Quality):**

| ef_construction | Build Time | Index Quality | Recommendation |
|----------------|------------|---------------|----------------|
| 100 | Fast | Basic | Development only |
| 200 | Moderate | **Good (default start)** | Most use cases |
| 400 | 2x slower | Excellent | Production with high recall needs |
| 1000+ | Very slow | Diminishing returns | Only if M is very high |

**Relationship**: `M × ef_construction` is roughly constant. If you need ef_construction > 1000, increase M instead.

**ef_search (Query-Time Parameter):**

Control recall vs latency at query time. Start with ef_search = 50-100, then tune:

```python
# Tuning process (pseudocode)
for ef in [50, 100, 200, 400]:
    recall = benchmark_recall(ef_search=ef)
    latency = measure_latency(ef_search=ef)
    if recall >= 0.95:
        optimal_ef_search = ef
        break
```

**Authority Level:** Official hnswlib documentation + OpenSearch, Pinecone, Milvus guides

**Sources:**
- https://github.com/nmslib/hnswlib/blob/master/ALGO_PARAMS.md (Official parameters guide)
- https://opensearch.org/blog/a-practical-guide-to-selecting-hnsw-hyperparameters/
- https://www.pinecone.io/learn/series/faiss/hnsw/
- https://milvus.io/docs/hnsw.md

### 2.2 Memory Sizing Formulas

**Core Formula:**

```
Memory per vector = (d × 4) + (M × 2 × 4) bytes

Where:
  d = vector dimensionality
  M = max connections per node
  4 = bytes per float32 value
  M × 2 = neighbors (2×M at base level for most nodes)
```

**Example Calculations:**

1. **100K vectors, 1024 dimensions, M=16:**
   - Per vector: (1024 × 4) + (16 × 2 × 4) = 4,096 + 128 = 4,224 bytes
   - Total: 4,224 × 100,000 = 422.4 MB

2. **100K vectors, 768 dimensions, M=32:**
   - Per vector: (768 × 4) + (32 × 2 × 4) = 3,072 + 256 = 3,328 bytes
   - Total: 3,328 × 100,000 = 332.8 MB

3. **1M vectors, 1536 dimensions, M=16:**
   - Per vector: (1536 × 4) + (16 × 2 × 4) = 6,144 + 128 = 6,272 bytes
   - Total: 6,272 × 1,000,000 = 6.27 GB

**Industry Rules of Thumb:**

- **Weaviate**: Memory usage ≈ 2× the raw vector data footprint
- **General**: HNSW requires 1.5-2× memory of raw vectors due to graph structure

**RexLit 100K Document Estimate (1024d, M=16):**
- Raw vectors: ~400 MB
- HNSW index: ~600-800 MB total
- Add 200-400 MB buffer for OS/operations
- **Recommended RAM**: 2 GB minimum

**Authority Level:** Mathematical formula from hnswlib + empirical validation

**Sources:**
- https://stackoverflow.com/questions/77401874/how-to-calculate-amount-of-ram-required-for-serving-x-n-dimensional-vectors-with
- https://lantern.dev/blog/calculator (HNSW memory calculator)
- https://weaviate.io/developers/weaviate/concepts/resources

### 2.3 Build vs Query Time Tradeoffs

**Build Time Factors:**

| Factor | Impact | Tuning Knob |
|--------|--------|-------------|
| ef_construction | Direct: 2× ef_construction ≈ 2× build time | Start 200, max 400 for prod |
| M | Moderate: Higher M = more distance computations | Keep M ≤ 32 for 100K docs |
| Corpus size | Linear-to-log: HNSW scales well | Use parallel indexing |
| Dimensionality | High: More dimensions = slower distance calcs | Choose lowest viable (1024) |

**Query Time Factors:**

| Factor | Impact | Tuning Knob |
|--------|--------|-------------|
| ef_search | Direct: Higher ef_search = more nodes explored | Tune per-query dynamically |
| M | Moderate: Higher M = more edges to traverse | Set at build time |
| Corpus size | Logarithmic: HNSW query time grows slowly | Excellent scaling |

**Tradeoff Strategy:**

1. **Invest in build quality**: Use higher ef_construction (400) since indexing is offline
2. **Keep M moderate**: M=16-32 provides good balance
3. **Tune ef_search dynamically**: Adjust per-query based on recall requirements
   - Fast/approximate queries: ef_search=50
   - High-precision queries: ef_search=200

**For RexLit (Offline-First, Batch Processing):**
- Build time is less critical (one-time operation, can run overnight)
- Favor higher build quality: ef_construction=400, M=32
- Query time is critical (user-facing search)
- Tune ef_search to meet <50ms latency target

**Authority Level:** Industry consensus from vector database vendors

### 2.4 Index Persistence and Versioning

**Key Challenges:**

1. **Binary Format Compatibility**: HNSW indices are binary structures that may not be compatible across library versions
2. **Determinism**: Graph construction may vary slightly between builds even with same data
3. **Metadata Coupling**: Need to version-sync vectors with document metadata

**Best Practices:**

**Versioning Scheme:**
```
index-v{SCHEMA_VERSION}-d{DIM}-m{M}-ef{EF_CONSTRUCTION}.hnsw
metadata-v{SCHEMA_VERSION}.jsonl
```

Example: `index-v1-d1024-m16-ef200.hnsw`

**Persistence Strategy:**

1. **Store Index Parameters**: Save M, ef_construction, dimensionality in metadata
2. **Schema Versioning**: Version the index format (similar to ADR 0004 for JSONL)
3. **Rebuild Capability**: Always maintain ability to rebuild from source documents
4. **Checksums**: SHA-256 hash of index file for integrity verification

**Legal E-Discovery Considerations:**

- **Deterministic Builds**: Same input documents + same parameters = same index (critical for reproducibility)
- **Audit Trail**: Log index creation parameters, timestamp, document count
- **Version Locking**: Pin embedding model version and HNSW library version
- **Backward Compatibility**: Maintain ability to load older indices for historical productions

**Implementation Example:**

```python
import hashlib
import json

def save_index_metadata(index_path: str, metadata: dict):
    """Save index metadata for versioning and audit trail."""
    meta = {
        "version": 1,
        "index_path": index_path,
        "dimensions": metadata["dimensions"],
        "M": metadata["M"],
        "ef_construction": metadata["ef_construction"],
        "document_count": metadata["doc_count"],
        "embedding_model": metadata["model"],
        "created_at": metadata["timestamp"],
        "index_checksum": hash_file(index_path),
        "library_version": get_hnsw_version(),
    }

    with open(f"{index_path}.meta.json", "w") as f:
        json.dump(meta, f, indent=2)

def hash_file(path: str) -> str:
    """Compute SHA-256 hash of index file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

**Authority Level:** Industry best practice + legal e-discovery standards

---

## 3. Hybrid Search Fusion Techniques

### 3.1 Reciprocal Rank Fusion (RRF) Implementation

**Core Concept:**

RRF combines multiple ranked result lists by assigning reciprocal rank scores to each document and summing them to create a unified ranking.

**Formula:**

```
RRF_score(d) = Σ ( 1 / (k + rank_i(d)) )

Where:
  d = document
  k = constant (typically 60)
  rank_i(d) = position of document d in result list i
  Σ = sum across all result lists
```

**Why k=60?**

The constant k=60 is an empirical default that:
- Prevents division by zero
- Reduces the impact of rank differences at lower positions
- Works well across diverse datasets (validated in research)

**Implementation Example:**

```python
def reciprocal_rank_fusion(
    result_lists: list[list[tuple[str, float]]],
    k: int = 60
) -> list[tuple[str, float]]:
    """
    Fuse multiple ranked result lists using RRF.

    Args:
        result_lists: List of ranked results, each result is (doc_id, score)
        k: RRF constant (default 60)

    Returns:
        Fused results sorted by RRF score
    """
    rrf_scores = {}

    for result_list in result_lists:
        for rank, (doc_id, _) in enumerate(result_list, start=1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            rrf_scores[doc_id] += 1.0 / (k + rank)

    # Sort by RRF score descending
    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return fused
```

**Benefits:**

1. **No Score Normalization Required**: RRF works on ranks, not raw scores (avoids BM25 vs cosine scale issues)
2. **Rank Consistency**: Documents appearing in top positions across multiple methods are prioritized
3. **No Tuning Required**: k=60 works well universally (unlike weighted fusion which needs tuning)
4. **Robust**: Handles missing documents gracefully (document only in one list gets lower score)

**Authority Level:** Widely adopted (Azure AI Search, OpenSearch 2.19+, Elasticsearch, Weaviate)

**Sources:**
- https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking (Microsoft Azure)
- https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/ (OpenSearch official)
- https://weaviate.io/blog/hybrid-search-explained

### 3.2 BM25 + Dense Vector Fusion Strategies

**Three Primary Approaches:**

#### **Option 1: Reciprocal Rank Fusion (Recommended)**

```python
# Retrieve from both indices
bm25_results = tantivy_search(query, top_k=100)
vector_results = hnsw_search(query_embedding, top_k=100)

# Fuse with RRF
fused_results = reciprocal_rank_fusion([bm25_results, vector_results], k=60)
```

**Pros**: No normalization needed, no hyperparameter tuning
**Cons**: Loses raw score information

#### **Option 2: Weighted Score Fusion**

```python
def weighted_fusion(bm25_results, vector_results, alpha=0.5):
    """
    Combine scores with weights.

    Args:
        alpha: Weight for BM25 (1-alpha for vector)
    """
    combined = {}

    # Normalize scores to [0, 1]
    bm25_norm = min_max_normalize(bm25_results)
    vector_norm = min_max_normalize(vector_results)

    # Combine
    for doc_id, score in bm25_norm.items():
        combined[doc_id] = alpha * score

    for doc_id, score in vector_norm.items():
        if doc_id in combined:
            combined[doc_id] += (1 - alpha) * score
        else:
            combined[doc_id] = (1 - alpha) * score

    return sorted(combined.items(), key=lambda x: x[1], reverse=True)
```

**Pros**: Preserves score magnitudes, allows dynamic weighting
**Cons**: Requires score normalization, alpha parameter needs tuning (0.3-0.7 typical range)

#### **Option 3: Cascade Retrieval**

```python
# Stage 1: Fast BM25 retrieval (broad recall)
bm25_candidates = tantivy_search(query, top_k=1000)

# Stage 2: Rerank top candidates with dense vectors
reranked = []
for doc_id, bm25_score in bm25_candidates[:100]:
    vector_score = compute_similarity(query_embedding, doc_embeddings[doc_id])
    combined_score = bm25_score * vector_score  # or linear combination
    reranked.append((doc_id, combined_score))

return sorted(reranked, key=lambda x: x[1], reverse=True)[:20]
```

**Pros**: Efficient, leverages speed of BM25
**Cons**: May miss documents not in BM25 top-K

**When to Use Each:**

| Approach | Best For | RexLit Use Case |
|----------|----------|-----------------|
| RRF | General purpose, no tuning | **Recommended default** |
| Weighted | Need to favor one method | Keyword-heavy queries (alpha=0.7 for BM25) |
| Cascade | Large corpus (1M+ docs) | Future scaling |

**Authority Level:** Industry standard approaches

**Sources:**
- https://medium.com/thinking-sand/hybrid-search-with-bm25-and-rank-fusion-for-accurate-results-456a70305dc5
- https://www.elastic.co/what-is/hybrid-search

### 3.3 Score Normalization Approaches

**Problem:**

BM25 scores are unbounded (0 to ∞), while cosine similarity is bounded (-1 to 1, typically 0 to 1 for embeddings). Direct combination is meaningless.

**Normalization Techniques:**

#### **1. Min-Max Normalization (MM)**

```python
def min_max_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Normalize scores to [0, 1] based on observed min/max."""
    values = list(scores.values())
    min_score = min(values)
    max_score = max(values)

    if max_score == min_score:
        return {k: 1.0 for k in scores}

    normalized = {}
    for doc_id, score in scores.items():
        normalized[doc_id] = (score - min_score) / (max_score - min_score)

    return normalized
```

**Pros**: Simple, bounded [0, 1]
**Cons**: Sensitive to outliers, per-query scaling

#### **2. Theoretical Min-Max (TMM) - Recommended**

```python
def theoretical_min_max_normalize(scores: dict[str, float],
                                  score_type: str) -> dict[str, float]:
    """Normalize using theoretical bounds."""
    if score_type == "bm25":
        # BM25 theoretical min is 0
        min_score = 0.0
        max_score = max(scores.values())
    elif score_type == "cosine":
        # Cosine theoretical range is -1 to 1
        min_score = -1.0
        max_score = 1.0
    else:
        raise ValueError(f"Unknown score type: {score_type}")

    normalized = {}
    for doc_id, score in scores.items():
        normalized[doc_id] = (score - min_score) / (max_score - min_score)

    return normalized
```

**Pros**: More robust across queries, preserves relative magnitudes
**Cons**: Requires knowledge of theoretical bounds

**Research Finding:** TMM is more robust than MM and produces sharper, more distinguishable peak scores.

#### **3. BM25-Max Scaling**

```python
def bm25_max_scale(scores: dict[str, float]) -> dict[str, float]:
    """Scale BM25 using max score (first result)."""
    max_score = max(scores.values())
    return {k: v / max_score for k, v in scores.items()}
```

**Pros**: Fast, preserves relative spacing
**Cons**: Only for BM25

**Recommendation for RexLit:**

Use **RRF (no normalization)** as default. If weighted fusion is needed, use **TMM normalization**.

**Authority Level:** Research-backed (OpenSearch, community analysis)

**Sources:**
- https://forum.opensearch.org/t/normalisation-in-hybrid-search/12996
- https://medium.com/@autorag/weights-in-hybrid-retrieval-are-you-just-using-any-values-990fb8af6a27

### 3.4 Fallback Strategies When Dense Vectors Unavailable

**Scenarios:**

1. **Online Mode Disabled**: User runs RexLit with `--offline`, no embedding API access
2. **API Failure**: Rate limit, network error, or API key expiration
3. **Partial Index**: Only some documents have embeddings (incremental indexing)
4. **Legacy Index**: Older index created before dense vector support

**Fallback Strategies:**

#### **Strategy 1: Graceful Degradation to BM25**

```python
def hybrid_search(query: str, online_mode: bool) -> list[SearchResult]:
    """Search with graceful fallback."""
    bm25_results = tantivy_search(query, top_k=20)

    if not online_mode or not embeddings_available():
        log.info("Dense vectors unavailable, using BM25 only")
        return bm25_results

    try:
        vector_results = dense_search(query, top_k=20)
        return reciprocal_rank_fusion([bm25_results, vector_results])
    except EmbeddingAPIError as e:
        log.warning(f"Embedding API failed: {e}, falling back to BM25")
        return bm25_results
```

**Pros**: Always returns results, no user-facing errors
**Cons**: Inconsistent quality (sometimes hybrid, sometimes BM25-only)

#### **Strategy 2: Explicit Mode Indication**

```python
@dataclass
class SearchResponse:
    results: list[SearchResult]
    mode: Literal["hybrid", "bm25_only", "vector_only"]
    reason: Optional[str] = None

def search_with_mode(query: str) -> SearchResponse:
    """Return results with explicit mode indication."""
    bm25_results = tantivy_search(query)

    if not embeddings_available():
        return SearchResponse(
            results=bm25_results,
            mode="bm25_only",
            reason="Dense vectors not available (run with --online to enable)"
        )

    # ... hybrid search ...
    return SearchResponse(results=fused, mode="hybrid")
```

**Pros**: Transparent to user, clear expectations
**Cons**: More complex API

#### **Strategy 3: Pre-computed Embeddings Cache**

```python
# At index build time (offline or online)
if online_mode and embedding_api_available():
    # Generate and cache embeddings for all documents
    embeddings = batch_generate_embeddings(documents)
    save_embeddings_cache(embeddings)
    build_hnsw_index(embeddings)

# At query time (always offline)
def search(query: str) -> list[SearchResult]:
    # Always use cached embeddings for documents
    # Generate query embedding on-the-fly if online
    if online_mode:
        query_emb = generate_embedding(query)
        return hybrid_search(query, query_emb)
    else:
        return bm25_search(query)
```

**Pros**: Best performance, predictable behavior
**Cons**: Requires upfront embedding generation

**Recommendation for RexLit:**

Implement **Strategy 3 (pre-computed cache)** with **Strategy 2 (explicit mode)**:

1. At index build time with `--online`: Pre-compute all document embeddings, store in `index/embeddings.bin`
2. At query time: If embeddings exist and `--online`, use hybrid search; otherwise, use BM25 with clear warning
3. CLI flag: `rexlit index search --mode [auto|hybrid|bm25]` for explicit control

**Authority Level:** Industry best practice for offline-first systems

---

## 4. Offline-First Embedding Architecture

### 4.1 Patterns for Caching Embeddings

**Key Principle: Embeddings are Expensive, Cache Aggressively**

**Caching Strategy for RexLit:**

#### **Document Embeddings (Long-Lived Cache)**

```python
# Storage format: Binary for efficiency
import struct
import numpy as np

class EmbeddingCache:
    """Persistent cache for document embeddings."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.index_path = cache_dir / "embeddings.bin"
        self.metadata_path = cache_dir / "embeddings.jsonl"

    def save(self, doc_id: str, embedding: np.ndarray):
        """Append embedding to cache."""
        with open(self.index_path, "ab") as f:
            # Write: doc_id_len (4 bytes) | doc_id (utf-8) | embedding (4*dim bytes)
            doc_id_bytes = doc_id.encode("utf-8")
            f.write(struct.pack("I", len(doc_id_bytes)))
            f.write(doc_id_bytes)
            f.write(embedding.astype(np.float32).tobytes())

        # Metadata for audit trail
        self.log_metadata(doc_id, embedding)

    def load_all(self) -> dict[str, np.ndarray]:
        """Load all embeddings into memory."""
        embeddings = {}
        with open(self.index_path, "rb") as f:
            while True:
                # Read doc_id length
                length_bytes = f.read(4)
                if not length_bytes:
                    break

                doc_id_len = struct.unpack("I", length_bytes)[0]
                doc_id = f.read(doc_id_len).decode("utf-8")

                # Read embedding
                emb_bytes = f.read(4 * EMBEDDING_DIM)
                embedding = np.frombuffer(emb_bytes, dtype=np.float32)
                embeddings[doc_id] = embedding

        return embeddings
```

**Storage Efficiency:**
- 100K documents × 1024 dimensions × 4 bytes = 409.6 MB (raw)
- Add ~10 MB for doc_id strings and metadata
- Total: ~420 MB (fits easily in memory, acceptable on disk)

#### **Query Embeddings (Short-Lived Cache)**

```python
from functools import lru_cache
import hashlib

def hash_query(query: str) -> str:
    """Create cache key from query."""
    return hashlib.sha256(query.encode()).hexdigest()[:16]

@lru_cache(maxsize=1000)
def get_query_embedding_cached(query: str, model: str) -> np.ndarray:
    """
    Cache query embeddings in memory (LRU).

    Rationale: Queries are often repeated in legal e-discovery
    (e.g., standard privilege searches).
    """
    # Check persistent cache first
    cache_key = hash_query(query)
    if cached := load_from_persistent_cache(cache_key):
        return cached

    # Generate and cache
    embedding = generate_embedding(query, model)
    save_to_persistent_cache(cache_key, embedding)
    return embedding
```

**Cache Invalidation:**

- Document embeddings: Invalidate when document content changes or embedding model changes
- Query embeddings: TTL of 7 days (legal searches are often repeated within productions)

**Authority Level:** Industry best practice for production systems

**Sources:**
- https://python.langchain.com/docs/how_to/caching_embeddings/
- https://arxiv.org/html/2411.05276v1 (Semantic caching paper)

### 4.2 Handling Online/Offline Mode Transitions

**State Transitions:**

```
Initial State → Build Index (Online) → Save Embeddings → Query (Offline)
     ↓                                                           ↑
     └─────────── Build Index (Offline, BM25 only) ─────────────┘
```

**Implementation Pattern:**

```python
class IndexBuilder:
    """Builds search index with online/offline awareness."""

    def __init__(self, online_mode: bool, embedding_api: Optional[EmbeddingAPI]):
        self.online_mode = online_mode
        self.embedding_api = embedding_api

    def build(self, documents: Iterator[Document], index_dir: Path):
        """Build index with hybrid or BM25-only support."""
        # Always build BM25 index (offline-capable)
        bm25_index = self.build_bm25_index(documents)

        if self.online_mode and self.embedding_api:
            # Build dense vector index (requires online)
            try:
                embeddings = self.generate_embeddings_batch(documents)
                hnsw_index = self.build_hnsw_index(embeddings)

                # Save for offline use
                self.save_embeddings(embeddings, index_dir / "embeddings")
                self.save_hnsw_index(hnsw_index, index_dir / "hnsw.bin")

                self.write_capability_flag(index_dir, hybrid=True)
            except EmbeddingAPIError as e:
                self.log_warning(f"Failed to generate embeddings: {e}")
                self.write_capability_flag(index_dir, hybrid=False)
        else:
            self.write_capability_flag(index_dir, hybrid=False)

    def write_capability_flag(self, index_dir: Path, hybrid: bool):
        """Write index capabilities for query-time behavior."""
        capabilities = {
            "version": 1,
            "supports_hybrid": hybrid,
            "supports_bm25": True,
            "embedding_model": self.embedding_api.model if hybrid else None,
            "embedding_dim": EMBEDDING_DIM if hybrid else None,
        }

        with open(index_dir / "capabilities.json", "w") as f:
            json.dump(capabilities, f, indent=2)
```

**Query-Time Behavior:**

```python
class SearchEngine:
    """Query engine with online/offline support."""

    def __init__(self, index_dir: Path, online_mode: bool):
        self.index_dir = index_dir
        self.online_mode = online_mode
        self.capabilities = self.load_capabilities()

    def search(self, query: str, mode: str = "auto") -> SearchResponse:
        """Search with automatic mode selection."""
        # Determine available modes
        can_bm25 = self.capabilities["supports_bm25"]
        can_hybrid = (
            self.capabilities["supports_hybrid"]
            and self.online_mode  # Need online for query embedding
        )

        # Mode selection logic
        if mode == "auto":
            selected_mode = "hybrid" if can_hybrid else "bm25"
        elif mode == "hybrid" and not can_hybrid:
            raise ValueError(
                "Hybrid search unavailable. Reasons:\n"
                f"  - Index supports hybrid: {self.capabilities['supports_hybrid']}\n"
                f"  - Online mode enabled: {self.online_mode}\n"
                "Suggestion: Run 'rexlit index build --online' to enable hybrid search."
            )
        else:
            selected_mode = mode

        # Execute search
        if selected_mode == "hybrid":
            return self.hybrid_search(query)
        else:
            return self.bm25_search(query)
```

**CLI Integration:**

```bash
# Build index with hybrid support (requires --online)
rexlit index build ./docs --online --index-dir out/index

# Query with hybrid (requires index built with --online)
rexlit index search out/index --query "privilege" --online

# Query offline (falls back to BM25)
rexlit index search out/index --query "privilege"
# Output: [INFO] Dense vectors available but --online not set, using BM25 only

# Explicit mode control
rexlit index search out/index --query "privilege" --mode bm25
```

**Authority Level:** Aligned with RexLit ADR 0001 (Offline-First Gate)

### 4.3 Self-Hosted Embedding Server Alternatives

**Why Self-Host?**

1. **Offline Operation**: Eliminate dependency on external APIs
2. **Data Privacy**: Keep sensitive legal documents on-premises
3. **Cost Control**: No per-token pricing for high-volume processing
4. **Determinism**: Full control over model versions and parameters

**Option 1: Ollama (Recommended for RexLit)**

**Overview**: Local LLM runner that supports embedding models

**Setup:**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model
ollama pull mxbai-embed-large  # 335M params, 1024 dimensions
# or
ollama pull nomic-embed-text   # 137M params, 768 dimensions

# Run server
ollama serve  # Listens on http://localhost:11434
```

**Integration:**

```python
import requests

class OllamaEmbeddingAPI:
    """Local embedding API using Ollama."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "mxbai-embed-large"):
        self.base_url = base_url
        self.model = model

    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text}
        )
        response.raise_for_status()
        return np.array(response.json()["embedding"])

    def generate_batch(self, texts: list[str],
                      batch_size: int = 32) -> list[np.ndarray]:
        """Generate embeddings in batches."""
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            # Ollama processes one at a time, but we can parallelize
            batch_embeddings = [self.generate_embedding(t) for t in batch]
            embeddings.extend(batch_embeddings)
        return embeddings
```

**Pros:**
- Simple setup (single binary)
- Docker support for deployment
- Multiple embedding models available
- GPU acceleration (CUDA, Metal)
- No external dependencies

**Cons:**
- Sequential processing (slower than cloud APIs)
- Requires local GPU for reasonable speed (CPU is slow)
- Quality may be lower than state-of-the-art commercial models

**Performance:**
- CPU (M1 Mac): ~50-100 embeddings/sec
- GPU (NVIDIA 3090): ~500-1000 embeddings/sec
- 100K documents at 100 emb/sec = ~17 minutes (acceptable for offline indexing)

**Option 2: Sentence Transformers (Python Library)**

**Setup:**

```bash
pip install sentence-transformers torch
```

**Implementation:**

```python
from sentence_transformers import SentenceTransformer

class SentenceTransformerAPI:
    """Local embeddings using Sentence Transformers."""

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        # Download and cache model on first use
        self.model = SentenceTransformer(model_name)

        # Move to GPU if available
        if torch.cuda.is_available():
            self.model = self.model.cuda()

    def generate_batch(self, texts: list[str],
                      batch_size: int = 32) -> np.ndarray:
        """Generate embeddings in batches (efficient)."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True  # L2 normalization for cosine similarity
        )
        return embeddings
```

**Recommended Models:**

| Model | Dimensions | Quality | Speed | Use Case |
|-------|-----------|---------|-------|----------|
| all-MiniLM-L6-v2 | 384 | Good | Fast | Development, testing |
| BAAI/bge-base-en-v1.5 | 768 | Excellent | Moderate | **Recommended for RexLit** |
| BAAI/bge-large-en-v1.5 | 1024 | Best | Slow | Maximum quality |
| nomic-ai/nomic-embed-text-v1 | 768 | Excellent | Moderate | Open license |

**Pros:**
- Native Python integration
- Efficient batch processing
- Wide model selection
- GPU acceleration built-in

**Cons:**
- Requires Python environment
- Model downloads can be large (1-2 GB)
- Memory footprint (model + documents in RAM)

**Option 3: Self-Hosted Inference Server**

For production deployment:

```yaml
# docker-compose.yml
services:
  embedding-server:
    image: ghcr.io/huggingface/text-embeddings-inference:latest
    ports:
      - "8080:80"
    volumes:
      - ./models:/data
    environment:
      - MODEL_ID=BAAI/bge-large-en-v1.5
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**Recommendation for RexLit:**

1. **Development/Testing**: Sentence Transformers with `all-MiniLM-L6-v2`
2. **Production (offline, batch)**: Ollama with `mxbai-embed-large` (1024d)
3. **Production (online, API)**: Fallback to external API (OpenAI, Cohere) with Ollama as backup

**Authority Level:** Community best practices + production deployments

**Sources:**
- https://ollama.com/ (Official Ollama documentation)
- https://www.sbert.net/ (Sentence Transformers official)
- https://medium.com/@mbrazel/open-source-self-hosted-rag-llm-server-with-chromadb-docker-ollama-7e6c6913da7a

### 4.4 Error Handling for Network Failures

**Failure Modes:**

1. **Connection Timeout**: Network unreachable, API endpoint down
2. **Rate Limit**: Exceeded API quota (429 Too Many Requests)
3. **Authentication Failure**: Invalid or expired API key (401/403)
4. **Transient Errors**: 5xx server errors, DNS failures
5. **Partial Failures**: Batch request with some failures

**Error Handling Strategy:**

```python
import time
import logging
from typing import Optional
from dataclasses import dataclass

@dataclass
class EmbeddingResult:
    """Result of embedding generation attempt."""
    success: bool
    embedding: Optional[np.ndarray]
    error: Optional[str]
    attempts: int
    latency_ms: float

class ResilientEmbeddingAPI:
    """Embedding API with retry logic and fallbacks."""

    def __init__(self,
                 primary_api: EmbeddingAPI,
                 fallback_api: Optional[EmbeddingAPI] = None,
                 max_retries: int = 3,
                 timeout_sec: int = 30):
        self.primary_api = primary_api
        self.fallback_api = fallback_api
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec
        self.logger = logging.getLogger(__name__)

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding with retry and fallback logic."""
        start_time = time.time()

        # Try primary API with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            try:
                embedding = self.primary_api.generate(
                    text,
                    timeout=self.timeout_sec
                )

                latency = (time.time() - start_time) * 1000
                self.logger.debug(f"Embedding generated in {latency:.1f}ms")

                return EmbeddingResult(
                    success=True,
                    embedding=embedding,
                    error=None,
                    attempts=attempt,
                    latency_ms=latency
                )

            except RateLimitError as e:
                # Wait before retry (exponential backoff)
                wait_time = min(2 ** attempt, 60)  # Max 60 seconds
                self.logger.warning(
                    f"Rate limit hit (attempt {attempt}/{self.max_retries}), "
                    f"waiting {wait_time}s"
                )
                time.sleep(wait_time)

            except AuthenticationError as e:
                # Don't retry auth errors
                self.logger.error(f"Authentication failed: {e}")
                break

            except (ConnectionError, TimeoutError) as e:
                # Retry transient errors
                self.logger.warning(
                    f"Network error (attempt {attempt}/{self.max_retries}): {e}"
                )
                time.sleep(2 ** attempt)

            except Exception as e:
                # Unexpected error
                self.logger.error(f"Unexpected error: {e}")
                break

        # Primary API failed, try fallback
        if self.fallback_api:
            self.logger.info("Attempting fallback API")
            try:
                embedding = self.fallback_api.generate(text)
                latency = (time.time() - start_time) * 1000

                return EmbeddingResult(
                    success=True,
                    embedding=embedding,
                    error="primary_failed_used_fallback",
                    attempts=self.max_retries + 1,
                    latency_ms=latency
                )
            except Exception as e:
                self.logger.error(f"Fallback API also failed: {e}")

        # All attempts failed
        latency = (time.time() - start_time) * 1000
        return EmbeddingResult(
            success=False,
            embedding=None,
            error="all_attempts_failed",
            attempts=self.max_retries,
            latency_ms=latency
        )

    def generate_batch_with_partial_failure_handling(
        self,
        texts: list[str],
        batch_size: int = 32
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings in batches, handling partial failures.

        If a batch fails, retry individual items.
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]

            try:
                # Try batch generation (faster)
                embeddings = self.primary_api.generate_batch(batch)

                for emb in embeddings:
                    results.append(EmbeddingResult(
                        success=True,
                        embedding=emb,
                        error=None,
                        attempts=1,
                        latency_ms=0  # Not tracked for batch
                    ))

            except Exception as e:
                # Batch failed, retry items individually
                self.logger.warning(
                    f"Batch generation failed ({e}), "
                    f"retrying {len(batch)} items individually"
                )

                for text in batch:
                    result = self.generate_embedding(text)
                    results.append(result)

        return results
```

**Audit Logging for Failures:**

```python
def log_embedding_failure(result: EmbeddingResult, doc_id: str,
                         audit_ledger: AuditLedger):
    """Log embedding failure to audit trail."""
    if not result.success:
        audit_ledger.write({
            "event": "embedding_generation_failed",
            "doc_id": doc_id,
            "error": result.error,
            "attempts": result.attempts,
            "latency_ms": result.latency_ms,
            "timestamp": datetime.utcnow().isoformat(),
        })
```

**CLI Behavior:**

```bash
# Graceful degradation
$ rexlit index build ./docs --online --index-dir out/index
[INFO] Generating embeddings for 100,000 documents...
[WARN] Rate limit hit for document 5234, retrying in 2s...
[WARN] Rate limit hit for document 5234, retrying in 4s...
[INFO] Successfully generated embedding for document 5234 (attempt 3/3)
...
[ERROR] Failed to generate embedding for document 8721 after 3 attempts
[INFO] Skipping dense vector for document 8721, will use BM25 only
[INFO] Generated 99,999/100,000 embeddings (99.99% success rate)
[INFO] Index built: 99,999 docs with hybrid search, 1 with BM25 only

# Query behavior with partial embeddings
$ rexlit index search out/index --query "privilege" --online
[INFO] Using hybrid search for 99,999/100,000 documents
[INFO] Document 8721 excluded from dense retrieval (embedding unavailable)
```

**Authority Level:** Production best practices from distributed systems

**Sources:**
- https://platform.openai.com/docs/guides/rate-limits (OpenAI rate limit handling)
- https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/

---

## 5. Performance and Scalability

### 5.1 Batch Processing Strategies for Embedding Generation

**Key Optimization: Batch Size vs Throughput**

**Optimal Batch Sizes:**

| Hardware | Batch Size | Throughput | Rationale |
|----------|-----------|------------|-----------|
| CPU (8 cores) | 16-32 | 50-100 emb/s | Avoid memory thrashing |
| GPU (8GB VRAM) | 64-128 | 500-1000 emb/s | Maximize GPU utilization |
| GPU (24GB VRAM) | 128-256 | 1000-2000 emb/s | Larger batches reduce overhead |
| API (OpenAI) | 100-2048 | Variable | Respect API batch limits |

**Strategy 1: Fixed Batch Size**

```python
def generate_embeddings_fixed_batch(
    documents: list[Document],
    api: EmbeddingAPI,
    batch_size: int = 32
) -> dict[str, np.ndarray]:
    """Generate embeddings with fixed batch size."""
    embeddings = {}

    texts = [doc.text for doc in documents]
    doc_ids = [doc.id for doc in documents]

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        batch_ids = doc_ids[i:i+batch_size]

        # Generate batch
        batch_embeddings = api.generate_batch(batch_texts)

        # Store results
        for doc_id, emb in zip(batch_ids, batch_embeddings):
            embeddings[doc_id] = emb

    return embeddings
```

**Strategy 2: Dynamic Batch Size (Length-Based)**

```python
def generate_embeddings_dynamic_batch(
    documents: list[Document],
    api: EmbeddingAPI,
    max_tokens_per_batch: int = 8000
) -> dict[str, np.ndarray]:
    """
    Generate embeddings with dynamic batching based on text length.

    Rationale: Short documents can be batched more aggressively,
    while long documents need smaller batches to avoid memory issues.
    """
    embeddings = {}

    # Sort by length to minimize padding waste
    sorted_docs = sorted(documents, key=lambda d: len(d.text))

    batch_texts = []
    batch_ids = []
    batch_token_count = 0

    for doc in sorted_docs:
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        doc_tokens = len(doc.text) // 4

        if batch_token_count + doc_tokens > max_tokens_per_batch and batch_texts:
            # Flush current batch
            batch_embeddings = api.generate_batch(batch_texts)
            for doc_id, emb in zip(batch_ids, batch_embeddings):
                embeddings[doc_id] = emb

            # Reset batch
            batch_texts = []
            batch_ids = []
            batch_token_count = 0

        batch_texts.append(doc.text)
        batch_ids.append(doc.id)
        batch_token_count += doc_tokens

    # Flush remaining batch
    if batch_texts:
        batch_embeddings = api.generate_batch(batch_texts)
        for doc_id, emb in zip(batch_ids, batch_embeddings):
            embeddings[doc_id] = emb

    return embeddings
```

**Benefits of Dynamic Batching:**
- Reduces padding overhead (shorter documents batched together)
- Avoids memory spikes from large document batches
- Improves GPU utilization

**Strategy 3: Parallel Batching**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def generate_embeddings_parallel(
    documents: list[Document],
    api: EmbeddingAPI,
    batch_size: int = 32,
    num_workers: int = 4
) -> dict[str, np.ndarray]:
    """
    Generate embeddings with parallel batch processing.

    Use ThreadPoolExecutor for I/O-bound API calls.
    """
    def process_batch(batch: list[Document]) -> dict[str, np.ndarray]:
        texts = [doc.text for doc in batch]
        doc_ids = [doc.id for doc in batch]
        embeddings = api.generate_batch(texts)
        return dict(zip(doc_ids, embeddings))

    # Split into batches
    batches = [
        documents[i:i+batch_size]
        for i in range(0, len(documents), batch_size)
    ]

    # Process in parallel
    all_embeddings = {}

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(process_batch, batch): batch
            for batch in batches
        }

        for future in as_completed(futures):
            batch_embeddings = future.result()
            all_embeddings.update(batch_embeddings)

    return all_embeddings
```

**When to Use Parallel Batching:**
- API-based generation (I/O-bound)
- Multiple API keys available (separate rate limits)
- Local server with multiple workers (e.g., Ollama with multiple GPUs)

**Cost Savings: OpenAI Batch API**

```python
# Regular API: $0.13 per 1M tokens
# Batch API: $0.065 per 1M tokens (50% discount)

def use_openai_batch_api(documents: list[Document]) -> str:
    """
    Submit batch job to OpenAI (async, 24-hour turnaround).

    Returns: batch_id for later retrieval
    """
    import openai

    # Prepare batch file (JSONL)
    batch_requests = []
    for i, doc in enumerate(documents):
        batch_requests.append({
            "custom_id": doc.id,
            "method": "POST",
            "url": "/v1/embeddings",
            "body": {
                "model": "text-embedding-3-large",
                "input": doc.text,
                "dimensions": 1024
            }
        })

    # Upload batch file
    batch_file = openai.File.create(
        file=jsonl_to_bytes(batch_requests),
        purpose="batch"
    )

    # Create batch job
    batch = openai.Batch.create(
        input_file_id=batch_file.id,
        endpoint="/v1/embeddings",
        completion_window="24h"
    )

    return batch.id

# Later: retrieve results
def retrieve_batch_results(batch_id: str) -> dict[str, np.ndarray]:
    batch = openai.Batch.retrieve(batch_id)

    if batch.status == "completed":
        results_file = openai.File.content(batch.output_file_id)
        # Parse JSONL results...
        return parse_embeddings(results_file)
    else:
        raise ValueError(f"Batch not ready: {batch.status}")
```

**Recommendation for RexLit:**

1. **Offline, local embeddings**: Use Strategy 2 (dynamic batch size) with sorted documents
2. **Online, API-based**: Use Strategy 3 (parallel batching) with 4 workers
3. **Large-scale (1M+ docs)**: Use OpenAI Batch API for 50% cost savings

**Authority Level:** Industry best practices + API vendor recommendations

**Sources:**
- https://platform.openai.com/docs/guides/batch (OpenAI Batch API)
- https://medium.com/@olujare.dada/how-to-efficiently-generate-text-embeddings-using-openais-batch-api-c9cd5f8a1961
- https://zilliz.com/ai-faq/what-is-the-impact-of-batch-size-on-embedding-generation-throughput

### 5.2 Parallel Indexing with Embeddings

**Challenge: Embeddings + HNSW Construction**

RexLit already uses parallel indexing for BM25 (ProcessPoolExecutor). Adding embeddings introduces complexity:

1. **Embedding generation**: Can be parallelized (API calls, multi-GPU)
2. **HNSW construction**: Single-threaded in most libraries (hnswlib, faiss)
3. **Combined workflow**: Need careful orchestration

**Architecture: Pipeline Parallelism**

```
Stage 1 (Parallel): Text Extraction + Chunking
   ↓
Stage 2 (Parallel): Embedding Generation (batched)
   ↓
Stage 3 (Sequential): HNSW Index Construction
   ↓
Stage 4 (Parallel): Tantivy BM25 Indexing
```

**Implementation:**

```python
from multiprocessing import Pool, Queue
from concurrent.futures import ProcessPoolExecutor

class HybridIndexBuilder:
    """Parallel index builder for hybrid search."""

    def __init__(self, workers: int, embedding_api: EmbeddingAPI):
        self.workers = workers
        self.embedding_api = embedding_api

    def build_index(self, documents: Iterator[Document],
                   index_dir: Path):
        """Build hybrid index with parallel processing."""

        # Stage 1: Parallel text extraction (already implemented in RexLit)
        extracted_docs = self.parallel_extract(documents)

        # Stage 2: Parallel embedding generation
        embeddings = self.parallel_generate_embeddings(extracted_docs)

        # Stage 3: Sequential HNSW construction
        hnsw_index = self.build_hnsw_index(embeddings)

        # Stage 4: Parallel BM25 indexing (existing RexLit code)
        bm25_index = self.parallel_build_bm25(extracted_docs)

        # Save indices
        self.save_indices(index_dir, hnsw_index, bm25_index)

    def parallel_generate_embeddings(
        self,
        documents: list[Document]
    ) -> dict[str, np.ndarray]:
        """
        Generate embeddings in parallel using process pool.

        Each worker handles a batch of documents.
        """
        # Split documents into chunks for workers
        chunk_size = len(documents) // self.workers
        doc_chunks = [
            documents[i:i+chunk_size]
            for i in range(0, len(documents), chunk_size)
        ]

        # Process chunks in parallel
        with ProcessPoolExecutor(max_workers=self.workers) as executor:
            # Each worker runs embedding generation for its chunk
            futures = [
                executor.submit(
                    self._generate_embeddings_worker,
                    chunk
                )
                for chunk in doc_chunks
            ]

            # Collect results
            all_embeddings = {}
            for future in futures:
                chunk_embeddings = future.result()
                all_embeddings.update(chunk_embeddings)

        return all_embeddings

    def _generate_embeddings_worker(
        self,
        documents: list[Document]
    ) -> dict[str, np.ndarray]:
        """Worker function for embedding generation (runs in subprocess)."""
        # Each worker needs its own API client
        api = self.embedding_api.clone()

        embeddings = {}
        batch_size = 32

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            texts = [doc.text for doc in batch]
            doc_ids = [doc.id for doc in batch]

            # Generate batch (this makes API calls or GPU inference)
            batch_embeddings = api.generate_batch(texts)

            for doc_id, emb in zip(doc_ids, batch_embeddings):
                embeddings[doc_id] = emb

        return embeddings

    def build_hnsw_index(
        self,
        embeddings: dict[str, np.ndarray]
    ) -> hnswlib.Index:
        """
        Build HNSW index (sequential, but optimized).

        Note: HNSW construction is single-threaded, but this is
        acceptable because it's fast relative to embedding generation.
        """
        import hnswlib

        # Create index
        dim = len(next(iter(embeddings.values())))
        index = hnswlib.Index(space='cosine', dim=dim)

        # Initialize with expected size
        index.init_index(
            max_elements=len(embeddings),
            ef_construction=400,  # High quality for offline build
            M=16
        )

        # Use multi-threaded insertion (hnswlib supports this)
        index.set_num_threads(self.workers)

        # Add embeddings
        doc_ids = list(embeddings.keys())
        vectors = np.array([embeddings[doc_id] for doc_id in doc_ids])

        # Batch insert (faster than one-by-one)
        index.add_items(vectors, ids=range(len(doc_ids)))

        # Save doc_id mapping
        self.save_doc_id_mapping(doc_ids)

        return index
```

**Performance Characteristics:**

**100K Documents, 1024d embeddings, 8-core CPU:**

| Stage | Time (Sequential) | Time (Parallel, 6 workers) | Speedup |
|-------|------------------|---------------------------|---------|
| Text extraction | 30 min | 5 min | 6x |
| Embedding generation (API) | 60 min | 12 min | 5x |
| HNSW construction | 5 min | 3 min | 1.7x |
| BM25 indexing | 120 min | 20 min | 6x |
| **Total** | **215 min (3.6h)** | **40 min** | **5.4x** |

**Key Insight**: Embedding generation dominates total time. Optimize this first.

**Memory Management:**

```python
# Problem: Loading all embeddings into memory before HNSW construction
# Solution: Stream embeddings from disk

def build_hnsw_index_streaming(
    embedding_cache_path: Path,
    index_path: Path
) -> None:
    """Build HNSW index by streaming embeddings from disk."""
    import hnswlib

    # Count embeddings first (for index sizing)
    num_embeddings = count_embeddings(embedding_cache_path)

    # Create index
    index = hnswlib.Index(space='cosine', dim=1024)
    index.init_index(max_elements=num_embeddings, ef_construction=400, M=16)

    # Stream and add embeddings in batches
    batch_size = 10000
    batch_vectors = []
    batch_ids = []

    for doc_id, embedding in stream_embeddings(embedding_cache_path):
        batch_vectors.append(embedding)
        batch_ids.append(doc_id)

        if len(batch_vectors) >= batch_size:
            # Add batch to index
            index.add_items(np.array(batch_vectors), ids=batch_ids)

            # Clear batch
            batch_vectors = []
            batch_ids = []

    # Add remaining
    if batch_vectors:
        index.add_items(np.array(batch_vectors), ids=batch_ids)

    # Save index
    index.save_index(str(index_path))
```

**Authority Level:** Informed by RexLit's existing parallel architecture

**Sources:**
- RexLit /Users/bg/Documents/Coding/rex/rexlit/index/build.py (existing parallel indexing)
- https://github.com/nmslib/hnswlib#python-bindings (hnswlib multi-threading)

### 5.3 Memory Management for Large Corpora (100K+ Documents)

**Memory Budgets:**

**100K Documents, 1024d embeddings:**

| Component | Memory Usage | Notes |
|-----------|-------------|-------|
| Raw embeddings (disk) | 410 MB | 100K × 1024 × 4 bytes |
| HNSW index (RAM) | 600-800 MB | 1.5-2× raw vectors |
| Tantivy BM25 index (disk) | 500-1000 MB | Depends on text size |
| Metadata cache (RAM) | <10 MB | O(1) lookups per ADR |
| Working memory | 500 MB | Batching, temporary buffers |
| **Total RAM** | **~2 GB** | Fits on modest hardware |

**Scaling to 1M Documents:**

| Component | Memory Usage | Notes |
|-----------|-------------|-------|
| Raw embeddings (disk) | 4.1 GB | Stored on disk, not RAM |
| HNSW index (RAM) | 6-8 GB | Load on demand or use mmap |
| Tantivy BM25 index (disk) | 5-10 GB | Memory-mapped |
| Metadata cache (RAM) | 100 MB | Still O(1) |
| **Total RAM** | **~8 GB** | Requires mmap for HNSW |

**Memory Optimization Strategies:**

#### **1. Memory-Mapped HNSW Index**

```python
import hnswlib
import mmap

class MemoryMappedHNSWIndex:
    """HNSW index with memory-mapped storage."""

    def __init__(self, index_path: Path):
        self.index_path = index_path
        self.index = None

    def load(self, max_elements: int):
        """Load index using mmap (doesn't load all into RAM immediately)."""
        self.index = hnswlib.Index(space='cosine', dim=1024)

        # Load index (hnswlib uses mmap internally for large indices)
        self.index.load_index(
            str(self.index_path),
            max_elements=max_elements
        )

        # Set query parameters
        self.index.set_ef(50)  # Default query ef

    def search(self, query_embedding: np.ndarray, k: int = 20):
        """Search index (pages in required data on demand)."""
        labels, distances = self.index.knn_query(query_embedding, k=k)
        return labels[0], distances[0]
```

**Benefit**: OS pages in only the required parts of the index during queries.

#### **2. Quantization (Reduce Embedding Precision)**

```python
def quantize_embeddings(
    embeddings: dict[str, np.ndarray],
    num_bits: int = 8
) -> dict[str, np.ndarray]:
    """
    Quantize embeddings from float32 to int8 (4× memory reduction).

    Trade-off: Slight accuracy loss (typically <1% recall @ k=10)
    """
    # Find global min/max for normalization
    all_values = np.concatenate(list(embeddings.values()))
    min_val = all_values.min()
    max_val = all_values.max()

    quantized = {}
    for doc_id, emb in embeddings.items():
        # Normalize to [0, 255] for int8
        normalized = (emb - min_val) / (max_val - min_val) * 255
        quantized[doc_id] = normalized.astype(np.uint8)

    # Save quantization parameters for dequantization
    return quantized, {"min": min_val, "max": max_val}

# Storage: 100K × 1024 × 1 byte = 102 MB (vs 410 MB float32)
```

**Trade-off Analysis:**
- Memory savings: 4× (float32 → int8)
- Accuracy impact: <1% recall loss (acceptable for most use cases)
- Speed: Slightly faster (smaller memory footprint = better cache locality)

#### **3. Lazy Loading with LRU Cache**

```python
from functools import lru_cache

class LazyEmbeddingCache:
    """Load embeddings on-demand with LRU eviction."""

    def __init__(self, cache_dir: Path, max_cache_size: int = 10000):
        self.cache_dir = cache_dir
        self.max_cache_size = max_cache_size

    @lru_cache(maxsize=10000)
    def get_embedding(self, doc_id: str) -> np.ndarray:
        """Load embedding from disk (cached in memory)."""
        emb_path = self.cache_dir / f"{doc_id}.npy"
        return np.load(emb_path)
```

**Use Case**: When only a subset of embeddings are accessed frequently (e.g., recent documents).

#### **4. Streaming Index Construction**

Already covered in Section 5.2 - build HNSW index without loading all embeddings into memory.

**Recommendation for RexLit:**

- **100K docs**: No special optimization needed (fits in 2 GB RAM)
- **500K docs**: Use memory-mapped HNSW index
- **1M+ docs**: Use mmap + quantization (int8)

**Authority Level:** Industry best practices for large-scale vector search

**Sources:**
- https://github.com/nmslib/hnswlib/issues/104 (HNSW memory footprint discussion)
- https://www.pinecone.io/learn/vector-database/ (Vector database memory management)

### 5.4 Query Latency Optimization

**Latency Budget for RexLit:**

Target: <50ms for hybrid search (99th percentile)

**Breakdown:**

| Operation | Target Latency | Optimization |
|-----------|---------------|--------------|
| Query embedding generation | 10-20 ms | Cache, batch API |
| HNSW vector search | 10-20 ms | Tune ef_search |
| BM25 search (Tantivy) | 5-10 ms | Already optimized |
| RRF fusion | 1-2 ms | In-memory merge |
| Metadata lookup | <1 ms | O(1) cache (existing) |
| **Total** | **26-53 ms** | Within budget |

**Optimization Techniques:**

#### **1. Query Embedding Caching**

```python
# Already covered in Section 4.1 - LRU cache for repeated queries
@lru_cache(maxsize=1000)
def get_query_embedding_cached(query: str) -> np.ndarray:
    return generate_embedding(query)
```

**Impact**: Reduces 10-20ms to <1ms for repeated queries (common in legal discovery).

#### **2. Dynamic ef_search Tuning**

```python
def adaptive_search(
    index: hnswlib.Index,
    query_embedding: np.ndarray,
    k: int = 20,
    target_latency_ms: float = 20.0
) -> tuple[list[int], list[float]]:
    """
    Dynamically adjust ef_search to meet latency target.

    Start with low ef_search, increase if results are poor.
    """
    ef_search = 50  # Start conservative

    while ef_search <= 400:
        start = time.perf_counter()

        index.set_ef(ef_search)
        labels, distances = index.knn_query(query_embedding, k=k)

        latency_ms = (time.perf_counter() - start) * 1000

        # Check if latency is acceptable
        if latency_ms <= target_latency_ms:
            return labels[0], distances[0]

        # If too slow, reduce ef_search
        ef_search = int(ef_search * 0.8)
        break

    return labels[0], distances[0]
```

**Impact**: Automatically balances latency vs accuracy per query.

#### **3. Parallel BM25 + Vector Search**

```python
from concurrent.futures import ThreadPoolExecutor

def parallel_hybrid_search(query: str, k: int = 20) -> list[SearchResult]:
    """Execute BM25 and vector search in parallel."""

    def bm25_search_thread():
        return tantivy_search(query, k=k)

    def vector_search_thread():
        query_emb = get_query_embedding_cached(query)
        return hnsw_search(query_emb, k=k)

    with ThreadPoolExecutor(max_workers=2) as executor:
        bm25_future = executor.submit(bm25_search_thread)
        vector_future = executor.submit(vector_search_thread)

        bm25_results = bm25_future.result()
        vector_results = vector_future.result()

    # Fuse results
    return reciprocal_rank_fusion([bm25_results, vector_results])
```

**Impact**: Reduces latency from (BM25 + Vector) to max(BM25, Vector).

**Example:**
- Sequential: 10ms (BM25) + 20ms (Vector) = 30ms
- Parallel: max(10ms, 20ms) = 20ms
- Savings: 33%

#### **4. Pre-filtering with BM25 (Cascade)**

```python
def cascade_search(query: str, k: int = 20) -> list[SearchResult]:
    """
    Fast BM25 pre-filtering + vector reranking.

    Use Case: Very large corpus (1M+ docs) where full HNSW search is slow.
    """
    # Stage 1: Fast BM25 to get candidates (100-1000 docs)
    candidates = tantivy_search(query, k=1000)  # 10ms

    # Stage 2: Rerank top candidates with vectors
    query_emb = get_query_embedding_cached(query)  # 1ms (cached)

    reranked = []
    for doc_id, bm25_score in candidates[:100]:  # Only rerank top 100
        vector_score = compute_similarity(query_emb, doc_embeddings[doc_id])
        combined_score = 0.5 * bm25_score + 0.5 * vector_score
        reranked.append((doc_id, combined_score))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked[:k]
```

**Impact**: Reduces HNSW search from 100K docs to 100 docs (10-100× faster).

**Authority Level:** Industry standard query optimization techniques

**Sources:**
- https://blog.vespa.ai/improving-zero-shot-ranking-with-vespa-part-two/ (Hybrid search optimization)
- https://www.elastic.co/search-labs/blog/linear-retriever-hybrid-search

---

## 6. Security and Audit

### 6.1 Logging Embedding API Calls

**What to Log:**

1. **API Request Details**:
   - Timestamp
   - Document ID or query text (hash if sensitive)
   - Embedding model used
   - API endpoint
   - Request size (bytes, token count)

2. **API Response Details**:
   - Success/failure status
   - HTTP status code
   - Latency (milliseconds)
   - Embedding dimensions
   - Error message (if failed)

3. **Cost Tracking**:
   - Token count (for billing)
   - Estimated cost
   - Cumulative cost

**Implementation:**

```python
import hashlib
from datetime import datetime
from rexlit.audit import AuditLedger

class AuditedEmbeddingAPI:
    """Embedding API with comprehensive audit logging."""

    def __init__(self, api: EmbeddingAPI, ledger: AuditLedger):
        self.api = api
        self.ledger = ledger

    def generate_embedding(
        self,
        text: str,
        context: dict = None
    ) -> np.ndarray:
        """Generate embedding with audit logging."""
        start_time = time.perf_counter()

        # Hash text for privacy (don't log sensitive content)
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        token_count = len(text) // 4

        try:
            # Generate embedding
            embedding = self.api.generate(text)

            # Calculate metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            cost = self.estimate_cost(token_count)

            # Log success
            self.ledger.write({
                "event": "embedding_generated",
                "timestamp": datetime.utcnow().isoformat(),
                "text_hash": text_hash,
                "doc_id": context.get("doc_id") if context else None,
                "model": self.api.model,
                "dimensions": len(embedding),
                "token_count": token_count,
                "latency_ms": round(latency_ms, 2),
                "cost_usd": round(cost, 6),
                "status": "success",
            })

            return embedding

        except Exception as e:
            # Log failure
            latency_ms = (time.perf_counter() - start_time) * 1000

            self.ledger.write({
                "event": "embedding_failed",
                "timestamp": datetime.utcnow().isoformat(),
                "text_hash": text_hash,
                "doc_id": context.get("doc_id") if context else None,
                "model": self.api.model,
                "token_count": token_count,
                "latency_ms": round(latency_ms, 2),
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
            })

            raise

    def estimate_cost(self, token_count: int) -> float:
        """Estimate API cost based on token count."""
        # Example: OpenAI text-embedding-3-large at $0.13 per 1M tokens
        cost_per_million_tokens = 0.13
        return (token_count / 1_000_000) * cost_per_million_tokens
```

**Example Audit Log Entries:**

```jsonl
{"event": "embedding_generated", "timestamp": "2025-10-27T10:15:32Z", "text_hash": "a3d2c1b0...", "doc_id": "DOC-00001", "model": "text-embedding-3-large", "dimensions": 1024, "token_count": 512, "latency_ms": 45.23, "cost_usd": 0.000067, "status": "success"}
{"event": "embedding_failed", "timestamp": "2025-10-27T10:16:10Z", "text_hash": "b4e3f2a1...", "doc_id": "DOC-00002", "model": "text-embedding-3-large", "token_count": 1024, "latency_ms": 5001.12, "status": "failed", "error": "Request timeout", "error_type": "TimeoutError"}
{"event": "embedding_batch_generated", "timestamp": "2025-10-27T10:20:00Z", "batch_size": 100, "model": "text-embedding-3-large", "total_tokens": 51200, "latency_ms": 1230.45, "cost_usd": 0.006656, "status": "success"}
```

**Privacy Considerations:**

- **DON'T log**: Full text content (may contain privileged information)
- **DO log**: SHA-256 hash of text (sufficient for deduplication checks)
- **DO log**: Document ID (links to manifest for audit trail)

**Authority Level:** Legal e-discovery compliance standards (EDRM, ISO 27001)

### 6.2 Tracking Usage Metrics (Latency, Count)

**Metrics to Track:**

1. **Latency Metrics**:
   - Mean, median, p95, p99 latency
   - Latency by operation (generate vs batch)
   - Latency over time (detect degradation)

2. **Count Metrics**:
   - Total embeddings generated
   - Embeddings per document
   - API calls per minute/hour/day
   - Success vs failure rate

3. **Cost Metrics**:
   - Total cost (cumulative)
   - Cost per document
   - Cost by time period

**Implementation:**

```python
from dataclasses import dataclass, field
from collections import defaultdict
import json

@dataclass
class EmbeddingMetrics:
    """Track embedding API usage metrics."""

    # Counters
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Latency tracking
    latencies_ms: list[float] = field(default_factory=list)

    # Failures by type
    failures_by_error: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_success(self, latency_ms: float, token_count: int, cost: float):
        """Record successful API call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.total_tokens += token_count
        self.total_cost_usd += cost
        self.latencies_ms.append(latency_ms)

    def record_failure(self, error_type: str):
        """Record failed API call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.failures_by_error[error_type] += 1

    def get_summary(self) -> dict:
        """Get metrics summary."""
        latencies = sorted(self.latencies_ms)
        n = len(latencies)

        return {
            "total_calls": self.total_calls,
            "success_rate": self.successful_calls / self.total_calls if self.total_calls > 0 else 0,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "latency_stats": {
                "mean_ms": round(sum(latencies) / n, 2) if n > 0 else 0,
                "median_ms": round(latencies[n // 2], 2) if n > 0 else 0,
                "p95_ms": round(latencies[int(n * 0.95)], 2) if n > 0 else 0,
                "p99_ms": round(latencies[int(n * 0.99)], 2) if n > 0 else 0,
                "min_ms": round(min(latencies), 2) if n > 0 else 0,
                "max_ms": round(max(latencies), 2) if n > 0 else 0,
            },
            "failures_by_error": dict(self.failures_by_error),
        }

    def save(self, path: Path):
        """Save metrics to JSON file."""
        with open(path, "w") as f:
            json.dump(self.get_summary(), f, indent=2)

# Usage in index building
metrics = EmbeddingMetrics()

for doc in documents:
    try:
        embedding = api.generate_embedding(doc.text)
        metrics.record_success(latency_ms, token_count, cost)
    except Exception as e:
        metrics.record_failure(type(e).__name__)

# Save metrics after indexing
metrics.save(index_dir / "embedding_metrics.json")
```

**Example Metrics Report:**

```json
{
  "total_calls": 100000,
  "success_rate": 0.9999,
  "total_tokens": 51200000,
  "total_cost_usd": 6.656,
  "latency_stats": {
    "mean_ms": 42.3,
    "median_ms": 38.5,
    "p95_ms": 65.2,
    "p99_ms": 89.1,
    "min_ms": 12.4,
    "max_ms": 1230.5
  },
  "failures_by_error": {
    "TimeoutError": 1
  }
}
```

**CLI Integration:**

```bash
# Show metrics after indexing
$ rexlit index build ./docs --online --index-dir out/index
[INFO] Generating embeddings for 100,000 documents...
[INFO] Progress: 50,000/100,000 (50%) - ETA 15min
[INFO] Progress: 100,000/100,000 (100%) - Complete
[INFO] Embedding metrics:
[INFO]   Total calls: 100,000
[INFO]   Success rate: 99.99%
[INFO]   Total tokens: 51.2M
[INFO]   Total cost: $6.66
[INFO]   Latency (p50/p95/p99): 38.5ms / 65.2ms / 89.1ms
[INFO] Metrics saved to: out/index/embedding_metrics.json

# Query metrics
$ rexlit index stats out/index --show-embeddings
Index Statistics:
  Documents: 100,000
  BM25 index size: 845 MB
  HNSW index size: 612 MB
  Embedding model: text-embedding-3-large (1024d)
  Embedding generation:
    Cost: $6.66 USD
    Avg latency: 42.3ms
    Success rate: 99.99%
```

**Authority Level:** Industry standard observability practices

### 6.3 Deterministic Vector Storage

**Challenge for Legal E-Discovery:**

Reproducibility is critical. The same documents must produce the same embeddings across runs.

**Sources of Non-Determinism:**

1. **Embedding API Non-Determinism**:
   - Some APIs (OpenAI) may have slight variations between calls
   - Network packet order, server load, model updates

2. **Floating-Point Precision**:
   - Different hardware (CPU vs GPU) may produce slightly different results
   - Compiler optimizations, rounding errors

3. **Data Processing Order**:
   - If embeddings are generated in non-deterministic order, index may differ

**Determinism Strategies:**

#### **1. Cache Embeddings (Freeze Results)**

```python
class DeterministicEmbeddingCache:
    """
    Cache embeddings to ensure reproducibility.

    Once an embedding is generated and cached, it's never regenerated.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_or_generate(
        self,
        doc_id: str,
        text: str,
        api: EmbeddingAPI
    ) -> np.ndarray:
        """Get cached embedding or generate and cache."""
        cache_path = self.cache_dir / f"{doc_id}.npy"

        if cache_path.exists():
            # Use cached embedding (deterministic)
            return np.load(cache_path)
        else:
            # Generate new embedding
            embedding = api.generate(text)

            # Cache for future runs
            np.save(cache_path, embedding)

            # Log to audit trail
            self.log_generation(doc_id, text, embedding)

            return embedding

    def log_generation(self, doc_id: str, text: str, embedding: np.ndarray):
        """Log embedding generation for audit trail."""
        # Compute hash of text input (for verification)
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Compute hash of embedding output (for verification)
        emb_hash = hashlib.sha256(embedding.tobytes()).hexdigest()

        # Log to audit ledger
        audit_ledger.write({
            "event": "embedding_generated_cached",
            "doc_id": doc_id,
            "text_hash": text_hash,
            "embedding_hash": emb_hash,
            "timestamp": datetime.utcnow().isoformat(),
        })
```

**Benefit**: Once cached, embeddings are deterministic across all future runs.

#### **2. Deterministic Document Ordering**

```python
# Use RexLit's existing deterministic sorting (ADR 0003)
from rexlit.utils.deterministic import deterministic_sort

def generate_embeddings_deterministically(
    documents: list[Document],
    api: EmbeddingAPI
) -> dict[str, np.ndarray]:
    """Generate embeddings in deterministic order."""
    # Sort documents by (hash, path) for reproducibility
    sorted_docs = deterministic_sort(
        documents,
        key=lambda d: (d.sha256_hash, d.path)
    )

    embeddings = {}
    for doc in sorted_docs:
        embeddings[doc.id] = api.generate(doc.text)

    return embeddings
```

**Benefit**: Same input corpus → same processing order → same results.

#### **3. Version Locking**

```python
# Store embedding model version in index metadata
def save_index_metadata(index_dir: Path, metadata: dict):
    """Save index metadata with version locking."""
    meta = {
        "embedding_model": {
            "provider": "openai",
            "model": "text-embedding-3-large",
            "version": "2024-09-01",  # Lock model version
            "dimensions": 1024,
        },
        "hnsw_library": {
            "name": "hnswlib",
            "version": "0.8.0",  # Lock library version
        },
        "created_at": datetime.utcnow().isoformat(),
    }

    with open(index_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

# At query time: verify model version matches
def verify_model_version(index_dir: Path):
    """Ensure query uses same model as indexing."""
    with open(index_dir / "metadata.json") as f:
        meta = json.load(f)

    expected_model = meta["embedding_model"]["model"]
    expected_version = meta["embedding_model"]["version"]

    if current_model != expected_model or current_version != expected_version:
        raise ValueError(
            f"Model mismatch: index built with {expected_model} v{expected_version}, "
            f"but querying with {current_model} v{current_version}"
        )
```

**Benefit**: Prevents accidental model changes that break reproducibility.

#### **4. Verification Hash Chain**

```python
def compute_embedding_hash_chain(
    embeddings: dict[str, np.ndarray]
) -> str:
    """
    Compute hash chain over all embeddings (similar to audit ledger).

    Hash chain ensures integrity: any change to embeddings is detectable.
    """
    # Sort by doc_id for determinism
    sorted_docs = sorted(embeddings.keys())

    # Chain hashes together
    chain_hash = hashlib.sha256(b"EMBEDDING_HASH_CHAIN_V1").digest()

    for doc_id in sorted_docs:
        embedding = embeddings[doc_id]

        # Hash: previous_hash || doc_id || embedding_bytes
        hasher = hashlib.sha256()
        hasher.update(chain_hash)
        hasher.update(doc_id.encode())
        hasher.update(embedding.tobytes())
        chain_hash = hasher.digest()

    return chain_hash.hex()

# Save hash chain with index
def save_index_with_verification(index_dir: Path, embeddings: dict):
    """Save index with tamper-evident hash chain."""
    # Build HNSW index
    hnsw_index = build_hnsw_index(embeddings)
    hnsw_index.save_index(str(index_dir / "hnsw.bin"))

    # Compute and save hash chain
    hash_chain = compute_embedding_hash_chain(embeddings)

    with open(index_dir / "embedding_hash_chain.txt", "w") as f:
        f.write(hash_chain)

    # Log to audit trail
    audit_ledger.write({
        "event": "index_built",
        "index_dir": str(index_dir),
        "document_count": len(embeddings),
        "embedding_hash_chain": hash_chain,
        "timestamp": datetime.utcnow().isoformat(),
    })
```

**Benefit**: Tamper-evident verification (similar to RexLit's audit ledger).

**Research Finding:**

Recent research (2024) found that modern transformer embedding models are perfectly reproducible when:
- Same input text
- Same model version
- Same hardware (CPU/GPU differences may cause tiny floating-point variations)

However, practitioners cannot assume this and must empirically verify.

**Recommendation for RexLit:**

Implement all four strategies:
1. **Cache embeddings** (primary determinism mechanism)
2. **Deterministic ordering** (align with ADR 0003)
3. **Version locking** (prevent accidental changes)
4. **Hash chain verification** (tamper-evident audit)

**Authority Level:** Research-backed + legal e-discovery standards

**Sources:**
- https://arxiv.org/html/2509.18869 (Reproducibility of RAG systems)
- RexLit ADR 0003 (Determinism Policy)
- https://ironcorelabs.com/ai-encryption/ (Securing embeddings)

### 6.4 Protecting API Keys

**Best Practices:**

1. **Environment Variables** (Current RexLit Approach):
   ```bash
   export ISAACUS_API_KEY="sk-..."
   export OPENAI_API_KEY="sk-..."
   ```

2. **Never Commit Keys**:
   - Add to `.gitignore`: `.env`, `*.key`, `credentials.json`
   - Use pre-commit hooks to detect accidental commits

3. **Key Rotation**:
   - Rotate API keys every 90 days
   - Log rotation events in audit trail

4. **Principle of Least Privilege**:
   - Use read-only API keys when possible
   - Separate keys for dev/staging/prod

5. **Secrets Management** (Production):
   ```python
   # Use secrets management service
   import boto3

   def get_api_key() -> str:
       """Fetch API key from AWS Secrets Manager."""
       client = boto3.client('secretsmanager')
       response = client.get_secret_value(SecretId='rexlit/embedding_api_key')
       return response['SecretString']
   ```

**RexLit Integration:**

```python
# In config.py
class RexLitConfig(BaseSettings):
    """RexLit configuration with secure API key handling."""

    # Embedding API keys
    openai_api_key: Optional[str] = Field(None, env='OPENAI_API_KEY')
    cohere_api_key: Optional[str] = Field(None, 'COHERE_API_KEY')
    isaacus_api_key: Optional[str] = Field(None, env='ISAACUS_API_KEY')

    class Config:
        env_file = '.env'  # Load from .env file (gitignored)
        case_sensitive = False

    def get_embedding_api_key(self, provider: str) -> str:
        """Get API key for specified provider."""
        key = getattr(self, f"{provider}_api_key", None)

        if not key:
            raise ValueError(
                f"API key for {provider} not found. "
                f"Set {provider.upper()}_API_KEY environment variable."
            )

        return key
```

**Security Audit Log:**

```python
# Log API key usage (but NEVER log the key itself)
def log_api_key_usage(provider: str, operation: str):
    """Log API key usage for security audit."""
    audit_ledger.write({
        "event": "api_key_used",
        "provider": provider,
        "operation": operation,
        "key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8],  # First 8 chars of hash only
        "timestamp": datetime.utcnow().isoformat(),
    })
```

**Authority Level:** Industry standard security practices (OWASP, NIST)

**Sources:**
- https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password
- https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning

---

## 7. Implementation Recommendations for RexLit

### 7.1 Phased Implementation Plan

**Phase 1: Foundation (Offline Capabilities)**
- Implement embedding cache architecture
- Integrate Ollama for self-hosted embeddings
- Add `--online` flag awareness to index builder
- Test with small corpus (1K docs)

**Phase 2: HNSW Integration**
- Integrate hnswlib for vector search
- Implement HNSW index builder (M=16, ef_construction=400)
- Add index persistence and versioning
- Memory-mapped index loading
- Test with 10K docs

**Phase 3: Hybrid Search**
- Implement RRF fusion (k=60)
- Parallel BM25 + vector search
- Fallback to BM25 when vectors unavailable
- CLI flag: `--mode [auto|hybrid|bm25]`
- Test with 100K docs

**Phase 4: Optimization**
- Parallel embedding generation (batch processing)
- Query embedding caching (LRU)
- Dynamic ef_search tuning
- Performance benchmarking

**Phase 5: Security & Audit**
- Embedding API call logging
- Usage metrics tracking
- Deterministic embedding cache
- Hash chain verification

### 7.2 Recommended Technology Stack

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| Embedding Model | BAAI/bge-large-en-v1.5 (1024d) | Best balance of quality/speed for legal text |
| Self-Hosted Inference | Ollama + mxbai-embed-large | Simple setup, good performance, offline-capable |
| Cloud API Fallback | OpenAI text-embedding-3-large | Industry-leading quality, batch API for cost savings |
| Vector Index | hnswlib (Python bindings) | Fast, memory-efficient, easy integration |
| Fusion Method | Reciprocal Rank Fusion (k=60) | No tuning required, robust, widely adopted |
| Embedding Cache | Binary .npy files + JSONL metadata | Fast loading, audit trail, deterministic |
| Dimensionality | 1024 | Sweet spot for 100K docs (quality + performance) |

### 7.3 Configuration Schema

```python
# Add to rexlit/config.py

class EmbeddingConfig(BaseSettings):
    """Configuration for dense embeddings and hybrid search."""

    # Embedding provider
    embedding_provider: Literal["openai", "ollama", "sentence_transformers"] = "ollama"
    embedding_model: str = "mxbai-embed-large"
    embedding_dimensions: int = 1024

    # API keys (from environment)
    openai_api_key: Optional[str] = Field(None, env='OPENAI_API_KEY')

    # Batch processing
    embedding_batch_size: int = 32
    embedding_max_retries: int = 3
    embedding_timeout_sec: int = 30

    # HNSW parameters
    hnsw_m: int = 16
    hnsw_ef_construction: int = 400
    hnsw_ef_search: int = 50

    # Hybrid search
    hybrid_fusion_method: Literal["rrf", "weighted"] = "rrf"
    rrf_k: int = 60

    # Caching
    enable_query_embedding_cache: bool = True
    query_cache_size: int = 1000
```

### 7.4 CLI Commands

```bash
# Build index with hybrid search support
rexlit index build ./docs \
  --online \
  --index-dir out/index \
  --embedding-model mxbai-embed-large \
  --embedding-provider ollama \
  --workers 6

# Build index offline (BM25 only)
rexlit index build ./docs \
  --index-dir out/index \
  --workers 6

# Search with hybrid (requires --online at query time)
rexlit index search out/index \
  --query "privileged communication attorney" \
  --online \
  --mode hybrid \
  --top-k 20

# Search with explicit BM25 (offline)
rexlit index search out/index \
  --query "privileged communication attorney" \
  --mode bm25 \
  --top-k 20

# Show index capabilities
rexlit index info out/index
# Output:
#   Index: out/index
#   Documents: 100,000
#   BM25 index: 845 MB
#   Dense vectors: Available
#   HNSW index: 612 MB (1024d, M=16, ef_construction=400)
#   Embedding model: ollama/mxbai-embed-large
#   Supports hybrid search: Yes (requires --online for queries)

# Show embedding metrics
rexlit index stats out/index --show-embeddings
# Output:
#   Embedding Generation Metrics:
#     Total documents: 100,000
#     Success rate: 99.99%
#     Total cost: $0.00 (self-hosted)
#     Avg latency: 42.3ms
#     p99 latency: 89.1ms
```

### 7.5 Testing Strategy

**Unit Tests:**
- Embedding cache (save/load)
- RRF fusion algorithm
- Score normalization
- Deterministic ordering

**Integration Tests:**
- End-to-end index build (small corpus: 100 docs)
- Hybrid search vs BM25-only comparison
- Offline/online mode transitions
- Fallback behavior (API failures)

**Performance Benchmarks:**
- 100K documents indexing time (target: <60 min)
- Query latency (target: <50ms p99)
- Memory usage (target: <2 GB for 100K docs)

**Security Tests:**
- API key not logged
- Embeddings deterministic across runs
- Hash chain verification

### 7.6 Documentation Requirements

1. **User Guide**: How to enable hybrid search, when to use online mode
2. **Architecture Doc**: Update ARCHITECTURE.md with dense vector design
3. **ADR**: Create ADR for hybrid search architecture decision
4. **CLI Guide**: Update CLI-GUIDE.md with new commands and flags

---

## 8. References

### 8.1 Official Documentation

- **hnswlib**: https://github.com/nmslib/hnswlib
- **OpenAI Embeddings API**: https://platform.openai.com/docs/guides/embeddings
- **Ollama**: https://ollama.com/
- **Sentence Transformers**: https://www.sbert.net/

### 8.2 Research Papers

1. **BEIR Benchmark**: Thakur, N., et al. (2021). "BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models." arXiv:2104.08663. https://arxiv.org/abs/2104.08663

2. **Late Chunking**: (2024). "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models." arXiv:2409.04701. https://arxiv.org/html/2409.04701v3

3. **Reproducibility of RAG**: (2024). "On The Reproducibility Limitations of RAG Systems." arXiv:2509.18869. https://arxiv.org/html/2509.18869

4. **HNSW Algorithm**: Malkov, Y. A., & Yashunin, D. A. (2018). "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs." IEEE Transactions on Pattern Analysis and Machine Intelligence.

### 8.3 Industry Guides

- **Microsoft Azure**: "Hybrid search ranking with RRF" https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
- **OpenSearch**: "Introducing reciprocal rank fusion for hybrid search" https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/
- **Weaviate**: "Hybrid Search Explained" https://weaviate.io/blog/hybrid-search-explained
- **Pinecone**: "Hierarchical Navigable Small Worlds (HNSW)" https://www.pinecone.io/learn/series/faiss/hnsw/
- **Elastic**: "Reciprocal rank fusion" https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion

### 8.4 Blog Posts and Tutorials

- "Optimizing Chunking, Embedding, and Vectorization for RAG" https://medium.com/@adnanmasood/optimizing-chunking-embedding-and-vectorization-for-retrieval-augmented-generation-ea3b083b68f7
- "Breaking up is hard to do: Chunking in RAG applications" https://stackoverflow.blog/2024/12/27/breaking-up-is-hard-to-do-chunking-in-rag-applications/
- "OpenSearch HNSW Hyperparameters" https://opensearch.org/blog/a-practical-guide-to-selecting-hnsw-hyperparameters/
- "Embedding models and dimensions" https://devblogs.microsoft.com/azure-sql/embedding-models-and-dimensions-optimizing-the-performance-resource-usage-ratio/

### 8.5 Vector Database Vendors

- **Milvus**: https://milvus.io/
- **Weaviate**: https://weaviate.io/
- **Qdrant**: https://qdrant.tech/
- **Pinecone**: https://www.pinecone.io/
- **LanceDB**: https://lancedb.com/

---

## Appendix A: Quick Reference

### HNSW Parameter Quick Guide

| Parameter | Range | Default | When to Increase | When to Decrease |
|-----------|-------|---------|-----------------|-----------------|
| M | 5-64 | 16 | High-dim data, need better recall | Low-dim data, memory constrained |
| ef_construction | 100-1000 | 200 | Index quality is poor | Build time too slow |
| ef_search | 10-500 | 50 | Need higher recall | Queries too slow |

### Embedding Model Comparison

| Model | Provider | Dimensions | Quality | Speed | Cost |
|-------|----------|-----------|---------|-------|------|
| all-MiniLM-L6-v2 | Sentence Transformers | 384 | Good | Fast | Free |
| bge-base-en-v1.5 | BAAI | 768 | Excellent | Moderate | Free |
| bge-large-en-v1.5 | BAAI | 1024 | Best | Moderate | Free |
| text-embedding-3-small | OpenAI | 1536 | Excellent | Fast | $0.02/1M tokens |
| text-embedding-3-large | OpenAI | 3072 (1024 via truncation) | Best | Moderate | $0.13/1M tokens |
| voyage-law-2 | Voyage AI | 1024 | Best (legal) | Moderate | $$$ |

### RRF Implementation (Python)

```python
def reciprocal_rank_fusion(result_lists, k=60):
    rrf_scores = {}
    for results in result_lists:
        for rank, (doc_id, _) in enumerate(results, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1/(k + rank)
    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
```

### Memory Estimation Formula

```
HNSW Memory (MB) = (num_vectors × dimensions × 4 + num_vectors × M × 2 × 4) / 1,048,576
```

Example: 100K vectors, 1024d, M=16
```
= (100,000 × 1024 × 4 + 100,000 × 16 × 2 × 4) / 1,048,576
= (409,600,000 + 12,800,000) / 1,048,576
= 402.8 MB
```

---

**Document Status**: Research Complete
**Next Steps**: Implement Phase 1 (Foundation) in RexLit
**Questions**: Contact for clarifications on implementation details
