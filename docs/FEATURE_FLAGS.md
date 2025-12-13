# Feature Flags and Environment Variables

RexLit configuration is controlled through environment variables and CLI flags. This document provides a complete reference.

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `REXLIT_HOME` | `~/.local/share/rexlit` | Base data directory for indexes, manifests, and audit logs |
| `REXLIT_ONLINE` | `false` | Enable network features (dense search, LLM privilege classification) |
| `REXLIT_WORKERS` | `cpu_count - 1` | Parallel worker count for indexing |
| `REXLIT_BATCH_SIZE` | `100` | Documents per batch during indexing |
| `REXLIT_LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Directory Structure

When `REXLIT_HOME` is set, RexLit creates the following structure:

```
$REXLIT_HOME/
├── index/              # Tantivy search index
│   └── dense/          # HNSW vector index (if dense enabled)
├── manifests/          # Document manifests (JSONL)
├── audit/              # Audit ledger
│   └── log.jsonl       # Append-only hash chain
├── bates/              # Bates plans and registries
├── productions/        # Production exports (DAT/Opticon)
└── policies/           # Privilege policy templates
```

## Online Mode

Network-dependent features require explicit opt-in:

```bash
# Via environment variable
export REXLIT_ONLINE=1

# Via CLI flag (per-command)
rexlit --online index build ./docs --dense
```

### Features Requiring Online Mode

| Feature | Required Variable | Description |
|---------|-------------------|-------------|
| Dense embeddings | `REXLIT_ONLINE=1` + `ISAACUS_API_KEY` | Kanon 2 semantic embeddings |
| Hybrid search | `REXLIT_ONLINE=1` + `ISAACUS_API_KEY` | Combined lexical + dense ranking |
| LLM privilege | `REXLIT_ONLINE=1` + `GROQ_API_KEY` | Groq-powered privilege classification |

## API Keys

### Isaacus (Dense Search)

```bash
# Kanon 2 API access token
export ISAACUS_API_KEY="your-isaacus-key"

# Optional: Self-hosted Isaacus endpoint
export ISAACUS_API_BASE="https://your-isaacus-host/api"
```

### Groq (Privilege Classification)

```bash
# Groq Cloud API key for LLM privilege classification
export GROQ_API_KEY="your-groq-key"

# Set up encrypted key storage (recommended)
python scripts/setup_groq_key.py
```

## Privilege Classification

| Variable | Default | Description |
|----------|---------|-------------|
| `REXLIT_PRIVILEGE_MODEL_PATH` | (bundled) | Path to local privilege model |
| `REXLIT_PRIVILEGE_PATTERN_SKIP_THRESHOLD` | `0.85` | Confidence to skip LLM escalation |
| `REXLIT_PRIVILEGE_PATTERN_ESCALATE_THRESHOLD` | `0.50` | Minimum confidence for LLM review |

## CLI Flag Overrides

Most environment variables have corresponding CLI flags:

```bash
# Override data directory
rexlit --data-dir /custom/path index build ./docs

# Enable online mode
rexlit --online privilege classify ./email.txt

# Set worker count
rexlit index build ./docs --workers 8
```

## XDG Compliance

RexLit follows the XDG Base Directory Specification:

| XDG Variable | RexLit Usage | Default |
|--------------|--------------|---------|
| `XDG_DATA_HOME` | Data directory fallback | `~/.local/share` |
| `XDG_CONFIG_HOME` | Config files | `~/.config/rexlit` |
| `XDG_CACHE_HOME` | Cache directory | `~/.cache/rexlit` |

If `REXLIT_HOME` is set, it takes precedence over XDG variables.

## Testing Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD` | (unset) | Set to `1` to disable pytest plugins |
| `IDL_FIXTURE_PATH` | (unset) | Custom path for IDL test fixtures |

Example test run:

```bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
uv run pytest -v --no-cov
```

## Web UI Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:3000/api` | API endpoint for React UI |
| `PORT` | `3000` | Bun/Elysia API server port |

## Security Considerations

- Never commit API keys to version control
- Use encrypted key storage for production (see `scripts/setup_groq_key.py`)
- Keep `REXLIT_ONLINE` disabled in air-gapped environments
- Audit logs are append-only with SHA-256 hash chaining

## Examples

### Offline Discovery Workflow

```bash
# No network access required
unset REXLIT_ONLINE
rexlit ingest ./evidence --manifest out/manifest.jsonl
rexlit index build ./evidence
rexlit index search "privileged" --limit 20
```

### Online Hybrid Search

```bash
export REXLIT_ONLINE=1
export ISAACUS_API_KEY="your-key"
rexlit index build ./docs --dense --dim 768
rexlit index search "attorney client privilege" --mode hybrid
```

### Custom Data Directory

```bash
export REXLIT_HOME=/mnt/secure/rexlit
rexlit ingest ./case_001 --manifest $REXLIT_HOME/manifests/case_001.jsonl
```

## See Also

- [INSTALL.md](INSTALL.md) - Installation guide
- [CLI-GUIDE.md](../CLI-GUIDE.md) - Complete command reference
- [SECURITY.md](../SECURITY.md) - Security posture and threat model
