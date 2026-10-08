# NaviForge：Agent 内核与外部框架集成决策（单页）

> **用途**：把你问过「是否值得集成 / 能否替换内核」的 agent **放在同一张表里**，避免和「修 scraper」「North Star」脱节。  
> **读者**：你（拍板）、维护 runtime 的人。  
> **关联**：[OPEN_SOURCE.md](./OPEN_SOURCE.md)、[AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md)、[BROWSER_AGENT_NORTH_STAR.md](./BROWSER_AGENT_NORTH_STAR.md)

---

## 1. 先分清三层（否则「换内核」永远在吵架）

```text
┌─────────────────────────────────────────────────────────────┐
│ L3 产品壳  MV3 扩展 UI · 侧栏 · 工具箱 · chrome.storage      │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│ L2 Agent 内核  packages/runtime — runAgentLoop · hooks ·     │
│                prompt · intent · spawn · Verify(应有)         │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│ L1 浏览器平面  dom-plane + network-plane（extension 实现）   │
│                page-agent / debugger / Host 可选 CDP         │
└─────────────────────────────────────────────────────────────┘
```

| 你说「替换内核」 | 通常指 | 不能动 |
|------------------|--------|--------|
| 换 **L2** | `packages/runtime` 的 loop / 工具编排 | L3 商店合规、单 tab 写者 |
| 换 **L1** | Playwright/Puppeteer 新浏览器 | **产品定义**（用户真实 Chrome 标签） |
| 接 **外部 agent** | 多数是 **Host 侧第二个 loop** 或 **借 L2 设计** | 整包塞进 MV3 content script |

**browser-harness-js** 主要是 **L1 增强（全量 CDP）**，不是完整 L2。  
**browser-use (Python)** 是 **L2+L1 一体**（Playwright 浏览器 + Agent 循环），**不能**整体替换 MV3 扩展，只能 **Host 并列** 或 **借设计改 L2**。

---

## 2. 你让分析过的 agent — 一张表说清

| 框架 / 项目 | 本质 | 替换 L2？ | 替换/增强 L1？ | 值得集成？ | 集成方式（推荐） |
|-------------|------|-----------|----------------|------------|------------------|
| **[browser-harness-js](https://github.com/browser-use/browser-harness-js)** | Bun + 652 CDP 方法，无 helper | ❌ 不是 loop | ✅ Host 上全 CDP | **有条件** | Host MCP provider；扩展仍 page-agent；**不**进主包 |
| **browser-use (Python)** | Agent + Playwright/Cloud Browser | ❌ 不进 MV3 | ❌ 违背「用户 Chrome」 | **借设计** | DOM index、step 字段、Watchdog → **Perceive/Plan**；Cloud 不对齐 BYOK 商店 |
| **@page-agent/page-controller** | DOM 执行 | — | ✅ 已是 L1 | ✅ 已集成 | 继续 Adapter，别 fork |
| **Pi / Prime / SoL-Pi** | 418 行 loop + 插件 + compaction | **可借鉴** | — | **高（L2 设计）** | steer/followUp、JSONL 账本、**插件不堆 hook 文本** → 重构 runtime |
| **Hermes / Harness-SDK** | event_loop_cycle + tools MCP | **可借鉴** | — | 中 | 工具管线、session 投影；Host 已有 MCP |
| **smolagents / DeepAgents** | 多 Agent + planning_interval | 低 | — | 低 | 研究/离页任务；**不是** in-tab 浏览器专长 |
| **OpenAI Agents SDK / MAF** | 编排 + handoff | 中 | — | 中 | spawn 子 Agent 语义对照，不 import |
| **Playwright MCP / CDP 通用** | 外部浏览器 | ❌ | ❌ 产品 | Host 可选 | 极客通道，默认 off |

### 2.1 对你最关心的两个结论

**browser-harness-js**

- **不值得**替换 NaviForge L2。  
- **值得**作为 **Host 可选 CDP 引擎**（与 `npm run host` 并列），服务「page-agent 搞不定的控件 / file input / 全协议调试」。  
- **interaction-skills** 值得 **迁入 Skill 正文**（ recipes），不是迁入 MV3。

**browser-use 整仓**

- **不值得**替换扩展内核（Playwright ≠ 用户标签页）。  
- **值得**抽 **三件事进 L2/L1 设计**（见 §4），否则学不到它的「像专业 browser agent」的部分。

---

## 3. 为什么你会感觉「分析乱了」

| 你问的问题 | 我后来给的回答 | 缺什么 |
|------------|----------------|--------|
| harness 是否集成 | Host 可选、不替换 page-agent | ✅ 方向对，但没写进总决策 |
| session 爬站失败 | intent / dom_read / 小改计划 | ❌ 没问「该换 kernel 还是修 Perceive」 |
| 要智能 Agent | PageState 四层 North Star | ❌ 没写 harness/Pi/browser-use **谁负责哪一层** |

**正确做法**（以后分析按这个顺序）：

1. 任务属于 **L1 观测** / **L2 规划** / **L2 执行** 哪类失败？  
2. 表 §2 里谁 **专精这一层**？  
3. **集成** = 接进 Host 或抄设计；**替换** = 只讨论 L2 重写边界。  
4. 再谈 PR，而不是反过来。

---

## 4. browser-use / harness 应「进」NaviForge 的具体部件

不是 import 仓库，而是 **对齐专业 browser agent 的部件**：

| 来自 | 进 NaviForge 哪里 | 对应 North Star 层 |
|------|-------------------|----------------------|
| browser-use **DOM 索引 / 可交互元素集** | L1 PageState.items + index revision | **L1 Perceive** |
| browser-use **step：evaluation + next_goal**（步内 ReAct，非会话 Goal） | L2 每步 Verify 小门 | **L4 Verify** |
| browser-use **Watchdog**（卡住检测） | L2 action-loop 超时 / replan | **L2 Plan** |
| harness **typed CDP + interaction-skills** | Host provider + Skill recipes | **L1 Host** |
| Pi **runLoop + compaction + steer** | 替换 hook 轰炸 | **L2 内核** |
| page-agent **已有** | L1 执行 | 保持 |

**当前 runtime 的问题**：L2 用 **regex intent + 700 行 hooks** 模仿 browser-use/Pi 的能力，但 **没有** browser-use 级 **DOM 状态对象**，也 **没有** Pi 级 **清晰 loop 边界** —— 所以既不如通用 Agent 会写代码，又不如 browser-use 会看页。

---

## 5. 推荐总路线（集成 + 是否换内核 — 一条线）

### 5.1 默认（商店 / 普通用户）

- **L2**：重写为 **Pi 式瘦 loop** + **Plan/Perceive/Verify**（保留 planes 接口），**不**换 Python browser-use。  
- **L1**：page-agent + **PageState 管线**（North Star A 阶段）。  
- **Host**：可选 **browser-harness-js** provider（CDP 深桥），默认不装。

### 5.2 Power user / 开发者

- Host 同时暴露：`naviforge_execute_browser_task`（扩展 loop）+ **`cdp_eval` / harness**（全 CDP）。  
- 两 loop **互斥写同一 tab**（锁），避免双自动化。

### 5.3 明确不换

- MV3 内嵌 Playwright / 整包 browser-use Python。  
- 用 harness **替换** page-agent 作为默认 L1（维护两套点击栈）。

### 5.4 「换内核」的准确定义（若你拍板大改）

| 选项 | 含义 | 工作量 | 风险 |
|------|------|--------|------|
| **A. 演化** | 现有 `agent.ts` + 删 hooks + 加 PageState/Plan | 中 | 低 |
| **B. 移植 Pi loop** | TS 重实现 runLoop 契约，planes 不变 | 高 | 中 |
| **C. Host 双内核** | 扩展只做 UI+planes；重任务走 Host browser-use | 很高 | 产品分裂 |
| **D. harness 当 L1 默认** | 仅当用户开 remote debugging | 中 | 安全/审核 |

**建议**：**A 为主 + Host harness 为 D**；**不选 C** 除非放弃「扩展 standalone」叙事。

### 5.5 执行主线（只走这一条）

选定 **A（演化 L2）**，Host harness **排在主线之后**，不并行改内核。

```text
0  冻结边界
   不换：Python browser-use 整包、MV3 内 Playwright、harness 替换 page-agent
   要换：L2 编排（PageState + Plan + Verify），L1 仍 page-agent

1  看见页面（L1）
   每轮 Act 前产出 PageState（URL、角色、列表预览、摩擦、可选 XHR）
   navigate 之后必须 wait 再刷新 PageState
   退出：脚本类任务不再只看到登录页链接就继续「分析」

2  一条计划（L2）
   一次 Run 只有一个交付类型：脚本 / 数据 / 媒体 / 摘要 / 研究
   删掉同一 Run 上 media + catalog 两套 preflight
   退出：你的原句（生成各分类第一页 Python）走「脚本」，不走 media_extract

3  交得出去（L4）
   脚本任务必须 script_save 或结构化 shortfall
   没证据禁止空 system_done
   退出：G1 类任务产出可打开的 .py，或明确缺 Network / 登录 / 公开入口

4  瘦循环（仍是 A，不是整仓换 Pi）
   用 Plan 里程碑替换 GUIDANCE 轰炸；卡住则 replan，不重复同一观察
   退出：同 URL 同读法最多 1 次，随后换策略或结束

5  Host CDP（D，主线 1–3 稳定后再做）
   可选 browser-harness-js；与扩展 loop 互斥写同一 tab
   退出：极客开远程调试能用 CDP；商店默认仍 page-agent、network 默认关
```

**现在只做第 1 步。** 第 1 步没过，不做第 5 步，也不移植 Pi 内核。

### 5.6 工程纪律（2026-10-01）

- **禁止 host 分支** — runtime/extension 不得对具体站点域名特判；SiteRecipe 的 `hosts` 仅为**数据** lookup。
- **新行为先写 Deliverable Plan** — 先 `deliverablePlanMilestone` / Verify 叙事，再 hook；详见 [`RUNTIME_ENGINEERING_RULES.md`](./RUNTIME_ENGINEERING_RULES.md)。

---

## 6. 与「连通用 Agent 都不如」的关系

通用 Agent 强在 **L2 直接交付**（无 tool 方差）。  
browser-use 强在 **L1 页面状态 + L2 步内验证**。  
NaviForge 当前 **L1 薄 + L2 hook 厚 + 无 Verify** → 最差组合。

**专业 browser agent = browser-use 的 Perceive/Verify + Pi 的 loop 纪律 + 你们独有的 session/network/Playbook moat**，  
**不是** 再多几个 dom_* tool，也 **不是** 把 harness 贴进侧栏。

---

## 7. 文档分工（避免再乱）

| 文档 | 回答什么 |
|------|----------|
| **本文** | 集成谁、换不换 L2、Host 放什么 |
| **RUNTIME_ENGINEERING_RULES** | 禁止 host 分支；新行为先 deliverable Plan |
| BROWSER_AGENT_NORTH_STAR | L1–L4 产品契约与 Horizon |
| SCRAPER_AGENT_RELIABILITY | 一条失败 trace 的战术验收 |
| OPEN_SOURCE | 法律/依赖边界 |
| monorepo browser-use / Pi 导读 | 抄设计时的源码锚点 |

---

## 8. 状态

| 日期 | 说明 |
|------|------|
| 2026-09-30 | 单页决策：合并 harness 分析与内核替换问题 |
