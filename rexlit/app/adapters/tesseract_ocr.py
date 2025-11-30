"""Tesseract OCR adapter with optional preflight page analysis and layout sidecars."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fitz  # type: ignore[import]
import pytesseract
from PIL import Image  # type: ignore[import]
from pydantic import BaseModel

from rexlit.app.ports.ocr import OCRPort, OCRResult

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class _SpanInfo:
    """Bounding box and offset info for a text span."""

    start: int
    end: int
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)


@dataclass
class _PageLayout:
    """Layout information for a single page."""

    page: int
    width: float
    height: float
    spans: list[_SpanInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "width": self.width,
            "height": self.height,
            "spans": [
                {"start": s.start, "end": s.end, "bbox": list(s.bbox)}
                for s in self.spans
            ],
        }


@dataclass(slots=True)
class _OCRStats:
    """Aggregate OCR results for a document."""

    texts: list[str]
    confidences: list[float]
    layouts: list[_PageLayout]

    def extend(
        self, text: str, confidence: float, layout: _PageLayout | None = None
    ) -> None:
        self.texts.append(text)
        self.confidences.append(confidence)
        if layout is not None:
            self.layouts.append(layout)

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
    """Tesseract-based OCR implementation with preflight optimisation and layout sidecars."""

    def __init__(
        self,
        *,
        lang: str = "eng",
        preflight: bool = True,
        dpi_scale: int = 2,
        min_text_threshold: int = 10,
        layout_dir: Path | None = None,
        generate_layout: bool = True,
    ) -> None:
        self.lang = lang
        self.preflight = preflight
        self.dpi_scale = dpi_scale
        self.min_text_threshold = min_text_threshold
        self.layout_dir = layout_dir
        self.generate_layout = generate_layout

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

            stats = _OCRStats(texts=[], confidences=[], layouts=[])
            ocr_pages = set(candidates)
            current_offset = 0

            for index in range(page_count):
                page = doc.load_page(index)
                rect = page.rect

                if index in ocr_pages:
                    text, confidence, spans = self._ocr_page_with_layout(page, lang)
                else:
                    text = page.get_text()
                    confidence = 1.0
                    # Extract text blocks for layout from PDF text layer
                    spans = self._extract_pdf_text_layout(page, current_offset)

                # Build page layout
                page_layout = _PageLayout(
                    page=index + 1,  # 1-indexed
                    width=rect.width,
                    height=rect.height,
                    spans=spans,
                )

                stats.extend(text, confidence, page_layout)
                # Account for text + double newline separator
                current_offset += len(text) + 2

            # Save layout sidecar if configured
            if self.generate_layout and self.layout_dir:
                self._save_layout_sidecar(pdf_path, stats.layouts)

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
            text, confidence, spans = self._ocr_image_with_layout(image, lang)

            # Generate layout sidecar for image
            if self.generate_layout and self.layout_dir:
                page_layout = _PageLayout(
                    page=1,
                    width=float(image.width),
                    height=float(image.height),
                    spans=spans,
                )
                self._save_layout_sidecar(image_path, [page_layout])

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
        text, confidence, _ = self._ocr_page_with_layout(page, lang)
        return text, confidence

    def _ocr_page_with_layout(
        self, page: fitz.Page, lang: str  # type: ignore[name-defined]
    ) -> tuple[str, float, list[_SpanInfo]]:
        """OCR a PDF page and extract layout information."""
        matrix = fitz.Matrix(self.dpi_scale, self.dpi_scale)
        pix = page.get_pixmap(matrix=matrix)
        mode = "RGBA" if pix.alpha else "RGB"
        image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        if pix.alpha:
            image = image.convert("RGB")

        text, confidence, ocr_spans = self._ocr_image_with_layout(image, lang)

        # Scale OCR coordinates back to page coordinates
        rect = page.rect
        scale_x = rect.width / pix.width
        scale_y = rect.height / pix.height

        page_spans: list[_SpanInfo] = []
        for span in ocr_spans:
            x0, y0, x1, y1 = span.bbox
            scaled_bbox = (
                x0 * scale_x,
                y0 * scale_y,
                x1 * scale_x,
                y1 * scale_y,
            )
            page_spans.append(_SpanInfo(start=span.start, end=span.end, bbox=scaled_bbox))

        return text, confidence, page_spans

    def _ocr_image(self, image: Image.Image, lang: str) -> tuple[str, float]:
        text, confidence, _ = self._ocr_image_with_layout(image, lang)
        return text, confidence

    def _ocr_image_with_layout(
        self, image: Image.Image, lang: str
    ) -> tuple[str, float, list[_SpanInfo]]:
        """OCR an image and extract word-level bounding boxes for layout."""
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

        # Build spans from OCR word data
        spans: list[_SpanInfo] = []
        current_offset = 0
        words = data.get("text", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])
        confs = data.get("conf", [])

        for i, word in enumerate(words):
            word_text = str(word).strip()
            if not word_text or confs[i] in {"-1", -1}:
                continue

            # Find this word in the combined text
            word_start = text.find(word_text, current_offset)
            if word_start == -1:
                continue

            word_end = word_start + len(word_text)

            # Build bounding box (x0, y0, x1, y1)
            x0 = float(lefts[i])
            y0 = float(tops[i])
            x1 = x0 + float(widths[i])
            y1 = y0 + float(heights[i])

            spans.append(_SpanInfo(start=word_start, end=word_end, bbox=(x0, y0, x1, y1)))
            current_offset = word_end

        return text, avg_confidence, spans

    def _extract_pdf_text_layout(
        self, page: fitz.Page, offset: int  # type: ignore[name-defined]
    ) -> list[_SpanInfo]:
        """Extract text span layout from PDF text layer using PyMuPDF."""
        spans: list[_SpanInfo] = []
        text = page.get_text()
        current_offset = 0

        # Use PyMuPDF's text extraction with position info
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])

        for block in blocks:
            if block.get("type") != 0:  # Skip non-text blocks
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text.strip():
                        continue

                    # Find this span in the page text
                    span_start = text.find(span_text, current_offset)
                    if span_start == -1:
                        continue

                    span_end = span_start + len(span_text)
                    bbox = span.get("bbox", (0, 0, 0, 0))

                    spans.append(
                        _SpanInfo(
                            start=offset + span_start,
                            end=offset + span_end,
                            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                        )
                    )
                    current_offset = span_end

        return spans

    def _save_layout_sidecar(self, pdf_path: Path, layouts: list[_PageLayout]) -> None:
        """Save layout sidecar JSON file for highlight box mapping."""
        if not self.layout_dir:
            return

        # Compute document hash for sidecar filename
        doc_hash = self._compute_file_hash(pdf_path)
        sidecar_path = self.layout_dir / f"{doc_hash}.layout.json"

        self.layout_dir.mkdir(parents=True, exist_ok=True)

        layout_data = {
            "source": str(pdf_path),
            "pages": [layout.to_dict() for layout in layouts],
        }

        sidecar_path.write_text(
            json.dumps(layout_data, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _compute_file_hash(path: Path) -> str:
        """Compute SHA-256 hash of file contents."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

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
