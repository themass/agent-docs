#!/usr/bin/env bash
# 内容生产项目：跟随日志。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
ensure_content_env
content_compose logs -f --tail=200 "$@"
