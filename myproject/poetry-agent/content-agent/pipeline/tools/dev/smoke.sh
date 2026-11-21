#!/usr/bin/env bash
set -euo pipefail
base="${AGENT_BFF_BASE_URL:-http://localhost:8100}"
printf 'Checking BFF health at %s ...\n' "$base"
curl --fail --silent --show-error "$base/health/ready" | python3 -m json.tool
printf '\nCreating no-content gap-analysis task ...\n'
payload='{"work_id":"work-chun-wang","title":"检查春望内容缺口","task_type":"GAP_ANALYSIS","actor":{"actor_id":"smoke_editor","role":"CONTENT_EDITOR"},"instructions":"只汇总已观察到的完整性缺口和人工审核问题。","requested_profile":"authoring"}'
response="$(curl --fail --silent --show-error -X POST "$base/api/poetry/v1/agent/tasks" -H 'content-type: application/json' -d "$payload")"
printf '%s\n' "$response" | python3 -m json.tool
printf '\nSmoke request completed. It does not create poetry content or publish anything.\n'
