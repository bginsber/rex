"""Groq Cloud adapter for OSS-20b-safeguard privilege detection.

This adapter integrates Groq Cloud's OpenAI-compatible API to call the
openai/gpt-oss-safeguard-20b model for policy-based privilege reasoning.

Key features:
- Online-only (requires --online flag per ADR 0001)
- Uses Groq Cloud API for fast inference on dedicated hardware
- Converts policy decisions to PrivilegeFinding objects
- Graceful error handling with clear messages
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from rexlit.app.ports.privilege import PrivilegeFinding, PrivilegePort
from rexlit.ingest.extract import extract_document
from rexlit.utils.json_parsing import parse_model_json_response

logger = logging.getLogger(__name__)


class GroqPrivilegeAdapter:
    """Groq Cloud adapter for privilege detection using OSS-20b-safeguard.

    This adapter calls Groq Cloud's API to use the openai/gpt-oss-safeguard-20b
    model for policy-based privilege classification. It requires online mode
    and a valid GROQ_API_KEY.

    Example:
        >>> adapter = GroqPrivilegeAdapter(
        ...     api_key="gsk_...",
        ...     policy_path="policies/juul_privilege_stage1.txt",
        ... )
        >>> findings = adapter.analyze_text(
        ...     text="Email from attorney@law.com: Here is my legal opinion...",
        ...     threshold=0.75,
        ... )
        >>> print(findings)  # [PrivilegeFinding(rule="groq_policy", ...)]
    """

    def __init__(
        self,
        api_key: str | None = None,
        policy_path: str | Path | None = None,
        *,
        api_base: str = "https://api.groq.com/openai/v1",
        model: str = "openai/gpt-oss-safeguard-20b",
        max_tokens: int = 2000,
    ) -> None:
        """Initialize Groq Cloud privilege adapter.

        Args:
            api_key: Groq Cloud API key (defaults to GROQ_API_KEY env var)
            policy_path: Path to privilege policy template file
            api_base: Groq API base URL (default: https://api.groq.com/openai/v1)
            model: Model identifier (default: openai/gpt-oss-safeguard-20b)
            max_tokens: Maximum tokens for model generation (default: 2000)

        Raises:
            RuntimeError: If API key not provided and GROQ_API_KEY env var not set
            FileNotFoundError: If policy_path provided but file not found
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Groq API key required. Set GROQ_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.api_base = api_base
        self.model = model
        self.max_tokens = max_tokens

        # Load policy template
        self.policy_text = self._load_policy(policy_path)

    def analyze_text(
        self,
        text: str,
        *,
        threshold: float = 0.75,
    ) -> list[PrivilegeFinding]:
        """Analyze text for privilege indicators using Groq Cloud API.

        Args:
            text: Text to analyze
            threshold: Confidence threshold (0.0-1.0); findings below are filtered

        Returns:
            List of PrivilegeFinding objects meeting or exceeding threshold

        Raises:
            RuntimeError: If API call fails or response is malformed
        """
        if not text.strip():
            return []

        # Verify API key is available (should be set at initialization)
        if not self.api_key:
            raise RuntimeError(
                "Groq API key not configured. Set GROQ_API_KEY environment variable "
                "or configure via settings."
            )

        # Construct prompt with policy and document text
        prompt = f"""{self.policy_text}

---

Classify the following document:

{text}

Provide your classification in JSON format as specified in the policy above."""

        # Call Groq Cloud API and parse response
        response = self._call_groq_api(prompt)
        decision = self._parse_response(response)

        # Convert policy decision to PrivilegeFinding objects
        findings = self._decision_to_findings(decision, text, threshold)
        return findings

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
        except Exception as e:
            logger.debug("Failed to extract document text from %s: %s", path, e, exc_info=True)
            return []

        findings = self.analyze_text(text, threshold=threshold)
        return findings

    def get_supported_rules(self) -> list[str]:
        """Get list of supported detection rules.

        Returns:
            List of rule names (always includes "groq_policy")
        """
        return ["groq_policy"]

    def requires_online(self) -> bool:
        """Return True when adapter needs network access.

        Groq Cloud adapter always requires online access.
        """
        return True

    def _call_groq_api(self, prompt: str) -> dict[str, Any]:
        """Call Groq Cloud API with the given prompt.

        Args:
            prompt: Full prompt including policy and document text

        Returns:
            API response dictionary

        Raises:
            RuntimeError: If API call fails
        """
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai package required for Groq Cloud adapter. "
                "Install with: pip install openai>=1.0.0"
            ) from e

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a privilege classification system for legal e-discovery."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.0,  # Deterministic output
            )

            # Extract content from response
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Empty response from Groq API")

            return {"content": content}
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}") from e

    def _parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON response from Groq API.

        Args:
            response: API response dictionary with "content" key

        Returns:
            Parsed decision dictionary with violation, labels, confidence, rationale

        Raises:
            ValueError: If response cannot be parsed
        """
        content = response.get("content", "")
        if not content:
            raise ValueError("Empty response content")

        try:
            return parse_model_json_response(content)
        except ValueError as e:
            raise ValueError(f"Failed to parse Groq API response: {e}") from e

    def _decision_to_findings(
        self,
        decision: dict[str, Any],
        text: str,
        threshold: float,
    ) -> list[PrivilegeFinding]:
        """Convert policy decision to PrivilegeFinding objects.

        Args:
            decision: Parsed decision dictionary
            text: Original document text
            threshold: Confidence threshold

        Returns:
            List of PrivilegeFinding objects
        """
        # Extract decision fields with type validation
        labels = decision.get("labels", [])
        if not isinstance(labels, list):
            labels = []

        confidence = float(decision.get("confidence", 0.0))
        violation_raw = decision.get("violation", 0)
        # Normalize violation to boolean (handle both int and str formats)
        violation = violation_raw == 1 or violation_raw == "1"

        # Only create findings if confidence meets threshold
        if confidence < threshold:
            return []

        # Create findings if violation detected OR labels present
        if not (violation or labels):
            return []

        # Find relevant text spans that indicate privilege
        snippet_start, snippet_end, snippet = self._extract_privilege_snippet(text)

        # Create finding
        finding = PrivilegeFinding(
            rule="groq_policy",
            match_type="policy_reasoning",
            confidence=confidence,
            snippet=snippet,
            start=snippet_start,
            end=snippet_end,
        )
        return [finding]

    def _extract_privilege_snippet(self, text: str) -> tuple[int, int, str]:
        """Extract a snippet from text highlighting privilege indicators.

        Returns:
            Tuple of (start_offset, end_offset, snippet_text)
        """
        privilege_keywords = [
            "attorney-client",
            "privileged",
            "work product",
            "confidential legal",
            "legal advice",
        ]

        # Default: first 200 chars
        snippet_start = 0
        snippet_end = min(200, len(text))

        # Try to find a keyword match for better context
        text_lower = text.lower()
        for keyword in privilege_keywords:
            idx = text_lower.find(keyword.lower())
            if idx >= 0:
                snippet_start = max(0, idx - 50)
                snippet_end = min(len(text), idx + len(keyword) + 50)
                break

        snippet = text[snippet_start:snippet_end]
        return snippet_start, snippet_end, snippet

    def _load_policy(self, policy_path: str | Path | None) -> str:
        """Load privilege policy template from file or use default.

        Args:
            policy_path: Explicit path to policy file, or None for default

        Returns:
            Policy text content
        """
        # If policy path explicitly provided, use it
        if policy_path:
            policy_path_obj = Path(policy_path)
            if not policy_path_obj.exists():
                raise FileNotFoundError(f"Policy template not found: {policy_path_obj}")
            return policy_path_obj.read_text(encoding="utf-8")

        # Try to load default policy from settings (if available)
        try:
            from rexlit.config import get_settings

            settings = get_settings()
            try:
                default_policy = settings.get_privilege_policy_path(stage=1)
                return default_policy.read_text(encoding="utf-8")
            except FileNotFoundError:
                pass  # Fall back to empty policy
        except Exception as e:
            logger.debug("Failed to load default policy from settings: %s", e)

        # Return empty policy (model will still work)
        return ""

