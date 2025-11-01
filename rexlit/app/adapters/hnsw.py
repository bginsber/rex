"""hnswlib-based vector store adapter implementing VectorStorePort."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from rexlit.app.ports.vector_store import VectorHit, VectorStorePort


class HNSWAdapter(VectorStorePort):
    """Disk-backed HNSW index for cosine similarity search."""

    def __init__(
        self,
        *,
        index_path: Path,
        dimensions: int,
        space: str = "cosine",
    ) -> None:
        self._index_path = Path(index_path)
        self._meta_path = self._index_path.with_suffix(self._index_path.suffix + ".meta.json")
        self._dim = int(dimensions)
        self._space = space
        self._index: Any | None = None
        self._ids: list[str] | None = None
        self._doc_meta: dict[str, dict[str, Any]] = {}

    @property
    def index_path(self) -> Path:
        return self._index_path

    def _ensure_index(self) -> Any:
        try:
            import hnswlib
        except Exception as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "hnswlib is required for dense retrieval. Install 'hnswlib'."
            ) from exc

        if self._index is None:
            self._index = hnswlib.Index(space=self._space, dim=self._dim)
        return self._index

    def build(
        self,
        embeddings: np.ndarray,
        identifiers: Sequence[str],
        metadata: dict[str, dict[str, Any]] | None = None,
        *,
        m: int = 32,
        ef_construction: int = 200,
        ef_search: int = 64,
    ) -> None:
        array = np.asarray(embeddings, dtype=np.float32)
        if array.ndim != 2 or array.shape[1] != self._dim:
            raise ValueError(f"Embeddings shape must be (n, {self._dim}); got {array.shape}")

        ids = list(identifiers)
        if len(ids) != array.shape[0]:
            raise ValueError("Identifiers length must match number of embeddings")

        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        index = self._ensure_index()
        index.init_index(max_elements=array.shape[0], ef_construction=ef_construction, M=m)
        index.add_items(array, np.arange(array.shape[0]))
        index.set_ef(ef_search)
        index.save_index(str(self._index_path))

        doc_meta_value = metadata or {}
        meta = {
            "dim": self._dim,
            "space": self._space,
            "ids": ids,
            "ef_search": ef_search,
            "doc_metadata": doc_meta_value,
        }
        self._meta_path.write_text(json.dumps(meta))
        self._ids = ids
        self._doc_meta = doc_meta_value

    def load(self, *, ef_search: int = 64) -> None:
        if not self._index_path.exists():
            raise FileNotFoundError(f"HNSW index not found: {self._index_path}")
        if not self._meta_path.exists():
            raise FileNotFoundError(f"HNSW metadata missing: {self._meta_path}")

        index = self._ensure_index()
        index.load_index(str(self._index_path))
        index.set_ef(ef_search)

        meta = json.loads(self._meta_path.read_text())
        if int(meta.get("dim", -1)) != self._dim:
            raise ValueError(
                f"Stored dimension {meta.get('dim')} does not match expected {self._dim}"
            )

        self._ids = list(meta.get("ids", []))
        loaded_doc_meta = meta.get("doc_metadata", {})
        # Validate doc_metadata is a dict[str, dict[str, Any]]
        if isinstance(loaded_doc_meta, dict):
            self._doc_meta = loaded_doc_meta
        else:
            self._doc_meta = {}

    def query(self, vector: np.ndarray, *, top_k: int = 20) -> list[VectorHit]:
        if self._ids is None:
            raise RuntimeError("HNSW index not loaded. Call load() first.")

        q = np.asarray(vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        if q.shape[1] != self._dim:
            raise ValueError(f"Query vector must have dimension {self._dim}; got {q.shape[1]}")

        index = self._ensure_index()
        labels, distances = index.knn_query(q, k=top_k)
        hits: list[VectorHit] = []
        for label, distance in zip(labels[0], distances[0], strict=True):
            doc_id = self._ids[int(label)]
            score = 1.0 - float(distance)
            meta = self._doc_meta.get(doc_id, {}) if isinstance(self._doc_meta, dict) else {}
            hits.append(VectorHit(identifier=doc_id, score=score, metadata=meta))
        return hits
