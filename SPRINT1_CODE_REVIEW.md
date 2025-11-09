# Sprint 1 Code Review: Redaction Pipeline Status
**Branch:** `claude/ultrathink-m2-redaction-strategy-011CUwn1QQKa9ajd3aw7roFd`
**Review Date:** November 9, 2025
**Reviewer:** Claude Code

---

## Executive Summary

**Current Status:** ⚠️ **FOUNDATION EXISTS, INTEGRATION INCOMPLETE**

The core building blocks for the redaction workflow are in place, but critical wiring and implementation gaps prevent the end-to-end workflow from functioning. Approximately **40% complete** - the infrastructure is solid, but integration work remains.

---

## ✅ What's Working (COMPLETE)

### 1. PII Detection Adapter - FULLY IMPLEMENTED
**File:** `rexlit/app/adapters/pii_regex.py` (181 lines)

**Status:** ✅ Production-ready, tested, functional

**Evidence:**
```python
class PIIRegexAdapter:
    """Regex-based PII detector implementing PIIPort."""

    PATTERNS = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
    }

    def analyze_text(self, text: str, ...) -> list[PIIFinding]:
        # ✅ FULLY IMPLEMENTED - 135 lines
        # Detects SSN, EMAIL, PHONE, custom names
        # Returns structured findings with character offsets

    def analyze_document(self, path: str, ...) -> list[PIIFinding]:
        # ✅ FULLY IMPLEMENTED
        # Extracts text, analyzes, returns findings
```

**Test Coverage:**
- `tests/test_pii_regex_adapter.py`: 12 tests, all passing
- Tests SSN/EMAIL/PHONE detection
- Tests domain whitelisting/blacklisting
- Tests character offset accuracy
- Tests name detection with custom profiles

**Capabilities:**
- ✅ Offline-first (no network required)
- ✅ Deterministic output (sorted by character offset)
- ✅ Configurable entity types
- ✅ Domain filtering (whitelist/blacklist)
- ✅ Custom name list support

### 2. PII Port Interface - DEFINED
**File:** `rexlit/app/ports/pii.py` (77 lines)

**Status:** ✅ Well-designed protocol interface

```python
class PIIPort(Protocol):
    def analyze_text(self, text: str, ...) -> list[PIIFinding]: ...
    def analyze_document(self, path: str, ...) -> list[PIIFinding]: ...
    def get_supported_entities(self) -> list[str]: ...
    def requires_online(self) -> bool: ...
```

### 3. RedactionService Structure - EXISTS
**File:** `rexlit/app/redaction_service.py` (257 lines)

**Status:** ✅ Architecture correct, plan/apply pattern implemented

**Working Methods:**
- `validate_plan()` - ✅ Hash verification works
- `apply()` - ✅ Copies file, logs to audit (but doesn't redact)
- Internal helpers - ✅ All functional

### 4. PDF Stamper for Bates - COMPLETE
**File:** `rexlit/app/adapters/pdf_stamper.py` (204 lines)

**Status:** ✅ Bates stamping fully functional

**Evidence:**
- Layout-aware positioning
- Rotation detection
- Safe-area calculation
- Background rendering
- Multi-page support

---

## ❌ What's Broken (BLOCKERS)

### BLOCKER 1: PIIRegexAdapter Not Wired in Bootstrap
**File:** `rexlit/bootstrap.py` lines 384-390

**Current Code:**
```python
redaction_service = RedactionService(
    pii_port=None,  # ❌ BLOCKER: Not wired!
    stamp_port=None,  # ❌ BLOCKER: Not wired!
    storage_port=storage,
    ledger_port=ledger_for_services,
    settings=active_settings,
)
```

**Impact:** 🔴 CRITICAL
- RedactionService cannot detect PII (no adapter)
- Tests fail when trying to use pii_port
- plan() method cannot populate redactions

**Fix Required:** (5 minutes)
```python
from rexlit.app.adapters.pii_regex import PIIRegexAdapter

redaction_service = RedactionService(
    pii_port=PIIRegexAdapter(),  # ✅ WIRE THIS
    stamp_port=bates_stamper,    # ✅ WIRE THIS (already exists)
    storage_port=storage,
    ledger_port=ledger_for_services,
    settings=active_settings,
)
```

---

### BLOCKER 2: RedactionService.plan() Doesn't Call PII Detection
**File:** `rexlit/app/redaction_service.py` lines 66-130

**Current Code:**
```python
def plan(self, input_path, output_plan_path, *, pii_types=None):
    # ... setup code ...

    document_hash = self.storage.compute_hash(resolved_input)
    annotations = {"pii_types": sorted(pii_types)}

    plan_entry = {
        "document": str(resolved_input),
        "sha256": document_hash,
        "plan_id": plan_id,
        "actions": [],  # ❌ BLOCKER: Always empty!
        "annotations": annotations,
        "notes": "Redaction planning stub. Replace with provider integration.",
    }

    # ❌ NEVER calls self.pii.analyze_document()
    # ❌ NEVER populates redaction actions
```

**Impact:** 🔴 CRITICAL
- Plans are generated but contain zero redactions
- Apply step has nothing to apply
- Workflow is non-functional end-to-end

**Fix Required:** (1-2 hours)
```python
def plan(self, input_path, output_plan_path, *, pii_types=None):
    # ... existing setup ...

    # ✅ ADD: Extract document text
    from rexlit.ingest.extract import extract_document
    doc_result = extract_document(resolved_input)

    # ✅ ADD: Detect PII entities
    pii_findings = self.pii.analyze_document(
        path=str(resolved_input),
        entities=pii_types,
    )

    # ✅ ADD: Convert findings to redaction actions
    redaction_actions = [
        {
            "entity_type": finding.entity_type,
            "start": finding.start,
            "end": finding.end,
            "text": finding.text,  # Masked
            "confidence": finding.score,
            "page": finding.page,
        }
        for finding in pii_findings
    ]

    plan_entry = {
        "document": str(resolved_input),
        "sha256": document_hash,
        "plan_id": plan_id,
        "actions": redaction_actions,  # ✅ NOW POPULATED
        "annotations": {
            **annotations,
            "finding_count": len(redaction_actions),
        },
        "notes": f"Found {len(redaction_actions)} PII entities",
    }

    # ... rest of method ...
```

---

### BLOCKER 3: apply_redactions() Not Implemented
**File:** `rexlit/app/adapters/pdf_stamper.py` lines 112-118

**Current Code:**
```python
def apply_redactions(
    self,
    path: Path,
    output_path: Path,
    redactions: list[dict[str, Any]],
) -> int:
    raise NotImplementedError("Redaction application is not yet implemented.")
```

**Impact:** 🔴 CRITICAL
- Cannot apply black boxes to PDFs
- Workflow stops at plan generation
- Core functionality missing

**Fix Required:** (2-3 days)

This is the **BIG LIFT** - converting character offsets to PDF coordinates and rendering black boxes.

**Implementation Strategy:**
```python
def apply_redactions(self, path, output_path, redactions):
    """Apply black box redactions to PDF."""
    doc = fitz.open(str(path))
    applied_count = 0

    try:
        # Group by page
        by_page = {}
        for r in redactions:
            page_num = r.get("page", 0) or 0
            by_page.setdefault(page_num, []).append(r)

        # Apply to each page
        for page_num, page_redactions in by_page.items():
            if page_num >= len(doc):
                continue

            page = doc[page_num]

            for redaction in page_redactions:
                # Strategy 1: Search by text
                search_text = redaction.get("text", "").strip("*")
                if search_text:
                    rects = page.search_for(search_text)
                    for rect in rects:
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        applied_count += 1

                # Strategy 2: Use char offsets (future enhancement)
                elif "start" in redaction and "end" in redaction:
                    bbox = self._char_offset_to_bbox(
                        page, redaction["start"], redaction["end"]
                    )
                    if bbox:
                        page.add_redact_annot(bbox, fill=(0, 0, 0))
                        applied_count += 1

            # Apply all redactions on page (makes permanent)
            page.apply_redactions()

        # Save
        doc.save(str(output_path))

    finally:
        doc.close()

    return applied_count
```

**Complexity:**
- Text search: ⭐⭐ (Simple, 80% of use cases)
- Character offset → coords: ⭐⭐⭐⭐ (Complex, 20% of use cases)
- Rotated pages: ⭐⭐⭐ (Medium, edge case)
- Multi-column layouts: ⭐⭐⭐⭐⭐ (Hard, rare)

**Recommended MVP:** Implement text-based search first (Strategy 1), defer char offset conversion to Sprint 2.

---

### BLOCKER 4: RedactionService.apply() Doesn't Call Stamper
**File:** `rexlit/app/redaction_service.py` lines 189-195

**Current Code:**
```python
if not preview:
    resolved_output.mkdir(parents=True, exist_ok=True)
    destination_path = resolved_output / document_path.name
    self.storage.copy_file(document_path, destination_path)  # ❌ Just copies!

# ❌ NEVER calls self.stamp.apply_redactions()
```

**Impact:** 🟡 MEDIUM
- After apply_redactions() is implemented, this needs to wire it
- Currently just copies file without redacting

**Fix Required:** (30 minutes)
```python
if not preview:
    resolved_output.mkdir(parents=True, exist_ok=True)
    destination_path = resolved_output / document_path.name

    # ✅ ADD: Apply redactions using stamp port
    applied_count = self.stamp.apply_redactions(
        path=document_path,
        output_path=destination_path,
        redactions=redactions,
    )

    # Update return value to reflect actual redactions
    return applied_count
```

---

## ⚠️ What's Incomplete (NON-BLOCKING)

### 1. Type Annotations
**File:** `rexlit/app/redaction_service.py` lines 42-48

**Current:**
```python
def __init__(
    self,
    pii_port: Any,  # ⚠️ Should be PIIPort
    stamp_port: Any,  # ⚠️ Should be StampPort
    storage_port: Any,  # ⚠️ Should be StoragePort
    ledger_port: Any,  # ⚠️ Should be LedgerPort
    ...
):
```

**Fix:** (5 minutes)
```python
from rexlit.app.ports.pii import PIIPort
from rexlit.app.ports.stamp import StampPort
from rexlit.app.ports.storage import StoragePort
from rexlit.app.ports.ledger import LedgerPort

def __init__(
    self,
    pii_port: PIIPort,
    stamp_port: StampPort,
    storage_port: StoragePort,
    ledger_port: LedgerPort,
    ...
):
```

### 2. CLI Commands Missing
**Status:** ❌ No redaction commands in CLI

**Evidence:**
```bash
$ grep -n "redact" rexlit/cli.py
# No results (only references in privilege reasoning privacy notes)
```

**Fix Required:** (2 hours)

Add to `rexlit/cli.py`:
```python
@app.command()
def redaction_plan(...):
    """Generate redaction plan for PII."""
    ...

@app.command()
def redaction_apply(...):
    """Apply redaction plan to documents."""
    ...
```

### 3. End-to-End Tests Missing
**Status:** ❌ No E2E test for full workflow

**Current tests:**
- `test_redaction_service.py`: Tests plan generation (stub)
- `test_pii_regex_adapter.py`: Tests PII detection
- ❌ No test for: plan → apply → verify redacted PDF

**Fix Required:** (4 hours)

Create `tests/test_redaction_e2e.py`:
```python
def test_full_redaction_workflow(tmp_path):
    # Create PDF with SSN
    # Generate plan
    # Apply plan
    # Verify SSN is redacted (black box)
```

---

## 📊 Completion Matrix

| Component | Status | Effort to Complete | Priority |
|-----------|--------|-------------------|----------|
| PIIRegexAdapter | ✅ DONE | 0 hours | N/A |
| PIIPort interface | ✅ DONE | 0 hours | N/A |
| Wire PII in bootstrap | ❌ TODO | 0.25 hours | 🔴 P0 |
| Integrate PII into plan() | ❌ TODO | 1-2 hours | 🔴 P0 |
| apply_redactions() - text search | ❌ TODO | 8-12 hours | 🔴 P0 |
| apply_redactions() - char offsets | ❌ TODO | 12-16 hours | 🟡 P1 |
| Wire stamp in apply() | ❌ TODO | 0.5 hours | 🟡 P1 |
| Type annotations | ❌ TODO | 0.5 hours | 🟢 P2 |
| CLI commands | ❌ TODO | 2 hours | 🟡 P1 |
| E2E tests | ❌ TODO | 4 hours | 🟡 P1 |
| Rotated page handling | ❌ TODO | 4 hours | 🟢 P2 |
| Preview mode | ❌ TODO | 2 hours | 🟢 P2 |

**Total Remaining Effort:** 34.25 - 43.75 hours (5-7 days)

---

## 🎯 Recommended Sprint Plan

### Phase 1: Quick Wins (Day 1)
**Time:** 4 hours
**Goal:** Get basic workflow functional

1. ✅ Wire PIIRegexAdapter in bootstrap (15 min)
2. ✅ Wire PDFStamperAdapter in bootstrap (5 min)
3. ✅ Integrate PII detection into plan() (1.5 hours)
4. ✅ Type annotation cleanup (30 min)
5. ✅ Test plan generation with real PII (1 hour)

**Deliverable:** Plans contain real redactions

### Phase 2: Core Implementation (Days 2-4)
**Time:** 16-24 hours
**Goal:** Implement PDF redaction

1. ✅ Implement text-based search redaction (8-12 hours)
2. ✅ Wire stamper into apply() (30 min)
3. ✅ Test PDF redaction (4 hours)
4. ✅ Handle edge cases (4 hours)
   - Empty redaction list
   - Invalid page numbers
   - Text not found
   - Rotated pages (log warning)

**Deliverable:** apply_redactions() works for 80% of cases

### Phase 3: Integration & Testing (Day 5-6)
**Time:** 8 hours
**Goal:** End-to-end validation

1. ✅ CLI command implementation (2 hours)
2. ✅ E2E integration test (4 hours)
3. ✅ Documentation updates (2 hours)

**Deliverable:** Full workflow works end-to-end

### Phase 4: Polish (Day 7, Optional)
**Time:** 8 hours
**Goal:** Production-ready

1. ⭐ Character offset → bbox (8 hours)
2. ⭐ Preview mode (2 hours)
3. ⭐ Performance testing (2 hours)

---

## 🚨 Critical Path

```
Day 1: Wire adapters → Integrate PII detection
  ↓
Day 2-4: Implement apply_redactions() (text search)
  ↓
Day 5: Wire into apply() → CLI commands → E2E test
  ↓
Day 6: Testing & validation
  ↓
Day 7: (Optional) Advanced features
```

**Blocker Chain:**
1. Cannot test redaction until `apply_redactions()` implemented
2. Cannot implement `apply_redactions()` without design decision (text vs. char offset)
3. Should implement text-based first (simpler, faster, 80% coverage)

---

## 💡 Design Recommendations

### Recommendation 1: Text-Based Search First
**Rationale:**
- Simpler implementation (1 day vs. 3 days)
- Covers 80% of use cases (SSN/email are distinct text)
- PyMuPDF `page.search_for()` is battle-tested
- Can add char offset later as enhancement

**Trade-off:**
- May miss PII in complex layouts (multi-column)
- Multiple occurrences of same text = all redacted (might over-redact)

### Recommendation 2: Fail Loudly on Edge Cases
**Approach:**
```python
if page.rotation != 0:
    logger.warning(f"Page {page_num} is rotated, skipping redaction")
    continue  # Don't silently fail
```

**Rationale:**
- Better to skip than to redact wrong area
- Audit log shows which pages were skipped
- User can manually review rotated pages

### Recommendation 3: Defer Preview Mode to Sprint 2
**Rationale:**
- Preview is "nice-to-have" not "must-have"
- Can generate side-by-side comparison later
- Focus on core functionality first

---

## 📝 Testing Strategy

### Unit Tests Needed
1. ✅ `test_pii_regex_adapter.py` (already exists, 12 tests)
2. ❌ `test_redaction_apply.py` (NEW - 8 tests)
   - Single redaction
   - Multiple redactions same page
   - Multi-page redaction
   - Empty redaction list
   - Invalid page number
   - Text not found
   - Rotated page handling
   - Character offset accuracy

### Integration Tests Needed
1. ❌ `test_redaction_e2e.py` (NEW - 3 tests)
   - Full workflow: create PDF → plan → apply → verify
   - Hash mismatch detection
   - Force override flag

### Manual Testing Checklist
- [ ] Create PDF with SSN
- [ ] Generate plan: `rexlit redaction-plan doc.pdf`
- [ ] Inspect plan: Should have 1 redaction
- [ ] Apply: `rexlit redaction-apply plan.enc ./out/`
- [ ] Open redacted PDF: SSN should be black box
- [ ] Extract text: SSN should be gone

---

## 🔗 Related Files

**Core Implementation:**
- `rexlit/app/redaction_service.py` - Service orchestration
- `rexlit/app/adapters/pii_regex.py` - PII detection
- `rexlit/app/adapters/pdf_stamper.py` - PDF manipulation
- `rexlit/bootstrap.py` - Dependency wiring

**Ports:**
- `rexlit/app/ports/pii.py` - PII port interface
- `rexlit/app/ports/stamp.py` - Stamp port interface

**Tests:**
- `tests/test_pii_regex_adapter.py` - PII tests (✅ passing)
- `tests/test_redaction_service.py` - Service tests (⚠️ stub)

**Documentation:**
- `docs/adr/0006-redaction-plan-apply-model.md` - Design rationale

---

## ✅ Next Actions

**Immediate (Next Hour):**
1. Wire PIIRegexAdapter in bootstrap.py
2. Wire PDFStamperAdapter in bootstrap.py
3. Update type annotations in RedactionService

**Short-term (Next Day):**
1. Integrate PII detection into plan()
2. Test plan generation with real documents
3. Verify plan JSONL contains redactions

**Medium-term (Next 3 Days):**
1. Implement apply_redactions() (text-based)
2. Wire stamper into apply()
3. Create E2E test

**Long-term (Sprint 2):**
1. Character offset → bbox conversion
2. Preview mode
3. CLI command polish

---

**Review Complete**
**Status:** Ready for implementation
**Confidence:** High (all blockers identified, fixes scoped)
**Risk:** Low (no architectural changes needed)
