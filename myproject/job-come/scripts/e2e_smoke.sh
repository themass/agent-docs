#!/usr/bin/env bash
# JobCome E2E smoke — run against a live API (staging/local).
# Usage:
#   export JOB_COME_E2E_BASE=http://127.0.0.1:8000/api/v1
#   export JOB_COME_E2E_EMAIL=e2e@example.com
#   export JOB_COME_E2E_PASSWORD='your-password'
#   ./scripts/e2e_smoke.sh
set -euo pipefail

BASE="${JOB_COME_E2E_BASE:-http://127.0.0.1:8000/api/v1}"
EMAIL="${JOB_COME_E2E_EMAIL:-}"
PASSWORD="${JOB_COME_E2E_PASSWORD:-}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "==> Health"
curl -sf "${BASE%/api/v1}/health" | grep -q ok

echo "==> Guest context"
curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE/auth/context" >/dev/null

echo "==> Upload resume fixture"
RESUME_FILE="${JOB_COME_E2E_RESUME:-tests/regression_assets/resumes/sample_backend_zh.txt}"
PROFILE_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -F "file=@${RESUME_FILE};filename=resume.txt;type=text/plain" \
  "$BASE/profiles/upload")
PROFILE_ID=$(echo "$PROFILE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "    profile_id=$PROFILE_ID"

if [[ -n "$EMAIL" && -n "$PASSWORD" ]]; then
  echo "==> Register or login"
  curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null 2>&1 || \
  curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null

  JD_FILE="${JOB_COME_E2E_JD:-tests/regression_assets/jds/jd_backend_bytedance.txt}"
  JD_TEXT=$(python3 -c "import json,pathlib; print(json.dumps(pathlib.Path('$JD_FILE').read_text()))")

  echo "==> Parse JD"
  JOB_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/jobs/profiles/${PROFILE_ID}/parse" \
    -H 'Content-Type: application/json' \
    -d "{\"raw_text\": $JD_TEXT, \"save\": true}")
  JOB_ID=$(echo "$JOB_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
  echo "    job_id=$JOB_ID"

  echo "==> Fit score"
  curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/jobs/profiles/${PROFILE_ID}/fit" \
    -H 'Content-Type: application/json' \
    -d "{\"job_id\":\"$JOB_ID\"}" >/dev/null

  echo "==> Campaign stats"
  curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    "$BASE/campaign/profiles/${PROFILE_ID}" >/dev/null

  echo "==> Apply pipeline (may fail reviewer if LLM strict — check response)"
  curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/jobs/profiles/${PROFILE_ID}/apply-pipeline" \
    -H 'Content-Type: application/json' \
    -d "{\"job_id\":\"$JOB_ID\",\"export_format\":\"docx\"}" || true
else
  echo "==> Skip login flows (set JOB_COME_E2E_EMAIL/PASSWORD for full path)"
fi

echo "==> E2E smoke done"
