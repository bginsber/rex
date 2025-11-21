from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from rexlit.app.adapters.pattern_concept_adapter import PatternConceptAdapter
from rexlit.app.highlight_service import HighlightService
from rexlit.config import Settings
from rexlit.utils.plans import (
    compute_highlight_plan_id,
    load_highlight_plan_entry,
    validate_highlight_plan_entry,
    write_highlight_plan_entry,
)


def test_highlight_plan_round_trip_has_no_text(tmp_path: Path) -> None:
    document_hash = "a" * 64
    highlights = [
        {
            "concept": "EMAIL_COMMUNICATION",
            "category": "communication",
            "confidence": 0.95,
            "start": 0,
            "end": 12,
            "page": 1,
            "color": "cyan",
            "shade_intensity": 0.95,
            "reasoning_hash": "b" * 64,
            "snippet_hash": "c" * 64,
        }
    ]
    annotations = {"concept_types": ["EMAIL_COMMUNICATION"], "detector": "PatternConceptAdapter"}
    plan_id = compute_highlight_plan_id(
        document_hash=document_hash,
        highlights=highlights,
        annotations=annotations,
    )
    entry = {
        "document_hash": document_hash,
        "plan_id": plan_id,
        "highlights": highlights,
        "annotations": annotations,
        "notes": "Sample plan",
    }

    key = Fernet.generate_key()
    plan_path = tmp_path / "plan.jsonl"
    write_highlight_plan_entry(plan_path, entry, key=key)

    loaded = load_highlight_plan_entry(plan_path, key=key)
    validate_highlight_plan_entry(loaded, document_hash=document_hash)

    highlight = loaded["highlights"][0]
    assert "text" not in highlight
    assert "reasoning_summary" not in highlight
    assert highlight["snippet_hash"] == "c" * 64


def test_highlight_plan_validation_rejects_hash_mismatch(tmp_path: Path) -> None:
    document_hash = "d" * 64
    highlights = [
        {
            "concept": "LEGAL_ADVICE",
            "category": "privilege",
            "confidence": 0.8,
            "start": 5,
            "end": 15,
            "page": 2,
            "color": "magenta",
            "shade_intensity": 0.8,
            "reasoning_hash": "e" * 64,
            "snippet_hash": "f" * 64,
        }
    ]
    plan_id = compute_highlight_plan_id(document_hash=document_hash, highlights=highlights)
    entry = {
        "document_hash": document_hash,
        "plan_id": plan_id,
        "highlights": highlights,
    }

    key = Fernet.generate_key()
    plan_path = tmp_path / "plan.jsonl"
    write_highlight_plan_entry(plan_path, entry, key=key)
    loaded = load_highlight_plan_entry(plan_path, key=key)

    with pytest.raises(ValueError):
        validate_highlight_plan_entry(loaded, document_hash="deadbeef")


class _MemoryStorage:
    def compute_hash(self, path):
        data = Path(path).read_bytes()
        import hashlib

        return hashlib.sha256(data).hexdigest()

    # Other StoragePort methods are not needed for these tests.


class _NoOpLedger:
    def log(self, *args, **kwargs):
        return None


def test_highlight_export_heatmap(tmp_path: Path) -> None:
    sample_doc = tmp_path / "doc.txt"
    sample_doc.write_text(
        "From: attorney@lawfirm.com\nThis is privileged and contains legal advice.",
        encoding="utf-8",
    )

    service = HighlightService(
        concept_port=PatternConceptAdapter(),
        storage_port=_MemoryStorage(),
        ledger_port=_NoOpLedger(),
        settings=Settings(highlight_plan_key_path=tmp_path / "highlight-plans.key"),
        offline_gate=None,
    )

    plan_path = tmp_path / "plan.enc"
    export_path = tmp_path / "heatmap.json"

    service.plan(
        sample_doc,
        plan_path,
        allowed_input_roots=[tmp_path],
        allowed_output_roots=[tmp_path],
    )

    result_path = service.export(plan_path, export_path, format="heatmap")
    assert result_path.exists()
    data = export_path.read_text(encoding="utf-8")
    assert "temperature" in data
