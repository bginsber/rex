"""M1 pipeline orchestration built on application ports."""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from rexlit.app.ports import (
    BatesPlan,
    BatesPlannerPort,
    DeduperPort,
    DiscoveryPort,
    DocumentRecord,
    LedgerPort,
    OCRPort,
    PackPort,
    PIIPort,
    RedactionPlannerPort,
    StoragePort,
)
from rexlit.config import Settings
from rexlit.utils.deterministic import deterministic_order_documents
from rexlit.utils.jsonl import atomic_write_jsonl
from rexlit.utils.offline import OfflineModeGate
from rexlit.utils.plans import validate_redaction_plan_file

StageStatus = Literal["pending", "completed", "skipped", "failed"]


@dataclass(slots=True)
class PipelineStage:
    """Represents the status of a pipeline phase."""

    name: str
    status: StageStatus = "pending"
    detail: str | None = None
    duration_seconds: float | None = None
    metrics: dict[str, Any] | None = None


class M1PipelineResult(BaseModel):
    """Summary of an M1 pipeline run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    documents: list[DocumentRecord] = Field(default_factory=list)
    manifest_path: Path
    redaction_plan_paths: dict[str, Path] = Field(default_factory=dict)
    redaction_plan_ids: dict[str, str] = Field(default_factory=dict)
    bates_plan_path: Path | None = None
    pack_path: Path | None = None
    stages: list[PipelineStage] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class M1Pipeline:
    """Orchestrate ingest → plan → package without direct I/O."""

    def __init__(
        self,
        *,
        settings: Settings,
        discovery_port: DiscoveryPort,
        storage_port: StoragePort,
        redaction_planner: RedactionPlannerPort,
        bates_planner: BatesPlannerPort,
        pack_port: PackPort,
        offline_gate: OfflineModeGate,
        ocr_port: OCRPort | None = None,
        pii_port: PIIPort | None = None,
        deduper_port: DeduperPort | None = None,
        ledger_port: LedgerPort | None = None,
    ) -> None:
        self._settings = settings
        self._discovery = discovery_port
        self._storage = storage_port
        self._redaction_planner = redaction_planner
        self._bates_planner = bates_planner
        self._packager = pack_port
        self._offline_gate = offline_gate
        self._ocr = ocr_port
        self._pii = pii_port
        self._deduper = deduper_port
        self._ledger = ledger_port

    @contextmanager
    def _stage(
        self,
        stages: list[PipelineStage],
        name: str,
    ) -> Iterator[PipelineStage]:
        """Context manager to standardize pipeline stage error handling."""

        stage = PipelineStage(name=name)
        stages.append(stage)
        start_time = time.monotonic()
        try:
            yield stage
        except Exception as exc:  # pragma: no cover - surfaced to caller
            stage.status = "failed"
            stage.detail = str(exc)
            raise
        else:
            if stage.status == "pending":
                stage.status = "completed"
        finally:
            stage.duration_seconds = time.monotonic() - start_time

    def run(
        self,
        source: Path,
        *,
        manifest_path: Path | None = None,
        recursive: bool = True,
        include_extensions: set[str] | None = None,
        exclude_extensions: set[str] | None = None,
    ) -> M1PipelineResult:
        """Execute the M1 pipeline."""

        if not source.exists():
            raise FileNotFoundError(f"Source path not found: {source}")

        resolved_source = source.resolve()
        manifest = (
            manifest_path.resolve()
            if manifest_path is not None
            else self._default_manifest_path(resolved_source)
        )
        manifest.parent.mkdir(parents=True, exist_ok=True)

        stages: list[PipelineStage] = []
        notes: list[str] = []

        self._guard_online_adapter(self._ocr, feature="OCR processing")
        self._guard_online_adapter(self._pii, feature="PII detection")

        discovered = self._run_discovery(
            resolved_source,
            stages,
            recursive=recursive,
            include_extensions=include_extensions,
            exclude_extensions=exclude_extensions,
        )

        unique_docs = self._run_dedupe(discovered, stages)

        redaction_plan_paths, redaction_plan_ids = self._run_redaction_planning(unique_docs, stages)

        bates_plan = self._run_bates(unique_docs, stages)

        self._write_manifest(manifest, unique_docs, stages)

        pack_path = self._run_pack(manifest.parent, stages)

        notes.append(f"Manifest written to {manifest}")
        if bates_plan is not None:
            notes.append(f"Bates plan stored at {bates_plan.path}")
        if pack_path is not None:
            notes.append(f"Pack archive created at {pack_path}")

        plan_metadata = [
            {
                "document": document,
                "plan_path": str(redaction_plan_paths[document]),
                "plan_id": redaction_plan_ids[document],
            }
            for document in sorted(redaction_plan_paths)
        ]

        self._log_audit(
            source=resolved_source,
            manifest_path=manifest,
            redaction_plans=plan_metadata,
            bates_plan=bates_plan,
            pack_path=pack_path,
            document_count=len(unique_docs),
        )

        return M1PipelineResult(
            documents=unique_docs,
            manifest_path=manifest,
            redaction_plan_paths=redaction_plan_paths,
            redaction_plan_ids=redaction_plan_ids,
            bates_plan_path=bates_plan.path if bates_plan else None,
            pack_path=pack_path,
            stages=stages,
            notes=notes,
        )

    # ------------------------------------------------------------------#
    # Internal helpers
    # ------------------------------------------------------------------#

    def _default_manifest_path(self, source: Path) -> Path:
        if source.is_dir():
            return source / "manifest.jsonl"
        return source.parent / "manifest.jsonl"

    def _run_discovery(
        self,
        source: Path,
        stages: list[PipelineStage],
        *,
        recursive: bool,
        include_extensions: set[str] | None,
        exclude_extensions: set[str] | None,
    ) -> Iterable[DocumentRecord]:
        with self._stage(stages, "discover") as stage:  # type: PipelineStage
            count = 0
            stage.detail = "Streaming discovery..."

            def stream() -> Iterator[DocumentRecord]:
                nonlocal count
                try:
                    for record in self._discovery.discover(
                        source,
                        recursive=recursive,
                        include_extensions=include_extensions,
                        exclude_extensions=exclude_extensions,
                    ):
                        count += 1
                        yield record
                finally:
                    stage.detail = f"{count} documents discovered"
                    stage.metrics = {"discovered_count": count}

            return stream()

    def _run_dedupe(
        self,
        documents: Iterable[DocumentRecord],
        stages: list[PipelineStage],
    ) -> list[DocumentRecord]:
        with self._stage(stages, "dedupe") as stage:  # type: PipelineStage
            docs = deterministic_order_documents(list(documents))

            if not docs:
                stage.status = "skipped"
                stage.detail = "No documents to dedupe"
                return docs

            if self._deduper is None:
                duplicates = self._detect_duplicate_hashes(docs)
                if duplicates:
                    stage.status = "failed"
                    stage.detail = f"Duplicate SHA-256 detected: {', '.join(sorted(duplicates))}"
                    raise ValueError(stage.detail)

                stage.status = "skipped"
                stage.detail = "Deduper unavailable; all hashes unique"
                return docs

            deduped = list(self._deduper.dedupe(docs))
            stage.detail = f"{len(deduped)} unique documents"
            return deduped

    def _run_redaction_planning(
        self,
        documents: Iterable[DocumentRecord],
        stages: list[PipelineStage],
    ) -> tuple[dict[str, Path], dict[str, str]]:
        with self._stage(stages, "redaction_plan") as stage:  # type: PipelineStage
            plans: dict[str, Path] = {}
            fingerprints: dict[str, str] = {}
            count = 0
            plan_key = self._settings.get_redaction_plan_key()

            for record in documents:
                document_path = Path(record.path)
                plan_path = self._redaction_planner.plan(document_path)
                plan_id = validate_redaction_plan_file(
                    plan_path,
                    document_path=document_path,
                    content_hash=record.sha256,
                    key=plan_key,
                )
                plans[record.path] = plan_path
                fingerprints[record.path] = plan_id
                count += 1

            stage.detail = f"{count} plans generated"
        return plans, fingerprints

    def _run_bates(
        self,
        documents: Iterable[DocumentRecord],
        stages: list[PipelineStage],
    ) -> BatesPlan | None:
        with self._stage(stages, "bates_plan") as stage:  # type: PipelineStage
            docs = list(documents)
            if not docs:
                stage.status = "skipped"
                stage.detail = "No documents available for Bates numbering"
                return None

            plan = self._bates_planner.plan(docs)
            stage.detail = f"{len(plan.assignments)} Bates assignments"
            return plan

    def _write_manifest(
        self,
        manifest_path: Path,
        documents: Iterable[DocumentRecord],
        stages: list[PipelineStage],
    ) -> None:
        with self._stage(stages, "manifest") as stage:  # type: PipelineStage
            atomic_write_jsonl(
                manifest_path,
                (record.model_dump(mode="json") for record in documents),
                schema_id="manifest",
                schema_version=1,
            )
            stage.detail = f"Manifest stored at {manifest_path}"

    def _run_pack(
        self,
        artifact_dir: Path,
        stages: list[PipelineStage],
    ) -> Path | None:
        with self._stage(stages, "pack") as stage:  # type: PipelineStage
            if not artifact_dir.exists():
                stage.status = "skipped"
                stage.detail = "Artifact directory missing; skip packaging"
                return None

            destination = self._packager.pack(artifact_dir)
            stage.detail = f"Pack archive stored at {destination}"
            return destination

    def _detect_duplicate_hashes(self, documents: Iterable[DocumentRecord]) -> set[str]:
        duplicates: set[str] = set()
        encountered: set[str] = set()

        for record in documents:
            if record.sha256 in encountered:
                duplicates.add(record.sha256)
            encountered.add(record.sha256)

        return duplicates

    def _log_audit(
        self,
        *,
        source: Path,
        manifest_path: Path,
        redaction_plans: list[dict[str, str]],
        bates_plan: BatesPlan | None,
        pack_path: Path | None,
        document_count: int,
    ) -> None:
        if self._ledger is None:
            return

        outputs = [str(manifest_path)]
        outputs.extend(plan["plan_path"] for plan in redaction_plans)
        if bates_plan is not None:
            outputs.append(str(bates_plan.path))
        if pack_path is not None:
            outputs.append(str(pack_path))

        args = {
            "document_count": document_count,
            "executed_at": datetime.now(UTC).isoformat(),
            "online_mode": self._settings.online,
            "redaction_plans": redaction_plans,
        }

        self._ledger.log(
            operation="m1_pipeline",
            inputs=[str(source)],
            outputs=outputs,
            args=args,
        )

    def _guard_online_adapter(self, adapter: Any, *, feature: str) -> None:
        if adapter is None:
            return

        requires_online = False
        if hasattr(adapter, "is_online"):
            requires_online = bool(cast(Any, adapter).is_online())
        elif hasattr(adapter, "requires_online"):
            requires_online = bool(cast(Any, adapter).requires_online())

        self._offline_gate.ensure_supported(feature=feature, requires_online=requires_online)
