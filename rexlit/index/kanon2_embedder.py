"""Isaacus Kanon 2 embedder integration (compatibility shim).

Deprecated: use `rexlit.app.ports.embedding.EmbeddingPort` and the
`rexlit.app.adapters.kanon2.Kanon2Adapter` instead. This module remains as a
shim to avoid breaking existing imports during the refactor. It may be removed
in a future release.
"""

from __future__ import annotations

import os
import time
import warnings
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from isaacus import Isaacus as IsaacusClient
else:  # pragma: no cover - runtime fallback
    IsaacusClient = Any

MODEL_ID: Literal["kanon-2-embedder"] = "kanon-2-embedder"
DOCUMENT_TASK: Literal["retrieval/document"] = "retrieval/document"
QUERY_TASK: Literal["retrieval/query"] = "retrieval/query"


@dataclass(slots=True)
class EmbeddingResult:
    """Container for embedding vectors and telemetry."""

    embeddings: list[list[float]]
    latency_ms: float
    usage: dict[str, Any] | None


def _normalise_usage(usage: Any) -> dict[str, Any] | None:
    """Attempt to serialise provider usage metadata."""
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        result = cast(Any, usage).model_dump()
        if isinstance(result, dict):
            return dict(result)
        return {"raw": repr(result)}
    if hasattr(usage, "to_dict"):
        result = cast(Any, usage).to_dict()
        if isinstance(result, dict):
            return dict(result)
        return {"raw": repr(result)}
    if isinstance(usage, dict):
        return usage
    # Best-effort string representation for unexpected types
    return {"raw": repr(usage)}


def _init_client(
    *,
    api_key: str | None,
    api_base: str | None,
) -> IsaacusClient:
    """Initialise the Isaacus client with optional self-host base URL."""
    try:
        from isaacus import Isaacus as IsaacusCtor
    except ImportError as exc:  # pragma: no cover - dependency missing runtime path
        raise RuntimeError(
            "The 'isaacus' package is required for dense embeddings. Install it with 'pip install isaacus'."
        ) from exc
    client_kwargs: dict[str, Any] = {}
    if api_key:
        client_kwargs["api_key"] = api_key
    client: IsaacusClient = IsaacusCtor(**client_kwargs)

    if api_base:
        # Isaacus SDK exposes api_base and/or base_url depending on version.
        client_any = cast(Any, client)
        if hasattr(client_any, "api_base"):
            client_any.api_base = api_base
        elif hasattr(client_any, "base_url"):
            client_any.base_url = api_base
        else:  # pragma: no cover - defensive branch
            # Fallback to attribute assignment for forward compatibility.
            client_any.api_base = api_base

    return client


def embed_texts(
    texts: Sequence[str] | Iterable[str],
    *,
    task: Literal["retrieval/document", "retrieval/query"],
    dimensions: int = 768,
    api_key: str | None = None,
    api_base: str | None = None,
) -> EmbeddingResult:
    """Compute embeddings for ``texts`` using Kanon 2.

    Args:
        texts: Ordered collection of input strings.
        task: Task specifier, e.g. ``retrieval/document`` or ``retrieval/query``.
        dimensions: Matryoshka dimension (defaults to 768).
        api_key: Optional override for ``ISAACUS_API_KEY``.
        api_base: Optional override for ``ISAACUS_API_BASE`` (self-host).

    Returns:
        EmbeddingResult containing vectors, latency, and usage metadata.
    """
    warnings.warn(
        "rexlit.index.kanon2_embedder is deprecated; use EmbeddingPort/Kanon2Adapter",
        DeprecationWarning,
        stacklevel=2,
    )

    materialised = list(texts)
    if not materialised:
        return EmbeddingResult(embeddings=[], latency_ms=0.0, usage=None)

    active_api_key = api_key or os.getenv("ISAACUS_API_KEY")
    active_api_base = api_base or os.getenv("ISAACUS_API_BASE")

    client = _init_client(api_key=active_api_key, api_base=active_api_base)

    start = time.perf_counter()
    # Try both common SDK signatures
    try:
        response = client.embeddings.create(
            model=MODEL_ID,
            texts=materialised,
            task=task,
            dimensions=dimensions,
        )
        embeddings = [entry.embedding for entry in getattr(response, "embeddings", [])]
        usage_raw = getattr(response, "usage", None)
    except TypeError:
        embeddings_api = cast(Any, client.embeddings)
        response = embeddings_api.create(
            model=MODEL_ID,
            input=materialised,
            task=task,
            dimensions=dimensions,
        )
        embeddings = [item.embedding for item in getattr(response, "data", [])]
        usage_raw = getattr(response, "usage", None)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    usage = _normalise_usage(usage_raw)

    telemetry: dict[str, Any] | None = None
    if usage is not None:
        telemetry = usage.copy()
        telemetry["input_count"] = len(materialised)
        telemetry["dimensions"] = dimensions
        telemetry["task"] = task

    return EmbeddingResult(embeddings=embeddings, latency_ms=elapsed_ms, usage=telemetry)
