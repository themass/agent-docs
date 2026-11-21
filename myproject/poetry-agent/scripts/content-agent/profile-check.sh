#!/usr/bin/env bash
# 内容生产项目：校验 Soul / Skill / MCP 策略（纯静态，不连任何服务）。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
exec python3 "$CONTENT_PIPELINE/tools/dev/check_profile.py" "$@"
