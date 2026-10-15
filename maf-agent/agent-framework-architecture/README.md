# Microsoft Agent Framework 架构文档中心

> **项目**: [microsoft/agent-framework](https://github.com/microsoft/agent-framework)（本仓库 `agent-framework/`）  
> **官方**: [learn.microsoft.com/agent-framework](https://learn.microsoft.com/en-us/agent-framework/)

Agent Framework = **Python / .NET 双实现** + **ChatAgent** 与 **Workflow graph** 双产品线 + **Foundry hosting** 长运行托管。

---

## 上游文档（源码仓）

| 文档 | 说明 |
|------|------|
| [**DESIGN_THINKING_SERIES**](../../agent-framework/docs/DESIGN_THINKING_SERIES.md) | 九幕图解导读（推荐先读） |
| [ARCHITECTURE.md](../../agent-framework/docs/ARCHITECTURE.md) | 架构导航入口 |
| [ARCHITECTURE_PART1](../../agent-framework/docs/ARCHITECTURE_PART1.md) | 核心架构、`agent.run`、Tool Loop |
| [ARCHITECTURE_PART2](../../agent-framework/docs/ARCHITECTURE_PART2.md) | Memory、Compaction、MCP/Tools |
| [ARCHITECTURE_PART3](../../agent-framework/docs/ARCHITECTURE_PART3.md) | Workflow 引擎、Orchestrator、Hosting |
| [decisions/](../../agent-framework/docs/decisions/) | ADR（含 steerable 长运行） |

---

## 30 秒心智模型

```text
Chat Agent：thread history + run 内 model → function tools 循环
Workflow：图遍历 + WorkflowRunState checkpoint（非 Pi 式 inner loop）
Foundry：远端 session + resilient loop + IDLE_WITH_PENDING_REQUESTS
```

---

## 交互式图解（Archify）

| 图 | 说明 |
|----|------|
| [agent-framework-workflow-graph.html](./diagrams/agent-framework-workflow-graph.architecture.html) | 双产品线架构：ChatAgent vs Workflow + checkpoint |
| [agent-framework-agent-run.html](./diagrams/agent-framework-agent-run.sequence.html) | ChatAgent 运行时序：run → model → tools → RunItem |
| [agent-framework-checkpoint.html](./diagrams/agent-framework-checkpoint.lifecycle.html) | Checkpoint 生命周期：初始化 → 执行 → 持久化 → 完成 |
| [agent-framework-orchestration.html](./diagrams/agent-framework-orchestration.workflow.html) | 编排工作流：图遍历与节点内 tool 循环 |

规格源文件：`diagrams/*.json`

---

## 阅读路径

| 你是谁 | 路径 |
|--------|------|
| **第一次读** | DESIGN_THINKING_SERIES → ARCHITECTURE Part 1 |
| **Workflow 深潜** | Part 3 · `python/samples/` workflows |
| **steerable 长运行** | ADR-0035 · `steerable_long_running_agent` 样本 |
| **与 Pi 对照** | [pi/docs/DESIGN_THINKING_SERIES](../../pi/docs/DESIGN_THINKING_SERIES.md) |

---

## 与同类框架对照

| 维度 | Agent Framework | openai-agents | LangGraph |
|------|-----------------|---------------|-----------|
| 编排 | Workflow graph | Runner.run | StateGraph |
| 状态 | checkpoint / thread | Session items | checkpoint |
| 托管 | Foundry | 应用自决 | 多种 |
| 内环 | Chat tool 循环 | run_loop | 节点内循环 |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-10
