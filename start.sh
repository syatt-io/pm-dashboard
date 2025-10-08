#!/bin/bash
set -e

echo "=== Starting Agent PM Application ==="
echo "Timestamp: $(date)"

# Run database migrations ONCE before starting Gunicorn workers
echo "Running Alembic migrations..."
alembic upgrade head || echo "Alembic migration warning (may be okay if already up to date)"

echo "Starting Gunicorn with 4 workers..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 src.web_interface:app
