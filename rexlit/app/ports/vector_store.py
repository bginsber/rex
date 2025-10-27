"""Vector store port interface for ANN search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import numpy as np


@dataclass(slots=True)
class VectorHit:
    """Single vector search result."""

    identifier: str
    score: float
    metadata: dict[str, Any] | None = None


class VectorStorePort(Protocol):
    """Port interface for disk‑backed approximate nearest neighbour search.

    Implementations should provide:
    - Deterministic index construction
    - Fast cosine similarity search
    - Persistent storage on disk

    Side effects: Writes to index directory (offline).
    """

    def build(
        self,
        embeddings: np.ndarray,  # shape: (n, dim)
        identifiers: Sequence[str],
        metadata: dict[str, dict] | None = None,
        *,
        m: int = 32,
        ef_construction: int = 200,
        ef_search: int = 64,
    ) -> None:
        """Construct and persist an ANN index alongside metadata."""
        ...

    def load(self, *, ef_search: int = 64) -> None:
        """Load an existing index from disk."""
        ...

    def query(self, vector: np.ndarray, *, top_k: int = 20) -> list[VectorHit]:
        """Return top‑k nearest neighbours for ``vector``."""
        ...

