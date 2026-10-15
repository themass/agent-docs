# GitHub 浏览器 Agent 项目精选

**文档目的**：整理「浏览器 × Agent」开源项目：按形态分类、给选型路径，并标注本仓库本地已有克隆。

**数据时点**：2026-08-05（Stars 经 GitHub API 刷新；超时未取到的标 `~`）

**筛选标准**：

- 明确服务 AI Agent / LLM 操控或读取浏览器 / Web
- 有可用 SDK / CLI / MCP / 扩展，而非纯论文 Demo
- Stars、维护活跃度或 2026 日榜有一定信号

---

## 一、赛道地图（先看这个）

```
你要什么？
│
├─ 自然语言「去网上办一件事」
│   └─ browser-use / Skyvern / Magnitude / Notte / HyperAgent
│
├─ 工程师写可维护的自动化（半 AI 半代码）
│   └─ Stagehand / Notte
│
├─ 给 Cursor / Claude Code「装上浏览器」
│   └─ Playwright MCP / Chrome DevTools MCP / agent-browser / wigolo
│
├─ 页面内嵌 GUI Agent（不另起浏览器进程）
│   └─ page-agent（阿里）→ 扩展侧可参考 Pagenter
│
├─ 读网页/社交内容（偏信息获取，非点击操控）
│   └─ Agent-Reach / Firecrawl / Crawl4AI / wigolo / pdf-inspector
│
├─ Agent 专用浏览器 / 沙箱（登录态、并行）
│   └─ ego-lite / Steel / BrowserOS / Nanobrowser / Lightpanda
│
└─ 企业 RPA 替代（表单、验证码、2FA）
    └─ Skyvern
```

---

## 二、分类总表

### 1. 自治浏览器 Agent 框架（任务进 → 结果出）

| 项目 | Stars | 语言 | 最近推送 | 定位 | 适合 |
|------|-------|------|----------|------|------|
| **[browser-use/browser-use](https://github.com/browser-use/browser-use)** | **108k** | Python | 2026-08-05 | 品类标杆。Playwright + 感知-行动循环 | 快速原型、通用网页任务 |
| **[Skyvern-AI/skyvern](https://github.com/Skyvern-AI/skyvern)** | ~23k | Python | — | 愿景+LLM 工作流，偏 **RPA 替代** | 业务门户、表单/验证码/2FA |
| **[magnitudedev/browser-agent](https://github.com/magnitudedev/browser-agent)** | 4.1k | — | — | **愿景优先**浏览器 Agent | 复杂 UI、要高成功率 |
| **[nottelabs/notte](https://github.com/nottelabs/notte)** | 2.0k | Python | 2026-08-05 | AI + 确定性脚本 / 云浏览器基建 | 生产里「能脚本就不烧 LLM」 |
| **[lavague-ai/LaVague](https://github.com/lavague-ai/LaVague)** | ~6k | Python | — | Large Action Model → 可执行代码 | 构建可交付 Web Agent 产品 |
| **[hyperbrowserai/HyperAgent](https://github.com/hyperbrowserai/HyperAgent)** | 1.5k | — | — | Hyperbrowser 系 AI 浏览器自动化 | 云浏览器 + Agent 一体 |

**对比要点**：

| | browser-use | Stagehand | Skyvern | Magnitude |
|--|-------------|-----------|---------|-----------|
| 姿态 | 全自治 Agent | 代码优先 SDK | 业务工作流 | 愿景优先 Agent |
| 感知 | DOM 为主 | DOM + 缓存 | 愿景为主 | 纯愿景强 |
| 典型用户 | 开发者/研究员 | 工程团队 | 运营/RPA | 要准确率 |
| 成本 | 每步 LLM | 缓存后可极低 | 愿景较贵 | 愿景成本 |

**本仓库**：本地有 `browser-use/`（v0.13.7）。

---

### 2. 工程向 SDK（半 AI、可维护）

| 项目 | Stars | 语言 | 最近推送 | 定位 | 适合 |
|------|-------|------|----------|------|------|
| **[browserbase/stagehand](https://github.com/browserbase/stagehand)** | **24k** | TypeScript | 2026-08-05 | Browser Agents SDK：`act` / `extract` / `observe`，动作可缓存 | 要上生产、可回归 |
| Browserbase Director | — | — | — | 无代码：自然语言 → 浏览器自动化 | 非技术运营配置 |

Stagehand 一句话：**确定性代码里，只在选择器会坏的地方用 AI**。

---

### 3. 给编码 Agent 的浏览器工具（MCP / CLI）

| 项目 | Stars | 语言 | 最近推送 | 定位 | 适合 |
|------|-------|------|----------|------|------|
| **[ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)** | **49k** | TypeScript | 2026-08-05 | Chrome DevTools 能力给编码 Agent | 查 DOM、网络、性能 |
| **[vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)** | **40k** | Rust | 2026-08-04 | Agent 专用浏览器自动化 **CLI** | 脚本/Agent 管道 |
| **[microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)** | **36k** | TypeScript | 2026-08-04 | Playwright 官方 MCP | E2E / 页面操作 |
| **[KnockOutEZ/wigolo](https://github.com/KnockOutEZ/wigolo)** | 4.2k | TypeScript | 2026-08-05 | 本地优先：搜索/抓取/研究 **MCP**，零 API 费 | 调研，不重度点 UI |

**选型**：要「点按钮、填表」→ Playwright MCP / agent-browser；要「读网/搜」→ wigolo / Agent-Reach；要「调试页面」→ chrome-devtools-mcp。

---

### 4. 页面内 GUI Agent（注入当前页）

| 项目 | Stars | 语言 | 定位 | 适合 |
|------|-------|------|------|------|
| **[alibaba/page-agent](https://github.com/alibaba/page-agent)** | ~24–28k | TypeScript | **页内 JS GUI Agent**，自然语言操控 Web UI | 后台系统、嵌入式助手 |

与 browser-use 的区别：page-agent 跑在**当前页面上下文**；browser-use 另起/控制浏览器实例。

**本仓库**：`pagenter-ext-1.8.0-chrome/` 为基于 page-agent 思路的 Chrome 扩展打包产物（含 `__pagenter`、`data-pa-hint` 等）。

---

### 5. 读网 / 抓取 / 给 Agent「眼睛」（偏信息层）

| 项目 | Stars | 语言 | 最近推送 | 定位 | 适合 |
|------|-------|------|----------|------|------|
| **[firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)** | **161k** | TypeScript | 2026-08-05 | 规模化搜索/爬取/交互 API | RAG、研究 Agent 网页摄入 |
| **[unclecode/crawl4ai](https://github.com/unclecode/crawl4ai)** | **76k** | Python | 2026-07-30 | LLM 友好爬虫/刮取 | 自托管抓取管道 |
| **[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach)** | **67k** | Python | 2026-08-05 | 零平台 API 费读 Twitter/Reddit/B站/小红书等 | Agent 内容采集（日榜常客） |
| **[firecrawl/pdf-inspector](https://github.com/firecrawl/pdf-inspector)** | **11k** | Rust | 2026-08-05 | PDF 检测/分类/抽文本（扫描件智能路由） | 文档摄入前置；8/4 日榜 #2 |
| **wigolo** | 4.2k | TS | 2026-08-05 | 见上，本地 MCP | 隐私/零成本调研 |

> Firecrawl / Crawl4AI / pdf-inspector 偏「数据摄入」，严格说不全是「浏览器操控 Agent」，但几乎所有 Web Agent 管线都会用到。

**本仓库**：本地有 `Agent-Reach/`。

---

### 6. Agent 专用浏览器 / 沙箱 / 扩展

| 项目 | Stars | 语言 | 最近推送 | 定位 | 适合 |
|------|-------|------|----------|------|------|
| **[browseros-ai/BrowserOS](https://github.com/browseros-ai/BrowserOS)** | **13k** | TypeScript | 2026-08-05 | 开源 **Agentic 浏览器**（对标 Comet/Dia/Atlas） | 「浏览器本身就是 Agent」 |
| **[nanobrowser/nanobrowser](https://github.com/nanobrowser/nanobrowser)** | **14k** | TypeScript | 2025-11-24 | Chrome 扩展多 Agent 网页自动化 | 轻量、跑在日常 Chrome（维护偏缓） |
| **[citrolabs/ego-lite](https://github.com/citrolabs/ego-lite)** | **8.5k** | JavaScript | 2026-08-05 | 人机并行；共享登录态跑自动化 | Cookie/登录态、人可随时接管 |
| **[steel-dev/steel-browser](https://github.com/steel-dev/steel-browser)** | **7.4k** | TypeScript | 2026-07-28 | 开源 Browser API / Agent 沙箱 | 自托管远程浏览器环境 |
| **[lightpanda-io/browser](https://github.com/lightpanda-io/browser)** | ~33k | Zig | — | 为 AI/自动化设计的 **无头浏览器** | 极致性能 headless 底座 |

---

## 三、2026 日榜相关（本仓库观察）

来自 `github-daily-rank`（热度信号，≠「最好」）：

| 时段 | 项目 | 备注 |
|------|------|------|
| 7 月 | **Agent-Reach** | 上榜 11 天，累计日增约 11k |
| 7 月 | **ego-lite** / **page-agent** / **wigolo** | 人机并行 / 页内 GUI / 本地 Web MCP |
| 8/3 | **Agent-Reach** | 仍进日榜 Top10 |
| 8/4 | **pdf-inspector** | Firecrawl 出品，日榜 #2（🔺1837） |

全年报告中另有 **browser-use** 等早期收录项。

---

## 四、怎么选（决策表）

| 场景 | 首选 | 备选 |
|------|------|------|
| 最快跑通「帮我在网上做 X」 | **browser-use** | Notte、HyperAgent、LaVague |
| 生产环境、要稳定可维护 | **Stagehand** | Notte（AI+脚本） |
| 企业表单/门户/验证码 | **Skyvern** | — |
| 愿景优先、复杂 UI | **Magnitude** | browser-use |
| Cursor/Claude 加浏览器手 | **Playwright MCP** | agent-browser、chrome-devtools-mcp |
| 嵌进自家 Web 产品 | **page-agent** | Pagenter 类扩展 |
| 只要读内容不要点按钮 | **Agent-Reach** / Firecrawl | Crawl4AI、wigolo |
| PDF/文档进 Agent | **pdf-inspector** + Firecrawl | — |
| 要登录态 + 人可接管 | **ego-lite** | Steel 沙箱 |
| 要完整 Agentic 浏览器产品 | **BrowserOS** | Nanobrowser（扩展） |

---

## 五、架构分层（集成时避免重复造轮）

```
┌──────────────────────────────────────────────┐
│  产品层：BrowserOS / Nanobrowser / 自研 UI     │
├──────────────────────────────────────────────┤
│  Agent 循环：browser-use / Skyvern / Magnitude │
├──────────────────────────────────────────────┤
│  工程 SDK：Stagehand / Notte                   │
├──────────────────────────────────────────────┤
│  工具协议：Playwright MCP / DevTools MCP / wigolo │
├──────────────────────────────────────────────┤
│  浏览器引擎：Playwright / Lightpanda / Steel / ego │
├──────────────────────────────────────────────┤
│  摄入层：Firecrawl / Crawl4AI / Agent-Reach / pdf-inspector │
└──────────────────────────────────────────────┘
```

常见组合：

- **研究 Agent**：wigolo 或 Firecrawl / Agent-Reach（读）+ LLM  
- **办任务 Agent**：browser-use 或 Stagehand（控）  
- **编码助手**：Playwright MCP + chrome-devtools-mcp  
- **ToB 回填**：Skyvern  
- **页内助手**：page-agent（或 Pagenter 扩展）

---

## 六、注意事项

1. **成本**：全自治每步调 LLM，长任务很贵；生产优先 Stagehand 缓存 / Notte 混合。  
2. **反爬与登录**：真实站点常要登录态、验证码——Skyvern、ego-lite（共享会话）更现实。  
3. **许可**：部署前查 LICENSE（部分项目非纯 MIT）。  
4. **安全**：能点「删除/付款」——必须人机确认与域名白名单。  
5. **不要混淆**：「读网」≠「控浏览器」；很多项目只解决一层。  
6. **Nanobrowser** 最近推送停在 2025-11，选型时留意活跃度。

---

## 七、个人开发者最小收藏夹

1. **browser-use** — 自治任务标杆（本仓库已有）  
2. **Stagehand** — 要上生产时换/叠这一层  
3. **Playwright MCP** — 给日常编码 Agent 用  
4. **page-agent** — 要做页内助手时看  
5. **Agent-Reach** 或 **Firecrawl** — 内容摄入（本仓库已有 Agent-Reach）  
6. **Skyvern** — 有表单/RPA 需求时再上  
7. **ego-lite** — 需要登录态且人机并行时  

---

## 八、本仓库相关路径

| 路径 | 说明 |
|------|------|
| `browser-use/` | browser-use v0.13.7 源码 |
| `Agent-Reach/` | Agent-Reach 源码 |
| `pagenter-ext-1.8.0-chrome/` | page-agent 系 Chrome 扩展打包（非完整源码） |
| `docs/GITHUB_BROWSER_AGENT_PROJECTS.md` | 本文档 |

---

## 九、参考链接

- browser-use：https://github.com/browser-use/browser-use  
- Stagehand：https://github.com/browserbase/stagehand  
- Skyvern：https://github.com/Skyvern-AI/skyvern  
- Playwright MCP：https://github.com/microsoft/playwright-mcp  
- Chrome DevTools MCP：https://github.com/ChromeDevTools/chrome-devtools-mcp  
- agent-browser：https://github.com/vercel-labs/agent-browser  
- page-agent：https://github.com/alibaba/page-agent  
- Agent-Reach：https://github.com/Panniantong/Agent-Reach  
- Firecrawl：https://github.com/firecrawl/firecrawl  
- Crawl4AI：https://github.com/unclecode/crawl4ai  
- pdf-inspector：https://github.com/firecrawl/pdf-inspector  
- BrowserOS：https://github.com/browseros-ai/BrowserOS  
- ego-lite：https://github.com/citrolabs/ego-lite  
- Steel：https://github.com/steel-dev/steel-browser  
- wigolo：https://github.com/KnockOutEZ/wigolo  

---

*整理更新日期：2026-08-05 · Stars 以 GitHub 实时为准；部分仓库 API 超时沿用近似值*
