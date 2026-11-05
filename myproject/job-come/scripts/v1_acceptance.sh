#!/usr/bin/env bash
# V1 live acceptance — the four real-dependency checks that cannot run in a sandbox.
#
# These need a real running API + a real served frontend build + real MySQL/Redis/TOS +
# a real LLM gateway. Nothing here is unattended-safe to run against production: it
# creates throwaway accounts, uploads a fixture resume, and (in --with-restart mode)
# asks you to restart the API mid-run. Point it at local or a disposable staging stack.
#
# Usage (zero setup — credentials are auto-generated per run, you do NOT need to
# export JC_E2E_EMAIL/JC_E2E_PASSWORD unless you want a stable account):
#   cd job-come
#   ./scripts/dev.sh                          # terminal 1: API on :8001, web on :3000
#   ./scripts/v1_acceptance.sh                # terminal 2 — just run it
#
# Flags:
#   --skip-browser        Skip the Playwright-driven UI checks (1)
#   --skip-export          Skip the export format x locale regression (3)
#   --skip-concurrency      Skip concurrent-users / cancel / restart checks (4)
#   --with-restart         Include the manual restart-recovery step (asks you to
#                          restart the API mid-run); omitted by default so the rest
#                          can run unattended
#   --users N              Concurrent users for the isolation check (default 5)
#   --email / --password  Use a specific account instead of an auto-generated one
#                          (also honors JC_E2E_EMAIL / JC_E2E_PASSWORD env vars)
#
# Each check writes its evidence JSON to docs/evidence/. This script's own exit code
# is non-zero if any check fails; read the per-check output above the summary to see
# which one and why.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "$ROOT/scripts/lib/project_paths.sh"
PYTHON="${JC_VERIFY_PYTHON:-$(jc_python "$ROOT")}"

API_BASE="${JC_E2E_BASE:-http://127.0.0.1:${JC_API_PORT:-8001}/api/v1}"
WEB_BASE="${UI_BASE_URL:-http://127.0.0.1:${JC_WEB_PORT:-3000}}"

SKIP_BROWSER=0
SKIP_EXPORT=0
SKIP_CONCURRENCY=0
WITH_RESTART=0
USERS=5
E2E_EMAIL="${JC_E2E_EMAIL:-}"
E2E_PASSWORD="${JC_E2E_PASSWORD:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-browser) SKIP_BROWSER=1; shift ;;
    --skip-export) SKIP_EXPORT=1; shift ;;
    --skip-concurrency) SKIP_CONCURRENCY=1; shift ;;
    --with-restart) WITH_RESTART=1; shift ;;
    --users) USERS="$2"; shift 2 ;;
    --email) E2E_EMAIL="$2"; shift 2 ;;
    --password) E2E_PASSWORD="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,28p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      exit 2
      ;;
  esac
done

# No pre-existing account needed: verify_export_regression.py self-registers
# (falls back to login on 409 if the account already exists). Auto-generate a
# throwaway account per run unless the caller passed/exported one explicitly.
if [[ -z "$E2E_EMAIL" ]]; then
  E2E_EMAIL="jc-v1-accept-$(date +%s)-$$@example.com"
fi
if [[ -z "$E2E_PASSWORD" ]]; then
  E2E_PASSWORD="V1Accept-$(date +%s)-$$"
fi

echo "==> API health ($API_BASE)"
if ! curl -sf "${API_BASE%/api/v1}/health" >/dev/null; then
  echo "FAIL: API not reachable at $API_BASE -- start it with ./scripts/dev.sh" >&2
  echo "      (default API port is 8001; override with JC_E2E_BASE if yours differs)" >&2
  exit 1
fi

FAILURES=()

run_check() {
  local name="$1"; shift
  echo ""
  echo "########################################"
  echo "# $name"
  echo "########################################"
  if "$@"; then
    echo "-- $name: PASS"
  else
    echo "-- $name: FAIL"
    FAILURES+=("$name")
  fi
}

# 1. Dynamic browser acceptance -- UI, streaming reply, failure/retry states.
if [[ "$SKIP_BROWSER" == "0" ]]; then
  if ! curl -sf "$WEB_BASE" >/dev/null; then
    echo "SKIP: browser checks -- web not reachable at $WEB_BASE." >&2
    echo "      Serve a production build first: (cd frontend/web && npm run build && npm start)" >&2
    FAILURES+=("browser (web not running)")
  else
    run_check "1a. UI fixture/browser acceptance" \
      "$PYTHON" "$ROOT/scripts/verify_ui.py" --base "$WEB_BASE"
    run_check "1b. Visual audit (contrast, overflow, type scale)" \
      "$PYTHON" "$ROOT/scripts/audit_visual.py" --base "$WEB_BASE"
    run_check "1c. Resume step 1/3/4 layout gates" \
      "$PYTHON" "$ROOT/scripts/verify_resume_steps.py" --base "$WEB_BASE"
    run_check "1d. Agent rail collapse/expand (run survives collapse)" \
      "$PYTHON" "$ROOT/scripts/verify_agent_rail.py" --base "$WEB_BASE"
    run_check "1e. Export gate never blocks download" \
      "$PYTHON" "$ROOT/scripts/verify_export_gate.py" --base "$WEB_BASE"
    run_check "1f. Auth error copy renders (login/forgot-password)" \
      "$PYTHON" "$ROOT/scripts/verify_auth_errors.py" --base "$WEB_BASE"
  fi
else
  echo "SKIP: browser checks (--skip-browser)"
fi

# 2. Document parsing evaluation -- real sample files, not synthetic fixtures.
echo ""
echo "########################################"
echo "# 2. Document parsing (real files) -- CANNOT be automated here"
echo "########################################"
echo "This is the one gate that genuinely needs files from you: a text-layer PDF, a"
echo "scanned/image-only PDF, a table-heavy DOCX, and at least one deliberately bad"
echo "file (corrupted, empty, wrong extension). Run each through:"
echo "  $PYTHON $ROOT/scripts/evaluate_writing.py <path> --job-title \"...\" --verbose"
echo "Confirm: the three good files produce a real structured profile (not"
echo "mock_fallback), and the bad file fails loudly instead of crashing or silently"
echo "degrading. The synthetic-sample baseline already runs unattended in"
echo "test-local.sh: docs/evidence/document-evaluation.json"

# 3. Export regression -- every format x locale combo, real download, real inspection.
if [[ "$SKIP_EXPORT" == "0" ]]; then
  run_check "3. Export regression (format x locale, fonts, links, download)" \
    "$PYTHON" "$ROOT/scripts/verify_export_regression.py" --base "$API_BASE" \
      --email "$E2E_EMAIL" --password "$E2E_PASSWORD"
else
  echo "SKIP: export regression (--skip-export)"
fi

# 4. Concurrency isolation, mid-stream cancel, restart recovery.
if [[ "$SKIP_CONCURRENCY" == "0" ]]; then
  RESTART_FLAG=()
  [[ "$WITH_RESTART" == "0" ]] && RESTART_FLAG=(--skip-restart)
  run_check "4. Concurrency isolation / cancel / restart recovery" \
    "$PYTHON" "$ROOT/scripts/verify_concurrency_resilience.py" --base "$API_BASE" \
      --users "$USERS" "${RESTART_FLAG[@]}"
else
  echo "SKIP: concurrency/cancel/restart checks (--skip-concurrency)"
fi

echo ""
echo "========================================"
if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo "FAIL: ${#FAILURES[@]} check(s) failed:"
  for f in "${FAILURES[@]}"; do echo "  - $f"; done
  echo "Evidence written to docs/evidence/ -- check each JSON for detail."
  exit 1
fi
echo "PASS: all automated V1 acceptance checks passed."
echo "Document parsing (item 2) needs a manual pass with real files -- see the printed command above."
