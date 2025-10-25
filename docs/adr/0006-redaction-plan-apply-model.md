# ADR 0006: Redaction Plan/Apply Model

**Status:** Accepted

**Date:** 2025-10-24

**Decision Makers:** Engineering Team

---

## Context

Redaction is a sensitive, high-stakes operation:
- Once applied, text is permanently obscured (irreversible)
- Mistakes can expose privileged information
- Over-redaction wastes attorney review time
- Must be defensible and reproducible

Risks of direct application:
- No preview before permanent changes
- Hard to verify coordinates are correct
- Can't compare before/after easily
- Accidental re-redaction of modified PDFs

## Decision

**We adopt a two-phase plan/apply model with hash verification:**

### Workflow

```
┌─────────────────────────────────────────────────┐
│  Phase 1: PLAN (Read-Only, Deterministic)      │
├─────────────────────────────────────────────────┤
│ 1. Scan PDFs for PII                           │
│ 2. Generate redaction coordinates               │
│ 3. Compute plan_id = sha256(input hashes)      │
│ 4. Write plan.jsonl (no PDFs modified)         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  Phase 2: APPLY (Write, with Verification)     │
├─────────────────────────────────────────────────┤
│ 1. Read plan.jsonl                              │
│ 2. Verify current PDF hash = plan.input_hash   │
│ 3. If mismatch: ABORT (unless --force)         │
│ 4. Apply redactions to PDFs                    │
│ 5. Log to audit trail                          │
└─────────────────────────────────────────────────┘
```

### Plan Format

```json
{
  "schema_id": "redaction_plan",
  "schema_version": 1,
  "plan_id": "abc123...",
  "input_hash": "def456...",
  "documents": [
    {
      "path": "contract.pdf",
      "sha256": "789abc...",
      "redactions": [
        {
          "page": 1,
          "entity_type": "SSN",
          "coordinates": {"x": 100, "y": 200, "width": 150, "height": 20},
          "rationale": "Detected SSN: XXX-XX-1234"
        }
      ]
    }
  ],
  "pii_types": ["SSN", "EMAIL", "CREDIT_CARD"],
  "created_at": "2025-10-24T12:00:00Z"
}
```

### Safety Checks

1. **Hash Verification:**
   ```python
   def verify_plan_matches_pdf(plan: RedactionPlan, pdf_path: Path) -> bool:
       """Verify PDF hasn't changed since plan creation."""
       current_hash = compute_hash(pdf_path)
       plan_hash = plan.documents[pdf_path]["sha256"]
       return current_hash == plan_hash
   ```

2. **Preview Mode:**
   ```python
   def preview_redactions(plan: RedactionPlan, output: Path) -> None:
       """Generate side-by-side comparison without applying."""
       for doc in plan.documents:
           create_preview_pdf(doc, output / f"{doc.name}_preview.pdf")
   ```

3. **Force Override:**
   ```python
   if not verify_plan_matches_pdf(plan, pdf) and not force:
       raise ValueError(
           f"PDF has changed since plan creation.\n"
           f"Expected hash: {plan.documents[pdf]['sha256']}\n"
           f"Current hash: {compute_hash(pdf)}\n"
           f"Regenerate plan or use --force (not recommended)."
       )
   ```

## Consequences

### Positive

- **Safety:** Preview before permanent changes
- **Verifiability:** Hash check prevents wrong PDF redaction
- **Reproducibility:** Same plan = same redactions
- **Auditability:** Plan shows exactly what was redacted and why
- **Review:** Attorney can review plan before applying

### Negative

- **Two-Phase:** Adds step vs. direct application
- **Storage:** Plan files add disk usage
- **Workflow:** Users must remember to apply after planning

### Mitigation

- **Automation:** `rexlit redaction run` does plan → review → apply in one command
- **Preview:** Built-in preview mode for visual confirmation
- **Documentation:** Clear examples and warnings

## Usage Examples

### Basic Workflow

```bash
# 1. Generate redaction plan
rexlit redaction plan ./docs --pii SSN,EMAIL --output plan.jsonl
# Scanned 50 documents, found 12 PII instances
# Plan saved to: plan.jsonl

# 2. Review plan (manual or automated)
cat plan.jsonl | jq '.documents[].redactions'

# 3. Preview (optional)
rexlit redaction apply --plan plan.jsonl --preview ./preview/
# Generated preview PDFs in ./preview/

# 4. Apply redactions
rexlit redaction apply --plan plan.jsonl ./docs/redacted/
# Applied 12 redactions to 8 documents
# Output: ./docs/redacted/
```

### Hash Mismatch Detected

```bash
# Someone edited contract.pdf after plan creation
rexlit redaction apply --plan plan.jsonl ./docs/redacted/
# Error: Hash mismatch for contract.pdf
# Expected: abc123... (from plan)
# Current:  def456...
# PDF has been modified since plan creation.
# Regenerate plan or use --force.

# Options:
# A. Regenerate plan (recommended)
rexlit redaction plan ./docs --output plan-v2.jsonl

# B. Force apply (dangerous, logs warning)
rexlit redaction apply --plan plan.jsonl --force ./docs/redacted/
# WARNING: Forcing redaction despite hash mismatch
# Logged to audit trail: redaction_force_override
```

### Preview Mode

```bash
# Generate side-by-side comparison
rexlit redaction apply --plan plan.jsonl --preview ./preview/
# Created preview PDFs showing:
# - Original text (highlighted)
# - Redacted version

# Open in PDF viewer for manual review
open ./preview/contract_preview.pdf
```

## Alternatives Considered

### 1. Direct Application (No Plan)

**Rejected:** Too risky. No preview, no verification, irreversible mistakes.

### 2. Undo/Rollback

**Rejected:** Redaction is cryptographically secure deletion. Cannot undo.

### 3. Database-Tracked Plans

**Rejected:** Adds complexity. JSONL plans are portable and human-readable.

## Edge Cases

### Plan Becomes Stale

- **Problem:** PDFs edited after plan creation
- **Solution:** Hash check detects mismatch, forces regeneration

### Partial Application

- **Problem:** Apply fails midway through batch
- **Solution:** Atomic operations per PDF, audit log tracks progress

### PII Detection Improvements

- **Problem:** New PII detector finds more instances
- **Solution:** Regenerate plan with new detector, compare to old plan

## Testing Strategy

```python
def test_redaction_apply_requires_matching_plan():
    """Verify plan hash check prevents wrong PDF redaction."""
    plan = create_plan([pdf1, pdf2])

    # Modify pdf1 after plan creation
    pdf1.write("MODIFIED")

    # Apply should fail due to hash mismatch
    with pytest.raises(ValueError, match="Hash mismatch"):
        apply_redactions(plan, output_dir, force=False)

def test_redaction_preview_no_side_effects():
    """Preview mode doesn't modify originals."""
    original_hash = compute_hash(pdf)
    preview_redactions(plan, preview_dir)
    assert compute_hash(pdf) == original_hash
```

## References

- FRCP Rule 26 (redaction requirements)
- NIST SP 800-88 (data sanitization)
- Related: ADR 0003 (Determinism Policy)

---

**Last Updated:** 2025-10-24
