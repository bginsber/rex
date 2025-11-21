"""Highlight service for legal concept detection and plan generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

from rexlit.app.ports import LedgerPort, StoragePort
from rexlit.app.ports.concept import ConceptFinding, ConceptPort
from rexlit.config import Settings, get_settings
from rexlit.utils.offline import OfflineModeGate
from rexlit.utils.paths import validate_input_root, validate_output_root
from rexlit.utils.plans import (
    compute_highlight_plan_id,
    load_highlight_plan_entry,
    validate_highlight_plan_entry,
    write_highlight_plan_entry,
)


DEFAULT_CATEGORY_COLORS: dict[str, str] = {
    "communication": "cyan",
    "privilege": "magenta",
    "entity": "yellow",
    "hotdoc": "red",
    "responsive": "green",
}


def _compute_shade_intensity(confidence: float) -> float:
    """Map confidence [0, 1] to shade intensity [0.3, 1.0]."""
    if confidence < 0.5:
        return 0.3
    return min(1.0, 0.3 + (confidence - 0.5) * 1.4)


def _finding_to_highlight(finding: ConceptFinding) -> dict[str, Any]:
    """Convert a concept finding into a highlight action."""
    color = DEFAULT_CATEGORY_COLORS.get(finding.category, "yellow")
    return {
        "concept": finding.concept,
        "category": finding.category,
        "confidence": finding.confidence,
        "start": finding.start,
        "end": finding.end,
        "page": finding.page,
        "color": color,
        "shade_intensity": _compute_shade_intensity(finding.confidence),
        "reasoning_hash": finding.reasoning_hash,
        "snippet_hash": finding.snippet_hash,
    }


class HighlightPlan(BaseModel):
    """Highlight plan with deterministic ID."""

    plan_id: str
    input_hash: str
    highlights: list[dict[str, Any]]
    annotations: dict[str, Any]


class HighlightService:
    """Orchestrates highlight planning."""

    def __init__(
        self,
        *,
        concept_port: ConceptPort,
        storage_port: StoragePort,
        ledger_port: LedgerPort | None,
        settings: Settings | None = None,
        offline_gate: OfflineModeGate | None = None,
    ):
        self.concept = concept_port
        self.storage = storage_port
        self.ledger = ledger_port
        self._settings = settings or get_settings()
        self._plan_key = self._settings.get_highlight_plan_key()
        self._offline_gate = offline_gate or OfflineModeGate.from_settings(self._settings)

    def plan(
        self,
        input_path: Path,
        output_plan_path: Path,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
        allowed_input_roots: Iterable[Path] | None = None,
        allowed_output_roots: Iterable[Path] | None = None,
    ) -> HighlightPlan:
        """Generate highlight plan without modifying documents."""

        if self.concept.requires_online():
            self._offline_gate.require("Highlight concept detection")

        resolved_input = validate_input_root(Path(input_path), allowed_input_roots)
        if not resolved_input.exists():
            raise FileNotFoundError(f"Highlight source not found: {resolved_input}")

        resolved_output = validate_output_root(Path(output_plan_path), allowed_output_roots)
        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        findings = self.concept.analyze_document(
            str(resolved_input),
            concepts=concepts,
            threshold=threshold,
        )
        highlights = [_finding_to_highlight(f) for f in findings]

        document_hash = self.storage.compute_hash(resolved_input)
        annotations = {
            "concept_types": sorted({f.concept for f in findings}),
            "detector": self.concept.__class__.__name__,
            "highlight_count": len(highlights),
            "pages_with_highlights": sorted({h.get("page") for h in highlights if h.get("page")}),
            "confidence_range": (
                min((h["confidence"] for h in highlights), default=0.0),
                max((h["confidence"] for h in highlights), default=0.0),
            ),
            "color_palette": DEFAULT_CATEGORY_COLORS,
        }

        plan_id = compute_highlight_plan_id(
            document_hash=document_hash,
            highlights=highlights,
            annotations=annotations,
        )

        plan_entry = {
            "document_hash": document_hash,
            "plan_id": plan_id,
            "highlights": highlights,
            "annotations": annotations,
            "notes": f"Found {len(highlights)} highlights",
        }

        write_highlight_plan_entry(resolved_output, plan_entry, key=self._plan_key)

        if self.ledger is not None:
            self.ledger.log(
                operation="highlight_plan_create",
                inputs=[str(resolved_input)],
                outputs=[str(resolved_output)],
                args={
                    "plan_id": plan_id,
                    "document_hash": document_hash,
                    "concept_types": annotations["concept_types"],
                    "highlight_count": len(highlights),
                },
            )

        return HighlightPlan(
            plan_id=plan_id,
            input_hash=document_hash,
            highlights=highlights,
            annotations=annotations,
        )

    def validate_plan(
        self,
        plan_path: Path,
        document_path: Path,
        *,
        allowed_input_roots: Iterable[Path] | None = None,
        key: bytes | None = None,
    ) -> bool:
        """Validate highlight plan against a document hash."""

        resolved_plan = Path(plan_path).resolve()
        resolved_document = validate_input_root(Path(document_path), allowed_input_roots)
        if not resolved_plan.exists():
            raise FileNotFoundError(f"Highlight plan not found: {resolved_plan}")
        if not resolved_document.exists():
            raise FileNotFoundError(f"Highlight document not found: {resolved_document}")

        entry = load_highlight_plan_entry(resolved_plan, key=key or self._plan_key)
        expected_hash = self.storage.compute_hash(resolved_document)
        validate_highlight_plan_entry(entry, document_hash=expected_hash)
        return True
