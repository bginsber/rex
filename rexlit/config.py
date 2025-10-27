"""Configuration management with Pydantic and XDG base directory support."""

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, PrivateAttr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from rexlit.utils.crypto import (
    decrypt_blob,
    encrypt_blob,
    load_or_create_fernet_key,
    load_or_create_hmac_key,
)


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


APIKeyName = Literal["anthropic", "deepseek"]


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
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key for Claude Agent SDK",
    )

    deepseek_api_key: SecretStr | None = Field(
        default=None,
        description="DeepSeek API key for online OCR",
    )

    # Audit settings
    audit_enabled: bool = Field(
        default=True,
        description="Enable append-only audit ledger",
    )

    audit_fsync_interval: int = Field(
        default=5,
        ge=1,
        description="Number of audit entries between fsync operations (1 = fsync every entry).",
    )

    pii_key_path: Path | None = Field(
        default=None,
        description="Location of the symmetric key used to encrypt PII findings",
    )

    redaction_plan_key_path: Path | None = Field(
        default=None,
        description="Location of the key used to encrypt redaction plans",
    )

    audit_hmac_key_path: Path | None = Field(
        default=None,
        description="Location of the audit ledger HMAC key for tamper detection",
    )

    api_secret_key_path: Path | None = Field(
        default=None,
        description="Location of the master encryption key used for API secrets",
    )

    # Index settings
    index_backend: str = Field(
        default="tantivy",
        description="Search backend: tantivy or whoosh",
    )

    _api_key_cache: dict[str, str | None] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Persist inline API keys into the encrypted secrets store."""
        super().model_post_init(__context)
        for provider in ("anthropic", "deepseek"):
            field_name = f"{provider}_api_key"
            secret: SecretStr | None = getattr(self, field_name)
            if secret is None:
                continue
            self.store_api_key(provider, secret.get_secret_value())
            # Prevent accidental plaintext reuse once persisted.
            object.__setattr__(self, field_name, None)

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

    def get_pii_key(self) -> bytes:
        """Return the Fernet key used to encrypt PII findings."""
        key_path = (
            self.pii_key_path
            if self.pii_key_path is not None
            else self.get_config_dir() / "pii.key"
        )
        return load_or_create_fernet_key(key_path)

    def get_redaction_plan_key(self) -> bytes:
        """Return the Fernet key used to encrypt redaction plans."""
        key_path = (
            self.redaction_plan_key_path
            if self.redaction_plan_key_path is not None
            else self.get_config_dir() / "redaction-plans.key"
        )
        return load_or_create_fernet_key(key_path)

    def get_audit_hmac_key(self) -> bytes:
        """Return the HMAC key used to seal audit ledger metadata."""
        key_path = (
            self.audit_hmac_key_path
            if self.audit_hmac_key_path is not None
            else self.get_config_dir() / "audit-ledger.key"
        )
        return load_or_create_hmac_key(key_path, length=32)

    def get_pii_store_path(self) -> Path:
        """Return the path used to persist encrypted PII findings."""
        return self.get_data_dir() / "pii_findings.enc"

    def _get_api_secret_store_key(self) -> bytes:
        """Load (or create) the Fernet key that seals API secrets."""
        key_path = (
            self.api_secret_key_path
            if self.api_secret_key_path is not None
            else self.get_config_dir() / "api-secrets.key"
        )
        return load_or_create_fernet_key(key_path)

    def _get_api_key_path(self, provider: APIKeyName) -> Path:
        """Return the encrypted storage location for ``provider``."""
        return self.get_config_dir() / "secrets" / f"{provider}.api.enc"

    def store_api_key(self, provider: APIKeyName, secret: str) -> None:
        """Persist ``secret`` for ``provider`` using at-rest encryption."""
        path = self._get_api_key_path(provider)
        token = encrypt_blob(secret.encode("utf-8"), key=self._get_api_secret_store_key())
        path.parent.mkdir(parents=True, exist_ok=True)

        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, token)
        finally:
            os.close(fd)
        try:
            os.chmod(path, 0o600)
        except PermissionError:
            # Windows may not support POSIX chmod semantics; ignore best-effort failure.
            pass

        self._api_key_cache[provider] = secret

    def get_api_key(self, provider: APIKeyName) -> str | None:
        """Retrieve the API key for ``provider`` from the encrypted store."""
        if provider in self._api_key_cache:
            return self._api_key_cache[provider]

        path = self._get_api_key_path(provider)
        if not path.exists():
            self._api_key_cache[provider] = None
            return None

        try:
            token = path.read_bytes()
            secret = decrypt_blob(
                token,
                key=self._get_api_secret_store_key(),
            ).decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - any failure leaves storage unreadable
            raise RuntimeError(f"Failed to load API key for provider '{provider}'.") from exc

        self._api_key_cache[provider] = secret
        return secret

    def get_anthropic_api_key(self) -> str | None:
        """Convenience accessor for the Anthropic API key."""
        return self.get_api_key("anthropic")

    def get_deepseek_api_key(self) -> str | None:
        """Convenience accessor for the DeepSeek API key."""
        return self.get_api_key("deepseek")


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
