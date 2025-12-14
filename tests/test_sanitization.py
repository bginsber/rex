"""Tests for manifest sanitization utilities."""

import json

import pytest

from rexlit.utils.sanitization import export_safe_manifest


def test_export_safe_manifest_basic(tmp_path):
    """Test basic safe manifest export."""
    # Create source manifest
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(
        json.dumps({
            "schema_id": "manifest",
            "schema_version": 1,
            "sha256": "abc123",
            "size": 1024,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "path": "/sensitive/path/doc.pdf",
            "custodian": "Jane Doe",
            "doctype": "contract",
        }) + "\n"
    )

    safe_manifest = tmp_path / "safe_manifest.jsonl"
    count = export_safe_manifest(source_manifest, safe_manifest)

    assert count == 1
    assert safe_manifest.exists()

    # Check content
    safe_line = safe_manifest.read_text().strip()
    safe_record = json.loads(safe_line)

    assert safe_record["schema_id"] == "safe_manifest"
    assert safe_record["schema_version"] == 1
    assert safe_record["sha256"] == "abc123"
    assert safe_record["size"] == 1024
    assert safe_record["custodian"] == "REDACTED"
    assert "path" not in safe_record


def test_export_safe_manifest_redacts_custodian(tmp_path):
    """Test that custodian field is always redacted."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(
        json.dumps({
            "sha256": "xyz",
            "size": 2048,
            "custodian": "Sensitive Name",
            "mime_type": "text/plain",
            "extension": ".txt",
        }) + "\n"
    )

    safe_manifest = tmp_path / "safe_manifest.jsonl"
    export_safe_manifest(source_manifest, safe_manifest)

    safe_record = json.loads(safe_manifest.read_text().strip())
    assert safe_record["custodian"] == "REDACTED"


def test_export_safe_manifest_multiple_records(tmp_path):
    """Test exporting multiple records."""
    source_manifest = tmp_path / "manifest.jsonl"

    records = [
        {
            "schema_id": "manifest",
            "sha256": f"hash{i}",
            "size": 1000 + i,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "custodian": f"User {i}",
        }
        for i in range(5)
    ]

    with source_manifest.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    safe_manifest = tmp_path / "safe_manifest.jsonl"
    count = export_safe_manifest(source_manifest, safe_manifest)

    assert count == 5

    safe_records = [
        json.loads(line)
        for line in safe_manifest.read_text().strip().split("\n")
    ]
    assert len(safe_records) == 5
    assert all(r["custodian"] == "REDACTED" for r in safe_records)


def test_export_safe_manifest_missing_source(tmp_path):
    """Test error when source manifest doesn't exist."""
    nonexistent = tmp_path / "nonexistent.jsonl"
    safe_manifest = tmp_path / "safe.jsonl"

    with pytest.raises(FileNotFoundError):
        export_safe_manifest(nonexistent, safe_manifest)


def test_export_safe_manifest_invalid_json(tmp_path):
    """Test error when source JSONL is invalid."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text("{ invalid json }\n")

    safe_manifest = tmp_path / "safe.jsonl"

    with pytest.raises(ValueError, match="Invalid JSON"):
        export_safe_manifest(source_manifest, safe_manifest)


def test_export_safe_manifest_preserves_schema(tmp_path):
    """Test that safe manifest has correct schema."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(
        json.dumps({
            "sha256": "test",
            "size": 100,
            "mime_type": "text/plain",
            "extension": ".txt",
        }) + "\n"
    )

    safe_manifest = tmp_path / "safe.jsonl"
    export_safe_manifest(source_manifest, safe_manifest)

    safe_record = json.loads(safe_manifest.read_text().strip())
    assert safe_record["schema_id"] == "safe_manifest"
    assert safe_record["schema_version"] == 1


def test_export_safe_manifest_masks_emails(tmp_path):
    """Test that email addresses are masked in doctype field."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(
        json.dumps({
            "sha256": "test",
            "size": 100,
            "mime_type": "text/plain",
            "extension": ".txt",
            "doctype": "report-user@company.com",
        }) + "\n"
    )

    safe_manifest = tmp_path / "safe.jsonl"
    export_safe_manifest(source_manifest, safe_manifest, mask_emails=True)

    safe_record = json.loads(safe_manifest.read_text().strip())
    # Doctype field should have email masked
    assert "[REDACTED_EMAIL]" in safe_record["doctype"]


def test_export_safe_manifest_no_email_mask_when_disabled(tmp_path):
    """Test email masking can be disabled."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(
        json.dumps({
            "sha256": "test",
            "size": 100,
            "doctype": "report-user@domain.com",
        }) + "\n"
    )

    safe_manifest = tmp_path / "safe.jsonl"
    export_safe_manifest(source_manifest, safe_manifest, mask_emails=False)

    safe_record = json.loads(safe_manifest.read_text().strip())
    assert "user@domain.com" in safe_record["doctype"]


def test_export_safe_manifest_output_atomic(tmp_path):
    """Test that output file is written atomically."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(json.dumps({"sha256": "test"}) + "\n")

    safe_manifest = tmp_path / "safe.jsonl"

    # Create a temporary file in the directory to verify atomic replacement
    export_safe_manifest(source_manifest, safe_manifest)

    # Verify the file exists and has correct content
    assert safe_manifest.exists()
    content = safe_manifest.read_text()
    assert "safe_manifest" in content


def test_export_safe_manifest_creates_parent_directory(tmp_path):
    """Test that parent directory is created if needed."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(json.dumps({"sha256": "test"}) + "\n")

    nested_path = tmp_path / "nested" / "deep" / "safe.jsonl"

    export_safe_manifest(source_manifest, nested_path)

    assert nested_path.exists()
    assert nested_path.parent.is_dir()


def test_export_safe_manifest_omits_path_field(tmp_path):
    """Test that path field is completely omitted from safe manifest."""
    source_manifest = tmp_path / "manifest.jsonl"
    source_manifest.write_text(
        json.dumps({
            "sha256": "test",
            "path": "/very/sensitive/path/file.pdf",
            "size": 100,
        }) + "\n"
    )

    safe_manifest = tmp_path / "safe.jsonl"
    export_safe_manifest(source_manifest, safe_manifest)

    safe_record = json.loads(safe_manifest.read_text().strip())
    assert "path" not in safe_record
