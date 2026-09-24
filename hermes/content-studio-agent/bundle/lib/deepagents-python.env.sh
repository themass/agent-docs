#!/usr/bin/env bash
# Canonical monorepo Python for all deepagents subprojects.
# Usage: source "$(dirname "$0")/../scripts/deepagents-python.env.sh"
#    or: source /Users/gqli/work/deepagents/scripts/deepagents-python.env.sh

if [[ -n "${DEEPAGENTS_PYTHON_ENV_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
DEEPAGENTS_PYTHON_ENV_LOADED=1

_DEEPAGENTS_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DEEPAGENTS_REPO_ROOT="${DEEPAGENTS_REPO_ROOT:-$(cd "$_DEEPAGENTS_ENV_DIR/.." && pwd)}"
DEEPAGENTS_VENV="${DEEPAGENTS_VENV:-$DEEPAGENTS_REPO_ROOT/venv}"
DEEPAGENTS_PYTHON="${DEEPAGENTS_PYTHON:-$DEEPAGENTS_VENV/bin/python3}"

export DEEPAGENTS_REPO_ROOT DEEPAGENTS_VENV DEEPAGENTS_PYTHON
export UV_PYTHON="$DEEPAGENTS_PYTHON"

if [[ -d "$DEEPAGENTS_VENV/bin" ]]; then
  export PATH="$DEEPAGENTS_VENV/bin:$PATH"
fi

# Aliases used by Content Studio / GitHub Analyst orchestrators
export CONTENT_STUDIO_PYTHON="${CONTENT_STUDIO_PYTHON:-$DEEPAGENTS_PYTHON}"
export GITHUB_ANALYST_PYTHON="${GITHUB_ANALYST_PYTHON:-$DEEPAGENTS_PYTHON}"

# Hermes CLI — editable install lives in monorepo venv
export HERMES_BIN="${HERMES_BIN:-$DEEPAGENTS_VENV/bin/hermes}"

unset _DEEPAGENTS_ENV_DIR
