# DeepTutor — 架构导航

> **完整大纲**: [README.md](./README.md)  
> **推荐先读（图表讲设计）**: [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) · [CONTEXT_AND_PROJECTION.md](./CONTEXT_AND_PROJECTION.md)

---

## 分章索引

| 主题 | 文档 | 章节 |
|------|------|------|
| **图解导读** | [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) | 九步：七层、Orchestrator、Tool/Capability、三层投影、Memory |
| **上下文投影** | [CONTEXT_AND_PROJECTION.md](./CONTEXT_AND_PROJECTION.md) | StreamEvent / messages / turn_events / LLM input |
| 核心运行时（深潜） | [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | §1.2 分层、Orchestrator、双层插件、AgentLoop、Memory |
| 扩展与垂直能力 | [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | RAG、Skills、MCP、Capabilities |
| 产品与取舍 | [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | i18n、Mastery |

## 专题深潜

| 主题 | 文档 |
|------|------|
| 实体 ER + 模块时序（字段/函数级） | [ENTITY_AND_SEQUENCES.md](./ENTITY_AND_SEQUENCES.md) |
| CLI / WS / regenerate 实例 | [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md) |

## 10 分钟速览

1. **一条运行路径** — `start_turn` → Orchestrator → Capability → AgentLoop → StreamEvent → [DESIGN_THINKING_SERIES](./DESIGN_THINKING_SERIES.md)
2. **七层架构** — 表现 → 传输 → 编排 → 能力 → Agent → 工具 → 数据 → [导读 §1](./DESIGN_THINKING_SERIES.md#第-1-步七层架构--谁该知道什么)
3. **双层插件** — L1 Tool 单步；L2 Capability 整轮 → [导读 §3](./DESIGN_THINKING_SERIES.md#第-3-步双层插件--tool-vs-capability)
4. **三层投影** — UI 流 ≠ messages ≠ LLM input → [CONTEXT_AND_PROJECTION](./CONTEXT_AND_PROJECTION.md)
5. **Memory L1–L3** — trace → consolidator → 注入 system → [导读 §6](./DESIGN_THINKING_SERIES.md#第-6-步memory-l1l3--学习画像怎么长出来)
6. **两条 Agent 引擎** — AgentLoop vs run_agentic_loop → [导读 §4](./DESIGN_THINKING_SERIES.md#第-4-步两条-agent-引擎)

返回：[文档中心](./README.md)
