"""Filesystem-backed storage port implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from rexlit.app.ports import StoragePort


class FileSystemStorageAdapter(StoragePort):
    """Adapter that performs direct filesystem operations."""

    def read_text(self, path: Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def read_jsonl(self, path: Path) -> Iterator[dict[str, Any]]:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def write_jsonl(self, path: Path, records: Iterator[dict[str, Any]]) -> int:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with destination.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False))
                handle.write("\n")
                count += 1

        return count

    def list_files(self, directory: Path, pattern: str = "*") -> Iterator[Path]:
        root = Path(directory)
        if not root.exists():
            return iter(())
        return iter(sorted(root.glob(pattern)))

    def copy_file(self, src: Path, dst: Path) -> None:
        destination = Path(dst)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(src).read_bytes())

    def compute_hash(self, path: Path) -> str:
        import hashlib

        sha = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()
