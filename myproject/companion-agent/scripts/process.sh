#!/usr/bin/env bash
# api / voice 两个进程的 start / stop / restart / status，用 PID 文件追踪。
#
#   ./scripts/process.sh start [api|voice|all]     默认 all
#   ./scripts/process.sh stop  [api|voice|all]
#   ./scripts/process.sh restart [api|voice|all]
#   ./scripts/process.sh status
#   ./scripts/process.sh logs [api|voice] [行数]
#
# 不用 systemd、不用 sudo：setsid 让进程脱离启动它的脚本（和 SSH 会话）继续跑。
# start 会轮询 /health 最多 30 秒才报成功——"进程起来了但从不响应"正是只查 PID 会漏掉的故障。
#
# 例外：如果机器上装了 deploy/systemd/ 的 unit（见那份 README），本脚本自动改走
# systemctl——进程归 init 管（重启自起、崩溃自动拉起、cgroup 归 system.slice），
# 命令语义不变，只是背后换人。两套不能混跑，装 unit 前先把 setsid 起的进程 stop 掉。
#
# 端口从 <部署目录>/.data/deploy.env 读（CA_API_PORT 等），nginx 必须指同一个值。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"      # 项目根：scripts/ agent/ .data/
SERVER="${ROOT}/server"                       # Python 工程：.env .venv
RUN_DIR="${ROOT}/.data/run"
LOG_DIR="${ROOT}/.data/logs"
DEPLOY_ENV="${ROOT}/.data/deploy.env"

# deploy.env 只认白名单里的键，值按字面读（不执行、不展开），已导出的环境变量优先。
# 先记下环境变量里给过的值，再让文件补空位 —— 默认值放到最后，否则文件永远比不过默认值。
_deploy_env_keys="CA_API_HOST CA_API_PORT CA_START_TIMEOUT"
declare -A _from_env=()
for key in $_deploy_env_keys; do
  [[ -n "${!key+x}" ]] && _from_env[$key]="${!key}"
done
if [[ -r "$DEPLOY_ENV" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$line" in "" | "#"*) continue ;; esac
    [[ "$line" == *=* ]] || { printf '[process] 跳过没有 = 的行: %s\n' "$line" >&2; continue; }
    key="${line%%=*}"; value="${line#*=}"
    key="${key//[[:space:]]/}"
    case " $_deploy_env_keys " in
      *" $key "*) printf -v "$key" '%s' "${_from_env[$key]:-$value}" ;;
      *) printf '[process] 忽略未知的 deploy.env 键 "%s"\n' "$key" >&2 ;;
    esac
  done <"$DEPLOY_ENV"
fi
CA_API_HOST="${CA_API_HOST:-127.0.0.1}"
CA_API_PORT="${CA_API_PORT:-8081}"
CA_START_TIMEOUT="${CA_START_TIMEOUT:-30}"

VENV="${CA_VENV:-${SERVER}/.venv}"
PY="${VENV}/bin/python"
API_LOG="${LOG_DIR}/api.log"
VOICE_LOG="${LOG_DIR}/voice.log"

log() { printf '[process] %s\n' "$*"; }
die() { printf '[process] ERROR: %s\n' "$*" >&2; exit 1; }

pidfile() { case "$1" in api) echo "${RUN_DIR}/api.pid" ;; voice) echo "${RUN_DIR}/voice.pid" ;; esac; }
marker() { case "$1" in api) echo "companion.serve" ;; voice) echo "companion.worker" ;; esac; }
# 进程模块名：api 走 companion.serve，voice 走 companion.worker
module() { case "$1" in api) echo "companion.serve" ;; voice) echo "companion.worker" ;; esac; }

is_running() {
  local pf pid; pf="$(pidfile "$1")"
  [[ -f "$pf" ]] || return 1
  pid="$(cat "$pf" 2>/dev/null)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null || return 1
  # PID 可能被别的进程复用（崩溃时没清理 PID 文件）：命令里要能看到我们的模块名
  ps -o command= -p "$pid" 2>/dev/null | grep -qF "$(marker "$1")"
}

health_ok() { curl -sf -m 3 "http://${CA_API_HOST}:${CA_API_PORT}/health" >/dev/null 2>&1; }

port_owner() {
  local port="$1" pid cwd
  pid="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  [[ -n "$pid" ]] || return 0
  cwd="$(readlink "/proc/${pid}/cwd" 2>/dev/null || echo '?')"
  echo "${pid} $(ps -o command= -p "$pid" 2>/dev/null | cut -c1-90) (cwd ${cwd})"
}

start_one() {
  local name="$1" pf
  pf="$(pidfile "$name")"
  if is_running "$name"; then
    log "${name} 已在运行（pid $(cat "$pf")）"
    return 0
  fi
  [[ -x "$PY" ]] || die "没有虚拟环境 ${VENV} — 先跑 ./scripts/deploy.sh"
  [[ -f "${SERVER}/.env" ]] || die "缺 ${SERVER}/.env"

  if [[ "$name" == api ]]; then
    # 端口被别的部署占着时，健康检查会对着**别人**的进程返回 200，看起来像启动成功。
    # 所以先看端口属于谁，再决定能不能起。
    owner="$(port_owner "$CA_API_PORT")"
    if [[ -n "$owner" ]]; then
      die "端口 ${CA_API_PORT} 已被占用：${owner}
       如果是本目录的旧进程：./scripts/process.sh stop api
       如果是别的部署：改 .data/deploy.env 里的 CA_API_PORT，并同步 nginx"
    fi
  fi

  mkdir -p "$RUN_DIR" "$LOG_DIR"
  local logfile; logfile=$([[ "$name" == api ]] && echo "$API_LOG" || echo "$VOICE_LOG")
  log "启动 ${name}（日志 ${logfile}）"
  (
    cd "$SERVER"
    export PYTHONPATH=src
    # 适配器和 LiveKit CLI 读 os.environ，不读 .env；这里统一导出，避免音色/供应商悄悄退回默认值
    if [[ -f .env ]]; then set -a; . ./.env; set +a; fi
    export COMPANION_HOST="$CA_API_HOST" COMPANION_PORT="$CA_API_PORT"
    setsid "$PY" -m "$(module "$name")" >>"$logfile" 2>&1 < /dev/null &
    echo $! >"$pf"
  )

  # 语音 worker 不监听端口，健康与否看它有没有活过几秒（LiveKit 连不上会立刻退出）。
  if [[ "$name" == api ]]; then
    local waited=0
    while (( waited < CA_START_TIMEOUT )); do
      if health_ok; then log "${name} 健康（http://${CA_API_HOST}:${CA_API_PORT}/health）"; return 0; fi
      is_running "$name" || break
      sleep 1; waited=$((waited + 1))
    done
    is_running "$name" || { tail -20 "$logfile" >&2; die "${name} 起来就退出了，见上面的日志"; }
    tail -20 "$logfile" >&2
    die "${name} 进程在，但 ${CA_START_TIMEOUT}s 内 /health 没响应"
  else
    sleep 5
    if is_running "$name"; then log "${name} 已启动（pid $(cat "$pf")）"; return 0; fi
    tail -20 "$logfile" >&2
    die "${name} 起来就退出了（多半是 LiveKit 连不上或缺凭据），见上面的日志"
  fi
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
  # api 有优雅停机：收到第一个 TERM 后停止接新请求，等回合收尾至多 45 秒。
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
  # 语音 worker 由 LiveKit 的 supervisor 起了子进程，父进程退出不代表端口已经放开；
  # 立刻 start 会撞上 "address already in use"（线上见过一次：新 worker 起来就死，
  # 而 status 还显示"运行中"，因为旧进程仍活着）。等端口真的空出来再返回。
  if [[ "$name" == voice ]]; then
    local port="${COMPANION_VOICE_WORKER_PORT:-8082}" waited_port=0
    while (( waited_port < 15 )); do
      ss -lnt 2>/dev/null | grep -q ":${port} " || break
      sleep 1; waited_port=$((waited_port + 1))
    done
    (( waited_port > 0 )) && log "等待 ${port} 释放用了 ${waited_port}s"
  fi
  log "${name} 已停止"
}

status_one() {
  local name="$1" pf pid
  pf="$(pidfile "$name")"
  if is_running "$name"; then
    pid="$(cat "$pf")"
    printf '  %-6s 运行中  pid %-8s 启动 %s\n' "$name" "$pid" "$(ps -o lstart= -p "$pid" 2>/dev/null | sed 's/^ *//')"
  else
    printf '  %-6s 未运行\n' "$name"
  fi
}

cmd="${1:-status}"
target="${2:-all}"
case "$target" in
  api | voice) names=("$target") ;;
  all) names=(api voice) ;;
  *) die "未知目标: ${target}（api / voice / all）" ;;
esac

# ---------------------------------------------------------------------------
# systemd 模式：如果 deploy/systemd 的 unit 已装进 /etc/systemd/system，
# 全部命令委托给 systemctl——进程归 init 管（机器重启自起、崩溃自动重启、
# cgroup 归位 system.slice），PID 文件那套只留给没装 unit 的机器。
# 需要 sudo（web 只对这两个 unit 的 start/stop/restart 有 NOPASSWD，见
# deploy/systemd/README.md）；sudo -n 不通就不委托，别卡在密码提示上。
unit_name() { case "$1" in api) echo companion-api ;; voice) echo companion-voice ;; esac; }

systemd_managed() {
  local unit; unit="$(unit_name "$1")"
  [[ -f "/etc/systemd/system/${unit}.service" ]] || return 1
  command -v systemctl >/dev/null 2>&1 || return 1
  sudo -n true >/dev/null 2>&1 || return 1
  # unit 活着：它是主人。
  sudo -n systemctl is-active --quiet "$unit" && return 0
  # unit 装了还没起，但 setsid 旧进程还在（切换窗口）：这一下仍走 PID 文件，
  # 好让 `process.sh stop` 能把旧进程收掉，而不是对着没起的 unit 打空。
  is_running "$1" && return 1
  return 0
}

systemd_cmd() {
  local cmd="$1" name="$2" unit
  unit="$(unit_name "$name")"
  case "$cmd" in
    start | stop | restart)
      log "systemd: ${cmd} ${unit}"
      sudo systemctl "$cmd" "$unit"
      # api 启动沿用健康检查：systemctl start 只保证 exec 成功，不代表 /health 活了。
      if [[ "$cmd" != stop && "$name" == api ]]; then
        local waited=0
        while (( waited < CA_START_TIMEOUT )); do
          health_ok && { log "api 健康（http://${CA_API_HOST}:${CA_API_PORT}/health）"; return 0; }
          sleep 1; waited=$((waited + 1))
        done
        die "api 起了但 ${CA_START_TIMEOUT}s 内 /health 没响应：journalctl -u ${unit} -n 40"
      fi
      ;;
    status)
      printf '  %-6s %s\n' "$name" "$(sudo systemctl is-active "$unit")  [systemd ${unit}]"
      ;;
    logs)
      local lines="${3:-80}"
      journalctl -u "$unit" -n "$lines" --no-pager
      ;;
  esac
}

# 目标里有一个是 systemd 管的，就整组走 systemd（混跑两套必打架）。
# 目标里每一个都是 systemd 管的，整组才走 systemd（混跑两套必打架；
# 切换窗口里旧的没停干净时，本组仍按 PID 文件模式走，先把旧的收掉）。
group_systemd=true
for n in "${names[@]}"; do systemd_managed "$n" || { group_systemd=false; break; }; done
if $group_systemd; then
  for n in "${names[@]}"; do
    case "$cmd" in
      start | stop | restart | status) systemd_cmd "$cmd" "$n" ;;
      logs) systemd_cmd logs "$n" "${3:-80}" ;;
      *) die "未知命令: ${cmd}（start / stop / restart / status / logs）" ;;
    esac
  done
  exit 0
fi

case "$cmd" in
  start) for n in "${names[@]}"; do start_one "$n"; done ;;
  stop) for n in "${names[@]}"; do stop_one "$n"; done ;;
  restart) for n in "${names[@]}"; do stop_one "$n"; done; for n in "${names[@]}"; do start_one "$n"; done ;;
  status)
    log "部署目录: ${ROOT}"
    log "端口:     ${CA_API_HOST}:${CA_API_PORT}（从 .data/deploy.env 或环境变量）"
    status_one api; status_one voice
    owner="$(port_owner "$CA_API_PORT")"
    [[ -n "$owner" ]] && log "端口 ${CA_API_PORT} 属于: ${owner}"
    ;;
  logs)
    lines="${3:-80}"
    case "$target" in api) tail -n "$lines" -f "$API_LOG" ;; voice) tail -n "$lines" -f "$VOICE_LOG" ;; *) die "logs 要指定 api 或 voice" ;; esac
    ;;
  -h | --help | help) sed -n '2,14p' "$0" ;;
  *) die "未知命令: ${cmd}（start / stop / restart / status / logs）" ;;
esac
