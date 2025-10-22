"""Pytest configuration and fixtures."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_text_file(temp_dir: Path) -> Path:
    """Create a sample text file."""
    file_path = temp_dir / "sample.txt"
    file_path.write_text("This is a sample text file for testing.")
    return file_path


@pytest.fixture
def sample_files(temp_dir: Path) -> list[Path]:
    """Create multiple sample files."""
    files = []

    # Text file
    txt_file = temp_dir / "document1.txt"
    txt_file.write_text("First sample document.")
    files.append(txt_file)

    # Another text file
    txt_file2 = temp_dir / "document2.txt"
    txt_file2.write_text("Second sample document with different content.")
    files.append(txt_file2)

    # Markdown file
    md_file = temp_dir / "readme.md"
    md_file.write_text("# README\n\nThis is a markdown file.")
    files.append(md_file)

    return files


@pytest.fixture
def nested_files(temp_dir: Path) -> Path:
    """Create nested directory structure with files."""
    # Create subdirectories
    sub1 = temp_dir / "custodians" / "john_doe"
    sub1.mkdir(parents=True)

    sub2 = temp_dir / "custodians" / "jane_smith"
    sub2.mkdir(parents=True)

    # Create files
    (sub1 / "doc1.txt").write_text("Document from John Doe.")
    (sub1 / "doc2.txt").write_text("Another document from John.")
    (sub2 / "doc1.txt").write_text("Document from Jane Smith.")

    return temp_dir
