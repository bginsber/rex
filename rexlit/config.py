"""Configuration management with Pydantic and XDG base directory support."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_xdg_data_home() -> Path:
    """Get XDG_DATA_HOME directory, defaulting to ~/.local/share."""
    xdg_data = os.getenv("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data)
    return Path.home() / ".local" / "share"


def get_xdg_config_home() -> Path:
    """Get XDG_CONFIG_HOME directory, defaulting to ~/.config."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config)
    return Path.home() / ".config"


class Settings(BaseSettings):
    """RexLit configuration settings.

    Precedence: CLI flag > environment variable > config file > defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="REXLIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Online mode control
    online: bool = Field(
        default=False,
        description="Enable online features (API calls, network requests)",
    )

    # Data directories
    data_dir: Path | None = Field(
        default=None,
        description="Override data directory (defaults to XDG_DATA_HOME/rexlit)",
    )

    config_dir: Path | None = Field(
        default=None,
        description="Override config directory (defaults to XDG_CONFIG_HOME/rexlit)",
    )

    # API keys (online features only)
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude Agent SDK",
    )

    deepseek_api_key: str | None = Field(
        default=None,
        description="DeepSeek API key for online OCR",
    )

    # Audit settings
    audit_enabled: bool = Field(
        default=True,
        description="Enable append-only audit ledger",
    )

    # Index settings
    index_backend: str = Field(
        default="tantivy",
        description="Search backend: tantivy or whoosh",
    )

    def get_data_dir(self) -> Path:
        """Get the data directory, creating if necessary."""
        if self.data_dir:
            data_dir = self.data_dir
        else:
            data_dir = get_xdg_data_home() / "rexlit"

        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def get_config_dir(self) -> Path:
        """Get the config directory, creating if necessary."""
        if self.config_dir:
            config_dir = self.config_dir
        else:
            config_dir = get_xdg_config_home() / "rexlit"

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def get_audit_path(self) -> Path:
        """Get path to audit ledger file."""
        return self.get_data_dir() / "audit.jsonl"

    def get_index_dir(self) -> Path:
        """Get path to search index directory."""
        index_dir = self.get_data_dir() / "index"
        index_dir.mkdir(parents=True, exist_ok=True)
        return index_dir


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(settings: Settings) -> None:
    """Set the global settings instance (useful for testing)."""
    global _settings
    _settings = settings
