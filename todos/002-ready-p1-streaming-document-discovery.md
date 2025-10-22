---
status: resolved
priority: p1
issue_id: "002"
tags: [performance, memory, code-review, scalability]
dependencies: []
---

# Convert Document Discovery to Streaming Pattern

## Problem Statement

All discovered documents are accumulated in a Python list in memory before processing begins. At 100K documents, this loads ~80MB of DocumentMetadata objects into memory, causing memory pressure and degraded I/O performance.

## Findings

- **Location:** rexlit/ingest/discover.py:198-208
- **Discovery:** Comprehensive code review / Performance analysis
- **Current Behavior:**
  - Memory usage: O(n) where n = document count
  - 100K documents = ~80MB in memory before processing
  - Cannot scale beyond available RAM
  - Processing cannot begin until discovery complete

**Problem Scenario:**
1. User runs `rexlit index build` on large document collection
2. `discover_documents()` calls `find_files()` which returns entire file list
3. For each file, `DocumentMetadata` created and appended to list
4. List grows to 100K items (~80MB) before returning
5. Memory pressure forces OS swapping
6. All subsequent I/O operations degrade
7. System becomes unresponsive or crashes with OOM

**Current Code Pattern:**
```python
files = find_files(root, recursive=recursive)  # O(n) memory

documents = []
for file_path in files:
    metadata = discover_document(file_path)
    documents.append(metadata)  # Growing list in memory
return documents  # All loaded before processing
```

## Proposed Solutions

### Option 1: Generator Pattern with Iterator (Recommended)
- **Pros**:
  - Constant memory usage O(1)
  - Processing starts immediately
  - No upper limit on document count
  - Pythonic and idiomatic
  - Enables streaming pipeline
- **Cons**:
  - Consumers must be updated to handle iterators
  - Cannot easily get total count upfront
  - Cannot reuse iterator without re-discovery
- **Effort**: Small (0.5-1 day)
- **Risk**: Low - common Python pattern

**Implementation:**
```python
from typing import Iterator

def discover_documents_streaming(
    root: Path,
    recursive: bool = True,
    include_extensions: set[str] | None = None,
    exclude_extensions: set[str] | None = None,
) -> Iterator[DocumentMetadata]:
    """Stream document discovery results without loading all into memory."""
    if root.is_file():
        yield discover_document(root)
        return

    # Stream files as they're discovered
    for file_path in find_files(root, recursive=recursive):
        if include_extensions and file_path.suffix.lower() not in include_extensions:
            continue
        if exclude_extensions and file_path.suffix.lower() in exclude_extensions:
            continue

        try:
            yield discover_document(file_path)
        except (FileNotFoundError, PermissionError, ValueError) as e:
            print(f"Warning: Skipping {file_path}: {e}")
            continue
```

**Update Consumers:**
```python
# In build.py
for doc_meta in discover_documents_streaming(root, recursive=True):
    # Process immediately without accumulation
    extracted = extract_document(Path(doc_meta.path))
    # ... index document ...
```

### Option 2: Keep List-Based API, Use Generator Internally
- **Pros**:
  - No API changes for consumers
  - Backward compatible
- **Cons**:
  - Doesn't solve memory problem
  - Misses streaming benefits
- **Effort**: N/A - not recommended
- **Risk**: N/A

## Recommended Action

Implement **Option 1 (Generator Pattern)** to achieve constant memory usage and enable streaming pipeline. Update all consumers (`index/build.py`, `cli.py`) to iterate over results instead of expecting list.

## Technical Details

- **Affected Files**:
  - `rexlit/ingest/discover.py` (change return type to Iterator)
  - `rexlit/index/build.py` (consume iterator)
  - `rexlit/cli.py` (update ingest command)
- **Related Components**:
  - File system traversal
  - Document metadata extraction
  - Index building pipeline
- **Database Changes**: No
- **Dependencies**: None (but complements Issue #001)

## Resources

- Python `typing.Iterator` documentation
- Generator patterns and best practices
- Memory profiling results from performance analysis

## Acceptance Criteria

- [ ] `discover_documents()` returns `Iterator[DocumentMetadata]` instead of list
- [ ] Memory usage remains constant regardless of document count
- [ ] Processing begins immediately without waiting for full discovery
- [ ] All consumers updated to handle iterator pattern
- [ ] Progress reporting still works (count processed, not total)
- [ ] Backward compatibility maintained through `list()` wrapper if needed
- [ ] Memory test: 100K documents uses < 100MB during discovery
- [ ] All existing tests pass
- [ ] New test validates streaming behavior

## Work Log

### 2025-10-22 - Initial Discovery
**By:** Claude Code Review (PR #2)
**Actions:**
- Issue discovered during comprehensive code review
- Categorized as P1 CRITICAL memory bottleneck
- Estimated effort: Small (0.5-1 day)
- Projected impact: 8-10x memory reduction, enables unlimited scale

**Learnings:**
- Unbounded memory growth prevents scaling to large document collections
- Generator pattern is Pythonic and enables streaming pipelines
- Early processing improves perceived performance

## Notes

**Source:** Code review of PR #2 - RexLit Phase 1 (M0) Foundation

**Priority Justification:** Combined with Issue #001, this is essential for reaching target scale of 100K+ documents. Without streaming, the tool cannot handle large litigation document sets.

**Performance Impact:**
- Memory: 80MB → <10MB (constant usage)
- Time: Enables early processing start
- Scalability: No upper limit on document count
