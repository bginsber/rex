from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from rexlit.app.ports.embedding import EmbeddingPort, EmbeddingResult
from rexlit.app.ports.vector_store import VectorStorePort, VectorHit
from rexlit.app.ports.ledger import LedgerPort
from rexlit.index.build import build_dense_index


class MockEmbedder(EmbeddingPort):
    def __init__(self, *, dim: int, tokens_per_call: int = 10, latency_ms: float = 12.5) -> None:
        self.dim = dim
        self.tokens_per_call = tokens_per_call
        self.latency_ms = latency_ms

    def embed_documents(self, texts: Sequence[str], *, dimensions: int = 768) -> EmbeddingResult:
        # Return a deterministic embedding vector per text (all ones)
        vec = [1.0] * dimensions
        return EmbeddingResult(
            embeddings=[vec for _ in texts],
            latency_ms=self.latency_ms,
            token_count=self.tokens_per_call,
            model="mock",
            dimensions=dimensions,
        )

    def embed_query(self, query: str, *, dimensions: int = 768) -> list[float]:
        return [0.0] * dimensions


class MockVectorStore(VectorStorePort):
    def __init__(self, index_path: Path, dim: int) -> None:
        self.index_path = index_path
        self.dim = dim
        self._loaded = False
        self._built = False
        self._meta: dict[str, dict] = {}

    def build(
        self,
        embeddings: np.ndarray,
        identifiers: Sequence[str],
        metadata: dict[str, dict] | None = None,
        *,
        m: int = 32,
        ef_construction: int = 200,
        ef_search: int = 64,
    ) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        # Touch a file where index would live
        self.index_path.write_bytes(b"mock-index")
        # Save metadata next to it to mimic adapter behavior
        meta_path = Path(str(self.index_path) + ".meta.json")
        meta_path.write_text("{}")
        self._built = True
        self._meta = metadata or {}

    def load(self, *, ef_search: int = 64) -> None:  # noqa: ARG002
        self._loaded = True

    def query(self, vector: np.ndarray, *, top_k: int = 20) -> list[VectorHit]:  # noqa: ARG002
        return []


@dataclass
class DummyLedger(LedgerPort):
    last: dict[str, Any] | None = None

    def log(self, operation: str, inputs: list[str], outputs: list[str], args: dict[str, Any]) -> None:  # noqa: D401
        self.last = {"operation": operation, "inputs": inputs, "outputs": outputs, "args": args}

    def verify(self) -> bool:  # pragma: no cover - not used
        return True

    def read_all(self):  # pragma: no cover - not used
        return []


def test_build_dense_with_ports_and_ledger(temp_dir: Path) -> None:
    # Arrange
    index_dir = temp_dir / "index"
    dim = 4
    docs = [
        {
            "identifier": "id-1",
            "path": "doc1.txt",
            "sha256": "id-1",
            "custodian": None,
            "doctype": "txt",
            "text": "a",
        },
        {
            "identifier": "id-2",
            "path": "doc2.txt",
            "sha256": "id-2",
            "custodian": None,
            "doctype": "txt",
            "text": "b",
        },
    ]

    embedder = MockEmbedder(dim=dim, tokens_per_call=7, latency_ms=20.0)
    vs = MockVectorStore(index_path=index_dir / "dense" / f"kanon2_{dim}.hnsw", dim=dim)
    ledger = DummyLedger()

    # Act
    result = build_dense_index(
        docs,
        index_dir=index_dir,
        dim=dim,
        batch_size=2,
        embedder=embedder,
        vector_store=vs,
        ledger=ledger,
    )

    # Assert
    assert result is not None
    assert Path(result["index_path"]).exists()
    assert ledger.last is not None
    assert ledger.last["operation"] == "embedding_batch"
    assert "latency_ms_p50" in ledger.last["args"]
    assert ledger.last["args"]["tokens_total"] >= 7
