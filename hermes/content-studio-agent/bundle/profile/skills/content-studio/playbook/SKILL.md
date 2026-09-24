---
name: playbook
description: "内容策划主编完整工作手册。定义日常工作节奏、指令路由、质量标准和异常处理。Agent 的核心 SOP，所有工作从这里开始。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [SOP, 工作手册, 编排, GitHub]
    related_skills: [github-daily, tool-radar, weekly-digest, video-script-generator, storyboard-planner, video-pipeline, video-execution, moneyprinter-video, hybrid-video, web-story-renderer, community-pulse, knowledge-library, help-manual]
---

# 内容策划主编 — 工作手册

这是我的**核心工作手册**。所有任务从这里开始，按流程执行，不靠即兴发挥。

---

## 一、指令路由

收到任何用户指令时，**第一步**是路由到对应流程：

```
用户输入
  │
  ├─ 匹配 "GitHub帮助" / "分析师帮助" / "帮助" / "help" / "使用说明" / "怎么用" / "有哪些 skills"
  │    → 调用 help-manual：`references/help-quick.md` 简版（Workspace 友好）
  ├─ 匹配 "help full" / "帮助 详细" / "完整帮助" / "命令大全"
  │    → help-manual + terminal `content-studio.sh help`（不要贴整份 SKILL.md）
  │
  ├─ 匹配 "日报" / "daily" / "今日" / "trending" / "热门"
  │    → 跳转 [二、日报流程]
  │
  ├─ 匹配 "周报" / "weekly" / "本周" / "深度分析"
  │    → 跳转 [三、周报流程]
  │
  ├─ 匹配 "生产级工具" / "工具雷达" / "production radar" / "有用项目"
  │    → 跳转 [四、生产级工具雷达流程]
  │
  ├─ 匹配 "社区脉搏" / "community pulse" / "大家在说什么" / "last30days" / "l30d"
  │    → 跳转 [五c、社区脉搏简报流程]
  │
  ├─ 匹配 "生成 sop视频" / "sop视频" / "主视频" / "GitHub 滚动视频" / "核心视频"
  │    → **先读 video-execution Skill**
  │    → terminal 执行: "$HERMES_HOME/scripts/content-studio.sh" video-pipeline [YYYY-MM-DD]
  │    → 按 Progress Report Template 分 Stage 汇报（禁止无 terminal 声称渲染中）
  │
  ├─ 匹配 "生成 mpt视频" / "生成 mpt 视频" / "mpt视频" / "MPT 视频" / "素材混剪视频"
  │    → **先读 video-execution + moneyprinter-video Skill**
  │    → 向用户说明：MPT 画面为 Pixabay 通用素材，**不会**展示 GitHub 项目页面
  │    → **禁止** `video-pipeline`；**禁止** 同轮跑 pipeline + mpt 两条命令
  │    → 已有 *-video-script.md → 仅 terminal: video-mpt [YYYY-MM-DD]
  │    → 无脚本 → 仅 terminal: video-mpt-pipeline [YYYY-MM-DD]
  │    → 按 Progress Report Template 汇报
  │
  ├─ 匹配 "生成 hybrid视频" / "hybrid视频" / "生成 AI增强视频" / "生成相关素材视频"
  │    → **先读 video-execution + hybrid-video Skill**
  │    → 向用户说明：这是第三条独立链路，不覆盖 sop/mpt 产物
  │    → terminal 执行: "$HERMES_HOME/scripts/content-studio.sh" video-hybrid-pipeline [YYYY-MM-DD]
  │    → 输出 *-hybrid-storyboard.md / *-hybrid-production-spec.yaml / *-hybrid-video.mp4
  │
  ├─ 匹配 "hybrid 进度" / "hybrid-status" / "AI增强视频状态"
  │    → terminal: "$HERMES_HOME/scripts/content-studio.sh" hybrid-status [YYYY-MM-DD]
  │    → 把 spec/assets/video 状态贴回 Chat
  │
  ├─ 匹配 "视频进度" / "渲染状态" / "sop 跑到哪" / "sop-status"
  │    → terminal: "$HERMES_HOME/scripts/content-studio.sh" sop-status [YYYY-MM-DD]
  │    → 把 CONTENT_STUDIO_PROGRESS 行与产出文件列表贴回 Chat
  │
  ├─ 匹配 "视频" / "video" / "小红书" / "脚本" / "分镜" / "storyboard"
  │    ├─ "MoneyPrinterTurbo" / "通用视频" / "素材混剪" / "MPT 视频" / "video-mpt"
  │    │    → 跳转 [五d、MoneyPrinterTurbo 通用视频流程]（或上方 mpt视频 快捷路由）
  │    ├─ "生成视频" / "video pipeline" / "出视频" / "视频 pipeline"
  │    │    → 跳转 [五b、视频 Pipeline 流程]（或上方 sop视频 快捷路由）
  │    ├─ "分镜" / "storyboard" / "production spec"
  │    │    → 调用 storyboard-planner Skill，把已有脚本转成分镜和 production spec
  │    └─ 其他（仅脚本）
  │         → 跳转 [五、视频脚本流程]
  │
  ├─ 匹配 "重跑今天 内容策划主编完整 SOP" / "重跑 SOP" / "sop" / "rerun" / "full" / "all" / "所有报告"
  │    → 必须直接执行: "$HERMES_HOME/scripts/content-studio.sh" sop
  │    → 如用户指定 YYYY-MM-DD，则执行: "$HERMES_HOME/scripts/content-studio.sh" sop YYYY-MM-DD
  │
  ├─ 匹配 "报告库" / "查看 reports" / "查看报告目录" / "打开最新日报" / "最新周报"
  │    → 跳转 [六、报告库流程]
  │
  ├─ 匹配 "分析 owner/repo" / 给了具体仓库 URL
  │    → 跳转 [七、单项目深度分析]
  │
  ├─ 匹配 "审查" / "review" / "PR #N" / PR 链接
  │    → 调用 github-code-review Skill
  │
  ├─ 匹配 "issue" / "问题" + 仓库名
  │    → 调用 github-issues Skill
  │
  └─ 其他 GitHub 相关
       → 用已有 Skills 直接回答
       → 如超出能力边界，回复"这个需要 coder profile 来处理"
```

---

## 二、日报流程

**触发**: Cron 每日 08:00 / 手动指令

### 前置检查

```
1. GitHub API 是否可达？
   → curl -s https://api.github.com/rate_limit
   → 如不可达: 输出"网络不通，跳过本日日报"，结束
   
2. 今日日报是否已存在？
   → 检查 reports/YYYY/MM/YYYY-MM-DD.md
   → 如存在: 提示"今日日报已存在，将覆盖"，继续
```

### 执行

```
Step 1 — 数据采集
  │  调用 github-daily Skill > Step 1
  │  数据源优先级:
  │    a. github_trending_snapshot.py（抓取 GitHub Trending 页面，排名以页面顺序为准）
  │    b. gh repo view / GitHub REST API（只补充 Stars、语言、描述等元数据，不改变排名）
  │    c. gh search repos（仅作为 Trending 页面抓取失败时的降级候选，不作为官方 Trending 排名）
  │  至少要获取 15 个项目的: 名称、Stars、语言、描述
  │
  ▼ 失败？
  │  → 429 限速: sleep 60s，重试，最多 3 次
  │  → 网络错误: 用最近一次缓存数据降级（如有），标注"数据非实时"
  │  → 全部失败: 输出"数据采集失败，不生成空报告"，结束
  │
Step 2 — 历史对比
  │  调用 github-daily Skill > Step 2
  │  读取前一日报告，识别: 新晋 / 持续热门 / 退热
  │  如无前日数据: 标注"首日追踪，无对比"
  │
Step 3 — 生成报告
  │  调用 github-daily Skill > Step 3（按其模板格式）
  │  质量自检（见 [七、质量标准]）:
  │    □ 3 条要点是否有洞察？（不能是空洞罗列）
  │    □ 项目数据是否来自 API？（不能编造）
  │    □ 描述是否控制在一句话内？
  │  如不合格: 重写要点部分，不发出低质量报告
  │
Step 4 — 归档
  │  调用 github-daily Skill > Step 4
  │  写入 reports/YYYY/MM/YYYY-MM-DD.md（同日覆盖）
  │
Step 5 — 分发
     调用 github-daily Skill > Step 5
     更新 reports/index.md
     当前: 本地归档 + stdout 输出 + 可选 webhook
     未来: 按 dispatcher_config.yaml 扩展更多渠道
```

### 完成标志

```
✅ reports/YYYY/MM/YYYY-MM-DD.md 已写入
✅ 报告至少包含 15 个项目
✅ 3 条要点通过质量自检
✅ stdout 已输出完整报告
```

---

## 三、周报流程

**触发**: Cron 每周一 08:00 / 手动指令

### 前置检查

```
1. 本周有多少份日报？
   → ls reports/YYYY/MM/*.md | grep -v weekly | grep -v video | 统计
   → 如 = 0: 先执行一次日报流程，再继续
   → 如 < 3: 提示"本周日报数据不足，周报将基于有限数据 + 实时补充"

2. 今日周报是否已存在？
   → 检查 reports/YYYY/MM/YYYY-MM-DD-weekly.md
   → 如存在: 提示"将覆盖"，继续
```

### 执行

```
Step 1 — 汇总日报
  │  调用 github-weekly-digest Skill > Step 1
  │  读取 7 天日报，提取所有项目、去重、统计连续上榜天数
  │  如日报不足 7 天: 用 GitHub API 补充缺失天数的数据
  │
Step 2 — 综合排名
  │  调用 github-weekly-digest Skill > Step 2
  │  按周累计 Star 增长排序，Top 10
  │  对 Top 10 调 GitHub API 获取详细信息
  │
Step 3 — 垂直领域分析
  │  调用 github-weekly-digest Skill > Step 3
  │  4 个领域: AI Agent / LLM Infra / DevTools / Android
  │  每个领域必须有:
  │    □ 项目清单（带数据）
  │    □ 架构特点分析
  │    □ 趋势判断（2-3 句，不能是废话）
  │
Step 4 — 生成周报
  │  调用 github-weekly-digest Skill > Step 4（按其模板格式）
  │  质量自检（见 [七、质量标准]）
  │
Step 5 — 归档
     写入 reports/YYYY/MM/YYYY-MM-DD-weekly.md
```

### 完成标志

```
✅ reports/YYYY/MM/YYYY-MM-DD-weekly.md 已写入
✅ Top 10 排名数据完整
✅ 4 个垂直领域各有分析
✅ 趋势对比（持续/新晋/退热）有具体项目名和数据
```

---

## 四、生产级工具雷达流程

**触发**: Cron 每日 / 手动指令

### 前置检查

```
1. GitHub API 是否可达？
   → curl -s https://api.github.com/rate_limit
   → 如不可达: 输出"网络不通，跳过工具雷达"，结束

2. 今日工具雷达是否已存在？
   → 检查 reports/YYYY/MM/YYYY-MM-DD-production-radar.md
   → 如存在: 提示"将覆盖"，继续
```

### 执行

```
Step 1 — 检索候选项目
  │  调用 github-tool-radar Skill > Step 1
  │  覆盖: AI Agent / MCP / DevTools / 文档数据处理 / 自托管 / Android
  │
Step 2 — 生产级筛选
  │  调用 github-tool-radar Skill > Step 2
  │  只保留: 活跃维护、README 清楚、可部署/可集成、有真实使用价值的项目
  │
Step 3 — 生成工具雷达
  │  调用 github-tool-radar Skill > Step 3
  │  必须包含: 推荐总览 + 最值得试用的 5 个工具 + 分类清单 + 今日结论
  │
Step 4 — 归档与分发
     写入 reports/YYYY/MM/YYYY-MM-DD-production-radar.md
     更新 reports/index.md
```

### 完成标志

```
✅ reports/YYYY/MM/YYYY-MM-DD-production-radar.md 已写入
✅ 至少 5 个项目有完整项目卡片
✅ 每个项目都说明生产价值和接入风险
✅ reports/index.md 已更新
```

---

## 五、视频脚本流程

**触发**: 仅手动指令（不自动执行）

### 前置检查

```
1. 来源报告是否存在？
   → 日报短视频优先读取 reports/YYYY/MM/YYYY-MM-DD.md
   → 周报深度视频读取最新 *-weekly.md
   → 如不存在: 提示缺少来源报告，先执行日报/周报
```

### 执行

```
Step 1 — 读取来源报告
  │  调用 video-script-generator Skill > Step 1
  │
Step 2 — 提炼本期主题
  │  调用 video-script-generator Skill > Step 2
  │  必须输出 thesis、趋势标签、核心证据和叙事链
  │
Step 3 — 选择叙事链项目
  │  从允许范围内选择能形成关系的项目
  │  每个项目必须有链上角色、原始排名、GitHub URL
  │
Step 4 — 生成趋势分析脚本
  │  调用 video-script-generator Skill > Required Output Format
  │  质量自检:
  │    □ 开场是否先给行业判断？
  │    □ 项目之间是否形成叙事链？
  │    □ 每个项目是否有链上角色？
  │    □ 是否包含分镜表？
  │    □ 口播文本是否无舞台标记？
  │
Step 5 — 归档
     写入 reports/YYYY/MM/YYYY-MM-DD-video-script.md
```

---

## 五b、视频 Pipeline 流程

**触发**: 日报完成后自动触发 / 用户说「**生成 sop视频**」/「生成视频」/ 手动 `content-studio.sh video-pipeline`

**Hermes 执行**: 必须先读 **`video-execution`** Skill，用 **`terminal`** 跑绝对路径命令；禁止无 terminal 声称「正在渲染」。完成后按 Progress Report Template 汇报各 Stage。

### 执行

```
Stage 1 — 生成趋势分析视频脚本（90-150 秒日报版）
  │  调用 video-script-generator Skill
  │  数据源: 今日日报 GitHub Trending Top 10
  │  输出格式: 本期主题 + 入选项目叙事链 + 完整口播文本 + 分镜表 + 小红书发布素材
  │  写入 reports/YYYY/MM/YYYY-MM-DD-video-script.md
  │
Stage 2 — 分镜规划（目标规范）
  │  调用 storyboard-planner Skill
  │  输出: YYYY-MM-DD-storyboard.md + YYYY-MM-DD-production-spec.yaml
  │  如果当前渲染器尚未完全支持 spec，也必须保留分镜规划作为审核依据
  │
Stage 3 — 视频生成
  │  执行 content-studio.sh video-pipeline（内部调用 video_generator.py）
  │  主链路: TTS + 日榜/概念画面 + GitHub 页面滚动红框 + 字幕 + ffmpeg
  │  失败策略: GitHub 页面滚动红框失败即中止，不生成 card-scroll / 静态背景版本
  │  输出: reports/YYYY/MM/YYYY-MM-DD-video.mp4
  │
Stage 4 — 配套 Web Story 页面（视频成功后自动生成）
  │  调用 web-story-renderer（同一脚本 + 日报，默认 5 个项目）
  │  只生成 HTML + 预览图，不重复录第二份 mp4（主成片已是 *-video.mp4）
  │  输出: assets/YYYY-MM-DD-web-story/index.html（可部署到静态站点对外发布）
  │
Stage 5 — 输出发布素材包
     提取封面: YYYY-MM-DD-video-cover.jpg
     生成发布指引: YYYY-MM-DD-video-publish.md
     更新 reports/index.md
     输出: 视频路径 + 封面 + 标题备选 + 标签 + 发布时间建议
```

### 完成标志

```
✅ YYYY-MM-DD-video-script.md 已写入
✅ YYYY-MM-DD-video.mp4 已生成，且日志不包含 card-scroll
✅ assets/YYYY-MM-DD-web-story/index.html 已生成（配套可发布页面）
✅ YYYY-MM-DD-video-publish.md 包含完整发布指引
✅ reports/index.md 已更新
```

---

## 五d、MoneyPrinterTurbo 通用视频流程

**触发**: 用户说「**生成 mpt视频**」/「MoneyPrinterTurbo / 通用视频 / 素材混剪 / MPT 视频」/ 手动 `content-studio.sh video-mpt-pipeline`

**Hermes 执行**: 必须先读 **`video-execution`** + **`moneyprinter-video`**；向用户说明 MPT **画面为通用素材，非 GitHub 页面**；用 **`terminal`** 执行 `video-mpt-pipeline`。

**与核心链路的区别**: 本流程走 `moneyprinter-video` Skill，产出 `*-mpt-video.mp4`；**不**生成 GitHub 页面滚动、项目介绍页、日榜开场图。日报 SOP 和 Cron **不得**默认走本流程。

### 前置检查

```
1. MoneyPrinterTurbo 服务是否可达？
   → curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8082/docs
   → 如不可达: 输出"MoneyPrinterTurbo 未启动"，结束

2. 视频脚本是否存在？（video-mpt 仅渲染时）
   → 检查 reports/YYYY/MM/YYYY-MM-DD-video-script.md
   → 如不存在: 先执行 [五、视频脚本流程] 或 video-mpt-pipeline
```

### 执行

```
Stage 1 — 脚本（video-mpt-pipeline 时）
  │  调用 video-script-generator Skill（与核心链路共用口播规范）
  │  写入 YYYY-MM-DD-video-script.md
  │
Stage 2 — MoneyPrinterTurbo 渲染
  │  执行 content-studio.sh video-mpt 或 video-mpt-pipeline
  │  内部调用 moneyprinter-video/scripts/moneyprinter_video.py
  │  API: POST /api/v1/videos → GET /api/v1/tasks/{task_id}
  │  失败策略: 中止，不降级到 GitHub 滚动链路
  │
Stage 3 — 发布素材包
     输出 YYYY-MM-DD-mpt-video.mp4
     封面 YYYY-MM-DD-mpt-video-cover.jpg
     发布指引 YYYY-MM-DD-mpt-video-publish.md
```

### 完成标志

```
✅ YYYY-MM-DD-mpt-video.mp4 已生成
✅ 未覆盖核心链路的 YYYY-MM-DD-video.mp4
✅ YYYY-MM-DD-mpt-video-publish.md 包含发布指引
```

---

## 五c、社区脉搏简报流程

**触发**: Cron 每日 08:45 / 用户说「社区脉搏」/ 手动 `content-studio.sh community-pulse`

**依赖**: 今日日报 `reports/YYYY/MM/YYYY-MM-DD.md`（不存在则先跑日报）

### 执行

```
Step 1 — 提取研究对象
  │  调用 community-pulse Skill > Step 1
  │  从日报 Trending Top 3 提取 owner/repo
  │
Step 2 — last30days 检索
  │  调用 last30days Skill，每个项目单独检索
  │  必须生成 --plan JSON；优先 Reddit/HN/GitHub 免费源
  │
Step 3 — 合成简报
  │  调用 community-pulse Skill > Step 3
  │  写入 reports/YYYY/MM/YYYY-MM-DD-community-pulse.md
  │
Step 4 — 推送
     更新 reports/index.md
     stdout 输出 3 条要点 + 文件路径
     可选 webhook 推送
```

### 完成标志

```
✅ YYYY-MM-DD-community-pulse.md 已写入
✅ 每个 Top 3 项目至少有 1 条带链接的社区引用
✅ reports/index.md 已更新
```

---

## 六、报告库流程

**触发**: 用户要查看、打开、检索或总结已生成报告

### 执行

```
Step 1 — 刷新报告索引
  │  调用 knowledge-library Skill（展示名 knowledge-library）> Step 1
  │  生成/更新 reports/index.md
  │
Step 2 — 路由用户意图
  │  "报告库" / "查看 reports" → 读取 reports/index.md
  │  "最新日报" → 读取最新 YYYY-MM-DD.md
  │  "最新工具雷达" → 读取最新 *-production-radar.md
  │  "最新周报" → 读取最新 *-weekly.md
  │  "最新视频脚本" → 读取最新 *-video-script.md
  │  "YYYY-MM-DD" → 列出该日期所有报告
  │
Step 3 — 输出
     Workspace Chat 优先直接贴内容或摘要，并给出绝对路径
```

### 完成标志

```
✅ reports/index.md 已刷新
✅ 已给出目标报告绝对路径
✅ 已按用户要求贴全文或摘要
```

---

## 七、单项目深度分析

**触发**: 用户给了具体仓库名或 URL

### 执行

```
1. 基本信息
   → gh repo view owner/repo --json stargazersCount,primaryLanguage,description,license,createdAt,updatedAt,forkCount,openIssues
   
2. 活跃度分析
   → 最近 30 天提交频率
   → Issue 关闭率
   → PR 合并速度
   → 贡献者数量趋势
   
3. 代码质量
   → 调用 codebase-inspection Skill 统计代码量
   → README 完整度评估
   → 文档/测试覆盖率评估
   
4. 竞品对比
   → 同领域 2-3 个类似项目对比
   
5. 输出
   → 结构化分析报告（不归档，直接回复用户）
```

---

## 八、异常处理手册

所有流程共享的异常处理规则：

| 异常 | 处理方式 | 重试 |
|------|---------|------|
| GitHub API 429 限速 | sleep 60s 后重试 | 最多 3 次 |
| GitHub API 403 认证 | 提示用户运行 `gh auth login` | 不重试 |
| 网络完全不通 | 用最近缓存数据降级，标注"非实时" | 不重试 |
| 缓存也没有 | 输出"数据采集失败"，**不生成空报告** | - |
| gh CLI 未安装 | 降级到 curl + REST API | - |
| 日报数据不足 | 用实时 API 补充 | - |
| 周报无日报依赖 | 先执行一次日报，再继续 | - |
| 工具雷达候选太少 | 放宽 stars 门槛但保留生产级筛选 | - |
| 报告索引不存在 | 调用 `report_index.py` 重新生成 | - |
| 指定日期没有报告 | 列出最近 10 份报告供用户选择 | - |
| 单个项目 API 失败 | 跳过该项目，不影响整体报告 | - |

**核心原则：宁可降级输出，不可生成假数据或空报告。**

---

## 九、质量标准

### 日报要点

```
✅ 好: "antirez 发布 ds4，Redis 之父进军本地 LLM 推理，Metal/CUDA 双端支持"
   → 有人物 + 有事件 + 有技术细节

❌ 差: "ds4 项目很受欢迎，获得了很多 Star"
   → 空洞、无信息增量、任何人都能写
```

### 领域分析

```
✅ 好: "本周 AI Agent 领域呈现'编排框架合并'趋势，LangGraph 和 CrewAI 都在
       向 event-driven 架构靠拢，暗示社区正在从 DAG 式编排转向响应式编排"
   → 有趋势判断 + 有具体证据 + 有前瞻性

❌ 差: "AI Agent 领域本周很活跃，有好几个项目上榜"
   → 废话，删掉也不影响任何人
```

### 生产级工具雷达

```
✅ 好: "这个 CLI 有 Docker 镜像、release、清晰配置示例，能直接接入 CI 处理构建缓存"
   → 有生产证据 + 有接入方式 + 有边界

❌ 差: "这个项目 Stars 很多，所以值得使用"
   → 只看热度，没有说明真实价值
```

### 视频脚本

```
✅ 好的 Hook: "你见过能自己修 Bug 的 AI 吗？这个项目上周涨了 8000 Star"
   → 问题引起好奇 + 数据制造紧迫感

❌ 差的 Hook: "今天给大家介绍一个有趣的开源项目"
   → 没有任何信息，用户直接划走
```

### 报告库

```
✅ 好: "已打开最新日报：/Users/.../2026-05-30.md，下面是正文..."
   → 路径清楚 + 内容可直接阅读

❌ 差: "你可以去 reports 目录看看"
   → 没有代用户完成查看动作
```

### 通用检查清单

每份报告发出前必须通过：

```
□ 所有数据来自 GitHub API，不是编造的
□ 项目链接可点击、格式正确
□ 没有"很多""非常""很好"等空洞形容词
□ 中文通顺，技术术语英文保留
□ 表格对齐、Markdown 语法正确
□ 文件已写入正确的归档路径
```

---

## 十、手动触发

除了 Cron 自动触发，任何时候可以手动运行：

```bash
# 通过脚本
"$HERMES_HOME/scripts/content-studio.sh" daily           # 今日日报
"$HERMES_HOME/scripts/content-studio.sh" radar           # 生产级工具雷达
"$HERMES_HOME/scripts/content-studio.sh" weekly          # 本周周报
"$HERMES_HOME/scripts/content-studio.sh" video           # 仅视频脚本
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline  # 完整视频 pipeline（脚本+GitHub滚动+素材包）
"$HERMES_HOME/scripts/content-studio.sh" video-mpt       # MoneyPrinterTurbo 素材混剪（复用脚本）
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-pipeline  # 脚本 + MoneyPrinterTurbo 完整链路
"$HERMES_HOME/scripts/content-studio.sh" library         # 报告库索引
"$HERMES_HOME/scripts/content-studio.sh" sop             # 重跑日常 SOP
"$HERMES_HOME/scripts/content-studio.sh" sop 2026-05-31  # 指定日期重跑日常 SOP
"$HERMES_HOME/scripts/content-studio.sh" daily 2026-05-29  # 指定日期
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-05-30 --auto  # 指定日期+自动发布

# 通过 Hermes Chat
hermes chat github  →  "日报" / "工具雷达" / "周报" / "视频" / "生成视频" / "报告库"
```

同日重复执行 = 覆盖，不保留多版本。

---

## 十一、归档结构

```
~/.hermes/profiles/content-studio/reports/
  ├── index.md                       ← 报告索引
  └── YYYY/
      └── MM/
          ├── YYYY-MM-DD.md                 ← 日报
          ├── YYYY-MM-DD-production-radar.md ← 生产级工具雷达
          ├── YYYY-MM-DD-weekly.md          ← 周报
          ├── YYYY-MM-DD-video-script.md    ← 趋势分析视频脚本
          ├── YYYY-MM-DD-storyboard.md      ← 视频分镜规划
          ├── YYYY-MM-DD-production-spec.yaml ← 视频生产规范
          ├── YYYY-MM-DD-video.mp4          ← 生成的视频（GitHub 滚动核心链路）
          ├── YYYY-MM-DD-mpt-video.mp4      ← MoneyPrinterTurbo 通用视频（可选）
          ├── YYYY-MM-DD-video-cover.jpg    ← 封面截图
          ├── YYYY-MM-DD-mpt-video-cover.jpg
          ├── YYYY-MM-DD-video-publish.md   ← 小红书发布指引（核心链路）
          └── YYYY-MM-DD-mpt-video-publish.md ← MPT 发布指引
```

---

## 十二、Skill 依赖关系

```
本手册 (playbook)
  │
  ├── 日报流程 ───→ github-daily Skill（模板 + 采集步骤）
  │
  ├── 工具雷达 ───→ github-tool-radar Skill（生产级工具发现）
  │
  ├── 周报流程 ───→ github-weekly-digest Skill（模板 + 分析步骤）
  │     │
  │     └── 依赖 ──→ 日报数据（如不足则先执行日报）
  │
  ├── 视频脚本 ──→ video-script-generator Skill（趋势分析脚本：thesis + 叙事链 + 分镜表）
  │     └── 依赖 ──→ 日报或周报数据
  │
  ├── 分镜规划 ──→ storyboard-planner Skill（storyboard + production spec）
  │     └── 依赖 ──→ video-script-generator 输出
  │
  ├── 视频 Pipeline → video-pipeline Skill（按脚本和分镜规范生成 GitHub 滚动视频 + 发布素材）
  │     ├── 依赖 ──→ 今日日报 + 视频脚本
  │     └── content-studio.sh video-pipeline → video_generator.py（TTS + GitHub 滚动 + ffmpeg）
  │
  ├── MPT 通用视频 → moneyprinter-video Skill（MoneyPrinterTurbo 素材混剪，与核心链路并行）
  │     ├── 依赖 ──→ 视频脚本（口播文本）
  │     └── content-studio.sh video-mpt → moneyprinter_video.py
  │
  ├── 报告库 ────→ knowledge-library Skill（展示名 knowledge-library，reports 目录查看、打开、摘要）
  │
  └── 辅助能力 ──→ github-auth / github-repo-management / github-code-review
                   github-issues / github-pr-workflow / codebase-inspection
```
