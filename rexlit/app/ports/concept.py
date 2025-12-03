"""Port interface for legal concept detection."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ConceptFinding(BaseModel):
    """Legal concept detection finding (no raw text)."""

    model_config = ConfigDict(frozen=False)

    concept: str
    category: str
    confidence: float
    start: int
    end: int
    page: int | None = None
    reasoning_hash: str | None = None
    snippet_hash: str | None = None

    # Multi-factor scoring metadata
    confidence_factors: dict[str, float] | None = None
    needs_refinement: bool = False


class ConceptPort(Protocol):
    """Port interface for legal concept detection.

    Adapters implement pattern-based or LLM-based concept detection.
    The hybrid architecture uses:
    1. Pattern adapter for fast pre-filtering
    2. LLM adapter for refining uncertain findings (0.50-0.84 confidence)

    See ADR 0008 for escalation strategy.
    """

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Analyze text for legal concepts."""
        ...

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Analyze document for legal concepts."""
        ...

    def refine_findings(
        self,
        text: str,
        findings: list[ConceptFinding],
        *,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Refine uncertain findings using deeper analysis (LLM).

        Called by HighlightService for findings with 0.50-0.84 confidence.
        Pattern adapters may return findings unchanged.
        LLM adapters analyze context and adjust confidence.

        Args:
            text: Original text for context
            findings: Uncertain findings to refine
            threshold: Minimum confidence threshold

        Returns:
            Refined findings with updated confidence scores
        """
        ...

    def get_supported_concepts(self) -> list[str]:
        """Get list of supported concept types."""
        ...

    def requires_online(self) -> bool:
        """Return True when adapter needs network access."""
        ...
