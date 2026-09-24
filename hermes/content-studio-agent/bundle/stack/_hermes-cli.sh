#!/usr/bin/env bash
# Resolve and run hermes from hermes-dev/hermes-agent (never a broken PATH shim).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$ROOT_DIR/hermes-agent}"
# shellcheck source=/dev/null
source "$ROOT_DIR/../scripts/deepagents-python.env.sh"

# 1. Monorepo venv (canonical — hermes-agent editable install).
if [[ -x "$DEEPAGENTS_VENV/bin/hermes" ]]; then
  exec "$DEEPAGENTS_VENV/bin/hermes" "$@"
fi

# 2. Legacy hermes-agent local venv (fallback).
if [[ -x "$HERMES_AGENT_DIR/.venv/bin/hermes" ]]; then
  exec "$HERMES_AGENT_DIR/.venv/bin/hermes" "$@"
fi
if [[ -x "$HERMES_AGENT_DIR/venv/bin/hermes" ]]; then
  exec "$HERMES_AGENT_DIR/venv/bin/hermes" "$@"
fi

# 3. uv run from source tree.
if command -v uv >/dev/null 2>&1; then
  exec uv run --directory "$HERMES_AGENT_DIR" hermes "$@"
fi

# 4. Only trust PATH if it points into monorepo venv, hermes-agent, or ~/.hermes.
if command -v hermes >/dev/null 2>&1; then
  hermes_path="$(command -v hermes)"
  case "$hermes_path" in
    "$DEEPAGENTS_VENV"/* | "$HERMES_AGENT_DIR"/* | "$HOME/.hermes"/*)
      exec "$hermes_path" "$@"
      ;;
    *)
      echo "hermes-dev: ignoring hermes on PATH (${hermes_path}) — missing hermes_cli." >&2
      echo "  Fix: cd ${HERMES_AGENT_DIR} && uv pip install -e '.[all]'" >&2
      ;;
  esac
fi

echo "hermes-dev: hermes CLI not found under ${HERMES_AGENT_DIR}" >&2
echo "  Install: cd ${HERMES_AGENT_DIR} && uv pip install -e '.[all]'" >&2
exit 1
