"""Redaction planning and application ports."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class RedactionPlannerPort(Protocol):
    """Port interface for producing redaction plans."""

    def plan(self, source: Path, *, output: Path | None = None) -> Path:
        """Generate a redaction plan JSONL for ``source`` and return its path."""
        ...


class RedactionApplierPort(Protocol):
    """Port interface for applying redaction plans to documents."""

    def apply(self, source: Path, *, plan: Path, force: bool = False) -> Path:
        """Apply ``plan`` to ``source`` and return the redacted artifact path."""
        ...
