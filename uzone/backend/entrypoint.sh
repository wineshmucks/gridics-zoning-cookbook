#!/bin/sh
set -eu

if [ "${UZONE_RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade heads
fi

if [ "${UZONE_RUN_SEED_DATA:-false}" = "true" ]; then
  python -m app.scripts.seed_data
fi

if [ "${UZONE_DEV_RELOAD:-true}" = "true" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
