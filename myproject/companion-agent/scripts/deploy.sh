#!/usr/bin/env bash
# 把一台机器备好并把服务装上去：缺什么装什么，装 Python 依赖，跑数据库迁移。**不启动任何进程**
# ——那是 process.sh 的事，单独一步，这样构建结果能在切过去之前先看一眼。
#
#   ./scripts/deploy.sh                    # 全部
#   ./scripts/deploy.sh --env-only         # 只备环境，不部署
#   ./scripts/deploy.sh --skip-voice       # 不装语音依赖（只跑文字）
#   ./scripts/deploy.sh --skip-migrate     # 不动数据库
#
# 装的东西都在当前用户家目录里，不用 sudo、不改 shell 配置：
#   uv          缺了就装到 ~/.local/bin
#   Python 3.12 由 uv 私有安装（系统 python3 是 3.8，不动它）
# 需要管理员的只有 curl、tar，缺了会在下载任何东西之前一次报全。
#
#   CA_DEPLOY_HEARTBEAT_SEC=30   长步骤每隔一段时间打印一行（防 SSH 断开）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${CA_VENV:-${ROOT}/.venv}"
HEARTBEAT="${CA_DEPLOY_HEARTBEAT_SEC:-30}"

DO_VOICE=true
DO_MIGRATE=true
ENV_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --skip-voice) DO_VOICE=false ;;
    --skip-migrate) DO_MIGRATE=false ;;
    --env-only) ENV_ONLY=true ;;
    -h | --help) sed -n '2,20p' "$0"; exit 0 ;;
    *) printf '[deploy] ERROR: 未知参数: %s\n' "$arg" >&2; exit 1 ;;
  esac
done

log() { printf '[deploy] %s\n' "$*"; }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

# 长命令加心跳：一分钟不出声的下载和“卡死”在 SSH 里长得一模一样。
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
       管理员执行一次：sudo apt-get install -y ${missing[*]}"
fi

# 2. uv。
if ! command -v uv >/dev/null 2>&1; then
  if [[ -x "${HOME}/.local/bin/uv" ]]; then
    export PATH="${HOME}/.local/bin:${PATH}"
  else
    log "安装 uv 到 ~/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | sh || die "uv 装不上；可能是网络，或换 CA_UV_INSTALLER_URL 镜像"
    export PATH="${HOME}/.local/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || die "uv 装完仍找不到，检查 ~/.local/bin 是否在 PATH 里"
  fi
fi
log "uv:      $(uv --version 2>&1)"

# 3. Python 3.12。项目要求 >=3.12,<3.13，系统的 python3 通常更老。
beat "python 3.12" uv python install 3.12 || die "uv 装不了 Python 3.12"
PYTHON="$(uv python find 3.12)" || die "找不到 uv 装的 3.12"
log "python:  ${PYTHON} ($("$PYTHON" -V 2>&1))"

if [[ "$ENV_ONLY" == true ]]; then
  log "环境就绪 — 什么都没部署（--env-only）"
  exit 0
fi

# 4. 先做不联网的检查：缺 .env 时不该先下载几百兆依赖再失败。
[[ -f "${ROOT}/.env" ]] || die "缺 ${ROOT}/.env。从 .env.example 复制一份再填值（权限 600；不要入库）"
[[ "$(stat -c '%a' "${ROOT}/.env" 2>/dev/null || echo 600)" =~ ^[0-7]?[04]00$ ]] \
  || log "提示：${ROOT}/.env 权限不是 600，里面有密钥，建议 chmod 600 .env"

[[ -f "${ROOT}/uv.lock" ]] || die "缺 uv.lock。在源码目录跑 uv lock 并提交；没有锁文件就装不出确定的依赖版本"

# 5. 依赖。--frozen：严格按 uv.lock 装，lock 和 pyproject 不一致就报错而不是悄悄重新解析。
#    --no-editable：把本项目也装成普通包，服务代码从 site-packages 读，
#    这样部署目录里改一个 .py 不会改掉正在跑的进程（改代码要走发布流程）。
extra_args=()
if [[ "$DO_VOICE" == true ]]; then
  extra_args+=(--extra livekit)
fi
log "安装 Python 依赖到 ${VENV}${DO_VOICE:+（含语音）}"
beat "uv sync" env UV_PROJECT_ENVIRONMENT="$VENV" uv sync --frozen --no-dev --no-editable "${extra_args[@]}"

log "核对关键包与导入"
"${VENV}/bin/python" - <<'PY' || die "关键包导入失败，见上面的报错"
import importlib.metadata as m
for name in ("deerflow-harness", "deerflow-extension-api", "langgraph", "fastapi", "psycopg"):
    print(f"  {name:24} {m.version(name)}")
import deerflow, companion  # noqa: F401
print("  imports OK")
PY

# 6. 数据库迁移。alembic 读的是项目根目录的 alembic.ini 和 .env。
if [[ "$DO_MIGRATE" == true ]]; then
  log "执行数据库迁移（alembic upgrade head）"
  (cd "$ROOT" && PYTHONPATH=src beat "alembic" "$VENV/bin/python" -m alembic upgrade head) \
    || die "迁移失败。库连不上，或 schema 与 baseline 不一致，见上面的报错"
fi

mkdir -p "${ROOT}/.data/run" "${ROOT}/.data/logs"
log "完成。接下来：./scripts/process.sh restart"
