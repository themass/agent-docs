# crewAI 架构文档中心

> **项目**: [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)（本仓库 `crewAI/`）  
> **对照来源**: [AGENT_PROJECTS_FULL_ARCHITECTURE_COMPARISON](../AGENT_PROJECTS_FULL_ARCHITECTURE_COMPARISON.md) §crewAI

crewAI = **声明式 Crew / Task DAG** + **静态 Agent 绑定** + **Task context 传递** + **RecallMemoryTool 智能召回**。

---

## 核心源码入口

| 模块 | 路径 |
|------|------|
| Crew / kickoff | `crewAI/lib/crewai/` |
| 记忆召回 | `crewAI/lib/crewai/memory/recall_flow.py` |
| 记忆工具 | `crewAI/lib/crewai/tools/memory_tools.py` |

---

## 30 秒心智模型

```text
定义 Agent + Task（DAG + context）→ 组装 Crew → Crew.kickoff 同步执行
Task 为核心单元；无运行时 spawn；流程在 kickoff 前固定
记忆：Task context 管短期；RecallMemoryTool / RememberTool 管长期
```

---

## 交互式图解（Archify）

| 图 | 说明 |
|----|------|
| [crewai-kickoff.html](./diagrams/crewai-kickoff.workflow.html) | Kickoff 工作流：定义 → 组装 → kickoff → 按序执行 |
| [crewai-task-dag.html](./diagrams/crewai-task-dag.architecture.html) | Task DAG 架构：Task 链 + Agent 绑定 |
| [crewai-role-agent.html](./diagrams/crewai-role-agent.sequence.html) | Role-Agent 时序：Task 分配 → LLM → tool → context 传递 |
| [crewai-memory-recall.html](./diagrams/crewai-memory-recall.dataflow.html) | 记忆召回数据流：RecallMemoryTool → recall_flow → 存储 |

规格源文件：`diagrams/*.json`

---

## 阅读路径

| 你是谁 | 路径 |
|--------|------|
| **选型对照** | [AGENT_PROJECTS §7–§11](../AGENT_PROJECTS_FULL_ARCHITECTURE_COMPARISON.md) |
| **记忆深潜** | [AGENT_PROJECTS §15.2 crewAI](../AGENT_PROJECTS_FULL_ARCHITECTURE_COMPARISON.md#crewai) |
| **改 kickoff** | `crewAI/lib/crewai/crew.py` |

---

## 与同类框架对照

| 维度 | crewAI | deer-flow / deepagents | openai-agents |
|------|--------|------------------------|---------------|
| 计划 | Task DAG 声明式 | 动态 task 工具委派 | 无内置 plan |
| 多 Agent | 静态 Crew | spawn 子 Agent | Handoff |
| 记忆 | context + Recall | checkpointer | Session |
| 执行 | 同步 kickoff | invoke / 线程 | Runner.run |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-10
