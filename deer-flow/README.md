# deer-flow 文档目录（导航 + 时效标记）

> **为什么有这个 README**：本目录有 **40+ 篇** deer-flow 文档，但此前没有索引，且各篇基线日期从 **2026-04 到 2026-11** 不等。下表给每篇标注**基线**与**时效**，避免读到过时描述。
> **本仓库（docs）可写；上游 deer-flow 仓库只读**（证据基线 HEAD `235b5556`，2026-11-04）。
> 时效图例：🟢 与当前源码一致 · ⚠️ 部分过时（顶部有快照注记） · 🔴 关键章节已被取代 · 📦 历史存档/快照

---

## 1. 必读（当前基线）

| 文档 | 基线 | 内容 |
|---|---|---|
| **[DEERFLOW_UPDATE_2026Q4.md](./DEERFLOW_UPDATE_2026Q4.md)** 🟢 | 2026-11-04 | 2026-09-06 → 2026-11-04 的**架构增量**：扩展面重构、Knowledge 契约、决策面（TypeSafe/OpenAI Decisions/authz）、Runtime 与可靠性（Queue&Steer / HarnessGuard / 多副本 / blob store / checkpoint retention）、Middleware 链现状、Workflows/Teams/Scheduled、持久化与运维、变更台账、旧文档阅读映射 |
| **[DEERMEM_MEMORY_DESIGN.md](./DEERMEM_MEMORY_DESIGN.md)** 🟢 | 2026-11-04 | 记忆子系统完整设计：L0–L4 分层、作用域与磁盘布局、manifest/fact/sidecar 数据模型、写路径与闸门、注入与检索、生命周期（staleness/consolidation/淘汰）、事务与崩溃恢复、prescreen/信号分类、配置全表、后端矩阵、端到端实例 |

## 2. 架构与运行时

| 文档 | 基线 | 时效 | 备注 |
|---|---|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 2026-09-06 | ⚠️ | 骨架仍有用；Component/DataFlow/Security 以 UPDATE 文为准 |
| [DEERFLOW_ARCHITECTURE_V2.md](./DEERFLOW_ARCHITECTURE_V2.md) | 2026-06-08 | 🔴 | §3 middleware、§5 记忆、§7 Guardrails、§2 RuntimeFeatures 已被取代（顶部有对照表） |
| [middleware-execution-flow.md](./middleware-execution-flow.md) | 2026-09-06 | 🔴 链清单 / 🟢 洋葱分析 | 链清单以 UPDATE 文 §7 为准 |
| [API.md](./API.md) | 2026-09-06 | ⚠️ | 上游 `backend/docs/API.md`（98K）更全 |
| [STREAMING.md](./STREAMING.md) · [RUN_EVENT_STREAM.md](./RUN_EVENT_STREAM.md) | 2026-09-06 | ⚠️ | 缺 producer fencing（#7619）、Queue & Steer（#7729） |
| [summarization.md](./summarization.md) | 2026-09-06 | 🟢 | 补：per-LLM-call 遥测（#6236）、compaction observer 契约（#7831） |
| [TUI.md](./TUI.md) | 2026-09-06 | 🟢 | 上游同名文档更全 |
| [plan_mode_usage.md](./plan_mode_usage.md) · [task_tool_improvements.md](./task_tool_improvements.md) | 2026-09-06 | ⚠️ | 使用向 |
| [PROMPT_AND_CONTEXT_FULL_CHAIN.md](./PROMPT_AND_CONTEXT_FULL_CHAIN.md) | 2026-09-06 | ⚠️ | 缺 prompt overlays（#5794）、client context capabilities（#7051） |

## 3. 配置与运维

| 文档 | 基线 | 时效 | 备注 |
|---|---|---|---|
| [CONFIGURATION.md](./CONFIGURATION.md) | 2026-09-06 | ⚠️ | 上游同名文件已 153K，`config_version: 64`；缺 `harness_guard:`、`scheduler:`、`agent_storage:`、`extensions.middlewares[].apply_to` |
| [memory-settings-sample.json](./memory-settings-sample.json) | 2026-03-28 | 🔴 | **legacy L1 manifest 样例**（`version:"1.0"` + facts 内联 + 无 `revision`）；文件内已加 `_note/_status/_see_also` |
| [PATH_EXAMPLES.md](./PATH_EXAMPLES.md) · [FILE_UPLOAD.md](./FILE_UPLOAD.md) | 2026-09-06 | ⚠️ | 路径与上传行为需对照上游 |
| [AUTO_TITLE_GENERATION.md](./AUTO_TITLE_GENERATION.md) · [TITLE_GENERATION_IMPLEMENTATION.md](./TITLE_GENERATION_IMPLEMENTATION.md) | 2026-08/09 | 🟢 | Title 中间件仍在链中（UPDATE 文 §7.3 #8） |

## 4. 安全与权限

| 文档 | 基线 | 时效 |
|---|---|---|
| [GUARDRAILS.md](./GUARDRAILS.md) | 2026-09-06 | ⚠️（缺两个后端与 §5.3 语义） |
| [AUTH_DESIGN.md](./AUTH_DESIGN.md) · [AUTH_QUICK_REFERENCE_zh.md](./AUTH_QUICK_REFERENCE_zh.md) · [SSO.md](./SSO.md) | 2026-08/09 | ⚠️（上游新增 `AUTH_UPGRADE.md`、`AUTH_TEST_PLAN.md`） |

## 5. 集成与生态

| 文档 | 基线 | 时效 |
|---|---|---|
| [MCP_SERVER.md](./MCP_SERVER.md) · [MCP_SERVER_zh.md](./MCP_SERVER_zh.md) | 2026-09-06 | ⚠️（缺 `mcp_tasks`、control leases） |
| [IM_CHANNEL_CONNECTIONS.md](./IM_CHANNEL_CONNECTIONS.md) | 2026-09-06 | ⚠️（缺 leader lease、notification outbox） |
| [GITHUB_AGENTS.md](./GITHUB_AGENTS.md) | 2026-07-23 | ⚠️ |
| [APP_PACKAGE_AND_AGENT_ECOSYSTEM.md](./APP_PACKAGE_AND_AGENT_ECOSYSTEM.md) · [_zh 版](./APP_PACKAGE_AND_AGENT_ECOSYSTEM_zh.md) | 2026-09-06 | ⚠️ |
| [DEEP_AGENTS_VS_DEERFLOW_PROMPT_COMPARISON.md](./DEEP_AGENTS_VS_DEERFLOW_PROMPT_COMPARISON.md) | 2026-09-06 | 🟢 对比向 |
| [rfc-create-deerflow-agent.md](./rfc-create-deerflow-agent.md) · [rfc-extract-shared-modules.md](./rfc-extract-shared-modules.md) | 2026-09-06 / 2026-04 | 📦 RFC 存档 |

## 6. 系统提示词快照（12 篇，📦 快照非设计文档）

| 组 | 文件 |
|---|---|
| lead agent（中/英 × 子代理开关） | [CN_DISABLED](./SYSTEM_PROMPT_CN_SUBAGENT_DISABLED.md) · [CN_ENABLED](./SYSTEM_PROMPT_CN_SUBAGENT_ENABLED.md) · [EN_DISABLED](./SYSTEM_PROMPT_EN_SUBAGENT_DISABLED.md) · [EN_ENABLED](./SYSTEM_PROMPT_EN_SUBAGENT_ENABLED.md) |
| deepagents 基座（中/英 × 子代理开关） | [CN_DISABLED](./SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md) · [CN_ENABLED](./SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md) · [EN_DISABLED](./SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md) · [EN_ENABLED](./SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md) |
| 运行时装配 | [RUNTIME_DEEPAGENTS.md](./SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md) · [RUNTIME_LEAD_AGENT.md](./SYSTEM_PROMPT_RUNTIME_LEAD_AGENT.md) |

> 引用时必须注明快照日期（2026-09-06）；prompt 内容在 2.2.0 期间多次变化（operator overlays、reasoning contract、`@` 引用）。

## 7. 存档

| 文档 | 说明 |
|---|---|
| [DEERFLOW_FRAMEWORK_QA_ARCHIVE.md](./DEERFLOW_FRAMEWORK_QA_ARCHIVE.md) | 2369 行问答归档，⚠️ 大量结论已过期，仅作历史检索 |
| [TODO.md](./TODO.md) | 2026-05 起的待办记录 |

---

## 8. 按问题找文档

| 想搞清楚 | 直接读 |
|---|---|
| 「记忆到底怎么分层、怎么写、怎么检索」 | DEERMEM §1–§7（端到端实例在 §14） |
| 「一轮请求经过哪些中间件、顺序为什么这样」 | DEERFLOW_UPDATE §7.2–§7.3 |
| 「用户中途发消息会发生什么」 | DEERFLOW_UPDATE §6.1（Queue & Steer）+ §6.2（HarnessGuard） |
| 「知识库怎么接进来、权限怎么限」 | DEERFLOW_UPDATE §4（契约/能力/作用域）+ §4.4（scope 三态） |
| 「工具调用会不会被拒绝、依据什么」 | DEERFLOW_UPDATE §5.1–§5.3 + §5.4（authz） |
| 「多副本部署要配什么、哪些检查会拦住启动」 | DEERFLOW_UPDATE §6.4 + §9.2 |
| 「排期任务/团队/脚本编排该用哪个」 | DEERFLOW_UPDATE §8.1（对比表）+ §8.2–§8.4 |
| 「升级要注意什么」 | DEERFLOW_UPDATE §9.4（breaking）+ §9.5（security）+ §10（台账） |

## 9. 维护约定

- **不删旧文**：过期文档保留，并在顶部加「文档基线 + 取代去处」注记（已对 `ARCHITECTURE.md`、`DEERFLOW_ARCHITECTURE_V2.md`、`middleware-execution-flow.md`、`memory-settings-sample.json` 执行）。
- **新增文档必须登记在本 README**，并写清基线日期与时效。
- 所有结论带 `文件:符号` 与带日期的 commit；无法从代码断定的事项写进「已知不确定项」，不写成结论。
