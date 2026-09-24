#!/usr/bin/env bash
# Start Content Studio full stack:
#   Hermes (Gateway + Dashboard + Workspace)
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
BUNDLE_ROOT="$(cd "$STACK_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$BUNDLE_ROOT/env.sh"
ROOT_DIR="$HERMES_DEV"
# shellcheck source=/dev/null
source "$STACK_DIR/ports.env"
# shellcheck source=/dev/null
source "$BUNDLE_ROOT/lib/deepagents-python.env.sh"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_DEV/hermes-agent}"
HERMES_WORKSPACE_DIR="${HERMES_WORKSPACE_DIR:-$HERMES_DEV/hermes-workspace}"
RUNTIME_DIR="$ROOT_DIR/.runtime/content-studio-stack"
LOGS_DIR="$RUNTIME_DIR/logs"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
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

mkdir -p "$RUNTIME_DIR" "$LOGS_DIR"

log() { printf '\033[1;36m[content-studio-stack]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[content-studio-stack]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[content-studio-stack]\033[0m %s\n' "$*" >&2; }

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
  echo $! >"$pid_file"
}

cleanup_ours() {
  local name pid pid_file
  for name in workspace dashboard gateway mpt-webui mpt-api notebook-frontend notebook-api notebook-worker ollama ali-tts-proxy volcano-tts-proxy; do
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

ensure_hermes_agent_deps() {
  local py missing=()
  py="$(hermes_python)"
  [[ -n "$py" ]] || return 0
  "$py" -c "import fastapi, uvicorn" >/dev/null 2>&1 || missing+=("web")
  if [[ "$HERMES_DASHBOARD_TUI" == "1" ]]; then
    "$py" -c "import ptyprocess" >/dev/null 2>&1 || missing+=("pty")
  fi
  [[ ${#missing[@]} -eq 0 ]] && return 0
  log "Installing hermes-agent [all] (dashboard dependencies)..."
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
  (cd "$web_dir" && npm install && npm run build)
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
  [[ -f "$ws_env" ]] || touch "$ws_env"
  grep -q '^HERMES_API_URL=' "$ws_env" 2>/dev/null || echo "HERMES_API_URL=${GATEWAY_URL}" >>"$ws_env"
  grep -q '^HERMES_DASHBOARD_URL=' "$ws_env" 2>/dev/null || echo "HERMES_DASHBOARD_URL=${DASHBOARD_URL}" >>"$ws_env"
  grep -q '^HERMES_AGENT_PATH=' "$ws_env" 2>/dev/null || echo "HERMES_AGENT_PATH=${HERMES_AGENT_DIR}" >>"$ws_env"
  grep -q '^WORKSPACE_AUTO_APPROVE=' "$ws_env" 2>/dev/null || echo "WORKSPACE_AUTO_APPROVE=1" >>"$ws_env"
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

ensure_mpt_deps() {
  local py="${DEEPAGENTS_PYTHON:-}"
  [[ -x "$py" ]] || return 0
  if "$py" -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('streamlit_tour') else 1)" 2>/dev/null; then
    return 0
  fi
  log "Installing MoneyPrinterTurbo WebUI dependency (streamlit-tour)..."
  if command -v uv >/dev/null 2>&1; then
    (cd "$MONEYPRINTER_DIR" && UV_PYTHON="$py" uv sync --frozen) \
      || "$py" -m pip install 'streamlit-tour==1.1.0'
  else
    "$py" -m pip install 'streamlit-tour==1.1.0'
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
  if [[ "${SECRETS_SYNC_NOTEBOOK:-0}" == "1" ]]; then
    "$sync_script" --quiet --notebook || warn "secrets sync failed (check $HERMES_HOME/secrets.env)"
  else
    "$sync_script" --quiet || warn "secrets sync failed (check $HERMES_HOME/secrets.env)"
  fi
}

start_openinspector() {
  [[ "$START_OPENINSPECTOR" == "1" ]] || { log "Skipping OpenInspector (START_OPENINSPECTOR=0)"; return 0; }
  local oi_script="$OPENINSPECTOR_DIR/scripts/dev-local.sh"
  [[ -x "$oi_script" ]] || { warn "OpenInspector script missing: ${oi_script}"; return 0; }
  PROXY_PORT="$OPENINSPECTOR_PROXY_PORT" API_PORT="$OPENINSPECTOR_API_PORT" UI_PORT="$OPENINSPECTOR_UI_PORT" \
    "$oi_script" start
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
  local on_dir="${OPEN_NOTEBOOK_DIR:-/Users/gqli/work/deepagents/open-notebook}"
  local env_file="$on_dir/.env"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi
  log "Maintaining Open Notebook job queue (drop stale embed jobs)..."
  # shellcheck disable=SC1090
  set -a
  source "$env_file" 2>/dev/null || true
  set +a
  "$DEEPAGENTS_PYTHON" "$BUNDLE_ROOT/ops/scripts/notebook-queue-maintain.py" || true
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
    if command -v surreal >/dev/null 2>&1; then
      mode="native"
    elif command -v docker >/dev/null 2>&1; then
      mode="docker"
    else
      err "SurrealDB not on :${SURREAL_PORT}. Install: brew install surrealdb/surreal/surreal"
      err "Or set START_SURREALDB=0 and start SurrealDB yourself."
      exit 1
    fi
  fi

  if [[ "$mode" == "native" ]]; then
    if [[ ! -x "$SURREALDB_NATIVE_SCRIPT" ]]; then
      err "Missing ${SURREALDB_NATIVE_SCRIPT}"
      exit 1
    fi
    log "Starting SurrealDB (native CLI)..."
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
sync_content_studio_secrets
start_openinspector
# Load profile secrets (VOLCENGINE_*, etc.) before optional services.
if [[ -f "$HERMES_HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$HERMES_HOME/.env" 2>/dev/null || true
  set +a
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
    bash -lc "cd '$MONEYPRINTER_DIR' && '$DEEPAGENTS_PYTHON' main.py"
  wait_http "${MPT_API_URL}/docs" "MoneyPrinterTurbo API" 60
else
  log "MoneyPrinterTurbo API already up: ${MPT_API_URL}"
fi

if ! port_in_use "$MPT_WEBUI_PORT" || ! curl -fsS "${MPT_WEBUI_URL}" >/dev/null 2>&1; then
  start_background mpt-webui \
    bash -lc "cd '$MONEYPRINTER_DIR' && MPT_WEBUI_HOST=127.0.0.1 MPT_WEBUI_PORT=${MPT_WEBUI_PORT} sh webui.sh"
  wait_http "${MPT_WEBUI_URL}" "MoneyPrinterTurbo WebUI" 90
else
  log "MoneyPrinterTurbo WebUI already up: ${MPT_WEBUI_URL}"
fi

# ── 4. Hermes Gateway + Dashboard ───────────────────────────────────────
ensure_hermes_agent_deps
ensure_workspace_env

if ! port_in_use "$GATEWAY_PORT" || ! curl -fsS "${GATEWAY_URL}/health" >/dev/null 2>&1; then
  start_background gateway "$HERMES_CLI" gateway run
  wait_http "${GATEWAY_URL}/health" "Hermes Gateway" 60
else
  log "Hermes Gateway already up: ${GATEWAY_URL}"
fi

if ! port_in_use "$DASHBOARD_PORT" || ! curl -fsS "${DASHBOARD_URL}/api/status" >/dev/null 2>&1; then
  ensure_dashboard_web_ui
  start_background dashboard "$HERMES_CLI" dashboard --skip-build --port "$DASHBOARD_PORT" --no-open
  wait_http "${DASHBOARD_URL}/api/status" "Hermes Dashboard" "$DASHBOARD_READY_TIMEOUT"
else
  log "Hermes Dashboard already up: ${DASHBOARD_URL}"
fi

# ── Summary ─────────────────────────────────────────────────────────────
cat <<EOF

══════════════════════════════════════════════════════════════
  Content Studio Stack — 服务地址
══════════════════════════════════════════════════════════════

  【OpenInspector · LLM 追踪】  ${OPENINSPECTOR_UI_URL}
    Proxy (Hermes base_url): ${OPENINSPECTOR_URL}/v1
    API logs: ${OPENINSPECTOR_API_URL}/api/logs

  【Hermes · 官方 Dashboard】  ${DASHBOARD_URL}
    Chat: ${DASHBOARD_URL}/chat

  【Hermes · Workspace】       ${WORKSPACE_URL}

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
  export PORT="$WORKSPACE_PORT"

  if [[ "$WORKSPACE_BACKGROUND" == "1" ]]; then
    start_background workspace bash -lc \
      "cd '$HERMES_WORKSPACE_DIR' && export HERMES_API_URL='$GATEWAY_URL' HERMES_DASHBOARD_URL='$DASHBOARD_URL' HERMES_AGENT_PATH='$HERMES_AGENT_DIR' PORT='$WORKSPACE_PORT' && pnpm dev"
    wait_http "${WORKSPACE_URL}" "Hermes Workspace" 120
    trap - EXIT INT TERM
    log "All services started in background. Stop with: ./stop-content-studio-stack.sh"
  else
    cd "$HERMES_WORKSPACE_DIR"
    pnpm dev
  fi
fi
