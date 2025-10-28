"""Discovery adapter that bridges ingest metadata into application records."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from rexlit.app.ports import DiscoveryPort, DocumentRecord
from rexlit.ingest.discover import discover_documents


class IngestDiscoveryAdapter(DiscoveryPort):
    """Adapter that streams ``DocumentRecord`` instances via ingest discovery."""

    def discover(
        self,
        root: Path,
        *,
        recursive: bool = True,
        include_extensions: set[str] | None = None,
        exclude_extensions: set[str] | None = None,
    ) -> Iterator[DocumentRecord]:
        for metadata in discover_documents(
            root,
            recursive=recursive,
            include_extensions=include_extensions,
            exclude_extensions=exclude_extensions,
        ):
            yield DocumentRecord.model_validate(metadata.model_dump())
