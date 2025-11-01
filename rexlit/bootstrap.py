"""Application bootstrap wiring ports, adapters, and services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rexlit.app import M1Pipeline, PackService, RedactionService, ReportService
from rexlit.app.adapters import (
    FileSystemStorageAdapter,
    HashDeduper,
    HNSWAdapter,
    IngestDiscoveryAdapter,
    JSONLineRedactionPlanner,
    Kanon2Adapter,
    PDFStamperAdapter,
    SequentialBatesPlanner,
    TesseractOCRAdapter,
    ZipPackager,
)
from rexlit.app.audit_service import AuditService
from rexlit.app.ports import (
    BatesPlannerPort,
    DeduperPort,
    DiscoveryPort,
    EmbeddingPort,
    IndexPort,
    LedgerPort,
    OCRPort,
    PackPort,
    StampPort,
    RedactionPlannerPort,
    StoragePort,
    VectorStorePort,
)
from rexlit.app.ports.ocr import OCRResult
from rexlit.audit.ledger import AuditLedger
from rexlit.config import Settings, get_settings
from rexlit.index.build import DenseDocument, build_dense_index, build_index
from rexlit.index.search import (
    SearchResult as TantivySearchResult,
)
from rexlit.index.search import (
    dense_search_index,
)
from rexlit.index.search import (
    get_custodians as load_custodians,
)
from rexlit.index.search import (
    get_doctypes as load_doctypes,
)
from rexlit.index.search import (
    search_index as lexical_search_index,
)
from rexlit.rules import RulesEngine
from rexlit.utils.offline import OfflineModeGate


@dataclass(slots=True)
class ApplicationContainer:
    """Aggregates wired services and adapters for the CLI layer."""

    settings: Settings
    pipeline: M1Pipeline
    report_service: ReportService
    redaction_service: RedactionService
    pack_service: PackService
    rules_engine: RulesEngine
    audit_service: AuditService
    ledger_port: LedgerPort
    storage_port: StoragePort
    discovery_port: DiscoveryPort
    deduper_port: DeduperPort | None
    redaction_planner: RedactionPlannerPort
    bates_planner: BatesPlannerPort
    bates_stamper: StampPort
    pack_port: PackPort
    index_port: IndexPort
    offline_gate: OfflineModeGate
    # New: optional embedding/vector store wiring for dense search
    embedder: EmbeddingPort | None
    vector_store_factory: Callable[[Path, int], VectorStorePort] | None
    ocr_providers: dict[str, OCRPort]


class NoOpLedger:
    """Ledger implementation that drops all writes."""

    def log(self, *args: Any, **kwargs: Any) -> None:
        return None

    def append(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - compatibility alias
        return None

    def read_all(self) -> list[dict[str, Any]]:
        return []

    def verify(self) -> tuple[bool, str | None]:
        return (True, None)


class StubIndexAdapter(IndexPort):
    """Placeholder index adapter used until Tantivy wiring lands."""

    def add_document(
        self, path: str, text: str, metadata: dict[str, Any]
    ) -> None:  # pragma: no cover - stub
        raise RuntimeError("Search indexing not yet implemented for offline bootstrap.")

    def search(  # type: ignore[override]
        self, query: str, *, limit: int = 10, filters: dict[str, Any] | None = None
    ) -> list[TantivySearchResult]:
        raise RuntimeError("Search indexing not yet implemented for offline bootstrap.")

    def get_custodians(self) -> set[str]:
        return set()

    def get_doctypes(self) -> set[str]:
        return set()

    def commit(self) -> None:
        return None


class TantivyIndexAdapter(IndexPort):
    """Tantivy-backed index adapter with optional dense retrieval support."""

    def __init__(
        self,
        settings: Settings,
        *,
        embedder: EmbeddingPort | None = None,
        vector_store_factory: Callable[[Path, int], VectorStorePort] | None = None,
        ledger_port: LedgerPort | None = None,
        offline_gate: OfflineModeGate | None = None,
    ) -> None:
        self._settings = settings
        self._embedder = embedder
        self._vector_store_factory = vector_store_factory
        self._ledger_port = ledger_port
        self._offline_gate = offline_gate or OfflineModeGate.from_settings(settings)

    def _resolve_embedder(
        self, api_key: str | None = None, api_base: str | None = None
    ) -> EmbeddingPort | None:
        """Return an embedder honoring command-line overrides when provided."""
        if api_key or api_base:
            override = _safe_init_embedder(
                self._offline_gate, api_key=api_key, api_base=api_base
            )
            if override is not None:
                return override
            return None

        if self._embedder is None:
            self._embedder = _safe_init_embedder(self._offline_gate)

        return self._embedder


class LazyOCRAdapter(OCRPort):
    """Lazy wrapper that defers adapter construction until first use."""

    def __init__(self, factory: Callable[[], OCRPort]) -> None:
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_instance", None)

    def _resolve(self) -> OCRPort:
        instance = object.__getattribute__(self, "_instance")
        if instance is None:
            instance = object.__getattribute__(self, "_factory")()
            object.__setattr__(self, "_instance", instance)
        return instance

    def process_document(
        self,
        path: Path,
        *,
        language: str = "eng",
    ) -> OCRResult:
        return self._resolve().process_document(path, language=language)

    def is_online(self) -> bool:
        return self._resolve().is_online()

    def __getattr__(self, item: str) -> Any:
        return getattr(self._resolve(), item)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_factory", "_instance"}:
            object.__setattr__(self, name, value)
        else:
            setattr(self._resolve(), name, value)

    def add_document(
        self, path: str, text: str, metadata: dict[str, Any]
    ) -> None:  # pragma: no cover - adapter writes via build
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
        if dense:
            self._offline_gate.require("Dense indexing")

        index_dir = self._settings.get_index_dir()
        dense_documents: list[DenseDocument] = []
        collector = dense_documents if dense else None
        # Map passthrough kwargs for tantivy build
        passthrough: dict[str, Any] = {}
        for key in ("show_progress", "max_workers", "batch_size"):
            if key in kwargs:
                passthrough[key] = kwargs[key]

        document_count = build_index(
            source,
            index_dir,
            rebuild=rebuild,
            dense_collector=collector,
            **passthrough,
        )

        if dense and dense_documents:
            dim = int(kwargs.get("dense_dim", 768))
            dense_batch = int(kwargs.get("dense_batch_size", 32))
            api_key = kwargs.get("dense_api_key")
            api_base = kwargs.get("dense_api_base")
            embedder = self._resolve_embedder(api_key=api_key, api_base=api_base)

            vector_store = (
                self._vector_store_factory(index_dir, dim)
                if self._vector_store_factory is not None
                else None
            )
            build_dense_index(
                dense_documents,
                index_dir=index_dir,
                dim=dim,
                batch_size=dense_batch,
                api_key=api_key,
                api_base=api_base,
                embedder=embedder,
                vector_store=vector_store,
                ledger=self._ledger_port,
            )

        return document_count

    def search(  # type: ignore[override]
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,  # noqa: ARG002 - reserved for future use
        mode: str | None = None,
        dim: int = 768,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> list[TantivySearchResult]:
        # Extension of IndexPort.search to support dense/hybrid modes
        strategy = (mode or "lexical").lower()

        if strategy == "dense":
            self._offline_gate.require("dense search")
            embedder = self._resolve_embedder(api_key=api_key, api_base=api_base)
            vector_store = (
                self._vector_store_factory(self._settings.get_index_dir(), dim)
                if self._vector_store_factory is not None
                else None
            )
            results, _ = dense_search_index(
                self._settings.get_index_dir(),
                query,
                limit=limit,
                dim=dim,
                api_key=api_key,
                api_base=api_base,
                embedder=embedder,
                vector_store=vector_store,
            )
            return results

        if strategy == "hybrid":
            self._offline_gate.require("hybrid search")
            embedder = self._resolve_embedder(api_key=api_key, api_base=api_base)
            vector_store = (
                self._vector_store_factory(self._settings.get_index_dir(), dim)
                if self._vector_store_factory is not None
                else None
            )
            from rexlit.index.search import hybrid_search_index as _hybrid

            results, _ = _hybrid(
                self._settings.get_index_dir(),
                query,
                limit=limit,
                dim=dim,
                api_key=api_key,
                api_base=api_base,
                embedder=embedder,
                vector_store=vector_store,
            )
            return results

        if strategy in {"lexical", "bm25"}:
            return lexical_search_index(
                self._settings.get_index_dir(),
                query,
                limit=limit,
            )

        raise NotImplementedError(f"Unsupported search mode '{strategy}'.")

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
    ledger.append = ledger.log  # type: ignore[attr-defined]
    return ledger  # type: ignore[return-value]


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
    bates_stamper = PDFStamperAdapter()
    rules_dir = Path(__file__).resolve().parent / "rules"
    rules_engine = RulesEngine(rules_dir)

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
    ocr_providers: dict[str, OCRPort] = {
        "tesseract": LazyOCRAdapter(
            lambda: TesseractOCRAdapter(
                lang="eng",
                preflight=True,
                dpi_scale=2,
                min_text_threshold=50,
            )
        )
    }

    return ApplicationContainer(
        settings=active_settings,
        pipeline=pipeline,
        report_service=report_service,
        redaction_service=redaction_service,
        pack_service=pack_service,
        rules_engine=rules_engine,
        audit_service=audit_service,
        ledger_port=ledger if ledger is not None else ledger_for_services,
        storage_port=storage,
        discovery_port=discovery,
        deduper_port=deduper,
        redaction_planner=redaction_planner,
        bates_planner=bates_planner,
        bates_stamper=bates_stamper,
        pack_port=pack_adapter,
        index_port=TantivyIndexAdapter(
            active_settings,
            embedder=(None if not active_settings.online else _safe_init_embedder(offline_gate)),
            vector_store_factory=(
                lambda index_dir, dim: HNSWAdapter(
                    index_path=Path(index_dir) / "dense" / f"kanon2_{int(dim)}.hnsw",
                    dimensions=int(dim),
                )
            ),
            ledger_port=ledger_for_services,
            offline_gate=offline_gate,
        ),
        offline_gate=offline_gate,
        embedder=(None if not active_settings.online else _safe_init_embedder(offline_gate)),
        vector_store_factory=(
            lambda index_dir, dim: HNSWAdapter(
                index_path=Path(index_dir) / "dense" / f"kanon2_{int(dim)}.hnsw",
                dimensions=int(dim),
            )
        ),
        ocr_providers=ocr_providers,
    )


# Backwards-compatible alias used by older callers/tests
def create_container(settings: Settings | None = None) -> ApplicationContainer:
    return bootstrap_application(settings=settings)


# Public API expected by CLI/tests
def bootstrap_application_container(settings: Settings | None = None) -> ApplicationContainer:
    """Alias retained for IDE snippets."""

    return bootstrap_application(settings=settings)


# Internal helper to construct the embedder without failing bootstrap
def _safe_init_embedder(
    offline_gate: OfflineModeGate, *, api_key: str | None = None, api_base: str | None = None
) -> EmbeddingPort | None:
    try:
        return Kanon2Adapter(offline_gate=offline_gate, api_key=api_key, api_base=api_base)
    except Exception:
        return None
