"""Concrete adapters wiring application ports to built-in implementations."""

from __future__ import annotations

from .bates import SequentialBatesPlanner
from .discovery import IngestDiscoveryAdapter
from .dedupe import HashDeduper
from .storage import FileSystemStorageAdapter
from .pack import ZipPackager
from .redaction import JSONLineRedactionPlanner, PassthroughRedactionApplier
from .kanon2 import Kanon2Adapter
from .hnsw import HNSWAdapter

__all__ = [
    "SequentialBatesPlanner",
    "IngestDiscoveryAdapter",
    "HashDeduper",
    "FileSystemStorageAdapter",
    "ZipPackager",
    "JSONLineRedactionPlanner",
    "PassthroughRedactionApplier",
    "Kanon2Adapter",
    "HNSWAdapter",
]
