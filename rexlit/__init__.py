"""RexLit - Offline-first UNIX litigation SDK/CLI.

A comprehensive e-discovery and deadline management toolkit for litigation professionals.
"""

__version__ = "0.1.0"
__author__ = "RexLit Contributors"

from rexlit.config import Settings, get_settings

__all__ = ["Settings", "get_settings", "__version__"]
