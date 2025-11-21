"""Offline regex-based concept detector."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from rexlit.app.ports.concept import ConceptFinding, ConceptPort


EMAIL_HEADER_PATTERN = re.compile(r"\b(from|to|cc|bcc):\s+\S+@\S+", re.IGNORECASE)
EMAIL_ADDRESS_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
LEGAL_ADVICE_PATTERN = re.compile(
    r"\b(privileged|attorney\-client|work product|legal advice|counsel advises)\b",
    re.IGNORECASE,
)
KEY_PARTY_PATTERN = re.compile(r"\b(plaintiff|defendant|respondent|claimant|patent\s+\d+)\b", re.IGNORECASE)


class PatternConceptAdapter(ConceptPort):
    """Heuristic regex detector for offline highlighting."""

    def __init__(self) -> None:
        self._supported = ["EMAIL_COMMUNICATION", "LEGAL_ADVICE", "KEY_PARTY"]

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        target = set(concepts) if concepts else set(self._supported)
        findings: list[ConceptFinding] = []

        if "EMAIL_COMMUNICATION" in target:
            findings.extend(self._find_email(text, threshold))

        if "LEGAL_ADVICE" in target:
            findings.extend(self._find_legal_advice(text, threshold))

        if "KEY_PARTY" in target:
            findings.extend(self._find_key_party(text, threshold))

        return findings

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        with open(Path(path), "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        return self.analyze_text(text, concepts=concepts, threshold=threshold)

    def get_supported_concepts(self) -> list[str]:
        return list(self._supported)

    def requires_online(self) -> bool:
        return False

    @staticmethod
    def _find_email(text: str, threshold: float) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in EMAIL_HEADER_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="EMAIL_COMMUNICATION",
                    category="communication",
                    confidence=max(threshold, 0.9),
                    start=match.start(),
                    end=match.end(),
                    page=1,
                    snippet_hash=None,
                )
            )
        for match in EMAIL_ADDRESS_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="EMAIL_COMMUNICATION",
                    category="communication",
                    confidence=max(threshold, 0.85),
                    start=match.start(),
                    end=match.end(),
                    page=1,
                    snippet_hash=None,
                )
            )
        return findings

    @staticmethod
    def _find_legal_advice(text: str, threshold: float) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in LEGAL_ADVICE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="LEGAL_ADVICE",
                    category="privilege",
                    confidence=max(threshold, 0.8),
                    start=match.start(),
                    end=match.end(),
                    page=1,
                    snippet_hash=None,
                )
            )
        return findings

    @staticmethod
    def _find_key_party(text: str, threshold: float) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in KEY_PARTY_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="KEY_PARTY",
                    category="entity",
                    confidence=max(threshold, 0.75),
                    start=match.start(),
                    end=match.end(),
                    page=1,
                    snippet_hash=None,
                )
            )
        return findings
