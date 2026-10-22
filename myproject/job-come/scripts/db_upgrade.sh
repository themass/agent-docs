#!/usr/bin/env bash
# Apply Alembic migrations for the JC schema.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
# shellcheck source=lib/ensure_python_env.sh
source "${JC_ROOT}/scripts/lib/ensure_python_env.sh"
SERVER_ROOT="${JC_SERVER_ROOT:-$(jc_server_root "$JC_ROOT")}"
PYTHON="$(jc_python "$JC_ROOT")" || {
  echo "[db-upgrade] ERROR: cannot find deepagents/venv above ${JC_ROOT}" >&2
  exit 1
}

[[ -d "$SERVER_ROOT" ]] || { echo "[db-upgrade] ERROR: server root missing: $SERVER_ROOT" >&2; exit 1; }
[[ -x "$PYTHON" ]] || { echo "[db-upgrade] ERROR: Python not found: $PYTHON" >&2; exit 1; }
jc_ensure_python_env "$JC_ROOT" "$PYTHON" || exit 1
[[ -f "$SERVER_ROOT/alembic.ini" ]] || {
  echo "[db-upgrade] ERROR: missing $SERVER_ROOT/alembic.ini" >&2
  exit 1
}

# Must use the venv `alembic` entrypoint (see jc_alembic_bin in ensure_python_env.sh).
ALEMBIC_BIN="$(jc_alembic_bin "$PYTHON")"
if [[ ! -x "$ALEMBIC_BIN" ]]; then
  echo "[db-upgrade] ERROR: Alembic CLI not found: $ALEMBIC_BIN" >&2
  echo "[db-upgrade] Run: ${JC_ROOT}/scripts/setup-venv.sh" >&2
  exit 1
fi
cd "$SERVER_ROOT"
exec "$ALEMBIC_BIN" -c "$SERVER_ROOT/alembic.ini" upgrade head
