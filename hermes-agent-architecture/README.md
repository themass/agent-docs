# Hermes Agent 架构与设计文档中心

> **源码仓**: `hermes-dev/hermes-agent`（Nous Research）  
> **产品面**: Hermes Workspace · Hermes WebUI · Hermes Studio · Desktop  
> **体例参照**: [CROSS_AGENT_DESIGN_INDEX](../CROSS_AGENT_DESIGN_INDEX.md) · [OpenHarness HARNESS-SPECTRUM](../../OpenHarness/docs/framework-comparison/HARNESS-SPECTRUM.md)  
> **整理日期**: 2026-09-10

Hermes 是 **族 A（SessionDB + 单列表）** 的个人助手 harness：Gateway 多平台、ReAct turn loop、三层 Memory、Skills/Plugins 扩展、子代理委派。本目录把 **散落在 `hermes-dev/` 各子仓的新 feature 设计** 收拢为可检索索引；深潜仍以各子仓 canonical 文档为准。

---

## 先读什么

| 读者 | 路径 | 时长 |
|------|------|------|
| **第一次建立心智模型** | [FEATURE_DESIGN_CATALOG.md](./FEATURE_DESIGN_CATALOG.md) §0–§2 | ~20min |
| **多 Agent / Swarm** | 目录 §3 + `hermes-workspace/docs/swarm2-*.md` | ~40min |
| **Agent 内核改代码** | `hermes-agent/AGENTS.md` → `agent/conversation_loop.py` | 按需 |
| **跨框架对照** | [AGENT_PROJECTS 对比](../AGENT_PROJECTS_FULL_ARCHITECTURE_COMPARISON.md) · [framework-comparison/14-loop-interjection](../../OpenHarness/docs/framework-comparison/14-loop-interjection.md) | ~30min |

---

## 文档全目录

| 文档 | 说明 |
|------|------|
| [**FEATURE_DESIGN_CATALOG**](./FEATURE_DESIGN_CATALOG.md) | **新 feature 设计总表**（版本轴 + 状态 + 源码锚点） |
| [hermes-agent/docs/VERSION_HISTORY.md](../../hermes-dev/hermes-agent/docs/VERSION_HISTORY.md) | CalVer 0.10→0.19 发版矩阵 |
| [hermes-agent/docs/MULTI_AGENT_ARCHITECTURE.md](../../hermes-dev/hermes-agent/docs/MULTI_AGENT_ARCHITECTURE.md) | `delegate_task` · 子代理 · HITL |
| [hermes-agent/docs/SURFACE_ARCHITECTURE.md](../../hermes-dev/hermes-agent/docs/SURFACE_ARCHITECTURE.md) | 四 Surface · Gateway 事件总线 |
| [hermes-agent/docs/MEMORY_SYSTEM.md](../../hermes-dev/hermes-agent/docs/MEMORY_SYSTEM.md) | 三层 Memory 主模型 |
| [hermes-workspace/CHANGELOG.md](../../hermes-dev/hermes-workspace/CHANGELOG.md) | Workspace 2.0 Zero-fork · 2.1 Swarm |
| [hermes-workspace/docs/HARNESS_HUB.md](../../hermes-dev/hermes-workspace/docs/HARNESS_HUB.md) | AionCore 外部 harness 兼容层 |
| [hermes-workspace/FUTURE-FEATURES.md](../../hermes-dev/hermes-workspace/FUTURE-FEATURES.md) | App Factory 后续（handoff / 角色分工） |

---

## 10 分钟速览

1. **真源** — `SessionDB`（`state.db`）+ 冻结注入的 `MEMORY.md` / `USER.md` → [MEMORY_SYSTEM](../../hermes-dev/hermes-agent/docs/MEMORY_SYSTEM.md)
2. **Loop** — `run_agent` → `conversation_loop` ReAct；**prompt cache 神圣不可侵犯**（压缩是唯一例外）→ [AGENTS.md](../../hermes-dev/hermes-agent/AGENTS.md)
3. **中途输入** — 默认 **interrupt**；可配 queue / steer → [14-loop-interjection](../../OpenHarness/docs/framework-comparison/14-loop-interjection.md)
4. **子代理** — `delegate_task` 隔离上下文 + 独立预算；0.17 async · 0.19 live transcript tail
5. **产品栈** — CLI / Ink TUI / Desktop / WebUI 共享 Gateway WS；Workspace 2.x 加 Conductor · Swarm2 · Harness Hub
6. **进行中** — Tool artifact 与 context 分离、Swarm2 autopilot、多 Gateway pool

---

## 与 monorepo 其他 harness 的关系

| 对照轴 | Hermes | 近邻 |
|--------|--------|------|
| 真源族 | A SessionDB | nanobot · OpenHarness |
| Gateway | 23+ 消息面 | OpenCode admit 分离 |
| 多 Agent | delegate + Kanban + Swarm2 持久 worker | OpenHarness Swarm 子进程 |
| 压缩 | ContextCompressor + Curator | OpenHarness 四层 compact |
| 外部 harness | Harness Hub / ACP | 无（本仓独有） |

**Archify 图解**: 待建（见 [ARCHIFY_DIAGRAM_PROGRAM](../ARCHIFY_DIAGRAM_PROGRAM.md) P7）。
