"""Storage port interface for filesystem operations."""

from pathlib import Path
from typing import Protocol, Iterator, Any


class StoragePort(Protocol):
    """Port interface for storage operations.

    Abstracts filesystem I/O to enable testing and alternative backends.

    Side effects: Reads/writes files (offline).
    """

    def read_text(self, path: Path) -> str:
        """Read text file.

        Args:
            path: File path

        Returns:
            File contents as string
        """
        ...

    def write_text(self, path: Path, content: str) -> None:
        """Write text file.

        Args:
            path: File path
            content: Content to write
        """
        ...

    def read_jsonl(self, path: Path) -> Iterator[dict[str, Any]]:
        """Read JSONL file line by line.

        Args:
            path: Path to JSONL file

        Yields:
            Parsed JSON objects
        """
        ...

    def write_jsonl(self, path: Path, records: Iterator[dict[str, Any]]) -> int:
        """Write JSONL file.

        Args:
            path: Path to JSONL file
            records: Iterator of dictionaries to write

        Returns:
            Number of records written
        """
        ...

    def list_files(self, directory: Path, pattern: str = "*") -> Iterator[Path]:
        """List files in directory.

        Args:
            directory: Directory path
            pattern: Glob pattern (default: all files)

        Yields:
            File paths
        """
        ...

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy file.

        Args:
            src: Source path
            dst: Destination path
        """
        ...

    def compute_hash(self, path: Path) -> str:
        """Compute SHA-256 hash of file.

        Args:
            path: File path

        Returns:
            Hex-encoded SHA-256 hash
        """
        ...
