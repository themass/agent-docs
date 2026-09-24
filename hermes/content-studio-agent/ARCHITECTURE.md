# Content Studio Agent — 架构

## 1. 逻辑分层

```text
┌─────────────────────────────────────────────────────────────────┐
│  Surface：Hermes Workspace (:3000) · Dashboard (:9119) · WebUI   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / WS
┌────────────────────────────▼────────────────────────────────────┐
│  Hermes Gateway (:8642)  —  HERMES_HOME=content-studio profile   │
│  AIAgent · conversation_loop · skills · cron · terminal          │
└─────┬──────────────────┬──────────────────┬───────────────────────┘
      │                  │                  │
      ▼                  ▼                  ▼
 OpenInspector      Open Notebook      MoneyPrinterTurbo
 Proxy :8080/v1      API :5055          API :8082
 (LLM 追踪)          知识库/播客         素材混剪视频
```

**设计原则**（与 Hermes core 一致）：

- **编排与 SOP 在 Skill + shell**，不在 SOUL 里堆命令表。
- **可重复、可 Cron 的步骤**走 `content-studio.sh`；Agent 用 `terminal` 调用并读进度行。
- **LLM 调用**经 Gateway →（可选）OpenInspector → 上游；MPT 为独立 HTTP，不走 Inspector。

---

## 2. Content Studio Agent 在 Hermes 里的位置

| 层 | 路径 / 机制 | 作用 |
|----|-------------|------|
| 人设 | `SOUL.md` | 内容策划主编：栏目、证据、视频表达原则 |
| 路由 | `skills/content-studio/playbook/SKILL.md` | 用户意图 → Skill + `content-studio.sh` 子命令 |
| 手册 | `skills/content-studio/help-manual/` | Workspace 友好的 help 简版 + `help full` |
| 能力包 | `skills/content-studio/*/` | 日报、周报、脚本、三条视频、报告库、社区脉搏等 |
| 编排器 | `scripts/content-studio.sh` | 唯一 CLI 真相源（Cron、人工、Agent terminal） |
| 产物 | `reports/YYYY/MM/` | Markdown、yaml、mp4、发布 sidecar |

Agent 收到任务时应：**先 `skill_view` 加载 playbook 或具体 Skill**，再执行；禁止在 SOUL 层即兴编造 pipeline。

---

## 3. 内容生产流水线（按日）

典型 **日常 SOP**（`content-studio.sh sop` / `all`）：

```text
github-daily（日报）
    → tool-radar（工具雷达，可选并行语义）
    → community-pulse（社区脉搏）
    → video-pipeline（SOP：GitHub 滚动红框证据链视频）
    → knowledge-library（索引 + notebook-sync）
```

**视频三条链路**（互不复盖主文件名约定）：

| 链路 | 命令 | 产出（同日 DATE） | 引擎 |
|------|------|-------------------|------|
| **SOP** | `video-pipeline` / `video-render` | `*-video.mp4`、storyboard、production-spec | `video-pipeline` Skill 内 `video_generator.py` |
| **MPT** | `video-mpt-pipeline` / `video-mpt` | `*-mpt-video.mp4`、`.mpt-task.json` sidecar | MoneyPrinterTurbo API |
| **Hybrid** | `video-hybrid-pipeline` | `*-hybrid-video.mp4`、hybrid spec/yaml | `hybrid-video` Skill（cards + 可选 Seedance） |

状态查询：`sop-status`、`mpt-status`、`hybrid-status`（读 `logs/sop-latest.log` 中的 `CONTENT_STUDIO_PROGRESS` 行）。

---

## 4. 与开源项目边界

| 项目 | 仓库路径 | 在 Content Studio 中的角色 |
|------|----------|---------------------------|
| **Hermes Agent** | `hermes-dev/hermes-agent` | 运行时、Gateway、Skills 平台 |
| **Hermes Workspace** | `hermes-dev/hermes-workspace` | 主控制台；Chat 被动更新见 `WORKSPACE_VS_WEBUI.md` |
| **Open Notebook** | `open-notebook/` | `notebook-sync`、播客/研究 UI（:3001） |
| **MoneyPrinterTurbo** | `MoneyPrinterTurbo/` | MPT 视频链路 |
| **OpenInspector** | `openinspector/` | LLM 代理与 trace（:8080 / :5173） |
| **DeepSpace Field** | `hermes-dev/deepspace-field/` | 独立 3D 科普 MVP，**非** Content Studio 主链 |

---

## 5. 演进：GitHub Analyst → Content Studio

| 阶段 | Profile | 仓库镜像 |
|------|---------|----------|
| v1 GitHub 分析师 | `~/.hermes/profiles/github` | `hermes-dev/profiles/github/`（**已在 git**） |
| v2 内容工作室 | `~/.hermes/profiles/content-studio` | **`hermes-dev/profiles/content-studio/`**（git 可分享包） |

设计文档（早期分析师）：[../GITHUB_ANALYST_DESIGN.md](../GITHUB_ANALYST_DESIGN.md)  
Hybrid 中期计划：[../../plans/2026-06-14-hybrid-video-midterm-plan.md](../../plans/2026-06-14-hybrid-video-midterm-plan.md)
