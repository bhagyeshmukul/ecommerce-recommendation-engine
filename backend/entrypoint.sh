#!/usr/bin/env sh
# Train explicitly through the setup job; API startup never trains a surprise model.
set -eu
alembic upgrade head
python -m src.seed_database
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
