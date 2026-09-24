---
name: knowledge-library
description: "内容策划主编报告库。通过 Chat 查看、检索、打开、摘要 reports 目录下的日报、周报、工具雷达和视频脚本文档。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GitHub, reports, file, library, workspace]
    related_skills: [github-daily, tool-radar, weekly-digest, video-script-generator]
---

# GitHub 报告库

> **路径约定**：索引脚本位于 `skills/content-studio/knowledge-library/scripts/`。报告产物仍在 profile `reports/`。

你是 内容策划主编的报告管理员。这个 Skill 专门操作：

```text
~/.hermes/profiles/content-studio/reports/
```

目标是让用户在 Hermes Workspace Chat 里能稳定查看目录、打开文档、检索历史报告，而不需要记路径。

**无需 Obsidian 桌面应用**。

**Open Notebook 归档**：如果用户要求“同步到 Open Notebook / 进入知识库 / 管理我们的数据”，运行：

```bash
"$HERMES_HOME/scripts/content-studio.sh" notebook-sync
```

`library` 和 `sop` 完成后也会**自动增量同步**新报告到 Open Notebook（可用 `CONTENT_STUDIO_SKIP_NOTEBOOK_SYNC=1` 跳过）。

首次验证或担心重复导入时先运行：

```bash
"$HERMES_HOME/scripts/content-studio.sh" notebook-sync --dry-run
```

默认使用 `direct` backend，直接写入 `full_text`，避免 Open Notebook 处理队列超时导致空内容。需要改回 REST 导入时：

```bash
OPEN_NOTEBOOK_SYNC_BACKEND=api "$HERMES_HOME/scripts/content-studio.sh" notebook-sync
```

默认只导入为 Open Notebook Source，不请求 embedding，避免 Open Notebook 还没配置模型/API Key 时失败。需要向量检索和知识库问答时，先在 Open Notebook UI 配置模型，再运行：

```bash
"$HERMES_HOME/scripts/content-studio.sh" notebook-sync --embed
```

默认只同步 `reports/`。如果用户明确要求把 `github-daily-rank` 历史库也导入，再加：

```bash
"$HERMES_HOME/scripts/content-studio.sh" notebook-sync --include-github-rank
```

**Open Notebook 查询**：当用户要在 Hermes Chat 里查历史资料、跨文档搜索、读某篇已归档报告时，优先运行：

```bash
"$HERMES_HOME/scripts/content-studio.sh" notebook-query stats
"$HERMES_HOME/scripts/content-studio.sh" notebook-query search "agent 视频" --limit 5
"$HERMES_HOME/scripts/content-studio.sh" notebook-query get "2026-06-04 · GitHub 社区趋势简报"
"$HERMES_HOME/scripts/content-studio.sh" notebook-query notebooks
```

查询结果用于选题、写脚本、回答“知识库里有什么”。深度跨文档问答仍推荐 Open Notebook UI 的 Notebook Chat。

**普通用户浏览（推荐）**：执行

```bash
"$HERMES_HOME/scripts/content-studio.sh" browse
```

会在浏览器打开 `http://127.0.0.1:18765/index.html`（左侧列表 + 右侧阅读）。用户说「打开报告库网页」时你必须运行上述命令，不要只给 `find`/`less` 等终端说明。

**附件转 Markdown**：对用户提供的 PDF/Word/PPT 等，调用 MCP `convert_to_markdown`（`markitdown` 服务器），再写入 `reports/`。

---

## 硬规则

- **绝对路径优先**：报告根目录固定为 `"$HERMES_HOME/reports"`（`HERMES_HOME` 默认 `~/.hermes/profiles/content-studio`）。不要用当前 Workspace 的 `./reports`、`~/reports` 或其它工作目录判断。
- **先查真实文件**：说“报告库不存在或为空”之前，必须检查：
  - `"$HERMES_HOME/reports/index.md"`
  - `"$HERMES_HOME/reports/YYYY/MM/YYYY-MM-DD.md"`
- **索引可重建**：如果 `index.md` 不存在，运行：

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
python3 "$HERMES_HOME/skills/content-studio/knowledge-library/scripts/report_index.py" \
  --report-dir "$HERMES_HOME/reports"
```

---

## 触发方式

用户说以下任一表达时使用本 Skill：

- `报告库`
- `查看 reports`
- `查看报告目录`
- `打开最新日报`
- `打开最新周报`
- `打开最新工具雷达`
- `查看 2026-05-30 的报告`
- `把最新报告贴出来`
- `同步到 Open Notebook`
- `导入知识库`
- `查 Open Notebook`
- `知识库里搜`
- `从知识库找`

---

## 路径约定

```text
REPORT_DIR=~/.hermes/profiles/content-studio/reports

reports/
  ├── index.md
  └── YYYY/
      └── MM/
          ├── YYYY-MM-DD.md
          ├── YYYY-MM-DD-production-radar.md
          ├── YYYY-MM-DD-weekly.md
          └── YYYY-MM-DD-video-script.md
```

报告类型：

| 类型 | 文件模式 | 含义 |
|------|----------|------|
| 日报 | `YYYY-MM-DD.md` | GitHub Trending 日报 |
| 工具雷达 | `YYYY-MM-DD-production-radar.md` | 生产级工具发现 |
| 周报 | `YYYY-MM-DD-weekly.md` | 一周去重汇总与深度分析 |
| 视频脚本 | `YYYY-MM-DD-video-script.md` | 小红书视频脚本 |

Open Notebook Notebook 映射：

| Notebook | 内容 |
|----------|------|
| Content Studio Daily | 每日总报 |
| Community Pulse | last30days 社区热点简报 |
| GitHub Radar | GitHub 榜单、工具雷达、年度报告 |
| Video Production | 视频脚本、发布文案、分镜 |
| Raw Research Archive | raw 抓取材料和原始仓库分析 |

---

## Step 1 — 刷新索引

任何查看动作前，先刷新索引：

```bash
python3 "$HERMES_HOME/skills/content-studio/knowledge-library/scripts/report_index.py" \
  --report-dir ~/.hermes/profiles/content-studio/reports
```

索引文件：

```text
~/.hermes/profiles/content-studio/reports/index.md
```

---

## Step 2 — 指令路由

```text
用户输入
  │
  ├─ "报告库" / "查看 reports" / "查看报告目录"
  │    → 读取并输出 reports/index.md
  │
  ├─ "最新日报"
  │    → 找最新的 YYYY-MM-DD.md（排除 weekly/video/production-radar）并贴出内容
  │
  ├─ "最新周报"
  │    → 找最新的 *-weekly.md 并贴出内容
  │
  ├─ "最新工具雷达" / "最新生产级工具"
  │    → 找最新的 *-production-radar.md 并贴出内容
  │
  ├─ "最新视频脚本"
  │    → 找最新的 *-video-script.md 并贴出内容
  │
  ├─ 包含日期 YYYY-MM-DD
  │    → 列出该日期的全部报告，并按用户指定类型读取
  │
  ├─ "同步到 Open Notebook" / "导入知识库"
  │    → 运行 notebook-sync（或 library / sop 自动触发）
  │
  ├─ "查 Open Notebook" / "知识库里搜" / "从知识库找"
  │    → 运行 notebook-query search/get/stats，基于结果回答或继续写脚本
  │
  ├─ "摘要" / "总结"
  │    → 读取目标报告，输出 5-8 条要点，不贴全文
  │
  └─ "打开目录" / "打开文件"
       → 如果在本机执行，可用 open 命令；如果在 Workspace Chat，优先贴出路径和内容
```

---

## Step 3 — 常用命令

列出所有报告：

```bash
find ~/.hermes/profiles/content-studio/reports -name "*.md" -type f | sort
```

刷新索引：

```bash
python3 "$HERMES_HOME/skills/content-studio/knowledge-library/scripts/report_index.py"
```

读取索引：

```bash
sed -n '1,200p' ~/.hermes/profiles/content-studio/reports/index.md
```

打开 reports 目录（macOS 本机）：

```bash
open ~/.hermes/profiles/content-studio/reports
```

打开索引文件（macOS 本机）：

```bash
open ~/.hermes/profiles/content-studio/reports/index.md
```

---

## Step 4 — 输出格式

查看目录时：

```markdown
# 内容策划主编报告库

报告根目录：`~/.hermes/profiles/content-studio/reports`
索引文件：`~/.hermes/profiles/content-studio/reports/index.md`

## 最近报告

| 日期 | 日报 | 工具雷达 | 周报 | 视频脚本 |
|------|------|----------|------|----------|
| 2026-05-30 | ✅ | ✅ | ✅ | ✅ |

## 可用指令

- `打开最新日报`
- `打开最新工具雷达`
- `查看 2026-05-30 的报告`
- `总结最新周报`
```

读取单篇报告时：

```markdown
已打开：`/absolute/path/to/report.md`

<报告正文>
```

摘要报告时：

```markdown
已读取：`/absolute/path/to/report.md`

## 摘要

1. ...
2. ...
```

---

## 规则

- **先刷新索引**：除非用户明确只给了某个文件路径
- **优先贴内容**：Workspace 不一定有文件浏览 UI，Chat 里要能直接看
- **路径要完整**：回复中必须给出绝对路径，方便用户本机打开
- **不修改报告正文**：除非用户明确要求重写或修订
- **大文件摘要优先**：如果报告很长，先给目录和摘要，再问是否贴全文
