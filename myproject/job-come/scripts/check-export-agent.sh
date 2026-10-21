#!/usr/bin/env bash
# Deterministic export + confirmation/trace regression. No live model or user DB.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "$ROOT/scripts/lib/project_paths.sh"
PYTHON="${JC_VERIFY_PYTHON:-$(jc_python "$ROOT")}"
cd "$(jc_server_root "$ROOT")"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
export OTEL_SDK_DISABLED=true
"$PYTHON" -m pytest -q --tb=short \
  tests/test_export_lifecycle.py tests/test_export_pdf.py tests/test_export_quality.py \
  tests/test_profile_confirmations.py tests/test_profile_patch_paths.py \
  tests/test_agent_trace_stream_wiring.py tests/test_agent_trace_store.py \
  tests/test_v1_mcp_contracts.py
printf '\nPASS: isolated export + Agent regression; no live model/DB calls.\n'
printf 'Not covered: real model quality, shared MySQL multi-worker behavior, deployment.\n'
