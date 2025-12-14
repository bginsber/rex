#!/usr/bin/env python3
"""Generate RexLit-friendly IDL fixture corpora via the Hugging Face dataset API.

This script is a *developer tool* that converts a sampled slice of the UCSF
Industry Documents Library (IDL) webdataset into a plain filesystem directory
containing PDFs and a minimal `manifest.jsonl`. RexLit can ingest the output
directory just like any other evidence root.

The script relies on the standard Hugging Face tooling (``datasets`` +
``huggingface_hub``). Install them with:

    uv tool install huggingface_hub
    uv tool run python -m pip install datasets

or via pip:

    pip install --upgrade huggingface_hub datasets

Example usage:
    python scripts/dev/idl_sample_docs.py \
        --tier small \
        --count 100 \
        --seed 42 \
        --output /tmp/rexlit-idl/small \
        --validate

    python scripts/dev/idl_sample_docs.py \
        --tier edge-cases \
        --count 50 \
        --filter page_count_min=10 \
        --output ./rexlit/docs/idl-fixtures/edge-cases/long-form
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from datasets import IterableDataset, load_dataset
except ModuleNotFoundError:  # pragma: no cover - exercised via CLI
    IterableDataset = None  # type: ignore[assignment]
    load_dataset = None  # type: ignore[assignment]

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from idl_fixtures.utils import (  # noqa: E402
    MANIFEST_FILENAME,
    filters_help,
    parse_filter_args,
    validate_corpus,
)

IDL_DATASET_NAME = "pixparse/idl-wds"


class HuggingFaceToolsMissingError(RuntimeError):
    """Raised when Hugging Face's dataset tooling is unavailable."""


@dataclass(frozen=True)
class SampledDocument:
    """In-memory representation of an IDL document prepared for export."""

    doc_id: str
    pdf_bytes: bytes
    page_count: int


def _require_dataset_loader() -> Any:  # pragma: no cover - trivial
    """Ensure the Hugging Face dataset tooling is present before continuing."""

    if load_dataset is None:
        raise HuggingFaceToolsMissingError(
            "Hugging Face tools are not installed. Install them with:\n"
            "    uv tool install huggingface_hub && uv tool run python -m pip install datasets\n"
            "or:\n"
            "    pip install --upgrade huggingface_hub datasets"
        )
    return load_dataset


def _extract_pdf_bytes(pdf_payload: Any) -> bytes | None:
    """Normalize the Hugging Face payload into raw PDF bytes."""

    if pdf_payload is None:
        return None

    if isinstance(pdf_payload, (bytes, bytearray)):
        return bytes(pdf_payload)

    if isinstance(pdf_payload, str):
        candidate = Path(pdf_payload)
        if candidate.exists():
            return candidate.read_bytes()
        return None

    if isinstance(pdf_payload, Mapping):
        if "bytes" in pdf_payload and isinstance(pdf_payload["bytes"], (bytes, bytearray)):
            return bytes(pdf_payload["bytes"])
        if "path" in pdf_payload:
            candidate = Path(str(pdf_payload["path"]))
            if candidate.exists():
                return candidate.read_bytes()

    if hasattr(pdf_payload, "read"):
        return pdf_payload.read()

    return None


def _extract_page_count(json_payload: Any) -> int:
    """Pull the page count from the JSON sidecar payload."""

    if isinstance(json_payload, Mapping):
        pages = json_payload.get("pages")
        if isinstance(pages, list):
            return len(pages)

    if isinstance(json_payload, str):
        try:
            parsed = json.loads(json_payload)
        except json.JSONDecodeError:
            return 0
        return _extract_page_count(parsed)

    return 0


def sample_idl_documents(
    *,
    count: int,
    seed: int,
    filters: Mapping[str, object] | None = None,
) -> Iterator[SampledDocument]:
    """Stream documents from the IDL webdataset via the Hugging Face dataset API.

    Parameters
    ----------
    count:
        Number of documents to sample. The generator stops once this many
        documents have been yielded even if the dataset contains more.

    seed:
        Random seed fed to the Hugging Face iterable dataset shuffler so runs
        remain reproducible.

    filters:
        Optional mapping of filter criteria such as ``page_count_min`` or
        ``page_count_max``. Only a small subset is interpreted directly by this
        helper; call sites may expand it over time as new use cases emerge.
    """

    load_dataset_fn = _require_dataset_loader()
    dataset = load_dataset_fn(IDL_DATASET_NAME, split="train", streaming=True)

    if IterableDataset is not None and isinstance(dataset, IterableDataset):
        loader: Iterable[Mapping[str, Any]] = dataset.shuffle(seed=seed, buffer_size=10_000)
    else:  # pragma: no cover - defensive
        loader = dataset
    sampled = 0
    active_filters = filters or {}

    for sample in loader:
        # Each `sample` is expected to be a mapping with "__key__", "pdf", and "json".
        doc_id = str(sample.get("__key__"))
        if not doc_id:
            continue

        pdf_bytes = _extract_pdf_bytes(sample.get("pdf"))
        if pdf_bytes is None:
            print(f"[warn] Skipping {doc_id}: missing pdf payload", file=sys.stderr)
            continue

        json_payload = sample.get("json") or {}
        page_count = _extract_page_count(json_payload)

        if not _passes_filters(page_count=page_count, filters=active_filters):
            continue

        yield SampledDocument(doc_id=doc_id, pdf_bytes=pdf_bytes, page_count=page_count)
        sampled += 1

        if sampled >= count:
            break


def _passes_filters(*, page_count: int, filters: Mapping[str, object]) -> bool:
    """Evaluate whether a sample satisfies the supported filter clauses."""

    min_pages = filters.get("page_count_min")
    if isinstance(min_pages, (int, float)) and page_count < int(min_pages):
        return False

    max_pages = filters.get("page_count_max")
    if isinstance(max_pages, (int, float)) and page_count > int(max_pages):
        return False

    return True


def export_corpus(documents: Iterable[SampledDocument], output_dir: Path) -> int:
    """Write sampled documents and a minimal manifest to ``output_dir``."""

    docs_dir = output_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_FILENAME

    count = 0
    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        for document in documents:
            pdf_path = docs_dir / f"{document.doc_id}.pdf"
            pdf_path.write_bytes(document.pdf_bytes)

            sha256 = hashlib.sha256(document.pdf_bytes).hexdigest()
            record = {
                "schema_version": "1.0",
                "doc_id": document.doc_id,
                "filepath": f"docs/{document.doc_id}.pdf",
                "sha256": sha256,
                "file_size": len(document.pdf_bytes),
                "page_count": document.page_count,
                "idl_url": f"https://www.industrydocuments.ucsf.edu/docs/{document.doc_id}",
            }
            manifest_file.write(json.dumps(record))
            manifest_file.write("\n")
            count += 1

    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate IDL fixture corpora for RexLit.")
    parser.add_argument("--tier", required=True, help="Corpus tier name (small, medium, large, xl, edge-cases).")
    parser.add_argument("--count", required=True, type=int, help="Number of documents to sample.")
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed forwarded to the Hugging Face iterable dataset shuffler.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Directory to write the exported corpus into.")
    parser.add_argument(
        "--filter",
        action="append",
        dest="filters",
        help=f"Optional sampling filters defined as key=value pairs ({filters_help()}).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the generated corpus after export.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - exercised via CLI
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        parsed_filters = parse_filter_args(args.filters)
    except ValueError as exc:
        parser.error(str(exc))

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        documents = sample_idl_documents(count=args.count, seed=args.seed, filters=parsed_filters)
        written = export_corpus(documents, output_dir)
    except HuggingFaceToolsMissingError as exc:
        parser.error(str(exc))
        return 2

    print(f"✓ Exported {written} documents to {output_dir}")
    print(f"  PDFs: {output_dir / 'docs'}")
    print(f"  Manifest: {output_dir / MANIFEST_FILENAME}")

    if args.validate:
        errors = validate_corpus(output_dir)
        if errors:
            print("✗ Validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print("✓ Corpus validated successfully")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
