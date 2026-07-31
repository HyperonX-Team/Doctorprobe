"""Alembic environment.

The target URL comes from the application settings (which read
``DATABASE_URL`` from the environment), so migrations work identically
against SQLite (dev) and PostgreSQL (production).

The migration engine is async; SQLite connections are coerced to run
statements synchronously via ``connection.run_sync``.
"""

from __future__ import annotations

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings, normalize_database_url
from app.db.base import Base
from app import models  # noqa: F401 — ensures all tables are registered

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Force the URL from application settings (environment variable driven).
config.set_main_option(
    "sqlalchemy.url", normalize_database_url(get_settings().DATABASE_URL)
)

target_metadata = Base.metadata

logger = logging.getLogger("alembic.runtime.migration")


def run_migrations_offline() -> None:
    """Emit SQL without a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on a sync connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and drive migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the configured database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
