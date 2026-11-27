#!/usr/bin/env bash
# 把一台机器备好并把 agent 栈装上去：缺什么装什么，装 Python 依赖，做导入自检。**不启动任何进程**
# ——那是 process.sh 的事，单独一步，这样构建结果能在切过去之前先看一眼。
#
#   ./scripts/deploy/deploy.sh                 # 全部
#   ./scripts/deploy/deploy.sh --env-only      # 只备环境，不部署
#   ./scripts/deploy/deploy.sh --skip-imports  # 跳过导入自检
#
# **没有数据库迁移这一步，这是设计**：poetry_* 表唯一的写入口是 Java Poetry API
# （docs/deployment.md「MySQL remains private to Java」）；agent 平台拿不到也不该拿库凭据。
# 迁移由 testserverV 仓库的 db/poetry/ 迁移文件走 Java 侧流程，与本脚本无关。
#
# 装的东西都在当前用户家目录里，不用 sudo、不改 shell 配置：
#   uv            缺了就装到 ~/.local/bin
#   Python 3.12   由 uv 私有安装（不动系统 python3）
# 需要管理员的只有 curl、tar，缺了会在下载任何东西之前一次报全。
#
#   PAP_DEPLOY_HEARTBEAT_SEC=30   长步骤每隔一段时间打印一行（防 SSH 断开误判卡死）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"   # 平台根：pyproject.toml + uv.lock + content-agent/ 在这里
ENV_FILE="${ROOT}/content-agent/deploy/.env"  # 真实凭据：服务器手工维护，永不入库
VENV="${PAP_VENV:-${ROOT}/.venv}"
HEARTBEAT="${PAP_DEPLOY_HEARTBEAT_SEC:-30}"

DO_IMPORTS=true
ENV_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --skip-imports) DO_IMPORTS=false ;;
    --env-only) ENV_ONLY=true ;;
    -h | --help) sed -n '2,18p' "$0"; exit 0 ;;
    *) printf '[deploy] ERROR: 未知参数: %s\n' "$arg" >&2; exit 1 ;;
  esac
done

log() { printf '[deploy] %s\n' "$*"; }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

# 长命令加心跳：一分钟不出声的下载和"卡死"在 SSH 里长得一模一样。
beat() {
  local label="$1"; shift
  local start=$SECONDS
  "$@" &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    sleep "$HEARTBEAT"
    kill -0 "$pid" 2>/dev/null || break
    log "  ... ${label} 还在跑（$((SECONDS - start))s）"
  done
  wait "$pid"
}

# 1. 只有管理员能装的东西，一次报全，别让人一件一件发现。
missing=()
for tool in curl tar gzip; do
  command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done
if [[ ${#missing[@]} -gt 0 ]]; then
  die "缺这些系统工具：${missing[*]}
       管理员执行一次：yum install -y ${missing[*]}   # 或 apt-get install -y ${missing[*]}"
fi

# 2. uv。
if ! command -v uv >/dev/null 2>&1; then
  if [[ -x "${HOME}/.local/bin/uv" ]]; then
    export PATH="${HOME}/.local/bin:${PATH}"
  else
    log "安装 uv 到 ~/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | sh || die "uv 装不上；可能是网络，或先手工放一个 uv 到 ~/.local/bin"
    export PATH="${HOME}/.local/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || die "uv 装完仍找不到，检查 ~/.local/bin 是否在 PATH 里"
  fi
fi
log "uv:      $(uv --version 2>&1)"

# 3. Python 3.12。三个 agent 服务都要求 >=3.12。
beat "python 3.12" uv python install 3.12 || die "uv 装不了 Python 3.12"
PYTHON="$(uv python find 3.12)" || die "找不到 uv 装的 3.12"
log "python:  ${PYTHON} ($("$PYTHON" -V 2>&1))"

if [[ "$ENV_ONLY" == true ]]; then
  log "环境就绪 — 什么都没部署（--env-only）"
  exit 0
fi

# 4. 先做不联网的检查：缺 .env 时不该先下载几百兆依赖再失败。
[[ -f "$ENV_FILE" ]] || die "缺 ${ENV_FILE}。从 content-agent/deploy/.env.example 复制一份再填值（权限 600；不要入库）。
     裸机部署提醒：POETRY_API_BASE_URL 应指向本机 Java API（http://127.0.0.1:8888），不是 compose 里的 host.docker.internal:8080。"
# 只看"别人和同组能不能读"：600 合格，640/644 不合格。用位运算，别用字符串比大小。
env_mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE" 2>/dev/null || echo 600)"
if (( (8#${env_mode} & 077) != 0 )); then
  log "提示：${ENV_FILE} 权限是 ${env_mode}，里面有令牌，建议 chmod 600"
fi
[[ -f "${ROOT}/uv.lock" ]] || die "缺 ${ROOT}/uv.lock。在源码目录跑 uv lock 并提交；没有锁文件就装不出确定的依赖版本"

# 5. 依赖。平台根是 uv workspace（bff / mcp / worker / student-agent 都是成员），
#    在根上 sync 一次装齐全部成员——不要按服务目录分别装，lock 只有一个。
#    --all-packages：根项目自身依赖是空的，**不带它只会装出一个空 venv**（workspace 语义），
#    2026-11-28 在 104 上就是这么踩的：sync 秒过、导入自检才炸。
#    --frozen：严格按 uv.lock 装，lock 和 pyproject 不一致就报错而不是悄悄重新解析。
log "安装 Python 依赖到 ${VENV}（uv workspace：bff + mcp + worker + student-agent）"
beat "uv sync" env UV_PROJECT_ENVIRONMENT="$VENV" uv sync --frozen --no-dev --all-packages --project "$ROOT"

if [[ "$DO_IMPORTS" == true ]]; then
  log "核对关键包与导入"
  "$VENV/bin/python" - <<'PY' || die "关键包导入失败，见上面的报错"
import importlib.metadata as m
for name in ("poetry-agent-bff", "poetry-domain-mcp", "poetry-agent-worker", "fastapi", "httpx", "mcp"):
    print(f"  {name:22} {m.version(name)}")
import agent_bff.main          # noqa: F401  模块级只建 app，不起服务（run() 有 __main__ 守卫）
import poetry_domain_mcp.server  # noqa: F401
import agent_worker.app        # noqa: F401
print("  imports OK")
PY
fi

mkdir -p "${ROOT}/.data/run" "${ROOT}/.data/logs"
log "完成。**没有跑任何数据库迁移——这是设计**（Java API 是 poetry_* 唯一写入口）。"
log "接下来：./scripts/deploy/process.sh start"
