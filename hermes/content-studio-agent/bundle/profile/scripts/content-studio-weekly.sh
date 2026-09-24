#!/usr/bin/env bash
set -euo pipefail
export LC_ALL="en_US.UTF-8"
export LANG="en_US.UTF-8"

PROFILE_DIR="${HERMES_HOME:-${CONTENT_STUDIO_PROFILE_DIR:-$HOME/.hermes/profiles/content-studio}}"
export HERMES_HOME="$PROFILE_DIR"

DATE="$(date +%Y-%m-%d)"
LOG_DIR="$PROFILE_DIR/logs/cron"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/content-studio-weekly-$DATE.log"

if "$PROFILE_DIR/scripts/content-studio.sh" weekly "$DATE" >"$LOG_FILE" 2>&1; then
  echo "OK weekly-digest date=$DATE log=$LOG_FILE"
else
  code=$?
  echo "ERROR weekly-digest date=$DATE exit=$code log=$LOG_FILE"
  exit "$code"
fi
