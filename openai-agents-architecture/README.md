# OpenAI Agents Python SDK 架构文档中心

> **项目**: [openai/openai-agents-python](https://github.com/openai/openai-agents-python)（本仓库 `openai-agents-python/`）  
> **体例参照**: [agent-framework/docs](../../agent-framework/docs/README.md)

OpenAI Agents Python SDK = **Runner 编排** + **run_loop 执行核** + **Agent 声明式定义** + **Handoff 多 Agent 路由** + **Session 持久化**。

---

## 上游文档（源码仓）

| 文档 | 说明 |
|------|------|
| [**DESIGN_THINKING_SERIES**](../../openai-agents-python/docs/DESIGN_THINKING_SERIES.md) | 九幕图解导读（推荐先读） |
| [**OPENAI_AGENTS_SDK_ARCHITECTURE_INDEX**](../../openai-agents-python/docs/OPENAI_AGENTS_SDK_ARCHITECTURE_INDEX.md) | 架构索引与分章导航 |
| [OPENAI_AGENTS_SDK_ARCHITECTURE_PART1](../../openai-agents-python/docs/OPENAI_AGENTS_SDK_ARCHITECTURE_PART1.md) | 核心架构、运行时、Handoff、工具 |
| [OPENAI_AGENTS_SDK_ARCHITECTURE_PART2](../../openai-agents-python/docs/OPENAI_AGENTS_SDK_ARCHITECTURE_PART2.md) | Session、Guardrails、Tracing、Sandbox |
| [ROLLOUT_AND_SESSION_EXAMPLES](../../openai-agents-python/docs/ROLLOUT_AND_SESSION_EXAMPLES.md) | Rollout / Session 示例 |

---

## 30 秒心智模型

```text
Runner.run（外层：多轮直到无 tool / handoff / max_turns）
  └── run_loop 单轮（内层：model → tool → items 回注）
Session items 持久化 → 下次 run 注入 history
Handoff = 图上的边；Agent.as_tool() = 子 Agent 作 function
```

---

## 交互式图解（Archify）

| 图 | 说明 |
|----|------|
| [openai-agents-runner-stack.html](./diagrams/openai-agents-runner-stack.architecture.html) | Runner 栈：应用 → Runner → run_loop → Agent/Model/Tools/Session |
| [openai-agents-agent-loop.html](./diagrams/openai-agents-agent-loop.sequence.html) | 单轮循环时序：model 采样 → tool 执行 → NextStep |
| [openai-agents-handoff.html](./diagrams/openai-agents-handoff.workflow.html) | Handoff 工作流：Agent A → 切换 → Agent B |
| [openai-agents-session-memory.html](./diagrams/openai-agents-session-memory.dataflow.html) | Session 记忆数据流：RunItem 持久化与 history 注入 |
| [openai-agents-e2e.html](./diagrams/openai-agents-e2e.sequence.html) | 端到端会话时序：首轮 + 续聊 |

规格源文件：`diagrams/*.json`

---

## 阅读路径

| 你是谁 | 路径 |
|--------|------|
| **第一次读** | DESIGN_THINKING_SERIES → ARCHITECTURE_INDEX |
| **要改 run_loop** | Part 1 §3 → `src/agents/run_internal/run_loop.py` |
| **Session / 恢复** | Part 2 §7 → `session_persistence.py` |
| **与 Codex 对照** | [FULL_LIFECYCLE_SEQUENCE](../codex-architecture/FULL_LIFECYCLE_SEQUENCE.md) |

---

## 与同类框架对照

| 维度 | openai-agents-python | Codex | crewAI |
|------|---------------------|-------|--------|
| 编排 | Runner.run | Session harness | Crew.kickoff |
| 多 Agent | Handoff | MA delegate | 静态 Crew |
| 持久化 | Session items | Rollout JSONL | Task context |
| 状态 | RunState | 三真相 | 流程型 |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-10
