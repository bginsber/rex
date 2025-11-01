"""Tests for PackService validate_pack functionality."""

from __future__ import annotations

import json
from pathlib import Path

from rexlit.bootstrap import bootstrap_application
from rexlit.config import Settings


def test_validate_pack_success(temp_dir: Path) -> None:
    """validate_pack returns True for valid pack with all artifacts present."""
    # Setup: Create a valid pack directory
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    # Create artifact directories
    natives_dir = pack_dir / "natives"
    text_dir = pack_dir / "text"
    metadata_dir = pack_dir / "metadata"
    natives_dir.mkdir()
    text_dir.mkdir()
    metadata_dir.mkdir()

    # Create artifact files
    native_file = natives_dir / "abc123.pdf"
    text_file = text_dir / "abc123.txt"
    metadata_file = metadata_dir / "documents.jsonl"

    native_file.write_bytes(b"PDF content")
    text_file.write_text("Extracted text", encoding="utf-8")
    metadata_file.write_text('{"doc": "metadata"}\n', encoding="utf-8")

    # Create manifest.json
    manifest = {
        "pack_id": "pack_test_123",
        "created_at": "2025-10-28T12:00:00Z",
        "document_count": 1,
        "total_pages": 5,
        "bates_range": "PROD001-PROD005",
        "redaction_count": 0,
        "artifacts": [
            "natives/abc123.pdf",
            "text/abc123.txt",
            "metadata/documents.jsonl",
        ],
    }

    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Create PackService
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation passed
    assert result is True

    # Verify audit log entry
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "valid"
    assert validate_record.args["pack_id"] == "pack_test_123"
    assert validate_record.args["artifact_count"] == 3


def test_validate_pack_missing_manifest(temp_dir: Path) -> None:
    """validate_pack returns False when manifest.json is missing."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation failed
    assert result is False

    # Verify audit log entry
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "failed"
    assert validate_record.args["reason"] == "Manifest file not found"


def test_validate_pack_empty_manifest(temp_dir: Path) -> None:
    """validate_pack returns False when manifest.json is empty."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    # Create empty manifest
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text("", encoding="utf-8")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation failed
    assert result is False

    # Verify audit log entry
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "failed"
    assert validate_record.args["reason"] == "Empty manifest file"


def test_validate_pack_missing_artifact(temp_dir: Path) -> None:
    """validate_pack returns False when an artifact is missing."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    # Create manifest with artifacts that don't exist
    manifest = {
        "pack_id": "pack_test_missing",
        "created_at": "2025-10-28T12:00:00Z",
        "document_count": 1,
        "total_pages": 5,
        "bates_range": None,
        "redaction_count": 0,
        "artifacts": [
            "natives/missing.pdf",
            "text/missing.txt",
        ],
    }

    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation failed
    assert result is False

    # Verify audit log entry
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "failed"
    assert "failures" in validate_record.args
    failures = validate_record.args["failures"]
    assert len(failures) == 2
    assert "Missing artifact: natives/missing.pdf" in failures
    assert "Missing artifact: text/missing.txt" in failures


def test_validate_pack_partial_artifacts(temp_dir: Path) -> None:
    """validate_pack returns False when some artifacts are present but others missing."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    # Create one artifact but not the other
    natives_dir = pack_dir / "natives"
    natives_dir.mkdir()
    native_file = natives_dir / "abc123.pdf"
    native_file.write_bytes(b"PDF content")

    # Create manifest with two artifacts
    manifest = {
        "pack_id": "pack_test_partial",
        "created_at": "2025-10-28T12:00:00Z",
        "document_count": 1,
        "total_pages": 5,
        "bates_range": None,
        "redaction_count": 0,
        "artifacts": [
            "natives/abc123.pdf",  # exists
            "text/abc123.txt",     # missing
        ],
    }

    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation failed
    assert result is False

    # Verify audit log entry
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "failed"
    failures = validate_record.args["failures"]
    assert len(failures) == 1
    assert "Missing artifact: text/abc123.txt" in failures


def test_validate_pack_empty_artifacts_list(temp_dir: Path) -> None:
    """validate_pack returns True for pack with no artifacts (edge case)."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    # Create manifest with empty artifacts list
    manifest = {
        "pack_id": "pack_test_empty",
        "created_at": "2025-10-28T12:00:00Z",
        "document_count": 0,
        "total_pages": 0,
        "bates_range": None,
        "redaction_count": 0,
        "artifacts": [],
    }

    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation passed (no artifacts to validate)
    assert result is True

    # Verify audit log entry
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "valid"
    assert validate_record.args["artifact_count"] == 0


def test_validate_pack_invalid_json(temp_dir: Path) -> None:
    """validate_pack returns False when manifest.json contains invalid JSON."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    # Create invalid JSON manifest
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text("{ invalid json }", encoding="utf-8")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=True,
    )
    container = bootstrap_application(settings=settings)

    # Validate pack
    result = container.pack_service.validate_pack(pack_dir)

    # Assert validation failed
    assert result is False

    # Verify audit log entry contains error reason
    audit_records = container.ledger_port.read_all()
    validate_record = next(
        (r for r in audit_records if r.operation == "pack_validate"), None
    )
    assert validate_record is not None
    assert validate_record.args["status"] == "failed"
    assert "reason" in validate_record.args
