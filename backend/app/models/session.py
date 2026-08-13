"""Session ORM model: opaque bearer tokens for browser sessions.

The token handed to the client is random and only its SHA-256 digest is
stored, so a database leak does not expose usable session tokens.
Sessions can be revoked individually (logout) or in bulk (password
change, account deletion) without issuing new tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


def generate_session_token() -> str:
    """Return a fresh random bearer token (url-safe, 32 bytes)."""
    import secrets

    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """SHA-256 digest of a session token — what is actually stored."""
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def default_expiry() -> datetime:
    """Expiry of a newly created session (now + SESSION_TTL_DAYS)."""
    return datetime.now(timezone.utc) + timedelta(
        days=get_settings().SESSION_TTL_DAYS
    )


class Session(Base):
    """One logged-in browser session for a user."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=default_expiry, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="sessions")

    @property
    def is_active(self) -> bool:
        """A session is usable when not revoked and not expired."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            # SQLite returns naive datetimes; treat them as UTC before
            # comparing against the aware clock.
            expires = self.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= datetime.now(timezone.utc):
                return False
        return True
