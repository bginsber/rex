"""Offline regex-based concept detector."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from rexlit.app.ports.concept import ConceptFinding, ConceptPort


# Communication patterns
EMAIL_HEADER_PATTERN = re.compile(r"\b(from|to|cc|bcc):\s+\S+@\S+", re.IGNORECASE)
EMAIL_ADDRESS_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

# Privilege patterns
LEGAL_ADVICE_PATTERN = re.compile(
    r"\b(privileged|attorney[\-\s]client|work[\-\s]product|legal advice|counsel advises|"
    r"confidential communication|protected by privilege|litigation hold)\b",
    re.IGNORECASE,
)

# Entity patterns
KEY_PARTY_PATTERN = re.compile(
    r"\b(plaintiff|defendant|respondent|claimant|petitioner|appellee|appellant|"
    r"patent\s*(?:#|no\.?|number)?\s*\d+|contract\s*(?:#|no\.?)?\s*\d+)\b",
    re.IGNORECASE,
)

# Hot document indicators - smoking guns, admissions, intent to destroy
HOTDOC_PATTERN = re.compile(
    r"\b(violat(?:e|ed|es|ing)|smoking gun|destroy(?:ed|ing)?|shred(?:ded|ding)?|"
    r"cover(?:ed|ing)?\s+up|i knew this was wrong|don'?t tell anyone|"
    r"delete(?:d|ing)?\s+(?:all\s+)?(?:the\s+)?(?:files?|emails?|documents?)|"
    r"off the record|between us|keep(?:ing)?\s+this\s+quiet|"
    r"nobody needs to know|hide(?:s|ing)?(?:\s+(?:this|the|from))|"
    r"never happened|forget(?:\s+(?:this|about|we))|shouldn'?t have|"
    r"illegal|fraud(?:ulent)?|bribe|kickback|falsif(?:y|ied|ying))\b",
    re.IGNORECASE,
)

# Responsive content - claim-related terms
RESPONSIVE_PATTERN = re.compile(
    r"\b(claim(?:s|ed|ing)?|alleg(?:e|ed|es|ations?)|damages?|breach(?:ed|ing)?|"
    r"infring(?:e|ed|es|ement)|liabl(?:e|ility)|negligen(?:t|ce)|"
    r"malpractice|misrepresent(?:ed|ation)?|material(?:ly)?\s+false|"
    r"settlement|arbitrat(?:e|ion)|mediat(?:e|ion)|injunction|"
    r"discovery request|interrogator(?:y|ies)|subpoena|deposition|"
    r"demand letter|cease and desist|cause of action)\b",
    re.IGNORECASE,
)


class PatternConceptAdapter(ConceptPort):
    """Heuristic regex detector for offline highlighting.

    Detects five concept categories:
    - EMAIL_COMMUNICATION: Email headers and addresses
    - LEGAL_ADVICE: Privilege markers and attorney-client indicators
    - KEY_PARTY: Plaintiffs, defendants, patent/contract references
    - HOTDOC: Smoking guns, admissions, intent to destroy evidence
    - RESPONSIVE: Claim-related terms, litigation keywords
    """

    def __init__(self) -> None:
        self._supported = [
            "EMAIL_COMMUNICATION",
            "LEGAL_ADVICE",
            "KEY_PARTY",
            "HOTDOC",
            "RESPONSIVE",
        ]

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
        page: int | None = None,
    ) -> list[ConceptFinding]:
        """Analyze text for legal concepts.

        Args:
            text: Text to analyze
            concepts: Concept types to detect (None = all)
            threshold: Minimum confidence threshold
            page: Optional page number to assign to findings

        Returns:
            List of concept findings
        """
        target = set(concepts) if concepts else set(self._supported)
        findings: list[ConceptFinding] = []

        if "EMAIL_COMMUNICATION" in target:
            findings.extend(self._find_email(text, threshold, page))

        if "LEGAL_ADVICE" in target:
            findings.extend(self._find_legal_advice(text, threshold, page))

        if "KEY_PARTY" in target:
            findings.extend(self._find_key_party(text, threshold, page))

        if "HOTDOC" in target:
            findings.extend(self._find_hotdoc(text, threshold, page))

        if "RESPONSIVE" in target:
            findings.extend(self._find_responsive(text, threshold, page))

        return findings

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Analyze document for legal concepts with page-aware detection.

        For PDFs, extracts text per-page so findings have accurate page numbers.
        For other file types, reads as plain text with page=1.
        """
        file_path = Path(path)
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return self._analyze_pdf(file_path, concepts, threshold)

        # Plain text / other formats - single page
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        return self.analyze_text(text, concepts=concepts, threshold=threshold, page=1)

    def _analyze_pdf(
        self,
        path: Path,
        concepts: list[str] | None,
        threshold: float,
    ) -> list[ConceptFinding]:
        """Extract text from PDF pages and analyze with page numbers."""
        try:
            import fitz  # type: ignore[import]
        except ImportError:
            # Fallback: read as text without page info
            with open(path, "rb") as f:
                text = f.read().decode("utf-8", errors="ignore")
            return self.analyze_text(text, concepts=concepts, threshold=threshold, page=1)

        findings: list[ConceptFinding] = []
        try:
            doc = fitz.open(str(path))
            for page_index in range(doc.page_count):
                page_text = doc[page_index].get_text()
                page_findings = self.analyze_text(
                    page_text,
                    concepts=concepts,
                    threshold=threshold,
                    page=page_index + 1,  # 1-indexed pages
                )
                findings.extend(page_findings)
            doc.close()
        except Exception:
            # Fallback on any fitz error
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read()
            return self.analyze_text(text, concepts=concepts, threshold=threshold, page=1)

        return findings

    def get_supported_concepts(self) -> list[str]:
        return list(self._supported)

    def requires_online(self) -> bool:
        return False

    @staticmethod
    def _find_email(
        text: str, threshold: float, page: int | None = None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in EMAIL_HEADER_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="EMAIL_COMMUNICATION",
                    category="communication",
                    confidence=max(threshold, 0.9),
                    start=match.start(),
                    end=match.end(),
                    page=page,
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
                    page=page,
                    snippet_hash=None,
                )
            )
        return findings

    @staticmethod
    def _find_legal_advice(
        text: str, threshold: float, page: int | None = None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in LEGAL_ADVICE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="LEGAL_ADVICE",
                    category="privilege",
                    confidence=max(threshold, 0.8),
                    start=match.start(),
                    end=match.end(),
                    page=page,
                    snippet_hash=None,
                )
            )
        return findings

    @staticmethod
    def _find_key_party(
        text: str, threshold: float, page: int | None = None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in KEY_PARTY_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="KEY_PARTY",
                    category="entity",
                    confidence=max(threshold, 0.75),
                    start=match.start(),
                    end=match.end(),
                    page=page,
                    snippet_hash=None,
                )
            )
        return findings

    @staticmethod
    def _find_hotdoc(
        text: str, threshold: float, page: int | None = None
    ) -> list[ConceptFinding]:
        """Detect hot document indicators - smoking guns and admissions."""
        findings: list[ConceptFinding] = []
        for match in HOTDOC_PATTERN.finditer(text):
            # HOTDOC findings get high confidence - these are serious indicators
            findings.append(
                ConceptFinding(
                    concept="HOTDOC",
                    category="hotdoc",
                    confidence=max(threshold, 0.85),
                    start=match.start(),
                    end=match.end(),
                    page=page,
                    snippet_hash=None,
                )
            )
        return findings

    @staticmethod
    def _find_responsive(
        text: str, threshold: float, page: int | None = None
    ) -> list[ConceptFinding]:
        """Detect responsive content - claim-related terms."""
        findings: list[ConceptFinding] = []
        for match in RESPONSIVE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="RESPONSIVE",
                    category="responsive",
                    confidence=max(threshold, 0.7),
                    start=match.start(),
                    end=match.end(),
                    page=page,
                    snippet_hash=None,
                )
            )
        return findings
