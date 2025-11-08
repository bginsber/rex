"""Utilities for sanitizing and redacting sensitive manifest data."""

import json
import re
from pathlib import Path
from typing import Any

from rexlit.utils.jsonl import atomic_write_jsonl


def export_safe_manifest(
    source: Path,
    dest: Path,
    *,
    mask_emails: bool = True,
) -> int:
    """Export sanitized manifest with redacted sensitive fields.

    Reads source manifest JSONL, emits minimal records with:
    - Keeps: sha256, size, mime_type, extension, doctype, produced_at, producer
    - Redacts: path (omitted), custodian (set to "REDACTED")
    - Optionally masks: email patterns in text fields

    Args:
        source: Path to source manifest.jsonl
        dest: Path to write safe_manifest.jsonl
        mask_emails: Whether to mask email addresses in string fields

    Returns:
        Count of exported records

    Raises:
        FileNotFoundError: If source manifest doesn't exist
        ValueError: If source JSONL is invalid or dest is outside allowed root
    """
    if not source.exists():
        raise FileNotFoundError(f"Source manifest not found: {source}")

    # Enforce boundary: dest must reside under source parent directory
    allowed_root = source.parent.resolve()
    dest_resolved = dest.resolve()
    try:
        dest_resolved.relative_to(allowed_root)
    except ValueError:
        raise ValueError(
            f"Safe manifest path must reside within {allowed_root}, "
            f"but got {dest_resolved}"
        ) from None

    safe_records = []
    record_count = 0

    with source.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in manifest at line {line_num}: {e}"
                ) from e

            # Extract fields to keep
            safe_record: dict[str, Any] = {
                "schema_id": "safe_manifest",
                "schema_version": 1,
                "sha256": record.get("sha256"),
                "size": record.get("size"),
                "mime_type": record.get("mime_type"),
                "extension": record.get("extension"),
                "doctype": record.get("doctype"),
                "produced_at": record.get("produced_at"),
                "producer": record.get("producer"),
                "custodian": "REDACTED",  # Always redact custodian
            }

            # Optionally mask email patterns in string fields
            if mask_emails:
                for key in ["producer", "doctype"]:
                    if key in safe_record and isinstance(safe_record[key], str):
                        safe_record[key] = _mask_emails(safe_record[key])

            safe_records.append(safe_record)
            record_count += 1

    # Write sanitized manifest
    atomic_write_jsonl(
        dest,
        safe_records,
        schema_id="safe_manifest",
        schema_version=1,
    )

    return record_count


def _mask_emails(text: str) -> str:
    """Mask email addresses in text.

    Replaces email addresses with [REDACTED_EMAIL].

    Args:
        text: Text potentially containing email addresses

    Returns:
        Text with emails masked
    """
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return re.sub(email_pattern, "[REDACTED_EMAIL]", text)
