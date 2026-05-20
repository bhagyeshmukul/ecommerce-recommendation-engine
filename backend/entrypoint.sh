#!/usr/bin/env sh
set -e

alembic upgrade head
python -m src.seed_database
uvicorn app.main:app --host 0.0.0.0 --port 8000
