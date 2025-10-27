# Track B — Kanon 2 integration (minimal, hex-friendly)

## Objective
Deliver dense and hybrid retrieval that respects RexLit's offline-first contract while keeping the index module hexagonal and vendor-neutral.

## Success Criteria
- `rexlit index build PATH --dense --dim 768 --online` produces Tantivy + HNSW artifacts that can be re-opened offline.
- `rexlit search "query" --hybrid` returns results with higher Recall@10 than BM25-only on the sample corpus.
- Embedding calls refuse to run unless `--online` or `REXLIT_ONLINE=1` is present and emit structured audit entries.
- Tests and docs explain the new online dependency and self-host escape hatches.

## Work Breakdown (Day 3–5)
1. **Embedding port + Kanon 2 adapter**
   - Add `EmbeddingPort` protocol to `rexlit/index/ports.py` with docstring clarifying doc vs query embeddings and dimensionality expectations.
   - Implement `Kanon2Adapter` in `rexlit/index/adapters/kanon2.py`; guard constructor with `utils.online.is_online()` and surface `ISAACUS_API_KEY` / `ISAACUS_API_BASE`.
   - Default to 768 dims; allow overrides via CLI flag and config; return vectors plus optional usage metadata for logging.
   - Emit audit ledger entries `{timestamp, model, dim, count, latency_p50, latency_p95}` and fail fast with actionable error when offline.

2. **Local ANN store (HNSW)**
   - Introduce `HNSWStore` in `rexlit/index/hnsw_store.py` wrapping `hnswlib`; ensure all paths resolve inside the requested index root.
   - Implement `build/load/query` methods with configurable `M`, `ef_construction`, and `ef_search`; persist metadata alongside serialized index.
   - Document memory sizing heuristic (768 dims ≈ 3 KB per chunk; 1M chunks ~3 GB vectors + 0.5–1 GB graph) and chunking guidance (1–2k tokens, 10–15% overlap).

3. **Hybrid ranking glue**
   - Add `rrf_score` and `fuse` helpers (`rexlit/index/hybrid.py`) implementing Reciprocal Rank Fusion with BM25 fallback.
   - Extend indexing pipeline to optionally compute dense vectors and persist them to HNSW during `index build`.
   - Update search flow to fan out BM25 + dense queries when `--hybrid` is set, fusing scores and returning top-k doc IDs with provenance.
   - Keep BM25-only path untouched when dense materials are absent.

4. **CLI, config, and docs**
   - Extend `rexlit index build` with `--dense/--no-dense`, `--dim`, and `--online` switches; wire defaults through settings module.
   - Update `rexlit search` to accept `--hybrid`, `--top`, and dim overrides while remaining backward compatible.
   - Document new flags, ISAACUS configuration, and hybrid usage in `README.md` under “Dense/Hybrid Search (Kanon 2)”; call out offline gating and security considerations.

5. **Validation suite**
   - Add pytest coverage: dense index build smoke, hybrid recall improvement on `tests/data/sample-corpus`, offline guard raising when `--online` missing, ledger integrity check (`H-009` truncation).
   - Rebuild golden manifests in `tests/fixtures/` as needed; ensure deterministic vectors within tolerance.
   - Capture CLI smoke snippets (`rexlit index build ...`, `rexlit search ...`) for PR artifacts.

## Open Items & Risks
- Confirm `isaacus` client availability in offline environments; prepare fallback message if wheel missing.
- Validate HNSW parameter defaults for typical corpus sizes (<100k chunks) to avoid over-allocating memory.
- Coordinate with audit team on ledger schema change to store latency percentiles.

## Exit Checklist
- [ ] Code merged with green `pytest -v --no-cov`.
- [ ] CLI smoke runs recorded in PR description.
- [ ] README updated with Kanon 2 workflow.
- [ ] Ledger entries reviewed for hash-chain continuity.
