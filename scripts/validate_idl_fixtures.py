#!/usr/bin/env python3
"""Validate RexLit IDL fixture corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

MANIFEST_FILENAME = "manifest.jsonl"


def validate_corpus(corpus_dir: Path) -> list[str]:
    """Validate manifest integrity and referenced PDFs within ``corpus_dir``."""

    manifest_path = corpus_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return [f"Manifest not found: {manifest_path}"]

    errors: list[str] = []
    with manifest_path.open(encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{manifest_path}:{line_num} invalid JSON - {exc}")
                continue

            filepath = record.get("filepath")
            if not filepath:
                errors.append(f"{manifest_path}:{line_num} missing 'filepath'")
                continue

            sha256 = record.get("sha256")
            doc_path = corpus_dir / filepath
            if not doc_path.exists():
                errors.append(f"{manifest_path}:{line_num} file missing - {doc_path}")
                continue

            if sha256:
                actual_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
                if actual_hash != sha256:
                    errors.append(
                        f"{manifest_path}:{line_num} checksum mismatch for {filepath} "
                        f"(expected {sha256}, got {actual_hash})"
                    )
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate RexLit IDL fixture corpora.")
    parser.add_argument(
        "corpus",
        nargs="+",
        type=Path,
        help="One or more directories containing an IDL manifest and docs/",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success output and only print validation errors.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    overall_errors: list[str] = []
    for corpus_dir in args.corpus:
        errors = validate_corpus(corpus_dir)
        if errors:
            overall_errors.extend(errors)
            for error in errors:
                print(f"[FAIL] {error}", file=sys.stderr)
        elif not args.quiet:
            print(f"[OK] {corpus_dir} validated successfully")

    return 1 if overall_errors else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

