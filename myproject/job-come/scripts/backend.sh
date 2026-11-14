#!/usr/bin/env bash
# Start / stop / restart / status for the JC API (uvicorn), tracked by a PID file.
#
# No systemd, no sudo: it runs the process detached with `setsid` so it survives
# this script (and the SSH session that launched it) exiting, and self-checks
# `/health` before `start` reports success — a process that launches but never
# answers is exactly the failure a bare "it's running" check would miss.
#
# Usage:
#   ./scripts/backend.sh start|stop|restart|status
#
# Env:
#   JC_API_HOST=127.0.0.1   bind loopback only; Nginx is the public listener
#   JC_API_PORT=8000        must match the jc_api upstream in the Nginx conf
#   JC_API_WORKERS=2
#   JC_VENV=/path/to/venv   default: backend/server/.venv (./scripts/deploy.sh)
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
# shellcheck source=lib/daemon.sh
source "${JC_ROOT}/scripts/lib/daemon.sh"
# shellcheck source=lib/deploy_env.sh
source "${JC_ROOT}/scripts/lib/deploy_env.sh"
jc_load_deploy_env "$JC_ROOT"

VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"
API_HOST="${JC_API_HOST:-127.0.0.1}"
API_PORT="${JC_API_PORT:-8000}"
API_WORKERS="${JC_API_WORKERS:-2}"

RUN_DIR="${JC_ROOT}/.data/run"
LOG_DIR="${JC_PROD_LOG_DIR:-${JC_ROOT}/.data/logs/production}"
PIDFILE="${RUN_DIR}/api.pid"
LOGFILE="${LOG_DIR}/api.log"
MARKER="jc.main:app"

log() { printf '[backend] %s\n' "$*"; }
die() { printf '[backend] ERROR: %s\n' "$*" >&2; exit 1; }

check_health() { curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; }

cmd_start() {
  # Refuse to run as root, same rule as publish.sh and for the same reason: a process
  # started as root writes files (pid, logs, the metrics mmap directory) that the `web`
  # user cannot later update, so every subsequent restart by the real owner fails with
  # permission errors far from their cause. It also owned a directory tree whose files
  # the deploy user then could not remove.
  [[ "$(id -u)" -ne 0 ]] || die "run as the web user, not root: files created as root cannot be updated by the user that runs the services"
  [[ -x "${VENV}/bin/python" ]] || die "no venv at ${VENV} — run ./scripts/deploy.sh first"
  [[ -f "${SERVER_ROOT}/.env" ]] || die "missing ${SERVER_ROOT}/.env"

  # The venv's interpreter, not the system `python3`: they are unrelated once
  # the venv exists, and on a host whose python3 is 3.10 the two versions in
  # play are far enough apart that "which one is this actually running on" is
  # a question worth answering in the log rather than at the next crash.
  local py_version
  py_version="$("${VENV}/bin/python" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true)"
  [[ -n "$py_version" ]] || die "${VENV}/bin/python does not run — the venv is broken, re-run ./scripts/deploy.sh"
  [[ "$py_version" == 3.12.* ]] || die "venv runs Python ${py_version}, project requires 3.12.x.
       Rebuild it: rm -rf ${VENV} && ./scripts/deploy.sh --skip-frontend"
  log "python: ${VENV}/bin/python (${py_version})"

  # Checked on every start, not only at deploy time, because it is read from
  # .env — a file someone can edit without re-running deploy.sh — and the
  # failure it prevents (pages load, every login silently fails to persist)
  # is otherwise nowhere near its cause.
  local cookie_secure public_url
  cookie_secure="$(grep -hE '^JC_COOKIE_SECURE=' "${SERVER_ROOT}/.env" 2>/dev/null \
    | tail -1 | cut -d= -f2- | tr '[:upper:]' '[:lower:]' || true)"
  public_url="$(grep -hE '^JC_PUBLIC_URL=' "${SERVER_ROOT}/.env" 2>/dev/null \
    | tail -1 | cut -d= -f2- || true)"
  if [[ "$public_url" == https://* && "$cookie_secure" != "true" ]]; then
    die "JC_PUBLIC_URL is https but JC_COOKIE_SECURE=${cookie_secure:-unset} — sessions will not persist.
       Set JC_COOKIE_SECURE=true in ${SERVER_ROOT}/.env."
  fi
  if [[ "$public_url" == http://* && "$cookie_secure" == "true" ]]; then
    die "JC_COOKIE_SECURE=true but JC_PUBLIC_URL is plain http — the browser will drop every cookie."
  fi

  # --- metrics counter sharing across workers ---------------------------------
  # prometheus_client decides how to store every counter at IMPORT time
  # (`values.py`: `ValueClass = get_value_class()`), reading
  # PROMETHEUS_MULTIPROC_DIR from the environment. Setting it later — inside the
  # app, from .env, after the import — has no effect at all, and the failure is
  # silent: metrics appear to work while each worker counts alone, so a scrape
  # reports one worker's traffic as if it were the service's.
  #
  # So it is exported here, before python starts. The directory is wiped on every
  # start because each worker writes `<type>_<pid>.db` and a worker killed with
  # SIGKILL never calls mark_process_dead: leftovers from a previous run would be
  # summed into this run's totals forever, and the number would only ever grow.
  local mp_dir
  mp_dir="$(grep -hE '^JC_METRICS_MULTIPROCESS_DIR=' "${SERVER_ROOT}/.env" 2>/dev/null \
    | tail -1 | cut -d= -f2- | tr -d '"'"'"' ' || true)"
  if [[ -n "$mp_dir" ]]; then
    # A relative path would resolve against uvicorn's cwd, which is not the
    # directory this script thinks it is.
    [[ "$mp_dir" == /* ]] || mp_dir="${JC_ROOT}/${mp_dir}"
    rm -rf "$mp_dir"
    mkdir -p "$mp_dir"
    export PROMETHEUS_MULTIPROC_DIR="$mp_dir"
    log "metrics: counters shared across workers in ${mp_dir}"
  else
    # An inherited value from the calling shell would silently change behaviour
    # between an interactive `restart` and a cron one.
    unset PROMETHEUS_MULTIPROC_DIR
    if [[ "$API_WORKERS" != "1" ]]; then
      log "metrics: per-worker counters (${API_WORKERS} workers) — set JC_METRICS_MULTIPROCESS_DIR in .env to aggregate"
    fi
  fi

  DAEMON_PORT="${API_PORT}" daemon_start backend "$PIDFILE" "$LOGFILE" "$MARKER" check_health - \
    "${VENV}/bin/python" -m uvicorn jc.main:app \
    --app-dir "${SERVER_ROOT}/src" \
    --host "$API_HOST" --port "$API_PORT" \
    --workers "$API_WORKERS" \
    --proxy-headers --forwarded-allow-ips='127.0.0.1'
    # The `-` above means "trust $!, no pid resolver needed": uvicorn's master
    # process supervises its workers for the whole run and never hands off and
    # exits the way `next start` does (see frontend.sh), so $! stays valid.
}

case "${1:-}" in
  start) cd "$SERVER_ROOT"; cmd_start ;;
  stop) daemon_stop backend "$PIDFILE" "$MARKER" ;;
  restart) daemon_stop backend "$PIDFILE" "$MARKER"; cd "$SERVER_ROOT"; cmd_start ;;
  status) daemon_status backend "$PIDFILE" "$MARKER" ;;
  *) die "usage: $0 start|stop|restart|status" ;;
esac
