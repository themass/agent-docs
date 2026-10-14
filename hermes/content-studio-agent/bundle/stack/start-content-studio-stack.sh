#!/usr/bin/env bash
# Start Content Studio full stack:
#   Hermes (Gateway + Dashboard + Workspace + WebUI + Studio)
#   Open Notebook (SurrealDB + API + Web UI)
#   MoneyPrinterTurbo (API + WebUI)
#
# Logs from background services interleave in this terminal.
# Stop with: ./stop-content-studio-stack.sh  (or Ctrl+C then stop script)

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# bundle/stack/start-*.sh  → ../env.sh
# hermes-dev/start-*.sh    → ../docs/hermes/content-studio-agent/bundle/env.sh
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
  err "Cannot find Content Studio bundle (missing env.sh). Run from bundle/stack/ or hermes-dev/."
  exit 1
fi
# shellcheck source=/dev/null
source "$BUNDLE_ROOT/env.sh"
ROOT_DIR="${ROOT_DIR:-$HERMES_DEV}"
# shellcheck source=/dev/null
source "$STACK_DIR/ports.env"
# shellcheck source=/dev/null
source "$BUNDLE_ROOT/lib/deepagents-python.env.sh"
# Suppress pip's "new release available" stderr on every stack start (OpenInspector + notebook paths use other venvs).
export PIP_DISABLE_PIP_VERSION_CHECK=1
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_DEV/hermes-agent}"
HERMES_WORKSPACE_DIR="${HERMES_WORKSPACE_DIR:-$HERMES_DEV/hermes-workspace}"
HERMES_WEBUI_DIR="${HERMES_WEBUI_DIR:-$ROOT_DIR/hermes-webui}"
HERMES_STUDIO_DIR="${HERMES_STUDIO_DIR:-$ROOT_DIR/hermes-studio}"
AIONUI_DIR="${AIONUI_DIR:-$ROOT_DIR/AionUi}"
HERMES_DESKTOP_DIR="${HERMES_DESKTOP_DIR:-$ROOT_DIR/hermes-desktop}"
RUNTIME_DIR="$ROOT_DIR/.runtime/content-studio-stack"
LOGS_DIR="$RUNTIME_DIR/logs"
CONTENT_STUDIO_PROFILE_NAME="${CONTENT_STUDIO_PROFILE_NAME:-content-studio}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/${CONTENT_STUDIO_PROFILE_NAME}}"
# One host gateway serves every profile (multiplex). Do not run gateway under a named profile.
HERMES_GATEWAY_HOME="${HERMES_GATEWAY_HOME:-$HOME/.hermes}"
export HERMES_HOME

# ── Ports (override via ports.env or env) ────────────────────────────────
# See PORTS.md — MPT API uses 8082 (OpenInspector keeps 8080).

# SurrealDB: auto (native surreal CLI, else docker) | native | docker | 0 (skip)
START_SURREALDB="${START_SURREALDB:-auto}"
SURREALDB_NATIVE_SCRIPT="${SURREALDB_NATIVE_SCRIPT:-$OPEN_NOTEBOOK_DIR/scripts/surrealdb-native.sh}"
START_NOTEBOOK_WORKER="${START_NOTEBOOK_WORKER:-1}"
# Ollama only needed when default_embedding_model is set. Content Studio uses no embedding.
START_OLLAMA="${START_OLLAMA:-0}"
OLLAMA_API_BASE="${OLLAMA_API_BASE:-http://127.0.0.1:11434}"
API_RELOAD="${API_RELOAD:-false}"
HERMES_DASHBOARD_TUI="${HERMES_DASHBOARD_TUI:-1}"
DASHBOARD_READY_TIMEOUT="${DASHBOARD_READY_TIMEOUT:-90}"
START_NOTEBOOK_FRONTEND="${START_NOTEBOOK_FRONTEND:-1}"

GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"
DASHBOARD_URL="http://127.0.0.1:${DASHBOARD_PORT}"
WORKSPACE_URL="http://127.0.0.1:${WORKSPACE_PORT}"
NOTEBOOK_API_URL="http://127.0.0.1:${NOTEBOOK_API_PORT}"
NOTEBOOK_FRONTEND_URL="http://127.0.0.1:${NOTEBOOK_FRONTEND_PORT}"
MPT_API_URL="http://127.0.0.1:${MPT_API_PORT}"
MPT_WEBUI_URL="http://127.0.0.1:${MPT_WEBUI_PORT}"
OPENINSPECTOR_URL="http://127.0.0.1:${OPENINSPECTOR_PROXY_PORT}"
OPENINSPECTOR_API_URL="http://127.0.0.1:${OPENINSPECTOR_API_PORT}"
OPENINSPECTOR_UI_URL="http://127.0.0.1:${OPENINSPECTOR_UI_PORT}"
HERMES_WEBUI_URL="http://127.0.0.1:${HERMES_WEBUI_PORT}"
HERMES_STUDIO_URL="http://127.0.0.1:${HERMES_STUDIO_PORT}"
AIONUI_URL="http://127.0.0.1:${AIONUI_PORT}"
TDAI_PANEL_URL="http://127.0.0.1:${MEMORY_PANEL_PORT}"
TDAI_PROXY_URL="http://127.0.0.1:${MEMORY_PROXY_PORT}"
TDAI_PROXY_HERMES_BASE="${TDAI_PROXY_URL}/hermes/${TDAI_SPACE_ID}"

mkdir -p "$RUNTIME_DIR" "$LOGS_DIR"

log() { printf '\033[1;36m[content-studio-stack]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[content-studio-stack]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[content-studio-stack]\033[0m %s\n' "$*" >&2; }

# Gateway API_SERVER_KEY → Workspace HERMES_API_TOKEN (portable chat uses Bearer auth).
read_gateway_api_server_key() {
  local env_file="${HERMES_GATEWAY_HOME}/.env"
  [[ -f "$env_file" ]] || return 0
  grep -E '^API_SERVER_KEY=' "$env_file" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'\''"'
}

ensure_workspace_env_kv() {
  local ws_env="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "$ws_env" 2>/dev/null; then
    return 0
  fi
  echo "${key}=${value}" >>"$ws_env"
}

HERMES_CLI="${HERMES_CLI:-$STACK_DIR/_hermes-cli.sh}"
chmod +x "$HERMES_CLI" 2>/dev/null || true

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1
    return $?
  fi
  (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
}

print_port_occupiers() {
  local port="$1"
  local label="$2"
  err ""
  err "Port ${port} (${label}) is already in use:"
  if ! command -v lsof >/dev/null 2>&1; then
    err "  lsof not found — install lsof to inspect the listener."
    return 1
  fi
  local lines
  lines="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$lines" ]]; then
    err "  (no LISTEN socket found — port may be in TIME_WAIT)"
    return 1
  fi
  while IFS= read -r line; do
    err "  ${line}"
  done <<<"$lines"
  local pids
  pids="$(lsof -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u | tr '\n' ' ')"
  if [[ -n "${pids// /}" ]] && command -v ps >/dev/null 2>&1; then
    err "  Process details:"
    # shellcheck disable=SC2086
    ps -o pid=,ppid=,user=,etime=,command= -p $pids 2>/dev/null | while IFS= read -r pline; do
      err "    ${pline}"
    done
  fi
  return 0
}

# Return 0 = OK to skip start (healthy reuse). Return 1 = fatal conflict.
resolve_port_for_start() {
  local port="$1"
  local label="$2"
  local health_url="${3:-}"

  if ! port_in_use "$port"; then
    return 0
  fi

  print_port_occupiers "$port" "$label"

  if [[ -n "$health_url" ]] && curl -fsS "$health_url" >/dev/null 2>&1; then
    warn "  → ${label} health check passed; reusing existing service on :${port}."
    return 0
  fi

  err "  → Cannot start ${label}. Stop the process above or set a different port."
  return 1
}

wait_http() {
  local url="$1"
  local label="$2"
  local tries="${3:-60}"
  local i
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "${label} ready: ${url}"
      return 0
    fi
    sleep 1
  done
  err "${label} not ready after ${tries}s: ${url}"
  return 1
}

start_background() {
  local name="$1"
  shift
  local pid_file="$RUNTIME_DIR/${name}.pid"
  local log_file="$LOGS_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
      warn "${name} already tracked (pid ${old_pid}), skipping start"
      return 0
    fi
  fi

  if [[ "${STACK_LOG_TO_TERMINAL:-0}" == "1" ]]; then
    log "Starting ${name}... (logging to this terminal)"
    "$@" &
  else
    log "Starting ${name}... (log: ${log_file})"
    : >"$log_file"
    "$@" >>"$log_file" 2>&1 &
  fi
  disown $! 2>/dev/null || true
  echo $! >"$pid_file"
}

cleanup_ours() {
  local name pid pid_file
  for name in aionui hermes-desktop hermes-studio hermes-webui workspace dashboard gateway mpt-webui mpt-api notebook-frontend notebook-api notebook-worker ollama ali-tts-proxy volcano-tts-proxy; do
    pid_file="$RUNTIME_DIR/${name}.pid"
    [[ -f "$pid_file" ]] || continue
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      log "Stopping ${name} (pid ${pid})..."
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  done
}

trap cleanup_ours INT TERM

# ── Hermes helpers (trimmed from start-dev.sh) ───────────────────────────
hermes_python() {
  if [[ -x "$DEEPAGENTS_PYTHON" ]]; then
    echo "$DEEPAGENTS_PYTHON"
  elif [[ -x "$HERMES_AGENT_DIR/.venv/bin/python" ]]; then
    echo "$HERMES_AGENT_DIR/.venv/bin/python"
  elif [[ -x "$HERMES_AGENT_DIR/venv/bin/python" ]]; then
    echo "$HERMES_AGENT_DIR/venv/bin/python"
  else
    echo ""
  fi
}

_hermes_agent_venv_needs_install() {
  local py="$1"
  [[ -x "$py" ]] || return 1
  "$py" -c "import snowballstemmer" >/dev/null 2>&1 || return 0
  "$py" -c "import fastapi, uvicorn" >/dev/null 2>&1 || return 0
  return 1
}

_install_hermes_agent_into_python() {
  local py="$1"
  local label="$2"
  command -v uv >/dev/null 2>&1 || { err "uv not found"; exit 1; }
  log "Installing hermes-agent [all] into ${label} (${py})..."
  (cd "$HERMES_AGENT_DIR" && UV_PYTHON="$py" uv pip install --python "$py" -e ".[all]")
}

ensure_hermes_agent_deps() {
  local py missing=()
  py="$(hermes_python)"
  [[ -n "$py" ]] || return 0
  "$py" -c "import fastapi, uvicorn" >/dev/null 2>&1 || missing+=("web")
  "$py" -c "import snowballstemmer" >/dev/null 2>&1 || missing+=("all")
  if [[ "$HERMES_DASHBOARD_TUI" == "1" ]]; then
    "$py" -c "import ptyprocess" >/dev/null 2>&1 || missing+=("pty")
  fi
  if [[ ${#missing[@]} -gt 0 ]]; then
    _install_hermes_agent_into_python "$py" "monorepo venv"
  fi
  # Hermes Studio bridge prefers hermes-agent/{venv,.venv} when present — keep them in sync.
  for side_venv in "$HERMES_AGENT_DIR/venv/bin/python" "$HERMES_AGENT_DIR/.venv/bin/python"; do
    [[ -x "$side_venv" ]] || continue
    [[ "$side_venv" == "$py" ]] && continue
    if _hermes_agent_venv_needs_install "$side_venv"; then
      _install_hermes_agent_into_python "$side_venv" "hermes-agent side venv"
    fi
  done
}

hermes_cli_bin() {
  if [[ -x "${DEEPAGENTS_VENV}/bin/hermes" ]]; then
    echo "${DEEPAGENTS_VENV}/bin/hermes"
  elif [[ -x "${HERMES_AGENT_DIR}/venv/bin/hermes" ]]; then
    echo "${HERMES_AGENT_DIR}/venv/bin/hermes"
  else
    echo ""
  fi
}

# Hermes Studio discovers `hermes` on PATH at boot; monorepo venv must expose the CLI.
ensure_hermes_cli_for_studio() {
  [[ "$START_HERMES_STUDIO" == "1" ]] || return 0
  [[ -x "${DEEPAGENTS_VENV}/bin/hermes" ]] && return 0
  local py
  py="$(hermes_python)"
  [[ -n "$py" ]] || return 0
  if "$py" -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('hermes_cli') else 1)" 2>/dev/null; then
    return 0
  fi
  log "Installing hermes CLI into monorepo venv (Hermes Studio runtime)..."
  command -v uv >/dev/null 2>&1 || { err "uv not found"; exit 1; }
  (cd "$HERMES_AGENT_DIR" && UV_PYTHON="$DEEPAGENTS_PYTHON" uv pip install -e ".[all]")
}

dashboard_build_needed() {
  local web_dir="$HERMES_AGENT_DIR/web"
  local sentinel="$HERMES_AGENT_DIR/hermes_cli/web_dist/.vite/manifest.json"
  [[ -f "$web_dir/package.json" ]] || return 1
  [[ ! -f "$sentinel" ]] && return 0
  [[ "$web_dir/package.json" -nt "$sentinel" ]] && return 0
  return 1
}

ensure_dashboard_web_ui() {
  local web_dir="$HERMES_AGENT_DIR/web"
  dashboard_build_needed || return 0
  command -v npm >/dev/null 2>&1 || { err "npm required to build dashboard"; exit 1; }
  log "Building Hermes dashboard web UI (first run may take several minutes)..."
  (cd "$web_dir" && npm install --engine-strict=false && npm run build)
}

ensure_notebook_frontend_deps() {
  local fe_dir="$OPEN_NOTEBOOK_DIR/frontend"
  if [[ ! -f "$fe_dir/package.json" ]]; then
    err "Missing Open Notebook frontend: ${fe_dir}"
    exit 1
  fi
  if [[ -d "$fe_dir/node_modules" ]]; then
    return 0
  fi
  command -v npm >/dev/null 2>&1 || { err "npm required for Open Notebook frontend"; exit 1; }
  log "Installing Open Notebook frontend dependencies (first run may take a few minutes)..."
  (cd "$fe_dir" && npm install)
}

ensure_workspace_env() {
  local ws_env="$HERMES_WORKSPACE_DIR/.env"
  local gw_key
  [[ -f "$ws_env" ]] || touch "$ws_env"
  ensure_workspace_env_kv "$ws_env" "HERMES_API_URL" "${GATEWAY_URL}"
  ensure_workspace_env_kv "$ws_env" "HERMES_DASHBOARD_URL" "${DASHBOARD_URL}"
  ensure_workspace_env_kv "$ws_env" "HERMES_AGENT_PATH" "${HERMES_AGENT_DIR}"
  ensure_workspace_env_kv "$ws_env" "WORKSPACE_AUTO_APPROVE" "1"
  # Multiplex gateway: chat must hit /p/<profile>/v1/... (unscoped /v1/* is always default).
  ensure_workspace_env_kv "$ws_env" "HERMES_WORKSPACE_GATEWAY_PROFILE" "${CONTENT_STUDIO_PROFILE_NAME}"
  # Portable Local Chat → POST :8642/v1/chat/completions; first token can take 30–90s on reasoning models.
  ensure_workspace_env_kv "$ws_env" "STREAM_ACCEPTED_TIMEOUT_MS" "${WORKSPACE_STREAM_ACCEPTED_TIMEOUT_MS:-300000}"
  gw_key="$(read_gateway_api_server_key)"
  if [[ -n "$gw_key" ]]; then
    ensure_workspace_env_kv "$ws_env" "HERMES_API_TOKEN" "$gw_key"
  fi
}

ensure_workspace_deps() {
  local nm="$HERMES_WORKSPACE_DIR/node_modules"
  local vite_js="$nm/vite/bin/vite.js"
  if [[ -f "$vite_js" && -d "$nm/rehype-raw" && -d "$nm/rehype-sanitize" ]]; then
    return 0
  fi
  log "Installing workspace dependencies (pnpm install --ignore-scripts)..."
  (cd "$HERMES_WORKSPACE_DIR" && pnpm install --ignore-scripts)
}

ensure_hermes_webui_deps() {
  [[ "$START_HERMES_WEBUI" == "1" ]] || return 0
  [[ -d "$HERMES_WEBUI_DIR" ]] || return 0
  [[ -f "$HERMES_WEBUI_DIR/bootstrap.py" ]] || { err "Missing ${HERMES_WEBUI_DIR}/bootstrap.py"; exit 1; }
  chmod +x "$HERMES_WEBUI_DIR/start.sh" "$HERMES_WEBUI_DIR/ctl.sh" 2>/dev/null || true
}

ensure_content_studio_hermes_profile() {
  # Studio reads ~/.hermes/active_profile + per-browser localStorage; WebUI/Gateway use HERMES_HOME.
  local root="${HERMES_GATEWAY_HOME}"
  local name="${CONTENT_STUDIO_PROFILE_NAME}"
  local profile_dir="${root}/profiles/${name}"
  [[ -d "$profile_dir" ]] || {
    warn "Content Studio profile missing: ${profile_dir} (run bundle/profile/install.sh)"
    return 0
  }
  printf '%s\n' "$name" >"${root}/active_profile"
}

ensure_hermes_studio_deps() {
  [[ "$START_HERMES_STUDIO" == "1" ]] || return 0
  [[ -d "$HERMES_STUDIO_DIR" ]] || return 0
  if [[ -d "$HERMES_STUDIO_DIR/node_modules" ]]; then
    return 0
  fi
  command -v npm >/dev/null 2>&1 || { err "npm required for hermes-studio"; exit 1; }
  log "Installing hermes-studio dependencies (npm install; first run may take several minutes)..."
  (cd "$HERMES_STUDIO_DIR" && npm install)
}

start_hermes_webui() {
  [[ "$START_HERMES_WEBUI" == "1" ]] || { log "Skipping hermes-webui (START_HERMES_WEBUI=0)"; return 0; }
  [[ -d "$HERMES_WEBUI_DIR" ]] || { warn "Missing hermes-webui at ${HERMES_WEBUI_DIR} — skip"; return 0; }
  local health_url="${HERMES_WEBUI_URL}/health"
  if port_in_use "$HERMES_WEBUI_PORT" && curl -fsS "$health_url" >/dev/null 2>&1; then
    log "hermes-webui already up: ${HERMES_WEBUI_URL}"
    return 0
  fi
  resolve_port_for_start "$HERMES_WEBUI_PORT" "hermes-webui" "$health_url" || exit 1
  ensure_hermes_webui_deps
  export HERMES_HOME
  log "Starting hermes-webui (${HERMES_WEBUI_URL})..."
  if [[ -x "$HERMES_WEBUI_DIR/ctl.sh" ]]; then
    (
      cd "$HERMES_WEBUI_DIR"
      export HERMES_WEBUI_PORT="${HERMES_WEBUI_PORT}"
      export HERMES_WEBUI_PYTHON="${HERMES_WEBUI_PYTHON:-${DEEPAGENTS_PYTHON:-}}"
      ./ctl.sh start --no-browser "$HERMES_WEBUI_PORT"
    ) >>"$LOGS_DIR/hermes-webui.log" 2>&1
  else
    start_background hermes-webui bash -lc \
      "cd '$HERMES_WEBUI_DIR' && export HERMES_HOME='$HERMES_HOME' HERMES_WEBUI_PORT='$HERMES_WEBUI_PORT' && ./start.sh --no-browser '$HERMES_WEBUI_PORT'"
  fi
  wait_http "$health_url" "hermes-webui" 90
}

start_hermes_studio() {
  [[ "$START_HERMES_STUDIO" == "1" ]] || { log "Skipping hermes-studio (START_HERMES_STUDIO=0)"; return 0; }
  [[ -d "$HERMES_STUDIO_DIR" ]] || { warn "Missing hermes-studio at ${HERMES_STUDIO_DIR} — skip"; return 0; }
  local backend_url="http://127.0.0.1:${HERMES_STUDIO_BACKEND_PORT}"
  if port_in_use "$HERMES_STUDIO_PORT" && curl -fsS "${HERMES_STUDIO_URL}" >/dev/null 2>&1; then
    log "hermes-studio already up: ${HERMES_STUDIO_URL}"
    return 0
  fi
  resolve_port_for_start "$HERMES_STUDIO_BACKEND_PORT" "hermes-studio API" "$backend_url" || exit 1
  resolve_port_for_start "$HERMES_STUDIO_PORT" "hermes-studio (Vite)" "${HERMES_STUDIO_URL}" || exit 1
  command -v npm >/dev/null 2>&1 || { err "npm required for hermes-studio"; exit 1; }
  ensure_hermes_studio_deps
  ensure_hermes_cli_for_studio
  ensure_content_studio_hermes_profile
  local studio_py studio_hermes studio_path
  studio_py="$(hermes_python)"
  studio_hermes="$(hermes_cli_bin)"
  studio_path="${DEEPAGENTS_VENV}/bin"
  if [[ -n "$studio_hermes" ]]; then
    studio_path="$(dirname "$studio_hermes"):${studio_path}"
  fi
  log "Starting hermes-studio (${HERMES_STUDIO_URL}, API ${backend_url})..."
  warn "Studio 默认会话是 Ekko 通用助手；Content Studio 视频 Agent 请选运行时 Hermes + Profile「${CONTENT_STUDIO_PROFILE_NAME}」，新建会话后再聊（见 ARCHITECTURE.md）"
  start_background hermes-studio bash -lc \
    "cd '$HERMES_STUDIO_DIR' && export PATH='${studio_path}:'\"\${PATH:-}\" HERMES_HOME='$HERMES_GATEWAY_HOME' PROFILE='${CONTENT_STUDIO_PROFILE_NAME}' HERMES_WEB_UI_BACKEND_PORT='$HERMES_STUDIO_BACKEND_PORT' HERMES_AGENT_ROOT='$HERMES_AGENT_DIR' HERMES_AGENT_BRIDGE_PYTHON='$studio_py' HERMES_AGENT_CLI_PYTHON='$studio_py'${studio_hermes:+ HERMES_BIN='$studio_hermes'} && npm run dev"
  wait_http "${HERMES_STUDIO_URL}" "hermes-studio" 180
}

# Strip whitespace/quotes from env values (never embed secrets in quoted shell fragments).
_strip_env_value() {
  tr -d " \t\"'"
}

read_profile_llm_key() {
  local env_file="${HERMES_HOME}/.env" k
  [[ -f "$env_file" ]] || return 0
  for k in CUSTOM_API_KEY OPENAI_API_KEY OPENAI_COMPATIBLE_API_KEY; do
    if grep -qE "^${k}=" "$env_file" 2>/dev/null; then
      grep -E "^${k}=" "$env_file" | head -1 | cut -d= -f2- | _strip_env_value
      return 0
    fi
  done
}

# Real upstream LLM key (newapi/OpenInspector), not TencentDB sk-mem user_key.
read_upstream_llm_key() {
  local secrets="${HERMES_HOME}/secrets.env" k
  if [[ -f "$secrets" ]]; then
    k="$(grep -E '^LLM_API_KEY=' "$secrets" 2>/dev/null | head -1 | cut -d= -f2- | _strip_env_value)"
    if [[ -n "$k" && "$k" != sk-mem-* && "$k" != sk-your-key-here ]]; then
      printf '%s' "$k"
      return 0
    fi
  fi
  k="$(read_profile_llm_key)"
  if [[ -n "$k" && "$k" != sk-mem-* ]]; then
    printf '%s' "$k"
    return 0
  fi
  return 1
}

read_profile_llm_model() {
  local cfg="${HERMES_HOME}/config.yaml"
  [[ -f "$cfg" ]] || return 0
  awk '/^model:/{m=1;next} m&&/^[^ ]/{m=0} m&&/^  default:/{print $2; exit}' "$cfg" | _strip_env_value
}

# Write KEY=VALUE lines for a background service; values via printf %q (safe for secrets).
write_service_env_file() {
  local dest="$1"
  shift
  : >"$dest"
  local pair key value
  for pair in "$@"; do
    key="${pair%%=*}"
    value="${pair#*=}"
    [[ -n "$key" ]] || continue
    printf '%s=%q\n' "$key" "$value" >>"$dest"
  done
}

# AionUi: bun run webui（独立于 Electron）。LLM 走 OpenInspector；Hermes 相关环境与 profile 对齐。
start_aionui() {
  [[ "$START_AIONUI" == "1" ]] || { log "Skipping AionUi (START_AIONUI=0)"; return 0; }
  [[ -d "$AIONUI_DIR" ]] || { warn "Missing AionUi at ${AIONUI_DIR} — skip"; return 0; }
  if port_in_use "$AIONUI_PORT" && curl -fsS "${AIONUI_URL}" >/dev/null 2>&1; then
    log "AionUi already up: ${AIONUI_URL}"
    return 0
  fi
  resolve_port_for_start "$AIONUI_PORT" "AionUi" "${AIONUI_URL}" || exit 1
  if ! command -v bun >/dev/null 2>&1; then
    # Official installer (Homebrew CLT may be broken on macOS 26).
    export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
    export PATH="$BUN_INSTALL/bin:$PATH"
    if ! command -v bun >/dev/null 2>&1; then
      warn "AionUi 需要 bun（未找到）。安装: curl -fsSL https://bun.sh/install | bash ；已跳过 AionUi"
      return 0
    fi
  fi
  if [[ ! -d "$AIONUI_DIR/node_modules" ]]; then
    log "Installing AionUi dependencies (bun install; first run may take several minutes)..."
    (cd "$AIONUI_DIR" && bun install) >>"$LOGS_DIR/aionui.log" 2>&1 || { warn "AionUi bun install 失败，见 ${LOGS_DIR}/aionui.log；已跳过"; return 0; }
  fi
  local aioncore_bin=""
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) aioncore_bin="${AIONUI_DIR}/resources/bundled-aioncore/darwin-arm64/aioncore" ;;
    Darwin-x86_64) aioncore_bin="${AIONUI_DIR}/resources/bundled-aioncore/darwin-x64/aioncore" ;;
    Linux-aarch64|Linux-arm64) aioncore_bin="${AIONUI_DIR}/resources/bundled-aioncore/linux-arm64/aioncore" ;;
    Linux-x86_64) aioncore_bin="${AIONUI_DIR}/resources/bundled-aioncore/linux-x64/aioncore" ;;
  esac
  if [[ ! -x "$aioncore_bin" ]]; then
    log "Preparing AionUi backend (aioncore) — first download may take a few minutes..."
    (cd "$AIONUI_DIR" && node scripts/prepareAioncore.js) >>"$LOGS_DIR/aionui.log" 2>&1 \
      || { warn "aioncore 下载/准备失败，见 ${LOGS_DIR}/aionui.log；已跳过 AionUi"; return 0; }
  fi
  if [[ ! -x "$aioncore_bin" ]]; then
    warn "aioncore 仍不可用（${aioncore_bin}）；已跳过 AionUi"
    return 0
  fi
  local llm_model env_file llm_base llm_key_out
  content_studio_resolve_llm_routing
  llm_model="$(read_profile_llm_model)"
  llm_base="${CONTENT_STUDIO_LLM_HERMES_BASE}"
  llm_key_out="${CONTENT_STUDIO_LLM_KEY}"
  if [[ "${CONTENT_STUDIO_LLM_USING_TDAI}" == "1" ]]; then
    log "AionUi LLM via TencentDB Proxy: ${llm_base}"
  fi
  env_file="$RUNTIME_DIR/aionui.env"
  write_service_env_file "$env_file" \
    "AIONUI_PORT=${AIONUI_PORT}" \
    "AIONUI_OPEN_BROWSER=0" \
    "AIONUI_BACKEND_BIN=${aioncore_bin}" \
    "HERMES_HOME=${HERMES_GATEWAY_HOME}" \
    "HERMES_PROFILE=${CONTENT_STUDIO_PROFILE_NAME}" \
    "HERMES_API_URL=${GATEWAY_URL}" \
    "HERMES_DASHBOARD_URL=${DASHBOARD_URL}" \
    "OPENAI_BASE_URL=${llm_base}" \
    "OPENAI_API_BASE=${llm_base}" \
    "OPENAI_MODEL=${llm_model:-gpt-5-6-luna}" \
    ${llm_key_out:+ "OPENAI_API_KEY=${llm_key_out}"} \
    ${HERMES_API_TOKEN:+ "HERMES_API_TOKEN=${HERMES_API_TOKEN}"}
  log "Starting AionUi (${AIONUI_URL}; LLM=${llm_base}, profile=${CONTENT_STUDIO_PROFILE_NAME})..."
  warn "AionUi 内置助手 Base URL=${llm_base}；Codex 需在 ~/.codex/config.toml 指向 ${TDAI_PROXY_URL}/codex/${TDAI_SPACE_ID}"
  start_background aionui bash -lc \
    "cd $(printf %q "$AIONUI_DIR") && set -a && source $(printf %q "$env_file") && set +a && bun run webui"
  # First webui may rebuild renderer; allow longer wait
  wait_http "${AIONUI_URL}" "AionUi" 180 || warn "AionUi 未在预期时间内就绪，查看 ${LOGS_DIR}/aionui.log"
}

# hermes-desktop: Electron 桌面端（npm run dev）。HERMES_HOME 指向根目录，profile 由 active_profile 决定。
start_hermes_desktop() {
  [[ "$START_HERMES_DESKTOP" == "1" ]] || { log "Skipping hermes-desktop (START_HERMES_DESKTOP=0)"; return 0; }
  [[ -d "$HERMES_DESKTOP_DIR" ]] || { warn "Missing hermes-desktop at ${HERMES_DESKTOP_DIR} — skip"; return 0; }
  command -v npm >/dev/null 2>&1 || { warn "npm required for hermes-desktop — skip"; return 0; }
  local pid_file="$RUNTIME_DIR/hermes-desktop.pid" old_pid
  if [[ -f "$pid_file" ]]; then
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
      log "hermes-desktop already running (pid ${old_pid})"
      return 0
    fi
  fi
  export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"
  export ELECTRON_BUILDER_BINARIES_MIRROR="${ELECTRON_BUILDER_BINARIES_MIRROR:-https://npmmirror.com/mirrors/electron-builder-binaries/}"
  if [[ ! -d "$HERMES_DESKTOP_DIR/node_modules" ]]; then
    log "Installing hermes-desktop dependencies (npm install; first run may take several minutes)..."
    (cd "$HERMES_DESKTOP_DIR" && npm install) >>"$LOGS_DIR/hermes-desktop.log" 2>&1 || { warn "hermes-desktop npm install 失败，见 ${LOGS_DIR}/hermes-desktop.log；已跳过"; return 0; }
  fi
  if [[ ! -x "$HERMES_DESKTOP_DIR/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron" ]]; then
    log "Downloading Electron binary via ${ELECTRON_MIRROR}..."
    (cd "$HERMES_DESKTOP_DIR" && node node_modules/electron/install.js && npx electron-builder install-app-deps) >>"$LOGS_DIR/hermes-desktop.log" 2>&1 \
      || { warn "Electron 二进制下载失败，见 ${LOGS_DIR}/hermes-desktop.log；已跳过 hermes-desktop"; return 0; }
  fi
  ensure_content_studio_hermes_profile
  local env_file
  content_studio_resolve_llm_routing
  env_file="$RUNTIME_DIR/hermes-desktop.env"
  write_service_env_file "$env_file" \
    "ELECTRON_MIRROR=${ELECTRON_MIRROR}" \
    "ELECTRON_BUILDER_BINARIES_MIRROR=${ELECTRON_BUILDER_BINARIES_MIRROR}" \
    "HERMES_HOME=${HERMES_GATEWAY_HOME}" \
    "HERMES_PROFILE=${CONTENT_STUDIO_PROFILE_NAME}" \
    "HERMES_API_URL=${GATEWAY_URL}" \
    "HERMES_DASHBOARD_URL=${DASHBOARD_URL}" \
    "OPENAI_BASE_URL=${CONTENT_STUDIO_LLM_HERMES_BASE}" \
    ${CONTENT_STUDIO_LLM_KEY:+ "OPENAI_API_KEY=${CONTENT_STUDIO_LLM_KEY}"} \
    ${HERMES_API_TOKEN:+ "API_SERVER_KEY=${HERMES_API_TOKEN}"}
  log "Starting hermes-desktop (Electron; HERMES_HOME=${HERMES_GATEWAY_HOME}, profile=${CONTENT_STUDIO_PROFILE_NAME}, LLM=${CONTENT_STUDIO_LLM_HERMES_BASE})..."
  warn "hermes-desktop 本地模式需要 ${HERMES_GATEWAY_HOME}/hermes-agent；没有时请选 Use existing → hermes-dev，或 Remote 连 ${GATEWAY_URL}"
  start_background hermes-desktop bash -lc \
    "cd $(printf %q "$HERMES_DESKTOP_DIR") && set -a && source $(printf %q "$env_file") && set +a && npm run dev"
}

ensure_mpt_deps() {
  local py="${DEEPAGENTS_PYTHON:-}"
  local req="${MONEYPRINTER_DIR}/requirements.txt"
  [[ -x "$py" ]] || return 0
  [[ -f "$req" ]] || return 0
  if "$py" -c "import moviepy, streamlit_tour" 2>/dev/null; then
    return 0
  fi
  log "Installing MoneyPrinterTurbo dependencies into monorepo venv (${req})..."
  if command -v uv >/dev/null 2>&1; then
    UV_PYTHON="$py" uv pip install --python "$py" -r "$req"
  else
    "$py" -m pip install -r "$req"
  fi
}

ensure_mpt_listen_port() {
  local cfg="$MONEYPRINTER_DIR/config.toml"
  [[ -f "$cfg" ]] || return 0
  # MoneyPrinterTurbo reads listen_port at the ROOT of config.toml (_cfg.get),
  # NOT under [app]. See app/config/config.py lines 175-176.
  if grep -qE '^listen_port\s*=' "$cfg" 2>/dev/null; then
    if ! grep -qE "^listen_port = ${MPT_API_PORT}\$" "$cfg" 2>/dev/null \
      && ! grep -qE "^listen_port = ${MPT_API_PORT} " "$cfg" 2>/dev/null; then
      warn "Setting MoneyPrinterTurbo config.toml listen_port → ${MPT_API_PORT} (8080 conflicts with OpenInspector)"
      sed -i '' "s/^listen_port = .*/listen_port = ${MPT_API_PORT}/" "$cfg"
    fi
  else
    log "Prepending listen_port=${MPT_API_PORT} to MoneyPrinterTurbo config.toml (root level)"
    printf 'listen_host = "127.0.0.1"\nlisten_port = %s\n\n' "$MPT_API_PORT" | cat - "$cfg" >"${cfg}.tmp" && mv "${cfg}.tmp" "$cfg"
  fi
  if grep -qE '^\[app\]' "$cfg" && awk '/^\[app\]/{f=1} f && /^listen_port/{found=1} END{exit !found}' "$cfg" 2>/dev/null; then
    warn "Removing mistaken listen_port under [app] (MPT only reads root-level listen_port)"
    sed -i '' '/^\[app\]/,/^\[/{ /^listen_port/d; /^listen_host/d; }' "$cfg"
  fi
}

sync_content_studio_secrets() {
  [[ "${SECRETS_SYNC:-1}" == "1" ]] || return 0
  local sync_script="$BUNDLE_ROOT/ops/scripts/sync-content-studio-secrets.sh"
  [[ -x "$sync_script" ]] || return 0
  [[ -f "$HERMES_HOME/secrets.env" ]] || return 0
  export CONTENT_STUDIO_RUNTIME_DIR="$RUNTIME_DIR"
  export CONTENT_STUDIO_LLM_VIA_TDAI_PROXY="${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}"
  export HERMES_GATEWAY_HOME="${HERMES_GATEWAY_HOME:-$HOME/.hermes}"
  if [[ "${SECRETS_SYNC_NOTEBOOK:-0}" == "1" ]]; then
    "$sync_script" --quiet --notebook || warn "secrets sync failed (check $HERMES_HOME/secrets.env)"
  else
    "$sync_script" --quiet || warn "secrets sync failed (check $HERMES_HOME/secrets.env)"
  fi
}

# Resolved LLM endpoints for Hermes vs OpenAI-compatible clients (Notebook / MPT / AionUi).
content_studio_resolve_llm_routing() {
  CONTENT_STUDIO_LLM_HERMES_BASE="${OPENINSPECTOR_URL}/v1"
  CONTENT_STUDIO_LLM_OPENAI_BASE="${OPENINSPECTOR_URL}/v1"
  CONTENT_STUDIO_LLM_KEY="$(read_profile_llm_key)"
  CONTENT_STUDIO_LLM_USING_TDAI=0
  if [[ "${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}" == "1" ]] && read_tdai_user_key; then
    CONTENT_STUDIO_LLM_HERMES_BASE="${TDAI_PROXY_HERMES_BASE}"
    CONTENT_STUDIO_LLM_OPENAI_BASE="${TDAI_PROXY_URL}/codebuddy/${TDAI_SPACE_ID}"
    CONTENT_STUDIO_LLM_KEY="${TDAI_USER_KEY}"
    CONTENT_STUDIO_LLM_USING_TDAI=1
  fi
}

start_openinspector() {
  [[ "$START_OPENINSPECTOR" == "1" ]] || { log "Skipping OpenInspector (START_OPENINSPECTOR=0)"; return 0; }
  local oi_script="$OPENINSPECTOR_DIR/scripts/dev-local.sh"
  [[ -x "$oi_script" ]] || { warn "OpenInspector script missing: ${oi_script}"; return 0; }
  PROXY_PORT="$OPENINSPECTOR_PROXY_PORT" API_PORT="$OPENINSPECTOR_API_PORT" UI_PORT="$OPENINSPECTOR_UI_PORT" \
    "$oi_script" start
}

# TencentDB Agent Memory — proxy 模式（docker：core + hub + proxy）
start_tdai_memory() {
  [[ "${START_TDAI_MEMORY:-0}" == "1" ]] || { log "Skipping TencentDB Memory (START_TDAI_MEMORY=0)"; return 0; }
  local tdai_script="$BUNDLE_ROOT/stack/start-tdai-memory.sh"
  [[ -f "$tdai_script" ]] || { warn "Missing ${tdai_script}"; return 0; }
  chmod +x "$tdai_script" 2>/dev/null || true

  local llm_key llm_model
  llm_key="$(read_upstream_llm_key)" || llm_key=""
  llm_model="$(read_profile_llm_model)"
  llm_model="${llm_model:-gpt-5-6-luna}"
  if [[ -z "${llm_key:-}" ]]; then
    warn "TencentDB Memory needs upstream LLM API key (${HERMES_HOME}/secrets.env LLM_API_KEY) — skip START_TDAI_MEMORY"
    return 0
  fi

  resolve_port_for_start "$MEMORY_CORE_PORT" "TencentDB Memory Core" "http://127.0.0.1:${MEMORY_CORE_PORT}/" || return 0
  resolve_port_for_start "$MEMORY_PROXY_PORT" "TencentDB Memory Proxy" "http://127.0.0.1:${MEMORY_PROXY_PORT}/" || return 0

  log "Starting TencentDB Agent Memory (proxy ${TDAI_PROXY_URL}; upstream ${OPENINSPECTOR_URL}/v1)..."
  if ! TDAI_MEMORY_DIR="$TDAI_MEMORY_DIR" RUNTIME_DIR="$RUNTIME_DIR" LOGS_DIR="$LOGS_DIR" \
    OPENINSPECTOR_URL="$OPENINSPECTOR_URL" \
    MEMORY_CORE_PORT="$MEMORY_CORE_PORT" MEMORY_PANEL_PORT="$MEMORY_PANEL_PORT" \
    MEMORY_KNOWLEDGE_PORT="$MEMORY_KNOWLEDGE_PORT" MEMORY_PROXY_PORT="$MEMORY_PROXY_PORT" \
    TDAI_LLM_BASE_URL="${TDAI_LLM_BASE_URL:-${OPENINSPECTOR_URL}/v1}" \
    TDAI_LLM_API_KEY="$llm_key" TDAI_LLM_MODEL="$llm_model" TDAI_SPACE_ID="$TDAI_SPACE_ID" \
    bash "$tdai_script"; then
    warn "TencentDB Memory failed — see ${LOGS_DIR}/tdai-memory.log"
    return 0
  fi
}

read_tdai_user_key() {
  local cred="$RUNTIME_DIR/tdai-memory.env"
  [[ -f "$cred" ]] || return 1
  # shellcheck disable=SC1090
  source "$cred"
  [[ -n "${TDAI_USER_KEY:-}" ]] || return 1
}

# ── Preflight ────────────────────────────────────────────────────────────
[[ -d "$HERMES_AGENT_DIR" ]] || { err "Missing hermes-agent: ${HERMES_AGENT_DIR}"; exit 1; }
[[ -d "$HERMES_WORKSPACE_DIR" ]] || { err "Missing hermes-workspace: ${HERMES_WORKSPACE_DIR}"; exit 1; }
[[ -d "$OPEN_NOTEBOOK_DIR" ]] || { err "Missing open-notebook: ${OPEN_NOTEBOOK_DIR}"; exit 1; }
[[ -d "$MONEYPRINTER_DIR" ]] || { err "Missing MoneyPrinterTurbo: ${MONEYPRINTER_DIR}"; exit 1; }

if ! "$HERMES_CLI" --version >/dev/null 2>&1; then
  err "hermes CLI check failed. Run: cd ${HERMES_AGENT_DIR} && uv pip install -e '.[all]'"
  exit 1
fi

command -v curl >/dev/null 2>&1 || { err "curl is required"; exit 1; }
command -v pnpm >/dev/null 2>&1 || { err "pnpm is required for Workspace"; exit 1; }
command -v uv >/dev/null 2>&1 || { err "uv is required for Open Notebook / MoneyPrinterTurbo"; exit 1; }

ensure_ali_tts_proxy() {
  local tts_cfg="${CONTENT_STUDIO_TTS_CONFIG:-$HERMES_HOME/config/tts-providers.yaml}"
  local verify_script="$BUNDLE_ROOT/ops/scripts/verify-ali-tts-proxy.sh"
  if [[ ! -s "$tts_cfg" ]]; then
    warn "Ali TTS config missing: ${tts_cfg} — Open Notebook podcast TTS proxy skipped"
    return 0
  fi

  # Health alone is insufficient: old proxy builds pass /health but fail voice=ash (OpenAI id).
  if [[ -x "$verify_script" ]] && ALI_TTS_PROXY_URL="$ALI_TTS_PROXY_URL" "$verify_script" >/dev/null 2>&1; then
    log "Aliyun TTS proxy verified: ${ALI_TTS_PROXY_URL}"
    return 0
  fi

  local pid_file="$RUNTIME_DIR/ali-tts-proxy.pid"
  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
      warn "Restarting Aliyun TTS proxy (failed ash voice verification)"
      kill "$old_pid" 2>/dev/null || true
      wait "$old_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi

  if port_in_use "$ALI_TTS_PROXY_PORT"; then
    warn "Freeing port ${ALI_TTS_PROXY_PORT} for Aliyun TTS proxy restart"
    if command -v lsof >/dev/null 2>&1; then
      local stale_pid
      for stale_pid in $(lsof -t -iTCP:"$ALI_TTS_PROXY_PORT" -sTCP:LISTEN 2>/dev/null); do
        kill "$stale_pid" 2>/dev/null || true
      done
      sleep 1
    fi
  fi

  if ! port_in_use "$ALI_TTS_PROXY_PORT"; then
    log "Starting Aliyun TTS proxy (${ALI_TTS_PROXY_URL})..."
    start_background ali-tts-proxy \
      env HERMES_HOME="$HERMES_HOME" \
          CONTENT_STUDIO_TTS_CONFIG="$tts_cfg" \
          ALI_TTS_PROVIDER="${ALI_TTS_PROVIDER:-ALI_DEF}" \
          ALI_TTS_PROXY_PORT="$ALI_TTS_PROXY_PORT" \
          "$DEEPAGENTS_PYTHON" "$BUNDLE_ROOT/ops/scripts/ali-tts-proxy.py"
    for _ in $(seq 1 20); do
      if [[ -x "$verify_script" ]] && ALI_TTS_PROXY_URL="$ALI_TTS_PROXY_URL" "$verify_script" >/dev/null 2>&1; then
        log "Aliyun TTS proxy ready (verified ash→Ali voice map): ${ALI_TTS_PROXY_URL}"
        return 0
      fi
      sleep 1
    done
    err "Aliyun TTS proxy failed verification — run: $verify_script"
    return 1
  fi

  err "Could not start Aliyun TTS proxy on port ${ALI_TTS_PROXY_PORT}"
  return 1
}

ensure_notebook_queue() {
  local on_dir="${OPEN_NOTEBOOK_DIR}"
  local env_file="$on_dir/.env"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi
  log "Maintaining Open Notebook job queue (drop stale embed jobs)..."
  # shellcheck disable=SC1090
  set -a
  source "$env_file" 2>/dev/null || true
  set +a
  local queue_py="${DEEPAGENTS_PYTHON}"
  local on_venv="${OPEN_NOTEBOOK_DIR}/.venv/bin/python"
  if [[ -x "$on_venv" ]] && "$on_venv" -c "import surrealdb" 2>/dev/null; then
    queue_py="$on_venv"
  elif ! "$DEEPAGENTS_PYTHON" -c "import surrealdb" 2>/dev/null; then
    log "Installing surrealdb into monorepo venv (notebook queue maintenance)..."
    if command -v uv >/dev/null 2>&1; then
      UV_PYTHON="$DEEPAGENTS_PYTHON" uv pip install --python "$DEEPAGENTS_PYTHON" surrealdb || true
    else
      "$DEEPAGENTS_PYTHON" -m pip install surrealdb || true
    fi
  fi
  "$queue_py" "$BUNDLE_ROOT/ops/scripts/notebook-queue-maintain.py" || true
}

ensure_volcano_tts_proxy() {
  if [[ -z "${VOLCENGINE_APP_ID:-}" || -z "${VOLCENGINE_TOKEN:-}" ]]; then
    if [[ -f "$HERMES_HOME/.env" ]]; then
      # shellcheck disable=SC1090
      set -a
      source "$HERMES_HOME/.env" 2>/dev/null || true
      set +a
    fi
  fi

  if [[ -z "${VOLCENGINE_APP_ID:-}" || -z "${VOLCENGINE_TOKEN:-}" ]]; then
    warn "VOLCENGINE_APP_ID / VOLCENGINE_TOKEN not set — volcano TTS proxy skipped (optional)"
    return 0
  fi

  if curl -fsS "${VOLCENGINE_TTS_PROXY_URL}/health" >/dev/null 2>&1; then
    log "Volcengine TTS proxy already up: ${VOLCENGINE_TTS_PROXY_URL}"
    return 0
  fi

  if ! port_in_use "$VOLCENGINE_TTS_PROXY_PORT"; then
    log "Starting Volcengine TTS proxy (${VOLCENGINE_TTS_PROXY_URL})..."
    start_background volcano-tts-proxy \
      env VOLCENGINE_APP_ID="$VOLCENGINE_APP_ID" \
          VOLCENGINE_TOKEN="$VOLCENGINE_TOKEN" \
          VOLCENGINE_CLUSTER="${VOLCENGINE_CLUSTER:-volcano_tts}" \
          VOLCENGINE_VOICE_TYPE="${VOLCENGINE_VOICE_TYPE:-zh_female_wanwanxiaohe_moon_bigtts}" \
          VOLCENGINE_TTS_PROXY_PORT="$VOLCENGINE_TTS_PROXY_PORT" \
          "$DEEPAGENTS_PYTHON" "$BUNDLE_ROOT/ops/scripts/volcano-tts-proxy.py"
    for _ in $(seq 1 20); do
      if curl -fsS "${VOLCENGINE_TTS_PROXY_URL}/health" >/dev/null 2>&1; then
        log "Volcengine TTS proxy ready: ${VOLCENGINE_TTS_PROXY_URL}"
        return 0
      fi
      sleep 1
    done
    warn "Volcengine TTS proxy did not become ready within 20s"
    return 0
  fi

  warn "Port ${VOLCENGINE_TTS_PROXY_PORT} in use but health check failed for volcano TTS proxy"
}

ensure_ollama() {
  if curl -fsS "${OLLAMA_API_BASE}/api/tags" >/dev/null 2>&1; then
    log "Ollama already up: ${OLLAMA_API_BASE}"
    return 0
  fi

  if [[ "$START_OLLAMA" == "0" ]]; then
    warn "Ollama not running on ${OLLAMA_API_BASE} and START_OLLAMA=0"
    warn "Open Notebook embedding search requires Ollama (nomic-embed-text)."
    return 0
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    warn "ollama CLI not found — install: brew install ollama"
    warn "Embedding model nomic-embed-text will not work until Ollama is running."
    return 0
  fi

  log "Starting Ollama (${OLLAMA_API_BASE})..."
  start_background ollama ollama serve
  for _ in $(seq 1 30); do
    if curl -fsS "${OLLAMA_API_BASE}/api/tags" >/dev/null 2>&1; then
      log "Ollama ready: ${OLLAMA_API_BASE}"
      if ! curl -fsS "${OLLAMA_API_BASE}/api/tags" | grep -q 'nomic-embed-text'; then
        log "Pulling embedding model nomic-embed-text (first run may take a minute)..."
        ollama pull nomic-embed-text
      fi
      return 0
    fi
    sleep 1
  done
  warn "Ollama did not become ready within 30s — embedding search may fail until it starts."
}

ensure_surrealdb() {
  if port_in_use "$SURREAL_PORT"; then
    log "SurrealDB already listening on :${SURREAL_PORT}"
    return 0
  fi

  if [[ "$START_SURREALDB" == "0" ]]; then
    err "SurrealDB not running on :${SURREAL_PORT} and START_SURREALDB=0"
    err "Start manually: bash ${SURREALDB_NATIVE_SCRIPT} start"
    exit 1
  fi

  local mode="$START_SURREALDB"
  if [[ "$mode" == "auto" ]]; then
    # Open Notebook migrations target SurrealDB v2 (docker tag surrealdb/surrealdb:v2).
    # Homebrew surreal 3.x rejects `DEFINE FIELD ... TYPE option FLEXIBLE`.
    local surreal_ver=""
    if command -v surreal >/dev/null 2>&1; then
      surreal_ver="$(surreal version 2>/dev/null | head -1 || true)"
    fi
    if [[ "$surreal_ver" == 2.* ]]; then
      mode="native"
    elif command -v docker >/dev/null 2>&1; then
      if [[ -n "$surreal_ver" ]]; then
        warn "Local surreal is not v2 (${surreal_ver}); starting docker surrealdb/surrealdb:v2"
      fi
      mode="docker"
    elif command -v surreal >/dev/null 2>&1; then
      warn "Docker not available; trying native surreal anyway (${surreal_ver})"
      mode="native"
    else
      err "SurrealDB not on :${SURREAL_PORT}. Install docker or surreal v2."
      err "Or set START_SURREALDB=0 and start SurrealDB yourself."
      exit 1
    fi
  fi

  if [[ "$mode" == "native" ]]; then
    if [[ ! -x "$SURREALDB_NATIVE_SCRIPT" && -x "$BUNDLE_ROOT/ops/scripts/surrealdb-native.sh" ]]; then
      SURREALDB_NATIVE_SCRIPT="$BUNDLE_ROOT/ops/scripts/surrealdb-native.sh"
    fi
    if [[ ! -x "$SURREALDB_NATIVE_SCRIPT" ]]; then
      err "Missing ${SURREALDB_NATIVE_SCRIPT}"
      exit 1
    fi
    log "Starting SurrealDB (native CLI)..."
    OPEN_NOTEBOOK_DIR="$OPEN_NOTEBOOK_DIR" SURREAL_PORT="$SURREAL_PORT" \
      bash "$SURREALDB_NATIVE_SCRIPT" start
    return 0
  fi

  if [[ "$mode" == "docker" ]] || [[ "$mode" == "1" ]]; then
    command -v docker >/dev/null 2>&1 || { err "docker not found for START_SURREALDB=${START_SURREALDB}"; exit 1; }
    log "Starting SurrealDB (docker compose)..."
    (cd "$OPEN_NOTEBOOK_DIR" && docker compose up -d surrealdb)
    for _ in $(seq 1 30); do
      port_in_use "$SURREAL_PORT" && break
      sleep 1
    done
    port_in_use "$SURREAL_PORT" || { err "SurrealDB did not open port ${SURREAL_PORT}"; exit 1; }
    log "SurrealDB ready on :${SURREAL_PORT}"
    return 0
  fi

  err "Unknown START_SURREALDB=${START_SURREALDB} (use auto|native|docker|0)"
  exit 1
}

log "Checking ports..."
ensure_mpt_listen_port
start_openinspector
# Load profile secrets (VOLCENGINE_*, etc.) before optional services.
if [[ -f "$HERMES_HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$HERMES_HOME/.env" 2>/dev/null || true
  set +a
fi
start_tdai_memory
sync_content_studio_secrets
install_tdai_hermes_integration() {
  [[ "${CONTENT_STUDIO_TDAI_INSTALL_PLUGIN:-1}" == "1" ]] || return 0
  [[ "${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}" == "1" ]] || return 0
  local plugin_script="$BUNDLE_ROOT/ops/scripts/install-tdai-proxy-headers-plugin.sh"
  [[ -x "$plugin_script" ]] || chmod +x "$plugin_script" 2>/dev/null || true
  if [[ -f "$plugin_script" ]]; then
    HERMES_HOME="$HERMES_HOME" HERMES_GATEWAY_HOME="${HERMES_GATEWAY_HOME:-$HOME/.hermes}" \
      DEEPAGENTS_PYTHON="${DEEPAGENTS_PYTHON:-}" \
      "$plugin_script" || warn "tdai-proxy-headers plugin install failed"
  fi
}
install_tdai_hermes_integration
if [[ "${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}" == "1" ]] && ! read_tdai_user_key; then
  warn "CONTENT_STUDIO_LLM_VIA_TDAI_PROXY=1 but TencentDB Memory 未就绪 — LLM 仍走 OpenInspector（见 ${LOGS_DIR}/tdai-memory.log）"
fi
ensure_ali_tts_proxy
# Volcano proxy is optional (only when VOLCENGINE_* env is set).
ensure_volcano_tts_proxy
ensure_ollama
ensure_surrealdb
resolve_port_for_start "$OPENINSPECTOR_API_PORT" "OpenInspector Dashboard API" "${OPENINSPECTOR_API_URL}/api/metrics" || exit 1
resolve_port_for_start "$NOTEBOOK_API_PORT" "Open Notebook API" "${NOTEBOOK_API_URL}/docs" || exit 1
if [[ "$START_NOTEBOOK_FRONTEND" == "1" ]]; then
  resolve_port_for_start "$NOTEBOOK_FRONTEND_PORT" "Open Notebook Web UI" "${NOTEBOOK_FRONTEND_URL}" || exit 1
fi
resolve_port_for_start "$MPT_API_PORT" "MoneyPrinterTurbo API" "${MPT_API_URL}/docs" || exit 1
resolve_port_for_start "$MPT_WEBUI_PORT" "MoneyPrinterTurbo WebUI" "${MPT_WEBUI_URL}" || exit 1
resolve_port_for_start "$GATEWAY_PORT" "Hermes Gateway" "${GATEWAY_URL}/health" || exit 1
resolve_port_for_start "$DASHBOARD_PORT" "Hermes Dashboard" "${DASHBOARD_URL}/api/status" || exit 1
if [[ "$START_HERMES_WEBUI" == "1" && -d "$HERMES_WEBUI_DIR" ]]; then
  resolve_port_for_start "$HERMES_WEBUI_PORT" "hermes-webui" "${HERMES_WEBUI_URL}/health" || exit 1
fi
if [[ "$START_HERMES_STUDIO" == "1" && -d "$HERMES_STUDIO_DIR" ]]; then
  resolve_port_for_start "$HERMES_STUDIO_BACKEND_PORT" "hermes-studio API" "http://127.0.0.1:${HERMES_STUDIO_BACKEND_PORT}" || exit 1
  resolve_port_for_start "$HERMES_STUDIO_PORT" "hermes-studio (Vite)" "${HERMES_STUDIO_URL}" || exit 1
fi
if [[ "$START_AIONUI" == "1" && -d "$AIONUI_DIR" ]]; then
  resolve_port_for_start "$AIONUI_PORT" "AionUi" "${AIONUI_URL}" || exit 1
fi
if port_in_use "$WORKSPACE_PORT"; then
  warn "Workspace port ${WORKSPACE_PORT} is already in use (checked again before foreground start):"
  print_port_occupiers "$WORKSPACE_PORT" "Hermes Workspace" || true
fi

# ── 2. Open Notebook API ─────────────────────────────────────────────────
if ! port_in_use "$NOTEBOOK_API_PORT" || ! curl -fsS "${NOTEBOOK_API_URL}/docs" >/dev/null 2>&1; then
  start_background notebook-api \
    env API_RELOAD="$API_RELOAD" API_PORT="$NOTEBOOK_API_PORT" API_HOST=127.0.0.1 UV_PYTHON="$DEEPAGENTS_PYTHON" \
    bash -lc "cd '$OPEN_NOTEBOOK_DIR' && uv run --env-file .env run_api.py"
  wait_http "${NOTEBOOK_API_URL}/docs" "Open Notebook API" 90
else
  log "Open Notebook API already up: ${NOTEBOOK_API_URL}"
fi
if [[ -f "$HERMES_HOME/secrets.env" && "${SECRETS_SYNC_NOTEBOOK:-1}" == "1" ]]; then
  SECRETS_SYNC_NOTEBOOK=1 sync_content_studio_secrets || true
fi

if [[ "$START_NOTEBOOK_WORKER" == "1" ]]; then
  ensure_notebook_queue
  fix_script="$BUNDLE_ROOT/ops/scripts/fix-notebook-speaker-voices.py"
  zh_script="$BUNDLE_ROOT/ops/scripts/fix-notebook-podcast-zh.py"
  if curl -fsS "${NOTEBOOK_API_URL}/api/speaker-profiles" >/dev/null 2>&1; then
    [[ -f "$fix_script" ]] && "$DEEPAGENTS_PYTHON" "$fix_script" --api-url "$NOTEBOOK_API_URL" || true
    [[ -f "$zh_script" ]] && "$DEEPAGENTS_PYTHON" "$zh_script" --api-url "$NOTEBOOK_API_URL" || true
  fi
  start_background notebook-worker \
    bash -lc "cd '$OPEN_NOTEBOOK_DIR' && \
      PYTHONPATH='$ROOT_DIR/scripts':\"\${PYTHONPATH:-}\" \
      CONTENT_STUDIO_PODCAST_SHORT='${CONTENT_STUDIO_PODCAST_SHORT:-1}' \
      TTS_BATCH_SIZE='${TTS_BATCH_SIZE:-1}' \
      UV_PYTHON='$DEEPAGENTS_PYTHON' \
      uv run --env-file .env surreal-commands-worker start \
        --import-modules commands,content_studio_podcast_bootstrap"
  log "Open Notebook worker started (TTS_BATCH_SIZE=${TTS_BATCH_SIZE:-1}, CONTENT_STUDIO_PODCAST_SHORT=${CONTENT_STUDIO_PODCAST_SHORT:-1})"
fi

if [[ "$START_NOTEBOOK_FRONTEND" == "1" ]]; then
  if ! port_in_use "$NOTEBOOK_FRONTEND_PORT" || ! curl -fsS "${NOTEBOOK_FRONTEND_URL}" >/dev/null 2>&1; then
    ensure_notebook_frontend_deps
    start_background notebook-frontend \
      bash -lc "cd '$OPEN_NOTEBOOK_DIR/frontend' && INTERNAL_API_URL='${NOTEBOOK_API_URL}' npm run dev -- -p ${NOTEBOOK_FRONTEND_PORT} -H 127.0.0.1"
    wait_http "${NOTEBOOK_FRONTEND_URL}" "Open Notebook Web UI" 120
  else
    log "Open Notebook Web UI already up: ${NOTEBOOK_FRONTEND_URL}"
  fi
fi

# ── 3. MoneyPrinterTurbo ─────────────────────────────────────────────────
ensure_mpt_deps
if ! port_in_use "$MPT_API_PORT" || ! curl -fsS "${MPT_API_URL}/docs" >/dev/null 2>&1; then
  start_background mpt-api \
    bash -lc "cd '$MONEYPRINTER_DIR' && export PYTHONPATH='$MONEYPRINTER_DIR':\"\${PYTHONPATH:-}\" && '$DEEPAGENTS_PYTHON' main.py"
  wait_http "${MPT_API_URL}/docs" "MoneyPrinterTurbo API" 150
else
  log "MoneyPrinterTurbo API already up: ${MPT_API_URL}"
fi

if ! port_in_use "$MPT_WEBUI_PORT" || ! curl -fsS "${MPT_WEBUI_URL}" >/dev/null 2>&1; then
  start_background mpt-webui \
    bash -lc "cd '$MONEYPRINTER_DIR' && export DEEPAGENTS_PYTHON='$DEEPAGENTS_PYTHON' MPT_WEBUI_HOST=127.0.0.1 MPT_WEBUI_PORT=${MPT_WEBUI_PORT} && sh webui.sh"
  wait_http "${MPT_WEBUI_URL}" "MoneyPrinterTurbo WebUI" 90
else
  log "MoneyPrinterTurbo WebUI already up: ${MPT_WEBUI_URL}"
fi

# ── 4. Hermes Gateway + Dashboard ───────────────────────────────────────
ensure_hermes_agent_deps
ensure_workspace_env
ensure_content_studio_hermes_profile

content_studio_resolve_llm_routing
# Memory Proxy mode: plugin + TDAI_* env load only at Gateway process start — recycle on every stack start.
if [[ "${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}" == "1" ]] && port_in_use "$GATEWAY_PORT"; then
  log "Recycling Hermes Gateway (tdai-proxy-headers / TDAI env must load at process start)..."
  pkill -f "hermes gateway run" 2>/dev/null || true
  sleep 2
fi
if ! port_in_use "$GATEWAY_PORT" || ! curl -fsS "${GATEWAY_URL}/health" >/dev/null 2>&1; then
  # Local OpenInspector proxy + reasoning models (e.g. gpt-5-6-luna) need long TTFB; avoid 40s client aborts.
  start_background gateway bash -lc "
    set -a
    # shellcheck disable=SC1090
    source '${HERMES_GATEWAY_HOME}/.env' 2>/dev/null || true
    set +a
    export HERMES_HOME='${HERMES_GATEWAY_HOME}'
    export HERMES_API_CALL_STALE_TIMEOUT='${HERMES_API_CALL_STALE_TIMEOUT:-600}'
    export HERMES_LOCAL_STREAM_STALE_TIMEOUT='${HERMES_LOCAL_STREAM_STALE_TIMEOUT:-900}'
    export OPENAI_BASE_URL='${CONTENT_STUDIO_LLM_HERMES_BASE}'
    export TDAI_PROXY_URL='${TDAI_PROXY_URL:-http://127.0.0.1:8096}'
    export TDAI_PROXY_HERMES_BASE='${CONTENT_STUDIO_LLM_HERMES_BASE}'
    tdai_ids='${HERMES_HOME}/tdai-hermes-ids.env'
    if [[ -f \"\$tdai_ids\" ]]; then
      for kv in TDAI_TEAM_ID TDAI_AGENT_ID TDAI_TASK_ID; do
        v=\$(grep -E \"^\${kv}=\" \"\$tdai_ids\" | head -1 | cut -d= -f2- | tr -d ' \"'\\'')
        [[ -n \"\$v\" ]] && export \"\$kv=\$v\"
      done
    fi
    ${CONTENT_STUDIO_LLM_KEY:+export OPENAI_API_KEY='${CONTENT_STUDIO_LLM_KEY}'}
    ${CONTENT_STUDIO_LLM_KEY:+export CUSTOM_API_KEY='${CONTENT_STUDIO_LLM_KEY}'}
    exec '${HERMES_CLI}' -p default gateway run --replace
  "
  wait_http "${GATEWAY_URL}/health" "Hermes Gateway" 60
else
  if [[ "${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}" == "1" ]]; then
    warn "Hermes Gateway still up after recycle attempt — memory headers may be stale; run stop-content-studio-stack.sh then start again"
  else
    log "Hermes Gateway already up: ${GATEWAY_URL}"
  fi
fi

if ! port_in_use "$DASHBOARD_PORT" || ! curl -fsS "${DASHBOARD_URL}/api/status" >/dev/null 2>&1; then
  ensure_dashboard_web_ui
  start_background dashboard "$HERMES_CLI" dashboard --skip-build --port "$DASHBOARD_PORT" --no-open
  wait_http "${DASHBOARD_URL}/api/status" "Hermes Dashboard" "$DASHBOARD_READY_TIMEOUT"
else
  log "Hermes Dashboard already up: ${DASHBOARD_URL}"
fi

# WebUI / Studio 已停用（需要时设置 START_HERMES_WEBUI=1 / START_HERMES_STUDIO=1 并取消下面注释）
# start_hermes_webui
# start_hermes_studio
start_aionui
start_hermes_desktop

# ── Summary ─────────────────────────────────────────────────────────────
content_studio_resolve_llm_routing
cat <<EOF

══════════════════════════════════════════════════════════════
  Content Studio Stack — 服务地址
══════════════════════════════════════════════════════════════

  【OpenInspector · 上游 + 追踪】  ${OPENINSPECTOR_UI_URL}
    上游出口（TencentDB Proxy 再转发到这里）: ${OPENINSPECTOR_URL}/v1
    API logs: ${OPENINSPECTOR_API_URL}/api/logs

  【TencentDB Agent Memory】   Panel ${TDAI_PANEL_URL}  |  Proxy ${TDAI_PROXY_URL}
    Hermes LLM base: ${CONTENT_STUDIO_LLM_HERMES_BASE}  (via_tdai=${CONTENT_STUDIO_LLM_USING_TDAI})
    OpenAI-compat (Notebook/MPT): ${CONTENT_STUDIO_LLM_OPENAI_BASE}
    开关: CONTENT_STUDIO_LLM_VIA_TDAI_PROXY=${CONTENT_STUDIO_LLM_VIA_TDAI_PROXY:-0}
    凭据: ${RUNTIME_DIR}/tdai-memory.env  |  日志: ${LOGS_DIR}/tdai-memory.log
    Memory headers: ${HERMES_HOME}/tdai-hermes-ids.env → sync-content-studio-secrets（见 bundle/profile/tdai-hermes-ids.env.example）

  【Hermes · 官方 Dashboard】  ${DASHBOARD_URL}
    Chat: ${DASHBOARD_URL}/chat

  【Hermes · Workspace】       ${WORKSPACE_URL}

  【AionUi · WebUI】           ${AIONUI_URL}
    LLM: ${CONTENT_STUDIO_LLM_HERMES_BASE}；Hermes profile: ${CONTENT_STUDIO_PROFILE_NAME}

  【hermes-desktop · Electron】 桌面窗口（日志: ${LOGS_DIR}/hermes-desktop.log）
    HERMES_HOME=${HERMES_GATEWAY_HOME}，active_profile=${CONTENT_STUDIO_PROFILE_NAME}

  # 【Hermes · WebUI】           ${HERMES_WEBUI_URL}    （已停用）
  # 【Hermes · Studio (Ekko UI)】 ${HERMES_STUDIO_URL}  （已停用）

  【Hermes · Gateway API】     ${GATEWAY_URL}
    Health: ${GATEWAY_URL}/health

  【Open Notebook · Web UI】   ${NOTEBOOK_FRONTEND_URL}
    （Notebook 管理/使用界面）

  【Open Notebook · API】        ${NOTEBOOK_API_URL}
    Docs:   ${NOTEBOOK_API_URL}/docs
    SurrealDB: localhost:${SURREAL_PORT}

  【MoneyPrinterTurbo API】    ${MPT_API_URL}
    Docs:   ${MPT_API_URL}/docs

  【MoneyPrinterTurbo WebUI】  ${MPT_WEBUI_URL}

  Profile:  ${HERMES_HOME}
  停止全部: ./stop-content-studio-stack.sh
  后台日志: ${LOGS_DIR}/   (例: tail -f ${LOGS_DIR}/notebook-worker.log)
  终端日志: 设置 STACK_LOG_TO_TERMINAL=1 可恢复旧行为（不推荐）

══════════════════════════════════════════════════════════════

EOF

# ── 5. Workspace ─────────────────────────────────────────────────────────
if port_in_use "$WORKSPACE_PORT"; then
  if curl -fsS "${WORKSPACE_URL}" >/dev/null 2>&1; then
    warn "Hermes Workspace already up: ${WORKSPACE_URL}"
  else
    print_port_occupiers "$WORKSPACE_PORT" "Hermes Workspace"
    err "Workspace port ${WORKSPACE_PORT} is busy."
    err "Run: ./stop-content-studio-stack.sh   then start again."
    err "Or use another port: WORKSPACE_PORT=3002 $0"
    trap - EXIT INT TERM
    exit 1
  fi
else
  ensure_workspace_deps
  log "Starting Hermes Workspace on ${WORKSPACE_URL} ..."
  export HERMES_API_URL="$GATEWAY_URL"
  export HERMES_DASHBOARD_URL="$DASHBOARD_URL"
  export HERMES_AGENT_PATH="$HERMES_AGENT_DIR"
  export HERMES_WORKSPACE_GATEWAY_PROFILE="$CONTENT_STUDIO_PROFILE_NAME"
  export PORT="$WORKSPACE_PORT"
  export STREAM_ACCEPTED_TIMEOUT_MS="${WORKSPACE_STREAM_ACCEPTED_TIMEOUT_MS:-300000}"
  if [[ -z "${HERMES_API_TOKEN:-}" ]]; then
    HERMES_API_TOKEN="$(read_gateway_api_server_key)"
    export HERMES_API_TOKEN
  fi

  if [[ "$WORKSPACE_BACKGROUND" == "1" ]]; then
    write_service_env_file "$RUNTIME_DIR/workspace.env" \
      "HERMES_API_URL=${GATEWAY_URL}" \
      "HERMES_DASHBOARD_URL=${DASHBOARD_URL}" \
      "HERMES_AGENT_PATH=${HERMES_AGENT_DIR}" \
      "HERMES_WORKSPACE_GATEWAY_PROFILE=${CONTENT_STUDIO_PROFILE_NAME}" \
      "PORT=${WORKSPACE_PORT}" \
      "STREAM_ACCEPTED_TIMEOUT_MS=${STREAM_ACCEPTED_TIMEOUT_MS}" \
      ${HERMES_API_TOKEN:+ "HERMES_API_TOKEN=${HERMES_API_TOKEN}"}
    start_background workspace bash -lc \
      "cd $(printf %q "$HERMES_WORKSPACE_DIR") && set -a && source $(printf %q "$RUNTIME_DIR/workspace.env") && set +a && pnpm dev"
    wait_http "${WORKSPACE_URL}" "Hermes Workspace" 120
    if [[ "${CONTENT_STUDIO_VERIFY_CONNECTIVITY:-1}" == "1" ]]; then
      verify_script="${BUNDLE_ROOT}/ops/scripts/verify-content-studio-connectivity.sh"
      if [[ -x "$verify_script" ]]; then
        log "Running connectivity smoke test..."
        CONTENT_STUDIO_RUNTIME_DIR="$RUNTIME_DIR" \
          GATEWAY_URL="$GATEWAY_URL" TDAI_PROXY_URL="$TDAI_PROXY_URL" WORKSPACE_URL="$WORKSPACE_URL" \
          CONTENT_STUDIO_PROFILE_NAME="$CONTENT_STUDIO_PROFILE_NAME" HERMES_GATEWAY_HOME="$HERMES_GATEWAY_HOME" \
          "$verify_script" || warn "Connectivity smoke test failed (services may still be starting — re-run verify script)"
      fi
    fi
    trap - EXIT INT TERM
    log "All services started in background. Stop with: ./stop-content-studio-stack.sh"
  else
    cd "$HERMES_WORKSPACE_DIR"
    pnpm dev
  fi
fi
