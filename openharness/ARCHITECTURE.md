# OpenHarness 系统架构（导航）

> **版本**: v0.1.9 · **最后更新**: 2026-08-05  
> **完整大纲**: [README.md](./README.md) · **模块目录**: [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md)

原先约 10,800 行的单体文已归档为 [ARCHITECTURE_MONOLITH.md](./ARCHITECTURE_MONOLITH.md)（**勿在 IDE 中直接打开**）。日常从 [README.md](./README.md) 或下表进入分章。

---

## 按主题

| 主题 | 文档 |
|------|------|
| Engine / ReAct / Compact | [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md) |
| Session / Memory | [ARCHITECTURE_SESSION_MEMORY.md](./ARCHITECTURE_SESSION_MEMORY.md) |
| Prompt | [ARCHITECTURE_PROMPTS.md](./ARCHITECTURE_PROMPTS.md) |
| Tools / Swarm / 子 Agent | [ARCHITECTURE_TOOLS_SWARM.md](./ARCHITECTURE_TOOLS_SWARM.md) |
| Coordinator | [ARCHITECTURE_COORDINATOR.md](./ARCHITECTURE_COORDINATOR.md) |
| Sandbox / Hooks | [ARCHITECTURE_SANDBOX_HOOKS.md](./ARCHITECTURE_SANDBOX_HOOKS.md) |
| Skills / Plugins | [ARCHITECTURE_SKILLS_PLUGINS.md](./ARCHITECTURE_SKILLS_PLUGINS.md) |
| Permissions / MCP | [ARCHITECTURE_PERMISSIONS_MCP.md](./ARCHITECTURE_PERMISSIONS_MCP.md) |
| Tasks / Auth | [ARCHITECTURE_TASKS_AUTH.md](./ARCHITECTURE_TASKS_AUTH.md) |
| UI / Config | [ARCHITECTURE_UI_CONFIG.md](./ARCHITECTURE_UI_CONFIG.md) |
| Backend Host / 前端 | [BACKEND_HOST_ARCHITECTURE.md](./BACKEND_HOST_ARCHITECTURE.md) |
| 全模块索引 + 横切主题 | [ARCHITECTURE_MODULE_CATALOG.md](./ARCHITECTURE_MODULE_CATALOG.md) |

---

## 设计理念（摘要）

> **The model is the agent. The code is the harness.**

自研 `QueryEngine` + ReAct，非 LangGraph 子图。子 Agent 通过 `agent` 工具非阻塞 spawn；Coordinator 模式由 `drain_coordinator_async_agents` 收 Worker 结果。

- Prompt：每条用户消息重建 `build_runtime_system_prompt`（见 [ARCHITECTURE_PROMPTS.md](./ARCHITECTURE_PROMPTS.md)）
- Compact：四层渐进（见 [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md)）
- 框架横向对比：[framework-comparison/README.md](./framework-comparison/README.md)

全文检索归档：`rg "关键词" ARCHITECTURE_MONOLITH.md`
