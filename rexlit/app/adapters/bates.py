"""Bates numbering planner adapters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from rexlit.app.ports import BatesAssignment, BatesPlan, BatesPlannerPort, DocumentRecord
from rexlit.config import Settings
from rexlit.utils.deterministic import deterministic_order_documents
from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.jsonl import atomic_write_jsonl


class SequentialBatesPlanner(BatesPlannerPort):
    """Assign sequential Bates IDs and persist the plan as JSONL."""

    def __init__(self, settings: Settings, prefix: str = "RXL") -> None:
        self._settings = settings
        self._prefix = prefix
        self.last_plan_path: Path | None = None

    def plan(self, documents: Iterable[DocumentRecord]) -> BatesPlan:
        sorted_docs = deterministic_order_documents(documents)

        bates_dir = self._settings.get_data_dir() / "bates"
        bates_dir.mkdir(parents=True, exist_ok=True)

        plan_path = bates_dir / "bates_plan.jsonl"

        seen_paths: set[Path] = set()
        seen_hashes: set[str] = set()
        seen_bates_ids: set[str] = set()

        entries: list[BatesAssignment] = []

        for index, document in enumerate(sorted_docs, start=1):
            doc_path = Path(document.path)
            if not doc_path.exists():
                raise FileNotFoundError(f"Bates planning source is missing: {document.path}")

            resolved = doc_path.resolve()
            if resolved in seen_paths:
                raise ValueError(f"Duplicate document path during Bates planning: {resolved}")
            seen_paths.add(resolved)

            expected_hash = document.sha256
            if expected_hash in seen_hashes:
                raise ValueError(
                    f"Duplicate SHA-256 detected during Bates planning: {expected_hash}"
                )
            seen_hashes.add(expected_hash)

            current_hash = compute_sha256_file(resolved)
            if current_hash != expected_hash:
                raise ValueError(
                    "Document hash mismatch detected during Bates planning for "
                    f"{resolved}. Expected {expected_hash}, computed {current_hash}."
                )

            bates_id = f"{self._prefix}-{index:06d}"
            if bates_id in seen_bates_ids:
                raise ValueError(f"Bates identifier collision detected: {bates_id}")
            seen_bates_ids.add(bates_id)

            entry = BatesAssignment(
                document=document.path,
                sha256=expected_hash,
                bates_id=bates_id,
            )
            entries.append(entry)

        atomic_write_jsonl(
            plan_path,
            (entry.model_dump() for entry in entries),
            schema_id="bates_map",
            schema_version=1,
        )

        self.last_plan_path = plan_path
        return BatesPlan(path=plan_path, assignments=entries)
