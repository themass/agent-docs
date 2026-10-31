#!/usr/bin/env bash
# Start / stop / restart / status for the JC web (Next.js `next start`), tracked by
# a PID file. See backend.sh for why this is PID-file based rather than systemd.
#
# This serves a build, it does not make one — run ./scripts/deploy.sh (or
# ./scripts/deploy.sh --skip-backend) after any code change before `restart`.
# `next start` on a stale `.next` silently serves the previous release; there is
# no error to catch, which is why deploy.sh and this script are separate steps
# rather than one that might skip the part that actually matters.
#
# Usage:
#   ./scripts/frontend.sh start|stop|restart|status
#
# Env:
#   JC_WEB_PORT=3000        must match the jc_web upstream in the Nginx conf
#   JC_API_PORT=8000        passed through so Next's (normally unused) rewrite
#                           points at the real API port instead of the dev default
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_ROOT="${JC_ROOT}/frontend/web"
# shellcheck source=lib/daemon.sh
source "${JC_ROOT}/scripts/lib/daemon.sh"

WEB_PORT="${JC_WEB_PORT:-3000}"
API_PORT="${JC_API_PORT:-8000}"

RUN_DIR="${JC_ROOT}/.data/run"
LOG_DIR="${JC_PROD_LOG_DIR:-${JC_ROOT}/.data/logs/production}"
PIDFILE="${RUN_DIR}/web.pid"
LOGFILE="${LOG_DIR}/web.log"
MARKER="next-server"

log() { printf '[frontend] %s\n' "$*"; }
die() { printf '[frontend] ERROR: %s\n' "$*" >&2; exit 1; }

# No dedicated health route on the Next side, so "healthy" means "a request to
# the port got an HTTP response at all" — any status code, including a login
# redirect, proves the server is up; curl's own connection failure (code 000)
# is the only thing that means it is not.
check_health() {
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${WEB_PORT}/" 2>/dev/null || echo 000)"
  [[ "$code" != "000" ]]
}

# `next start`'s own process forks the long-lived "next-server" and then exits
# once the handoff is done (verified directly: the PID `$!` captures becomes
# unreachable within a couple seconds while a *different*, init-reparented PID
# keeps answering on the port) — so $! cannot be trusted as the PID to manage.
# This finds the one actually holding the port, which is the only thing that is
# true of the real server for its entire life.
resolve_web_pid() {
  lsof -t -iTCP:"${WEB_PORT}" -sTCP:LISTEN 2>/dev/null | head -1
}

cmd_start() {
  [[ -d "${WEB_ROOT}/.next" ]] || die "no build at ${WEB_ROOT}/.next — run ./scripts/deploy.sh first"
  local next_bin="${WEB_ROOT}/node_modules/.bin/next"
  [[ -x "$next_bin" ]] || die "missing ${next_bin} — run ./scripts/deploy.sh first"
  command -v lsof >/dev/null 2>&1 || die "lsof not found — needed to track the real next-server pid"

  # `next` directly, not `npm run start`: npm runs the script in a child shell, so
  # the PID this script would track is npm's wrapper, not the Next server itself.
  #
  # Nginx routes /api/v1 straight to the API, so this rewrite is normally unused;
  # pointed at the real port anyway so a stray direct hit does not silently proxy
  # to the dev default 8001 (far harder to diagnose than a clean 502).
  JC_API_PROXY_TARGET="http://127.0.0.1:${API_PORT}" \
    daemon_start frontend "$PIDFILE" "$LOGFILE" "$MARKER" check_health resolve_web_pid \
    "$next_bin" start --port "$WEB_PORT"
}

case "${1:-}" in
  start) cd "$WEB_ROOT"; cmd_start ;;
  stop) daemon_stop frontend "$PIDFILE" ;;
  restart) daemon_stop frontend "$PIDFILE"; cd "$WEB_ROOT"; cmd_start ;;
  status) daemon_status frontend "$PIDFILE" "$MARKER" ;;
  *) die "usage: $0 start|stop|restart|status" ;;
esac
