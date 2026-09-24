# OpenHarness 文档中心

> **包版本**: 0.1.9 · **同步说明**: [ARCHITECTURE_DOCS_SYNC.md](./ARCHITECTURE_DOCS_SYNC.md)  
> **最后整理**: 2026-08-05（分类合并去重；删除重复导航与已并入分章的独立稿）

---

## 完整大纲

| 类别 | 文档 | 说明 |
|------|------|------|
| **入口** | [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构轻量导航（10 分钟） |
| **模块目录** | [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md) | 概述 §1–§3、§4 索引、横切 §5–§12 |
| **同步** | [ARCHITECTURE_DOCS_SYNC.md](./ARCHITECTURE_DOCS_SYNC.md) | 分章版本与源码锚点 |
| **归档** | [ARCHITECTURE_MONOLITH.md](./ARCHITECTURE_MONOLITH.md) | 历史单体（~10800 行，**勿在 IDE 打开**） |

### A. 快速上手

| 文档 | 说明 |
|------|------|
| [DEV_SOURCE_RUN.md](./DEV_SOURCE_RUN.md) | CLI / TUI / BackendHost / Coordinator 启动时序 |
| [OHMO_DESIGN.md](./OHMO_DESIGN.md) | ohmo 个人 Agent、`~/.ohmo`、Gateway |
| [DEMO_EXECUTION_FLOW.md](./DEMO_EXECUTION_FLOW.md) | 端到端执行走读 |

### B. 核心分章（按源码模块）

| 主题 | 文档 | 关键源码 |
|------|------|----------|
| Engine / Compact | [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md) | `engine/query.py`, `services/compact/` |
| Session / Memory | [ARCHITECTURE_SESSION_MEMORY.md](./ARCHITECTURE_SESSION_MEMORY.md) | `state/`, `memory/` |
| Prompt 装配 | [ARCHITECTURE_PROMPTS.md](./ARCHITECTURE_PROMPTS.md) | `prompts/context.py` |
| Tools / Swarm | [ARCHITECTURE_TOOLS_SWARM.md](./ARCHITECTURE_TOOLS_SWARM.md) | `tools/`, `swarm/`（含 Worker 深潜附录） |
| Coordinator | [ARCHITECTURE_COORDINATOR.md](./ARCHITECTURE_COORDINATOR.md) | `coordinator/`, `ui/coordinator_drain.py` |
| Sandbox / Hooks | [ARCHITECTURE_SANDBOX_HOOKS.md](./ARCHITECTURE_SANDBOX_HOOKS.md) | `sandbox/`, `hooks/` |
| Skills / Plugins | [ARCHITECTURE_SKILLS_PLUGINS.md](./ARCHITECTURE_SKILLS_PLUGINS.md) | `skills/`, `plugins/` |
| Permissions / MCP | [ARCHITECTURE_PERMISSIONS_MCP.md](./ARCHITECTURE_PERMISSIONS_MCP.md) | `permissions/`, `mcp/` |
| Tasks / Auth | [ARCHITECTURE_TASKS_AUTH.md](./ARCHITECTURE_TASKS_AUTH.md) | `tasks/`, `auth/` |
| UI / Config | [ARCHITECTURE_UI_CONFIG.md](./ARCHITECTURE_UI_CONFIG.md) | `config/`, `ui/` |
| Backend Host | [BACKEND_HOST_ARCHITECTURE.md](./BACKEND_HOST_ARCHITECTURE.md) | `backend_host.py`, React 终端 |

### C. Prompt 专题（分层阅读，有重叠）

| 文档 | 侧重 |
|------|------|
| [ARCHITECTURE_PROMPTS.md](./ARCHITECTURE_PROMPTS.md) | **首选**：源码级装配、动态注入 |
| [RUNTIME_PROMPT_COMPLETE.md](./RUNTIME_PROMPT_COMPLETE.md) | 运行时 Section 清单与真机示例 |
| [PROMPT_SYSTEM_DESIGN.md](./PROMPT_SYSTEM_DESIGN.md) | 设计哲学、与 deepagents 等对比 |
| [OPENHARNESS_SKILLS_RUNTIME.md](./OPENHARNESS_SKILLS_RUNTIME.md) | Skills 加载管线（非 deepagents） |

### D. 全工程 Harness 设计对比

| 文档 | 说明 |
|------|------|
| [**framework-comparison/00-HARNESS-DESIGN-PHILOSOPHY.md**](./framework-comparison/00-HARNESS-DESIGN-PHILOSOPHY.md) | **推荐先读**：Harness 设计思想、五平面、十条原则 |
| [framework-comparison/HARNESS-SPECTRUM.md](./framework-comparison/HARNESS-SPECTRUM.md) | 框架设计光谱（无路径表） |
| [framework-comparison/README.md](./framework-comparison/README.md) | 完整目录：设计层 / 专题层 / 实现索引 |
| [FRAMEWORK_MODULES_COMPARISON.md](./FRAMEWORK_MODULES_COMPARISON.md) | 旧版对比入口（链到 framework-comparison） |

### E. 对照学习（非 OpenHarness 本体）

| 文档 | 说明 |
|------|------|
| [guides/README.md](./guides/README.md) | deepagents Prompt/Skill、LangChain Middleware |

---

## 阅读路径（按角色）

| 角色 | 路径 | 时间 |
|------|------|------|
| 新手 | README → [DEV_SOURCE_RUN.md](./DEV_SOURCE_RUN.md) → [DEMO_EXECUTION_FLOW.md](./DEMO_EXECUTION_FLOW.md) | ~2h |
| Agent 开发者 | [ARCHITECTURE_PROMPTS.md](./ARCHITECTURE_PROMPTS.md) → [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md) | ~4h |
| 核心贡献者 | [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md) → [BACKEND_HOST_ARCHITECTURE.md](./BACKEND_HOST_ARCHITECTURE.md) → [ARCHITECTURE_TASKS_AUTH.md](./ARCHITECTURE_TASKS_AUTH.md) | ~8h |
| 架构师 | [framework-comparison/00-HARNESS-DESIGN-PHILOSOPHY.md](./framework-comparison/00-HARNESS-DESIGN-PHILOSOPHY.md) → [HARNESS-SPECTRUM](./framework-comparison/HARNESS-SPECTRUM.md) → [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md) | ~4h |
| Ohmo 部署 | [OHMO_DESIGN.md](./OHMO_DESIGN.md) → [DEV_SOURCE_RUN.md](./DEV_SOURCE_RUN.md) | ~2h |

---

## 合并说明（2026-08-05）

| 已删除 / 旧文件 | 现行位置 |
|-----------------|----------|
| `ARCHITECTURE_INDEX.md` | [README.md](./README.md) + [ARCHITECTURE.md](./ARCHITECTURE.md) |
| `ARCHITECTURE_COMPLETE.md` | [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md)（§4.1–4.10 长文 → 分章跳转表；§4.3–4.5 保留正文） |
| `MCP_INTEGRATION_SUMMARY.md` | [ARCHITECTURE_PERMISSIONS_MCP.md](./ARCHITECTURE_PERMISSIONS_MCP.md) 附录 |
| `COORDINATOR_UI_POLLING.md` | [ARCHITECTURE_COORDINATOR.md](./ARCHITECTURE_COORDINATOR.md) 附录 |
| `WORKER_MESSAGE_PASSING_DEEP_DIVE.md` | [ARCHITECTURE_TOOLS_SWARM.md](./ARCHITECTURE_TOOLS_SWARM.md) 深潜 §1 |
| `SPAWN_SUBAGENT_IO_TOPOLOGY.md` | [ARCHITECTURE_TOOLS_SWARM.md](./ARCHITECTURE_TOOLS_SWARM.md) 深潜 §2 |
| `LANGCHAIN_MIDDLEWARE.md` 等根目录对照稿 | [guides/](./guides/README.md) |

**刻意保留多文件**（角色不同、未深度去重）：`PROMPT_SYSTEM_DESIGN.md`、`RUNTIME_PROMPT_COMPLETE.md`、`ARCHITECTURE_MONOLITH.md`（归档）。

**维护者**: OpenHarness Community
