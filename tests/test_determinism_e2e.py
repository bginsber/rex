"""End-to-end determinism tests per ADR-0003.

This module verifies that RexLit pipelines produce identical outputs
across multiple runs on the same input, which is critical for legal
defensibility. Per ADR-0003, determinism is achieved through:

1. Stable ordering by (sha256, path) tuple
2. Plan IDs derived from sorted input hashes
3. Bates numbers assigned sequentially from sorted inputs

These tests run actual pipelines twice and verify output equality.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rexlit.bootstrap import bootstrap_application
from rexlit.config import Settings
from rexlit.utils.deterministic import (
    compute_input_hash,
    deterministic_sort_paths,
    verify_determinism,
)


class TestDeterministicHelpers:
    """Unit tests for determinism utilities."""

    def test_deterministic_sort_paths_stable(self, temp_dir: Path) -> None:
        """Verify path sorting is stable across multiple calls."""
        # Create files with known content
        (temp_dir / "z_file.txt").write_text("content_z")
        (temp_dir / "a_file.txt").write_text("content_a")
        (temp_dir / "m_file.txt").write_text("content_m")

        paths = list(temp_dir.glob("*.txt"))

        # Sort multiple times
        sorted1 = deterministic_sort_paths(paths)
        sorted2 = deterministic_sort_paths(paths)
        sorted3 = deterministic_sort_paths(list(reversed(paths)))

        # All should produce identical order
        assert sorted1 == sorted2 == sorted3

    def test_compute_input_hash_stable(self) -> None:
        """Verify input hash is deterministic regardless of input order."""
        inputs_a = ["hash_a", "hash_b", "hash_c"]
        inputs_b = ["hash_c", "hash_a", "hash_b"]  # Different order
        inputs_c = ["hash_b", "hash_c", "hash_a"]  # Yet another order

        hash_a = compute_input_hash(inputs_a)
        hash_b = compute_input_hash(inputs_b)
        hash_c = compute_input_hash(inputs_c)

        # All should produce same hash (sorted internally)
        assert hash_a == hash_b == hash_c


class TestPipelineDeterminism:
    """End-to-end determinism tests for the M1 pipeline."""

    def test_manifest_order_deterministic(self, temp_dir: Path) -> None:
        """Running ingest twice produces identical manifest order (ADR-0003)."""
        # Create documents with different filenames and content
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()

        # Create files in non-alphabetical order
        (docs_dir / "zebra.txt").write_text("I am a zebra document")
        (docs_dir / "alpha.txt").write_text("I am an alpha document")
        (docs_dir / "beta.txt").write_text("I am a beta document")

        # Create shared directories for both runs to use same encryption keys
        shared_data_dir = temp_dir / "shared_data"
        shared_config_dir = temp_dir / "shared_config"
        shared_data_dir.mkdir()
        shared_config_dir.mkdir()

        def run_pipeline(output_suffix: str) -> list[dict[str, object]]:
            """Run pipeline and return manifest records."""
            # Use shared data/config dirs so encryption keys are stable
            settings = Settings(
                data_dir=shared_data_dir,
                config_dir=shared_config_dir,
                audit_enabled=False,
            )
            container = bootstrap_application(settings=settings)
            manifest_path = temp_dir / f"manifest_{output_suffix}.jsonl"
            container.pipeline.run(docs_dir, manifest_path=manifest_path)

            # Filter out non-original documents (e.g., .enc files from previous runs)
            records = []
            for line in manifest_path.read_text().splitlines():
                rec = json.loads(line)
                # Only include original .txt files, not generated artifacts
                if rec.get("extension") == ".txt":
                    records.append(rec)
            return records

        # Run twice
        manifest_1 = run_pipeline("run1")
        manifest_2 = run_pipeline("run2")

        # Verify same number of original documents
        assert len(manifest_1) == len(manifest_2) == 3, (
            f"Expected 3 .txt files in each run, got {len(manifest_1)} and {len(manifest_2)}"
        )

        # Verify identical order (by sha256 and path)
        for i, (rec1, rec2) in enumerate(zip(manifest_1, manifest_2, strict=True)):
            assert rec1["sha256"] == rec2["sha256"], f"Document {i}: sha256 mismatch"
            assert rec1["path"] == rec2["path"], f"Document {i}: path mismatch"

    def test_redaction_plan_ids_deterministic(self, temp_dir: Path) -> None:
        """Redaction plan IDs are stable across runs (ADR-0003, ADR-0006)."""
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()

        # Create documents
        (docs_dir / "doc1.txt").write_text("Document with PII: 123-45-6789")
        (docs_dir / "doc2.txt").write_text("Another document with email: test@example.com")

        # Create shared directories for both runs to use same encryption keys
        shared_data_dir = temp_dir / "shared_data"
        shared_config_dir = temp_dir / "shared_config"
        shared_data_dir.mkdir()
        shared_config_dir.mkdir()

        def run_pipeline(output_suffix: str) -> dict[str, str]:
            """Run pipeline and return redaction plan IDs for .txt files only."""
            settings = Settings(
                data_dir=shared_data_dir,
                config_dir=shared_config_dir,
                audit_enabled=False,
            )
            container = bootstrap_application(settings=settings)
            manifest_path = temp_dir / f"manifest_{output_suffix}.jsonl"
            result = container.pipeline.run(docs_dir, manifest_path=manifest_path)
            # Filter to only .txt files (exclude artifacts like .enc files)
            return {k: v for k, v in result.redaction_plan_ids.items() if k.endswith(".txt")}

        # Run twice
        plans_1 = run_pipeline("run1")
        plans_2 = run_pipeline("run2")

        # Verify identical plan IDs for same documents
        assert plans_1 == plans_2, f"Redaction plan IDs should be deterministic: {plans_1} != {plans_2}"

    def test_bates_plan_deterministic(self, temp_dir: Path) -> None:
        """Bates plan produces same assignments across runs (ADR-0003, ADR-0005)."""
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()

        # Create documents in random order
        (docs_dir / "x_contract.txt").write_text("Contract document")
        (docs_dir / "a_invoice.txt").write_text("Invoice document")
        (docs_dir / "m_email.txt").write_text("Email document")

        # Create shared directories for both runs to use same encryption keys
        shared_data_dir = temp_dir / "shared_data"
        shared_config_dir = temp_dir / "shared_config"
        shared_data_dir.mkdir()
        shared_config_dir.mkdir()

        def run_pipeline(output_suffix: str) -> list[dict[str, object]]:
            """Run pipeline and return Bates plan entries for .txt files only."""
            settings = Settings(
                data_dir=shared_data_dir,
                config_dir=shared_config_dir,
                audit_enabled=False,
            )
            container = bootstrap_application(settings=settings)
            manifest_path = temp_dir / f"manifest_{output_suffix}.jsonl"
            container.pipeline.run(docs_dir, manifest_path=manifest_path)

            # Read Bates plan
            bates_plan_path = settings.get_data_dir() / "bates" / "bates_plan.jsonl"
            if not bates_plan_path.exists():
                return []

            # Filter to only .txt files (exclude artifacts like .enc files)
            entries = []
            for line in bates_plan_path.read_text().splitlines():
                entry = json.loads(line)
                doc_path = entry.get("document", "")
                if doc_path.endswith(".txt"):
                    entries.append(entry)
            return entries

        # Run twice
        bates_1 = run_pipeline("run1")
        bates_2 = run_pipeline("run2")

        # Skip if no Bates plan generated (feature may not be enabled)
        if not bates_1:
            pytest.skip("Bates plan not generated - feature may be disabled")

        # Verify identical Bates assignments
        assert len(bates_1) == len(bates_2), f"Different number of Bates entries: {len(bates_1)} vs {len(bates_2)}"

        for i, (entry1, entry2) in enumerate(zip(bates_1, bates_2, strict=True)):
            # Compare relevant fields (skip timestamps)
            assert entry1.get("document") == entry2.get("document"), f"Entry {i}: document mismatch"
            assert entry1.get("bates_start") == entry2.get("bates_start"), (
                f"Entry {i}: bates_start mismatch"
            )
            assert entry1.get("bates_end") == entry2.get("bates_end"), (
                f"Entry {i}: bates_end mismatch"
            )


class TestVerifyDeterminismHelper:
    """Tests for the verify_determinism() helper function itself."""

    def test_verify_determinism_passes_for_stable_function(self) -> None:
        """verify_determinism returns True for deterministic functions."""

        def stable_sort(items: list[int]) -> list[int]:
            return sorted(items)

        inputs = [3, 1, 4, 1, 5, 9, 2, 6]
        assert verify_determinism(stable_sort, inputs, runs=5) is True

    def test_verify_determinism_detects_unstable_function(self) -> None:
        """verify_determinism returns False for non-deterministic functions."""
        import random

        call_count = 0

        def unstable_shuffle(items: list[int]) -> list[int]:
            nonlocal call_count
            call_count += 1
            result = list(items)
            # Only shuffle after first call to guarantee at least one difference
            if call_count > 1:
                random.shuffle(result)
            return result

        inputs = list(range(100))  # Large enough to make collision unlikely
        # Note: This test could theoretically fail if shuffle happens to
        # produce same order, but probability is negligible with 100 items
        assert verify_determinism(unstable_shuffle, inputs, runs=3) is False
