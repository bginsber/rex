"""Tesseract OCR adapter with optional preflight page analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # type: ignore[import]
import pytesseract
from PIL import Image  # type: ignore[import]
from pydantic import BaseModel

from rexlit.app.ports.ocr import OCRPort, OCRResult

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class _OCRStats:
    """Aggregate OCR results for a document."""

    texts: list[str]
    confidences: list[float]

    def extend(self, text: str, confidence: float) -> None:
        self.texts.append(text)
        self.confidences.append(confidence)

    def combined_text(self) -> str:
        return "\n\n".join(self.texts)

    def average_confidence(self) -> float:
        return (
            sum(self.confidences) / len(self.confidences)
            if self.confidences
            else 0.0
        )


class PageAnalysis(BaseModel):
    """Preflight analysis result for a single PDF page."""

    page: int
    has_text_layer: bool
    text_length: int
    dpi_estimate: int
    needs_ocr: bool


class TesseractOCRAdapter(OCRPort):
    """Tesseract-based OCR implementation with preflight optimisation."""

    def __init__(
        self,
        *,
        lang: str = "eng",
        preflight: bool = True,
        dpi_scale: int = 2,
        min_text_threshold: int = 50,
    ) -> None:
        self.lang = lang
        self.preflight = preflight
        self.dpi_scale = dpi_scale
        self.min_text_threshold = min_text_threshold

        version = self._get_tesseract_version()
        major = self._extract_major_version(version)
        if major is not None and major < 4:
            raise RuntimeError(
                f"Tesseract 4.0+ required (found {version}). "
                "Upgrade: brew upgrade tesseract",
            )

    def process_document(
        self,
        path: Path,
        *,
        language: str = "eng",
    ) -> OCRResult:
        resolved = path.expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"OCR input not found: {resolved}")

        lang = language or self.lang
        suffix = resolved.suffix.lower()

        if suffix == ".pdf":
            return self._process_pdf(resolved, lang)

        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            return self._process_image(resolved, lang)

        raise ValueError(f"Unsupported file type for OCR: {suffix}")

    def is_online(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_pdf(self, pdf_path: Path, lang: str) -> OCRResult:
        doc = fitz.open(pdf_path)  # type: ignore[arg-type]
        try:
            page_count = doc.page_count
            candidates: Iterable[int] = range(page_count)

            if self.preflight:
                candidates = self._pages_requiring_ocr(doc)

            stats = _OCRStats(texts=[], confidences=[])
            ocr_pages = set(candidates)

            for index in range(page_count):
                page = doc.load_page(index)
                if index in ocr_pages:
                    text, confidence = self._ocr_page(page, lang)
                else:
                    text = page.get_text()
                    confidence = 1.0

                stats.extend(text, confidence)

            return OCRResult(
                path=str(pdf_path),
                text=stats.combined_text(),
                confidence=stats.average_confidence(),
                language=lang,
                page_count=page_count,
            )
        finally:
            doc.close()

    def _process_image(self, image_path: Path, lang: str) -> OCRResult:
        with Image.open(image_path) as image:
            text, confidence = self._ocr_image(image, lang)

        return OCRResult(
            path=str(image_path),
            text=text,
            confidence=confidence,
            language=lang,
            page_count=1,
        )

    def _pages_requiring_ocr(self, doc: fitz.Document) -> set[int]:  # type: ignore[name-defined]
        needing_ocr: set[int] = set()
        for page_index in range(doc.page_count):
            analysis = self._analyse_page(doc, page_index)
            if analysis.needs_ocr:
                needing_ocr.add(page_index)
        return needing_ocr

    def _analyse_page(self, doc: fitz.Document, index: int) -> PageAnalysis:  # type: ignore[name-defined]
        page = doc.load_page(index)
        text = page.get_text()
        text_length = len(text.strip())
        has_text_layer = text_length > self.min_text_threshold

        rect = page.rect
        width_inches = rect.width / 72 if rect.width else 0.0
        dpi_estimate = int(rect.width / width_inches) if width_inches else 300

        return PageAnalysis(
            page=index,
            has_text_layer=has_text_layer,
            text_length=text_length,
            dpi_estimate=dpi_estimate,
            needs_ocr=not has_text_layer,
        )

    def _ocr_page(self, page: fitz.Page, lang: str) -> tuple[str, float]:  # type: ignore[name-defined]
        matrix = fitz.Matrix(self.dpi_scale, self.dpi_scale)
        pix = page.get_pixmap(matrix=matrix)
        mode = "RGBA" if pix.alpha else "RGB"
        image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        if pix.alpha:
            image = image.convert("RGB")

        return self._ocr_image(image, lang)

    def _ocr_image(self, image: Image.Image, lang: str) -> tuple[str, float]:
        text = pytesseract.image_to_string(image, lang=lang)
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )

        confidences = [
            int(conf)
            for conf in data.get("conf", [])
            if conf not in {"-1", -1}
        ]
        avg_confidence = (
            sum(confidences) / len(confidences) / 100 if confidences else 0.0
        )

        return text, avg_confidence

    @staticmethod
    def _extract_major_version(version: str) -> int | None:
        parts = str(version).split(".", 1)
        try:
            return int(parts[0])
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _get_tesseract_version() -> str:
        try:
            return str(pytesseract.get_tesseract_version())
        except pytesseract.TesseractNotFoundError as exc:  # type: ignore[attr-defined]
            raise RuntimeError(
                "Tesseract not installed. Install with:\n"
                "  macOS: brew install tesseract\n"
                "  Ubuntu: apt-get install tesseract-ocr",
            ) from exc
