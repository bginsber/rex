"""Document discovery and metadata extraction."""

import mimetypes
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.paths import find_files


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


def discover_document(file_path: Path) -> DocumentMetadata:
    """Discover and extract metadata for a single document.

    Args:
        file_path: Path to document

    Returns:
        Document metadata

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # Get file stats
    stat = file_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()

    # Compute hash
    sha256 = compute_sha256_file(file_path)

    # Detect MIME type
    mime_type = detect_mime_type(file_path)

    # Get extension
    extension = file_path.suffix

    # Classify document type
    doctype = classify_doctype(mime_type, extension)

    # Extract custodian
    custodian = extract_custodian(file_path)

    return DocumentMetadata(
        path=str(file_path.absolute()),
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
) -> list[DocumentMetadata]:
    """Discover documents in directory and extract metadata.

    Args:
        root: Root directory or single file path
        recursive: Search recursively (default: True)
        include_extensions: Only include these extensions (e.g., {'.pdf', '.docx'})
        exclude_extensions: Exclude these extensions

    Returns:
        List of document metadata

    Raises:
        FileNotFoundError: If root path does not exist
    """
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    # Handle single file
    if root.is_file():
        return [discover_document(root)]

    # Discover all files
    files = find_files(root, recursive=recursive)

    # Filter by extensions
    if include_extensions:
        files = [f for f in files if f.suffix.lower() in include_extensions]

    if exclude_extensions:
        files = [f for f in files if f.suffix.lower() not in exclude_extensions]

    # Extract metadata
    documents = []
    for file_path in files:
        try:
            metadata = discover_document(file_path)
            documents.append(metadata)
        except (FileNotFoundError, PermissionError, ValueError) as e:
            # Skip files that can't be read
            print(f"Warning: Skipping {file_path}: {e}")
            continue

    return documents
