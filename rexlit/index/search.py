"""Search index using Tantivy for document retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import tantivy
from pydantic import BaseModel, Field

from rexlit.index.build import create_schema
from rexlit.index.hnsw_store import HNSWStore  # compatibility shim
from rexlit.index.kanon2_embedder import QUERY_TASK, embed_texts  # compatibility shim
from rexlit.app.ports import EmbeddingPort, VectorStorePort
from rexlit.index.metadata import IndexMetadata


class SearchResult(BaseModel):
    """Single search result."""

    path: str = Field(..., description="Document path")
    sha256: str = Field(..., description="Document SHA-256 hash")
    custodian: str | None = Field(None, description="Document custodian")
    doctype: str | None = Field(None, description="Document type")
    score: float = Field(..., description="Relevance score")
    lexical_score: float | None = Field(
        None, description="Raw lexical score when available (BM25)."
    )
    dense_score: float | None = Field(
        None, description="Raw dense similarity score when available."
    )
    strategy: str = Field("lexical", description="Search strategy that produced the score.")
    snippet: str | None = Field(None, description="Text snippet")
    metadata: str | None = Field(None, description="Document metadata")


def search_index(
    index_dir: Path,
    query: str,
    limit: int = 10,
    offset: int = 0,
) -> list[SearchResult]:
    """Search the index.

    Args:
        index_dir: Directory containing index
        query: Search query string
        limit: Maximum number of results (default: 10)
        offset: Number of results to skip (default: 0)

    Returns:
        List of search results sorted by relevance

    Raises:
        FileNotFoundError: If index not found
        ValueError: If query is invalid
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    if not query.strip():
        raise ValueError("Query cannot be empty")

    # Load index
    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))
    searcher = index.searcher()

    # Parse query
    try:
        parsed_query = index.parse_query(query, default_field_names=["body", "path", "custodian"])
    except Exception as e:
        raise ValueError(f"Invalid query syntax: {e}") from e

    # Execute search
    search_results = searcher.search(parsed_query, limit + offset)

    # Convert to SearchResult objects
    results = []
    for score, doc_address in search_results.hits[offset : offset + limit]:
        doc = searcher.doc(doc_address)
        doc_dict = index.schema.to_named_doc(doc)

        # Extract fields
        path = doc_dict.get("path", [""])[0] if "path" in doc_dict else ""
        sha256 = doc_dict.get("sha256", [""])[0] if "sha256" in doc_dict else ""
        custodian = doc_dict.get("custodian", [""])[0] if "custodian" in doc_dict else None
        doctype = doc_dict.get("doctype", [""])[0] if "doctype" in doc_dict else None
        metadata = doc_dict.get("metadata", [""])[0] if "metadata" in doc_dict else None

        # Create result
        result = SearchResult(
            path=path,
            sha256=sha256,
            custodian=custodian if custodian else None,
            doctype=doctype if doctype else None,
            score=score,
             lexical_score=score,
             dense_score=None,
             strategy="lexical",
            snippet=None,  # TODO: Extract snippet from body
            metadata=metadata if metadata else None,
        )
        results.append(result)

    return results


def dense_search_index(
    index_dir: Path,
    query: str,
    *,
    limit: int = 10,
    dim: int = 768,
    api_key: str | None = None,
    api_base: str | None = None,
    embedder: EmbeddingPort | None = None,
    vector_store: VectorStorePort | None = None,
) -> tuple[list[SearchResult], dict[str, Any]]:
    """Run a dense-only search using the Kanon 2 HNSW index."""
    if not query.strip():
        raise ValueError("Query cannot be empty")

    dense_dir = index_dir / "dense"
    store_path = dense_dir / f"kanon2_{dim}.hnsw"

    if vector_store is None:
        store = HNSWStore(dim=dim, index_path=store_path)
        store.load()
        resolve_meta = store.resolve_metadata
        def _query(v: np.ndarray) -> list:
            return store.query(v, top_k=limit)
    else:
        vs = vector_store
        vs.load()
        resolve_meta = lambda ident: getattr(vs, "_doc_meta", {}).get(ident) if hasattr(vs, "_doc_meta") else {}  # type: ignore[assignment]
        def _query(v: np.ndarray) -> list:
            return vs.query(v, top_k=limit)

    if embedder is not None:
        emb_vec = embedder.embed_query(query, dimensions=dim)
        embeddings = [emb_vec] if emb_vec else []
        telemetry = {"usage": {}}
        latency = 0.0
    else:
        embedding = embed_texts(
            [query],
            task=QUERY_TASK,
            dimensions=dim,
            api_key=api_key,
            api_base=api_base,
        )
        embeddings = embedding.embeddings
        telemetry = {"usage": embedding.usage or {}}
        latency = embedding.latency_ms

    if not embeddings:
        return [], {"latency_ms": latency, "usage": telemetry.get("usage", {})}

    query_vector = np.asarray(embeddings[0], dtype=np.float32)
    hits = _query(query_vector)

    results: list[SearchResult] = []
    for rank, hit in enumerate(hits, 1):
        # Handle both shim and adapter hits
        if hasattr(hit, "metadata"):
            metadata = getattr(hit, "metadata") or {}
        else:
            metadata = resolve_meta(hit.identifier) or {}
        result = SearchResult(
            path=metadata.get("path", ""),
            sha256=metadata.get("sha256", hit.identifier),
            custodian=metadata.get("custodian"),
            doctype=metadata.get("doctype"),
            score=float(getattr(hit, "score", 0.0)),
            dense_score=float(getattr(hit, "score", 0.0)),
            lexical_score=None,
            strategy="dense",
            snippet=None,
            metadata=None,
        )
        results.append(result)

    telemetry = {
        "latency_ms": latency,
        "usage": telemetry.get("usage", {}),
        "dim": dim,
        "hits": len(results),
    }
    return results, telemetry


def _rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def hybrid_search_index(
    index_dir: Path,
    query: str,
    *,
    limit: int = 10,
    dim: int = 768,
    lexical_budget: int | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    fusion_k: int = 60,
    embedder: EmbeddingPort | None = None,
    vector_store: VectorStorePort | None = None,
) -> tuple[list[SearchResult], dict[str, Any]]:
    """Combine lexical and dense scores using Reciprocal Rank Fusion."""
    if not query.strip():
        raise ValueError("Query cannot be empty")

    lexical_limit = lexical_budget or max(limit, 20)
    lexical_results = search_index(index_dir, query, limit=lexical_limit)
    dense_results, dense_telemetry = dense_search_index(
        index_dir,
        query,
        limit=lexical_limit,
        dim=dim,
        api_key=api_key,
        api_base=api_base,
        embedder=embedder,
        vector_store=vector_store,
    )

    fusion: dict[str, dict[str, Any]] = {}
    for rank, result in enumerate(dense_results, 1):
        fusion[result.sha256] = {
            "dense": result,
            "dense_rank": rank,
            "score": _rrf(rank, fusion_k),
        }

    for rank, result in enumerate(lexical_results, 1):
        entry = fusion.setdefault(result.sha256, {})
        entry["lexical"] = result
        entry["lexical_rank"] = rank
        entry["score"] = entry.get("score", 0.0) + _rrf(rank, fusion_k)

    fused_results: list[SearchResult] = []
    for entry in fusion.values():
        dense_component = entry.get("dense")
        lexical_component = entry.get("lexical")

        template = dense_component or lexical_component
        if template is None:
            continue

        fused_results.append(
            SearchResult(
                path=template.path,
                sha256=template.sha256,
                custodian=template.custodian,
                doctype=template.doctype,
                score=float(entry.get("score", 0.0)),
                lexical_score=getattr(lexical_component, "lexical_score", None),
                dense_score=getattr(dense_component, "dense_score", None),
                strategy="hybrid",
                snippet=getattr(lexical_component, "snippet", None),
                metadata=getattr(lexical_component, "metadata", None),
            )
        )

    fused_results.sort(key=lambda item: item.score, reverse=True)
    return fused_results[:limit], {
        "lexical_count": len(lexical_results),
        "dense_count": len(dense_results),
        "fusion": "rrf",
        "dim": dim,
        "dense_latency_ms": dense_telemetry.get("latency_ms", 0.0),
        "usage": dense_telemetry.get("usage", {}),
    }


def search_by_custodian(
    index_dir: Path,
    custodian: str,
    limit: int = 100,
) -> list[SearchResult]:
    """Search for documents by custodian.

    Args:
        index_dir: Directory containing index
        custodian: Custodian name
        limit: Maximum number of results (default: 100)

    Returns:
        List of search results for custodian
    """
    query = f"custodian:{custodian}"
    return search_index(index_dir, query, limit=limit)


def search_by_doctype(
    index_dir: Path,
    doctype: str,
    limit: int = 100,
) -> list[SearchResult]:
    """Search for documents by document type.

    Args:
        index_dir: Directory containing index
        doctype: Document type (e.g., 'pdf', 'docx')
        limit: Maximum number of results (default: 100)

    Returns:
        List of search results for document type
    """
    query = f"doctype:{doctype}"
    return search_index(index_dir, query, limit=limit)


def search_by_hash(
    index_dir: Path,
    sha256: str,
) -> SearchResult | None:
    """Search for document by SHA-256 hash.

    Args:
        index_dir: Directory containing index
        sha256: SHA-256 hash to search for

    Returns:
        Search result if found, None otherwise
    """
    query = f"sha256:{sha256}"
    results = search_index(index_dir, query, limit=1)
    return results[0] if results else None


def count_documents(index_dir: Path) -> int:
    """Count total documents in index.

    Args:
        index_dir: Directory containing index

    Returns:
        Number of documents in index

    Raises:
        FileNotFoundError: If index not found
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))
    searcher = index.searcher()

    return searcher.num_docs


def get_custodians(index_dir: Path) -> set[str]:
    """Get all unique custodians in index.

    Uses cached metadata for O(1) lookup instead of O(n) index scan.
    Performance: <10ms vs 5-10 seconds at 100K scale.

    Args:
        index_dir: Directory containing index

    Returns:
        Set of custodian names

    Raises:
        FileNotFoundError: If index not found
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    # Use metadata cache for instant lookup
    metadata_cache = IndexMetadata(index_dir)
    return metadata_cache.get_custodians()


def get_doctypes(index_dir: Path) -> set[str]:
    """Get all unique document types in index.

    Uses cached metadata for O(1) lookup instead of O(n) index scan.
    Performance: <10ms vs 5-10 seconds at 100K scale.

    Args:
        index_dir: Directory containing index

    Returns:
        Set of document types

    Raises:
        FileNotFoundError: If index not found
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    # Use metadata cache for instant lookup
    metadata_cache = IndexMetadata(index_dir)
    return metadata_cache.get_doctypes()
