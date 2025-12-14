"""Privilege detection adapter using pattern matching and domain lists."""

import re
from pathlib import Path
from typing import Any

from rexlit.app.ports.privilege import PrivilegeFinding
from rexlit.ingest.extract import extract_document


class PrivilegePatternsAdapter:
    """Pattern-based privilege detector implementing PrivilegePort.

    Detects:
    - Attorney domains: configured list of legal firm domains
    - Attorney names: configurable list of known attorney names
    - Legal keywords: "attorney-client", "privileged", "work product", "confidential legal advice"

    Always offline (requires_online() -> False).
    """

    # Default legal keywords
    DEFAULT_KEYWORDS = [
        "attorney-client privilege",
        "attorney client privilege",
        "work product",
        "privileged communication",
        "confidential legal advice",
        "attorney work product",
        "lawyer client privilege",
        "legal advice",
        "protected by privilege",
        "subject to privilege",
    ]

    def __init__(self, profile: dict[str, Any] | None = None):
        """Initialize privilege detector with optional profile.

        Args:
            profile: Profile dict with keys:
                - attorney_domains: list of legal firm domains (e.g., ["lawfirm.com"])
                - attorney_names: list of attorney names to detect
                - keywords: list of privilege-related keywords (overrides defaults)
                - threshold: confidence threshold (0.0-1.0, default 0.75)
        """
        self.profile = profile or {}
        self.attorney_domains = set(
            self.profile.get("attorney_domains", [])
        )
        self.attorney_names = self.profile.get("attorney_names", [])
        self.keywords = self.profile.get("keywords", self.DEFAULT_KEYWORDS)
        self.threshold = self.profile.get("threshold", 0.75)

        # Compile name patterns if present
        if self.attorney_names:
            escaped_names = [re.escape(name) for name in self.attorney_names]
            self._name_pattern = re.compile(
                r"\b(" + "|".join(escaped_names) + r")\b",
                re.IGNORECASE
            )
        else:
            self._name_pattern = None

        # Compile keyword patterns
        if self.keywords:
            escaped_keywords = [re.escape(kw) for kw in self.keywords]
            self._keyword_pattern = re.compile(
                "|".join(escaped_keywords),
                re.IGNORECASE
            )
        else:
            self._keyword_pattern = None

    def analyze_text(
        self,
        text: str,
        *,
        threshold: float = 0.75,
    ) -> list[PrivilegeFinding]:
        """Analyze text for privilege indicators.

        Args:
            text: Text to analyze
            threshold: Confidence threshold (0.0-1.0)

        Returns:
            List of PrivilegeFinding objects meeting or exceeding threshold
        """
        findings = []
        effective_threshold = threshold or self.threshold

        # Check for attorney domain mentions (lower confidence)
        if self.attorney_domains:
            domain_pattern = r"@(" + "|".join(
                re.escape(d) for d in self.attorney_domains
            ) + r")"
            for match in re.finditer(domain_pattern, text, re.IGNORECASE):
                domain = match.group(1)
                if effective_threshold <= 0.5:  # Only include if threshold is low
                    finding = PrivilegeFinding(
                        rule="attorney_domain",
                        match_type="domain",
                        confidence=0.7,
                        snippet=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                    findings.append(finding)

        # Check for attorney names (medium confidence)
        if self._name_pattern:
            for match in self._name_pattern.finditer(text):
                if effective_threshold <= 0.8:
                    finding = PrivilegeFinding(
                        rule="attorney_name",
                        match_type="name",
                        confidence=0.8,
                        snippet=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                    findings.append(finding)

        # Check for privilege keywords (high confidence)
        if self._keyword_pattern:
            for match in self._keyword_pattern.finditer(text):
                if effective_threshold <= 0.9:
                    finding = PrivilegeFinding(
                        rule="privilege_keyword",
                        match_type="keyword",
                        confidence=0.9,
                        snippet=self._get_snippet(text, match.start(), match.end()),
                        start=match.start(),
                        end=match.end(),
                    )
                    findings.append(finding)

        # Filter by threshold
        return [f for f in findings if f.confidence >= effective_threshold]

    def analyze_document(
        self,
        path: str,
        *,
        threshold: float = 0.75,
    ) -> list[PrivilegeFinding]:
        """Analyze document for privilege indicators.

        Args:
            path: Path to document
            threshold: Confidence threshold (0.0-1.0)

        Returns:
            List of PrivilegeFinding objects with page numbers (if available)
        """
        try:
            doc_result = extract_document(Path(path))
            text = doc_result.text
        except Exception:
            return []

        findings = self.analyze_text(text, threshold=threshold)

        # If document has page info, attach it (simplified: no page tracking for now)
        return findings

    def get_supported_rules(self) -> list[str]:
        """Get list of supported detection rules.

        Returns:
            List of rule names
        """
        rules = []
        if self.attorney_domains:
            rules.append("attorney_domain")
        if self._name_pattern:
            rules.append("attorney_name")
        if self._keyword_pattern:
            rules.append("privilege_keyword")
        return rules or ["privilege_keyword"]  # Always support keyword detection

    def requires_online(self) -> bool:
        """Return True when adapter needs network access.

        Always returns False for pattern-based detection.
        """
        return False

    @staticmethod
    def _get_snippet(text: str, start: int, end: int, context: int = 50) -> str:
        """Get a text snippet with context around a match.

        Args:
            text: Full text
            start: Match start position
            end: Match end position
            context: Characters of context to include on each side

        Returns:
            Snippet with context
        """
        snippet_start = max(0, start - context)
        snippet_end = min(len(text), end + context)
        snippet = text[snippet_start:snippet_end]

        # Add ellipsis if truncated
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."

        return snippet
