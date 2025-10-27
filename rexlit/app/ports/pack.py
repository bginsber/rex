"""Ports for packaging workflow artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PackPort(Protocol):
    """Port interface for packaging processed artifacts."""

    def pack(self, source_dir: Path, *, destination: Path | None = None) -> Path:
        """Create a packaged artifact from ``source_dir`` and return the destination path."""
        ...
