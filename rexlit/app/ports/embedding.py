"""Embedding port interface for dense retrieval.

Defines a protocol for text embedding providers and a small DTO for
returning vectors with minimal telemetry. Adapters implement this port
to support online embedding backends (e.g., Kanon 2) or self‑hosted
alternatives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(slots=True)
class EmbeddingResult:
    """Embedding vectors and basic telemetry."""

    embeddings: list[list[float]]
    latency_ms: float
    token_count: int | None = None
    model: str | None = None
    dimensions: int | None = None


class EmbeddingPort(Protocol):
    """Port interface for text embedding services.

    Implementations should support:
    - Asymmetric embeddings (document vs query tasks)
    - Matryoshka dimensions (variable output sizes)
    - Batched document embedding for throughput

    Side effects: Network API calls (requires online mode).
    """

    def embed_documents(self, texts: Sequence[str], *, dimensions: int = 768) -> EmbeddingResult:
        """Embed documents for indexing.

        Args:
            texts: Document texts to embed (ordered)
            dimensions: Desired output dimension

        Returns:
            EmbeddingResult with vectors and telemetry
        """
        ...

    def embed_query(self, query: str, *, dimensions: int = 768) -> list[float]:
        """Embed a single search query vector."""
        ...

