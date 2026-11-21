#!/usr/bin/env bash
# 内容生产项目：构建并后台启动（agent-bff + poetry-domain-mcp；加 --profile deerflow 才启动 DeerFlow）。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
ensure_content_env
content_compose up --build -d "$@"
