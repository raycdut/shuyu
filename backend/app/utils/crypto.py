"""Symmetric encryption utility for sensitive data (passwords, API keys).

Uses Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from AUTH_SECRET_KEY.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

logger = logging.getLogger("shuyu.crypto")

_FERNET_INSTANCE = None


def _get_key() -> bytes:
    """Derive a Fernet-compatible 32-byte key from AUTH_SECRET_KEY or env."""
    from ..auth.service import SECRET_KEY

    if SECRET_KEY:
        raw = SECRET_KEY.encode("utf-8")
    else:
        raw = os.environ.get("AUTH_SECRET_KEY", "").encode("utf-8")
    if not raw:
        logger.warning("AUTH_SECRET_KEY is empty, using fallback key")
        raw = b"shuyu-fallback-key-do-not-use-in-production"
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())


def _get_fernet():
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is None:
        from cryptography.fernet import Fernet

        _FERNET_INSTANCE = Fernet(_get_key())
    return _FERNET_INSTANCE


def encrypt_value(plaintext: str | None) -> str | None:
    """Encrypt a plaintext string. Returns None if input is None or empty."""
    if not plaintext:
        return plaintext
    try:
        f = _get_fernet()
        token = f.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return plaintext


def decrypt_value(ciphertext: str | None) -> str | None:
    """Decrypt a ciphertext string. Returns None if input is None or empty."""
    if not ciphertext:
        return ciphertext
    try:
        f = _get_fernet()
        plain = f.decrypt(ciphertext.encode("utf-8"))
        return plain.decode("utf-8")
    except Exception:
        # If decryption fails, return as-is (legacy plaintext data)
        return ciphertext


def reset_cache():
    """Reset the cached Fernet instance (useful in tests)."""
    global _FERNET_INSTANCE
    _FERNET_INSTANCE = None
