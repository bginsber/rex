"""End-to-end tests for the redaction workflow."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import]
import pytest

from rexlit.app.adapters.pii_regex import PIIRegexAdapter
from rexlit.app.adapters.pdf_stamper import PDFStamperAdapter
from rexlit.app.adapters.storage import FileSystemStorageAdapter
from rexlit.app.redaction_service import RedactionService
from rexlit.audit.ledger import AuditLedger
from rexlit.config import Settings


@pytest.fixture()
def redaction_stack(tmp_path: Path) -> tuple[RedactionService, AuditLedger, Settings]:
    """Provision a fully wired redaction service backed by real adapters."""

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    settings = Settings(
        data_dir=data_dir,
        config_dir=config_dir,
        audit_enabled=True,
    )

    ledger = AuditLedger(
        settings.get_audit_path(),
        hmac_key=settings.get_audit_hmac_key(),
        fsync_interval=1,
    )

    service = RedactionService(
        pii_port=PIIRegexAdapter(),
        stamp_port=PDFStamperAdapter(),
        storage_port=FileSystemStorageAdapter(),
        ledger_port=ledger,
        settings=settings,
    )

    return service, ledger, settings


def _make_test_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "SSN: 123-45-6789", fontsize=12)
    page.insert_text((100, 120), "Email: secret@example.com", fontsize=12)
    doc.save(str(path))
    doc.close()


def _extract_text(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def test_redaction_workflow_plan_to_apply(tmp_path: Path, redaction_stack: tuple[RedactionService, AuditLedger, Settings]) -> None:
    """Plan, validate, and apply redactions to a PDF with audit logging."""

    service, ledger, _settings = redaction_stack
    source_pdf = tmp_path / "sensitive.pdf"
    _make_test_pdf(source_pdf)

    plan_path = tmp_path / "sensitive.redaction-plan.enc"
    plan = service.plan(
        source_pdf,
        plan_path,
        pii_types=["SSN", "EMAIL"],
    )

    assert plan_path.exists()
    assert plan.plan_id
    assert len(plan.redactions) >= 2
    assert service.validate_plan(plan_path) is True

    output_dir = tmp_path / "redacted"
    applied = service.apply(plan_path, output_dir, preview=False, force=False)

    assert applied == len(plan.redactions)
    redacted_pdf = output_dir / source_pdf.name
    assert redacted_pdf.exists()
    redacted_text = _extract_text(redacted_pdf)
    assert "123-45-6789" not in redacted_text
    assert "secret@example.com" not in redacted_text

    operations = [entry.operation for entry in ledger.read_all()]
    assert "redaction_plan_create" in operations
    assert "redaction_apply" in operations


def test_apply_rejects_hash_mismatch(tmp_path: Path, redaction_stack: tuple[RedactionService, AuditLedger, Settings]) -> None:
    """Hash mismatches prevent applying outdated plans."""

    service, _ledger, _settings = redaction_stack
    source_pdf = tmp_path / "mismatch.pdf"
    _make_test_pdf(source_pdf)

    plan_path = tmp_path / "plan.enc"
    service.plan(source_pdf, plan_path, pii_types=["SSN"])

    # Mutate the source PDF so the stored hash no longer matches.
    doc = fitz.open(str(source_pdf))
    page = doc[0]
    page.insert_text((100, 140), "MODIFIED", fontsize=12)
    mutated = tmp_path / "mutated.pdf"
    doc.save(str(mutated))
    doc.close()
    mutated.replace(source_pdf)

    with pytest.raises(ValueError, match="hash mismatch"):
        service.apply(plan_path, tmp_path / "out")
