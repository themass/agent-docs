#!/usr/bin/env bash
# 素材任务体系入口:转发到 student-app/production/tools/prod.mjs。零网络、不碰数据库、不调用 git。
# 用法: prod.sh <gen|list|state|check|publish|placeholder|registry-check|bundle-refs|report> [参数...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
command -v node >/dev/null || { echo "需要 node(>=18)"; exit 127; }
exec node "$ROOT/student-app/production/tools/prod.mjs" "$@"
