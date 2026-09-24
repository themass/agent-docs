# OpenManus 架构设计文档中心

> **项目**: [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus)（本仓库 `OpenManus/`）  
> **体例参照**: [agent-framework/docs](../../agent-framework/docs/README.md)  
> **全量深潜**: [OpenManus/docs/ARCHITECTURE_DESIGN.md](../../OpenManus/docs/ARCHITECTURE_DESIGN.md)

OpenManus 是 **轻量 Manus-like Agent 内核**：`Memory` + ReAct（`think`/`act`）+ OpenAI tool calling；可选 **PlanningFlow**、**MCP** 双向扩展。

---

## 文档全目录

| 文档 | 说明 |
|------|------|
| [DESIGN_THINKING_SERIES](./DESIGN_THINKING_SERIES.md#目录) | 九步图解导读 |
| [**SYSTEM_ARCHITECTURE**](./SYSTEM_ARCHITECTURE.md) | **整体架构、分层、入口、状态边界** |
| [**MODULES_AND_INTERACTIONS**](./MODULES_AND_INTERACTIONS.md) | **模块职责、依赖、交互契约** |
| [**RUNTIME_FLOWS**](./RUNTIME_FLOWS.md) | **单 Agent / Plan / MCP / Sandbox 完整流程** |
| [**ARCHITECTURE_PART1**](./ARCHITECTURE_PART1.md#目录) | §0–§9 + 附录 |
| [ARCHITECTURE_PART2](./ARCHITECTURE_PART2.md#目录) | 工具、MCP、Planning |
| [**PLAN_MODE_SOURCE_WALKTHROUGH**](./PLAN_MODE_SOURCE_WALKTHROUGH.md) | **Plan 模式源码导读**：完整示例 + 每步 message 变化 |
| [**ARCHITECTURE_ATLAS**](./ARCHITECTURE_ATLAS.md#目录) | **全维度图谱**：Memory/Loop/Sandbox/队列/Plan… |
| [ARCHITECTURE_DESIGN](../../OpenManus/docs/ARCHITECTURE_DESIGN.md#目录) | 17 章全量深潜 |
| [ARCHITECTURE](./ARCHITECTURE.md) | 导航入口 |

---

## 三卷结构

| 卷 | 文件 | 内容 |
|----|------|------|
| **导读** | [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) | 九步图解（推荐先读，~35min） |
| **Part 1** | [**ARCHITECTURE_PART1.md**](./ARCHITECTURE_PART1.md) | 分层、类图、Agent 五模块、think/act、PlanningFlow、时序、特点 |
| **Part 2** | [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | 工具系统、MCP、沙箱、改造建议 |
| **Plan 源码** | [PLAN_MODE_SOURCE_WALKTHROUGH.md](./PLAN_MODE_SOURCE_WALKTHROUGH.md) | 完整示例 + 每步 message |
| **全量** | [ARCHITECTURE_DESIGN.md](../../OpenManus/docs/ARCHITECTURE_DESIGN.md) | 17 章完整深潜（~60KB） |

| 入口 | [ARCHITECTURE.md](./ARCHITECTURE.md) |

---

## 10 分钟速览

1. **整体架构** — 系统边界、模块分层、状态所有权 → [SYSTEM_ARCHITECTURE](./SYSTEM_ARCHITECTURE.md)
2. **模块交互** — Flow / Agent / LLM / Tool / MCP / Sandbox → [MODULES_AND_INTERACTIONS](./MODULES_AND_INTERACTIONS.md)
3. **完整流程** — 单 Agent、PlanningFlow、MCP、Sandbox → [RUNTIME_FLOWS](./RUNTIME_FLOWS.md)
4. **内核** — `think()` + `act()` ReAct → [Part 1 §5](./ARCHITECTURE_PART1.md#§5-thinkact-内层循环)
5. **状态** — `Memory` + `AgentState`，无持久化 → [Part 1 §3](./ARCHITECTURE_PART1.md#§3-核心实体与类图)
6. **工具** — `BaseTool` → `ToolCollection` → [Part 2 §1](./ARCHITECTURE_PART2.md#§1-工具系统设计)
7. **外层编排** — `PlanningFlow` 按 step 调 executor → [Part 1 §6](./ARCHITECTURE_PART1.md#§6-planningflow--外层编排) · [源码导读](./PLAN_MODE_SOURCE_WALKTHROUGH.md)
8. **MCP** — 客户端代理 + FastMCP 服务端 → [Part 2 §2](./ARCHITECTURE_PART2.md#§2-mcp-双向扩展)
9. **非目标** — 无 Gateway、checkpoint、权限层 → [Part 1 §9](./ARCHITECTURE_PART1.md#§9-边界与非目标)

---

## 概念交叉索引

| 你想搞懂… | 读 |
|-----------|-----|
| 继承链 Manus | Part 1 §2.2 |
| run 循环源码 | Part 1 §4.2 · `app/agent/base.py` |
| Terminate | Part 1 §4.6 |
| Planning 路由 | Part 2 §3 · [源码导读](./PLAN_MODE_SOURCE_WALKTHROUGH.md) |
| 与 MetaGPT 对比 | Part 1 §0.3 · Part 1 §8.4 |
| 全量时序 | ARCHITECTURE_DESIGN §11 |

---

## 阅读路径

| 时间 | 路径 |
|------|------|
| 35 分钟 | DESIGN_THINKING_SERIES |
| 1 小时 | 导读 → Part 1 |
| MCP / 工具 | Part 2 |
| 改代码 | Part 1 → `app/agent/manus.py` |

---

## 与 MetaGPT / Codex 对照

| 维度 | OpenManus | MetaGPT | Codex |
|------|-----------|---------|-------|
| 编排 | 单 Agent + Flow | Team + bus | Session |
| 状态 | 内存 Memory | 消息 + 文件 | Rollout |
| 工具 | ToolCollection | Action/命令 | 四层安全 |
| 持久化 | 无框架级 | ProjectRepo | JSONL |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-09
