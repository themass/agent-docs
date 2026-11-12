#!/usr/bin/env bash
# Cron entry point for the agent ledger retention policy (jc_agent_trace).
#
# The ledger stores the full model input per turn, which includes the candidate's
# profile and resume text. JC_AGENT_TRACE_RETENTION_DAYS (default 60) is the window
# we promise; without this running on a schedule that promise is not true.
#
# crontab (as the web user, in the deploy directory; the script finds backend/server/.venv itself):
#   23 4 * * *  cd /home/web/webroot/job-come && ./scripts/prune_agent_trace.sh >> .data/logs/production/prune.log 2>&1
#
# Defaults to --apply: a cron job that only reports what it would do is the failure
# mode this script exists to prevent. Set JC_PRUNE_DRY_RUN=1 to inspect.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
PYTHON="$(jc_python "$JC_ROOT")" || {
  echo "[prune-agent-trace] ERROR: no Python found. Looked for the monorepo venv above ${JC_ROOT} and for" >&2
  echo "[prune-agent-trace]        ${JC_ROOT}/backend/server/.venv (built by ./scripts/deploy.sh). Or set JC_PYTHON." >&2
  exit 1
}

MODE=(--apply)
if [[ "${JC_PRUNE_DRY_RUN:-0}" == "1" ]]; then
  MODE=()
fi

printf '[prune-agent-trace] %s start\n' "$(date -Iseconds)"
exec "$PYTHON" "${JC_ROOT}/scripts/prune_agent_trace.py" "${MODE[@]}"
