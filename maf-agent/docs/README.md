# Microsoft Agent Framework — 架构文档

> **官方**: [learn.microsoft.com/agent-framework](https://learn.microsoft.com/en-us/agent-framework/)  
> **合并**: 2026-08-05 · 原 17 个专题文件 → **3 卷**  
> **源码**: `agent-framework/python/packages/`

---

## 三卷结构

| 卷 | 文件 | 内容 |
|----|------|------|
| **导读** | [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) | **九幕图解**（Workflow / Hosting 映射，推荐先读） |
| **Part 1** | [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | 核心架构、`agent.run`、Tool Loop、Handoff、Workflow 概念、内置 Prompt 手册、Python 指南、术语表 |
| **Part 2** | [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | Memory、Compaction 源码、SessionContext、Harness、Skills、MCP/Tools、运行时 Prompt 五类、FIDES 安全 |
| **Part 3** | [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | Workflow 引擎、声明式 YAML、Orchestrator、Hosting、Providers 包、Evaluation、.NET FAQ |

---

## 10 分钟速览

1. 心智模型 `agent.run` / `workflow.run` / Hosting → [Part 1 §0](./ARCHITECTURE_PART1.md#0-阅读导航)
2. SessionContext 与 Provider 管道（含每条消息/队列） → [Part 2 §4](./ARCHITECTURE_PART2.md#4-sessioncontext-与-providers-深度解读) · [§3.1](./ARCHITECTURE_PART2.md#31-每条用户消息--队列取下一条何时走整条管道)
3. Compaction 源码 → [Part 2 Memory 卷末](./ARCHITECTURE_PART2.md#compaction-源码解读)
4. Magentic / GroupChat / Orchestrator 原理 → [Part 3 §11](./ARCHITECTURE_PART3.md)（[§2.1 心智模型](./ARCHITECTURE_PART3.md#21-心智模型builder--workflow--executor) · [§5–§8 各实现](./ARCHITECTURE_PART3.md#5-basegroupchatorchestrator抽象底座)）

---

## 概念交叉索引

| 你想搞懂… | 读 |
|-----------|-----|
| Memory / History / Recall | Part 2 §3 |
| SessionContext 拼装 / 每条消息走管道 | Part 2 §4（§2.5 示例、§3.1 队列） |
| Skills `before_run` 改 tools | Part 2 §4.4 |
| Tool Loop 消息存在哪 | Part 2 §11 |
| Harness 默认 Provider | Part 2 §5 |
| Workflow superstep | Part 3 §10 |
| Orchestrator / Builder / Executor | Part 3 §11（§2.1–§2.6 清单；§5–§8 原理） |
| HTTP 托管 AgentState | Part 3 §12 |
| ADR | [decisions/](./decisions/) |

---

## 阅读路径

| 时间 | 路径 |
|------|------|
| 30 分钟 | Part 1 §0–§6 |
| Memory 专题 | Part 2 §3 全文 |
| Skills / MCP | Part 2 §6–§7 |
| 多 Agent | Part 3 §10–§11 |
| Prompt 调试 | Part 2 §8 完整示例 |

---

## 本地运行

```bash
cd agent-framework/python && uv sync
uv run python examples/mytest/debug_quick.py
```
