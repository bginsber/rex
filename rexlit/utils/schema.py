"""Schema validation and metadata stamping utilities."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rexlit import __version__


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


def stamp_metadata(
    record: dict[str, Any],
    schema_id: str,
    schema_version: int = 1,
) -> dict[str, Any]:
    """Add schema metadata to record.

    Args:
        record: Record dictionary to stamp
        schema_id: Schema identifier
        schema_version: Schema version

    Returns:
        Record with added metadata fields
    """
    now = datetime.now(timezone.utc).isoformat()

    # Add schema metadata
    record["schema_id"] = schema_id
    record["schema_version"] = schema_version
    record["producer"] = f"rexlit-{__version__}"
    record["produced_at"] = now

    # Compute content hash (excludes metadata fields)
    content = {
        k: v
        for k, v in record.items()
        if k not in ("schema_id", "schema_version", "producer", "produced_at", "content_hash")
    }
    content_json = json.dumps(content, sort_keys=True)
    content_hash = hashlib.sha256(content_json.encode()).hexdigest()
    record["content_hash"] = content_hash

    return record


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
        # Lazy import to avoid hard dependency
        import jsonschema

        schema = load_schema(schema_id, schema_version)
        jsonschema.validate(record, schema)
        return True
    except ImportError:
        # jsonschema not installed, skip validation
        return True
    except jsonschema.ValidationError as e:
        # TODO: Log warning in prod, raise in dev
        raise ValueError(f"Schema validation failed: {e.message}")


def validate_file(path: Path, schema_id: str, schema_version: int = 1) -> tuple[int, int]:
    """Validate JSONL file against schema.

    Args:
        path: Path to JSONL file
        schema_id: Schema identifier
        schema_version: Schema version

    Returns:
        Tuple of (valid_count, invalid_count)
    """
    valid_count = 0
    invalid_count = 0

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                if validate_record(record, schema_id, schema_version):
                    valid_count += 1
                else:
                    invalid_count += 1
            except (json.JSONDecodeError, ValueError) as e:
                invalid_count += 1
                # TODO: Log warning with line number

    return valid_count, invalid_count
