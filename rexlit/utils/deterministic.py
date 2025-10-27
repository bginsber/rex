"""Deterministic ordering utilities for reproducible workflows."""

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from rexlit.utils.hashing import compute_sha256_file

T = TypeVar("T")


def deterministic_sort_paths(paths: Iterable[Path]) -> list[Path]:
    """Sort paths deterministically using (sha256, relative_path).

    This ensures identical ordering across runs regardless of filesystem
    traversal order, enabling reproducible artifact generation.

    Args:
        paths: Iterable of paths to sort

    Returns:
        Sorted list of paths

    Example:
        >>> paths = [Path("doc3.pdf"), Path("doc1.pdf"), Path("doc2.pdf")]
        >>> sorted_paths = deterministic_sort_paths(paths)
        >>> # Always returns same order based on content hash + path
    """

    def sort_key(path: Path) -> tuple[str, str]:
        """Compute sort key: (content_hash, path_str)."""
        # Compute content hash if file exists
        if path.is_file():
            try:
                content_hash = compute_sha256_file(path)
            except (OSError, ValueError):
                # Fall back to deterministic path hashing if file cannot be read
                content_hash = hashlib.sha256(str(path).encode()).hexdigest()
        else:
            # For non-files (directories, missing files), use path hash
            content_hash = hashlib.sha256(str(path).encode()).hexdigest()

        return (content_hash, str(path))

    # Convert to list and sort by (hash, path)
    path_list = list(paths)
    return sorted(path_list, key=sort_key)


def deterministic_sort_records(
    records: Iterable[dict],
    key_field: str = "sha256",
) -> list[dict]:
    """Sort records deterministically by key field.

    Args:
        records: Iterable of dictionaries
        key_field: Field name to use as sort key (default: 'sha256')

    Returns:
        Sorted list of records
    """
    record_list = list(records)
    return sorted(record_list, key=lambda r: r.get(key_field, ""))


def compute_input_hash(inputs: list[str]) -> str:
    """Compute deterministic hash of sorted inputs.

    Used for plan_id generation to ensure reproducibility.

    Args:
        inputs: List of input identifiers (paths, hashes, etc.)

    Returns:
        SHA-256 hex digest of sorted inputs
    """
    # Sort inputs for determinism
    sorted_inputs = sorted(inputs)

    # Concatenate and hash
    combined = "\n".join(sorted_inputs)
    return hashlib.sha256(combined.encode()).hexdigest()


def verify_determinism(func, inputs: Iterable[T], runs: int = 3) -> bool:
    """Verify function produces deterministic output.

    Useful for testing pipeline determinism.

    Args:
        func: Function to test
        inputs: Input data
        runs: Number of runs to verify (default: 3)

    Returns:
        True if all runs produce identical output

    Example:
        >>> def my_pipeline(docs):
        ...     return process(docs)
        >>> assert verify_determinism(my_pipeline, test_docs)
    """
    results = []

    for _ in range(runs):
        result = func(inputs)
        results.append(result)

    # Check all results are identical
    first_result = results[0]
    return all(r == first_result for r in results)


def document_sort_key(document: Any) -> tuple[str, str]:
    """Return deterministic sort key for document-like objects."""

    if isinstance(document, dict):
        sha = document.get("sha256", "")
        path = document.get("path", "")
    else:
        sha = getattr(document, "sha256", "")
        path = getattr(document, "path", "")

    return (str(sha), str(path))


def deterministic_order_documents(documents: Iterable[T]) -> list[T]:
    """Sort documents deterministically by (sha256, path)."""

    return sorted(list(documents), key=document_sort_key)
