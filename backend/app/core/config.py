"""Application configuration.

Settings are loaded from environment variables (and an optional `.env` file)
using `pydantic-settings`. The settings object is cached with
`functools.lru_cache` so it is parsed exactly once per process.
"""

from __future__ import annotations

import functools
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Doctordrobe API.

    Every value can be overridden via a matching environment variable,
    e.g. ``DATABASE_URL``, ``CORS_ORIGINS``, ``FERNET_KEY``.
    """

    #: Human-readable application name, used in logs and responses.
    APP_NAME: str = "Doctordrobe API"

    #: "development" | "production" — switches logging and error verbosity.
    ENV: str = "development"

    #: Enables verbose SQL echo and more permissive behaviour when True.
    DEBUG: bool = False

    #: SQLAlchemy async URL. SQLite for local dev, PostgreSQL in production.
    DATABASE_URL: str = "sqlite:///./doctordrobe.db"

    #: Comma/JSON list of allowed browser origins for CORS.
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    #: Secret used to derive the Fernet symmetric key for report encryption.
    #: Replace with a strong random value in production.
    FERNET_KEY: str = "dev-key-change-me"

    #: If set, `/api/devices/reading` requires the `X-API-Key` header.
    DEVICE_API_KEY: str | None = None

    #: Root log level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    LOG_LEVEL: str = "INFO"

    #: Tokens awarded to a user when they share a checkup.
    TOKEN_REWARD: int = 5

    #: Lifetime of a browser session in days.
    SESSION_TTL_DAYS: int = 30

    #: Minimum accepted password length at registration / change.
    PASSWORD_MIN_LENGTH: int = 8

    #: Login rate limiting: max attempts per IP within the window.
    AUTH_LOGIN_MAX_ATTEMPTS: int = 10
    AUTH_LOGIN_WINDOW_SECONDS: int = 900

    #: A device is considered "connected" if it was seen within this window.
    DEVICE_STALE_SECONDS: int = 300

    #: Snapshots posted closer together than this are treated as one
    #: "burst" of the same strip (see app/services/spectral.py).
    READING_BURST_GAP_SECONDS: float = 45.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def normalize_database_url(url: str) -> str:
    """Ensure plain ``sqlite://`` URLs use the async aiosqlite driver."""
    if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


@functools.lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
