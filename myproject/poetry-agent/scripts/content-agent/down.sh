#!/usr/bin/env bash
# 内容生产项目：停止并移除容器（不删卷）。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
ensure_content_env
content_compose down "$@"
