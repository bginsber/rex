"""CLI smoke test for redaction plan/apply commands."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import]
from typer.testing import CliRunner

from rexlit.cli import app

runner = CliRunner()


def _make_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "SSN: 123-45-6789", fontsize=12)
    page.insert_text((100, 120), "Email: cli@example.com", fontsize=12)
    doc.save(str(path))
    doc.close()


def _extract_text(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def test_cli_plan_apply_smoke(tmp_path: Path) -> None:
    """End-to-end smoke coverage for CLI redaction commands."""

    pdf_path = tmp_path / "sensitive.pdf"
    plan_path = tmp_path / "plan.enc"
    output_dir = tmp_path / "redacted"
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"

    _make_pdf(pdf_path)

    env = {
        "REXLIT_DATA_DIR": str(data_dir),
        "REXLIT_CONFIG_DIR": str(config_dir),
    }

    plan_result = runner.invoke(
        app,
        [
            "redaction",
            "plan",
            str(pdf_path),
            "--output",
            str(plan_path),
            "--pii-types",
            "SSN,EMAIL",
        ],
        env=env,
    )
    assert plan_result.exit_code == 0, plan_result.stdout
    assert plan_path.exists()

    apply_result = runner.invoke(
        app,
        [
            "redaction",
            "apply",
            str(plan_path),
            str(output_dir),
        ],
        env=env,
    )
    assert apply_result.exit_code == 0, apply_result.stdout
    redacted_pdf = output_dir / pdf_path.name
    assert redacted_pdf.exists()
    text = _extract_text(redacted_pdf)
    assert "123-45-6789" not in text
    assert "cli@example.com" not in text
