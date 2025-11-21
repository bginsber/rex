"""Port interface for legal concept detection."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ConceptFinding(BaseModel):
    """Legal concept detection finding (no raw text)."""

    concept: str
    category: str
    confidence: float
    start: int
    end: int
    page: int | None = None
    reasoning_hash: str | None = None
    snippet_hash: str | None = None


class ConceptPort(Protocol):
    """Port interface for legal concept detection."""

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

    def get_supported_concepts(self) -> list[str]:
        """Get list of supported concept types."""
        ...

    def requires_online(self) -> bool:
        """Return True when adapter needs network access."""
        ...
