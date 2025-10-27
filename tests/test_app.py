"""Tests for the RexLit application layer bootstrap."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from rexlit.bootstrap import bootstrap_application
from rexlit.config import Settings


def test_bootstrap_application_provides_services(temp_dir: Path) -> None:
    """bootstrap_application returns wired services and ledger adapter."""

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )

    container = bootstrap_application(settings=settings)

    assert container.pipeline is not None
    assert container.report_service is not None
    assert container.redaction_service is not None
    assert container.pack_service is not None
    assert container.ledger_port is not None
    assert container.audit_service.is_enabled()

    container.ledger_port.append("smoke", inputs=["in"], outputs=["out"])

    ledger_path = settings.get_audit_path()
    assert ledger_path.exists()

    entry = json.loads(ledger_path.read_text().splitlines()[0])
    assert entry["operation"] == "smoke"
    assert entry["inputs"] == ["in"]
    assert entry["outputs"] == ["out"]

    service_entries = container.audit_service.get_entries()
    assert service_entries
    assert service_entries[-1].operation == "smoke"


def test_pipeline_run_emits_manifest(temp_dir: Path) -> None:
    """Pipeline writes manifest files with discovered document metadata."""

    documents_dir = temp_dir / "docs"
    documents_dir.mkdir()
    sample_doc = documents_dir / "sample.txt"
    sample_doc.write_text("sample content for pipeline test")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )

    container = bootstrap_application(settings=settings)

    assert not container.audit_service.is_enabled()

    manifest_path = temp_dir / "out" / "manifest.jsonl"
    result = container.pipeline.run(documents_dir, manifest_path=manifest_path)

    assert manifest_path.exists()

    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(result.documents) == 1

    record = json.loads(lines[0])
    assert Path(record["path"]).name == sample_doc.name
    assert record["sha256"] == result.documents[0].sha256
    assert record["schema_id"] == "manifest"
    assert record["schema_version"] == 1
    assert record["producer"].startswith("rexlit-")
    datetime.fromisoformat(record["produced_at"])
    assert result.notes

    redaction_plan = sample_doc.with_suffix(".redaction-plan.jsonl")
    assert redaction_plan.exists()
    redaction_entry = json.loads(redaction_plan.read_text(encoding="utf-8").splitlines()[0])
    assert redaction_entry["document"] == str(sample_doc.resolve())
    assert redaction_entry["sha256"] == result.documents[0].sha256
    assert redaction_entry["schema_id"] == "redaction_plan"
    assert redaction_entry["schema_version"] == 1
    assert redaction_entry["producer"].startswith("rexlit-")
    datetime.fromisoformat(redaction_entry["produced_at"])

    bates_plan_path = settings.get_data_dir() / "bates" / "bates_plan.jsonl"
    assert bates_plan_path.exists()
    bates_lines = bates_plan_path.read_text(encoding="utf-8").splitlines()
    assert len(bates_lines) == 1
    bates_entry = json.loads(bates_lines[0])
    assert bates_entry["document"] == str(sample_doc.resolve())
    assert bates_entry["bates_id"].startswith("RXL-")
    assert bates_entry["schema_id"] == "bates_map"
    assert bates_entry["schema_version"] == 1
    assert bates_entry["producer"].startswith("rexlit-")
    datetime.fromisoformat(bates_entry["produced_at"])

    pack_archive = settings.get_data_dir() / "packs" / "out.rexpack.zip"
    assert pack_archive.exists()

    with ZipFile(pack_archive) as archive:
        assert "manifest.jsonl" in archive.namelist()


def test_pipeline_manifest_rejects_duplicate_documents(temp_dir: Path) -> None:
    """Pipeline enforces SHA-256 uniqueness when writing manifests."""

    documents_dir = temp_dir / "docs"
    documents_dir.mkdir()
    (documents_dir / "dup1.txt").write_text("duplicate content")
    (documents_dir / "dup2.txt").write_text("duplicate content")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )

    container = bootstrap_application(settings=settings)
    container.pipeline._deduper = None  # type: ignore[attr-defined]

    manifest_path = temp_dir / "out" / "manifest.jsonl"

    with pytest.raises(ValueError) as excinfo:
        container.pipeline.run(documents_dir, manifest_path=manifest_path)

    assert "Duplicate SHA-256 detected" in str(excinfo.value)
