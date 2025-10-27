"""Ledger port interface for audit trail operations."""

from typing import Any, Protocol

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """Normalized view of an audit ledger entry."""

    timestamp: str = Field(..., description="ISO-8601 timestamp")
    operation: str = Field(..., description="Operation name recorded in the ledger")
    inputs: list[str] = Field(default_factory=list, description="Input identifiers for the event")
    outputs: list[str] = Field(
        default_factory=list, description="Output identifiers or artifact paths for the event"
    )
    args: dict[str, Any] = Field(default_factory=dict, description="Additional parameters")
    versions: dict[str, str] | None = Field(default=None, description="Tool versions (optional)")


class LedgerPort(Protocol):
    """Port interface for audit ledger operations.

    Adapters implementing this port must provide:
    - Append-only audit logging
    - Hash chain verification
    - Tamper-evident storage

    Side effects: Writes to audit ledger (offline).
    """

    def log(
        self,
        operation: str,
        inputs: list[str],
        outputs: list[str],
        args: dict[str, Any],
    ) -> None:
        """Log an operation to the audit ledger.

        Args:
            operation: Operation name (e.g., "ingest", "index_build")
            inputs: List of input paths/identifiers
            outputs: List of output paths/identifiers
            args: Additional arguments/metadata
        """
        ...

    def verify(self) -> bool:
        """Verify audit ledger integrity.

        Returns:
            True if hash chain is valid, False otherwise
        """
        ...

    def read_all(self) -> list[AuditRecord]:
        """Read all audit entries.

        Returns:
            List of audit entry DTOs
        """
        ...
