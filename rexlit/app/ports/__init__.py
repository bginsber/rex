"""Port interfaces for RexLit application layer.

These protocol/ABC interfaces define contracts for adapters.
Domain logic depends on these ports, never on concrete implementations.
"""

__all__ = [
    "AuditRecord",
    "LedgerPort",
    "SignerPort",
    "StoragePort",
    "OCRPort",
    "StampPort",
    "PIIPort",
    "IndexPort",
    "DocumentRecord",
    "DiscoveryPort",
    "DeduperPort",
    "BatesAssignment",
    "BatesPlan",
    "BatesPlannerPort",
    "RedactionPlannerPort",
    "RedactionApplierPort",
    "PackPort",
    "EmbeddingResult",
    "EmbeddingPort",
    "VectorHit",
    "VectorStorePort",
]

from rexlit.app.ports.bates import BatesAssignment, BatesPlan, BatesPlannerPort
from rexlit.app.ports.dedupe import DeduperPort
from rexlit.app.ports.discovery import DiscoveryPort, DocumentRecord
from rexlit.app.ports.embedding import EmbeddingPort, EmbeddingResult
from rexlit.app.ports.index import IndexPort
from rexlit.app.ports.ledger import AuditRecord, LedgerPort
from rexlit.app.ports.ocr import OCRPort
from rexlit.app.ports.pack import PackPort
from rexlit.app.ports.pii import PIIPort
from rexlit.app.ports.redaction import RedactionApplierPort, RedactionPlannerPort
from rexlit.app.ports.signer import SignerPort
from rexlit.app.ports.stamp import StampPort
from rexlit.app.ports.storage import StoragePort
from rexlit.app.ports.vector_store import VectorHit, VectorStorePort
