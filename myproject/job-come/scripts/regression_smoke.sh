#!/usr/bin/env bash
# Regression smoke: upload 3 resumes, parse 6 JDs, HTML elevate preview.
# Requires API + JOB_COME_E2E_EMAIL / JOB_COME_E2E_PASSWORD (or demo seed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${JOB_COME_E2E_BASE:-http://127.0.0.1:8000/api/v1}"
EMAIL="${JOB_COME_E2E_EMAIL:-demo@jobcome.local}"
PASSWORD="${JOB_COME_E2E_PASSWORD:-Demo1234!}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "[regression] API base: $BASE"

curl -sf "$BASE/../health/live" >/dev/null && echo "[regression] API health OK" || {
  echo "[regression] API not reachable — start with ./scripts/dev.sh"
  exit 1
}

RESUME_COUNT=$(find "$ROOT/fixtures/regression/resumes" -type f | wc -l | tr -d ' ')
JD_COUNT=$(find "$ROOT/fixtures/regression/jds" -type f | wc -l | tr -d ' ')
echo "[regression] fixtures: ${RESUME_COUNT} resumes, ${JD_COUNT} JDs"
if [[ "$RESUME_COUNT" -lt 3 || "$JD_COUNT" -lt 6 ]]; then
  echo "[regression] expected 3 resumes + 6 JDs"
  exit 1
fi

echo "[regression] login $EMAIL"
curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null

PROFILE_ID=""
for resume in "$ROOT/fixtures/regression/resumes"/*.txt; do
  name="$(basename "$resume")"
  echo "[regression] upload $name"
  PROFILE_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -F "file=@${resume};filename=${name};type=text/plain" \
    "$BASE/profiles/upload")
  PROFILE_ID=$(echo "$PROFILE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "    profile_id=$PROFILE_ID"
done

if [[ -z "$PROFILE_ID" ]]; then
  echo "[regression] no profile from upload"
  exit 1
fi

for jd in "$ROOT/fixtures/regression/jds"/*.txt; do
  name="$(basename "$jd")"
  echo "[regression] parse JD $name"
  BODY=$(python3 -c "import json,sys; print(json.dumps({'raw_text': open(sys.argv[1], encoding='utf-8').read(), 'save': True}))" "$jd")
  JD_JSON=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    "$BASE/jobs/profiles/${PROFILE_ID}/parse" \
    -H 'Content-Type: application/json' \
    -d "$BODY")
  echo "$JD_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"    job_id={d['id']} title={d.get('title')}\")"
done

echo "[regression] elevate HTML preview (zh-CN)"
PREVIEW=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  "$BASE/profiles/${PROFILE_ID}/elevate/preview?elevation_level=conservative&locale=zh-CN")
echo "$PREVIEW" | python3 -c "import sys,json; d=json.load(sys.stdin); html=d.get('html') or '';
assert '<html' in html.lower(), 'preview missing html'; print('    html_chars=', len(html))"

echo "[regression] elevate HTML preview (en-US)"
PREVIEW_EN=$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  "$BASE/profiles/${PROFILE_ID}/elevate/preview?elevation_level=conservative&locale=en-US")
echo "$PREVIEW_EN" | python3 -c "import sys,json; d=json.load(sys.stdin); html=d.get('html') or '';
assert 'Summary' in html or 'Experience' in html, 'en-US template headings missing'; print('    en html_chars=', len(html))"

echo "[regression] done"
