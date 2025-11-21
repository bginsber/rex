"""Concrete adapters wiring application ports to built-in implementations."""

from __future__ import annotations

from .bates import SequentialBatesPlanner
from .dedupe import HashDeduper
from .discovery import IngestDiscoveryAdapter
from .hnsw import HNSWAdapter
from .kanon2 import Kanon2Adapter
from .pack import ZipPackager
from .pdf_stamper import PDFStamperAdapter
from .groq_privilege import GroqPrivilegeAdapter
from .local_llm_concept_adapter import LocalLLMConceptAdapter
from .pattern_concept_adapter import PatternConceptAdapter
from .privilege_patterns import PrivilegePatternsAdapter
from .privilege_safeguard import PrivilegeSafeguardAdapter
from .redaction import JSONLineRedactionPlanner, PassthroughRedactionApplier
from .storage import FileSystemStorageAdapter
from .null_concept_adapter import NullConceptAdapter
try:
    from .tesseract_ocr import TesseractOCRAdapter
except ModuleNotFoundError as _tesseract_err:  # pragma: no cover - optional dependency
    class TesseractOCRAdapter:  # type: ignore[no-redef]
        """Placeholder adapter that surfaces missing optional dependency."""

        def __init__(self, *args, **kwargs) -> None:
            raise ModuleNotFoundError(
                "pytesseract is required to use TesseractOCRAdapter"
            ) from _tesseract_err

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
    "PrivilegeSafeguardAdapter",
    "PrivilegePatternsAdapter",
    "GroqPrivilegeAdapter",
    "NullConceptAdapter",
    "LocalLLMConceptAdapter",
    "PatternConceptAdapter",
]
