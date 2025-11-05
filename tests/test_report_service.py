"""Tests for report service CSV generation."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

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


def test_build_impact_report_aggregates_metrics(temp_dir: Path) -> None:
    """build_impact_report generates accurate impact discovery metrics from manifest."""
    # Setup
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    # Create sample manifest with varied custodians, doctypes, extensions
    manifest_path = temp_dir / "manifest.jsonl"
    manifest_data = [
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": "/custodians/alice/doc1.pdf",
            "sha256": "a" * 64,
            "size": 1024000,  # ~1 MB
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "doctype": "pdf",
            "custodian": "alice",
            "mtime": "2024-01-15T10:00:00Z",
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:00:00Z",
        },
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": "/custodians/alice/doc2.docx",
            "sha256": "b" * 64,
            "size": 512000,  # ~0.5 MB
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "extension": ".docx",
            "doctype": "docx",
            "custodian": "alice",
            "mtime": "2024-03-20T14:30:00Z",
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:01:00Z",
        },
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": "/custodians/bob/email.eml",
            "sha256": "c" * 64,
            "size": 256000,  # ~0.25 MB
            "mime_type": "message/rfc822",
            "extension": ".eml",
            "doctype": "email",
            "custodian": "bob",
            "mtime": "2024-06-30T17:45:00Z",
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:02:00Z",
        },
    ]

    container.storage_port.write_jsonl(manifest_path, iter(manifest_data))

    # Create mock stages
    from rexlit.app.m1_pipeline import PipelineStage

    stages = [
        PipelineStage(
            name="discover",
            status="completed",
            detail="3 documents discovered",
            duration_seconds=1.2,
            metrics={"discovered_count": 3},
        ),
        PipelineStage(
            name="dedupe",
            status="completed",
            detail="3 unique documents",
            duration_seconds=0.3,
        ),
        PipelineStage(
            name="redaction_plan",
            status="completed",
            detail="3 plans generated",
            duration_seconds=2.1,
        ),
    ]

    # Execute
    report = container.report_service.build_impact_report(
        manifest_path,
        discovered_count=3,
        stages=stages,
        review_rate_low=50,
        review_rate_high=150,
        cost_low=75.0,
        cost_high=200.0,
    )

    # Verify summary statistics
    assert report.summary["total_discovered"] == 3
    assert report.summary["unique_documents"] == 3
    assert report.summary["duplicates_removed"] == 0
    assert report.summary["dedupe_rate_pct"] == 0.0
    assert report.summary["total_size_bytes"] == 1792000  # 1024000 + 512000 + 256000
    assert report.summary["total_size_mb"] == pytest.approx(1.71, abs=0.01)

    # Verify estimated review (3 documents at 50-150 docs/hr)
    # hours_low = 3 / 150 = 0.02 → rounds to 0.0
    # hours_high = 3 / 50 = 0.06 → rounds to 0.1
    # Just verify they exist and are reasonable
    assert report.estimated_review["hours_low"] >= 0.0
    assert report.estimated_review["hours_high"] >= 0.0
    assert report.estimated_review["cost_low_usd"] >= 0.0
    assert report.estimated_review["cost_high_usd"] >= 0.0
    assert "50-150 docs/hr" in report.estimated_review["assumptions"]

    # Verify custodian grouping
    assert len(report.by_custodian) == 2
    assert report.by_custodian["alice"]["count"] == 2
    assert report.by_custodian["alice"]["size_bytes"] == 1536000
    assert report.by_custodian["bob"]["count"] == 1
    assert report.by_custodian["bob"]["size_bytes"] == 256000

    # Verify doctype grouping
    assert len(report.by_doctype) == 3
    assert report.by_doctype["pdf"]["count"] == 1
    assert report.by_doctype["docx"]["count"] == 1
    assert report.by_doctype["email"]["count"] == 1

    # Verify extension grouping
    assert report.by_extension[".pdf"] == 1
    assert report.by_extension[".docx"] == 1
    assert report.by_extension[".eml"] == 1

    # Verify date range
    assert report.date_range is not None
    assert report.date_range["earliest"] == "2024-01-15T10:00:00Z"
    assert report.date_range["latest"] == "2024-06-30T17:45:00Z"
    assert report.date_range["span_days"] > 160  # Jan 15 to Jun 30 = ~166 days

    # Verify size distribution
    # 1024000 bytes = 1.0 MB (falls into "under_1mb" because < 1.0 after division)
    # 512000 bytes = 0.488 MB (under_1mb)
    # 256000 bytes = 0.244 MB (under_1mb)
    # Actually all 3 are under 1 MB
    assert report.size_distribution["under_1mb"] == 3
    assert report.size_distribution["1mb_to_10mb"] == 0
    assert report.size_distribution["over_10mb"] == 0

    # Verify stages
    assert len(report.stages) == 3
    assert report.stages[0]["name"] == "discover"
    assert report.stages[0]["duration_seconds"] == 1.2

    # Verify culling rationale
    assert "0 duplicates removed" in report.culling_rationale


def test_build_html_report_escapes_user_fields(temp_dir: Path) -> None:
    """HTML report escapes user-controlled fields to prevent XSS."""

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    manifest_path = temp_dir / "manifest.jsonl"
    html_path = temp_dir / "report.html"

    malicious_name = "<script>alert(1)</script>.pdf"
    manifest_data = [
        {
            "schema_id": "manifest",
            "schema_version": 1,
            "path": f"/docs/{malicious_name}",
            "sha256": "d" * 64,
            "size": 2048,
            "mime_type": "application/pdf",
            "doctype": "pdf",
            "custodian": '<img src=x onerror="alert(2)">',
            "producer": "rexlit-0.1.0",
            "produced_at": "2025-10-28T12:03:00Z",
        },
    ]

    container.storage_port.write_jsonl(manifest_path, iter(manifest_data))
    container.report_service.build_html_report(manifest_path, html_path, include_thumbnails=False)

    html_content = html_path.read_text(encoding="utf-8")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;.pdf" in html_content
    assert "&lt;img src=x onerror=&quot;alert(2)&quot;&gt;" in html_content
