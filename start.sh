#!/bin/bash
set -e

export PYTHONPATH="${PYTHONPATH:-/app}"

echo "Running database migrations..."
python -m alembic upgrade head || echo "Migration warning (may be ok on first run)"

echo "Starting web server on port ${PORT:-8000}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
