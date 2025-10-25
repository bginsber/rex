"""Index port interface for search index operations."""

from pathlib import Path
from typing import Protocol, Iterator

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Search result."""

    path: str
    score: float
    snippet: str | None = None


class IndexPort(Protocol):
    """Port interface for search index operations.

    Adapter: Tantivy full-text search.

    Side effects: Reads/writes index directory (offline).
    """

    def add_document(
        self,
        path: str,
        text: str,
        metadata: dict,
    ) -> None:
        """Add document to index.

        Args:
            path: Document path
            text: Document text
            metadata: Document metadata (custodian, doctype, etc.)
        """
        ...

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """Search index.

        Args:
            query: Search query
            limit: Maximum results
            filters: Metadata filters (custodian, doctype, etc.)

        Returns:
            List of search results
        """
        ...

    def get_custodians(self) -> set[str]:
        """Get all custodians in index.

        Returns:
            Set of custodian names
        """
        ...

    def get_doctypes(self) -> set[str]:
        """Get all document types in index.

        Returns:
            Set of document types
        """
        ...

    def commit(self) -> None:
        """Commit pending changes to index."""
        ...
