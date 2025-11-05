"""Unit tests for Methods Appendix helpers and report integration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from rexlit.app.m1_pipeline import PipelineStage
from rexlit.app.report_service import MethodsAppendix, ReportService
from rexlit.utils.methods import (
    compute_input_set_hash,
    extract_command_history,
    extract_search_activity,
    format_dedupe_policy,
    sanitize_argv,
)


class FakeStorage:
    """Minimal storage stub exercising the Methods helpers."""

    def __init__(self, *, records: list[dict[str, object]], file_hash: str) -> None:
        self._records = records
        self._hash = file_hash

    def read_jsonl(self, path: Path):
        yield from self._records

    def compute_hash(self, path: Path) -> str:
        return self._hash

    # Unused methods from the protocol
    def read_text(self, path: Path) -> str:  # pragma: no cover - interface stub
        raise NotImplementedError

    def write_text(self, path: Path, content: str) -> None:  # pragma: no cover - interface stub
        raise NotImplementedError

    def write_jsonl(self, path, records):  # pragma: no cover - interface stub
        raise NotImplementedError

    def list_files(self, directory: Path, pattern: str = "*"):  # pragma: no cover - interface stub
        raise NotImplementedError

    def copy_file(self, src: Path, dst: Path) -> None:  # pragma: no cover - interface stub
        raise NotImplementedError


class FakeLedger:
    """Lightweight ledger stub returning predefined entries."""

    def __init__(
        self,
        *,
        entries: list[SimpleNamespace],
        verification: tuple[bool, str | None] = (True, None),
    ) -> None:
        self._entries = entries
        self._verification = verification

    def verify(self) -> tuple[bool, str | None]:
        return self._verification

    def read_all(self):
        return self._entries

    # Unused protocol method retained for clarity
    def log(self, operation, inputs, outputs, args):  # pragma: no cover - interface stub
        raise NotImplementedError


def test_sanitize_argv_masks_sensitive_flags() -> None:
    argv = [
        "rexlit",
        "ingest",
        "run",
        "--api-key",
        "super-secret",
        "--dense",
        "--isaacus-api-key=abc123",
        "--globalKey",
        "value",
    ]
    sanitized = sanitize_argv(argv)
    assert "--api-key ***" in sanitized
    assert "--isaacus-api-key=***" in sanitized
    assert "--globalKey ***" in sanitized
    assert "super-secret" not in sanitized
    assert "abc123" not in sanitized
    assert "value" not in sanitized


def test_compute_input_set_hash_determinism(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    storage = FakeStorage(
        records=[
            {"sha256": "a" * 64},
            {"path": "fallback.docx"},
            {"sha256": "b" * 64},
        ],
        file_hash="manifest-hash",
    )
    expected_inputs = ["a" * 64, "fallback.docx", "b" * 64]
    expected_hash = hashlib.sha256("\n".join(sorted(expected_inputs)).encode("utf-8")).hexdigest()

    first = compute_input_set_hash(manifest_path, storage)
    second = compute_input_set_hash(manifest_path, storage)
    assert first == second == expected_hash


def test_extract_command_history_parses_cli_invocations() -> None:
    entries = [
        SimpleNamespace(
            timestamp="2024-03-01T00:00:00Z",
            operation="cli.invoke",
            inputs=["/cases/demo"],
            outputs=[],
            args={"argv": ["rexlit", "index", "search", "--api-key", "secret"]},
        ),
        SimpleNamespace(
            timestamp="2024-03-01T01:00:00Z",
            operation="cli.invoke",
            inputs=["/cases/demo"],
            outputs=[],
            args={"command_line": "rexlit report methods manifest.jsonl --output appendix.json"},
        ),
        SimpleNamespace(
            timestamp="2024-03-01T02:00:00Z",
            operation="index.search",
            inputs=[],
            outputs=[],
            args={"query": "privilege"},
        ),
    ]
    ledger = FakeLedger(entries=entries)
    history = extract_command_history(ledger)

    assert len(history) == 2
    assert history[0]["cwd"] == "/cases/demo"
    assert history[0]["command_line"].endswith("***")
    assert "manifest.jsonl" in history[1]["command_line"]
    assert history[1]["timestamp"] == "2024-03-01T01:00:00Z"


def test_extract_search_activity_filters_non_search_events() -> None:
    entries = [
        SimpleNamespace(
            timestamp="2024-04-10T12:34:56Z",
            operation="index.search",
            inputs=[],
            outputs=[],
            args={"query": "project phoenix", "mode": "lexical", "limit": 5, "dim": 512},
        ),
        SimpleNamespace(
            timestamp="2024-04-10T12:35:56Z",
            operation="cli.invoke",
            inputs=["/cases/demo"],
            outputs=[],
            args={"command_line": "rexlit ingest run ./docs"},
        ),
    ]
    ledger = FakeLedger(entries=entries)
    searches = extract_search_activity(ledger)

    assert searches == [
        {
            "timestamp": "2024-04-10T12:34:56Z",
            "query": "project phoenix",
            "mode": "lexical",
            "limit": 5,
            "dim": 512,
        }
    ]


def test_format_dedupe_policy_structure() -> None:
    policy = format_dedupe_policy()
    assert policy["policy"] == "sha256"
    assert "sha256, path" in policy["ordering"]
    assert "HashDeduper" in policy.get("implementation", "")


def test_build_methods_appendix_compiles_inputs_and_audit_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    storage = FakeStorage(
        records=[
            {"sha256": "a" * 64, "path": "/docs/doc1.pdf"},
            {"sha256": "b" * 64, "path": "/docs/doc2.pdf"},
        ],
        file_hash="deadbeef" * 8,
    )
    entries = [
        SimpleNamespace(
            timestamp="2024-05-01T09:00:00Z",
            operation="cli.invoke",
            inputs=[str(tmp_path)],
            outputs=[],
            args={"command_line": "rexlit ingest run ./docs"},
            entry_hash="hash1",
        ),
        SimpleNamespace(
            timestamp="2024-05-01T09:10:00Z",
            operation="index.search",
            inputs=[],
            outputs=[],
            args={"query": "sanctions", "mode": "lexical", "limit": 10, "dim": 768},
            entry_hash="hash2",
        ),
    ]
    ledger = FakeLedger(entries=entries)
    stages = [
        PipelineStage(name="discover", status="completed", duration_seconds=1.5, detail="ok"),
    ]

    service = ReportService(storage_port=storage, ledger_port=ledger)
    appendix = service.build_methods_appendix(manifest_path, stages=stages)

    assert isinstance(appendix, MethodsAppendix)
    assert appendix.manifest_path == str(manifest_path.resolve())
    assert appendix.manifest_content_hash == "deadbeef" * 8
    assert appendix.command_history
    assert appendix.command_history[0]["command_line"].startswith("rexlit ingest run")
    assert appendix.search_activity[0]["query"] == "sanctions"
    assert appendix.dedupe["policy"] == "sha256"
    assert appendix.discovery["root"] == str(manifest_path.resolve().parent)
    assert appendix.audit["entry_count"] == 2
    assert appendix.audit["tip_hash"] == "hash2"
    assert appendix.pipeline_stages and appendix.pipeline_stages[0]["name"] == "discover"
