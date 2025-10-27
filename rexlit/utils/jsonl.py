"""JSONL writing helpers with durability guarantees."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from rexlit import __version__


@dataclass(frozen=True, slots=True)
class SchemaStamp:
    """Stamp applied to JSONL records to encode schema provenance."""

    schema_id: str
    schema_version: int
    producer: str
    produced_at: str

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``payload`` with schema metadata overlaid."""
        stamped = dict(payload)
        stamped["schema_id"] = self.schema_id
        stamped["schema_version"] = self.schema_version
        stamped["producer"] = self.producer
        stamped["produced_at"] = self.produced_at
        return stamped


def _normalize_record(record: Any, *, schema_stamp: SchemaStamp | None = None) -> str:
    """Convert supported record types into a JSON string."""
    if isinstance(record, str):
        line = record.rstrip("\n")
        if not line:
            raise ValueError("Blank string provided to JSONL writer.")
        if schema_stamp is not None:
            raise TypeError(
                "Cannot apply schema metadata to pre-serialized JSONL strings. "
                "Provide dict, dataclass, or Pydantic model records instead."
            )
        return line

    if hasattr(record, "model_dump"):
        payload = record.model_dump(mode="json")
    elif hasattr(record, "model_dump_json"):
        line = record.model_dump_json()
        if schema_stamp is not None:
            payload = json.loads(line)
        else:
            return line
    elif is_dataclass(record):
        payload = asdict(record)
    elif isinstance(record, dict):
        payload = record
    else:
        raise TypeError(
            "Unsupported record type for JSONL serialization: "
            f"{type(record)!r}. Provide dict, dataclass, or Pydantic model."
        )

    if schema_stamp is not None:
        payload = schema_stamp.apply(payload)

    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def _build_schema_stamp(
    *,
    schema_id: str | None,
    schema_version: int | None,
    producer: str | None,
    produced_at: str | None,
) -> SchemaStamp | None:
    """Construct a SchemaStamp from the provided components."""
    args_provided = any(
        value is not None for value in (schema_id, schema_version, producer, produced_at)
    )

    if not args_provided:
        return None

    if schema_id is None or schema_version is None:
        raise ValueError("Both schema_id and schema_version are required when stamping records.")

    default_producer = f"rexlit-{__version__}"
    metadata_producer = producer or default_producer
    metadata_produced_at = produced_at or datetime.now(UTC).isoformat()

    return SchemaStamp(
        schema_id=schema_id,
        schema_version=schema_version,
        producer=metadata_producer,
        produced_at=metadata_produced_at,
    )


def atomic_write_jsonl(
    path: Path,
    records: Iterable[Any],
    *,
    schema_id: str | None = None,
    schema_version: int | None = None,
    producer: str | None = None,
    produced_at: str | None = None,
) -> None:
    """Write ``records`` to ``path`` atomically as JSONL.

    The write is performed via a temporary file followed by an ``os.replace``
    once the contents are flushed and fsynced, ensuring durability even if the
    process crashes mid-write.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    schema_stamp = _build_schema_stamp(
        schema_id=schema_id,
        schema_version=schema_version,
        producer=producer,
        produced_at=produced_at,
    )

    fd: int | None = None
    tmp_path: str | None = None

    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(destination.parent),
            prefix=destination.name,
            suffix=".tmp",
            text=True,
        )

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None  # Ownership transferred to file object
            for record in records:
                line = _normalize_record(record, schema_stamp=schema_stamp)
                handle.write(line)
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, destination)
        tmp_path = None
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
