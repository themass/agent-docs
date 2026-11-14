#!/usr/bin/env bash
# Shared filesystem discovery for JC scripts. Source this file; do not execute it.
#
# Two questions, answered separately on purpose:
#
#   * WHERE IS THE REPO?  A stable, committed marker (`libs/agentkit`). This is what
#     locates build inputs like the vendored DeerFlow submodule.
#   * WHICH INTERPRETER?  An environment concern. A virtualenv is never committed,
#     so it is discovered independently and may live somewhere the repo does not.
#
# They used to be one check ("directory owning both venv/ and libs/agentkit"),
# which broke the moment the venv and the source tree stopped being siblings —
# exactly what happened when the source moved into the repository at `docs/`.

# The repository root: the nearest ancestor that owns `libs/agentkit/src/agentkit`.
# The `src/agentkit` half matters: an empty leftover `libs/agentkit` directory must
# not be mistaken for the real thing.
jc_repo_root() {
  local probe="${1:-$PWD}"
  while [[ "$probe" != "/" ]]; do
    if [[ -f "$probe/libs/agentkit/pyproject.toml" && -d "$probe/libs/agentkit/src/agentkit" ]]; then
      printf '%s\n' "$probe"
      return 0
    fi
    probe="$(cd "$probe/.." && pwd)"
  done
  return 1
}

# Backwards-compatible name. Callers that only need "the tree that owns the build
# inputs" should use `jc_repo_root`; this alias remains because several scripts and
# docs already speak of a "monorepo root" and renaming them all buys nothing.
jc_monorepo_root() {
  jc_repo_root "${1:-$PWD}"
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
#   2. A `venv/` beside the repository root (the committed layout expects one here;
#      it is gitignored, so a fresh clone must run ./scripts/setup-venv.sh).
#   3. Any `venv/` further up, which is where a "monorepo sibling" checkout keeps it.
#   4. backend/server/.venv, the venv deploy.sh builds (a server, where job-come is
#      deployed alone and no repo-level venv exists).
# The repo-adjacent venvs come before the project venv on purpose: on a dev machine
# a leftover backend/server/.venv from trying out deploy.sh has no dev dependencies,
# and picking it would make the test tooling fail with missing-module errors.
jc_python() {
  local project_root="$1"
  local configured="${JC_PYTHON:-}"
  local repo_root probe server_python
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  if repo_root="$(jc_repo_root "$project_root")"; then
    if [[ -x "$repo_root/venv/bin/python" ]]; then
      printf '%s\n' "$repo_root/venv/bin/python"
      return 0
    fi
  fi
  probe="$project_root"
  while [[ "$probe" != "/" ]]; do
    if [[ -x "$probe/venv/bin/python" ]]; then
      printf '%s\n' "$probe/venv/bin/python"
      return 0
    fi
    probe="$(cd "$probe/.." && pwd)"
  done
  server_python="$(jc_server_root "$project_root")/.venv/bin/python"
  if [[ -x "$server_python" ]]; then
    printf '%s\n' "$server_python"
    return 0
  fi
  return 1
}

# The vendored DeerFlow checkout, resolved from the repo root rather than by counting
# `../`. One definition, so the build, the upstream sync and the docs cannot drift.
jc_vendor_deerflow() {
  local project_root="$1"
  local repo_root
  repo_root="$(jc_repo_root "$project_root")" || return 1
  printf '%s\n' "$repo_root/libs/agentkit/vendor/deer-flow"
}
