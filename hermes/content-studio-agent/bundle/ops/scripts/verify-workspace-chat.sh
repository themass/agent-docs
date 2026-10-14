#!/usr/bin/env bash
# Quick check: Workspace send-stream → Gateway → LLM (Content Studio).
set -euo pipefail

WORKSPACE_URL="${WORKSPACE_URL:-http://127.0.0.1:3000}"
TIMEOUT_SEC="${VERIFY_WORKSPACE_CHAT_TIMEOUT_SEC:-120}"
SESSION_KEY="${VERIFY_WORKSPACE_CHAT_SESSION:-content-studio-verify}"

log() { printf '[verify-workspace-chat] %s\n' "$*"; }

if ! curl -fsS -m 5 "${WORKSPACE_URL}/api/connection-status" >/dev/null 2>&1; then
  log "Workspace not reachable at ${WORKSPACE_URL}"
  exit 1
fi

log "POST ${WORKSPACE_URL}/api/send-stream (timeout ${TIMEOUT_SEC}s)..."
out="$(mktemp)"
trap 'rm -f "$out"' EXIT

if ! curl -sS -m "$TIMEOUT_SEC" -N -X POST "${WORKSPACE_URL}/api/send-stream" \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"reply with exactly: WORKSPACE_OK\",\"sessionKey\":\"${SESSION_KEY}\",\"model\":\"gpt-5-6-luna\"}" \
  >"$out"; then
  log "curl failed or timed out after ${TIMEOUT_SEC}s"
  tail -20 "$out" || true
  exit 1
fi

if grep -q 'WORKSPACE_OK' "$out" && grep -q 'event: done' "$out"; then
  log "OK — workspace chat completed"
  exit 0
fi

log "FAILED — no done/WORKSPACE_OK in stream"
tail -30 "$out" || true
exit 1
