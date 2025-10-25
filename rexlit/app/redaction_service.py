"""Redaction service for PII detection and redaction planning/application.

Implements plan/apply pattern for safety. All I/O delegated to ports.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel


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
    ):
        """Initialize redaction service.

        Args:
            pii_port: PII detection port
            stamp_port: PDF manipulation port
            storage_port: Filesystem operations port
            ledger_port: Audit logging port
        """
        self.pii = pii_port
        self.stamp = stamp_port
        self.storage = storage_port
        self.ledger = ledger_port

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

        # TODO: Scan for PII via pii_port
        # TODO: Generate plan with coordinates
        # TODO: Compute plan_id = sha256(input artifacts)
        # TODO: Write plan JSONL via storage_port

        plan = RedactionPlan(
            plan_id="placeholder",
            input_hash="placeholder",
            redactions=[],
            rationale="PII detection",
        )

        # Log to audit
        self.ledger.log(
            operation="redaction_plan_create",
            inputs=[str(input_path)],
            outputs=[str(output_plan_path)],
            args={"pii_types": pii_types},
        )

        return plan

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
        # TODO: Read plan via storage_port
        # TODO: Verify current PDF hash matches plan.input_hash
        # TODO: If preview, generate diff and return
        # TODO: Apply redactions via stamp_port
        # TODO: Write redacted PDFs via storage_port

        # Log to audit
        self.ledger.log(
            operation="redaction_apply",
            inputs=[str(plan_path)],
            outputs=[str(output_path)],
            args={"preview": preview, "force": force},
        )

        return 0

    def validate_plan(self, plan_path: Path) -> bool:
        """Validate redaction plan against current PDFs.

        Args:
            plan_path: Path to redaction plan JSONL

        Returns:
            True if plan matches current PDFs, False otherwise
        """
        # TODO: Read plan via storage_port
        # TODO: Compute current PDF hashes
        # TODO: Compare with plan.input_hash

        return True
