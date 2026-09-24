# 量化与股票 Agent 开源项目整理

> **范围**: 开源 **LLM Agent** 驱动的量化选股、投研、交易决策项目（含本 workspace 已克隆仓库 + 社区主流 Repo）  
> **关联**: [04-multi-agent.md](./04-multi-agent.md) §7 TradingAgents · [01-overview.md](./01-overview.md) §14.1 · [11-product-deep-dives.md](./11-product-deep-dives.md)  
> **最后更新**: 2026-08-10

---

## 目录

1. [先分清四类「金融 Agent」](#1-先分清四类金融-agent)
2. [总览矩阵](#2-总览矩阵)
3. [Tier A — 多 Agent 交易/投研框架](#3-tier-a--多-agent-交易投研框架)
4. [Tier B — Agent 原生交易平台](#4-tier-b--agent-原生交易平台)
5. [Tier C — 投研/合规顾问（非自动下单）](#5-tier-c--投研合规顾问非自动下单)
6. [Tier D — 数据通道与 Persona 层](#6-tier-d--数据通道与-persona-层)
7. [本 workspace 内相关资产](#7-本-workspace-内相关资产)
8. [编排与数据模式对照](#8-编排与数据模式对照)
9. [选型决策树](#9-选型决策树)
10. [风险与合规提示](#10-风险与合规提示)

---

## 1. 先分清四类「金融 Agent」

| 类型 | 做什么 | 典型产物 | 是否自动下单 |
|------|--------|----------|--------------|
| **T1 多角色投研流水线** | 模拟分析师团队 → 辩论 → 风控 → 组合决策 | BUY/HOLD/SELL、评级、研报摘要 | 多数 **模拟/纸交易**；少数接券商 API |
| **T2 Agent 原生交易平台** | 给 Agent 完整行情、回测、执行、IM 渠道 | Shadow account、实验挑战、API | 可接实盘适配器，需自建风控 |
| **T3 研究/合规顾问** | 教育性策略讨论、KYC、财报解读 | 策略说明、合规报告 | ❌ |
| **T4 数据与人设层** | 雪球/行情 Skill、财务 persona Markdown | 工具调用、Prompt 片段 | ❌ |

**「量化」在这里** = 技术指标、因子、回测、条件选股、组合优化等 **可计算规则** 与 Agent 推理结合；不等于传统 Qlib/Backtrader 纯规则引擎。

---

## 2. 总览矩阵

| 项目 | 类型 | 编排 | 市场 | 自动交易 | 回测 | 本 workspace | 许可 |
|------|------|------|------|----------|------|--------------|------|
| **TradingAgents** | T1 | LangGraph 固定 DAG | 美股为主 + 扩展 | 模拟撮合 | 历史日回放 | ✅ `TradingAgents/` | Apache-2.0 |
| **Vibe-Trading** | T2 | 多 Agent + MCP/API | 全球 + **A/印股** 等 | 适配器（Longbridge 等） | ✅ 因子/组合优化 | ❌ | MIT |
| **AI-Trader** | T2 | Agent 原生平台 | 美股等 | 纸交易/实验 | ✅ 挑战/实验 | ❌ | MIT |
| **FinRobot** | T1/T2 | AutoGen 等多 Agent | 全球 | 策略 Agent 层 | 依子模块 | ❌ | Apache-2.0 |
| **PrimoAgent** | T1 | LangGraph 线性 4 Agent | 美股 | 信号输出 | ✅ `backtesting/` | ❌ | 见 Repo |
| **FinanceAgent-LangGraph** | T1 | LangGraph 并行 10 Agent | 股+加密 | Alpaca **纸交易** + HITL gate | ⚠️ | ❌ | 见 Repo |
| **GenericAgent** | T4→T1 | 手写 ReAct | **A 股**（mootdx） | ❌ 监控/选股 | 可自建 | ✅ `GenericAgent/` | 见 Repo |
| **Google ADK financial-advisor** | T3 | ADK 子 Agent 团队 | 美股示例 | ❌ | ❌ | ✅ `google/adk-samples/...` | Apache-2.0 |
| **Google ADK global-kyc** | T3 | ADK 路由 UK/US | 合规数据 | ❌ | ❌ | ✅ `google/adk-samples/...` | Apache-2.0 |
| **agency-agents finance** | T4 | 无 runtime | 通用财务 | ❌ | ❌ | ✅ `agency-agents-zh/` | 见 Repo |
| **Agent-Reach 雪球** | T4 | 宿主 Agent 工具 | **A 股社区** | ❌ | ❌ | ✅ `Agent-Reach/` | 见 Repo |
| **openhuman stock tool** | T4 | Rust harness + tool | 行情 API | 可选 Polymarket | ❌ | ✅ `openhuman/` | 见 Repo |

图例：**自动交易** = 项目内建或文档明确的下单路径（仍须自建风控与合规）。

---

## 3. Tier A — 多 Agent 交易/投研框架

### 3.1 TradingAgents（本 workspace 主力）

| 项 | 说明 |
|----|------|
| **仓库** | [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) · 本地 `TradingAgents/` |
| **论文** | [arXiv:2412.20138](https://arxiv.org/abs/2412.20138) |
| **定位** | 模拟「交易公司」：分析师 → 多空研究员辩论 → Trader → 风控辩论 → Portfolio Manager |

**固定 DAG（MA6 模式）**：

```text
Analysts（market / social / news / fundamentals，可选子集）
  → Bull ↔ Bear 辩论 → Research Manager
  → Trader → Risk（激进/中性/保守）辩论 → Portfolio Manager → END
```

**技术栈**：

- **LangGraph** `StateGraph` + checkpoint 续跑（ticker + date）
- **数据**: yfinance、Alpha Vantage、FRED、Polymarket、Reddit/StockTwits 情绪等（v0.3+ 多 vendor）
- **LLM**: OpenAI / Anthropic / Google / xAI / DeepSeek / Qwen / GLM / MiniMax / Bedrock / Ollama / OpenRouter…
- **记忆**: `TradingMemoryLog` 决策 Markdown 日志 + `Reflector` 事后反思
- **输出**: 结构化评级、报告树 `results/`，CLI `cli/main.py`

**入口**：`TradingAgentsGraph.propagate()` → `graph.stream()`（`tradingagents/graph/trading_graph.py`）

**适用**：学习 LangGraph 多角色金融 DAG；投研 demo。**非**实盘交易系统。

---

### 3.2 FinRobot

| 项 | 说明 |
|----|------|
| **仓库** | [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) |
| **定位** | 金融 **Agent 平台**（四层：Agent / LLM 算法 / DataOps / 多源模型），覆盖研报、市场预测、交易策略 Agent |

**特点**：Financial Chain-of-Thought、多数据源 LLM 编排、桌面端 FinRobot Desktop；与 FinGPT 生态相关。  
**编排**：AutoGen 等 Agent 组合（非单一 TradingAgents 式 DAG）。  
**适用**：金融 Agent **平台化**参考；模块多，需按子 Agent 选型。

---

### 3.3 PrimoAgent

| 项 | 说明 |
|----|------|
| **仓库** | [ivebotunac/PrimoAgent](https://github.com/ivebotunac/PrimoAgent) |
| **定位** | LangGraph **线性** 四 Agent：数据采集 → 技术分析 → 新闻 NLP（7 维量化特征）→ 组合管理 |

**特点**：强调技术指标（SMA/RSI/MACD/BB/ADX/CCI）+ 新闻量化特征 → BUY/SELL/HOLD + 置信度；内置 `backtesting/`。  
**适用**：「技术分析 + 情绪量化」教学向流水线。

---

### 3.4 FinanceAgent-LangGraph（小型全栈示例）

| 项 | 说明 |
|----|------|
| **仓库** | [aakarsh31/FinanceAgent-LangGraph](https://github.com/aakarsh31/FinanceAgent-LangGraph) |
| **定位** | 10 个分析 Agent **并行** + Supervisor；FastAPI + React；**trade_gate** HITL |

**数据**：yfinance、CoinGecko、FRED、`ta` 指标；纸交易 Alpaca。  
**适用**：全栈参考（API + 前端 + LangGraph + 合规门）。

---

## 4. Tier B — Agent 原生交易平台

### 4.1 Vibe-Trading

| 项 | 说明 |
|----|------|
| **仓库** | [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) |
| **定位** | **Personal Trading Agent** — 一条命令给 Agent 完整交易能力 |

**能力摘要**（以 README/CHANGELOG 为准）：

- 回测、**PIT-safe 基本面因子**（Alpha Zoo → 460 因子）、组合优化（含换手约束）
- **多市场**：美股、**A/印股**（NSE/BSE）、多适配器（如 Longbridge）
- **16 路 IM Channel**、定时研究、MCP/API、Shadow Account
- `pip install vibe-trading-ai`

**适用**：要 **产品级** 个人交易 Agent（渠道 + 回测 + 数据 + 可选实盘适配器）。

---

### 4.2 AI-Trader

| 项 | 说明 |
|----|------|
| **仓库** | [HKUDS/AI-Trader](https://github.com/HKUDS/AI-Trader) |
| **定位** | **Agent-Native Trading Platform** —「AI 也需要自己的交易平台」 |

**架构**（README）：

```text
skills/          # Agent skill 定义
docs/api/        # OpenAPI
service/server/  # FastAPI
service/frontend/# React
```

**特点**：实验/挑战排行榜、多 Agent 生态接入（文档提及 nanobot 等）、yfinance 回退、纸交易向。  
**适用**：要做 **交易平台 + 社区实验**，而非单一分析脚本。

---

## 5. Tier C — 投研/合规顾问（非自动下单）

### 5.1 Google ADK Financial Advisor

- **路径**: `google/adk-samples/python/agents/financial-advisor/`
- **角色**: Data Analyst → Trading Analyst（≥5 策略）→ Execution → Risk Evaluation
- **输出**: 教育性策略与执行计划；**明确非投资建议**
- **部署**: 可部署到 Agent Runtime（Google Cloud）

### 5.2 Google ADK Global KYC Agent

- **路径**: `google/adk-samples/python/agents/global-kyc-agent/`
- **角色**: 全球路由 → UK（Companies House）/ US（SEC EDGAR）合规子 Agent
- **场景**: KYC、内幕交易披露查询等 **合规数据**，非交易策略

### 5.3 其它 ADK / 示例

- `google/adk-samples/python/agents/README.md` 索引更多 **Financial Services** vertical skills（部署前看 manifest）。

---

## 6. Tier D — 数据通道与 Persona 层

| 资产 | 作用 | 路径/链接 |
|------|------|-----------|
| **Agent-Reach 雪球** | A 股行情、搜股、热帖 | `Agent-Reach/README.md` |
| **agency-agents finance** | 财务预测、风控、港股合规等 **persona** | `agency-agents-zh/finance/` |
| **openhuman stock tool** | 集成行情等工具 | `openhuman/src/openhuman/tools/` |
| **ClarityFinance** | 外部金融 Agent 框架（Planning-with-Files） | [cooragent/ClarityFinance](https://github.com/cooragent/ClarityFinance) |

这类 **不提供** 完整交易 loop，需挂在 Hermes / nanobot / OpenHarness 等宿主上。

---

## 7. 本 workspace 内相关资产

| 路径 | 角色 |
|------|------|
| `TradingAgents/` | **完整** 多 Agent 投研框架（§3.1） |
| `GenericAgent/` | 通用 ReAct + **A 股 mootdx 选股/监控** demo（`README` 量化选股 GIF） |
| `google/adk-samples/python/agents/financial-advisor/` | ADK 四 Agent 投研教程 |
| `google/adk-samples/python/agents/global-kyc-agent/` | ADK 合规多 Agent |
| `agency-agents-zh/finance/` | 财务/风控 persona 库 |
| `Agent-Reach/` | 雪球等 **中国市场** 数据通道 |
| `openhuman/` | 桌面 Harness + stock / Polymarket 等集成工具 |
| `OpenHarness/docs/framework-comparison/04-multi-agent.md` | TradingAgents MA6 拓扑 |
| `OpenHarness/docs/framework-comparison/01-overview.md` | §14.1 TradingAgents 画像 |

**未克隆但常一起讨论**（见 §2 矩阵）：Vibe-Trading、AI-Trader、FinRobot、PrimoAgent。

---

## 8. 编排与数据模式对照

### 8.1 编排模式

| 模式 | 代表 | 特点 |
|------|------|------|
| **固定 DAG** | TradingAgents, PrimoAgent | 拓扑不变，适合演示与论文复现 |
| **并行 + Supervisor** | FinanceAgent-LangGraph | 宏观/技术/情绪并行再汇总 |
| **平台 + Skills** | AI-Trader, Vibe-Trading | Agent 能力以 skill/API 扩展 |
| **ADK 子 Agent** | financial-advisor, global-kyc | Google ADK 编排，云部署友好 |
| **通用 ReAct + 金融 Skill** | GenericAgent, 宿主 + Agent-Reach | 最灵活，需自建流水线 |

### 8.2 数据源（常见）

| 来源 | 用途 | 出现在 |
|------|------|--------|
| yfinance | OHLCV、基本面 | TradingAgents, PrimoAgent, AI-Trader |
| Alpha Vantage | 行情、新闻、指标 | TradingAgents |
| FRED | 宏观 | TradingAgents, FinanceAgent-LangGraph |
| mootdx / 通达信 | **A 股** 行情 | GenericAgent（文档） |
| 雪球（Agent-Reach） | A 股社区、行情 | Agent-Reach |
| Longbridge 等 | 实盘适配 | Vibe-Trading |
| Alpaca | 美股纸交易 | FinanceAgent-LangGraph |
| Polymarket | 预测市场 | TradingAgents, openhuman |

### 8.3 记忆与复盘

| 项目 | 机制 |
|------|------|
| TradingAgents | `TradingMemoryLog` + `Reflector` + checkpoint |
| FinRobot | 平台级 DataOps / 多 Agent 状态 |
| GenericAgent | L0–L4 文件结晶（非金融专用） |

---

## 9. 选型决策树

```text
要学 LangGraph 多角色金融 DAG、论文级复现？
  └─ TradingAgents（本 workspace 已有）

要个人交易 Agent 产品（回测 + IM + 可选实盘 + A 股）？
  └─ Vibe-Trading

要交易平台 + 实验/排行榜 + FastAPI/React？
  └─ AI-Trader

要金融 Agent 平台/多层架构参考？
  └─ FinRobot

要技术分析 + 新闻 NLP + 内置回测模块？
  └─ PrimoAgent

要 Google Cloud ADK 部署的投研教程（无下单）？
  └─ google/adk-samples financial-advisor

要 A 股选股/监控，最小通用 Agent？
  └─ GenericAgent + mootdx Skill

只要雪球/行情数据，已有 Hermes/nanobot？
  └─ Agent-Reach 雪球通道

要财务/风控「专家人格」无代码框架？
  └─ agency-agents-zh finance/
```

---

## 10. 风险与合规提示

- 上述项目 **普遍声明仅供研究/教育**，不构成投资建议。
- **自动实盘** 需自行处理：券商合规、风控、限速、密钥、回测过拟合、数据前视（TradingAgents v0.3.1 强调 Alpha Vantage look-ahead 修复）。
- **A 股** 注意数据授权、延迟与交易规则；社区数据（雪球、Reddit）噪声大。
- 生产前：纸交易 → 小资金 → 审计日志（TradingAgents `results/`、AI-Trader 实验框架均可参考）。

---

## 相关阅读

| 文档 | 内容 |
|------|------|
| [04-multi-agent.md](./04-multi-agent.md) §7 | TradingAgents 固定图 |
| [06-memory.md](./06-memory.md) | TradingAgents 决策 log |
| [01-overview.md](./01-overview.md) §14.1 | TradingAgents Tier 2 画像 |
| [github-daily-rank 2026 日榜分析](../../github-daily-rank/2026/QUANT_STOCK_AGENTS_RANK_ANALYSIS.md) | **GitHub 2026 日榜** 量化/股票 Agent 热度与时间线 |
| [TradingAgents/README.md](../../TradingAgents/README.md) | 安装、CLI、Docker |
| [browser-use/docs](../browser-use/docs/README.md) | 浏览器自动化（研报抓取、交易网站，非量化核心） |

---

**维护**: 新克隆金融 Agent 仓库进 workspace 时，更新 §2 矩阵与 §7 路径表。
