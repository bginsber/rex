"""Integration checks for UCSF IDL fixture corpora.

These tests exercise the developer-generated fixture corpora produced by
`scripts/dev/idl_sample_docs.py`. They are intentionally lightweight and skip
automatically when the corresponding corpus tier is not available locally.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rexlit.ingest.discover import discover_documents


def _load_manifest(corpus_dir: Path) -> list[dict]:
    manifest_path = corpus_dir / "manifest.jsonl"
    assert manifest_path.exists(), f"Missing manifest at {manifest_path}"
    return [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.idl_small
def test_idl_small_manifest_records_have_expected_fields(idl_small: Path) -> None:
    """Minimal manifest should contain required identifiers and file references."""

    records = _load_manifest(idl_small)
    assert records, "Expected at least one record in the small corpus manifest"

    sample = records[0]
    for field in ("schema_version", "doc_id", "filepath", "sha256", "file_size", "idl_url"):
        assert field in sample, f"Record missing required field: {field}"

    doc_path = idl_small / sample["filepath"]
    assert doc_path.exists(), f"Referenced document missing: {doc_path}"


@pytest.mark.idl_small
def test_idl_small_discovery_matches_manifest_count(idl_small: Path) -> None:
    """RexLit's document discovery should surface the same number of items as the manifest."""

    records = _load_manifest(idl_small)
    docs_dir = idl_small / "docs"
    discovered = list(discover_documents(docs_dir))

    assert len(discovered) == len(records)


@pytest.mark.idl_medium
@pytest.mark.slow
def test_idl_medium_has_expected_volume(idl_medium: Path) -> None:
    """Medium corpus should contain roughly 1,000 documents."""

    records = _load_manifest(idl_medium)
    assert len(records) >= 900, "Medium corpus should contain approximately 1,000 documents"


