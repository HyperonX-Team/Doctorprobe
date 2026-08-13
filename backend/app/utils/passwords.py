"""Password hashing and verification (PBKDF2-HMAC-SHA256, stdlib only).

Stored format: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`` so the
iteration count and salt travel with the hash, which lets us raise the
cost later without invalidating existing rows.

Iterations follow the OWASP recommendation for PBKDF2-HMAC-SHA256
(600,000). Verification is constant-time via ``hmac.compare_digest``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16
_HASH_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a plaintext password into the portable storage format."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    )
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Return True when ``password`` matches the stored hash.

    Accepts hashes produced by this module; anything else fails closed.
    """
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False
