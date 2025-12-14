"""Path utilities for directory and file operations."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir(app_name: str = "rexlit") -> Path:
    """Get XDG data directory for application."""
    xdg_data = os.getenv("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"

    data_dir = base / app_name
    return ensure_dir(data_dir)


def get_config_dir(app_name: str = "rexlit") -> Path:
    """Get XDG config directory for application."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        base = Path(xdg_config)
    else:
        base = Path.home() / ".config"

    config_dir = base / app_name
    return ensure_dir(config_dir)


def find_files(
    root: Path,
    pattern: str = "*",
    recursive: bool = True,
    follow_symlinks: bool = False,
) -> list[Path]:
    """Find files matching pattern in directory."""
    if not root.is_dir():
        return []

    if recursive:
        matches = root.rglob(pattern)
    else:
        matches = root.glob(pattern)

    files = []
    for path in matches:
        if path.is_symlink() and not follow_symlinks:
            continue

        if path.is_file():
            files.append(path)

    return sorted(files)


def get_relative_path(path: Path, base: Path | None = None) -> Path:
    """Get relative path from base directory."""
    if base is None:
        base = Path.cwd()

    try:
        return path.relative_to(base)
    except ValueError:
        return path


def _resolve_allowed_roots(allowed_roots: Iterable[Path] | None) -> list[Path]:
    """Resolve allowed roots to absolute paths."""
    if not allowed_roots:
        return []
    return [root.resolve() for root in allowed_roots]


def validate_input_root(path: Path, allowed_roots: Iterable[Path] | None) -> Path:
    """Resolve ``path`` and ensure it resides within one of ``allowed_roots``."""

    resolved_path = Path(path).resolve()
    roots = _resolve_allowed_roots(allowed_roots)
    if not roots:
        return resolved_path

    for root in roots:
        if resolved_path.is_relative_to(root):
            return resolved_path

    raise ValueError(f"Input path {resolved_path} is outside allowed roots: {roots}")


def validate_output_root(path: Path, allowed_roots: Iterable[Path] | None) -> Path:
    """Resolve ``path`` and ensure it resides within one of ``allowed_roots``."""

    resolved_path = Path(path).resolve()
    roots = _resolve_allowed_roots(allowed_roots)
    if not roots:
        return resolved_path

    for root in roots:
        if resolved_path.is_relative_to(root):
            return resolved_path

    raise ValueError(f"Output path {resolved_path} is outside allowed roots: {roots}")
