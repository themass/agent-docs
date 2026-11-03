#!/usr/bin/env bash
# Get a host ready and deploy the app on it: install the tools that are missing, install the
# Python dependencies, migrate the database, build the frontend. Starts nothing - that is
# backend.sh / frontend.sh's job, run separately so a build can be inspected before the
# running service is switched onto it.
#
# Usage:
#   ./scripts/deploy.sh                  # everything
#   ./scripts/deploy.sh --env-only       # only install what is missing, deploy nothing
#   ./scripts/deploy.sh --skip-backend   # frontend build only
#   ./scripts/deploy.sh --skip-frontend  # backend install + migrate only
#   ./scripts/deploy.sh --python-default # also make CPython 3.12 this user's python3
#
# Tools. Everything below is installed into the invoking user's home, without sudo and
# without editing shell profiles, so the web user can prepare a bare machine by itself:
#   uv        into ~/.local/bin, when missing
#   Python    3.12 by uv, privately; the system python3 is never touched. --python-default
#             also puts shims in ~/.local/bin so a new shell's `python3` is 3.12 too
#             (existing shells need `source ~/.local/bin/env`)
#   Node      20, under ~/.local/node, when none >= 18.18 is on PATH. Checksum-verified
# Only these need an administrator, and are reported together before anything is
# downloaded: curl or wget, tar, gzip, and lsof for the frontend.
#
#   JC_DEPLOY_HEARTBEAT_SEC=30   # stdout heartbeat during long steps (SSH keepalive)
#   JC_NODE_DIST_URLS, JC_UV_INSTALLER_URL     # mirrors for the tool downloads
#   JC_NPM_REGISTRY, JC_NPM_REPLACE_REGISTRY_HOST=always   # npm ci via a mirror
#   JC_SKIP_NPM_CI=1             # use an already-extracted node_modules, skip npm ci
#                                 entirely (for a host where even the mirror is too
#                                 slow/unreachable); frontend/web/node_modules must
#                                 already be a real install of THIS package-lock.json
#
# After this: ./scripts/backend.sh restart && ./scripts/frontend.sh restart
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
WEB_ROOT="${JC_ROOT}/frontend/web"
# shellcheck source=lib/run_with_heartbeat.sh
source "${JC_ROOT}/scripts/lib/run_with_heartbeat.sh"
# shellcheck source=lib/tools_env.sh
source "${JC_ROOT}/scripts/lib/tools_env.sh"

log() { printf '[deploy] %s\n' "$*"; }
jc_heartbeat_log=log
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }
HEARTBEAT="${JC_DEPLOY_HEARTBEAT_SEC:-30}"

DO_BACKEND=true
DO_FRONTEND=true
PYTHON_DEFAULT=false
ENV_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --skip-backend) DO_BACKEND=false ;;
    --skip-frontend) DO_FRONTEND=false ;;
    --python-default) PYTHON_DEFAULT=true ;;
    --env-only) ENV_ONLY=true ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) die "unknown argument: $arg" ;;
  esac
done

VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"

# 1. What only an administrator can install. Reported together, before any download, so a
#    bare machine is not discovered missing one thing at a time.
if [[ "$DO_FRONTEND" == true ]]; then
  jc_check_system_tools lsof || exit 1
else
  jc_check_system_tools || exit 1
fi

# 2. Checks on the checkout itself, which need no network. They run before the tools are
#    installed so a missing .env is reported in a second, not after a download.
if [[ "$ENV_ONLY" != true ]]; then
  if [[ "$DO_BACKEND" == true ]]; then
    if ! compgen -G "${SERVER_ROOT}/wheels/*.whl" >/dev/null; then
      die "no wheels in ${SERVER_ROOT}/wheels/.
       pyproject.toml sources agentkit/deerflow-harness/deerflow-extension-api from
       those files. Build them on a machine with the monorepo checkout:
         ./scripts/build-release.sh --update
       and commit backend/server/wheels/."
    fi
    [[ -f "${SERVER_ROOT}/.env" ]] || die "missing ${SERVER_ROOT}/.env (copy from .env.example)"
  fi
  if [[ "$DO_FRONTEND" == true ]]; then
    # Refuse to build with a localhost site URL: NEXT_PUBLIC_SITE_URL is baked into
    # the build (canonical tags, sitemap, OG urls) and has a silent localhost
    # fallback, so an unset value only shows up weeks later as "nothing got indexed".
    #
    # `|| true` on both reads: grep exits 1 on no match and 2 on a missing file
    # (.env.production.local is optional), and under `set -e` a nonzero command
    # substitution would abort the assignment before the check below can report it.
    SITE_URL="$(grep -hE '^NEXT_PUBLIC_SITE_URL=' "${WEB_ROOT}/.env.production" "${WEB_ROOT}/.env.production.local" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
    SITE_URL="${NEXT_PUBLIC_SITE_URL:-$SITE_URL}"
    case "$SITE_URL" in
      http://localhost*|http://127.0.0.1*|"")
        die "NEXT_PUBLIC_SITE_URL is unset or localhost (got: '${SITE_URL:-unset}').
         Set it in frontend/web/.env.production." ;;
    esac
    log "site URL: ${SITE_URL}"

  fi
fi

# 3. The tools themselves.
if [[ "$DO_BACKEND" == true ]]; then
  jc_ensure_uv || exit 1
  # shellcheck source=lib/python_env.sh
  source "${JC_ROOT}/scripts/lib/python_env.sh"
  # `--python-default` (opt-in) also makes uv's 3.12 what plain `python3` resolves
  # to for this user, via shims in ~/.local/bin. Left off by default because it
  # changes the user's PATH resolution; --update-style surprises are worse than an
  # explicit flag.
  ensure_args=()
  [[ "$PYTHON_DEFAULT" == true ]] && ensure_args=(--install-default)
  # `${arr[@]+"${arr[@]}"}` not `"${arr[@]}"`: bash 3.2 (macOS /bin/bash) treats an
  # empty array under `set -u` as an unbound variable and aborts the script.
  # Heartbeat-wrapped: the steady-state path (uv already has 3.12) is instant and
  # this stays silent, but a cold host downloads a standalone CPython build with
  # no progress output of its own - without this it looks identical to a hang.
  jc_run_with_heartbeat "python 3.12 resolve/install" "$HEARTBEAT" \
    jc_ensure_python ${ensure_args[@]+"${ensure_args[@]}"} || die "no Python 3.12 and uv could not install one.
       Required by pyproject.toml (>=3.12,<3.13). The system python3 is deliberately
       left alone - apt/yum depend on it - and uv installs a private 3.12 instead.
       To also make it this user's default: ./scripts/deploy.sh --python-default"
  log "uv:      $(uv --version 2>&1)"
  log "python:  ${JC_PYTHON_BIN} ($("$JC_PYTHON_BIN" -V 2>&1))"
fi
if [[ "$DO_FRONTEND" == true ]]; then
  jc_run_with_heartbeat "node ${JC_NODE_MAJOR} resolve/install" "$HEARTBEAT" jc_ensure_node || exit 1
  log "node:    $(node -v)   npm: $(npm -v)   ($(command -v node))"
fi
if [[ "$ENV_ONLY" == true ]]; then
  log "environment ready - nothing was deployed (--env-only)"
  exit 0
fi

if [[ "$DO_BACKEND" == true ]]; then
  log "installing Python dependencies into ${VENV}"
  # `--extra export` is not optional here: it is what installs playwright, which
  # `resume_render_engine.render_pdf` needs. Without it every PDF export dies at
  # runtime with "playwright not installed" — long after a deploy that looked
  # clean, and only for users who export (the DOCX and HTML paths do not touch
  # playwright, so a smoke test that exports Word would pass and prove nothing).
  jc_run_with_heartbeat "uv sync (backend, export extra)" "$HEARTBEAT" \
    bash -c 'cd "$1" && UV_PROJECT_ENVIRONMENT="$2" uv sync --frozen --no-dev --extra export --no-editable' \
    _ "$SERVER_ROOT" "$VENV"

  # The PDF renderer launches Playwright's Chromium from the user's cache, which `uv sync` does
  # not install. Without it every PDF export fails at runtime with "Executable doesn't exist".
  # Idempotent (a no-op when present) and heartbeat-wrapped: it downloads ~150MB on a cold host.
  jc_run_with_heartbeat "playwright chromium (PDF export)" "$HEARTBEAT" \
    "${VENV}/bin/python" -m playwright install chromium

  # Downloading the browser is not enough: it also needs system libraries, which need an
  # administrator to install. Launch it once here, so a missing library fails the deploy with
  # the command to run, instead of the first PDF export failing for a user.
  log "checking that the PDF browser starts"
  CHECK_LOG="${JC_ROOT}/.data/run/playwright-check.log"
  mkdir -p "$(dirname "$CHECK_LOG")"
  if ! "${VENV}/bin/python" -c 'from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    p.chromium.launch().close()
' >"$CHECK_LOG" 2>&1; then
    tail -5 "$CHECK_LOG" >&2
    die "Chromium is downloaded but will not start - it is missing system libraries.
       An administrator runs once:
           sudo apt-get install -y libxkbcommon0 libgbm1
       then run this deploy again. PDF export does not work until it passes."
  fi
  rm -f "$CHECK_LOG"

  # The PDF's Chinese text comes from an installed font. A host with none falls back to a face
  # with no CJK glyphs, and the export then fails its text check. fc-list is absent on macOS,
  # where the template's own PingFang face is always present, so the check only runs where it exists.
  if command -v fc-list >/dev/null 2>&1 && [[ -z "$(fc-list ':lang=zh' family 2>/dev/null | head -1)" ]]; then
    die "no Chinese font is installed, so PDF export cannot place Chinese text.
       An administrator runs once:
           sudo apt-get install -y fonts-noto-cjk && sudo fc-cache -f
       then run this deploy again."
  fi

  log "verifying the three in-repo packages import"
  "${VENV}/bin/python" - <<'PY'
import importlib.metadata as m
for name in ("agentkit", "deerflow-harness", "deerflow-extension-api"):
    print(f"  {name:28} {m.version(name)}")
import agentkit, deerflow, deerflow_extension_api  # noqa: F401
print("  imports OK")
PY

  log "applying database migrations (alembic upgrade head)"
  # Heartbeat-wrapped, and alembic/env.py now sets the same connect_timeout as the
  # app engine (jc/db/session.py) — before this fix, an unreachable JC_DB_HOST hung
  # silently for however long the OS TCP connect takes (minutes on some cloud
  # firewalls that drop instead of reject), indistinguishable from a working deploy
  # that is just slow.
  jc_run_with_heartbeat "alembic upgrade head" "$HEARTBEAT" \
    env JC_PYTHON="${VENV}/bin/python" JC_SERVER_ROOT="$SERVER_ROOT" "${JC_ROOT}/scripts/db_upgrade.sh"
fi

if [[ "$DO_FRONTEND" == true ]]; then
  # The Next.js CLI prompts interactively the first time it runs on a machine
  # ("Would you like to send anonymous usage data to Vercel? (Y/n)") whenever
  # stdout is a TTY — true for `npm run build` run attached to a live SSH
  # session. The heartbeat wrapper keeps printing progress from its own timer
  # regardless, so the result looks identical to a slow build instead of what
  # it actually is: blocked forever on a keypress nobody is watching for.
  export NEXT_TELEMETRY_DISABLED=1

  log "installing web dependencies (npm ci)"
  cd "${WEB_ROOT}"
  if [[ "${JC_SKIP_NPM_CI:-}" == "1" ]]; then
    # Escape hatch for a host whose network to any npm registry (including a
    # mirror) is bad enough that `npm ci` cannot finish in a reasonable time.
    # The only correct substitute is a `node_modules` built elsewhere FROM THE
    # SAME package-lock.json — anything else silently drifts from what CI/dev
    # actually tested. `.package-lock.json` is the marker npm itself writes on
    # a completed install; its absence means "this is not an installed tree",
    # not "close enough".
    [[ -f "${WEB_ROOT}/node_modules/.package-lock.json" ]] || die \
      "JC_SKIP_NPM_CI=1 but ${WEB_ROOT}/node_modules has no .package-lock.json.
       Build node_modules elsewhere from this exact frontend/web/package-lock.json
       and extract it here first; this flag skips installing, not having installed."
    log "skipping npm ci (JC_SKIP_NPM_CI=1) — using existing node_modules"
  else
  # Every `resolved` URL in package-lock.json points at registry.npmjs.org — and
  # `npm ci` honours those literal URLs, so setting `registry=` alone changes
  # nothing. On a mainland cloud host those connections are throttled or left
  # half-open, and the download then hangs for tens of minutes with the process
  # alive and the heartbeat still ticking (observed: past 1500s, not the OOM kill
  # seen when the machine was merely short on memory). `replace-registry-host=always`
  # rewrites the host of each lockfile URL to whatever registry is configured, so
  # the mirror is actually used while the lockfile itself stays untouched and
  # `npm ci` keeps its exact-version guarantee.
  #
  # The timeouts are the other half: without them a stalled socket waits on npm's
  # (very long) defaults. With them the worst case is a fast, repeated failure that
  # says which package could not be fetched instead of an unbounded silence.
  #
  # If even the mirror cannot be reached in reasonable time, set JC_SKIP_NPM_CI=1
  # and ship a prebuilt node_modules instead (see the branch above).
  jc_run_with_heartbeat "npm ci" "$HEARTBEAT" \
    env NPM_CONFIG_LOGLEVEL="${NPM_CONFIG_LOGLEVEL:-info}" \
        NPM_CONFIG_REGISTRY="${JC_NPM_REGISTRY:-https://registry.npmmirror.com}" \
        NPM_CONFIG_REPLACE_REGISTRY_HOST="${JC_NPM_REPLACE_REGISTRY_HOST:-always}" \
        NPM_CONFIG_FETCH_TIMEOUT="${JC_NPM_FETCH_TIMEOUT:-60000}" \
        NPM_CONFIG_FETCH_RETRIES="${JC_NPM_FETCH_RETRIES:-3}" \
        NPM_CONFIG_FETCH_RETRY_MINTIMEOUT="${JC_NPM_FETCH_RETRY_MINTIMEOUT:-10000}" \
        NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT="${JC_NPM_FETCH_RETRY_MAXTIMEOUT:-60000}" \
    npm ci --no-audit --no-fund
  fi

  log "building web (npm run build)"
  jc_run_with_heartbeat "npm run build" "$HEARTBEAT" \
    env JC_API_PROXY_TARGET="http://127.0.0.1:${JC_API_PORT:-8000}" \
    npm run build
fi

log "done. Start/restart with: ./scripts/backend.sh restart && ./scripts/frontend.sh restart"
