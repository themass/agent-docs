#!/usr/bin/env bash
# Shared start/stop/status for a PID-file-tracked background process.
# Source this file; do not execute it.
#
# Exists because backend.sh and frontend.sh need the same three operations and
# nothing else — no systemd, no root, just a PID file and a log file. That fits
# a host where the deploy user has no sudo (the actual case this was written
# for: a server where `sudo` reported "web is not in the sudoers file").

# Is the pid in $1's pidfile alive, and does it look like ours (not a PID reused
# by an unrelated process after a crash-without-cleanup)? `ps -o command=`
# comparison is deliberately loose (substring), since the command line commonly
# has the venv's absolute python path on one call and a bare module name later.
daemon_is_running() {
  local pidfile="$1" marker="$2"
  [[ -f "$pidfile" ]] || return 1
  local pid; pid="$(cat "$pidfile" 2>/dev/null)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null || return 1
  ps -o command= -p "$pid" 2>/dev/null | grep -qF "$marker"
}

# daemon_start <name> <pidfile> <logfile> <marker> <check_fn> <resolve_pid_fn|-> <command...>
#
# Starts `command...` detached (setsid, so it survives this script's own exit —
# the previous foreground-only script died with the SSH session that launched
# it), writes its PID to `pidfile`, then polls `check_fn` for up to 30s before
# declaring success. A process that *starts* but never becomes healthy is
# exactly the failure a bare `systemctl start` reports as a success, so the
# check is not optional here.
#
# `resolve_pid_fn` (pass `-` to skip) is the fix for a real failure mode found
# while testing this against `next start`: its CLI process forks the actual
# long-lived "next-server" and then EXITS once the handoff is done, so `$!`
# captures a PID that is correct for a few hundred ms and then simply stops
# existing — `kill -0` on it fails forever after, even though the real server
# is up and serving traffic under a different (reparented-to-init) PID.
# uvicorn's master process has no such handoff (it supervises workers for its
# whole life), so backend.sh passes `-` and trusts `$!` directly. When a
# resolver is given, the authoritative PID is whatever it returns once the
# health check first passes — not `$!` — and `$!`'s own liveness is not used
# to fail the loop early, since for a handoff-style process that PID dying is
# expected, not a crash.
daemon_start() {
  local name="$1" pidfile="$2" logfile="$3" marker="$4" check_fn="$5" resolve_fn="$6"
  shift 6

  if daemon_is_running "$pidfile" "$marker"; then
    printf '[%s] already running (pid %s)\n' "$name" "$(cat "$pidfile")"
    return 0
  fi
  rm -f "$pidfile"
  mkdir -p "$(dirname "$pidfile")" "$(dirname "$logfile")"

  printf '[%s] starting: %s\n' "$name" "$*"
  # `setsid` detaches into a new session so the process survives this shell (and
  # the SSH session that ran it) exiting — the thing the old foreground-only
  # script could not do. It is util-linux, Linux-only; macOS has no equivalent,
  # so a dev running this script locally falls back to `nohup` + `disown`, which
  # protects against SIGHUP but not a full session detach. The deploy target is
  # Linux, where `setsid` is present, so this only matters for local testing.
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >>"$logfile" 2>&1 < /dev/null &
  else
    nohup "$@" >>"$logfile" 2>&1 < /dev/null &
  fi
  local launcher_pid=$! pid=$!
  echo "$pid" > "$pidfile"
  disown "$pid" 2>/dev/null || true

  # How long to wait for the first healthy answer. A cold start of the API loads the whole
  # agent stack and takes well over 30s on a small machine, so the default is generous and
  # JC_START_TIMEOUT overrides it.
  local timeout_s="${JC_START_TIMEOUT:-90}" i max
  [[ "$timeout_s" =~ ^[0-9]+$ ]] && ((timeout_s > 0)) || timeout_s=90
  max=$((timeout_s * 2))
  for i in $(seq 1 "$max"); do
    if [[ "$resolve_fn" == "-" ]] && ! kill -0 "$launcher_pid" 2>/dev/null; then
      printf '[%s] ERROR: process exited before becoming healthy — see %s\n' "$name" "$logfile" >&2
      tail -20 "$logfile" >&2 2>/dev/null || true
      rm -f "$pidfile"
      return 1
    fi
    if "$check_fn"; then
      if [[ "$resolve_fn" != "-" ]]; then
        local resolved; resolved="$("$resolve_fn" 2>/dev/null || true)"
        if [[ -n "$resolved" ]]; then
          pid="$resolved"
          echo "$pid" > "$pidfile"
        fi
      fi
      printf '[%s] healthy (pid %s). Logs: %s\n' "$name" "$pid" "$logfile"
      return 0
    fi
    # One line every 10s, so a slow start reads as progress and not as a hang.
    if ((i % 20 == 0)); then
      printf '[%s] still starting... (%ss of %ss)\n' "$name" "$((i / 2))" "$timeout_s"
    fi
    sleep 0.5
  done
  printf '[%s] ERROR: not healthy after %ss — see %s\n' "$name" "$timeout_s" "$logfile" >&2
  tail -20 "$logfile" >&2 2>/dev/null || true
  # The process was not stopped, on purpose: a start that is only slow would otherwise be
  # killed just before it came up. Say so, because the error above reads as a failure.
  if daemon_is_running "$pidfile" "$marker"; then
    printf '[%s] The process is still running (pid %s) - it may only be slow to start.\n' "$name" "$(cat "$pidfile")" >&2
    printf '[%s] Check again with: ./scripts/%s.sh status   or wait longer: JC_START_TIMEOUT=300 ./scripts/%s.sh restart\n' "$name" "$name" "$name" >&2
  fi
  return 1
}

# daemon_stop <name> <pidfile>
#
# TERM, then a bounded wait, then KILL — never an unconditional kill -9, which
# would cut off an in-flight SSE preview stream or an export mid-write instead
# of letting the process close it out.
daemon_stop() {
  local name="$1" pidfile="$2"
  if [[ ! -f "$pidfile" ]]; then
    printf '[%s] not running (no pidfile)\n' "$name"
    return 0
  fi
  local pid; pid="$(cat "$pidfile" 2>/dev/null)"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    printf '[%s] not running (stale pidfile)\n' "$name"
    rm -f "$pidfile"
    return 0
  fi
  printf '[%s] stopping pid %s\n' "$name" "$pid"
  kill "$pid" 2>/dev/null || true
  local i
  for i in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || { rm -f "$pidfile"; printf '[%s] stopped\n' "$name"; return 0; }
    sleep 0.5
  done
  printf '[%s] still running after 10s, sending KILL\n' "$name" >&2
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pidfile"
}

daemon_status() {
  local name="$1" pidfile="$2" marker="$3"
  if daemon_is_running "$pidfile" "$marker"; then
    printf '[%s] running (pid %s)\n' "$name" "$(cat "$pidfile")"
    return 0
  fi
  printf '[%s] not running\n' "$name"
  return 1
}
