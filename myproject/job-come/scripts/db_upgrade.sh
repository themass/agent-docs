#!/usr/bin/env bash
# Apply Alembic migrations for JobCome schema.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VENV="${JOB_COME_VENV:-../venv}"
exec "$VENV/bin/alembic" upgrade head
