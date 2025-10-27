"""Deduplication port interface."""

from __future__ import annotations

from typing import Iterable, Iterator, Protocol

from rexlit.app.ports.discovery import DocumentRecord


class DeduperPort(Protocol):
    """Port interface for document deduplication."""

    def dedupe(self, documents: Iterable[DocumentRecord]) -> Iterator[DocumentRecord]:
        """Yield a deterministic subset of ``documents`` without duplicate hashes."""
        ...
