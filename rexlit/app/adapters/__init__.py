"""Concrete adapters wiring application ports to built-in implementations."""

from __future__ import annotations

from .bates import SequentialBatesPlanner
from .dedupe import HashDeduper
from .discovery import IngestDiscoveryAdapter
from .hnsw import HNSWAdapter
from .kanon2 import Kanon2Adapter
from .pack import ZipPackager
from .pdf_stamper import PDFStamperAdapter
from .redaction import JSONLineRedactionPlanner, PassthroughRedactionApplier
from .storage import FileSystemStorageAdapter
from .tesseract_ocr import TesseractOCRAdapter

__all__ = [
    "SequentialBatesPlanner",
    "IngestDiscoveryAdapter",
    "HashDeduper",
    "FileSystemStorageAdapter",
    "ZipPackager",
    "JSONLineRedactionPlanner",
    "PassthroughRedactionApplier",
    "Kanon2Adapter",
    "HNSWAdapter",
    "PDFStamperAdapter",
    "TesseractOCRAdapter",
]
