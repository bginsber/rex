"""Tests for schema stamping, migrations, and validation utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rexlit.utils.schema import (
    SchemaMigrationError,
    SchemaValidationError,
    migrate_file,
    migrate_record,
    register_schema_migration,
    schema_migrations,
    stamp_metadata,
    strip_schema_metadata,
    validate_file,
)


@pytest.fixture(autouse=True)
def reset_schema_registry():
    """Ensure each test starts with a clean migration registry."""
    schema_migrations.clear()
    yield
    schema_migrations.clear()


def _base_manifest_payload() -> dict[str, str | int | None]:
    return {
        "path": "/tmp/example.pdf",
        "sha256": "a" * 64,
        "size": 1024,
        "mime_type": "application/pdf",
        "doctype": "pdf",
        "custodian": None,
    }


def _register_manifest_v2_migration() -> None:
    def v1_to_v2(payload: dict[str, object]) -> dict[str, object]:
        upgraded = dict(payload)
        upgraded.setdefault("language", "en")
        upgraded.setdefault("ocr_confidence", 0.0)
        return upgraded

    register_schema_migration(
        "manifest",
        from_version=1,
        to_version=2,
        migrate=v1_to_v2,
    )


def test_migrate_record_applies_registered_steps():
    _register_manifest_v2_migration()

    record_v1 = stamp_metadata(_base_manifest_payload(), schema_id="manifest", schema_version=1)
    upgraded = migrate_record("manifest", record_v1, 2)

    assert upgraded["schema_version"] == 2
    assert upgraded["schema_id"] == "manifest"
    assert upgraded["language"] == "en"
    assert upgraded["ocr_confidence"] == 0.0
    assert upgraded["content_hash"] != record_v1["content_hash"]
    assert strip_schema_metadata(upgraded)["language"] == "en"


def test_migrate_record_without_path_raises():
    record_v1 = stamp_metadata(_base_manifest_payload(), schema_id="manifest", schema_version=1)

    with pytest.raises(SchemaMigrationError):
        migrate_record("manifest", record_v1, 2)


def test_migrate_file_updates_artifact(tmp_path: Path):
    _register_manifest_v2_migration()
    record_v1 = stamp_metadata(_base_manifest_payload(), schema_id="manifest", schema_version=1)

    artifact = tmp_path / "manifest.jsonl"
    artifact.write_text(json.dumps(record_v1) + "\n", encoding="utf-8")

    migrate_file(artifact, "manifest", 2)

    migrated = json.loads(artifact.read_text(encoding="utf-8").splitlines()[0])
    assert migrated["schema_version"] == 2
    assert migrated["language"] == "en"


def test_validate_file_raises_with_detailed_errors(tmp_path: Path):
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        pytest.skip("jsonschema dependency not installed")

    record_v1 = stamp_metadata(_base_manifest_payload(), schema_id="manifest", schema_version=1)
    # Corrupt schema_version to violate manifest@1 const requirement.
    record_v1["schema_version"] = 99

    artifact = tmp_path / "invalid.jsonl"
    artifact.write_text(json.dumps(record_v1) + "\n", encoding="utf-8")

    with pytest.raises(SchemaValidationError) as excinfo:
        validate_file(artifact, "manifest", 1)

    message = str(excinfo.value)
    assert "manifest@1" in message
    assert "schema_version" in message
    assert "invalid.jsonl" in message

    valid, invalid = validate_file(artifact, "manifest", 1, raise_on_error=False)
    assert valid == 0
    assert invalid == 1
