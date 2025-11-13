#!/usr/bin/env python3
"""Generate RexLit-friendly IDL fixture corpora via Chug.

This script is a *developer tool* that converts a sampled slice of the UCSF
Industry Documents Library (IDL) webdataset into a plain filesystem directory
containing PDFs and a minimal `manifest.jsonl`. RexLit can ingest the output
directory just like any other evidence root.

The script depends on Hugging Face's experimental `chug` loader and is therefore
distributed as part of the optional `dev-idl` extra (`pip install 'rexlit[dev-idl]'`).

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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Tuple, Type

try:
    import chug
    from chug import DataCfg, DataTaskDocReadCfg
except ModuleNotFoundError:  # pragma: no cover - exercised via CLI
    chug = None  # type: ignore[assignment]
    DataCfg = DataTaskDocReadCfg = None  # type: ignore[assignment]

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from idl_fixtures.utils import MANIFEST_FILENAME, filters_help, parse_filter_args, validate_corpus  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from chug import DataCfg as _DataCfgType, DataTaskDocReadCfg as _DataTaskDocReadCfgType
else:
    _DataCfgType = Any
    _DataTaskDocReadCfgType = Any

IDL_DATASET_NAME = "pixparse/idl-wds"


class ChugNotInstalledError(RuntimeError):
    """Raised when chug is not available in the current Python environment."""


@dataclass(frozen=True)
class SampledDocument:
    """In-memory representation of an IDL document prepared for export."""

    doc_id: str
    pdf_bytes: bytes
    page_count: int


def _require_chug() -> Tuple[Type[_DataCfgType], Type[_DataTaskDocReadCfgType]]:  # pragma: no cover - trivial
    """Ensure the chug dependencies are present before continuing."""

    if chug is None or DataCfg is None or DataTaskDocReadCfg is None:
        raise ChugNotInstalledError(
            "Chug is not installed. Install the optional dev dependency group:\n"
            "    pip install 'rexlit[dev-idl]'"
        )
    return DataCfg, DataTaskDocReadCfg


def sample_idl_documents(
    *,
    count: int,
    seed: int,
    filters: Mapping[str, object] | None = None,
) -> Iterator[SampledDocument]:
    """Stream documents from the IDL webdataset via Chug.

    Parameters
    ----------
    count:
        Number of documents to sample. The generator stops once this many
        documents have been yielded even if the dataset contains more.

    seed:
        Random seed fed to Chug's loader configuration to provide reproducible
        sampling.

    filters:
        Optional mapping of filter criteria such as ``page_count_min`` or
        ``page_count_max``. Only a small subset is interpreted directly by this
        helper; call sites may expand it over time as new use cases emerge.
    """

    DataCfgClass, DataTaskDocReadCfgClass = _require_chug()

    task_cfg = DataTaskDocReadCfgClass(page_sampling="all")
    data_cfg = DataCfgClass(
        source=IDL_DATASET_NAME,
        split="train",
        batch_size=None,
        format="hfids",
        num_workers=0,
        seed=seed,
    )

    loader = chug.create_loader(data_cfg, task_cfg)
    sampled = 0
    active_filters = filters or {}

    for sample in loader:
        # Each `sample` is expected to be a mapping with "__key__", "pdf", and "json".
        doc_id = str(sample.get("__key__"))
        if not doc_id:
            continue

        pdf_blob = sample.get("pdf")
        if pdf_blob is None:
            continue
        if isinstance(pdf_blob, bytes):
            pdf_bytes = pdf_blob
        elif hasattr(pdf_blob, "read"):
            pdf_bytes = pdf_blob.read()
        else:
            # Unknown payload type; skip with a warning.
            print(f"[warn] Skipping {doc_id}: unsupported pdf payload {type(pdf_blob)!r}", file=sys.stderr)
            continue

        json_payload = sample.get("json") or {}
        if isinstance(json_payload, Mapping):
            page_count = len(json_payload.get("pages", []))
        else:
            page_count = 0

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
    parser.add_argument("--seed", type=int, default=42, help="RNG seed forwarded to the Chug loader.")
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
    except ChugNotInstalledError as exc:
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

