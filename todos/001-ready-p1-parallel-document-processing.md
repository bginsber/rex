---
status: resolved
priority: p1
issue_id: "001"
tags: [performance, code-review, indexing, scalability]
dependencies: []
---

# Implement Parallel Document Processing for Index Build

## Problem Statement

Sequential single-threaded document processing makes indexing 15-20x slower than necessary. At the target scale of 100K documents, indexing would take 83+ hours instead of 4-6 hours with parallelization.

## Findings

- **Location:** rexlit/index/build.py:82-125
- **Discovery:** Comprehensive code review / Performance analysis
- **Current Performance:**
  - 100K documents @ 3-5 sec/doc = 83-139 hours total
  - CPU utilization: 10-20% (single core bottleneck)
  - Memory: O(n) - entire document list loaded at once

**Problem Scenario:**
1. User runs `rexlit index build /path/to/100k-documents`
2. Each document processed sequentially: discover → hash → extract → index
3. Average processing time: 3-5 seconds per document
4. Total time: 83-139 hours (3.5-5.8 days)
5. CPU utilization: only 10-20% (single core)
6. User waits days for indexing to complete

**Current Code Pattern:**
```python
for doc_meta in documents:
    extracted = extract_document(Path(doc_meta.path))  # BLOCKING I/O
    doc = tantivy.Document()
    # ... field additions ...
    writer.add_document(doc)  # One at a time
```

## Proposed Solutions

### Option 1: ProcessPoolExecutor with Batch Processing (Recommended)
- **Pros**:
  - 15-20x performance improvement with 8 cores
  - Reduces 83 hours → 4-6 hours at 100K scale
  - Better CPU utilization (80-90%)
  - Controlled memory usage through batching
- **Cons**:
  - Adds complexity with multiprocessing
  - Requires proper error handling across processes
  - Need to manage Tantivy writer commits
- **Effort**: Medium (2-3 days)
- **Risk**: Low - well-established pattern

**Implementation Approach:**
```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count

def process_document_batch(doc_metas: list[DocumentMetadata]) -> list[tantivy.Document]:
    """Process batch of documents in worker process."""
    results = []
    for doc_meta in doc_metas:
        extracted = extract_document(Path(doc_meta.path))
        doc = create_tantivy_doc(doc_meta, extracted)
        results.append(doc)
    return results

def build_index_parallel(root: Path, index_dir: Path, batch_size: int = 100):
    documents = discover_documents_streaming(root, recursive=True)
    batches = [documents[i:i+batch_size] for i in range(0, len(documents), batch_size)]

    writer = index.writer(heap_size=200_000_000)

    with ProcessPoolExecutor(max_workers=cpu_count() - 1) as executor:
        futures = {executor.submit(process_document_batch, batch): batch
                   for batch in batches}

        for future in as_completed(futures):
            docs = future.result()
            for doc in docs:
                writer.add_document(doc)

            # Periodic commits for memory management
            if indexed_count % 1000 == 0:
                writer.commit()
                writer = index.writer(heap_size=200_000_000)

    writer.commit()
```

### Option 2: ThreadPoolExecutor (Simpler but less gain)
- **Pros**:
  - Simpler than multiprocessing
  - Good for I/O-bound operations
  - 4-6x improvement expected
- **Cons**:
  - Limited by GIL for CPU-bound work
  - Smaller performance gains than ProcessPoolExecutor
- **Effort**: Small (1 day)
- **Risk**: Low

## Recommended Action

Implement **Option 1 (ProcessPoolExecutor with Batching)** for maximum performance gain. The additional complexity is justified by the 15-20x speedup at target scale.

## Technical Details

- **Affected Files**:
  - `rexlit/index/build.py` (main changes)
  - `rexlit/ingest/discover.py` (convert to streaming - see Issue #002)
- **Related Components**:
  - Document extraction pipeline
  - Tantivy index writer
  - Progress reporting
- **Database Changes**: No
- **Dependencies**: Requires Issue #002 (streaming discovery) for optimal memory usage

## Resources

- Performance analysis report from code review
- Python `concurrent.futures` documentation
- Tantivy Python bindings documentation

## Acceptance Criteria

- [ ] Index build uses ProcessPoolExecutor with configurable worker count
- [ ] Batch size is configurable (default 100 documents)
- [ ] Periodic commits every 1000 documents for memory management
- [ ] Progress reporting shows documents/sec throughput
- [ ] Error handling preserves partial progress on worker failures
- [ ] CPU utilization reaches 80-90% during indexing
- [ ] Performance test: 10K documents completes in < 15 minutes
- [ ] All existing tests pass
- [ ] New tests for parallel processing edge cases

## Work Log

### 2025-10-22 - Initial Discovery
**By:** Claude Code Review (PR #2)
**Actions:**
- Issue discovered during comprehensive code review
- Categorized as P1 CRITICAL performance bottleneck
- Estimated effort: Medium (2-3 days)
- Projected impact: 15-20x speedup at 100K scale

**Learnings:**
- Sequential processing is the primary bottleneck for scalability
- Python multiprocessing is well-suited for CPU + I/O bound document processing
- Tantivy writer can handle batched document additions efficiently

## Notes

**Source:** Code review of PR #2 - RexLit Phase 1 (M0) Foundation
**Priority Justification:** Without this fix, the tool is unusable at the stated target scale of 100K+ documents. This blocks production deployment.

**Performance Targets:**
- 1,000 documents: < 2 minutes
- 10,000 documents: < 15 minutes
- 100,000 documents: < 6 hours (with all optimizations)
