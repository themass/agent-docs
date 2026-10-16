#!/usr/bin/env bash
# Run one authenticated live-environment JC test. See scripts/README.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-smoke}"

case "$MODE" in
  smoke)
    exec "$ROOT/scripts/e2e_smoke.sh"
    ;;
  agent)
    exec "$ROOT/scripts/agent_e2e.sh"
    ;;
  regression)
    exec "$ROOT/scripts/regression_smoke.sh"
    ;;
  all)
    "$ROOT/scripts/e2e_smoke.sh"
    "$ROOT/scripts/agent_e2e.sh"
    "$ROOT/scripts/regression_smoke.sh"
    ;;
  help|-h|--help)
    cat <<'USAGE'
Usage: ./scripts/test-live.sh [smoke|agent|regression|all]

Required for authenticated modes:
  JC_E2E_EMAIL and JC_E2E_PASSWORD
Optional:
  JC_E2E_BASE=http://127.0.0.1:8000/api/v1

Modes:
  smoke       Core API flow plus DOCX and PDF export (default)
  agent       DeerFlow session, SSE, persistence, cancellation
  regression  Resume/JD fixture corpus smoke test
  all         Run the preceding three modes in sequence
USAGE
    ;;
  *)
    echo "Unknown live test mode: $MODE" >&2
    echo "Run ./scripts/test-live.sh --help" >&2
    exit 2
    ;;
esac
