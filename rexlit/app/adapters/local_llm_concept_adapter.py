"""Local LLM-backed concept detector (LM Studio/OpenAI-compatible API)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from rexlit.app.ports.concept import ConceptFinding, ConceptPort


def _hash_snippet(snippet: str) -> str:
    return hashlib.sha256(snippet.encode("utf-8")).hexdigest()


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
    """Lightweight concept detector intended for local LM Studio usage.

    If LM Studio/OpenAI client is unavailable, falls back to fast heuristics.
    """

    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._api_base = api_base
        self._api_key = api_key
        self._model = model
        self._client = None
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=api_key or "lm-studio",
                base_url=api_base or "http://localhost:1234/v1",
            )
        except ModuleNotFoundError:
            # Optional dependency; heuristics will handle detection
            self._client = None

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
        except Exception:
            # Fall back to heuristics on any failure
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
