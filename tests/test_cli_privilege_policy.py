"""Tests for `rexlit privilege policy` management commands."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from rexlit.cli import app

POLICY_TEXT = (
    dedent(
        """
        # Stage Policy Template

        ```json
        {
          "labels": ["PRIVILEGED:ACP"],
          "confidence": 0.95,
          "rationale": "Policy-based explanation."
        }
        ```

        Confidence scoring descriptions and classification labels are documented here.
        """
    ).strip()
    + "\n"
)


def _override_path(settings, stage: int) -> Path:
    return settings.get_config_dir() / "policies" / f"privilege_stage{stage}.txt"


def test_privilege_policy_apply_and_show(override_settings) -> None:
    """Applying a policy from file stores it in config overrides and shows metadata."""

    settings = override_settings
    source = settings.get_config_dir() / "policy_source.txt"
    source.write_text(POLICY_TEXT, encoding="utf-8")

    runner = CliRunner()

    apply_result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "apply",
            "--stage",
            "1",
            "--file",
            str(source),
            "--json",
        ],
    )
    assert apply_result.exit_code == 0, apply_result.stdout

    metadata = json.loads(apply_result.stdout)
    target_path = _override_path(settings, 1)
    assert metadata["path"] == str(target_path)
    assert metadata["source"] == "override"
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8") == POLICY_TEXT

    show_result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "show",
            "--stage",
            "1",
            "--json",
        ],
    )
    assert show_result.exit_code == 0, show_result.stdout
    show_payload = json.loads(show_result.stdout)
    assert show_payload["text"] == POLICY_TEXT
    assert show_payload["source"] == "override"

    list_result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "list",
            "--json",
        ],
    )
    assert list_result.exit_code == 0, list_result.stdout
    list_payload = json.loads(list_result.stdout)
    stage1 = next(item for item in list_payload if item["stage"] == 1)
    assert stage1["source"] == "override"
    assert stage1["path"] == str(target_path)


def test_privilege_policy_apply_from_stdin(override_settings) -> None:
    """Applying policy content from STDIN writes to the override path."""

    settings = override_settings
    stdin_text = POLICY_TEXT.replace("0.95", "0.85")

    runner = CliRunner()
    apply_result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "apply",
            "--stage",
            "2",
            "--stdin",
            "--json",
        ],
        input=stdin_text,
    )
    assert apply_result.exit_code == 0, apply_result.stdout

    metadata = json.loads(apply_result.stdout)
    target_path = _override_path(settings, 2)
    assert metadata["path"] == str(target_path)
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8") == (
        stdin_text if stdin_text.endswith("\n") else stdin_text + "\n"
    )


def test_privilege_policy_diff_identical(override_settings) -> None:
    """Diff reports identical policies when comparing the same file."""

    settings = override_settings
    source = settings.get_config_dir() / "policy_diff.txt"
    source.write_text(POLICY_TEXT, encoding="utf-8")

    runner = CliRunner()
    runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "apply",
            "--stage",
            "1",
            "--file",
            str(source),
        ],
    )

    diff_result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "diff",
            "--stage",
            "1",
            str(source),
        ],
    )
    assert diff_result.exit_code == 0, diff_result.stdout
    assert "Policies are identical." in diff_result.stdout


def test_privilege_policy_apply_rejects_path_outside_root(override_settings, temp_dir: Path) -> None:
    """Path traversal guard rejects sources outside allowed roots."""

    settings = override_settings
    forbidden_source = temp_dir / "forbidden_policy.txt"
    forbidden_source.write_text(POLICY_TEXT, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "apply",
            "--stage",
            "1",
            "--file",
            str(forbidden_source),
        ],
    )

    assert result.exit_code != 0
    assert "Path traversal detected" in result.stderr
    assert not _override_path(settings, 1).exists()


def test_privilege_policy_validate_reports_errors(override_settings) -> None:
    """Validation emits errors for malformed policies."""

    settings = override_settings
    malformed_text = "This template is missing required JSON documentation.\n"
    target_path = _override_path(settings, 3)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(malformed_text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "privilege",
            "policy",
            "validate",
            "--stage",
            "3",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout

    payload = json.loads(result.stdout)
    assert not payload["passed"]
    assert payload["errors"]

