"""Offline-first gating utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rexlit.config import Settings


@dataclass(slots=True)
class OfflineModeGate:
    """Centralized guard for online-only capabilities."""

    online_enabled: bool

    @classmethod
    def from_settings(cls, settings: "Settings") -> "OfflineModeGate":
        """Construct gate using configuration and environment overrides."""

        env_override = os.getenv("REXLIT_ONLINE")
        online_enabled = settings.online or (env_override is not None and env_override != "0")
        return cls(online_enabled=online_enabled)

    def is_online_enabled(self) -> bool:
        """Return True when online-only adapters may be used."""

        return self.online_enabled

    def require(self, feature: str) -> None:
        """Raise if ``feature`` cannot execute under offline-only mode."""

        if self.online_enabled:
            return

        raise RuntimeError(
            f"{feature} requires online mode. Enable with `--online` or set REXLIT_ONLINE=1."
        )

    def ensure_supported(self, *, feature: str, requires_online: bool) -> None:
        """Validate that the adapter supporting ``feature`` is permitted."""

        if not requires_online:
            return

        self.require(feature)
