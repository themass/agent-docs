# 源码深潜索引（LongHorizon-Harness）

对照打开：`src/lh_harness/`。

| 文件 | 源码 | 内容 |
|------|------|------|
| [01-manager-loop.md](./01-manager-loop.md) | `manager.py` | `run` 崩溃边界 · `_run_impl` 整轮 · 完成门禁 · `_run_role_episode` · human gate |
| [02-adapters-env-auditor.md](./02-adapters-env-auditor.md) | `adapters/*` · `environment/*` · `auditor_agent.py` · `role_prompts.py` | Protocol · CommandAgent · 路由解析 · AuditReport |
| [03-supervisor-web.md](./03-supervisor-web.md) | `supervisor/*` · `webapi/*` · `cli.py` 片段 | RunSupervisor · worker · 事件 |

上级：[CORE_RUNTIME.md](../CORE_RUNTIME.md)
