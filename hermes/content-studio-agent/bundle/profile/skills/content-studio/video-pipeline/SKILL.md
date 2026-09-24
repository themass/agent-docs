---
name: video-pipeline
description: "按视频脚本和分镜规范生成发布素材包。"
version: 2.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [视频, 小红书, GitHub, production-spec, pipeline]
    related_skills: [github-daily, video-script-generator, storyboard-planner]
---

# GitHub 视频生成与发布 Pipeline（核心链路）

`video-pipeline` 是 **GitHub 日榜 + 介绍页 + 页面滚动** 的执行层。MoneyPrinterTurbo 素材混剪走独立 Skill `moneyprinter-video`，见 `content-studio.sh video-mpt`。

## Hard Rules

1. **唯一入口**：Agent 和 Cron 必须通过编排脚本触发，禁止直接运行 `python3 .../video_generator.py`。
2. **内容策略不写进 shell**：shell 只负责串联 Skill 和执行，不负责决定人设、叙事链或画面策略。
3. **生产视频必须失败即停**：GitHub 页面滚动红框失败时，必须清晰报错并中止，不生成卡片截图版或静态背景版。
4. **口播文本必须干净**：`## 完整口播文本` 不能包含 `（开场）`、`【第一个】` 等舞台标记。
5. **每个项目必须有真实 GitHub 证据画面**：每个入选项目至少一个 `github_scroll_callout`。

## Commands

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
export CONTENT_STUDIO_TTS_CONFIG="$HERMES_HOME/config/tts-providers.yaml"
export CONTENT_STUDIO_NARRATION_VOLUME=10

"$HERMES_HOME/scripts/content-studio.sh" video-pipeline              # 今天：脚本 + 视频
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-06-04   # 指定日期
"$HERMES_HOME/scripts/content-studio.sh" video-render                # 复用现有脚本，只重渲染
"$HERMES_HOME/scripts/content-studio.sh" video-render 2026-06-04
```

调试画面链路时可以复用固定音频：

```bash
CONTENT_STUDIO_VIDEO_AUDIO_FILE="$HERMES_HOME/audio_cache/YYYY-MM-DD-current-audio.m4a" \
  "$HERMES_HOME/scripts/content-studio.sh" video-render YYYY-MM-DD
```

## Production SOP

```text
日报/周报
  │
  ▼
video-script-generator
  ├─ 本期主题 thesis
  ├─ 入选项目叙事链
  ├─ 完整口播文本
  ├─ 分镜表
  └─ 发布素材
  │
  ▼
storyboard-planner
  ├─ YYYY-MM-DD-storyboard.md
  └─ YYYY-MM-DD-production-spec.yaml
  │
  ▼
video-pipeline
  ├─ TTS
  ├─ ranking_chart / concept_card / github_scroll_callout / summary_card
  ├─ transitions
  ├─ subtitles
  ├─ mp4 + cover + publish guide
  └─ web-story-renderer（自动）→ assets/YYYY-MM-DD-web-story/index.html
```

核心成片 `*-video.mp4` 与配套页面 `assets/*-web-story/index.html` **共用脚本和日报**；页面在视频成功后自动生成，用于外链/静态站发布。

当前渲染器已经支持稳定主链路：TTS、开场排行图、GitHub 页面滚动红框、字幕、封面和发布指引。`concept_card`、`workflow_diagram`、`transition` 和 `production-spec.yaml` 是下一阶段的渲染输入标准；在渲染器完全支持前，脚本仍必须先输出分镜表，作为人工审核和后续升级依据。

## Required Inputs

`video-render` 要求以下文件存在：

```text
reports/YYYY/MM/YYYY-MM-DD.md
reports/YYYY/MM/YYYY-MM-DD-video-script.md
```

生产级目标还应生成：

```text
reports/YYYY/MM/YYYY-MM-DD-storyboard.md
reports/YYYY/MM/YYYY-MM-DD-production-spec.yaml
```

`video-pipeline` 会先调用 `video-script-generator` 生成/覆盖脚本，再调用渲染链路。

## Script Contract

`YYYY-MM-DD-video-script.md` 必须包含：

```markdown
## 本期主题
## 入选项目
## 完整口播文本
## 分镜表
## 小红书发布素材
```

`## 入选项目` 中的 GitHub URL 是视频素材项目的唯一来源。不要从日报外补项目。

## Visual Contract

每条生产级视频至少包含：

| 段 | 画面类型 | 要求 |
|----|----------|------|
| 开场 | `concept_card` 或 `ranking_chart` | 给出 thesis 或热榜证据 |
| 项目段 | `github_scroll_callout` | 每个项目至少一次，带红框标注 |
| 项目解释 | `concept_card` / `workflow_diagram` | 解释项目角色、能力或链路 |
| 段间 | `transition` | 0.3-0.6 秒，淡入/擦除/滑动 |
| 收尾 | `summary_card` | 给长期判断和落地建议 |

当前实现若暂不支持某种画面类型，必须在 `storyboard.md` 里保留规划，不要删除规范。

## Failure Policy

生产环境宁愿失败，也不要输出错误风格视频。

必须失败的情况：

- Playwright 无法打开 GitHub 页面。
- GitHub 全页截图为空或无效。
- 项目段无法渲染 `github_scroll_callout`。
- 入选项目不在日报/周报允许范围。
- 口播脚本缺失 `## 完整口播文本`。
- 渲染器只能生成卡片截图版或静态背景版。

报错要说明：

- 失败阶段。
- 失败项目。
- 失败素材路径。
- 建议重试命令。

## Outputs

```text
reports/YYYY/MM/
  ├── YYYY-MM-DD-video-script.md
  ├── YYYY-MM-DD-storyboard.md              # 目标产物
  ├── YYYY-MM-DD-production-spec.yaml       # 目标产物
  ├── YYYY-MM-DD-video.mp4
  ├── YYYY-MM-DD-video-cover.jpg
  └── YYYY-MM-DD-video-publish.md

reports/YYYY/MM/assets/YYYY-MM-DD-video/
  ├── daily-ranking-chart.png
  └── github-scroll/
      └── owner__repo-fullpage.png
```

## Review Checklist

视频生成后检查：

- 日志中每个项目段都是 `github-scroll -> owner/repo`，不能出现 `card-scroll`。
- 字幕没有 `开场`、`第一个` 等舞台标记。
- 开场有趋势判断，不是普通 TOP3 安利。
- 项目画面和口播点匹配。
- 至少有一个画面解释行业趋势或长期判断。
- 发布标题表达趋势，而不只是项目名。

## Common Issues

| 问题 | 原因 | 处理 |
|------|------|------|
| `card-scroll` 出现 | 旧渲染路径或旧脚本 | 中止，修复渲染器或脚本后重跑 |
| GitHub 截图失败 | Playwright/网络/GitHub 超时 | 确认 profile HOME 下 Chromium 已安装，重跑 |
| 字幕出现舞台标记 | 脚本口播不干净 | 重写脚本或让生成器清洗 |
| 视频风格像普通安利 | 缺 thesis 和叙事链 | 回到 `video-script-generator` 重写 |
| 画面全是滚动截图 | 缺分镜/概念卡规划 | 运行 `storyboard-planner` |

## Verification

完成后至少确认：

```bash
"$HERMES_HOME/scripts/content-studio.sh" video-render YYYY-MM-DD
```

日志应包含：

```text
github-scroll -> owner/repo
```

且不包含：

```text
card-scroll
readme-demo
```
