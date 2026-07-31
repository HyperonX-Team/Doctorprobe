"""Declarative base shared by all ORM models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Timezone-aware UTC now, used as the default for timestamp columns."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all mapped models."""
