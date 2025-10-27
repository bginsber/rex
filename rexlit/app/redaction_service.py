"""Redaction service for PII detection and redaction planning/application.

Implements plan/apply pattern for safety. All I/O delegated to ports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rexlit.config import Settings, get_settings
from rexlit.utils.plans import (
    compute_redaction_plan_id,
    load_redaction_plan_entry,
    validate_redaction_plan_entry,
    write_redaction_plan_entry,
)


class RedactionPlan(BaseModel):
    """Redaction plan with deterministic ID."""

    plan_id: str
    input_hash: str
    redactions: list[dict[str, Any]]
    rationale: str


class RedactionService:
    """Orchestrates redaction planning and application.

    Implements two-phase plan/apply pattern for safety:
    1. plan: Generate redaction coordinates without modifying PDFs
    2. apply: Verify plan matches current PDF, then apply redactions

    All I/O is delegated to ports.
    """

    def __init__(
        self,
        pii_port: Any,  # Will be typed with port interface in Workstream 2
        stamp_port: Any,
        storage_port: Any,
        ledger_port: Any,
        *,
        settings: Settings | None = None,
    ):
        """Initialize redaction service.

        Args:
            pii_port: PII detection port
            stamp_port: PDF manipulation port
            storage_port: Filesystem operations port
            ledger_port: Audit logging port
            settings: Application settings (used for encryption keys)
        """
        self.pii = pii_port
        self.stamp = stamp_port
        self.storage = storage_port
        self.ledger = ledger_port
        self._settings = settings or get_settings()
        self._plan_key = self._settings.get_redaction_plan_key()

    def plan(
        self,
        input_path: Path,
        output_plan_path: Path,
        *,
        pii_types: list[str] | None = None,
    ) -> RedactionPlan:
        """Generate redaction plan without modifying PDFs.

        Args:
            input_path: Path to PDF or directory of PDFs
            output_plan_path: Output path for plan JSONL
            pii_types: PII types to detect (default: all)

        Returns:
            RedactionPlan with deterministic plan_id
        """
        if pii_types is None:
            pii_types = ["SSN", "EMAIL", "PHONE", "CREDIT_CARD", "ADDRESS"]

        resolved_input = Path(input_path).resolve()
        if not resolved_input.exists():
            raise FileNotFoundError(f"Redaction source not found: {resolved_input}")

        resolved_output = Path(output_plan_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        document_hash = self.storage.compute_hash(resolved_input)
        annotations = {"pii_types": sorted(pii_types)}

        plan_id = compute_redaction_plan_id(
            document_path=resolved_input,
            content_hash=document_hash,
            annotations=annotations,
        )

        plan_entry = {
            "document": str(resolved_input),
            "sha256": document_hash,
            "plan_id": plan_id,
            "actions": [],
            "annotations": annotations,
            "notes": "Redaction planning stub. Replace with provider integration.",
        }

        write_redaction_plan_entry(resolved_output, plan_entry, key=self._plan_key)

        if self.ledger is not None:
            self.ledger.log(
                operation="redaction_plan_create",
                inputs=[str(resolved_input)],
                outputs=[str(resolved_output)],
                args={
                    "plan_id": plan_id,
                    "document_sha256": document_hash,
                    "pii_types": annotations["pii_types"],
                },
            )

        return RedactionPlan(
            plan_id=plan_id,
            input_hash=document_hash,
            redactions=[],
            rationale="PII detection",
        )

    def apply(
        self,
        plan_path: Path,
        output_path: Path,
        *,
        preview: bool = False,
        force: bool = False,
    ) -> int:
        """Apply redactions from plan to PDFs.

        Safety checks:
        1. Verify PDF hash matches plan
        2. Abort if mismatch (unless --force)
        3. Preview mode returns diff without writing

        Args:
            plan_path: Path to redaction plan JSONL
            output_path: Output directory for redacted PDFs
            preview: Return diff without writing
            force: Skip hash verification (dangerous)

        Returns:
            Number of redactions applied

        Raises:
            ValueError: If plan hash doesn't match current PDF
        """
        resolved_plan = Path(plan_path).resolve()
        if not resolved_plan.exists():
            raise FileNotFoundError(f"Redaction plan not found: {resolved_plan}")

        entry = self._read_plan_entry(resolved_plan)

        document_path = Path(entry.get("document", "")).resolve()
        if not document_path.exists():
            raise FileNotFoundError(
                f"Redaction target referenced by plan is missing: {document_path}"
            )

        expected_hash = str(entry.get("sha256", ""))
        plan_id = validate_redaction_plan_entry(
            entry,
            document_path=document_path,
            content_hash=expected_hash,
        )

        if not force:
            current_hash = self.storage.compute_hash(document_path)
            if current_hash != expected_hash:
                raise ValueError(
                    "Redaction plan hash mismatch detected. "
                    f"Expected {expected_hash}, computed {current_hash}."
                )

        redactions = entry.get("redactions", [])
        applied_count = len(redactions)

        resolved_output = Path(output_path).resolve()
        destination_path: Path | None = None

        if not preview:
            resolved_output.mkdir(parents=True, exist_ok=True)
            destination_path = resolved_output / document_path.name
            self.storage.copy_file(document_path, destination_path)

        if self.ledger is not None:
            outputs: list[str] = []
            if destination_path is not None:
                outputs.append(str(destination_path))

            self.ledger.log(
                operation="redaction_apply",
                inputs=[str(document_path), str(resolved_plan)],
                outputs=outputs,
                args={
                    "plan_id": plan_id,
                    "preview": preview,
                    "force": force,
                    "redaction_count": applied_count,
                    "document_sha256": expected_hash,
                    "output_dir": str(resolved_output),
                },
            )

        return applied_count

    def _read_plan_entry(self, plan_path: Path) -> dict[str, Any]:
        """Load a single redaction plan entry from disk."""

        return load_redaction_plan_entry(Path(plan_path), key=self._plan_key)

    def validate_plan(self, plan_path: Path) -> bool:
        """Validate redaction plan against current PDFs.

        Args:
            plan_path: Path to redaction plan JSONL

        Returns:
            True if plan matches current PDFs, False otherwise
        """
        resolved_plan = Path(plan_path).resolve()
        if not resolved_plan.exists():
            raise FileNotFoundError(f"Redaction plan not found: {resolved_plan}")

        try:
            entry = self._read_plan_entry(resolved_plan)
        except ValueError:
            return False

        document_path = Path(entry.get("document", "")).resolve()
        if not document_path.exists():
            return False

        expected_hash = str(entry.get("sha256", ""))
        try:
            validate_redaction_plan_entry(
                entry,
                document_path=document_path,
                content_hash=expected_hash,
            )
        except ValueError:
            return False

        current_hash = self.storage.compute_hash(document_path)
        return current_hash == expected_hash
