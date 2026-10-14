# AgentScope 主题地图与文档缺口

| 项 | 说明 |
|----|------|
| **文档类型** | 对照 `AGENTSCOPE.md` 总目录与仓库实现，标出「已有 / 薄弱 / 缺失」及应读材料 |
| **主规格** | [AGENTSCOPE.md](./AGENTSCOPE.md) — 仍是一文主读；本文 **不重复** 正文，只做索引与补洞指引 |
| **最后更新** | 2026-10-13 |

---

## 1. 你的问题：大纲里好像缺了什么？

`AGENTSCOPE.md` 总目录按 **Part** 组织（总览、内核、Memory、Middleware、App、Workspace、RAG、GoalPipeline、扩展、LTM），**并非**按 Harness 对比里的「Loop / 队列 / steer / Plan / Goal 产品族」组织。因此：

- 很多能力 **写在正文深处**（例如 App §4–§7 才有 wakeup / inbox），总目录 **一眼看不到**。
- 有些能力 **只有代码 + 测试**，主文档 **没有独立章节**（例如 `Task*` 规划工具、steer 语义）。
- 跨框架概念（steer、interjection、Plan mode）在 **[框架对比](../框架对比/framework-comparison/)**，**未**收进 `AGENTSCOPE.md`。

本文把常见主题 **摊开成表**，并列出建议补写优先级。

---

## 2. 主题速查表（你提到的 + 易漏的）

图例：**主文档** = `AGENTSCOPE.md`；**缺口** = 建议单独加深或新 Part。

| 主题 | 人话 | 主文档覆盖 | 实现位置（库） | 还应读 |
|------|------|------------|----------------|--------|
| **Loop / ReAct** | 单 Agent 内 model ↔ tool 直到终稿或 HITL 挂起 | ✅ [Part · 库内核 §4](./AGENTSCOPE.md#part-kernel) 流程图 + `_check_next_action` | `agent/_agent.py` `_reply_impl` | [03-runtime-loop-queue](../框架对比/framework-comparison/03-runtime-loop-queue.md) §3 A 柱 |
| **Goal（验收环）** | Executor + Verifier 外环，pass/fail 结构化停 | ✅ [Part · GoalPipeline](./AGENTSCOPE.md#part-pipeline) | `pipeline/_goal_pipeline.py` | [22-goal-mode §13](../框架对比/framework-comparison/22-goal-mode.md)（与 DSH/Cursor 等对比） |
| **Goal（产品语义）** | 会话级「接着干」、armed 续跑、slash `/goal` | ⚠️ 仅 GoalPipeline 旁注「与 Plan 产品语义不同」 | App 无统一 Goal 真源；各宿主自建 | [22-goal-mode](../框架对比/framework-comparison/22-goal-mode.md) 全文 |
| **Plan / 任务板** | `TaskCreate` / `TaskList` / `tasks_context` 待办 | ⚠️ 内核表提到 `tasks`；**无** Plan 专章 | `tool/_task/*`；`state.tasks_context`；App `get_toolkit` 注册 | [05-plan-mode](../框架对比/framework-comparison/05-plan-mode.md)（OpenHarness 等）；注入见 `_inject_runtime_state` 的 `<tasks>` |
| **多 Agent（库内）** | 单进程 Leader 委派 | ✅ [扩展 §2 TeamPipeline](./AGENTSCOPE.md#part-extensions) | `pipeline/_team_pipeline.py` | — |
| **多 Agent（生产）** | 多 Session、TeamSay、子 Agent 工具 | ✅ [Part · App §7](./AGENTSCOPE.md#part-app) + 扩展选型表 | `app/_tool/_agent_create.py` 等 | — |
| **SOP** | 多里程碑、每步 executor/verifier、跨天 resume | ✅ [扩展 §3 SOP](./AGENTSCOPE.md#part-extensions) | `sop/_engine.py`；`app/middleware/_sop_step_middleware.py` | — |
| **队列（App）** | wakeup 队列、谁 spawn run、409 防重 | ✅ App §4–§5、MessageBus 键表 | `message_bus/`；`_manager/_wakeup_dispatcher.py`；`ChatRunRegistry` | [03-runtime](../框架对比/framework-comparison/03-runtime-loop-queue.md) §4 控制面 |
| **inbox** | Session 忙时先排队 Hint，不杀当前 run | ✅ App + Middleware `InboxMiddleware` | `app/middleware/_inbox_middleware.py` | [14-loop-interjection](../框架对比/framework-comparison/14-loop-interjection.md) |
| **steer / 插队** | 运行中用户改口、注入新指令 | ❌ **无** AgentScope 一等 API 专章 | 忙时 ≈ **inbox**；真 steer 各宿主不同 | [14-loop-interjection](../框架对比/framework-comparison/14-loop-interjection.md)；对比 DSH/Codex |
| **interrupt** | Ctrl+C、`UserInterruptEvent`、取消 run | ⚠️ 分散在 GoalPipeline / Team / console | `agent/_agent.py`；`SessionService` cancel | App `CancelDispatcher` |
| **observe** | 只写入 context、不跑 ReAct | ✅ Memory §6.2.2 | `agent.observe` | — |
| **HintBlock** | 动态提醒，Formatter → user | ✅ [§13.8–13.9](./AGENTSCOPE.md#hintblock-生产者与送模) | `message/_block.py`；`_inject_runtime_state` | [REME §9](./REME_ARCHITECTURE.md) |
| **ReMe / LTM** | 跨会话记忆 | ✅ [REME_ARCHITECTURE](./REME_ARCHITECTURE.md)；Middleware 章 | `middleware/_longterm_memory/` | QwenPaw：[REME §9.2](./REME_ARCHITECTURE.md#92-qwenpaw-集成memorymiddleware--reme-light非-rememiddleware) |
| **RAG** | 知识库检索 Middleware | ✅ [Part · RAG](./AGENTSCOPE.md#part-rag) | `rag/`；`middleware/_rag.py` | — |
| **权限 / HITL** | ALLOW / ASK / DENY、外部执行 | ✅ 库内核 §6 | `permission/`；`RequireUserConfirmEvent` | — |
| **并发 tool** | 一轮多个 tool_call 并行执行 | ❌ 主文档未单列 | `agent/_agent.py` `_execute_tool_calls` + 内部 `Queue` | 读源码 + `agent_interrupt_test` |
| **Background tool** | 慢工具后台跑、inbox 通知 | ⚠️ Middleware 表一行 | `app/middleware/_tool_offload_middleware.py` | — |
| **调度 / Cron** | 定时任务 → inbox + wakeup | ✅ App §8 _scheduler | `app/_manager/_scheduler/` | — |
| **Realtime 语音** | 双向音频 Agent | ⚠️ 扩展 §语音一句 | `agent/_realtime/`；`realtime/` | `_archive/REALTIME_*` |
| **WebRTC** | App 侧实时会话 | ❌ 主文档几乎无 | `app/_service/_webrtc_session.py` | 需补 Part 或 ARCHIVE |
| **Model Router** | 多模型路由中间件 | ❌ | `middleware/_model_router.py` | — |
| **Budget** | 预算/用量 Hint | ❌ | `middleware/_budget.py` | — |
| **Tracing** | OTel | ⚠️ Middleware 目录表 | `middleware/_tracing/` | — |
| **Classifier** | 评测/分类模型 | ❌ | `classifier/` | — |
| **A2A** | 远程 Agent 客户端 | ✅ 扩展 § | `a2a/`（若在包内） | 扩展模块表 |
| **AG-UI** | 前端协议中间件 | ❌ | `app/middleware` AG-UI 相关 | — |
| **Access 多租户** | 跨用户 Agent/Session 可见性 | ⚠️ App 模块地图一行 | `app/access/` | — |
| **已删除 v0** | MsgHub、FanoutPipeline、memory 包 | ✅ 内核 §3 脚注 | — | `_archive/` |

---

## 3. 按「Harness 五平面」归类（和 monorepo 对比文档对齐）

读 [00-HARNESS-DESIGN-PHILOSOPHY](../框架对比/framework-comparison/00-HARNESS-DESIGN-PHILOSOPHY.md) 时，AgentScope 文档分布如下：

| 平面 | AgentScope 载体 | 主文档 Part |
|------|-----------------|-------------|
| **A Loop 驱动** | `Agent._reply_impl` ReAct | 库内核 §4 |
| **B 多 Agent** | TeamPipeline / App Team / SOP / A2A | GoalPipeline + 扩展 + App §7 |
| **C 执行环境** | `workspace` + App `WorkspaceManager` | Workspace + App |
| **D HITL** | Permission + parked tool + wakeup resume | 库 §6 + App §4 |
| **E 权限** | `PermissionEngine` + `PermissionContext` | 库 §6 |
| **控制面队列** | `wakeup_queue` + `session_lock` + inbox | App §4–§5（**总目录未单独列「队列」**） |
| **L3 压缩** | `compress_context` + Offloader | Memory §9、§15 |
| **插队 L1** | inbox（非 steer 同名 API） | App + InboxMiddleware |

---

## 4. Plan vs Goal vs Task*（避免混名）

```text
Task* 工具（TaskCreate/List/…）  →  AgentState.tasks_context 上的「待办板」
                                 →  _inject_runtime_state 可提醒「还有 pending 任务」
                                 →  不是 GoalPipeline，也不是 Harness 文档里的「Goal 模式」

GoalPipeline                    →  库内双 Agent 验收环（executor + verifier）

产品 Goal（22-goal-mode）        →  会话外环、续跑、armed；AgentScope App 无统一实现
                                 →  对比文见 framework-comparison/22-goal-mode.md
```

**文档缺口**：`AGENTSCOPE.md` **缺少**「App 规划工具与 `tasks_context`」专节（建议未来 **库内核 §6 附录** 或 **App §Toolkit**）。

---

## 5. Queue / steer / loop — 在 AgentScope 里具体指什么

### 5.1 Loop

- **就是** 库内核 ReAct：`reasoning` →（可选）`acting` → `cur_iter++`，直到 `ReplyEnd` 或 HITL **exit**。
- **不是** LangGraph 节点图；**不是** DSH 的 `turn/step` event log（无 session event 真源）。

### 5.2 Queue（有）

| 队列 | 作用 |
|------|------|
| **`wakeup_queue`** | 统一触发 `ChatService.run`（新消息 / resume / wake drain inbox） |
| **`inbox(session_id)`** | 跨 turn 投递 `HintBlock`（TeamSay、调度、channel 忙时） |
| **并发 tool 内部 `asyncio.Queue`** | 单 Agent 一轮多 tool 并行时收事件（**实现细节**，无产品文档） |
| **`ChatRunRegistry`** | 同 session 同时只一个 run（409） |

### 5.3 Steer（弱 / 间接）

AgentScope **没有** 名为 `steer` 的 API。接近语义的行为：

| 行为 | 机制 |
|------|------|
| Session **忙** 时再发用户消息 | Channel → **inbox**，当前 run 继续，下轮或 wake 后注入 |
| **打断** | `UserInterruptEvent` / cancel API（SessionService） |
| **运行中改模型输入** | 仅 Middleware `on_model_call` 改 **当次** messages（QwenPaw 记忆即此类） |
| **真·steer**（合并进当前 turn 的 user 指令） | **未** 作为库级标准；见 [14-loop-interjection](../框架对比/framework-comparison/14-loop-interjection.md) 各 Harness |

---

## 6. `AGENTSCOPE.md` 建议增补的 Part（优先级）

| 优先级 | 建议章节 | 内容要点 |
|--------|----------|----------|
| P0 | **总目录增加「主题地图」链** | 指向本文 |
| P0 | **模块架构全集** | [MODULE_ARCHITECTURE_ATLAS.md](./MODULE_ARCHITECTURE_ATLAS.md)（§0 清单 + 设计/时序图，含 MessageBus §C4）；[ARCHITECTURE_DIAGRAMS.md](./ARCHITECTURE_DIAGRAMS.md) 速览 |
| P1 | **运行时控制面**（或 App 子章） | 图集 [§7](./ARCHITECTURE_DIAGRAMS.md#module-app-control)；正文仍待扩写 wakeup / inbox / 409 表 |
| P1 | **Plan 与 Task\*** | `tasks_context`、Task 工具、与 GoalPipeline / 产品 Goal 分界 |
| P2 | **Steer 与 interrupt** | 明确 AgentScope 支持边界 + 指向 framework-comparison §14 |
| P2 | **并发 acting** | 多 tool 并行、与串行 HITL 的关系 |
| P3 | **Realtime / WebRTC** | 从 archive 拉回或新建短 Part |
| P3 | **ModelRouter / Budget / Classifier** | 中间件级能力一页表 |

---

## 7. 仓库内其他必读（不在 `docs/agentscope/`）

| 路径 | 用途 |
|------|------|
| [framework-comparison/](../框架对比/framework-comparison/) | Loop、队列、Plan、Goal、Session 六族、steer |
| [22-goal-mode.md](../框架对比/framework-comparison/22-goal-mode.md) | Goal 模式横评（含 AgentScope GoalPipeline §13） |
| [21-session-message-architecture.md](../框架对比/framework-comparison/21-session-message-architecture.md) | 快照 vs event 真源（Memory §8.5 已链） |
| [REME_ARCHITECTURE.md](./REME_ARCHITECTURE.md) | ReMe + QwenPaw 集成 |
| `agentscope/tests/service_*` | App Team、inbox、scheduler 行为契约 |
| [QwenPaw memory 文档](https://github.com/agentscope-ai/QwenPaw)（若用宿主） | `website/public/docs/memory.*` |

---

## 8. 与 `AGENTSCOPE.md` 总目录的对照（现有 Part 已含什么）

| 总目录 Part | 已覆盖你关心的 |
|-------------|----------------|
| 库内核 | **Loop**（§4）、Tool、Permission、Model |
| Memory | Session 快照、投影、Hint、压缩 |
| Middleware | Inbox（表）、RAG、LTM、TTS… |
| App | **队列**、Team、Channel、Scheduler、SSE |
| GoalPipeline | **Goal（验收环）** |
| 扩展 | **多 Agent**（TeamPipeline、SOP、A2A）、语音、console |
| Agent 边界 | 子 Agent 工具指针、无 children |

**总目录未单独列出**：Plan/Task*、steer、并发 tool、WebRTC、ModelRouter、AG-UI、Classifier。

---

## 9. 维护说明

- 新增 `agentscope/src` 一级包或 App 子系统时，先更新 **§2 速查表** 与 **§6 优先级**。
- 若某主题在 `AGENTSCOPE.md` 写了完整 Part，可从本文 **降级为一句链接**，避免双份维护。
