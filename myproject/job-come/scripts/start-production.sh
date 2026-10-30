#!/usr/bin/env bash
# Build and run JC in production: migrations, frontend build, API + web.
#
# Usage:
#   ./scripts/start-production.sh              # build, then run both in foreground
#   ./scripts/start-production.sh --build-only # deploy artifact only, no processes
#   ./scripts/start-production.sh --no-build   # restart against the existing .next
#
# Foreground by default so it can be driven by systemd (Type=simple) or run by
# hand during a first deploy. For real supervision use the units in
# `deploy/systemd/`, which start the two processes separately — a single script
# holding both means one crash takes down the other.
#
# Optional env:
#   JC_API_HOST=127.0.0.1   # bind loopback only; Nginx is the public listener
#   JC_API_PORT=8000        # must match the jc_api upstream in the Nginx conf
#   JC_WEB_PORT=3000        # must match the jc_web upstream
#   JC_API_WORKERS=2
#   JC_VENV=/path/to/venv   # default: backend/server/.venv (install-production.sh)
#   JC_PROD_LOG_DIR=/path   # default: <project>/.data/logs/production
if [ -n "${POSIXLY_CORRECT:-}" ] || [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
SERVER_ROOT="$(jc_server_root "$JC_ROOT")"
WEB_ROOT="$(jc_web_root "$JC_ROOT")"

DO_BUILD=true
DO_RUN=true
for arg in "$@"; do
  case "$arg" in
    --build-only) DO_RUN=false ;;
    --no-build) DO_BUILD=false ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "[prod] ERROR: unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# Production installs a dedicated non-editable venv under backend/server/.venv
# (install-production.sh). The monorepo venv is a dev convenience and holds
# editable installs, so it is only a fallback here.
VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"
if [[ -x "${VENV}/bin/python" ]]; then
  PYTHON="${VENV}/bin/python"
else
  PYTHON="$(jc_python "$JC_ROOT")" || {
    echo "[prod] ERROR: no venv at ${VENV} and no monorepo venv — run ./scripts/install-production.sh" >&2
    exit 1
  }
  echo "[prod] WARN: ${VENV} not found, falling back to ${PYTHON} (dev venv, editable installs)" >&2
fi

API_HOST="${JC_API_HOST:-127.0.0.1}"
API_PORT="${JC_API_PORT:-8000}"
WEB_PORT="${JC_WEB_PORT:-3000}"
API_WORKERS="${JC_API_WORKERS:-2}"

LOG_DIR="${JC_PROD_LOG_DIR:-${JC_ROOT}/.data/logs/production}"
mkdir -p "$LOG_DIR"
LOG_DIR="$(cd "$LOG_DIR" && pwd)"

log() { printf '[prod] %s\n' "$*"; }
die() { printf '[prod] ERROR: %s\n' "$*" >&2; exit 1; }

[[ -f "${SERVER_ROOT}/.env" ]] || die "Missing ${SERVER_ROOT}/.env"
[[ -x "$PYTHON" ]] || die "Python not executable: $PYTHON"
command -v npm >/dev/null 2>&1 || die "npm not found in PATH"

# Refuse to start a build that would publish localhost URLs. NEXT_PUBLIC_SITE_URL
# is baked in at build time and has a silent localhost fallback, so an unset
# value produces a sitemap and canonical tags pointing at the crawler's own
# machine — a failure that only shows up weeks later as "nothing got indexed".
#
# `|| true` on both reads: grep exits 1 on no match and 2 on a missing file
# (.env.production.local is optional), and under `set -e` a non-zero command
# substitution aborts the assignment's whole script — killing the run before
# the checks below can report anything.
SITE_URL="$(grep -hE '^NEXT_PUBLIC_SITE_URL=' "${WEB_ROOT}/.env.production" "${WEB_ROOT}/.env.production.local" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
SITE_URL="${NEXT_PUBLIC_SITE_URL:-$SITE_URL}"
case "$SITE_URL" in
  http://localhost*|http://127.0.0.1*|"")
    die "NEXT_PUBLIC_SITE_URL is unset or localhost (got: '${SITE_URL:-unset}').
       Set it in frontend/web/.env.production — canonical, sitemap and OG urls depend on it." ;;
esac
log "Site URL: ${SITE_URL}"

# Verify the production env is internally consistent before anything binds a
# port. An https site served with JC_COOKIE_SECURE=false loses every session,
# and the symptom (pages load, login never sticks) points nowhere near the cause.
COOKIE_SECURE="$(grep -hE '^JC_COOKIE_SECURE=' "${SERVER_ROOT}/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr '[:upper:]' '[:lower:]' || true)"
if [[ "$SITE_URL" == https://* && "$COOKIE_SECURE" != "true" ]]; then
  die "Site is https but JC_COOKIE_SECURE=${COOKIE_SECURE:-unset} — sessions will not persist.
       Set JC_COOKIE_SECURE=true in backend/server/.env."
fi
if [[ "$SITE_URL" == http://* && "$COOKIE_SECURE" == "true" ]]; then
  die "JC_COOKIE_SECURE=true but the site is plain http — the browser will drop every cookie."
fi

log "Applying database migrations (alembic upgrade head)"
JC_PYTHON="$PYTHON" JC_SERVER_ROOT="$SERVER_ROOT" "${JC_ROOT}/scripts/db_upgrade.sh"

if [[ "$DO_BUILD" == true ]]; then
  log "Installing web dependencies (npm ci)"
  cd "${WEB_ROOT}"
  # `npm ci` not `npm install`: it honours the lockfile exactly and wipes
  # node_modules first, so a deploy cannot inherit a half-upgraded tree.
  npm ci
  log "Building web (npm run build)"
  # `JC_API_PROXY_TARGET` must be set HERE, not only on `npm run start` below.
  # `next.config.ts` reads it while evaluating `rewrites()`, which happens at build
  # time and is frozen into `.next/routes-manifest.json`. Setting it only at start
  # produced a production build whose rewrite pointed at the dev default 8001 while
  # the API listens on 8000 — verified in the manifest. Nginx routes `/api/v1`
  # straight to the API so the broken rewrite is normally unreachable, which is what
  # makes it dangerous: any request that does fall through proxies to a dead port
  # and returns 502 with nothing pointing at the cause.
  JC_API_PROXY_TARGET="http://127.0.0.1:${API_PORT}" npm run build
else
  [[ -d "${WEB_ROOT}/.next" ]] || die "--no-build given but ${WEB_ROOT}/.next does not exist"
  log "Skipping build, reusing existing .next"
fi

if [[ "$DO_RUN" != true ]]; then
  log "Build complete (--build-only); not starting processes"
  exit 0
fi

API_PID=""
WEB_PID=""
cleanup() {
  for pid in "$WEB_PID" "$API_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      log "Stopping pid $pid"
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

set -a
# shellcheck disable=SC1091
source "${SERVER_ROOT}/.env"
set +a

log "Starting API on ${API_HOST}:${API_PORT} (${API_WORKERS} workers)"
cd "${SERVER_ROOT}"
# No --reload: the file watcher is a dev tool and doubles memory per worker.
"${PYTHON}" -m uvicorn jc.main:app \
  --app-dir "${SERVER_ROOT}/src" \
  --host "$API_HOST" --port "$API_PORT" \
  --workers "$API_WORKERS" \
  --proxy-headers --forwarded-allow-ips='127.0.0.1' \
  >> "${LOG_DIR}/api.log" 2>&1 &
API_PID=$!

for i in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
  kill -0 "$API_PID" 2>/dev/null || die "API exited before becoming healthy — see ${LOG_DIR}/api.log"
  [[ "$i" == 60 ]] && die "API not healthy after 30s — see ${LOG_DIR}/api.log"
  sleep 0.5
done
log "API healthy at http://127.0.0.1:${API_PORT}/health"

log "Starting web on port ${WEB_PORT}"
cd "${WEB_ROOT}"
# Nginx routes /api/v1 straight to the API, so Next's rewrite is normally not
# used. It is pointed at the right port anyway: when it does get hit — a stray
# direct request to port 3000, or an Nginx conf missing the API location — a
# silent proxy to the dev default 8001 is far harder to diagnose than a 502.
JC_API_PROXY_TARGET="http://127.0.0.1:${API_PORT}" PORT="$WEB_PORT" npm run start \
  >> "${LOG_DIR}/web.log" 2>&1 &
WEB_PID=$!

log "Running. API pid ${API_PID}, web pid ${WEB_PID}. Logs: ${LOG_DIR}"
log "Press Ctrl+C to stop both."
# Exit as soon as either process dies, rather than waiting for both: a dead API
# behind a live web server serves a site that looks up and answers nothing.
wait -n "$API_PID" "$WEB_PID"
die "A process exited — see ${LOG_DIR}/api.log and ${LOG_DIR}/web.log"
