# RexLit

Offline-first UNIX litigation SDK/CLI for e-discovery and legal timeline management.

## Status

✅ **Phase 1 (M0) Complete** - Foundation with document ingest, indexing, and audit trail.
🚧 **Phase 2 (M1)** - E-discovery tools (OCR, deduplication, Bates stamping) coming next.

## Overview

RexLit is a comprehensive toolkit for litigation professionals, combining:
- **E-discovery toolkit**: ingest → OCR → dedupe → Bates stamp → produce → audit
- **TX/FL rules & timeline engine**: event → computed deadlines → citations → ICS export

## Philosophy

**Offline-by-default.** All networked features gated behind `--online`.

## Installation

Requires Python 3.11+:

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

### Ingest Documents

```bash
# Ingest documents and create manifest
rexlit ingest /path/to/documents --manifest documents.jsonl

# Ingest with recursive scanning
rexlit ingest /path/to/documents --recursive
```

### Build Search Index

```bash
# Build index from documents
rexlit index build /path/to/documents

# Rebuild index from scratch
rexlit index build /path/to/documents --rebuild
```

### Search Documents

```bash
# Search with JSON output
rexlit index search "contract" --json

# Limit results
rexlit index search "litigation" --limit 5
```

### Audit Trail

```bash
# Show audit ledger
rexlit audit show

# Show last 10 entries
rexlit audit show --tail 10

# Verify ledger integrity
rexlit audit verify
```

## Phase 1 Features

- ✅ Typer CLI with subcommand routing
- ✅ Pydantic settings with XDG base directory support
- ✅ Append-only JSONL audit ledger with SHA-256 hashing
- ✅ Document ingest for PDF, DOCX, TXT, images
- ✅ Tantivy-based full-text search index
- ✅ JSON output for programmatic consumption
- ✅ Pytest test suite with golden output harness

## Architecture

```
rexlit/
├── cli.py              # Typer entrypoint
├── config.py           # Pydantic settings
├── utils/              # hashing, paths
├── audit/              # Append-only ledger
├── ingest/             # Document discovery and extraction
├── index/              # Tantivy search
└── ...                 # Future phases
```

## Documentation

See `.cursor/plans/` for detailed implementation plans and GitHub issues for roadmap.

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=rexlit --cov-report=term-missing
```

## License

MIT
