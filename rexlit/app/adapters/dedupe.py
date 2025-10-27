"""Deduplication adapter implementations."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Iterator

from rexlit.app.ports import DeduperPort, DocumentRecord


class HashDeduper(DeduperPort):
    """Deduplicate documents by SHA-256 while preserving deterministic ordering."""

    def dedupe(self, documents: Iterable[DocumentRecord]) -> Iterator[DocumentRecord]:
        """Yield the first instance of each unique document hash."""

        ordered_docs = sorted(documents, key=lambda doc: (doc.sha256, doc.path))
        unique: OrderedDict[str, DocumentRecord] = OrderedDict()

        for document in ordered_docs:
            if document.sha256 not in unique:
                unique[document.sha256] = document

        yield from unique.values()
