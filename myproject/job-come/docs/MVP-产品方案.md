# JobCome MVP 产品方案

| 项 | 内容 |
|---|---|
| 产品名 | JobCome |
| 文档版本 | 1.4 |
| 日期 | 2026-09-02 |
| 状态 | **MVP 规格冻结候选** — 供技术方案与 W1 开发对齐 |
| 上位文档 | [`产品设计.md`](产品设计.md) v0.6 |
| 代码目录 | `/Users/gqli/work/deepagents/job-come/` |

本文是 **MVP 层产品方案（PRD）**：把上位产品设计收敛成可验收的范围、页面、对象 schema、流程与竖切故事。不重复市场分析与竞品长文，需要背景时回读 [`产品设计.md`](产品设计.md)。

---

## 执行摘要

### 产品全貌

JobCome 是面向 **2–10 年经验知识工作者** 的独立 **Web 求职工作流** 产品。终极目标不是在 App 里改完简历，而是帮用户在 **目标公司拿下 Offer**。

**定位句：**

> 帮用户发现招聘、拔高简历，先用非目标公司练手，再攻目标公司；每次真面与模拟都沉淀真题，形成个人面试库，越练越强。导出 PDF/Word，投递用户自己做。

**三条差异化（缺一不可）：**

| # | 差异化 | 含义 |
|---|---|---|
| 1 | **剑指 Offer** | 一切围绕目标公司签约，导出只是手段 |
| 2 | **先练手、后攻目标** | 非目标公司攒真面经验，达标后再打 dream company |
| 3 | **面试库飞轮** | 记公司/岗位/真题 → 模拟抽库 → 迭代最佳答法 → 再真面 → 库更厚 |

**五块产品能力（终态）：**

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 档案中心  │   │ 岗位中心  │   │ 进攻计划  │   │ 面试中心  │   │   设置   │
│建档·拔高  │   │JD·Fit   │   │练手→目标 │   │模拟·记题  │   │隐私·语言 │
│导出      │   │标签     │   │达标门禁  │   │题库·答法  │   │         │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

**用户完整旅程（产品终态）：**

```
建档 + 拔高导出
    ↓
发现岗位（粘贴 JD / 后期聚合招聘）→ 标练手 / 目标 → Fit 判断
    ↓
【练手期】非目标公司：自行投递 → 真面前模拟 → 真面后记题入库
    ↓
库驱动再模拟 → 同一题迭代「最佳参考答法」
    ↓
达标 → 【目标期】攻 dream company → 高压模拟 → 真面 → Offer
    ↓
（M3+）自愿脱敏贡献社区题库，帮同岗位其他人
```

**分阶段路线图：**

| 阶段 | 主题 | 核心能力 |
|---|---|---|
| **M1 MVP（12 周，本期）** | 打穿竖切 | 备稿 + 记面试 + 个人库 + 库驱动模拟 + 参考答法 |
| **M2** | 攻目标加厚 | Scout 聚合招聘、Campaign 达标强化、目标高压模式、答案版本对比 |
| **M3** | 网络效应 | 社区题库、同岗聚类、挂点复盘自动化 |

**明确不做：** 代投递、海投、通用八股题库、浏览器插件；MVP 不做支付。

---

### 第一期重点（M1 / 12 周）

第一期 **不是** 做全功能求职平台，而是 **打穿一条可演示、可自用的闭环**：

> **建档拔高导出 → 标练手/目标 → 模拟 → 记真题 → 库抽题再模拟 → 保存参考答法**

**第一期必须交付：**

| 优先级 | 能力 | 为什么 |
|---|---|---|
| **P0** | 档案建档 + 拔高 + PDF/Word 导出 | 入口：用户要有能投的亮简历 |
| **P0** | 真面后记题（公司/岗位/轮次/≥3 题） | 飞轮起点：真题从用户自己面试来 |
| **P0** | 个人面试库 + 模拟优先抽库内题 | 核心差异化：不是每次泛生成 |
| **P0** | 参考答法 + 同一题多轮对比 | 渐进提升：答得更好，不是刷题量 |
| **P1** | 粘贴 JD + Fit + 练手/目标标签 | 支撑针对性备稿和进攻节奏 |
| **P1** | 练手/目标 Campaign + 达标规则 | 产品主动规划「先练后攻」 |
| **P1** | 练手模式 vs 目标模式模拟 | 两种面试压力与复盘重点 |

**第一期刻意不做：** 招聘爬虫/岗位聚合（只粘贴 JD）、社区题库、代投递、支付、语音面试、求职 CRM 看板。

**第一期验收一句话：** 作者 + 5 个熟人能在浏览器跑通——上传简历 → 拔高导出 → 模拟一轮 → 真面后记 3 道题 → 第二次模拟抽到库内题 → 保存并对比参考答法。

**12 周重心分布：**

| 周次 | 重心 |
|---|---|
| W1–W2 | 档案 + 导出（先有能投的简历） |
| W3–W4 | JD、Fit、练手/目标标记 |
| **W5–W8** | **面试飞轮核心**：模拟 → 记题 → 个人库 → 参考答法 |
| W9–W11 | 岗位关联、目标模式、达标追踪 |
| W12 | 全链路演示冻结 |

> **W5–W8 是第一期真正的产品灵魂**；W1–W4 是必要前置，但不是差异化所在。

**一句话：**

- **全貌** = 拔高简历 + 练手攻目标 + 面试库飞轮 → Offer
- **第一期** = 把「记题 → 抽库模拟 → 迭代答法」这条飞轮在 Web 里跑通；备稿和标签是支撑，爬虫/社区/支付都后置

---

## 1. MVP 目标

### 1.1 一句话

在 **12 周内** 交付一条可在浏览器完整演示的竖切：

> **建档拔高导出 → 标记练手/目标 → 模拟面试 → 录入真题 → 个人库抽题再模拟 → 保存参考答法**

### 1.2 MVP 成功标准（演示验收）

| # | 验收项 | 量化标准 |
|---|---|---|
| A | 建档导出 | 上传底稿 → 核对 Profile → 拔高 → 下载 PDF **或** Word，全程 **< 15 分钟** |
| B | 针对性备稿 | 粘贴 JD → Fit 建议 → 出岗位变体终稿，**< 20 分钟** |
| C | 练手标记 | 至少 2 个练手岗 + 1 个目标岗，系统建议先攻练手 |
| D | 面试记录 | 一场练手真面后录入 **≥ 3 道** 真题（含公司、岗位、轮次） |
| E | 库驱动模拟 | 第二次模拟 **优先抽到库内题**，而非每次从零泛生成 |
| F | 参考答法迭代 | 同一题完成两轮练习，可看到并保存「当前最佳答案」 |
| G | 全链路演示 | W12 冻结演示脚本可跑通：备稿 → 模拟 → 记题 → 再模拟(抽库) → 参考答法 |

### 1.3 滩头用户（MVP 只服务这一种）

> 2–10 年经验知识工作者（研发 / 数据 / 产品 / 设计 / 运营），社招 + 可选外企/远程。有一份偏平的旧简历，要改亮、导出 Word/PDF 自行投递。接受拔高表达，拒绝假公司/假学历。

---

## 2. 整体框架

### 2.1 产品模块图

```
┌─────────────────────────────────────────────────────────────────┐
│                        JobCome Web App                          │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│   档案中心   │   岗位中心   │  进攻计划   │  面试中心   │  设置   │
│  Profile    │  Jobs/Fit   │  Campaign   │ Interview   │ Settings│
├─────────────┴─────────────┴─────────────┴─────────────┴─────────┤
│                     智能体编排层（产品视角）                        │
│  Ingest │ Writer │ Reviewer │ Analyst │ Coach │ Archivist │ Strategist │
├─────────────────────────────────────────────────────────────────┤
│                     导出引擎 + 存储 + 模型网关                      │
└─────────────────────────────────────────────────────────────────┘
```

五个用户可见模块：

| 模块 | 职责 | MVP 深度 |
|---|---|---|
| **档案中心** | 上传底稿、核对 Profile、拔高档位、导出通用简历 | 完整 |
| **岗位中心** | 粘贴 JD、结构化、Fit 评分、练手/目标标记 | 完整（无爬虫聚合） |
| **进攻计划** | 练手期 / 目标期状态、达标建议、岗位优先级 | 规则版（写死阈值） |
| **面试中心** | 模拟、记真题、个人库、参考答法、结果追踪 | **核心差异化，完整** |
| **设置** | **账户**（登录/注册/改密/注销）、**个人信息**（昵称/联系偏好）、语言、拔高默认档、数据导出与删除 | 完整（M1 前置） |

### 2.2 核心飞轮（MVP 必须打通）

```
        ┌──────────────┐
        │  档案 + 导出  │
        └──────┬───────┘
               ▼
        ┌──────────────┐     用户自行投递（产品不代投）
        │ 练手岗 + 模拟 │
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ 真面后记真题  │──► InterviewBank（个人库）
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ 库抽题再模拟  │──► AnswerAttempt（最佳答法）
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ 达标攻目标岗  │──► OfferTrack
        └──────────────┘
```

### 2.3 信息架构（站点地图）

```
/                          首页 / 仪表盘（进攻状态摘要）
/profile                   档案列表（通常只有 1 份活跃档案）
/profile/new               上传建档
/profile/:id               档案详情 / 核对
/profile/:id/elevate       拔高预览与档位
/profile/:id/export        导出 PDF / Word

/jobs                      岗位列表
/jobs/new                  粘贴 JD 新建
/jobs/:id                  岗位详情（Fit、标签、关联简历变体）
/jobs/:id/package          针对性申请包（简历变体 + ATS 检查）

/campaign                  进攻计划（练手期 / 目标期、达标进度）

/interviews                面试记录列表
/interviews/new            录入真面（公司/岗位/轮次/题）
/interviews/:id            单次面试详情与复盘

/bank                      个人面试库（按公司/岗位/题型筛选）
/bank/:questionId          单题详情 + 答题历史 + 最佳答法

/mock                      开始模拟（选模式、关联岗位）
/mock/:sessionId           模拟进行中 / 复盘

/auth/login                登录
/auth/register             注册
/auth/forgot-password      忘记密码（发重置邮件）
/auth/reset-password       重置密码（邮件链接落地）

/settings                  设置首页（偏好、隐私入口）
/settings/account          账户：邮箱、改密、注销
/settings/profile-meta     个人信息：昵称、头像、通知偏好（≠ 求职档案）
/settings/privacy          数据导出、一键删除业务数据、隐私政策

/legal/privacy             隐私政策
/legal/terms               用户协议
```

MVP **不做**：社区题库浏览、招聘爬虫聚合页、支付页、顾问后台。

---

## 3. MVP 范围

### 3.1 必须做（In Scope）

| 域 | 功能 | 对应周次 |
|---|---|---|
| **账户** | 注册、登录、登出、忘记密码、重置密码 | **W0** |
| **账户** | 改密、邮箱验证、账户注销（含业务数据级联删除） | W0–W1 |
| **账户** | 个人信息维护（昵称、头像、通知偏好） | W1 |
| 档案 | PDF/DOCX 解析 → Profile 草稿 → 人工核对 → 确认 | W1 |
| 档案 | 拔高三档（保守/标准/拔高），默认拔高 | W2 |
| 档案 | 中文一页模板导出 PDF + Word | W2 |
| 档案 | 英文两页模板导出 PDF + Word | W2–W3 |
| 岗位 | 粘贴 JD 文本 → 结构化要求 | W3 |
| 岗位 | 五维 Fit + 禁区否决 + 投/不投建议 | W3 |
| 岗位 | 练手 / 目标 / 观望 标签 | W4 |
| 进攻 | Campaign 状态机（练手期→目标期）+ 达标规则 | W4, W11 |
| 面试 | 练手模式 / 目标模式 模拟（文字） | W5, W10 |
| 面试 | 录入 InterviewRecord（公司/岗位/轮次/≥3题） | W6 |
| 面试 | 个人 InterviewBank 列表与筛选 | W7 |
| 面试 | MockSession 优先从库抽题 | W7–W8 |
| 面试 | 用户答 + 点评 + 参考答法 + 保存最佳版 | W8 |
| 面试 | 同一题 AnswerAttempt 版本对比 | W8 |
| 岗位 | Application 快照（用户标记已投递，系统不执行） | W9 |
| 追踪 | OfferTrack：进面/挂/Offer，区分练手/目标 | W11 |

### 3.2 明确不做（Out of Scope）

| 功能 | 原因 | 何时考虑 |
|---|---|---|
| 代投递、自动填表、一键海投 | 产品原则 | 不做或 Q3 评估「人在场填表」 |
| 招聘网站爬虫 / Scout 聚合 | MVP 复杂度；粘贴 JD 够用 | M2 |
| 社区题库 CommunityBank | 需脱敏与治理 | M3 |
| 语音模拟面试 | 文字先跑通 | M2+ |
| 支付 / 订阅 | 商业模式未定 | 付费单独开一轮 |
| 求职 CRM 看板（Teal 式） | 非核心飞轮 | M2 |
| 浏览器插件 / NaviForge 集成 | 独立 Web | 不做 |
| PDF↔Word 互转编辑 | 技术陷阱 | 不做 |
| 通用八股题库导入 | 违背「真面沉淀」 | 不做 |

### 3.3 可 Stub（界面有、逻辑最简）

| 功能 | MVP 行为 |
|---|---|
| Scout 招聘信息 | 仅「粘贴 JD」入口，无自动抓取 |
| Strategist 建议 | 规则引擎：练手岗数、库题数、真面场次 → 文案建议 |
| ATS 深度检测 | 文本层检查：联系方式是否真文字、阅读顺序警告 |
| 求职信 | 可选生成，非演示主线 |

---

## 4. 核心功能设计

### 4.1 档案中心

#### 4.1.1 建档流程

```
上传 PDF/DOCX
    → Ingest 解析为 ProfileDraft
    → 用户核对页（高亮「待确认」字段）
    → 用户确认 → Profile v1（真相源冻结）
    → 可选：进入拔高预览、切换档位（访客可用）
```

**交互要点：**

- 解析不确定的字段标黄「待确认」，不得静默写入终稿。
- 确认前不可导出为「终稿」；访客可拔高预览，导出须登录。
- 支持重新上传覆盖（生成新版本，保留历史版本 ID）。

#### 4.1.2 拔高与导出

| 档位 | 默认 | 行为 |
|---|---|---|
| 保守 | | 理顺、纠错、量化已有事实 |
| 标准 | | 成果导向、动词升级 |
| 拔高 | ✓ | 可圆上的夸张；保留 `sourceText → writtenText` 映射 |

导出物：

- 中文：一页 PDF + 同名 docx
- 英文：两页 PDF + 同名 docx
- 导出记录绑定：`profileVersionId` + `elevationLevel` + `templateId`

#### 4.1.3 Reviewer 闸门（导出前）

自动检查项：

- [ ] 无假公司 / 假学历 / 假任职时间
- [ ] 无档案中不存在的项目
- [ ] 拔高句可关联回 Profile 证据或标为「需在面试圆场」

未通过：阻断导出或强制用户确认风险后继续。

---

### 4.2 岗位中心

#### 4.2.1 JD 输入

MVP 仅支持：

- 粘贴纯文本 JD
- 可选填：公司名、职位名、来源链接（手动）

Ingest/Analyst 输出 `Job`：

- 原文 `rawText`
- 结构化 `requirements`（技能、年限、学历、关键词）
- `redFlags`（明显不匹配项）

#### 4.2.2 Fit 五维

| 维度 | 权重（默认） | 说明 |
|---|---|---|
| 技能匹配 | 30% | 硬技能与 JD 关键词 |
| 经历匹配 | 25% | 行业/职能/项目相似度 |
| 职级匹配 | 20% | 年限与职级措辞 |
| 语言匹配 | 15% | 中英要求 |
| 文化/软信号 | 10% | 从 JD 推断，仅建议 |

输出：

- `fitScore` 0–100
- `recommendation`: `apply` | `caution` | `skip`
- `gaps[]`: 缺口列表
- `blockers[]`: 禁区命中则硬否决

#### 4.2.3 岗位标签

| 标签 | UI | 系统行为 |
|---|---|---|
| 练手 | 默认推荐非 dream 公司 | 优先出现在进攻计划练手列表 |
| 目标 | 用户标记 dream job | 未达标前：可备稿/模拟，Strategist 提示「建议先练手」 |
| 观望 | 存档 | 不进 Campaign |

#### 4.2.4 针对性申请包（Package）

有 JD 时：

```
Profile + Job + elevationLevel
    → Writer 出 ResumeVariant
    → Reviewer 批评
    → ATS 文本层检查
    → 导出 PDF/Word
```

---

### 4.3 进攻计划（Campaign）

#### 4.3.1 状态机

```
[练手期 WARMUP]
    │  达标条件满足（见下）
    ▼
[目标进攻期 TARGET]
    │  Offer / 用户手动结束
    ▼
[已完成 COMPLETED]
```

用户可手动从练手期切到目标期（弹窗确认风险）。

#### 4.3.2 达标规则（MVP 写死，可配置后置）

满足 **其一** 即建议开启目标进攻：

| 条件 | 阈值 |
|---|---|
| 练手真面 + 复盘 | ≥ 3 场，且每场 ≥ 3 题入库 |
| 针对性模拟 | ≥ 5 轮 MockSession 完成 |
| 用户主观 | 手动切换（需确认） |

仪表盘展示进度条：真面场次 / 模拟轮次 / 库内题数。

---

### 4.4 面试中心（核心）

#### 4.4.1 模拟面试（MockSession）

**前置选择：**

- 模式：`warmup`（练手）| `target`（目标）
- 关联：`Job`（可选）、`ResumeVariant`（默认最近导出）
- 轮次：一面 / 二面 / 技术面 / HR（影响题型权重）

**出题逻辑（Coach）：**

```
1. 用户库：同 company + roleTitle 的历史题
2. 用户库：同 roleCategory（如 backend-p6）的历史题
3. AI 补充题：绑定当前 JD + 导出稿，不脱离上下文
4. （M3）社区库 — MVP 不实现
```

每轮默认 **5–8 题**（MVP 可配置为 5 题固定）。

**练手模式 vs 目标模式：**

| | 练手模式 | 目标模式 |
|---|---|---|
| 语气 | 纠错、允许停顿提示 | 高压、追问深挖 |
| 题型权重 | 项目深挖 + 行为面为主 | + 业务 case、动机、反问 |
| 复盘重点 | 拔高句是否圆得上 | 离 Offer 差什么 |

#### 4.4.2 真面记录（InterviewRecord）

真面结束后用户进入 `/interviews/new`：

**必填：**

- 公司名
- 岗位名（可关联已有 Job）
- 轮次
- 类型：练手 / 目标
- 面试日期
- ≥ 3 道 `InterviewQuestion`

**选填：**

- 结果：进下一轮 / 挂 / Offer / 待定
- 挂点标签（多选）：项目说不清 / 八股卡壳 / 薪资 / 文化 / 其他
- 自由备注

提交后 Archivist：

- 去重相似题干
- 打标签：题型、公司、岗位类型
- 链到 `applicationId`（若有）

#### 4.4.3 个人面试库（InterviewBank）

列表视图：

- 筛选：公司、岗位、题型、来源（真面/模拟）、时间
- 排序：最近添加、练习次数、掌握度（自评）

单题详情 `/bank/:questionId`：

- 题干、来源、关联面试记录
- 全部 `AnswerAttempt` 时间线
- **当前最佳答案**（用户或系统标记）
- 操作：再练一次 → 进入 MockSession 单题模式

#### 4.4.4 参考答法迭代（AnswerAttempt）

每道题在一次模拟或单题练习中：

```
用户输入答案（文字）
    → Coach 点评（结构、证据、拔高句风险）
    → Coach 生成参考答法（必须挂 Profile 证据点）
    → 用户可：采纳为最佳 / 编辑后保存 / 丢弃
```

**版本对比：**

- 展示 Attempt #1 vs Attempt #n
- 高亮：新增证据、仍卡壳的点

---

### 4.5 账户与身份（M1 前置，W0 必须可用）

简历含敏感个人信息，**没有账户体系不能开工**。需与「求职档案 Profile」严格区分：

| 概念 | 是什么 | 典型字段 | 页面 |
|---|---|---|---|
| **账户 UserAccount** | 登录身份、鉴权、注销 | 邮箱、密码哈希、验证状态 | `/auth/*`、`/settings/account` |
| **个人信息 UserProfileMeta** | 产品内展示与通知偏好 | 昵称、头像、界面语言、通知开关 | `/settings/profile-meta` |
| **求职档案 Profile** | 简历真相源（可导出） | 经历、教育、技能、STAR | `/profile/*`、简历 Agent 页 |

**MVP 账户能力清单：**

| 能力 | 行为 | 验收 |
|---|---|---|
| **注册** | 邮箱 + 密码；发验证邮件（可宽限：未验证 7 天内可试用，导出前必须验证） | 重复邮箱拒绝；密码强度提示 |
| **登录** | 邮箱 + 密码 → **HttpOnly Cookie `jc_session`**（服务端 Session 存 Redis） | 错误密码统一文案；不用 localStorage JWT |
| **登出** | 清除 Session | 受保护路由不可访问 |
| **忘记密码** | 输入邮箱 → 发重置链接（1h 有效，一次性） | 无邮箱也显示「已发送」（防枚举） |
| **重置密码** | 链接落地设新密码 → 可选「踢掉其他设备」 | 旧链接失效 |
| **改密** | 已登录：旧密码 + 新密码 | 成功后可选重新登录 |
| **改邮箱** | 新邮箱验证通过后才切换 | 旧邮箱通知 |
| **注销账号** | 二次确认（输入「删除我的账号」）→ 逻辑删除账户 + **级联删除** Profile、导出物、面试库 | 24h 内不可恢复；Session 立即失效 |
| **个人信息维护** | 改昵称、头像、界面语言、默认拔高档位 | 与 Profile 经历字段分离 |

**MVP 登录方式（冻结建议）：** **邮箱 + 密码**（含忘记密码流程）。Magic link / 手机号 OTP 放 M2。

### 4.5.1 访客模式与登录后合并（核心体验）

**产品策略：** 降低上手门槛——**未登录也能上传、解析、手改简历**；在「要价值」的时刻（导出、Agent）再要求登录；**登录后访客草稿不丢**。

#### 能力矩阵（冻结）

| 能力 | 访客（未登录） | 已登录 |
|------|----------------|--------|
| 浏览首页、看功能说明 | ✅ | ✅ |
| 上传简历、解析、**手改编辑器** | ✅ | ✅ |
| **拔高预览 / 改档位** | ✅（一键预览，非对话） | ✅ |
| **导出 PDF / Word** | ❌ → 引导登录 | ✅ |
| **简历 Agent 多轮对话** | ❌ → 引导登录 | ✅ |
| **面试辅导 Agent**（模拟/记题/题库） | ❌ | ✅ |
| 个人信息 / 设置 / 数据导出 | ❌ | ✅ |

访客可体验 **建档 → 手改 → 拔高预览 → 切档位**，在「带走结果」和「多轮改稿」时再登录；**登录后草稿不丢**。

**拔高 vs Agent 对话（冻结）：**

| 能力 | 形态 | 访客 |
|------|------|------|
| **拔高预览 / 改档位** | 选档位 → 单次 Writer 任务 → 页面展示 `ResumeDraft` 预览 | ✅ |
| **简历 Agent 对话** | 多轮聊天、逐段改写、`profile_patch` | ❌ |

拔高预览走 **结构化单次任务**（非 Chat Session），与右侧 Agent 对话区分开；访客按 `guest_session` 限流（如每日 N 次拔高）。

**冻结决策（2026-09-02 更新）：** 访客 **可以** 拔高预览与改档位；导出与 Agent 多轮对话仍须登录。

#### 前端：Header 与登录态

| 项 | 要求 |
|---|---|
| **登录态来源** | 启动时 `GET /auth/context`；登录/注册/登出后刷新 |
| **Header 展示** | 访客：「登录」「注册」+ 若有草稿显示「继续编辑简历」；已登录：昵称/邮箱 + 下拉（设置、登出） |
| **全局状态** | `actor: guest \| user` + `capabilities`（后端下发，前端不硬编码权限） |
| **门禁 UI** | **导出**、**Agent 对话区**：未登录 disabled +「登录后继续」；拔高预览/档位切换访客可用 |
| **Cookie** | 访客 **`jc_guest`**、已登录 **`jc_session`** 均为 **HttpOnly**；详见 [前端架构与鉴权.md](前端架构与鉴权.md) |

#### 登录后简历不丢（合并规则）

访客每次上传/编辑，档案落在服务端 **`GuestSession`** 下（不靠纯浏览器 localStorage，防清缓存丢稿）。

**注册 / 登录请求**自动携带访客 Cookie（或 body `guestSessionId`），后端执行 **`claim_guest_assets`**：

| 账户侧现状 | 访客侧现状 | 行为 |
|------------|------------|------|
| 无 Profile | 有访客 Profile | **直接认领**：`guest_session_id → user_id`，登录后同一 `profileId` 继续编辑 |
| 有 Profile | 有访客 Profile | **冲突**：弹窗二选一——「用本次草稿覆盖账户档案」/「保留账户档案，丢弃访客草稿」 |
| 有 Profile | 无访客数据 | 正常登录，不变 |
| 无 Profile | 无访客数据 | 正常登录，走新建档案 |

MVP **不做**字段级三路合并；冲突只给「覆盖 / 丢弃访客」两选项，避免实现爆炸。

**合并成功后：** 刷新 `/auth/context`；编辑器保持当前 `profileId`（若被认领则 id 不变）；Guest Cookie 失效。

#### 访客数据生命周期

| 项 | 规则 |
|---|---|
| 有效期 | 未认领访客 Session **30 天**过期（定时任务清理 Profile + S3） |
| 限流 | 访客上传按 IP + `guest_session` 限流；**拔高预览** 每访客每日上限（如 10 次，可配置） |
| 隐私文案 | 未登录页说明：「草稿存于本设备会话，登录可永久保存」 |

#### 未登录可访问路由

`/`, `/resume-agent`（编辑器可用，Agent/导出门禁）, `/auth/*`, `/legal/*`  
面试相关路由 `/interview-coach`, `/bank`, `/mock` 等 **默认需登录**（M1 简化）。

### 4.6 设置与隐私

| 项 | MVP |
|---|---|
| 界面语言 | 中文 UI 为主；档案与导出支持中英内容（在 UserProfileMeta 或 Profile.locale） |
| 默认拔高档位 | 拔高（可改，存 UserProfileMeta） |
| 模型 | **MVP 建议：托管单一模型**；设置页预留 BYOK 字段 |
| **数据导出** | 打包下载：Profile JSON + 面试库 + 导出记录清单（个保法响应） |
| **删除业务数据** | 保留账户，仅删 Profile / 面试 / 导出物（与「注销账号」不同） |
| **注销账号** | 见 §4.5；含全部业务数据 |
| 训练 | 默认不用于模型训练（文案声明） |

---

## 5. 核心对象 Schema（v1 冻结候选）

以下为 JSON 逻辑模型；物理存储（关系表 vs 文档）由技术方案决定。

### 5.0 UserAccount 与 UserProfileMeta

```json
{
  "id": "usr_xxx",
  "email": "user@example.com",
  "emailVerified": true,
  "passwordChangedAt": "2026-09-01T10:00:00Z",
  "status": "active",
  "createdAt": "2026-08-01T08:00:00Z",
  "deletedAt": null
}
```

```json
{
  "userId": "usr_xxx",
  "displayName": "张三",
  "avatarUrl": null,
  "locale": "zh-CN",
  "defaultElevationLevel": "elevated",
  "notifyEmail": {
    "productUpdates": false,
    "securityAlerts": true
  },
  "updatedAt": "2026-09-02T12:00:00Z"
}
```

**关系：** 一个 `UserAccount` 对应一份 `UserProfileMeta`；MVP **单活跃 Profile**（`Profile.userId` 外键）。注销时 `UserAccount.status=deleted`，关联数据逻辑删除。

### 5.0.1 GuestSession（访客草稿）

```json
{
  "id": "gst_xxx",
  "createdAt": "2026-09-02T08:00:00Z",
  "expiresAt": "2026-10-02T08:00:00Z",
  "claimedByUserId": null,
  "claimedAt": null,
  "lastSeenAt": "2026-09-02T12:00:00Z"
}
```

`Profile` 归属字段（与 §5.1 合并理解）：

```json
{
  "ownerKind": "guest",
  "guestSessionId": "gst_xxx",
  "userId": null
}
```

认领后：`ownerKind=user`，`userId=usr_xxx`，`guestSessionId=null`。

### 5.1 Profile

```json
{
  "id": "prof_xxx",
  "version": 3,
  "status": "confirmed",
  "locale": "zh-CN",
  "contact": {
    "name": "张三",
    "email": "a@b.com",
    "phone": "+86...",
    "location": "上海",
    "links": [{ "type": "github", "url": "..." }]
  },
  "summary": "待确认或已确认的一句话简介",
  "experiences": [{
    "id": "exp_1",
    "company": "某某科技",
    "title": "高级后端工程师",
    "startDate": "2021-03",
    "endDate": "2024-06",
    "location": "上海",
    "highlights": ["负责订单服务核心链路..."],
    "skills": ["Go", "Kafka"],
    "confidence": "confirmed"
  }],
  "education": [{
    "id": "edu_1",
    "school": "某某大学",
    "degree": "本科",
    "major": "计算机",
    "startDate": "2015-09",
    "endDate": "2019-06",
    "confidence": "confirmed"
  }],
  "skills": [{
    "name": "Go",
    "level": "advanced",
    "evidence": ["exp_1"]
  }],
  "projects": [{
    "id": "proj_1",
    "name": "订单中台",
    "role": "核心开发",
    "description": "...",
    "confidence": "confirmed"
  }],
  "starStories": [{
    "id": "star_1",
    "situation": "...",
    "task": "...",
    "action": "...",
    "result": "...",
    "tags": ["performance", "leadership"]
  }],
  "constraints": {
    "forbiddenCompanies": [],
    "forbiddenKeywords": [],
    "mustInclude": []
  },
  "preferences": {
    "targetRoles": ["后端开发", "Backend Engineer"],
    "targetIndustries": ["互联网", "SaaS"],
    "salaryRange": null,
    "remoteOk": true
  },
  "meta": {
    "sourceFile": "resume.pdf",
    "createdAt": "2026-09-02T10:00:00Z",
    "confirmedAt": "2026-09-02T10:30:00Z"
  }
}
```

`confidence`: `confirmed` | `needs_review` | `inferred`

### 5.2 ResumeDraft / ResumeVariant

```json
{
  "id": "rd_xxx",
  "profileId": "prof_xxx",
  "profileVersion": 3,
  "jobId": null,
  "elevationLevel": "elevated",
  "locale": "zh-CN",
  "templateId": "zh-one-page-v1",
  "sections": {},
  "elevationMap": [{
    "fieldPath": "experiences[0].highlights[0]",
    "sourceText": "参与订单服务开发",
    "writtenText": "主导订单核心链路设计与性能优化，P99 降至 200ms 量级",
    "needsDefense": true
  }],
  "reviewerStatus": "passed",
  "exportedAt": null
}
```

`jobId` 非空时为针对性 `ResumeVariant`（Package 的一部分）。

### 5.3 Job

```json
{
  "id": "job_xxx",
  "company": "某互联网公司",
  "title": "高级后端工程师",
  "sourceUrl": "https://...",
  "rawText": "完整 JD 原文...",
  "requirements": {
    "skills": ["Go", "K8s"],
    "yearsMin": 5,
    "education": "本科",
    "keywords": ["微服务", "高并发"]
  },
  "roleCategory": "backend-senior",
  "tag": "warmup",
  "fit": {
    "score": 72,
    "recommendation": "caution",
    "gaps": ["缺少 K8s 生产经验表述"],
    "blockers": []
  },
  "status": "active",
  "createdAt": "2026-09-02T11:00:00Z"
}
```

`tag`: `warmup` | `target` | `watch`

### 5.4 Campaign

```json
{
  "id": "camp_xxx",
  "profileId": "prof_xxx",
  "phase": "warmup",
  "warmupJobIds": ["job_a", "job_b"],
  "targetJobIds": ["job_c"],
  "progress": {
    "realInterviews": 2,
    "realInterviewsRequired": 3,
    "mockSessions": 4,
    "mockSessionsRequired": 5,
    "bankQuestionCount": 12
  },
  "targetUnlockedAt": null,
  "updatedAt": "2026-09-02T12:00:00Z"
}
```

### 5.5 InterviewRecord

```json
{
  "id": "int_xxx",
  "profileId": "prof_xxx",
  "company": "练手公司 A",
  "roleTitle": "后端开发工程师",
  "jobId": "job_a",
  "round": "first",
  "type": "warmup",
  "interviewDate": "2026-09-10",
  "result": "rejected",
  "failureTags": ["project_depth"],
  "notes": "二面挂在项目量化",
  "questionIds": ["iq_1", "iq_2", "iq_3"],
  "resumeVariantId": "rd_xxx",
  "createdAt": "2026-09-10T20:00:00Z"
}
```

`round`: `first` | `second` | `technical` | `hr` | `final`  
`result`: `next_round` | `rejected` | `offer` | `pending`

### 5.6 InterviewQuestion

```json
{
  "id": "iq_xxx",
  "profileId": "prof_xxx",
  "stem": "介绍一个你主导的性能优化项目",
  "questionType": "project_deep",
  "source": "real",
  "company": "练手公司 A",
  "roleTitle": "后端开发工程师",
  "roleCategory": "backend-mid",
  "round": "first",
  "interviewRecordId": "int_xxx",
  "jobId": "job_a",
  "tags": ["performance", "go"],
  "bestAttemptId": "aa_2",
  "attemptCount": 2,
  "createdAt": "2026-09-10T20:05:00Z"
}
```

`questionType`: `project_deep` | `technical` | `behavioral` | `system_design` | `case` | `reverse` | `other`  
`source`: `real` | `mock` | `community`（MVP 仅前两种）

### 5.7 AnswerAttempt

```json
{
  "id": "aa_xxx",
  "questionId": "iq_xxx",
  "profileId": "prof_xxx",
  "mockSessionId": "mock_xxx",
  "userAnswer": "用户原始回答...",
  "coachFeedback": {
    "score": 65,
    "strengths": ["结构清晰"],
    "weaknesses": ["量化不足", "拔高句未圆"],
    "defenseFlags": ["elevationMap[0]"]
  },
  "referenceAnswer": "参考答法，含 STAR 与证据挂点...",
  "isBest": true,
  "createdAt": "2026-09-11T10:00:00Z"
}
```

### 5.8 MockSession

```json
{
  "id": "mock_xxx",
  "profileId": "prof_xxx",
  "mode": "warmup",
  "jobId": "job_a",
  "resumeVariantId": "rd_xxx",
  "round": "first",
  "questionIds": ["iq_1", "iq_4", "iq_new_1"],
  "bankDrawCount": 2,
  "generatedCount": 1,
  "status": "completed",
  "startedAt": "2026-09-11T09:00:00Z",
  "completedAt": "2026-09-11T09:25:00Z"
}
```

### 5.9 Application & OfferTrack

```json
{
  "id": "app_xxx",
  "jobId": "job_a",
  "profileId": "prof_xxx",
  "resumeVariantId": "rd_xxx",
  "appliedAt": "2026-09-05",
  "userMarked": true,
  "note": "BOSS 上已投递"
}
```

```json
{
  "id": "ot_xxx",
  "jobId": "job_c",
  "profileId": "prof_xxx",
  "type": "target",
  "stage": "interviewing",
  "outcome": null,
  "updatedAt": "2026-09-15T10:00:00Z"
}
```

`stage`: `preparing` | `applied` | `interviewing` | `offer` | `signed` | `rejected`

---

## 6. 智能体编排（产品级）

MVP 不要求用户感知「多个 Agent」，但后台职责必须分离：

| Agent | 触发场景 | 输入 | 输出 |
|---|---|---|---|
| **Ingest** | 上传简历 / 粘贴 JD | 文件或文本 | ProfileDraft / Job.requirements |
| **Analyst** | JD 保存后 | Profile + Job | Fit 分与建议 |
| **Writer** | 拔高 / 出 Package | Profile + 档位 + 可选 Job | ResumeDraft |
| **Reviewer** | Writer 之后 | Profile + ResumeDraft | pass / fail + 修改建议 |
| **Coach** | MockSession | Profile + ResumeVariant + Bank + Job | 出题、点评、参考答法 |
| **Archivist** | 保存 InterviewRecord | 表单 + 可选录音转写 | InterviewQuestion[] 入库 |
| **Strategist** | 仪表盘 / Campaign | Campaign 进度 + Jobs | 练手/目标建议文案 |

**硬约束（与产品设计一致）：**

- Reviewer 与 Writer **独立上下文**，Reviewer 不得只看 Writer 的自评。
- Coach 参考答法必须引用 Profile 证据或标 `needsDefense`。
- 无用户确认，Profile 不得标为 `confirmed`。

---

## 7. 关键用户故事与验收

### Epic 0：账户与身份（W0）

| ID | 故事 | 验收标准 |
|---|---|---|
| US-0.1 | 作为新用户，我用邮箱注册并登录 | 注册成功；重复邮箱报错；可进入仪表盘 |
| US-0.2 | 作为用户，我忘记密码后能重置 | 邮件链接 1h 内有效；重置后可登录 |
| US-0.3 | 作为用户，我修改昵称和界面语言 | `UserProfileMeta` 更新；刷新后生效 |
| US-0.4 | 作为用户，我注销账号 | 确认后无法登录；Profile 与面试库不可见 |
| US-0.5 | 作为用户，我导出全部个人数据 | 下载 zip 含 Profile + 面试库 JSON |
| US-0.6 | 作为访客，我上传并手改简历 | 无需登录；`GuestSession` 下可保存 |
| US-0.7 | 作为访客，我点导出或 Agent 对话 | 引导登录/注册；登录前草稿仍在 |
| US-0.8 | 作为访客，我登录后草稿不丢 | 无账户 Profile 时认领同一 `profileId`；有冲突时二选一 |
| US-0.9 | 作为访客，我切换拔高档位并看预览 | 无需登录；预览不落盘为终稿导出物 |

### Epic 1：档案与导出

| ID | 故事 | 验收标准 |
|---|---|---|
| US-1.1 | 作为求职者，我上传 PDF 简历，系统解析成可编辑档案 | 3 份样本简历解析后，≥80% 核心字段正确；不确定项标「待确认」 |
| US-1.2 | 作为求职者，我核对并确认档案 | 确认后生成 `profileVersion`；未确认不能导出终稿 |
| US-1.3 | 作为求职者，我选择拔高档位并导出 Word | 默认拔高；下载 docx；`elevationMap` 有记录 |
| US-1.4 | 作为求职者，我导出英文两页 PDF | 模板排版正常；ATS 文本层联系方式可选取 |

### Epic 2：岗位与 Fit

| ID | 故事 | 验收标准 |
|---|---|---|
| US-2.1 | 作为求职者，我粘贴 JD 得到 Fit 报告 | 五维分 + 文字建议；明显不匹配 JD 给 `skip` |
| US-2.2 | 作为求职者，我标记练手与目标岗 | 标签持久化；Campaign 列表正确分组 |
| US-2.3 | 作为求职者，我为某 JD 生成针对性简历 | Package 导出与通用版有差异；Reviewer 跑过 |

### Epic 3：进攻计划

| ID | 故事 | 验收标准 |
|---|---|---|
| US-3.1 | 作为求职者，我看到练手期进度与达标提示 | 仪表盘显示三场真面 / 五轮模拟进度 |
| US-3.2 | 作为求职者，达标后系统建议攻目标 | 状态切到 `target`；目标岗模拟默认高压模式 |

### Epic 4：面试库飞轮（核心）

| ID | 故事 | 验收标准 |
|---|---|---|
| US-4.1 | 作为求职者，真面后我录入公司与 ≥3 道题 | 生成 InterviewRecord + Question；出现在 /bank |
| US-4.2 | 作为求职者，第二次模拟抽到库内题 | `MockSession.bankDrawCount` ≥ 1；日志可追溯抽题来源 |
| US-4.3 | 作为求职者，我练习一题并保存参考答法 | AnswerAttempt 写入；可标为 best |
| US-4.4 | 作为求职者，我对比同一题两次作答 | 题详页展示 ≥2 次 Attempt 差异 |
| US-4.5 | 作为求职者，练手模式模拟帮我圆拔高句 | 点评中出现 `defenseFlags` 时给具体改法 |

### Epic 5：隐私

| ID | 故事 | 验收标准 |
|---|---|---|
| US-5.1 | 作为用户，我删除全部业务数据但保留账户 | Profile、面试库清空；账户仍可登录 |
| US-5.2 | 作为用户，我注销账号 | 等同 US-0.4；24h 内不可恢复 |

---

## 8. 页面线框级说明

### 8.1 仪表盘 `/`

**区块：**

1. Campaign 阶段徽章（练手期 / 目标期）
2. 进度卡：真面场次、模拟轮次、库内题数
3. Strategist 一句建议（规则生成）
4. 快捷入口：上传简历、粘贴 JD、开始模拟、记面试
5. 最近动态：最近导出、最近模拟、最近入库

### 8.2 档案核对 `/profile/:id`

- 左：分段表单（联系、经历、教育、技能、项目）
- 右：原文件预览（PDF）或解析摘要
- 顶栏：待确认项计数、「确认档案」主按钮

### 8.3 模拟 `/mock/:sessionId`

- 顶：模式、关联岗位、进度 2/5
- 中：题干 + 多行输入
- 底：提交答案 → 展示点评 + 参考答法 → 下一题
- 结束页：本轮摘要 + 「将模拟题入库」勾选（默认开）

### 8.4 简历 Agent 页 `/resume-agent`（访客 + 登录共用）

- **左**：`ProfileEditor`（访客可编辑）
- **中/上**：档位切换 + **拔高预览**（访客可用，只读预览区）
- **右**：`ResumeAgentChat` — 访客显示登录蒙层；已登录可多轮对话
- **顶栏导出**：访客 disabled +「登录后下载」；已登录可用
- **Header**：见 §4.5.1

### 8.5 登录合并冲突弹窗

- 展示：账户现有档案摘要 vs 访客草稿摘要（公司数、最近修改时间）
- 按钮：「用本次草稿」/「保留账户档案」

### 8.6 账户设置 `/settings/account`

- 区块：邮箱（脱敏展示）、改密、注销账号（危险区）
- 注销：输入确认文案 → 说明将删除档案与面试库 → 确认

### 8.7 个人信息 `/settings/profile-meta`

- 昵称、头像上传、界面语言、默认拔高档位
- 说明：「求职经历请在档案中心或简历 Agent 页维护」

### 8.8 记面试 `/interviews/new`

- Step1：公司、岗位、轮次、日期、练手/目标
- Step2：逐题添加（题干、题型）；至少 3 题才可提交
- Step3：结果与挂点标签
- 提交后：跳转题详或提示「立即练刚记的题」

---

## 9. 非功能需求（MVP）

| 类别 | 要求 |
|---|---|
| 性能 | 建档解析 < 60s；单题点评 < 30s（依赖模型） |
| 安全 | HTTPS；简历静态文件加密存储；鉴权后访问 |
| 隐私 | 注册/登录；数据导出与删除；隐私政策页 |
| 兼容 | 最新 Chrome / Safari / Edge；移动端可阅读，编辑以桌面为主 |
| 可用性 | 核心路径 3 次点击内可达：模拟、记题、题库 |
| 可观测 | 关键事件埋点：confirm_profile, export, mock_complete, record_interview, bank_draw |

---

## 10. 回归测试集（开工前收齐）

| 类型 | 数量 | 用途 |
|---|---|---|
| 匿名真实简历 | 3 | 技术社招、产品社招、中英双语各一 |
| 真实 JD 文本 | 6 | 2 匹配、2 边缘、2 明显不匹配 |
| 模拟面试剧本 | 1 | W12 演示用固定台词 |

存放建议：`job-come/fixtures/`（git 忽略 PII，仅团队内共享）。

---

## 11. MVP 开放决策（本方案建议默认值）

上位文档 [`产品设计.md`](产品设计.md) §9 未决项，本 PRD **建议如下冻结**，技术方案可据此开工：

| 决策 | MVP 建议 | 理由 |
|---|---|---|
| 模型谁付钱 | **平台托管单一模型**；设置页隐藏预留 BYOK | 降低熟人试用摩擦；成本可控 |
| 界面与内容语言 | **中文 UI**；档案与模板 **中英双轨** | 滩头用户常同时看外企岗 |
| 登录方式 | **邮箱 + 密码**；忘记密码走邮件重置 | 个保法 + 传统账户心智；OTP/magic link 放 M2 |
| 访客拔高 | **可预览、可改档位**；单次 Writer 任务，非 Agent 对话 | 导出与多轮对话仍须登录 |
| 多 Profile | **单活跃 Profile** | MVP 简化 |
| 演示账号 | 预置脱敏样本 + 一键加载 | W12 演示稳定 |

---

## 12. 12 周交付对照

| 周 | 交付物 | 本 PRD 章节 |
|---|---|---|
| **W0** | 注册/登录/忘记密码/注销 + **访客 Session + 认领合并** + 鉴权分级 | §4.5–4.5.1, §5.0–5.0.1, US-0.1–0.8 |
| W1 | Profile schema + 解析 + 核对页 + 个人信息设置 | §5.0–5.1, §4.1, US-0.3, US-1.1–1.2 |
| W2 | 拔高 + 中英导出 | §4.1.2, US-1.3–1.4 |
| W3 | JD + Fit + Package | §4.2, US-2.1–2.3 |
| W4 | 标签 + Campaign | §4.3, US-3.1 |
| W5 | 首次模拟 | §4.4.1 |
| W6 | 记面试 | §4.4.2, US-4.1 |
| W7 | 个人库 + 抽题 | §4.4.3, US-4.2 |
| W8 | 参考答法 + 对比 | §4.4.4, US-4.3–4.5 |
| W9 | Application 关联 | §5.9 |
| W10 | 目标模式模拟 | §4.4.1 目标模式 |
| W11 | 达标 + OfferTrack | §4.3, §5.9 |
| W12 | 全链路演示冻结 | §1.2 |

---

## 13. 下一步

- **全貌与节奏**：[`路线图.md`](路线图.md)
- **技术实现**：[`技术方案.md`](技术方案.md)
- **M0**：确认路线图 → 回归样本 → Hermes spike → W1 建档

---

## 附录 A. 与产品设计文档的映射

| 产品设计 § | 本 PRD |
|---|---|
| §5.1 核心对象 | §5 Schema |
| §5.6 练手→目标 | §4.3 Campaign |
| §5.8 面试库 | §4.4 面试中心 |
| §5.9 用户旅程 | §2.2 飞轮 + §7 用户故事 |
| §6.3 M1 MVP | §1、§3 |
| §7.1 12 周 | §12 |
| §10 立即下一步 | §10 回归集 + §13 技术方案 |

## 附录 B. 名词表

| 名词 | 含义 |
|---|---|
| Profile | 用户经历真相源，非简历文件 |
| 拔高 | 允许夸张表达，硬事实不造假 |
| 练手岗 | 非 dream company，用来攒经验与真题 |
| 面试库 | 个人真题集合，模拟优先抽库 |
| 参考答法 | AI 生成、可挂证据的示范回答，非照搬 |
