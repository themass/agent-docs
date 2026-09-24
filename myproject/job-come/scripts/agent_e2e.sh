#!/usr/bin/env bash
# Agent harness E2E — session create, SSE stream, message persistence.
# Usage:
#   export JOB_COME_E2E_BASE=http://127.0.0.1:8000/api/v1
#   export JOB_COME_E2E_EMAIL=e2e@example.com
#   export JOB_COME_E2E_PASSWORD='your-password'
#   ./scripts/agent_e2e.sh
set -euo pipefail

BASE="${JOB_COME_E2E_BASE:-http://127.0.0.1:8000/api/v1}"
EMAIL="${JOB_COME_E2E_EMAIL:-}"
PASSWORD="${JOB_COME_E2E_PASSWORD:-}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Set JOB_COME_E2E_EMAIL and JOB_COME_E2E_PASSWORD for agent E2E."
  exit 1
fi

echo "==> Login"
curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null

CTX=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE/auth/context")
PROFILE_ID=$(echo "$CTX" | python3 -c "import sys,json; print(json.load(sys.stdin).get('active_profile_id') or '')")
if [[ -z "$PROFILE_ID" ]]; then
  RESUME_FILE="${JOB_COME_E2E_RESUME:-tests/regression_assets/resumes/sample_backend_zh.txt}"
  PROFILE_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -F "file=@${RESUME_FILE};filename=resume.txt;type=text/plain" \
    "$BASE/profiles/upload")
  PROFILE_ID=$(echo "$PROFILE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
fi
echo "    profile_id=$PROFILE_ID"

echo "==> Create agent session"
SESSION_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/agent/sessions" \
  -H 'Content-Type: application/json' \
  -d "{\"profile_id\":\"$PROFILE_ID\",\"skill_hint\":\"resume-coach\",\"kind\":\"resume\"}")
SESSION_ID=$(echo "$SESSION_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "    session_id=$SESSION_ID"

echo "==> Stream agent message (SSE) — round 1 greeting"
STREAM_FILE="$(mktemp)"
curl -sf -N -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  "$BASE/agent/sessions/${SESSION_ID}/messages" \
  -H 'Content-Type: application/json' \
  -d '{"content":"你好"}' >"$STREAM_FILE"

python3 - <<'PY' "$STREAM_FILE"
import json, sys
path = sys.argv[1]
events = []
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line.startswith("data:"):
        continue
    payload = line[5:].strip()
    if payload:
        events.append(json.loads(payload))
types = [e.get("type") for e in events]
print("    round1 event_types:", types)
if "done" not in types:
    raise SystemExit("round1: missing done event")
if "error" in types:
    err = next(e for e in events if e.get("type") == "error")
    raise SystemExit(f"round1 error: {err.get('message')}")
if "tool_start" in types and any(
    (e.get("name") or "").startswith("ask_clarification") for e in events if e.get("type") == "tool_start"
):
    raise SystemExit("round1: ask_clarification must not run in non-interactive mode")
PY
rm -f "$STREAM_FILE"

echo "==> Stream agent message (SSE) — round 2 resume help"
STREAM_FILE="$(mktemp)"
curl -sf -N -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  "$BASE/agent/sessions/${SESSION_ID}/messages" \
  -H 'Content-Type: application/json' \
  -d '{"content":"帮我看看工作经历怎么写，先给建议"}' >"$STREAM_FILE"

python3 - <<'PY' "$STREAM_FILE"
import json, sys
path = sys.argv[1]
events = []
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line.startswith("data:"):
        continue
    payload = line[5:].strip()
    if payload:
        events.append(json.loads(payload))
types = [e.get("type") for e in events]
print("    round2 event_types:", types)
if "done" not in types:
    raise SystemExit("round2: missing done event")
PY
rm -f "$STREAM_FILE"

echo "==> List persisted messages"
MSG_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  "$BASE/agent/sessions/${SESSION_ID}/messages")
python3 - <<'PY' "$MSG_JSON"
import json, sys
data = json.load(sys.stdin)
messages = data["messages"]
print(f"    message_count={len(messages)}")
user_msgs = [m for m in messages if m.get("role") == "user" and m.get("event_type") == "message"]
assistant_msgs = [m for m in messages if m.get("role") == "assistant" and m.get("event_type") == "message"]
print(f"    user_turns={len(user_msgs)} assistant_replies={len(assistant_msgs)}")
if len(user_msgs) < 2:
    raise SystemExit("expected 2 user turns")
if len(assistant_msgs) < 2:
    raise SystemExit("expected assistant reply for each turn (multi-turn broken)")
PY

echo "==> Steer cancel (no dangling tool_start)"
CANCEL_SESSION=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/agent/sessions" \
  -H 'Content-Type: application/json' \
  -d "{\"profile_id\":\"$PROFILE_ID\",\"skill_hint\":\"resume-coach\",\"kind\":\"resume\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
STREAM_FILE="$(mktemp)"
curl -sf -N -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  "$BASE/agent/sessions/${CANCEL_SESSION}/messages" \
  -H 'Content-Type: application/json' \
  -d '{"content":"请读取我的档案并逐条分析工作经历，尽量详细"}' >"$STREAM_FILE" &
STREAM_PID=$!
sleep 2
CANCEL_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  "$BASE/agent/sessions/${CANCEL_SESSION}/cancel")
echo "    cancel=$CANCEL_JSON"
wait "$STREAM_PID" || true
python3 - <<'PY' "$STREAM_FILE"
import json, sys
events = []
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if line.startswith("data:"):
        payload = line[5:].strip()
        if payload:
            events.append(json.loads(payload))
open_tools = []
for e in events:
    t = e.get("type")
    if t == "tool_start":
        open_tools.append(e.get("name") or "tool")
    elif t in {"tool_result", "tool"} and open_tools:
        open_tools.pop()
print("    dangling_tools=", open_tools)
if open_tools:
    raise SystemExit("cancel left dangling tool_start without tool_result")
types = [e.get("type") for e in events]
print("    cancel stream types:", types[-8:])
PY
rm -f "$STREAM_FILE"

echo "==> Agent E2E done"
