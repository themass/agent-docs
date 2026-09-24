#!/usr/bin/env bash
# Start JobCome API (uvicorn) + web (Next.js dev).
# Prerequisite: ./scripts/setup-venv.sh, .env (migrations run automatically).
#
# Usage:
#   ./scripts/dev.sh
#
# Optional env:
#   JOB_COME_API_HOST=0.0.0.0
#   JOB_COME_API_PORT=8000
#   JOB_COME_WEB_PORT=3000
#   JOB_COME_PYTHON=/path/to/python   # default: ../venv/bin/python
set -euo pipefail

JOB_COME_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MONO_ROOT="$(cd "${JOB_COME_ROOT}/.." && pwd)"
PYTHON="${JOB_COME_PYTHON:-${MONO_ROOT}/venv/bin/python}"

API_HOST="${JOB_COME_API_HOST:-0.0.0.0}"
API_PORT="${JOB_COME_API_PORT:-8000}"
WEB_PORT="${JOB_COME_WEB_PORT:-3000}"

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

if [[ ! -f "${JOB_COME_ROOT}/.env" ]]; then
  die "Missing .env — copy .env.example to .env and configure it"
fi

log "Applying database migrations (alembic upgrade head)"
"${JOB_COME_ROOT}/scripts/db_upgrade.sh"

if [[ ! -d "${JOB_COME_ROOT}/apps/web/node_modules" ]]; then
  die "Missing apps/web/node_modules — run: cd apps/web && npm install"
fi

if ! command -v npm >/dev/null 2>&1; then
  die "npm not found in PATH"
fi

set -a
# shellcheck disable=SC1091
source "${JOB_COME_ROOT}/.env"
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
if [[ "${JOB_COME_LLM_ENABLED:-false}" != "true" ]]; then
  log "WARN: JOB_COME_LLM_ENABLED is not true — resume parse/elevate will use placeholder rules"
fi
cd "${JOB_COME_ROOT}"
"${PYTHON}" -m uvicorn jobcome.main:app \
  --reload \
  --host "$API_HOST" \
  --port "$API_PORT" &
API_PID=$!

wait_for_api
log "API ready - http://127.0.0.1:${API_PORT}/health"
if [[ "${JOB_COME_WEB_CLEAN:-true}" == "true" ]]; then
  log "Cleaning Next.js cache (.next)"
  rm -rf "${JOB_COME_ROOT}/apps/web/.next"
fi

log "Starting web at http://localhost:${WEB_PORT}"
log "Press Ctrl+C to stop both. Set JOB_COME_WEB_CLEAN=false to keep .next cache."

cd "${JOB_COME_ROOT}/apps/web"
PORT="$WEB_PORT" npm run dev
