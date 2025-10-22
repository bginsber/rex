"""Append-only audit ledger with deterministic hashing for chain-of-custody."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from rexlit import __version__
from rexlit.utils.hashing import compute_sha256


class AuditEntry(BaseModel):
    """Single audit ledger entry.

    All entries are immutable and include cryptographic hashes for verification.
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
    entry_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of entry content (excluding this field)",
    )

    def compute_hash(self) -> str:
        """Compute deterministic hash of entry content.

        Returns:
            SHA-256 hash of entry (excluding entry_hash field)
        """
        # Create copy without entry_hash for deterministic hashing
        data = self.model_dump(mode="json", exclude={"entry_hash"})
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
    append-only semantics.
    """

    def __init__(self, ledger_path: Path) -> None:
        """Initialize audit ledger.

        Args:
            ledger_path: Path to JSONL ledger file
        """
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

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

        # Create entry
        entry = AuditEntry(
            timestamp=datetime.now(UTC).isoformat(),
            operation=operation,
            inputs=inputs or [],
            outputs=outputs or [],
            args=args or {},
            versions=versions,
        )

        # Append to ledger
        with open(self.ledger_path, "a") as f:
            f.write(entry.model_dump_json() + "\n")

        return entry

    def read_all(self) -> list[AuditEntry]:
        """Read all entries from the ledger.

        Returns:
            List of audit entries in chronological order

        Raises:
            FileNotFoundError: If ledger file does not exist
        """
        if not self.ledger_path.exists():
            return []

        entries = []
        with open(self.ledger_path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = AuditEntry.model_validate_json(line)
                    entries.append(entry)
                except Exception as e:
                    raise ValueError(
                        f"Invalid entry at line {line_num} in {self.ledger_path}: {e}"
                    ) from e

        return entries

    def verify(self) -> bool:
        """Verify integrity of all entries in the ledger.

        Returns:
            True if all entries have valid hashes, False otherwise
        """
        try:
            entries = self.read_all()
        except (FileNotFoundError, ValueError):
            return False

        for entry in entries:
            expected_hash = entry.compute_hash()
            if entry.entry_hash != expected_hash:
                return False

        return True

    def get_by_operation(self, operation: str) -> list[AuditEntry]:
        """Get all entries for a specific operation.

        Args:
            operation: Operation name to filter by

        Returns:
            List of matching audit entries
        """
        entries = self.read_all()
        return [e for e in entries if e.operation == operation]

    def get_by_input(self, input_path: str) -> list[AuditEntry]:
        """Get all entries that processed a specific input.

        Args:
            input_path: Input file path or identifier

        Returns:
            List of matching audit entries
        """
        entries = self.read_all()
        return [e for e in entries if input_path in e.inputs]

    def get_by_output(self, output_hash: str) -> list[AuditEntry]:
        """Get all entries that produced a specific output.

        Args:
            output_hash: Output SHA-256 hash or identifier

        Returns:
            List of matching audit entries
        """
        entries = self.read_all()
        return [e for e in entries if output_hash in e.outputs]
