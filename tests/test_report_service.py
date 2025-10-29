"""Tests for report service CSV generation."""

from __future__ import annotations

import csv
from pathlib import Path

from rexlit.bootstrap import bootstrap_application
from rexlit.config import Settings


def test_build_csv_report_basic(temp_dir: Path) -> None:
    """build_csv_report generates valid CSV from manifest."""
    # Setup
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    # Create sample manifest
    manifest_path = temp_dir / "manifest.jsonl"
    csv_path = temp_dir / "report.csv"

    # Write test manifest with sample data
    manifest_data = [
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": "/docs/sample1.pdf",
            "sha256": "a" * 64,
            "size": 12345,
            "mime_type": "application/pdf",
            "doctype": "pdf",
            "custodian": "john_doe",
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:00:00Z",
            "metadata": {
                "pages": 5,
                "createdate": "2025-01-01T00:00:00Z",
                "modifydate": "2025-01-15T00:00:00Z",
            },
        },
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": "/docs/sample2.txt",
            "sha256": "b" * 64,
            "size": 678,
            "mime_type": "text/plain",
            "doctype": "text",
            "custodian": "jane_smith",
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:01:00Z",
            "metadata": {
                "pages": 1,
            },
        },
    ]

    container.storage_port.write_jsonl(manifest_path, iter(manifest_data))

    # Execute
    row_count = container.report_service.build_csv_report(manifest_path, csv_path)

    # Verify
    assert row_count == 2
    assert csv_path.exists()

    # Read and verify CSV content
    csv_content = csv_path.read_text(encoding="utf-8")
    lines = csv_content.strip().split("\n")
    assert len(lines) == 3  # Header + 2 data rows

    # Parse CSV
    reader = csv.DictReader(lines)
    rows = list(reader)

    # Verify first row
    assert rows[0]["DOCID"] == "a" * 16
    assert rows[0]["PATH"] == "/docs/sample1.pdf"
    assert rows[0]["SHA256"] == "a" * 64
    assert rows[0]["SIZE_BYTES"] == "12345"
    assert rows[0]["MIME_TYPE"] == "application/pdf"
    assert rows[0]["DOCTYPE"] == "pdf"
    assert rows[0]["CUSTODIAN"] == "john_doe"
    assert rows[0]["PAGES"] == "5"
    assert rows[0]["CREATEDATE"] == "2025-01-01T00:00:00Z"
    assert rows[0]["MODIFYDATE"] == "2025-01-15T00:00:00Z"
    assert rows[0]["PRODUCED_AT"] == "2025-10-28T12:00:00Z"
    assert rows[0]["PRODUCER"] == "rexlit-0.1.0"

    # Verify second row
    assert rows[1]["DOCID"] == "b" * 16
    assert rows[1]["PATH"] == "/docs/sample2.txt"
    assert rows[1]["SHA256"] == "b" * 64
    assert rows[1]["CUSTODIAN"] == "jane_smith"
    assert rows[1]["PAGES"] == "1"
    assert rows[1]["CREATEDATE"] == ""  # Not present in metadata
    assert rows[1]["MODIFYDATE"] == ""  # Not present in metadata


def test_build_csv_report_handles_special_characters(temp_dir: Path) -> None:
    """build_csv_report properly escapes special characters per RFC 4180."""
    # Setup
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    manifest_path = temp_dir / "manifest.jsonl"
    csv_path = temp_dir / "report.csv"

    # Create manifest with special characters
    manifest_data = [
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": '/docs/file with "quotes" and, commas.pdf',
            "sha256": "c" * 64,
            "size": 999,
            "mime_type": "application/pdf",
            "doctype": "pdf",
            "custodian": 'Smith, John "Johnny"',
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:00:00Z",
            "metadata": {},
        }
    ]

    container.storage_port.write_jsonl(manifest_path, iter(manifest_data))

    # Execute
    row_count = container.report_service.build_csv_report(manifest_path, csv_path)

    # Verify
    assert row_count == 1
    assert csv_path.exists()

    # Read and verify CSV can be parsed correctly
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Verify special characters are preserved
    assert len(rows) == 1
    assert rows[0]["PATH"] == '/docs/file with "quotes" and, commas.pdf'
    assert rows[0]["CUSTODIAN"] == 'Smith, John "Johnny"'


def test_build_csv_report_handles_missing_fields(temp_dir: Path) -> None:
    """build_csv_report handles missing optional fields gracefully."""
    # Setup
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    manifest_path = temp_dir / "manifest.jsonl"
    csv_path = temp_dir / "report.csv"

    # Create minimal manifest (only required fields)
    manifest_data = [
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": "/docs/minimal.txt",
            "sha256": "d" * 64,
            "size": 100,
            "mime_type": "text/plain",
            "doctype": "text",
            # No custodian, no metadata, no producer, no produced_at
        }
    ]

    container.storage_port.write_jsonl(manifest_path, iter(manifest_data))

    # Execute
    row_count = container.report_service.build_csv_report(manifest_path, csv_path)

    # Verify
    assert row_count == 1
    assert csv_path.exists()

    # Verify CSV has empty strings for missing fields
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["CUSTODIAN"] == ""
    assert rows[0]["PAGES"] == ""
    assert rows[0]["CREATEDATE"] == ""
    assert rows[0]["MODIFYDATE"] == ""
    assert rows[0]["PRODUCER"] == ""
    assert rows[0]["PRODUCED_AT"] == ""


def test_build_csv_report_empty_manifest(temp_dir: Path) -> None:
    """build_csv_report handles empty manifest correctly."""
    # Setup
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    manifest_path = temp_dir / "manifest.jsonl"
    csv_path = temp_dir / "report.csv"

    # Create empty manifest
    container.storage_port.write_jsonl(manifest_path, iter([]))

    # Execute
    row_count = container.report_service.build_csv_report(manifest_path, csv_path)

    # Verify
    assert row_count == 0
    assert csv_path.exists()

    # Verify CSV has only header
    csv_content = csv_path.read_text(encoding="utf-8")
    lines = csv_content.strip().split("\n")
    assert len(lines) == 1  # Only header
    assert "DOCID,PATH,SHA256" in lines[0]
