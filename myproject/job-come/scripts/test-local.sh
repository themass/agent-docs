#!/usr/bin/env bash
# Local release checks only. Does not seed, migrate or call live services.
# Credentialed integrations and browser checks are opt-in and never retried here.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "$ROOT/scripts/lib/project_paths.sh"
SERVER_ROOT="$(jc_server_root "$ROOT")"
WEB_ROOT="$(jc_web_root "$ROOT")"
cd "$SERVER_ROOT"
PYTHON="${JC_VERIFY_PYTHON:-$(jc_python "$ROOT")}"
if [[ ! -x "$PYTHON" ]]; then
  echo "FAIL: Python missing: $PYTHON" >&2
  exit 1
fi
"$PYTHON" -m compileall -q src tests "$ROOT/scripts"
"$PYTHON" -m pytest -q --tb=short
"$PYTHON" "$ROOT/scripts/evaluate_documents.py" --output "$ROOT/docs/evidence/document-evaluation.json"
bash -n "$ROOT/scripts/e2e_smoke.sh" "$ROOT/scripts/agent_e2e.sh"
(cd "$WEB_ROOT" && npm run build)

if [[ "${RUN_UI_ACCEPTANCE:-0}" == "1" ]]; then
  "$PYTHON" "$ROOT/scripts/verify_ui.py" --base "${UI_BASE_URL:-http://127.0.0.1:3107}"
else
  echo "SKIP: UI acceptance (set RUN_UI_ACCEPTANCE=1 with the fixture server running)"
fi

if [[ "${RUN_DOCLING_EVAL:-0}" == "1" ]]; then
  echo "INFO: Docling evaluation is an external isolated environment; invoke scripts/evaluate_docling.py explicitly."
else
  echo "SKIP: Docling/OCR evaluation (set RUN_DOCLING_EVAL=1 only to acknowledge the separate gate)"
fi

echo "PASS: local V1 checks"
echo "PENDING: credentialed API/Agent E2E, live services, deployment, and optional UI/Docling gates"
