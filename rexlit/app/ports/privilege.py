"""Privilege port interface for attorney-client privilege and work product detection."""

from typing import Protocol

from pydantic import BaseModel, Field


class PrivilegeFinding(BaseModel):
    """Privilege detection finding."""

    rule: str  # e.g., "attorney_domain", "keyword_privileged", "attorney_name"
    match_type: str  # "domain", "keyword", "name"
    confidence: float = Field(ge=0.0, le=1.0)
    snippet: str  # matched text excerpt
    start: int  # character offset in text
    end: int  # character offset in text
    page: int | None = None  # page number if available


class PrivilegePort(Protocol):
    """Port interface for privilege and work product detection operations.

    Adapters: Hybrid pattern matching (domains, keywords, names), optional Presidio NER.

    Side effects: None (read-only analysis).
    """

    def analyze_text(
        self,
        text: str,
        *,
        threshold: float = 0.75,
    ) -> list[PrivilegeFinding]:
        """Analyze text for privilege indicators.

        Args:
            text: Text to analyze
            threshold: Confidence threshold (0.0-1.0); findings below are filtered

        Returns:
            List of privilege findings meeting or exceeding threshold
        """
        ...

    def analyze_document(
        self,
        path: str,
        *,
        threshold: float = 0.75,
    ) -> list[PrivilegeFinding]:
        """Analyze document for privilege indicators.

        Args:
            path: Document path
            threshold: Confidence threshold (0.0-1.0); findings below are filtered

        Returns:
            List of privilege findings with page numbers (if available)
        """
        ...

    def get_supported_rules(self) -> list[str]:
        """Get list of supported detection rules.

        Returns:
            List of rule names (e.g., ["attorney_domain", "keyword_privileged"])
        """
        ...

    def requires_online(self) -> bool:
        """Return True when adapter needs network access.

        Always returns False for offline-first privilege detection.
        """

        ...
