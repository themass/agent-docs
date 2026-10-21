#!/usr/bin/env bash
# Cron entry point for the LLM audit log retention policy.
#
# Exists because `JC_LLM_LOG_PAYLOAD=true` in production is only defensible if
# something actually enforces the window. The decision there was "keep the原文 so a
# complaint about one phrasing can be answered, but not forever" — and without this
# running on a schedule, the second half of that sentence is not true.
#
# Two windows, on purpose:
#   --forget-payload-after  prompt/response/reasoning text (resume personal data)
#   --days                  the whole row, metrics included
#
# crontab:
#   17 4 * * *  cd /srv/jc && ./scripts/prune_llm_log.sh >> /var/log/jc/prune.log 2>&1
#
# Defaults to --apply: a cron job that reports what it would do and changes nothing is
# the failure mode this script exists to prevent. Pass JC_PRUNE_DRY_RUN=1 to inspect.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
PYTHON="$(jc_python "$JC_ROOT")" || {
  echo "[prune-llm-log] ERROR: cannot find deepagents/venv above ${JC_ROOT}" >&2
  exit 1
}

FORGET_PAYLOAD_AFTER="${JC_LLM_LOG_PAYLOAD_DAYS:-14}"

MODE=(--apply)
if [[ "${JC_PRUNE_DRY_RUN:-0}" == "1" ]]; then
  MODE=()
fi

printf '[prune-llm-log] %s start (payload window: %sd)\n' "$(date -Iseconds)" "$FORGET_PAYLOAD_AFTER"
exec "$PYTHON" "${JC_ROOT}/scripts/prune_llm_log.py" \
  --forget-payload-after "$FORGET_PAYLOAD_AFTER" \
  "${MODE[@]}"
