# OpenManus — 架构导航

> **完整大纲**: [README.md](./README.md)  
> **推荐先读**: [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) → [**ARCHITECTURE_PART1.md**](./ARCHITECTURE_PART1.md)

---

## 文档全目录

| 文档 | 锚点 |
|------|------|
| [DESIGN_THINKING_SERIES](./DESIGN_THINKING_SERIES.md#目录) | 九步导读 |
| [**SYSTEM_ARCHITECTURE**](./SYSTEM_ARCHITECTURE.md) | 整体架构、入口、状态边界 |
| [**MODULES_AND_INTERACTIONS**](./MODULES_AND_INTERACTIONS.md) | 模块设计与交互契约 |
| [**RUNTIME_FLOWS**](./RUNTIME_FLOWS.md) | 完整运行流程设计 |
| [ARCHITECTURE_PART1](./ARCHITECTURE_PART1.md#目录) | §0–§9 核心架构 |
| [ARCHITECTURE_PART2](./ARCHITECTURE_PART2.md#目录) | 工具 / MCP / Planning |
| [**PLAN_MODE_SOURCE_WALKTHROUGH**](./PLAN_MODE_SOURCE_WALKTHROUGH.md) | Plan 模式逐步 message 导读 |
| [**ARCHITECTURE_ATLAS**](./ARCHITECTURE_ATLAS.md#目录) | **全维度概念图谱** |
| [ARCHITECTURE_DESIGN](../../OpenManus/docs/ARCHITECTURE_DESIGN.md#目录) | 17 章全量 |

---

## 分章索引

| Part | 链接 | 章节 |
|------|------|------|
| **导读** | [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) | think/act、Tool、Flow、MCP、边界 |
| **Part 1 核心** | [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | §1 分层 · §3 类图 · §4 Agent 五模块 · §5–7 流程 · §8 特点 |
| **Part 2 专题** | [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | 工具 · MCP · Planning 深潜 · 沙箱 |
| **Plan 源码** | [PLAN_MODE_SOURCE_WALKTHROUGH.md](./PLAN_MODE_SOURCE_WALKTHROUGH.md) | 完整示例 · 三本账 · 每步 Memory |
| **全量深潜** | [ARCHITECTURE_DESIGN.md](../../OpenManus/docs/ARCHITECTURE_DESIGN.md) | 17 章完整版 |

---

## 10 分钟速览

1. **内核** — `BaseAgent.run` → `step` = `think` + `act`
2. **工具** — `ToolCollection.execute` 统一入口
3. **终止** — `Terminate` → `FINISHED`；max_steps 仅回 IDLE
4. **PlanningFlow** — 外层 plan，内层完整 ReAct → [源码导读](./PLAN_MODE_SOURCE_WALKTHROUGH.md)
5. **MCP** — 客户端合并工具 + 可选服务端
6. **定位** — 教学内核，非生产 harness

---

## 设计目标（一句话）

提供 **可读、可改、可扩展** 的 ReAct + tool calling 参考实现；复杂 harness 由应用层自建。

返回：[文档中心](./README.md)
