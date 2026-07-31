# Doctordrobe Backend

FastAPI + SQLAlchemy 2.0 (async) + Alembic. Full documentation for the
whole product lives in the [root README](../README.md); this file covers
backend specifics.

## Stack

- Python 3.11, FastAPI 0.111, Pydantic v2, `pydantic-settings`
- SQLAlchemy 2.0 async ORM — asyncpg (PostgreSQL) / aiosqlite (dev)
- Alembic migrations (initial schema: `alembic/versions/initial_migration.py`)
- Fernet report encryption (`app/utils/crypto.py`)
- Structured JSON logs + request-id middleware (`app/core/logging.py`)

## Layout

```
app/
  main.py            app factory, CORS, exception envelope, /health
  api/routes/        users, checkups, devices, shares
  core/              config (env-driven), security, logging
  db/                base, async session, models
  schemas/           Pydantic v2 request/response models
  services/          deterministic biomarker analyzer + report orchestration
  utils/             crypto, map_range
tests/               pytest + pytest-asyncio (in-memory SQLite)
```

## Configuration

All settings are environment variables (see `.env.example`):

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./doctordrobe.db` | Async DB URL |
| `ENV` | `development` | JSON vs plain logging |
| `DEBUG` | `false` | SQL echo |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | Allowed origins |
| `FERNET_KEY` | `dev-key-change-me` | Report encryption secret |
| `DEVICE_API_KEY` | unset | Enables `X-API-Key` on `/api/devices/reading` |
| `LOG_LEVEL` | `INFO` | Root log level |
| `TOKEN_REWARD` | `5` | Tokens per shared checkup |
| `DEVICE_STALE_SECONDS` | `300` | Device “connected” window |

## Development

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Tests (23): `python -m pytest`. They run against an in-memory async
SQLite database — no services required.

## Docker

`docker build -t doctordrobe-backend .` — the entrypoint runs
`alembic upgrade head` before launching uvicorn; `curl` is installed for
the compose healthcheck.
