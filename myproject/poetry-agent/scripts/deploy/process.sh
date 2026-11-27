#!/usr/bin/env bash
# **一个进程**（agent）的 start / stop / restart / status / logs，用 PID 文件追踪。
#
#   ./scripts/deploy/process.sh start [agent|all]     默认 all
#   ./scripts/deploy/process.sh stop  [agent|all]
#   ./scripts/deploy/process.sh restart [agent|all]
#   ./scripts/deploy/process.sh status
#   ./scripts/deploy/process.sh logs [agent] [行数]
#
# 2026-11-28：bff / 控制桥 / worker 合并成**一个进程、一个端口**（agent_bff.allinone，:8100），
# 内部令牌统一成一把（POETRY_AGENT_INTERNAL_TOKEN）。原三进程六令牌的设计（A-05/A-12/A-18）
# 是用户看过架构后否掉的：「放一起，不要那么多的令牌」。人工闸没动——批准仍只有 Studio
# 登录后的审阅人按得动。旧的三进程模块还在（poetry_domain_mcp.server、agent_worker.app
# 仍可单独起），只是这里不再起它们。
#
# 不用 systemd、不用 sudo、**不用 docker**：setsid 让进程脱离启动它的脚本（和 SSH 会话）继续跑。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"    # 平台根：pyproject.toml + uv.lock + content-agent/
ENV_FILE="${ROOT}/content-agent/deploy/.env"   # 真实凭据：服务器手工维护，永不入库
RUN_DIR="${ROOT}/.data/run"
LOG_DIR="${ROOT}/.data/logs"
VENV="${PAP_VENV:-${ROOT}/.venv}"
PROFILE_ROOT="${PAP_PROFILE_ROOT:-${ROOT}/content-agent/agent/deerflow-profile}"
START_TIMEOUT="${PAP_START_TIMEOUT:-30}"

log() { printf '[process] %s\n' "$*"; }
die() { printf '[process] ERROR: %s\n' "$*" >&2; exit 1; }

# ---------- .env 按字面读（不 eval、不展开），last-wins，与 docker compose 一致 ----------
# 兼容 bash 3.2（macOS 本地也能跑）：不用关联数组，键值对全留在 .env 文件里，按需 awk 取值。
env_val() {  # env_val KEY —— 文件里的最后一次赋值；文件不存在则空
  [[ -f "$ENV_FILE" ]] || return 0
  awk -F= -v k="$1" '
    /^[[:space:]]*#/ { next }
    index($0, k "=") == 1 {
      key = substr($0, 1, index($0, "=") - 1)
      gsub(/[[:space:]]/, "", key)
      if (key == k) { v = substr($0, index($0, "=") + 1) }   # last-wins
    }
    END { printf "%s", v }
  ' "$ENV_FILE"
}
envget() {  # envget KEY DEFAULT —— 已导出的同名环境变量优先，方便一次性覆盖
  [[ -n "${!1+x}" ]] && { printf '%s' "${!1}"; return; }
  local v; v="$(env_val "$1")"
  printf '%s' "${v:-${2-}}"
}

# ---------- 单进程的环境（一把内部令牌 + Studio 登录 + Java 地址） ----------
keys_for() {
  case "$1" in
    agent) printf '%s\n' DEERFLOW_ENABLED POETRY_AGENT_PROFILE_ROOT POETRY_DOMAIN_CONTROL_URL \
            POETRY_DOMAIN_CONTROL_TOKEN POETRY_DOMAIN_REVIEW_TOKEN POETRY_API_BASE_URL \
            POETRY_API_TIMEOUT_SECONDS POETRY_STUDIO_REVIEWER_TOKEN POETRY_WORKER_URL \
            POETRY_WORKER_TOKEN POETRY_STUDIO_ORIGINS POETRY_STUDIO_AUTH POETRY_STUDIO_USERS_FILE \
            POETRY_STUDIO_SESSION_SECRET POETRY_AGENT_INTERNAL_TOKEN MCP_INTERNAL_TOKEN \
            POETRY_AGENT_ACTOR_ROLE DEERFLOW_GATEWAY_URL DEERFLOW_GATEWAY_TOKEN \
            DEERFLOW_ASSISTANT_ID WORKER_MAX_CONCURRENT_RUNS DEERFLOW_AUTH_MODE \
            DEERFLOW_OWNER_USER_ID DEERFLOW_FALLBACK_MODEL ;;
  esac
}

# 端口与绑定：一个进程一个端口
port_for() {
  case "$1" in
    agent) envget AGENT_BFF_PORT 8100 ;;
  esac
}
BIND_HOST="$(envget AGENT_BIND_HOST 127.0.0.1)"
PROBE_HOST=127.0.0.1   # 健康探测永远走回环，与绑定地址无关

pidfile() { echo "${RUN_DIR}/$1.pid"; }
marker()  { case "$1" in agent) echo "agent_bff.allinone" ;; esac; }
logfor()  { echo "${LOG_DIR}/$1.log"; }

is_running() {
  local pf pid; pf="$(pidfile "$1")"
  [[ -f "$pf" ]] || return 1
  pid="$(cat "$pf" 2>/dev/null)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null || return 1
  # PID 可能被别的进程复用（崩溃时没清理 PID 文件）：命令里要能看到我们的模块名
  ps -o command= -p "$pid" 2>/dev/null | grep -qF "$(marker "$1")"
}

health_ok() {  # health_ok NAME —— 单进程轮询 /health/ready（它会把桥与 worker 的可达性一起报出来）
  local name="$1" port; port="$(port_for "$name")"
  curl -sf -m 3 "http://${PROBE_HOST}:${port}/health/ready" >/dev/null 2>&1
}

port_owner() {
  local port="$1" pid cwd
  pid="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  [[ -n "$pid" ]] || return 0
  cwd="$(readlink "/proc/${pid}/cwd" 2>/dev/null || echo '?')"
  echo "${pid} $(ps -o command= -p "$pid" 2>/dev/null | cut -c1-90) (cwd ${cwd})"
}

start_one() {
  local name="$1" pf port owner v
  pf="$(pidfile "$name")"
  if is_running "$name"; then
    log "${name} 已在运行（pid $(cat "$pf")）"
    return 0
  fi
  [[ -x "${VENV}/bin/python" ]] || die "没有虚拟环境 ${VENV} — 先跑 ./scripts/deploy/deploy.sh"
  [[ -f "$ENV_FILE" ]] || die "缺 ${ENV_FILE}。从 content-agent/deploy/.env.example 复制一份再填值（chmod 600）"
  [[ -d "$PROFILE_ROOT" ]] || die "缺 profile 目录 ${PROFILE_ROOT}（bff/worker 需要；PAP_PROFILE_ROOT 可覆盖）"

  port="$(port_for "$name")"
  # 端口被别的部署占着时，健康检查会对着**别人**的进程返回 200，看起来像启动成功。
  # 所以先看端口属于谁，再决定能不能起。
  owner="$(port_owner "$port")"
  if [[ -n "$owner" ]]; then
    die "端口 ${port}（${name}）已被占用：${owner}
     如果是本目录的旧进程：./scripts/deploy/process.sh stop ${name}
     如果是别的部署：改 content-agent/deploy/.env 里的端口键，并同步 nginx"
  fi

  mkdir -p "$RUN_DIR" "$LOG_DIR" "${ROOT}/.data/studio-auth"
  local logfile; logfile="$(logfor "$name")"
  log "启动 ${name}（端口 ${port}，日志 ${logfile}）"
  (
    # 白名单导出：只有本服务该有的键进环境。空值不导出等价于导出空串（os.getenv 缺省即 ""）。
    # HOST/PORT 是我们注入的进程级配置，最后设。
    while IFS= read -r key; do
      v="$(env_val "$key")"
      [[ -n "$v" ]] && export "$key=$v"
    done < <(keys_for "$name")
    export HOST="$BIND_HOST" PORT="$port"
    export POETRY_AGENT_PROFILE_ROOT="${POETRY_AGENT_PROFILE_ROOT:-$(envget POETRY_AGENT_PROFILE_ROOT "$PROFILE_ROOT")}"
    # 桥与 worker 挂在同一进程里（allinone），URL 指回自己的挂载点。
    export POETRY_DOMAIN_CONTROL_URL="${POETRY_DOMAIN_CONTROL_URL:-$(envget POETRY_DOMAIN_CONTROL_URL "http://127.0.0.1:${port}/_bridge")}"
    export POETRY_WORKER_URL="${POETRY_WORKER_URL:-$(envget POETRY_WORKER_URL "http://127.0.0.1:${port}/_worker")}"
    export POETRY_STUDIO_USERS_FILE="${POETRY_STUDIO_USERS_FILE:-$(envget POETRY_STUDIO_USERS_FILE "${ROOT}/.data/studio-auth/users.json")}"
    # setsid 让进程脱离本脚本的进程组（Linux 有；本地 mac 没有就退化成普通后台进程，
    # 靠 nohup 语义的 SIGHUP 忽略已经够用——生产机是 Linux，走的是 setsid 分支）。
    if command -v setsid >/dev/null 2>&1; then
      setsid "${VENV}/bin/python" -m "$(marker "$name")" >>"$logfile" 2>&1 < /dev/null &
    else
      "${VENV}/bin/python" -m "$(marker "$name")" >>"$logfile" 2>&1 < /dev/null &
    fi
    echo $! >"$pf"
  )

  local waited=0
  while (( waited < START_TIMEOUT )); do
    health_ok "$name" && { log "${name} 健康（${PROBE_HOST}:${port}）"; return 0; }
    is_running "$name" || break
    sleep 1; waited=$((waited + 1))
  done
  is_running "$name" || { tail -20 "$logfile" >&2; die "${name} 起来就退出了，见上面的日志"; }
  tail -20 "$logfile" >&2
  die "${name} 进程在，但 ${START_TIMEOUT}s 内 /health/ready 没响应"
}

stop_one() {
  local name="$1" pf pid waited=0
  pf="$(pidfile "$name")"
  if ! is_running "$name"; then
    log "${name} 没在运行"
    rm -f "$pf"
    return 0
  fi
  pid="$(cat "$pf")"
  log "停止 ${name}（pid ${pid}）"
  kill -TERM "$pid" 2>/dev/null || true
  while kill -0 "$pid" 2>/dev/null && (( waited < 60 )); do
    sleep 1; waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    log "${name} 60 秒内没退出，强制结束"
    kill -KILL "$pid" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$pf"
  # 等端口真的空出来再返回，否则紧接着的 start 会撞 "address already in use"
  local port port_wait=0 owner; port="$(port_for "$name")"
  while (( port_wait < 15 )); do
    owner="$(port_owner "$port")"
    [[ -z "$owner" ]] && break
    sleep 1; port_wait=$((port_wait + 1))
  done
  (( port_wait > 0 )) && log "等待 ${port} 释放用了 ${port_wait}s"
  log "${name} 已停止"
}

status_one() {
  local name="$1" pf pid port state
  pf="$(pidfile "$name")"; port="$(port_for "$name")"
  if is_running "$name"; then
    pid="$(cat "$pf")"
    state="运行中  pid $(printf '%-8s' "$pid") 启动 $(ps -o lstart= -p "$pid" 2>/dev/null | sed 's/^ *//')"
  else
    state="未运行"
  fi
  printf '  %-6s %-60s :%s\n' "$name" "$state" "$port"
}

cmd="${1:-status}"
target="${2:-all}"
ALL_NAMES=(agent)
case "$target" in
  agent | all) names=(agent) ;;
  *) die "未知目标: ${target}（agent / all）" ;;
esac

case "$cmd" in
  start)
    [[ -f "$ENV_FILE" ]] || die "缺 ${ENV_FILE}"
    for n in "${names[@]}"; do start_one "$n"; done ;;
  stop)
    for (( i=${#names[@]}-1; i>=0; i-- )); do stop_one "${names[$i]}"; done ;;
  restart)
    [[ -f "$ENV_FILE" ]] || die "缺 ${ENV_FILE}"
    for (( i=${#names[@]}-1; i>=0; i-- )); do stop_one "${names[$i]}"; done
    for n in "${names[@]}"; do start_one "$n"; done ;;
  status)
    log "部署目录: ${ROOT}"
    log "绑定:     ${BIND_HOST}（AGENT_BIND_HOST；健康探测走 127.0.0.1）"
    for n in "${ALL_NAMES[@]}"; do status_one "$n"; done
    for n in "${ALL_NAMES[@]}"; do
      owner="$(port_owner "$(port_for "$n")")"
      # 空 owner 时不能留假值给 $?——它会让脚本以 1 退出
      if [[ -n "$owner" ]]; then log "端口 $(port_for "$n")（${n}）属于: ${owner}"; fi
    done
    ;;
  logs)
    lines="${3:-80}"
    tail -n "$lines" -f "$(logfor agent)"
    ;;
  -h | --help | help) sed -n '2,14p' "$0" ;;
  *) die "未知命令: ${cmd}（start / stop / restart / status / logs）" ;;
esac
