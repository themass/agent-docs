#!/usr/bin/env bash
# Open the GitHub analyst report library in the default browser.
set -euo pipefail
SCRIPT="${HOME}/.hermes/profiles/github/scripts/github-analyst.sh"
if [[ ! -x "$SCRIPT" ]]; then
  echo "Missing: $SCRIPT" >&2
  exit 1
fi
export HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes/profiles/github}"
exec "$SCRIPT" browse
