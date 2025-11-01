# PII & Privilege Detection Integration — Working TODO

Scope: Integrate Microsoft Presidio (PII) and hybrid embeddings (privilege) into RexLit's redaction workflow per Next_plan.md.

Owner: @bg
Created: 2025-10-28

## NOW: Ports & Data Models (Day 1)
- [ ] Create `PIIDetectorPort` in `rexlit/app/ports/pii_detector.py`
- [ ] Define `PIIEntity` Pydantic model
- [ ] Create `PrivilegeDetectorPort` in `rexlit/app/ports/privilege_detector.py`
- [ ] Define `PrivilegeMatch` Pydantic model
- [ ] Update `rexlit/app/ports/__init__.py` exports
- [ ] Update `RedactionPlan` model in `rexlit/app/redaction_service.py`

## NOW: Presidio Adapter (Day 1-2)
- [ ] Verify Presidio deps present in `pyproject.toml`
- [ ] Create `PresidioAdapter` in `rexlit/app/adapters/presidio_adapter.py`
- [ ] Implement `detect()` method (Presidio → PIIEntity mapping)
- [ ] Implement `supported_entities()` method
- [ ] Add custom recognizers (attorney names, case numbers)
- [ ] Write unit tests in `tests/test_pii_detector.py`
- [ ] Download spaCy model: `python -m spacy download en_core_web_lg`

## NEXT: Hybrid Privilege Adapter (Day 2-3)
- [ ] Add dependencies to `pyproject.toml` (sentence-transformers, torch)
- [ ] Create `HybridPrivilegeAdapter` in `rexlit/app/adapters/hybrid_privilege_adapter.py`
- [ ] Implement regex component (trigger patterns + context)
- [ ] Implement embedding component (SentenceTransformer + cosine similarity)
- [ ] Create `privilege_exemplars.jsonl` (sample privileged texts)
- [ ] Implement hybrid fusion (regex + semantic scores)
- [ ] Write unit tests in `tests/test_privilege_detector.py`

## NEXT: RedactionService Integration (Day 3)
- [ ] Update `RedactionService.__init__()` to accept typed ports
- [ ] Reuse `rexlit.ingest.extract.extract_document()` for text
- [ ] Implement PII detection in `plan()` method
- [ ] Implement privilege detection in `plan()` method (optional flag)
- [ ] Merge PII + privilege into `RedactionPlan.redactions`
- [ ] Update audit logging (add counts, latency)
- [ ] Write integration tests in `tests/test_redaction_integration.py`

## NEXT: Bootstrap & CLI (Day 4)
- [ ] Wire `PresidioAdapter` in `rexlit/bootstrap.py`
- [ ] Wire `HybridPrivilegeAdapter` in `rexlit/bootstrap.py`
- [ ] Add `redact` Typer group with `plan` and `apply` commands in `rexlit/cli.py`
- [ ] Add config fields to `rexlit/config.py` (thresholds, model names)
- [ ] Test CLI E2E: `rexlit redact plan ./test.pdf --pii-types SSN EMAIL`

## LATER: Testing & Documentation (Day 4-5)
- [ ] Run full test suite: `pytest -v --no-cov` (100% passing)
- [ ] Performance benchmarks (PII detection, privilege detection)
- [ ] Memory profiling (model loading overhead)
- [ ] Update `README.md` with redaction section
- [ ] Create `REDACTION-GUIDE.md` with CLI examples
- [ ] Write ADR 0007: PII/Privilege Detection Design
- [ ] Update `ARCHITECTURE.md` with new ports/adapters
- [ ] Add CLI help text and examples

## Stretch Goals (Optional)
- [ ] Interactive TUI for plan review
- [ ] GPU acceleration for batch embeddings
- [ ] Custom model fine-tuning for privilege detection
- [ ] Redaction audit report generation

## Notes
- Keep offline-first: All models run locally
- Follow ADR 0006 (plan/apply pattern)
- Maintain hexagonal architecture (ports/adapters)
- Encrypted JSONL plans (existing pattern)
- Audit trail for all operations
