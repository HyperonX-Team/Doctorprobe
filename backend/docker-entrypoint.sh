#!/bin/sh
# Apply pending Alembic migrations, then run the given command (uvicorn).
set -e

echo "[entrypoint] running database migrations..."
alembic upgrade head
echo "[entrypoint] migrations complete."

exec "$@"
