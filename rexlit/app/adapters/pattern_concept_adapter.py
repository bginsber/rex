"""Offline regex-based concept detector with multi-factor confidence scoring.

Implements ADR 0008 pattern pre-filter with confidence-based escalation.
High confidence (≥0.85) → skip LLM
Uncertain (0.50-0.84) → escalate to LLM
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

from rexlit.app.ports.concept import ConceptFinding, ConceptPort

_logger = logging.getLogger(__name__)


# =============================================================================
# DETECTION PATTERNS
# =============================================================================

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

# =============================================================================
# MULTI-FACTOR CONFIDENCE PATTERNS
# =============================================================================

# Attorney domain indicators (boost confidence when present nearby)
ATTORNEY_DOMAIN_PATTERN = re.compile(
    r"@(?:[\w-]+\.)*(?:law|legal|attorney|counsel|lawfirm|esq)\b|"
    r"\b(?:esquire|esq\.?|attorney at law|counsel)\b",
    re.IGNORECASE,
)

# Quoted/forwarded text markers (reduce confidence - may be context, not substance)
# NOTE: All patterns use non-greedy [^\n]*? to prevent ReDoS (catastrophic backtracking)
QUOTED_TEXT_PATTERN = re.compile(
    r"^[>\|]{1,}\s*|"  # Quote markers at line start (> or | followed by content)
    r"(?:^|\n)-{3,}[^\n]*?(?:forwarded|original)[^\n]*?-{3,}|"  # Forwarded headers
    r"(?:^|\n)on\s+[^\n]{1,50}?\s+wrote:\s*$|"  # "On ... wrote:" reply headers (bounded)
    r"(?:^|\n)from:[^\n]*\nsent:[^\n]*\nto:|"  # Outlook-style headers in body
    r"\[cid:|<image\d+\.",  # Embedded image references
    re.IGNORECASE | re.MULTILINE,
)

# Strong legal context (boost confidence)
STRONG_LEGAL_CONTEXT_PATTERN = re.compile(
    r"\b(?:hereby|pursuant to|in accordance with|notwithstanding|"
    r"whereas|stipulate|enjoin|adjudicate|memorandum of law|"
    r"motion to|brief in support|declaration of)\b",
    re.IGNORECASE,
)

# Base confidence scores per concept type
BASE_CONFIDENCE: dict[str, float] = {
    "EMAIL_HEADER": 0.80,
    "EMAIL_ADDRESS": 0.65,
    "LEGAL_ADVICE": 0.70,
    "KEY_PARTY": 0.60,
    "HOTDOC": 0.75,
    "RESPONSIVE": 0.55,
}

# Confidence thresholds for escalation (per ADR 0008)
HIGH_CONFIDENCE_THRESHOLD = 0.85
UNCERTAIN_LOWER_BOUND = 0.50


class PatternConceptAdapter(ConceptPort):
    """Heuristic regex detector for offline highlighting with multi-factor scoring.

    Detects five concept categories:
    - EMAIL_COMMUNICATION: Email headers and addresses
    - LEGAL_ADVICE: Privilege markers and attorney-client indicators
    - KEY_PARTY: Plaintiffs, defendants, patent/contract references
    - HOTDOC: Smoking guns, admissions, intent to destroy evidence
    - RESPONSIVE: Claim-related terms, litigation keywords

    Multi-factor confidence scoring (ADR 0008):
    - Base confidence per pattern type
    - Boost for attorney domain nearby (+0.10)
    - Boost for strong legal context (+0.05)
    - Boost for multiple concept types in region (+0.05 per additional type)
    - Penalty for quoted/forwarded text (-0.15)

    Findings with confidence < 0.85 are flagged for LLM refinement.
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
        """Analyze text for legal concepts with multi-factor confidence scoring.

        Args:
            text: Text to analyze
            concepts: Concept types to detect (None = all)
            threshold: Minimum confidence threshold
            page: Optional page number to assign to findings

        Returns:
            List of concept findings with multi-factor confidence scores
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

        # Apply multi-factor scoring to all findings
        findings = self._apply_multi_factor_scoring(text, findings, threshold)

        return findings

    def refine_findings(
        self,
        text: str,
        findings: list[ConceptFinding],
        *,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Pattern adapter returns findings unchanged (no LLM capability).

        LLM adapters override this to provide context-aware refinement.
        """
        return findings

    def _apply_multi_factor_scoring(
        self,
        text: str,
        findings: list[ConceptFinding],
        threshold: float,
    ) -> list[ConceptFinding]:
        """Apply multi-factor confidence adjustments to findings.

        Scoring factors (per ADR 0008):
        - Attorney domain nearby: +0.10
        - Strong legal context: +0.05
        - Multiple concepts in region: +0.05 per additional type
        - Quoted/forwarded text: -0.15

        Performance: Uses O(n log n) sorted index for nearby concept lookup
        instead of O(n²) nested iteration.
        """
        if not findings:
            return findings

        # Pre-compute context signals for efficiency
        attorney_matches = list(ATTORNEY_DOMAIN_PATTERN.finditer(text))
        quoted_matches = list(QUOTED_TEXT_PATTERN.finditer(text))
        legal_context_matches = list(STRONG_LEGAL_CONTEXT_PATTERN.finditer(text))

        # Build sorted index for O(n log n) nearby concept lookup
        nearby_index = self._build_nearby_index(findings, window=500)

        scored_findings: list[ConceptFinding] = []

        for idx, finding in enumerate(findings):
            factors: dict[str, float] = {"base": finding.confidence}

            # Check for attorney domain within 300 chars
            has_attorney = self._has_nearby_match(
                finding.start, finding.end, attorney_matches, window=300
            )
            if has_attorney:
                factors["attorney_domain"] = 0.10

            # Check for strong legal context within 200 chars
            has_legal_context = self._has_nearby_match(
                finding.start, finding.end, legal_context_matches, window=200
            )
            if has_legal_context:
                factors["legal_context"] = 0.05

            # Check for multiple concept types in region (O(1) lookup via index)
            nearby_concepts = nearby_index.get(idx, 0)
            if nearby_concepts > 0:
                factors["multi_concept"] = 0.05 * min(nearby_concepts, 3)

            # Penalty for quoted/forwarded text
            is_quoted = self._has_nearby_match(
                finding.start, finding.end, quoted_matches, window=100
            )
            if is_quoted:
                factors["quoted_text"] = -0.15

            # Compute final confidence
            final_confidence = sum(factors.values())
            final_confidence = max(threshold, min(1.0, final_confidence))

            # Determine if needs LLM refinement
            needs_refinement = (
                final_confidence >= UNCERTAIN_LOWER_BOUND
                and final_confidence < HIGH_CONFIDENCE_THRESHOLD
            )

            scored_findings.append(
                ConceptFinding(
                    concept=finding.concept,
                    category=finding.category,
                    confidence=final_confidence,
                    start=finding.start,
                    end=finding.end,
                    page=finding.page,
                    snippet_hash=finding.snippet_hash,
                    reasoning_hash=finding.reasoning_hash,
                    confidence_factors=factors,
                    needs_refinement=needs_refinement,
                )
            )

        return scored_findings

    @staticmethod
    def _build_nearby_index(
        findings: list[ConceptFinding],
        window: int,
    ) -> dict[int, int]:
        """Build index of nearby concept counts using sorted position index.

        Returns dict mapping finding index → count of distinct nearby concept types.

        Complexity: O(n log n) sort + O(n * k) where k = avg findings in window.
        For typical legal documents, k << n, making this much faster than O(n²).
        """
        import bisect

        if not findings:
            return {}

        n = len(findings)
        if n <= 1:
            return {0: 0} if n == 1 else {}

        # Build sorted index: list of (start_pos, original_index)
        sorted_by_start = sorted(
            [(f.start, idx) for idx, f in enumerate(findings)],
            key=lambda x: x[0],
        )
        starts = [x[0] for x in sorted_by_start]
        indices = [x[1] for x in sorted_by_start]

        result: dict[int, int] = {}

        for idx, f in enumerate(findings):
            range_start = max(0, f.start - window)
            range_end = f.end + window

            # Binary search to find range of findings that might overlap
            left = bisect.bisect_left(starts, range_start - window)
            right = bisect.bisect_right(starts, range_end)

            # Collect distinct concepts in range (excluding self)
            nearby_types: set[str] = set()
            for i in range(left, min(right, n)):
                other_idx = indices[i]
                if other_idx == idx:
                    continue
                other = findings[other_idx]
                # Verify overlap (start already in range, check end)
                if other.end >= range_start:
                    nearby_types.add(other.concept)

            result[idx] = len(nearby_types)

        return result

    @staticmethod
    def _has_nearby_match(
        start: int,
        end: int,
        matches: list[re.Match[str]],
        window: int,
    ) -> bool:
        """Check if any match is within window chars of the finding."""
        for m in matches:
            if (m.start() <= end + window) and (m.end() >= start - window):
                return True
        return False

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
        except Exception as e:
            _logger.warning(
                "PDF extraction failed for %s, falling back to text: %s",
                path,
                e,
            )
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
        """Detect email headers and addresses with differentiated base confidence."""
        findings: list[ConceptFinding] = []
        for match in EMAIL_HEADER_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="EMAIL_COMMUNICATION",
                    category="communication",
                    confidence=max(threshold, BASE_CONFIDENCE["EMAIL_HEADER"]),
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
                    confidence=max(threshold, BASE_CONFIDENCE["EMAIL_ADDRESS"]),
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
        """Detect privilege markers with base confidence for context scoring."""
        findings: list[ConceptFinding] = []
        for match in LEGAL_ADVICE_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="LEGAL_ADVICE",
                    category="privilege",
                    confidence=max(threshold, BASE_CONFIDENCE["LEGAL_ADVICE"]),
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
        """Detect key party mentions with base confidence for context scoring."""
        findings: list[ConceptFinding] = []
        for match in KEY_PARTY_PATTERN.finditer(text):
            findings.append(
                ConceptFinding(
                    concept="KEY_PARTY",
                    category="entity",
                    confidence=max(threshold, BASE_CONFIDENCE["KEY_PARTY"]),
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
            findings.append(
                ConceptFinding(
                    concept="HOTDOC",
                    category="hotdoc",
                    confidence=max(threshold, BASE_CONFIDENCE["HOTDOC"]),
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
                    confidence=max(threshold, BASE_CONFIDENCE["RESPONSIVE"]),
                    start=match.start(),
                    end=match.end(),
                    page=page,
                    snippet_hash=None,
                )
            )
        return findings
