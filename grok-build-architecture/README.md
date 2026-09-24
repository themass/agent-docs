# Grok Build 架构文档中心

> **项目**: 本仓库 `grok-build/`（Rust workspace）  
> **上游导读**: [grok-build/doc-cn/DESIGN_THINKING_SERIES.md](../../grok-build/doc-cn/DESIGN_THINKING_SERIES.md)

Grok Build = **CLI → core Session → provider / Tool registry / Memory**；**Session FIFO（外层）** + **Turn 内 LLM↔tool（内层）**；**Interjection** 中途改道。

---

## 上游文档（源码仓）

| 文档 | 说明 |
|------|------|
| [**DESIGN_THINKING_SERIES**](../../grok-build/doc-cn/DESIGN_THINKING_SERIES.md) | 九幕图解导读（推荐先读） |
| [ARCHITECTURE.md](../../grok-build/doc-cn/ARCHITECTURE.md) | Part I/II 全架构 |
| [GROK_RUNTIME_PROMPTS.md](../../grok-build/doc-cn/GROK_RUNTIME_PROMPTS.md) | 运行时 Prompt 中文全文 |
| [PACKAGE_MODULES.md](../../grok-build/doc-cn/PACKAGE_MODULES.md) | Crate 模块索引 |

---

## 30 秒心智模型

```text
Session 队列（外层，产品级串行）
  └── Turn（内层：LLM → tool → 结果直到 stop）
Interjection = steer 语义（synthetic user → loop continue）
Memory / Plan / 多 Agent = 三个正交维度
```

---

## 交互式图解（Archify）

| 图 | 说明 |
|----|------|
| [grok-build-stack.html](./diagrams/grok-build-stack.architecture.html) | 运行栈：CLI → Session → Turn → provider / tools / Memory |
| [grok-build-agent-loop.html](./diagrams/grok-build-agent-loop.sequence.html) | Agent 循环时序：submit → run_turn → tool → Interjection |
| [grok-build-pi-comparison.html](./diagrams/grok-build-pi-comparison.architecture.html) | 与 Pi 架构对照：Session FIFO vs runLoop while |

规格源文件：`diagrams/*.json`

---

## 阅读路径

| 你是谁 | 路径 |
|--------|------|
| **第一次读** | DESIGN_THINKING_SERIES → ARCHITECTURE Part I |
| **Memory / Plan / MA** | ARCHITECTURE §II.4 |
| **与 Pi 对照** | [pi/docs/DESIGN_THINKING_SERIES](../../pi/docs/DESIGN_THINKING_SERIES.md) |
| **Prompt 全文** | GROK_RUNTIME_PROMPTS |

---

## 与 Pi / OpenHuman 对照

| 语义 | Grok Build | Pi | OpenHuman |
|------|------------|-----|-----------|
| 运行中注入 | Interjection | steer() | QueueMode::Steer |
| turn 后再跑 | pending_inputs | followUp() | Followup |
| 外层队列 | Session FIFO | runLoop while | 队列模式 |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-10
