"""Disk-backed HNSW index for dense retrieval (compatibility shim).

Deprecated: use `rexlit.app.ports.vector_store.VectorStorePort` and
`rexlit.app.adapters.hnsw.HNSWAdapter` instead. This class remains as a shim
to avoid breaking existing imports during the refactor.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - optional dependency warning path
    import hnswlib
except ImportError:  # pragma: no cover - handled at runtime
    hnswlib = None  # type: ignore[assignment]

import numpy as np

DEFAULT_EF = 64


@dataclass(slots=True)
class DenseHit:
    """Single dense retrieval result."""

    identifier: str
    score: float


class HNSWStore:
    """Manage on-disk HNSW indexes for cosine similarity search."""

    def __init__(
        self,
        dim: int,
        index_path: Path,
        *,
        space: str = "cosine",
    ) -> None:
        import warnings

        warnings.warn(
            "rexlit.index.hnsw_store.HNSWStore is deprecated; use HNSWAdapter",
            DeprecationWarning,
            stacklevel=2,
        )
        self.dim = dim
        self.index_path = Path(index_path)
        self.space = space
        self._index = None
        self._ids: list[str] | None = None
        self._metadata: dict[str, dict] | None = None
        self._metadata_path = self.index_path.with_suffix(self.index_path.suffix + ".meta.json")

    @property
    def metadata_path(self) -> Path:
        """Return the path to the metadata JSON file."""
        return self._metadata_path

    def build(
        self,
        embeddings: np.ndarray,
        identifiers: Sequence[str] | Iterable[str],
        *,
        max_elements: int | None = None,
        m: int = 32,
        ef_construction: int = 200,
        ef_search: int = DEFAULT_EF,
        doc_metadata: dict[str, dict] | None = None,
    ) -> None:
        """Construct a fresh index and persist it alongside metadata."""
        array = np.asarray(embeddings, dtype=np.float32)
        if array.ndim != 2 or array.shape[1] != self.dim:
            raise ValueError(
                f"Embeddings must be a 2D array with shape (n, {self.dim}); received {array.shape}"
            )

        ids = list(identifiers)
        if len(ids) != array.shape[0]:
            raise ValueError("Number of identifiers must match number of embeddings")

        max_elems = max_elements or array.shape[0]
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        index = self._ensure_index()
        index.init_index(max_elements=max_elems, ef_construction=ef_construction, M=m)
        index.add_items(array, np.arange(array.shape[0]))
        index.set_ef(ef_search)
        index.save_index(str(self.index_path))

        metadata = {
            "dim": self.dim,
            "space": self.space,
            "ids": ids,
            "ef_search": ef_search,
            "doc_metadata": doc_metadata or {},
        }
        self._metadata_path.write_text(json.dumps(metadata))
        self._ids = ids
        self._metadata = metadata["doc_metadata"]

    def load(self, *, ef_search: int = DEFAULT_EF) -> None:
        """Load an index from disk."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"HNSW index not found: {self.index_path}")

        if not self._metadata_path.exists():
            raise FileNotFoundError(f"HNSW metadata missing: {self._metadata_path}")

        index = self._ensure_index()
        index.load_index(str(self.index_path))
        index.set_ef(ef_search)

        metadata = json.loads(self._metadata_path.read_text())
        if metadata.get("dim") != self.dim:
            raise ValueError(
                f"Stored dimension {metadata.get('dim')} does not match expected {self.dim}"
            )

        self._ids = list(metadata.get("ids", []))
        self._metadata = metadata.get("doc_metadata", {})

    def is_ready(self) -> bool:
        """Return True when the index and metadata exist on disk."""
        return self.index_path.exists() and self._metadata_path.exists()

    def query(self, vector: np.ndarray, *, top_k: int = 20) -> list[DenseHit]:
        """Return the top ``top_k`` nearest neighbours."""
        if self._ids is None:
            raise RuntimeError("HNSW index not loaded. Call 'load()' first.")

        query_vector = np.asarray(vector, dtype=np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        if query_vector.shape[1] != self.dim:
            raise ValueError(
                f"Query vector must have dimension {self.dim}; received {query_vector.shape[1]}"
            )

        index = self._ensure_index()
        labels, distances = index.knn_query(query_vector, k=top_k)
        hits: list[DenseHit] = []
        for label, distance in zip(labels[0], distances[0]):
            identifier = self._ids[int(label)]
            # Convert cosine distance (0 == identical, 2 == opposite) to similarity score
            score = 1.0 - float(distance)
            hits.append(DenseHit(identifier=identifier, score=score))
        return hits

    def resolve_metadata(self, identifier: str) -> dict | None:
        """Return stored metadata for ``identifier`` if present."""
        if not hasattr(self, "_metadata"):
            self._metadata = {}
        return self._metadata.get(identifier)

    def _ensure_index(self) -> hnswlib.Index:
        if hnswlib is None:  # pragma: no cover - dependency missing runtime path
            raise RuntimeError(
                "hnswlib is required for dense search. Install it with 'pip install hnswlib'."
            )

        if self._index is None:
            self._index = hnswlib.Index(space=self.space, dim=self.dim)
        return self._index
