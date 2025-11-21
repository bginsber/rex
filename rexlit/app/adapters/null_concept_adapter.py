"""No-op concept adapter used as a placeholder until real detectors are wired."""

from __future__ import annotations

from rexlit.app.ports.concept import ConceptFinding, ConceptPort


class NullConceptAdapter(ConceptPort):
    """Adapter that returns no concepts and never requires online calls."""

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        return []

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        return []

    def get_supported_concepts(self) -> list[str]:
        return []

    def requires_online(self) -> bool:
        return False
