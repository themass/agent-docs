#!/usr/bin/env bash
# 一键本地离线演示:Mock Domain API(8080) -> MCP 控制桥(8101) -> worker(8102) -> BFF(8100) -> [Studio(5190)]
#
# - 全部使用脚本内固定的本地假令牌,不读取任何 .env;DEERFLOW_ENABLED=false(运行时走确定性 STUB)。
# - 每个子进程用 env -i 起,只带白名单环境变量,不会继承你 shell 里的任何真实密钥。
# - pid 与日志在 content-agent/deploy/dev-mock/.run/(已被 .gitignore 忽略)。
# - 幂等:已在运行的服务只提示,不会重复启动。
# - 不修改 pyproject.toml / uv.lock:用 `uv run --frozen --package <pkg>`。
#
# 用法: scripts/content-agent/dev-offline.sh [--studio] [--require-worker] [--timeout 秒]
set -euo pipefail
source "$(dirname "$0")/_dev-offline-common.sh"

WITH_STUDIO=0
REQUIRE_WORKER=0
READY_TIMEOUT=60

while [[ $# -gt 0 ]]; do
  case "$1" in
    --studio) WITH_STUDIO=1 ;;
    --require-worker) REQUIRE_WORKER=1 ;;
    --timeout)
      shift
      READY_TIMEOUT="${1:-}"
      [[ "$READY_TIMEOUT" =~ ^[0-9]+$ ]] || { echo "--timeout 需要一个整数(秒)" >&2; exit 2; }
      ;;
    -h | --help)
      sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数: $1(见 --help)" >&2; exit 2 ;;
  esac
  shift
done

for tool in uv curl lsof pgrep; do
  command -v "$tool" >/dev/null 2>&1 || { echo "缺少命令: $tool" >&2; exit 1; }
done
[[ "$WITH_STUDIO" == 1 ]] && { command -v npm >/dev/null 2>&1 || { echo "缺少命令: npm(--studio 需要)" >&2; exit 1; }; }

mkdir -p "$RUN_DIR"
STARTED_NOW=""

cleanup_on_failure() {
  local rc=$?
  if [[ $rc -ne 0 && -n "$STARTED_NOW" ]]; then
    echo "启动失败,停止本次新启动的服务:$STARTED_NOW" >&2
    local s
    for s in $STARTED_NOW; do stop_service "$s" >&2 || true; done
  fi
  exit "$rc"
}
trap cleanup_on_failure EXIT

# 子进程环境白名单:PATH/HOME 等工具链需要的变量 + 各服务自己的变量。
base_env=(
  "PATH=$PATH" "HOME=$HOME" "TMPDIR=${TMPDIR:-/tmp}"
  "LANG=${LANG:-en_US.UTF-8}" "LC_ALL=${LC_ALL:-en_US.UTF-8}"
  "PYTHONUNBUFFERED=1" "PYTHONDONTWRITEBYTECODE=1"
)

launch() {
  local name="$1"
  shift
  local port
  port="$(port_of "$name")"

  if is_running "$name"; then
    if is_ready "$name"; then
      echo "  $name: 已在运行 (pid $(cat "$(pid_file "$name")"), 端口 $port),跳过"
      return 0
    fi
    echo "  $name: 进程在但未就绪,先停止再重启"
    stop_service "$name"
  fi
  if port_listening "$port"; then
    echo "错误: 端口 $port 已被其他进程占用($name 无法启动)。用 lsof -nP -iTCP:$port -sTCP:LISTEN 查看。" >&2
    return 1
  fi

  : >"$(log_file "$name")"
  (
    cd "$PLATFORM_ROOT"
    exec nohup "$@" >>"$(log_file "$name")" 2>&1
  ) &
  echo $! >"$(pid_file "$name")"
  STARTED_NOW="$STARTED_NOW $name"

  local waited=0
  while ((waited < READY_TIMEOUT)); do
    if ! is_running "$name"; then
      echo "错误: $name 启动后退出了。日志末尾:" >&2
      tail -n 25 "$(log_file "$name")" >&2 || true
      return 1
    fi
    if is_ready "$name"; then
      echo "  $name: 就绪 (pid $(cat "$(pid_file "$name")"), 端口 $port, ${waited}s)"
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  echo "错误: $name 在 ${READY_TIMEOUT}s 内未就绪。日志末尾:" >&2
  tail -n 25 "$(log_file "$name")" >&2 || true
  return 1
}

echo "== 本地离线演示(假令牌,内存 Mock,DEERFLOW_ENABLED=false)=="

# 1. Mock Domain API
launch mock env -i "${base_env[@]}" \
  "PORT=8080" "HOST=127.0.0.1" "MOCK_JSON_NAMING=snake" \
  "POETRY_AGENT_INTERNAL_TOKEN=$FAKE_AGENT_TOKEN" \
  "POETRY_STUDIO_REVIEWER_TOKEN=$FAKE_STUDIO_TOKEN" \
  uv run --frozen --package poetry-agent-bff python "$DEV_MOCK_DIR/mock_domain_api.py"

# 2. MCP 控制桥(只拿 agent 令牌;拿不到 studio 令牌与 worker 令牌)
launch mcp env -i "${base_env[@]}" \
  "PORT=8101" "HOST=127.0.0.1" \
  "POETRY_API_BASE_URL=http://127.0.0.1:8080" "POETRY_API_TIMEOUT_SECONDS=15" \
  "POETRY_AGENT_INTERNAL_TOKEN=$FAKE_AGENT_TOKEN" "POETRY_AGENT_ACTOR_ROLE=CONTENT_EDITOR" \
  "MCP_INTERNAL_TOKEN=$FAKE_MCP_TOKEN" "POETRY_DOMAIN_CONTROL_TOKEN=$FAKE_CONTROL_TOKEN" \
  uv run --frozen --package poetry-domain-mcp python -m poetry_domain_mcp.server

# 3. worker(S3 实现 agent_worker.app;模块还不存在时给清晰提示,不崩)
WORKER_APP="$CONTENT_AGENT/agent/agent-worker/src/agent_worker/app.py"
if [[ -f "$WORKER_APP" ]]; then
  launch worker env -i "${base_env[@]}" \
    "PORT=8102" "HOST=127.0.0.1" \
    "POETRY_AGENT_PROFILE_ROOT=$CONTENT_AGENT/agent/deerflow-profile" \
    "POETRY_DOMAIN_CONTROL_URL=http://127.0.0.1:8101" "POETRY_DOMAIN_CONTROL_TOKEN=$FAKE_CONTROL_TOKEN" \
    "POETRY_WORKER_TOKEN=$FAKE_WORKER_TOKEN" "DEERFLOW_ENABLED=false" "WORKER_MAX_CONCURRENT_RUNS=2" \
    uv run --frozen --package poetry-agent-worker python -m agent_worker.app
else
  msg="worker: 跳过。agent_worker.app 还不存在($WORKER_APP);它由子任务 S3 实现,完成后重新运行本脚本即可。"
  if [[ "$REQUIRE_WORKER" == 1 ]]; then
    echo "错误: $msg" >&2
    exit 1
  fi
  echo "  $msg"
  echo "  (BFF 仍会启动,读接口和人工评审可用;发起运行 POST /tasks/{id}/run 会因 worker 不可达而失败)"
fi

# 4. BFF(拿 studio 令牌直连 Mock;不拿 agent 令牌)
launch bff env -i "${base_env[@]}" \
  "PORT=8100" "HOST=127.0.0.1" \
  "POETRY_AGENT_PROFILE_ROOT=$CONTENT_AGENT/agent/deerflow-profile" \
  "POETRY_DOMAIN_CONTROL_URL=http://127.0.0.1:8101" "POETRY_DOMAIN_CONTROL_TOKEN=$FAKE_CONTROL_TOKEN" \
  "POETRY_API_BASE_URL=http://127.0.0.1:8080" "POETRY_STUDIO_REVIEWER_TOKEN=$FAKE_STUDIO_TOKEN" \
  "POETRY_WORKER_URL=http://127.0.0.1:8102" "POETRY_WORKER_TOKEN=$FAKE_WORKER_TOKEN" \
  "POETRY_STUDIO_ORIGINS=http://localhost:5190,http://127.0.0.1:5190" \
  "DEERFLOW_ENABLED=false" \
  "POETRY_STUDIO_AUTH=off" \
  uv run --frozen --package poetry-agent-bff python -c "from agent_bff.main import run; run()"

# 5. 可选 Studio
if [[ "$WITH_STUDIO" == 1 ]]; then
  FRONTEND="$CONTENT_AGENT/frontend"
  if [[ ! -d "$FRONTEND/node_modules" ]]; then
    echo "错误: $FRONTEND/node_modules 不存在,请先在 content-agent/frontend 里运行 npm install。" >&2
    exit 1
  fi
  launch studio env -i "${base_env[@]}" \
    "VITE_AGENT_BFF_URL=http://127.0.0.1:8100" \
    npm --prefix "$FRONTEND" run dev -- --host 127.0.0.1 --port 5190 --strictPort
fi

trap - EXIT
echo
echo "已就绪。常用入口:"
echo "  (离线演示模式: Studio 登录已关闭 POETRY_STUDIO_AUTH=off,身份由页面自行声明,仅限本机演示)"
echo "  Mock 健康        curl http://127.0.0.1:8080/__mock/health"
echo "  Mock 重置种子    curl -X POST http://127.0.0.1:8080/__mock/reset"
echo "  BFF 健康         curl http://127.0.0.1:8100/health/ready"
[[ "$WITH_STUDIO" == 1 ]] && echo "  Studio           http://127.0.0.1:5190/"
echo "  状态 / 停止      make content-dev-offline-status / make content-dev-offline-down"
echo "  日志             $RUN_DIR/<服务>.log"
