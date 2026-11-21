#!/usr/bin/env bash
# 内容生产项目：最小连通检查（需要先 up）。不创建诗词内容，不发布。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
exec "$CONTENT_PIPELINE/tools/dev/smoke.sh" "$@"
