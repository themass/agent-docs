#!/usr/bin/env bash
# Shared path helpers for Content Studio skills and orchestrator scripts.

if [ -z "${CONTENT_STUDIO_PROFILE_DIR:-}" ] && [ -n "${HERMES_HOME:-}" ]; then
  CONTENT_STUDIO_PROFILE_DIR="$HERMES_HOME"
fi

if [ -z "${CONTENT_STUDIO_PROFILE_DIR:-}" ]; then
  _paths_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  _candidate="$(cd "$_paths_lib/../../.." && pwd)"
  if [ -f "$_candidate/SOUL.md" ] && [ -d "$_candidate/reports" ]; then
    CONTENT_STUDIO_PROFILE_DIR="$_candidate"
  fi
  unset _paths_lib _candidate
fi

CONTENT_STUDIO_PROFILE_DIR="${CONTENT_STUDIO_PROFILE_DIR:-$HOME/.hermes/profiles/content-studio}"
CS_PROFILE_DIR="$CONTENT_STUDIO_PROFILE_DIR"
CS_REPORT_DIR="$CS_PROFILE_DIR/reports"
CS_SKILL_ROOT="$CS_PROFILE_DIR/skills/content-studio"

CS_DAILY_TRENDING_DIR="$CS_SKILL_ROOT/github-daily"
CS_VIDEO_PIPELINE_DIR="$CS_SKILL_ROOT/video-pipeline"
CS_MONEYPRINTER_VIDEO_DIR="$CS_SKILL_ROOT/moneyprinter-video"
CS_REPORT_LIBRARY_DIR="$CS_SKILL_ROOT/knowledge-library"
CS_COMMUNITY_PULSE_DIR="$CS_SKILL_ROOT/community-pulse"
CS_VIDEO_SCRIPT_DIR="$CS_SKILL_ROOT/video-script-generator"

CS_GENERATE_DAILY_REPORT="$CS_DAILY_TRENDING_DIR/scripts/generate_daily_report.py"
CS_TRENDING_SNAPSHOT="$CS_DAILY_TRENDING_DIR/scripts/github_trending_snapshot.py"
CS_VIDEO_GENERATOR="$CS_VIDEO_PIPELINE_DIR/scripts/video_generator.py"
CS_MONEYPRINTER_VIDEO="$CS_MONEYPRINTER_VIDEO_DIR/scripts/moneyprinter_video.py"
CS_WEB_STORY_RENDERER="$CS_SKILL_ROOT/web-story-renderer/scripts/web_story_renderer.py"
CS_WEB_STORY_SCRIPT="$CS_PROFILE_DIR/scripts/content-studio-web-story.sh"
CS_REPORT_INDEX="$CS_REPORT_LIBRARY_DIR/scripts/report_index.py"
CS_REPORT_DISPATCHER="$CS_REPORT_LIBRARY_DIR/scripts/report_dispatcher.py"
CS_OPEN_NOTEBOOK_SYNC="$CS_REPORT_LIBRARY_DIR/scripts/open_notebook_sync.py"
CS_OPEN_NOTEBOOK_QUERY="$CS_REPORT_LIBRARY_DIR/scripts/open_notebook_query.py"
CS_OPEN_NOTEBOOK_ROOT="${OPEN_NOTEBOOK_ROOT:-/Users/gqli/work/deepagents/open-notebook}"
CS_COMMUNITY_VALIDATE="$CS_COMMUNITY_PULSE_DIR/scripts/validate_community_pulse.py"
CS_COMMUNITY_GENERATOR="$CS_COMMUNITY_PULSE_DIR/scripts/generate_community_pulse.py"
CS_VIDEO_SCRIPT_FALLBACK="$CS_VIDEO_SCRIPT_DIR/scripts/generate_video_script_fallback.py"

# Python for all content-studio skill scripts.
# Override: export CONTENT_STUDIO_PYTHON=/path/to/python3
# Default: monorepo venv → CONTENT_STUDIO_PYTHON → pyenv → python3
_DEEPAGENTS_PYTHON_DEFAULT="/Users/gqli/work/deepagents/venv/bin/python3"
_ga_resolve_python() {
  if [ -n "${CONTENT_STUDIO_PYTHON:-}" ] && [ -x "$CONTENT_STUDIO_PYTHON" ]; then
    printf '%s\n' "$CONTENT_STUDIO_PYTHON"
    return 0
  fi
  if [ -x "$_DEEPAGENTS_PYTHON_DEFAULT" ]; then
    printf '%s\n' "$_DEEPAGENTS_PYTHON_DEFAULT"
    return 0
  fi
  local candidate=""
  for candidate in \
    "${PYENV_ROOT:+$PYENV_ROOT/shims/python3}" \
    "$HOME/.pyenv/shims/python3" \
    "$(command -v python3.12 2>/dev/null || true)" \
    "$(command -v python3.11 2>/dev/null || true)" \
    "$(command -v python3 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

CS_PYTHON="$(_ga_resolve_python || true)"
unset -f _ga_resolve_python 2>/dev/null || true
if [ -z "$CS_PYTHON" ]; then
  echo "❌ 未找到可用的 Python。请安装 pyenv/python3.12 或设置 CONTENT_STUDIO_PYTHON" >&2
  exit 1
fi
export CS_PYTHON CONTENT_STUDIO_PYTHON="${CONTENT_STUDIO_PYTHON:-$CS_PYTHON}"
