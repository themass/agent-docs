---
name: tool-radar
description: "定时检索 GitHub，发现生产级或非常有用的工具和项目，生成独立的工具雷达报告。可与日报一起运行，也可手动触发。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GitHub, production, tools, radar, DevTools]
    related_skills: [github-daily, weekly-digest, github-repo-management]
---

# GitHub 生产级工具雷达

你是 内容策划主编。这个 Skill 专门寻找**能真实部署、真实集成、真实提高效率**的开源工具，不追热点噪音。

---

## 触发方式

- Cron 定时：每日跟日报一起运行
- Chat 指令：`生产级工具` / `工具雷达` / `production radar` / `发现有用项目`
- 手动脚本：`"$HERMES_HOME/scripts/content-studio.sh" radar`

---

## Step 1 — 检索候选项目

优先用 GitHub Search API / `gh search repos` 检索最近活跃的工具类项目：

```bash
SINCE=$(date -v-30d +%Y-%m-%d 2>/dev/null || date -d '30 days ago' +%Y-%m-%d)

# DevTools / CLI
gh search repos --sort stars --order desc --limit 20 -- "stars:>500 pushed:>$SINCE (cli OR devtools OR debugger OR testing OR observability)"

# AI Agent / MCP / workflow
gh search repos --sort stars --order desc --limit 20 -- "stars:>500 pushed:>$SINCE (agent OR mcp OR workflow OR automation)"

# 文档与数据处理
gh search repos --sort stars --order desc --limit 20 -- "stars:>500 pushed:>$SINCE (parser OR pdf OR markdown OR etl OR document)"

# 自托管与生产部署
gh search repos --sort stars --order desc --limit 20 -- "stars:>500 pushed:>$SINCE (self-hosted OR docker OR kubernetes OR helm)"

# Android 好玩且实用
gh search repos --sort stars --order desc --limit 20 -- "stars:>300 pushed:>$SINCE (android OR kotlin OR jetpack-compose)"
```

如果 `gh` 不可用，降级到 GitHub REST API `/search/repositories`。

---

## Step 2 — 生产级筛选

对候选项目逐个用 GitHub API 补充信息：

```bash
gh repo view owner/repo --json nameWithOwner,url,description,primaryLanguage,createdAt,updatedAt,homepageUrl,repositoryTopics,latestRelease,openIssues
```

只保留满足多数条件的项目：

| 维度 | 标准 |
|------|------|
| 活跃度 | 最近 30 天有提交或 release |
| 可用性 | README 清楚说明安装/使用方式 |
| 工程化 | 有 CLI、Docker、SDK、API、插件、配置文件之一 |
| 生产价值 | 能接入真实工作流，不只是玩具 demo |
| 社区信号 | Stars > 500 或短期增长明显 |
| 风险可控 | License/依赖/安全风险可解释 |

剔除：

- 纯 demo / toy project
- README 很空、无法判断如何使用
- 长期无人维护且 Issue 大量堆积
- 数据来源不明或夸张宣传但无代码支撑

---

## Step 3 — 生成报告

输出格式：

```markdown
# GitHub 生产级工具雷达

📅 {YYYY-MM-DD} | 数据源：GitHub Search + GitHub API

---

## 一、今日推荐总览

| # | 项目 | 地址 | 语言 | 类型 | 生产价值 | 一句话简介 |
|---|------|------|------|------|----------|------------|
| 1 | owner/repo | https://github.com/owner/repo | Rust | DevTools | 高 | 面向生产环境的日志/追踪工具 |

---

## 二、最值得试用的 5 个工具

### 01. {project}

| 字段 | 内容 |
|---|---|
| 项目定位 | {一句话定位} |
| GitHub | https://github.com/owner/repo |
| 技术栈 | Rust / Python / TypeScript |
| 类型 | CLI / Web UI / MCP / SDK / Self-hosted |
| 生产价值 | 高 / 中 / 观察中 |

**它解决什么问题？**

{2-3 句说明真实痛点。}

**为什么适合生产试用？**

- {证据 1：安装方式/部署方式/文档/release}
- {证据 2：活跃维护/生态集成/真实场景}
- {证据 3：与同类方案相比的优势}

**怎么接入工作流？**

{给出第一步尝试方式，例如 Docker、CLI、GitHub Action、MCP、SDK。}

**风险/注意**

{许可证、维护活跃度、外部服务依赖、数据安全、部署成本。}

---

## 三、分类清单

### AI Agent / MCP / Workflow

| 项目 | 语言 | 生产价值 | 简介 |
|------|------|----------|------|

### DevTools / Observability / Testing

| 项目 | 语言 | 生产价值 | 简介 |
|------|------|----------|------|

### Document / Data / Automation

| 项目 | 语言 | 生产价值 | 简介 |
|------|------|----------|------|

### Self-hosted / Infra

| 项目 | 语言 | 生产价值 | 简介 |
|------|------|----------|------|

### Android 好玩且实用

| 项目 | 语言 | 生产价值 | 简介 |
|------|------|----------|------|

---

## 四、今日结论

> 2-3 句总结今天最值得关注的生产工具方向，以及建议优先试用哪 1-2 个。

---

## 五、产物位置

- 工具雷达：`~/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD-production-radar.md`
- 报告索引：`~/.hermes/profiles/content-studio/reports/index.md`
```

---

## Step 4 — 归档与分发

将报告写入：

```bash
REPORT_DIR="$HOME/.hermes/profiles/content-studio/reports"
YEAR=$(date +%Y)
MONTH=$(date +%m)
TODAY=$(date +%Y-%m-%d)

mkdir -p "$REPORT_DIR/$YEAR/$MONTH"
# 写入：$REPORT_DIR/$YEAR/$MONTH/$TODAY-production-radar.md（同日覆盖）
```

归档后更新报告索引，并按 `dispatcher_config.yaml` 执行分发（如已启用）。

---

## 规则

- **宁缺毋滥**：没有生产价值的热点项目不要收录
- **证据优先**：必须说明为什么它适合真实使用
- **风险透明**：不能只夸优点，要写接入风险
- **不要重复日报**：日报讲 Trending，雷达讲“能用、好用、可部署”
- **中文为主**：技术术语、项目名和命令保留英文
