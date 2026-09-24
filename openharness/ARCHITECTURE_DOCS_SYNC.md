# OpenHarness 架构文档同步说明

> **同步基准**: 2026-08-05 · **包版本**: 0.1.9  
> **导航入口**: [README.md](./README.md)（取代 `ARCHITECTURE_INDEX.md`）

---

## 阅读顺序

1. [README.md](./README.md) — 完整大纲与角色路径  
2. [ARCHITECTURE.md](./ARCHITECTURE.md) — 轻量主题表  
3. 下表 **权威分章** 或 [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md)

---

## 分章与源码锚点

| 文档 | 版本 | 权威范围 | 关键源码 |
|------|------|----------|----------|
| [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md) | v1.4 | ReAct、Compact、子 Agent、drain | `engine/query.py`, `ui/coordinator_drain.py` |
| [ARCHITECTURE_PROMPTS.md](./ARCHITECTURE_PROMPTS.md) | v1.6 | Prompt 装配 | `prompts/context.py` |
| [ARCHITECTURE_SESSION_MEMORY.md](./ARCHITECTURE_SESSION_MEMORY.md) | v1.3 | Session、Compact 数据结构 | `state/`, `services/compact/` |
| [ARCHITECTURE_TOOLS_SWARM.md](./ARCHITECTURE_TOOLS_SWARM.md) | v2.2+ | Tools、Swarm、Worker 深潜附录 | `tools/`, `swarm/` |
| [ARCHITECTURE_COORDINATOR.md](./ARCHITECTURE_COORDINATOR.md) | v1.0+ | Coordinator、UI 轮询附录 | `coordinator/`, `ui/coordinator_drain.py` |
| [ARCHITECTURE_PERMISSIONS_MCP.md](./ARCHITECTURE_PERMISSIONS_MCP.md) | v1.1+ | 权限、MCP、示例附录 | `permissions/`, `mcp/` |
| [ARCHITECTURE_SKILLS_PLUGINS.md](./ARCHITECTURE_SKILLS_PLUGINS.md) | v1.1 | Skills、Plugins | `skills/`, `plugins/` |
| [ARCHITECTURE_SANDBOX_HOOKS.md](./ARCHITECTURE_SANDBOX_HOOKS.md) | v1.1 | Sandbox、Hooks | `sandbox/`, `hooks/` |
| [ARCHITECTURE_TASKS_AUTH.md](./ARCHITECTURE_TASKS_AUTH.md) | v1.1 | Tasks、Auth | `tasks/manager.py` |
| [ARCHITECTURE_UI_CONFIG.md](./ARCHITECTURE_UI_CONFIG.md) | v1.0 | Settings、CLI、UI | `config/settings.py`, `ui/runtime.py` |
| [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md) | — | 概述、§4.11–4.29 索引、§5–§12 | 各模块目录 |
| [BACKEND_HOST_ARCHITECTURE.md](./BACKEND_HOST_ARCHITECTURE.md) | v1.7 | BackendHost、React 终端 | `backend_host.py` |

---

## 归档

| 文件 | 说明 |
|------|------|
| [ARCHITECTURE_MONOLITH.md](./ARCHITECTURE_MONOLITH.md) | 历史单体；用 `rg` 检索，勿在 Cursor 打开 |
| [PROMPT_SYSTEM_DESIGN.md](./PROMPT_SYSTEM_DESIGN.md) | Prompt 长文；与 PROMPTS 互补 |
| [framework-comparison/12-modules-reference.md](./framework-comparison/12-modules-reference.md) | 全工程模块对比单体（恢复） |

---

## 2026-08 文档整理

- 删除 `ARCHITECTURE_INDEX.md`、`ARCHITECTURE_COMPLETE.md`（并入 README + `ARCHITECTURE_MODULE_CATALOG.md`）
- MCP / Coordinator / Swarm 深潜并入对应分章附录
- 外部对照文档移至 [guides/](./guides/README.md)
