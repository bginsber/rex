"""Search index using Tantivy for document retrieval."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import numpy as np
import tantivy
from pydantic import BaseModel, Field

from rexlit.app.adapters.hnsw import HNSWAdapter
from rexlit.app.ports import EmbeddingPort, VectorStorePort
from rexlit.index.build import create_schema
from rexlit.index.kanon2_embedder import QUERY_TASK, embed_texts  # compatibility shim
from rexlit.index.metadata import IndexMetadata
from rexlit.ingest.extract import extract_document


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


def _extract_snippet(
    text: str,
    query: str,
    max_length: int = 200,
    context_chars: int = 80,
) -> str:
    """Extract a snippet from text showing the query term in context.

    Args:
        text: Full document text
        query: Search query string (may contain operators like AND, OR, quotes)
        max_length: Maximum snippet length in characters (default: 200)
        context_chars: Characters to show before/after match (default: 80)

    Returns:
        Snippet with search term in context, or start of text if no match

    Examples:
        >>> _extract_snippet("This is a long document about contracts.", "contract")
        '...long document about contracts.'
        >>> _extract_snippet("Short text", "missing")
        'Short text'
    """
    if not text or not query:
        return ""

    # Normalize whitespace
    text = " ".join(text.split())

    # Extract search terms from query (remove Tantivy operators)
    # Remove field specifiers (e.g., "body:", "path:")
    query_cleaned = re.sub(r"\w+:", "", query)
    # Remove operators and special characters
    query_cleaned = re.sub(r"[+\-!(){}[\]^\"~*?:\\|&]", " ", query_cleaned)
    # Remove common query operators
    query_cleaned = re.sub(r"\b(AND|OR|NOT)\b", " ", query_cleaned, flags=re.IGNORECASE)

    # Extract individual terms (words 2+ chars)
    terms = [term.strip() for term in query_cleaned.split() if len(term.strip()) >= 2]

    if not terms:
        # No valid search terms, return start of document
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    # Find first occurrence of any term (case-insensitive)
    best_match_pos = None
    best_term = None
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            pos = match.start()
            if best_match_pos is None or pos < best_match_pos:
                best_match_pos = pos
                best_term = term

    if best_match_pos is None:
        # No match found, return start of document
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    # Calculate snippet boundaries
    # Center around the match, but don't exceed max_length
    start = max(0, best_match_pos - context_chars)
    end = min(len(text), best_match_pos + len(best_term or "") + context_chars)

    # Adjust if snippet would be too long
    if end - start > max_length:
        end = start + max_length

    snippet = text[start:end]

    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet.strip()


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

    # Precompute field handles for efficient lookup
    path_field = getattr(schema, "get_field", lambda name: None)("path")
    sha_field = getattr(schema, "get_field", lambda name: None)("sha256")
    custodian_field = getattr(schema, "get_field", lambda name: None)("custodian")
    doctype_field = getattr(schema, "get_field", lambda name: None)("doctype")
    metadata_field = getattr(schema, "get_field", lambda name: None)("metadata")

    def _coerce_value(value: Any) -> str:
        """Convert Tantivy field values into plain strings."""
        if value is None:
            return ""
        if hasattr(value, "text") and callable(value.text):
            value = value.text()
        elif hasattr(value, "as_text") and callable(value.as_text):  # pragma: no cover - compatibility
            value = value.as_text()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return str(value)

    def _extract_field(doc: Any, field_handle: Any, field_name: str) -> list[str]:
        """Extract stored field values regardless of Tantivy version."""
        if field_handle is None:
            return []
        get_all = getattr(doc, "get_all", None)
        if callable(get_all):
            try:
                values = get_all(field_handle) or []
            except TypeError:  # pragma: no cover - compatibility
                try:
                    values = get_all(field_name) or []
                except TypeError:
                    values = []
            return [_coerce_value(value) for value in values if value is not None]

        # Fallback for older bindings where Document behaves like a mapping.
        if hasattr(doc, "get"):
            raw = doc.get(field_name)
        else:  # pragma: no cover - legacy fallback
            try:
                raw = doc[field_name]
            except Exception:
                raw = None

        if raw is None:
            return []
        if isinstance(raw, (list, tuple, set)):
            return [_coerce_value(value) for value in raw if value is not None]
        return [_coerce_value(raw)]

    # Convert to SearchResult objects
    results: list[SearchResult] = []
    for score, doc_address in search_results.hits[offset : offset + limit]:
        doc = searcher.doc(doc_address)
        # Use to_dict() method which works reliably across Tantivy versions
        doc_dict = doc.to_dict()

        # Extract fields from dict (values are lists in Tantivy)
        path = doc_dict.get("path", [""])[0] if "path" in doc_dict else ""
        sha256 = doc_dict.get("sha256", [""])[0] if "sha256" in doc_dict else ""
        custodian = doc_dict.get("custodian", [""])[0] if "custodian" in doc_dict else None
        doctype = doc_dict.get("doctype", [""])[0] if "doctype" in doc_dict else None
        metadata = doc_dict.get("metadata", [""])[0] if "metadata" in doc_dict else None

        # Extract snippet from document
        snippet = None
        if path:
            try:
                doc_path = Path(path)
                if doc_path.exists():
                    extracted = extract_document(doc_path)
                    if extracted.text:
                        snippet = _extract_snippet(extracted.text, query)
            except Exception:
                # Silently ignore snippet extraction errors
                # (document may be moved/deleted, or extraction may fail)
                pass

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
            snippet=snippet,
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
        store = HNSWAdapter(index_path=store_path, dimensions=dim)
        store.load()

        def resolve_meta(identifier: str) -> dict[str, Any]:
            return {}

        def query_fn(v: np.ndarray) -> list[Any]:
            return store.query(v, top_k=limit)

    else:
        vs = vector_store
        vs.load()

        def resolve_meta(identifier: str) -> dict[str, Any]:
            if hasattr(vs, "resolve_metadata"):
                resolver = vs.resolve_metadata
                if callable(resolver):
                    resolved = resolver(identifier)
                    if isinstance(resolved, dict):
                        return dict(resolved)
            try:
                doc_meta = vs._doc_meta  # type: ignore[attr-defined]
            except AttributeError:
                doc_meta = None
            if isinstance(doc_meta, dict):
                value = doc_meta.get(identifier, {})
                if isinstance(value, dict):
                    return dict(value)
            return {}

        def query_fn(v: np.ndarray) -> list[Any]:
            return vs.query(v, top_k=limit)

    if embedder is not None:
        emb_vec = embedder.embed_query(query, dimensions=dim)
        embeddings = [emb_vec] if emb_vec else []
        telemetry: dict[str, Any] = {"usage": {}}
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
    hits = query_fn(query_vector)

    results: list[SearchResult] = []
    for _, hit in enumerate(hits, 1):
        # Handle both shim and adapter hits
        if hasattr(hit, "metadata"):
            metadata = cast(dict[str, Any], getattr(hit, "metadata", {}) or {})
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
        if result.sha256 not in fusion:
            fusion[result.sha256] = {}
        entry = fusion[result.sha256]
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
