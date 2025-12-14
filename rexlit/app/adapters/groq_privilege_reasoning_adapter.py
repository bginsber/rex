"""Groq Cloud adapter wrapper for PrivilegeReasoningPort interface.

This adapter wraps GroqPrivilegeAdapter to provide the PrivilegeReasoningPort
interface required by the CLI privilege classification commands.

Key features:
- Wraps GroqPrivilegeAdapter to bridge interface mismatch
- Converts PrivilegeFinding results to PolicyDecision format
- Implements privacy-preserving reasoning hash and summary
- Online-only (requires --online flag and GROQ_API_KEY)
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Literal

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter
from rexlit.app.ports.privilege_reasoning import (
    PolicyDecision,
    RedactionSpan,
)

logger = logging.getLogger(__name__)


class GroqPrivilegeReasoningAdapter:
    """Wrapper adapter that bridges GroqPrivilegeAdapter to PrivilegeReasoningPort.

    This adapter wraps GroqPrivilegeAdapter and implements the PrivilegeReasoningPort
    interface, converting the Groq adapter's PrivilegeFinding results into
    PolicyDecision objects required by the CLI.

    Privacy guarantees:
    - Full reasoning/rationale is SHA-256 hashed (salted)
    - Only redacted summaries (no excerpts) are logged
    - Matches PrivilegeSafeguardAdapter privacy model

    Example:
        >>> groq_adapter = GroqPrivilegeAdapter(
        ...     api_key="gsk_...",
        ...     policy_path="policies/privilege_groq_v1.txt",
        ... )
        >>> reasoning_adapter = GroqPrivilegeReasoningAdapter(groq_adapter)
        >>> decision = reasoning_adapter.classify_privilege(
        ...     text="Email from attorney@law.com...",
        ...     threshold=0.75,
        ...     reasoning_effort="dynamic",
        ... )
        >>> print(decision.labels)  # ["PRIVILEGED:ACP"]
        >>> print(decision.reasoning_hash)  # "a3f2b1..."
    """

    def __init__(self, groq_adapter: GroqPrivilegeAdapter, *, cot_salt: str | None = None) -> None:
        """Initialize Groq privilege reasoning adapter.

        Args:
            groq_adapter: Wrapped GroqPrivilegeAdapter instance
            cot_salt: Salt for reasoning hash (generated if not provided)

        Raises:
            ValueError: If groq_adapter is None
        """
        if groq_adapter is None:
            raise ValueError("groq_adapter cannot be None")

        self.groq = groq_adapter
        self.cot_salt = cot_salt or os.urandom(32).hex()

    def classify_privilege(
        self,
        text: str,
        *,
        threshold: float = 0.75,
        reasoning_effort: Literal["low", "medium", "high", "dynamic"] = "dynamic",
    ) -> PolicyDecision:
        """Classify document for privilege using Groq Cloud API.

        Args:
            text: Document text to classify
            threshold: Confidence threshold for automatic classification (0.0-1.0).
                      Decisions below threshold set needs_review=True.
            reasoning_effort: Reasoning depth control (ignored for Groq, but required by protocol)

        Returns:
            PolicyDecision with privacy-preserving reasoning fields

        Raises:
            RuntimeError: If API call fails or response is malformed
        """
        if not text.strip():
            return PolicyDecision(
                labels=[],
                confidence=0.0,
                needs_review=True,
                error_message="Empty document text",
                model_version=self.groq.model,
                reasoning_effort=reasoning_effort,
            )

        try:
            # Access internal methods to get raw decision dict before conversion to PrivilegeFinding
            # Construct prompt same way GroqPrivilegeAdapter does
            prompt = f"""{self.groq.policy_text}

---

Classify the following document:

{text}

Provide your classification in JSON format as specified in the policy above."""

            # Call Groq API and parse response
            response = self.groq._call_groq_api(prompt)
            decision_dict = self.groq._parse_response(response)

            # Extract fields from decision dict
            labels = decision_dict.get("labels", [])
            if not isinstance(labels, list):
                labels = []

            confidence = float(decision_dict.get("confidence", 0.0))
            rationale = decision_dict.get("rationale", "") or decision_dict.get("reasoning", "")

            # Hash reasoning/rationale for privacy-preserving audit trail
            reasoning_hash = self._hash_reasoning(rationale) if rationale else ""

            # Create redacted summary without privileged excerpts
            reasoning_summary = self._redact_summary(rationale) if rationale else ""

            # Parse redaction spans if present
            redaction_spans = []
            for span_data in decision_dict.get("redaction_spans", []):
                try:
                    redaction_spans.append(RedactionSpan(**span_data))
                except Exception:
                    # Skip malformed spans
                    logger.debug("Skipping malformed redaction span: %s", span_data)
                    pass

            # Get policy version (hash of policy text)
            policy_version = self._get_policy_version()

            return PolicyDecision(
                labels=labels,
                confidence=confidence,
                needs_review=(confidence < threshold),
                reasoning_hash=reasoning_hash,
                reasoning_summary=reasoning_summary,
                full_reasoning_available=False,  # Groq doesn't support vault storage
                redaction_spans=redaction_spans,
                model_version=self.groq.model,
                policy_version=policy_version,
                reasoning_effort=reasoning_effort,
                decision_ts=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error("Groq privilege classification failed: %s", e, exc_info=True)
            return PolicyDecision(
                labels=[],
                confidence=0.0,
                needs_review=True,
                error_message=f"Classification failed: {e}",
                model_version=self.groq.model,
                reasoning_effort=reasoning_effort,
            )

    def requires_online(self) -> bool:
        """Check if this adapter requires online/network access.

        Returns:
            True (Groq Cloud adapter always requires online access)
        """
        return True

    def _hash_reasoning(self, reasoning: str) -> str:
        """Hash full reasoning with salt for privacy-preserving audit trail.

        Args:
            reasoning: Full reasoning/rationale text from model

        Returns:
            SHA-256 hash hex string
        """
        return hashlib.sha256((reasoning + self.cot_salt).encode()).hexdigest()

    def _redact_summary(self, full_cot: str) -> str:
        """Redact excerpts from CoT, keeping only policy citations.

        Privacy requirement: Remove any quoted text or document excerpts.

        Args:
            full_cot: Full chain-of-thought reasoning text

        Returns:
            Redacted summary string (max 200 chars)
        """
        lines = full_cot.split("\n")
        safe_lines = []

        for line in lines:
            # Skip lines with quoted text or excerpts
            if '"' in line or "excerpt:" in line.lower() or "states:" in line.lower():
                continue
            safe_lines.append(line)

        summary = " ".join(safe_lines)
        # Truncate to max 200 chars for audit log brevity
        return summary[:200] if len(summary) > 200 else summary

    def _get_policy_version(self) -> str:
        """Get policy version identifier (hash of policy text).

        Returns:
            Policy version string (hash or "unknown")
        """
        try:
            policy_text = self.groq.policy_text
            if policy_text:
                policy_hash = hashlib.sha256(policy_text.encode()).hexdigest()[:16]
                return f"groq-{policy_hash}"
        except Exception as e:
            logger.debug("Failed to compute policy version: %s", e)

        return "unknown"

