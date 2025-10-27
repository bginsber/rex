"""Utilities for deterministic plan identifiers and validation."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from rexlit.utils.crypto import decrypt_blob, encrypt_blob
from rexlit.utils.deterministic import compute_input_hash
from rexlit.utils.schema import stamp_metadata


def _normalize_actions(actions: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Return a JSON-serializable list of action dictionaries."""

    if actions is None:
        return []

    normalized: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, Mapping):
            raise TypeError(
                "Redaction plan actions must be mappings to ensure deterministic hashing."
            )
        normalized.append(dict(action))
    return normalized


def _normalize_annotations(annotations: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return metadata annotations as a dictionary."""

    if annotations is None:
        return {}
    if not isinstance(annotations, Mapping):
        raise TypeError(
            "Redaction plan annotations must be a mapping to ensure deterministic hashing."
        )
    return dict(annotations)


def compute_redaction_plan_id(
    *,
    document_path: Path,
    content_hash: str,
    actions: Iterable[Mapping[str, Any]] | None = None,
    annotations: Mapping[str, Any] | None = None,
) -> str:
    """Compute deterministic identifier for a redaction plan."""

    resolved_path = Path(document_path).resolve()

    components: list[str] = [
        str(resolved_path),
        content_hash,
    ]

    normalized_actions = _normalize_actions(actions)
    if normalized_actions:
        components.append(
            json.dumps(
                normalized_actions,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )

    normalized_annotations = _normalize_annotations(annotations)
    if normalized_annotations:
        components.append(
            json.dumps(
                normalized_annotations,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )

    return compute_input_hash(components)


def validate_redaction_plan_entry(
    entry: Mapping[str, Any],
    *,
    document_path: Path,
    content_hash: str,
) -> str:
    """Validate a redaction plan entry against expected provenance."""

    expected_path = Path(document_path).resolve()
    entry_path = Path(str(entry.get("document", ""))).resolve()
    if entry_path != expected_path:
        raise ValueError(
            "Redaction plan provenance mismatch: "
            f"expected document '{expected_path}', found '{entry_path}'."
        )

    entry_hash = entry.get("sha256")
    if entry_hash != content_hash:
        raise ValueError(
            "Redaction plan hash mismatch detected for "
            f"{expected_path}. Expected {content_hash}, found {entry_hash}."
        )

    plan_id = entry.get("plan_id")
    if not isinstance(plan_id, str) or len(plan_id) != 64:
        raise ValueError("Redaction plan missing deterministic plan_id.")

    actions = entry.get("actions")
    annotations = entry.get("annotations")

    normalized_actions = _normalize_actions(actions if isinstance(actions, Iterable) else None)
    normalized_annotations = _normalize_annotations(
        annotations if isinstance(annotations, Mapping) else None
    )
    expected_plan_id = compute_redaction_plan_id(
        document_path=expected_path,
        content_hash=content_hash,
        actions=normalized_actions or None,
        annotations=normalized_annotations or None,
    )

    if plan_id != expected_plan_id:
        raise ValueError(
            f"Redaction plan_id mismatch for {expected_path}. "
            f"Expected {expected_plan_id}, found {plan_id}."
        )

    return plan_id


def validate_redaction_plan_file(
    plan_path: Path,
    *,
    document_path: Path,
    content_hash: str,
    key: bytes | None = None,
) -> str:
    """Validate plan file on disk and return its deterministic plan_id."""

    entry = load_redaction_plan_entry(plan_path, key=key)

    return validate_redaction_plan_entry(
        entry,
        document_path=document_path,
        content_hash=content_hash,
    )


def load_redaction_plan_entry(plan_path: Path, *, key: bytes | None = None) -> dict[str, Any]:
    """Load (and decrypt) the single entry stored in ``plan_path``."""

    path = Path(plan_path)
    if not path.exists():
        raise FileNotFoundError(f"Redaction plan not found at {path}.")

    entries = _read_plan_entries(path, key)

    if not entries:
        raise ValueError(f"Redaction plan at {path} is empty.")

    if len(entries) > 1:
        raise ValueError(
            f"Redaction plan at {path} contains multiple entries; expected a single record."
        )

    return entries[0]


def write_redaction_plan_entry(
    path: Path,
    entry: Mapping[str, Any],
    *,
    key: bytes,
) -> None:
    """Write ``entry`` to ``path`` as an encrypted JSONL record."""
    stamped_entry = stamp_metadata(
        dict(entry),
        schema_id="redaction_plan",
        schema_version=1,
    )

    payload = json.dumps(
        stamped_entry,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    token = encrypt_blob(payload, key=key).decode("utf-8")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(token)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass


def _read_plan_entries(path: Path, key: bytes | None) -> list[dict[str, Any]]:
    """Internal helper to load plan entries handling encrypted + plaintext formats."""
    entries: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                entries.append(json.loads(line))
                continue

            if key is None:
                raise ValueError(
                    f"Redaction plan at {path} is encrypted but no key was provided."
                )

            try:
                decrypted = decrypt_blob(line.encode("utf-8"), key=key)
                entries.append(json.loads(decrypted.decode("utf-8")))
            except Exception as exc:
                raise ValueError(f"Failed to decrypt redaction plan {path}: {exc}") from exc

    return entries
