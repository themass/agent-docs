#!/usr/bin/env bash
# One-shot deploy: install backend deps, migrate the database, build the frontend.
# Starts nothing — that is backend.sh / frontend.sh's job, run separately so you can
# inspect a build before flipping the running service onto it.
#
# Usage:
#   ./scripts/deploy.sh                  # everything
#   ./scripts/deploy.sh --skip-backend   # frontend build only
#   ./scripts/deploy.sh --skip-frontend  # backend install + migrate only
#   ./scripts/deploy.sh --python-default # also make CPython 3.12 this user's python3
#
# Python: needs 3.12.x. The system python3 is never modified; uv installs a private
# 3.12 on first deploy. --python-default additionally puts shims in ~/.local/bin so a
# new shell's `python3` is 3.12 too (existing shells need `source ~/.local/bin/env`).
#
# After this: ./scripts/backend.sh restart && ./scripts/frontend.sh restart
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
WEB_ROOT="${JC_ROOT}/frontend/web"

log() { printf '[deploy] %s\n' "$*"; }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

DO_BACKEND=true
DO_FRONTEND=true
PYTHON_DEFAULT=false
for arg in "$@"; do
  case "$arg" in
    --skip-backend) DO_BACKEND=false ;;
    --skip-frontend) DO_FRONTEND=false ;;
    --python-default) PYTHON_DEFAULT=true ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "unknown argument: $arg" ;;
  esac
done

command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"

if [[ "$DO_BACKEND" == true ]]; then
  VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"
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
  jc_ensure_python ${ensure_args[@]+"${ensure_args[@]}"} || die "no Python 3.12 and uv could not install one.
       Required by pyproject.toml (>=3.12,<3.13). The system python3 is deliberately
       left alone — apt/yum depend on it — and uv installs a private 3.12 instead.
       To also make it this user's default: ./scripts/deploy.sh --python-default"
  log "python: ${JC_PYTHON_BIN} ($("$JC_PYTHON_BIN" -V 2>&1))"

  if ! compgen -G "${SERVER_ROOT}/wheels/*.whl" >/dev/null; then
    die "no wheels in ${SERVER_ROOT}/wheels/.
       pyproject.toml sources agentkit/deerflow-harness/deerflow-extension-api from
       those files. Build them on a machine with the monorepo checkout:
         ./scripts/build-release.sh --update
       and commit backend/server/wheels/."
  fi
  [[ -f "${SERVER_ROOT}/.env" ]] || die "missing ${SERVER_ROOT}/.env (copy from .env.example)"

  log "installing Python dependencies into ${VENV}"
  # `--extra export` is not optional here: it is what installs playwright, which
  # `resume_render_engine.render_pdf` needs. Without it every PDF export dies at
  # runtime with "playwright not installed" — long after a deploy that looked
  # clean, and only for users who export (the DOCX and HTML paths do not touch
  # playwright, so a smoke test that exports Word would pass and prove nothing).
  ( cd "$SERVER_ROOT" && UV_PROJECT_ENVIRONMENT="${VENV}" uv sync --frozen --no-dev --extra export --no-editable )

  log "verifying the three in-repo packages import"
  "${VENV}/bin/python" - <<'PY'
import importlib.metadata as m
for name in ("agentkit", "deerflow-harness", "deerflow-extension-api"):
    print(f"  {name:28} {m.version(name)}")
import agentkit, deerflow, deerflow_extension_api  # noqa: F401
print("  imports OK")
PY

  log "applying database migrations (alembic upgrade head)"
  JC_PYTHON="${VENV}/bin/python" JC_SERVER_ROOT="$SERVER_ROOT" "${JC_ROOT}/scripts/db_upgrade.sh"
fi

if [[ "$DO_FRONTEND" == true ]]; then
  command -v npm >/dev/null 2>&1 || die "npm not found in PATH"

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

  log "installing web dependencies (npm ci)"
  cd "${WEB_ROOT}"
  # `npm ci` not `npm install`: it honours the lockfile exactly and wipes
  # node_modules first, so a deploy cannot inherit a half-upgraded tree.
  npm ci

  log "building web (npm run build)"
  # JC_API_PORT, not JC_API_PROXY_TARGET directly: next.config.ts reads this at
  # build time (rewrites() is frozen into .next/routes-manifest.json), and it must
  # agree with the port backend.sh actually binds. Nginx routes /api/v1 straight to
  # the API so this rewrite is normally unreachable — which is exactly why a wrong
  # port here stays invisible until the one request that does hit it 502s with
  # nothing pointing at a stale build as the cause.
  JC_API_PROXY_TARGET="http://127.0.0.1:${JC_API_PORT:-8000}" npm run build
fi

log "done. Start/restart with: ./scripts/backend.sh restart && ./scripts/frontend.sh restart"
