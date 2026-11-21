#!/usr/bin/env bash
# 学生端一键本地预览:前端(含 /api/student/v1 演示夹具)+ agent(没有网关配置就只走脚本)。
# 不连数据库、不连 Java。Ctrl-C 同时退出两个进程。
#   STUDENT_AGENT=off make student-dev     只起前端(页面会用本机兜底回答)
#   STUDENT_API_BASE=http://host:port      把 /api/student/* 代理到真实 vvv-student
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if [[ "${STUDENT_AGENT:-on}" != "off" ]]; then
  PY="$PLATFORM_ROOT/.venv/bin/python"
  if [[ -x "$PY" ]] && "$PY" -c 'import fastapi, uvicorn, httpx' 2>/dev/null; then
    # STUDENT_BUNDLES_DIR: 让 agent 读与页面同一份已编译的夹具包(按哈希),台词编号才对得上;没编译就回落到样例包。
    (cd "$STUDENT_APP/agent" && STUDENT_BUNDLES_DIR="${STUDENT_BUNDLES_DIR:-$CONTENT_PIPELINE/dist/bundles}" \
      PYTHONPATH="$STUDENT_APP/agent/src" exec "$PY" -c 'from student_agent.main import run; run()') &
    pids+=($!)
    echo "agent: 127.0.0.1:${STUDENT_AGENT_PORT:-8765}（无网关配置时为脚本模式）"
  else
    echo "agent 没起来:找不到 $PY 或缺依赖(在平台根执行 uv sync)。前端会用本机兜底回答。" >&2
  fi
fi

cd "$STUDENT_APP/frontend"
node build.mjs
exec node serve.mjs "$@"
