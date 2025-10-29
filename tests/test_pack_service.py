"""Tests for PackService export_load_file functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rexlit.bootstrap import bootstrap_application
from rexlit.config import Settings


def test_export_load_file_dat_format(temp_dir: Path) -> None:
    """export_load_file generates valid DAT format load file."""
    # Setup: Create a pack directory with metadata/documents.jsonl
    pack_dir = temp_dir / "pack"
    metadata_dir = pack_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    # Create sample manifest records
    manifest_records = [
        {
            "path": "/path/to/doc1.pdf",
            "sha256": "abc123def456",
            "size": 1024,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "mtime": "2025-10-28T10:00:00Z",
            "custodian": "John Doe",
            "doctype": "pdf",
        },
        {
            "path": "/path/to/doc2.docx",
            "sha256": "xyz789ghi012",
            "size": 2048,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "extension": ".docx",
            "mtime": "2025-10-28T11:00:00Z",
            "custodian": "Jane Smith",
            "doctype": "docx",
        },
    ]

    # Write metadata/documents.jsonl
    documents_path = metadata_dir / "documents.jsonl"
    with documents_path.open("w", encoding="utf-8") as f:
        for record in manifest_records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    # Create PackService
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    # Export load file
    output_path = temp_dir / "loadfile.dat"
    result_path = container.pack_service.export_load_file(
        pack_dir, output_path, format="dat"
    )

    # Verify output
    assert result_path == output_path
    assert output_path.exists()

    # Read and verify content
    content = output_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    # Should have header + 2 data rows
    assert len(lines) == 3

    # Verify header
    header = lines[0]
    expected_fields = [
        "DOCID",
        "BEGDOC",
        "ENDDOC",
        "CUSTODIAN",
        "DOCTYPE",
        "FILEPATH",
        "FILEEXT",
        "FILESIZE",
        "DATEMODIFIED",
        "SHA256",
    ]
    assert header == "|".join(expected_fields)

    # Verify first data row
    row1 = lines[1].split("|")
    assert row1[0] == "abc123def456"  # DOCID
    assert row1[3] == "John Doe"  # CUSTODIAN
    assert row1[4] == "pdf"  # DOCTYPE
    assert row1[5] == "/path/to/doc1.pdf"  # FILEPATH
    assert row1[6] == ".pdf"  # FILEEXT
    assert row1[7] == "1024"  # FILESIZE

    # Verify second data row
    row2 = lines[2].split("|")
    assert row2[0] == "xyz789ghi012"  # DOCID
    assert row2[3] == "Jane Smith"  # CUSTODIAN
    assert row2[4] == "docx"  # DOCTYPE


def test_export_load_file_missing_manifest(temp_dir: Path) -> None:
    """export_load_file raises FileNotFoundError when metadata is missing."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.dat"

    with pytest.raises(FileNotFoundError) as excinfo:
        container.pack_service.export_load_file(pack_dir, output_path, format="dat")

    assert "Pack metadata documents not found" in str(excinfo.value)


def test_export_load_file_empty_manifest(temp_dir: Path) -> None:
    """export_load_file raises ValueError when metadata is empty."""
    pack_dir = temp_dir / "pack"
    metadata_dir = pack_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    # Create empty documents.jsonl
    documents_path = metadata_dir / "documents.jsonl"
    documents_path.write_text("", encoding="utf-8")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.dat"

    with pytest.raises(ValueError) as excinfo:
        container.pack_service.export_load_file(pack_dir, output_path, format="dat")

    assert "Pack metadata is empty" in str(excinfo.value)


def test_export_load_file_invalid_format(temp_dir: Path) -> None:
    """export_load_file raises ValueError for invalid format."""
    pack_dir = temp_dir / "pack"
    pack_dir.mkdir(parents=True)

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.txt"

    with pytest.raises(ValueError) as excinfo:
        container.pack_service.export_load_file(
            pack_dir, output_path, format="invalid"
        )

    assert "Unsupported load file format" in str(excinfo.value)
    assert "invalid" in str(excinfo.value)


def test_export_load_file_opticon_not_implemented(temp_dir: Path) -> None:
    """export_load_file raises NotImplementedError for opticon format."""
    pack_dir = temp_dir / "pack"
    metadata_dir = pack_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    # Create minimal documents.jsonl
    documents_path = metadata_dir / "documents.jsonl"
    documents_path.write_text(
        json.dumps({"path": "/test.pdf", "sha256": "abc123"}) + "\n",
        encoding="utf-8",
    )

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.opt"

    with pytest.raises(NotImplementedError) as excinfo:
        container.pack_service.export_load_file(pack_dir, output_path, format="opticon")

    assert "opticon" in str(excinfo.value)
    assert "not yet implemented" in str(excinfo.value)


def test_export_load_file_lfp_not_implemented(temp_dir: Path) -> None:
    """export_load_file raises NotImplementedError for lfp format."""
    pack_dir = temp_dir / "pack"
    metadata_dir = pack_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    # Create minimal documents.jsonl
    documents_path = metadata_dir / "documents.jsonl"
    documents_path.write_text(
        json.dumps({"path": "/test.pdf", "sha256": "abc123"}) + "\n",
        encoding="utf-8",
    )

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.lfp"

    with pytest.raises(NotImplementedError) as excinfo:
        container.pack_service.export_load_file(pack_dir, output_path, format="lfp")

    assert "lfp" in str(excinfo.value)
    assert "not yet implemented" in str(excinfo.value)


def test_export_load_file_escapes_pipe_characters(temp_dir: Path) -> None:
    """export_load_file properly escapes pipe characters in data."""
    pack_dir = temp_dir / "pack"
    metadata_dir = pack_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    # Create manifest with pipe character in path
    manifest_records = [
        {
            "path": "/path/to/file|with|pipes.pdf",
            "sha256": "abc123",
            "size": 1024,
            "extension": ".pdf",
            "mtime": "2025-10-28T10:00:00Z",
            "custodian": "John|Doe",
            "doctype": "pdf",
        }
    ]

    documents_path = metadata_dir / "documents.jsonl"
    with documents_path.open("w", encoding="utf-8") as f:
        for record in manifest_records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.dat"
    container.pack_service.export_load_file(pack_dir, output_path, format="dat")

    content = output_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    # Data should have escaped pipes
    data_line = lines[1]
    assert "\\|" in data_line
    assert "/path/to/file\\|with\\|pipes.pdf" in data_line
    assert "John\\|Doe" in data_line


def test_export_load_file_handles_missing_optional_fields(temp_dir: Path) -> None:
    """export_load_file handles missing optional fields gracefully."""
    pack_dir = temp_dir / "pack"
    metadata_dir = pack_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    # Create manifest with minimal fields (no custodian or doctype)
    manifest_records = [
        {
            "path": "/path/to/doc.pdf",
            "sha256": "abc123",
            "size": 1024,
            "extension": ".pdf",
            "mtime": "2025-10-28T10:00:00Z",
        }
    ]

    documents_path = metadata_dir / "documents.jsonl"
    with documents_path.open("w", encoding="utf-8") as f:
        for record in manifest_records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    output_path = temp_dir / "loadfile.dat"
    container.pack_service.export_load_file(pack_dir, output_path, format="dat")

    content = output_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    # Should have header + 1 data row
    assert len(lines) == 2

    # Empty fields should be present (empty strings between delimiters)
    data_line = lines[1]
    fields = data_line.split("|")

    # CUSTODIAN (index 3) should be empty
    assert fields[3] == ""
    # DOCTYPE (index 4) should be empty
    assert fields[4] == ""
    # Other fields should be populated
    assert fields[0] == "abc123"  # DOCID
    assert fields[5] == "/path/to/doc.pdf"  # FILEPATH
