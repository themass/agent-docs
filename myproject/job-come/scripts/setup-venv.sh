#!/usr/bin/env bash
# Install job-come deps into monorepo venv (deepagents/venv).
# Job-come is designed as a standalone project; while inside deepagents monorepo
# we only borrow the parent Python venv — do not use job-come/.venv here.
set -euo pipefail

JOB_COME_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MONO_ROOT="$(cd "${JOB_COME_ROOT}/../../.." && pwd)"
if [[ ! -x "${MONO_ROOT}/venv/bin/python" ]]; then
  # walk up until monorepo venv is found
  probe="${JOB_COME_ROOT}"
  MONO_ROOT=""
  while [[ "${probe}" != "/" ]]; do
    if [[ -x "${probe}/venv/bin/python" && -d "${probe}/libs/agentkit" ]]; then
      MONO_ROOT="${probe}"
      break
    fi
    probe="$(cd "${probe}/.." && pwd)"
  done
fi
if [[ -z "${MONO_ROOT}" ]]; then
  echo "Cannot find monorepo root (venv + libs/agentkit) above ${JOB_COME_ROOT}"
  exit 1
fi
VENV="${MONO_ROOT}/venv"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Missing ${VENV}/bin/python — create monorepo venv first (Python 3.12)."
  echo "  cd ${MONO_ROOT} && python3.12 -m venv venv"
  exit 1
fi

export UV_PROJECT_ENVIRONMENT="${VENV}"
cd "${JOB_COME_ROOT}"
uv sync --extra dev --python "${VENV}/bin/python"
echo "OK: job-come → ${VENV} ($( "${VENV}/bin/python" -c 'import sys; print(sys.version.split()[0])' ))"
