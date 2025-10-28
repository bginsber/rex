"""Discovery port interface and document DTOs for ingest workflows."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, field_validator


class DocumentRecord(BaseModel):
    """Normalized representation of a discovered document."""

    path: str = Field(..., description="Absolute filesystem path to the document")
    sha256: str = Field(..., description="Content hash used for integrity and dedupe checks")
    size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str | None = Field(
        None, description="Best-effort MIME type detected for the document"
    )
    extension: str = Field(..., description="File extension including leading dot")
    mtime: str = Field(..., description="ISO 8601 modification timestamp")
    custodian: str | None = Field(None, description="Custodian inferred from the path")
    doctype: str | None = Field(None, description="Document classification (pdf, email, etc.)")

    @field_validator("path")
    def _validate_path(cls, value: str) -> str:
        resolved = Path(value)
        if not resolved.is_absolute():
            raise ValueError("DocumentRecord.path must be an absolute path")
        return str(resolved)


class DiscoveryPort(Protocol):
    """Port interface for streaming document discovery."""

    def discover(
        self,
        root: Path,
        *,
        recursive: bool = True,
        include_extensions: set[str] | None = None,
        exclude_extensions: set[str] | None = None,
    ) -> Iterator[DocumentRecord]:
        """Yield document records discovered under ``root``."""
        ...
