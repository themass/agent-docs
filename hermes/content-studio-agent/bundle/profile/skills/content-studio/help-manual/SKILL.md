---
name: help-manual
description: "内容策划主编帮助手册。Chat 说 help/帮助 时输出 Workspace 友好简版；help full/帮助 详细 时输出命令大全。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [content-studio, help, manual, skills, usage]
    related_skills: [playbook, knowledge-library, moneyprinter-video, video-pipeline, video-execution]
---

# 内容策划主编帮助手册

本 Skill 是帮助内容的**事实来源**（指令、命令、目录）。在 **Workspace / Chat** 里不要整份粘贴下文。

## Workspace 输出规则（默认 help）

触发：`Content Studio 帮助`、`内容帮助`、`帮助`、`help`、`使用说明`、`有哪些 skills`、`怎么用`。

1. 加载并**只输出** `references/help-quick.md` 的正文（从 `# Content Studio 快速帮助` 起）。
2. 保持短表格、短列表；**禁止**输出本文件里的 `## Skills 能力树` 大段 ` ```text ` 树、**禁止**贴 frontmatter。
3. 不要摘要到丢失关键命令名；不要执行 pipeline。

## Workspace 输出规则（help full）

触发：`help full`、`帮助 详细`、`完整帮助`、`命令大全`。

1. **terminal** 执行：`"$HERMES_HOME/scripts/content-studio.sh" help`
2. 将终端输出按小节整理后回复（可加报告库路径、三条视频对比）。
3. **禁止**把本 `SKILL.md` 全文原样贴进 Chat。

## Agent 内部参考（以下供 skill_view / 人工查阅，非 Chat 默认输出）

一句话：我是 Content Studio Agent / 内容策划主编，负责多题材选题、日报、工具雷达、社区脉搏、周报、视频脚本、分镜规划、视频生成和知识库管理。

---

## Skills 能力树

```text
Content Studio Agent / 内容策划主编
│
├── 工作手册
│   ├── playbook
│   │   └── 总 SOP：决定每条指令走哪个流程。
│   └── help-manual (`help-manual` 兼容别名)
│       └── 帮助：输出本说明。
│
├── 报告生产
│   ├── github-daily
│   │   └── 日报：每天抓 GitHub Trending。
│   ├── tool-radar
│   │   └── 工具雷达：寻找真正能落地、能集成的生产级开源工具。
│   └── weekly-digest
│       └── 周报：汇总一周日报，去重项目并分析趋势。
│
├── 视频内容
│   ├── video-script-generator
│   │   └── 趋势分析脚本：生成 thesis、叙事链、口播和分镜表。
│   ├── storyboard-planner
│   │   └── 分镜规划：把口播转成 storyboard 和 production spec。
│   ├── video-pipeline
│   │   └── GitHub 滚动核心视频流水线：日榜 + 介绍页 + 页面滚动 + 发布指引。
│   ├── video-execution
│   │   └── Hermes 执行手册：Chat 说 sop视频/mpt视频 时用 terminal 跑 pipeline 并分 Stage 汇报。
│   ├── moneyprinter-video
│   │   └── MoneyPrinterTurbo 通用视频：口播 + 素材混剪 + 字幕（独立链路，产出 *-mpt-video.mp4）。
│   ├── hybrid-video
│   │   └── Hybrid 第三条视频链路：GitHub 证据 + 概念卡 + Seedance/fallback 相关素材（产出 *-hybrid-video.mp4）。
│   └── web-story-renderer
│       └── 配套 Web Story 页面：video-pipeline 成功后自动生成，可对外发布。
│
├── 社区研究
│   ├── last30days (`research/last30days`)
│   │   └── 跨平台检索：Reddit/X/YouTube/HN 社区在说什么。
│   └── community-pulse (`community-pulse`)
│       └── 社区脉搏：基于日报 Top 3，合成 last30days 结果。
│
└── 报告管理
    └── knowledge-library
        └── 报告库：查看、检索、打开、摘要 reports 目录下的文档。
```

---

## 指令系统

你不需要记 skill 名，只要说自然语言。Agent 会先经过 `playbook` 路由，再调用对应 skill。

```text
帮助 / GitHub帮助 / 分析师帮助 / help / 怎么用 / 有哪些 skills
  → 输出 help-quick 简版（Workspace 友好）

help full / 帮助 详细 / 完整帮助 / 命令大全
  → terminal content-studio.sh help + 整理输出

日报 / daily / 今日热门 / trending
  → 生成今日日报

补跑 2026-05-30 日报
  → 生成指定日期日报，同日文件覆盖

工具雷达 / 生产级工具 / 发现有用项目
  → 生成生产级工具雷达

周报 / weekly / 本周分析
  → 生成周报，汇总本周日报并去重分析

视频脚本 / 小红书脚本
  → 生成趋势分析脚本：本期主题、叙事链、口播、分镜表

分镜 / storyboard / production spec
  → 把视频脚本转成 storyboard 和 production spec

生成视频 / 视频 pipeline / 出视频
  → GitHub 滚动核心链路完整视频素材包 + 配套 Web Story 页面

生成 sop视频 / sop视频 / 主视频 / GitHub 滚动视频
  → 读 video-execution Skill → terminal 执行 video-pipeline → 产出 *-video.mp4

生成 mpt视频 / 生成 mpt 视频 / mpt视频 / MPT 视频 / 素材混剪视频
  → 读 video-execution + moneyprinter-video → **禁止 video-pipeline**
  → 已有脚本 → terminal 仅 video-mpt → 产出 *-mpt-video.mp4
  → 无脚本 → terminal 仅 video-mpt-pipeline → 产出 *-mpt-video.mp4
  → 画面为通用 B-roll，非 GitHub 页面；项目深描靠口播

生成 hybrid视频 / hybrid视频 / AI增强视频 / 相关素材视频
  → 读 video-execution + hybrid-video → terminal 执行 video-hybrid-pipeline → 产出 *-hybrid-video.mp4
  → 第三条独立链路，不覆盖 sop/mpt；Seedance 不可用时降级为概念卡

视频进度 / 渲染状态 / sop-status / mpt-status
  → terminal 执行 sop-status / mpt-status，贴回 CONTENT_STUDIO_PROGRESS 与产出文件列表
  → MPT 超时或断线后 terminal 执行 mpt-finish（见 video-execution）

hybrid 进度 / hybrid-status / AI增强视频状态
  → terminal 执行 hybrid-status，贴回 hybrid spec/assets/video 状态

Web Story / 打开视频配套页面 / 资源页面
  → assets/YYYY-MM-DD-web-story/index.html（video-pipeline 成功后自动生成）

MoneyPrinterTurbo / 通用视频 / 素材混剪 / MPT 视频
  → 走 moneyprinter-video Skill，产出 *-mpt-video.mp4（不替代核心链路）

社区脉搏 / community pulse / 大家在说什么 / last30days
  → 基于今日日报 Top 3，检索 Reddit/HN 社区讨论并生成简报

报告库 / 查看 reports / 打开最新日报
  → 查看报告目录或读取报告内容

查看 2026-05-30 的报告
  → 列出该日期的日报、周报、视频脚本、发布包等文件
```

指令原则：

```text
1. 你说目标，不用说 skill 名。
2. 如果带日期，就按该日期执行。
3. 同一天重复执行，会覆盖同名文件。
4. 日报生成成功后，会自动触发核心 video-pipeline（GitHub 滚动），不会自动走 MoneyPrinterTurbo。
5. 核心 video-pipeline 可以先用固定音频验证，不必一开始接 TTS。
6. MoneyPrinterTurbo 通用视频需手动说「MPT 视频」或执行 video-mpt / video-mpt-pipeline。
```

---

## 手动命令系统

所有手动入口都在：

```bash
"$HERMES_HOME/scripts/content-studio.sh"
```

**【特殊兜底：无 terminal 环境的后台运行】**
如果被迫使用 `execute_code`，**严禁**阻塞等待，必须用 `subprocess.Popen(..., start_new_session=True)`，或者直接在 python 中调用脚本中自带的后台命令（如 `video-mpt-bg`）。

常用命令：

```bash
# 生成今日日报；日报完成后自动触发 video-pipeline
"$HERMES_HOME/scripts/content-studio.sh" daily

# 补跑指定日期日报（同日覆盖）
"$HERMES_HOME/scripts/content-studio.sh" daily 2026-05-30

# 生成生产级工具雷达
"$HERMES_HOME/scripts/content-studio.sh" radar

# 生成周报
"$HERMES_HOME/scripts/content-studio.sh" weekly

# 只生成视频脚本
"$HERMES_HOME/scripts/content-studio.sh" video

# 生成 GitHub 滚动核心链路完整视频素材包
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-05-30

# 复用已有脚本，只重新渲染 GitHub 滚动视频
"$HERMES_HOME/scripts/content-studio.sh" video-render
"$HERMES_HOME/scripts/content-studio.sh" video-render 2026-05-30

# MoneyPrinterTurbo 通用视频（复用脚本）
"$HERMES_HOME/scripts/content-studio.sh" video-mpt
"$HERMES_HOME/scripts/content-studio.sh" video-mpt 2026-06-11

# MoneyPrinterTurbo 完整链路（脚本 + 素材混剪）
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-pipeline
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-pipeline 2026-06-11

# MPT 超时 / 有 sidecar 无 mp4 / 有 mp4 无发布包（Hermes 断线后必跑）
"$HERMES_HOME/scripts/content-studio.sh" mpt-finish
"$HERMES_HOME/scripts/content-studio.sh" mpt-finish 2026-06-11

# 从 sidecar 续轮询（mpt-finish 仍缺 mp4 时再用）
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-resume

# Hybrid 第三条链路（相关素材 + 概念卡 + Seedance/fallback）
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid-pipeline
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid-pipeline 2026-06-13
"$HERMES_HOME/scripts/content-studio.sh" hybrid-status 2026-06-13

# 查视频/SOP 进度（无需重跑 pipeline）
"$HERMES_HOME/scripts/content-studio.sh" sop-status
"$HERMES_HOME/scripts/content-studio.sh" sop-status 2026-06-13

# 生成社区脉搏简报（last30days）
"$HERMES_HOME/scripts/content-studio.sh" community-pulse
"$HERMES_HOME/scripts/content-studio.sh" community-pulse 2026-05-30

# 重跑完整日常 SOP：日报 → 工具雷达 → 社区脉搏 → 视频 Pipeline → 报告库
"$HERMES_HOME/scripts/content-studio.sh" sop
"$HERMES_HOME/scripts/content-studio.sh" sop 2026-05-31

# 用固定音频验证视频链路，不调用 TTS
CONTENT_STUDIO_VIDEO_AUDIO_FILE="/path/to/audio.mp3" \
  "$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-05-30

# 刷新并查看报告库索引
"$HERMES_HOME/scripts/content-studio.sh" library

# 在浏览器打开/停止报告库网页
"$HERMES_HOME/scripts/content-studio.sh" browse
"$HERMES_HOME/scripts/content-studio.sh" stop-browse

# 查看/打开最新视频
"$HERMES_HOME/scripts/content-studio.sh" latest-video
"$HERMES_HOME/scripts/content-studio.sh" open-latest-video

# 查看命令行帮助
"$HERMES_HOME/scripts/content-studio.sh" help
```

---

## 报告目录

报告根目录：

```text
~/.hermes/profiles/content-studio/reports/
```

归档结构：

```text
reports/
  ├── index.md
  └── YYYY/
      └── MM/
          ├── YYYY-MM-DD.md                 # 日报
          ├── YYYY-MM-DD-production-radar.md # 生产级工具雷达
          ├── YYYY-MM-DD-community-pulse.md    # 社区脉搏简报（last30days）
          ├── YYYY-MM-DD-weekly.md          # 周报
          ├── YYYY-MM-DD-video-script.md    # 视频脚本（两条视频链路共用）
          ├── YYYY-MM-DD-video.mp4          # 核心成片（GitHub 滚动）
          ├── YYYY-MM-DD-mpt-video.mp4      # MoneyPrinterTurbo 成片（可选）
          ├── YYYY-MM-DD-video-cover.jpg    # 核心视频封面
          ├── YYYY-MM-DD-mpt-video-cover.jpg
          ├── YYYY-MM-DD-video-publish.md   # 核心链路发布指引
          ├── YYYY-MM-DD-mpt-video-publish.md
          └── assets/
              ├── YYYY-MM-DD-video/         # 核心视频素材
              └── YYYY-MM-DD-web-story/     # 配套页面（index.html 可对外发布）
                  └── index.html
```

查看报告库：

```bash
"$HERMES_HOME/scripts/content-studio.sh" library
```

Chat 里说：

```text
报告库
打开最新日报
打开最新视频脚本
查看 2026-05-30 的报告
```

---

## 常见工作流速查

```text
每日完整 SOP:
  content-studio.sh sop
  → 日报
  → 工具雷达
  → 社区脉搏
  → 视频 Pipeline
  → 更新 reports/index.md

MoneyPrinterTurbo 通用视频（独立链路，不进日常 SOP）:
  content-studio.sh video-mpt YYYY-MM-DD
  → 复用已有 *-video-script.md
  → 产出 *-mpt-video.mp4

  content-studio.sh video-mpt-pipeline YYYY-MM-DD
  → 生成脚本 + MoneyPrinterTurbo 成片
  → 产出 *-mpt-video.mp4 + *-mpt-video-publish.md

只生成日报:
  content-studio.sh daily
  → 日报
  → 默认自动触发视频 Pipeline（定时任务中会关闭自动视频，避免重复）

每日社区讨论（08:45 Cron 或手动）:
  content-studio.sh community-pulse
  → 从日报 Top 3 调用 last30days
  → 生成 YYYY-MM-DD-community-pulse.md

只看生产级工具:
  content-studio.sh radar
  → 生产级工具雷达

只看历史文档:
  Chat 里说“报告库”
  → 展示 reports/index.md

快速验证视频:
  CONTENT_STUDIO_VIDEO_AUDIO_FILE="/path/to/audio.mp3" content-studio.sh video-pipeline 2026-05-30
  → 跳过 TTS，使用固定音频生成 mp4
```

火山引擎 TTS 环境变量：

```bash
export VOLCENGINE_APP_ID="你的 AppID"
export VOLCENGINE_TOKEN="你的 Token"
export VOLCENGINE_CLUSTER="volcano_tts"
export VOLCENGINE_VOICE_TYPE="zh_female_wanwanxiaohe_moon_bigtts"
```

---

## 如果你忘了

只要说：

```text
帮助
```

我就会输出这份手册。
