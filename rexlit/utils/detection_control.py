"""Detection control and gating utilities for PII/privilege filtering."""

from typing import Optional

# MIME types eligible for PII/privilege detection
DETECTABLE_MIME_TYPES = {
    "text/plain",
    "text/csv",
    "text/xml",
    "text/html",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "application/x-yaml",
    "text/x-log",
}

# File extensions eligible for detection
DETECTABLE_EXTENSIONS = {
    ".txt",
    ".csv",
    ".xml",
    ".html",
    ".htm",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".json",
    ".yaml",
    ".yml",
    ".log",
    ".md",
    ".markdown",
    ".eml",
    ".msg",
}

# Maximum file size for text extraction (100 MB)
DEFAULT_MAX_DETECTION_SIZE_BYTES = 100 * 1024 * 1024


def should_detect_document(
    mime_type: str,
    extension: str,
    size_bytes: int,
    max_size: int = DEFAULT_MAX_DETECTION_SIZE_BYTES,
) -> tuple[bool, Optional[str]]:
    """Determine if a document should be scanned for PII/privilege.

    Args:
        mime_type: MIME type of document
        extension: File extension (with leading dot)
        size_bytes: File size in bytes
        max_size: Maximum size to scan (default 100 MB)

    Returns:
        Tuple of (should_detect, reason_if_skipped)
        - (True, None) if document should be detected
        - (False, reason) if document should be skipped
    """
    # Check extension first (faster than MIME type check)
    ext_lower = extension.lower()
    if ext_lower not in DETECTABLE_EXTENSIONS:
        return (False, f"extension_not_detectable:{ext_lower}")

    # Check MIME type
    mime_lower = mime_type.lower()
    if mime_lower not in DETECTABLE_MIME_TYPES:
        return (False, f"mime_not_detectable:{mime_lower}")

    # Check file size
    if size_bytes > max_size:
        return (False, f"exceeds_max_size:{size_bytes // (1024 * 1024)}MB")

    return (True, None)
