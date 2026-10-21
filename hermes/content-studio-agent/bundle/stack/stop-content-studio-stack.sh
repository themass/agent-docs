#!/usr/bin/env bash
# Stop Content Studio stack services (pid files + port listeners + patterns).
# Also stops processes tracked by start-dev.sh (.runtime/*.pid).

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_resolve_content_studio_bundle_root() {
  local stack_dir="$1"
  if [[ -f "${stack_dir}/../env.sh" ]]; then
    (cd "${stack_dir}/.." && pwd)
    return 0
  fi
  local repo_root
  repo_root="$(cd "${stack_dir}/.." && pwd)"
  local bundle="${repo_root}/docs/hermes/content-studio-agent/bundle"
  if [[ -f "${bundle}/env.sh" ]]; then
    (cd "$bundle" && pwd)
    return 0
  fi
  return 1
}

if ! BUNDLE_ROOT="$(_resolve_content_studio_bundle_root "$STACK_DIR")"; then
  echo "stop-content-studio-stack: cannot find Content Studio bundle env.sh" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$BUNDLE_ROOT/env.sh"
ROOT_DIR="${ROOT_DIR:-$HERMES_DEV}"
# shellcheck source=/dev/null
source "$STACK_DIR/ports.env"

# shellcheck source=/dev/null
# ports loaded above
STACK_RUNTIME="$ROOT_DIR/.runtime/content-studio-stack"
DEV_RUNTIME="$ROOT_DIR/.runtime"
HERMES_WORKSPACE_DIR="${HERMES_WORKSPACE_DIR:-$ROOT_DIR/hermes-workspace}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
HERMES_GATEWAY_HOME="${HERMES_GATEWAY_HOME:-$HOME/.hermes}"
export HERMES_HOME

GATEWAY_PORT="${GATEWAY_PORT:-8642}"
DASHBOARD_PORT="${DASHBOARD_PORT:-9119}"
WORKSPACE_PORT="${WORKSPACE_PORT:-${PORT:-3000}}"
HERMES_WEBUI_PORT="${HERMES_WEBUI_PORT:-8787}"
HERMES_STUDIO_BACKEND_PORT="${HERMES_STUDIO_BACKEND_PORT:-8647}"
HERMES_STUDIO_PORT="${HERMES_STUDIO_PORT:-8649}"
AIONUI_PORT="${AIONUI_PORT:-25809}"
AIONUI_DIR="${AIONUI_DIR:-$ROOT_DIR/AionUi}"
HERMES_DESKTOP_DIR="${HERMES_DESKTOP_DIR:-$ROOT_DIR/hermes-desktop}"
HERMES_WEBUI_DIR="${HERMES_WEBUI_DIR:-$ROOT_DIR/hermes-webui}"
HERMES_STUDIO_DIR="${HERMES_STUDIO_DIR:-$ROOT_DIR/hermes-studio}"
SURREAL_PORT="${SURREAL_PORT:-8000}"
NOTEBOOK_API_PORT="${NOTEBOOK_API_PORT:-5055}"
NOTEBOOK_FRONTEND_PORT="${NOTEBOOK_FRONTEND_PORT:-3001}"
MPT_API_PORT="${MPT_API_PORT:-8082}"
MPT_WEBUI_PORT="${MPT_WEBUI_PORT:-8501}"
FREELLMAPI_PORT="${FREELLMAPI_PORT:-3011}"
OPENINSPECTOR_PROXY_PORT="${OPENINSPECTOR_PROXY_PORT:-8080}"
OPENINSPECTOR_API_PORT="${OPENINSPECTOR_API_PORT:-8081}"
OPENINSPECTOR_UI_PORT="${OPENINSPECTOR_UI_PORT:-5173}"
OPENINSPECTOR_DIR="${OPENINSPECTOR_DIR:-$REPO_ROOT/openinspector}"
STOP_SURREALDB="${STOP_SURREALDB:-0}"

log() { printf '\033[1;36m[content-studio-stack]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[content-studio-stack]\033[0m %s\n' "$*"; }

kill_pid_gracefully() {
  local pid="$1"
  local label="${2:-pid ${pid}}"
  [[ -n "$pid" ]] || return 0
  kill -0 "$pid" 2>/dev/null || return 0
  log "Stopping ${label} (pid ${pid})"
  kill "$pid" 2>/dev/null || true
  local i
  for ((i = 1; i <= 20; i++)); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    warn "Force killing ${label} (pid ${pid})"
    kill -9 "$pid" 2>/dev/null || true
  fi
}

stop_pid_file() {
  local runtime_dir="$1"
  local name="$2"
  local pid_file="${runtime_dir}/${name}.pid"
  [[ -f "$pid_file" ]] || return 0
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  kill_pid_gracefully "$pid" "$name"
  rm -f "$pid_file"
}

stop_port_listeners() {
  local port="$1"
  local label="$2"
  if ! command -v lsof >/dev/null 2>&1; then
    warn "lsof not found — cannot stop listeners on port ${port} (${label})"
    return 0
  fi
  local pids
  pids="$(lsof -t -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  [[ -n "${pids// /}" ]] || return 0
  local pid
  for pid in $pids; do
    kill_pid_gracefully "$pid" "${label} on :${port}"
  done
}

log "Stopping Content Studio stack..."

stop_pid_file "$STACK_RUNTIME" freellmapi
stop_pid_file "$STACK_RUNTIME" memory-core
stop_pid_file "$STACK_RUNTIME" memory-proxy
stop_port_listeners "$FREELLMAPI_PORT" "FreeLLMAPI"
stop_port_listeners "${MEMORY_CORE_PORT:-8420}" "TencentDB Memory Core"
stop_port_listeners "${MEMORY_PROXY_PORT:-8096}" "TencentDB Memory Proxy"
pkill -f "MemoryCore.*gateway/server" 2>/dev/null || true
pkill -f "MemoryProxy.*src/index.ts" 2>/dev/null || true
if [[ -d "${FREELLMAPI_INSTALL_DIR:-$HOME/freellmapi}" ]] && command -v docker >/dev/null 2>&1; then
  (cd "${FREELLMAPI_INSTALL_DIR:-$HOME/freellmapi}" && docker compose stop 2>/dev/null) || true
fi

if [[ -x "$OPENINSPECTOR_DIR/scripts/dev-local.sh" ]]; then
  PROXY_PORT="$OPENINSPECTOR_PROXY_PORT" API_PORT="$OPENINSPECTOR_API_PORT" UI_PORT="$OPENINSPECTOR_UI_PORT" \
    "$OPENINSPECTOR_DIR/scripts/dev-local.sh" stop 2>/dev/null || true
fi

TDAI_MEMORY_DIR="${TDAI_MEMORY_DIR:-/Users/gqli/work/TencentDB-Agent-Memory}"
STOP_TDAI_MEMORY="${STOP_TDAI_MEMORY:-1}"
if [[ "$STOP_TDAI_MEMORY" == "1" ]] && [[ -x "${TDAI_MEMORY_DIR}/deploy/global-images/stop-all.sh" ]]; then
  log "Stopping TencentDB Memory (docker)..."
  (cd "${TDAI_MEMORY_DIR}/deploy/global-images" && ./stop-all.sh) 2>/dev/null || true
fi

# 1) Hermes CLI helpers (dashboard; gateway if supported)
if [[ -x "$ROOT_DIR/_hermes-cli.sh" ]]; then
  "$ROOT_DIR/_hermes-cli.sh" dashboard --stop 2>/dev/null || true
  env HERMES_HOME="$HERMES_GATEWAY_HOME" "$ROOT_DIR/_hermes-cli.sh" -p default gateway stop 2>/dev/null || true
fi

# 2) pid files from this stack + start-dev.sh
for name in aionui hermes-desktop hermes-studio hermes-webui workspace mpt-webui mpt-api notebook-frontend notebook-worker notebook-api dashboard gateway ali-tts-proxy volcano-tts-proxy; do
  stop_pid_file "$STACK_RUNTIME" "$name"
done
for name in workspace dashboard gateway; do
  stop_pid_file "$DEV_RUNTIME" "$name"
done

# 3) Port listeners (covers processes started outside pid tracking)
stop_port_listeners "$WORKSPACE_PORT" "Hermes Workspace"
stop_port_listeners "$DASHBOARD_PORT" "Hermes Dashboard"
stop_port_listeners "$GATEWAY_PORT" "Hermes Gateway"
if [[ -x "$HERMES_WEBUI_DIR/ctl.sh" ]]; then
  (cd "$HERMES_WEBUI_DIR" && ./ctl.sh stop) 2>/dev/null || true
fi
stop_port_listeners "$HERMES_WEBUI_PORT" "hermes-webui"
stop_port_listeners "$AIONUI_PORT" "AionUi"
stop_port_listeners "$HERMES_STUDIO_BACKEND_PORT" "hermes-studio API"
stop_port_listeners "$HERMES_STUDIO_PORT" "hermes-studio (Vite)"
stop_port_listeners "$MPT_WEBUI_PORT" "MoneyPrinterTurbo WebUI"
stop_port_listeners "$MPT_API_PORT" "MoneyPrinterTurbo API"
stop_port_listeners "$NOTEBOOK_API_PORT" "Open Notebook API"
ALI_TTS_PROXY_PORT="${ALI_TTS_PROXY_PORT:-8969}"
VOLCENGINE_TTS_PROXY_PORT="${VOLCENGINE_TTS_PROXY_PORT:-8968}"
stop_port_listeners "$ALI_TTS_PROXY_PORT" "Aliyun TTS proxy"
stop_port_listeners "$VOLCENGINE_TTS_PROXY_PORT" "Volcano TTS proxy"

if [[ "$STOP_SURREALDB" == "1" ]]; then
  SURREALDB_NATIVE_SCRIPT="${SURREALDB_NATIVE_SCRIPT:-$OPEN_NOTEBOOK_DIR/scripts/surrealdb-native.sh}"
  if [[ -x "$SURREALDB_NATIVE_SCRIPT" ]]; then
    bash "$SURREALDB_NATIVE_SCRIPT" stop 2>/dev/null || true
  fi
  stop_port_listeners "$SURREAL_PORT" "SurrealDB"
  if command -v docker >/dev/null 2>&1 && [[ -d "$OPEN_NOTEBOOK_DIR" ]]; then
    log "Stopping SurrealDB docker container (if any)..."
    (cd "$OPEN_NOTEBOOK_DIR" && docker compose stop surrealdb) 2>/dev/null || true
  fi
fi

# 4) Pattern fallbacks (parent shells / stale children)
pkill -f "hermes-workspace.*vite.*dev" 2>/dev/null || true
pkill -f "${HERMES_WORKSPACE_DIR}/node_modules/vite/bin/vite.js dev" 2>/dev/null || true
pkill -f "hermes gateway run" 2>/dev/null || true
pkill -f "hermes dashboard" 2>/dev/null || true
pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "${OPEN_NOTEBOOK_DIR}/frontend.*next dev" 2>/dev/null || true
pkill -f "open-notebook/frontend.*next dev" 2>/dev/null || true
pkill -f "${OPEN_NOTEBOOK_DIR}/run_api.py" 2>/dev/null || true
pkill -f "run_api.py" 2>/dev/null || true
pkill -f "surreal-commands-worker" 2>/dev/null || true
pkill -f "${MONEYPRINTER_DIR}/main.py" 2>/dev/null || true
pkill -f "MoneyPrinterTurbo.*main.py" 2>/dev/null || true
pkill -f "streamlit run.*MoneyPrinterTurbo" 2>/dev/null || true
pkill -f "ali-tts-proxy.py" 2>/dev/null || true
pkill -f "volcano-tts-proxy.py" 2>/dev/null || true
pkill -f "webui/Main.py" 2>/dev/null || true
pkill -f "${HERMES_STUDIO_DIR}/packages/server" 2>/dev/null || true
pkill -f "${HERMES_STUDIO_DIR}.*vite.*--port ${HERMES_STUDIO_PORT}" 2>/dev/null || true
pkill -f "hermes-studio.*npm run dev" 2>/dev/null || true
pkill -f "${AIONUI_DIR}.*scripts/webui.ts" 2>/dev/null || true
pkill -f "${HERMES_DESKTOP_DIR}.*electron" 2>/dev/null || true

# 5) Report remaining listeners
if command -v lsof >/dev/null 2>&1; then
  remaining=()
  for spec in \
    "${WORKSPACE_PORT}:Workspace" \
    "${GATEWAY_PORT}:Gateway" \
    "${DASHBOARD_PORT}:Dashboard" \
    "${HERMES_WEBUI_PORT}:hermes-webui" \
    "${AIONUI_PORT}:AionUi" \
    "${HERMES_STUDIO_BACKEND_PORT}:hermes-studio API" \
    "${HERMES_STUDIO_PORT}:hermes-studio UI" \
    "${NOTEBOOK_API_PORT}:Notebook API" \
    "${NOTEBOOK_FRONTEND_PORT}:Notebook Web UI" \
    "${MPT_API_PORT}:MPT API" \
    "${MPT_WEBUI_PORT}:MPT WebUI" \
    "${FREELLMAPI_PORT}:FreeLLMAPI" \
    "${OPENINSPECTOR_PROXY_PORT}:OpenInspector Proxy" \
    "${OPENINSPECTOR_API_PORT}:OpenInspector API" \
    "${OPENINSPECTOR_UI_PORT}:OpenInspector UI" \
    "${MEMORY_CORE_PORT:-8420}:TencentDB Memory Core" \
    "${MEMORY_PROXY_PORT:-8096}:TencentDB Memory Proxy" \
    "${MEMORY_PANEL_PORT:-8125}:TencentDB Memory Panel"; do
    port="${spec%%:*}"
    label="${spec#*:}"
    if lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1; then
      remaining+=("${port} (${label})")
    fi
  done
  if [[ ${#remaining[@]} -gt 0 ]]; then
    warn "Still listening (manual stop may be needed): ${remaining[*]}"
    for spec in "${remaining[@]}"; do
      port="${spec%% *}"
      lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | while IFS= read -r line; do
        warn "  ${line}"
      done
    done
  else
    log "All stack ports are free."
  fi
fi

log "Done."
if [[ "$STOP_SURREALDB" != "1" ]]; then
  log "SurrealDB on :${SURREAL_PORT} left running (set STOP_SURREALDB=1 to stop it)."
fi
