"""Append-only audit ledger with deterministic hashing for chain-of-custody."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from rexlit import __version__
from rexlit.utils.crypto import load_or_create_hmac_key
from rexlit.utils.hashing import compute_sha256

GENESIS_HASH = "0" * 64
GENESIS_SIGNATURE = "0" * 64


class AuditEntry(BaseModel):
    """Single audit ledger entry.

    All entries are immutable and include cryptographic hashes for verification.
    Entries are linked in a hash chain to ensure tamper-evidence.
    """

    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp in UTC",
    )
    operation: str = Field(
        ...,
        description="Operation name (e.g., ingest, ocr, bates)",
    )
    inputs: list[str] = Field(
        default_factory=list,
        description="Input file paths or identifiers",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="Output SHA-256 hashes or identifiers",
    )
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation arguments and parameters",
    )
    versions: dict[str, str] = Field(
        default_factory=dict,
        description="Tool versions used in operation",
    )
    previous_hash: str = Field(
        default=GENESIS_HASH,
        description="SHA-256 hash of previous entry (chain link). Genesis entry has 64 zeros.",
    )
    sequence: int | None = Field(
        default=None,
        ge=1,
        description="Monotonic sequence number starting at 1.",
    )
    entry_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of entry content including previous_hash (excluding this field)",
    )
    signature: str | None = Field(
        default=None,
        description="HMAC signature sealing the entry for tamper detection.",
    )

    def compute_hash(self) -> str:
        """Compute deterministic hash of entry content.

        Returns:
            SHA-256 hash of entry (excluding entry_hash and signature fields)
        """
        # Create copy without entry_hash/signature for deterministic hashing
        data = self.model_dump(
            mode="json",
            exclude={"entry_hash", "signature"},
            exclude_none=True,
        )
        content = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return compute_sha256(content.encode("utf-8"))

    def model_post_init(self, __context: Any) -> None:
        """Compute hash after initialization if not set."""
        if self.entry_hash is None:
            self.entry_hash = self.compute_hash()


class AuditLedger:
    """Append-only audit ledger for defensible chain-of-custody.

    All operations are logged with timestamps, inputs, outputs, and cryptographic hashes.
    The ledger is stored as JSONL (one JSON object per line) for easy parsing and
    append-only semantics. Entries are linked in a blockchain-style hash chain for
    tamper-evidence and sealed with HMAC signatures for tamper detection.
    """

    def __init__(self, ledger_path: Path, *, hmac_key: bytes | None = None) -> None:
        """Initialize audit ledger.

        Args:
            ledger_path: Path to JSONL ledger file
            hmac_key: Optional key for signing metadata (defaults to on-disk secret)
        """
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        self._metadata_path = ledger_path.with_suffix(".meta")
        if hmac_key is None:
            self._hmac_key = load_or_create_hmac_key(ledger_path.with_suffix(".key"), length=32)
        else:
            self._hmac_key = hmac_key

        self._last_hash = GENESIS_HASH
        self._last_sequence = 0
        self._last_signature = GENESIS_SIGNATURE

        self._bootstrap_state()

    # ---------------------------------------------------------------------#
    # Internal helpers
    # ---------------------------------------------------------------------#

    def _bootstrap_state(self) -> None:
        """Restore last known hash/sequence/signature state from ledger."""
        entries = self._read_entries()

        if entries:
            last_entry = entries[-1]
            self._last_hash = last_entry.entry_hash or GENESIS_HASH
            if last_entry.sequence is not None:
                self._last_sequence = last_entry.sequence
            else:
                self._last_sequence = len(entries)
            self._last_signature = last_entry.signature or GENESIS_SIGNATURE

        self._ensure_metadata_initialized()

    def _ensure_metadata_initialized(self) -> None:
        """Create metadata file if missing."""
        try:
            metadata = self._load_metadata()
        except ValueError:
            # Metadata exists but is invalid; leave untouched so verify() surfaces it.
            return

        if metadata is None:
            last_hash = None if self._last_sequence == 0 else self._last_hash
            self._write_metadata(self._last_sequence, last_hash)

    def _read_entries(self) -> list[AuditEntry]:
        """Load ledger entries from disk."""
        if not self.ledger_path.exists():
            return []

        entries: list[AuditEntry] = []
        with open(self.ledger_path, encoding="utf-8") as fh:
            for line_num, raw_line in enumerate(fh, 1):
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    entry = AuditEntry.model_validate_json(line)
                    entries.append(entry)
                except Exception as exc:  # pragma: no cover - defensive logging path
                    raise ValueError(
                        f"Invalid entry at line {line_num} in {self.ledger_path}: {exc}"
                    ) from exc

        return entries

    def _compute_signature(self, entry: AuditEntry, previous_signature: str) -> str:
        """Compute HMAC signature for an entry."""
        payload = "|".join(
            [
                str(entry.sequence or 0),
                entry.previous_hash,
                entry.entry_hash or "",
                previous_signature,
            ]
        ).encode("utf-8")

        return hmac.new(self._hmac_key, payload, hashlib.sha256).hexdigest()

    def _compute_metadata_hmac(self, last_sequence: int, last_hash: str | None) -> str:
        """Compute HMAC for ledger metadata."""
        payload = f"{last_sequence}:{last_hash or GENESIS_HASH}".encode("utf-8")
        return hmac.new(self._hmac_key, payload, hashlib.sha256).hexdigest()

    def _write_metadata(self, last_sequence: int, last_hash: str | None) -> None:
        """Persist metadata describing the current tip of the ledger."""
        payload = {
            "version": 1,
            "last_sequence": last_sequence,
            "last_hash": last_hash,
            "hmac": self._compute_metadata_hmac(last_sequence, last_hash),
        }
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

        fd = os.open(self._metadata_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

        try:
            os.chmod(self._metadata_path, 0o600)
        except PermissionError:
            pass

    def _load_metadata(self) -> dict[str, Any] | None:
        """Load and validate ledger metadata."""
        try:
            raw = self._metadata_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        data = json.loads(raw)
        expected_hmac = self._compute_metadata_hmac(
            int(data.get("last_sequence", 0)), data.get("last_hash")
        )
        actual_hmac = data.get("hmac")

        if not isinstance(actual_hmac, str) or not hmac.compare_digest(expected_hmac, actual_hmac):
            raise ValueError("Audit metadata HMAC mismatch")

        return data

    # ---------------------------------------------------------------------#
    # Public API
    # ---------------------------------------------------------------------#

    def log(
        self,
        operation: str,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        args: dict[str, Any] | None = None,
        versions: dict[str, str] | None = None,
    ) -> AuditEntry:
        """Log an operation to the audit ledger.

        Args:
            operation: Operation name
            inputs: Input file paths or identifiers
            outputs: Output SHA-256 hashes or identifiers
            args: Operation arguments and parameters
            versions: Tool versions (defaults to rexlit version)

        Returns:
            The created audit entry
        """
        # Default versions to include rexlit
        if versions is None:
            versions = {}
        if "rexlit" not in versions:
            versions["rexlit"] = __version__

        sequence = self._last_sequence + 1

        entry = AuditEntry(
            timestamp=datetime.now(UTC).isoformat(),
            operation=operation,
            inputs=inputs or [],
            outputs=outputs or [],
            args=args or {},
            versions=versions,
            previous_hash=self._last_hash,
            sequence=sequence,
        )

        # Compute hash (includes previous_hash for chain integrity)
        entry.entry_hash = entry.compute_hash()
        entry.signature = self._compute_signature(entry, self._last_signature)

        # Append to ledger with fsync for legal defensibility
        with open(self.ledger_path, "a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())

        # Update last state for next entry
        self._last_sequence = sequence
        self._last_hash = entry.entry_hash or GENESIS_HASH
        self._last_signature = entry.signature or GENESIS_SIGNATURE

        self._write_metadata(sequence, entry.entry_hash)

        return entry

    def read_all(self) -> list[AuditEntry]:
        """Read all entries from the ledger.

        Returns:
            List of audit entries in chronological order
        """
        return self._read_entries()

    def verify(self) -> tuple[bool, str | None]:
        """Verify integrity of hash chain and metadata.

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        try:
            metadata = self._load_metadata()
        except ValueError as exc:
            return False, f"Audit metadata integrity failure: {exc}"

        entries = self._read_entries()

        if not self.ledger_path.exists():
            if metadata and metadata.get("last_sequence", 0) > 0:
                return False, "Audit ledger file is missing but metadata indicates prior entries."
            return True, None

        if not entries:
            if metadata and metadata.get("last_sequence", 0) > 0:
                return False, "Audit ledger appears truncated (no entries but metadata expects data)."
            return True, None

        previous_hash = GENESIS_HASH
        previous_signature = GENESIS_SIGNATURE

        for idx, entry in enumerate(entries, 1):
            if entry.sequence is None:
                return (
                    False,
                    f"Entry {idx} missing sequence number; audit log predates tamper-proofing.",
                )

            if entry.entry_hash is None:
                return (
                    False,
                    f"Entry {idx} missing entry_hash; ledger corrupted or tampered.",
                )

            if entry.signature is None:
                return (
                    False,
                    f"Entry {idx} missing signature; audit log predates tamper-proofing.",
                )

            expected_hash = entry.compute_hash()
            if not hmac.compare_digest(entry.entry_hash, expected_hash):
                return (
                    False,
                    f"Entry {idx} has invalid hash (expected '{expected_hash}', got '{entry.entry_hash}').",
                )

            if entry.previous_hash != previous_hash:
                return (
                    False,
                    f"Entry {idx} breaks hash chain (expected previous_hash='{previous_hash}', "
                    f"found '{entry.previous_hash}').",
                )

            expected_signature = self._compute_signature(entry, previous_signature)
            if not hmac.compare_digest(entry.signature, expected_signature):
                return (
                    False,
                    f"Entry {idx} has invalid signature; ledger may have been tampered.",
                )

            if entry.sequence != idx:
                return (
                    False,
                    f"Entry {idx} sequence mismatch (expected {idx}, got {entry.sequence}).",
                )

            previous_hash = entry.entry_hash
            previous_signature = entry.signature

        if metadata is None:
            return False, "Audit metadata file is missing."

        last_entry = entries[-1]
        meta_sequence = int(metadata.get("last_sequence", 0))
        meta_hash = metadata.get("last_hash")

        if meta_sequence != last_entry.sequence:
            return (
                False,
                f"Ledger metadata sequence mismatch (expected {last_entry.sequence}, got {meta_sequence}).",
            )

        if meta_hash != last_entry.entry_hash:
            return (
                False,
                "Ledger metadata hash mismatch; possible truncation or tampering detected.",
            )

        return True, None

    def get_by_operation(self, operation: str) -> list[AuditEntry]:
        """Get all entries for a specific operation.

        Args:
            operation: Operation name to filter by

        Returns:
            List of matching audit entries
        """
        entries = self.read_all()
        return [entry for entry in entries if entry.operation == operation]

    def get_by_input(self, input_path: str) -> list[AuditEntry]:
        """Get all entries that processed a specific input.

        Args:
            input_path: Input file path or identifier

        Returns:
            List of matching audit entries
        """
        entries = self.read_all()
        return [entry for entry in entries if input_path in entry.inputs]

    def get_by_output(self, output_hash: str) -> list[AuditEntry]:
        """Get all entries that produced a specific output.

        Args:
            output_hash: Output SHA-256 hash or identifier

        Returns:
            List of matching audit entries
        """
        entries = self.read_all()
        return [entry for entry in entries if output_hash in entry.outputs]
