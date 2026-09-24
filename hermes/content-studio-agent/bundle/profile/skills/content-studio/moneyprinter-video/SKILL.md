---
name: moneyprinter-video
description: "MoneyPrinterTurbo 通用短视频链路：口播 + 素材混剪 + 字幕 + BGM。独立于 GitHub 页面滚动核心视频 pipeline，按需手动或单独 SOP 触发。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [视频, MoneyPrinterTurbo, 素材混剪, 通用短视频, 小红书]
    related_skills: [video-script-generator, video-pipeline, playbook]
---

# MoneyPrinterTurbo 通用短视频 Pipeline

`moneyprinter-video` 是**第二条视频链路**，与 `video-pipeline`（GitHub 日榜 + 介绍页 + 页面滚动红框）**并行、互不替代**。

| 维度 | `video-pipeline`（核心 / **sop视频**） | `moneyprinter-video`（本 Skill / **mpt视频**） |
|------|----------------------------------------|-----------------------------------------------|
| 画面 | 日榜图、项目介绍页、**GitHub 滚动红框** | Pixabay/Pexels **通用 B-roll**（coding/developer 等） |
| 与项目关系 | 画面与口播**一一对应**（滚动展示真实仓库） | 口播讲 GitHub 项目，**画面通常无关**（仅字幕同步） |
| 引擎 | TTS + Playwright + ffmpeg | MoneyPrinterTurbo HTTP API |
| 产出 | `YYYY-MM-DD-video.mp4` | `YYYY-MM-DD-mpt-video.mp4` |
| 触发 | 「生成 sop视频」/ `video-pipeline` | 「生成 mpt视频」/ `video-mpt-pipeline` |
| 失败策略 | GitHub 滚动失败即中止 | MPT 失败即中止，不降级到核心链路 |

## Hard Rules

0. **Hermes 执行**：用户说「生成 mpt视频」时必须先读 **`video-execution`** Skill，用 `terminal` 跑 **一条** MPT 命令并按 Stage 汇报。**禁止** `execute_code`、**禁止**让用户手动去终端粘贴命令（见 video-execution「工具白名单」）。
   - 已有 `*-video-script.md` → **仅** `video-mpt [DATE]`
   - 无脚本 → **仅** `video-mpt-pipeline [DATE]`
   - **禁止** 跑 `video-pipeline`；**禁止** 同轮 `video-pipeline` + `video-mpt`
1. **不得替换核心链路**：Cron、日报 SOP、`video-pipeline` 仍走 GitHub 滚动；本 Skill 只在用户明确要求 MPT / mpt视频 时使用。**MPT 请求不得顺带触发 sop pipeline**。
2. **脚本版本**：渲染前确认 `*-video-script.md` 为最新（`ls -lh`）；Cron 降级脚本会导致口播与当前日报叙事不一致。
3. **唯一入口**：通过 `content-studio.sh video-mpt` 或 `video-mpt-pipeline` 触发，禁止在 `video_generator.py --engine auto` 中隐式调用。
4. **脚本复用**：口播来源仍是 `video-script-generator` 产出的 `*-video-script.md`，读取 `## 完整口播文本`；项目段应含 **项目深描**（见 `video-script-generator/references/wechat-style-project-intro.md`）。
5. **产物命名隔离**：输出 `*-mpt-video.mp4`、`*-mpt-video-cover.jpg`、`*-mpt-video-publish.md`，避免覆盖核心链路的 `*-video.mp4`。
6. **服务前置**：MoneyPrinterTurbo 必须在 `MONEYPRINTER_BASE_URL`（默认 `http://127.0.0.1:8082`）可访问。

## 长任务与超时（必读）

MPT Stage 2 通过 HTTP 轮询任务，**经常超过 10 分钟**。单次 foreground 命令可能在 `MONEYPRINTER_TIMEOUT`（默认 1200s）到点退出，但 **MPT 服务端任务可能仍在跑**。

| 手段 | 命令 | 说明 |
|------|------|------|
| 加长轮询 | `MONEYPRINTER_TIMEOUT=1800 ... video-mpt DATE` | 仍是一次性等待 |
| 后台渲染 | `content-studio.sh video-mpt-bg DATE` | 写日志 `logs/mpt-render-DATE.log`，Hermes 可立即回复 |
| 断点续轮询 | `content-studio.sh video-mpt-resume DATE` | 读 `*-mpt-video.mpt-task.json`，**不重新 POST** |
| 查状态 | `content-studio.sh mpt-status DATE` | mp4 / sidecar / 后台日志 |

**Sidecar 文件**：渲染提交后写入 `reports/YYYY/MM/YYYY-MM-DD-mpt-video.mpt-task.json`，含 `task_id`。超时后优先 `video-mpt-resume`，避免重复提交浪费 MPT 队列。

## Commands

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"

# 复用已有脚本，只走 MoneyPrinterTurbo 渲染
"$HERMES_HOME/scripts/content-studio.sh" video-mpt
"$HERMES_HOME/scripts/content-studio.sh" video-mpt 2026-06-11

# 完整链路：趋势脚本 + MoneyPrinterTurbo 成片
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-pipeline
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-pipeline 2026-06-11

# 长任务：后台渲染 + 状态 / 续跑
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-bg 2026-06-11
"$HERMES_HOME/scripts/content-studio.sh" mpt-status 2026-06-11
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-resume 2026-06-11

# 自定义服务地址 / 音色
MONEYPRINTER_BASE_URL=http://127.0.0.1:8082 \
  "$HERMES_HOME/scripts/content-studio.sh" video-mpt 2026-06-11
```

## Production SOP

```text
日报 / 周报（可选，脚本来源）
  │
  ▼
video-script-generator          ← 与核心链路共用脚本规范
  ├─ 本期主题
  ├─ 完整口播文本
  └─ 小红书发布素材
  │
  ▼
moneyprinter-video            ← 本 Skill
  ├─ POST /api/v1/videos
  ├─ GET  /api/v1/tasks/{task_id}
  ├─ 下载 combined/final mp4
  └─ 提取封面 + 发布指引
  │
  ▼
产出 *-mpt-video.mp4 + *-mpt-video-publish.md
```

## Required Inputs

`video-mpt` 至少需要：

```text
reports/YYYY/MM/YYYY-MM-DD-video-script.md
```

`video-mpt-pipeline` 还需要日报或周报作为脚本来源（与 `video` 命令相同）。

## Prerequisites

启动 MoneyPrinterTurbo 服务（见 `references/SERVICE.md`）：

```bash
cd /path/to/MoneyPrinterTurbo
python3 main.py   # 或 docker compose up
curl -s http://127.0.0.1:8082/docs | head -1   # 应可访问
```

## Outputs

```text
reports/YYYY/MM/
  ├── YYYY-MM-DD-video-script.md       # 共用脚本（video-mpt-pipeline 会生成/覆盖）
  ├── YYYY-MM-DD-mpt-video.mp4         # MPT 成片
  ├── YYYY-MM-DD-mpt-video-cover.jpg   # 封面（ffmpeg 截帧）
  └── YYYY-MM-DD-mpt-video-publish.md  # 发布指引
```

## Failure Policy

必须失败并清晰报错的情况：

- MoneyPrinterTurbo 服务不可达（连接拒绝 / 超时）
- API 返回非 200（路径错误、参数无效）
- 任务 `state=-1`（素材下载失败、TTS 失败等）
- 轮询超时（默认 10 分钟）
- 脚本缺少 `## 完整口播文本`

**禁止**在 MPT 失败后自动降级到 GitHub 滚动链路；两条链路由用户或 SOP 显式选择。

## When To Use

适合：

- 快速验证口播 + 字幕 + BGM 的通用竖屏短视频
- 不需要 GitHub 页面证据画面的口播类内容
- A/B 对比 MPT 混剪风格 vs 核心 GitHub 滚动风格

不适合：

- 日报 SOP 默认产出（用 `video-pipeline`）
- 需要项目介绍页、GitHub 滚动红框、日榜开场图的内容

## Review Checklist

- 日志包含 `MoneyPrinterTurbo 任务 … 已提交` 且最终 `✅ MoneyPrinterTurbo 视频已生成`
- 产出文件名带 `-mpt-` 前缀，未覆盖 `*-video.mp4`
- 字幕无舞台标记（开场、第一个等）
- 竖屏 9:16，时长与口播匹配

## Common Issues

| 问题 | 原因 | 处理 |
|------|------|------|
| HTTP 405 | 旧集成调用了 `/api/v1/video` | 本 Skill 使用正确路径 `/api/v1/videos` |
| 连接拒绝 | MPT 未启动 | 启动服务，确认 8082 端口 |
| state=-1 | 素材 API / TTS / LLM 配置问题 | 查 MPT 日志与 `config.toml` |
| 口播为空 | 脚本缺 `## 完整口播文本` | 回到 `video-script-generator` 补全 |
