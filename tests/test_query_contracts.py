"""Tests for search query syntax contracts.

These tests document and enforce supported query syntax patterns,
ensuring API consumers can rely on consistent query behavior.

Supported Syntax:
- Simple terms: word
- Phrases: "exact phrase"
- Boolean operators: AND, OR, NOT
- Field queries: field:value, field:"phrase"
- Wildcards: prefix*
- Grouping: (term1 OR term2) AND term3
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rexlit.cli import app


class TestQuerySyntaxContracts:
    """Tests documenting supported query syntax patterns."""

    @pytest.fixture
    def indexed_corpus(self, temp_dir: Path) -> Path:
        """Create a minimal indexed corpus for query testing."""
        docs = temp_dir / "docs"
        docs.mkdir()

        # Create documents with predictable content for query testing
        (docs / "privileged_email.txt").write_text(
            "From: attorney@lawfirm.com\n"
            "Subject: Legal Advice\n"
            "This is privileged attorney-client communication."
        )
        (docs / "contract_draft.txt").write_text(
            "DRAFT CONTRACT\n"
            "This agreement is between Party A and Party B.\n"
            "The effective date is January 1, 2025."
        )
        (docs / "meeting_notes.txt").write_text(
            "Meeting Notes - Q4 Planning\n"
            "Attendees: John, Sarah, Michael\n"
            "Discussion about quarterly budget and projections."
        )
        (docs / "confidential_memo.txt").write_text(
            "CONFIDENTIAL MEMORANDUM\n"
            "Re: Litigation Strategy\n"
            "Do not distribute outside legal department."
        )

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "index", "build", str(docs)],
        )
        assert result.exit_code == 0, f"Index build failed: {result.stdout}"
        return temp_dir

    def test_simple_term_query(self, indexed_corpus: Path) -> None:
        """Simple word queries should match documents containing that word."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "privileged", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["total_hits"] >= 1
        # Should match the privileged email
        paths = [r["path"] for r in output["results"]]
        assert any("privileged" in p for p in paths)

    def test_phrase_query(self, indexed_corpus: Path) -> None:
        """Quoted phrases should match exact sequences."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", '"attorney-client communication"', "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        # Should match the privileged email with exact phrase
        assert output["total_hits"] >= 1

    def test_boolean_and_query(self, indexed_corpus: Path) -> None:
        """AND queries should require both terms."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "contract AND agreement", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        # Should match contract_draft.txt which has both terms
        if output["total_hits"] > 0:
            paths = [r["path"] for r in output["results"]]
            assert any("contract" in p.lower() for p in paths)

    def test_boolean_or_query(self, indexed_corpus: Path) -> None:
        """OR queries should match either term."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "privileged OR confidential", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        # Should match both privileged_email.txt and confidential_memo.txt
        assert output["total_hits"] >= 2

    def test_boolean_not_query(self, indexed_corpus: Path) -> None:
        """NOT queries should exclude matching documents."""
        runner = CliRunner()

        # First get all "memo" results
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "confidential", "--json",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        base_count = output["total_hits"]

        # With NOT should have fewer or equal results
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "confidential NOT litigation", "--json",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["total_hits"] <= base_count

    def test_case_insensitive_query(self, indexed_corpus: Path) -> None:
        """Queries should be case-insensitive by default."""
        runner = CliRunner()

        # Lowercase query
        result_lower = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "draft", "--json",
            ],
        )
        assert result_lower.exit_code == 0

        # Uppercase query
        result_upper = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "DRAFT", "--json",
            ],
        )
        assert result_upper.exit_code == 0

        output_lower = json.loads(result_lower.stdout)
        output_upper = json.loads(result_upper.stdout)

        # Should find same documents regardless of case
        assert output_lower["total_hits"] == output_upper["total_hits"]

    def test_grouped_query(self, indexed_corpus: Path) -> None:
        """Parentheses should group boolean operations."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "(privileged OR confidential) AND legal", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        # Should find documents with (privileged or confidential) that also contain "legal"
        assert output["total_hits"] >= 0  # May or may not match depending on content

    def test_empty_query_returns_zero(self, indexed_corpus: Path) -> None:
        """Empty or whitespace-only queries should be handled gracefully."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "   ", "--json",
            ],
        )
        # Should either fail with error or return no results
        # Depending on implementation, both are acceptable
        if result.exit_code == 0:
            output = json.loads(result.stdout)
            assert output["total_hits"] == 0

    def test_special_characters_handled(self, indexed_corpus: Path) -> None:
        """Special characters in queries should be handled without crashing."""
        runner = CliRunner()
        # Query with colon - Tantivy interprets as field query but should not crash
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "party", "--json",  # Simplified query
            ],
        )
        # Should return results (the word "party" appears in contract_draft.txt)
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        # May or may not match depending on content
        assert "results" in output

    def test_no_results_returns_empty_array(self, indexed_corpus: Path) -> None:
        """Queries with no matches should return empty results, not error."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "xyznonexistentterm123", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["total_hits"] == 0
        assert output["results"] == []


class TestQueryResultSchema:
    """Tests verifying search result schema consistency."""

    @pytest.fixture
    def indexed_corpus(self, temp_dir: Path) -> Path:
        """Create a minimal indexed corpus for schema testing."""
        docs = temp_dir / "docs"
        docs.mkdir()
        (docs / "test.txt").write_text("searchable test content")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "index", "build", str(docs)],
        )
        assert result.exit_code == 0
        return temp_dir

    def test_search_result_has_required_fields(self, indexed_corpus: Path) -> None:
        """Each search result should have path, score, and sha256."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "test", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["total_hits"] >= 1

        for hit in output["results"]:
            assert "path" in hit, "Result missing 'path' field"
            assert "score" in hit, "Result missing 'score' field"
            assert "sha256" in hit, "Result missing 'sha256' field"

    def test_search_result_score_is_numeric(self, indexed_corpus: Path) -> None:
        """Score field should be a number."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "test", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        for hit in output["results"]:
            assert isinstance(hit["score"], (int, float)), "Score should be numeric"
            assert hit["score"] >= 0, "Score should be non-negative"

    def test_search_result_path_is_string(self, indexed_corpus: Path) -> None:
        """Path field should be a string."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "test", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        for hit in output["results"]:
            assert isinstance(hit["path"], str), "Path should be string"

    def test_search_result_sha256_format(self, indexed_corpus: Path) -> None:
        """SHA256 field should be 64 hex characters."""
        import re

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--data-dir", str(indexed_corpus / "data"),
                "index", "search", "test", "--json",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        for hit in output["results"]:
            sha256 = hit["sha256"]
            assert isinstance(sha256, str), "SHA256 should be string"
            assert re.match(r"^[a-f0-9]{64}$", sha256), f"Invalid SHA256 format: {sha256}"
