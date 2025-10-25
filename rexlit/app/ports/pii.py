"""PII port interface for personally identifiable information detection."""

from typing import Protocol

from pydantic import BaseModel


class PIIFinding(BaseModel):
    """PII detection finding."""

    entity_type: str  # "SSN", "EMAIL", "PHONE", etc.
    text: str
    score: float
    start: int
    end: int
    page: int | None = None


class PIIPort(Protocol):
    """Port interface for PII detection operations.

    Adapters: Presidio Analyzer (offline), custom regex patterns.

    Side effects: None (read-only analysis).
    """

    def analyze_text(
        self,
        text: str,
        *,
        language: str = "en",
        entities: list[str] | None = None,
    ) -> list[PIIFinding]:
        """Analyze text for PII.

        Args:
            text: Text to analyze
            language: Language code
            entities: Entity types to detect (None = all)

        Returns:
            List of PII findings
        """
        ...

    def analyze_document(
        self,
        path: str,
        *,
        language: str = "en",
        entities: list[str] | None = None,
    ) -> list[PIIFinding]:
        """Analyze document for PII.

        Args:
            path: Document path
            language: Language code
            entities: Entity types to detect (None = all)

        Returns:
            List of PII findings with page numbers
        """
        ...

    def get_supported_entities(self) -> list[str]:
        """Get list of supported entity types.

        Returns:
            List of entity type names
        """
        ...
