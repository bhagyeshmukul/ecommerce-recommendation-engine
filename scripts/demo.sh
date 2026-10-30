#!/usr/bin/env sh
# The explicit prepare step keeps expensive training out of API requests/startup.
set -eu
cd "$(dirname "$0")/.."
docker compose --profile setup run --build --rm prepare
docker compose up --build -d --wait
printf '\nDashboard: http://localhost:5173\nAPI docs: http://localhost:8000/docs\n'
