"""Utilities for key management and symmetric encryption."""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def _write_secure_file(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Write ``data`` to ``path`` and restrict permissions.

    Args:
        path: Target file path
        data: Bytes to persist
        mode: File mode to apply (POSIX style)
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)

    try:
        os.chmod(path, mode)
    except PermissionError:
        # Windows may not support POSIX-style chmod; best effort only.
        pass


def load_or_create_fernet_key(path: Path) -> bytes:
    """Load an existing Fernet key from ``path`` or create a new one.

    Returns:
        Base64-encoded Fernet key bytes.
    """
    try:
        return path.read_bytes()
    except FileNotFoundError:
        key = Fernet.generate_key()
        _write_secure_file(path, key)
        return key


def load_or_create_hmac_key(path: Path, *, length: int = 32) -> bytes:
    """Load an existing HMAC key or generate a new random key.

    Args:
        path: Key file location
        length: Number of random bytes to generate

    Returns:
        Raw key bytes suitable for HMAC operations.
    """
    try:
        return path.read_bytes()
    except FileNotFoundError:
        key = secrets.token_bytes(length)
        _write_secure_file(path, key)
        return key


def encrypt_blob(data: bytes, *, key: bytes) -> bytes:
    """Encrypt ``data`` using Fernet symmetric encryption."""
    fernet = Fernet(key)
    return fernet.encrypt(data)


def decrypt_blob(token: bytes, *, key: bytes) -> bytes:
    """Decrypt a token produced by :func:`encrypt_blob`."""
    fernet = Fernet(key)
    return fernet.decrypt(token)


def encode_bytes(data: bytes) -> str:
    """Encode binary data for JSON persistence."""
    return base64.b64encode(data).decode("utf-8")


def decode_bytes(encoded: str) -> bytes:
    """Decode data produced by :func:`encode_bytes`."""
    return base64.b64decode(encoded.encode("utf-8"))
