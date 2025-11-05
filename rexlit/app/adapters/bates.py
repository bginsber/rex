"""Bates numbering planner adapters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rexlit.app.ports import BatesAssignment, BatesPlan, BatesPlannerPort, DocumentRecord
from rexlit.config import Settings
from rexlit.utils.deterministic import deterministic_order_documents
from rexlit.utils.hashing import compute_sha256_file
from rexlit.utils.jsonl import atomic_write_jsonl


class SequentialBatesPlanner(BatesPlannerPort):
    """Assign sequential Bates IDs and persist the plan as JSONL."""

    def __init__(self, settings: Settings, prefix: str = "RXL", width: int = 6) -> None:
        self._settings = settings
        self._prefix = prefix
        self._width = max(1, width)
        self.last_plan_path: Path | None = None

    def plan(
        self,
        documents: Iterable[DocumentRecord],
        *,
        prefix: str | None = None,
        width: int | None = None,
    ) -> BatesPlan:
        sorted_docs = deterministic_order_documents(documents)

        active_prefix = prefix or self._prefix
        active_width = max(1, width or self._width)

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

            bates_id = self._format_bates(active_prefix, index, active_width, separator="-")
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
        return BatesPlan(path=plan_path, assignments=entries, prefix=active_prefix, width=active_width)

    def plan_with_families(
        self,
        documents: Iterable[DocumentRecord],
        *,
        prefix: str,
        width: int,
        separator: str = "-",
    ) -> dict[str, Any]:
        docs = deterministic_order_documents(list(documents))

        families: dict[str, list[DocumentRecord]] = {}
        for record in docs:
            family_id = self._resolve_family_id(record)
            families.setdefault(family_id, []).append(record)

        for family_id, members in families.items():
            families[family_id] = deterministic_order_documents(members)

        ordered_family_ids = sorted(families.keys())

        counter = 1
        bates_map: dict[str, str] = {}
        ordered_documents: list[dict[str, Any]] = []

        for family_id in ordered_family_ids:
            for record in families[family_id]:
                bates_label = self._format_bates(prefix, counter, width, separator=separator)
                bates_map[record.sha256] = bates_label
                ordered_documents.append(
                    {
                        "path": record.path,
                        "sha256": record.sha256,
                        "family_id": family_id,
                        "label": bates_label,
                    }
                )
                counter += 1

        return {
            "prefix": prefix,
            "width": width,
            "total_documents": len(docs),
            "families": {family_id: len(members) for family_id, members in families.items()},
            "bates_map": bates_map,
            "ordered_documents": ordered_documents,
        }

    def _format_bates(
        self, prefix: str, number: int, width: int, *, separator: str = "-"
    ) -> str:
        digits = max(1, width)
        numeric = f"{number:0{digits}d}"
        if separator:
            return f"{prefix}{separator}{numeric}"
        return f"{prefix}{numeric}"

    def _resolve_family_id(self, record: DocumentRecord) -> str:
        metadata: dict[str, object] = {}
        metadata_attr = record.metadata if hasattr(record, "metadata") else None
        if isinstance(metadata_attr, dict):
            metadata = metadata_attr

        for key in ("thread_id", "family_id", "conversation_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value

        inferred = record.family_id if hasattr(record, "family_id") else None
        if isinstance(inferred, str) and inferred.strip():
            return inferred

        return record.sha256
