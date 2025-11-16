# RexLit API - REXLIT_HOME Configuration Guide

## Problem: SHA-256 Document Not Found Errors

If you see errors like:
```
No document found for SHA-256 96b331f0f550e1d2e6efb698040e0c77ebfe4ed7de332b297e64fad3376b0f7f
```

This means the API's REXLIT_HOME doesn't match where documents were indexed.

## Default Configuration

By default, the API uses:
- **REXLIT_HOME**: `~/.local/share/rexlit` (or `$REXLIT_HOME` if set)
- **REXLIT_BIN**: Auto-detected from `.venv/bin/rexlit` or `rexlit` on PATH

## Verifying Your Setup

### 1. Check where your index is located:
```bash
# Default location
ls -la ~/.local/share/rexlit/index/

# Check metadata cache
cat ~/.local/share/rexlit/index/.metadata_cache.json
```

### 2. Check API configuration:
```bash
cd api
echo $REXLIT_HOME  # Should match where your index is
which rexlit       # Verify CLI is accessible
```

### 3. Test the CLI directly:
```bash
# Search for documents
rexlit index search "test" --limit 5 --json

# Get a specific document by hash
rexlit index get <sha256-hash> --json
```

## Setting Custom REXLIT_HOME

If you need to use a different location:

### Option 1: Environment Variable (Recommended)
```bash
cd api
export REXLIT_HOME=/path/to/your/rexlit/data
bun run dev
```

### Option 2: Create `.env` file
```bash
cd api
cat > .env << EOF
REXLIT_HOME=/path/to/your/rexlit/data
REXLIT_BIN=/path/to/rexlit
PORT=3000
EOF
bun run dev
```

## Rebuilding the Index

If your documents and index are out of sync:

```bash
# 1. Set REXLIT_HOME to where you want everything
export REXLIT_HOME=~/.local/share/rexlit

# 2. Rebuild the index
rexlit index build ~/Documents/sample-docs --workers 6

# 3. Verify the index
rexlit index search "*" --limit 10 --json
```

## Troubleshooting

### API can't find documents that search returns:
- **Cause**: Search is using one index, but document lookup uses different REXLIT_HOME
- **Fix**: Ensure API's REXLIT_HOME matches where you built the index

### Multiple REXLIT_HOME directories:
- **Issue**: Having multiple locations (e.g., `api/.tmp-rexlit-home/`) causes confusion
- **Fix**: Delete old/test locations, use one canonical REXLIT_HOME

### Fresh start:
```bash
# Remove all RexLit data
rm -rf ~/.local/share/rexlit

# Remove temp directories
rm -rf api/.tmp-rexlit-home

# Rebuild from scratch
rexlit index build ~/Documents/sample-docs --workers 6

# Start API
cd api && bun run dev
```

## Verification

Once configured correctly:

```bash
# Start API
cd api && bun run dev

# In another terminal, test search:
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'

# Test document retrieval (use a hash from search results):
curl http://localhost:3000/api/documents/<hash>/meta
curl http://localhost:3000/api/documents/<hash>/file
```

Both endpoints should return 200 OK with document data.
