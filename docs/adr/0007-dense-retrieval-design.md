# ADR 0007: Dense Retrieval and Hybrid Search

Date: 2025-10-27

## Status
Accepted

## Context

RexLit adds optional dense retrieval using Kanon 2 embeddings and an HNSW vector index. The project is offline-first with a strict hexagonal architecture.

## Decision

1. Ports and adapters
   - Introduce `EmbeddingPort` and `VectorStorePort` protocols
   - Implement `Kanon2Adapter` (Isaacus) and `HNSWAdapter` (hnswlib)
   - Wire via `bootstrap.py` behind `OfflineModeGate`

2. Separate indexes
   - Keep Tantivy (BM25) and HNSW (cosine) as separate artifacts
   - Persist HNSW to `<index_dir>/dense/kanon2_<dim>.hnsw` with adjacent metadata JSON

3. Fusion strategy
   - Use Reciprocal Rank Fusion (RRF) with `k=60` for hybrid results
   - Avoid fragile score normalization across BM25 and cosine

4. Matryoshka dimensions
   - Default to 768 dimensions; support 256–1792

5. Offline-first enforcement
   - Embedding RPCs require `--online` or `REXLIT_ONLINE=1`
   - Once built, HNSW loads and queries offline

## Consequences

- Enables provider swap (future: Ollama/OpenAI) without touching domain code
- Simplifies testing via mock ports; avoids network during CI
- Maintains clear security boundary for network calls

## Alternatives Considered

- Unified index in Tantivy → rejected (no native ANN; higher complexity)
- Score normalization for fusion → rejected (corpus-specific tuning)
- FAISS instead of hnswlib → rejected (GPU dependency; not offline-friendly)

## References

- `rexlit/app/ports/embedding.py`, `rexlit/app/ports/vector_store.py`
- `rexlit/app/adapters/kanon2.py`, `rexlit/app/adapters/hnsw.py`
- `rexlit/index/build.py`, `rexlit/index/search.py`
