#!/usr/bin/env bash
# 内容生产项目：首次准备环境（依赖 + 配置校验）。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
ensure_content_env
cd "$PLATFORM_ROOT"
uv sync --all-packages --all-groups
python3 "$CONTENT_PIPELINE/tools/dev/check_profile.py"
printf 'Bootstrap complete. Configure %s before starting a DeerFlow profile.\n' "content-agent/deploy/.env"
