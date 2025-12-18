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

import difflib
import hashlib
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from rexlit.app.ports.privilege_reasoning import PolicyDecision
from rexlit.utils.methods import sanitize_argv

if TYPE_CHECKING:
    from rexlit.app.ports.ledger import LedgerPort
    from rexlit.app.ports.privilege_reasoning import PrivilegeReasoningPort
    from rexlit.config import Settings


STAGE_LABELS: dict[int, str] = {
    1: "Privilege",
    2: "Responsiveness",
    3: "Redaction",
}


@dataclass(slots=True)
class PrivilegePolicyMetadata:
    """Metadata describing a privilege policy template."""

    stage: int
    stage_name: str
    path: Path
    exists: bool
    sha256: str | None
    size_bytes: int | None
    modified_at: datetime | None
    source: Literal["default", "override", "explicit", "missing"]

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata for JSON output."""
        return {
            "stage": self.stage,
            "stage_name": self.stage_name,
            "path": str(self.path),
            "exists": self.exists,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "source": self.source,
        }


class PrivilegePolicyManager:
    """Manage privilege policy templates, ensuring offline-safe updates."""

    def __init__(self, settings: Settings, ledger: LedgerPort | None = None) -> None:
        self._settings = settings
        self._ledger = ledger

    def list_policies(self) -> list[PrivilegePolicyMetadata]:
        """Return metadata for all configured policy stages."""
        metadata: list[PrivilegePolicyMetadata] = []
        for stage in (1, 2, 3):
            metadata.append(self._build_metadata(stage))
        return metadata

    def show_policy(self, stage: int) -> tuple[PrivilegePolicyMetadata, str]:
        """Return policy metadata and text for ``stage``."""
        metadata = self._build_metadata(stage)
        if not metadata.exists:
            raise FileNotFoundError(f"Policy template missing for stage {stage}.")
        text = metadata.path.read_text(encoding="utf-8")
        return metadata, text

    def prepare_edit_path(self, stage: int) -> Path:
        """Return editable path for policy ``stage``, copying default if needed."""
        attr_name = f"privilege_policy_stage{stage}"
        explicit_path: Path | None = getattr(self._settings, attr_name, None)

        if explicit_path is not None:
            explicit_path.parent.mkdir(parents=True, exist_ok=True)
            return explicit_path

        override_path = self._override_path(stage)
        if override_path.exists():
            return override_path

        source_path = self._settings.get_privilege_policy_path(stage=stage)
        override_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, override_path)
        return override_path

    def save_policy_from_text(
        self,
        stage: int,
        content: str,
        *,
        source: str,
        command_args: Sequence[str] | None = None,
    ) -> PrivilegePolicyMetadata:
        """Persist ``content`` to the policy for ``stage``."""
        target_path = self.prepare_edit_path(stage)
        previous_hash = self._compute_sha256(target_path) if target_path.exists() else None

        target_path.write_text(content, encoding="utf-8")
        metadata = self._build_metadata(stage)

        self._log_update(stage, metadata, previous_hash, source, command_args)
        return metadata

    def apply_from_file(
        self,
        stage: int,
        source_path: Path,
        *,
        command_args: Sequence[str] | None = None,
    ) -> PrivilegePolicyMetadata:
        """Copy policy contents from ``source_path`` into the configured stage."""
        resolved = source_path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Policy source not found: {source_path}")

        self._validate_allowed_path(resolved)
        content = resolved.read_text(encoding="utf-8")
        return self.save_policy_from_text(
            stage,
            content,
            source="file",
            command_args=command_args,
        )

    def diff_with_file(self, stage: int, other: Path) -> str:
        """Return unified diff between stage policy and ``other``."""
        metadata, current_text = self.show_policy(stage)

        resolved = other.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Comparison file not found: {other}")
        self._validate_allowed_path(resolved)
        other_text = resolved.read_text(encoding="utf-8")

        diff_lines = difflib.unified_diff(
            current_text.splitlines(),
            other_text.splitlines(),
            fromfile=str(metadata.path),
            tofile=str(resolved),
            lineterm="",
        )
        return "\n".join(diff_lines)

    def validate_policy(self, stage: int) -> dict[str, Any]:
        """Perform lightweight validation of policy structure."""
        metadata, text = self.show_policy(stage)

        errors: list[str] = []
        if not text.strip():
            errors.append("Policy template is empty.")
        if "```json" not in text:
            errors.append("Policy must document JSON response schema.")
        if "labels" not in text.lower():
            errors.append("Policy must mention classification labels.")
        if "confidence" not in text.lower():
            errors.append("Policy must describe confidence scoring.")

        return {
            "stage": metadata.stage,
            "stage_name": metadata.stage_name,
            "path": str(metadata.path),
            "sha256": metadata.sha256,
            "size_bytes": metadata.size_bytes,
            "modified_at": metadata.modified_at.isoformat()
            if metadata.modified_at
            else None,
            "passed": not errors,
            "errors": errors,
        }

    def _build_metadata(self, stage: int) -> PrivilegePolicyMetadata:
        """Construct metadata for ``stage``."""
        stage_name = STAGE_LABELS.get(stage, f"Stage {stage}")
        try:
            path = self._settings.get_privilege_policy_path(stage=stage)
            exists = path.exists()
        except FileNotFoundError:
            return PrivilegePolicyMetadata(
                stage=stage,
                stage_name=stage_name,
                path=self._override_path(stage),
                exists=False,
                sha256=None,
                size_bytes=None,
                modified_at=None,
                source="missing",
            )

        sha256 = self._compute_sha256(path) if exists else None
        stat = path.stat() if exists else None
        source = self._determine_source(stage, path)

        return PrivilegePolicyMetadata(
            stage=stage,
            stage_name=stage_name,
            path=path,
            exists=exists,
            sha256=sha256,
            size_bytes=stat.st_size if stat else None,
            modified_at=datetime.fromtimestamp(stat.st_mtime) if stat else None,
            source=source,
        )

    def _determine_source(self, stage: int, path: Path) -> Literal["default", "override", "explicit", "missing"]:
        attr_name = f"privilege_policy_stage{stage}"
        explicit_path: Path | None = getattr(self._settings, attr_name, None)
        if explicit_path is not None and path == explicit_path:
            return "explicit"

        if path == self._override_path(stage):
            return "override"

        return "default"

    def _override_path(self, stage: int) -> Path:
        filename = {
            1: "privilege_stage1.txt",
            2: "privilege_stage2.txt",
            3: "privilege_stage3.txt",
        }.get(stage, f"privilege_stage{stage}.txt")
        return self._settings.get_config_dir() / "policies" / filename

    def _validate_allowed_path(self, path: Path) -> None:
        allowed_roots: set[Path] = {
            self._settings.get_config_dir().resolve(),
            self._settings.get_data_dir().resolve(),
        }

        configured = [
            self._settings.privilege_policy_stage1,
            self._settings.privilege_policy_stage2,
            self._settings.privilege_policy_stage3,
        ]
        for configured_path in configured:
            if configured_path is not None:
                allowed_roots.add(configured_path.resolve().parent)

        if any(path.is_relative_to(root) for root in allowed_roots):
            return
        raise ValueError(f"Path traversal detected: {path}")

    def _compute_sha256(self, path: Path) -> str:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()

    def _log_update(
        self,
        stage: int,
        metadata: PrivilegePolicyMetadata,
        previous_hash: str | None,
        source: str,
        command_args: Sequence[str] | None,
    ) -> None:
        if self._ledger is None:
            return

        args: dict[str, Any] = {
            "stage": stage,
            "stage_name": metadata.stage_name,
            "path": str(metadata.path),
            "sha256": metadata.sha256,
            "previous_sha256": previous_hash,
            "source": source,
            "size_bytes": metadata.size_bytes,
        }
        if command_args:
            args["cli_args"] = sanitize_argv(list(command_args))

        outputs: list[str] = []
        if metadata.sha256:
            outputs.append(metadata.sha256)

        self._ledger.log(
            operation="privilege.policy.update",
            inputs=[str(metadata.path)],
            outputs=outputs,
            args=args,
        )


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
        pattern_adapter: Any | None = None,
        pattern_skip_threshold: float = 0.85,
        pattern_escalate_threshold: float = 0.50,
        enable_responsiveness: bool = False,
        enable_redactions: bool = False,
    ) -> None:
        """Initialize privilege review service.

        Args:
            safeguard_adapter: Safeguard LLM adapter for deep reasoning
            ledger_port: Optional audit ledger for logging decisions
            pattern_adapter: Optional pattern-based privilege detector for fast pre-filtering
            pattern_skip_threshold: Confidence above which to skip LLM (default: 0.85)
            pattern_escalate_threshold: Confidence above which to use LLM (default: 0.50)
            enable_responsiveness: Enable Stage 2 (responsiveness classification)
            enable_redactions: Enable Stage 3 (redaction span detection)
        """
        self.safeguard = safeguard_adapter
        self.ledger = ledger_port
        self.pattern_adapter = pattern_adapter
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
        1. Pattern pre-filter (fast heuristics) - skip LLM if confidence >= 0.85
        2. Escalate to LLM with high effort if pattern confidence 0.50-0.84
        3. Use LLM with medium effort if pattern confidence < 0.50 or no patterns
        """
        # Pattern pre-filter: fast offline path when pattern adapter is available
        if not force_llm and self.pattern_adapter is not None:
            try:
                pattern_findings = self.pattern_adapter.analyze_text(
                    text, threshold=self.pattern_escalate_threshold
                )
                if pattern_findings:
                    # Get the highest confidence finding
                    max_confidence = max(f.confidence for f in pattern_findings)

                    # High-confidence patterns: skip LLM entirely (offline fast path)
                    if max_confidence >= self.pattern_skip_threshold:
                        # Build labels from pattern findings
                        labels = []
                        if any(f.match_type == "keyword" for f in pattern_findings):
                            labels.append("PRIVILEGED:PATTERN_KEYWORD")
                        if any(f.match_type == "name" for f in pattern_findings):
                            labels.append("PRIVILEGED:ATTORNEY_NAME")
                        if any(f.match_type == "domain" for f in pattern_findings):
                            labels.append("PRIVILEGED:ATTORNEY_DOMAIN")

                        return PolicyDecision(
                            labels=labels or ["PRIVILEGED:PATTERN"],
                            confidence=max_confidence,
                            needs_review=False,
                            reasoning_summary=f"Pattern match ({len(pattern_findings)} findings, max conf {max_confidence:.2f})",
                            reasoning_hash=hashlib.sha256(
                                f"pattern:{','.join(f.rule for f in pattern_findings)}".encode()
                            ).hexdigest(),
                            reasoning_effort="low",  # Pattern-only, no LLM
                            model_version="pattern-v1",
                            policy_version="pattern-v1",
                        )

                    # Medium-confidence patterns: escalate to LLM with high effort
                    if max_confidence >= self.pattern_escalate_threshold:
                        decision = self.safeguard.classify_privilege(
                            text,
                            threshold=threshold,
                            reasoning_effort="high",
                        )
                        return decision
            except Exception:
                # Pattern adapter failed, fall through to LLM
                pass

        # No pattern adapter, patterns below threshold, or force_llm: use safeguard
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
        text: str,  # noqa: ARG002 - reserved for future implementation
        base_decision: PolicyDecision,
    ) -> PolicyDecision:
        """Stage 2: Responsiveness classification (RESPONSIVE/HOTDOC).

        NOT YET IMPLEMENTED - This is a placeholder that passes through
        the base decision unchanged.

        When implemented, this stage will use a separate policy template
        focused on responsiveness criteria (e.g., relevance to litigation
        topics, HOTDOC scoring).

        Implementation plan:
        1. Load responsiveness policy template from config
        2. Call safeguard with focused responsiveness prompt
        3. Merge RESPONSIVE/HOTDOC labels into base_decision
        4. Log to audit trail with stage="responsiveness"
        """
        # Log that stage was skipped (not implemented)
        if self.ledger is not None:
            self.ledger.log(
                operation="privilege.responsiveness.skipped",
                doc_id=doc_id,
                labels=base_decision.labels,
                confidence=base_decision.confidence,
                reason="Stage 2 (responsiveness) is not yet implemented",
            )

        return base_decision

    def _detect_redactions(
        self,
        doc_id: str,
        text: str,  # noqa: ARG002 - reserved for future implementation
        base_decision: PolicyDecision,
    ) -> PolicyDecision:
        """Stage 3: Redaction span detection (CPI, trade secrets, etc.).

        NOT YET IMPLEMENTED - This is a placeholder that passes through
        the base decision unchanged.

        When implemented, this stage will use a separate policy template
        focused on identifying specific text spans requiring redaction.

        Note: PII-based redaction is available through the redaction planner
        which uses PIIPort for SSN, email, phone, and credit card detection.
        This stage is for LLM-based privilege redaction (trade secrets, CPI).

        Implementation plan:
        1. Load redaction policy template from config
        2. Call safeguard with span detection prompt
        3. Parse redaction_spans from LLM output
        4. Merge spans into base_decision.redaction_spans
        5. Log to audit trail with stage="redaction"
        """
        # Log that stage was skipped (not implemented)
        if self.ledger is not None:
            self.ledger.log(
                operation="privilege.redaction.skipped",
                doc_id=doc_id,
                labels=base_decision.labels,
                confidence=base_decision.confidence,
                reason="Stage 3 (LLM redaction detection) is not yet implemented. Use PII-based redaction plans.",
            )

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
