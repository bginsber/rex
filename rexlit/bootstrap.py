"""Application bootstrap wiring ports, adapters, and services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rexlit.app import M1Pipeline, PackService, RedactionService, ReportService
from rexlit.app.adapters import (
    FileSystemStorageAdapter,
    HashDeduper,
    IngestDiscoveryAdapter,
    JSONLineRedactionPlanner,
    SequentialBatesPlanner,
    ZipPackager,
)
from rexlit.app.audit_service import AuditService
from rexlit.app.ports import (
    BatesPlannerPort,
    DeduperPort,
    DiscoveryPort,
    IndexPort,
    LedgerPort,
    PackPort,
    RedactionPlannerPort,
    StoragePort,
)
from rexlit.audit.ledger import AuditLedger
from rexlit.config import Settings, get_settings
from rexlit.index.build import build_dense_index, build_index
from rexlit.index.search import (
    SearchResult as TantivySearchResult,
    dense_search_index,
    get_custodians as load_custodians,
    get_doctypes as load_doctypes,
)
from rexlit.utils.offline import OfflineModeGate


@dataclass(slots=True)
class ApplicationContainer:
    """Aggregates wired services and adapters for the CLI layer."""

    settings: Settings
    pipeline: M1Pipeline
    report_service: ReportService
    redaction_service: RedactionService
    pack_service: PackService
    audit_service: AuditService
    ledger_port: LedgerPort
    storage_port: StoragePort
    discovery_port: DiscoveryPort
    deduper_port: DeduperPort | None
    redaction_planner: RedactionPlannerPort
    bates_planner: BatesPlannerPort
    pack_port: PackPort
    index_port: IndexPort
    offline_gate: OfflineModeGate


class NoOpLedger:
    """Ledger implementation that drops all writes."""

    def log(self, *args: Any, **kwargs: Any) -> None:
        return None

    def append(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - compatibility alias
        return None

    def read_all(self) -> list[Any]:
        return []

    def verify(self) -> bool:
        return True


class StubIndexAdapter(IndexPort):
    """Placeholder index adapter used until Tantivy wiring lands."""

    def add_document(self, path: str, text: str, metadata: dict) -> None:  # pragma: no cover - stub
        raise RuntimeError("Search indexing not yet implemented for offline bootstrap.")

    def search(self, query: str, *, limit: int = 10, filters: dict | None = None):
        raise RuntimeError("Search indexing not yet implemented for offline bootstrap.")

    def get_custodians(self) -> set[str]:
        return set()

    def get_doctypes(self) -> set[str]:
        return set()

    def commit(self) -> None:
        return None


class TantivyIndexAdapter(IndexPort):
    """Tantivy-backed index adapter with optional dense retrieval support."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def add_document(self, path: str, text: str, metadata: dict) -> None:  # pragma: no cover - adapter writes via build
        raise NotImplementedError("Use build() to create Tantivy indexes.")

    def build(
        self,
        source: Path,
        *,
        rebuild: bool = False,
        dense: bool = False,
        **kwargs: Any,
    ) -> int:
        """Build Tantivy index and optional dense embeddings."""

        if dense and not self._settings.online:
            raise RuntimeError("Dense index build requires online mode (--online flag).")

        index_dir = self._settings.get_index_dir()
        dense_documents: list[dict[str, Any]] = []
        collector = dense_documents if dense else None

        document_count = build_index(
            source,
            index_dir,
            rebuild=rebuild,
            dense_collector=collector,
            **kwargs,
        )

        if dense and dense_documents:
            build_dense_index(
                dense_documents,
                index_dir=index_dir,
            )

        return document_count

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict | None = None,  # noqa: ARG002 - filters reserved for future use
        mode: str | None = None,
    ) -> list[TantivySearchResult]:
        strategy = (mode or "lexical").lower()

        if strategy == "dense":
            if not self._settings.online:
                raise RuntimeError("Dense search requires online mode (--online flag).")

            results, _ = dense_search_index(
                self._settings.get_index_dir(),
                query,
                limit=limit,
            )
            return results

        raise NotImplementedError("Lexical search not yet implemented for Tantivy adapter.")

    def get_custodians(self) -> set[str]:
        return load_custodians(self._settings.get_index_dir())

    def get_doctypes(self) -> set[str]:
        return load_doctypes(self._settings.get_index_dir())

    def commit(self) -> None:
        return None


def _create_ledger(settings: Settings) -> LedgerPort | None:
    if not settings.audit_enabled:
        return None

    ledger = AuditLedger(
        settings.get_audit_path(),
        hmac_key=settings.get_audit_hmac_key(),
        fsync_interval=settings.audit_fsync_interval,
    )
    # Compatibility alias for legacy call sites
    setattr(ledger, "append", ledger.log)
    return ledger


def bootstrap_application(settings: Settings | None = None) -> ApplicationContainer:
    """Instantiate adapters and services for CLI consumption."""

    active_settings = settings or get_settings()

    offline_gate = OfflineModeGate.from_settings(active_settings)

    storage = FileSystemStorageAdapter()
    discovery = IngestDiscoveryAdapter()
    deduper = HashDeduper()
    redaction_planner = JSONLineRedactionPlanner(settings=active_settings)
    bates_planner = SequentialBatesPlanner(settings=active_settings)
    pack_adapter = ZipPackager(active_settings.get_data_dir() / "packs")

    ledger = _create_ledger(active_settings)
    ledger_for_services: LedgerPort = ledger or NoOpLedger()  # type: ignore[assignment]

    pipeline = M1Pipeline(
        settings=active_settings,
        discovery_port=discovery,
        storage_port=storage,
        redaction_planner=redaction_planner,
        bates_planner=bates_planner,
        pack_port=pack_adapter,
        offline_gate=offline_gate,
        deduper_port=deduper,
        ledger_port=ledger,
    )

    report_service = ReportService(storage_port=storage, ledger_port=ledger_for_services)
    redaction_service = RedactionService(
        pii_port=None,
        stamp_port=None,
        storage_port=storage,
        ledger_port=ledger_for_services,
        settings=active_settings,
    )
    pack_service = PackService(storage_port=storage, ledger_port=ledger_for_services)
    audit_service = AuditService(ledger=ledger)

    return ApplicationContainer(
        settings=active_settings,
        pipeline=pipeline,
        report_service=report_service,
        redaction_service=redaction_service,
        pack_service=pack_service,
        audit_service=audit_service,
        ledger_port=ledger if ledger is not None else ledger_for_services,
        storage_port=storage,
        discovery_port=discovery,
        deduper_port=deduper,
        redaction_planner=redaction_planner,
        bates_planner=bates_planner,
        pack_port=pack_adapter,
        index_port=StubIndexAdapter(),
        offline_gate=offline_gate,
    )


# Backwards-compatible alias used by older callers/tests
def create_container(settings: Settings | None = None) -> ApplicationContainer:
    return bootstrap_application(settings=settings)


# Public API expected by CLI/tests
def bootstrap_application_container(settings: Settings | None = None) -> ApplicationContainer:
    """Alias retained for IDE snippets."""

    return bootstrap_application(settings=settings)
