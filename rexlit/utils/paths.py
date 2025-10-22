"""Path utilities for directory and file operations."""

import os
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating if necessary.

    Args:
        path: Directory path to ensure

    Returns:
        The created/verified directory path
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir(app_name: str = "rexlit") -> Path:
    """Get XDG data directory for application.

    Args:
        app_name: Application name for subdirectory

    Returns:
        Path to data directory
    """
    xdg_data = os.getenv("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"

    data_dir = base / app_name
    return ensure_dir(data_dir)


def get_config_dir(app_name: str = "rexlit") -> Path:
    """Get XDG config directory for application.

    Args:
        app_name: Application name for subdirectory

    Returns:
        Path to config directory
    """
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
    """Find files matching pattern in directory.

    Args:
        root: Root directory to search
        pattern: Glob pattern to match (default: all files)
        recursive: Search recursively (default: True)
        follow_symlinks: Follow symbolic links (default: False)

    Returns:
        List of matching file paths
    """
    if not root.is_dir():
        return []

    if recursive:
        matches = root.rglob(pattern)
    else:
        matches = root.glob(pattern)

    files = []
    for path in matches:
        # Skip symlinks unless explicitly following
        if path.is_symlink() and not follow_symlinks:
            continue
        if path.is_file():
            files.append(path)

    return sorted(files)


def get_relative_path(path: Path, base: Path | None = None) -> Path:
    """Get relative path from base directory.

    Args:
        path: Absolute or relative path
        base: Base directory (defaults to current directory)

    Returns:
        Relative path
    """
    if base is None:
        base = Path.cwd()

    try:
        return path.relative_to(base)
    except ValueError:
        # Path is not relative to base
        return path
