"""Redaction planner and applier adapters."""

from __future__ import annotations

from pathlib import Path

from rexlit.app.ports import RedactionApplierPort, RedactionPlannerPort
from rexlit.config import Settings, get_settings
from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.plans import (
    compute_redaction_plan_id,
    validate_redaction_plan_file,
    write_redaction_plan_entry,
)


class JSONLineRedactionPlanner(RedactionPlannerPort):
    """Emit placeholder redaction plans as encrypted JSONL files."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._key = self._settings.get_redaction_plan_key()

    def plan(self, source: Path, *, output: Path | None = None) -> Path:
        if not source.exists():
            raise FileNotFoundError(f"Cannot produce redaction plan, source not found: {source}")

        destination = output or source.with_suffix(".redaction-plan.enc")
        destination.parent.mkdir(parents=True, exist_ok=True)

        resolved_source = source.resolve()
        content_hash = compute_sha256_file(resolved_source)

        plan_id = compute_redaction_plan_id(
            document_path=resolved_source,
            content_hash=content_hash,
        )

        plan_entry = {
            "document": str(resolved_source),
            "sha256": content_hash,
            "plan_id": plan_id,
            "actions": [],
            "notes": "Redaction planning stub. Replace with provider integration.",
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
