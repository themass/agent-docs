#!/usr/bin/env bash
# Export smoke — requires live API + login + LLM (optional full path).
# Usage:
#   export JOB_COME_E2E_BASE=http://127.0.0.1:8000/api/v1
#   export JOB_COME_E2E_EMAIL=... JOB_COME_E2E_PASSWORD=...
#   ./scripts/export_smoke.sh
set -euo pipefail

BASE="${JOB_COME_E2E_BASE:-http://127.0.0.1:8000/api/v1}"
EMAIL="${JOB_COME_E2E_EMAIL:-}"
PASSWORD="${JOB_COME_E2E_PASSWORD:-}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Set JOB_COME_E2E_EMAIL and JOB_COME_E2E_PASSWORD"
  exit 1
fi

curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null

CTX=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE/auth/context")
PROFILE_ID=$(echo "$CTX" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('active_profile_id') or '')")
if [[ -z "$PROFILE_ID" ]]; then
  echo "No profile — upload resume first"
  exit 1
fi

echo "==> Elevate preview (export prerequisite)"
curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  "$BASE/resumes/profiles/${PROFILE_ID}/elevate" \
  -H 'Content-Type: application/json' \
  -d '{"elevation_level":"elevated"}' >/dev/null

echo "==> Export PDF"
EXPORT_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  "$BASE/resumes/profiles/${PROFILE_ID}/export" \
  -H 'Content-Type: application/json' \
  -d '{"format":"pdf","elevation_level":"elevated"}')
echo "$EXPORT_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print('status=', d.get('status'), 'id=', d.get('id'))"

echo "==> Export smoke done (Playwright visual test: optional dev dependency)"
