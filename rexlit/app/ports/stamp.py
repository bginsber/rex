"""Stamp port interface for PDF stamping (Bates numbering)."""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class StampConfig(BaseModel):
    """Bates stamp configuration."""

    prefix: str
    start_number: int
    digits: int
    position: str  # "top-right", "bottom-right", etc.
    font_size: int


class BatesAllocation(BaseModel):
    """Bates number allocation record."""

    document_id: str
    bates_start: str
    bates_end: str
    page_count: int


class StampPort(Protocol):
    """Port interface for PDF stamping operations.

    Used for Bates numbering and redaction application.

    Side effects: Modifies PDF files (offline).
    """

    def apply_bates(
        self,
        path: Path,
        output_path: Path,
        config: StampConfig,
    ) -> BatesAllocation:
        """Apply Bates numbering to PDF.

        Args:
            path: Input PDF path
            output_path: Output PDF path
            config: Stamp configuration

        Returns:
            BatesAllocation with assigned numbers
        """
        ...

    def apply_redactions(
        self,
        path: Path,
        output_path: Path,
        redactions: list[dict],
    ) -> int:
        """Apply redactions to PDF.

        Args:
            path: Input PDF path
            output_path: Output PDF path
            redactions: List of redaction coordinates

        Returns:
            Number of redactions applied
        """
        ...

    def get_page_count(self, path: Path) -> int:
        """Get PDF page count.

        Args:
            path: PDF path

        Returns:
            Number of pages
        """
        ...
