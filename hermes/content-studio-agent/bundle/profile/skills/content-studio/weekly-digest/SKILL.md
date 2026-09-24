---
name: weekly-digest
description: "每周一生成 GitHub 深度分析周报。汇总本周日报，按垂直领域（AI Agent、LLM Infra、DevTools、Android）深度分析，归档至 reports/YYYY/MM/YYYY-MM-DD-weekly.md"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GitHub, 周报, 深度分析, AI Agent, LLM, DevTools, Android]
    related_skills: [github-daily, github-repo-management]
---

# GitHub 周度深度分析报告

你是 内容策划主编。每周一生成一份深度分析周报，覆盖本周热门项目与 4 个垂直领域。

## 执行步骤

### Step 1 — 汇总本周日报

读取本周 7 天的日报数据：

```bash
REPORT_DIR="$HOME/.hermes/profiles/content-studio/reports"
YEAR=$(date +%Y)
MONTH=$(date +%m)

# 列出本周的日报文件
ls "$REPORT_DIR/$YEAR/$MONTH/"*.md 2>/dev/null | grep -v weekly | grep -v video | tail -7
```

从 7 天日报中提取：
- 所有上榜项目的去重列表
- 连续上榜天数统计
- 每个项目的首次出现日期、最近出现日期、语言、分类、一句话简介
- 本周新增趋势（如多日有数据）

如果日报不足 7 天，基于现有日报 + 实时 GitHub Trending 补充。

### Step 2 — 综合排名

按**本周新增热度 + 上榜天数 + 生产价值**综合排序，筛选 Top 10 明星项目。

对 Top 10 项目，用 GitHub API 获取详细信息：

```bash
gh repo view owner/repo --json stargazersCount,primaryLanguage,description,createdAt,updatedAt,forkCount,openIssues
gh api repos/owner/repo/stats/commit_activity --jq '.[0]'
```

### Step 3 — 垂直领域深度分析

将项目按 4 个垂直领域分类分析：

#### 领域分类标准

| 领域 | 关键词/标签 |
|------|-----------|
| **AI Agent / Multi-Agent** | agent, multi-agent, langgraph, autogen, crew, swarm, tool-use, function-calling |
| **LLM Infra / 模型服务** | llm, inference, serving, vllm, ollama, fine-tune, rag, embedding, tokenizer |
| **DevTools / 开发者工具** | cli, editor, linter, formatter, debugger, ci-cd, testing, build-tool |
| **Android 好玩项目** | android, kotlin, jetpack-compose, app, mobile, material-design |

对每个领域，分析：
- 本周上榜项目清单
- 架构特点与创新点
- 与同领域其他项目的对比
- 领域整体趋势

### Step 4 — 生成周报

按以下格式生成 Markdown：

```markdown
# GitHub 爆火项目周报 — 深度分析

📅 {周一日期} ~ {周日日期} | 第{N}周

---

## 一、本周去重项目总览

| # | 项目 | 地址 | 本周新增 | 上榜天数 | 语言 | 分类 | 一句话简介 |
|---|------|------|----------|----------|------|------|------------|
| 1 | owner/repo | https://github.com/owner/repo | +5,200 | 7/7 | TypeScript | AI Agent | 一句话说明 |

---

## 二、本周 Top 10

| # | 项目 | 本周新增 | 上榜天数 | 分类 | 推荐理由 |
|---|------|----------|----------|------|----------|
| 1 | [owner/repo](url) | +5,200 | 7/7 | AI Agent | {为什么值得关注} |

---

## 三、垂直领域复盘

### AI Agent / Multi-Agent

| 项目 | 本周新增 | 上榜天数 | 架构特点 | 值得关注的原因 |
|------|----------|----------|----------|----------------|
| [owner/repo](url) | +2,100 | 5/7 | 事件驱动 | ... |

**领域趋势：** {2-3 句专业分析}

**推荐理由：** {针对开发者的具体建议}

---

### LLM Infra / 模型服务

（同上表格+分析格式）

---

### DevTools / 开发者工具

（同上格式）

---

### Android 好玩项目

（同上格式，额外关注：创意性、实用性、UI 设计）

---

### 生产级工具

（从本周去重项目中筛选真正适合部署、集成或作为工作流基础设施的工具）

---

## 四、趋势对比

- **持续上升：** {project}（连续 N 天上榜 / 本周新增明显）
- **新晋黑马：** {project}（本周首次上榜即进入 Top 5）
- **退热项目：** {project}（前几日高热，后续消失）
- **值得继续观察：** {project}（基础设施价值高，但热度仍在验证）

---

## 五、值得深挖的 5 个项目

### 01. {project}

- **项目定位：** {一句话}
- **为什么值得深挖：** {2-3 句}
- **适合谁：** {目标用户}
- **下一步观察：** {继续追踪什么指标}

---

## 六、本周推荐

> **最值得学习：** {project} — {原因}
> **最值得关注：** {project} — {原因}
> **最具创意：** {project} — {原因}
> **最适合生产试用：** {project} — {原因}

---

## 📊 数据来源

- GitHub Trending (daily/weekly)
- GitHub REST API
- 本周日报: {N} 份
- 去重项目数: {N} 个
```

### Step 5 — 归档

```bash
REPORT_DIR="$HOME/.hermes/profiles/content-studio/reports"
YEAR=$(date +%Y)
MONTH=$(date +%m)
TODAY=$(date +%Y-%m-%d)

mkdir -p "$REPORT_DIR/$YEAR/$MONTH"
# 写入：$REPORT_DIR/$YEAR/$MONTH/$TODAY-weekly.md（同日覆盖）
```

---

## 规则

- **数据驱动**：所有数据必须来自 GitHub API / Trending，不可编造
- **深度不水**：每个领域分析至少 2-3 句有洞察的趋势判断
- **对比有料**：与上周对比时要有具体数据支撑
- **推荐有理**：推荐理由要具体，说清楚对什么样的人有用
- **去重完整**：必须包含本周去重后的项目列表和简介，不能只列 Top 10
- **中文为主**：技术术语和项目名保留英文
- **同日覆盖**：如果当日已有周报，直接覆盖
