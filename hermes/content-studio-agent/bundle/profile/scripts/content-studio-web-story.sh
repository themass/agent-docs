#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Content Studio Web Story — experimental renderer
#
# This is a separate path from content-studio.sh video-render. It generates a
# shareable Web Story page and preview screenshot without modifying stable MP4
# artifacts.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_DATE="${1:-$(date +%Y-%m-%d)}"
REPORT_DIR="${CONTENT_STUDIO_REPORT_DIR:-$PROFILE_DIR/reports}"
PYTHON_BIN="${CS_PYTHON:-$(command -v python3)}"
RENDERER="$PROFILE_DIR/skills/content-studio/web-story-renderer/scripts/web_story_renderer.py"

if [ ! -f "$RENDERER" ]; then
  echo "❌ Web Story renderer 不存在: $RENDERER" >&2
  exit 1
fi

export CONTENT_STUDIO_PROFILE_DIR="$PROFILE_DIR"
export HOME="${HOME:-$PROFILE_DIR/home}"

echo "🌐 生成 Content Studio Web Story — $TARGET_DATE"
echo "   稳定视频链路不会被修改"
echo "   Reports: $REPORT_DIR"
echo ""

args=("$TARGET_DATE" --report-dir "$REPORT_DIR")
args+=(--visual-project-limit "${CONTENT_STUDIO_WEB_STORY_VISUAL_LIMIT:-5}")
if [ "${CONTENT_STUDIO_WEB_STORY_SKIP_RECORD:-0}" != "1" ]; then
  args+=(--record-video)
fi
if [ "${CONTENT_STUDIO_WEB_STORY_SKIP_AUDIO:-0}" != "1" ]; then
  args+=(--with-audio)
fi

"$PYTHON_BIN" "$RENDERER" "${args[@]}"
