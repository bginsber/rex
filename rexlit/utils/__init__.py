"""Utility modules for common operations."""

from rexlit.utils.hashing import compute_sha256, compute_sha256_file
from rexlit.utils.jsonl import atomic_write_jsonl
from rexlit.utils.paths import ensure_dir, get_data_dir
from rexlit.utils.schema import (
    SchemaMigrationError,
    SchemaMigrationRegistry,
    SchemaStamp,
    SchemaValidationError,
    build_schema_stamp,
    migrate_file,
    migrate_record,
    register_schema_migration,
    schema_migrations,
    stamp_metadata,
    stamp_records,
    strip_schema_metadata,
    validate_file,
    validate_record,
)

__all__ = [
    "atomic_write_jsonl",
    "compute_sha256",
    "compute_sha256_file",
    "ensure_dir",
    "get_data_dir",
    "SchemaMigrationError",
    "SchemaMigrationRegistry",
    "SchemaStamp",
    "SchemaValidationError",
    "schema_migrations",
    "build_schema_stamp",
    "register_schema_migration",
    "migrate_record",
    "migrate_file",
    "stamp_metadata",
    "stamp_records",
    "strip_schema_metadata",
    "validate_record",
    "validate_file",
]
