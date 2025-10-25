# ADR 0003: Determinism Policy

**Status:** Accepted

**Date:** 2025-10-24

**Decision Makers:** Engineering Team

---

## Context

Legal e-discovery requires reproducible workflows:
- Re-running the same pipeline must produce identical outputs
- Bates numbering must be stable and monotonic
- Artifact hashes must match across runs for legal verification
- Filesystem traversal order varies by OS and implementation

Non-deterministic processing creates risks:
- Different Bates numbers on re-run breaks chain of custody
- Hash mismatches fail verification checks
- Irreproducible bugs hard to debug
- Legal defensibility compromised

## Decision

**We enforce deterministic processing across all M1 workflows:**

### Core Principles

1. **Stable Ordering:** All file/record processing uses deterministic sort
2. **Content-Based Keys:** Sort by `(sha256_hash, path)` tuple
3. **Plan-Before-Execute:** Generate deterministic plans, then execute
4. **Input Hashing:** Plan IDs derived from sorted input hashes
5. **Validation:** Verify outputs match across multiple runs

### Implementation

```python
from rexlit.utils.deterministic import deterministic_sort_paths, compute_input_hash

# 1. Sort inputs deterministically
def ingest_documents(root: Path) -> Iterator[Document]:
    paths = discover_documents(root)
    sorted_paths = deterministic_sort_paths(paths)  # Sort by (hash, path)
    for path in sorted_paths:
        yield process(path)

# 2. Generate plan with deterministic ID
def create_redaction_plan(inputs: list[Path]) -> RedactionPlan:
    sorted_hashes = sorted([compute_hash(p) for p in inputs])
    plan_id = compute_input_hash(sorted_hashes)
    return RedactionPlan(plan_id=plan_id, ...)

# 3. Bates numbering uses plan
def apply_bates(docs: list[Document], start: int) -> list[BatesRecord]:
    # Documents already sorted, numbers assigned sequentially
    records = []
    current = start
    for doc in docs:
        records.append(BatesRecord(doc.id, current, current + doc.pages - 1))
        current += doc.pages
    return records
```

### Affected Operations

| Operation | Determinism Strategy |
|-----------|---------------------|
| Ingest | Sort paths by (hash, path) |
| OCR | Process documents in sorted order |
| Dedupe | Sort hashes before clustering |
| Redaction | Generate plan with sorted inputs |
| Bates | Assign numbers from sorted list |
| Pack | Assemble artifacts in sorted order |

## Consequences

### Positive

- **Reproducibility:** Identical outputs across runs
- **Verifiability:** Hashes match expected values
- **Debugging:** Reproducible bugs easier to fix
- **Legal Defense:** Chain of custody preserved
- **Confidence:** Automated testing can verify determinism

### Negative

- **Performance:** Sorting adds overhead (~1-2% for large sets)
- **Memory:** Must collect items before sorting (streaming broken)
- **Complexity:** Additional code for deterministic helpers

### Mitigation

- **Streaming Sorting:** Use external sort for very large sets
- **Caching:** Cache sorted lists when possible
- **Testing:** Verify determinism with `verify_determinism()` helper

## Validation

```bash
# Run pipeline twice
rexlit run m1 ./sample-docs
shasum -a 256 ./sample-docs/out/* > run1.txt

rexlit run m1 ./sample-docs --force
shasum -a 256 ./sample-docs/out/* > run2.txt

# Verify identical hashes
diff run1.txt run2.txt
# Expected: no differences
```

## Alternatives Considered

### 1. Best-Effort Ordering

**Rejected:** Insufficient for legal requirements. Must be 100% deterministic.

### 2. Timestamp-Based Ordering

**Rejected:** Timestamps vary across runs. Not reproducible.

### 3. Database Sequence Numbers

**Rejected:** Adds database dependency. Breaks offline-first principle.

## Edge Cases

### Concurrent Modifications

If source documents change between runs:
- Hashes will differ (expected behavior)
- Plan verification detects mismatches
- User must acknowledge changes or regenerate plan

### Filesystem Limits

For >1M files, in-memory sorting infeasible:
- Use external sort (GNU sort)
- Stream sorted chunks
- Merge with priority queue

## References

- Reproducible Builds (https://reproducible-builds.org/)
- NIST SP 800-53 (System Integrity)
- Related: ADR 0006 (Redaction Plan/Apply Model)

---

**Last Updated:** 2025-10-24
