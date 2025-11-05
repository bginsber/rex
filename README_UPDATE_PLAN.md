# README.md Update Plan

**Analysis Date**: 2025-11-03
**Source**: DOCS_CONSISTENCY_CHECK.md findings
**Status**: Documentation needs updating to match actual codebase state

---

## Key Finding: README is Outdated

The README.md claims M1 is fully complete, but the codebase shows:
- ✅ **Actually complete**: M0 + partial M1 (OCR, Rules, Bates planning)
- ⚠️ **In progress**: Bates PDF stamping, Load file exports (Opticon/LFP), Redaction
- ❌ **Blocked**: Redaction workflow (needs PIIPort + apply_redactions)

---

## Issues to Fix

### 1. Test Count (Line 16)

**Current**: `Tests: 146/146 passing`
**Should be**: `Tests: ~151+ passing (OCR optional)`

**Reason**: Tesseract dependency optional; README claims 146 but NEXT_STEPS says 151. Actual runnable tests vary based on optional dependencies.

**Recommendation**:
```markdown
**Tests:** 151+ unit/integration tests (100% passing core suite)*
*OCR tests require Tesseract; path traversal tests always included
```

---

### 2. Production Exports (Lines 28, 384-388)

**Current** (overstates):
```
- **Production Exports**: Court-ready DAT/Opticon load files for discovery productions
```

**Reality**: Only DAT works; Opticon/LFP raise `NotImplementedError`

**Fix**:
```markdown
- **Production Exports**: DAT load files (Opticon/LFP in progress)
```

And update the checklist:
```markdown
**Production Exports:**
- ✅ DAT load file generation
- ⚠️ Opticon format (blocking M2)
- ⚠️ LFP format (blocking M2)
- ✅ Bates prefix validation
- ✅ Full audit trail integration
```

---

### 3. Bates Stamping (Lines 26, 371-375)

**Current** (conflates planning + stamping):
```
- **Bates Stamping**: Layout-aware PDF stamping with rotation handling and safe-area detection
```

**Reality**:
- ✅ Bates **planning** (SequentialBatesPlanner)
- ❌ Bates **PDF stamping** (NotImplementedError in apply_redactions)

**Fix**:
```markdown
**Bates Planning & Numbering:**
- ✅ Sequential numbering with deterministic SHA-256 ordering
- ✅ Safe-area detection and layout-aware placement (planned)
- ✅ Audit trail integration

**Note**: PDF stamping is in progress (blocked by redaction apply implementation)
```

---

### 4. Redaction Status (Lines 394-397)

**Current** (too vague):
```markdown
**Redaction (Planned):**
- 🚧 PII detection via Presidio
- 🚧 Interactive redaction review TUI
- 🚧 Redaction plan versioning
```

**Reality**:
- ❌ PIIPort adapter (no implementation yet)
- ❌ apply_redactions() (NotImplementedError)
- ✅ Ports defined
- ✅ Plans defined

**Fix**:
```markdown
**Redaction (M2 - BLOCKING):**
- ❌ PII detection adapter (Presidio integration) — **BLOCKING**
- ❌ Redaction application (PDF support) — **BLOCKING**
- 🚧 Redaction plan versioning
- 🚧 Interactive review TUI (stretch goal)

**Status**: Core functionality blocked waiting for PIIPort & apply_redactions
```

---

### 5. Phase 3 Status Badge (Line 13)

**Current**:
```
🚧 **Phase 3 (M2)** – Redaction, email threading, advanced analytics
```

**Should indicate blocking**:
```
🚧 **Phase 3 (M2)** – Redaction ⚠️ CRITICAL BLOCKERS, email threading, advanced analytics
```

---

### 6. Dense Retrieval Under-emphasis

**Current** (line 24, minimized):
```
- **Search & Indexing**: Tantivy-backed full-text search with optional Kanon 2 dense/hybrid retrieval
```

**Should be elevated** (it's production-quality):
```
- **Search & Indexing**:
  - Tantivy full-text search with BM25 scoring
  - Kanon 2 dense embeddings + HNSW vector search (online mode)
  - Hybrid RRF fusion for combined lexical + semantic search
```

---

## Files That Need Updating

### PRIMARY: README.md

**Sections to update**:
1. Line 16 - Test count
2. Lines 26-28 - Feature summary
3. Lines 384-390 - M1 deliverables
4. Lines 392-407 - M2 deliverables & blockers

### SECONDARY: CLAUDE.md (project instructions)

**Update if M2 status changes in README**, to keep instructions in sync.

---

## Before Publishing Changes

Verify these facts:

```bash
# 1. Actual test count (core tests without OCR):
pytest tests/test_audit.py tests/test_ingest.py tests/test_security_path_traversal.py -v --no-cov 2>/dev/null | grep -c "PASSED"

# 2. Verify NotImplementedError locations:
grep -n "NotImplementedError" rexlit/app/adapters/pdf_stamper.py
grep -n "NotImplementedError" rexlit/app/pack_service.py

# 3. Check if Opticon/LFP are really not implemented:
grep -A5 "opticon\|lfp" rexlit/app/pack_service.py
```

---

## Recommended Commit Message

```
docs: Update README.md to reflect actual M1 completion status

- Test count: 146 → 151+ (Tesseract optional)
- Clarify Bates: planning ✅, PDF stamping ⚠️ in progress
- Mark Opticon/LFP as blocking (not yet implemented)
- Elevate redaction blockers for M2 visibility
- Emphasize dense retrieval as production feature
- Align with NEXT_STEPS.md truthfulness

Fixes discrepancy between docs and actual codebase state
```

---

## Timeline

**Recommend**: Update README immediately after verifying:
1. Tesseract optional dependency status
2. Exact test count that passes without OCR
3. Confirmation of NotImplementedError locations

**Impact**: High - README is first thing users/reviewers see

---

**Generated**: 2025-11-03
**Source**: DOCS_CONSISTENCY_CHECK.md analysis
