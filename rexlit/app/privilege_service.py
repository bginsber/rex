"""Privilege review service with modular multi-stage classification pipeline.

This service orchestrates privilege classification with:
1. Pattern-based pre-filtering (fast, offline)
2. Safeguard LLM invocation (deep reasoning when needed)
3. Fallback strategies for robustness
4. Privacy-preserving audit logging

Architecture:
    Stage 1: Privilege Detection (ACP/WP/CI)
    Stage 2: Responsiveness Classification (optional)
    Stage 3: Redaction Span Detection (optional)

See ADR 0008 for design rationale and privacy controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rexlit.app.ports.privilege_reasoning import PolicyDecision

if TYPE_CHECKING:
    from pathlib import Path

    from rexlit.app.ports.ledger import LedgerPort
    from rexlit.app.ports.privilege_reasoning import PrivilegeReasoningPort


class PrivilegeReviewService:
    """Orchestrates privilege classification with hybrid pattern/LLM approach.

    This service implements a smart escalation strategy:
    - High-confidence patterns (≥0.85) → skip LLM, use pattern classification
    - Uncertain patterns (0.50-0.84) → escalate to LLM with high reasoning effort
    - Low/no patterns (<0.50) → escalate to LLM with medium reasoning effort

    Privacy guarantees:
    - All audit logs contain hashed reasoning only (no excerpts)
    - Full CoT stored in encrypted vault only if explicitly configured
    - Document text never logged at INFO level

    Example:
        >>> service = PrivilegeReviewService(
        ...     pattern_adapter=pattern_adapter,
        ...     safeguard_adapter=safeguard_adapter,
        ...     ledger_port=ledger,
        ... )
        >>> decision = service.review_document(
        ...     doc_id="DOC-001",
        ...     text="Email from attorney@law.com...",
        ... )
        >>> if decision.is_privileged:
        ...     print(f"Privileged: {decision.labels}")
    """

    def __init__(
        self,
        safeguard_adapter: PrivilegeReasoningPort,
        ledger_port: LedgerPort | None = None,
        *,
        pattern_skip_threshold: float = 0.85,
        pattern_escalate_threshold: float = 0.50,
        enable_responsiveness: bool = False,
        enable_redactions: bool = False,
    ) -> None:
        """Initialize privilege review service.

        Args:
            safeguard_adapter: Safeguard LLM adapter for deep reasoning
            ledger_port: Optional audit ledger for logging decisions
            pattern_skip_threshold: Confidence above which to skip LLM (default: 0.85)
            pattern_escalate_threshold: Confidence above which to use LLM (default: 0.50)
            enable_responsiveness: Enable Stage 2 (responsiveness classification)
            enable_redactions: Enable Stage 3 (redaction span detection)
        """
        self.safeguard = safeguard_adapter
        self.ledger = ledger_port
        self.pattern_skip_threshold = pattern_skip_threshold
        self.pattern_escalate_threshold = pattern_escalate_threshold
        self.enable_responsiveness = enable_responsiveness
        self.enable_redactions = enable_redactions

    def review_document(
        self,
        doc_id: str,
        text: str,
        *,
        threshold: float = 0.75,
        force_llm: bool = False,
    ) -> PolicyDecision:
        """Review document for privilege (Stage 1).

        Args:
            doc_id: Document identifier for audit logging
            text: Document text to classify
            threshold: Confidence threshold for automatic classification
            force_llm: If True, skip pattern pre-filter and use LLM directly

        Returns:
            PolicyDecision with privilege classification and reasoning
        """
        # Stage 1: Privilege Detection
        decision = self._classify_privilege(text, threshold=threshold, force_llm=force_llm)

        # Audit log (privacy-preserving)
        if self.ledger is not None:
            self._log_decision(doc_id, decision, stage="privilege")

        # Stage 2: Responsiveness (if privileged and enabled)
        if self.enable_responsiveness and decision.is_privileged:
            decision = self._classify_responsiveness(doc_id, text, decision)

        # Stage 3: Redaction Detection (if responsive and enabled)
        if self.enable_redactions and decision.is_responsive:
            decision = self._detect_redactions(doc_id, text, decision)

        return decision

    def _classify_privilege(
        self,
        text: str,
        *,
        threshold: float,
        force_llm: bool,
    ) -> PolicyDecision:
        """Stage 1: Privilege classification (ACP/WP/CI).

        Smart escalation strategy:
        1. Pattern pre-filter (fast heuristics)
        2. Escalate to LLM if uncertain
        3. Skip LLM if pattern confidence is high
        """
        # For now, always use safeguard (pattern adapter to be added later)
        # TODO: Add pattern pre-filter with PrivilegePatternsAdapter
        reasoning_effort = "medium" if not force_llm else "high"

        decision = self.safeguard.classify_privilege(
            text,
            threshold=threshold,
            reasoning_effort=reasoning_effort,
        )

        return decision

    def _classify_responsiveness(
        self,
        doc_id: str,
        text: str,
        base_decision: PolicyDecision,
    ) -> PolicyDecision:
        """Stage 2: Responsiveness classification (RESPONSIVE/HOTDOC).

        This stage uses a separate policy template focused on responsiveness
        criteria (e.g., relevance to litigation topics, HOTDOC scoring).

        TODO: Implement with separate safeguard call using responsiveness policy.
        """
        # Placeholder: In full implementation, this would:
        # 1. Load responsiveness policy template
        # 2. Call safeguard with focused prompt
        # 3. Merge labels into base_decision
        # 4. Log to audit trail

        if self.ledger is not None:
            self._log_decision(doc_id, base_decision, stage="responsiveness")

        return base_decision

    def _detect_redactions(
        self,
        doc_id: str,
        text: str,
        base_decision: PolicyDecision,
    ) -> PolicyDecision:
        """Stage 3: Redaction span detection (CPI, trade secrets, etc.).

        This stage uses a separate policy template focused on identifying
        specific text spans requiring redaction.

        TODO: Implement with separate safeguard call using redaction policy.
        """
        # Placeholder: In full implementation, this would:
        # 1. Load redaction policy template
        # 2. Call safeguard with span detection prompt
        # 3. Parse redaction_spans from output
        # 4. Merge into base_decision
        # 5. Log to audit trail

        if self.ledger is not None:
            self._log_decision(doc_id, base_decision, stage="redaction")

        return base_decision

    def _log_decision(
        self,
        doc_id: str,
        decision: PolicyDecision,
        *,
        stage: str,
    ) -> None:
        """Log privacy-preserving decision to audit trail.

        Logged fields:
        - Document ID
        - Labels (e.g., ["PRIVILEGED:ACP"])
        - Confidence score
        - Reasoning hash (SHA-256)
        - Redacted summary (no excerpts)
        - Model version
        - Policy version
        - Timestamp

        NOT logged:
        - Full document text
        - Full reasoning chain (unless vault enabled)
        - Document excerpts or quotes
        """
        if self.ledger is None:
            return

        log_entry: dict[str, Any] = {
            "operation": f"privilege.{stage}",
            "doc_id": doc_id,
            "labels": decision.labels,
            "confidence": decision.confidence,
            "needs_review": decision.needs_review,
            "reasoning_hash": decision.reasoning_hash,
            "reasoning_summary": decision.reasoning_summary,
            "model_version": decision.model_version,
            "policy_version": decision.policy_version,
            "reasoning_effort": decision.reasoning_effort,
            "decision_ts": decision.decision_ts,
        }

        # Include redaction spans if present
        if decision.redaction_spans:
            log_entry["redaction_count"] = len(decision.redaction_spans)
            log_entry["redaction_categories"] = list(
                {span.category for span in decision.redaction_spans}
            )

        # Include error if present
        if decision.error_message:
            log_entry["error"] = decision.error_message

        self.ledger.log(**log_entry)

    def batch_review(
        self,
        documents: list[tuple[str, str]],
        *,
        threshold: float = 0.75,
        show_progress: bool = True,
    ) -> list[PolicyDecision]:
        """Batch review multiple documents with optional progress display.

        Args:
            documents: List of (doc_id, text) tuples
            threshold: Confidence threshold for automatic classification
            show_progress: Show progress bar (requires tqdm)

        Returns:
            List of PolicyDecision objects (same order as input)
        """
        results: list[PolicyDecision] = []

        if show_progress:
            try:
                from tqdm import tqdm  # type: ignore[import-untyped]

                iterator = tqdm(documents, desc="Reviewing documents")
            except ImportError:
                # Fallback if tqdm not available
                iterator = documents
        else:
            iterator = documents

        for doc_id, text in iterator:
            decision = self.review_document(doc_id, text, threshold=threshold)
            results.append(decision)

        return results

    def export_review_report(
        self,
        decisions: list[tuple[str, PolicyDecision]],
        output_path: Path,
    ) -> None:
        """Export privilege review report to JSONL.

        Each line contains:
        - Document ID
        - Labels
        - Confidence
        - Needs review flag
        - Reasoning hash
        - Summary

        Args:
            decisions: List of (doc_id, PolicyDecision) tuples
            output_path: Path to output JSONL file
        """
        import json

        with output_path.open("w", encoding="utf-8") as f:
            for doc_id, decision in decisions:
                record = {
                    "doc_id": doc_id,
                    "labels": decision.labels,
                    "confidence": decision.confidence,
                    "needs_review": decision.needs_review,
                    "reasoning_hash": decision.reasoning_hash,
                    "reasoning_summary": decision.reasoning_summary,
                    "model_version": decision.model_version,
                    "policy_version": decision.policy_version,
                    "timestamp": decision.decision_ts,
                }

                # Include redactions if present
                if decision.redaction_spans:
                    record["redactions"] = [
                        {
                            "category": span.category,
                            "start": span.start,
                            "end": span.end,
                            "justification": span.justification,
                        }
                        for span in decision.redaction_spans
                    ]

                f.write(json.dumps(record) + "\n")
