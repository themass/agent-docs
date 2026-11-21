#!/usr/bin/env bash
# dev-offline*.sh 共用的常量与小函数。只被 source,不单独运行。
# 这里的令牌全是明显的本地假令牌,只对本机 127.0.0.1 上的内存 Mock 有意义;脚本不读取任何 .env。

source "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"

DEV_MOCK_DIR="$CONTENT_DEPLOY/dev-mock"
RUN_DIR="$DEV_MOCK_DIR/.run"

# 服务清单(启动顺序)。每项:名称 端口。停止时按相反顺序。
SERVICES_BASE="mock mcp worker bff"
SERVICES_ALL="mock mcp worker bff studio"

port_of() {
  case "$1" in
    mock) echo 8080 ;;
    mcp) echo 8101 ;;
    worker) echo 8102 ;;
    bff) echo 8100 ;;
    studio) echo 5190 ;;
  esac
}

# 就绪探测地址。mcp 没有专门的健康端点,只要端口能回 HTTP 状态码即视为就绪。
health_url_of() {
  case "$1" in
    mock) echo "http://127.0.0.1:8080/health/live" ;;
    mcp) echo "http://127.0.0.1:8101/internal/tasks" ;;
    worker) echo "http://127.0.0.1:8102/health/live" ;;
    bff) echo "http://127.0.0.1:8100/health/live" ;;
    studio) echo "http://127.0.0.1:5190/" ;;
  esac
}

# 本地假令牌(契约 §14)。四类令牌互不相同,便于验证令牌隔离。
FAKE_AGENT_TOKEN="dev-offline-fake-agent-token"
FAKE_STUDIO_TOKEN="dev-offline-fake-studio-reviewer-token"
FAKE_MCP_TOKEN="dev-offline-fake-mcp-token"
FAKE_CONTROL_TOKEN="dev-offline-fake-control-token"
FAKE_WORKER_TOKEN="dev-offline-fake-worker-token"

pid_file() { echo "$RUN_DIR/$1.pid"; }
log_file() { echo "$RUN_DIR/$1.log"; }

# 记录的 pid 是否仍在运行。
is_running() {
  local f pid
  f="$(pid_file "$1")"
  [[ -f "$f" ]] || return 1
  pid="$(cat "$f" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# 端口上是否有监听进程(不论是不是我们启动的)。
port_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

# 健康探测:返回 HTTP 状态码(连不上为 000)。
http_code() {
  curl -s -o /dev/null -m 3 -w '%{http_code}' "$1" 2>/dev/null || true
}

# 服务是否就绪。mcp 与 studio 只要有 HTTP 响应即可,其余要求 200。
is_ready() {
  local code
  code="$(http_code "$(health_url_of "$1")")"
  case "$1" in
    mcp | studio) [[ "$code" != "000" && -n "$code" ]] ;;
    *) [[ "$code" == "200" ]] ;;
  esac
}

# 递归停止进程树(uv run 会派生子进程,只杀父进程会留下孤儿)。
kill_tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stop_service() {
  local name="$1" f pid i
  f="$(pid_file "$name")"
  if ! is_running "$name"; then
    rm -f "$f"
    echo "  $name: 未在运行"
    return 0
  fi
  pid="$(cat "$f")"
  kill_tree "$pid"
  for i in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
    echo "  $name: 已强制结束 (pid $pid)"
  else
    echo "  $name: 已停止 (pid $pid)"
  fi
  rm -f "$f"
}
