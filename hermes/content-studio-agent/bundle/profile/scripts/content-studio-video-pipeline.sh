#!/usr/bin/env bash
set -euo pipefail
export LC_ALL="en_US.UTF-8"
export LANG="en_US.UTF-8"
export CONTENT_STUDIO_CHAT_TIMEOUT="${CONTENT_STUDIO_CHAT_TIMEOUT:-600}"

PROFILE_DIR="${HERMES_HOME:-${CONTENT_STUDIO_PROFILE_DIR:-$HOME/.hermes/profiles/content-studio}}"
export HERMES_HOME="$PROFILE_DIR"
export CONTENT_STUDIO_PROFILE_DIR="$PROFILE_DIR"
if [ -d "$PROFILE_DIR/home" ]; then
  export HOME="$PROFILE_DIR/home"
fi

DATE="$(date +%Y-%m-%d)"
LOG_DIR="$PROFILE_DIR/logs/cron"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/content-studio-video-pipeline-$DATE.log"

if "$PROFILE_DIR/scripts/content-studio.sh" video-pipeline "$DATE" >"$LOG_FILE" 2>&1; then
  echo "OK video-pipeline date=$DATE log=$LOG_FILE"
else
  code=$?
  echo "ERROR video-pipeline date=$DATE exit=$code log=$LOG_FILE" >&2
  if [ -s "$LOG_FILE" ]; then
    echo "---- last 50 log lines ($LOG_FILE) ----" >&2
    tail -50 "$LOG_FILE" >&2
  fi
  exit "$code"
fi
