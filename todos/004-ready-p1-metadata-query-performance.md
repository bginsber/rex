---
status: resolved
priority: p1
issue_id: "004"
tags: [performance, code-review, search, indexing]
dependencies: []
---

# Fix O(n) Metadata Queries with Caching

## Problem Statement

`get_custodians()` and `get_doctypes()` functions scan the entire index with a hard-coded 10,000 result limit every time they're called. At 100K documents, these queries take 5-10 seconds each and return incomplete results. This blocks UI/CLI responsiveness.

## Findings

- **Location:** rexlit/index/search.py:172-239
- **Discovery:** Performance analysis during code review
- **Current Performance:**
  - Query time: 5-10 seconds at 100K documents
  - Result limit: Hard-coded 10,000 (incomplete data)
  - Complexity: O(n) - full index scan every call

**Problem Scenario:**
1. User runs `rexlit search --filter-by-custodian` to see available custodians
2. CLI calls `get_custodians()` to populate dropdown/list
3. Function executes `*` wildcard query matching ALL documents
4. Tantivy returns 10,000 results (limit hit)
5. Function iterates all results extracting custodian field
6. Takes 5-10 seconds, still missing custodians from remaining 90K docs
7. User experiences slow, unresponsive CLI
8. Incomplete metadata shown

**Current Code:**
```python
def get_custodians(index_dir: Path) -> set[str]:
    """Get all unique custodians in index."""
    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))
    searcher = index.searcher()

    # Search for ALL documents - O(n) operation!
    query_parser = tantivy.QueryParser.for_index(index, ["custodian"])
    parsed_query = query_parser.parse_query("*")  # Matches EVERYTHING
    search_results = searcher.search(parsed_query, 10000)  # Hard limit!

    custodians = set()
    for _, doc_address in search_results.hits:  # Iterate all results
        doc = searcher.doc(doc_address)
        doc_dict = index.schema.to_named_doc(doc)
        custodian = doc_dict.get("custodian", [""])[0]
        if custodian:
            custodians.add(custodian)

    return custodians  # Incomplete if >10K docs
```

**Same issue in `get_doctypes()`:** Lines 207-239

## Proposed Solutions

### Option 1: Metadata Cache Updated During Indexing (Recommended)
- **Pros**:
  - O(1) lookup instead of O(n) scan
  - 1000x+ performance improvement (5-10s → <10ms)
  - Complete metadata (no 10K limit)
  - Minimal memory overhead (< 1KB JSON)
- **Cons**:
  - Adds small overhead during index build
  - Cache file must be kept in sync with index
- **Effort**: Small (1 day)
- **Risk**: Low - simple JSON caching

**Implementation:**
```python
from pathlib import Path
import json

class IndexMetadata:
    """Cached metadata about index contents."""

    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.cache_file = index_dir / ".metadata_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            with open(self.cache_file) as f:
                return json.load(f)
        return {"custodians": [], "doctypes": [], "doc_count": 0}

    def update(self, custodian: str | None, doctype: str | None):
        """Update metadata incrementally during indexing."""
        if custodian and custodian not in self._cache["custodians"]:
            self._cache["custodians"].append(custodian)
        if doctype and doctype not in self._cache["doctypes"]:
            self._cache["doctypes"].append(doctype)
        self._cache["doc_count"] += 1

    def save(self):
        with open(self.cache_file, "w") as f:
            json.dump(self._cache, f)

    def get_custodians(self) -> set[str]:
        return set(self._cache["custodians"])

    def get_doctypes(self) -> set[str]:
        return set(self._cache["doctypes"])

# Update build.py to maintain cache
def build_index(root: Path, index_dir: Path, ...):
    metadata_cache = IndexMetadata(index_dir)

    for doc_meta in documents:
        # ... index document ...
        metadata_cache.update(doc_meta.custodian, doc_meta.doctype)

    metadata_cache.save()

# Update search.py to use cache
def get_custodians(index_dir: Path) -> set[str]:
    """Get all unique custodians (from cache)."""
    cache = IndexMetadata(index_dir)
    return cache.get_custodians()
```

### Option 2: Tantivy Faceting (If Supported)
- **Pros**:
  - Native Tantivy feature
  - Very efficient
- **Cons**:
  - May not be available in Python bindings
  - Requires schema changes
- **Effort**: Medium (research + implementation)
- **Risk**: Medium - dependent on library support

## Recommended Action

Implement **Option 1 (Metadata Cache)** for immediate 1000x performance gain with minimal complexity. If Tantivy faceting becomes available later, can migrate to that.

## Technical Details

- **Affected Files**:
  - `rexlit/index/search.py` (update get_custodians, get_doctypes)
  - `rexlit/index/build.py` (maintain cache during indexing)
  - Add new `rexlit/index/metadata.py` module
- **Related Components**:
  - Search index building
  - CLI filtering/faceting
  - Query interface
- **Database Changes**: No (just JSON cache file)
- **Dependencies**: None

## Resources

- Performance analysis report
- Tantivy documentation on faceting
- JSON cache patterns

## Acceptance Criteria

- [ ] `IndexMetadata` class created for cache management
- [ ] Cache updated incrementally during index build
- [ ] Cache persisted as `.metadata_cache.json` in index directory
- [ ] `get_custodians()` reads from cache (O(1) lookup)
- [ ] `get_doctypes()` reads from cache (O(1) lookup)
- [ ] Cache invalidated/rebuilt when index rebuilt
- [ ] Performance test: metadata queries < 10ms at 100K scale
- [ ] No 10K result limit - complete metadata returned
- [ ] Graceful fallback if cache missing (rebuild or warn)
- [ ] All existing tests pass
- [ ] New tests for cache consistency

## Work Log

### 2025-10-22 - Initial Discovery
**By:** Claude Performance Analysis (PR #2)
**Actions:**
- Issue discovered during performance review
- Categorized as P1 CRITICAL performance bottleneck
- Estimated effort: Small (1 day)
- Projected impact: 1000x speedup (5-10s → <10ms)

**Learnings:**
- Metadata queries are frequent in typical workflows
- Full index scans don't scale beyond 10K documents
- Simple caching provides massive performance gains
- Cache overhead during indexing is negligible

## Notes

**Source:** Performance analysis of PR #2 - RexLit Phase 1 (M0) Foundation

**Priority Justification:** CLI becomes unresponsive at target scale. User workflows that filter by custodian or doctype are blocked by 5-10 second delays. This severely impacts usability.

**Performance Impact:**
- Query time: 5-10 seconds → <10ms (1000x improvement)
- Completeness: 10K limit → unlimited (accurate metadata)
- Memory: Negligible (<1KB cache file)
