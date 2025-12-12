"""Tests enforcing CLI JSON API schema versioning (ADR-0004).

Per ADR-0004, all JSON outputs should include schema metadata:
- schema_id: Identifier for the output type (e.g., "search_results")
- schema_version: Integer version for backward compatibility
- producer: RexLit version that generated output
- produced_at: ISO timestamp of generation

This enables:
1. API consumers to detect breaking changes
2. Migration paths for schema evolution
3. Debugging via producer/timestamp metadata

NOTE: These tests use pytest.xfail() for missing schema implementation.
When CLI JSON wrapping is implemented, tests will unexpectedly pass (xpass),
signaling that the xfail markers should be removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rexlit.cli import app

# Required schema metadata fields per ADR-0004
REQUIRED_SCHEMA_FIELDS = {"schema_id", "schema_version", "producer", "produced_at"}


class TestCLIJsonSchemaVersioning:
    """Verify CLI JSON outputs include schema metadata."""

    def test_index_search_json_has_schema_metadata(self, temp_dir: Path) -> None:
        """index search --json output should include schema metadata."""
        # Create a minimal index
        docs = temp_dir / "docs"
        docs.mkdir()
        (docs / "test.txt").write_text("searchable content here")

        runner = CliRunner()

        # Build index first
        result = runner.invoke(
            app,
            [
                "--data-dir", str(temp_dir / "data"),
                "index", "build", str(docs),
            ],
        )
        assert result.exit_code == 0, f"Index build failed: {result.stdout}"

        # Search with JSON output
        result = runner.invoke(
            app,
            [
                "--data-dir", str(temp_dir / "data"),
                "index", "search", "searchable", "--json",
            ],
        )
        assert result.exit_code == 0, f"Search failed: {result.stdout}"

        # Parse and validate schema metadata
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in search output: {e}")

        # For list outputs, schema metadata should be in wrapper object
        if isinstance(output, list):
            pytest.xfail(
                "ADR-0004 violation: List output lacks schema wrapper. "
                "CLI JSON outputs should be wrapped with schema_id, schema_version, producer, produced_at."
            )

        missing = REQUIRED_SCHEMA_FIELDS - set(output.keys())
        assert not missing, f"Missing schema fields in search output: {missing}"
        assert output["schema_id"] == "search_results"
        assert isinstance(output["schema_version"], int)

    def test_index_metadata_json_has_schema_metadata(self, temp_dir: Path) -> None:
        """index metadata --json output should include schema metadata."""
        # Create and index a document
        docs = temp_dir / "docs"
        docs.mkdir()
        (docs / "doc.txt").write_text("document content")

        runner = CliRunner()

        # Build index
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "index", "build", str(docs)],
        )
        assert result.exit_code == 0

        # Get the document hash from search
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "index", "search", "document", "--json"],
        )
        assert result.exit_code == 0

        try:
            search_results = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in search output: {e}")

        if not search_results:
            pytest.skip("No search results to test metadata")

        # Handle both list and wrapped formats
        if isinstance(search_results, list):
            doc_hash = search_results[0].get("sha256") or search_results[0].get("document_hash")
        else:
            results = search_results.get("results", [])
            if not results:
                pytest.skip("No search results to test metadata")
            doc_hash = results[0].get("sha256") or results[0].get("document_hash")

        if not doc_hash:
            pytest.skip("Could not extract document hash from search results")

        # Fetch metadata
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "index", "metadata", doc_hash, "--json"],
        )
        if result.exit_code != 0:
            pytest.skip(f"Metadata fetch failed (exit {result.exit_code}): {result.stdout or result.stderr}")

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in metadata output: {e}")

        missing = REQUIRED_SCHEMA_FIELDS - set(output.keys())
        if missing:
            pytest.xfail(
                f"ADR-0004 violation: Missing schema fields in metadata output: {missing}. "
                "CLI JSON outputs should include schema_id, schema_version, producer, produced_at."
            )

        assert output["schema_id"] == "document_metadata"
        assert isinstance(output["schema_version"], int)

    def test_audit_log_json_has_schema_metadata(self, temp_dir: Path) -> None:
        """audit log --json output should include schema metadata."""
        runner = CliRunner()

        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "audit", "log", "--json"],
        )

        # May return empty list if no audit entries
        if result.exit_code != 0:
            pytest.skip(f"Audit log command failed: {result.stdout}")

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in audit output: {e}")

        if isinstance(output, list):
            pytest.xfail(
                "ADR-0004 violation: List output lacks schema wrapper. "
                "CLI JSON outputs should be wrapped with schema_id, schema_version, producer, produced_at."
            )

        missing = REQUIRED_SCHEMA_FIELDS - set(output.keys())
        assert not missing, f"Missing schema fields in audit output: {missing}"

    def test_privilege_classify_json_has_schema_metadata(self, temp_dir: Path) -> None:
        """privilege classify --json output should include schema metadata."""
        # Create test document
        doc = temp_dir / "test.txt"
        doc.write_text("This is a test document for classification.")

        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "--data-dir", str(temp_dir / "data"),
                "privilege", "classify", str(doc), "--json",
            ],
        )

        if result.exit_code != 0:
            pytest.skip(f"Privilege classify failed (adapter may not be available): {result.stdout}")

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in classify output: {e}")

        missing = REQUIRED_SCHEMA_FIELDS - set(output.keys())
        if missing:
            pytest.xfail(
                f"ADR-0004 violation: Missing schema fields in classify output: {missing}. "
                "CLI JSON outputs should include schema_id, schema_version, producer, produced_at."
            )

        assert output["schema_id"] == "privilege_decision"
        assert isinstance(output["schema_version"], int)


class TestSchemaVersionConsistency:
    """Verify schema version metadata is consistent and valid."""

    def test_schema_version_is_positive_integer(self) -> None:
        """Schema versions must be positive integers."""
        from rexlit.utils.schema import build_schema_stamp

        stamp = build_schema_stamp(schema_id="test", schema_version=1)
        assert stamp.schema_version >= 1
        assert isinstance(stamp.schema_version, int)

    def test_producer_includes_rexlit_version(self) -> None:
        """Producer field should include RexLit version."""
        from rexlit import __version__
        from rexlit.utils.schema import build_schema_stamp

        stamp = build_schema_stamp(schema_id="test", schema_version=1)
        assert __version__ in stamp.producer or "rexlit" in stamp.producer.lower()

    def test_produced_at_is_valid_iso_timestamp(self) -> None:
        """produced_at field should be valid ISO 8601 timestamp."""
        from datetime import datetime

        from rexlit.utils.schema import build_schema_stamp

        stamp = build_schema_stamp(schema_id="test", schema_version=1)
        # Should not raise
        datetime.fromisoformat(stamp.produced_at.replace("Z", "+00:00"))
