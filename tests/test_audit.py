"""Tests for audit ledger functionality."""

import json
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
    assert entry.sequence == 1
    assert entry.signature is not None

    # Verify file was created
    assert ledger_path.exists()
    # Metadata should also be persisted
    assert ledger_path.with_suffix(".meta").exists()


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
    assert [entry.sequence for entry in entries] == [1, 2, 3]


def test_audit_ledger_verify(temp_dir: Path):
    """Test verifying ledger integrity."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Log entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])

    # Verify integrity
    is_valid, error = ledger.verify()
    assert is_valid is True
    assert error is None


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
    is_valid, error = ledger.verify()
    assert is_valid is True
    assert error is None


# Hash Chain Integrity Tests


def test_audit_entry_has_previous_hash():
    """Test that audit entries include previous_hash field."""
    entry = AuditEntry(
        timestamp="2025-10-22T10:00:00Z",
        operation="ingest",
        inputs=["/path/to/file.pdf"],
        outputs=["abc123"],
        args={"recursive": True},
        versions={"rexlit": "0.1.0"},
    )

    # Default should be genesis hash
    assert entry.previous_hash == "0" * 64


def test_audit_chain_first_entry_genesis_hash(temp_dir: Path):
    """Test that first entry has genesis previous_hash."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    entry = ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])

    # First entry should have genesis hash
    assert entry.previous_hash == "0" * 64
    assert entry.sequence == 1
    assert entry.signature is not None


def test_audit_chain_entries_linked(temp_dir: Path):
    """Test that entries are properly linked in hash chain."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    entry1 = ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    entry2 = ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    entry3 = ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    # Verify chain links
    assert entry1.previous_hash == "0" * 64
    assert entry2.previous_hash == entry1.entry_hash
    assert entry3.previous_hash == entry2.entry_hash
    assert [entry.sequence for entry in (entry1, entry2, entry3)] == [1, 2, 3]


def test_audit_chain_hash_includes_previous_hash(temp_dir: Path):
    """Test that entry hash computation includes previous_hash."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    entry1 = ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    entry2 = ledger.log(operation="op2", inputs=["file1.pdf"], outputs=["hash1"])

    # Entries with same data but different previous_hash should have different hashes
    # (This would be same content but entry2 has entry1's hash as previous_hash)
    assert entry1.entry_hash != entry2.entry_hash


def test_audit_tampering_modified_entry_content(temp_dir: Path):
    """Test detection of modified entry content."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Create ledger with entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    # Read and modify entry content
    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Tamper with middle entry - change operation name
    entry_data = json.loads(lines[1])
    entry_data["operation"] = "TAMPERED"

    # Write back tampered ledger
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(lines[0])
        f.write(json.dumps(entry_data) + "\n")
        f.write(lines[2])

    # Verify should detect tampering
    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    lowered = error.lower()
    assert "invalid hash" in lowered or "breaks hash chain" in lowered


def test_audit_tampering_deleted_middle_entry(temp_dir: Path):
    """Test detection of deleted entry from middle of chain."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Create ledger with entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])
    ledger.log(operation="op4", inputs=["file4.pdf"], outputs=["hash4"])

    # Read entries
    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Delete middle entries (op2 and op3)
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(lines[0])  # op1
        f.write(lines[3])  # op4

    # Verify should detect broken chain
    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    lowered = error.lower()
    assert "invalid hash" in lowered or "breaks hash chain" in lowered


def test_audit_tampering_reordered_entries(temp_dir: Path):
    """Test detection of reordered entries."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Create ledger with entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    # Read entries
    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Reorder entries (swap op2 and op3)
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(lines[0])  # op1
        f.write(lines[2])  # op3 (should be op2)
        f.write(lines[1])  # op2 (should be op3)

    # Verify should detect broken chain
    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    lowered = error.lower()
    assert "invalid hash" in lowered or "breaks hash chain" in lowered


def test_audit_tampering_duplicated_entry(temp_dir: Path):
    """Test detection of duplicated entries."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Create ledger with entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    # Read entries
    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Duplicate middle entry
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(lines[0])  # op1
        f.write(lines[1])  # op2
        f.write(lines[1])  # op2 again (duplicate)
        f.write(lines[2])  # op3

    # Verify should detect broken chain (duplicate has wrong previous_hash)
    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    lowered = error.lower()
    assert "invalid hash" in lowered or "breaks hash chain" in lowered


def test_audit_tampering_invalid_genesis_hash(temp_dir: Path):
    """Test detection of invalid genesis hash."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)

    # Create ledger with entries
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])

    # Read and modify first entry's previous_hash
    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    entry_data = json.loads(lines[0])
    entry_data["previous_hash"] = "abc123"  # Invalid genesis hash

    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(entry_data) + "\n")

    # Verify should detect invalid genesis hash
    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    lowered = error.lower()
    assert "invalid hash" in lowered or "breaks hash chain" in lowered


def test_audit_chain_persistence_across_ledger_instances(temp_dir: Path):
    """Test that hash chain persists across ledger instances."""
    ledger_path = temp_dir / "audit.jsonl"

    # Create first ledger and log entries
    ledger1 = AuditLedger(ledger_path)
    _entry1 = ledger1.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    entry2 = ledger1.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])

    # Create new ledger instance and log more entries
    ledger2 = AuditLedger(ledger_path)
    entry3 = ledger2.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    # Verify chain continuity
    assert entry3.previous_hash == entry2.entry_hash

    # Verify entire chain
    ledger3 = AuditLedger(ledger_path)
    is_valid, error = ledger3.verify()
    assert is_valid is True
    assert error is None


def test_audit_metadata_mismatch_detected(temp_dir: Path):
    """Tampering with metadata must be detected."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])

    metadata_path = ledger_path.with_suffix(".meta")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["last_hash"] = "tampered"

    # Avoid recomputing HMAC to simulate tampering
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    assert "metadata" in error.lower()


def test_audit_detects_missing_ledger_file(temp_dir: Path):
    """Deleting the ledger file must be detected."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])

    ledger_path.unlink()

    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    assert "missing" in error.lower()


def test_audit_detects_truncation(temp_dir: Path):
    """Removing tail entries must be detected."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])
    ledger.log(operation="op3", inputs=["file3.pdf"], outputs=["hash3"])

    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Remove last entry
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.writelines(lines[:-1])

    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    assert "metadata" in error.lower() or "sequence" in error.lower()


def test_audit_detects_signature_tamper(temp_dir: Path):
    """Tampering with a signature must be detected."""
    ledger_path = temp_dir / "audit.jsonl"
    ledger = AuditLedger(ledger_path)
    ledger.log(operation="op1", inputs=["file1.pdf"], outputs=["hash1"])
    ledger.log(operation="op2", inputs=["file2.pdf"], outputs=["hash2"])

    with open(ledger_path, encoding="utf-8") as f:
        lines = f.readlines()

    entry = json.loads(lines[1])
    entry["signature"] = "00" * 32

    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(lines[0])
        f.write(json.dumps(entry) + "\n")

    ledger2 = AuditLedger(ledger_path)
    is_valid, error = ledger2.verify()
    assert is_valid is False
    assert error is not None
    assert "signature" in error.lower()
