# Self-Hosted Embeddings

This guide explains how to run dense retrieval without sending data to a hosted API. RexLit’s dense integration uses the `EmbeddingPort` and `VectorStorePort` so providers can be swapped.

Current adapter: `Kanon2Adapter` (Isaacus API). Future adapters: `OllamaAdapter`, `OpenAIAdapter`.

## Options

1) Self-hosted Isaacus-compatible endpoint
- Run an Isaacus-compatible embedding service on your network
- Set `ISAACUS_API_BASE` to the service base URL
- Provide `ISAACUS_API_KEY` (or `--isaacus-api-key`)

Example:
```bash
export REXLIT_ONLINE=1
export ISAACUS_API_BASE=http://isaacus.local:8080
export ISAACUS_API_KEY=sk-...redacted...
rexlit index build ./docs --dense --dim 768
```

2) Translation proxy (advanced)
- Run a small proxy that exposes the Isaacus embeddings API surface and forwards to a local runtime (e.g., Ollama `mxbai-embed-large`)
- Configure `ISAACUS_API_BASE` to point at the proxy

Notes:
- Ensure the proxy matches the Isaacus embeddings request/response schema (`embeddings.create` with `input`/`texts`, `data[*].embedding`, `usage.total_tokens`).
- Keep request payload sizes reasonable (32–64 texts per batch) to avoid timeouts.

## Offline-first considerations

- Online mode must be explicitly enabled (`--online` or `REXLIT_ONLINE=1`)
- API keys are never written to the audit ledger; only document hashes and artifact paths are logged
- Once built, the HNSW index can be loaded and queried offline; however, query-time embeddings still require an online embedder

## Troubleshooting

- `Kanon 2 embeddings requires online mode`: add `--online` to CLI or set `REXLIT_ONLINE=1`
- `ISAACUS_API_KEY required`: pass `--isaacus-api-key` or set the env var
- `hnswlib is required`: install `hnswlib` (CPU-only) if you plan to build/query the vector index locally

## Roadmap

- Native `OllamaAdapter` implementing `EmbeddingPort`
- `--provider` and `--model` flags to select adapters at runtime
- Incremental HNSW updates via `add_items`
