"""Tests for Bates registry collision detection and idempotency (ADR-0005).

These tests verify:
1. Collision detection - duplicate paths, hashes, or Bates IDs are rejected
2. Idempotency - running the same plan twice produces identical assignments
3. Hash integrity - modified files are detected and rejected

Per ADR-0005, Bates numbers are the authoritative document identifiers for
legal production, so collision prevention is critical for legal defensibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rexlit.app.adapters.bates import SequentialBatesPlanner
from rexlit.config import Settings


class MockDocument:
    """Mock document record for testing."""

    def __init__(
        self,
        path: Path,
        sha256: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.path = str(path)
        self.sha256 = sha256
        self.extension = path.suffix
        self.mtime = "2025-01-01T00:00:00Z"
        self.metadata = metadata or {}


class TestBatesCollisionDetection:
    """Tests verifying collision detection in Bates numbering."""

    def test_duplicate_path_raises_error(self, temp_dir: Path) -> None:
        """Duplicate document paths should be rejected."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )
        planner = SequentialBatesPlanner(settings=settings)

        # Create a real file
        doc_path = temp_dir / "doc.txt"
        doc_path.write_text("content")

        # Create mock with same path twice (simulating duplicate)
        from rexlit.utils.hashing import compute_sha256_file
        doc_hash = compute_sha256_file(doc_path)

        doc1 = MockDocument(doc_path, doc_hash)
        doc2 = MockDocument(doc_path, doc_hash)  # Same path

        with pytest.raises(ValueError, match="Duplicate document path"):
            planner.plan([doc1, doc2])

    def test_duplicate_hash_raises_error(self, temp_dir: Path) -> None:
        """Duplicate SHA-256 hashes should be rejected (even with different paths)."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )
        planner = SequentialBatesPlanner(settings=settings)

        # Create two files with identical content (same hash)
        doc1_path = temp_dir / "doc1.txt"
        doc2_path = temp_dir / "doc2.txt"
        doc1_path.write_text("identical content")
        doc2_path.write_text("identical content")

        from rexlit.utils.hashing import compute_sha256_file
        hash1 = compute_sha256_file(doc1_path)
        hash2 = compute_sha256_file(doc2_path)

        # Hashes should be identical
        assert hash1 == hash2

        doc1 = MockDocument(doc1_path, hash1)
        doc2 = MockDocument(doc2_path, hash2)

        with pytest.raises(ValueError, match="Duplicate SHA-256"):
            planner.plan([doc1, doc2])

    def test_hash_mismatch_raises_error(self, temp_dir: Path) -> None:
        """Document modified between discovery and planning should be rejected."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )
        planner = SequentialBatesPlanner(settings=settings)

        doc_path = temp_dir / "doc.txt"
        doc_path.write_text("original content")

        from rexlit.utils.hashing import compute_sha256_file
        original_hash = compute_sha256_file(doc_path)

        # Modify the file
        doc_path.write_text("MODIFIED content")

        doc = MockDocument(doc_path, original_hash)  # Still using old hash

        with pytest.raises(ValueError, match="hash mismatch"):
            planner.plan([doc])

    def test_missing_file_raises_error(self, temp_dir: Path) -> None:
        """Non-existent files should be rejected."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )
        planner = SequentialBatesPlanner(settings=settings)

        missing_path = temp_dir / "nonexistent.txt"
        doc = MockDocument(missing_path, "fake_hash")

        with pytest.raises(FileNotFoundError, match="source is missing"):
            planner.plan([doc])


class TestBatesIdempotency:
    """Tests verifying Bates planning is idempotent."""

    def test_same_input_produces_same_output(self, temp_dir: Path) -> None:
        """Running plan() twice with same input should produce identical assignments."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )

        # Create test files
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()

        for i in range(3):
            (docs_dir / f"doc{i}.txt").write_text(f"Content for document {i}")

        from rexlit.utils.hashing import compute_sha256_file

        documents = [
            MockDocument(
                docs_dir / f"doc{i}.txt",
                compute_sha256_file(docs_dir / f"doc{i}.txt"),
            )
            for i in range(3)
        ]

        # Run plan twice
        planner1 = SequentialBatesPlanner(settings=settings)
        plan1 = planner1.plan(documents, prefix="ABC", width=6)

        # Need to use fresh planner and clear plan file to re-run
        plan_path = settings.get_data_dir() / "bates" / "bates_plan.jsonl"
        plan_path.unlink(missing_ok=True)

        planner2 = SequentialBatesPlanner(settings=settings)
        plan2 = planner2.plan(documents, prefix="ABC", width=6)

        # Verify identical assignments
        assert len(plan1.assignments) == len(plan2.assignments)
        for a1, a2 in zip(plan1.assignments, plan2.assignments, strict=True):
            assert a1.document == a2.document
            assert a1.sha256 == a2.sha256
            assert a1.bates_id == a2.bates_id

    def test_different_document_order_produces_same_output(self, temp_dir: Path) -> None:
        """Input order should not affect output (deterministic sorting)."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )

        # Create test files
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()

        for name in ["zebra.txt", "alpha.txt", "beta.txt"]:
            (docs_dir / name).write_text(f"Content for {name}")

        from rexlit.utils.hashing import compute_sha256_file

        def make_docs(order: list[str]) -> list[MockDocument]:
            return [
                MockDocument(
                    docs_dir / name,
                    compute_sha256_file(docs_dir / name),
                )
                for name in order
            ]

        # Create documents in different orders
        docs_order1 = make_docs(["alpha.txt", "beta.txt", "zebra.txt"])
        docs_order2 = make_docs(["zebra.txt", "alpha.txt", "beta.txt"])

        # Run plan with first order
        planner1 = SequentialBatesPlanner(settings=settings)
        plan1 = planner1.plan(docs_order1, prefix="TST", width=4)

        # Clear and run with second order
        plan_path = settings.get_data_dir() / "bates" / "bates_plan.jsonl"
        plan_path.unlink(missing_ok=True)

        planner2 = SequentialBatesPlanner(settings=settings)
        plan2 = planner2.plan(docs_order2, prefix="TST", width=4)

        # Verify same Bates IDs assigned to same documents
        map1 = {a.sha256: a.bates_id for a in plan1.assignments}
        map2 = {a.sha256: a.bates_id for a in plan2.assignments}
        assert map1 == map2


class TestBatesPlanPersistence:
    """Tests verifying Bates plan JSONL output."""

    def test_plan_writes_jsonl_with_schema_metadata(self, temp_dir: Path) -> None:
        """Plan output should include schema metadata per ADR-0004."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )

        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.txt").write_text("test content")

        from rexlit.utils.hashing import compute_sha256_file

        doc = MockDocument(
            docs_dir / "doc.txt",
            compute_sha256_file(docs_dir / "doc.txt"),
        )

        planner = SequentialBatesPlanner(settings=settings)
        planner.plan([doc])  # Result not needed, we check the file directly

        # Read the JSONL file and check schema metadata
        plan_path = settings.get_data_dir() / "bates" / "bates_plan.jsonl"
        assert plan_path.exists()

        with open(plan_path) as f:
            first_line = f.readline()
            record = json.loads(first_line)

        # Should have schema metadata per ADR-0004
        assert "schema_id" in record, "Missing schema_id in Bates plan JSONL"
        assert record["schema_id"] == "bates_map"
        assert "schema_version" in record
        assert record["schema_version"] == 1

    def test_plan_path_stored_in_planner(self, temp_dir: Path) -> None:
        """Planner should track the last plan path for reference."""
        settings = Settings(
            data_dir=temp_dir / "data",
            config_dir=temp_dir / "config",
            audit_enabled=False,
        )

        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.txt").write_text("test content")

        from rexlit.utils.hashing import compute_sha256_file

        doc = MockDocument(
            docs_dir / "doc.txt",
            compute_sha256_file(docs_dir / "doc.txt"),
        )

        planner = SequentialBatesPlanner(settings=settings)
        assert planner.last_plan_path is None

        planner.plan([doc])  # Triggers plan path assignment
        assert planner.last_plan_path is not None
        assert planner.last_plan_path.exists()
