"""Encrypted storage helpers for personally identifiable information findings."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from rexlit import __version__
from rexlit.config import Settings
from rexlit.utils.crypto import decrypt_blob, encrypt_blob


class PIIFindingRecord(BaseModel):
    """Schema-compatible representation of a PII finding."""

    schema_id: str = Field(default="pii_findings", description="Schema identifier.")
    schema_version: int = Field(default=1, description="Schema version number.")
    producer: str = Field(
        default_factory=lambda: f"rexlit-{__version__}",
        description="Producer identifier (tool version).",
    )
    produced_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Timestamp when the finding was produced.",
    )
    document_id: str = Field(..., description="Identifier of the analyzed document.")
    entity_type: str = Field(..., description="Type of PII entity detected.")
    text: str = Field(..., description="Raw text containing PII (encrypted at rest).")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1).")
    start: int = Field(..., ge=0, description="Start offset within the source text.")
    end: int = Field(..., ge=0, description="End offset within the source text.")
    page: int | None = Field(default=None, ge=1, description="Optional page number.")
    coordinates: dict[str, float] | None = Field(
        default=None,
        description="Optional bounding box coordinates for redaction tooling.",
    )

    @field_validator("entity_type")
    @staticmethod
    def _normalize_entity(entity_type: str) -> str:
        """Normalize entity type to uppercase tokens."""
        return entity_type.upper()


class EncryptedPIIStore:
    """Append-only encrypted store for PII findings."""

    def __init__(self, settings: Settings, *, path: Path | None = None) -> None:
        self._settings = settings
        self._path = path or settings.get_pii_store_path()
        self._key = settings.get_pii_key()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Return the underlying storage path."""
        return self._path

    def append(self, record: PIIFindingRecord) -> None:
        """Encrypt and append a record to the store."""
        payload = json.dumps(
            record.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        encrypted = encrypt_blob(payload, key=self._key)
        token = encrypted.decode("utf-8")

        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(token + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read_all(self) -> list[PIIFindingRecord]:
        """Decrypt and load all stored records."""
        if not self._path.exists():
            return []

        records: list[PIIFindingRecord] = []

        with open(self._path, encoding="utf-8") as fh:
            for line_num, raw_line in enumerate(fh, 1):
                token = raw_line.strip()
                if not token:
                    continue

                try:
                    decrypted = decrypt_blob(token.encode("utf-8"), key=self._key)
                    data: dict[str, Any] = json.loads(decrypted.decode("utf-8"))
                    records.append(PIIFindingRecord.model_validate(data))
                except Exception as exc:  # pragma: no cover - defensive path
                    raise ValueError(
                        f"Failed to decrypt PII record at line {line_num}: {exc}"
                    ) from exc

        return records

    def read_by_document(self, document_id: str) -> list[PIIFindingRecord]:
        """Return all findings associated with ``document_id``."""
        return [record for record in self.read_all() if record.document_id == document_id]

    def purge(self) -> None:
        """Securely remove stored findings."""
        try:
            self._path.unlink()
        except FileNotFoundError:
            return
