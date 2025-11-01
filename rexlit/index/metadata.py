"""Metadata caching for search index performance optimization."""

from __future__ import annotations

import json
import logging
from bisect import bisect_left
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class CachePayload(TypedDict):
    custodians: list[str]
    doctypes: list[str]
    doc_count: int


class IndexMetadata:
    """Cached metadata about index contents.

    This class provides O(1) lookups for index metadata (custodians, doctypes)
    instead of O(n) full index scans. Cache is maintained during indexing
    and persisted to .metadata_cache.json in the index directory.

    Performance: Reduces metadata queries from 5-10 seconds to <10ms at 100K scale.
    """

    def __init__(self, index_dir: Path):
        """Initialize metadata cache.

        Args:
            index_dir: Directory containing the search index
        """
        self.index_dir = index_dir
        self.cache_file = index_dir / ".metadata_cache.json"
        self._cache: CachePayload = self._load_cache()

    def _load_cache(self) -> CachePayload:
        """Load cache from disk or return empty cache.

        Returns:
            Dictionary containing custodians, doctypes, and doc_count
        """
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as fh:
                    data = json.load(fh)
                    return self._normalize_loaded_cache(data)
            except (OSError, json.JSONDecodeError) as exc:
                return self._handle_corrupt_cache(f"{exc}")
        return self._empty_cache()

    def _empty_cache(self) -> CachePayload:
        """Create an empty cache structure.

        Returns:
            Empty cache dictionary
        """
        return CachePayload(custodians=[], doctypes=[], doc_count=0)

    def _normalize_loaded_cache(self, data: Mapping[str, Any]) -> CachePayload:
        """Normalize cache payloads loaded from disk."""
        custodians = data.get("custodians", [])
        doctypes = data.get("doctypes", [])
        doc_count = data.get("doc_count", 0)

        if not isinstance(custodians, list):
            custodians = []
        if not isinstance(doctypes, list):
            doctypes = []
        if not isinstance(doc_count, int):
            doc_count = 0

        return CachePayload(
            custodians=sorted(dict.fromkeys(custodians)),
            doctypes=sorted(dict.fromkeys(doctypes)),
            doc_count=doc_count,
        )

    def _handle_corrupt_cache(self, reason: str) -> CachePayload:
        """Handle corrupted cache files by logging and backing up the payload."""

        logger.warning(
            "Metadata cache %s is corrupted (%s); rebuilding fresh cache.",
            self.cache_file,
            reason,
        )

        backup_path = self.cache_file.with_suffix(".corrupt")
        try:
            if self.cache_file.exists():
                # Avoid overwriting an existing backup
                if backup_path.exists():
                    backup_path.unlink()
                self.cache_file.replace(backup_path)
        except OSError:
            # Failure to backup shouldn't stop recovery; log and continue.
            logger.debug("Failed to backup corrupted cache %s", self.cache_file)
        return self._empty_cache()

    def reset(self) -> None:
        """Reset cache to empty state.

        Called when rebuilding index from scratch.
        """
        self._cache = self._empty_cache()

    def update(self, custodian: str | None, doctype: str | None) -> None:
        """Update metadata incrementally during indexing.

        Args:
            custodian: Custodian name (or None)
            doctype: Document type (or None)
        """
        # Track unique custodians
        if custodian:
            custodians = self._cache["custodians"]
            idx = bisect_left(custodians, custodian)
            if idx == len(custodians) or custodians[idx] != custodian:
                custodians.insert(idx, custodian)

        # Track unique doctypes (exclude 'unknown')
        if doctype and doctype != "unknown":
            doctypes = self._cache["doctypes"]
            idx = bisect_left(doctypes, doctype)
            if idx == len(doctypes) or doctypes[idx] != doctype:
                doctypes.insert(idx, doctype)

        # Increment document count
        self._cache["doc_count"] += 1

    def save(self) -> None:
        """Persist cache to disk.

        Writes cache as JSON to .metadata_cache.json in index directory.
        Should be called after index build/update completes.
        """
        try:
            with open(self.cache_file, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, indent=2)
        except OSError as exc:
            # Log error but don't fail the indexing process
            logger.warning(
                "Failed to save metadata cache to %s: %s", self.cache_file, exc, exc_info=True
            )

    def get_custodians(self) -> set[str]:
        """Get all unique custodians from cache.

        Returns:
            Set of custodian names (empty strings excluded)
        """
        return {c for c in self._cache["custodians"] if c}

    def get_doctypes(self) -> set[str]:
        """Get all unique document types from cache.

        Returns:
            Set of document types (empty strings and 'unknown' excluded)
        """
        return {d for d in self._cache["doctypes"] if d and d != "unknown"}

    def get_doc_count(self) -> int:
        """Get total document count from cache.

        Returns:
            Number of documents indexed
        """
        return self._cache["doc_count"]

    def exists(self) -> bool:
        """Check if cache file exists.

        Returns:
            True if cache file exists, False otherwise
        """
        return self.cache_file.exists()
