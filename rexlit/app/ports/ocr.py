"""OCR port interface for optical character recognition."""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class OCRResult(BaseModel):
    """OCR processing result."""

    path: str
    text: str
    confidence: float
    language: str
    page_count: int


class OCRPort(Protocol):
    """Port interface for OCR operations.

    Adapters: Tesseract, PaddleOCR, DeepSeek (online).

    Side effects:
    - Offline: Tesseract, PaddleOCR (local processing)
    - Online: DeepSeek (API calls, requires --online flag)
    """

    def process_document(
        self,
        path: Path,
        *,
        language: str = "eng",
    ) -> OCRResult:
        """Process document with OCR.

        Args:
            path: Path to document (PDF or image)
            language: OCR language code

        Returns:
            OCRResult with extracted text and metadata
        """
        ...

    def is_online(self) -> bool:
        """Check if this adapter requires online access.

        Returns:
            True if adapter makes network calls
        """
        ...
