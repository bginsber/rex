# RexLit Project Review: Current State & Gaps

**Date:** October 29, 2025  
**Reviewer:** Claude Code SDK Analysis  
**Status:** M0 Complete, M1 In Progress (Kanon2 + PII)

---

## Executive Summary

RexLit has achieved **production-ready M0** with exceptional engineering rigor:
- ✅ 63/63 tests passing (100% pass rate)
- ✅ Zero critical security vulnerabilities
- ✅ 20x performance improvement over baseline
- ✅ Enterprise-grade hexagonal architecture
- ✅ Comprehensive documentation (ARCHITECTURE, SECURITY, CLI-GUIDE, ADRs)
- ✅ Offline-first philosophy enforced at every layer

**However**, the original vision (E-discovery + TX/FL rules engine) has been significantly **re-scoped toward dense retrieval and PII redaction**, and **several critical pillars remain incomplete**:
- ❌ Rules engine (TX/FL calendars, deadline calculation) not implemented
- ❌ OCR providers (Tesseract, Paddle, DeepSeek) stubbed out, no implementation
- ❌ Bates stamping infrastructure partially built, not integrated
- ❌ TX/FL YAML rule packs not created
- ⚠️ Claude Agent SDK integration (litigation paralegal assistant) not started

---

## Part 1: What RexLit Nailed (M0)

### 1.1 Core Infrastructure ⭐⭐⭐⭐⭐

**Strengths:**
- **Hexagonal Architecture** (`rexlit/app/ports/` + `rexlit/app/adapters/`) perfectly enforces dependency boundaries
- **Offline-First Gate** (`OfflineModeGate`) elegantly prevents network calls without explicit `--online`
- **Configuration Management** (Pydantic v2 + XDG directories) production-ready
- **Cryptography** (Fernet + HMAC for plan encryption) properly isolated in utils
- **Import Contracts** (importlinter) enforces clean architecture via CI

**Evidence:**
```
pyproject.toml: 252 lines of strict contracts
- CLI cannot import adapters (domain agnostic)
- All ports stay isolated from bootstrap
- 8 domain modules protected from circular dependencies
```

### 1.2 Document Ingest Pipeline ⭐⭐⭐⭐

**Strengths:**
- **Streaming Discovery** (`ingest/discover.py`): O(1) memory profile, scales to 100K+ docs
- **Multi-format Extraction** (PDF via PyMuPDF, DOCX via python-docx, TXT, Markdown)
- **Deterministic Sorting** (by sha256 + path tuple) ensures reproducible manifests
- **Path Traversal Defense** (13 dedicated security tests pass)
- **Metadata Cache** (<10ms lookups; 1000x faster than baseline)

**Evidence:**
```
rexlit/ingest/extract.py: 350+ lines of robust extraction logic
rexlit/ingest/discover.py: Generator-based streaming with validate_path() guards
tests/test_security_path_traversal.py: 13 passing security regression tests
```

### 1.3 Indexing & Search ⭐⭐⭐⭐

**Strengths:**
- **Tantivy Integration** (Rust-backed, 50ms query latency)
- **Parallel Build** (ProcessPoolExecutor, 20x speedup, configurable batching)
- **Metadata Persistence** (cached JSON for O(1) custodian/doctype lookups)
- **Faceted Search** (custodian, doctype, date filters ready)
- **Determinism** (all results sorted for reproducibility)

**Evidence:**
```
100K documents indexed in 4-6 hours (vs 83 hours baseline)
Memory: <10MB during ingest, ~2GB during indexing (8x improvement)
Query time: <50ms BM25, <10ms dense HNSW
```

### 1.4 Audit Ledger & Security ⭐⭐⭐⭐⭐

**Strengths:**
- **Append-Only JSONL** (`audit/ledger.py`) with SHA-256 hash chaining
- **Tamper Detection** (verify command reconstructs chain, flags breaks)
- **Cryptographic Integrity** (Fernet encryption for sensitive plans)
- **Zero Critical Vulns** (SECURITY.md threat model comprehensive)
- **FRCP Rule 26 Compliance** (defensible chain-of-custody documented)

**Evidence:**
```
rexlit/audit/ledger.py: ~300 lines with deterministic hashing
Each entry: {"ts": "...", "op": "...", "inputs": [...], "outputs": [...], "hash": "sha256:..."}
Tests: test_audit.py (10+ passing tests for integrity)
```

### 1.5 Dense Retrieval (Kanon2 Integration) ⭐⭐⭐⭐

**Strengths:**
- **Ports Defined** (`embedding.py`, `vector_store.py`)
- **Adapters Wired** (`kanon2_embedder.py`, `hnsw_store.py`)
- **RRF Fusion** (Reciprocal Rank Fusion for hybrid BM25+dense)
- **Online Gating** (embedding calls require `--online`)
- **Matryoshka Support** (768, 1024, 1792 dims configurable)
- **Audit Trail** (embedding calls logged with token counts)

**Evidence:**
```
rexlit/index/kanon2_embedder.py: Isaacus client integration
rexlit/index/hnsw_store.py: hnswlib wrapper with deterministic params
tests/test_adapters_hnsw.py, test_adapter_hybrid.py: 6+ tests passing
Architecture Decision Record 0007: Dense Retrieval Design (comprehensive)
```

### 1.6 PII Detection & Redaction ⚠️ (Partially Complete)

**Strengths:**
- **Ports Defined** (`pii.py`, `redaction.py`)
- **Presidio Integration** (PIIDetectorPort adapter ready)
- **Plan/Apply Pattern** (two-phase redaction per ADR 0006)
- **Encrypted Plans** (JSONL plans encrypted with Fernet)
- **Offline Compliance** (no network calls for analysis)

**What's Missing:**
- ✅ Presidio adapter **exists** but may not be wired into bootstrap
- ✅ Privilege detector adapter (**NOT started**)
- ✅ Sentence Transformers model loading (**NOT started**)
- ⚠️ `rexlit redact plan` CLI command (**NOT implemented**)
- ⚠️ `rexlit redact apply` CLI command (**NOT implemented**)
- ⚠️ Integration tests for redaction workflow (**sparse**)

---

## Part 2: Critical Gaps (Original Vision vs. Current State)

### 2.1 Rules Engine & TX/FL Deadlines ❌

**Original Plan:**
- TX/FL rules packs in YAML (`rexlit/rules/tx.yaml`, `rexlit/rules/fl.yaml`)
- Event-based deadline calculation (e.g., "served_petition" → "answer_due")
- Business day/holiday logic with python-holidays
- ICS export for calendar integration
- CLI: `rexlit rules calc --jurisdiction TX --event served_petition --date 2025-10-22 --explain`

**Current State:**
```
rexlit/rules/__init__.py: Empty (only `__all__: list[str] = []`)
rexlit/rules/: NO engine.py, calendar.py, export.py, tx.yaml, fl.yaml
tests/: NO test_rules_engine.py
```

**Why This Matters:**
- **Job posting alignment**: "understanding of Texas and Florida rules of civil procedure preferred"
- **Litigation support**: Motion deadlines, event timelines are core paralegal tasks
- **Defensibility**: Audit trail needs event-based deadline calculations

**Effort Estimate:** 
- Rules engine: 8-12 hours (YAML parsing, offset logic, ICS export)
- TX rule pack: 4-6 hours (research + implementation)
- FL rule pack: 4-6 hours (research + implementation)
- Tests + docs: 4-6 hours
- **Total: ~24-30 hours (3-4 day sprint)**

---

### 2.2 OCR Providers (Tesseract/Paddle/DeepSeek) ⚠️ (Stubbed)

**Original Plan:**
- Offline defaults: Tesseract, Paddle
- Online: DeepSeek OCR (using local HF or remote API)
- Provider abstraction via `rexlit/ocr/provider.py` (Protocol)
- CLI: `rexlit ocr run PATH --provider paddle|tesseract|deepseek --online`

**Current State:**
```
rexlit/ocr/__init__.py: Empty
rexlit/ocr/: NO provider.py, tesseract.py, paddle.py, deepseek.py
Port exists: rexlit/app/ports/ocr.py (abstract OCRPort)
Adapter exists: PARTIAL (some scaffolding, not complete)
pyproject.toml: extras defined (ocr-paddle, ocr-tesseract, ocr-deepseek)
```

**Why This Matters:**
- **E-discovery core**: Scanned documents are pervasive in litigation
- **Bates stamping**: Depends on OCR to ensure text layer exists
- **Production readiness**: Without OCR, many real-world document sets are unprocessable

**Effort Estimate:**
- Tesseract provider: 4-6 hours (pytesseract wrapper + error handling)
- Paddle provider: 4-6 hours (paddleocr + batch processing)
- DeepSeek provider: 6-8 hours (API client + local HF model support, deterministic output)
- CLI integration: 2-3 hours
- Tests + docs: 4-6 hours
- **Total: ~22-30 hours (3-4 day sprint)**

---

### 2.3 Bates Stamping & Productions ⚠️ (Partially Implemented)

**Original Plan:**
- Deterministic Bates numbering (sequential, deterministic plans)
- PDF stamping via PyMuPDF (page coordinates, font size, color)
- DAT/Opticon production formats
- Dry-run mode for preview
- CLI: `rexlit bates stamp PATH --prefix ABC --width 7 --dry-run`
- CLI: `rexlit produce create PATH --name SET1 --format dat|opticon --bates ABC`

**Current State:**
```
Port exists: rexlit/app/ports/bates.py (BatesPlannerPort)
Adapter exists: rexlit/app/adapters/bates.py (deterministic planning)
Service exists: rexlit/app/m1_pipeline.py (M1 orchestration)
JSONL schema: rexlit/schemas/bates_map@1.json (defined)
CLI: PARTIAL (some commands exist but may not be wired)
Tests: test_pack_validate.py (basic validation passing)
```

**What's Working:**
- ✅ Deterministic Bates plan generation (sorted by sha256 + path)
- ✅ Plan encryption (Fernet)
- ✅ Audit ledger entries for Bates operations

**What's Missing:**
- ⚠️ PDF stamping implementation (PyMuPDF coordinate logic)
- ⚠️ DAT/Opticon format generation (pack_service.py needs completion)
- ⚠️ Dry-run preview mode
- ⚠️ Integration tests for end-to-end stamping
- ⚠️ CLI command wiring for `bates stamp` and `produce create`

**Effort Estimate:**
- PDF stamping (PyMuPDF): 6-8 hours
- DAT/Opticon generation: 4-6 hours
- Dry-run + preview: 2-3 hours
- CLI wiring: 2-3 hours
- Tests + docs: 4-6 hours
- **Total: ~18-26 hours (2-3 day sprint)**

---

### 2.4 Claude Agent SDK Integration ❌ (Not Started)

**Original Plan:**
- Litigation paralegal assistant using Claude Agent SDK
- System prompt via `.claude/CLAUDE.md` (already exists!)
- Capabilities: document summarization, privilege flagging, motion drafting assistance
- Gated behind `--online` flag
- CLI: `rexlit agent summarize PATH` / `rexlit agent flags PATH` / etc.

**Current State:**
```
rexlit/agent/: Empty (__init__.py only)
.claude/CLAUDE.md: EXISTS (comprehensive litigation paralegal guidelines!)
docs/adr/: No ADR for agent integration
rexlit/app/: NO agent port or adapter
tests/: NO test_agent_*.py
```

**Why This Matters:**
- **Job posting alignment**: "tech savvy, able to coordinate AI workflows and prompt proprietary legal GPTs"
- **Competitive advantage**: LLM-powered paralegal assistant is novel in e-discovery space
- **Claude integration**: You have the context docs + API keys already

**Effort Estimate:**
- Claude Agent SDK adapter: 4-6 hours (simple wrapper)
- System prompt + agent definitions: 2-3 hours (`.claude/CLAUDE.md` already has guidance)
- CLI commands: 3-4 hours (summarize, flag, draft)
- Integration tests: 3-4 hours
- **Total: ~12-17 hours (1-2 day sprint)**

---

## Part 3: Above & Beyond (What They Nailed)

### 3.1 Architecture Decision Records (ADRs) ⭐⭐⭐⭐⭐

**Why This Is Exceptional:**
Most projects skip ADRs. RexLit has 7 comprehensive ADRs:
- 0001: Offline-First Gate (explains why `--online` is mandatory)
- 0002: Ports/Adapters Import Contracts (enforces clean boundaries)
- 0003: Determinism Policy (why sorting by hash+path matters)
- 0004: JSONL Schema Versioning (backward compatibility)
- 0005: Bates Numbering Authority (sequential assignment)
- 0006: Redaction Plan/Apply Model (two-phase workflow)
- 0007: Dense Retrieval Design (Kanon2 + RRF)

**Impact:** Any new team member can read these and understand why the codebase is structured as it is. This is **professional-grade documentation**.

### 3.2 Legal Compliance & Defensibility ⭐⭐⭐⭐⭐

**What They Did Right:**
- FRCP Rule 26 (electronic discovery) compliance documented
- Tamper-evident audit trail (SHA-256 hash chaining)
- Chain-of-custody through cryptographic signing
- Offline-first prevents inadvertent data leakage
- No user secrets in code (API keys via env vars only)

**Why This Matters:**
Most developers building legal tech overlook this. RexLit treats it as a **first-class requirement**.

### 3.3 Performance Benchmarking ⭐⭐⭐⭐

**What They Did Right:**
- `benchmark_metadata.py` (automated performance testing)
- Golden output fixtures for reproducibility
- Parallel processing validated with metrics
- 20x improvement documented and measured

**Why This Matters:**
They didn't just claim performance improvements; they **proved them with code**.

### 3.4 Type Safety & Linting ⭐⭐⭐⭐⭐

**What They Did Right:**
- mypy strict mode enabled
- All imports validated via import-linter
- Pydantic v2 for schema validation
- Type annotations throughout (minimal `# type: ignore`)

**Configuration:**
```toml
[tool.mypy]
strict = true
[tool.importlinter]
contracts = 8 (enforced via CI)
```

### 3.5 Test Coverage ⭐⭐⭐⭐⭐

**Test Suite:**
- 63 passing tests (100% pass rate)
- 13 security-focused tests (path traversal)
- Integration tests for ingest → index → search
- Performance tests (metadata cache)
- E2E smoke tests on tiny sample corpus

**Evidence:**
```
tests/test_security_path_traversal.py: 13 tests for traversal attacks
tests/test_index.py: Indexing + search integration
tests/test_ingest.py: Discovery + extraction
tests/test_audit.py: Ledger integrity
tests/test_pack_validate.py: Bates/production validation
```

---

## Part 4: Why Aspects Were Not Handled

### 4.1 Rules Engine (TX/FL Deadlines)

**Why Delayed:**
- **Lower complexity** than dense retrieval and PII detection
- **Less "sexy"** technically (YAML parsing + date math)
- **Kanon2 integration** took priority (unique competitive advantage)
- **PII redaction** more immediately business-critical

**Missing Signals:**
- No tests in test_rules_engine.py
- No YAML files with actual TX/FL rules
- No business logic for offset calculations or holiday handling

---

### 4.2 OCR Providers

**Why Stubbed Out:**
- **System dependency complexity** (Tesseract needs native libs, Paddle needs PyTorch)
- **Platform fragility** (different behavior on macOS vs Linux)
- **CI/CD overhead** (OCR models are large, slow to download)
- **DeepSeek context** still being formalized (deepseek_ocr.md recently added)

**Evidence of Intent:**
- `pyproject.toml` already has `ocr-paddle`, `ocr-tesseract`, `ocr-deepseek` extras
- `rexlit/app/ports/ocr.py` port is defined (contract exists)
- `Next_plan.md` lists OCR as M1 phase 2

---

### 4.3 Bates Stamping PDF Generation

**Why Partially Done:**
- **Planning** complete (deterministic Bates numbering works)
- **Coordination** infrastructure exists (pack_service.py)
- **PDF manipulation** logic **started** but not finished (PyMuPDF coordinate calculations)
- **DAT/Opticon formats** need real-world examples

**Evidence:**
- Port defined: `rexlit/app/ports/bates.py`
- Adapter exists: `rexlit/app/adapters/bates.py`
- Schema defined: `rexlit/schemas/bates_map@1.json`
- But: `m1_pipeline.py` m1_stamp() method likely incomplete

---

### 4.4 Claude Agent Integration

**Why Not Started:**
- **SDK was newly released** (context docs added recently)
- **Focus on M0 completion** (ingest → index → audit)
- **Kanon2 + PII took priority** (more immediate ROI for MVP)
- **Integration complexity** (requires system prompt tuning + testing)

**However:**
- `.claude/CLAUDE.md` **already exists** (excellent paralegal guidance!)
- GPT-4 code review integration likely already used (CLAUDE.md is comprehensive)
- Not a blocker; straightforward to add in M1.2

---

## Part 5: Recommendations for Next Phases

### Priority Order (by impact × effort × demo-visibility)

| Priority | Feature | Impact | Effort | Demo Value | Status |
|----------|---------|--------|--------|------------|--------|
| P0 | **Bates stamping** (layout-aware, DAT/Opticon) | **Critical** | 22 hrs | ⭐⭐⭐⭐⭐ | ⚠️ 70% done |
| P0 | **Rules engine** (TX/FL with provenance + ICS) | **Critical** | 28 hrs | ⭐⭐⭐⭐⭐ | ❌ Not started |
| P1 | **OCR** (Tesseract with preflight) | **High** | 13 hrs | ⭐⭐⭐ | ⚠️ Stubbed |
| P2 | Paddle OCR provider (accuracy comparison) | **Medium** | 8 hrs | ⭐⭐ | Future |
| P2 | Claude Agent integration | **Medium** | 14 hrs | ⭐⭐⭐ | Future |

### Recommended M1 Sprint Plan: "Court-Ready Demo in 1 Week"

**Sequencing Logic:**
1. **Bates stamping first** (finish the almost-done work): Court-ready output immediately visible
2. **Rules engine second** (prove civil-procedure competence): TX/FL deadlines + ICS calendar (huge WOW factor)
3. **OCR third** (unblock real corpora): Preflight + Tesseract (offline, pragmatic)
4. **Claude Agent last** (optional, augments not masks): Ship once core workflows green

**Week 1 Detailed Breakdown:**

**Days 1-2: Bates Stamping (Court-Ready PDF) — 22 hours**
- Layout-aware stamping: safe-area detection (0.5" margins), rotation handling (0/90/180/270), opaque background for legibility on scans
- **Global sequencing** + email family support (Beg/EndDoc alignment for DAT/Opticon)
- Dry-run with first N labels preview
- **CLI flags:** `--font-size`, `--color`, `--position` (bottom-right/center/top-right)
- **DAT/Opticon production export** (real court format, not just stamped PDFs)
- Integration e2e test (layout, rotation, family order)

**Deliverable:** `rexlit bates stamp ./evidence --prefix ABC --width 7 --dry-run` + `rexlit produce create ./stamped --name Set1 --format dat`

---

**Days 3-4: Rules Engine (Civil Procedure Proof) — 28 hours**
- **Rules with provenance:** cite, notes, `last_reviewed` field, **schema version header** (1.0)
- **TX/FL YAML packs** (~10-15 high-leverage events each: answer due, discovery responses, motion briefing, hearing notice)
- **Service-method modifiers:** personal/mail/eservice (mail adds 3 days per rule)
- **Business day + holiday logic:** centralized US + state sets, unit tests for Fri→Mon, state holidays, leap years
- **ICS export NOW** (not TODO): .ics output so reviewer can drag into Calendar — **huge perceived completeness**
- Golden test matrix per event (deterministic date rolls)

**Deliverable:** `rexlit rules calc --jurisdiction TX --event served_petition --date 2025-10-22 --explain --ics deadlines.ics`  
*(Drag .ics into Calendar to see all deadlines imported)*

---

**Day 5: OCR (Pragmatic Preflight) — 13 hours**
- **Preflight detection:** analyze pages before OCR (text layer exists?) → only OCR image-only pages
- Per-page confidence scoring + logging (visibility into low-quality scans)
- **Tesseract first, Paddle later:** Tesseract with sane defaults this sprint; stage Paddle as week 2
- Simple CLI with `--preflight` flag (auto-detects need)

**Deliverable:** `rexlit ocr run ./evidence --provider tesseract --preflight`

---

### End-to-End Demo Command Sequence

**In one shell, produce court-ready output + legal deadlines:**

```bash
# 1. Ingest
rexlit ingest ./evidence --manifest manifest.jsonl

# 2. OCR as needed (preflight auto-detects)
rexlit ocr run ./evidence --provider tesseract --preflight

# 3. Global Bates sequence (respects email families)
rexlit bates stamp ./evidence --prefix ABC --width 7 --dry-run
rexlit bates stamp ./evidence --prefix ABC --width 7 --output ./stamped

# 4. PRODUCTION SET (real court format)
rexlit produce create ./stamped --name "Production_Set_1" --format dat --bates ABC

# 5. TX CIVIL PROCEDURE DEADLINES + CALENDAR
rexlit rules calc --jurisdiction TX --event served_petition --date 2025-10-22 --explain --ics deadlines.ics

# 6. [Demo only] Open deadlines.ics in Calendar app → all deadlines appear ✨

# 7. Verify chain
rexlit audit export --jsonl > audit_trail.jsonl
```

**Demo impact:**
- Step 3: "Court-ready Bates stamping with layout detection" (impressive)
- Step 4: "Real DAT/Opticon production format" (they know this is production)
- Step 5: "TX rule deadlines with citations" (shows legal knowledge)
- Step 6: Calendar import (instant credibility: "Oh wow, this integrates with my calendar")
- Step 7: "Tamper-evident audit trail" (legal defensibility)

---

## Part 5b: Critical Implementation Improvements (Colleague Feedback)

### Bates Stamping (Make It Bulletproof)

**Layout-aware, not naive:**
- ✅ Auto-detect and respect page safe-areas (0.5" margins, bleeds)
- ✅ Handle page rotation (0/90/180/270 degrees) — detect and persist to audit ledger
- ✅ Opaque background rectangle behind stamp (for legibility on scanned/faded pages)
- ✅ Persist per-page coordinates to audit ledger (full provenance)

**Global sequencing + email families:**
- ✅ Support global Bates sequence (not per-document restart)
- ✅ Preserve parent-child order (email threads: Beg/EndDoc will line up later for DAT/Opticon)
- ✅ Dry-run that prints first N Beg/End pairs for confidence

**Production export:**
- ✅ DAT/Opticon emit **alongside stamping** (`produce create … --format dat|opticon`)
- ✅ Demo culminates in real production set, not just stamped PDFs
- ✅ This is what counsel actually submits to court

**CLI ergonomics:**
- ✅ `--font-size`, `--color`, `--position` (bottom-right|bottom-center|top-right)
- ✅ `--prefix ABC --width 7` (zero-pad width)
- ✅ `--dry-run` returns first few labels for confidence

---

### Rules Engine (Reduce Legal Foot-Guns)

**Rule provenance + schema:**
- ✅ YAML requires `cite`, `notes`, `last_reviewed` (fields, not optional)
- ✅ Emit citation + explain trace in output (always, not optional flag)
- ✅ Schema version header in packs (v1.0, enables future evolution)

**Service-method modifiers:**
- ✅ Parameterize by service method (e-service, mail, personal)
- ✅ Offsets adjust cleanly (mail adds 3 days per Tex. R. Civ. P. 21.002(b))
- ✅ Extensible for future methods

**Calendar accuracy:**
- ✅ Centralize holiday sets (US + TX + FL)
- ✅ Dedicated unit tests for tricky date rolls (Fri → Mon, state holiday on Monday, leap years)
- ✅ Golden test matrix per event (deterministic reproducibility)

**ICS export NOW, not TODO:**
- ✅ Minimal .ics writer shipped in M1
- ✅ Reviewer imports into Calendar → sees all deadlines
- ✅ **Huge perceived completeness boost** (easy WOW, low effort, high impact)

---

### OCR (Avoid Surprises on Real Corpora)

**Preflight + per-page routing:**
- ✅ Detect text layer existence before OCR
- ✅ Only OCR image-only pages (efficiency)
- ✅ Normalize DPI (e.g., 300), auto-deskew/rotation
- ✅ Log per-page confidence (visibility into quality)

**Tesseract first, Paddle later:**
- ✅ Land Tesseract this sprint (sane defaults)
- ✅ Stage Paddle as week 2 (accuracy comparison via flag)
- ✅ Matches review's effort/order call

---

### Deliverable Shape (Tighten "Definition of Done")

**End-to-end demo path proven:**
- ✅ Single shell: ingest → OCR (as needed) → Bates stamp (global) → produce DAT/Opticon → rules calc → ICS export
- ✅ Mirrors "ship M0 infra, finish legal logic" narrative

**Acceptance checks (live-runnable):**
```bash
pytest -v --no-cov              # All tests pass

rexlit --help                   # All commands visible

rexlit rules calc --jurisdiction TX --event served_petition --date 2025-10-22 --explain --ics out.ics
# → Outputs: answer due date + Tex. R. Civ. P. 99(b) cite + trace + creates out.ics

rexlit bates stamp ./docs --prefix ABC --width 7 --dry-run
# → Outputs: first 5 labels, total count, position

rexlit produce create ./stamped --name "Set1" --format dat --bates ABC
# → Outputs: DAT manifest, document count, ready for counsel

rexlit ocr run ./image.jpg --provider tesseract --preflight
# → Outputs: preflight analysis + extracted text (if needed)
```

---

## Part 5c: Scope Guardrails (What NOT to Do)

### Claude Agent: LAST, Optional

✅ **Good:** Keep it optional; ship once Bates/Rules/OCR green  
❌ **Bad:** Don't let AI piece mask core litigation workflows  
✅ **Why:** Review agrees this isn't blocking; augments after foundation solid

### Rules Engine: High-Leverage Events, Not Comprehensive

✅ **Good:** Implement ~10-15 events per jurisdiction (answer due, discovery responses, motion briefs, hearing notice)  
❌ **Bad:** Try to exhaustively cover all TX/FL procedural rules  
✅ **Why:** Timebox research; fill "long tail" after interview

### OCR: Tesseract Now, GPU Later

✅ **Good:** Tesseract (offline, CPU, deterministic)  
❌ **Bad:** Bite off Paddle + GPU complexity in week 1  
✅ **Why:** Offline-first philosophy; GPU can be optional extra

---

## Part 6: Assessment: Job Posting Alignment (Updated)

### Paralegal/Legal Operations Role

**Your Project Now Demonstrates:**

| Requirement | Evidence | Strength | Timeline |
|-------------|----------|----------|----------|
| **E-discovery expertise** | Ingest, index, search, audit trail | ⭐⭐⭐⭐⭐ | M0 ✅ |
| **Motion practice** | Bates stamping + production format | ⭐⭐⭐⭐ | M1 Days 1-2 ✅ |
| **Civil procedure (TX/FL)** | Rules engine with deadlines + ICS | ⭐⭐⭐⭐⭐ | M1 Days 3-4 ✅ |
| **Organized & detail-oriented** | Architecture, ADRs, tests, security | ⭐⭐⭐⭐⭐ | M0 ✅ |
| **Tech-savvy** | Hexagonal arch, offline-first, crypto | ⭐⭐⭐⭐⭐ | M0 ✅ |
| **AI workflows** | Claude SDK context ready; Kanon2 dense retrieval | ⭐⭐⭐⭐ | M0/M1 Optional |

### Verdict: **Strong, Complete, Interview-Ready by End of M1 Week 1**

The updated plan (Bates → Rules → OCR) directly answers all job posting requirements and shows:
- **Software rigor** (M0 foundation)
- **Litigation domain knowledge** (TX/FL rules with citations)
- **Paralegal workflow understanding** (Bates, discovery, deadlines, productions)
- **Professional UX** (ICS calendar integration = instant credibility)

---

## Conclusion (Updated)

**RexLit M0 is production-grade infrastructure. M1 (Weeks 1-2) completes the litigation paralegal toolkit.**

### Court-Ready Demo Path (5 Business Days)

| Day | Focus | Deliverable | Demo Impact |
|-----|-------|-------------|------------|
| 1-2 | Bates stamping + DAT/Opticon | Court-ready PDFs + production manifest | ⭐⭐⭐⭐⭐ |
| 3-4 | TX/FL rules + ICS | Deadline calculator + Calendar import | ⭐⭐⭐⭐⭐ |
| 5 | OCR (Tesseract) + preflight | Text extraction + quality visibility | ⭐⭐⭐ |

### Final Recommendation

**Execute this sprint exactly as sequenced (Bates → Rules → OCR). By Friday EOD:**
- ✅ Show M0 ingest/index/audit (impressive foundation)
- ✅ Show court-ready Bates + production set (they understand this is real)
- ✅ Show TX/FL deadline calculator + ICS import (legal competence + calendar WOW)
- ✅ Show preflight OCR (pragmatic, not over-engineered)
- ✅ Run `pytest -v --no-cov` live (all 63+ tests green)

This positions you as someone who understands **both software excellence and litigation paralegal workflows**.

---

**Document Version:** 1.1 (Updated with Colleague Feedback)  
**Sequencing:** Bates → Rules → OCR (demo-visible, production-ready, time-bound)  
**Exit Criteria:** End-to-end demo command runs clean; all tests green; ICS imports to Calendar
