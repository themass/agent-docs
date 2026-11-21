#!/usr/bin/env bash
# 所有启动脚本共用的路径变量。用法：source "$(dirname "$0")/../lib.sh"
# 这里只定义路径与两个小函数，不做任何有副作用的事。

PLATFORM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 内容生产项目：frontend / agent / pipeline / deploy
CONTENT_AGENT="$PLATFORM_ROOT/content-agent"
CONTENT_PIPELINE="$CONTENT_AGENT/pipeline"   # contracts · scene-runtime · tools · dist
CONTENT_DEPLOY="$CONTENT_AGENT/deploy"       # compose.yaml · .env · k8s · upstream(DeerFlow)

# 学生端项目：frontend / agent / runtime
STUDENT_APP="$PLATFORM_ROOT/student-app"
STUDENT_RUNTIME="$STUDENT_APP/runtime"       # contracts · scene-runtime · platform-web

content_compose() {
  docker compose --env-file "$CONTENT_DEPLOY/.env" -f "$CONTENT_DEPLOY/compose.yaml" "$@"
}

ensure_content_env() {
  [[ -f "$CONTENT_DEPLOY/.env" ]] || cp "$CONTENT_DEPLOY/.env.example" "$CONTENT_DEPLOY/.env"
}
