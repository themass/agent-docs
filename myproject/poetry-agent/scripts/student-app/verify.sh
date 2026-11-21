#!/usr/bin/env bash
# 学生端静态检查与构建。不跑任何测试套件,不连数据库,不需要网络。
#   运行时内核/前端/agent 的测试文件已写好,留到最后统一执行:见 docs/handoff/B.md 的"最后一次性运行"。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
echo "== 构建(共享内核 + platform-web → dist)";  (cd "$STUDENT_APP/frontend" && node build.mjs)
echo "== 前端静态检查";                             (cd "$STUDENT_APP/frontend" && node scripts/check.mjs)
echo "== agent: ruff + py_compile"
if [[ -x "$PLATFORM_ROOT/.venv/bin/ruff" ]]; then
  "$PLATFORM_ROOT/.venv/bin/ruff" check "$STUDENT_APP/agent"
  "$PLATFORM_ROOT/.venv/bin/python" -m py_compile "$STUDENT_APP"/agent/src/student_agent/*.py "$STUDENT_APP"/agent/tests/*.py
else
  echo "  跳过:没有 .venv(在平台根执行 uv sync)" >&2
fi
echo "== 脚本语法";                                 bash -n "$PLATFORM_ROOT/scripts/student-app/dev.sh" && bash -n "$0"
echo "ok"
