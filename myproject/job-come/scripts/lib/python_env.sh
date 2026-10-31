#!/usr/bin/env bash
# Resolve the Python interpreter the JC runtime must run on, installing it if needed.
# Source this file; do not execute it.
#
# The project requires >=3.12,<3.13 (pyproject.toml). A deploy host commonly ships
# something older as `python3` — Ubuntu 20.04 has 3.10, CentOS 8 has 3.6 — and
# upgrading the system interpreter is the wrong fix: apt/yum bind their own tooling
# to it, so replacing it breaks package management in ways that surface later and
# elsewhere.
#
# `uv` already needs to be installed for this project, and it can fetch a standalone
# 3.12 into the user's home directory without touching anything system-wide. So the
# answer is: make uv's 3.12 the interpreter this project uses, and optionally make it
# what `python3` resolves to for this user (`--default`, shims in ~/.local/bin). That
# is a per-user PATH change, reversible by deleting a directory, and harmless to the
# OS.
#
# Exports: JC_PYTHON_BIN (absolute path) and UV_PYTHON (version string for uv).
# shellcheck shell=bash

JC_REQUIRED_PY="3.12"

# Prints a usable interpreter path, or nothing. Prefers an already-installed uv
# 3.12; falls back to whatever `python3` is, but only if it is actually in range —
# handing 3.10 to `uv sync` produces "requires-python" resolution errors that read
# like a broken lockfile rather than a wrong interpreter.
jc_find_python() {
  local found
  if command -v uv >/dev/null 2>&1; then
    found="$(uv python find "${JC_REQUIRED_PY}" 2>/dev/null || true)"
    [[ -n "$found" && -x "$found" ]] && { printf '%s\n' "$found"; return 0; }
  fi
  for candidate in python3.12 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>/dev/null; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

# jc_ensure_python [--install-default]
#
# Returns nonzero when no 3.12 can be found and uv is not available to fetch one.
# `--install-default` additionally makes uv register 3.12 as this user's default
# (shims in ~/.local/bin, so `python3` in a new shell is 3.12). Off by default
# because it changes the user's PATH resolution, which is a thing to opt into once
# rather than surprise someone mid-deploy.
jc_ensure_python() {
  local make_default=false
  [[ "${1:-}" == "--install-default" ]] && make_default=true

  local found
  if found="$(jc_find_python)"; then
    JC_PYTHON_BIN="$found"
    UV_PYTHON="${JC_REQUIRED_PY}"
    export JC_PYTHON_BIN UV_PYTHON
    return 0
  fi

  command -v uv >/dev/null 2>&1 || return 1

  printf '[python] installing CPython %s via uv (no system change)\n' "$JC_REQUIRED_PY" >&2
  if [[ "$make_default" == true ]]; then
    # `--default` writes shims into ~/.local/bin, so plain `python3` resolves to
    # 3.12 for this user in a fresh shell. Existing shells keep their old PATH and
    # need `source ~/.local/bin/env` (or a re-login).
    uv python install "$JC_REQUIRED_PY" --default >&2 || return 1
  else
    uv python install "$JC_REQUIRED_PY" >&2 || return 1
  fi

  found="$(uv python find "${JC_REQUIRED_PY}" 2>/dev/null || true)"
  [[ -n "$found" && -x "$found" ]] || return 1
  JC_PYTHON_BIN="$found"
  UV_PYTHON="${JC_REQUIRED_PY}"
  export JC_PYTHON_BIN UV_PYTHON
}
