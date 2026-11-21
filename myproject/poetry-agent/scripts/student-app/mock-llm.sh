#!/usr/bin/env bash
# 本地走查:mock OpenAI 兼容网关 + 学生端 agent(LLM 模式)。两个进程都绑 127.0.0.1,Ctrl-C 同时停止。
# 不读取 student-app/agent/.env 的值:这里用的是假变量,进程环境变量会覆盖 .env 中的同名项。
#   MODE=ok|leak|garbage|empty|5xx|timeout   mock 网关的行为(默认 ok)
#   MOCK_LLM_PORT=8799  STUDENT_AGENT_PORT=8792  MOCK_LLM_SLEEP=12
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
PY="$PLATFORM_ROOT/.venv/bin/python"
[[ -x "$PY" ]] || { echo "没有 .venv:在平台根执行 uv sync" >&2; exit 2; }
MODE="${MODE:-ok}"
MOCK_PORT="${MOCK_LLM_PORT:-8799}"
AGENT_PORT="${STUDENT_AGENT_PORT:-8792}"
LOG="${MOCK_LLM_LOG:-$STUDENT_APP/agent/dev/mock_llm_requests.jsonl}"
pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

(cd "$STUDENT_APP/agent" && MOCK_LLM_PORT="$MOCK_PORT" MOCK_LLM_MODE="$MODE" MOCK_LLM_LOG="$LOG" \
  MOCK_LLM_SLEEP="${MOCK_LLM_SLEEP:-12}" exec "$PY" dev/mock_llm.py) &
pids+=($!)

(cd "$STUDENT_APP/agent" && \
  POETRY_LLM_API_BASE="http://127.0.0.1:$MOCK_PORT/v1" POETRY_LLM_API_KEY="mock-key" \
  POETRY_LLM_MODEL_PRIMARY="mock-model" POETRY_LLM_MODEL_FALLBACK="mock-model-b" \
  STUDENT_LLM_POET=1 STUDENT_AGENT_PORT="$AGENT_PORT" \
  STUDENT_BUNDLES_DIR="$CONTENT_PIPELINE/dist/bundles" PYTHONPATH="$STUDENT_APP/agent/src" \
  exec "$PY" -c 'from student_agent.main import run; run()') &
pids+=($!)

sleep 2
echo "mock 网关  http://127.0.0.1:$MOCK_PORT/v1   行为=$MODE   请求记录=$LOG"
echo "agent      http://127.0.0.1:$AGENT_PORT/agent/v1   (LLM 模式;健康检查: curl -s http://127.0.0.1:$AGENT_PORT/agent/v1/health)"
echo "例:curl -s -X POST http://127.0.0.1:$AGENT_PORT/agent/v1/turn -H 'content-type: application/json' \\"
echo "     -d '{\"bundle_hash\":\"a1a919c215d656000910a72ef2d01f8aa249f9826f8b5a82ec315f66c732f8d9\",\"work_id\":\"work-chun-wang\",\"audience\":\"JUNIOR\",\"step\":\"arrive\",\"action\":\"rephrase\",\"args\":{\"layer\":\"WORLD\"}}'"
wait
