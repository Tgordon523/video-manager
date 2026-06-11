#!/usr/bin/env bash
set -euo pipefail

# Apply DB migrations (idempotent), then start the web app.
echo "Running database migrations..."
alembic upgrade head

echo "Starting Video Manager on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
