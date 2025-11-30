"""Offline regex-based concept detector."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rexlit.app.ports.concept import ConceptFinding, ConceptPort

if TYPE_CHECKING:
    from rexlit.ingest.extract import ExtractedContent


# Email patterns
EMAIL_HEADER_PATTERN = re.compile(r"\b(from|to|cc|bcc):\s+\S+@\S+", re.IGNORECASE)
EMAIL_ADDRESS_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

# Legal advice / privilege patterns
LEGAL_ADVICE_PATTERN = re.compile(
    r"\b(privileged|attorney\-client|work product|legal advice|counsel advises)\b",
    re.IGNORECASE,
)
PRIVILEGE_ASSERTION_PATTERN = re.compile(
    r"\b(do not forward|confidential|foia exempt|attorney eyes only|litigation hold"
    r"|protected by|work-product doctrine|prepared in anticipation)\b",
    re.IGNORECASE,
)

# Key party patterns
KEY_PARTY_PATTERN = re.compile(
    r"\b(plaintiff|defendant|respondent|claimant|patent\s+\d+|petitioner|appellee|appellant)\b",
    re.IGNORECASE,
)

# Contract language patterns
CONTRACT_LANGUAGE_PATTERN = re.compile(
    r"\b(hereby|whereas|covenant|indemnify|warrant|representations?\s+and\s+warranties"
    r"|force majeure|governing law|arbitration|liquidated damages|non-compete"
    r"|confidentiality agreement|non-disclosure|severability)\b",
    re.IGNORECASE,
)

# Date/deadline patterns for timeline analysis
DATE_DEADLINE_PATTERN = re.compile(
    r"\b(deadline|due date|expiration|termination date|effective date|closing date"
    r"|statute of limitations|response due|filing deadline|discovery cutoff)\b",
    re.IGNORECASE,
)

# Hot document indicators
HOT_DOC_PATTERN = re.compile(
    r"\b(smoking gun|i know this|we knew|should not have|violated|cover up|hide this"
    r"|destroy|shred|do not disclose|off the record|between us|delete this)\b",
    re.IGNORECASE,
)


class PatternConceptAdapter(ConceptPort):
    """Heuristic regex detector for offline highlighting."""

    def __init__(self) -> None:
        self._supported = [
            "EMAIL_COMMUNICATION",
            "LEGAL_ADVICE",
            "KEY_PARTY",
            "CONTRACT_LANGUAGE",
            "DATE_DEADLINE",
            "HOTDOC",
        ]

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> list[ConceptFinding]:
        """Analyze text for legal concepts.

        Args:
            text: The text to analyze
            concepts: List of concept types to detect (None = all supported)
            threshold: Minimum confidence threshold
            kwargs: Additional arguments (e.g. page_boundaries)
        """
        page_boundaries = kwargs.get("page_boundaries")
        target = set(concepts) if concepts else set(self._supported)
        findings: list[ConceptFinding] = []

        if "EMAIL_COMMUNICATION" in target:
            findings.extend(self._find_email(text, threshold, page_boundaries))

        if "LEGAL_ADVICE" in target:
            findings.extend(self._find_legal_advice(text, threshold, page_boundaries))

        if "KEY_PARTY" in target:
            findings.extend(self._find_key_party(text, threshold, page_boundaries))

        if "CONTRACT_LANGUAGE" in target:
            findings.extend(self._find_contract_language(text, threshold, page_boundaries))

        if "DATE_DEADLINE" in target:
            findings.extend(self._find_date_deadline(text, threshold, page_boundaries))

        if "HOTDOC" in target:
            findings.extend(self._find_hotdoc(text, threshold, page_boundaries))

        return findings

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Analyze document for legal concepts using proper extraction.

        Uses rexlit.ingest.extract to handle PDFs, DOCX, and text files properly.
        """
        from rexlit.ingest.extract import extract_document

        file_path = Path(path)
        extracted = extract_document(file_path)

        # Extract page boundaries from PDF for accurate page assignment
        page_boundaries = self._get_page_boundaries(file_path, extracted)

        return self.analyze_text(
            extracted.text,
            concepts=concepts,
            threshold=threshold,
            page_boundaries=page_boundaries,
        )

    def get_supported_concepts(self) -> list[str]:
        return list(self._supported)

    def requires_online(self) -> bool:
        return False

    def _get_page_boundaries(
        self, file_path: Path, extracted: "ExtractedContent"
    ) -> list[int] | None:
        """Extract page boundary offsets for multi-page documents."""
        if file_path.suffix.lower() != ".pdf":
            return None

        try:
            import fitz  # PyMuPDF
        except ImportError:
            return None

        try:
            doc = fitz.open(str(file_path))
            boundaries: list[int] = []
            current_offset = 0

            for page_num in range(len(doc)):
                boundaries.append(current_offset)
                page = doc[page_num]
                page_text = page.get_text()
                # Account for the double newline separator used in extract_pdf
                current_offset += len(page_text) + 2

            doc.close()
            return boundaries
        except Exception:
            return None

    def _offset_to_page(self, offset: int, page_boundaries: list[int] | None) -> int:
        """Convert character offset to 1-indexed page number."""
        if page_boundaries is None or len(page_boundaries) <= 1:
            return 1

        for i in range(len(page_boundaries) - 1, -1, -1):
            if offset >= page_boundaries[i]:
                return i + 1  # 1-indexed
        return 1

    def _find_email(
        self, text: str, threshold: float, page_boundaries: list[int] | None
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
                    page=self._offset_to_page(match.start(), page_boundaries),
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
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        return findings

    def _find_legal_advice(
        self, text: str, threshold: float, page_boundaries: list[int] | None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        # Primary legal advice patterns
        for match in LEGAL_ADVICE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="LEGAL_ADVICE",
                    category="privilege",
                    confidence=max(threshold, 0.85),
                    start=match.start(),
                    end=match.end(),
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        # Privilege assertion patterns (slightly lower confidence)
        for match in PRIVILEGE_ASSERTION_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="LEGAL_ADVICE",
                    category="privilege",
                    confidence=max(threshold, 0.75),
                    start=match.start(),
                    end=match.end(),
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        return findings

    def _find_key_party(
        self, text: str, threshold: float, page_boundaries: list[int] | None
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
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        return findings

    def _find_contract_language(
        self, text: str, threshold: float, page_boundaries: list[int] | None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in CONTRACT_LANGUAGE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="CONTRACT_LANGUAGE",
                    category="responsive",
                    confidence=max(threshold, 0.8),
                    start=match.start(),
                    end=match.end(),
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        return findings

    def _find_date_deadline(
        self, text: str, threshold: float, page_boundaries: list[int] | None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in DATE_DEADLINE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="DATE_DEADLINE",
                    category="entity",
                    confidence=max(threshold, 0.7),
                    start=match.start(),
                    end=match.end(),
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        return findings

    def _find_hotdoc(
        self, text: str, threshold: float, page_boundaries: list[int] | None
    ) -> list[ConceptFinding]:
        findings: list[ConceptFinding] = []
        for match in HOT_DOC_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="HOTDOC",
                    category="hotdoc",
                    confidence=max(threshold, 0.9),
                    start=match.start(),
                    end=match.end(),
                    page=self._offset_to_page(match.start(), page_boundaries),
                    snippet_hash=None,
                )
            )
        return findings
