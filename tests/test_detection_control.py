"""Tests for detection control and MIME-type gating."""

import pytest

from rexlit.utils.detection_control import should_detect_document


class TestShouldDetectDocument:
    """Test document detection eligibility."""

    def test_detectable_text_mime_types(self):
        """Test common text MIME types are detectable."""
        detectable, reason = should_detect_document(
            "text/plain", ".txt", 1000
        )
        assert detectable is True
        assert reason is None

        detectable, reason = should_detect_document("text/csv", ".csv", 1000)
        assert detectable is True

        detectable, reason = should_detect_document("text/html", ".html", 1000)
        assert detectable is True

    def test_detectable_document_types(self):
        """Test document formats are detectable."""
        detectable, reason = should_detect_document(
            "application/pdf", ".pdf", 1000
        )
        assert detectable is True

        detectable, reason = should_detect_document(
            "application/msword", ".doc", 1000
        )
        assert detectable is True

        detectable, reason = should_detect_document(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
            1000,
        )
        assert detectable is True

    def test_non_detectable_extension_first(self):
        """Test that extension check happens before MIME type check."""
        # Extension is checked first, so undetectable extensions are rejected first
        detectable, reason = should_detect_document(
            "image/jpeg", ".jpg", 1000
        )
        assert detectable is False
        assert "extension_not_detectable" in reason

        # Use undetectable MIME with undetectable extension
        detectable, reason = should_detect_document(
            "video/mp4", ".mp4", 1000
        )
        assert detectable is False
        assert "extension_not_detectable" in reason

    def test_non_detectable_extension(self):
        """Test non-detectable extensions are skipped."""
        detectable, reason = should_detect_document(
            "application/octet-stream", ".bin", 1000
        )
        assert detectable is False
        assert "extension_not_detectable" in reason

    def test_file_size_limit(self):
        """Test files exceeding size limit are skipped."""
        # 101 MB should exceed default 100 MB limit
        oversized = 101 * 1024 * 1024

        detectable, reason = should_detect_document(
            "text/plain", ".txt", oversized
        )
        assert detectable is False
        assert "exceeds_max_size" in reason

    def test_custom_file_size_limit(self):
        """Test custom size limit is respected."""
        small_limit = 1000  # 1 KB
        detectable, reason = should_detect_document(
            "text/plain", ".txt", 2000, max_size=small_limit
        )
        assert detectable is False
        assert "exceeds_max_size" in reason

    def test_at_size_boundary(self):
        """Test document exactly at size limit is detectable."""
        limit = 1000
        detectable, reason = should_detect_document(
            "text/plain", ".txt", limit, max_size=limit
        )
        assert detectable is True
        assert reason is None

    def test_just_under_size_limit(self):
        """Test document just under size limit is detectable."""
        limit = 1000
        detectable, reason = should_detect_document(
            "text/plain", ".txt", limit - 1, max_size=limit
        )
        assert detectable is True

    def test_case_insensitive_mime_type(self):
        """Test MIME type matching is case-insensitive."""
        detectable, reason = should_detect_document(
            "Text/Plain", ".txt", 1000
        )
        assert detectable is True

        detectable, reason = should_detect_document(
            "APPLICATION/PDF", ".pdf", 1000
        )
        assert detectable is True

    def test_case_insensitive_extension(self):
        """Test extension matching is case-insensitive."""
        detectable, reason = should_detect_document(
            "text/plain", ".TXT", 1000
        )
        assert detectable is True

        detectable, reason = should_detect_document(
            "application/pdf", ".PDF", 1000
        )
        assert detectable is True

    def test_email_formats(self):
        """Test email file formats are detectable."""
        # .eml extension is in DETECTABLE_EXTENSIONS
        detectable, reason = should_detect_document(
            "text/plain", ".eml", 1000
        )
        assert detectable is True

    def test_log_files(self):
        """Test log files are detectable."""
        detectable, reason = should_detect_document(
            "text/x-log", ".log", 1000
        )
        assert detectable is True

        detectable, reason = should_detect_document(
            "text/plain", ".log", 1000
        )
        assert detectable is True

    def test_markdown_files(self):
        """Test markdown files are detectable."""
        detectable, reason = should_detect_document(
            "text/plain", ".md", 1000
        )
        assert detectable is True

        detectable, reason = should_detect_document(
            "text/plain", ".markdown", 1000
        )
        assert detectable is True
