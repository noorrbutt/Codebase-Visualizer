#!/bin/sh
# Migrations run before the app starts. `set -e` makes a failed migration exit non-zero,
# so the container stops instead of serving against an outdated schema.
set -eu

echo "Running database migrations..."
alembic upgrade head

# Single worker: analyses run as in-process BackgroundTasks and startup resumes them,
# so multiple workers would duplicate that work.
echo "Starting API on 0.0.0.0:7860"
exec uvicorn app.main:app --host 0.0.0.0 --port 7860 --workers 1
