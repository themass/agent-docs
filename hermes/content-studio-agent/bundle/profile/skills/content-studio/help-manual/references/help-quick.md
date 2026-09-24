# Content Studio 快速帮助

我是 **内容策划主编**，负责日报、工具雷达、社区脉搏、周报、视频脚本与三条独立视频链路。直接说自然语言即可，不必记 skill 名。

## 常用指令

| 你想做什么 | 直接说 |
|------------|--------|
| 今日 GitHub 日报 | `日报` / `daily` / `今日热门` |
| 补跑某天日报 | `补跑 2026-06-16 日报` |
| 工具雷达 | `工具雷达` / `生产级工具` |
| 周报 | `周报` / `weekly` |
| 视频脚本 | `视频脚本` / `小红书脚本` |
| 报告库 | `报告库` / `打开最新日报` |
| 社区讨论 | `社区脉搏` / `last30days` |

## 三条视频（互不影响，产物文件名不同）

| 链路 | 说法 | 产出 |
|------|------|------|
| **SOP 主视频** | `生成 sop视频` / `sop视频` | `*-video.mp4`（GitHub 页面滚动 + 口播对应） |
| **MPT 样片** | `生成 mpt视频` / `mpt视频` | `*-mpt-video.mp4`（口播 + 通用素材混剪） |
| **Hybrid 样片** | `生成 hybrid视频` / `hybrid视频` | `*-hybrid-video.mp4`（分镜 + 概念卡 / 可选 AI 素材） |

查进度：`sop-status` / `mpt-status` / `hybrid-status`（Agent 会用 terminal 执行）。

MPT 超时或断线后：说 `mpt收尾` 或让 Agent 跑 `mpt-finish`。

## 报告库路径

`/Users/gqli/.hermes/profiles/content-studio/reports`

## 原则

- 带日期就按该日期执行；同一天重复跑会覆盖同名文件。
- 要 mpt 时不要同轮跑 sop；要 sop 时不要同轮跑 mpt。
- 视频渲染必须由 Agent 用 **terminal** 执行 `content-studio.sh`，不要让你自己去终端粘贴命令。

## 更完整的说明

说 **`help full`**、**`帮助 详细`** 或 **`完整帮助`**，我会输出命令大全与目录结构（仍按 Workspace 友好排版，不贴整份 Skill 原文）。
