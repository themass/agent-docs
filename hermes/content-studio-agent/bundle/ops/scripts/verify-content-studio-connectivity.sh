#!/usr/bin/env bash
# Quick smoke test after stack start (Gateway, TencentDB Proxy, Workspace path).
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8642}"
PROXY_URL="${TDAI_PROXY_URL:-http://127.0.0.1:8096}"
WORKSPACE_URL="${WORKSPACE_URL:-http://127.0.0.1:3000}"
PROFILE="${CONTENT_STUDIO_PROFILE_NAME:-content-studio}"
GATEWAY_HOME="${HERMES_GATEWAY_HOME:-$HOME/.hermes}"
PROFILE_HOME="${HERMES_PROFILE_HOME:-$HOME/.hermes/profiles/${PROFILE}}"

fail() { echo "[verify] FAIL: $*" >&2; exit 1; }
ok() { echo "[verify] OK: $*"; }

curl_ok() {
  local url="$1" label="$2"
  local code
  code="$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
  [[ "$code" =~ ^(200|204)$ ]] || fail "$label ($url) HTTP $code"
  ok "$label"
}

wait_curl_ok() {
  local url="$1" label="$2" tries="${3:-24}" delay="${4:-5}"
  local i code
  for ((i = 1; i <= tries; i++)); do
    code="$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
    if [[ "$code" =~ ^(200|204)$ ]]; then
      ok "$label"
      return 0
    fi
    sleep "$delay"
  done
  fail "$label ($url) HTTP $code after ${tries} tries"
}

read_tdai_env_val() {
  local f="$1" key="$2"
  grep -E "^${key}=" "$f" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "\047'
}

load_tdai_ids() {
  local f="${PROFILE_HOME}/tdai-hermes-ids.env"
  [[ -f "$f" ]] || return 1
  TDAI_TEAM_ID="$(read_tdai_env_val "$f" TDAI_TEAM_ID)"
  TDAI_AGENT_ID="$(read_tdai_env_val "$f" TDAI_AGENT_ID)"
  TDAI_TASK_ID="$(read_tdai_env_val "$f" TDAI_TASK_ID)"
  [[ -n "${TDAI_TEAM_ID}" && -n "${TDAI_AGENT_ID}" && -n "${TDAI_TASK_ID}" ]] || return 1
  return 0
}

wait_curl_ok "${GATEWAY_URL}/health" "Hermes Gateway" 12 5
wait_curl_ok "${PROXY_URL}/health" "TencentDB Proxy" 24 5
curl_ok "${WORKSPACE_URL}/" "Hermes Workspace"

mem_key=""
if [[ -f "${CONTENT_STUDIO_RUNTIME_DIR:-}/tdai-memory.env" ]]; then
  # shellcheck disable=SC1090
  source "${CONTENT_STUDIO_RUNTIME_DIR}/tdai-memory.env"
  mem_key="${TDAI_USER_KEY:-}"
fi
if [[ -z "$mem_key" && -f "${TDAI_ADMIN_KEY_FILE:-}" ]]; then
  mem_key="$(cat "$TDAI_ADMIN_KEY_FILE" 2>/dev/null || true)"
fi

if [[ -n "$mem_key" ]]; then
  conv_id="verify-smoke-$(date +%s)"
  hdr_args=()
  if load_tdai_ids; then
    hdr_args+=(-H "x-team-id: ${TDAI_TEAM_ID}" -H "x-agent-id: ${TDAI_AGENT_ID}" -H "x-task-id: ${TDAI_TASK_ID}")
    hdr_args+=(-H "x-conversation-id: ${conv_id}")
    ok "TencentDB ids loaded from ${PROFILE_HOME}/tdai-hermes-ids.env"
  else
    fail "Missing or incomplete ${PROFILE_HOME}/tdai-hermes-ids.env (need TDAI_TEAM_ID, TDAI_AGENT_ID, TDAI_TASK_ID)"
  fi
  body="$(curl -sS -m 90 -X POST "${PROXY_URL}/hermes/default/v1/chat/completions" \
    -H "Authorization: Bearer ${mem_key}" \
    -H "Content-Type: application/json" \
    "${hdr_args[@]}" \
    -d "{\"model\":\"gpt-5-6-luna\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8,\"stream\":false}" || true)"
  echo "$body" | grep -q '"choices"' || fail "Proxy chat completions (no choices in response)"
  ok "Proxy → LLM chat/completions (with Memory headers)"
  if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^tdai-proxy$'; then
    if docker logs tdai-proxy 2>&1 | tail -40 | grep -q "write-l0"; then
      ok "Proxy tdai-recorder write-l0 seen in recent logs"
    else
      fail "Proxy chat succeeded but no write-l0 in recent tdai-proxy logs (session bypass?)"
    fi
  fi
fi

cfg="${PROFILE_HOME}/config.yaml"
if [[ -f "$cfg" ]]; then
  if grep -q 'x-team-id:' "$cfg" && grep -q 'x-agent-id:' "$cfg" && grep -q 'x-task-id:' "$cfg"; then
    ok "Hermes config.yaml has TencentDB default_headers"
  else
    fail "Hermes config.yaml missing model.default_headers (run sync-content-studio-secrets.sh)"
  fi
fi

api_key="$(grep -E '^API_SERVER_KEY=' "${GATEWAY_HOME}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' \"'\''')"
[[ -n "$api_key" ]] || fail "API_SERVER_KEY missing in ${GATEWAY_HOME}/.env"

proxy_inj_before=""
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^tdai-proxy$'; then
  proxy_inj_before="$(docker logs tdai-proxy 2>&1 | grep 'injection-debug' | tail -1 || true)"
fi

gbody="$(curl -sS -m 120 -X POST "${GATEWAY_URL}/p/${PROFILE}/v1/chat/completions" \
  -H "Authorization: Bearer ${api_key}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5-6-luna","messages":[{"role":"user","content":"Reply exactly: stack-ok"}],"stream":false,"max_tokens":16}' || true)"
echo "$gbody" | grep -q '"choices"' || fail "Gateway profile chat (no choices)"
ok "Gateway → profile ${PROFILE} chat/completions"

if [[ -n "$mem_key" ]] && command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^tdai-proxy$'; then
  inj="$(docker logs tdai-proxy 2>&1 | grep 'injection-debug' | tail -1 || true)"
  if [[ -z "$inj" || "$inj" == "$proxy_inj_before" ]]; then
    fail "No new injection-debug line after Gateway chat (LLM may not have used Memory Proxy)"
  fi
  if echo "$inj" | grep -q 'conversationId=null'; then
    fail "Gateway LLM hit Proxy without memory session (conversationId=null). Restart Gateway after tdai-proxy-headers install + secrets sync."
  fi
  if echo "$inj" | grep -q 'injectedSkipped=true'; then
    fail "Memory injection skipped for Gateway chat (injectedSkipped=true)"
  fi
  ok "Gateway chat resolved Proxy conversationId (memory path active)"
fi

# Desktop/API continuity: explicit session id → x-conversation-id on Proxy (requires tdai-proxy-headers + Gateway restart).
desktop_session="verify-session-$(date +%s)"
sbody="$(curl -sS -m 120 -X POST "${GATEWAY_URL}/p/${PROFILE}/v1/chat/completions" \
  -H "Authorization: Bearer ${api_key}" \
  -H "X-Hermes-Session-Id: ${desktop_session}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5-6-luna","messages":[{"role":"user","content":"Reply exactly: session-ok"}],"stream":false,"max_tokens":16}' || true)"
echo "$sbody" | grep -q '"choices"' || fail "Gateway session chat (no choices)"
ok "Gateway chat with X-Hermes-Session-Id"

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^tdai-proxy$'; then
  if ! docker logs tdai-proxy 2>&1 | tail -120 | grep -q "conversationId=${desktop_session}"; then
    fail "Proxy never saw conversationId=${desktop_session}. Restart Gateway after install-tdai-proxy-headers-plugin.sh (plugin sets x-conversation-id from session_id)."
  fi
  ok "x-conversation-id propagated (conversationId=${desktop_session})"
fi

echo "[verify] All connectivity checks passed."
