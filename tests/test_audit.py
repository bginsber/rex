"""Tests for audit ledger functionality."""

from pathlib import Path

from rexlit.audit.ledger import AuditEntry, AuditLedger


def test_audit_entry_hash():
    """Test that audit entry hash is computed correctly."""
    entry = AuditEntry(
        timestamp="2025-10-22T10:00:00Z",
        operation="ingest",
        inputs=["/path/to/file.pdf"],
        outputs=["abc123"],
        args={"recursive": True},
        versions={"rexlit": "0.1.0"},
    )

    assert entry.entry_hash is not None
    assert len(entry.entry_hash) == 64  # SHA-256 hex digest length

    # Hash should be deterministic
    expected_hash = entry.compute_hash()
    assert entry.entry_hash == expected_hash


def test_audit_entry_hash_consistency():
    """Test that identical entries produce identical hashes."""
    entry1 = AuditEntry(
        timestamp="2025-10-22T10:00:00Z",
        operation="ingest",
        inputs=["/path/to/file.pdf"],
        outputs=["abc123"],
        args={"recursive": True},
        versions={"rexlit": "0.1.0"},
    )

    entry2 = AuditEntry(
        timestamp="2025-10-22T10:00:00Z",
        operation="ingest",
        inputs=["/path/to/file.pdf"],
        outputs=["abc123"],
        args={"recursive": True},
        versions={"rexlit": "0.1.0"},
    )

    assert entry1.entry_hash == entry2.entry_hash


def test_audit_ledger_log(temp_dir: Path):
    """Test logging operations to audit ledger."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    entry = ledger.log(
        operation="test_operation",
        inputs=["/input/file.pdf"],
        outputs=["hash123"],
        args={"param": "value"},
    )

    assert entry.operation == "test_operation"
    assert entry.inputs == ["/input/file.pdf"]
    assert entry.outputs == ["hash123"]
    assert entry.args == {"param": "value"}
    assert "rexlit" in entry.versions

    # Verify file was created
    assert ledger_path.exists()


def test_audit_ledger_read_all(temp_dir: Path):
    """Test reading all entries from ledger."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Log multiple entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    # Read all entries
    entries = ledger.read_all()
    assert len(entries) == 3
    assert entries[0].operation == "op1"
    assert entries[1].operation == "op2"
    assert entries[2].operation == "op3"


def test_audit_ledger_verify(temp_dir: Path):
    """Test verifying ledger integrity."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Log entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])

    # Verify integrity
    assert ledger.verify() is True


def test_audit_ledger_get_by_operation(temp_dir: Path):
    """Test filtering entries by operation."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    ledger.log(operation="ingest", inputs=["file1.pdf"])
    ledger.log(operation="ocr", inputs=["file2.pdf"])
    ledger.log(operation="ingest", inputs=["file3.pdf"])

    ingest_entries = ledger.get_by_operation("ingest")
    assert len(ingest_entries) == 2
    assert all(e.operation == "ingest" for e in ingest_entries)


def test_audit_ledger_get_by_input(temp_dir: Path):
    """Test filtering entries by input."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    ledger.log(operation="ingest", inputs=["file1.pdf", "file2.pdf"])
    ledger.log(operation="ocr", inputs=["file2.pdf"])
    ledger.log(operation="bates", inputs=["file3.pdf"])

    entries = ledger.get_by_input("file2.pdf")
    assert len(entries) == 2


def test_audit_ledger_empty(temp_dir: Path):
    """Test reading empty ledger."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    entries = ledger.read_all()
    assert len(entries) == 0

    # Verify should return True for empty ledger
    assert ledger.verify() is True
