#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Content Studio — 手动触发后门
#
# 用法:
#   ./content-studio.sh daily              # 触发日报（当日覆盖）
#   ./content-studio.sh radar              # 触发生产级工具雷达
#   ./content-studio.sh weekly             # 触发周报
#   ./content-studio.sh video              # 触发视频脚本
#   ./content-studio.sh latest-video       # 显示最新视频路径
#   ./content-studio.sh open-latest-video  # 打开最新视频
#   ./content-studio.sh library            # 刷新并查看报告库索引
#   ./content-studio.sh notebook-sync      # 同步报告到 Open Notebook
#   ./content-studio.sh all                # 全部触发
#   ./content-studio.sh daily 2026-05-29   # 指定日期
#
# 依赖: hermes CLI (hermes-agent/.venv/bin/hermes)
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE_DIR="$(dirname "$SCRIPT_DIR")"
_env_file="$PROFILE_DIR/.env"
if [ -f "$_env_file" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$_env_file"
  set +a
fi
unset _env_file
# shellcheck source=../skills/content-studio/lib/paths.sh
source "$PROFILE_DIR/skills/content-studio/lib/paths.sh"
ACTION="${1:-help}"
TARGET_DATE="${2:-$(date +%Y-%m-%d)}"
REPORT_DIR="$PROFILE_DIR/reports"

HERMES_BIN="${HERMES_BIN:-/Users/gqli/work/deepagents/venv/bin/hermes}"

# 如果 monorepo venv 没有 hermes，回退到 _hermes-cli.sh
if [ ! -x "$HERMES_BIN" ]; then
  HERMES_BIN="/Users/gqli/work/deepagents/hermes-dev/_hermes-cli.sh"
fi

if [ -z "$HERMES_BIN" ] && [[ "$ACTION" != "library" && "$ACTION" != "reports" && "$ACTION" != "index" && "$ACTION" != "notebook-sync" && "$ACTION" != "open-notebook-sync" && "$ACTION" != "notebook-query" && "$ACTION" != "open-notebook-query" && "$ACTION" != "help" && "$ACTION" != "--help" && "$ACTION" != "-h" ]]; then
  echo "❌ 找不到 hermes CLI。请设置 HERMES_BIN 环境变量或确保 hermes 在 PATH 中。"
  exit 1
fi

export HERMES_HOME="$PROFILE_DIR"

YEAR="$(echo "$TARGET_DATE" | cut -d- -f1)"
MONTH="$(echo "$TARGET_DATE" | cut -d- -f2)"
mkdir -p "$REPORT_DIR/$YEAR/$MONTH"

dispatch_report() {
  local report_file="$1"
  if [ -f "$CS_REPORT_DISPATCHER" ] && [ -f "$report_file" ]; then
    "$CS_PYTHON" "$CS_REPORT_DISPATCHER" "$report_file" --report-dir "$REPORT_DIR" --stdout || true
  elif [ -f "$CS_REPORT_INDEX" ]; then
    "$CS_PYTHON" "$CS_REPORT_INDEX" --report-dir "$REPORT_DIR" || true
  fi
}

require_nonempty_file() {
  local file="$1"
  local label="$2"
  if [ ! -s "$file" ]; then
    echo "❌ $label 未生成或为空: $file"
    return 1
  fi
}

cleanup_empty_file() {
  local file="$1"
  if [ -f "$file" ] && [ ! -s "$file" ]; then
    rm -f "$file"
    echo "🧹 已删除空文件: $file"
  fi
}

CS_PROGRESS_LOG="${PROFILE_DIR}/logs/sop-latest.log"
mkdir -p "$(dirname "$CS_PROGRESS_LOG")"

# Machine-readable progress for Hermes / sop-status (grep CONTENT_STUDIO_PROGRESS).
cs_progress() {
  local pipeline="$1"
  local stage="$2"
  local total="$3"
  local status="$4"
  local message="$5"
  local artifact="${6:-}"
  local ts
  ts="$(date '+%Y-%m-%dT%H:%M:%S')"
  echo "CONTENT_STUDIO_PROGRESS date=${TARGET_DATE} pipeline=${pipeline} stage=${stage}/${total} status=${status} msg=${message} artifact=${artifact}"
  case "$status" in
    ok|done) echo "✅ [${pipeline}] Stage ${stage}/${total}: ${message}" ;;
    fail|error) echo "❌ [${pipeline}] Stage ${stage}/${total}: ${message}" >&2 ;;
    *) echo "⏳ [${pipeline}] Stage ${stage}/${total}: ${message}" ;;
  esac
  {
    echo "${ts} CONTENT_STUDIO_PROGRESS date=${TARGET_DATE} pipeline=${pipeline} stage=${stage}/${total} status=${status} msg=${message} artifact=${artifact}"
  } >>"$CS_PROGRESS_LOG"
}

show_sop_status() {
  local y m
  y="$(echo "$TARGET_DATE" | cut -d- -f1)"
  m="$(echo "$TARGET_DATE" | cut -d- -f2)"
  local base="${REPORT_DIR}/${y}/${m}/${TARGET_DATE}"
  echo "📊 Content Studio 进度 — $TARGET_DATE"
  echo "   日志: $CS_PROGRESS_LOG"
  echo ""
  if [ -f "$CS_PROGRESS_LOG" ]; then
    echo "—— 最近进度行 ——"
    grep "date=${TARGET_DATE}" "$CS_PROGRESS_LOG" 2>/dev/null | tail -15 || true
    echo ""
  fi
  echo "—— 产出文件 ——"
  for f in \
    "${base}.md" \
    "${base}-video-script.md" \
    "${base}-video.mp4" \
    "${base}-video-publish.md" \
    "${base}-mpt-video.mp4" \
    "${base}-mpt-video-publish.md"; do
    if [ -f "$f" ]; then
      ls -lh "$f"
    else
      echo "  （无）$(basename "$f")"
    fi
  done
}

MPT_RENDER_LOG="${PROFILE_DIR}/logs/mpt-render-${TARGET_DATE}.log"
MPT_BG_PID_FILE="${PROFILE_DIR}/logs/mpt-render-${TARGET_DATE}.pid"

show_mpt_status() {
  local y m
  y="$(echo "$TARGET_DATE" | cut -d- -f1)"
  m="$(echo "$TARGET_DATE" | cut -d- -f2)"
  local base="${REPORT_DIR}/${y}/${m}/${TARGET_DATE}"
  local video_file="${base}-mpt-video.mp4"
  local sidecar="${video_file%.mp4}.mpt-task.json"

  echo "📊 MPT 进度 — $TARGET_DATE"
  echo ""

  if curl -sf -o /dev/null -w "MPT API HTTP %{http_code}\n" "${MONEYPRINTER_BASE_URL:-http://127.0.0.1:8082}/docs" 2>/dev/null; then
    :
  else
    echo "❌ MPT API 不可达 (${MONEYPRINTER_BASE_URL:-http://127.0.0.1:8082})"
  fi

  if [ -f "$sidecar" ]; then
    echo "—— sidecar（可 video-mpt-resume）——"
    cat "$sidecar"
    echo ""
  else
    echo "（无 sidecar — 未提交或已完成）"
    echo ""
  fi

  if [ -f "$MPT_BG_PID_FILE" ]; then
    local bg_pid
    bg_pid="$(cat "$MPT_BG_PID_FILE" 2>/dev/null || true)"
    if [ -n "$bg_pid" ] && kill -0 "$bg_pid" 2>/dev/null; then
      echo "🔄 后台渲染进行中 pid=$bg_pid  日志: $MPT_RENDER_LOG"
    else
      echo "（后台 pid 文件存在但进程已结束: $MPT_BG_PID_FILE）"
    fi
    echo ""
  fi

  if [ -f "$MPT_RENDER_LOG" ]; then
    echo "—— 后台日志末尾 ——"
    tail -20 "$MPT_RENDER_LOG" 2>/dev/null || true
    echo ""
  fi

  echo "—— 产出 ——"
  for f in \
    "${base}-video-script.md" \
    "$video_file" \
    "${base}-mpt-video-publish.md" \
    "${video_file%.mp4}-cover.jpg"; do
    if [ -f "$f" ]; then
      ls -lh "$f"
    else
      echo "  （无）$(basename "$f")"
    fi
  done

  if [ -f "$CS_PROGRESS_LOG" ]; then
    echo ""
    echo "—— mpt-video 进度行 ——"
    grep "date=${TARGET_DATE}" "$CS_PROGRESS_LOG" 2>/dev/null | grep "pipeline=mpt-video" | tail -8 || true
  fi
}

render_mpt_video_resume() {
  local script_file="$1"
  local video_file="$2"
  local mpt_timeout="${MONEYPRINTER_TIMEOUT:-1200}"
  local mpt_poll="${MONEYPRINTER_POLL_SECONDS:-10}"

  cs_progress "mpt-video" 2 3 "running" "续轮询 MPT 任务（sidecar）" "$video_file"
  echo "🔁 video-mpt-resume — $TARGET_DATE"

  if ! "$CS_PYTHON" -u "$CS_MONEYPRINTER_VIDEO" \
    --script "$script_file" \
    --output "$video_file" \
    --timeout "$mpt_timeout" \
    --poll-seconds "$mpt_poll" \
    --resume 2>&1; then
    cs_progress "mpt-video" 2 3 "fail" "MPT resume 失败" "$video_file"
    return 1
  fi

  if ! require_nonempty_file "$video_file" "MoneyPrinterTurbo 视频"; then
    cs_progress "mpt-video" 2 3 "fail" "MPT resume 后仍无 mp4" "$video_file"
    return 1
  fi
  cs_progress "mpt-video" 2 3 "ok" "MPT 视频已生成（resume）" "$video_file"
  return 0
}

run_video_mpt_bg() {
  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  if ! require_nonempty_file "$script_file" "视频脚本"; then
    echo "❌ 先运行: content-studio.sh video $TARGET_DATE 或 video-mpt-pipeline"
    return 1
  fi

  mkdir -p "$(dirname "$MPT_RENDER_LOG")"
  if [ -f "$MPT_BG_PID_FILE" ]; then
    local old_pid
    old_pid="$(cat "$MPT_BG_PID_FILE" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
      echo "⚠️  已有后台 MPT 任务 pid=$old_pid，日志: $MPT_RENDER_LOG"
      echo "   查进度: content-studio.sh mpt-status $TARGET_DATE"
      return 0
    fi
  fi

  cs_progress "mpt-video" 2 3 "running" "后台 MPT 渲染已启动" "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video.mp4"
  echo "🚀 后台启动 video-mpt — $TARGET_DATE"
  echo "   日志: $MPT_RENDER_LOG"

  nohup "$0" video-mpt "$TARGET_DATE" >>"$MPT_RENDER_LOG" 2>&1 &
  echo $! >"$MPT_BG_PID_FILE"
  echo "   pid=$(cat "$MPT_BG_PID_FILE")"
  echo "   查进度: $0 mpt-status $TARGET_DATE"
}

run_video_mpt_resume() {
  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local video_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video.mp4"
  local publish_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video-publish.md"

  if ! render_mpt_video_resume "$script_file" "$video_file"; then
    echo "❌ video-mpt-resume 失败" >&2
    return 1
  fi

  show_mpt_video_package "$script_file" "$video_file" "$publish_file"
  cs_progress "mpt-video" 3 3 "ok" "发布素材包已输出" "$publish_file"
  echo "💡 预览视频：open $video_file"
}

run_video_hybrid_status() {
  local hybrid_script="$PROFILE_DIR/skills/content-studio/hybrid-video/scripts/hybrid_video.py"
  if [ ! -f "$hybrid_script" ]; then
    echo "❌ hybrid-video 脚本不存在: $hybrid_script"
    return 1
  fi
  "$CS_PYTHON" "$hybrid_script" status --date "$TARGET_DATE" --report-dir "$REPORT_DIR"
}

run_video_hybrid() {
  local hybrid_script="$PROFILE_DIR/skills/content-studio/hybrid-video/scripts/hybrid_video.py"
  if [ ! -f "$hybrid_script" ]; then
    echo "❌ hybrid-video 脚本不存在: $hybrid_script"
    return 1
  fi
  echo "🎬 Hybrid 视频 — $TARGET_DATE"
  echo "   第三条独立链路：不覆盖 sop/mpt 现有视频"
  echo "   Stage 1: 读取已有 video-script.md 生成 hybrid spec"
  echo "   Stage 2: 生成 cards / github placeholder / ai-broll fallback"
  echo "   Stage 3: 合成 v1 hybrid mp4"
  echo ""
  "$CS_PYTHON" "$hybrid_script" render --date "$TARGET_DATE" --report-dir "$REPORT_DIR"
  echo ""
  run_video_hybrid_status
}

run_video_hybrid_pipeline() {
  local hybrid_script="$PROFILE_DIR/skills/content-studio/hybrid-video/scripts/hybrid_video.py"
  if [ ! -f "$hybrid_script" ]; then
    echo "❌ hybrid-video 脚本不存在: $hybrid_script"
    return 1
  fi
  echo "🎬 Hybrid 完整 Pipeline — $TARGET_DATE"
  echo "   第三条独立链路：不覆盖 sop/mpt 现有视频"
  echo "   Stage 1: 读取已有 video-script.md 生成 hybrid spec"
  echo "   Stage 2: 生成 cards / github placeholder / ai-broll fallback"
  echo "   Stage 3: 合成 v1 hybrid mp4"
  echo ""
  "$CS_PYTHON" "$hybrid_script" pipeline --date "$TARGET_DATE" --report-dir "$REPORT_DIR"
  echo ""
  run_video_hybrid_status
}

run_hermes_chat() {
  local skill="$1"
  local prompt="$2"
  local timeout_seconds="${CONTENT_STUDIO_CHAT_TIMEOUT:-75}"
  HERMES_BIN="$HERMES_BIN" "$CS_PYTHON" - "$timeout_seconds" "$skill" "$prompt" <<'PY'
from __future__ import annotations

import os
import subprocess
import sys

timeout = int(sys.argv[1])
skill = sys.argv[2]
prompt = sys.argv[3]
cmd = [os.environ["HERMES_BIN"], "chat", "-s", skill, "-Q", "-q", prompt]
try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
except subprocess.TimeoutExpired as exc:
    if exc.stdout:
        sys.stdout.write(exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(errors="replace"))
    if exc.stderr:
        sys.stderr.write(exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(errors="replace"))
    print(f"⚠️  Hermes chat 超时（{timeout}s）: {skill}", file=sys.stderr)
    sys.exit(124)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
PY
}

generate_video_script_fallback() {
  local daily_report="$1"
  local script_file="$2"
  "$CS_PYTHON" "$CS_VIDEO_SCRIPT_FALLBACK" "$daily_report" "$script_file" "$TARGET_DATE"
}

validate_community_pulse() {
  local daily_report="$1"
  local pulse_file="$2"
  "$CS_PYTHON" "$CS_COMMUNITY_VALIDATE" "$daily_report" "$pulse_file"
}

run_daily() {
  echo "📊 触发日报 — $TARGET_DATE"
  echo "   输出: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
  echo ""

  "$CS_PYTHON" "$CS_GENERATE_DAILY_REPORT" \
    --date "$TARGET_DATE" \
    --report-dir "$REPORT_DIR" \
    --limit 25 || {
      if [ -s "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md" ]; then
        echo "⚠️  GitHub Trending 抓取失败，复用已存在的非空日报继续执行: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
      else
        return 1
      fi
    }

  if require_nonempty_file "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md" "日报"; then
    echo ""
    echo "✅ 日报已生成: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
    dispatch_report "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
    if [ "${CONTENT_STUDIO_SKIP_AUTO_VIDEO:-0}" != "1" ]; then
      echo ""
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      echo "🎬 自动触发视频 Pipeline…"
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      echo ""
      if ! run_video_pipeline; then
        echo "❌ 日报后的视频 Pipeline 失败" >&2
        return 1
      fi
    fi
  else
    echo ""
    echo "⚠️  日报文件未找到，请检查 Hermes 输出日志"
    return 1
  fi
}

run_radar() {
  echo "🧭 触发生产级工具雷达 — $TARGET_DATE"
  echo "   输出: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-production-radar.md"
  echo ""

  run_hermes_chat tool-radar \
    "今天是 ${TARGET_DATE}。请执行 tool-radar skill 的完整流程，检索生产级或非常有用的 GitHub 工具和项目，生成工具雷达报告。必须将报告写入 ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-production-radar.md（已有则覆盖）。" \
    2>&1 || true

  if require_nonempty_file "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-production-radar.md" "工具雷达"; then
    echo ""
    echo "✅ 工具雷达已生成: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-production-radar.md"
    dispatch_report "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-production-radar.md"
  else
    echo ""
    echo "⚠️  工具雷达文件未找到，请检查 Hermes 输出日志"
    return 1
  fi
}

run_weekly() {
  echo "📈 触发周报 — $TARGET_DATE"
  echo "   输出: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-weekly.md"
  echo ""

  run_hermes_chat weekly-digest \
    "今天是 ${TARGET_DATE}。请执行 weekly-digest skill 的完整流程，生成本周 GitHub 深度分析周报。必须包含本周去重后的项目总览列表和简介。将报告写入 ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-weekly.md（已有则覆盖）。" \
    2>&1 || true

  if require_nonempty_file "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-weekly.md" "周报"; then
    echo ""
    echo "✅ 周报已生成: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-weekly.md"
    dispatch_report "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-weekly.md"
  else
    echo ""
    echo "⚠️  周报文件未找到，请检查 Hermes 输出日志"
    return 1
  fi
}

run_video() {
  echo "🎬 触发视频脚本 — $TARGET_DATE"
  echo "   输出: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  echo ""

  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local daily_report="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
  local weekly_report
  local source_prompt
  if [ -f "$daily_report" ]; then
    source_prompt="基于今日日报（${daily_report}）生成日报短视频脚本，项目必须严格限制在日报 GitHub Trending Top 10 内"
  else
    weekly_report="$(find "$REPORT_DIR" -name "*-weekly.md" -type f | sort | tail -1)"
    if [ -z "$weekly_report" ]; then
      echo "❌ 找不到日报或周报，视频脚本生成中止"
      return 1
    fi
    source_prompt="基于最近一期周报（${weekly_report}）生成周报深度视频脚本"
  fi

  run_hermes_chat video-script-generator \
    "今天是 ${TARGET_DATE}。请按 video-script-generator Skill 的「技术趋势栏目主编」模式，${source_prompt}。不要做普通项目安利，必须输出本期主题 thesis、入选项目叙事链、完整口播文本、分镜表、小红书发布素材和质量自检。开场第一句必须是行业判断，不要用「哈喽大家」；每个项目必须有链上角色；完整口播文本不要写（开场）（第一个）【结尾】等舞台标记。将脚本写入 ${script_file}（已有则覆盖）。" \
    2>&1 || true

  if require_nonempty_file "$script_file" "视频脚本"; then
    echo ""
    echo "✅ 视频脚本已生成: $script_file"
    dispatch_report "$script_file"
  else
    echo ""
    echo "⚠️  视频脚本文件未找到，请检查 Hermes 输出日志"
    return 1
  fi
}

render_video_assets() {
  local script_file="$1"
  local video_file="$2"
  local daily_report="$3"

  cs_progress "sop-video" 2 3 "running" "TTS + GitHub 页面滚动渲染（约 2-8 分钟）" "$video_file"
  echo "⏳ Stage 2: 生成视频（可能需要 2-8 分钟）…"
  echo "🐍 Python: $CS_PYTHON ($("$CS_PYTHON" --version 2>&1))"
  if [ -d "$PROFILE_DIR/home" ]; then
    export HOME="$PROFILE_DIR/home"
    echo "🏠 Playwright HOME: $HOME"
  fi
  local audio_args=()
  local tts_config="${CONTENT_STUDIO_TTS_CONFIG:-$PROFILE_DIR/config/tts-providers.yaml}"
  export CONTENT_STUDIO_TTS_CONFIG="$tts_config"
  if [ -n "${CONTENT_STUDIO_VIDEO_AUDIO_FILE:-}" ]; then
    audio_args=(--audio-file "$CONTENT_STUDIO_VIDEO_AUDIO_FILE")
    echo "🎙️  使用固定音频: $CONTENT_STUDIO_VIDEO_AUDIO_FILE"
  elif [ "${CONTENT_STUDIO_FORCE_PLACEHOLDER_AUDIO:-}" = "1" ] && [ -f "$PROFILE_DIR/audio_cache/github-video-placeholder.mp3" ]; then
    audio_args=(--audio-file "$PROFILE_DIR/audio_cache/github-video-placeholder.mp3")
    echo "🎙️  强制使用占位音频（MVP 验证）: $PROFILE_DIR/audio_cache/github-video-placeholder.mp3"
  elif [ -f "$PROFILE_DIR/audio_cache/github-video-placeholder.mp3" ] && [ -z "${VOLCENGINE_APP_ID:-}" ] && [ ! -s "$tts_config" ]; then
    audio_args=(--audio-file "$PROFILE_DIR/audio_cache/github-video-placeholder.mp3")
    echo "🎙️  使用占位音频（MVP 验证）: $PROFILE_DIR/audio_cache/github-video-placeholder.mp3"
  elif [ -s "$tts_config" ]; then
    echo "🎙️  使用 TTS 配置: $tts_config"
  fi
  local video_cmd=(
    "$CS_PYTHON" -u "$CS_VIDEO_GENERATOR"
    --script "$script_file"
    --output "$video_file"
    --engine fallback
    --tts auto
    --source-report "$daily_report"
    --source-project-limit 10
    --visual-project-limit 5
  )
  if [ "${#audio_args[@]}" -gt 0 ]; then
    video_cmd+=("${audio_args[@]}")
  fi
  if ! "${video_cmd[@]}" 2>&1; then
    cleanup_empty_file "$video_file"
    cleanup_empty_file "${video_file%.mp4}-cover.jpg"
    cs_progress "sop-video" 2 3 "fail" "GitHub 页面滚动渲染失败" "$video_file"
    echo "❌ 视频生成失败：GitHub 页面滚动方案未成功，未输出视频文件" >&2
    echo "   排查：确认 Playwright Chromium 已安装在 \$PROFILE_DIR/home，且可访问 github.com" >&2
    echo "   手动重试：$CS_PYTHON -u $CS_VIDEO_GENERATOR --script $script_file --output $video_file --engine fallback --source-report $daily_report" >&2
    return 1
  fi

  if ! require_nonempty_file "$video_file" "视频"; then
    cleanup_empty_file "$video_file"
    cleanup_empty_file "${video_file%.mp4}-cover.jpg"
    cs_progress "sop-video" 2 3 "fail" "视频文件未生成" "$video_file"
    return 1
  fi
  cs_progress "sop-video" 2 3 "ok" "视频已生成" "$video_file"
}

show_video_package() {
  local script_file="$1"
  local video_file="$2"
  local publish_file="$3"

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📦 视频素材包"
  [ -s "$video_file" ]   && echo "  📹 视频  : $video_file"   || echo "  📹 视频  : （待生成）$video_file"
  [ -f "$script_file" ]  && echo "  📝 脚本  : $script_file"
  [ -f "$publish_file" ] && echo "  📋 发布  : $publish_file"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  if [ -f "$publish_file" ]; then
    echo "👉 发布指引："
    head -40 "$publish_file"
    echo ""
  fi
}

render_web_story_page() {
  if [ "${CONTENT_STUDIO_SKIP_WEB_STORY:-0}" = "1" ]; then
    echo "⏭️  跳过 Web Story 页面（CONTENT_STUDIO_SKIP_WEB_STORY=1）"
    return 0
  fi
  if [ ! -f "$CS_WEB_STORY_RENDERER" ]; then
    echo "⚠️  Web Story 渲染器不存在，跳过页面生成: $CS_WEB_STORY_RENDERER" >&2
    return 0
  fi

  local page_dir="${REPORT_DIR}/${YEAR}/${MONTH}/assets/${TARGET_DATE}-web-story"
  local page_file="${page_dir}/index.html"

  echo "🌐 生成配套 Web Story 页面（可对外发布）…"
  # 主链路已产出 *-video.mp4，这里只生成 HTML + 预览图，避免重复录第二份视频。
  if CONTENT_STUDIO_WEB_STORY_SKIP_RECORD=1 \
    CONTENT_STUDIO_WEB_STORY_SKIP_AUDIO=1 \
    CONTENT_STUDIO_WEB_STORY_VISUAL_LIMIT="${CONTENT_STUDIO_WEB_STORY_VISUAL_LIMIT:-5}" \
    "$CS_PYTHON" "$CS_WEB_STORY_RENDERER" "$TARGET_DATE" --report-dir "$REPORT_DIR" \
      --visual-project-limit "${CONTENT_STUDIO_WEB_STORY_VISUAL_LIMIT:-5}"; then
    if [ -f "$page_file" ]; then
      echo "✅ Web Story 页面: $page_file"
      echo "   本地打开: open $page_file"
      return 0
    fi
  fi
  echo "⚠️  Web Story 页面生成失败（不影响已生成的视频）" >&2
  return 0
}

run_video_render() {
  echo "🎬 只渲染视频 — $TARGET_DATE"
  echo "   Stage 1: 跳过脚本生成，复用已有 video-script.md"
  echo "   Stage 2: 视频生成（TTS + GitHub 页面滚动，失败即中止）"
  echo "   Stage 3: 输出小红书发布素材包 + 配套 Web Story 页面"
  echo ""

  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local video_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video.mp4"
  local daily_report="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
  local publish_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-publish.md"

  if ! require_nonempty_file "$script_file" "视频脚本"; then
    echo "❌ 已跳过脚本生成，但找不到可用脚本: $script_file"
    echo "   先运行: content-studio.sh video-pipeline $TARGET_DATE"
    return 1
  fi
  if ! require_nonempty_file "$daily_report" "日报"; then
    echo "❌ 已跳过日报/脚本生成，但找不到日报: $daily_report"
    echo "   先运行: content-studio.sh daily $TARGET_DATE"
    return 1
  fi

  if ! render_video_assets "$script_file" "$video_file" "$daily_report"; then
    echo "❌ video-render 失败：未生成视频文件" >&2
    return 1
  fi
  echo ""
  render_web_story_page
  echo ""
  show_video_package "$script_file" "$video_file" "$publish_file"
  echo "💡 预览视频：open $video_file"

  dispatch_report "$script_file"
}

render_mpt_video_assets() {
  local script_file="$1"
  local video_file="$2"
  local mpt_base_url="${MONEYPRINTER_BASE_URL:-http://127.0.0.1:8082}"
  local mpt_voice="${MONEYPRINTER_VOICE_NAME:-zh-CN-XiaoxiaoNeural-Female}"
  local mpt_timeout="${MONEYPRINTER_TIMEOUT:-1200}"
  local mpt_poll="${MONEYPRINTER_POLL_SECONDS:-10}"

  cs_progress "mpt-video" 2 3 "running" "MoneyPrinterTurbo API 渲染（约 5-15 分钟）" "$video_file"
  echo "⏳ MoneyPrinterTurbo 渲染（可能需要 5-15 分钟）…"
  echo "🐍 Python: $CS_PYTHON ($("$CS_PYTHON" --version 2>&1))"
  echo "🔗 服务: $mpt_base_url"

  local mpt_cmd=(
    "$CS_PYTHON" -u "$CS_MONEYPRINTER_VIDEO"
    --script "$script_file"
    --output "$video_file"
    --base-url "$mpt_base_url"
    --voice-name "$mpt_voice"
    --timeout "$mpt_timeout"
    --poll-seconds "$mpt_poll"
  )
  if ! "${mpt_cmd[@]}" 2>&1; then
    if [ -f "${video_file%.mp4}.mpt-task.json" ]; then
      echo "⚠️  前台 MPT 渲染中断或超时，自动尝试 sidecar 续轮询…" >&2
      if render_mpt_video_resume "$script_file" "$video_file"; then
        return 0
      fi
    fi
    cleanup_empty_file "$video_file"
    cleanup_empty_file "${video_file%.mp4}-cover.jpg"
    echo "❌ MoneyPrinterTurbo 视频生成失败" >&2
    echo "   排查：确认服务可访问 $mpt_base_url/docs，见 moneyprinter-video/references/SERVICE.md" >&2
    echo "   手动重试：$CS_PYTHON -u $CS_MONEYPRINTER_VIDEO --script $script_file --output $video_file" >&2
    return 1
  fi

  if ! require_nonempty_file "$video_file" "MoneyPrinterTurbo 视频"; then
    cleanup_empty_file "$video_file"
    cleanup_empty_file "${video_file%.mp4}-cover.jpg"
    cs_progress "mpt-video" 2 3 "fail" "MPT 视频未生成" "$video_file"
    return 1
  fi
  cs_progress "mpt-video" 2 3 "ok" "MPT 视频已生成" "$video_file"
}

show_mpt_video_package() {
  local script_file="$1"
  local video_file="$2"
  local publish_file="$3"

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📦 MoneyPrinterTurbo 视频素材包"
  [ -s "$video_file" ]   && echo "  📹 视频  : $video_file"   || echo "  📹 视频  : （待生成）$video_file"
  [ -f "$script_file" ]  && echo "  📝 脚本  : $script_file"
  [ -f "$publish_file" ] && echo "  📋 发布  : $publish_file"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  if [ -f "$publish_file" ]; then
    echo "👉 发布指引："
    head -35 "$publish_file"
    echo ""
  fi
}

run_video_mpt() {
  echo "🎬 MoneyPrinterTurbo 视频 — $TARGET_DATE"
  echo "   Stage 1: 复用已有 video-script.md"
  echo "   Stage 2: MoneyPrinterTurbo 素材混剪 + 字幕 + BGM"
  echo "   Stage 3: 输出 MPT 发布素材包"
  echo ""

  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local video_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video.mp4"
  local publish_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video-publish.md"

  if ! require_nonempty_file "$script_file" "视频脚本"; then
    echo "❌ 找不到视频脚本: $script_file"
    echo "   先运行: content-studio.sh video $TARGET_DATE"
    return 1
  fi

  if ! render_mpt_video_assets "$script_file" "$video_file"; then
    echo "⚠️  尝试 mpt-finish 收尾…" >&2
    run_mpt_finish || { echo "❌ video-mpt 失败：未生成视频文件" >&2; return 1; }
  elif [ ! -f "$publish_file" ]; then
    run_mpt_finish || true
  fi
  echo ""
  show_mpt_video_package "$script_file" "$video_file" "$publish_file"
  cs_progress "mpt-video" 3 3 "ok" "发布素材包已输出" "$publish_file"
  echo "💡 预览视频：open $video_file"

  dispatch_report "$script_file"
}

# Hermes 超时/断线后的标准收尾：续轮询 + 补封面/发布指引（不重新 POST 任务）
run_mpt_finish() {
  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local video_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video.mp4"
  local publish_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video-publish.md"
  local sidecar="${video_file%.mp4}.mpt-task.json"
  local mpt_base_url="${MONEYPRINTER_BASE_URL:-http://127.0.0.1:8082}"

  echo "🔧 MPT 收尾 — $TARGET_DATE"

  if [ ! -s "$video_file" ] && [ -f "$sidecar" ]; then
    echo "→ mp4 缺失但有 sidecar，执行 video-mpt-resume…"
    if ! render_mpt_video_resume "$script_file" "$video_file"; then
      echo "❌ 续轮询失败" >&2
      return 1
    fi
  fi

  if [ ! -s "$video_file" ]; then
    echo "❌ 仍无成片: $video_file" >&2
    echo "   先查: $0 mpt-status $TARGET_DATE" >&2
    return 1
  fi

  if [ ! -f "$publish_file" ] || [ ! -s "${video_file%.mp4}-cover.jpg" ]; then
    echo "→ 补封面与发布指引…"
    if ! "$CS_PYTHON" -u "$CS_MONEYPRINTER_VIDEO" \
      --script "$script_file" \
      --output "$video_file" \
      --finalize-only 2>&1; then
      echo "❌ 发布素材生成失败" >&2
      return 1
    fi
  fi

  show_mpt_video_package "$script_file" "$video_file" "$publish_file"
  cs_progress "mpt-video" 3 3 "ok" "发布素材包已输出（finish）" "$publish_file"
  echo "✅ MPT 收尾完成"
  return 0
}

run_video_mpt_pipeline() {
  echo "🎬 MoneyPrinterTurbo 完整 Pipeline — $TARGET_DATE"
  cs_progress "mpt-video" 0 3 "running" "Pipeline 开始" ""
  echo "   Stage 1: 生成视频脚本（与核心链路共用规范）"
  echo "   Stage 2: MoneyPrinterTurbo 素材混剪 + 字幕 + BGM"
  echo "   Stage 3: 输出 MPT 发布素材包"
  echo ""

  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local video_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video.mp4"
  local publish_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-mpt-video-publish.md"
  local daily_report="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"

  if [ ! -f "$daily_report" ]; then
    echo "❌ 今日日报不存在，Pipeline 中止: $daily_report"
    return 1
  fi

  if ! run_hermes_chat video-script-generator \
    "今天是 ${TARGET_DATE}。基于今日日报（${daily_report}），请按 video-script-generator Skill 的「技术趋势栏目主编」模式生成一条 90-150 秒口播脚本，并写入 ${script_file}（已有则覆盖）。项目来源必须严格限制在今日日报 GitHub Trending Top 10 内。必须包含：## 本期主题、## 入选项目、## 完整口播文本、## 小红书发布素材。完整口播文本必须是纯口播，不要写舞台标记。" \
    2>&1; then
    echo "⚠️  Hermes 视频脚本生成超时或异常，尝试降级脚本…" >&2
    if ! generate_video_script_fallback "$daily_report" "$script_file" "$TARGET_DATE"; then
      echo "❌ Stage 1 失败：模型脚本与降级脚本均未生成" >&2
      return 1
    fi
    echo "✅ Stage 1 降级完成: $script_file"
  fi

  if ! require_nonempty_file "$script_file" "视频脚本"; then
    echo "❌ Stage 1 失败：视频脚本未生成: $script_file" >&2
    cs_progress "mpt-video" 1 3 "fail" "脚本未生成" "$script_file"
    return 1
  fi
  cs_progress "mpt-video" 1 3 "ok" "脚本已生成" "$script_file"
  echo "✅ Stage 1 完成: $script_file"
  echo ""

  if ! render_mpt_video_assets "$script_file" "$video_file"; then
    echo "❌ Stage 2 失败：MoneyPrinterTurbo 视频未生成，Pipeline 中止" >&2
    return 1
  fi
  echo ""
  show_mpt_video_package "$script_file" "$video_file" "$publish_file"
  cs_progress "mpt-video" 3 3 "ok" "发布素材包已输出" "$publish_file"
  echo "💡 预览视频：open $video_file"

  dispatch_report "$script_file"
}

run_video_pipeline() {
  local auto_mode="${2:-}"
  echo "🎬 触发视频 Pipeline — $TARGET_DATE"
  cs_progress "sop-video" 0 3 "running" "Pipeline 开始" ""
  echo "   Stage 1: 生成视频脚本"
  echo "   Stage 2: 视频生成（TTS + GitHub 页面滚动，失败即中止）"
  echo "   Stage 3: 输出小红书发布素材包 + 配套 Web Story 页面"
  echo ""

  local script_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-script.md"
  local video_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video.mp4"

  # --- Stage 1: 生成视频脚本 ---
  # 优先从日报生成（日报版 60-90s），若日报不存在则降级到周报版
  local daily_report="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
  local daily_source_prompt
  if [ -f "$daily_report" ]; then
    daily_source_prompt="基于今日日报（${daily_report}）"
  else
    echo "❌ 今日日报不存在，视频 Pipeline 中止: $daily_report"
    return 1
  fi

  if ! run_hermes_chat video-script-generator \
    "今天是 ${TARGET_DATE}。${daily_source_prompt}，请按 video-script-generator Skill 的「技术趋势栏目主编」模式生成一条 90-150 秒的小红书/抖音短视频脚本，并写入 ${script_file}（已有则覆盖）。项目来源必须严格限制在今日日报 GitHub Trending Top 10 内，不允许引入日报之外的项目。不要做普通 TOP3 安利，必须先提炼「本期主题」和一句话 thesis，再选择 5 个能形成叙事链的项目；每个项目必须保留原始排名、GitHub URL 和「链上角色」（例如标准制定者、工程增强包、成本压缩网关、落地载体）。脚本必须包含：## 基本信息、## 本期主题、## 入选项目、## 完整口播文本、## 分镜表、## 小红书发布素材、## 质量自检。完整口播文本必须是纯口播，不要写（开场）（第一个）【结尾】等舞台标记；开场第一句必须是行业判断，不要用「哈喽大家」；结尾必须有长期思考或落地建议。分镜表必须为每个项目安排至少一个 github_scroll_callout，并包含 concept_card / ranking_chart / summary_card 等画面规划。数字保留阿拉伯数字写法（如 1200、3600），视频流水线会自动转换 TTS 读法。" \
    2>&1; then
    echo "⚠️  Hermes 视频脚本生成超时或异常，尝试降级脚本…" >&2
    if ! generate_video_script_fallback "$daily_report" "$script_file" "$TARGET_DATE"; then
      echo "❌ Stage 1 失败：模型脚本与降级脚本均未生成" >&2
      echo "   日志：$PROFILE_DIR/logs/agent.log" >&2
      return 1
    fi
    echo "✅ Stage 1 降级完成: $script_file"
  fi

  if ! require_nonempty_file "$script_file" "视频脚本"; then
    echo "❌ Stage 1 失败：视频脚本文件未生成: $script_file" >&2
    cs_progress "sop-video" 1 3 "fail" "脚本未生成" "$script_file"
    return 1
  fi
  cs_progress "sop-video" 1 3 "ok" "脚本已生成" "$script_file"
  echo "✅ Stage 1 完成: $script_file"
  echo ""

  # --- Stage 2: 视频生成 ---
  if ! render_video_assets "$script_file" "$video_file" "$daily_report"; then
    echo "❌ Stage 2 失败：GitHub 页面滚动视频未生成，Pipeline 中止" >&2
    return 1
  fi

  echo ""
  render_web_story_page

  echo ""

  # --- Stage 3: 显示素材包 ---
  local publish_file="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-video-publish.md"
  show_video_package "$script_file" "$video_file" "$publish_file"
  cs_progress "sop-video" 3 3 "ok" "发布素材包已输出" "$publish_file"

  # 是否自动打开创作者中心（需要用户确认）
  if [ "$auto_mode" != "--auto" ]; then
    echo "💡 在浏览器发布：open https://creator.xiaohongshu.com/publish/publish"
    echo "   （或运行 'open $video_file' 先预览视频）"
  else
    echo "🌐 打开小红书创作者中心…"
    open "https://creator.xiaohongshu.com/publish/publish" 2>/dev/null || true
  fi

  dispatch_report "$script_file"
}

run_community_pulse() {
  echo "📰 触发社区脉搏简报 — $TARGET_DATE"
  echo "   输出: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md"
  echo ""

  local daily_report="${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
  if [ ! -f "$daily_report" ]; then
    echo "⚠️  今日日报不存在，先触发日报…"
    run_daily
  fi

  export CONTENT_STUDIO_COMMUNITY_STABLE="${CONTENT_STUDIO_COMMUNITY_STABLE:-1}"

  if ! "$CS_PYTHON" "$CS_COMMUNITY_GENERATOR" \
    "$daily_report" \
    "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md" \
    "$TARGET_DATE" \
    --limit "${CONTENT_STUDIO_COMMUNITY_LIMIT:-3}" \
    --timeout "${CONTENT_STUDIO_COMMUNITY_TIMEOUT:-300}"; then
    echo ""
    echo "❌ 社区脉搏简报生成失败：last30days 未成功完成，已停止生成，未写入降级简报。" >&2
    echo "   请检查 last30days 安装、Python 3.12、API key / cookie，或 cron 日志。" >&2
    return 1
  fi

  if require_nonempty_file "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md" "社区脉搏" && validate_community_pulse "$daily_report" "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md"; then
    echo ""
    echo "✅ 社区脉搏已生成: ${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md"
    dispatch_report "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md"
  else
    echo ""
    echo "⚠️  社区脉搏无效，请检查 Hermes 输出日志"
    mv "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.md" "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}-community-pulse.invalid.md" 2>/dev/null || true
    return 1
  fi
}

REPORT_VIEWER_PORT="${REPORT_VIEWER_PORT:-18765}"
REPORT_VIEWER_PID_FILE="${HERMES_HOME:-$HOME/.hermes}/.runtime/reports-viewer.pid"

run_library() {
  echo "📚 刷新 内容策划主编报告库"
  echo "   目录: $REPORT_DIR"
  echo ""

  if [ -f "$CS_REPORT_INDEX" ]; then
    "$CS_PYTHON" "$CS_REPORT_INDEX" --report-dir "$REPORT_DIR" --html || true
  fi

  local index_file="$REPORT_DIR/index.md"
  if [ -f "$index_file" ]; then
    echo ""
    echo "✅ 报告索引: $index_file"
    if [ -f "$REPORT_DIR/index.html" ]; then
      echo "🌐 网页浏览: content-studio.sh browse"
      echo "   或 Chat 里说「打开报告库网页」"
    fi
  else
    echo "⚠️  报告索引未找到，请检查 report_index.py"
  fi

  if [ "${CONTENT_STUDIO_SKIP_NOTEBOOK_SYNC:-0}" != "1" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    run_open_notebook_sync || true
  fi
}

run_open_notebook_sync() {
  echo "📓 同步 Content Studio 报告到 Open Notebook"
  echo "   Reports: $REPORT_DIR"
  echo "   API: ${OPEN_NOTEBOOK_API_URL:-http://127.0.0.1:5055}"
  echo "   Backend: ${OPEN_NOTEBOOK_SYNC_BACKEND:-direct}"
  echo ""

  if [ ! -f "$CS_OPEN_NOTEBOOK_SYNC" ]; then
    echo "❌ Open Notebook 同步脚本不存在: $CS_OPEN_NOTEBOOK_SYNC"
    return 1
  fi

  local backend="${OPEN_NOTEBOOK_SYNC_BACKEND:-direct}"
  if [ "$backend" = "direct" ]; then
    if [ ! -d "$CS_OPEN_NOTEBOOK_ROOT" ]; then
      echo "❌ Open Notebook 源码目录不存在: $CS_OPEN_NOTEBOOK_ROOT"
      echo "   请设置 OPEN_NOTEBOOK_ROOT 或改用 OPEN_NOTEBOOK_SYNC_BACKEND=api"
      return 1
    fi
    (
      cd "$CS_OPEN_NOTEBOOK_ROOT" || exit 1
      uv run --env-file .env python "$CS_OPEN_NOTEBOOK_SYNC" \
        --backend direct \
        --report-dir "$REPORT_DIR" \
        "$@"
    )
    return $?
  fi

  "$CS_PYTHON" "$CS_OPEN_NOTEBOOK_SYNC" \
    --backend api \
    --report-dir "$REPORT_DIR" \
    "$@"
}

run_open_notebook_query() {
  if [ ! -f "$CS_OPEN_NOTEBOOK_QUERY" ]; then
    echo "❌ Open Notebook 查询脚本不存在: $CS_OPEN_NOTEBOOK_QUERY"
    return 1
  fi
  "$CS_PYTHON" "$CS_OPEN_NOTEBOOK_QUERY" "$@"
}

run_browse() {
  echo "🌐 打开报告库网页"
  echo "   目录: $REPORT_DIR"
  echo ""

  if [ -f "$CS_REPORT_INDEX" ]; then
    "$CS_PYTHON" "$CS_REPORT_INDEX" --report-dir "$REPORT_DIR" --html || true
  fi

  if [ ! -f "$REPORT_DIR/index.html" ]; then
    echo "❌ 未生成 index.html，请检查 report_index.py"
    return 1
  fi

  mkdir -p "$(dirname "$REPORT_VIEWER_PID_FILE")"
  local url="http://127.0.0.1:${REPORT_VIEWER_PORT}/index.html"

  if [ -f "$REPORT_VIEWER_PID_FILE" ]; then
    local old_pid
    old_pid="$(cat "$REPORT_VIEWER_PID_FILE" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
      echo "✅ 报告库服务已在运行 (pid $old_pid)"
      echo "   $url"
      if command -v open >/dev/null 2>&1; then
        open "$url" || true
      fi
      return 0
    fi
    rm -f "$REPORT_VIEWER_PID_FILE"
  fi

  (
    cd "$REPORT_DIR" || exit 1
    exec "$CS_PYTHON" -m http.server "$REPORT_VIEWER_PORT" --bind 127.0.0.1
  ) >/dev/null 2>&1 &
  local pid=$!
  echo "$pid" >"$REPORT_VIEWER_PID_FILE"
  sleep 0.4

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "❌ 无法启动本地浏览服务（端口 ${REPORT_VIEWER_PORT} 可能被占用）"
    rm -f "$REPORT_VIEWER_PID_FILE"
    return 1
  fi

  echo "✅ 已在浏览器打开报告库"
  echo "   $url"
  echo "   停止服务: content-studio.sh stop-browse"
  if command -v open >/dev/null 2>&1; then
    open "$url" || true
  fi
}

stop_browse() {
  if [ ! -f "$REPORT_VIEWER_PID_FILE" ]; then
    echo "报告库浏览服务未运行"
    return 0
  fi
  local pid
  pid="$(cat "$REPORT_VIEWER_PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "✅ 已停止报告库浏览服务 (pid $pid)"
  else
    echo "报告库浏览服务未运行（已清理 pid 文件）"
  fi
  rm -f "$REPORT_VIEWER_PID_FILE"
}

show_latest_video() {
  local latest_video
  latest_video="$("$CS_PYTHON" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
videos = [p for p in root.glob("*/*/*-video.mp4") if p.is_file()]
videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
print(videos[0] if videos else "")
PY
)"

  if [ -z "$latest_video" ]; then
    echo "❌ 未找到视频文件（*-video.mp4）"
    echo "   报告目录: $REPORT_DIR"
    return 1
  fi

  local latest_cover="${latest_video%.mp4}-video-cover.jpg"
  if [ ! -f "$latest_cover" ]; then
    latest_cover="${latest_video%.mp4}-cover.jpg"
  fi
  local latest_publish="${latest_video%-video.mp4}-video-publish.md"

  echo "🎬 最新视频"
  echo "  视频: $latest_video"
  if [ -f "$latest_cover" ]; then
    echo "  封面: $latest_cover"
  fi
  if [ -f "$latest_publish" ]; then
    echo "  发布指引: $latest_publish"
  fi
}

open_latest_video() {
  local latest_video
  latest_video="$("$CS_PYTHON" - "$REPORT_DIR" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
videos = [p for p in root.glob("*/*/*-video.mp4") if p.is_file()]
videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
print(videos[0] if videos else "")
PY
)"

  if [ -z "$latest_video" ]; then
    echo "❌ 未找到可打开的视频文件（*-video.mp4）"
    echo "   报告目录: $REPORT_DIR"
    return 1
  fi

  show_latest_video
  echo ""
  echo "🌐 正在打开视频文件…"
  open "$latest_video" 2>/dev/null || {
    echo "⚠️  自动打开失败，请手动执行："
    echo "   open \"$latest_video\""
    return 1
  }
}

run_daily_sop() {
  echo "🚀 重跑 内容策划主编日常 SOP — $TARGET_DATE"
  cs_progress "daily-sop" 0 5 "running" "完整 SOP 开始" ""
  echo "   顺序: 日报 → 工具雷达 → 社区脉搏 → 视频 Pipeline → 报告库"
  echo ""

  cs_progress "daily-sop" 1 5 "running" "日报" ""
  CONTENT_STUDIO_SKIP_AUTO_VIDEO=1 run_daily
  cs_progress "daily-sop" 1 5 "ok" "日报完成" "${REPORT_DIR}/${YEAR}/${MONTH}/${TARGET_DATE}.md"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  cs_progress "daily-sop" 2 5 "running" "工具雷达" ""
  run_radar
  cs_progress "daily-sop" 2 5 "ok" "工具雷达完成" ""
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  cs_progress "daily-sop" 3 5 "running" "社区脉搏" ""
  run_community_pulse
  cs_progress "daily-sop" 3 5 "ok" "社区脉搏完成" ""
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  cs_progress "daily-sop" 4 5 "running" "视频 Pipeline" ""
  run_video_pipeline
  cs_progress "daily-sop" 4 5 "ok" "视频 Pipeline 完成" ""
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  cs_progress "daily-sop" 5 5 "running" "报告库" ""
  run_library
  cs_progress "daily-sop" 5 5 "ok" "完整 SOP 结束" ""
}

case "$ACTION" in
  daily)
    run_daily
    ;;
  weekly)
    run_weekly
    ;;
  radar|tools|production)
    run_radar
    ;;
  video)
    run_video
    ;;
  video-render|render-video|render|vr)
    run_video_render
    ;;
  video-pipeline|pipeline|vp)
    run_video_pipeline "$ACTION" "${3:-}"
    ;;
  video-mpt|mpt-video|moneyprinter-video|vmpt)
    run_video_mpt
    ;;
  video-mpt-bg|mpt-bg)
    run_video_mpt_bg
    ;;
  video-mpt-resume|mpt-resume)
    run_video_mpt_resume
    ;;
  mpt-status)
    show_mpt_status
    ;;
  mpt-finish|video-mpt-finish)
    run_mpt_finish
    ;;
  video-mpt-pipeline|mpt-pipeline|vmp)
    run_video_mpt_pipeline
    ;;
  video-hybrid|hybrid-video|vh)
    run_video_hybrid
    ;;
  video-hybrid-pipeline|hybrid-pipeline|vhp)
    run_video_hybrid_pipeline
    ;;
  hybrid-status)
    run_video_hybrid_status
    ;;
  community-pulse|pulse)
    run_community_pulse
    ;;
  latest-video|video-latest|最新视频)
    show_latest_video
    ;;
  open-latest-video|video-open|打开最新视频)
    open_latest_video
    ;;
  library|reports|index)
    run_library
    ;;
  notebook-sync|open-notebook-sync)
    shift || true
    run_open_notebook_sync "$@"
    ;;
  notebook-query|open-notebook-query)
    shift || true
    run_open_notebook_query "$@"
    ;;
  browse|open-library|web|网页|打开报告库)
    run_browse
    ;;
  stop-browse|stop-web)
    stop_browse
    ;;
  sop|rerun|full|all)
    run_daily_sop
    ;;
  sop-status|status|进度)
    show_sop_status
    ;;
  help|--help|-h|*)
    cat <<'USAGE'
Content Studio — 手动触发后门

用法:
  content-studio.sh <command> [date]

命令:
  daily              生成日报（当日覆盖）[日报完成后自动触发 video-pipeline]
  radar              生成生产级工具雷达（当日覆盖）
  weekly             生成周报（当日覆盖）
  video              生成趋势分析视频脚本（thesis → 叙事链 → 分镜表）
  video-pipeline     完整视频 Pipeline：趋势脚本 → GitHub 滚动红框视频 → 发布素材包
  video-render       只渲染视频：复用已有脚本 → GitHub 滚动红框视频 → 发布素材包
  video-mpt          MoneyPrinterTurbo：复用已有脚本 → 素材混剪视频 → MPT 发布包
  video-mpt-bg       后台运行 video-mpt（写 logs/mpt-render-DATE.log）
  video-mpt-resume   从 sidecar 续轮询 MPT（超时后不断点重提）
  mpt-finish         标准收尾：续轮询 + 补封面/发布指引（Hermes 超时后必跑）
  mpt-status         查看 MPT sidecar / 后台日志 / 产出
  video-mpt-pipeline MoneyPrinterTurbo 完整链路：脚本 + 素材混剪视频 + MPT 发布包
  video-hybrid       Hybrid：复用已有脚本 → 相关素材 cards/AI fallback → hybrid 视频
  video-hybrid-pipeline Hybrid 完整链路：hybrid spec + assets + v1 mp4（不覆盖 sop/mpt）
  hybrid-status      查看 hybrid spec/assets/video 状态
  latest-video       显示最新视频路径
  open-latest-video  打开最新视频（macOS 使用 open）
  community-pulse    社区脉搏简报（last30days：Reddit/HN 社区讨论）
  library            刷新报告库索引（生成 index.md + index.html，并自动同步 Open Notebook）
  notebook-sync      同步 reports 到 Open Notebook（可加 --include-github-rank）
  notebook-query     查询 Open Notebook 知识库（search/get/notebooks/stats）
  browse             在浏览器打开报告库（推荐，普通用户用这个）
  stop-browse        停止报告库本地浏览服务
  sop|rerun|full|all 重跑日常 SOP（日报 → 工具雷达 → 社区脉搏 → 视频 Pipeline → 报告库 → Open Notebook）
  sop-status|status  查看指定日期的 pipeline 进度行与产出文件（无需重跑）
  help               显示此帮助

视频内容体系:
  人设              Content Studio Agent / 内容策划主编
  脚本框架          hook/thesis → 叙事链/故事链 → 完整口播 → 分镜表 → 长期思考
  分镜规范          concept_card / ranking_chart / github_scroll_callout / summary_card / web_story
  生产策略          画面证据链失败即中止，不生成静默降级版本
  规范产物          *-video-script.md / *-storyboard.md / *-production-spec.yaml / *-video.mp4

可选参数:
  date               指定日期，格式 YYYY-MM-DD（默认今天）
  --auto             video-pipeline 专用，跳过审核自动打开浏览器

示例:
  content-studio.sh daily                        # 今日日报 + 自动触发视频 pipeline
  content-studio.sh daily 2026-05-29             # 补昨天的日报
  content-studio.sh video                         # 只生成趋势分析脚本和分镜表
  content-studio.sh video 2026-05-29              # 指定日期只生成趋势分析脚本
  content-studio.sh video-pipeline               # 运行视频 pipeline（趋势脚本+视频+素材包）
  content-studio.sh video-pipeline 2026-05-29    # 指定日期运行视频 pipeline
  content-studio.sh video-render                 # 复用今天脚本，只重新生成视频/封面/发布指引
  content-studio.sh video-render 2026-05-29      # 指定日期只重新生成视频
  content-studio.sh video-mpt                      # 用已有脚本走 MoneyPrinterTurbo
  content-studio.sh video-mpt-pipeline 2026-06-11  # 脚本 + MoneyPrinterTurbo 完整链路
  content-studio.sh video-hybrid-pipeline 2026-06-13 # 新增 hybrid 独立链路
  content-studio.sh hybrid-status 2026-06-13          # 查看 hybrid 状态
  content-studio.sh community-pulse                 # 今日社区脉搏（基于日报 Top 3）
  content-studio.sh community-pulse 2026-05-30      # 指定日期社区脉搏
  content-studio.sh latest-video                 # 显示最新视频路径
  content-studio.sh open-latest-video            # 打开最新视频
  content-studio.sh video-pipeline today --auto  # 生成后自动打开小红书发布页
  content-studio.sh radar                        # 今日生产级工具雷达
  content-studio.sh weekly                       # 本周周报
  content-studio.sh library                      # 刷新报告库索引并自动同步 Open Notebook
  content-studio.sh notebook-sync --dry-run      # 预览 Open Notebook 同步
  content-studio.sh notebook-sync                # 导入 Open Notebook（默认 direct backend）
  content-studio.sh notebook-sync --embed        # 导入并请求 embedding（需配置模型 key）
  content-studio.sh notebook-sync --include-github-rank --dry-run
  content-studio.sh notebook-query stats         # 查看 Open Notebook 知识库统计
  content-studio.sh notebook-query search "agent" --limit 5
  content-studio.sh notebook-query get "2026-06-04 · GitHub 社区趋势简报"
  content-studio.sh browse                       # 浏览器打开报告库（推荐）
  content-studio.sh stop-browse                  # 停止报告库本地浏览服务
  content-studio.sh sop                          # 重跑今天完整日常 SOP
  content-studio.sh sop 2026-05-31               # 重跑指定日期完整日常 SOP

报告归档位置:
  ~/.hermes/profiles/content-studio/reports/YYYY/MM/

USAGE
    ;;
esac
