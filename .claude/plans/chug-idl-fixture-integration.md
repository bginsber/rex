# Chug IDL Fixture Integration Plan

**Date:** November 12, 2025
**Status:** Planning Phase
**Goal:** Integrate Chug tool for sampling/curating UCSF IDL documents to generate local fixture corpora for RexLit stress tests and benchmarks

---

## Executive Summary

RexLit currently uses programmatic, synthetic test fixtures (146 tests, 100% passing). While this approach provides fast, deterministic, isolated testing, it lacks:

1. **Scale realism** - Synthetic corpora don't reflect real-world document diversity (file formats, sizes, metadata complexity)
2. **Performance validation** - Benchmarks use generated data that may not expose real bottlenecks
3. **Edge case coverage** - Real litigation documents contain formatting quirks, OCR challenges, and metadata inconsistencies

**Solution:** Use **Chug** (Hugging Face's multimodal dataset loader) as a **dev-only fixture generation tool** to sample and curate documents from the **UCSF Industry Documents Library (IDL)** - a public repository of tobacco/vaping litigation materials stored as webdataset shards on Hugging Face.

### Key Architectural Decision

**Chug is a sidecar R&D tool, NOT a runtime integration:**

- ✅ **Strong fit:** One-time fixture generation - Sample IDL docs, write to filesystem, RexLit ingests normally
- ✅ **Strong fit:** ML model training - Train OCR/layout/privilege models on IDL via Chug, RexLit consumes outputs
- ❌ **Not a fit:** First-class ingestion backend - RexLit stays filesystem-native, doesn't couple to webdataset format

**Why this approach?**
- **Maturity mismatch:** Chug is alpha/unstable; RexLit is M1-complete and production-ready
- **Dependency weight:** Chug requires PyTorch, torchvision, transformers; RexLit is a lightweight CLI
- **Architectural fit:** RexLit is filesystem-driven and audit-focused; Chug is training-loop oriented
- **Offline-first principle:** Fixtures generated once offline, then used like any other evidence directory

This plan outlines the architecture for using Chug as a **fixture generation bridge** while keeping RexLit's core ingestion filesystem-based.

---

## 1. Background: Current Test Infrastructure

### 1.1 Existing Fixture Patterns

**Location:** `tests/conftest.py` (4 primary fixtures)

| Fixture | Type | Characteristics | Limitation |
|---------|------|-----------------|------------|
| `sample_text_file` | Single .txt file | 40 bytes, basic text | Not representative of PDFs/DOCX |
| `sample_files` | 3 files (txt, md) | Flat structure | No custodian hierarchy |
| `nested_files` | 2 custodians × 2-3 docs | Programmatic generation | All "PDFs" are actually .txt with .pdf extension |
| `override_settings` | Config isolation | Per-test temp dirs | No persistent corpus |

**Key insight:** All current fixtures are **ephemeral** (created/destroyed per test) and **synthetic** (plain text files with misleading extensions).

### 1.2 Benchmark Infrastructure

**Existing benchmarks:**
- `benchmark_metadata.py` (137 lines) - Tests O(1) metadata cache with 1,000 synthetic docs
- `scripts/benchmark_privilege.py` (169 lines) - Groq API latency for privilege classification

**Gaps:**
- No large-scale corpus (100K+ documents)
- No real document format diversity (PDF, DOCX, RTF, emails)
- No persistent baseline comparison (results not stored)
- No statistical regression detection

### 1.3 Git Submodule Pattern (rex-test-data)

**Current setup:**
```bash
.gitmodules:
[submodule "rexlit/docs/sample-docs"]
    path = rexlit/docs/sample-docs
    url = https://github.com/bginsber/rex-test-data.git
```

**Status:** Submodule infrastructure exists but **not initialized** in working directory.

**Template for Chug integration:** This pattern can be replicated for IDL fixture corpora.

---

## 2. What is Chug? (Actual Capabilities & Constraints)

### 2.1 Chug Overview

**Chug** is Hugging Face's minimal sharded dataset loader for multimodal document, image, and text datasets, explicitly designed as a **training/eval dataloader** for ML model development.

**Source:** `huggingface/chug` (GitHub, alpha status, API unstable)

**Key characteristics:**
- **Purpose:** PyTorch-style iterable dataloaders for training doc models (Donut, DocVQA, OCR, layout detection)
- **Format:** Reads webdataset `.tar` shards (not plain filesystems)
- **Scale:** Designed for massive datasets (6TB+ IDL corpus, millions of docs, tens of millions of pages)
- **Features:** On-the-fly PDF decoding/rendering via `pypdfium2`, document-oriented task pipelines
- **Dependencies:** PyTorch, torchvision, albumentations, HF transformers (heavy ML stack)
- **Maturity:** **Alpha, pre-announcement, API unstable** (marked explicitly in repo)

### 2.2 IDL on Hugging Face

**UCSF Industry Documents Library (IDL)** is available on HF as `pixparse/idl-wds`:
- **Format:** Webdataset `.tar` shards with JSON metadata + embedded PDF bytes/page text
- **Size:** 6TB+ for broader IDL stack (millions of documents)
- **Content:** Tobacco/vaping litigation documents (JUUL, Phillip Morris, etc.) with OCR text
- **Quality:** High-quality OCR dataset with ugly scans, fax artifacts, charts, typewriter text (stress-test material)
- **Alternative view:** Parquet-converted format also available

**Chug integration:** Chug's `DataTaskDocReadCfg` has IDL examples in README, designed specifically for this dataset.

### 2.3 Why Chug is NOT a First-Class RexLit Integration

**RexLit's architecture conflicts with Chug's design:**

| Dimension | RexLit | Chug |
|-----------|--------|------|
| **Purpose** | Offline-first litigation toolkit | Training loop dataloader |
| **Input format** | Filesystem directories of PDFs/DOCX/EML | Webdataset tar shards |
| **Processing model** | Deterministic, single-pass, audit-logged | Multi-epoch, shuffled, randomized |
| **Dependencies** | Lightweight (Tantivy, Tesseract, pypdf) | Heavy ML stack (PyTorch, transformers) |
| **Maturity** | M1-complete, production-ready | Alpha, API unstable |
| **Licensing** | Clear (Apache/MIT preferred) | Optional AGPL (PyMuPDF backend) |

**Making Chug a first-class ingestion backend would:**
- ❌ Complicate offline/audit story (webdataset streaming vs. deterministic file processing)
- ❌ Add heavy ML dependencies to a CLI tool
- ❌ Couple production code to alpha-quality, API-unstable library
- ❌ Require teaching RexLit to read webdataset shards instead of plain files

### 2.4 The Right Integration Pattern: Dev-Only Fixture Bridge

**Instead of coupling Chug to RexLit's core, use Chug as a dev-time fixture generator:**

```
Chug (dev-only)                RexLit (production)
      ↓                              ↓
  IDL webdataset          Filesystem directory
      ↓                              ↓
Sample/filter/render  →   Plain PDFs + manifest.jsonl
      ↓                              ↓
  One-time export         Normal ingest/index/ocr workflow
```

**This approach:**
- ✅ Keeps RexLit filesystem-native and lightweight
- ✅ Isolates alpha-quality Chug code in dev scripts only
- ✅ Enables one-time fixture generation with offline reuse
- ✅ Allows Chug to break without affecting RexLit production code
- ✅ Maintains audit trail and determinism in RexLit's core workflows

### 2.5 Dual Use Cases for Chug

**Use Case 1: Fixture Generation (this plan's focus)**
- Sample IDL docs via Chug
- Export to filesystem as plain PDFs + JSONL manifest
- RexLit ingests like any other evidence directory
- Use for stress tests, benchmarks, edge case validation

**Use Case 2: ML Model Training (separate, future work)**
- Train OCR models (Tesseract alternatives, PaddleOCR)
- Train layout detection models (privilege region identification)
- Train document classification models (privilege detection, responsiveness)
- Train multimodal doc readers (Donut-style)
- **RexLit consumes trained model outputs**, never the training loop itself

### 2.6 Dependency Management

Chug will be an **optional dev dependency**, not required for RexLit's core functionality:

**pyproject.toml:**
```toml
[project.optional-dependencies]
dev-idl = [
    "chug>=0.1.0",  # Hugging Face dataset loader
    "torch>=2.0",    # Required by Chug
    "datasets>=2.14", # HF datasets library
]
```

**Installation:**
```bash
# Standard RexLit (no Chug)
pip install rexlit

# With IDL fixture generation (dev only)
pip install 'rexlit[dev-idl]'
```

**CI/Runtime:** RexLit's core tests and CLI **never** import Chug; fixtures are pre-generated.

---

## 3. Proposed Architecture

### 3.1 Directory Structure

```
rexlit/
├── docs/
│   ├── sample-docs/              # Existing submodule (small developer samples)
│   └── idl-fixtures/             # NEW: IDL fixture corpora (generated once, committed or submodule)
│       ├── small/                # 100 docs - Fast smoke tests
│       │   ├── docs/             # Plain PDFs extracted from IDL
│       │   └── manifest.jsonl    # Metadata (Bates, custodian, case, etc.)
│       ├── medium/               # 1,000 docs - Integration tests
│       ├── large/                # 10,000 docs - Stress tests
│       ├── xl/                   # 100,000 docs - Benchmark suite (optional, external storage)
│       └── edge-cases/           # Curated edge cases (malformed PDFs, OCR challenges)
│           ├── ocr-failures/     # Scanned docs with poor OCR
│           ├── layout-complex/   # Charts, tables, multi-column
│           └── privilege-patterns/ # Known privileged/non-privileged examples
│
tests/
├── conftest.py                   # EXTEND: Add idl_corpus() fixture
├── test_idl_integration.py       # NEW: IDL corpus tests
└── benchmark_idl.py              # NEW: IDL corpus benchmarks
│
scripts/
├── dev/                          # DEV-ONLY scripts (require [dev-idl] extra)
│   ├── idl_to_rexlit_fixture.py  # NEW: Chug → filesystem bridge
│   ├── idl_train_ocr_model.py    # NEW: Train OCR models on IDL (future)
│   └── idl_train_privilege.py    # NEW: Train privilege models on IDL (future)
├── setup-idl-fixtures.sh         # NEW: Initialize IDL fixtures (download or generate)
└── validate-idl-fixtures.py      # NEW: Validate corpus integrity
│
.gitmodules                       # ADD: IDL fixtures submodule (optional)
```

**Key changes from original plan:**
- Renamed `chug-fixtures/` to `idl-fixtures/` (reflects source, not tool)
- Chug scripts isolated in `scripts/dev/` (requires optional `[dev-idl]` extra)
- Fixtures are **plain filesystem directories** that RexLit ingests normally
- No FixturePort/ChugFixtureAdapter in core RexLit (no runtime integration)

### 3.2 Corpus Tier Design

Each corpus tier has specific use cases:

| Tier | Doc Count | Size | Use Case | Test Marker |
|------|-----------|------|----------|-------------|
| **small** | 100 | ~50MB | CI smoke tests, quick iteration | `@pytest.mark.chug_small` |
| **medium** | 1,000 | ~500MB | Full integration tests | `@pytest.mark.chug_medium` |
| **large** | 10,000 | ~5GB | Stress tests, parallel processing | `@pytest.mark.chug_large` |
| **xl** | 100,000 | ~50GB | Benchmarking, performance baselines | `@pytest.mark.chug_xl` |
| **edge-cases** | ~50 | ~25MB | Malformed PDFs, OCR failures, edge cases | `@pytest.mark.chug_edge` |

**Curation criteria:**
- **File type diversity:** PDFs (70%), DOCX (15%), RTF (5%), emails (10%)
- **Custodian distribution:** 5-10 custodians per tier
- **Date range:** Span 5+ years to test temporal features
- **Privilege patterns:** Mix of privileged/non-privileged (10-20% privileged)
- **OCR complexity:** Native text PDFs + scanned images requiring OCR

### 3.3 Corpus Manifest Format

Each corpus includes a `manifest.jsonl` with IDL metadata:

```jsonl
{"doc_id": "JLI00489744", "bates": "JLI00489744", "custodian": "jerry.masoudi", "case": "NC-v-JUUL", "filepath": "docs/JLI00489744.pdf", "sha256": "a1b2c3...", "file_size": 245678, "page_count": 3, "datesent": "2019-04-14", "type": "email", "ocr_text_path": "ocr/JLI00489744.txt", "privilege_claimed": false, "idl_url": "https://industrydocuments.ucsf.edu/tobacco/docs/#id=JLI00489744"}
{"doc_id": "JLI00490012", "bates": "JLI00490012", "custodian": "sarah.chen", "case": "NC-v-JUUL", "filepath": "docs/JLI00490012.pdf", "sha256": "d4e5f6...", "file_size": 102400, "page_count": 2, "datesent": "2019-05-20", "type": "email", "ocr_text_path": "ocr/JLI00490012.txt", "privilege_claimed": true, "idl_url": "https://industrydocuments.ucsf.edu/tobacco/docs/#id=JLI00490012"}
```

**Key fields:**
- `doc_id` - IDL unique identifier
- `bates` - Bates number from original production
- `custodian` - Document custodian (for RexLit's custodian hierarchy)
- `case` - Source litigation (NC-v-JUUL, etc.)
- `filepath` - Relative path to document within corpus
- `sha256` - Document hash (for deterministic processing)
- `privilege_claimed` - Ground truth for privilege classification tests
- `idl_url` - Link back to original IDL document (for provenance)

### 3.4 NO Hexagonal Architecture Changes Required

**Critical design decision:** IDL fixtures are **not** integrated into RexLit's core architecture. No new ports, adapters, or bootstrap wiring.

**Why?**
- IDL fixtures are **plain filesystem directories** with PDFs + metadata
- RexLit's existing `discover_documents()` already handles them
- No need for specialized ingestion logic
- Keeps core RexLit lightweight and decoupled from IDL/Chug

**Data flow:**

```
Dev-time (one-time):
  Chug (scripts/dev/idl_to_rexlit_fixture.py)
    ↓
  IDL webdataset → Sample/filter → Export PDFs to rexlit/docs/idl-fixtures/small/docs/
    ↓
  Generate manifest.jsonl with metadata

Runtime (every test/benchmark):
  RexLit ingests idl-fixtures/ like any other directory
    ↓
  rexlit ingest run ./rexlit/docs/idl-fixtures/small
    ↓
  Normal discovery → extraction → indexing workflow
```

**No code changes to RexLit's core modules:**
- ❌ No new port interfaces
- ❌ No new adapters
- ❌ No bootstrap wiring
- ✅ Fixtures are transparent to RexLit (just another evidence directory)

**All Chug-specific logic stays in `scripts/dev/`** (optional `[dev-idl]` dependency)

---

## 4. Pytest Integration

### 4.1 New Fixture in conftest.py

**Simplified fixtures** - Just return paths to filesystem directories, no specialized loaders.

```python
# tests/conftest.py

import os
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def idl_fixture_root() -> Path:
    """
    Determine IDL fixture corpus root directory.

    Priority:
    1. IDL_FIXTURE_PATH environment variable
    2. rexlit/docs/idl-fixtures/ (local or submodule)
    3. Skip if not available (for CI without fixtures)
    """
    env_path = os.getenv("IDL_FIXTURE_PATH")
    if env_path:
        return Path(env_path)

    default_path = Path(__file__).parent.parent / "rexlit/docs/idl-fixtures"
    if default_path.exists():
        return default_path

    pytest.skip("IDL fixtures not available (set IDL_FIXTURE_PATH or run setup-idl-fixtures.sh)")

@pytest.fixture(scope="session")
def idl_small(idl_fixture_root: Path) -> Path:
    """Small IDL corpus (100 docs) for quick smoke tests."""
    corpus_path = idl_fixture_root / "small"
    if not corpus_path.exists():
        pytest.skip("Small IDL corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def idl_medium(idl_fixture_root: Path) -> Path:
    """Medium IDL corpus (1,000 docs) for integration tests."""
    corpus_path = idl_fixture_root / "medium"
    if not corpus_path.exists():
        pytest.skip("Medium IDL corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def idl_large(idl_fixture_root: Path) -> Path:
    """Large IDL corpus (10,000 docs) for stress tests."""
    corpus_path = idl_fixture_root / "large"
    if not corpus_path.exists():
        pytest.skip("Large IDL corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def idl_edge_cases(idl_fixture_root: Path) -> Path:
    """Edge case IDL corpus (malformed PDFs, OCR challenges)."""
    corpus_path = idl_fixture_root / "edge-cases"
    if not corpus_path.exists():
        pytest.skip("Edge cases corpus not initialized")
    return corpus_path
```

**Key simplifications:**
- Renamed `chug_*` to `idl_*` (reflects data source, not tool)
- Fixtures just return `Path` objects (no custom adapters)
- RexLit's existing `discover_documents()` handles these directories
- Tests remain agnostic to IDL/Chug specifics

### 4.2 Pytest Markers

**Add to pyproject.toml:**

```toml
[tool.pytest.ini_options]
markers = [
    "idl: Tests using IDL fixture corpora",
    "idl_small: Tests using small IDL corpus (100 docs)",
    "idl_medium: Tests using medium IDL corpus (1,000 docs)",
    "idl_large: Tests using large IDL corpus (10,000 docs)",
    "idl_edge: Tests using edge case IDL corpus",
    "slow: Slow-running tests (skip in fast CI)",
]
```

### 4.3 Example Test Using IDL Fixtures

```python
# tests/test_idl_integration.py

import pytest
from rexlit.app.bootstrap import create_container
from rexlit.ingest.discover import discover_documents
from rexlit.index.build import build_index

@pytest.mark.idl_small
def test_ingest_idl_small_corpus(idl_small, temp_dir):
    """Test ingestion of small IDL corpus."""
    # Discover documents from IDL corpus (RexLit treats it like any directory)
    docs = list(discover_documents(idl_small / "docs"))

    assert len(docs) >= 100, "Small corpus should have ~100 docs"

    # Verify all docs have required metadata
    for doc in docs:
        assert doc.sha256
        assert doc.path.exists()

@pytest.mark.idl_medium
@pytest.mark.slow
def test_index_build_determinism_idl_medium(idl_medium, temp_dir):
    """Verify deterministic indexing with medium IDL corpus."""
    index_dir_1 = temp_dir / "index1"
    index_dir_2 = temp_dir / "index2"

    # Build index twice
    build_index(idl_medium / "docs", index_dir_1, workers=4)
    build_index(idl_medium / "docs", index_dir_2, workers=4)

    # Indexes should be identical (deterministic sorting)
    # Compare index metadata, document order, etc.
    # ... assertions ...

@pytest.mark.idl_edge
def test_malformed_pdf_handling(idl_edge_cases):
    """Test graceful handling of malformed PDFs from edge case corpus."""
    # Load known-malformed document from edge case corpus
    # Verify error handling, logging, skip behavior
    # ... test logic ...
```

---

## 5. Chug Fixture Generation Script

### 5.1 The IDL-to-Filesystem Bridge: `idl_to_rexlit_fixture.py`

**Purpose:** One-time dev script to sample IDL documents via Chug and export to plain filesystem directories that RexLit can ingest.

**Location:** `scripts/dev/idl_to_rexlit_fixture.py` (requires `pip install 'rexlit[dev-idl]'`)

**Key responsibilities:**
1. Load IDL webdataset shards via Chug
2. Apply stratified sampling (file type, custodian, date range, privilege status)
3. Extract PDF bytes and write to filesystem
4. Generate manifest.jsonl with IDL metadata
5. Validate corpus integrity (checksums, file counts)

### 5.2 Implementation Sketch

```python
#!/usr/bin/env python3
"""
IDL to RexLit Fixture Generator

Samples documents from UCSF Industry Documents Library (IDL) via Chug
and exports to filesystem directories that RexLit can ingest normally.

Usage:
    python scripts/dev/idl_to_rexlit_fixture.py \\
        --tier small \\
        --count 100 \\
        --seed 42 \\
        --output rexlit/docs/idl-fixtures/small

    python scripts/dev/idl_to_rexlit_fixture.py \\
        --tier edge-cases \\
        --filter "privilege_claimed=true" \\
        --count 50 \\
        --output rexlit/docs/idl-fixtures/edge-cases/privilege-patterns

Requires: pip install 'rexlit[dev-idl]'
"""

import json
import hashlib
import argparse
from pathlib import Path
from typing import Iterator, Dict, Any

try:
    import chug
    from chug import DataCfg, DataTaskDocReadCfg
except ImportError:
    print("ERROR: Chug not installed. Run: pip install 'rexlit[dev-idl]'")
    exit(1)


def sample_idl_documents(
    count: int,
    seed: int = 42,
    filters: Dict[str, Any] | None = None,
) -> Iterator[Dict[str, Any]]:
    """
    Sample documents from IDL via Chug.

    Args:
        count: Number of documents to sample
        seed: Random seed for reproducibility
        filters: Optional filters (case, custodian, date_range, file_type, privilege_claimed)

    Yields:
        Document records with keys: pdf_bytes, metadata (Bates, custodian, case, etc.)
    """
    # Configure Chug to load IDL webdataset
    task_cfg = DataTaskDocReadCfg(
        page_sampling='all',  # Include all pages per document
    )

    data_cfg = DataCfg(
        source='pixparse/idl-wds',  # IDL on Hugging Face
        split='train',
        batch_size=None,  # Stream one at a time
        format='hfids',  # Hugging Face dataset format
        num_workers=0,  # Single-threaded for determinism
        seed=seed,
    )

    loader = chug.create_loader(data_cfg, task_cfg)

    sampled = 0
    for sample in loader:
        # Apply filters
        if filters:
            if 'case' in filters and sample['metadata'].get('case') != filters['case']:
                continue
            if 'custodian' in filters and sample['metadata'].get('custodian') not in filters['custodian']:
                continue
            if 'privilege_claimed' in filters and sample['metadata'].get('privilege_claimed') != filters['privilege_claimed']:
                continue
            # ... more filter logic ...

        yield {
            'pdf_bytes': sample['pdf_bytes'],
            'metadata': sample['metadata'],
        }

        sampled += 1
        if sampled >= count:
            break


def export_corpus(
    documents: Iterator[Dict[str, Any]],
    output_dir: Path,
) -> None:
    """
    Export sampled documents to filesystem directory.

    Structure:
        output_dir/
        ├── docs/
        │   ├── JLI00489744.pdf
        │   ├── JLI00490012.pdf
        │   └── ...
        └── manifest.jsonl
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = output_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    manifest_path = output_dir / "manifest.jsonl"
    manifest_records = []

    for doc in documents:
        metadata = doc['metadata']
        pdf_bytes = doc['pdf_bytes']

        # Write PDF to disk
        doc_id = metadata['doc_id']
        pdf_path = docs_dir / f"{doc_id}.pdf"
        pdf_path.write_bytes(pdf_bytes)

        # Compute SHA-256 hash
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()

        # Build manifest record
        manifest_record = {
            'doc_id': doc_id,
            'bates': metadata.get('bates', doc_id),
            'custodian': metadata.get('custodian', 'unknown'),
            'case': metadata.get('case', 'unknown'),
            'filepath': f"docs/{doc_id}.pdf",
            'sha256': sha256,
            'file_size': len(pdf_bytes),
            'page_count': metadata.get('page_count', 0),
            'datesent': metadata.get('datesent'),
            'type': metadata.get('type', 'document'),
            'privilege_claimed': metadata.get('privilege_claimed', False),
            'idl_url': f"https://industrydocuments.ucsf.edu/tobacco/docs/#id={doc_id}",
        }
        manifest_records.append(manifest_record)

    # Write manifest.jsonl
    with open(manifest_path, 'w') as f:
        for record in manifest_records:
            f.write(json.dumps(record) + '\\n')

    print(f"✓ Exported {len(manifest_records)} documents to {output_dir}")
    print(f"  - PDFs: {docs_dir}")
    print(f"  - Manifest: {manifest_path}")


def validate_corpus(corpus_dir: Path) -> bool:
    """Validate corpus integrity (checksums, file existence)."""
    manifest_path = corpus_dir / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"✗ Manifest not found: {manifest_path}")
        return False

    errors = []
    with open(manifest_path) as f:
        for line_num, line in enumerate(f, start=1):
            record = json.loads(line)
            doc_path = corpus_dir / record['filepath']

            if not doc_path.exists():
                errors.append(f"Line {line_num}: File not found: {doc_path}")
                continue

            # Verify checksum
            actual_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            if actual_hash != record['sha256']:
                errors.append(f"Line {line_num}: Checksum mismatch for {record['filepath']}")

    if errors:
        print(f"✗ Corpus validation failed ({len(errors)} errors):")
        for error in errors[:10]:  # Print first 10 errors
            print(f"  {error}")
        return False

    print(f"✓ Corpus validated successfully ({line_num} documents)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate IDL fixture corpus via Chug")
    parser.add_argument("--tier", required=True, help="Corpus tier name (small, medium, large, xl, edge-cases)")
    parser.add_argument("--count", type=int, required=True, help="Number of documents to sample")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--filter", action="append", help="Filters (key=value format)")
    parser.add_argument("--validate", action="store_true", help="Validate corpus after generation")

    args = parser.parse_args()

    # Parse filters
    filters = {}
    if args.filter:
        for f in args.filter:
            key, value = f.split('=', 1)
            filters[key] = value

    print(f"=== IDL Fixture Generation ({args.tier}) ===")
    print(f"  Count: {args.count}")
    print(f"  Seed: {args.seed}")
    print(f"  Output: {args.output}")
    print(f"  Filters: {filters or 'None'}")
    print()

    # Sample documents
    print("Sampling documents from IDL via Chug...")
    documents = sample_idl_documents(args.count, args.seed, filters)

    # Export to filesystem
    export_corpus(documents, args.output)

    # Validate
    if args.validate:
        print()
        validate_corpus(args.output)


if __name__ == "__main__":
    main()
```

### 5.3 Corpus Generation Workflow

**One-time generation per tier:**

```bash
# 1. Install dev dependencies
pip install 'rexlit[dev-idl]'

# 2. Generate small corpus (100 docs, for CI)
python scripts/dev/idl_to_rexlit_fixture.py \\
    --tier small \\
    --count 100 \\
    --seed 42 \\
    --output rexlit/docs/idl-fixtures/small \\
    --validate

# 3. Generate medium corpus (1K docs, for integration tests)
python scripts/dev/idl_to_rexlit_fixture.py \\
    --tier medium \\
    --count 1000 \\
    --seed 42 \\
    --output rexlit/docs/idl-fixtures/medium \\
    --validate

# 4. Generate edge case corpus (privileged documents only)
python scripts/dev/idl_to_rexlit_fixture.py \\
    --tier edge-cases \\
    --count 50 \\
    --filter "privilege_claimed=true" \\
    --output rexlit/docs/idl-fixtures/edge-cases/privilege-patterns \\
    --validate

# 5. Generate edge case corpus (OCR failures)
python scripts/dev/idl_to_rexlit_fixture.py \\
    --tier edge-cases \\
    --count 50 \\
    --filter "quality=poor_ocr" \\
    --output rexlit/docs/idl-fixtures/edge-cases/ocr-failures \\
    --validate
```

**After generation:**
- Fixtures are plain filesystem directories
- Commit to git (small/medium) or store separately (large/xl)
- RexLit ingests them like any other evidence directory
- Chug/IDL are no longer needed at runtime

### 5.4 Alternative: ML Model Training Workflows

**Future use case:** Train doc models on IDL via Chug, RexLit consumes trained model outputs.

**Example:** Train privilege classification model

```python
# scripts/dev/idl_train_privilege.py

import chug
from transformers import AutoModel, AutoTokenizer

# Load IDL via Chug with privilege labels
task_cfg = chug.DataTaskDocReadCfg(page_sampling='first')  # First page only
data_cfg = chug.DataCfg(source='pixparse/idl-wds', split='train')
loader = chug.create_loader(data_cfg, task_cfg)

# Train doc classifier (simplified)
model = AutoModel.from_pretrained("microsoft/layoutlmv3-base")
tokenizer = AutoTokenizer.from_pretrained("microsoft/layoutlmv3-base")

for sample in loader:
    # Extract features
    tokens = tokenizer(sample['text'], return_tensors='pt')

    # Train on privilege label
    label = sample['metadata']['privilege_claimed']
    # ... training loop ...

# Save trained model
model.save_pretrained("models/idl-privilege-classifier")

# RexLit can then use this model:
# rexlit privilege classify --model models/idl-privilege-classifier
```

**Key insight:** Chug is used for **training only**, not runtime. RexLit only depends on trained model weights, not Chug itself.

---

## 6. Benchmark Suite Enhancement

### 6.1 New Benchmark: benchmark_idl.py

```python
# scripts/benchmark_chug.py

"""
Benchmark RexLit performance against Chug IDL fixture corpora.

Usage:
    python scripts/benchmark_chug.py --corpus medium --workers 6
    python scripts/benchmark_chug.py --corpus xl --baseline results/baseline_2025-11-01.json
"""

import json
import time
import argparse
from pathlib import Path
from statistics import mean, median, stdev
from rexlit.ingest.discover import discover_documents
from rexlit.index.build import build_index
from rexlit.index.search import search_index

def benchmark_discovery(corpus_path: Path) -> dict:
    """Benchmark document discovery performance."""
    start = time.time()
    docs = list(discover_documents(corpus_path))
    elapsed = time.time() - start

    return {
        "operation": "discovery",
        "doc_count": len(docs),
        "elapsed_sec": elapsed,
        "throughput_docs_per_sec": len(docs) / elapsed,
    }

def benchmark_indexing(corpus_path: Path, index_dir: Path, workers: int) -> dict:
    """Benchmark parallel indexing performance."""
    start = time.time()
    build_index(corpus_path, index_dir, workers=workers)
    elapsed = time.time() - start

    doc_count = len(list(discover_documents(corpus_path)))

    return {
        "operation": "indexing",
        "doc_count": doc_count,
        "workers": workers,
        "elapsed_sec": elapsed,
        "throughput_docs_per_sec": doc_count / elapsed,
    }

def benchmark_search(index_dir: Path, queries: list[str]) -> dict:
    """Benchmark search query latency."""
    latencies = []

    for query in queries:
        start = time.time()
        results = search_index(index_dir, query)
        elapsed = time.time() - start
        latencies.append(elapsed * 1000)  # Convert to ms

    return {
        "operation": "search",
        "query_count": len(queries),
        "mean_latency_ms": mean(latencies),
        "median_latency_ms": median(latencies),
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
    }

def run_benchmark_suite(corpus_name: str, workers: int, baseline_path: Path | None):
    """Run full benchmark suite and compare to baseline."""
    corpus_path = Path(f"rexlit/docs/chug-fixtures/{corpus_name}")
    index_dir = Path(f"/tmp/rexlit-benchmark-{corpus_name}")

    print(f"Running benchmark suite on {corpus_name} corpus...")

    results = {
        "corpus": corpus_name,
        "timestamp": time.time(),
        "benchmarks": [],
    }

    # Discovery
    print("  [1/3] Benchmarking discovery...")
    results["benchmarks"].append(benchmark_discovery(corpus_path))

    # Indexing
    print(f"  [2/3] Benchmarking indexing (workers={workers})...")
    results["benchmarks"].append(benchmark_indexing(corpus_path, index_dir, workers))

    # Search
    print("  [3/3] Benchmarking search...")
    test_queries = ["privilege", "attorney", "contract", "email"]
    results["benchmarks"].append(benchmark_search(index_dir, test_queries))

    # Print summary
    print("\n=== Benchmark Results ===")
    for bench in results["benchmarks"]:
        print(f"\n{bench['operation'].upper()}:")
        for key, value in bench.items():
            if key != "operation":
                print(f"  {key}: {value}")

    # Compare to baseline if provided
    if baseline_path and baseline_path.exists():
        with open(baseline_path) as f:
            baseline = json.load(f)
        print("\n=== Comparison to Baseline ===")
        # ... comparison logic ...

    # Save results
    output_path = Path(f"benchmark-results-{corpus_name}-{int(time.time())}.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, choices=["small", "medium", "large", "xl"])
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--baseline", type=Path, help="Baseline results JSON for comparison")
    args = parser.parse_args()

    run_benchmark_suite(args.corpus, args.workers, args.baseline)
```

### 5.2 Benchmark Baselines

Store baseline results in `benchmarks/baselines/`:

```
benchmarks/
├── baselines/
│   ├── medium-2025-11-01.json
│   ├── large-2025-11-01.json
│   └── xl-2025-11-01.json
└── reports/
    └── regression-report-2025-11-12.md
```

**Baseline format:**

```json
{
  "corpus": "medium",
  "timestamp": 1730476800,
  "git_commit": "f463cc0",
  "benchmarks": [
    {
      "operation": "indexing",
      "doc_count": 1000,
      "workers": 6,
      "elapsed_sec": 42.3,
      "throughput_docs_per_sec": 23.6
    }
  ]
}
```

---

## 6. Configuration & Setup Workflow

### 6.1 Environment Variables

**Add to .env.example:**

```bash
# Chug IDL Fixture Configuration
CHUG_FIXTURE_PATH=/path/to/chug-fixtures  # Override default location
CHUG_CORPUS_TIER=medium                   # Default corpus for tests (small/medium/large/xl)
```

**Add to rexlit/config.py:**

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Chug fixture configuration
    chug_fixture_path: Path | None = None
    chug_corpus_tier: str = "small"  # Default tier for tests

    @property
    def fixture_root(self) -> Path:
        """Resolve Chug fixture root directory."""
        if self.chug_fixture_path:
            return self.chug_fixture_path
        return Path(__file__).parent.parent / "docs/chug-fixtures"
```

### 6.2 Setup Script: setup-chug-fixtures.sh

```bash
#!/usr/bin/env bash
# scripts/setup-chug-fixtures.sh
# Initialize Chug IDL fixture corpora

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FIXTURE_ROOT="$PROJECT_ROOT/rexlit/docs/chug-fixtures"

echo "=== RexLit Chug Fixture Setup ==="

# Option 1: Git submodule (if fixtures are in separate repo)
if [ -f "$PROJECT_ROOT/.gitmodules" ] && grep -q "chug-fixtures" "$PROJECT_ROOT/.gitmodules"; then
    echo "Initializing Chug fixtures submodule..."
    git submodule update --init --recursive rexlit/docs/chug-fixtures
    echo "✓ Submodule initialized"
fi

# Option 2: Download from release archive (if fixtures are distributed separately)
# if [ ! -d "$FIXTURE_ROOT" ]; then
#     echo "Downloading Chug fixtures..."
#     curl -L https://github.com/your-org/rex-chug-fixtures/releases/latest/download/fixtures.tar.gz | tar -xz -C "$PROJECT_ROOT/rexlit/docs/"
# fi

# Verify fixture integrity
echo ""
echo "Verifying fixture corpora..."
for tier in small medium large xl edge-cases; do
    manifest="$FIXTURE_ROOT/$tier/manifest.jsonl"
    if [ -f "$manifest" ]; then
        doc_count=$(wc -l < "$manifest")
        echo "  ✓ $tier: $doc_count documents"
    else
        echo "  ✗ $tier: not found (skip with CHUG_FIXTURE_PATH)"
    fi
done

echo ""
echo "=== Setup Complete ==="
echo "To use Chug fixtures in tests:"
echo "  pytest -m chug_small    # Run tests with small corpus"
echo "  pytest -m chug_medium   # Run tests with medium corpus"
echo ""
echo "To run benchmarks:"
echo "  python scripts/benchmark_chug.py --corpus medium --workers 6"
```

### 6.3 Git Submodule Configuration (Optional)

If Chug fixtures are stored in a separate repository:

```bash
# .gitmodules
[submodule "rexlit/docs/chug-fixtures"]
    path = rexlit/docs/chug-fixtures
    url = https://github.com/your-org/rex-chug-fixtures.git
```

**Advantages:**
- Separate versioning for fixtures vs. code
- Large binary files don't bloat main repo
- Multiple projects can share fixture repo

**Disadvantages:**
- Requires `git submodule update` step
- More complex for new developers

**Alternative:** Store fixtures in Git LFS if keeping in main repo.

---

## 7. Implementation Phases (REVISED)

### Phase 1: Dev Infrastructure & Dependencies (1 day)

**Goal:** Set up optional dev dependencies and directory structure

**Tasks:**
1. ✅ Document current test infrastructure (complete - agent analysis)
2. ✅ Design IDL fixture architecture (complete - this plan)
3. Add `[dev-idl]` optional dependency group to `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   dev-idl = ["chug>=0.1.0", "torch>=2.0", "datasets>=2.14"]
   ```
4. Create `scripts/dev/` directory for Chug-specific scripts
5. Update `pyproject.toml` with pytest markers (`idl`, `idl_small`, etc.)
6. Create `.gitignore` entries for IDL fixture directories (if not committing)

**Deliverable:** Infrastructure ready for dev-time fixture generation (NO core RexLit changes)

### Phase 2: Fixture Generation Script (2-3 days)

**Goal:** Build `idl_to_rexlit_fixture.py` to sample IDL docs via Chug

**Tasks:**
1. Implement `scripts/dev/idl_to_rexlit_fixture.py`:
   - Sample IDL webdataset via Chug (with seed for reproducibility)
   - Apply stratified sampling filters (case, custodian, privilege, etc.)
   - Extract PDF bytes and write to filesystem
   - Generate manifest.jsonl with IDL metadata
   - Validation logic (checksums, file existence)
2. Test script with small sample (10 docs) to verify Chug integration
3. Document script usage and CLI options
4. Create `scripts/validate-idl-fixtures.py` for corpus integrity checks

**Deliverable:** Working script that generates IDL fixture corpora

### Phase 3: Generate Initial Fixture Corpora (1-2 days)

**Goal:** Generate small/medium/edge-case corpora for testing

**Tasks:**
1. Run fixture generation for each tier:
   - `small` (100 docs, seed=42)
   - `medium` (1,000 docs, seed=42)
   - `edge-cases/privilege-patterns` (50 privileged docs)
   - `edge-cases/ocr-failures` (50 poor-OCR docs)
2. Validate all corpora with checksums
3. Document corpus composition (file types, cases, custodians)
4. Decide storage strategy:
   - Option A: Commit small/medium to git (if <500MB total)
   - Option B: Git submodule pointing to separate repo
   - Option C: Git LFS for large binary files
   - Option D: External storage (S3/network) with download script

**Deliverable:** Usable fixture corpora ready for tests

### Phase 4: Pytest Integration (1 day)

**Goal:** Enable IDL fixtures in RexLit test suite

**Tasks:**
1. Add fixture functions to `tests/conftest.py` (`idl_small`, `idl_medium`, etc.)
2. Create `tests/test_idl_integration.py` with 3-5 example tests
3. Verify tests pass with IDL fixtures
4. Create setup script: `scripts/setup-idl-fixtures.sh` (download or generate)
5. Update `CLAUDE.md` with IDL testing guidance

**Deliverable:** Tests can load and use IDL fixtures (RexLit treats them like any directory)

### Phase 5: Benchmark Suite (2-3 days)

**Goal:** Establish performance baselines with IDL fixtures

**Tasks:**
1. Implement `scripts/benchmark_chug.py`
2. Add benchmark operations:
   - Discovery throughput
   - Indexing throughput (parallel workers)
   - Search query latency
   - OCR processing time
   - Privilege classification accuracy
3. Run baseline benchmarks on `medium` and `large` corpora
4. Store baseline results in `benchmarks/baselines/`
5. Create regression detection logic (compare current vs. baseline)
6. Add statistical significance testing (t-test for latency comparisons)

**Deliverable:** Benchmark suite with baseline results

### Phase 5: Large-Scale Testing (2-3 days)

**Goal:** Validate RexLit at scale with realistic data

**Tasks:**
1. Generate `large` corpus (10,000 docs)
2. Generate `xl` corpus (100,000 docs)
3. Run stress tests:
   - Parallel indexing (6+ workers)
   - Memory usage profiling
   - Search performance under load
   - Audit trail integrity at scale
4. Identify and fix bottlenecks
5. Update performance documentation with findings

**Deliverable:** Validated performance at 100K+ document scale

### Phase 6: Documentation & Maintenance (1-2 days)

**Goal:** Comprehensive documentation for Chug integration

**Tasks:**
1. Write `docs/CHUG_INTEGRATION.md` guide
2. Update `CLAUDE.md` with Chug usage patterns
3. Add docstrings to all Chug-related code
4. Create runbook for regenerating fixtures
5. Document corpus versioning strategy
6. Add troubleshooting guide for common issues

**Deliverable:** Complete documentation for developers and CI

---

## 8. Quality Assurance Strategy

### 8.1 Fixture Validation

**Automated checks:**
- SHA-256 checksums match manifest
- All referenced files exist in corpus
- Manifest JSONL is valid (no parse errors)
- Required metadata fields present
- No duplicate doc_ids

**Script:** `scripts/chug-validate.py`

```python
def validate_corpus(corpus_path: Path) -> list[str]:
    """Validate Chug corpus integrity. Returns list of errors."""
    errors = []

    manifest_path = corpus_path / "manifest.jsonl"
    if not manifest_path.exists():
        return [f"Manifest not found: {manifest_path}"]

    with open(manifest_path) as f:
        for line_num, line in enumerate(f, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                continue

            # Check required fields
            required = ["doc_id", "bates", "filepath", "sha256"]
            missing = [f for f in required if f not in record]
            if missing:
                errors.append(f"Line {line_num}: Missing fields: {missing}")

            # Check file exists
            doc_path = corpus_path / record["filepath"]
            if not doc_path.exists():
                errors.append(f"Line {line_num}: File not found: {doc_path}")

            # Verify checksum
            actual_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            if actual_hash != record["sha256"]:
                errors.append(f"Line {line_num}: Checksum mismatch for {record['filepath']}")

    return errors
```

### 8.2 Test Coverage Goals

**Target coverage for Chug-related code:**
- FixturePort interface: 100%
- ChugFixtureAdapter: 100%
- Corpus validation: 100%
- Fixture loading in tests: 90%+

**New test files:**
- `tests/test_fixture_port.py` - Port interface tests
- `tests/test_chug_adapter.py` - Adapter implementation tests
- `tests/test_chug_integration.py` - End-to-end integration tests
- `tests/test_chug_validation.py` - Corpus validation tests

### 8.3 CI/CD Integration

**GitHub Actions workflow:**

```yaml
# .github/workflows/chug-tests.yml
name: Chug Fixture Tests

on: [push, pull_request]

jobs:
  test-small-corpus:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive  # Initialize chug-fixtures submodule

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e '.[dev]'

      - name: Validate Chug fixtures
        run: python scripts/chug-validate.py --corpus small

      - name: Run Chug small corpus tests
        run: pytest -m chug_small -v

  benchmark-medium-corpus:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Run benchmark suite
        run: |
          python scripts/benchmark_chug.py --corpus medium --workers 6

      - name: Compare to baseline
        run: |
          python scripts/benchmark_chug.py --corpus medium --baseline benchmarks/baselines/medium-latest.json

      - name: Upload benchmark results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark-results-*.json
```

---

## 9. Success Criteria

This integration is successful when:

1. **Infrastructure:**
   - ✅ FixturePort and ChugFixtureAdapter implemented
   - ✅ Pytest fixtures for all corpus tiers (small, medium, large, xl, edge-cases)
   - ✅ Configuration supports `CHUG_FIXTURE_PATH` environment variable

2. **Tooling:**
   - ✅ Chug sampling tool can generate deterministic corpora from IDL
   - ✅ Validation script detects corrupted/invalid fixtures
   - ✅ Setup script initializes fixtures with one command

3. **Testing:**
   - ✅ At least 10 tests use Chug fixtures
   - ✅ Tests marked with appropriate `@pytest.mark.chug_*` decorators
   - ✅ CI runs `chug_small` tests on every PR
   - ✅ All 146+ existing tests still pass (no regression)

4. **Benchmarking:**
   - ✅ Baseline results established for medium and large corpora
   - ✅ Benchmark suite runs automatically on main branch merges
   - ✅ Regression detection alerts when performance degrades >10%

5. **Performance:**
   - ✅ RexLit can index 10,000 docs in <30 minutes (parallel)
   - ✅ RexLit can index 100,000 docs in <6 hours (parallel)
   - ✅ Search latency <100ms on 100K doc index
   - ✅ Memory usage <4GB during indexing

6. **Documentation:**
   - ✅ `docs/CHUG_INTEGRATION.md` guide written
   - ✅ `CLAUDE.md` updated with Chug usage patterns
   - ✅ All Chug-related code has comprehensive docstrings

---

## 10. Risks & Mitigation

### Risk 1: Chug Tool Doesn't Exist Yet

**Risk:** This plan assumes Chug is an existing tool, but it may need to be built from scratch.

**Mitigation:**
- Clarify Chug implementation status with user **before** Phase 3
- If Chug needs to be built, add 1-2 week development phase
- Consider simpler alternatives (manual curation, wget scripts) for initial prototyping

### Risk 2: IDL Access Restrictions

**Risk:** UCSF IDL may have rate limits, authentication requirements, or download restrictions.

**Mitigation:**
- Research IDL API terms of service
- If API is restricted, download corpora manually in bulk
- Cache downloaded documents to avoid repeated API calls

### Risk 3: Large Corpus Storage Costs

**Risk:** 100K document corpus (~50GB) may be too large for Git, CI caching, or developer machines.

**Mitigation:**
- Use Git LFS for large binary files
- Store XL corpus separately (S3, network share) with opt-in download
- Only require `small` corpus for CI (skip medium/large/xl unless explicitly requested)

### Risk 4: Fixture Corpus Staleness

**Risk:** IDL documents may be updated, removed, or new documents added, invalidating fixtures.

**Mitigation:**
- Version corpora with semantic versioning (v1.0.0, v1.1.0)
- Pin corpus version in tests (fixture manifest includes version metadata)
- Document corpus regeneration procedure (when to refresh fixtures)

### Risk 5: Determinism Challenges

**Risk:** Chug sampling may not be deterministic, causing fixture corpora to differ across regenerations.

**Mitigation:**
- Enforce deterministic sampling in Chug (use fixed random seed)
- Store sampling parameters in corpus metadata (seed, filter criteria)
- Validate corpus checksums match expected values

---

## 11. Next Steps

### Immediate Actions

1. **Clarify Chug requirements** (see §2.3 Open Questions):
   - What is Chug's current implementation status?
   - How do we access IDL documents?
   - What output format should Chug produce?

2. **Review this plan** with stakeholders:
   - Is the proposed architecture appropriate?
   - Are corpus tiers (small/medium/large/xl) the right granularity?
   - Should fixtures be a git submodule or stored in main repo?

3. **Prioritize phases:**
   - Can we skip Phase 3 (Chug tool) if it already exists?
   - Should we start with Phase 1+2 (infrastructure + pytest) before building Chug?

### Decision Points

**Decision 1: Fixture Storage Strategy**
- Option A: Git submodule (separate repo, like rex-test-data)
- Option B: Git LFS in main repo
- Option C: External storage (S3, network share) with download script
- **Recommendation:** Option A (submodule) for consistency with existing pattern

**Decision 2: Chug Implementation Approach**
- Option A: Standalone Python CLI tool (`scripts/chug.py`)
- Option B: RexLit CLI extension (`rexlit chug sample ...`)
- Option C: External tool (separate repo/package)
- **Recommendation:** Option A (standalone script) for simplicity

**Decision 3: Corpus Versioning**
- Option A: Git tags on submodule (v1.0.0, v1.1.0)
- Option B: Directory naming (chug-fixtures-v1/, chug-fixtures-v2/)
- Option C: Metadata field in manifest.jsonl
- **Recommendation:** Option A (git tags) for semantic versioning

---

## 12. Appendix: Example Chug CLI Usage

**(Conceptual - actual implementation TBD)**

```bash
# Sample documents from IDL into small corpus
rexlit chug sample \
    --source idl \
    --case "NC-v-JUUL" \
    --count 100 \
    --output rexlit/docs/chug-fixtures/small \
    --seed 42 \
    --format manifest-jsonl

# Sample with filters
rexlit chug sample \
    --source idl \
    --case "NC-v-JUUL" \
    --custodian "jerry.masoudi,sarah.chen" \
    --date-range 2018-01-01:2020-12-31 \
    --file-type pdf,docx \
    --privilege-claimed true \
    --count 50 \
    --output rexlit/docs/chug-fixtures/edge-cases/privilege \
    --seed 1337

# Validate corpus
rexlit chug validate \
    --corpus rexlit/docs/chug-fixtures/small \
    --checksum \
    --metadata

# Update corpus (add more documents)
rexlit chug update \
    --corpus rexlit/docs/chug-fixtures/medium \
    --add 100 \
    --seed 99

# Export corpus metadata
rexlit chug export \
    --corpus rexlit/docs/chug-fixtures/medium \
    --format csv \
    --output corpus-metadata.csv
```

---

## Summary

This plan provides a comprehensive roadmap for integrating Chug-generated IDL fixture corpora into RexLit's test and benchmark infrastructure. Key highlights:

1. **Tiered corpora** (small/medium/large/xl/edge-cases) for different testing needs
2. **Hexagonal architecture compliance** (FixturePort + ChugFixtureAdapter)
3. **Pytest integration** with fixtures and markers for easy test authoring
4. **Benchmark suite** with baseline tracking and regression detection
5. **Phased implementation** (6 phases, ~10-15 days total)
6. **Quality assurance** (validation scripts, CI integration, test coverage)

**Next step:** Review open questions (§2.3) and obtain clarifications before proceeding to Phase 1 implementation.

---

**Plan Author:** Claude (AI Assistant)
**Plan Date:** November 12, 2025
**Approval Status:** Pending User Review
