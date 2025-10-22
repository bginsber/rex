"""Search index using Tantivy for document retrieval."""

from pathlib import Path

import tantivy
from pydantic import BaseModel, Field

from rexlit.index.build import create_schema


class SearchResult(BaseModel):
    """Single search result."""

    path: str = Field(..., description="Document path")
    sha256: str = Field(..., description="Document SHA-256 hash")
    custodian: str | None = Field(None, description="Document custodian")
    doctype: str | None = Field(None, description="Document type")
    score: float = Field(..., description="Relevance score")
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
    query_parser = tantivy.QueryParser.for_index(index, ["body", "path", "custodian"])

    try:
        parsed_query = query_parser.parse_query(query)
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
            snippet=None,  # TODO: Extract snippet from body
            metadata=metadata if metadata else None,
        )
        results.append(result)

    return results


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

    Args:
        index_dir: Directory containing index

    Returns:
        Set of custodian names

    Raises:
        FileNotFoundError: If index not found
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))
    searcher = index.searcher()

    # Search for all documents
    query_parser = tantivy.QueryParser.for_index(index, ["custodian"])
    parsed_query = query_parser.parse_query("*")
    search_results = searcher.search(parsed_query, 10000)

    custodians = set()
    for _, doc_address in search_results.hits:
        doc = searcher.doc(doc_address)
        doc_dict = index.schema.to_named_doc(doc)
        custodian = doc_dict.get("custodian", [""])[0]
        if custodian:
            custodians.add(custodian)

    return custodians


def get_doctypes(index_dir: Path) -> set[str]:
    """Get all unique document types in index.

    Args:
        index_dir: Directory containing index

    Returns:
        Set of document types

    Raises:
        FileNotFoundError: If index not found
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))
    searcher = index.searcher()

    # Search for all documents
    query_parser = tantivy.QueryParser.for_index(index, ["doctype"])
    parsed_query = query_parser.parse_query("*")
    search_results = searcher.search(parsed_query, 10000)

    doctypes = set()
    for _, doc_address in search_results.hits:
        doc = searcher.doc(doc_address)
        doc_dict = index.schema.to_named_doc(doc)
        doctype = doc_dict.get("doctype", [""])[0]
        if doctype and doctype != "unknown":
            doctypes.add(doctype)

    return doctypes
