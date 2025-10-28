from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from rexlit.app.adapters.hnsw import HNSWAdapter


class _FakeHNSWIndex:
    def __init__(self, *, space: str, dim: int) -> None:  # noqa: D401
        self.space = space
        self.dim = dim
        self._vecs: np.ndarray | None = None

    # Methods mirroring hnswlib.Index
    def init_index(
        self, *, max_elements: int, ef_construction: int, M: int
    ) -> None:  # noqa: ARG002
        return None

    def add_items(self, array: np.ndarray, ids: np.ndarray) -> None:  # noqa: ARG002
        self._vecs = np.asarray(array, dtype=np.float32)

    def set_ef(self, ef_search: int) -> None:  # noqa: ARG002
        return None

    def save_index(self, path: str) -> None:  # noqa: ARG002
        # Touch a file to simulate persistence
        Path(path).write_bytes(b"fake-index")

    def load_index(self, path: str) -> None:  # noqa: ARG002
        return None

    def knn_query(self, q: np.ndarray, k: int):
        assert self._vecs is not None
        q = np.asarray(q, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        vecs = self._vecs
        # cosine similarity
        q_norm = np.linalg.norm(q, axis=1, keepdims=True) + 1e-8
        v_norm = np.linalg.norm(vecs, axis=1, keepdims=True).T + 1e-8
        sims = (q @ vecs.T) / (q_norm * v_norm)
        # convert to distance per hnswlib 'cosine' space: 1 - cosine_similarity
        dists = 1.0 - sims
        # top-k indices
        idxs = np.argsort(dists, axis=1)[:, :k]
        picked = np.take_along_axis(dists, idxs, axis=1)
        return idxs.astype(np.int32), picked.astype(np.float32)


class _FakeHNSWLibModule:
    def Index(self, *, space: str, dim: int):  # noqa: D401
        return _FakeHNSWIndex(space=space, dim=dim)


def test_hnsw_adapter_build_load_query(monkeypatch, tmp_path: Path) -> None:
    # Inject fake hnswlib
    sys.modules["hnswlib"] = _FakeHNSWLibModule()  # type: ignore[assignment]

    index_path = tmp_path / "dense" / "kanon2_2.hnsw"
    adapter = HNSWAdapter(index_path=index_path, dimensions=2)

    # Two simple 2D vectors
    vecs = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    ids = ["a", "b"]
    metadata = {"a": {"path": "a.txt"}, "b": {"path": "b.txt"}}

    adapter.build(vecs, ids, metadata=metadata, m=8, ef_construction=100, ef_search=32)

    assert index_path.exists()
    meta_path = Path(str(index_path) + ".meta.json")
    assert meta_path.exists()

    # Reload and query
    adapter.load(ef_search=16)

    # Query near [1, 0] should return 'a' first
    q = np.asarray([1.0, 0.1], dtype=np.float32)
    hits = adapter.query(q, top_k=2)
    assert hits[0].identifier == "a"
    assert isinstance(hits[0].score, float)
    assert hits[0].metadata and hits[0].metadata.get("path") == "a.txt"
