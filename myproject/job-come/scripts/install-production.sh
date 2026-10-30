#!/usr/bin/env bash
# Install the JC runtime into backend/server/.venv.
#
# Two modes, chosen automatically:
#
#   artifact   dist/ (or JC_RELEASE_DIR) contains wheels + requirements.txt built by
#              scripts/build-release.sh. Used when present. Needs NO monorepo source
#              tree — this is the normal deployment path.
#   source     Falls back to `uv sync --frozen --no-editable` against the in-repo
#              path dependencies. Only works with the whole monorepo present, i.e. on
#              a dev machine or a host that deliberately carries the source.
#
# Why the artifact exists: backend/server/pyproject.toml declares `agentkit`,
# `deerflow-harness` and `deerflow-extension-api` as `{ path = ..., editable = true }`.
# Those are build-time inputs, not runtime dependencies. Requiring a deployment host to
# carry 200MB of vendored DeerFlow source so that three packages can be compiled in
# place conflates the two; the wheels are the compiled result.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
VENDOR_ROOT="$(cd "${JC_ROOT}/../../../libs/agentkit" 2>/dev/null && pwd || true)"
VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"
RELEASE_DIR="${JC_RELEASE_DIR:-${JC_ROOT}/dist}"

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERROR: %s\n' "$*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"

if [[ -f "${RELEASE_DIR}/requirements.txt" ]]; then
  log "installing from release artifact: ${RELEASE_DIR}"
  [[ -f "${RELEASE_DIR}/RELEASE" ]] && sed 's/^/         /' "${RELEASE_DIR}/RELEASE"

  wheels=( "${RELEASE_DIR}"/*.whl )
  [[ -e "${wheels[0]}" ]] || die "no wheels in ${RELEASE_DIR} — rebuild with scripts/build-release.sh"

  # A fresh venv every time. `uv pip install` into an existing environment would leave
  # packages that were removed from requirements.txt, so the host slowly diverges from
  # the artifact it claims to be running.
  rm -rf "${VENV}"

  # `--python` lets uv create the venv with the right interpreter rather than whatever
  # `python3` happens to be; UV_PYTHON selects it.
  UV_PYTHON="${UV_PYTHON:-3.12}" uv venv --python "${UV_PYTHON:-3.12}" "${VENV}" >/dev/null
  UV_PYTHON="${UV_PYTHON:-3.12}" "${VENV}/bin/python" -V

  # `--find-links` rather than naming each wheel: it also resolves the interdependencies
  # between the three in-repo packages and catches a version skew (a wheel pinning
  # deerflow-extension-api==0.2.5 against a 0.2.9 wheel) as an install error instead of
  # a confusing ImportError at runtime.
  uv pip install --python "${VENV}/bin/python" \
    --find-links "${RELEASE_DIR}" \
    -r "${RELEASE_DIR}/requirements.txt"
  uv pip install --python "${VENV}/bin/python" \
    --find-links "${RELEASE_DIR}" \
    --no-deps --no-index \
    agentkit deerflow-harness deerflow-extension-api

  log "verifying"
  "${VENV}/bin/python" - <<'PY'
import importlib.metadata as m
for name in ("agentkit", "deerflow-harness", "deerflow-extension-api"):
    print(f"  {name:28} {m.version(name)}")
# Import, not just metadata: a wheel that installs but cannot import is exactly the
# failure a version table cannot show. Distribution names and import names differ
# here (`deerflow-harness` ships the `deerflow` package), so these are spelled out.
import agentkit  # noqa: F401
import deerflow  # noqa: F401
import deerflow_extension_api  # noqa: F401
print("  imports OK")
PY

  printf 'OK: JC runtime installed at %s\n' "${VENV}"
  exit 0
fi

log "no release artifact at ${RELEASE_DIR}; falling back to source install"
[[ -n "$VENDOR_ROOT" && -d "${VENDOR_ROOT}/vendor/deer-flow/backend/packages/harness" ]] || die \
  "Missing vendored DeerFlow source under ${JC_ROOT}/../../../libs/agentkit.
       This host has neither a release artifact nor the monorepo source.
       Build one on the dev machine with ./scripts/build-release.sh, copy dist/ here,
       then re-run this script (or set JC_RELEASE_DIR to where it landed)."

cd "${SERVER_ROOT}"
UV_PROJECT_ENVIRONMENT="${VENV}" uv sync --frozen --no-dev --no-editable
printf 'OK: JC production runtime installed at %s (from source)\n' "${VENV}"
