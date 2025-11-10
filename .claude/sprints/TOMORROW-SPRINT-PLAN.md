# Tomorrow Sprint Plan — M1++ Architecture Foundations

**Date:** October 24, 2025  
**Mission:** Deliver the scaffolding and guardrails required to ship the M1++ feature set with deterministic, auditable workflows.

---

## Introduction
This sprint plan sequences the work required to lock in the M1++ architecture foundation. It begins by readying the engineering environment, then moves through eight focused workstreams that establish the application layer, enforce port and adapter boundaries, codify schema and version guarantees, and harden deterministic behaviors. Each workstream includes concrete acceptance checks so the coding agent can validate progress before advancing. Daily cadence, verification commands, and the deliverables checklist ensure we finish with a tested, documented pipeline plus audit-ready artifacts and ADRs that capture the architectural decisions.

## Objective & Success Criteria
- Stand up a dedicated application layer (`rexlit/app/`) that orchestrates pipelines without leaking filesystem or network side-effects into domain modules.
- Introduce the minimal set of provider ports and adapters needed for ingest, audit, OCR, stamping, and PII so future features plug into stable contracts.
- Stabilize every JSONL/manifest artifact with a schema registry (`schema_id`, `schema_version`, provenance metadata) and wire producers to emit v1 records.
- Enforce deterministic processing (stable ordering, idempotent plans, reproducible artifacts) across ingest, bates, redaction, and dedupe.
- Ship safety rails for redaction apply, bates registry collisions, and offline/online enforcement.
- Lock the architecture in documentation: ADRs 0001–0006, README updates, and CLI usage notes.
- All unit and integration tests (`pytest -v --no-cov`) pass green; `rexlit run m1 ./sample-docs` produces byte-identical outputs on repeat runs.

---

## Prerequisites for the Coding Agent
1. Create and activate the project venv, then install dev dependencies:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
2. Review `ARCHITECTURE.md`, `SECURITY.md`, and the recommendations memo to internalize constraints.
3. Ensure sample corpus in `tests/data/` is intact for smoke tests.

---

## Workstream 1 – Application Layer & Bootstrap (AM Block)
- [ ] Scaffold `rexlit/app/` with the following modules:
  - `m1_pipeline.py`: coordinates ingest → OCR → dedupe → redaction plan → bates → pack.
  - `report_service.py`: read-only renderer consuming manifests/artifacts.
  - `redaction_service.py`, `pack_service.py`: orchestration facades with zero direct IO.
- [ ] Add `rexlit/bootstrap.py` that instantiates adapters based on `rexlit/config.Settings`.
- [ ] Refactor `rexlit/cli.py` Typer commands to call the new application services only.
- [ ] Acceptance: CLI diffs limited to service invocation; unit tests continue to pass.

## Workstream 2 – Ports & Adapter Separation
- [ ] Define protocol/ABC interfaces under `rexlit/app/ports/`:
  - `LedgerPort`, `SignerPort`, `StoragePort`, `OCRPort`, `StampPort`, `PIIPort`, `IndexPort`.
- [ ] Move existing concrete implementations into adapters (e.g., `rexlit/audit/file_ledger.py`, `rexlit/ocr/tesseract_adapter.py`, `rexlit/pdf/pymupdf_stamper.py`).
- [ ] Ensure domain packages (`audit/ledger.py`, `index/…`, `pdf/…`) depend only on DTOs plus ports.
- [ ] Add light docstrings describing side effects and offline/online expectations.
- [ ] Acceptance: mypy passes on new protocols; direct imports from domain into CLI are eliminated.

## Workstream 3 – Import Rules Enforcement
- [ ] Add `importlinter` configuration (`pyproject.toml` or `tools/importlinter.cfg`) enforcing:
  - `cli` may import `app` and `bootstrap` only.
  - Domain packages (`audit`, `ingest`, `index`, `pdf`, `ocr`, `rules`, `ediscovery`) cannot import adapters or CLI.
- [ ] Wire `importlinter` into CI via `tox`/`nox` or `Makefile` command.
- [ ] Run locally: `importlinter lint`.
- [ ] Acceptance: No contract violations; CI hook documented in README.

## Workstream 4 – Schema Registry & Versioning
- [ ] Create `rexlit/schemas/` containing JSON Schema files for:
  - `audit@1.json`, `manifest@1.json`, `bates_map@1.json`, `pii_findings@1.json`, `near_dupes@1.json`, `rexpack@1.json`.
- [ ] Update every writer (ingest manifest, audit ledger entries, dedupe outputs, bates registry, pack manifest) to include:
  - `schema_id`, `schema_version`, `producer`, `produced_at`, `content_hash`.
- [ ] Introduce helper in `rexlit/utils/schema.py` to stamp metadata and validate against registry (fail-fast in dev mode, warn in prod).
- [ ] Adapt report builder to accept `@1` schemas and emit warnings for unknown fields.
- [ ] Acceptance: Existing artifacts regenerate with new metadata; golden fixtures updated and validated via `pytest`.

## Workstream 5 – Determinism & Concurrency Discipline
- [ ] Introduce deterministic ordering helper (e.g., `deterministic_sort(paths: Iterable[Path]) -> List[Path]`) using `(sha256, relative_path)`.
- [ ] Ensure ingest, OCR batching, dedupe, and bates planning consume sorted inputs and emit sorted outputs.
- [ ] Generate bates plan JSONL before stamping; include `plan_id = sha256(input artifacts)`.
- [ ] Audit middleware wraps application services: compute input/output hashes, append to ledger via `LedgerPort`.
- [ ] Acceptance: Re-running `rexlit run m1 ./sample-docs` twice yields identical digests (`shasum -a 256` over artifacts).

## Workstream 6 – Safety Rails for Redaction & Bates
- [ ] Redaction:
  - `plan` command produces deterministic JSONL with `plan_id`, page coordinates, rationale.
  - `apply` requires `--plan` file; verify current PDF hash matches plan hash before mutating.
  - Provide `--preview` flag returning diff without writing.
- [ ] Bates:
  - Maintain append-only `bates_map.jsonl`; enforce monotonic IDs.
  - Implement `preflight` check comparing intended allocation to registry; abort on collisions unless `--force`.
  - Emit WARN log for skipped/forced allocations.
- [ ] Acceptance: Add pytest cases `test_redaction_apply_requires_matching_plan` and `test_bates_preflight_detects_collision`.

## Workstream 7 – Testing & Verification
- [ ] Expand `tests/`:
  - Contract tests per port using lightweight fixtures in `tests/data/`.
  - Determinism test re-running pipeline and asserting identical digests.
  - Property test for bates monotonicity and redaction irreversibility (no recoverable text).
  - Import-linter smoke test via `pytest --import-mode=importlib`.
- [ ] Keep runtime fast; reuse sample corpus.
- [ ] Final validation script:
   ```bash
   pytest -v --no-cov
   rexlit run m1 ./sample-docs
   rexlit report build ./sample-docs/out --output report.html
   shasum -a 256 $(find ./sample-docs/out -type f | sort)
   ```
- [ ] Acceptance: All tests pass; hashes identical across two runs.

## Workstream 8 – Documentation & ADRs (Late Afternoon)
- [ ] Draft ADRs under `docs/adr/`:
  - 0001 Offline-first gate.
  - 0002 Ports/adapters & import contracts.
  - 0003 Determinism policy.
  - 0004 JSONL schema versioning.
  - 0005 Bates numbering authority.
  - 0006 Redaction plan/apply model.
- [ ] Update `README.md` with:
  - New architecture overview.
  - Instructions for running `importlinter`, determinism checks, redaction/bates workflows.
- [ ] Add CLI examples to `CLI-GUIDE.md` covering `run m1`, `report build`, `redaction plan/apply`, `bates preflight`.
- [ ] Acceptance: Docs reviewed by PM; links to ADRs in README.

---

## Execution Cadence for the Day
- **09:00–09:30:** Kickoff, confirm ownership of each workstream, review acceptance criteria.
- **09:30–12:00:** Complete Workstreams 1–3 (application layer, ports, import rules).
- **13:00–15:00:** Tackle Workstreams 4–6 (schemas, determinism, safety rails).
- **15:00–17:00:** Expand tests (Workstream 7) and validate determinism run.
- **17:00–18:00:** Wrap documentation/ADRs (Workstream 8), run final verification commands, prep summary for stakeholders.

---

## Deliverables Checklist
- [ ] Updated source tree with application layer, ports, adapters, and bootstrap.
- [ ] Schema files plus regenerated artifacts including version metadata.
- [ ] Deterministic pipeline validated via repeated runs.
- [ ] Safety mechanisms for redaction and bates with passing tests.
- [ ] ADRs 0001–0006 and README/CLI guide revisions.
- [ ] Recorded verification output (hashes + pytest) attached to handoff notes.

Once every box is checked and verification artifacts captured, notify stakeholders via the standard end-of-day update. This completes the M1++ architecture foundation sprint. 
