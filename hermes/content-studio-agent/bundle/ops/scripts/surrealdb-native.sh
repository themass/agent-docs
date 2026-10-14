#!/usr/bin/env bash
# Start/stop a local SurrealDB for Open Notebook.
# Data: $OPEN_NOTEBOOK_DIR/surreal_data/open_notebook.db
# The upstream open-notebook tree no longer ships this helper.
set -euo pipefail

ACTION="${1:-start}"
if [[ -z "${OPEN_NOTEBOOK_DIR:-}" || ! -d "$OPEN_NOTEBOOK_DIR" ]]; then
  echo "OPEN_NOTEBOOK_DIR is not set or missing" >&2
  exit 1
fi

DATA_DIR="${SURREAL_DATA_DIR:-$OPEN_NOTEBOOK_DIR/surreal_data}"
DB_PATH="${DATA_DIR}/open_notebook.db"
PORT="${SURREAL_PORT:-8000}"
SURREAL_USER="${SURREAL_USER:-root}"
SURREAL_PASSWORD="${SURREAL_PASSWORD:-root}"
PID_FILE="${DATA_DIR}/surreal.pid"
LOG_FILE="${DATA_DIR}/surreal.log"

mkdir -p "$DATA_DIR"

listening() {
  lsof -iTCP:"$PORT" -sTCP:LISTEN -Pn >/dev/null 2>&1
}

case "$ACTION" in
  start)
    if listening; then
      echo "SurrealDB already listening on :${PORT}"
      exit 0
    fi
    command -v surreal >/dev/null 2>&1 || { echo "surreal CLI not found" >&2; exit 1; }
    nohup surreal start --log info \
      --user "$SURREAL_USER" --pass "$SURREAL_PASSWORD" \
      --bind "127.0.0.1:${PORT}" \
      "rocksdb:${DB_PATH}" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    for _ in $(seq 1 30); do
      listening && exit 0
      sleep 1
    done
    echo "SurrealDB did not open :${PORT} (see ${LOG_FILE})" >&2
    exit 1
    ;;
  stop)
    if [[ -f "$PID_FILE" ]]; then
      kill "$(cat "$PID_FILE")" 2>/dev/null || true
      rm -f "$PID_FILE"
    fi
    ;;
  status)
    if listening; then echo "up :${PORT}"; else echo "down"; exit 1; fi
    ;;
  *)
    echo "usage: $0 {start|stop|status}" >&2
    exit 1
    ;;
esac
