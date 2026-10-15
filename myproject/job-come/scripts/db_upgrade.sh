#!/usr/bin/env bash
# Apply Alembic migrations for the JC schema.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
SERVER_ROOT="${JC_SERVER_ROOT:-$(jc_server_root "$JC_ROOT")}"
PYTHON="$(jc_python "$JC_ROOT")" || {
  echo "[db-upgrade] ERROR: cannot find deepagents/venv above ${JC_ROOT}" >&2
  exit 1
}

[[ -d "$SERVER_ROOT" ]] || { echo "[db-upgrade] ERROR: server root missing: $SERVER_ROOT" >&2; exit 1; }
[[ -x "$PYTHON" ]] || { echo "[db-upgrade] ERROR: Python not found: $PYTHON" >&2; exit 1; }
[[ -f "$SERVER_ROOT/alembic.ini" ]] || {
  echo "[db-upgrade] ERROR: missing $SERVER_ROOT/alembic.ini" >&2
  exit 1
}
cd "$SERVER_ROOT"
exec "$PYTHON" -m alembic -c "$SERVER_ROOT/alembic.ini" upgrade head
