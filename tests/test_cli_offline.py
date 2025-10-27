from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from rexlit.cli import app


def test_cli_offline_dense_build_refuses(temp_dir: Path) -> None:
    # Prepare a simple docs directory
    docs = temp_dir / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello")

    runner = CliRunner()
    # Omit --online; pass --data-dir to isolate settings
    result = runner.invoke(
        app, ["--data-dir", str(temp_dir / "data"), "index", "build", str(docs), "--dense"]
    )  # fmt: off
    assert result.exit_code == 2
    assert "requires online mode" in result.stdout.lower()


def test_cli_offline_hybrid_search_refuses(temp_dir: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app, ["--data-dir", str(temp_dir / "data"), "index", "search", "q", "--mode", "hybrid"]
    )  # fmt: off
    assert result.exit_code == 2
    assert "requires online mode" in result.stdout.lower()
