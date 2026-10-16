#!/usr/bin/env bash
# Install the locked JC runtime as non-editable packages for production.
# The deployment checkout must retain the vendored AgentKit + DeerFlow source tree.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
VENDOR_ROOT="$(cd "${JC_ROOT}/../../../libs/agentkit" && pwd)"
VENV="${JC_VENV:-${SERVER_ROOT}/.venv}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to install the JC production runtime" >&2
  exit 1
fi

if [[ ! -d "${VENDOR_ROOT}/vendor/deer-flow/backend/packages/harness" ]]; then
  echo "Missing vendored DeerFlow source under ${VENDOR_ROOT}/vendor/deer-flow" >&2
  exit 1
fi

cd "${SERVER_ROOT}"
UV_PROJECT_ENVIRONMENT="${VENV}" uv sync --frozen --no-dev --no-editable
printf 'OK: JC production runtime installed at %s\n' "${VENV}"
