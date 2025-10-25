"""Bootstrap module for dependency injection and adapter instantiation.

This module creates concrete adapter instances based on configuration
and wires them to application services.
"""

from pathlib import Path
from typing import Any

from rexlit.audit.ledger import AuditLedger
from rexlit.config import Settings
from rexlit.app import M1Pipeline, ReportService, RedactionService, PackService


class Container:
    """Dependency injection container.

    Instantiates adapters based on settings and provides
    fully-wired application services.
    """

    def __init__(self, settings: Settings):
        """Initialize container with settings.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._ledger_port: Any | None = None
        self._storage_port: Any | None = None
        self._ocr_port: Any | None = None
        self._stamp_port: Any | None = None
        self._pii_port: Any | None = None
        self._index_port: Any | None = None

    @property
    def ledger_port(self) -> Any:
        """Get or create ledger port adapter."""
        if self._ledger_port is None:
            # Create file-based audit ledger adapter
            audit_path = self.settings.get_audit_path()
            self._ledger_port = AuditLedger(audit_path) if self.settings.audit_enabled else NoOpLedger()
        return self._ledger_port

    @property
    def storage_port(self) -> Any:
        """Get or create storage port adapter."""
        if self._storage_port is None:
            # TODO: Create filesystem storage adapter
            # For now, return placeholder
            self._storage_port = None
        return self._storage_port

    @property
    def ocr_port(self) -> Any:
        """Get or create OCR port adapter."""
        if self._ocr_port is None:
            # TODO: Create OCR adapter based on settings.ocr_provider
            # Options: tesseract, paddle, deepseek
            self._ocr_port = None
        return self._ocr_port

    @property
    def stamp_port(self) -> Any:
        """Get or create PDF stamping port adapter."""
        if self._stamp_port is None:
            # TODO: Create PyMuPDF stamper adapter
            self._stamp_port = None
        return self._stamp_port

    @property
    def pii_port(self) -> Any:
        """Get or create PII detection port adapter."""
        if self._pii_port is None:
            # TODO: Create Presidio PII detector adapter
            self._pii_port = None
        return self._pii_port

    @property
    def index_port(self) -> Any:
        """Get or create search index port adapter."""
        if self._index_port is None:
            # TODO: Create Tantivy index adapter
            self._index_port = None
        return self._index_port

    def get_m1_pipeline(self) -> M1Pipeline:
        """Create M1 pipeline service with dependencies.

        Returns:
            Fully-wired M1Pipeline instance
        """
        return M1Pipeline(
            ledger_port=self.ledger_port,
            storage_port=self.storage_port,
            ocr_port=self.ocr_port,
            stamp_port=self.stamp_port,
            pii_port=self.pii_port,
            index_port=self.index_port,
        )

    def get_report_service(self) -> ReportService:
        """Create report service with dependencies.

        Returns:
            Fully-wired ReportService instance
        """
        return ReportService(
            storage_port=self.storage_port,
            ledger_port=self.ledger_port,
        )

    def get_redaction_service(self) -> RedactionService:
        """Create redaction service with dependencies.

        Returns:
            Fully-wired RedactionService instance
        """
        return RedactionService(
            pii_port=self.pii_port,
            stamp_port=self.stamp_port,
            storage_port=self.storage_port,
            ledger_port=self.ledger_port,
        )

    def get_pack_service(self) -> PackService:
        """Create pack service with dependencies.

        Returns:
            Fully-wired PackService instance
        """
        return PackService(
            storage_port=self.storage_port,
            ledger_port=self.ledger_port,
        )


class NoOpLedger:
    """No-operation ledger for when auditing is disabled."""

    def log(self, **kwargs: Any) -> None:
        """No-op log method."""
        pass

    def verify(self) -> bool:
        """Always return True for no-op ledger."""
        return True


def create_container(settings: Settings | None = None) -> Container:
    """Create dependency injection container.

    Args:
        settings: Application settings (uses default if None)

    Returns:
        Container instance
    """
    from rexlit.config import get_settings

    if settings is None:
        settings = get_settings()

    return Container(settings)
