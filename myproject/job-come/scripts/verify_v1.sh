#!/usr/bin/env bash
# Local release checks only. Does not seed, migrate or call live services.
# Credentialed integrations and browser checks are opt-in and never retried here.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${JOB_COME_VERIFY_PYTHON:-$ROOT/../../../venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "FAIL: Python missing: $PYTHON" >&2
  exit 1
fi
"$PYTHON" -m compileall -q src tests scripts
"$PYTHON" -m pytest -q --tb=short
"$PYTHON" scripts/evaluate_documents.py --output docs/DOCUMENT_EVALUATION.json
bash -n scripts/e2e_smoke.sh scripts/agent_e2e.sh
(cd apps/web && npm run build)

if [[ "${RUN_UI_ACCEPTANCE:-0}" == "1" ]]; then
  "$PYTHON" scripts/verify_ui.py --base "${UI_BASE_URL:-http://127.0.0.1:3107}"
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
