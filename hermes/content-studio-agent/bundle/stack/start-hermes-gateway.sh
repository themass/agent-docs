#!/usr/bin/env bash
# Launched by start-content-studio-stack.sh (avoids nested-quote bugs in bash -lc).
set -euo pipefail

: "${HERMES_GATEWAY_HOME:?HERMES_GATEWAY_HOME}"
: "${HERMES_CLI:?HERMES_CLI}"
: "${CONTENT_STUDIO_LLM_HERMES_BASE:?CONTENT_STUDIO_LLM_HERMES_BASE}"

set -a
# shellcheck disable=SC1090
source "${HERMES_GATEWAY_HOME}/.env" 2>/dev/null || true
set +a

export HERMES_HOME="${HERMES_GATEWAY_HOME}"
export HERMES_API_CALL_STALE_TIMEOUT="${HERMES_API_CALL_STALE_TIMEOUT:-600}"
export HERMES_LOCAL_STREAM_STALE_TIMEOUT="${HERMES_LOCAL_STREAM_STALE_TIMEOUT:-900}"
export OPENAI_BASE_URL="${CONTENT_STUDIO_LLM_HERMES_BASE}"
export TDAI_PROXY_URL="${TDAI_PROXY_URL:-http://127.0.0.1:8096}"
export TDAI_PROXY_HERMES_BASE="${CONTENT_STUDIO_LLM_HERMES_BASE}"

tdai_ids="${TDAI_HERMES_IDS_FILE:-}"
if [[ -z "$tdai_ids" && -n "${HERMES_PROFILE_HOME:-}" ]]; then
  tdai_ids="${HERMES_PROFILE_HOME}/tdai-hermes-ids.env"
fi
if [[ -f "$tdai_ids" ]]; then
  while IFS= read -r line; do
    case "$line" in
      TDAI_TEAM_ID=*|TDAI_AGENT_ID=*|TDAI_TASK_ID=*)
        key="${line%%=*}"
        val="${line#*=}"
        val="${val%\"}"
        val="${val#\"}"
        val="${val%\'}"
        val="${val#\'}"
        export "${key}=${val}"
        ;;
    esac
  done <"$tdai_ids"
fi

if [[ -n "${CONTENT_STUDIO_LLM_KEY:-}" ]]; then
  export OPENAI_API_KEY="${CONTENT_STUDIO_LLM_KEY}"
  export CUSTOM_API_KEY="${CONTENT_STUDIO_LLM_KEY}"
fi

exec "$HERMES_CLI" -p default gateway run --replace
