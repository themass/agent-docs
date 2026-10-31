#!/usr/bin/env bash
# Run a long command while printing periodic heartbeats (keeps SSH sessions alive).
# Source this file; do not execute directly.
#
#   jc_run_with_heartbeat "label" interval_seconds command [args...]
#
# Interval defaults from JC_DEPLOY_HEARTBEAT_SEC (30). Heartbeats go to stdout with
# prefix [deploy] when jc_heartbeat_log is unset; deploy.sh sets jc_heartbeat_log=log.

jc_run_with_heartbeat() {
  local label="$1"
  local interval="${2:-${JC_DEPLOY_HEARTBEAT_SEC:-30}}"
  shift 2

  local heartbeat_log="${jc_heartbeat_log:-jc_heartbeat_log_default}"
  jc_heartbeat_log_default() {
    printf '[deploy] %s\n' "$*"
  }

  local started elapsed n=0 rc=0 hb_pid=""
  started="$(date '+%Y-%m-%d %H:%M:%S %z')"
  "$heartbeat_log" "begin: ${label} (heartbeat every ${interval}s, started ${started})"

  (
    while true; do
      sleep "$interval"
      n=$((n + 1))
      elapsed=$((n * interval))
      "$heartbeat_log" "… ${label} still running (${elapsed}s elapsed, heartbeat #${n})"
    done
  ) &
  hb_pid=$!

  set +e
  "$@"
  rc=$?
  set -e

  kill "$hb_pid" 2>/dev/null || true
  wait "$hb_pid" 2>/dev/null || true

  if [[ "$rc" -ne 0 ]]; then
    printf '[deploy] failed: %s (exit %s)\n' "$label" "$rc" >&2
    return "$rc"
  fi
  "$heartbeat_log" "finished: ${label}"
  return 0
}
