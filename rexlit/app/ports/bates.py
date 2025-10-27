"""Bates planning port interfaces and DTOs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from pydantic import BaseModel, Field

from rexlit.app.ports.discovery import DocumentRecord


class BatesAssignment(BaseModel):
    """Single Bates number assignment for a document."""

    document: str = Field(..., description="Absolute path to the document")
    sha256: str = Field(..., description="Content hash verified during planning")
    bates_id: str = Field(..., description="Assigned Bates identifier")


class BatesPlan(BaseModel):
    """Container describing a generated Bates plan artifact."""

    path: Path = Field(..., description="Filesystem path to the persisted plan JSONL")
    assignments: list[BatesAssignment] = Field(
        default_factory=list,
        description="Ordered Bates assignments covering the input documents",
    )


class BatesPlannerPort(Protocol):
    """Port interface for Bates plan generation."""

    def plan(self, documents: Iterable[DocumentRecord]) -> BatesPlan:
        """Produce a Bates numbering plan for ``documents``."""
        ...
