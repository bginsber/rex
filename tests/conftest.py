"""Pytest configuration and fixtures."""

import gc
import os
import shutil
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from rexlit.config import Settings


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    try:
        yield Path(tmpdir)
    finally:
        # Force garbage collection to release any file handles
        gc.collect()
        # Small delay to allow OS to release file locks
        time.sleep(0.1)
        # Retry cleanup with ignore_errors for better cross-platform support
        shutil.rmtree(tmpdir, ignore_errors=True)


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


@pytest.fixture
def override_settings(temp_dir: Path) -> Generator[Settings, None, None]:
    """Provide isolated RexLit settings scoped to tests."""

    import rexlit.config as config_module

    original_settings = getattr(config_module, "_settings", None)

    data_dir = temp_dir / "appdata"
    config_dir = temp_dir / "appconfig"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    settings = config_module.Settings(
        data_dir=data_dir,
        config_dir=config_dir,
        audit_enabled=True,
    )

    config_module._settings = settings

    try:
        yield settings
    finally:
        config_module._settings = original_settings


def _resolve_corpus_path(root: Path, name: str) -> Path:
    corpus_path = root / name
    if not corpus_path.exists():
        pytest.skip(f"IDL fixture corpus '{name}' not initialized at {corpus_path}")
    return corpus_path


@pytest.fixture(scope="session")
def idl_fixture_root() -> Path:
    """Resolve the local root directory for IDL fixture corpora."""

    env_path = os.getenv("IDL_FIXTURE_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if not path.exists():
            pytest.skip(f"IDL fixture path from IDL_FIXTURE_PATH does not exist: {path}")
        return path

    default = Path(__file__).resolve().parent.parent / "rexlit" / "docs" / "idl-fixtures"
    if not default.exists():
        pytest.skip(
            "IDL fixtures not available. Set IDL_FIXTURE_PATH or run scripts/setup-idl-fixtures.sh."
        )
    return default


@pytest.fixture(scope="session")
def idl_small(idl_fixture_root: Path) -> Path:
    """Small (~100 docs) IDL corpus for smoke tests."""

    return _resolve_corpus_path(idl_fixture_root, "small")


@pytest.fixture(scope="session")
def idl_medium(idl_fixture_root: Path) -> Path:
    """Medium (~1,000 docs) IDL corpus for integration tests."""

    return _resolve_corpus_path(idl_fixture_root, "medium")


@pytest.fixture(scope="session")
def idl_large(idl_fixture_root: Path) -> Path:
    """Large (~10,000 docs) IDL corpus for stress tests."""

    return _resolve_corpus_path(idl_fixture_root, "large")


@pytest.fixture(scope="session")
def idl_xl(idl_fixture_root: Path) -> Path:
    """XL (~100,000 docs) IDL corpus for benchmark runs."""

    return _resolve_corpus_path(idl_fixture_root, "xl")


@pytest.fixture(scope="session")
def idl_edge_cases(idl_fixture_root: Path) -> Path:
    """Edge-case IDL corpus (malformed PDFs, OCR challenges, privilege patterns)."""

    return _resolve_corpus_path(idl_fixture_root, "edge-cases")
