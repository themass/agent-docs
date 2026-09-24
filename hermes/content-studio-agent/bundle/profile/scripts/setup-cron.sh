#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Content Studio — Cron 定时任务配置
#
# 创建定时任务：
#   1. github-daily          — 每日 08:00
#   2. tool-radar   — 每日 08:30
#   3. community-pulse      — 每日 08:45
#   4. video-pipeline          — 每日 09:00
#   5. weekly-digest    — 每周一 08:00
#
# 用法: ./setup-cron.sh
# 前提: Gateway 必须在运行中
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE_DIR="$(dirname "$SCRIPT_DIR")"

export HERMES_HOME="$PROFILE_DIR"

HERMES_BIN="${HERMES_BIN:-$PROFILE_DIR/../../hermes-agent/.venv/bin/hermes}"
if [ ! -x "$HERMES_BIN" ]; then
  HERMES_BIN="$(command -v hermes 2>/dev/null || true)"
fi
if [ -z "$HERMES_BIN" ] && [ -x "/Users/gqli/work/deepagents/hermes-dev/_hermes-cli.sh" ]; then
  HERMES_BIN="/Users/gqli/work/deepagents/hermes-dev/_hermes-cli.sh"
fi

if [ -z "$HERMES_BIN" ]; then
  echo "❌ 找不到 hermes CLI"
  exit 1
fi

echo "🔧 配置 Content Studio 定时任务"
echo ""

chmod +x \
  "$SCRIPT_DIR/content-studio-daily.sh" \
  "$SCRIPT_DIR/content-studio-radar.sh" \
  "$SCRIPT_DIR/content-studio-weekly.sh" \
  "$SCRIPT_DIR/content-studio-video-pipeline.sh" \
  "$SCRIPT_DIR/content-studio-community-pulse.sh"

# --- 日报：每 24 小时 ---
echo "📊 创建日报定时任务 (每日)"
"$HERMES_BIN" cron create \
  --name "github-daily" \
  --profile content-studio \
  --deliver local \
  --script "content-studio-daily.sh" \
  --no-agent \
  "0 8 * * *" \
  2>&1 && echo "  ✅ 日报任务已创建" || echo "  ⚠️  日报任务创建失败（可能已存在）"

echo ""

# --- 工具雷达：每 24 小时 ---
echo "🧭 创建生产级工具雷达定时任务 (每日)"
"$HERMES_BIN" cron create \
  --name "tool-radar" \
  --profile content-studio \
  --deliver local \
  --script "content-studio-radar.sh" \
  --no-agent \
  "30 8 * * *" \
  2>&1 && echo "  ✅ 工具雷达任务已创建" || echo "  ⚠️  工具雷达任务创建失败（可能已存在）"

echo ""

# --- 周报：每 168 小时（7天）---
echo "📈 创建周报定时任务 (每周)"
"$HERMES_BIN" cron create \
  --name "weekly-digest" \
  --profile content-studio \
  --deliver local \
  --script "content-studio-weekly.sh" \
  --no-agent \
  "0 8 * * 1" \
  2>&1 && echo "  ✅ 周报任务已创建" || echo "  ⚠️  周报任务创建失败（可能已存在）"

echo ""

# --- 视频 Pipeline：每 24 小时 ---
echo "🎬 创建视频 Pipeline 定时任务 (每日)"
"$HERMES_BIN" cron create \
  --name "video-pipeline" \
  --profile content-studio \
  --deliver local \
  --script "content-studio-video-pipeline.sh" \
  --no-agent \
  "0 9 * * *" \
  2>&1 && echo "  ✅ 视频 Pipeline 任务已创建" || echo "  ⚠️  视频 Pipeline 任务创建失败（可能已存在）"

echo ""

# --- 社区脉搏：每日 08:45（依赖日报）---
echo "📰 创建社区脉搏简报定时任务 (每日 08:45)"
"$HERMES_BIN" cron create \
  --name "community-pulse" \
  --profile content-studio \
  --deliver local \
  --script "content-studio-community-pulse.sh" \
  --no-agent \
  "45 8 * * *" \
  2>&1 && echo "  ✅ 社区脉搏任务已创建" || echo "  ⚠️  社区脉搏任务创建失败（可能已存在）"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# --- 查看任务列表 ---
echo "📋 当前定时任务列表："
"$HERMES_BIN" cron list 2>&1 || true

echo ""
echo "✅ 配置完成！"
echo ""
echo "管理命令："
echo "  hermes cron list                           # 查看任务"
echo "  hermes cron run github-daily              # 立即执行日报"
echo "  hermes cron run tool-radar       # 立即执行工具雷达"
echo "  hermes cron run weekly-digest        # 立即执行周报"
echo "  hermes cron run video-pipeline              # 立即执行视频 Pipeline"
echo "  hermes cron run community-pulse          # 立即执行社区脉搏"
echo "  hermes cron pause github-daily            # 暂停日报"
echo "  hermes cron resume github-daily           # 恢复日报"
echo ""
echo "手动触发后门："
echo "  \$HERMES_HOME/scripts/content-studio.sh daily"
echo "  \$HERMES_HOME/scripts/content-studio.sh radar"
echo "  \$HERMES_HOME/scripts/content-studio.sh weekly"
echo "  \$HERMES_HOME/scripts/content-studio.sh video-pipeline"
echo "  \$HERMES_HOME/scripts/content-studio.sh community-pulse"
echo "  \$HERMES_HOME/scripts/content-studio.sh sop"
echo ""
echo "Skill 脚本（直接调用）："
echo "  skills/content-studio/github-daily/scripts/generate_daily_report.py"
echo "  skills/content-studio/video-pipeline/scripts/video_generator.py"
echo "  skills/content-studio/knowledge-library/scripts/report_index.py"
