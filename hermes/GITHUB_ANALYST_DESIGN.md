# GitHub 分析师系统 — 完整设计文档

> **状态**: v1.0 初版设计
> **日期**: 2026-05-30
> **Owner**: gqli

---

## 1. 项目目标

构建一个基于 Hermes Agent 的 **GitHub 分析师角色**，实现：

- **每日 8:00** 自动分析 GitHub 热门项目，生成结构化日报
- **每周一 8:00** 生成深度分析周报（含垂直领域分析）
- **视频脚本** 自动生成，适配小红书短视频格式
- **手动触发** 随时执行任意报告，同日覆盖
- **可扩展分发** 初版本地归档，未来支持邮件/Webhook/Telegram 等

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                 GitHub Analyst System                     │
├───────────┬───────────┬────────────┬────────────────────┤
│ 日报 Skill │ 周报 Skill │ 视频脚本    │ 分发引擎           │
│ daily-    │ weekly-   │ video-     │ report-            │
│ trending  │ deep-     │ script-    │ dispatcher         │
│           │ analysis  │ generator  │ (可扩展)            │
├───────────┴───────────┴────────────┴────────────────────┤
│              Hermes Cron 调度层 + 手动触发后门            │
├─────────────────────────────────────────────────────────┤
│      数据源：GitHub Trending / GitHub API / gh CLI        │
└─────────────────────────────────────────────────────────┘
```

### 2.1 归档目录结构

```
~/.hermes/profiles/github/reports/
  └── 2026/
      └── 05/
          ├── 2026-05-30.md              ← 日报
          ├── 2026-05-26-weekly.md       ← 周报（每周一）
          └── 2026-05-26-video-script.md ← 视频脚本（随周报）
```

### 2.2 组件清单

| 组件 | 类型 | 触发方式 | 产出 |
|------|------|---------|------|
| `daily-trending` | Skill | Cron 每日 8:00 / 手动 | 日报 Markdown |
| `weekly-deep-analysis` | Skill | Cron 每周一 8:00 / 手动 | 周报 Markdown |
| `video-script-generator` | Skill | 手动 / 随周报 | 小红书视频脚本 |
| `report-dispatcher` | 脚本 | 报告生成后 hook | 分发到各渠道 |
| `github-analyst-trigger.sh` | 脚本 | 手动 CLI | 后门触发器 |

---

## 3. 日报 Skill 设计 (`daily-trending`)

### 3.1 报告格式

```markdown
# GitHub 热门项目日报

📅 2026-05-30（周五）| 数据源：GitHub Trending

---

## 🔥 今日要点

1. **[要点1]** — 一句话概述
2. **[要点2]** — 一句话概述
3. **[要点3]** — 一句话概述

---

## 📊 Top 15 热门项目

| # | 项目 | ⭐ Stars | 📈 今日 | 语言 | 简介 |
|---|------|---------|--------|------|------|
| 1 | [owner/repo](url) | 12.3k | +1,200 | Python | 一句话描述 |
| 2 | ... | ... | ... | ... | ... |

---

## 🏷️ 领域分布

| 领域 | 项目数 | 代表项目 |
|------|--------|---------|
| AI/ML | 5 | repo1, repo2 |
| DevTools | 3 | repo3 |
| Web | 2 | repo4 |

---

## 🆕 新晋项目（首次上榜）

- **owner/repo** — 描述 | 为什么值得关注

---

## 📝 分析师点评

> 2-3 句整体趋势分析
```

### 3.2 数据采集流程

```
1. 抓取 GitHub Trending（today + this week）
2. 用 GitHub API 补充 Star 数、语言、描述
3. 与前一日报告对比（识别新晋/持续上榜）
4. 生成结构化报告
5. 写入 reports/YYYY/MM/YYYY-MM-DD.md
6. 调用 report-dispatcher 分发
```

---

## 4. 周报 Skill 设计 (`weekly-deep-analysis`)

### 4.1 报告格式

```markdown
# GitHub 周报 — 深度分析

📅 2026-05-26 ~ 2026-05-30 | 第22周

---

## 🏆 本周 Top 10 明星项目

| # | 项目 | 周 Star 增长 | 总 Stars | 领域 | 首次/持续 |
|---|------|------------|---------|------|----------|
| 1 | owner/repo | +5,200 | 28.3k | AI Agent | 持续 3 周 |

---

## 🔬 垂直领域深度分析

### 🤖 AI Agent / Multi-Agent

| 项目 | Stars | 本周变化 | 架构特点 | 值得关注的原因 |
|------|-------|---------|---------|--------------|
| ... | ... | ... | ... | ... |

**领域趋势：** 2-3 句分析

### 🧠 LLM Infra / 模型服务

（同上格式）

### 🛠️ DevTools / 开发者工具

（同上格式）

### 📱 Android 好玩项目

（同上格式）

---

## 📈 周趋势对比

- **持续上升：** project1 (连续3周), project2
- **新晋黑马：** project3 (从0到5k stars)
- **退热项目：** project4 (上周Top5，本周跌出)

---

## 🎯 本周推荐

> **最值得学习：** project — 原因
> **最值得关注：** project — 原因
> **最具创意：** project — 原因
```

### 4.2 分析维度

对 Top 项目的深度分析包括：
- 代码规模与质量（LoC、测试覆盖、CI）
- 社区活跃度（Issue 响应时间、PR 合并率、Contributor 数）
- 架构创新点
- 适用场景与局限性
- 与同领域竞品的对比

---

## 5. 视频脚本 Skill 设计 (`video-script-generator`)

### 5.1 脚本格式（适配小红书 3-5 分钟短视频）

```markdown
# 视频脚本：本周 GitHub 最火项目 | 第22周

## 基本信息
- **时长**: 3-5 分钟
- **风格**: 技术科普 + 项目展示
- **BGM**: 轻快电子风

---

## 开场（15秒）

**画面**: GitHub Trending 页面滚动
**口播**: "这周 GitHub 上又出了不少好东西，我帮你筛了最值得看的 5 个项目"

## 项目1（40-60秒）

**项目名**: owner/repo
**画面**: 项目 README 截图 → Demo 演示 → 架构图
**口播**:
- Hook: "你见过能自己写代码的 AI 吗？"
- 介绍: 一句话说清楚它是什么
- 亮点: 最吸引人的 1-2 个特性
- 数据: "一周涨了 5000 Star"

## 项目2-5（同上格式）

## 总结（15秒）

**口播**: "这周你最想试哪个？评论区告诉我"
**画面**: 5 个项目 Logo 拼图

---

## 标题备选
1. 「本周GitHub最火的5个项目，第3个太好玩了」
2. 「AI圈这周又卷疯了，这些开源项目你该知道」
3. 「程序员本周必看：GitHub热门TOP5」

## 标签
#GitHub #开源 #程序员 #AI #科技 #编程
```

---

## 6. 分发引擎设计 (`report-dispatcher`)

### 6.1 插件式架构

```python
# 分发渠道配置 (dispatcher_config.yaml)
channels:
  local:
    enabled: true
    # 默认通道，报告写入本地文件

  # --- 以下为扩展通道，按需启用 ---
  email:
    enabled: false
    to: "your@email.com"
    subject_template: "GitHub日报 - {date}"

  webhook:
    enabled: false
    url: "https://your-webhook-url"
    # 支持飞书/企业微信/钉钉

  telegram:
    enabled: false
    # 使用 Hermes 原生 deliver=telegram
```

### 6.2 扩展方式

添加新渠道只需：
1. 在 `dispatcher_config.yaml` 中添加渠道配置
2. 在 `scripts/dispatchers/` 下添加对应发送脚本
3. 无需修改任何 Skill

---

## 7. 手动触发后门

### 7.1 触发脚本

```bash
# 触发日报（当日覆盖）
./github-analyst.sh daily

# 触发周报
./github-analyst.sh weekly

# 触发视频脚本（基于最近一期周报）
./github-analyst.sh video

# 触发全部（日报 + 周报 + 视频脚本）
./github-analyst.sh all

# 指定日期（补历史数据）
./github-analyst.sh daily 2026-05-29
```

### 7.2 实现原理

通过 `hermes cron run <job-name>` 立即触发，结果写入相同日期文件（自动覆盖）。

---

## 8. Cron 定时任务配置

| 任务名 | Schedule | Profile | 说明 |
|--------|----------|---------|------|
| `github-daily-trending` | 每日 08:00 | github | 日报 |
| `github-weekly-analysis` | 每周一 08:00 | github | 周报 |

---

## 9. 未来扩展方向（SOP）

### 9.1 GitHub 分析师应具备的其他 Skill

| Skill | 优先级 | 说明 |
|-------|--------|------|
| **star-history-tracker** | P1 | 跟踪关注项目的 Star 增长曲线，发现加速/减速拐点 |
| **repo-deep-scanner** | P1 | 对指定仓库做完整体检（代码质量、安全、架构） |
| **competitor-monitor** | P2 | 监控竞品仓库动态（新 Release、重大 PR、Issue 讨论） |
| **developer-radar** | P2 | 追踪明星开发者动态（新项目、贡献活动） |
| **ecosystem-mapper** | P2 | 绘制特定领域的项目生态图谱 |
| **release-digest** | P3 | 汇总关注项目的版本更新日志 |
| **issue-sentiment** | P3 | 分析热门项目 Issue 区的情绪和痛点 |
| **fork-network-analyzer** | P3 | 分析 Fork 网络，发现有价值的分支创新 |

### 9.2 完整 SOP（标准操作流程）

```
每日 SOP:
  08:00  Cron 触发 daily-trending
         → 抓取 Trending + API 补充数据
         → 生成日报 → 归档 → 分发
         → 全程 ≤ 5 分钟

每周 SOP:
  周一 08:00  Cron 触发 weekly-deep-analysis
              → 汇总本周 7 天日报
              → 垂直领域深度分析
              → 生成周报 → 归档 → 分发
              → 全程 ≤ 15 分钟

  周一 09:00  手动或自动触发 video-script-generator
              → 读取本周周报
              → 生成小红书视频脚本
              → 归档
              → 人工审核后录制

手动 SOP:
  任意时间  ./github-analyst.sh [daily|weekly|video|all]
           → 立即执行，同日覆盖
           → 可指定历史日期补数据

小红书发布 SOP:
  1. 审核视频脚本（AI 生成 → 人工微调）
  2. 准备素材（项目截图、Demo 录屏、架构图）
  3. 录制/剪辑（3-5 分钟）
  4. 发布（标题 + 标签已在脚本中生成）
  5. 互动回复
```

---

## 10. 文件清单

```
~/.hermes/profiles/github/
├── SOUL.md                              ← 更新：加入分析师角色定义
├── scripts/
│   ├── github_trending_snapshot.py      ← 已有
│   ├── github-analyst.sh               ← 新增：手动触发后门
│   └── dispatchers/
│       └── dispatcher_config.yaml      ← 新增：分发配置
├── skills/
│   └── github-analyst/                 ← 新增：Skill 组
│       ├── DESCRIPTION.md
│       ├── daily-trending/
│       │   └── SKILL.md
│       ├── weekly-deep-analysis/
│       │   └── SKILL.md
│       └── video-script-generator/
│           └── SKILL.md
└── reports/                            ← 新增：报告归档
    └── 2026/
        └── 05/
            └── ...
```
