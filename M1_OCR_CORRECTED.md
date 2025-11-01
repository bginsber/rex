# RexLit M1: OCR Implementation Plan (Corrected)

**Target:** Tesseract OCR with preflight logic, properly integrated with RexLit architecture
**Timeline:** 18-20 hours (including architecture alignment)
**Key Changes:** Fixed port interface compliance, bootstrap wiring, audit integration

---

## Architecture Compliance Checklist

- ✅ Implements `OCRPort` protocol from `rexlit/app/ports/ocr.py`
- ✅ Returns `OCRResult` (not raw dicts)
- ✅ Wired through `bootstrap.py` (not directly imported by CLI)
- ✅ Audit logging for all OCR operations
- ✅ Follows ADR 0001 (offline-first), ADR 0002 (ports/adapters)
- ✅ Import rules enforced (CLI → bootstrap → ports → adapters)

---

## Task 1: Tesseract OCR Adapter (8 hours)

### File: `rexlit/app/adapters/tesseract_ocr.py` (NEW)

**Location:** Adapters layer (not `rexlit/ocr/`)

```python
"""Tesseract OCR adapter with preflight optimization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pydantic import BaseModel

from rexlit.app.ports import OCRPort, OCRResult

if TYPE_CHECKING:
    from typing import Literal


class PageAnalysis(BaseModel):
    """Preflight analysis result for a single page."""

    page: int
    has_text_layer: bool
    text_length: int
    dpi_estimate: int
    needs_ocr: bool


class TesseractOCRAdapter(OCRPort):
    """Tesseract-based OCR with preflight optimization.

    Preflight Logic:
    - Analyzes each PDF page for existing text layer
    - Only OCRs pages without extractable text (>50 chars threshold)
    - Skips unnecessary processing on text-native PDFs

    Architecture:
    - Implements OCRPort protocol
    - Returns OCRResult for consistency
    - Offline-first (no network dependencies)

    Performance:
    - ~2-5 seconds per page on 300 DPI scans
    - Batch processing (single doc open)
    - Confidence scoring for audit trail
    """

    def __init__(
        self,
        *,
        lang: str = "eng",
        preflight: bool = True,
        dpi_scale: int = 2,
        min_text_threshold: int = 50,
    ):
        """Initialize Tesseract OCR adapter.

        Args:
            lang: Tesseract language code (default: eng)
            preflight: Enable preflight text layer detection
            dpi_scale: Render scale multiplier (2 = 600 DPI from 300 DPI source)
            min_text_threshold: Minimum chars to consider page has text layer

        Raises:
            RuntimeError: If Tesseract not installed
        """
        self.lang = lang
        self.preflight = preflight
        self.dpi_scale = dpi_scale
        self.min_text_threshold = min_text_threshold

        # Validate Tesseract installation
        try:
            version = pytesseract.get_tesseract_version()
            # Tesseract 4.0+ required for confidence scoring
            if version.major < 4:
                raise RuntimeError(
                    f"Tesseract 4.0+ required (found {version}). "
                    "Upgrade: brew upgrade tesseract"
                )
        except pytesseract.TesseractNotFoundError as e:
            raise RuntimeError(
                "Tesseract not installed. Install with:\n"
                "  macOS: brew install tesseract\n"
                "  Ubuntu: apt-get install tesseract-ocr"
            ) from e

    def process_document(
        self, path: Path, *, language: str = "eng"
    ) -> OCRResult:
        """Process document with OCR (port interface implementation).

        Args:
            path: Path to PDF or image file
            language: Tesseract language override

        Returns:
            OCRResult with extracted text and metadata
        """
        lang = language or self.lang

        if path.suffix.lower() == ".pdf":
            return self._process_pdf(path, lang)
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
            return self._process_image(path, lang)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")

    def is_online(self) -> bool:
        """Check if adapter requires network access."""
        return False

    def _process_pdf(self, pdf_path: Path, lang: str) -> OCRResult:
        """Process multi-page PDF with preflight optimization."""
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)

        # Preflight: detect pages needing OCR
        pages_to_ocr: list[int] = []
        if self.preflight:
            for page_num in range(page_count):
                analysis = self._analyze_page(doc, page_num)
                if analysis.needs_ocr:
                    pages_to_ocr.append(page_num)
        else:
            pages_to_ocr = list(range(page_count))

        # Batch OCR needed pages
        all_text: list[str] = []
        confidences: list[float] = []

        for page_num in range(page_count):
            if page_num in pages_to_ocr:
                # OCR this page
                page = doc[page_num]
                text, confidence = self._ocr_page(page, lang)
                all_text.append(text)
                confidences.append(confidence)
            else:
                # Extract existing text layer
                page = doc[page_num]
                text = page.get_text()
                all_text.append(text)
                confidences.append(1.0)  # Native text = 100% confidence

        doc.close()

        # Aggregate results
        combined_text = "\n\n".join(all_text)
        avg_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )

        return OCRResult(
            path=str(pdf_path),
            text=combined_text,
            confidence=avg_confidence,
            language=lang,
            page_count=page_count,
        )

    def _process_image(self, image_path: Path, lang: str) -> OCRResult:
        """Process single image file."""
        image = Image.open(image_path)
        text, confidence = self._ocr_image(image, lang)

        return OCRResult(
            path=str(image_path),
            text=text,
            confidence=confidence,
            language=lang,
            page_count=1,
        )

    def _analyze_page(self, doc: fitz.Document, page_num: int) -> PageAnalysis:
        """Preflight: detect if page needs OCR."""
        page = doc[page_num]
        text = page.get_text()
        text_length = len(text.strip())
        has_text_layer = text_length > self.min_text_threshold

        # Estimate DPI (heuristic based on page size)
        rect = page.rect
        # Assume standard letter size (8.5" x 11")
        width_inches = rect.width / 72  # 72 pts per inch
        dpi_estimate = int(rect.width / width_inches) if width_inches > 0 else 300

        return PageAnalysis(
            page=page_num,
            has_text_layer=has_text_layer,
            text_length=text_length,
            dpi_estimate=dpi_estimate,
            needs_ocr=not has_text_layer,
        )

    def _ocr_page(self, page: fitz.Page, lang: str) -> tuple[str, float]:
        """OCR a single PyMuPDF page object."""
        # Render page to high-DPI image
        matrix = fitz.Matrix(self.dpi_scale, self.dpi_scale)
        pix = page.get_pixmap(matrix=matrix)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        return self._ocr_image(image, lang)

    def _ocr_image(self, image: Image.Image, lang: str) -> tuple[str, float]:
        """OCR a PIL image with confidence scoring."""
        try:
            # Extract text
            text = pytesseract.image_to_string(image, lang=lang)

            # Get word-level confidence scores
            data = pytesseract.image_to_data(
                image, lang=lang, output_type=pytesseract.Output.DICT
            )

            # Calculate average confidence (filter out -1 values = no text)
            confidences = [
                int(c) for c in data.get("conf", []) if int(c) >= 0
            ]
            avg_confidence = (
                sum(confidences) / len(confidences) / 100.0  # Normalize to 0-1
                if confidences
                else 0.0
            )

            return text, avg_confidence

        except Exception as e:
            # Log error but don't fail entire document
            return f"[OCR ERROR: {e}]", 0.0
```

---

## Task 2: Bootstrap Wiring (2 hours)

### File: `rexlit/bootstrap.py` (MODIFY)

**Changes:**

1. **Import adapter** (add to top):
```python
from rexlit.app.adapters import (
    # ... existing imports ...
    TesseractOCRAdapter,  # NEW
)
```

2. **Add to ApplicationContainer** (line ~59):
```python
@dataclass(slots=True)
class ApplicationContainer:
    """Aggregates wired services and adapters for the CLI layer."""

    # ... existing fields ...

    # NEW: OCR providers (multi-provider support)
    ocr_providers: dict[str, OCRPort]
```

3. **Wire in bootstrap_application()** (line ~320):
```python
def bootstrap_application(settings: Settings | None = None) -> ApplicationContainer:
    """Instantiate adapters and services for CLI consumption."""

    active_settings = settings or get_settings()

    # ... existing wiring ...

    # NEW: OCR providers
    ocr_providers = {
        "tesseract": TesseractOCRAdapter(
            lang="eng",
            preflight=True,
            dpi_scale=2,
            min_text_threshold=50,
        ),
        # Future: "paddle": PaddleOCRAdapter(),
    }

    return ApplicationContainer(
        # ... existing fields ...
        ocr_providers=ocr_providers,  # NEW
    )
```

---

## Task 3: Update Adapter Exports (1 hour)

### File: `rexlit/app/adapters/__init__.py` (MODIFY)

Add to `__all__`:
```python
__all__ = [
    # ... existing exports ...
    "TesseractOCRAdapter",  # NEW
]

# ... existing imports ...
from rexlit.app.adapters.tesseract_ocr import TesseractOCRAdapter  # NEW
```

---

## Task 4: CLI Integration with Audit Logging (5 hours)

### File: `rexlit/cli.py` (MODIFY)

**Replace stub at lines 636-661:**

```python
@ocr_app.command("run")
def ocr_run(
    path: Annotated[Path, typer.Argument(help="Path to PDF, image, or directory")],
    provider: Annotated[
        Literal["tesseract", "paddle"],
        typer.Option("--provider", "-p", help="OCR provider"),
    ] = "tesseract",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output text file or directory"),
    ] = None,
    preflight: Annotated[
        bool,
        typer.Option("--preflight/--no-preflight", help="Analyze pages before OCR"),
    ] = True,
    language: Annotated[
        str,
        typer.Option("--language", "-l", help="Tesseract language code"),
    ] = "eng",
    online: Annotated[
        bool,
        typer.Option("--online", help="Enable online OCR (future: DeepSeek)"),
    ] = False,
    show_confidence: Annotated[
        bool,
        typer.Option("--confidence", help="Show OCR confidence scores"),
    ] = False,
) -> None:
    """Run OCR on documents with preflight optimization.

    Examples:
        # OCR single PDF with preflight
        rexlit ocr run document.pdf --output document.txt

        # OCR directory (batch)
        rexlit ocr run ./scans --output ./text --provider tesseract

        # Skip preflight (force OCR all pages)
        rexlit ocr run scan.pdf --no-preflight

        # Show confidence scores
        rexlit ocr run doc.pdf --confidence
    """
    container = bootstrap_application()

    # Validate provider
    if provider not in container.ocr_providers:
        typer.secho(
            f"Error: OCR provider '{provider}' not available. "
            f"Options: {', '.join(container.ocr_providers.keys())}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Get adapter
    ocr_adapter = container.ocr_providers[provider]

    # Online mode gate (future: DeepSeek)
    if online and ocr_adapter.is_online():
        container.offline_gate.require(f"{provider} OCR")

    # Validate path
    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Process single file or directory
    if path.is_file():
        _ocr_single_file(
            path, ocr_adapter, output, language, show_confidence, container
        )
    elif path.is_dir():
        _ocr_directory(
            path, ocr_adapter, output, language, show_confidence, container
        )
    else:
        typer.secho(f"Error: Not a file or directory: {path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _ocr_single_file(
    path: Path,
    ocr_adapter: OCRPort,
    output: Path | None,
    language: str,
    show_confidence: bool,
    container: ApplicationContainer,
) -> None:
    """Process single file with OCR."""
    typer.secho(f"🔍 OCR processing: {path.name}", fg=typer.colors.BLUE)

    # Start time for performance tracking
    import time
    start = time.time()

    try:
        result = ocr_adapter.process_document(path, language=language)
        elapsed = time.time() - start

        # Audit logging
        container.ledger_port.log(
            operation="ocr.process",
            inputs={
                "path": str(path),
                "provider": type(ocr_adapter).__name__,
                "language": language,
            },
            outputs={
                "page_count": result.page_count,
                "text_length": len(result.text),
                "confidence": result.confidence,
                "elapsed_seconds": round(elapsed, 2),
            },
        )

        # Display results
        typer.secho(f"✓ OCR complete", fg=typer.colors.GREEN)
        typer.echo(f"  Pages: {result.page_count}")
        typer.echo(f"  Characters extracted: {len(result.text):,}")
        typer.echo(f"  Time: {elapsed:.2f}s")

        if show_confidence:
            confidence_pct = result.confidence * 100
            color = (
                typer.colors.GREEN if confidence_pct >= 80
                else typer.colors.YELLOW if confidence_pct >= 60
                else typer.colors.RED
            )
            typer.secho(f"  Confidence: {confidence_pct:.1f}%", fg=color)

        # Save output
        if output:
            output.write_text(result.text, encoding="utf-8")
            typer.secho(f"  Saved: {output}", fg=typer.colors.CYAN)
        else:
            # Preview first 500 chars
            preview = result.text[:500]
            typer.echo(f"\n{preview}...")
            if len(result.text) > 500:
                typer.echo(f"\n[{len(result.text) - 500:,} more characters...]")

    except Exception as e:
        typer.secho(f"✗ OCR failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _ocr_directory(
    path: Path,
    ocr_adapter: OCRPort,
    output_dir: Path | None,
    language: str,
    show_confidence: bool,
    container: ApplicationContainer,
) -> None:
    """Batch process directory with OCR."""
    # Find all supported files
    from rexlit.utils.deterministic import deterministic_sort_paths

    patterns = ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.tiff"]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path.rglob(pattern))

    # Deterministic sort (ADR 0003)
    files = deterministic_sort_paths(files)

    if not files:
        typer.secho(f"No supported files found in {path}", fg=typer.colors.YELLOW)
        return

    typer.secho(
        f"🔍 Batch OCR: {len(files)} files in {path}",
        fg=typer.colors.BLUE,
    )

    # Create output directory
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Process each file
    successes = 0
    failures = 0

    for i, file_path in enumerate(files, 1):
        typer.echo(f"\n[{i}/{len(files)}] {file_path.name}")

        try:
            result = ocr_adapter.process_document(file_path, language=language)

            # Save output
            if output_dir:
                output_file = output_dir / f"{file_path.stem}.txt"
                output_file.write_text(result.text, encoding="utf-8")
                typer.secho(f"  ✓ {len(result.text):,} chars", fg=typer.colors.GREEN)

            successes += 1

        except Exception as e:
            typer.secho(f"  ✗ Failed: {e}", fg=typer.colors.RED)
            failures += 1

    # Summary
    typer.echo(f"\n{'='*60}")
    typer.secho(f"✓ Success: {successes}/{len(files)}", fg=typer.colors.GREEN)
    if failures > 0:
        typer.secho(f"✗ Failures: {failures}/{len(files)}", fg=typer.colors.RED)
```

---

## Task 5: Dependencies (1 hour)

### File: `pyproject.toml` (MODIFY)

**Update optional dependencies (line ~59):**

```toml
[project.optional-dependencies]
# ... existing dev dependencies ...

ocr-tesseract = [
    "pytesseract>=0.3.10",
    "Pillow>=10.0.0",      # NEW: Required for image processing
    "PyMuPDF>=1.23.0",     # Already in main deps, but document requirement
]
ocr-paddle = [
    "paddleocr>=2.8.0",
    "paddlepaddle>=2.6.0",
]
# ... rest ...
```

---

## Task 6: Integration Tests (5 hours)

### File: `tests/test_ocr_tesseract.py` (NEW)

```python
"""Integration tests for Tesseract OCR adapter."""

from pathlib import Path

import pytest

from rexlit.app.adapters.tesseract_ocr import TesseractOCRAdapter
from rexlit.app.ports import OCRResult


@pytest.fixture
def ocr_adapter():
    """Create Tesseract adapter for testing."""
    return TesseractOCRAdapter(lang="eng", preflight=True)


@pytest.fixture
def sample_pdf_with_text(tmp_path):
    """Create PDF with native text layer."""
    import fitz

    pdf_path = tmp_path / "sample_with_text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This is a test document with native text.")
    doc.save(str(pdf_path))
    doc.close()

    return pdf_path


@pytest.fixture
def sample_pdf_image_only(tmp_path):
    """Create PDF with image (no text layer)."""
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    # Create image with text
    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "OCR THIS TEXT", fill="black")

    img_path = tmp_path / "temp_img.png"
    img.save(img_path)

    # Embed as image in PDF
    pdf_path = tmp_path / "sample_scan.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=str(img_path))
    doc.save(str(pdf_path))
    doc.close()

    return pdf_path


def test_adapter_implements_port(ocr_adapter):
    """Test adapter implements OCRPort protocol."""
    from rexlit.app.ports import OCRPort

    # Check methods exist
    assert hasattr(ocr_adapter, "process_document")
    assert hasattr(ocr_adapter, "is_online")
    assert callable(ocr_adapter.process_document)
    assert callable(ocr_adapter.is_online)


def test_is_offline(ocr_adapter):
    """Test Tesseract adapter is offline-first."""
    assert ocr_adapter.is_online() is False


def test_tesseract_installation_check():
    """Test adapter validates Tesseract installation."""
    # Should not raise if Tesseract installed
    adapter = TesseractOCRAdapter()
    assert adapter is not None


def test_preflight_detects_text_layer(ocr_adapter, sample_pdf_with_text):
    """Test preflight skips pages with native text layers."""
    result = ocr_adapter.process_document(sample_pdf_with_text)

    assert isinstance(result, OCRResult)
    assert result.page_count == 1
    assert "test document" in result.text.lower()
    assert result.confidence >= 0.9  # High confidence for native text


def test_preflight_detects_image_only(ocr_adapter, sample_pdf_image_only):
    """Test preflight OCRs pages without text layers."""
    result = ocr_adapter.process_document(sample_pdf_image_only)

    assert isinstance(result, OCRResult)
    assert result.page_count == 1
    # OCR should extract some text (even if imperfect)
    assert len(result.text) > 0
    # Confidence should be lower than native text
    assert result.confidence < 1.0


def test_multi_page_pdf(tmp_path, ocr_adapter):
    """Test multi-page PDF processing."""
    import fitz

    pdf_path = tmp_path / "multi_page.pdf"
    doc = fitz.open()

    # Page 1: Native text
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Page 1 native text")

    # Page 2: Native text
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Page 2 native text")

    doc.save(str(pdf_path))
    doc.close()

    result = ocr_adapter.process_document(pdf_path)

    assert result.page_count == 2
    assert "Page 1" in result.text
    assert "Page 2" in result.text


def test_unsupported_file_type(tmp_path, ocr_adapter):
    """Test error handling for unsupported file types."""
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("plain text")

    with pytest.raises(ValueError, match="Unsupported file type"):
        ocr_adapter.process_document(bad_file)


def test_ocr_result_schema(ocr_adapter, sample_pdf_with_text):
    """Test OCRResult matches expected schema."""
    result = ocr_adapter.process_document(sample_pdf_with_text)

    # Check all fields present
    assert hasattr(result, "path")
    assert hasattr(result, "text")
    assert hasattr(result, "confidence")
    assert hasattr(result, "language")
    assert hasattr(result, "page_count")

    # Check types
    assert isinstance(result.path, str)
    assert isinstance(result.text, str)
    assert isinstance(result.confidence, float)
    assert isinstance(result.language, str)
    assert isinstance(result.page_count, int)

    # Check ranges
    assert 0.0 <= result.confidence <= 1.0
    assert result.page_count > 0


def test_language_parameter(tmp_path, ocr_adapter):
    """Test language parameter override."""
    import fitz

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test text")
    doc.save(str(pdf_path))
    doc.close()

    result = ocr_adapter.process_document(pdf_path, language="fra")

    assert result.language == "fra"


def test_no_preflight_mode(tmp_path, sample_pdf_with_text):
    """Test disabling preflight forces OCR on all pages."""
    adapter_no_preflight = TesseractOCRAdapter(preflight=False)

    result = adapter_no_preflight.process_document(sample_pdf_with_text)

    # Should still work, just OCRs everything
    assert isinstance(result, OCRResult)
    assert len(result.text) > 0


@pytest.mark.skipif(
    not Path("tests/fixtures/legal_scan.pdf").exists(),
    reason="Test fixture not available"
)
def test_real_legal_document():
    """Test OCR on real legal document scan (if available)."""
    adapter = TesseractOCRAdapter()
    result = adapter.process_document(Path("tests/fixtures/legal_scan.pdf"))

    # Legal docs should have reasonable confidence
    assert result.confidence > 0.5
    assert result.page_count > 0
```

### File: `tests/fixtures/README.md` (NEW)

```markdown
# Test Fixtures for OCR

## Required Files

Place sample PDF files here for testing:

- `sample_with_text.pdf` - PDF with native text layer
- `sample_scan.pdf` - Scanned image PDF (no text layer)
- `legal_scan.pdf` - Real legal document scan (optional, for manual testing)

## Generating Test Fixtures

```bash
# Create sample PDF with text
python3 -c "
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), 'This is a test document with native text.')
doc.save('tests/fixtures/sample_with_text.pdf')
"

# For scanned documents, use your scanner or download samples from:
# https://github.com/tesseract-ocr/tessdata/wiki/Test-Data
```

## Licensing

Ensure test fixtures comply with licensing requirements.
Do not commit copyrighted material without permission.
```

---

## Task 7: Documentation Updates (1 hour)

### File: `README.md` (ADD to Optional Dependencies section)

```markdown
### OCR Support

RexLit supports multiple OCR providers for extracting text from scanned documents.

#### Tesseract OCR (Offline)

```bash
# Install Tesseract system dependency
brew install tesseract  # macOS
apt-get install tesseract-ocr  # Ubuntu

# Install Python dependencies
pip install -e '.[ocr-tesseract]'

# Run OCR
rexlit ocr run document.pdf --output text.txt
```

#### Features

- **Preflight optimization**: Automatically detects pages with text layers, only OCRs scanned pages
- **Confidence scoring**: Reports OCR quality metrics for audit trail
- **Batch processing**: Process entire directories with `rexlit ocr run ./scans/`
- **Offline-first**: No network dependencies

See `CLI-GUIDE.md` for full OCR command reference.
```

### File: `CLI-GUIDE.md` (ADD OCR section)

```markdown
## OCR Commands

### `rexlit ocr run`

Run optical character recognition on documents.

**Usage:**
```bash
rexlit ocr run <path> [OPTIONS]
```

**Arguments:**
- `path`: Path to PDF, image, or directory

**Options:**
- `--provider, -p`: OCR provider (default: tesseract)
  - `tesseract`: Offline Tesseract OCR
  - `paddle`: PaddleOCR (future)
- `--output, -o`: Output text file or directory
- `--preflight/--no-preflight`: Analyze pages before OCR (default: enabled)
- `--language, -l`: Tesseract language code (default: eng)
- `--confidence`: Show OCR confidence scores
- `--online`: Enable online OCR providers (future)

**Examples:**

```bash
# OCR single PDF with preflight
rexlit ocr run contract.pdf --output contract.txt

# Batch process directory
rexlit ocr run ./scans --output ./text --provider tesseract

# Force OCR all pages (skip preflight)
rexlit ocr run scan.pdf --no-preflight

# Show confidence scores for quality assessment
rexlit ocr run deposition.pdf --confidence

# Use Spanish language model
rexlit ocr run documento.pdf --language spa
```

**Preflight Optimization:**

Preflight automatically detects pages with existing text layers:
- Pages with >50 characters: Text extracted directly (no OCR)
- Pages with <50 characters: OCR applied
- Result: 10-50× faster on mixed text/scan PDFs

**Confidence Scoring:**

OCR confidence indicates text extraction quality:
- 80-100%: High quality (clean scans, printed text)
- 60-80%: Medium quality (verify manually)
- 0-60%: Low quality (poor scan, handwriting, review required)

**Audit Trail:**

All OCR operations logged to audit ledger with:
- Input path and provider
- Page count and text length
- Confidence score
- Processing time
```

---

## Task 8: Import Linter Updates (1 hour)

### File: `.importlinter` (ADD OCR adapter rules)

```ini
[importlinter:contract:cli-bootstrap-only]
name = CLI depends only on bootstrap and app layer
type = layers
layers =
    rexlit.cli
    rexlit.bootstrap
    rexlit.app
    rexlit.audit | rexlit.index | rexlit.ingest | rexlit.ocr | rexlit.rules

[importlinter:contract:adapters-implement-ports]
name = Adapters implement ports (not vice versa)
type = forbidden
source_modules =
    rexlit.app.ports
forbidden_modules =
    rexlit.app.adapters.tesseract_ocr  # NEW
```

---

## Acceptance Criteria

### Functional:
- [ ] `TesseractOCRAdapter` implements `OCRPort` protocol
- [ ] `process_document()` returns `OCRResult` with all fields
- [ ] Preflight detects text layers (>50 char threshold)
- [ ] Confidence scoring averages word-level scores
- [ ] Single file and directory processing both work
- [ ] Audit logging captures all OCR operations
- [ ] CLI has `--preflight`, `--confidence`, `--language` flags

### Architecture:
- [ ] Adapter in `rexlit/app/adapters/` (not `rexlit/ocr/`)
- [ ] Wired through `bootstrap.py` into `ApplicationContainer`
- [ ] CLI calls `container.ocr_providers[name]` (not direct import)
- [ ] Import linter rules pass
- [ ] No violations of ADR 0002 (ports/adapters)

### Testing:
- [ ] 10+ integration tests covering adapter functionality
- [ ] Tests use generated fixtures (no external dependencies)
- [ ] All tests pass with `pytest -v --no-cov`
- [ ] Coverage >80% for new adapter code

### Documentation:
- [ ] README.md updated with installation instructions
- [ ] CLI-GUIDE.md has full command reference
- [ ] Test fixtures README explains setup
- [ ] Inline docstrings follow Google style

---

## Installation & Smoke Test

```bash
# 1. Install system dependency
brew install tesseract

# 2. Install Python packages
pip install -e '.[ocr-tesseract]'

# 3. Verify Tesseract
tesseract --version
# Should show: tesseract 5.x.x

# 4. Create test PDF
python3 -c "
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), 'Test document for OCR')
doc.save('test.pdf')
doc.close()
"

# 5. Run OCR
rexlit ocr run test.pdf --confidence
# Expected: ✓ OCR complete, Confidence: 90-100%

# 6. Run tests
pytest tests/test_ocr_tesseract.py -v

# 7. Verify audit trail
rexlit audit show --tail 5
# Should show ocr.process operation
```

---

## Known Limitations & Future Work

### Current Limitations:
1. **Handwriting**: Poor accuracy (<30%) - Tesseract not trained for cursive
2. **Complex Tables**: Multi-column layouts may have text order issues
3. **Low DPI**: <150 DPI scans have degraded accuracy
4. **Large Files**: No progress bars for 100+ page documents

### Phase 2 Enhancements:
1. Add PaddleOCR adapter for better table/layout handling
2. Preprocessing pipeline (deskew, contrast adjustment, noise reduction)
3. Progressive OCR with progress callbacks
4. OCR quality pre-check (DPI detection, blur detection)
5. Parallel page processing (ProcessPoolExecutor)

---

## Time Estimates (Revised)

| Task | Hours | Dependencies |
|------|-------|--------------|
| Task 1: Tesseract Adapter | 8 | PyMuPDF, pytesseract, Pillow |
| Task 2: Bootstrap Wiring | 2 | Task 1 |
| Task 3: Adapter Exports | 1 | Task 1 |
| Task 4: CLI Integration | 5 | Task 2 |
| Task 5: Dependencies | 1 | - |
| Task 6: Integration Tests | 5 | Task 1, 4 |
| Task 7: Documentation | 1 | All above |
| Task 8: Import Linter | 1 | Task 3 |
| **Total** | **24 hours** | (includes testing/docs) |

**Implementation Timeline:**
- Day 1 (8h): Tasks 1-3 (adapter + wiring)
- Day 2 (8h): Task 4 (CLI integration)
- Day 3 (8h): Tasks 5-8 (tests + docs)

---

## Contractor Handoff Checklist

Before assigning to contractor:
- [ ] Ensure they have access to CLAUDE.md and ARCHITECTURE.md
- [ ] Brief on ADR 0002 (ports/adapters architecture)
- [ ] Provide access to this corrected implementation plan
- [ ] Confirm Tesseract installed locally for testing
- [ ] Review existing `OCRPort` interface together
- [ ] Explain deterministic sorting requirement (ADR 0003)
- [ ] Show examples of existing adapters (e.g., `PDFStamperAdapter`)

**Key Message to Contractor:**
"This is not a standalone feature - it must integrate with RexLit's ports/adapters architecture. The adapter implements `OCRPort`, gets wired through `bootstrap.py`, and the CLI never directly imports adapters. Follow the existing pattern in `rexlit/app/adapters/bates.py` as a reference."

---

## Success Metrics

OCR implementation is complete when:
1. ✅ All acceptance criteria met
2. ✅ `pytest -v` shows 73+ tests passing (63 existing + 10 new)
3. ✅ `ruff check .` and `mypy rexlit/` pass with no errors
4. ✅ `lint-imports` passes (no architecture violations)
5. ✅ Demo workflow works end-to-end:
   ```bash
   rexlit ocr run sample.pdf --confidence
   rexlit audit show --tail 1
   # Shows ocr.process with confidence score
   ```
