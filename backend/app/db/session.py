"""Async database engine and session management.

PostgreSQL (asyncpg) is used in production; SQLite (aiosqlite) is used for
local development. The URL is switched purely via the ``DATABASE_URL``
environment variable.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings, normalize_database_url

settings = get_settings()

# Normalize plain sqlite:// URLs to the async aiosqlite driver so the
# default dev URL works out of the box.
database_url = normalize_database_url(settings.DATABASE_URL)

_engine_kwargs: dict = {"pool_pre_ping": True}
if database_url.startswith("sqlite"):
    # SQLite runs in-process: a static pool keeps a single in-memory
    # database alive across sessions (used heavily by the test suite).
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    **_engine_kwargs,
)


if database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        """Enforce foreign key constraints on SQLite (off by default)."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session.

    The session is always closed (and rolled back on error) when the
    request is finished.
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
