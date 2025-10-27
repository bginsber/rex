"""Document discovery and metadata extraction."""

import logging
import mimetypes
import os
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.paths import find_files

logger = logging.getLogger(__name__)


class DocumentMetadata(BaseModel):
    """Metadata for a discovered document."""

    path: str = Field(..., description="Absolute path to document")
    sha256: str = Field(..., description="SHA-256 hash of file content")
    size: int = Field(..., description="File size in bytes")
    mime_type: str | None = Field(None, description="MIME type")
    extension: str = Field(..., description="File extension (lowercase)")
    mtime: str = Field(..., description="Modification time (ISO 8601)")
    custodian: str | None = Field(None, description="Document custodian")
    doctype: str | None = Field(None, description="Document type classification")

    def model_dump(self, **kwargs) -> dict:  # type: ignore
        """Override to ensure compatibility."""
        return super().model_dump(**kwargs)


def detect_mime_type(file_path: Path) -> str | None:
    """Detect MIME type of file.

    Args:
        file_path: Path to file

    Returns:
        MIME type string or None if unknown
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type


def classify_doctype(mime_type: str | None, extension: str) -> str | None:
    """Classify document type based on MIME type and extension.

    Args:
        mime_type: MIME type string
        extension: File extension

    Returns:
        Document type classification
    """
    if mime_type:
        if mime_type.startswith("application/pdf"):
            return "pdf"
        elif mime_type.startswith("application/vnd.openxmlformats-officedocument.wordprocessing"):
            return "docx"
        elif mime_type.startswith("application/msword"):
            return "doc"
        elif mime_type.startswith("text/"):
            return "text"
        elif mime_type.startswith("image/"):
            return "image"
        elif mime_type.startswith("message/"):
            return "email"

    # Fallback to extension-based classification
    ext_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "doc",
        ".txt": "text",
        ".md": "text",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".tiff": "image",
        ".msg": "email",
        ".eml": "email",
        ".pst": "email_archive",
    }

    return ext_map.get(extension.lower())


def extract_custodian(file_path: Path) -> str | None:
    """Extract custodian from file path.

    Attempts to extract custodian name from directory structure.
    Looks for patterns like /custodians/john_doe/ or /users/jane_smith/

    Args:
        file_path: Path to file

    Returns:
        Custodian name or None
    """
    parts = file_path.parts

    # Look for custodian markers in path
    custodian_markers = {"custodians", "users", "custodian", "user"}

    for i, part in enumerate(parts):
        if part.lower() in custodian_markers and i + 1 < len(parts):
            return parts[i + 1]

    return None


def discover_document(
    file_path: Path,
    allowed_root: Path | None = None,
    *,
    precomputed_hash: str | None = None,
) -> DocumentMetadata:
    """Discover and extract metadata for a single document.

    Args:
        file_path: Path to document
        allowed_root: Optional root directory to enforce path boundary validation.
                     If provided, ensures discovered files are within this directory.
        precomputed_hash: Optional SHA-256 hash computed upstream to avoid re-reading the file.

    Returns:
        Document metadata

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
        ValueError: If path traversal attempt detected or not a file
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # SECURITY: Resolve symlinks and validate path is within allowed root
    resolved_path = file_path.resolve()

    if allowed_root:
        allowed_root_resolved = allowed_root.resolve()
        try:
            resolved_path.relative_to(allowed_root_resolved)
        except ValueError:
            raise ValueError(
                f"Security: Path traversal detected. "
                f"File {file_path} resolves to {resolved_path} "
                f"which is outside allowed root {allowed_root_resolved}"
            ) from None

    if not resolved_path.is_file():
        raise ValueError(f"Not a file: {resolved_path}")

    # Get file stats - use resolved_path for all operations
    stat = resolved_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()

    # Compute hash
    sha256 = precomputed_hash or compute_sha256_file(resolved_path)

    # Detect MIME type
    mime_type = detect_mime_type(resolved_path)

    # Get extension
    extension = resolved_path.suffix

    # Classify document type
    doctype = classify_doctype(mime_type, extension)

    # Extract custodian
    custodian = extract_custodian(resolved_path)

    return DocumentMetadata(
        path=str(resolved_path.absolute()),
        sha256=sha256,
        size=stat.st_size,
        mime_type=mime_type,
        extension=extension,
        mtime=mtime,
        custodian=custodian,
        doctype=doctype,
    )


def discover_documents(
    root: Path,
    recursive: bool = True,
    include_extensions: set[str] | None = None,
    exclude_extensions: set[str] | None = None,
) -> Iterator[DocumentMetadata]:
    """Discover documents in directory and extract metadata.

    This function streams document discovery results using a generator pattern,
    enabling constant memory usage regardless of document count. Processing
    can begin immediately without waiting for full discovery to complete.

    Args:
        root: Root directory or single file path
        recursive: Search recursively (default: True)
        include_extensions: Only include these extensions (e.g., {'.pdf', '.docx'})
        exclude_extensions: Exclude these extensions

    Yields:
        DocumentMetadata objects as they are discovered

    Raises:
        FileNotFoundError: If root path does not exist
    """
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    # SECURITY: Establish security boundary for path validation
    allowed_root = root.resolve() if root.is_dir() else None

    # Handle single file
    if root.is_file():
        yield discover_document(root, allowed_root=None)
        return

    max_workers = max(1, min(32, (os.cpu_count() or 1) * 2))
    pending: dict[Future[str], Path] = {}

    def drain_pending(*, block: bool) -> Iterator[DocumentMetadata]:
        """Yield metadata for completed hash computations."""
        if not pending:
            return

        ready_iter = (
            as_completed(list(pending))
            if block
            else (future for future in list(pending) if future.done())
        )

        for future in ready_iter:
            path = pending.pop(future)
            try:
                sha256 = future.result()
            except Exception as exc:
                logger.warning("Failed to compute hash for %s: %s", path, exc)
                print(f"Warning: Skipping {path}: hash computation failed ({exc})")
                continue

            try:
                metadata = discover_document(
                    path, allowed_root=allowed_root, precomputed_hash=sha256
                )
            except ValueError as e:
                if "Path traversal" in str(e):
                    logger.warning("SECURITY: %s", e)
                    print(f"SECURITY WARNING: {e}")
                else:
                    print(f"Warning: Skipping {path}: {e}")
                continue
            except (FileNotFoundError, PermissionError) as e:
                print(f"Warning: Skipping {path}: {e}")
                continue
            else:
                yield metadata

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Stream files as they're discovered
        for file_path in find_files(root, recursive=recursive):
            suffix = file_path.suffix.lower()
            if include_extensions and suffix not in include_extensions:
                continue
            if exclude_extensions and suffix in exclude_extensions:
                continue

            try:
                resolved_path = file_path.resolve()
            except FileNotFoundError as exc:
                print(f"Warning: Skipping {file_path}: {exc}")
                continue

            if allowed_root:
                try:
                    resolved_path.relative_to(allowed_root)
                except ValueError:
                    logger.warning(
                        "SECURITY: Path traversal detected. File %s resolves to %s outside %s",
                        file_path,
                        resolved_path,
                        allowed_root,
                    )
                    print(
                        "SECURITY WARNING: Path traversal detected. "
                        f"File {file_path} resolves to {resolved_path} outside {allowed_root}"
                    )
                    continue

            if not resolved_path.is_file():
                print(f"Warning: Skipping {resolved_path}: Not a file")
                continue

            try:
                pending[executor.submit(compute_sha256_file, resolved_path)] = resolved_path
            except PermissionError as exc:
                print(f"Warning: Skipping {resolved_path}: {exc}")
                continue

            if len(pending) >= max_workers * 4:
                yield from drain_pending(block=False)

        # Drain remaining futures
        yield from drain_pending(block=True)
