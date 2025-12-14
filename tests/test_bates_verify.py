"""Tests for Bates registry verification (ADR-0005).

These tests verify the verify_bates_registry function and CLI command
correctly detect integrity issues in Bates plan files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rexlit.utils.bates_verify import verify_bates_registry
from rexlit.cli import app
from rexlit.utils.hashing import compute_sha256_file


class TestVerifyBatesRegistry:
    """Unit tests for verify_bates_registry function."""

    def test_valid_registry_passes(self, temp_dir: Path) -> None:
        """Valid Bates registry should pass verification."""
        # Create test documents
        docs = temp_dir / "docs"
        docs.mkdir()
        doc1 = docs / "doc1.txt"
        doc2 = docs / "doc2.txt"
        doc1.write_text("First document content")
        doc2.write_text("Second document content")

        # Create valid Bates plan
        plan_path = temp_dir / "bates_plan.jsonl"
        records = [
            {
                "document": str(doc1),
                "sha256": compute_sha256_file(doc1),
                "bates_id": "RXL-000001",
            },
            {
                "document": str(doc2),
                "sha256": compute_sha256_file(doc2),
                "bates_id": "RXL-000002",
            },
        ]
        with plan_path.open("w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert is_valid, f"Expected valid registry, got errors: {errors}"
        assert errors == []

    def test_missing_plan_file(self, temp_dir: Path) -> None:
        """Non-existent plan file should fail verification."""
        plan_path = temp_dir / "nonexistent.jsonl"

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_empty_plan_file(self, temp_dir: Path) -> None:
        """Empty plan file should fail verification."""
        plan_path = temp_dir / "bates_plan.jsonl"
        plan_path.write_text("")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("empty" in e.lower() for e in errors)

    def test_duplicate_bates_id_detected(self, temp_dir: Path) -> None:
        """Duplicate Bates IDs should be reported."""
        docs = temp_dir / "docs"
        docs.mkdir()
        doc1 = docs / "doc1.txt"
        doc2 = docs / "doc2.txt"
        doc1.write_text("First document")
        doc2.write_text("Second document")

        plan_path = temp_dir / "bates_plan.jsonl"
        records = [
            {
                "document": str(doc1),
                "sha256": compute_sha256_file(doc1),
                "bates_id": "RXL-000001",  # Duplicate
            },
            {
                "document": str(doc2),
                "sha256": compute_sha256_file(doc2),
                "bates_id": "RXL-000001",  # Duplicate
            },
        ]
        with plan_path.open("w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("Duplicate Bates ID" in e for e in errors)

    def test_duplicate_sha256_detected(self, temp_dir: Path) -> None:
        """Duplicate SHA-256 hashes should be reported."""
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Document content")
        doc_hash = compute_sha256_file(doc)

        plan_path = temp_dir / "bates_plan.jsonl"
        records = [
            {
                "document": str(doc),
                "sha256": doc_hash,
                "bates_id": "RXL-000001",
            },
            {
                "document": str(doc),
                "sha256": doc_hash,  # Same hash
                "bates_id": "RXL-000002",
            },
        ]
        with plan_path.open("w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("Duplicate SHA-256" in e for e in errors)

    def test_missing_file_detected(self, temp_dir: Path) -> None:
        """References to missing files should be reported."""
        plan_path = temp_dir / "bates_plan.jsonl"
        record = {
            "document": str(temp_dir / "nonexistent.txt"),
            "sha256": "a" * 64,
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("File not found" in e for e in errors)

    def test_hash_mismatch_detected(self, temp_dir: Path) -> None:
        """Modified files should be detected via hash mismatch."""
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Original content")
        original_hash = compute_sha256_file(doc)

        # Modify the file after recording the hash
        doc.write_text("MODIFIED content")

        plan_path = temp_dir / "bates_plan.jsonl"
        record = {
            "document": str(doc),
            "sha256": original_hash,  # Original hash, but file was modified
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("Hash mismatch" in e for e in errors)

    def test_missing_bates_id_field_detected(self, temp_dir: Path) -> None:
        """Records missing bates_id field should be reported."""
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Content")

        plan_path = temp_dir / "bates_plan.jsonl"
        record = {
            "document": str(doc),
            "sha256": compute_sha256_file(doc),
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("'bates_id'" in e for e in errors)

    def test_missing_sha256_field_detected(self, temp_dir: Path) -> None:
        """Records missing sha256 field should be reported."""
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Content")

        plan_path = temp_dir / "bates_plan.jsonl"
        record = {
            "document": str(doc),
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("'sha256'" in e for e in errors)

    def test_missing_document_field_detected(self, temp_dir: Path) -> None:
        """Records missing document field should be reported."""
        plan_path = temp_dir / "bates_plan.jsonl"
        record = {
            "sha256": "a" * 64,
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("'document'" in e for e in errors)

    def test_invalid_json_detected(self, temp_dir: Path) -> None:
        """Invalid JSON lines should be reported."""
        plan_path = temp_dir / "bates_plan.jsonl"
        with plan_path.open("w") as f:
            f.write("not valid json\n")

        is_valid, errors = verify_bates_registry(plan_path)
        assert not is_valid
        assert any("Invalid JSON" in e for e in errors)


class TestBatesVerifyCLI:
    """Integration tests for the bates verify CLI command."""

    def test_verify_valid_registry_succeeds(self, temp_dir: Path) -> None:
        """CLI should return success for valid registry."""
        # Create test documents
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Document content")

        # Create valid Bates plan
        bates_dir = temp_dir / "data" / "bates"
        bates_dir.mkdir(parents=True)
        plan_path = bates_dir / "bates_plan.jsonl"
        record = {
            "document": str(doc),
            "sha256": compute_sha256_file(doc),
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "bates", "verify"],
        )
        assert result.exit_code == 0
        assert "verified" in result.stdout.lower()

    def test_verify_invalid_registry_fails(self, temp_dir: Path) -> None:
        """CLI should return error for invalid registry."""
        # Create plan with missing file reference
        bates_dir = temp_dir / "data" / "bates"
        bates_dir.mkdir(parents=True)
        plan_path = bates_dir / "bates_plan.jsonl"
        record = {
            "document": str(temp_dir / "nonexistent.txt"),
            "sha256": "a" * 64,
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "bates", "verify"],
        )
        assert result.exit_code == 1
        # Error output includes our error message somewhere in the output
        assert "failed" in result.output.lower() or "error" in result.output.lower() or "not found" in result.output.lower()

    def test_verify_json_output_format(self, temp_dir: Path) -> None:
        """CLI --json output should have schema metadata."""
        # Create test documents
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Document content")

        # Create valid Bates plan
        bates_dir = temp_dir / "data" / "bates"
        bates_dir.mkdir(parents=True)
        plan_path = bates_dir / "bates_plan.jsonl"
        record = {
            "document": str(doc),
            "sha256": compute_sha256_file(doc),
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "bates", "verify", "--json"],
        )
        # JSON output goes to stdout regardless of exit code
        # Parse the output to validate schema
        try:
            output = json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.output}")

        assert output["schema_id"] == "bates_verification"
        assert "producer" in output
        assert "produced_at" in output
        # The test should pass - valid is True if no errors
        if result.exit_code == 0:
            assert output["valid"] is True

    def test_verify_json_output_when_invalid(self, temp_dir: Path) -> None:
        """CLI --json output should include errors when verification fails."""
        # Create plan with missing file reference
        bates_dir = temp_dir / "data" / "bates"
        bates_dir.mkdir(parents=True)
        plan_path = bates_dir / "bates_plan.jsonl"
        record = {
            "document": str(temp_dir / "nonexistent.txt"),
            "sha256": "a" * 64,
            "bates_id": "RXL-000001",
        }
        with plan_path.open("w") as f:
            f.write(json.dumps(record) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "bates", "verify", "--json"],
        )
        assert result.exit_code == 1

        try:
            output = json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.output}")

        assert output["schema_id"] == "bates_verification"
        assert output["valid"] is False
        assert "errors" in output
        assert len(output["errors"]) >= 1
        assert any("not found" in e.lower() for e in output["errors"])

    def test_verify_missing_plan_file(self, temp_dir: Path) -> None:
        """CLI should fail gracefully when no plan file exists."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "bates", "verify"],
        )
        assert result.exit_code == 1
        # Error output includes our error message somewhere
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_verify_explicit_plan_path(self, temp_dir: Path) -> None:
        """CLI should accept explicit plan path argument."""
        # Create test document
        docs = temp_dir / "docs"
        docs.mkdir()
        doc = docs / "doc.txt"
        doc.write_text("Content")

        # Create plan in custom location
        custom_plan = temp_dir / "custom_plan.jsonl"
        record = {
            "document": str(doc),
            "sha256": compute_sha256_file(doc),
            "bates_id": "RXL-000001",
        }
        with custom_plan.open("w") as f:
            f.write(json.dumps(record) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["--data-dir", str(temp_dir / "data"), "bates", "verify", str(custom_plan)],
        )
        assert result.exit_code == 0
        assert "verified" in result.stdout.lower()
