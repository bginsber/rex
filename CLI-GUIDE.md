# RexLit CLI Guide

Complete command reference for RexLit M0.

## Table of Contents

- [Global Options](#global-options)
- [Ingest Commands](#ingest-commands)
- [Index Commands](#index-commands)
- [Audit Commands](#audit-commands)
- [Common Workflows](#common-workflows)

---

## Global Options

Available for all commands:

```bash
--help              Show help message and exit
--version           Show version and exit
```

---

## Ingest Commands

### `rexlit ingest`

Discover and ingest documents from a directory.

#### Synopsis

```bash
rexlit ingest PATH [OPTIONS]
```

#### Arguments

- `PATH` - Path to file or directory to ingest (required)

#### Options

- `--manifest FILE` - Write document metadata to JSONL manifest file
- `--recursive` - Recursively scan subdirectories (default: True)
- `--filter PATTERN` - Filter files by glob pattern (e.g., "*.pdf")

#### Examples

```bash
# Ingest single directory
rexlit ingest /litigation/case-001

# Create manifest file
rexlit ingest /docs --manifest output.jsonl

# Filter only PDFs
rexlit ingest /docs --filter "*.pdf"

# Non-recursive scan
rexlit ingest /docs --no-recursive
```

#### Output

```
Discovering documents in /litigation/case-001...
Found 1,523 documents
  - PDF: 1,245
  - DOCX: 178
  - TXT: 100

Manifest written to output.jsonl
```

#### Supported Formats

- **PDF** (.pdf) - Portable Document Format
- **DOCX** (.docx) - Microsoft Word documents
- **TXT** (.txt) - Plain text files
- **Markdown** (.md) - Markdown documents

#### Metadata Extraction

RexLit automatically extracts:
- **Custodian**: From directory path (e.g., `/custodians/john_doe/doc.pdf` → "john_doe")
- **Document Type**: From file extension
- **SHA-256 Hash**: Cryptographic fingerprint
- **File Path**: Absolute path to document

---

## Index Commands

### `rexlit index build`

Build full-text search index from documents.

#### Synopsis

```bash
rexlit index build PATH [OPTIONS]
```

#### Arguments

- `PATH` - Root directory containing documents (required)

#### Options (core)

- `--rebuild` - Delete and rebuild existing index

#### Options (dense retrieval)

- `--dense` - Build Kanon 2 dense embeddings + HNSW (requires `--online`)
- `--dim INT` - Matryoshka output dimension (default: 768)
- `--dense-batch INT` - Embedding request batch size (default: 32)
- `--isaacus-api-key TEXT` - Override `ISAACUS_API_KEY`
- `--isaacus-api-base TEXT` - Self-hosted Isaacus endpoint

#### Examples

```bash
# Build index with defaults
rexlit index build /litigation/docs

# Rebuild from scratch
rexlit index build /docs --rebuild

# Control parallelism
rexlit index build /docs --max-workers 4

# Silent mode
rexlit index build /docs --no-progress
```

#### Output

```
Discovering and indexing documents in /docs...
Found 10,000 documents. Processing with 7 workers...
Indexed 1000/10000 documents (234.5 docs/sec)
Indexed 2000/10000 documents (256.3 docs/sec)
...
Indexed 10000/10000 documents (248.7 docs/sec)

Index complete:
  - Indexed: 10,000 documents
  - Skipped: 0 documents
  - Time: 40.2 seconds
  - Throughput: 248.7 docs/sec
```

#### Performance Notes

- **Parallel Processing**: Uses `ProcessPoolExecutor` for maximum throughput
- **Memory Efficient**: Streaming document discovery (O(1) memory)
- **Optimal Workers**: `cpu_count() - 1` leaves one core for OS
- **Batch Commits**: Commits every 1,000 documents for memory management

#### Benchmarks

| Document Count | Time (8 cores) | Throughput |
|----------------|----------------|------------|
| 1,000 | 4 seconds | 250 docs/sec |
| 10,000 | 40 seconds | 250 docs/sec |
| 100,000 | 4-6 hours | 5-7 docs/sec* |

*Note: Includes text extraction overhead for PDF/DOCX

---

### `rexlit index search`

Search indexed documents using full-text search.

#### Synopsis

```bash
rexlit index search QUERY [OPTIONS]
```

#### Arguments

- `QUERY` - Search query string (required)

#### Options (core)

- `--limit N` - Maximum results to return (default: 10)
- `--json` - Output results as JSON

#### Options (dense/hybrid)

- `--mode [lexical|dense|hybrid]` - Retrieval strategy (dense/hybrid require `--online`)
- `--dim INT` - Embedding dimension for query/dense search (default: 768)
- `--isaacus-api-key TEXT` - Override `ISAACUS_API_KEY`
- `--isaacus-api-base TEXT` - Self-hosted Isaacus endpoint

#### Examples

```bash
# Basic search
rexlit index search "breach of contract"

# Limit results
rexlit index search "evidence" --limit 5

# JSON output
rexlit index search "deposition" --json

# With metadata
rexlit index search "plaintiff" --show-metadata
```

#### Output (Default)

```
Search results for "breach of contract":

1. /docs/custodians/john_doe/contract-2024.pdf
   Custodian: john_doe
   Type: pdf
   SHA256: 3a5f89b...

2. /docs/legal/agreements/vendor-contract.docx
   Custodian: legal
   Type: docx
   SHA256: 7b2c41d...

Found 2 documents
```

#### Output (JSON)

```json
{
  "query": "breach of contract",
  "results": [
    {
      "path": "/docs/custodians/john_doe/contract-2024.pdf",
      "custodian": "john_doe",
      "doctype": "pdf",
      "sha256": "3a5f89b2c14d...",
      "score": 12.45
    }
  ],
  "total": 2
}
```

#### Search Syntax

RexLit uses Tantivy's query parser:

```bash
# Phrase search
rexlit index search '"breach of contract"'

# Boolean operators
rexlit index search "contract AND (breach OR violation)"

# Wildcard
rexlit index search "depos*"

# Field search (if schema supports)
rexlit index search "custodian:john_doe"
```

---

### `rexlit index stats`

Display index statistics.

#### Synopsis

```bash
rexlit index stats [OPTIONS]
```

#### Options

- `--json` - Output as JSON

#### Examples

```bash
# Show stats
rexlit index stats

# JSON output
rexlit index stats --json
```

#### Output

```
Index Statistics:
  Location: /Users/user/.local/share/rexlit/index
  Documents: 10,000
  Segments: 5
  Size: 2.3 GB

Metadata Cache:
  Custodians: 45
  Document Types: 4
  Last Updated: 2025-10-23 14:32:15
```

---

## Audit Commands

### `rexlit audit show`

Display audit trail entries.

#### Synopsis

```bash
rexlit audit show [OPTIONS]
```

#### Options

- `--tail N` - Show last N entries only
- `--json` - Output as JSON (one entry per line)
- `--audit-file FILE` - Path to audit ledger (default: `~/.local/share/rexlit/audit.jsonl`)

#### Examples

```bash
# Show all entries
rexlit audit show

# Last 10 entries
rexlit audit show --tail 10

# JSON output
rexlit audit show --json > audit-export.jsonl

# Custom audit file
rexlit audit show --audit-file /backup/audit.jsonl
```

#### Output

```
Audit Trail: /Users/user/.local/share/rexlit/audit.jsonl

[2025-10-23 09:15:23] INDEX_BUILD_START
  root: /litigation/docs
  hash: 4a7b3c2d...

[2025-10-23 09:18:45] INDEX_BUILD_COMPLETE
  indexed: 1000
  skipped: 0
  hash: 9f1e8a4b...
  previous_hash: 4a7b3c2d...

[2025-10-23 10:22:10] SEARCH_QUERY
  query: "breach of contract"
  results: 5
  hash: 2b5c9e1a...
  previous_hash: 9f1e8a4b...

Total entries: 3
```

---

### `rexlit audit verify`

Verify audit trail cryptographic integrity.

#### Synopsis

```bash
rexlit audit verify [OPTIONS]
```

#### Options

- `--audit-file FILE` - Path to audit ledger (default: `~/.local/share/rexlit/audit.jsonl`)
- `--verbose` - Show detailed verification output

#### Examples

```bash
# Verify integrity
rexlit audit verify

# Verbose mode
rexlit audit verify --verbose

# Custom file
rexlit audit verify --audit-file /backup/audit.jsonl
```

#### Output (Success)

```
✓ Audit trail verification PASSED

Verified 15 entries
Chain integrity: OK
Genesis hash: Valid
No tampering detected
```

#### Output (Failure)

```
✗ Audit trail verification FAILED

Entry 12 has invalid hash chain
  Expected previous_hash: 9f1e8a4b2c5d...
  Actual previous_hash: 1234567890ab...

Possible tampering detected at entry 12
```

#### Verification Process

The verification checks:

1. **Genesis Hash**: First entry must have `previous_hash` of 64 zeros
2. **Hash Chain**: Each entry's `hash` must match recomputed SHA-256
3. **Chain Linkage**: Each `previous_hash` must match prior entry's `hash`
4. **Temporal Order**: Entries must be in chronological order

**Any modification breaks the chain** - this is by design for legal defensibility.

---

## Common Workflows

### Complete E-Discovery Workflow

```bash
# 1. Ingest documents
rexlit ingest /case-data --manifest case-manifest.jsonl

# 2. Build searchable index
rexlit index build /case-data

# 3. Search for responsive documents
rexlit index search "privileged communication" --limit 50 --json > responsive.json

# 4. Verify audit trail
rexlit audit verify

# 5. Export audit for production
rexlit audit show > audit-trail-$(date +%Y%m%d).jsonl
```

### Large Document Set Processing

```bash
# Index 100K+ documents with optimal settings
rexlit index build /large-dataset \
  --max-workers 8 \
  --batch-size 100 \
  --rebuild

# Monitor progress
watch -n 5 'rexlit index stats'
```

### Security Audit Workflow

```bash
# 1. Ingest potentially adversarial documents
rexlit ingest /untrusted-docs --manifest untrusted.jsonl

# 2. Check audit log for path traversal attempts
rexlit audit show --tail 50 | grep "PATH_TRAVERSAL"

# 3. Verify no tampering occurred
rexlit audit verify --verbose
```

### Metadata Analysis

```bash
# Extract custodians from index
rexlit index search "*" --show-metadata --json | \
  jq -r '.results[].custodian' | \
  sort | uniq -c | sort -rn

# Document type distribution
rexlit index search "*" --show-metadata --json | \
  jq -r '.results[].doctype' | \
  sort | uniq -c
```

---

## Configuration

### Environment Variables

- `REXLIT_DATA_DIR` - Override XDG data directory
- `REXLIT_AUDIT_FILE` - Override default audit file location
- `REXLIT_INDEX_DIR` - Override default index directory

### Config File

Future: `~/.config/rexlit/config.toml`

---

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Invalid arguments
- `3` - File not found
- `4` - Permission denied
- `5` - Audit verification failed

---

## Tips & Tricks

### Faster Indexing

```bash
# Use RAMdisk for temporary speed boost
rexlit index build /docs --index-dir /tmp/index
```

### Monitoring Long-Running Jobs

```bash
# Run in background with progress log
rexlit index build /large-dataset --max-workers 8 2>&1 | tee index.log &

# Follow progress
tail -f index.log
```

### Scripting Integration

```bash
#!/bin/bash
# Automated daily index update

DOCS="/litigation/active-cases"
INDEX="$HOME/.local/share/rexlit/index"

# Rebuild index
rexlit index build "$DOCS" --rebuild --no-progress

# Verify audit
if ! rexlit audit verify; then
  echo "ERROR: Audit verification failed"
  exit 1
fi

# Export stats
rexlit index stats --json > "stats-$(date +%Y%m%d).json"
```

---

## Getting Help

- **Command help**: `rexlit COMMAND --help`
- **Version info**: `rexlit --version`
- **Issues**: https://github.com/yourusername/rex/issues
- **Docs**: https://rexlit.readthedocs.io

---

**Last Updated**: 2025-10-23 (M0 Release)
