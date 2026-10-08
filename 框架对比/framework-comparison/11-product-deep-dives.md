# 单产品设计深潜（导航）

> **设计导读** · 原 1600+ 行源码 walkthrough 已归档：[_archive/11-product-deep-dives.md](./_archive/11-product-deep-dives.md)  
> **原则**：单产品 **设计思想** 读各项目 `DESIGN_THINKING_SERIES`；本页只做 **导航与对比锚点**。

---

## 1. 为什么改版

旧版按产品堆 **路径 + 函数名**，与 [00-HARNESS-DESIGN-PHILOSOPHY](./00-HARNESS-DESIGN-PHILOSOPHY.md) 目标冲突。现改为：

| 要什么 | 读哪里 |
|--------|--------|
| **设计取舍、五平面、故事** | 下表「设计导读」列 |
| **Harness 横向对比** | 本目录 03–09、14、21 |
| **改某仓库代码** | 归档 11 或各仓 README |

---

## 2. Tier 1 设计导读索引

| 产品 | 设计导读 | Harness 对比锚点 |
|------|----------|------------------|
| **Codex** | [docs/codex-architecture/DESIGN_THINKING_SERIES.md](../../../docs/codex-architecture/DESIGN_THINKING_SERIES.md) | Turn、四层安全、[14](./14-loop-interjection.md) |
| **OpenCode** | [docs/opencode-architecture/ARCHITECTURE.md](../../../docs/opencode-architecture/ARCHITECTURE.md) | Context Epoch、Session |
| **Pi** | [pi/docs/DESIGN_THINKING_SERIES.md](../../../pi/docs/DESIGN_THINKING_SERIES.md) | 双环、steering |
| **Prime** | [docs/prime-agent-architecture/DESIGN_THINKING_SERIES.md](../../../docs/prime-agent-architecture/DESIGN_THINKING_SERIES.md) | JSONL 树、Daemon |
| **DeepTutor** | [docs/deeptutor-architecture/DESIGN_THINKING_SERIES.md](../../../docs/deeptutor-architecture/DESIGN_THINKING_SERIES.md) | 投影、capability |
| **OpenManus** | [docs/openmanus-architecture/DESIGN_THINKING_SERIES.md](../../../docs/openmanus-architecture/DESIGN_THINKING_SERIES.md) | Plan-and-Execute |
| **MetaGPT** | [docs/metagpt-architecture/ARCHITECTURE.md](../../../docs/metagpt-architecture/ARCHITECTURE.md) | SOP、消息总线 |
| **deepagents** | monorepo `libs/deepagents` + [01](./01-overview.md) | MA1、middleware 图 |
| **deer-flow** | 产品仓文档 | Gateway、PG、reject |
| **nanobot** | 产品仓 + 归档 §nanobot | inject、Bus |
| **Hermes** | 产品仓 | interrupt/steer、kanban |
| **OpenHarness** | `OpenHarness/docs/` | ohmo、四层 compact |
| **OpenHands** | [10-openhands](./10-openhands.md) | 双平面、Condenser |
| **browser-use** | [23-browser-use-vs-trading-agents](./23-browser-use-vs-trading-agents.md) §2 | computer-use、Watchdog、DOM index |
| **TradingAgents** | [23](./23-browser-use-vs-trading-agents.md) §3 · [18-quant-stock-agents](./18-quant-stock-agents.md) | MA6 固定图、dataflows PIT |
| **Claude Agent SDK** | 归档 11 §Claude | **CLI 黑盒** E 族 |
| **OpenAI Agents SDK** | 官方文档 | MA3 handoff |

跨项目索引：[CROSS_AGENT_DESIGN_INDEX.md](../../../docs/CROSS_AGENT_DESIGN_INDEX.md)

---

## 3. 按设计问题找产品

| 问题 | 建议先读 |
|------|----------|
| 事件溯源 + 审计 | Codex、OpenHands、OpenCode |
| 轻量教学内核 | OpenManus、smolagents |
| IM Gateway + inject | nanobot、[09-channels](./09-channels.md) |
| interrupt vs queue | hermes、ohmo、[14](./14-loop-interjection.md) |
| 公司式多 Role | MetaGPT、crewAI |
| CLI 遥控黑盒 | Claude Agent SDK（归档 11） |

---

## 4. 深潜（实现向）

逐产品源码导读、API 表 → [_archive/11-product-deep-dives.md](./_archive/11-product-deep-dives.md)
