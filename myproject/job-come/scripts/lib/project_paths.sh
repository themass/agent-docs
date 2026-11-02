#!/usr/bin/env bash
# Shared filesystem discovery for JC scripts. Source this file; do not execute it.

jc_monorepo_root() {
  local probe="$1"
  while [[ "$probe" != "/" ]]; do
    if [[ -x "$probe/venv/bin/python" && -d "$probe/libs/agentkit" ]]; then
      printf '%s\n' "$probe"
      return 0
    fi
    probe="$(cd "$probe/.." && pwd)"
  done
  return 1
}

jc_server_root() {
  local project_root="$1"
  printf '%s\n' "$project_root/backend/server"
}

jc_web_root() {
  local project_root="$1"
  printf '%s\n' "$project_root/frontend/web"
}

# Which interpreter the backend tooling runs on. In order:
#   1. $JC_PYTHON, when set.
#   2. The monorepo venv, when this checkout sits inside the monorepo (development).
#   3. backend/server/.venv, the project's own venv that deploy.sh builds (a server, where
#      job-come is deployed alone and no monorepo exists above it).
# The monorepo comes before the project venv on purpose: on a dev machine a leftover
# backend/server/.venv from trying out deploy.sh has no dev dependencies, and picking it
# would make the test tooling fail with missing-module errors.
jc_python() {
  local project_root="$1"
  local configured="${JC_PYTHON:-}"
  local monorepo_root server_python
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  if monorepo_root="$(jc_monorepo_root "$project_root")"; then
    printf '%s\n' "$monorepo_root/venv/bin/python"
    return 0
  fi
  server_python="$(jc_server_root "$project_root")/.venv/bin/python"
  if [[ -x "$server_python" ]]; then
    printf '%s\n' "$server_python"
    return 0
  fi
  return 1
}
