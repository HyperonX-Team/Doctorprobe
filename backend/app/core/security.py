"""Security helpers: device API key and browser session verification.

Two independent trust domains:

* **Devices** authenticate with a shared ``X-API-Key`` header
  (``verify_device_api_key``) — enforced as a dependency on the
  device-ingest endpoints.
* **Browsers** authenticate with an opaque bearer token
  (``get_current_user``) issued by ``POST /api/auth/login|register`` and
  stored (hashed) in the ``sessions`` table. The dependency resolves the
  session to its user; endpoints never trust a client-supplied user id.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.session import Session, token_digest
from app.models.user import User

_BEARER_PREFIX = "Bearer "


async def verify_device_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Require a valid `X-API-Key` header when `DEVICE_API_KEY` is configured.

    When ``DEVICE_API_KEY`` is unset (local development) the check is
    skipped so the ESP32 device can post readings without secrets.
    Comparison is constant-time to avoid timing attacks.
    """
    settings = get_settings()
    if not settings.DEVICE_API_KEY:
        return

    if x_api_key is None or not hmac.compare_digest(
        x_api_key, settings.DEVICE_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def _bearer_token(authorization: str | None) -> str:
    """Extract the token from an ``Authorization: Bearer ...`` header."""
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[len(_BEARER_PREFIX):].strip()


async def get_current_session(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Session:
    """Resolve the bearer token to a live (non-revoked, non-expired) session."""
    token = _bearer_token(authorization)
    result = await db.execute(
        select(Session).where(Session.token_hash == token_digest(token))
    )
    session = result.scalar_one_or_none()
    if session is None or not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session


async def get_current_user(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated session to its user row (404 if missing)."""
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
