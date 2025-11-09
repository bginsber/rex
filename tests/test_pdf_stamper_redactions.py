"""Tests for PDFStamperAdapter redaction application."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import]

from rexlit.app.adapters.pdf_stamper import PDFStamperAdapter


def _create_pdf(path: Path, pages: list[list[str]]) -> None:
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        y = 100
        for line in lines:
            page.insert_text((100, y), line, fontsize=12)
            y += 20
    doc.save(str(path))
    doc.close()


def _extract_text(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def test_apply_single_redaction(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    output_path = tmp_path / "redacted.pdf"
    _create_pdf(pdf_path, [["SSN: 123-45-6789", "Email: test@example.com"]])

    adapter = PDFStamperAdapter()

    count = adapter.apply_redactions(
        pdf_path,
        output_path,
        [
            {
                "entity_type": "SSN",
                "text": "123-45-6789",
                "page": 0,
            }
        ],
    )

    assert count == 1
    assert output_path.exists()
    text = _extract_text(output_path)
    assert "123-45-6789" not in text


def test_apply_redactions_multiple_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi.pdf"
    output_path = tmp_path / "multi_redacted.pdf"
    _create_pdf(
        pdf_path,
        [
            ["Page1 SSN: 000-11-2222"],
            ["Page2 Email: example@corp.com"],
        ],
    )

    adapter = PDFStamperAdapter()
    count = adapter.apply_redactions(
        pdf_path,
        output_path,
        [
            {"entity_type": "SSN", "text": "000-11-2222", "page": 0},
            {"entity_type": "EMAIL", "text": "example@corp.com", "page": 1},
        ],
    )

    assert count == 2
    text = _extract_text(output_path)
    assert "000-11-2222" not in text
    assert "example@corp.com" not in text


def test_redaction_without_page_scans_document(tmp_path: Path) -> None:
    pdf_path = tmp_path / "nopage.pdf"
    output_path = tmp_path / "nopage_redacted.pdf"
    _create_pdf(pdf_path, [["Contact: person@example.com"]])

    adapter = PDFStamperAdapter()
    count = adapter.apply_redactions(
        pdf_path,
        output_path,
        [
            {
                "entity_type": "EMAIL",
                "text": "person@example.com",
                # page intentionally omitted
            }
        ],
    )

    assert count == 1
    assert "person@example.com" not in _extract_text(output_path)


def test_invalid_page_is_skipped(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invalid.pdf"
    output_path = tmp_path / "invalid_redacted.pdf"
    _create_pdf(pdf_path, [["SSN: 333-44-5555"]])

    adapter = PDFStamperAdapter()
    count = adapter.apply_redactions(
        pdf_path,
        output_path,
        [
            {"entity_type": "SSN", "text": "333-44-5555", "page": 999},
        ],
    )

    # Redaction should not apply due to invalid page, but file still written.
    assert count == 0
    assert output_path.exists()
    assert "333-44-5555" in _extract_text(output_path)
