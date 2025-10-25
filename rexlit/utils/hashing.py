"""Hashing utilities for deterministic file and content hashing."""

import hashlib
from pathlib import Path


def compute_sha256(content: bytes) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: Bytes to hash

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(content).hexdigest()


def compute_sha256_file(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        file_path: Path to file
        chunk_size: Size of chunks to read (default 64KB)

    Returns:
        Hexadecimal hash string

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


def compute_sha256_files(file_paths: list[Path]) -> dict[Path, str]:
    """Compute SHA-256 hashes for multiple files.

    Args:
        file_paths: List of file paths

    Returns:
        Dictionary mapping file paths to their hashes
    """
    return {path: compute_sha256_file(path) for path in file_paths if path.is_file()}
