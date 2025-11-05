"""CLI integration smoke tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from rexlit.cli import app


def test_cli_ingest_emits_manifest_and_logs(
    temp_dir: Path,
    override_settings,
) -> None:
    """`rexlit ingest run` writes manifest records and audit entries."""

    settings = override_settings

    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    sample_doc = docs_dir / "sample.txt"
    sample_doc.write_text("cli ingest test")

    manifest_path = temp_dir / "manifest.jsonl"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "run",
            str(docs_dir),
            "--manifest",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Found 1 documents" in result.stdout
    assert "Manifest written to" in result.stdout
    assert "NOTE:" in result.stdout
    assert "[completed] dedupe" in result.stdout
    assert "[completed] redaction_plan" in result.stdout
    assert "[completed] bates" in result.stdout
    assert "[completed] pack" in result.stdout

    assert manifest_path.exists()
    manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(manifest_lines) == 1

    manifest_record = json.loads(manifest_lines[0])
    assert Path(manifest_record["path"]).name == sample_doc.name
    assert manifest_record["schema_id"] == "manifest"
    assert manifest_record["schema_version"] == 1
    assert manifest_record["producer"].startswith("rexlit-")
    datetime.fromisoformat(manifest_record["produced_at"])

    audit_path = settings.get_audit_path()
    assert audit_path.exists()

    audit_lines = [line for line in audit_path.read_text().splitlines() if line.strip()]
    assert audit_lines
    audit_entry = json.loads(audit_lines[-1])
    assert audit_entry["operation"] == "m1_pipeline"
    assert [Path(path).resolve() for path in audit_entry["inputs"]] == [docs_dir.resolve()]
    outputs = {Path(output).resolve() for output in audit_entry["outputs"]}
    assert manifest_path.resolve() in outputs
    assert any(output.name.endswith(".redaction-plan.enc") for output in outputs)
    assert "redaction_plans" in audit_entry["args"]
    assert audit_entry["args"]["redaction_plans"]


def test_cli_ingest_writes_impact_report(
    temp_dir: Path,
    override_settings,
) -> None:
    """`rexlit ingest run --impact-report` generates JSON discovery impact summary."""

    # Setup: create a small corpus with varied files and custodians
    corpus_dir = temp_dir / "corpus"
    corpus_dir.mkdir()

    # Create custodian structure
    (corpus_dir / "custodians" / "alice").mkdir(parents=True)
    (corpus_dir / "custodians" / "bob").mkdir(parents=True)

    # Create sample files with different types (with reasonable size)
    (corpus_dir / "custodians" / "alice" / "doc1.pdf").write_text("PDF content " * 10000)
    (corpus_dir / "custodians" / "alice" / "doc2.docx").write_text("DOCX content " * 10000)
    (corpus_dir / "custodians" / "bob" / "email.eml").write_text("Email content " * 10000)

    manifest_path = temp_dir / "manifest.jsonl"
    impact_path = temp_dir / "impact.json"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "run",
            str(corpus_dir),
            "--manifest",
            str(manifest_path),
            "--impact-report",
            str(impact_path),
            "--review-docs-per-hour-low",
            "60",
            "--review-docs-per-hour-high",
            "120",
            "--review-cost-low",
            "100",
            "--review-cost-high",
            "250",
        ],
    )

    # Assert success
    assert result.exit_code == 0, result.stdout
    assert "Impact report written to" in result.stdout

    # Assert impact report file exists
    assert impact_path.exists()

    # Parse and validate structure
    report_data = json.loads(impact_path.read_text())

    # Schema and version
    assert report_data["schema_version"] == "1.0.0"
    assert "tool_version" in report_data
    assert report_data["tool_version"]

    # Summary statistics
    assert report_data["summary"]["unique_documents"] == 3
    assert report_data["summary"]["total_discovered"] >= 3
    assert "duplicates_removed" in report_data["summary"]
    assert "dedupe_rate_pct" in report_data["summary"]
    assert report_data["summary"]["total_size_bytes"] > 0
    assert report_data["summary"]["total_size_mb"] > 0

    # Estimated review
    assert report_data["estimated_review"]["hours_low"] >= 0
    assert report_data["estimated_review"]["hours_high"] >= 0
    assert report_data["estimated_review"]["cost_low_usd"] >= 0
    assert report_data["estimated_review"]["cost_high_usd"] >= 0
    assert "60-120 docs/hr" in report_data["estimated_review"]["assumptions"]

    # Culling rationale
    assert report_data["culling_rationale"]

    # Custodians
    assert len(report_data["by_custodian"]) == 2
    assert "alice" in report_data["by_custodian"]
    assert "bob" in report_data["by_custodian"]
    assert report_data["by_custodian"]["alice"]["count"] == 2
    assert report_data["by_custodian"]["bob"]["count"] == 1

    # Extensions
    assert ".pdf" in report_data["by_extension"]
    assert ".docx" in report_data["by_extension"]
    assert ".eml" in report_data["by_extension"]

    # Errors (should be empty for successful run)
    assert report_data["errors"]["count"] == 0

    # Timestamp
    assert report_data["generated_at"]
    datetime.fromisoformat(report_data["generated_at"])

    # Manifest path
    assert report_data["manifest_path"]


def test_cli_ingest_rejects_invalid_review_rates(temp_dir: Path, override_settings) -> None:
    """CLI exits when review rate parameters are invalid."""

    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "sample.txt").write_text("content")

    manifest_path = temp_dir / "manifest.jsonl"
    impact_path = temp_dir / "impact.json"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "run",
            str(docs_dir),
            "--manifest",
            str(manifest_path),
            "--impact-report",
            str(impact_path),
            "--review-docs-per-hour-low",
            "0",
        ],
    )

    assert result.exit_code == 1
    assert not impact_path.exists()


def test_cli_ingest_rejects_impact_report_outside_root(temp_dir: Path, override_settings) -> None:
    """CLI prevents writing impact report outside the manifest directory."""

    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "sample.txt").write_text("content")

    manifest_path = temp_dir / "manifest.jsonl"
    outside_path = temp_dir.parent / "impact.json"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "run",
            str(docs_dir),
            "--manifest",
            str(manifest_path),
            "--impact-report",
            str(outside_path),
        ],
    )

    assert result.exit_code == 1
    assert not outside_path.exists()
