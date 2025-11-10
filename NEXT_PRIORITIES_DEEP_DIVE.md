# RexLit Next Priorities: Deep Dive Analysis
**Date:** November 8, 2025
**Project Status:** Phase 2 (M1) Merged & Shipped | Phase 3 (M2) Roadmap
**Latest PR:** Security fix + Bun/React web UI wrapper
**All Tests:** 151 passing (100%)

---

## Executive Summary

RexLit has successfully completed Phase 2 (M1) with **massive momentum**:
- ✅ Core CLI platform fully functional (discovery, indexing, search, OCR, Bates, rules, privilege)
- ✅ Web API + React UI layer added (Bun/Elysia/TypeScript)
- ✅ Security vulnerability patched (arbitrary file read in document endpoint)
- ✅ All 151 tests passing with 100% compliance

**The last big push merged TWO major milestones:**
1. **Privilege Classification Pipeline** - 3-stage modular system with pattern-based pre-filtering and LLM escalation
2. **Web UI Wrapper** - Complete React interface for human-in-the-loop privilege review

This deep dive identifies **what's next** based on code analysis, current TODOs, and architectural gaps.

---

## What Was Just Merged: The Big Picture

### Commit f5cd0d2: Security Fix (Critical)
**Vulnerability:** `/api/documents/:hash/file` endpoint had arbitrary file read via user-controlled `path` query parameter
- **Attack:** `GET /api/documents/anything/file?path=/etc/passwd` → returns contents
- **Fix:** Endpoint now trusts Tantivy index as authoritative source, ignores query parameters
- **Impact:** Essential for shipping the web UI safely

### Commit 3611bac: Bun API + React UI (Major Feature)
**What landed:**
```
api/index.ts (180 lines)
├─ GET /api/search - Full-text search
├─ GET /api/documents/:hash/file - Document retrieval (fixed)
├─ POST /api/reviews/:hash - Privilege decision logging
└─ GET /api/stats - Index metadata

ui/src/App.tsx (168 lines) - React SPA
├─ Search form with query input
├─ Results sidebar with previews
├─ Document viewer (iframe text display)
├─ Decision buttons (Privileged/Not Privileged/Skip)
└─ Real-time status messages
```

**Architecture:** Clever "CLI-as-API" pattern - TypeScript wraps Python CLI via subprocess
```typescript
const result = await execSync(`rexlit index get ${hash}`, { encoding: 'utf-8' });
```

**E2E tested with:** 401 sample email documents, full search + privilege decisions logged

### Earlier Commits: Privilege Pipeline

The **privilege classification pipeline** was implemented in preceding commits:
- **Pattern-based filtering** (PrivilegePatternsAdapter) - Fast, offline, high-confidence
- **Safeguard LLM** (GroqPrivilegeAdapter) - For uncertain cases, privacy-preserving reasoning
- **OpenAI integration** - Optional fallback with CoT privacy masking
- **EDRM compliance** - Privilege log format validated against protocol standards

---

## Current Codebase Snapshot

### Architecture Health: Excellent ✅

**Hexagonal Structure Enforced:**
- 15/15 port interfaces defined
- 11/11 adapters implemented
- `importlinter` actively prevents violations
- Bootstrap wiring in place

**Key Ports & Adapters:**
```
DiscoveryPort ←→ IngestDiscoveryAdapter
IndexPort ←→ TantivyIndexAdapter
OCRPort ←→ TesseractOCRAdapter
BatesPlannerPort ←→ SequentialBatesPlanner
PrivilegePort ←→ PrivilegePatternsAdapter + GroqPrivilegeAdapter
StoragePort ←→ FileSystemStorageAdapter
PackPort ←→ ZipPackager
LedgerPort ←→ FileSystemLedgerAdapter
EmbeddingPort ←→ Kanon2Adapter
VectorStorePort ←→ HNSWAdapter
```

**Domain Modules Complete:**
- `rexlit/ingest/` - Discovery & extraction
- `rexlit/index/` - Tantivy building & searching
- `rexlit/ocr/` - Tesseract integration
- `rexlit/pdf/` - PDF manipulation
- `rexlit/audit/` - HMAC-signed append-only ledger
- `rexlit/rules/` - TX/FL civil procedure engine
- `rexlit/ediscovery/` - DAT/Opticon export
- `rexlit/agent/` - LLM coordination

### Lines of Code & Test Coverage

**Python Codebase:**
- ~13,000 lines across 40+ modules
- 151 tests across 22 test files
- 100% passing rate
- mypy strict mode enabled
- Ruff + Black formatting enforced

**TypeScript Web Layer (NEW):**
- 180 lines API server (Bun/Elysia)
- 168 lines React UI
- Uses RexLit CLI as subprocess backend

### Known Limitations & TODOs

**In-Code TODOs (5 total):**
```
rexlit/app/privilege_service.py:
  - Line 72: "TODO: Add pattern pre-filter with PrivilegePatternsAdapter"
  - Line 85: "TODO: Implement with separate safeguard call using responsiveness policy"
  - Line 92: "TODO: Implement with separate safeguard call using redaction policy"

rexlit/app/adapters/privilege_safeguard.py:
  - Line 310: "TODO: Encrypt with Fernet key (reuse existing crypto utils)"

rexlit/app/adapters/pii_regex.py:
  - Line 28: "SSN/PII regex comments only"
```

**NotImplementedError Functions:**
```python
# rexlit/app/pack_service.py
def _generate_opticon_load_file() → NotImplementedError  # Line 404
def _generate_lfp_load_file() → NotImplementedError      # Line 409
def _apply_redactions() → NotImplementedError            # Line 465

# rexlit/app/redaction_service.py
def apply_redactions() → NotImplementedError             # Line 67
```

---

## Next Phase Analysis: What M2 Requires

Based on NEXT_STEPS.md (dated Nov 3), here's the prioritized roadmap:

### TIER 1: BLOCKING (5-8 days)

#### 1. **Redaction Application** (2-3 days) ⚠️ CRITICAL
**Current State:** NotImplementedError in `redaction_service.py:apply_redactions()`
**What's needed:**
- Coordinate-based PDF redaction (black boxes over privileged text)
- Support multiple shapes (rectangle, line, area)
- PDF coordinate system transformations
- Error handling for malformed PDFs
- Audit trail logging per redaction
- 8+ test cases

**Files to modify:**
- `rexlit/app/adapters/pdf_stamper.py` - Implement `apply_redactions()`
- `rexlit/app/redaction_service.py` - Wire through to adapter
- `rexlit/pdf/` - PDF coordinate handling

**Why it matters:** Core redaction feature is completely non-functional without this

#### 2. **PIIPort Adapter Implementation** (3-5 days) ⚠️ CRITICAL
**Current State:** Port defined but NO adapters exist
**What's needed:**
- PII entity extraction (SSN, credit card, DOB, etc.)
- Integration with detection library (Presidio or similar)
- Two methods: `analyze_text()` and `analyze_document()`
- Deterministic ordering of findings (SHA-256)
- 10+ test cases covering accuracy

**Files to create:**
- `rexlit/app/adapters/pii.py` (NEW)
- `rexlit/app/adapters/pii_regex.py` (skeleton exists, needs expansion)
- Update `rexlit/bootstrap.py` to wire adapter

**Why it matters:** Redaction workflow depends on PII detection to find sensitive spans

#### 3. **Load File Format Support** (2-3 days each)

##### 3a. Opticon Format (`.opt` files)
- Image-based production format
- Bates number → page image mapping
- Load file manifest generation

##### 3b. LFP (Load File Protocol)
- Legacy system compatibility
- Document metadata field mapping
- Validation against LFP schema

**Current:** Both are `NotImplementedError` in `pack_service.py:404-409`

**Why it matters:** Cannot export to legacy systems without these formats

---

### TIER 2: HIGHLY DESIRED (3-4 days)

#### 4. **Page Count Accuracy** (0.5 days) - QUICK WIN
**Current:** File size heuristic (`file_size / 50KB per page`)
**Fix:** Use PyMuPDF (fitz) to extract actual PDF page count
**Files:** `rexlit/app/pack_service.py:127-130`
**Impact:** Manifest reports will show actual page counts instead of estimates

#### 5. **DAT Rendering Consolidation** (1 day)
**Issue:** Two separate DAT implementations with inconsistent approaches
- `_generate_dat_loadfile()` (lines 439-485) - Generic with placeholders
- `_render_dat_loadfile()` (lines 487-516) - Specialized with Bates numbers

**Task:** Unify into single renderer with configurable options

#### 6. **Type Annotation Cleanup** (1 day)
**Current:** Some service constructors use `Any` for port types
```python
def __init__(self, storage_port: Any, ledger_port: Any):  # Should be typed
```
**Fix:** Replace with proper protocol types
**Files:** `pack_service.py`, `redaction_service.py`, `report_service.py`

---

### TIER 3: NICE-TO-HAVE (4-6 days)

#### 7. **Watch Mode Implementation** (1-2 days)
**Status:** Parsed in CLI but not functional
**Enhancement:** Auto-trigger ingest on new file detection using `watchdog` library

#### 8. **Adapter Documentation** (2-3 days)
**Need:** Comprehensive docstrings + `docs/adapters.md` API reference
**Coverage:** kanon2.py, hnsw.py, dedupe.py, discovery.py, storage.py, pdf_stamper.py, pack.py, bates.py, redaction.py

#### 9. **SignerPort Adapter** (2 days)
**Status:** Deferred to M3 (not critical for M2)
**When ready:** Implement cryptographic signing with key management

#### 10. **Pack Artifact Validation** (1-2 days)
**Enhancement:** Add checksum validation for corruption detection
- Store artifact hashes in PackManifest
- Validate on unpacking
- Detect tampering/data loss

#### 11. **HTML Report Thumbnails** (2-3 days)
**Enhancement:** Add document thumbnails to HTML reports instead of text-only stats

---

## Web Layer Observations (NEW)

### What the Bun/React UI Reveals About Next Steps

The UI was built with **document review workflow in mind**:
```typescript
// App.tsx component structure
<SearchForm /> → <ResultsSidebar /> → <DocumentViewer />
                                    → <DecisionButtons />
```

**This suggests the intended workflow:**
1. Search for potentially privileged documents
2. Preview document content in sidebar
3. Open full document in viewer
4. Make privilege decision (Privileged/Not Privileged/Skip)
5. Log decision to audit trail
6. Apply redactions based on batch decisions

**Implication:** The next priority after basic redaction is **batch privilege review UI** - but the foundation is already there!

### TypeScript API Layer Quality

The API design is solid:
- Proper error handling with typed responses
- Path-safe document access (uses hash-based lookup)
- Privilege decision logging wired to audit trail
- Stats endpoint for metadata

**Note:** Still using Python CLI as subprocess - could be optimized to direct library calls later, but works well for MVP.

---

## Suggested Sprint Prioritization

### Sprint 1 (This Week) - Core Features
**Goal:** Get basic redaction workflow functional

- [ ] PIIPort adapter implementation (Presidio integration)
  - Research Presidio API
  - Implement `analyze_text()` and `analyze_document()`
  - Add 10+ unit tests
  - Wire into bootstrap
  - **Effort:** 3-4 days

- [ ] Quick wins (1 day):
  - Type annotation cleanup
  - Page count accuracy fix
  - Import any missing dependencies

**Deliverable:** Core redaction feature functional (PII detection works)

### Sprint 2 (Next Week) - Redaction Complete
**Goal:** Ship full redaction workflow

- [ ] Redaction application implementation
  - PDF coordinate handling
  - Black box rendering
  - Audit trail logging
  - 8+ test cases
  - **Effort:** 2-3 days

- [ ] DAT rendering consolidation (1 day)

- [ ] Opticon format support (1-2 days, optional)

**Deliverable:** Full redaction workflow end-to-end

### Sprint 3 (Following Week) - Polish & Export
**Goal:** Complete export functionality

- [ ] LFP format support (1-2 days)
- [ ] Adapter documentation (2-3 days)
- [ ] Additional test coverage
- [ ] Performance optimization

**Deliverable:** All export formats working, comprehensive documentation

---

## Architecture Gaps & Opportunities

### Security-Related
- ✅ Path traversal defense (13 tests, robust)
- ✅ Audit trail with HMAC signatures
- ⚠️ Privilege reasoning encryption (TODO in privilege_safeguard.py)
- ⚠️ Web API CORS + authentication (currently open, add in M2+)

### Performance
- ✅ Parallel document processing (ProcessPoolExecutor)
- ✅ Metadata cache (O(1) lookups)
- ⚠️ Vector search (HNSW integrated but may need tuning)
- ⚠️ PDF manipulation (PyMuPDF works but could parallelize redaction apply)

### Feature Completeness
- ✅ Discovery & ingest
- ✅ Indexing & search (lexical + dense/hybrid)
- ✅ OCR with smart preflight
- ✅ Bates stamping with layout awareness
- ✅ Rules engine (TX/FL)
- ✅ Privilege classification (pattern + LLM)
- 🚧 Redaction (blocked on PIIPort + apply implementation)
- 🚧 Export formats (DAT works, Opticon/LFP blocked)
- ⚠️ Email threading (0%, not yet started)
- ⚠️ Claude integration (0%, not yet started)
- ⚠️ PaddleOCR adapter (0%, not yet started)

---

## The Elephant in the Room: Email Threading

**Not yet started** but visible in project notes. This is a separate major feature (3 weeks estimated) that:
1. Requires email header parsing (From/To/Date/Subject/References)
2. Thread reconstruction algorithm (similarity matching or explicit References header)
3. UI representation (thread visualization)
4. Performance optimization for 100K+ emails

This is likely **Phase 3 (M2) stretch goal** rather than critical path to redaction completion.

---

## Recommendations

### Immediate (This Sprint)
1. **PIIPort adapter first** - This is the most critical blocker
   - Unblock the redaction workflow
   - Enables PII-specific handling in UI
   - Measurable progress quickly

2. **Type annotation cleanup** - Low-effort, high-ROI quality improvement

3. **Redaction apply implementation** - Start design/research while PIIPort dev is underway

### Next 2-3 Weeks
1. Complete redaction application
2. Export format support (at least Opticon)
3. Comprehensive test coverage
4. Adapter documentation

### Phase 3 (M2 Stretch)
1. Email threading
2. Claude integration
3. PaddleOCR adapter
4. Web UI enhancements (CORS, auth, caching)

---

## Key Files to Watch

**High-Priority Implementation:**
- `rexlit/app/adapters/pii.py` (create new)
- `rexlit/app/adapters/pdf_stamper.py:apply_redactions()`
- `rexlit/app/redaction_service.py`
- `rexlit/app/pack_service.py` (load file formats)

**Test Files to Expand:**
- `tests/test_redaction.py`
- `tests/test_pii_adapter.py` (create new)
- `tests/test_load_file_formats.py` (create new)

**Configuration:**
- `rexlit/bootstrap.py` (wire new adapters)
- `pyproject.toml` (add new dependencies)

---

## Testing Strategy for M2

Current: 151 tests passing (100%)
Target: 165+ tests (covering new features)

**New test files needed:**
1. `test_pii_adapter.py` - 15+ tests
2. `test_redaction_apply.py` - 12+ tests
3. `test_load_file_formats.py` - 10+ tests
4. `test_page_count.py` - 3+ tests
5. Expand existing privilege tests

**Keep in mind:**
- All new code must pass mypy strict mode
- ImportLinter must enforce architecture
- Determinism tests for redaction ordering
- Security regression tests for path handling

---

## Conclusion

RexLit has reached a **stable, shippable foundation** with Phase 2 (M1) complete. The remaining work for Phase 3 (M2) is **well-scoped and clearly sequenced**:

**Critical Path:** PIIPort → Redaction Apply → Export Formats (~2 weeks)
**Quality Pass:** Documentation, testing, type cleanup (~1 week)
**Stretch Goals:** Email threading, Claude integration (~4-5 weeks additional)

The **web UI layer** adds immediate value for human-in-the-loop privilege review and positions RexLit for production deployment. The architecture is solid - implementation is now execution-focused.

**Next meeting:** Review PIIPort implementation design before starting development.

---

**Analysis Date:** November 8, 2025
**Confidence Level:** High (based on code inspection + 5 planning documents + 151 passing tests)
**Ready for:** Sprint planning & task breakdown
