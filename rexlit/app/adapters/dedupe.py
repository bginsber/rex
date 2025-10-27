"""Deduplication adapter implementations."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Iterator

from rexlit.app.ports import DeduperPort, DocumentRecord
from rexlit.utils.deterministic import deterministic_order_documents


class HashDeduper(DeduperPort):
    """Deduplicate documents by SHA-256 while preserving deterministic ordering."""

    def dedupe(self, documents: Iterable[DocumentRecord]) -> Iterator[DocumentRecord]:
        """Yield the first instance of each unique document hash."""

        ordered_docs = deterministic_order_documents(documents)
        unique: OrderedDict[str, DocumentRecord] = OrderedDict()

        for document in ordered_docs:
            if document.sha256 not in unique:
                unique[document.sha256] = document

        yield from unique.values()
