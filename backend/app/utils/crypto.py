"""Fernet encryption helpers for report payloads at rest.

The Fernet key is derived from ``settings.FERNET_KEY`` using SHA-256 so any
non-empty secret string works. For production, generate a strong key:

    >>> python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

and export it as ``FERNET_KEY``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Build (and cache) the Fernet cipher from the configured secret."""
    global _fernet
    if _fernet is None:
        settings = get_settings()
        if not settings.FERNET_KEY:
            raise RuntimeError("FERNET_KEY must be set")
        # Derive a 32-byte urlsafe-base64 key from any secret string.
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(settings.FERNET_KEY.encode("utf-8")).digest()
        )
        _fernet = Fernet(derived)
    return _fernet


def encrypt_json(data: dict[str, Any]) -> str:
    """Serialize ``data`` to JSON and encrypt it, returning a Fernet token."""
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return _get_fernet().encrypt(payload).decode("ascii")


def decrypt_json(encrypted: str) -> dict[str, Any]:
    """Decrypt a Fernet token produced by :func:`encrypt_json`."""
    payload = _get_fernet().decrypt(encrypted.encode("ascii"))
    return json.loads(payload.decode("utf-8"))
