# Next Plan: PII & Privilege Detection Integration

**Date:** 2025-10-28
**Phase:** M1 (Phase 2) - PII Redaction & Privilege Recognition
**Owner:** @bg
**Quick Reference:** See `PII_PRIVILEGE_INTEGRATION_SUMMARY.md`

---

## Executive Summary

Integrate Microsoft Presidio for PII detection and a hybrid (regex + embeddings) approach for privilege recognition into RexLit's existing redaction workflow. All operations run offline after one-time model downloads. Follows ADR 0006 (plan/apply pattern) and hexagonal architecture.

**Timeline:** 3-5 days
**Complexity:** Medium (ports/adapters already exist, integrating 3rd party libs)
**Risk:** Low (well-tested libraries, no breaking changes to existing code)

---

## Goals

### Core Features
1. **PII Detection:** Integrate Presidio to detect 15+ entity types (SSN, EMAIL, PHONE, etc.)
2. **Privilege Detection:** Hybrid approach combining regex triggers + semantic embeddings
3. **Redaction Workflow:** Wire into existing RedactionService (plan/apply pattern)
4. **CLI Commands:** `rexlit redact plan` and `rexlit redact apply`

### Stretch Goals
1. **Custom Recognizers:** Domain-specific patterns for legal PII (attorney names, case numbers)
2. **GPU Acceleration:** Batch embedding generation for privilege detection (10x speedup)
3. **Model Swapping:** Plugin system to swap Presidio for lighter-weight alternatives
4. **Interactive Review:** TUI for plan review before applying redactions

---

## Architecture Overview

### Ports (Interfaces)

```python
# rexlit/app/ports/pii_detector.py
class PIIDetectorPort(Protocol):
    def detect(self, text: str, *, entities: list[str] | None = None) -> list[PIIEntity]: ...
    def supported_entities(self) -> list[str]: ...
    def is_online(self) -> bool: ...  # Always False

# rexlit/app/ports/privilege_detector.py
class PrivilegeDetectorPort(Protocol):
    def detect(self, text: str, *, threshold: float = 0.75) -> list[PrivilegeMatch]: ...
    def is_online(self) -> bool: ...  # Always False
```

### Adapters (Implementations)

```python
# rexlit/app/adapters/presidio_adapter.py
class PresidioAdapter(PIIDetectorPort):
    def __init__(self):
        self.analyzer = AnalyzerEngine()  # spaCy + regex
        self.anonymizer = AnonymizerEngine()

# rexlit/app/adapters/hybrid_privilege_adapter.py
class HybridPrivilegeAdapter(PrivilegeDetectorPort):
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.exemplar_embeddings = ...  # Pre-computed
```

### Integration with RedactionService

```python
# rexlit/app/redaction_service.py (modify existing)
class RedactionService:
    def __init__(
        self,
        pii_detector: PIIDetectorPort,  # Type the existing pii_port
        privilege_detector: PrivilegeDetectorPort,  # New
        stamp_port: PDFStampPort,
        storage_port: StoragePort,
        ledger_port: LedgerPort,
    ):
        ...

    def plan(
        self,
        input_path: Path,
        output_plan_path: Path,
        *,
        pii_types: list[str] | None = None,
        detect_privilege: bool = False,
        privilege_threshold: float = 0.75,
    ) -> RedactionPlan:
        # Extract document text using existing extractor
        from rexlit.ingest.extract import extract_document
        text = extract_document(input_path).text

        # Detect PII
        pii_entities = self.pii_detector.detect(text, entities=pii_types)

        # Detect privilege (if requested)
        privilege_matches = []
        if detect_privilege:
            privilege_matches = self.privilege_detector.detect(
                text, threshold=privilege_threshold
            )

        # Merge into redaction plan
        redactions = self._merge_redactions(pii_entities, privilege_matches)

        # Generate encrypted plan (existing logic)
        ...
```

---

## Work Breakdown

### Phase 1: Ports & Data Models (Day 1)

**Goal:** Define interfaces and data structures

#### Tasks
1. **Create PIIDetectorPort** (`rexlit/app/ports/pii_detector.py`)
   - Define `PIIEntity` model (entity_type, start, end, score, text)
   - Define `detect()` method signature
   - Define `supported_entities()` method
   - Add to `rexlit/app/ports/__init__.py`

2. **Create PrivilegeDetectorPort** (`rexlit/app/ports/privilege_detector.py`)
   - Define `PrivilegeMatch` model (start, end, score, method, trigger)
   - Define `detect()` method signature
   - Add to `rexlit/app/ports/__init__.py`

3. **Update RedactionPlan Model** (`rexlit/app/redaction_service.py`)
   - Add `pii_entities: list[PIIEntity]` field
   - Add `privilege_matches: list[PrivilegeMatch]` field
   - Update `redactions` to merge both sources

**Deliverables:**
- ✅ Port interfaces defined
- ✅ Data models (Pydantic) for entities
- ✅ Type annotations complete

---

### Phase 2: Presidio Adapter (Day 1-2)

**Goal:** Implement PII detection with Presidio

#### Tasks
1. **Verify Dependencies**
   - Presidio analyzer/anonymizer already present in `pyproject.toml`.
   - Ensure spaCy model download is documented (see Model Downloads).

2. **Create PresidioAdapter** (`rexlit/app/adapters/presidio_adapter.py`)
   - Implement `PIIDetectorPort`
   - Lazy-load `AnalyzerEngine` (expensive initialization)
   - Map Presidio `RecognizerResult` → `PIIEntity`
   - Implement `supported_entities()` (query Presidio registry)
   - Add error handling (model not found, analysis failures)

3. **Add Custom Recognizers**
   - Create `PresidioCustomRecognizers` utility
   - Add pattern for attorney names (e.g., "John Doe, Esq.")
   - Add pattern for case numbers (e.g., "Case No. 12-3456")
   - Register with Presidio analyzer

4. **Write Unit Tests** (`tests/test_pii_detector.py`)
   - Mock `AnalyzerEngine.analyze()`
   - Test entity mapping (Presidio → PIIEntity)
   - Test supported entities list
   - Test error handling

**Deliverables:**
- ✅ PresidioAdapter implements PIIDetectorPort
- ✅ Custom recognizers for legal domain
- ✅ Unit tests passing

---

### Phase 3: Hybrid Privilege Adapter (Day 2-3)

**Goal:** Implement privilege detection with regex + embeddings

#### Tasks
1. **Add Dependencies** (`pyproject.toml`)
   ```toml
   sentence-transformers = "^2.2.0"
   torch = "^2.0.0"  # CPU-only version
   ```

2. **Create HybridPrivilegeAdapter** (`rexlit/app/adapters/hybrid_privilege_adapter.py`)
   - Implement `PrivilegeDetectorPort`
   - **Regex Component:**
     - Trigger patterns: "attorney-client", "work product", "privileged"
     - Context words: "confidential", "legal", "counsel"
   - **Embedding Component:**
     - Load `all-MiniLM-L6-v2` model (cached locally)
     - Pre-compute exemplar embeddings (privileged text samples)
     - For each regex match, embed surrounding context (±100 chars)
     - Compute cosine similarity to exemplars
     - Flag if similarity > threshold (default 0.75)
   - Combine regex + semantic scores

3. **Exemplar Management**
   - Create `privilege_exemplars.jsonl` (sample privileged texts)
   - Encrypt with Fernet key (same as redaction plans)
   - Load and embed at initialization

4. **Write Unit Tests** (`tests/test_privilege_detector.py`)
   - Mock `SentenceTransformer` model
   - Test regex-only detection
   - Test semantic-only detection
   - Test hybrid fusion (both signals)
   - Test threshold tuning

**Deliverables:**
- ✅ HybridPrivilegeAdapter implements PrivilegeDetectorPort
- ✅ Regex + embeddings working
- ✅ Exemplar management
- ✅ Unit tests passing

---

### Phase 4: RedactionService Integration (Day 3)

**Goal:** Wire ports into existing RedactionService

#### Tasks
1. **Update RedactionService** (`rexlit/app/redaction_service.py`)
   - Add `pii_detector: PIIDetectorPort` parameter (type the existing `pii_port`)
   - Add `privilege_detector: PrivilegeDetectorPort` parameter
   - Update `plan()` method:
     - Extract text via `rexlit.ingest.extract.extract_document()`
     - Call `pii_detector.detect(text, entities=pii_types)`
     - Call `privilege_detector.detect(text, threshold=threshold)` (if enabled)
     - Merge results into `RedactionPlan`
   - Update audit logging (add PII/privilege counts)

2. **Text Extraction (Reuse, no new port)**
   - Reuse `rexlit.ingest.extract.extract_document()` to get text
   - Handles multi-page PDFs and other formats (pdf/docx/txt)

3. **Redaction Merging Logic**
   - Deduplicate overlapping entities (PII + privilege)
   - Prioritize privilege over PII (broader scope)
   - Sort by start offset for rendering

4. **Write Integration Tests** (`tests/test_redaction_integration.py`)
   - End-to-end: PDF → Detect PII → Generate plan → Apply redactions
   - Test PII-only mode
   - Test privilege-only mode
   - Test hybrid mode (PII + privilege)
   - Verify plan integrity (hash matching)

**Deliverables:**
- ✅ RedactionService wired with ports
- ✅ PDF text extraction working
- ✅ Redaction merging correct
- ✅ Integration tests passing

---

### Phase 5: Bootstrap & CLI (Day 4)

**Goal:** Wire adapters into DI container and expose CLI

#### Tasks
1. **Update Bootstrap** (`rexlit/bootstrap.py`)
   ```python
   from rexlit.app.adapters.presidio_adapter import PresidioAdapter
   from rexlit.app.adapters.hybrid_privilege_adapter import HybridPrivilegeAdapter

   def create_redaction_service(settings: Settings) -> RedactionService:
       pii_detector = PresidioAdapter(settings)
       privilege_detector = HybridPrivilegeAdapter(settings)

       return RedactionService(
           pii_detector=pii_detector,
           privilege_detector=privilege_detector,
           stamp_port=...,
           storage_port=...,
           ledger_port=...,
       )
   ```

2. **Add CLI Commands** (`rexlit/cli.py`)
   ```python
   # Redaction subcommands (consistent with other groups)
   redact_app = typer.Typer(help="Redaction planning and application")
   app.add_typer(redact_app, name="redact")

   @redact_app.command("plan")
   def redact_plan(
       source: Path,
       output: Path | None = None,
       pii_types: list[str] | None = typer.Option(None, "--pii-types"),
       privilege: bool = typer.Option(False, "--privilege"),
       threshold: float = typer.Option(0.75, "--threshold"),
   ):
       """Generate redaction plan for PII and/or privilege."""
       container = bootstrap.bootstrap_application()
       service = container.redaction_service

       plan = service.plan(
           source,
           output,
           pii_types=pii_types,
           detect_privilege=privilege,
           privilege_threshold=threshold,
       )
       typer.echo(f"Plan generated: {plan.plan_id}")

   @redact_app.command("apply")
   def redact_apply(
       plan: Path,
       output: Path,
       preview: bool = typer.Option(False, "--preview"),
       force: bool = typer.Option(False, "--force"),
   ):
       """Apply redaction plan to PDFs."""
       container = bootstrap.bootstrap_application()
       service = container.redaction_service

       count = service.apply(plan, output, preview=preview, force=force)
       typer.echo(f"Applied {count} redactions")
   ```

3. **Update Config** (`rexlit/config.py`)
   ```python
   class Settings(BaseSettings):
       # Existing fields...

       # PII detection
       pii_score_threshold: float = 0.5
       spacy_model: str = "en_core_web_lg"

       # Privilege detection
       privilege_threshold: float = 0.75
       privilege_model: str = "all-MiniLM-L6-v2"
   ```

**Deliverables:**
- ✅ Adapters wired in bootstrap
- ✅ CLI commands functional
- ✅ Config updated

---

### Phase 6: Testing & Documentation (Day 4-5)

**Goal:** Achieve 100% test pass rate, update docs

#### Tasks
1. **Performance Tests**
   - Benchmark PII detection (docs/sec)
   - Benchmark privilege detection (embeddings/sec)
   - Memory profiling (model loading overhead)
   - Identify bottlenecks

2. **Regression Tests**
   - Deterministic plan IDs (hash-based)
   - Audit ledger integrity (hash chain)
   - Offline-only operations (mock network failures)

3. **Update Documentation**
   - **README.md:** Add "Redaction" section
   - **REDACTION-GUIDE.md:** New file with CLI examples
   - **ADR 0007:** PII/Privilege Detection Design
   - **ARCHITECTURE.md:** Update with new ports/adapters

4. **CLI Help Text**
   - Add docstrings to all commands
   - Include examples in `--help`

**Deliverables:**
- ✅ All tests passing (63 → ~75 tests)
- ✅ Documentation complete
- ✅ ADR 0007 written

---

## Dependencies

### Python Packages

Only new packages to add (Presidio packages are already present in `pyproject.toml`):

```toml
# pyproject.toml
sentence-transformers = "^2.2.0"
torch = "^2.0.0"  # CPU version
```

### Model Downloads (One-Time)

```bash
# spaCy model (~500MB)
python -m spacy download en_core_web_lg

# Sentence Transformer (~80MB, auto-downloaded)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

---

## Testing Strategy

### Unit Tests (Fast, Isolated)
- **PresidioAdapter:** Mock `AnalyzerEngine`
- **HybridPrivilegeAdapter:** Mock `SentenceTransformer`
- **RedactionService:** Mock all ports

### Integration Tests (Slower, Real Components)
- **End-to-End:** Real PDF → Presidio → Plan → Apply
- **Hybrid Detection:** Regex + embeddings together
- **Plan Integrity:** Hash verification, encryption

### Performance Benchmarks
- **PII Detection:** 1000 docs, measure throughput
- **Privilege Detection:** 1000 emails, measure latency
- **Memory:** Track model loading overhead

---

## Success Criteria

### Functional
- [ ] `rexlit redact plan ./docs/sensitive.pdf --pii-types SSN EMAIL` generates plan
- [ ] `rexlit redact plan ./emails/ --privilege --threshold 0.8` detects privileged content
- [ ] `rexlit redact apply plan.enc --output ./redacted/` applies redactions
- [ ] Plan hash verification prevents applying to modified PDFs
- [ ] Audit ledger logs all operations with structured entries

### Quality
- [ ] 100% test pass rate (`pytest -v --no-cov`)
- [ ] Type checking passes (`mypy rexlit/`)
- [ ] Import rules enforced (`lint-imports`)
- [ ] Code formatted (`black`, `ruff`)

### Performance
- [ ] PII detection: >50 docs/sec (CPU)
- [ ] Privilege detection: >20 emails/sec (CPU)
- [ ] Memory: <1GB per worker process
- [ ] Plan generation: <5s for typical document

### Documentation
- [ ] README.md updated with redaction section
- [ ] REDACTION-GUIDE.md created with examples
- [ ] ADR 0007 written (PII/Privilege Detection Design)
- [ ] CLI `--help` comprehensive

---

## Risks & Mitigations

### Risk: Model Download Failures
**Impact:** Medium (blocks first-time setup)
**Mitigation:**
- Document download steps clearly
- Add CLI command to pre-download models: `rexlit setup models`
- Graceful error messages with instructions

### Risk: spaCy Model Size (~500MB)
**Impact:** Low (acceptable for local processing)
**Mitigation:**
- Use smaller model (`en_core_web_md`, ~40MB) for low-resource environments
- Make model configurable via settings

### Risk: Embedding Latency
**Impact:** Medium (privilege detection could be slow)
**Mitigation:**
- Batch embedding (process multiple texts at once)
- GPU acceleration (optional, 10x speedup)
- Cache embeddings for repeated analysis

### Risk: False Positives (Privilege)
**Impact:** Medium (over-redaction)
**Mitigation:**
- Tunable threshold (default 0.75, can raise to 0.85)
- Hybrid approach (require both regex AND high similarity)
- Preview mode for plan review

---

## Open Questions

1. **PDF Manipulation Library?**
   - Options: PyMuPDF (fast), pikepdf (pure Python), pypdf (lightweight)
   - Recommendation: PyMuPDF (mupdf) for speed, pikepdf for pure Python

2. **Privilege Exemplars Source?**
   - Manual curation vs. synthetic generation?
   - Public datasets (Enron emails, legal docs)?
   - Recommendation: Start with 10-20 manually curated, expand with user feedback

3. **Redaction Rendering?**
   - Black boxes vs. `[REDACTED-TYPE]` text?
   - Recommendation: Black boxes for PDFs (industry standard)

4. **GPU Support?**
   - Optional for batch embeddings (10x speedup)?
   - Recommendation: Make optional, detect at runtime

---

## Future Enhancements (Post-MVP)

1. **Interactive Review TUI:** Terminal UI for reviewing plans before applying
2. **Batch Processing:** Parallel redaction across multiple PDFs
3. **Custom Model Fine-Tuning:** Train domain-specific privilege classifier
4. **Redaction Audit Report:** Generate PDF report of redactions applied
5. **API Server:** REST API for redaction as a service (offline mode)

---

## Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1. Ports & Models | 0.5 day | Port interfaces, data models |
| 2. Presidio Adapter | 1 day | PresidioAdapter + tests |
| 3. Privilege Adapter | 1 day | HybridPrivilegeAdapter + tests |
| 4. RedactionService | 1 day | Integration + tests |
| 5. Bootstrap & CLI | 0.5 day | DI wiring, CLI commands |
| 6. Testing & Docs | 1 day | Full test suite, docs |
| **Total** | **5 days** | Feature-complete PII/privilege redaction |

---

## References

- **Presidio Docs:** https://microsoft.github.io/presidio/
- **Sentence Transformers:** https://www.sbert.net/
- **ADR 0006 (Plan/Apply):** `docs/adr/0006-redaction-plan-apply-model.md`
- **RexLit Architecture:** `ARCHITECTURE.md`
- **Quick Reference:** `PII_PRIVILEGE_INTEGRATION_SUMMARY.md`

---

**Plan Version:** 1.0
**Created:** 2025-10-28
**Status:** Ready for Implementation
