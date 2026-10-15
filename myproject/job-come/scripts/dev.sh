#!/usr/bin/env bash
# Start JC API (uvicorn) + web (Next.js dev).
# Prerequisite: ./scripts/setup-venv.sh, .env (migrations run automatically).
#
# Usage:
#   ./scripts/dev.sh
#
# Optional env:
#   JC_API_HOST=0.0.0.0
#   JC_API_PORT=8000
#   JC_WEB_PORT=3000
#   JC_PYTHON=/path/to/python   # default: deepagents/venv/bin/python
#   JC_SKIP_DB_UPGRADE=1        # start without executing Alembic migrations
#   JC_API_RELOAD=false          # disable Uvicorn file watcher
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
SERVER_ROOT="$(jc_server_root "$JC_ROOT")"
WEB_ROOT="$(jc_web_root "$JC_ROOT")"
PYTHON="$(jc_python "$JC_ROOT")" || {
  echo "[dev] ERROR: cannot find deepagents/venv above ${JC_ROOT}" >&2
  exit 1
}

API_HOST="${JC_API_HOST:-0.0.0.0}"
API_PORT="${JC_API_PORT:-8000}"
WEB_PORT="${JC_WEB_PORT:-3000}"

API_PID=""

log() {
  printf '[dev] %s\n' "$*"
}

die() {
  printf '[dev] ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    log "Stopping API (pid $API_PID)"
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
  API_PID=""
}

trap cleanup EXIT INT TERM

if [[ ! -x "$PYTHON" ]]; then
  die "Python not found: $PYTHON (run ./scripts/setup-venv.sh first)"
fi

if [[ ! -f "${SERVER_ROOT}/.env" ]]; then
  die "Missing .env — copy .env.example to .env and configure it"
fi

if [[ "${JC_SKIP_DB_UPGRADE:-false}" != "true" && "${JC_SKIP_DB_UPGRADE:-0}" != "1" ]]; then
  log "Applying database migrations (alembic upgrade head)"
  JC_PYTHON="$PYTHON" JC_SERVER_ROOT="$SERVER_ROOT" "${JC_ROOT}/scripts/db_upgrade.sh"
else
  log "Skipping database migrations (JC_SKIP_DB_UPGRADE is set)"
fi

if [[ ! -d "${WEB_ROOT}/node_modules" ]]; then
  die "Missing frontend/web/node_modules — run: cd frontend/web && npm install"
fi

if ! command -v npm >/dev/null 2>&1; then
  die "npm not found in PATH"
fi

set -a
# shellcheck disable=SC1091
source "${SERVER_ROOT}/.env"
set +a

wait_for_api() {
  local url="http://127.0.0.1:${API_PORT}/health"
  local i
  for i in $(seq 1 60); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    if [[ -n "$API_PID" ]] && ! kill -0 "$API_PID" 2>/dev/null; then
      die "API process exited before health check passed"
    fi
    sleep 0.5
  done
  die "API did not become healthy at $url (timeout 30s)"
}

log "Starting API on ${API_HOST}:${API_PORT}"
if [[ "${JC_LLM_ENABLED:-false}" != "true" ]]; then
  log "WARN: JC_LLM_ENABLED is not true — resume parse/elevate will use placeholder rules"
fi
cd "${SERVER_ROOT}"
UVICORN_ARGS=(jc.main:app --app-dir "${SERVER_ROOT}/src" --host "$API_HOST" --port "$API_PORT")
if [[ "${JC_API_RELOAD:-true}" == "true" || "${JC_API_RELOAD:-1}" == "1" ]]; then
  UVICORN_ARGS+=(--reload)
fi
"${PYTHON}" -m uvicorn "${UVICORN_ARGS[@]}" &
API_PID=$!

wait_for_api
log "API ready - http://127.0.0.1:${API_PORT}/health"
if [[ "${JC_WEB_CLEAN:-true}" == "true" ]]; then
  log "Cleaning Next.js cache (.next)"
  rm -rf "${WEB_ROOT}/.next"
fi

log "Starting web at http://localhost:${WEB_PORT}"
log "Press Ctrl+C to stop both. Set JC_WEB_CLEAN=false to keep .next cache."

cd "${WEB_ROOT}"
PORT="$WEB_PORT" npm run dev
