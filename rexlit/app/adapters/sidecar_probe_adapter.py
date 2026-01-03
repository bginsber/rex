"""Sidecar probe adapter for neural privilege classification.

This adapter calls the rexlit-guardrail-eval FastAPI sidecar running on a
remote GPU server. It uses linear probes on Llama representations for
fast, accurate privilege classification with hard negative detection.

Key features:
- Remote GPU inference (requires online mode)
- Circuit breaker pattern for resilience
- Batch classification support
- Surface marker detection (identifies over-labeling)

See: rexlit-guardrail-eval/src/api/app.py for sidecar API spec.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Literal

import httpx

from rexlit.app.ports.privilege_reasoning import PolicyDecision
from rexlit.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)


class SidecarConnectionError(Exception):
    """Raised when sidecar connection fails."""

    pass


class SidecarProbeAdapter:
    """Remote sidecar adapter for neural privilege classification.

    This adapter calls the rexlit-guardrail-eval FastAPI sidecar for
    privilege classification using linear probes on Llama representations.

    Privacy guarantees:
    - Document text is sent to the sidecar for classification
    - No reasoning chain is returned (probe-based, not generative)
    - Surface marker detection identifies potential over-labeling

    Example:
        >>> adapter = SidecarProbeAdapter(
        ...     base_url="http://gpu-server:8000",
        ...     timeout_seconds=10.0,
        ... )
        >>> decision = adapter.classify_privilege(
        ...     text="Email from attorney@law.com...",
        ...     threshold=0.75,
        ... )
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        circuit_breaker_threshold: int = 3,
        cot_salt: str | None = None,
    ) -> None:
        """Initialize sidecar probe adapter.

        Args:
            base_url: Sidecar API base URL (e.g., "http://gpu-server:8000")
            timeout_seconds: Request timeout in seconds
            circuit_breaker_threshold: Failures before circuit opens
            cot_salt: Salt for reasoning hash (generated if not provided)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.cot_salt = cot_salt or os.urandom(32).hex()

        # HTTP client with connection pooling
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
        )

        # Circuit breaker for resilience
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout_seconds=60.0,
        )

        self._model_version = "sidecar-probe-v1"

    def classify_privilege(
        self,
        text: str,
        *,
        threshold: float = 0.75,
        reasoning_effort: Literal["low", "medium", "high", "dynamic"] = "dynamic",
    ) -> PolicyDecision:
        """Classify document for privilege using sidecar probe.

        Args:
            text: Document text to classify
            threshold: Confidence threshold for automatic classification
            reasoning_effort: Ignored (probe-based, not LLM)

        Returns:
            PolicyDecision with probe-based classification
        """
        if not text.strip():
            return self._create_error_decision(
                "Empty document text",
                reasoning_effort if reasoning_effort != "dynamic" else "medium",
            )

        try:

            def _call_sidecar() -> dict[str, Any]:
                response = self._client.post(
                    "/classify",
                    json={
                        "text": text,
                        "document_id": None,
                    },
                )
                response.raise_for_status()
                return response.json()

            result = self.circuit_breaker.call(_call_sidecar)

        except CircuitBreakerOpen as e:
            return self._create_error_decision(
                str(e),
                reasoning_effort if reasoning_effort != "dynamic" else "medium",
            )
        except httpx.HTTPStatusError as e:
            self.circuit_breaker._on_failure()
            return self._create_error_decision(
                f"Sidecar HTTP {e.response.status_code}: {e.response.text[:200]}",
                reasoning_effort if reasoning_effort != "dynamic" else "medium",
            )
        except httpx.RequestError as e:
            self.circuit_breaker._on_failure()
            return self._create_error_decision(
                f"Sidecar connection error: {e}",
                reasoning_effort if reasoning_effort != "dynamic" else "medium",
            )
        except Exception as e:
            return self._create_error_decision(
                f"Sidecar error: {e}",
                reasoning_effort if reasoning_effort != "dynamic" else "medium",
            )

        return self._map_sidecar_response(
            result,
            threshold,
            reasoning_effort if reasoning_effort != "dynamic" else "medium",
        )

    def classify_batch(
        self,
        documents: list[tuple[str, str]],
        *,
        threshold: float = 0.75,
    ) -> list[PolicyDecision]:
        """Batch classify multiple documents.

        Args:
            documents: List of (doc_id, text) tuples
            threshold: Confidence threshold

        Returns:
            List of PolicyDecision objects
        """
        if not documents:
            return []

        try:

            def _call_batch() -> dict[str, Any]:
                request_docs = [
                    {"text": text, "document_id": doc_id}
                    for doc_id, text in documents
                ]
                response = self._client.post(
                    "/batch",
                    json={"documents": request_docs},
                    timeout=self.timeout * 10,  # Longer timeout for batch
                )
                response.raise_for_status()
                return response.json()

            result = self.circuit_breaker.call(_call_batch)

        except Exception as e:
            logger.warning("Batch classification failed: %s", e)
            return [
                self._create_error_decision(f"Batch error: {e}", "medium")
                for _ in documents
            ]

        decisions = []
        for item in result.get("results", []):
            decisions.append(self._map_sidecar_response(item, threshold, "medium"))

        return decisions

    def health_check(self) -> dict[str, Any]:
        """Check sidecar health status.

        Returns:
            Health response dict from sidecar
        """
        try:
            response = self._client.get("/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "status": "unreachable",
                "error": str(e),
            }

    def requires_online(self) -> bool:
        """Sidecar adapter requires network access."""
        return True

    def _map_sidecar_response(
        self,
        response: dict[str, Any],
        threshold: float,
        reasoning_effort: Literal["low", "medium", "high"],
    ) -> PolicyDecision:
        """Map sidecar API response to PolicyDecision.

        Sidecar response format:
        {
            "document_id": "DOC001",
            "privilege_score": 0.87,        # 0.0-1.0
            "privilege_category": "HIGH",   # HIGH/MEDIUM/LOW/UNLIKELY
            "surface_marker_flag": false,   # Over-labeling detection
            "confidence": 0.74              # Distance from 0.5
        }
        """
        privilege_score = float(response.get("privilege_score", 0.0))
        privilege_category = response.get("privilege_category", "UNLIKELY")
        surface_marker_flag = response.get("surface_marker_flag", False)
        confidence = float(response.get("confidence", 0.0))

        # Map category to labels
        labels: list[str] = []
        if privilege_category in ("HIGH", "MEDIUM"):
            labels.append("PRIVILEGED:PROBE")
        if surface_marker_flag:
            labels.append("FLAG:SURFACE_MARKER")

        # Generate reasoning hash from probe inputs
        hash_input = f"probe:{privilege_score:.4f}:{privilege_category}:{surface_marker_flag}"
        reasoning_hash = hashlib.sha256(
            (hash_input + self.cot_salt).encode()
        ).hexdigest()

        # Build summary
        summary_parts = [f"Probe score {privilege_score:.2f} ({privilege_category})"]
        if surface_marker_flag:
            summary_parts.append(
                "Surface marker detected but content classified non-privileged"
            )
        reasoning_summary = ". ".join(summary_parts)

        # needs_review if confidence below threshold OR category is MEDIUM (borderline)
        needs_review = (confidence < threshold) or (privilege_category == "MEDIUM")

        return PolicyDecision(
            labels=labels,
            confidence=confidence,
            needs_review=needs_review,
            reasoning_hash=reasoning_hash,
            reasoning_summary=reasoning_summary,
            full_reasoning_available=False,
            redaction_spans=[],
            model_version=self._model_version,
            policy_version="probe-v1",
            reasoning_effort=reasoning_effort,
            decision_ts=datetime.utcnow().isoformat(),
        )

    def _create_error_decision(
        self,
        error_msg: str,
        reasoning_effort: Literal["low", "medium", "high"],
    ) -> PolicyDecision:
        """Create fallback decision when sidecar fails."""
        return PolicyDecision(
            labels=[],
            confidence=0.0,
            needs_review=True,
            reasoning_hash="",
            reasoning_summary=f"Error: {error_msg}",
            full_reasoning_available=False,
            redaction_spans=[],
            model_version=self._model_version,
            policy_version="error",
            reasoning_effort=reasoning_effort,
            decision_ts=datetime.utcnow().isoformat(),
            error_message=error_msg,
        )

    def close(self) -> None:
        """Close HTTP client connection."""
        self._client.close()

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        try:
            self._client.close()
        except Exception:
            pass
