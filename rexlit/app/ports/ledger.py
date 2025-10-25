"""Ledger port interface for audit trail operations."""

from typing import Protocol, Any


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

    def read_all(self) -> list[dict[str, Any]]:
        """Read all audit entries.

        Returns:
            List of audit entry dictionaries
        """
        ...
