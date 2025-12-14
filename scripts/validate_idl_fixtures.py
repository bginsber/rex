#!/usr/bin/env python3
"""Validate RexLit IDL fixture corpora."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
DEV_DIR = SCRIPT_ROOT / "dev"
if str(DEV_DIR) not in sys.path:
    sys.path.insert(0, str(DEV_DIR))

from idl_fixtures.utils import validate_corpus  # noqa: E402


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

