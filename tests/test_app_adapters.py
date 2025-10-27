"""Contract tests covering application adapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pytest

from rexlit.app.adapters import (
    HashDeduper,
    JSONLineRedactionPlanner,
    SequentialBatesPlanner,
    ZipPackager,
)
from rexlit.app.ports import DocumentRecord
from rexlit.config import Settings
from rexlit.utils.crypto import decrypt_blob, encrypt_blob
from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.plans import compute_redaction_plan_id


def build_document_record(path: Path) -> DocumentRecord:
    """Construct a ``DocumentRecord`` for the given path."""

    resolved = path.resolve()
    stat = resolved.stat()
    sha256 = compute_sha256_file(resolved)

    return DocumentRecord(
        path=str(resolved),
        sha256=sha256,
        size=stat.st_size,
        mime_type="text/plain",
        extension=resolved.suffix or "",
        mtime=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        custodian=None,
        doctype=None,
    )


def make_records(paths: Iterable[Path]) -> list[DocumentRecord]:
    """Helper to build ``DocumentRecord`` list from paths."""

    return [build_document_record(path) for path in paths]


def _read_encrypted_plan(path: Path, key: bytes) -> dict[str, object]:
    """Decrypt and return the redaction plan entry stored at ``path``."""
    token = path.read_text(encoding="utf-8").splitlines()[0]
    decrypted = decrypt_blob(token.encode("utf-8"), key=key)
    return json.loads(decrypted.decode("utf-8"))


def test_redaction_planner_generates_deterministic_plan(temp_dir: Path) -> None:
    """JSONLineRedactionPlanner emits deterministic plans with plan_id."""

    source = temp_dir / "source.txt"
    source.write_text("adapter redaction content")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    planner = JSONLineRedactionPlanner(settings=settings)

    plan_path = planner.plan(source)
    assert plan_path.exists()
    assert plan_path.suffix == ".enc"

    raw_line = plan_path.read_text(encoding="utf-8").splitlines()[0]
    assert not raw_line.startswith("{"), "Redaction plan should be encrypted on disk."

    key = settings.get_redaction_plan_key()
    entry = _read_encrypted_plan(plan_path, key)

    expected_plan_id = compute_redaction_plan_id(
        document_path=source,
        content_hash=compute_sha256_file(source),
    )
    assert entry["plan_id"] == expected_plan_id
    assert entry["schema_id"] == "redaction_plan"
    assert entry["schema_version"] == 1

    # Re-running planner should succeed without modifying fingerprint.
    planner.plan(source)
    second_entry = _read_encrypted_plan(plan_path, key)
    assert second_entry["plan_id"] == expected_plan_id


def test_redaction_planner_rejects_tampered_plan(temp_dir: Path) -> None:
    """Planner refuses to overwrite when provenance fails validation."""

    source = temp_dir / "tamper.txt"
    source.write_text("redaction tamper content")

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    planner = JSONLineRedactionPlanner(settings=settings)
    plan_path = planner.plan(source)

    key = settings.get_redaction_plan_key()
    entry = _read_encrypted_plan(plan_path, key)
    entry["plan_id"] = "0" * 64
    payload = json.dumps(
        entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    tampered = encrypt_blob(payload, key=key).decode("utf-8")
    plan_path.write_text(tampered + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        planner.plan(source)

    assert "plan_id mismatch" in str(excinfo.value)


def test_hash_deduper_eliminates_duplicate_hashes(temp_dir: Path) -> None:
    """HashDeduper emits first instance of each unique SHA-256."""

    file_a = temp_dir / "a.txt"
    file_b = temp_dir / "b.txt"
    file_c = temp_dir / "c.txt"
    file_a.write_text("duplicate payload")
    file_b.write_text("duplicate payload")
    file_c.write_text("unique payload")

    records = make_records([file_a, file_b, file_c])
    deduper = HashDeduper()
    unique = list(deduper.dedupe(records))

    assert len(unique) == 2
    hashes = {record.sha256 for record in unique}
    assert len(hashes) == 2
    assert compute_sha256_file(file_c) in hashes
    # Ensure deterministic ordering by verifying sorted paths.
    expected_order = sorted(unique, key=lambda doc: (doc.sha256, doc.path))
    assert [record.path for record in unique] == [record.path for record in expected_order]


def test_sequential_bates_planner_persists_plan(temp_dir: Path) -> None:
    """SequentialBatesPlanner produces schema-stamped JSONL output."""

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )

    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    doc1 = docs_dir / "doc1.txt"
    doc2 = docs_dir / "doc2.txt"
    doc1.write_text("doc1 content")
    doc2.write_text("doc2 content")

    planner = SequentialBatesPlanner(settings=settings, prefix="RXL")
    plan = planner.plan(make_records([doc1, doc2]))

    expected_path = settings.get_data_dir() / "bates" / "bates_plan.jsonl"
    assert plan.path == expected_path
    assert plan.path.exists()
    assert len(plan.assignments) == 2
    assert plan.assignments[0].bates_id == "RXL-000001"
    assert plan.assignments[1].bates_id == "RXL-000002"

    first_entry = json.loads(plan.path.read_text(encoding="utf-8").splitlines()[0])
    assert first_entry["schema_id"] == "bates_map"
    assert first_entry["schema_version"] == 1


def test_sequential_bates_planner_detects_hash_mismatch(temp_dir: Path) -> None:
    """SequentialBatesPlanner validates document hashes before persisting."""

    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )

    doc = temp_dir / "doc.txt"
    doc.write_text("original content")
    record = build_document_record(doc)

    # Change file contents to trigger hash mismatch.
    doc.write_text("mutated content")

    planner = SequentialBatesPlanner(settings=settings)

    with pytest.raises(ValueError) as excinfo:
        planner.plan([record])

    assert "Document hash mismatch" in str(excinfo.value)


def test_zip_packager_creates_archive(temp_dir: Path) -> None:
    """ZipPackager archives artifacts under deterministic name."""

    artifact_dir = temp_dir / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "file.txt").write_text("zip me")

    packs_dir = temp_dir / "packs"
    packer = ZipPackager(packs_dir)

    archive_path = packer.pack(artifact_dir)
    assert archive_path.exists()
    assert archive_path.suffix == ".zip"

    from zipfile import ZipFile

    with ZipFile(archive_path) as archive:
        assert "file.txt" in archive.namelist()
