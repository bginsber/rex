"""Utility helpers shared by IDL fixture scripts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

MANIFEST_FILENAME = "manifest.jsonl"

FilterParser = Callable[[str], object]


def _parse_int(name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer (got {raw!r})") from exc


def _parse_bool(name: str, raw: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in {"true", "1"}:
        return True
    if lowered in {"false", "0"}:
        return False
    raise ValueError(f"{name} must be either true/false (got {raw!r})")


@dataclass(frozen=True)
class FilterSpec:
    parser: FilterParser
    description: str


VALID_FILTERS: Mapping[str, FilterSpec] = {
    "page_count_min": FilterSpec(
        parser=lambda value: _parse_int("page_count_min", value),
        description="minimum page count (int)",
    ),
    "page_count_max": FilterSpec(
        parser=lambda value: _parse_int("page_count_max", value),
        description="maximum page count (int)",
    ),
    "include_ocr": FilterSpec(
        parser=lambda value: _parse_bool("include_ocr", value),
        description="only include records with OCR text (bool)",
    ),
}


def filters_help() -> str:
    """Return a comma-separated description of supported filters."""

    return ", ".join(f"{name}: {spec.description}" for name, spec in sorted(VALID_FILTERS.items()))


def parse_filter_args(filters: Iterable[str] | None) -> dict[str, object]:
    """Parse CLI filter arguments using the VALID_FILTERS mapping."""

    parsed: dict[str, object] = {}
    if not filters:
        return parsed

    allowed = ", ".join(sorted(VALID_FILTERS))
    for item in filters:
        if "=" not in item:
            raise ValueError(f"Invalid --filter argument '{item}'. Expected key=value format.")
        key, value = item.split("=", 1)
        key = key.strip()
        if key not in VALID_FILTERS:
            raise ValueError(f"Unsupported filter '{key}'. Supported filters: {allowed}")
        spec = VALID_FILTERS[key]
        parsed[key] = spec.parser(value.strip())
    return parsed


def validate_corpus(corpus_dir: Path) -> list[str]:
    """Validate manifest integrity and referenced PDFs within ``corpus_dir``."""

    manifest_path = corpus_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return [f"Manifest not found: {manifest_path}"]

    errors: list[str] = []
    with manifest_path.open(encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{manifest_path}:{line_num} invalid JSON - {exc}")
                continue

            filepath = record.get("filepath")
            if not filepath:
                errors.append(f"{manifest_path}:{line_num} missing 'filepath'")
                continue

            sha256 = record.get("sha256")
            doc_path = corpus_dir / filepath
            if not doc_path.exists():
                errors.append(f"{manifest_path}:{line_num} file missing - {doc_path}")
                continue

            if sha256:
                actual_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
                if actual_hash != sha256:
                    errors.append(
                        f"{manifest_path}:{line_num} checksum mismatch for {filepath} "
                        f"(expected {sha256}, got {actual_hash})"
                    )
    return errors

