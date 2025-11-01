"""Integration tests for the Tesseract OCR adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

pytesseract = pytest.importorskip("pytesseract", reason="pytesseract not available")

try:
    pytesseract.get_tesseract_version()
except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - environment check
    pytest.skip("Tesseract binary not installed", allow_module_level=True)  # type: ignore[arg-type]

import fitz  # type: ignore[import]  # noqa: E402
from PIL import Image, ImageDraw  # type: ignore[import]  # noqa: E402

from rexlit.app.adapters.tesseract_ocr import TesseractOCRAdapter  # noqa: E402
from rexlit.app.ports.ocr import OCRResult  # noqa: E402


@pytest.fixture
def ocr_adapter() -> TesseractOCRAdapter:
    """Provide adapter with preflight enabled."""

    return TesseractOCRAdapter(lang="eng", preflight=True)


@pytest.fixture
def pdf_with_text(tmp_path: Path) -> Path:
    """Create a single-page PDF with a native text layer."""

    pdf_path = tmp_path / "text_layer.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Native text is extracted without OCR.")
    document.save(pdf_path)
    document.close()
    return pdf_path


@pytest.fixture
def pdf_image_only(tmp_path: Path) -> Path:
    """Create a single-page PDF containing only an embedded image."""

    image = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((25, 80), "OCR ME", fill="black")

    image_path = tmp_path / "scan.png"
    image.save(image_path)

    pdf_path = tmp_path / "scan.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_image(page.rect, filename=image_path)
    document.save(pdf_path)
    document.close()
    return pdf_path


def test_adapter_implements_port(ocr_adapter: TesseractOCRAdapter) -> None:
    """Adapter exposes expected port methods."""

    assert hasattr(ocr_adapter, "process_document")
    assert callable(ocr_adapter.process_document)
    assert hasattr(ocr_adapter, "is_online")
    assert callable(ocr_adapter.is_online)


def test_offline_flag(ocr_adapter: TesseractOCRAdapter) -> None:
    """Adapter is offline-first."""

    assert ocr_adapter.is_online() is False


def test_preflight_skips_native_text(
    ocr_adapter: TesseractOCRAdapter,
    pdf_with_text: Path,
) -> None:
    """Preflight should detect native text and skip OCR."""

    result = ocr_adapter.process_document(pdf_with_text)

    assert isinstance(result, OCRResult)
    assert result.page_count == 1
    assert "native text" in result.text.lower()
    assert result.confidence == 1.0


def test_image_only_page_requires_ocr(
    ocr_adapter: TesseractOCRAdapter,
    pdf_image_only: Path,
) -> None:
    """Image-only PDFs should trigger OCR processing."""

    result = ocr_adapter.process_document(pdf_image_only)

    assert isinstance(result, OCRResult)
    assert result.page_count == 1
    assert len(result.text.strip()) > 0
    assert 0.0 <= result.confidence <= 1.0


def test_no_preflight_forces_ocr(
    pdf_with_text: Path,
) -> None:
    """Disabling preflight should force OCR even on native text."""

    adapter = TesseractOCRAdapter(preflight=False)
    result = adapter.process_document(pdf_with_text)

    assert isinstance(result, OCRResult)
    assert result.page_count == 1
    assert result.language == "eng"


def test_unsupported_extension(tmp_path: Path, ocr_adapter: TesseractOCRAdapter) -> None:
    """Unsupported file types raise an error."""

    text_file = tmp_path / "note.txt"
    text_file.write_text("plain text")

    with pytest.raises(ValueError, match="Unsupported file type"):
        ocr_adapter.process_document(text_file)
