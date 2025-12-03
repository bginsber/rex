"""Highlight service for legal concept detection and plan generation.

Implements ADR 0008 hybrid pattern → LLM escalation architecture:
- Pattern adapter for fast pre-filtering with multi-factor confidence
- LLM adapter for refining uncertain findings (0.50-0.84 confidence)
- High confidence (≥0.85) findings skip LLM escalation
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

_logger = logging.getLogger(__name__)

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
from rexlit.utils.layout import map_highlight_boxes


DEFAULT_CATEGORY_COLORS: dict[str, str] = {
    "communication": "cyan",
    "privilege": "magenta",
    "entity": "yellow",
    "hotdoc": "red",
    "responsive": "green",
}

# Confidence thresholds for escalation (per ADR 0008)
HIGH_CONFIDENCE_THRESHOLD = 0.85
UNCERTAIN_LOWER_BOUND = 0.50


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
    """Orchestrates highlight planning with hybrid pattern → LLM escalation.

    Per ADR 0008:
    - Pattern adapter runs first (fast, offline)
    - High confidence (≥0.85) → use pattern result, skip LLM
    - Uncertain (0.50-0.84) → escalate to LLM for refinement
    - Low (<0.50) → escalate to LLM for full analysis
    """

    def __init__(
        self,
        *,
        concept_port: ConceptPort,
        storage_port: StoragePort,
        ledger_port: LedgerPort | None,
        refinement_port: ConceptPort | None = None,
        settings: Settings | None = None,
        offline_gate: OfflineModeGate | None = None,
    ):
        """Initialize highlight service.

        Args:
            concept_port: Primary adapter for concept detection (usually pattern-based)
            storage_port: Filesystem operations port
            ledger_port: Audit logging port
            refinement_port: Optional LLM adapter for refining uncertain findings
            settings: Application settings
            offline_gate: Gate for online mode checking
        """
        self.concept = concept_port
        self.refinement = refinement_port
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
        enable_escalation: bool = True,
    ) -> HighlightPlan:
        """Generate highlight plan with hybrid pattern → LLM detection.

        Args:
            input_path: Document to analyze
            output_plan_path: Path for output plan
            concepts: Concept types to detect (None = all)
            threshold: Minimum confidence threshold
            allowed_input_roots: Allowed input directories
            allowed_output_roots: Allowed output directories
            enable_escalation: If True and refinement_port is set, escalate uncertain findings

        Returns:
            HighlightPlan with detection results and escalation stats
        """
        if self.concept.requires_online():
            self._offline_gate.require("Highlight concept detection")

        resolved_input = validate_input_root(Path(input_path), allowed_input_roots)
        if not resolved_input.exists():
            raise FileNotFoundError(f"Highlight source not found: {resolved_input}")

        resolved_output = validate_output_root(Path(output_plan_path), allowed_output_roots)
        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        # Read document text for escalation (needed for context window)
        text = self._read_document_text(resolved_input)

        # Stage 1: Pattern detection with multi-factor scoring
        findings = self.concept.analyze_document(
            str(resolved_input),
            concepts=concepts,
            threshold=threshold,
        )

        # Stage 2: Escalate uncertain findings to LLM (if enabled)
        escalation_stats = {"high_confidence": 0, "escalated": 0, "refined": 0}
        if enable_escalation and self.refinement is not None:
            findings, escalation_stats = self._escalate_uncertain_findings(
                text=text,
                findings=findings,
                threshold=threshold,
            )

        highlights = [_finding_to_highlight(f) for f in findings]

        document_hash = self.storage.compute_hash(resolved_input)
        annotations = {
            "concept_types": sorted({f.concept for f in findings}),
            "detector": self.concept.__class__.__name__,
            "refinement_detector": (
                self.refinement.__class__.__name__ if self.refinement else None
            ),
            "highlight_count": len(highlights),
            "pages_with_highlights": sorted({h.get("page") for h in highlights if h.get("page")}),
            "confidence_range": (
                min((h["confidence"] for h in highlights), default=0.0),
                max((h["confidence"] for h in highlights), default=0.0),
            ),
            "color_palette": DEFAULT_CATEGORY_COLORS,
            "escalation_stats": escalation_stats,
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
            "notes": f"Found {len(highlights)} highlights ({escalation_stats['escalated']} escalated to LLM)",
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
                    "escalation_stats": escalation_stats,
                },
            )

        return HighlightPlan(
            plan_id=plan_id,
            input_hash=document_hash,
            highlights=highlights,
            annotations=annotations,
        )

    def _read_document_text(self, path: Path) -> str:
        """Read document text for LLM context extraction."""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                import fitz  # type: ignore[import]

                doc = fitz.open(str(path))
                text = "\n\n".join(page.get_text() for page in doc)
                doc.close()
                return text
            except ImportError:
                _logger.debug("fitz not available for PDF extraction")
            except Exception as e:
                _logger.warning("PDF text extraction failed for %s: %s", path, e)
        # Fallback to plain text read
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            _logger.warning("Text read failed for %s: %s", path, e)
            return ""

    def _escalate_uncertain_findings(
        self,
        text: str,
        findings: list[ConceptFinding],
        threshold: float,
    ) -> tuple[list[ConceptFinding], dict[str, int]]:
        """Escalate uncertain findings to LLM refinement.

        Per ADR 0008:
        - High confidence (≥0.85): Keep as-is, skip LLM
        - Uncertain (0.50-0.84): Send to LLM for refinement
        - needs_refinement flag from pattern adapter used as hint

        Returns:
            Tuple of (refined_findings, escalation_stats)
        """
        if not self.refinement:
            return findings, {"high_confidence": len(findings), "escalated": 0, "refined": 0}

        high_confidence: list[ConceptFinding] = []
        uncertain: list[ConceptFinding] = []

        for f in findings:
            # Check needs_refinement flag or confidence range
            should_escalate = (
                getattr(f, "needs_refinement", False)
                or (UNCERTAIN_LOWER_BOUND <= f.confidence < HIGH_CONFIDENCE_THRESHOLD)
            )
            if should_escalate:
                uncertain.append(f)
            else:
                high_confidence.append(f)

        stats = {
            "high_confidence": len(high_confidence),
            "escalated": len(uncertain),
            "refined": 0,
        }

        if not uncertain:
            return findings, stats

        # Check offline gate before escalating to refinement adapter
        if self.refinement.requires_online():
            self._offline_gate.require("Highlight concept refinement")

        # Escalate to LLM
        try:
            refined = self.refinement.refine_findings(
                text=text,
                findings=uncertain,
                threshold=threshold,
            )
            stats["refined"] = len(refined)
            return high_confidence + refined, stats
        except Exception as e:
            _logger.warning(
                "LLM refinement failed for %d findings, using pattern results: %s",
                len(uncertain),
                e,
            )
            return findings, stats

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

    def export(
        self,
        plan_path: Path,
        output_path: Path,
        *,
        format: str = "json",
        key: bytes | None = None,
    ) -> Path:
        """Export highlight plan to UI-friendly JSON formats."""

        entry = load_highlight_plan_entry(Path(plan_path).resolve(), key=key or self._plan_key)
        highlights = entry.get("highlights", [])
        document_hash = entry.get("document_hash")

        layout_dir = self._settings.highlight_layout_dir
        if layout_dir is None:
            layout_dir = self._settings.get_data_dir() / "layouts"

        enriched_highlights: list[dict[str, Any]] = []
        for h in highlights:
            boxes = []
            if document_hash:
                boxes = map_highlight_boxes(
                    highlight=h,
                    document_hash=document_hash,
                    layout_dir=layout_dir,
                )
            enriched = dict(h)
            if boxes:
                enriched["boxes"] = boxes
            enriched_highlights.append(enriched)

        if format not in {"json", "heatmap"}:
            raise ValueError("format must be 'json' or 'heatmap'")

        if format == "heatmap":
            payload = self._build_heatmap_payload(enriched_highlights)
        else:
            payload = {
                "document_hash": entry.get("document_hash"),
                "highlights": enriched_highlights,
                "heatmap": self._build_heatmap_payload(enriched_highlights),
                "color_legend": entry.get("annotations", {}).get(
                    "color_palette", DEFAULT_CATEGORY_COLORS
                ),
            }

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path

    @staticmethod
    def _build_heatmap_payload(highlights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pages: dict[int, list[dict[str, Any]]] = {}
        for h in highlights:
            page = h.get("page")
            if page is None:
                continue
            pages.setdefault(int(page), []).append(h)

        heatmap: list[dict[str, Any]] = []
        for page, items in sorted(pages.items(), key=lambda kv: kv[0]):
            temperatures = [item.get("shade_intensity", 0.0) or 0.0 for item in items]
            temperature = max(temperatures) if temperatures else 0.0
            heatmap.append(
                {
                    "page": page,
                    "temperature": temperature,
                    "highlight_count": len(items),
                }
            )
        return heatmap
