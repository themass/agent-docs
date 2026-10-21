#!/usr/bin/env bash
# Start JC API (uvicorn) + web (Next.js dev).
# Prerequisite: ./scripts/setup-venv.sh, .env (migrations run automatically).
#
# Usage:
#   ./scripts/dev.sh
#   (or: bash scripts/dev.sh — do not use `sh`, which is not bash on macOS)
#
# This script is single-instance: on every start it kills whatever is
# already listening on the target ports (including a previous run of this
# same script, or one started by someone else) before binding. Re-running
# it is always safe and always leaves exactly one instance alive.
#
# Optional env:
#   JC_API_HOST=0.0.0.0
#   JC_API_PORT=8001
#   JC_WEB_PORT=3000
#   JC_PYTHON=/path/to/python   # default: deepagents/venv/bin/python
#   JC_SKIP_DB_UPGRADE=1        # start without executing Alembic migrations
#   JC_API_RELOAD=false          # disable Uvicorn file watcher
#   JC_WEB_CLEAN=false           # keep .next cache instead of wiping it
#   JC_DEV_LOG_DIR=/path/to/logs # default: <project>/.data/logs/dev
# Process substitution (`> >(…)`) requires bash. macOS `/bin/sh` is bash --posix,
# which still sets BASH_VERSION but rejects `>(…)`.
if [ -n "${POSIXLY_CORRECT:-}" ] || [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

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
API_PORT="${JC_API_PORT:-8001}"
WEB_PORT="${JC_WEB_PORT:-3000}"

API_PID=""

# Redirection, not `uvicorn | tee &`: $! must remain the real API PID so
# wait_for_api and cleanup keep managing uvicorn rather than the logging process.
LOG_DIR="${JC_DEV_LOG_DIR:-${JC_ROOT}/.data/logs/dev}"
mkdir -p "$LOG_DIR"
LOG_DIR="$(cd "$LOG_DIR" && pwd)"
LOG_SINK="${JC_ROOT}/scripts/lib/log_output.py"
export PYTHONUNBUFFERED=1
exec > >("$PYTHON" "$LOG_SINK" "${LOG_DIR}/dev.log") 2>&1

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

# Free a TCP port by killing whatever process is listening on it (any prior
# run of this script, a leftover uvicorn/next process, etc). Best-effort:
# ignores failures from processes we don't own or that already exited.
free_port() {
  local port="$1"
  local pids
  pids="$(lsof -nP -t "-iTCP:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    log "Port ${port} is in use (pid(s): $(echo "$pids" | tr '\n' ' ')) — stopping to restart cleanly"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
}

log "Local logs: ${LOG_DIR} (dev.log / api.log / web.log; 10 MiB × 4 each)"
log "Ensuring ports ${API_PORT} and ${WEB_PORT} are free before starting"
free_port "${API_PORT}"
free_port "${WEB_PORT}"

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
"${PYTHON}" -m uvicorn "${UVICORN_ARGS[@]}" \
  > >("$PYTHON" "$LOG_SINK" "${LOG_DIR}/api.log") 2>&1 &
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
JC_API_PROXY_TARGET="http://127.0.0.1:${API_PORT}" PORT="$WEB_PORT" npm run dev \
  > >("$PYTHON" "$LOG_SINK" "${LOG_DIR}/web.log") 2>&1
