# ADR 0005: Bates Numbering Authority

**Status:** Accepted

**Date:** 2025-10-24

**Decision Makers:** Engineering Team

---

## Context

Bates numbering is a legal requirement for e-discovery:
- Each page receives a unique, sequential identifier
- Numbers must be monotonically increasing
- Once assigned, numbers cannot be reused
- Collisions or duplicates invalidate production
- Gaps in sequence must be explained

Challenges:
- Multiple production runs may overlap
- Re-running pipeline shouldn't reassign numbers
- Parallel processing needs coordination
- Audit trail must show all allocations

## Decision

**We implement append-only Bates registry with preflight collision detection:**

### Architecture

```
┌──────────────────────────────────────────────┐
│         bates_map.jsonl (Registry)           │
│  Append-only, monotonically increasing       │
├──────────────────────────────────────────────┤
│ {"doc": "contract.pdf", "start": "REX001"}   │
│ {"doc": "invoice.pdf", "start": "REX005"}    │
│ {"doc": "email.pdf", "start": "REX012"}      │
└──────────────────────────────────────────────┘
                     ↑
                     │
        ┌────────────┴────────────┐
        │                         │
   ┌────▼─────┐            ┌─────▼────┐
   │  Plan    │            │  Apply   │
   │  Phase   │            │  Phase   │
   │          │            │          │
   │ Calculate│            │ Stamp    │
   │ ranges   │            │ PDFs     │
   └──────────┘            └──────────┘
```

### Workflow

1. **Plan Phase:** Calculate allocations without writing
   ```python
   plan = create_bates_plan(docs, start=1, prefix="REX")
   # Returns: [("doc1.pdf", "REX001", "REX010"), ...]
   ```

2. **Preflight Check:** Detect collisions
   ```python
   conflicts = check_bates_conflicts(plan, registry)
   if conflicts and not force:
       raise ValueError(f"Collision detected: {conflicts}")
   ```

3. **Apply Phase:** Stamp PDFs and update registry
   ```python
   for doc, start, end in plan:
       stamp_pdf(doc, start, end, config)
       registry.append({"doc": doc, "start": start, "end": end})
   ```

### Registry Format

```json
{
  "schema_id": "bates_map",
  "schema_version": 1,
  "document_id": "contract.pdf",
  "bates_start": "REX001",
  "bates_end": "REX010",
  "page_count": 10,
  "prefix": "REX",
  "assigned_at": "2025-10-24T12:00:00Z"
}
```

### Safety Rails

1. **Monotonicity Check:**
   ```python
   def verify_monotonic(registry: list[BatesRecord]) -> bool:
       """Verify numbers increase without gaps."""
       for i in range(1, len(registry)):
           assert parse_num(registry[i].start) > parse_num(registry[i-1].end)
   ```

2. **Collision Detection:**
   ```python
   def check_conflicts(plan: BatesPlan, registry: Registry) -> list[str]:
       """Find overlapping ranges."""
       existing_ranges = {(r.start, r.end) for r in registry}
       conflicts = []
       for doc, start, end in plan:
           if overlaps(start, end, existing_ranges):
               conflicts.append(doc)
       return conflicts
   ```

3. **Force Flag Warning:**
   ```python
   if force and conflicts:
       logger.warning(f"FORCE: Overriding {len(conflicts)} conflicts")
       audit.log("bates_force_override", conflicts)
   ```

## Consequences

### Positive

- **Safety:** Preflight prevents collisions
- **Auditability:** Registry shows all allocations
- **Determinism:** Plan phase deterministic, apply idempotent
- **Recovery:** Can verify and fix issues before stamping
- **Transparency:** Clear log of all number assignments

### Negative

- **Two-Phase:** Adds complexity vs. direct stamping
- **State Management:** Registry must be kept in sync
- **Collision Handling:** User must resolve conflicts manually

### Mitigation

- **Automation:** CLI handles plan → preflight → apply workflow
- **Validation:** Tests verify monotonicity and collision detection
- **Documentation:** Clear examples of resolving conflicts

## Usage Examples

### Normal Flow

```bash
# 1. Generate plan
rexlit bates plan ./docs --start 1 --prefix REX > plan.jsonl

# 2. Preflight check (automatic)
rexlit bates apply --plan plan.jsonl ./docs/out
# Success: No collisions detected

# 3. PDFs stamped, registry updated
```

### Collision Detected

```bash
# Preflight detects collision
rexlit bates apply --plan plan.jsonl ./docs/out
# Error: Collision detected for contract.pdf (REX001-REX010)
# Existing allocation: REX005-REX015 for invoice.pdf
# Aborting. Use --force to override (not recommended).

# Options:
# A. Renumber plan with higher start number
# B. Use --force (logs warning, may invalidate production)
```

### Registry Verification

```bash
# Verify monotonicity
python -c "from rexlit.bates import verify_registry; \
    assert verify_registry('bates_map.jsonl')"
```

## Alternatives Considered

### 1. Database Sequence

**Rejected:** Adds database dependency, breaks offline-first. Registry = simple append-only file.

### 2. Atomic File Locking

**Rejected:** Doesn't prevent logical collisions (overlapping ranges). Need explicit preflight.

### 3. No Preflight (YOLO)

**Rejected:** Too risky. Collisions invalidate productions, legal consequences.

## Edge Cases

### Concurrent Processes

- **Problem:** Two processes stamping simultaneously
- **Solution:** File locking on registry write, or use unique prefixes

### Production Supplements

- **Problem:** Adding documents to existing production
- **Solution:** Start numbering after last registry entry

### Number Gaps

- **Problem:** Skipped numbers due to errors
- **Solution:** Audit log explains gaps, can be justified to opposing counsel

## References

- Federal e-discovery best practices
- FRCP Rule 26 (production format)
- Related: ADR 0003 (Determinism Policy)

---

**Last Updated:** 2025-10-24
