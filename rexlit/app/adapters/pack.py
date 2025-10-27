"""Packaging adapters for RexLit artifacts."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from rexlit.app.ports import PackPort


class ZipPackager(PackPort):
    """Create zip archives from artifact directories."""

    def pack(self, source_dir: Path, *, destination: Path | None = None) -> Path:
        if not source_dir.exists():
            raise FileNotFoundError(f"Pack source directory not found: {source_dir}")
        if not source_dir.is_dir():
            raise ValueError(f"Pack source must be a directory: {source_dir}")

        dest_path = destination or source_dir.with_suffix(".rexpack.zip")
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with ZipFile(dest_path, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(source_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(source_dir))

        return dest_path
