#!/usr/bin/env bash
# JC E2E smoke — run against a live API (staging/local).
# Usage:
#   export JC_E2E_BASE=http://127.0.0.1:8000/api/v1
#   export JC_E2E_EMAIL=e2e@example.com
#   export JC_E2E_PASSWORD='your-password'
#   ./scripts/e2e_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="$ROOT/backend/server"

BASE="${JC_E2E_BASE:-http://127.0.0.1:8000/api/v1}"
EMAIL="${JC_E2E_EMAIL:-}"
PASSWORD="${JC_E2E_PASSWORD:-}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "==> Health"
curl -sf "${BASE%/api/v1}/health" | grep -q ok

echo "==> Guest context"
curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE/auth/context" >/dev/null

echo "==> Upload resume fixture"
RESUME_FILE="${JC_E2E_RESUME:-${SERVER_ROOT}/tests/regression_assets/resumes/sample_backend_zh.txt}"
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

  JD_FILE="${JC_E2E_JD:-${SERVER_ROOT}/tests/regression_assets/jds/jd_backend_bytedance.txt}"
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

  echo "==> Apply pipeline (reviewer/export failure is a test failure)"
  PIPELINE_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/jobs/profiles/${PROFILE_ID}/apply-pipeline" \
    -H 'Content-Type: application/json' \
    -d "{\"job_id\":\"$JOB_ID\",\"export_format\":\"docx\"}")
  echo "$PIPELINE_JSON" | python3 -c 'import json,sys; data=json.load(sys.stdin); export=data.get("export") or {}; assert export.get("status") == "done" and not export.get("error"), data'

  echo "==> PDF export"
  curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/profiles/${PROFILE_ID}/elevate?elevation_level=elevated" >/dev/null
  PDF_EXPORT_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/profiles/${PROFILE_ID}/export" \
    -H 'Content-Type: application/json' \
    -d '{"format":"pdf","elevation_level":"elevated"}')
  echo "$PDF_EXPORT_JSON" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data.get("status") == "done" and data.get("id") and not data.get("error"), data; print("    export_id=", data["id"])'
else
  echo "==> Skip login flows (set JC_E2E_EMAIL/PASSWORD for full path)"
fi

echo "==> E2E smoke done"
