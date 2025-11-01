"""Stamp port interface for PDF stamping (Bates numbering)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class BatesStampRequest(BaseModel):
    """Configuration and inputs for a Bates stamping operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    input_path: Path = Field(..., description="Source PDF to stamp")
    output_path: Path = Field(..., description="Destination PDF with Bates numbers")
    prefix: str = Field(..., description="Bates prefix (e.g. 'ABC')")
    start_number: int = Field(1, ge=1, description="Starting sequence number (1-indexed)")
    width: int = Field(7, ge=1, le=12, description="Zero-padding width for numeric portion")
    position: Literal["bottom-right", "bottom-center", "top-right"] = Field(
        "bottom-right", description="Stamp placement preset"
    )
    font_size: int = Field(10, ge=6, le=72, description="Font size in points")
    color: tuple[float, float, float] = Field(
        (0.0, 0.0, 0.0), description="RGB color tuple with values in range 0-1"
    )
    background: bool = Field(
        True, description="Whether to paint an opaque background rectangle behind text"
    )


class PageStampCoordinate(BaseModel):
    """Audit trail for a single stamped page."""

    page: int = Field(..., ge=1, description="1-indexed page number")
    label: str = Field(..., description="Rendered Bates label for the page")
    position: dict[str, float] = Field(
        ...,
        description="Axis-aligned bounding box coordinates (x0, y0, x1, y1) in PDF points",
    )
    rotation: int = Field(..., description="Page rotation in degrees")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Rendering confidence score")


class BatesStampResult(BaseModel):
    """Result metadata produced after stamping a PDF."""

    input_path: Path
    output_path: Path
    pages_stamped: int = Field(..., ge=0)
    start_number: int = Field(..., ge=1)
    end_number: int = Field(..., ge=1)
    start_label: str = Field(...)
    end_label: str = Field(...)
    prefix: str = Field(...)
    width: int = Field(..., ge=1)
    coordinates: list[PageStampCoordinate] = Field(default_factory=list)


class BatesStampPreview(BaseModel):
    """Preview information returned by dry-run executions."""

    input_path: Path
    total_pages: int = Field(..., ge=0)
    start_number: int = Field(..., ge=1)
    prefix: str = Field(...)
    width: int = Field(..., ge=1)
    preview_labels: list[str] = Field(default_factory=list)


class StampPort(Protocol):
    """Port interface for PDF stamping operations.

    Used for Bates numbering and redaction application.

    Side effects: Modifies PDF files (offline).
    """

    def stamp(self, request: BatesStampRequest) -> BatesStampResult:
        """Apply Bates numbers according to ``request`` and persist the output PDF."""
        ...

    def dry_run(self, request: BatesStampRequest) -> BatesStampPreview:
        """Return preview information without modifying the document."""
        ...

    def apply_redactions(
        self,
        path: Path,
        output_path: Path,
        redactions: list[dict[str, Any]],
    ) -> int:
        """Apply redactions to PDF and return the number of redactions applied."""
        ...

    def get_page_count(self, path: Path) -> int:
        """Get total number of pages contained in ``path``."""
        ...
