#!/usr/bin/env bash
# Install the JC runtime into backend/server/.venv.
#
# Plain `uv sync` against the lockfile. The three in-repo packages (`agentkit`,
# `deerflow-harness`, `deerflow-extension-api`) are sourced from the prebuilt wheels
# checked in under `backend/server/wheels/`, per `[tool.uv.sources]` in pyproject.toml,
# so this needs no monorepo checkout, no `libs/agentkit`, and no particular directory
# depth — the project installs the same way on a laptop and on a fresh server.
#
# Refresh those wheels with `./scripts/build-release.sh --update` whenever the
# vendored DeerFlow or agentkit source changes.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERROR: %s\n' "$*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"

if ! compgen -G "${SERVER_ROOT}/wheels/*.whl" >/dev/null; then
  die "no wheels in ${SERVER_ROOT}/wheels/.
       pyproject.toml sources three packages from those files, so the install cannot
       resolve without them. Build them on a machine with the monorepo checkout:
         ./scripts/build-release.sh --update
       and commit backend/server/wheels/."
fi

cd "${SERVER_ROOT}"
log "syncing into ${VENV}"
UV_PROJECT_ENVIRONMENT="${VENV}" uv sync --frozen --no-dev --no-editable

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
