"""Local LLM-backed concept detector (LM Studio/OpenAI-compatible API).

Implements ADR 0008 LLM refinement for uncertain pattern findings.
Used by HighlightService for confidence escalation (0.50-0.84 → LLM).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from rexlit.app.ports.concept import ConceptFinding, ConceptPort


def _hash_snippet(snippet: str) -> str:
    return hashlib.sha256(snippet.encode("utf-8")).hexdigest()


def _hash_reasoning(reasoning: str) -> str:
    """Hash reasoning for privacy-preserving audit (ADR 0008)."""
    return hashlib.sha256(reasoning.encode("utf-8")).hexdigest()


@dataclass
class _HeuristicRule:
    concept: str
    category: str
    keywords: tuple[str, ...]


HEURISTIC_RULES: tuple[_HeuristicRule, ...] = (
    _HeuristicRule(
        concept="EMAIL_COMMUNICATION",
        category="communication",
        keywords=("from:", "subject:", "@"),
    ),
    _HeuristicRule(
        concept="LEGAL_ADVICE",
        category="privilege",
        keywords=("counsel", "attorney", "legal advice", "privileged"),
    ),
    _HeuristicRule(
        concept="KEY_PARTY",
        category="entity",
        keywords=("plaintiff", "defendant", "party", "claim"),
    ),
    _HeuristicRule(
        concept="HOTDOC",
        category="hotdoc",
        keywords=("violate", "knew this was", "smoking gun", "destroy", "shred"),
    ),
    _HeuristicRule(
        concept="RESPONSIVE",
        category="responsive",
        keywords=("damages", "breach", "liable", "negligent", "settlement"),
    ),
)


class LocalLLMConceptAdapter(ConceptPort):
    """LLM-backed concept detector for local LM Studio usage.

    Implements two key functions:
    1. Full analysis: Detect concepts from scratch (analyze_text/analyze_document)
    2. Refinement: Refine uncertain pattern findings with context (refine_findings)

    If LM Studio/OpenAI client is unavailable, falls back to fast heuristics.

    Refinement follows ADR 0008:
    - Takes findings with 0.50-0.84 confidence
    - Analyzes surrounding context with LLM
    - Returns updated confidence scores
    - Stores reasoning hash for audit (no raw text)

    Security: API keys are not stored in instance variables to prevent exposure
    in logs, exceptions, or repr(). Keys are passed directly to the client.
    """

    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        import logging

        self._logger = logging.getLogger(__name__)
        self._api_base = api_base or "http://localhost:1234/v1"
        self._model = model
        # NOTE: Do NOT store api_key in instance variable (security)
        self._has_api_key = api_key is not None
        self._client = None
        self._client_available = False

        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=api_key or "lm-studio",
                base_url=self._api_base,
            )
            self._client_available = True
        except ModuleNotFoundError:
            self._logger.info(
                "OpenAI package not installed; LocalLLMConceptAdapter will use heuristics only"
            )
        except Exception as e:
            self._logger.warning(
                "Failed to initialize OpenAI client for LM Studio: %s", e
            )

    def __repr__(self) -> str:
        """Return safe representation without exposing credentials."""
        return (
            f"{self.__class__.__name__}("
            f"api_base={self._api_base!r}, "
            f"model={self._model!r}, "
            f"has_api_key={'[MASKED]' if self._has_api_key else 'None'}, "
            f"client_available={self._client_available})"
        )

    def _run_client(self, text: str, concepts: Iterable[str] | None, threshold: float) -> list[ConceptFinding]:
        """Attempt LM Studio inference; fall back to heuristics on any failure."""
        if self._client is None:
            return []
        try:
            response = self._client.chat.completions.create(
                model=self._model or "lmstudio-concept-model",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Detect legal concepts in the user text. "
                            "Return one JSON object per line with fields: "
                            "concept, category, confidence (0-1), start, end."
                        ),
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
                temperature=0.0,
                max_tokens=400,
            )
            content = response.choices[0].message.content or ""

            def _parse_line(line: str) -> tuple[str, str, float, int, int] | None:
                if not line:
                    return None
                if line.startswith("{"):
                    # Primary path: JSONL per system prompt
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        return None
                    if not isinstance(payload, dict):
                        return None
                    concept = str(payload.get("concept", "")).strip()
                    category = str(payload.get("category", "")).strip()
                    try:
                        confidence = float(payload.get("confidence"))
                        start = int(payload.get("start"))
                        end = int(payload.get("end"))
                    except (TypeError, ValueError):
                        return None
                    if not concept or not category:
                        return None
                    return concept, category, confidence, start, end

                # Fallback for legacy pipe-delimited responses
                parts = [part.strip() for part in line.split("|")]
                if len(parts) != 5:
                    return None
                concept, category, conf_str, start_str, end_str = parts
                try:
                    confidence = float(conf_str)
                    start = int(start_str)
                    end = int(end_str)
                except ValueError:
                    return None
                if not concept or not category:
                    return None
                return concept, category, confidence, start, end

            findings: list[ConceptFinding] = []
            for line in (entry.strip() for entry in content.splitlines()):
                parsed = _parse_line(line)
                if parsed is None:
                    continue
                concept, category, confidence, start, end = parsed
                if concepts and concept not in concepts:
                    continue
                if confidence < threshold:
                    continue
                snippet = text[start:end] if 0 <= start < end <= len(text) else ""
                findings.append(
                    ConceptFinding(
                        concept=concept,
                        category=category,
                        confidence=confidence,
                        start=start,
                        end=end,
                        snippet_hash=_hash_snippet(snippet) if snippet else None,
                    )
                )
            return findings
        except Exception as e:
            self._logger.warning(
                "LLM inference failed, falling back to heuristics: %s", e
            )
            return []

    def _run_heuristics(self, text: str, concepts: Iterable[str] | None, threshold: float) -> list[ConceptFinding]:
        lowered = text.lower()
        findings: list[ConceptFinding] = []
        for rule in HEURISTIC_RULES:
            if concepts and rule.concept not in concepts:
                continue
            for keyword in rule.keywords:
                idx = lowered.find(keyword)
                if idx == -1:
                    continue
                confidence = max(threshold, 0.65)
                snippet = text[idx : idx + len(keyword)]
                findings.append(
                    ConceptFinding(
                        concept=rule.concept,
                        category=rule.category,
                        confidence=confidence,
                        start=idx,
                        end=idx + len(keyword),
                        snippet_hash=_hash_snippet(snippet),
                    )
                )
                break
        return findings

    def refine_findings(
        self,
        text: str,
        findings: list[ConceptFinding],
        *,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Refine uncertain findings using LLM context analysis.

        Per ADR 0008, this method:
        1. Extracts context around each finding
        2. Asks LLM to evaluate if the concept is correctly identified
        3. Adjusts confidence based on LLM assessment
        4. Returns findings with updated confidence and reasoning hash

        Args:
            text: Original text for context extraction
            findings: Uncertain findings (typically 0.50-0.84 confidence)
            threshold: Minimum confidence threshold

        Returns:
            Refined findings with updated confidence scores
        """
        if not findings:
            return findings

        if self._client is None:
            # No LLM available - return findings unchanged
            return findings

        refined: list[ConceptFinding] = []
        for finding in findings:
            # Extract context window (200 chars before/after)
            context_start = max(0, finding.start - 200)
            context_end = min(len(text), finding.end + 200)
            context = text[context_start:context_end]
            match_text = text[finding.start : finding.end]

            # Ask LLM to evaluate
            try:
                new_confidence, reasoning = self._evaluate_with_llm(
                    context=context,
                    match_text=match_text,
                    concept=finding.concept,
                    category=finding.category,
                    original_confidence=finding.confidence,
                )

                refined.append(
                    ConceptFinding(
                        concept=finding.concept,
                        category=finding.category,
                        confidence=max(threshold, new_confidence),
                        start=finding.start,
                        end=finding.end,
                        page=finding.page,
                        snippet_hash=finding.snippet_hash,
                        reasoning_hash=_hash_reasoning(reasoning) if reasoning else None,
                        confidence_factors=finding.confidence_factors,
                        needs_refinement=False,  # Refinement complete
                    )
                )
            except Exception as e:
                self._logger.warning(
                    "LLM refinement failed for %s finding at %d-%d: %s",
                    finding.concept,
                    finding.start,
                    finding.end,
                    e,
                )
                refined.append(finding)

        return refined

    def _evaluate_with_llm(
        self,
        context: str,
        match_text: str,
        concept: str,
        category: str,
        original_confidence: float,
    ) -> tuple[float, str]:
        """Use LLM to evaluate a finding and return refined confidence.

        Returns:
            Tuple of (new_confidence, reasoning_text)
        """
        if self._client is None:
            return original_confidence, ""

        prompt = f"""Evaluate whether this text segment correctly identifies a legal concept.

CONTEXT (surrounding text):
{context}

MATCHED TEXT: "{match_text}"
DETECTED CONCEPT: {concept}
DETECTED CATEGORY: {category}
PATTERN CONFIDENCE: {original_confidence:.2f}

Analyze:
1. Is "{match_text}" correctly identified as {concept}?
2. Does the surrounding context support or contradict this classification?
3. Could this be a false positive (e.g., quoted text, hypothetical, negation)?

Respond with JSON only:
{{"confidence": 0.XX, "reasoning": "brief explanation without quoting document text"}}"""

        try:
            response = self._client.chat.completions.create(
                model=self._model or "lmstudio-concept-model",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a legal document analyst. Evaluate concept detections "
                            "and return refined confidence scores. Never quote document text "
                            "in your reasoning (privacy requirement). Respond with JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=200,
            )
            content = response.choices[0].message.content or ""

            # Parse JSON response
            # Handle markdown code blocks if present
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())
            confidence = float(result.get("confidence", original_confidence))
            reasoning = str(result.get("reasoning", ""))

            # Clamp confidence to valid range
            confidence = max(0.0, min(1.0, confidence))

            return confidence, reasoning

        except json.JSONDecodeError as e:
            self._logger.debug(
                "LLM response parsing failed for %s: %s", concept, e
            )
            return original_confidence, ""
        except Exception as e:
            self._logger.warning(
                "LLM evaluation failed for %s: %s", concept, e
            )
            return original_confidence, ""

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        findings = self._run_client(text, concepts, threshold)
        if findings:
            return findings
        return self._run_heuristics(text, concepts, threshold)

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        return self.analyze_text(text, concepts=concepts, threshold=threshold)

    def get_supported_concepts(self) -> list[str]:
        return [rule.concept for rule in HEURISTIC_RULES]

    def requires_online(self) -> bool:
        return False
