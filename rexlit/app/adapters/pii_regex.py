"""PII detection adapter using regex patterns and name lists."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rexlit.app.ports.pii import PIIFinding
from rexlit.ingest.extract import extract_document


class PIIRegexAdapter:
    """Regex-based PII detector implementing PIIPort.

    Detects:
    - SSN (Social Security Number): XXX-XX-XXXX format
    - EMAIL: basic email pattern
    - PHONE: US phone numbers
    - Optional: names from configurable name list

    Always offline (requires_online() -> False).
    """

    # Pattern definitions
    PATTERNS = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
    }

    def __init__(self, profile: dict[str, Any] | None = None):
        """Initialize PII detector with optional profile.

        Args:
            profile: Profile dict with keys:
                - enabled_patterns: list of pattern types to enable (default: all)
                - domain_whitelist: list of domains to exclude from email detection
                - domain_blacklist: list of domains to specifically detect
                - names: list of names to detect
        """
        self.profile = profile or {}
        self.enabled_patterns = set(
            self.profile.get("enabled_patterns", list(self.PATTERNS.keys()))
        )
        self.domain_whitelist = set(
            self.profile.get("domain_whitelist", [])
        )
        self.domain_blacklist = set(
            self.profile.get("domain_blacklist", [])
        )
        self.names = self.profile.get("names", [])

        # Compile patterns
        self._compiled_patterns = {
            entity: re.compile(pattern, re.IGNORECASE)
            for entity, pattern in self.PATTERNS.items()
            if entity in self.enabled_patterns
        }

        # Compile name patterns if present
        if self.names:
            # Escape special regex chars and join with |
            escaped_names = [re.escape(name) for name in self.names]
            self._name_pattern = re.compile(
                r"\b(" + "|".join(escaped_names) + r")\b",
                re.IGNORECASE
            )
        else:
            self._name_pattern = None

    def analyze_text(
        self,
        text: str,
        *,
        language: str = "en",
        entities: list[str] | None = None,
    ) -> list[PIIFinding]:
        """Analyze text for PII entities.

        Args:
            text: Text to analyze
            language: Language code (unused, for API compatibility)
            entities: Entity types to detect (None = all enabled patterns)

        Returns:
            List of PIIFinding objects
        """
        findings = []
        target_entities = (
            set(entities) & self.enabled_patterns
            if entities
            else self.enabled_patterns
        )

        for entity_type in target_entities:
            if entity_type not in self._compiled_patterns:
                continue

            pattern = self._compiled_patterns[entity_type]

            for match in pattern.finditer(text):
                matched_text = match.group(0)

                # Filter emails by whitelist/blacklist
                if entity_type == "EMAIL":
                    domain = matched_text.split("@")[1] if "@" in matched_text else ""
                    if self.domain_whitelist and domain in self.domain_whitelist:
                        continue
                    if self.domain_blacklist and domain not in self.domain_blacklist:
                        continue

                finding = PIIFinding(
                    entity_type=entity_type,
                    text=matched_text,
                    score=1.0,  # Regex matches are high confidence
                    start=match.start(),
                    end=match.end(),
                    page=None,
                )
                findings.append(finding)

        # Check name patterns
        if self._name_pattern and (entities is None or "NAME" in entities):
            for match in self._name_pattern.finditer(text):
                finding = PIIFinding(
                    entity_type="NAME",
                    text=match.group(0),
                    score=0.9,  # Regex match, slightly lower than SSN/email
                    start=match.start(),
                    end=match.end(),
                    page=None,
                )
                findings.append(finding)

        return findings

    def analyze_document(
        self,
        path: str,
        *,
        language: str = "en",
        entities: list[str] | None = None,
    ) -> list[PIIFinding]:
        """Analyze document for PII entities.

        Args:
            path: Path to document
            language: Language code (unused)
            entities: Entity types to detect

        Returns:
            List of PIIFinding objects with page numbers (if available)
        """
        path_obj = Path(path)
        page_spans: list[tuple[int, int, int]] | None = None

        if path_obj.suffix.lower() == ".pdf":
            try:
                text, page_spans = self._extract_pdf_text_with_offsets(path_obj)
            except Exception as exc:  # pragma: no cover - fallback path
                logging.getLogger(__name__).warning(
                    "PDF extraction fallback for %s due to error: %s", path_obj, exc
                )
                try:
                    text = extract_document(path_obj).text
                except Exception:
                    return []
        else:
            try:
                doc_result = extract_document(path_obj)
                text = doc_result.text
            except Exception:
                return []

        findings = self.analyze_text(text, language=language, entities=entities)

        if page_spans:
            for finding in findings:
                if finding.page is None:
                    page = self._lookup_page(finding.start, page_spans)
                    if page is not None:
                        finding.page = page

        return findings

    def get_supported_entities(self) -> list[str]:
        """Get list of supported entity types.

        Returns:
            List of entity type names
        """
        entities = list(self.enabled_patterns)
        if self._name_pattern:
            entities.append("NAME")
        return entities

    def requires_online(self) -> bool:
        """Return True when adapter needs network access.

        Always returns False for regex-based detection.
        """
        return False

    def _extract_pdf_text_with_offsets(
        self,
        path: Path,
    ) -> tuple[str, list[tuple[int, int, int]]]:
        """Return concatenated PDF text and per-page character spans."""

        import fitz  # type: ignore[import]

        doc = fitz.open(str(path))
        try:
            segments: list[str] = []
            spans: list[tuple[int, int, int]] = []
            cursor = 0

            for page_index in range(doc.page_count):
                page_text = doc[page_index].get_text()
                segments.append(page_text)
                start = cursor
                cursor += len(page_text)
                spans.append((page_index, start, cursor))
                if page_index != doc.page_count - 1:
                    segments.append("\n\n")
                    cursor += 2

            combined = "".join(segments)
            return combined, spans
        finally:
            doc.close()

    @staticmethod
    def _lookup_page(
        offset: int,
        spans: Iterable[tuple[int, int, int]],
    ) -> int | None:
        for page_index, start, end in spans:
            if start <= offset < end:
                return page_index
        return None
