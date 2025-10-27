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
    assert audit_entry["operation"] == "ingest"
    assert audit_entry["inputs"] == [str(docs_dir)]
    assert len(audit_entry["outputs"]) == 1
