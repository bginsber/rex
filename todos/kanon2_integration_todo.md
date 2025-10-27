# Kanon 2 Integration — Working TODO

Scope: Complete dense/hybrid retrieval integration per github_issue_kanon2_integration.md with hexagonal architecture compliance.

Owner: @bg  
Created: today

## Now
- [x] Scaffold ports: `EmbeddingPort`, `VectorStorePort`
- [x] Add adapters: `Kanon2Adapter`, `HNSWAdapter` (exports wired)
- [x] Bootstrap: optional `embedder` and `vector_store_factory` fields
- [x] Compatibility shims in `rexlit/index/kanon2_embedder.py` and `rexlit/index/hnsw_store.py`
- [x] Refactor `build_dense_index()` and `dense/hybrid` search to accept ports; minimal ledger log

## Next
- [x] Wire `TantivyIndexAdapter` into container (replace stub)
- [x] Route CLI index build/search through adapter using ports
- [x] Emit audit `embedding_batch` entries with latency p50/p95/p99 and token totals

## Tests
- [x] Mock embedder/vector store smoke test for port path
- [x] Vector store load/query happy path tests (adapter path)
- [x] Offline gate refusal tests for CLI dense/hybrid
- [x] Adapter hybrid search delegation test
- [x] Hybrid RRF fusion correctness with stubbed inputs

## Docs
- [ ] README: Dense/Hybrid Search section
- [ ] ADR 0007: Dense retrieval design
- [ ] Self-host guide: `docs/SELF_HOSTED_EMBEDDINGS.md`

## Notes
- Keep offline-first: gate network calls via `OfflineModeGate.require()`
- Avoid breaking current callers; maintain shims until refactor lands
