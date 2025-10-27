"""Schema validation, migration, and metadata stamping utilities."""

import hashlib
import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rexlit import __version__

SCHEMA_METADATA_FIELDS = {
    "schema_id",
    "schema_version",
    "producer",
    "produced_at",
    "content_hash",
}

MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""


class SchemaMigrationError(Exception):
    """Raised when schema migration cannot proceed."""


def strip_schema_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``record`` without schema metadata fields."""

    return {key: value for key, value in record.items() if key not in SCHEMA_METADATA_FIELDS}


@dataclass(frozen=True, slots=True)
class SchemaStamp:
    """Schema metadata applied to persisted records."""

    schema_id: str
    schema_version: int
    producer: str
    produced_at: str

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``payload`` augmented with schema metadata."""

        stamped = dict(payload)
        stamped["schema_id"] = self.schema_id
        stamped["schema_version"] = self.schema_version
        stamped["producer"] = self.producer
        stamped["produced_at"] = self.produced_at
        return stamped


def get_schema_path(schema_id: str, version: int = 1) -> Path:
    """Get path to schema file.

    Args:
        schema_id: Schema identifier (e.g., 'audit', 'manifest')
        version: Schema version (default: 1)

    Returns:
        Path to schema JSON file
    """
    schema_dir = Path(__file__).parent.parent / "schemas"
    return schema_dir / f"{schema_id}@{version}.json"


def load_schema(schema_id: str, version: int = 1) -> dict[str, Any]:
    """Load JSON schema.

    Args:
        schema_id: Schema identifier
        version: Schema version

    Returns:
        Parsed JSON schema

    Raises:
        FileNotFoundError: If schema file not found
    """
    schema_path = get_schema_path(schema_id, version)
    with open(schema_path) as f:
        return json.load(f)


def build_schema_stamp(
    *,
    schema_id: str,
    schema_version: int,
    producer: str | None = None,
    produced_at: str | None = None,
) -> SchemaStamp:
    """Construct a :class:`SchemaStamp` for reuse across writers."""

    default_producer = producer or f"rexlit-{__version__}"
    timestamp = produced_at or datetime.now(UTC).isoformat()
    return SchemaStamp(
        schema_id=schema_id,
        schema_version=schema_version,
        producer=default_producer,
        produced_at=timestamp,
    )


def stamp_metadata(
    record: dict[str, Any],
    schema_id: str,
    schema_version: int = 1,
    *,
    producer: str | None = None,
    produced_at: str | None = None,
) -> dict[str, Any]:
    """Add schema metadata and deterministic content hash to ``record``."""

    stamp = build_schema_stamp(
        schema_id=schema_id,
        schema_version=schema_version,
        producer=producer,
        produced_at=produced_at,
    )
    stamped = stamp.apply(record)

    content = {
        k: v
        for k, v in stamped.items()
        if k not in ("schema_id", "schema_version", "producer", "produced_at", "content_hash")
    }
    content_json = json.dumps(content, sort_keys=True)
    content_hash = hashlib.sha256(content_json.encode()).hexdigest()
    stamped["content_hash"] = content_hash

    return stamped


def stamp_records(
    records: Iterable[dict[str, Any]],
    schema_id: str,
    schema_version: int = 1,
    *,
    producer: str | None = None,
    produced_at: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield copies of ``records`` stamped with schema metadata."""

    for record in records:
        yield stamp_metadata(
            dict(record),
            schema_id,
            schema_version,
            producer=producer,
            produced_at=produced_at,
        )


def validate_record(record: dict[str, Any], schema_id: str, schema_version: int = 1) -> bool:
    """Validate record against schema.

    Args:
        record: Record to validate
        schema_id: Schema identifier
        schema_version: Schema version

    Returns:
        True if valid, False otherwise

    Note:
        In dev mode, raises ValueError on validation failure.
        In prod mode, logs warning and returns False.
    """
    try:
        # Lazy import to avoid hard dependency at module import time
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency misconfiguration
        raise SchemaValidationError(
            "Schema validation requires the 'jsonschema' package. "
            "Install RexLit with the 'dev' extras (pip install rexlit[dev])."
        ) from exc

    schema = load_schema(schema_id, schema_version)

    try:
        jsonschema.validate(record, schema)
    except jsonschema.ValidationError as exc:
        message = f"{schema_id}@{schema_version} validation failed: {exc.message}"
        raise SchemaValidationError(message) from exc
    except jsonschema.SchemaError as exc:  # pragma: no cover - schema authoring bug
        raise SchemaValidationError(
            f"Invalid schema definition for {schema_id}@{schema_version}: {exc}"
        ) from exc

    return True


def validate_file(
    path: Path,
    schema_id: str,
    schema_version: int = 1,
    *,
    raise_on_error: bool = True,
) -> tuple[int, int]:
    """Validate JSONL file against schema.

    Args:
        path: Path to JSONL file
        schema_id: Schema identifier
        schema_version: Schema version
        raise_on_error: Raise :class:`SchemaValidationError` when invalid records detected.

    Returns:
        Tuple of (valid_count, invalid_count)
    """
    valid_count = 0
    invalid_count = 0
    errors: list[str] = []

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                if validate_record(record, schema_id, schema_version):
                    valid_count += 1
            except json.JSONDecodeError as exc:
                invalid_count += 1
                errors.append(f"{path}:{line_num}: invalid JSON: {exc.msg}")
            except SchemaValidationError as exc:
                invalid_count += 1
                errors.append(f"{path}:{line_num}: {exc}")

    if errors and raise_on_error:
        raise SchemaValidationError(
            f"{schema_id}@{schema_version} validation encountered {len(errors)} error(s):\n"
            + "\n".join(errors)
        )
    return valid_count, invalid_count


@dataclass(frozen=True, slots=True)
class MigrationStep:
    """Represents a single schema migration step."""

    to_version: int
    migrate: MigrationFunc


class SchemaMigrationRegistry:
    """Registry of schema migrations keyed by ``schema_id`` and version."""

    def __init__(self) -> None:
        self._migrations: dict[str, dict[int, MigrationStep]] = {}

    def register(
        self,
        schema_id: str,
        *,
        from_version: int,
        to_version: int,
        migrate: MigrationFunc,
    ) -> None:
        """Register a migration step for ``schema_id``."""
        if to_version <= from_version:
            raise SchemaMigrationError(
                f"Invalid migration for {schema_id}: target version {to_version} "
                f"must be greater than source version {from_version}."
            )

        steps = self._migrations.setdefault(schema_id, {})
        if from_version in steps:
            existing = steps[from_version].to_version
            raise SchemaMigrationError(
                f"Migration for {schema_id} v{from_version}→v{existing} already registered."
            )

        steps[from_version] = MigrationStep(to_version=to_version, migrate=migrate)

    def migrate_record(
        self,
        schema_id: str,
        record: Mapping[str, Any],
        target_version: int,
        *,
        producer: str | None = None,
        produced_at: str | None = None,
    ) -> dict[str, Any]:
        """Upgrade ``record`` to ``target_version`` if migrations are available."""
        if not isinstance(record, Mapping):
            raise SchemaMigrationError("Only mapping types can be migrated.")

        record_schema = record.get("schema_id")
        if record_schema not in (None, schema_id):
            raise SchemaMigrationError(
                f"Cannot migrate record stamped as '{record_schema}' using schema '{schema_id}'."
            )

        current_version = int(record.get("schema_version", 1))
        if current_version > target_version:
            raise SchemaMigrationError(
                f"Downgrades are not supported (current v{current_version}, target v{target_version})."
            )

        if current_version == target_version:
            return dict(record)

        steps = self._migrations.get(schema_id, {})
        payload = dict(strip_schema_metadata(record))

        while current_version < target_version:
            step = steps.get(current_version)
            if step is None:
                raise SchemaMigrationError(
                    f"No migration path from v{current_version} to v{target_version} "
                    f"registered for schema '{schema_id}'."
                )

            next_payload = step.migrate(dict(payload))
            if not isinstance(next_payload, dict):
                raise SchemaMigrationError(
                    f"Migration for {schema_id} v{current_version}→v{step.to_version} "
                    "must return a dict."
                )

            payload = next_payload
            current_version = step.to_version

        return stamp_metadata(
            payload,
            schema_id=schema_id,
            schema_version=current_version,
            producer=producer,
            produced_at=produced_at,
        )

    def migrate_file(
        self,
        path: Path,
        schema_id: str,
        target_version: int,
        *,
        output_path: Path | None = None,
        producer: str | None = None,
        produced_at: str | None = None,
    ) -> Path:
        """Migrate a JSONL file in-place (or to ``output_path``) to ``target_version``."""
        if not path.exists():
            raise FileNotFoundError(f"Schema artifact not found: {path}")

        destination = output_path or path

        def _records() -> Iterator[dict[str, Any]]:
            with open(path, encoding="utf-8") as handle:
                for line_num, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise SchemaMigrationError(
                            f"{path}:{line_num} contains invalid JSON: {exc.msg}"
                        ) from exc
                    yield self.migrate_record(
                        schema_id,
                        record,
                        target_version,
                        producer=producer,
                        produced_at=produced_at,
                    )

        # Import lazily to avoid circular import at module load time.
        from rexlit.utils.jsonl import atomic_write_jsonl

        atomic_write_jsonl(destination, _records())
        return destination

    def clear(self, schema_id: str | None = None) -> None:
        """Clear registered migrations (useful for testing)."""
        if schema_id is None:
            self._migrations.clear()
        else:
            self._migrations.pop(schema_id, None)


schema_migrations = SchemaMigrationRegistry()


def register_schema_migration(
    schema_id: str,
    *,
    from_version: int,
    to_version: int,
    migrate: MigrationFunc,
) -> None:
    """Register a migration against the global registry."""
    schema_migrations.register(
        schema_id,
        from_version=from_version,
        to_version=to_version,
        migrate=migrate,
    )


def migrate_record(
    schema_id: str,
    record: Mapping[str, Any],
    target_version: int,
    *,
    producer: str | None = None,
    produced_at: str | None = None,
) -> dict[str, Any]:
    """Upgrade ``record`` to ``target_version`` using the global registry."""
    return schema_migrations.migrate_record(
        schema_id,
        record,
        target_version,
        producer=producer,
        produced_at=produced_at,
    )


def migrate_file(
    path: Path,
    schema_id: str,
    target_version: int,
    *,
    output_path: Path | None = None,
    producer: str | None = None,
    produced_at: str | None = None,
) -> Path:
    """Upgrade JSONL artifact located at ``path`` to ``target_version``."""
    return schema_migrations.migrate_file(
        path,
        schema_id,
        target_version,
        output_path=output_path,
        producer=producer,
        produced_at=produced_at,
    )
