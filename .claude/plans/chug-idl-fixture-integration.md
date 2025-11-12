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

**Solution:** Use Chug to sample and curate documents from the **UCSF Industry Documents Library (IDL)** - a public repository of tobacco/vaping litigation materials - to create persistent, realistic fixture corpora for:
- Stress testing (100K+ document scale)
- Performance benchmarking (indexing, search, OCR, privilege classification)
- Edge case validation (malformed PDFs, complex metadata, privilege patterns)

This plan outlines the architecture, implementation phases, and integration with RexLit's existing hexagonal structure.

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

## 2. What is Chug? (Requirements & Assumptions)

### 2.1 Assumed Capabilities

Based on the task description, Chug is expected to:

1. **Sample IDL documents** - Extract subsets from UCSF Industry Documents Library
2. **Curate corpora** - Filter/organize documents by criteria (case, custodian, file type, date range)
3. **Generate fixtures** - Export sampled documents in formats compatible with RexLit ingestion
4. **Metadata preservation** - Maintain IDL metadata (Bates, custodian, case, OCR text)

### 2.2 Integration Requirements

Chug must:
- Support **deterministic sampling** (reproducible fixture generation)
- Export in **RexLit-compatible formats** (directory structure with documents + metadata)
- Provide **corpus manifests** (JSONL with document metadata)
- Enable **incremental curation** (add/remove documents without regenerating entire corpus)
- Support **offline operation** (no network dependencies during fixture use)

### 2.3 Open Questions (Needs Clarification)

1. **Chug implementation status:**
   - Is Chug already implemented, or is this plan also for building Chug?
   - If implemented, where is it located? (External tool, Python module, CLI?)

2. **IDL access method:**
   - Direct filesystem access to downloaded IDL archives?
   - API-based sampling from UCSF servers?
   - Pre-downloaded corpus that Chug filters?

3. **Output format:**
   - Directory tree with documents + manifest.jsonl?
   - SQLite database with embedded documents?
   - Tar/zip archive?

4. **Corpus versioning:**
   - How are fixture corpora versioned (git tags, semantic versioning)?
   - Are corpora immutable once generated, or can they be updated?

**Action:** Clarify these questions before proceeding to implementation.

---

## 3. Proposed Architecture

### 3.1 Directory Structure

```
rexlit/
├── docs/
│   ├── sample-docs/          # Existing submodule (small developer samples)
│   └── chug-fixtures/        # NEW: IDL fixture corpora (git submodule or local)
│       ├── small/            # 100 docs - Fast smoke tests
│       ├── medium/           # 1,000 docs - Integration tests
│       ├── large/            # 10,000 docs - Stress tests
│       ├── xl/               # 100,000 docs - Benchmark suite
│       └── edge-cases/       # Curated edge cases (malformed PDFs, etc.)
│
tests/
├── conftest.py               # EXTEND: Add chug_corpus() fixture
├── test_chug_integration.py  # NEW: Chug-specific tests
└── benchmark_chug.py         # NEW: Chug corpus benchmarks
│
scripts/
├── setup-chug-fixtures.sh    # NEW: Initialize Chug fixtures
├── chug-sample.py            # NEW: CLI wrapper for Chug sampling
└── chug-validate.py          # NEW: Validate Chug corpus integrity
│
.gitmodules                   # ADD: Chug fixtures submodule (optional)
```

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

### 3.4 Integration with Hexagonal Architecture

Chug integration follows RexLit's ports-and-adapters pattern:

```
CLI (rexlit/cli.py)
  ↓
Bootstrap (rexlit/bootstrap.py)
  ↓
Application Services (rexlit/app/*.py)
  ↓
Port Interfaces (rexlit/app/ports/*.py)
  ↑ implemented by
FixturePort (NEW) ← ChugFixtureAdapter (NEW)
  ↓ uses
Chug CLI/Library
```

**New Port:** `rexlit/app/ports/fixture.py`

```python
from typing import Protocol, Iterator, Path
from dataclasses import dataclass

@dataclass
class FixtureMetadata:
    doc_id: str
    bates: str
    custodian: str
    filepath: Path
    sha256: str
    privilege_claimed: bool
    # ... other IDL metadata

class FixturePort(Protocol):
    """Port for loading test/benchmark fixture corpora."""

    def list_corpora(self) -> list[str]:
        """List available fixture corpus names."""
        ...

    def load_corpus(self, name: str) -> Iterator[FixtureMetadata]:
        """Stream fixture metadata from named corpus."""
        ...

    def validate_corpus(self, name: str) -> bool:
        """Validate corpus integrity (checksums, file existence)."""
        ...
```

**Adapter:** `rexlit/app/adapters/chug_fixture.py`

```python
class ChugFixtureAdapter:
    """Adapter for loading Chug-generated IDL fixture corpora."""

    def __init__(self, fixture_root: Path):
        self.fixture_root = fixture_root

    def load_corpus(self, name: str) -> Iterator[FixtureMetadata]:
        manifest_path = self.fixture_root / name / "manifest.jsonl"
        with open(manifest_path) as f:
            for line in f:
                record = json.loads(line)
                yield FixtureMetadata(
                    doc_id=record["doc_id"],
                    bates=record["bates"],
                    custodian=record["custodian"],
                    filepath=self.fixture_root / name / record["filepath"],
                    sha256=record["sha256"],
                    privilege_claimed=record["privilege_claimed"],
                )
```

**Bootstrap wiring:** `rexlit/bootstrap.py`

```python
def create_fixture_adapter(settings: Settings) -> ChugFixtureAdapter:
    fixture_root = settings.fixture_root or Path("rexlit/docs/chug-fixtures")
    return ChugFixtureAdapter(fixture_root)
```

---

## 4. Pytest Integration

### 4.1 New Fixture in conftest.py

```python
# tests/conftest.py

import os
import pytest
from pathlib import Path
from typing import Generator

@pytest.fixture(scope="session")
def chug_fixture_root() -> Path:
    """
    Determine Chug fixture corpus root directory.

    Priority:
    1. CHUG_FIXTURE_PATH environment variable
    2. rexlit/docs/chug-fixtures/ (local or submodule)
    3. Skip if not available (for CI without fixtures)
    """
    env_path = os.getenv("CHUG_FIXTURE_PATH")
    if env_path:
        return Path(env_path)

    default_path = Path(__file__).parent.parent / "rexlit/docs/chug-fixtures"
    if default_path.exists():
        return default_path

    pytest.skip("Chug fixtures not available (set CHUG_FIXTURE_PATH or initialize submodule)")

@pytest.fixture(scope="session")
def chug_small(chug_fixture_root: Path) -> Path:
    """Small corpus (100 docs) for quick smoke tests."""
    corpus_path = chug_fixture_root / "small"
    if not corpus_path.exists():
        pytest.skip("Small corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def chug_medium(chug_fixture_root: Path) -> Path:
    """Medium corpus (1,000 docs) for integration tests."""
    corpus_path = chug_fixture_root / "medium"
    if not corpus_path.exists():
        pytest.skip("Medium corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def chug_large(chug_fixture_root: Path) -> Path:
    """Large corpus (10,000 docs) for stress tests."""
    corpus_path = chug_fixture_root / "large"
    if not corpus_path.exists():
        pytest.skip("Large corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def chug_xl(chug_fixture_root: Path) -> Path:
    """XL corpus (100,000 docs) for benchmarks."""
    corpus_path = chug_fixture_root / "xl"
    if not corpus_path.exists():
        pytest.skip("XL corpus not initialized")
    return corpus_path

@pytest.fixture(scope="session")
def chug_edge_cases(chug_fixture_root: Path) -> Path:
    """Edge case corpus (malformed PDFs, OCR challenges)."""
    corpus_path = chug_fixture_root / "edge-cases"
    if not corpus_path.exists():
        pytest.skip("Edge cases corpus not initialized")
    return corpus_path
```

### 4.2 Pytest Markers

**Add to pyproject.toml:**

```toml
[tool.pytest.ini_options]
markers = [
    "chug: Tests using Chug IDL fixture corpora",
    "chug_small: Tests using small corpus (100 docs)",
    "chug_medium: Tests using medium corpus (1,000 docs)",
    "chug_large: Tests using large corpus (10,000 docs)",
    "chug_xl: Tests using XL corpus (100,000 docs)",
    "chug_edge: Tests using edge case corpus",
    "slow: Slow-running tests (skip in fast CI)",
]
```

### 4.3 Example Test Using Chug Fixtures

```python
# tests/test_chug_integration.py

import pytest
from rexlit.app.bootstrap import create_container
from rexlit.ingest.discover import discover_documents
from rexlit.index.build import build_index

@pytest.mark.chug_small
def test_ingest_chug_small_corpus(chug_small, temp_dir):
    """Test ingestion of small Chug corpus."""
    manifest_path = temp_dir / "manifest.jsonl"

    # Discover documents from Chug corpus
    docs = list(discover_documents(chug_small))

    assert len(docs) >= 100, "Small corpus should have ~100 docs"

    # Verify all docs have required metadata
    for doc in docs:
        assert doc.sha256
        assert doc.path.exists()

@pytest.mark.chug_medium
@pytest.mark.slow
def test_index_build_determinism_chug_medium(chug_medium, temp_dir):
    """Verify deterministic indexing with medium Chug corpus."""
    index_dir_1 = temp_dir / "index1"
    index_dir_2 = temp_dir / "index2"

    # Build index twice
    build_index(chug_medium, index_dir_1, workers=4)
    build_index(chug_medium, index_dir_2, workers=4)

    # Indexes should be identical (deterministic sorting)
    # Compare index metadata, document order, etc.
    # ... assertions ...

@pytest.mark.chug_edge
def test_malformed_pdf_handling(chug_edge_cases):
    """Test graceful handling of malformed PDFs from edge case corpus."""
    # Load known-malformed document from edge case corpus
    # Verify error handling, logging, skip behavior
    # ... test logic ...
```

---

## 5. Benchmark Suite Enhancement

### 5.1 New Benchmark: benchmark_chug.py

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

## 7. Implementation Phases

### Phase 1: Infrastructure Setup (1-2 days)

**Goal:** Establish foundation for Chug integration

**Tasks:**
1. ✅ Document current test infrastructure (complete - agent analysis)
2. ✅ Design Chug fixture architecture (complete - this plan)
3. Create `FixturePort` interface in `rexlit/app/ports/fixture.py`
4. Implement `ChugFixtureAdapter` in `rexlit/app/adapters/chug_fixture.py`
5. Wire adapter in `rexlit/bootstrap.py`
6. Add configuration to `rexlit/config.py`
7. Update `pyproject.toml` with pytest markers

**Deliverable:** Port/adapter infrastructure ready for fixture loading

### Phase 2: Pytest Integration (1 day)

**Goal:** Enable Chug fixtures in test suite

**Tasks:**
1. Add fixture functions to `tests/conftest.py`
2. Create `tests/test_chug_integration.py` with example tests
3. Add pytest markers for corpus tiers
4. Write documentation for using Chug fixtures in tests
5. Update `CLAUDE.md` with Chug testing guidance

**Deliverable:** Tests can load and use Chug fixtures

### Phase 3: Chug Sampling Tool (3-5 days)

**Goal:** Build tool to sample/curate IDL documents into fixture corpora

**Tasks:**
1. **Clarify Chug requirements** (see §2.3 Open Questions)
2. Design Chug sampling CLI or Python module
3. Implement sampling logic:
   - Connect to IDL source (API, filesystem, etc.)
   - Filter by case, custodian, date range, file type
   - Deterministic sampling (reproducible with seed)
   - Export to manifest.jsonl + document directory
4. Implement corpus validation (checksums, metadata consistency)
5. Create setup script: `scripts/setup-chug-fixtures.sh`
6. Generate initial fixture corpora:
   - `small` (100 docs)
   - `medium` (1,000 docs)
   - `edge-cases` (~50 curated edge cases)

**Deliverable:** Functional Chug tool producing valid fixture corpora

### Phase 4: Benchmark Suite (2-3 days)

**Goal:** Establish performance baselines with Chug fixtures

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
