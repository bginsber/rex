"""Redaction planner and applier adapters."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from rexlit.app.ports import RedactionApplierPort, RedactionPlannerPort
from rexlit.app.ports.pii import PIIPort
from rexlit.config import Settings, get_settings
from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.plans import (
    compute_redaction_plan_id,
    validate_redaction_plan_file,
    write_redaction_plan_entry,
)

logger = logging.getLogger(__name__)


class JSONLineRedactionPlanner(RedactionPlannerPort):
    """Emit redaction plans as encrypted JSONL files with PII detection.

    When a PIIPort is provided, the planner will analyze document text
    and generate redaction actions for detected PII entities (SSN, email,
    phone, credit card, etc.). Without a PIIPort, plans are created with
    empty actions (placeholder behavior).
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        pii_port: PIIPort | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._key = self._settings.get_redaction_plan_key()
        self._pii_port = pii_port

    def plan(self, source: Path, *, output: Path | None = None) -> Path:
        if not source.exists():
            raise FileNotFoundError(f"Cannot produce redaction plan, source not found: {source}")

        destination = output or source.with_suffix(".redaction-plan.enc")
        destination.parent.mkdir(parents=True, exist_ok=True)

        resolved_source = source.resolve()
        content_hash = compute_sha256_file(resolved_source)

        # Generate redaction actions from PII detection if available
        actions: list[dict[str, Any]] = []
        notes = "No PII detector configured."

        if self._pii_port is not None:
            try:
                pii_findings = self._pii_port.analyze_document(
                    str(resolved_source), language="en"
                )
                for finding in pii_findings:
                    actions.append({
                        "type": "redact",
                        "category": finding.entity_type,
                        "start": finding.start,
                        "end": finding.end,
                        "page": finding.page,
                        "confidence": finding.score,
                        "replacement": f"[{finding.entity_type}]",
                    })
                if actions:
                    notes = f"PII detection found {len(actions)} entities to redact."
                else:
                    notes = "PII detection completed. No entities found."
            except Exception as exc:
                logger.warning("PII detection failed for %s: %s", resolved_source, exc)
                notes = f"PII detection error: {exc}"

        # Compute plan_id AFTER generating actions to ensure determinism
        plan_id = compute_redaction_plan_id(
            document_path=resolved_source,
            content_hash=content_hash,
            actions=actions if actions else None,
        )

        plan_entry = {
            "document": str(resolved_source),
            "sha256": content_hash,
            "plan_id": plan_id,
            "actions": actions,
            "notes": notes,
        }

        if destination.exists():
            existing_plan_id = validate_redaction_plan_file(
                destination,
                document_path=resolved_source,
                content_hash=content_hash,
                key=self._key,
            )
            if existing_plan_id != plan_id:
                raise ValueError(
                    "Existing redaction plan fingerprint mismatch; refusing to overwrite "
                    f"{destination}."
                )
            return destination

        write_redaction_plan_entry(destination, plan_entry, key=self._key)
        return destination


class PassthroughRedactionApplier(RedactionApplierPort):
    """No-op redaction applier that validates inputs and returns the original document."""

    def apply(self, source: Path, *, plan: Path, force: bool = False) -> Path:
        if not source.exists():
            raise FileNotFoundError(f"Redaction target not found: {source}")
        if not plan.exists():
            raise FileNotFoundError(f"Redaction plan not found: {plan}")

        if not force:
            raise NotImplementedError(
                "Redaction apply requires --force until provider integration is implemented."
            )

        return source
