"""Privilege reasoning port interface for policy-based classification."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class RedactionSpan(BaseModel):
    """Represents a span of text requiring redaction.

    Privacy note: justification should not contain privileged excerpts.
    """

    category: str  # "CPI/PERSONNEL", "TRADE_SECRET", "FINANCIAL", etc.
    start: int  # Character offset (0-indexed)
    end: int  # Character offset (exclusive)
    justification: str  # Non-privileged explanation (e.g., "Contains salary information")


class PolicyDecision(BaseModel):
    """Privacy-preserving privilege classification decision.

    This model implements privacy controls to prevent inadvertent disclosure
    of privileged material in audit logs:

    - Full chain-of-thought (CoT) reasoning is hashed, not stored directly
    - Only a redacted summary (without excerpts) is logged
    - Optional encrypted vault storage for full CoT (requires explicit config)

    See ADR 0008 for privacy design rationale.
    """

    labels: list[str] = Field(
        default_factory=list,
        description="Classification labels (e.g., ['PRIVILEGED:ACP', 'RESPONSIVE', 'HOTDOC:4'])",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model confidence score (0.0-1.0)",
    )

    needs_review: bool = Field(
        default=False,
        description="True if confidence < threshold or model error occurred",
    )

    # Privacy-preserving reasoning fields
    reasoning_hash: str = Field(
        default="",
        description="SHA-256 hash of full CoT reasoning (salted)",
    )

    reasoning_summary: str = Field(
        default="",
        description="Redacted 1-2 sentence summary without privileged excerpts",
    )

    full_reasoning_available: bool = Field(
        default=False,
        description="True if full CoT is stored in encrypted vault",
    )

    # Redaction detection (Stage 3 output)
    redaction_spans: list[RedactionSpan] = Field(
        default_factory=list,
        description="Detected spans requiring redaction",
    )

    # Metadata
    model_version: str = Field(
        default="unknown",
        description="Model identifier (e.g., 'gpt-oss-safeguard-20b')",
    )

    policy_version: str = Field(
        default="unknown",
        description="Policy template version or hash",
    )

    reasoning_effort: Literal["low", "medium", "high", "dynamic"] = Field(
        default="medium",
        description="Reasoning effort level used for this decision",
    )

    decision_ts: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Decision timestamp (ISO 8601 UTC)",
    )

    error_message: str = Field(
        default="",
        description="Error message if classification failed",
    )

    @property
    def is_privileged(self) -> bool:
        """Check if document is classified as privileged."""
        return any("PRIVILEGED" in label.upper() for label in self.labels)

    @property
    def is_responsive(self) -> bool:
        """Check if document is classified as responsive."""
        return any("RESPONSIVE" in label.upper() for label in self.labels)

    @property
    def hotdoc_level(self) -> int | None:
        """Extract HOTDOC numeric level if present."""
        for label in self.labels:
            if label.upper().startswith("HOTDOC:"):
                try:
                    return int(label.split(":")[1])
                except (IndexError, ValueError):
                    pass
        return None


class PrivilegeReasoningPort(Protocol):
    """Port interface for privilege classification and reasoning.

    Adapters:
    - PrivilegeSafeguardAdapter: Self-hosted gpt-oss-safeguard-20b (offline)
    - Future: Pattern-based heuristic adapter (offline, fast)

    Privacy guarantees:
    - All adapters MUST hash full reasoning chains before audit logging
    - Reasoning summaries MUST NOT contain document excerpts or privileged text
    - Full CoT storage in encrypted vault is opt-in only

    Side effects:
    - Offline: All adapters run locally with no network calls
    - Audit: Decisions logged with hash/summary only (unless vault enabled)
    """

    def classify_privilege(
        self,
        text: str,
        *,
        threshold: float = 0.75,
        reasoning_effort: Literal["low", "medium", "high", "dynamic"] = "dynamic",
    ) -> PolicyDecision:
        """Classify document for attorney-client privilege.

        Args:
            text: Document text to classify
            threshold: Confidence threshold for automatic classification (0.0-1.0).
                      Decisions below threshold set needs_review=True.
            reasoning_effort: Reasoning depth control:
                - "low": Fast, basic pattern matching
                - "medium": Standard LLM reasoning
                - "high": Deep reasoning with policy citations
                - "dynamic": Adapter selects based on document complexity

        Returns:
            PolicyDecision with privacy-preserving reasoning fields

        Raises:
            RuntimeError: If adapter encounters unrecoverable error
        """
        ...

    def requires_online(self) -> bool:
        """Check if this adapter requires online/network access.

        Returns:
            False for all current adapters (self-hosted only)
        """
        ...
