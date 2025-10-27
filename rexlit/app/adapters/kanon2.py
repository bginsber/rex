"""Kanon 2 (Isaacus) embedding adapter implementing EmbeddingPort."""

from __future__ import annotations

import os
import time
from collections.abc import Sequence

from rexlit.app.ports.embedding import EmbeddingPort, EmbeddingResult
from rexlit.utils.offline import OfflineModeGate


class Kanon2Adapter(EmbeddingPort):
    """Embedding adapter backed by the Isaacus Kanon 2 API."""

    MODEL_ID = "kanon-2-embedder"
    DOCUMENT_TASK = "retrieval/document"
    QUERY_TASK = "retrieval/query"

    def __init__(
        self,
        *,
        offline_gate: OfflineModeGate,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        offline_gate.require("Kanon 2 embeddings")
        self._api_key = api_key or os.getenv("ISAACUS_API_KEY")
        self._api_base = api_base or os.getenv("ISAACUS_API_BASE")
        if not self._api_key:
            raise RuntimeError(
                "ISAACUS_API_KEY required for Kanon 2 embeddings. Set via --isaacus-api-key or env var."
            )

        try:
            from isaacus import Isaacus  # imported lazily to keep optional dependency
        except Exception as exc:  # pragma: no cover - optional dep
            raise RuntimeError("The 'isaacus' package is required for Kanon 2 embeddings.") from exc

        # Instantiate client with optional base URL (self‑host support)
        self._client = Isaacus(api_key=self._api_key)
        if self._api_base is not None:
            if hasattr(self._client, "api_base"):
                self._client.api_base = self._api_base
            elif hasattr(self._client, "base_url"):
                self._client.base_url = self._api_base

    def embed_documents(self, texts: Sequence[str], *, dimensions: int = 768) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                latency_ms=0.0,
                token_count=0,
                model=self.MODEL_ID,
                dimensions=dimensions,
            )

        start = time.perf_counter()
        # Isaacus SDK versions differ in parameter names; support common forms
        try:
            response = self._client.embeddings.create(  # type: ignore[call-arg]
                model=self.MODEL_ID,  # type: ignore[arg-type]
                task=self.DOCUMENT_TASK,  # type: ignore[arg-type]
                input=list(texts),
                dimensions=dimensions,
            )
            vectors: list[list[float]] = [item.embedding for item in response.data]  # type: ignore[attr-defined]
            tokens = int(getattr(getattr(response, "usage", None), "total_tokens", 0) or 0)
        except TypeError:
            # Fallback to older signature observed in current codebase
            response = self._client.embeddings.create(
                model=self.MODEL_ID,  # type: ignore[arg-type]
                task=self.DOCUMENT_TASK,  # type: ignore[arg-type]
                texts=list(texts),
                dimensions=dimensions,
            )
            vectors = [entry.embedding for entry in getattr(response, "embeddings", [])]
            usage = getattr(response, "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0)

        latency_ms = (time.perf_counter() - start) * 1000.0
        return EmbeddingResult(
            embeddings=vectors,
            latency_ms=latency_ms,
            token_count=tokens,
            model=self.MODEL_ID,
            dimensions=dimensions,
        )

    def embed_query(self, query: str, *, dimensions: int = 768) -> list[float]:
        if not query.strip():
            return []

        try:
            response = self._client.embeddings.create(  # type: ignore[call-arg]
                model=self.MODEL_ID,  # type: ignore[arg-type]
                task=self.QUERY_TASK,  # type: ignore[arg-type]
                input=[query],
                dimensions=dimensions,
            )
            embedding: list[float] = response.data[0].embedding  # type: ignore[attr-defined]
            return embedding
        except TypeError:
            response = self._client.embeddings.create(
                model=self.MODEL_ID,  # type: ignore[arg-type]
                task=self.QUERY_TASK,  # type: ignore[arg-type]
                texts=[query],
                dimensions=dimensions,
            )
            embedding_fallback: list[float] = response.embeddings[0].embedding
            return embedding_fallback
