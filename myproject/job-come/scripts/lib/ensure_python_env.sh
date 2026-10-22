#!/usr/bin/env bash
# Source from launch scripts — do not execute directly.
# Ensures backend/server deps are synced into the monorepo venv (alembic CLI, uvicorn, …).

jc_alembic_bin() {
  local python="$1"
  printf '%s\n' "$(cd "$(dirname "$python")" && pwd)/alembic"
}

# Fast proxy for "uv sync has been run for JC server".
jc_python_env_ready() {
  local python="$1"
  local alembic_bin
  [[ -x "$python" ]] || return 1
  alembic_bin="$(jc_alembic_bin "$python")"
  [[ -x "$alembic_bin" ]] || return 1
  "$python" -c 'import uvicorn' >/dev/null 2>&1 || return 1
  return 0
}

# Run setup-venv.sh when deps are missing. Honors JC_SKIP_VENV_SYNC=1|true.
jc_ensure_python_env() {
  local jc_root="$1"
  local python="$2"
  local skip="${JC_SKIP_VENV_SYNC:-}"

  if jc_python_env_ready "$python"; then
    return 0
  fi
  if [[ "$skip" == "1" || "$skip" == "true" ]]; then
    printf '[ensure-python] ERROR: JC Python env is incomplete (%s).\n' "$python" >&2
    printf '[ensure-python] Install deps: %s/scripts/setup-venv.sh\n' "$jc_root" >&2
    printf '[ensure-python] Or unset JC_SKIP_VENV_SYNC to allow auto sync on start.\n' >&2
    return 1
  fi
  if ! command -v uv >/dev/null 2>&1; then
    printf '[ensure-python] ERROR: missing `uv` and Alembic/uvicorn are not in the venv.\n' >&2
    printf '[ensure-python] Install uv (https://docs.astral.sh/uv/) then run: %s/scripts/setup-venv.sh\n' "$jc_root" >&2
    return 1
  fi
  printf '[ensure-python] Syncing JC backend deps into monorepo venv (first run or after lock change)…\n'
  JC_PYTHON="$python" "${jc_root}/scripts/setup-venv.sh"
  if ! jc_python_env_ready "$python"; then
    printf '[ensure-python] ERROR: setup finished but env still incomplete.\n' >&2
    return 1
  fi
  printf '[ensure-python] OK\n'
}
