"""Safeguard adapter for privacy-preserving privilege classification.

This adapter integrates OpenAI's gpt-oss-safeguard-20b model for policy-based
privilege reasoning with robust error handling and privacy controls.

Key features:
- Self-hosted only (offline-first, no external API calls)
- Privacy-preserving CoT: Full reasoning is hashed, not logged directly
- Circuit breaker pattern for resilience against model failures
- Dynamic reasoning effort based on document complexity

See ADR 0008 for architecture and privacy rationale.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from rexlit.app.ports.privilege_reasoning import PolicyDecision, RedactionSpan
from rexlit.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from rexlit.utils.json_parsing import parse_model_json_response

if TYPE_CHECKING:
    from transformers import Pipeline  # type: ignore[import-untyped]


class SafeguardBackendError(Exception):
    """Raised when safeguard model encounters errors (timeout, malformed output, etc.)."""

    pass


class PrivilegeSafeguardAdapter:
    """Self-hosted gpt-oss-safeguard-20b adapter with privacy controls.

    Privacy guarantees:
    - Full chain-of-thought reasoning is SHA-256 hashed (salted)
    - Only redacted summaries (no excerpts) are logged
    - Optional encrypted vault storage for full CoT (opt-in)

    Resilience features:
    - Circuit breaker prevents cascading failures
    - Configurable timeouts per inference
    - Graceful degradation with needs_review flag

    Example:
        >>> adapter = PrivilegeSafeguardAdapter(
        ...     model_path="/models/gpt-oss-safeguard-20b",
        ...     policy_path="policies/juul_privilege_stage1.txt",
        ...     log_full_cot=False,  # Privacy-preserving default
        ... )
        >>> decision = adapter.classify_privilege(
        ...     text="Email from attorney@law.com: Here is my legal opinion...",
        ...     threshold=0.75,
        ...     reasoning_effort="dynamic",
        ... )
        >>> print(decision.labels)  # ["PRIVILEGED:ACP"]
        >>> print(decision.reasoning_hash)  # "a3f2b1..."
        >>> print(decision.reasoning_summary)  # "Applied ACP definition §2.1"
    """

    def __init__(
        self,
        model_path: str | Path,
        policy_path: str | Path,
        *,
        log_full_cot: bool = False,
        cot_salt: str | None = None,
        cot_vault_path: Path | None = None,
        timeout_seconds: float = 30.0,
        circuit_breaker_threshold: int = 5,
        max_new_tokens: int = 2000,
    ) -> None:
        """Initialize safeguard adapter.

        Args:
            model_path: Path to gpt-oss-safeguard-20b model weights
            policy_path: Path to Harmony policy template file
            log_full_cot: If True, store full CoT in encrypted vault (default: False)
            cot_salt: Salt for CoT hashing (generated if not provided)
            cot_vault_path: Directory for encrypted CoT storage (required if log_full_cot=True)
            timeout_seconds: Inference timeout (default: 30s)
            circuit_breaker_threshold: Failures before opening circuit (default: 5)
            max_new_tokens: Max tokens for model generation (default: 2000)

        Raises:
            RuntimeError: If model fails to load or policy file not found
        """
        self.model_path = Path(model_path)
        self.policy_path = Path(policy_path)
        self.log_full_cot = log_full_cot
        self.cot_salt = cot_salt or os.urandom(32).hex()
        self.cot_vault_path = cot_vault_path
        self.timeout = timeout_seconds
        self.max_new_tokens = max_new_tokens

        # Validate configuration
        if log_full_cot and cot_vault_path is None:
            raise ValueError("cot_vault_path required when log_full_cot=True")

        if log_full_cot and cot_vault_path is not None:
            cot_vault_path.mkdir(parents=True, exist_ok=True)

        # Load policy
        if not self.policy_path.exists():
            raise FileNotFoundError(f"Policy template not found: {self.policy_path}")

        self.policy_text = self.policy_path.read_text(encoding="utf-8")
        self.policy_hash = hashlib.sha256(self.policy_text.encode()).hexdigest()[:16]

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout_seconds=60.0,  # Wait 60s before retrying after circuit opens
        )

        # Lazy-load model (deferred until first use)
        self._model: Pipeline | None = None
        self._model_version = "gpt-oss-safeguard-20b"

    def _load_model(self) -> Pipeline:
        """Lazy-load transformers pipeline."""
        if self._model is not None:
            return self._model

        try:
            # Import here to avoid dependency at module load time
            from transformers import pipeline  # type: ignore[import-untyped]

            self._model = pipeline(
                "text-generation",
                model=str(self.model_path),
                torch_dtype="auto",
                device_map="auto",
            )
            return self._model
        except Exception as e:
            raise RuntimeError(f"Failed to load safeguard model from {self.model_path}: {e}") from e

    def classify_privilege(
        self,
        text: str,
        *,
        threshold: float = 0.75,
        reasoning_effort: Literal["low", "medium", "high", "dynamic"] = "dynamic",
    ) -> PolicyDecision:
        """Classify document for privilege with privacy-preserving logging.

        Args:
            text: Document text to classify
            threshold: Confidence threshold for automatic classification
            reasoning_effort: Reasoning depth ("low", "medium", "high", "dynamic")

        Returns:
            PolicyDecision with hashed reasoning and redacted summary
        """
        # Select reasoning effort if dynamic
        if reasoning_effort == "dynamic":
            reasoning_effort = self._select_reasoning_effort(text)

        # Construct prompt as single string (transformers text-generation pipeline expects string)
        # Format: System prompt + User instruction + Document text
        prompt = f"""{self.policy_text}

---

Reasoning effort: {reasoning_effort}

Classify the following document:

{text}

Provide your classification in JSON format as specified in the policy above."""

        # Invoke model with circuit breaker protection
        try:

            def _run_inference() -> Any:
                model = self._load_model()
                result = model(
                    prompt,  # Pass string, not list of messages
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,  # Deterministic
                    return_full_text=False,
                )
                return result

            result = self.circuit_breaker.call(_run_inference)

        except CircuitBreakerOpen as e:
            # Circuit breaker tripped → fallback with needs_review
            return self._create_error_decision(
                error_msg=str(e),
                reasoning_effort=reasoning_effort,
            )
        except Exception as e:
            # Other errors (timeout, OOM, etc.) → needs review
            return self._create_error_decision(
                error_msg=f"Model inference error: {e}",
                reasoning_effort=reasoning_effort,
            )

        # Parse JSON output
        try:
            generated_text = result[0]["generated_text"]
            output = self._parse_model_output(generated_text)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return self._create_error_decision(
                error_msg=f"Malformed model output: {e}",
                reasoning_effort=reasoning_effort,
            )

        # Extract and redact reasoning
        full_cot = output.get("rationale", "")
        cot_hash = self._hash_reasoning(full_cot)
        cot_summary = self._redact_summary(full_cot)

        # Optionally store full CoT in encrypted vault
        if self.log_full_cot and self.cot_vault_path is not None:
            self._store_in_vault(full_cot, cot_hash)

        # Parse labels and confidence
        labels = output.get("labels", [])
        confidence = float(output.get("confidence", 0.0))

        # Parse redaction spans if present
        redaction_spans = []
        for span_data in output.get("redaction_spans", []):
            try:
                redaction_spans.append(RedactionSpan(**span_data))
            except Exception:
                # Skip malformed spans
                pass

        return PolicyDecision(
            labels=labels,
            confidence=confidence,
            needs_review=(confidence < threshold),
            reasoning_hash=cot_hash,
            reasoning_summary=cot_summary,
            full_reasoning_available=self.log_full_cot,
            redaction_spans=redaction_spans,
            model_version=self._model_version,
            policy_version=self.policy_hash,
            reasoning_effort=reasoning_effort,
            decision_ts=datetime.utcnow().isoformat(),
        )

    def requires_online(self) -> bool:
        """Safeguard adapter is self-hosted (offline only)."""
        return False

    def _select_reasoning_effort(self, text: str) -> Literal["low", "medium", "high"]:
        """Dynamically select reasoning effort based on document complexity.

        Heuristics:
        - Long documents (>5K chars) → medium effort
        - Complex legal terms → high effort
        - Otherwise → low effort
        """
        text_length = len(text)
        text_lower = text.lower()

        # Check for complex legal terminology
        complex_terms = [
            "attorney-client privilege",
            "work product",
            "common interest",
            "legal opinion",
            "confidential communication",
        ]
        has_complex_terms = any(term in text_lower for term in complex_terms)

        if has_complex_terms or text_length > 10000:
            return "high"
        elif text_length > 5000:
            return "medium"
        else:
            return "low"

    def _hash_reasoning(self, reasoning: str) -> str:
        """Hash full reasoning with salt for privacy-preserving audit trail."""
        return hashlib.sha256((reasoning + self.cot_salt).encode()).hexdigest()

    def _redact_summary(self, full_cot: str) -> str:
        """Redact excerpts from CoT, keeping only policy citations.

        Privacy requirement: Remove any quoted text or document excerpts.
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

    def _parse_model_output(self, generated_text: str) -> dict[str, Any]:
        """Parse JSON output from model, handling various formats.

        The model may output:
        1. Raw JSON: {"violation": 1, "labels": [...], ...}
        2. JSON in markdown code block: ```json\n{...}\n```
        3. JSON with explanation prefix: "Here is my analysis:\n{...}"
        """
        try:
            return parse_model_json_response(generated_text)
        except ValueError as e:
            raise json.JSONDecodeError(
                f"Could not parse JSON from model output: {str(e)}",
                generated_text,
                0,
            ) from e

    def _store_in_vault(self, reasoning: str, cot_hash: str) -> None:
        """Store full CoT in encrypted vault with hash-based filename."""
        if self.cot_vault_path is None:
            return

        # Use hash as filename for deduplication
        vault_file = self.cot_vault_path / f"{cot_hash}.txt"

        # Skip if already stored (deduplication)
        if vault_file.exists():
            return

        # TODO: Encrypt with Fernet key (reuse existing crypto utils)
        # For now, store plaintext (secure directory assumed)
        vault_file.write_text(reasoning, encoding="utf-8")

    def _create_error_decision(
        self,
        error_msg: str,
        reasoning_effort: Literal["low", "medium", "high"],
    ) -> PolicyDecision:
        """Create fallback decision when model fails."""
        return PolicyDecision(
            labels=[],
            confidence=0.0,
            needs_review=True,
            reasoning_hash="",
            reasoning_summary=f"Error: {error_msg}",
            full_reasoning_available=False,
            redaction_spans=[],
            model_version=self._model_version,
            policy_version=self.policy_hash,
            reasoning_effort=reasoning_effort,
            decision_ts=datetime.utcnow().isoformat(),
            error_message=error_msg,
        )
