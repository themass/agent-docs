---
name: github-daily
description: "每日 GitHub 热门项目分析日报。抓取 Trending 数据，生成结构化 Markdown 报告，归档至 reports/YYYY/MM/YYYY-MM-DD.md"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GitHub, Trending, 日报, 分析]
    related_skills: [weekly-digest, github-repo-management]
---

# GitHub 每日热门项目日报

你是 内容策划主编。每天生成一份结构化的热门项目日报。

> **路径约定**：`HERMES_HOME` 默认为 `~/.hermes/profiles/content-studio`。本 Skill 脚本位于 `skills/content-studio/github-daily/scripts/`。

## 执行步骤

### Step 1 — 数据采集

用 GitHub Trending 页面顺序作为今日排名的唯一依据。GitHub Search API / `gh search repos` 只能作为补充数据或页面抓取失败时的降级候选，不能替代 Trending 排名。

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"

# 方式一：直接抓取 Trending 页面（排名以输出顺序为准）
python3 "$HERMES_HOME/skills/content-studio/github-daily/scripts/github_trending_snapshot.py"

# 方式一（推荐）：确定性日报生成
python3 "$HERMES_HOME/skills/content-studio/github-daily/scripts/generate_daily_report.py" \
  --date "$(date +%Y-%m-%d)" \
  --report-dir "$HERMES_HOME/reports"

# 方式二：页面抓取失败时，才用 gh CLI 搜索近期高增长项目作为降级候选
gh search repos --sort stars --order desc --limit 20 -- "stars:>1000 pushed:>$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d '1 day ago' +%Y-%m-%d)"
```

对每个 Trending 上榜项目，用 GitHub API 补充详细信息，不改变原始排名：

```bash
gh repo view owner/repo --json nameWithOwner,url,primaryLanguage,description,createdAt,updatedAt,homepageUrl,repositoryTopics
```

### Step 2 — 历史对比

检查前一日报告是否存在：

```bash
REPORT_DIR="$HOME/.hermes/profiles/content-studio/reports"
YEAR=$(date +%Y)
MONTH=$(date +%m)
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d '1 day ago' +%Y-%m-%d)

PREV_REPORT="$REPORT_DIR/$YEAR/$MONTH/$YESTERDAY.md"
if [ -f "$PREV_REPORT" ]; then
  echo "前一日报告存在，可做对比分析"
fi
```

如果存在前一日报告，识别：
- **新晋项目**：今日上榜但昨日未出现
- **持续热门**：连续多日上榜
- **退热项目**：昨日上榜但今日消失

### Step 3 — 生成报告

按“总-分”方式生成 Markdown 报告：先给一张总览表方便快速扫描，再给每个项目一张详细项目卡片。总览表不要出现 Forks、Stars、License 三列。

```markdown
# GitHub 爆火项目日报

📅 {YYYY-MM-DD}（{星期}）| 数据源：GitHub Trending

---

## 一、今日总览

| # | 项目 | 地址 | 今日新增 | 语言 | 分类 | 一句话简介 |
|---|------|------|----------|------|------|------------|
| 1 | owner/repo | https://github.com/owner/repo | +1,200 | Python | AI Video | 一键生成短视频的 AI 工具链 |

---

## 二、今日要点

1. **{要点1}** — 一句话概述今天最重要的技术信号
2. **{要点2}** — 一句话概述值得关注的新趋势
3. **{要点3}** — 一句话概述最值得开发者马上看的项目

---

## 三、项目详解

### 01. {项目名}

| 字段 | 内容 |
|---|---|
| 项目定位 | {用一句话说清它解决什么问题} |
| GitHub | https://github.com/owner/repo |
| 技术栈 | Python / TypeScript / Java / Kotlin / Rust |
| 今日新增 | +1,200 |
| 分类 | AI Agent / LLM Infra / DevTools / Android / Creative / Productivity |

**它能做什么？**

- {能力 1：面向真实用户价值，不照抄 README}
- {能力 2}
- {能力 3}

**核心亮点**

> {2-4 句分析，说明为什么它今天值得关注。要有技术判断、场景判断或产品判断。}

**适合谁？**

{目标用户，比如：内容创作者、AI 应用开发者、DevOps 工程师、Android 玩家、开源工具作者。}

**风险/注意**

{生产使用前要注意的限制：稳定性、依赖外部服务、部署成本、许可证不清晰、维护活跃度等。没有明显风险时写“暂无明显风险，建议先看 README 和 Issue 活跃度”。}

---

### 02. {项目名}

（同上格式，Top 15 每个项目都要有项目卡片）

---

## 四、领域分布

| 领域 | 项目数 | 代表项目 | 今日信号 |
|------|--------|----------|----------|
| AI/ML | N | repo1, repo2 | {一句话趋势} |
| DevTools | N | repo3 | {一句话趋势} |

---

## 五、新晋项目（首次上榜）

- **owner/repo** — {描述} | {为什么值得关注}

（如无前一日报告可对比，此栏标注“首日追踪，无对比数据”）

---

## 六、分析师点评

> 2-3 句整体趋势分析，包括：
> - 哪个领域最热
> - 是否有值得深入关注的新趋势
> - 对开发者的建议

---

## 七、产物位置

- 日报文件：`~/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD.md`
- 报告索引：`~/.hermes/profiles/content-studio/reports/index.md`
```

### Step 4 — 归档

将报告写入归档目录（同日覆盖）：

```bash
REPORT_DIR="$HOME/.hermes/profiles/content-studio/reports"
YEAR=$(date +%Y)
MONTH=$(date +%m)
TODAY=$(date +%Y-%m-%d)

mkdir -p "$REPORT_DIR/$YEAR/$MONTH"
# 将报告写入此路径（已存在则覆盖，⚠️ 必须使用 `write_file` 工具，绝对不要用 shell redirect）：
# $REPORT_DIR/$YEAR/$MONTH/$TODAY.md
```

### Step 5 — 分发

检查分发配置并执行（初版仅本地归档）：

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
CONFIG="$HERMES_HOME/skills/content-studio/knowledge-library/assets/dispatcher_config.yaml"
if [ -f "$CONFIG" ]; then
  echo "分发配置存在，按配置执行"
fi
```

初版做本地文件归档、报告索引更新和 stdout 输出，供 Hermes Jobs 页面查看。若 `report_dispatcher.py` 存在，归档后调用它按配置分发：

```bash
python3 "$HERMES_HOME/skills/content-studio/knowledge-library/scripts/report_dispatcher.py" \
  "$HERMES_HOME/reports/YYYY/MM/YYYY-MM-DD.md" \
  --report-dir "$HERMES_HOME/reports"
```

---

## 规则

- **数据准确**：今日新增、语言、描述必须来自 GitHub API 或 GitHub Trending 页面，不可编造
- **同日覆盖**：如果当日已有报告，直接覆盖
- **中文为主**：报告用中文，项目名和技术术语保留英文
- **总览克制**：总览表不要放 Forks、Stars、License，避免信息过载
- **项目详解有料**：每个项目都要回答“是什么、能做什么、为什么值得看、适合谁、风险是什么”
- **要点优先**：3 条要点是报告最重要的部分，要写得有洞察
