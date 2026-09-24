#!/usr/bin/env bash
# JobCome regression CI — fixtures, export HTML, optional PDF (needs playwright browsers).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${JOB_COME_PYTHON:-$ROOT/../venv/bin/python}"

cd "$ROOT"
echo "==> pytest regression + export"
"$PY" -m pytest \
  tests/test_regression_fixtures.py \
  tests/test_export_pdf.py \
  tests/test_coach_followups.py \
  tests/test_mcp_handlers.py \
  tests/test_e2e_openapi_routes.py \
  -q

echo "==> ci_regression done"
