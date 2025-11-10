# Documentation Consistency: README.md vs NEXT_STEPS.md

**Analysis Date**: 2025-11-03
**Purpose**: Identify misalignments between project status (README.md) and development roadmap (NEXT_STEPS.md)

---

## Critical Inconsistencies Found

### 1. TEST COUNT MISMATCH ⚠️

**README.md says**:
```
Tests: 146/146 passing (`pytest -v --no-cov`)
```

**NEXT_STEPS.md says**:
```
Test Status: 151 tests passing (100%) across 22 test files
```

**Delta**: +5 tests (or README.md is outdated)

**Issue**: Which is correct? Need to verify actual test count:
```bash
pytest --collect-only -q | wc -l
```

**Implication**: If NEXT_STEPS.md is newer (+5 tests), README.md needs updating.

---

### 2. PHASE 2 (M1) COMPLETION CLAIMS

| Feature | README Status | NEXT_STEPS Status | Actual Implementation |
|---------|---|---|---|
| **Bates Stamping** | ✅ Complete | ⚠️ Partial (PDF stamping missing) | `PDFStamperAdapter` exists but `apply_redactions()` raises NotImplementedError |
| **Opticon Export** | ✅ Complete | ❌ NotImplementedError | Not actually implemented |
| **Production Exports** | ✅ Complete | ⚠️ Partial (Opticon/LFP missing) | Only DAT format works |
| **OCR Processing** | ✅ Complete | ✅ Complete | ✅ TesseractOCRAdapter fully implemented |
| **Rules Engine** | ✅ Complete | ✅ Complete | ✅ Both TX/FL rules engines implemented |

**Issue**: README claims M1 is complete with features that NEXT_STEPS.md identifies as incomplete or stubbed.

**Which is honest?**: NEXT_STEPS.md (it acknowledges gaps)

---

### 3. "PRODUCTION EXPORTS" - FALSE POSITIVE

**README.md line 28**:
```
- **Production Exports**: Court-ready DAT/Opticon load files for discovery productions
```

**README.md line 384-388**:
```
**Production Exports:**
- ✅ DAT load file generation
- ✅ Opticon format support
- ✅ Bates prefix validation
- ✅ Full audit trail integration
```

**NEXT_STEPS.md Reality**:
```
### 3. Load File Format Support (Opticon/LFP)
**Impact**: Cannot export to Opticon or LFP formats
**Effort**: 1-2 days each
**Files**: `rexlit/app/pack_service.py:404-409`
**Status**: Currently raises NotImplementedError
```

**Verdict**: README overstates M1 completion. Opticon support is marked ✅ but not actually implemented.

---

### 4. "BATES STAMPING" - OVERSTATED COMPLETION

**README.md line 26**:
```
- **Bates Stamping**: Layout-aware PDF stamping with rotation handling and safe-area detection
```

**README.md line 371-375**:
```
**Bates Stamping:**
- ✅ Layout-aware PDF stamping with rotation handling
- ✅ Safe-area detection (0.5\" margins)
- ✅ Position presets and color/font customization
- ✅ Deterministic sequencing by SHA-256 hash
```

**NEXT_STEPS.md Reality**:
```
### 2. Redaction Application (StampPort.apply_redactions) ⚠️ BLOCKING
**Impact**: Core redaction feature is non-functional
**Files**: `rexlit/app/adapters/pdf_stamper.py:112-118`
**Status**: Currently raises NotImplementedError
```

**Verdict**:
- ✅ Bates **planning** is complete (SequentialBatesPlanner)
- ❌ Bates **PDF stamping** is incomplete (NotImplementedError in apply_redactions)
- README conflates the two

---

### 5. REDACTION STATUS - HIDDEN GAPS

**README.md line 394-397**:
```
**Redaction (Planned):**
- 🚧 PII detection via Presidio
- 🚧 Interactive redaction review TUI
- 🚧 Redaction plan versioning
```

**What's Actually Missing**:
- ❌ PIIPort adapter (no Presidio integration)
- ❌ RedactionApplierPort implementation (raises NotImplementedError)
- ❌ CLI commands not wired
- ❌ No working end-to-end redaction workflow

**README framing**: "Redaction (Planned)" suggests it's not yet in scope.

**NEXT_STEPS framing**: "Redaction application (BLOCKING)" suggests it's critical for M2.

**Verdict**: README is vague; NEXT_STEPS is explicit about blockers.

---

### 6. TEST REPORTING INCONSISTENCY

**README.md line 16**:
```
**Tests:** 146/146 passing (`pytest -v --no-cov`)
```

**README.md line 361 & 390**:
```
**Testing:** 63 integration/unit tests (100% passing)     [M0]
**Testing:** 146 integration/unit tests (100% passing)    [M1]
```

**NEXT_STEPS.md line 5**:
```
**Test Status**: 151 tests passing (100%) across 22 test files
```

**Issue**:
- README header says 146 tests
- README section breakout says M0=63, M1=146 (total=146)
- NEXT_STEPS says 151 total

**Likely**: Tests were added since README last updated. NEXT_STEPS is newer.

---

### 7. DENSE RETRIEVAL - UNDERSOLD

**README.md** mentions it but doesn't emphasize:
- Line 24: "optional Kanon 2 dense/hybrid retrieval"
- Line 40: "Dense/hybrid search via Kanon 2 embeddings (requires online mode)"

**NEXT_STEPS.md** treats it as **core infrastructure**:
- Line 5: Fully implemented
- Complete HNSW adapter
- 15+ tests for dense functionality
- Hybrid search with RRF fusion

**Verdict**: README undersells this feature. Dense search should be more prominent.

---

## Summary: What Needs Updating

### UPDATE README.md TO:

1. **Fix test count** (146 → 151 or verify actual count)
2. **Demote Opticon to "Not Yet Implemented"**
   ```
   **Production Exports:**
   - ✅ DAT load file generation
   - ❌ Opticon format (in progress for M2)
   - ❌ LFP format (in progress for M2)
   ```

3. **Separate Bates Planning from Bates Stamping**
   ```
   **Bates Planning:**
   - ✅ Sequential numbering with deterministic ordering

   **Bates PDF Stamping:**
   - ⚠️ In progress (PDF application needed)
   ```

4. **Be honest about Redaction**
   ```
   **Redaction (In Progress):**
   - ⚠️ PII detection adapter (blocking)
   - ⚠️ Redaction application (blocking)
   - 🚧 Interactive review TUI (stretch)
   ```

5. **Promote Dense Retrieval**
   - Move from "optional" to core features
   - Highlight Kanon 2 + HNSW + Hybrid search

6. **Update Phase 3 Status**
   ```
   🚧 **Phase 3 (M2)** – Redaction ⚠️ BLOCKING, Email threading, Advanced analytics
   ```

---

## Recommended Changes to README.md

### SECTION: Status (Lines 9-17)

**Current**:
```
**Tests:** 146/146 passing (`pytest -v --no-cov`)
```

**Should be**:
```
**Tests:** 151/151 passing (`pytest -v --no-cov`)
**Gap**: Opticon/LFP load file export (blocking M2)
**Gap**: Redaction application PDF support (blocking M2)
```

### SECTION: Deliverables > Phase 2 (Lines 384-390)

**Current** (overstates completion):
```
**Production Exports:**
- ✅ DAT load file generation
- ✅ Opticon format support
- ✅ Bates prefix validation
- ✅ Full audit trail integration
```

**Should be**:
```
**Production Exports:**
- ✅ DAT load file generation
- ⚠️ Opticon format support (in progress)
- ⚠️ LFP format support (in progress)
- ✅ Bates prefix validation
- ✅ Full audit trail integration

**Bates Stamping:**
- ✅ Bates number planning & sequencing
- ⚠️ PDF stamping/application (in progress)
- ✅ Layout-aware positioning
- ✅ Deterministic ordering
```

### SECTION: Deliverables > Phase 3 (Lines 392-407)

**Current** (vague):
```
**Redaction (Planned):**
- 🚧 PII detection via Presidio
- 🚧 Interactive redaction review TUI
- 🚧 Redaction plan versioning
```

**Should be**:
```
**Redaction (In Progress - BLOCKING):**
- ❌ PII detection adapter (Presidio integration needed) — BLOCKING
- ❌ Redaction application (PDF coordinate support needed) — BLOCKING
- ⚠️ Interactive redaction review TUI (post-MVP)
- ⚠️ Redaction plan versioning (future)
```

---

## Verification Checklist

Before updating README.md, verify:

- [ ] Run `pytest --collect-only -q | wc -l` to get exact test count
- [ ] Check `rexlit/app/pack_service.py:404-409` — is Opticon actually NotImplementedError?
- [ ] Check `rexlit/app/adapters/pdf_stamper.py:112-118` — verify apply_redactions status
- [ ] Verify all 6 P1 todos are marked "resolved" in todo files
- [ ] Confirm NEXT_STEPS.md accurately reflects actual codebase state

---

## Conclusion

**README.md is 1-2 weeks outdated** relative to NEXT_STEPS.md:
- Test count off by 5
- Overstates M1 completion (Opticon, LFP, Redaction Apply)
- Undersells Dense Retrieval
- Vague about Redaction blockers

**NEXT_STEPS.md is more honest** about what's actually missing and what's blocking.

**Recommendation**: Use NEXT_STEPS.md as source of truth, then backport corrections to README.md.

---

**Generated**: 2025-11-03
**Scope**: README.md vs NEXT_STEPS.md consistency check
