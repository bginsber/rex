"""Tests for document ingest and discovery."""

from pathlib import Path

import pytest

from rexlit.ingest.discover import (
    classify_doctype,
    discover_document,
    discover_documents,
    extract_custodian,
)
from rexlit.ingest.extract import extract_document, extract_text_file


def test_classify_doctype():
    """Test document type classification."""
    assert classify_doctype("application/pdf", ".pdf") == "pdf"
    assert classify_doctype("text/plain", ".txt") == "text"
    assert classify_doctype("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx") == "docx"
    assert classify_doctype("image/png", ".png") == "image"
    assert classify_doctype(None, ".pdf") == "pdf"
    assert classify_doctype(None, ".unknown") is None


def test_extract_custodian():
    """Test custodian extraction from file path."""
    path1 = Path("/data/custodians/john_doe/file.pdf")
    assert extract_custodian(path1) == "john_doe"

    path2 = Path("/data/users/jane_smith/documents/file.pdf")
    assert extract_custodian(path2) == "jane_smith"

    path3 = Path("/data/random/file.pdf")
    assert extract_custodian(path3) is None


def test_discover_document(sample_text_file: Path):
    """Test discovering a single document."""
    metadata = discover_document(sample_text_file)

    assert metadata.path == str(sample_text_file.resolve())
    assert len(metadata.sha256) == 64
    assert metadata.size > 0
    assert metadata.extension == ".txt"
    assert metadata.doctype == "text"


def test_discover_documents_single_file(sample_text_file: Path):
    """Test discovering a single file."""
    documents = list(discover_documents(sample_text_file))

    assert len(documents) == 1
    assert documents[0].path == str(sample_text_file.resolve())


def test_discover_documents_directory(sample_files: list[Path]):
    """Test discovering documents in a directory."""
    root = sample_files[0].parent
    documents = list(discover_documents(root))

    assert len(documents) == len(sample_files)
    paths = {doc.path for doc in documents}
    expected_paths = {str(f.resolve()) for f in sample_files}
    assert paths == expected_paths


def test_discover_documents_recursive(nested_files: Path):
    """Test recursive document discovery."""
    documents = list(discover_documents(nested_files, recursive=True))

    assert len(documents) == 3

    # Check custodian extraction
    custodians = {doc.custodian for doc in documents}
    assert "john_doe" in custodians
    assert "jane_smith" in custodians


def test_discover_documents_with_filter(temp_dir: Path):
    """Test discovering documents with extension filter."""
    (temp_dir / "doc1.txt").write_text("Text file")
    (temp_dir / "doc2.md").write_text("Markdown file")
    (temp_dir / "doc3.pdf").write_text("PDF file")

    # Include only .txt files
    documents = list(discover_documents(temp_dir, include_extensions={".txt"}))
    assert len(documents) == 1
    assert documents[0].extension == ".txt"

    # Exclude .md files
    documents = list(discover_documents(temp_dir, exclude_extensions={".md"}))
    assert len(documents) == 2
    extensions = {doc.extension for doc in documents}
    assert ".md" not in extensions


def test_discover_documents_not_found():
    """Test discovering documents from non-existent path."""
    with pytest.raises(FileNotFoundError):
        # Iterator needs to be evaluated to raise the error
        list(discover_documents(Path("/nonexistent/path")))


def test_extract_text_file(sample_text_file: Path):
    """Test extracting text from plain text file."""
    extracted = extract_text_file(sample_text_file)

    assert extracted.path == str(sample_text_file.absolute())
    assert extracted.text == "This is a sample text file for testing."
    assert extracted.metadata["format"] == "text"


def test_extract_document_text(sample_text_file: Path):
    """Test extracting document content."""
    extracted = extract_document(sample_text_file)

    assert extracted.path == str(sample_text_file.absolute())
    assert len(extracted.text) > 0


def test_extract_document_unsupported():
    """Test extracting unsupported file type."""
    unsupported_file = Path("/tmp/test.unsupported")
    unsupported_file.write_text("content")

    with pytest.raises(ValueError, match="Unsupported file format"):
        extract_document(unsupported_file)

    unsupported_file.unlink()


def test_extract_document_not_found():
    """Test extracting non-existent file."""
    with pytest.raises(FileNotFoundError):
        extract_document(Path("/nonexistent/file.txt"))
