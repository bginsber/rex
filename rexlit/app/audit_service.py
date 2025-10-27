"""Audit ledger orchestration services."""

from __future__ import annotations

from dataclasses import dataclass

from rexlit.app.ports import AuditRecord, LedgerPort


@dataclass(slots=True)
class AuditService:
    """Expose read/verify operations over the audit ledger."""

    ledger: LedgerPort | None

    def is_enabled(self) -> bool:
        """Return True when audit logging is available."""

        return self.ledger is not None

    def get_entries(self) -> list[AuditRecord]:
        """Return all audit ledger entries (empty list when disabled)."""

        if self.ledger is None:
            return []
        return self.ledger.read_all()

    def verify(self) -> tuple[bool, str | None]:
        """Verify ledger integrity, treating missing ledger as valid."""

        if self.ledger is None:
            return True, None
        return self.ledger.verify()
