#!/usr/bin/env bash
# Install JC development dependencies into the monorepo venv (deepagents/venv).
# Job-come is designed as a standalone project; while inside deepagents monorepo
# we only borrow the parent Python venv — do not use job-come/.venv here.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
VENV_PYTHON="$(jc_python "$JC_ROOT" 2>/dev/null || true)"
[[ -n "$VENV_PYTHON" ]] || {
  echo "No interpreter found. Create one first:" >&2
  echo "  python3.12 -m venv ${JC_ROOT}/../../venv" >&2
  exit 1
}
VENV="$(cd "$(dirname "$VENV_PYTHON")/.." && pwd)"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Missing ${VENV}/bin/python — create monorepo venv first (Python 3.12)."
  echo "  cd ${MONO_ROOT} && python3.12 -m venv venv"
  exit 1
fi

export UV_PROJECT_ENVIRONMENT="${VENV}"
SERVER_ROOT="$(jc_server_root "$JC_ROOT")"
cd "$SERVER_ROOT"
uv sync --extra dev --python "${VENV}/bin/python"
echo "OK: JC development environment → ${VENV} ($( "${VENV}/bin/python" -c 'import sys; print(sys.version.split()[0])' ))"
