#!/bin/sh
# Runs before the API starts: apply migrations, optionally load demo data, then exec CMD.
set -e

echo "Applying database migrations..."
alembic upgrade head

if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m scripts.seed
fi

exec "$@"
