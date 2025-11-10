"""Profile loading utilities for PII and privilege detection configuration."""

from pathlib import Path
from typing import Any

import yaml

from rexlit.config import Settings


def load_profile(
    path: Path | None,
    settings: Settings,
) -> dict[str, Any]:
    """Load PII/privilege profile from YAML.

    Args:
        path: Path to profile YAML file. If None, uses default path.
        settings: Application settings for XDG-compliant path resolution.

    Returns:
        Profile dict with keys: "pii", "privilege". Empty dict if profile doesn't exist.

    Raises:
        ValueError: If YAML is invalid.
    """
    if path is not None:
        profile_path = path
    else:
        # Default to ~/.config/rexlit/profiles/default.yaml
        profile_path = settings.get_config_dir() / "profiles" / "default.yaml"

    if not profile_path.exists():
        return {}

    try:
        with profile_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to load profile from {profile_path}: {e}") from e

    return data or {}
