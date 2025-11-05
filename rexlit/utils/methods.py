"""Helpers for Methods Appendix generation and CLI capture.

These utilities support building a defensible "methods" sidecar that captures:
- Deterministic hash of the input set (from manifest JSONL records)
- Sanitized CLI command history extraction from the audit ledger
- Search activity extraction from the audit ledger
- Dedupe policy description for reproducibility

All helpers are pure and side-effect free; I/O is delegated to ports.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from rexlit.app.ports import LedgerPort, StoragePort
from rexlit.utils.deterministic import compute_input_hash

SENSITIVE_FLAG_KEYS = {
    "--isaacus-api-key",
    "--api-key",
}


def sanitize_argv(argv: Iterable[str]) -> str:
    """Return a sanitized CLI command string with secrets masked.

    Rules:
    - Mask values for flags in SENSITIVE_FLAG_KEYS (e.g., "--isaacus-api-key").
    - Generic handling for "--*key" patterns: mask the next token if present.
    - Preserve original ordering and spacing for transparency.
    """
    items = [str(part) for part in argv]
    sanitized: list[str] = []
    i = 0
    while i < len(items):
        token = items[i]
        sanitized.append(token)
        lower = token.lower()
        flag_lower = lower.split("=", 1)[0]
        if flag_lower.startswith("--"):
            # Mask explicit sensitive flags
            if flag_lower in SENSITIVE_FLAG_KEYS or flag_lower.endswith("key"):
                # If the flag is in the form --flag=value, mask the value inline
                if "=" in token:
                    flag, _sep, _value = token.partition("=")
                    sanitized[-1] = f"{flag}=***"
                else:
                    # Otherwise, if next token exists and looks like a value, mask it
                    if i + 1 < len(items):
                        next_token = items[i + 1]
                        if not next_token.startswith("-"):
                            sanitized.append("***")
                            i += 1
                i += 1
                continue
        i += 1
    return " ".join(sanitized)


def compute_input_set_hash(manifest_path: Path, storage: StoragePort) -> str:
    """Compute deterministic input set hash from a manifest JSONL.

    Uses sorted SHA-256 values if present in records; falls back to path where
    a hash is missing to keep records represented deterministically.
    """
    sha_or_paths: list[str] = []
    for record in storage.read_jsonl(manifest_path):
        sha = str(record.get("sha256") or "").strip()
        if sha:
            sha_or_paths.append(sha)
        else:
            path = str(record.get("path") or "").strip()
            if path:
                sha_or_paths.append(path)
    return compute_input_hash(sha_or_paths)


def extract_command_history(ledger: LedgerPort) -> list[dict[str, Any]]:
    """Extract sanitized CLI invocation history from the audit ledger."""
    try:
        entries = ledger.read_all()
    except Exception:
        return []
    history: list[dict[str, Any]] = []
    for entry in entries:
        try:
            operation = getattr(entry, "operation", None)
            if operation != "cli.invoke":
                continue
            timestamp = getattr(entry, "timestamp", None)
            args_obj = getattr(entry, "args", {})
            args: dict[str, Any] = args_obj if isinstance(args_obj, dict) else {}
            raw = args.get("command_line")
            if raw is None:
                raw = args.get("argv")
            sanitized = ""
            if isinstance(raw, Sequence) and not isinstance(raw, str):
                sanitized = sanitize_argv(raw)
            elif isinstance(raw, str):
                sanitized = raw
            cwd = None
            inputs = getattr(entry, "inputs", [])
            if isinstance(inputs, Sequence) and inputs:
                cwd = str(inputs[0])
            history.append(
                {
                    "timestamp": str(timestamp),
                    "command_line": sanitized,
                    "cwd": cwd,
                }
            )
        except Exception:
            # Defensive: ignore malformed historical entries
            continue
    return history


def extract_search_activity(ledger: LedgerPort) -> list[dict[str, Any]]:
    """Extract index search activity from the audit ledger."""
    try:
        entries = ledger.read_all()
    except Exception:
        return []
    searches: list[dict[str, Any]] = []
    for entry in entries:
        try:
            operation = getattr(entry, "operation", None)
            if operation != "index.search":
                continue
            timestamp = getattr(entry, "timestamp", None)
            args_obj = getattr(entry, "args", {})
            args: dict[str, Any] = args_obj if isinstance(args_obj, dict) else {}
            searches.append(
                {
                    "timestamp": str(timestamp),
                    "query": args.get("query"),
                    "mode": args.get("mode"),
                    "limit": args.get("limit"),
                    "dim": args.get("dim"),
                }
            )
        except Exception:
            continue
    return searches


def format_dedupe_policy() -> dict[str, Any]:
    """Return a human-readable dedupe policy summary used by RexLit."""
    return {
        "policy": "sha256",
        "ordering": "deterministic (sha256, path)",
        "implementation": "HashDeduper",
        "notes": "First occurrence of each SHA-256 kept; ordering stable by hash then path.",
    }
