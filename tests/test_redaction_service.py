"""Tests for the redaction service plan/apply workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rexlit.app.adapters import FileSystemStorageAdapter
from rexlit.app.redaction_service import RedactionService
from rexlit.config import Settings
from rexlit.utils.crypto import decrypt_blob, encrypt_blob


class StubLedger:
    """Minimal ledger stub to capture log calls."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def log(self, *, operation: str, inputs: list[str], outputs: list[str], args: dict) -> None:
        self.records.append(
            {
                "operation": operation,
                "inputs": inputs,
                "outputs": outputs,
                "args": args,
            }
        )


def create_service(temp_dir: Path) -> tuple[RedactionService, StubLedger, Path, Settings]:
    """Helper to instantiate service with filesystem storage."""

    storage = FileSystemStorageAdapter()
    ledger = StubLedger()
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    service = RedactionService(
        pii_port=None,
        stamp_port=None,
        storage_port=storage,
        ledger_port=ledger,
        settings=settings,
    )

    doc_path = temp_dir / "document.pdf"
    doc_path.write_text("sample redaction content")

    return service, ledger, doc_path, settings


def test_redaction_service_plan_generates_plan_and_logs(temp_dir: Path) -> None:
    """plan() emits deterministic metadata and logs to the ledger."""

    service, ledger, doc_path, settings = create_service(temp_dir)
    plan_path = temp_dir / "plan" / "doc.redaction-plan.enc"

    plan = service.plan(doc_path, plan_path)

    assert plan.plan_id
    assert len(plan.plan_id) == 64
    assert plan.input_hash
    assert plan_path.exists()

    key = settings.get_redaction_plan_key()
    token = plan_path.read_text(encoding="utf-8").splitlines()[0]
    entry = json.loads(decrypt_blob(token.encode("utf-8"), key=key).decode("utf-8"))
    assert entry["plan_id"] == plan.plan_id

    assert ledger.records
    last_entry = ledger.records[-1]
    assert last_entry["operation"] == "redaction_plan_create"
    assert last_entry["args"]["plan_id"] == plan.plan_id
    logged_outputs = [Path(item).resolve() for item in last_entry["outputs"]]
    assert plan_path.resolve() in logged_outputs


def test_redaction_service_apply_copies_artifact_and_logs(temp_dir: Path) -> None:
    """apply() validates plan fingerprint before copying artifacts."""

    service, ledger, doc_path, _ = create_service(temp_dir)
    plan_path = temp_dir / "plan.enc"
    service.plan(doc_path, plan_path)

    output_dir = temp_dir / "out"
    applied = service.apply(plan_path, output_dir)

    assert applied == 0
    copied_path = output_dir / doc_path.name
    assert copied_path.exists()
    assert ledger.records[-1]["operation"] == "redaction_apply"
    assert ledger.records[-1]["args"]["plan_id"] == ledger.records[-2]["args"]["plan_id"]


def test_redaction_service_detects_hash_mismatch(temp_dir: Path) -> None:
    """apply() rejects plans when document hash changes unless forced."""

    service, ledger, doc_path, settings = create_service(temp_dir)
    plan_path = temp_dir / "plan.enc"
    service.plan(doc_path, plan_path)

    # Mutate document after planning to trigger mismatch.
    doc_path.write_text("mutated content")

    with pytest.raises(ValueError):
        service.apply(plan_path, temp_dir / "out")

    assert service.validate_plan(plan_path) is False
