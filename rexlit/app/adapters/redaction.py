"""Redaction planner and applier adapters."""

from __future__ import annotations

from pathlib import Path

from rexlit.app.ports import RedactionApplierPort, RedactionPlannerPort
from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.jsonl import atomic_write_jsonl


class JSONLineRedactionPlanner(RedactionPlannerPort):
    """Emit placeholder redaction plans as JSONL files."""

    def plan(self, source: Path, *, output: Path | None = None) -> Path:
        if not source.exists():
            raise FileNotFoundError(f"Cannot produce redaction plan, source not found: {source}")

        destination = output or source.with_suffix(".redaction-plan.jsonl")
        destination.parent.mkdir(parents=True, exist_ok=True)

        resolved_source = source.resolve()
        content_hash = compute_sha256_file(resolved_source)

        plan_entry = {
            "document": str(resolved_source),
            "sha256": content_hash,
            "actions": [],
            "notes": "Redaction planning stub. Replace with provider integration.",
        }

        atomic_write_jsonl(
            destination,
            [plan_entry],
            schema_id="redaction_plan",
            schema_version=1,
        )
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
