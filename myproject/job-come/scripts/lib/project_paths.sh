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

jc_python() {
  local project_root="$1"
  local configured="${JC_PYTHON:-}"
  local monorepo_root
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  monorepo_root="$(jc_monorepo_root "$project_root")" || return 1
  printf '%s\n' "$monorepo_root/venv/bin/python"
}
