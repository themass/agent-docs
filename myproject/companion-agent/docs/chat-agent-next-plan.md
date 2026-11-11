# 架构回顾与下一步计划

日期：2026-11-11
范围：companion-agent 服务端（`main` 分支，`myproject/companion-agent`）与 agent 设计。Android 客户端只列与服务端相关的部分。

---

## 1. 已定的决策

| 决策 | 结论 | 来源 |
|---|---|---|
| 主脑 | **DeerFlow**（用户确认保持）；AgentScope v2 不再作为候选 | 2026-11-09 讨论 |
| 数据库 | **Postgres 替换 MySQL**；Redis 保留做控制面 | 2026-11-10 |
| 主动提醒 | 大脑用工具识别意图 → 用户确认 → Postgres 调度表 → `SKIP LOCKED` 多副本认领 → 走正常回合 → 推送；Hermes 不作大脑 | 2026-11-10 |
| 记忆 | 独立接口规范 `MemoryPort` + hook 插槽（recall / record / forget），后端可替换；不下载本地模型 | `chat-agent-memory-spec.md`、`chat-agent-memory-hooks.md` |
| 角色扮演提示词 | 按 SillyTavern 语义洁净室实现（只借设计，AGPL 代码不进服务端） | `chat-agent-harness-greenfield.md` 第 5 节 |
| 开发分支 | 后端在 `main` 上开发 | 2026-11-10 |

---

## 2. 目标架构

```
Android ──HTTP / SSE──▶ API（FastAPI，无状态，多副本）
                          │
   ┌──────── 会话层（我们自己的，已实现大部分）────────────┐
   │ 提交判定：开始 / 合并 / 插话 / 排队（Redis Lua）        │
   │ 会话锁 + 续期 + 围栏号（待补）；控制流；SSE 事件流与续传 │
   │ 确认表：工具确认 → 执行 → 新回合                       │
   │ 调度器：主动提醒到点入队（待做）                        │
   └───────────────┬────────────────────────────────────┘
                   │ 每回合
   ┌──────── 上下文组装（待做）─────────────────────────────┐
   │ 角色扮演提示词：角色卡、示例、按深度注入、世界书、作者注   │
   │ 记忆：会话前 recall（长期记忆 + 时间线）                  │
   │ 只组装 system 内容；对话历史由 checkpoint 提供             │
   └───────────────┬────────────────────────────────────┘
                   │ system_prompt + 本轮新消息
   ┌──────── 大脑：DeerFlow SDK 工厂 create_deerflow_agent ───┐
   │ checkpointer：AsyncPostgresSaver，thread_id = 会话 id     │
   │ 我们的中间件：Prompt、ToolVisibility、Steer、            │
   │   ToolAuthorization、ToolAudit                           │
   │ DeerFlow 中间件：Summarization（显式开启）、              │
   │   DanglingToolCall、ToolErrorHandling、LoopDetection、    │
   │   TokenBudget；Clarification 被过滤                       │
   └───────────────┬────────────────────────────────────┘
                   │ LiteLLM 网关（多模型）
   Postgres：业务表 + 消息表 + checkpoint 表 + 记忆 + 调度
   Redis：锁、控制流、SSE 事件流（可重建，不存权威数据）
后台 worker：摘要后处理、记忆抽取、提醒调度、过期确认、注销清理
```

### 2.1 为什么走 SDK 工厂，而不是 DeerFlow 网关

| | SDK 工厂（推荐） | DeerFlow 网关 |
|---|---|---|
| 提示词控制 | 系统提示词完全由我们给 | lead agent 固定「super agent」模板，人设被转义进 `<soul>` |
| 会话层 | 用我们已经做好、测过的那一套 | 它有自己的一套（运行输入、多任务策略），会和我们的重复 |
| 重量 | 只用图与中间件 | 约 20 个中间件 + 网关 6 万行 + 多项启动强制配置 |
| 代价 | 摘要要显式传入；需要的注入自己补 | 绕开模板与输入包装的工作量未知 |

### 2.2 消息的三份数据，各自的职责

| 数据 | 存储 | 职责 | 谁是权威 |
|---|---|---|---|
| 消息表（`chat_message`） | Postgres | 界面历史、原始存档、编辑与删除的依据 | **原始内容的权威** |
| checkpoint | Postgres（`AsyncPostgresSaver`） | 模型的工作上下文（最近消息 + `summary_text`） | **模型输入的权威** |
| Redis 事件流 | Redis | SSE 实时推送与续传 | 不是权威，可丢 |

对应关系：每条消息写入 checkpoint 时用**稳定 id**：`m{message_id}`。这样合并重跑、插话、删除、重新生成都能按 id 精确操作，而不是靠位置。

---

## 3. 现状对照

| 组件 | 现状 | 差距 |
|---|---|---|
| 会话层（提交、锁、合并、插话、排队、取消、SSE） | 已实现，线上 MySQL + Redis 测过 | 锁丢失后仍会写回复（缺围栏号） |
| 正式入口 `serve.py` | 不走 `build_platform`，默认 FakeBrain、内存存储 | 要接上新栈与真实 DeerFlow 大脑 |
| 大脑 | DeerFlow SDK 图 + 5 个中间件，工具经 ToolRuntime 路由 | **只发本轮一句话，没有历史**；没有 checkpointer；没有摘要 |
| 上下文组装 | 设计已写（`chat-agent-context-design.md`、`chat-agent-deerflow-message-flow.md`） | 未实现；需要按 2.2 的分工修订（历史交给 checkpoint） |
| 角色扮演提示词 | 角色卡 V2/V3 能加载；分层提示词有雏形 | 世界书、按深度注入、预算未实现 |
| 工具与确认 | 已实现：授权、确认、审计；副作用工具确认前不执行 | — |
| 记忆 | `MemoryPort` v1 + 一致性测试；MySQL 后端；词法召回 | hook 流水线未实现；新链路未接入召回；Postgres 后端待写 |
| 后台任务 | worker 只注册 2 种任务 | 记忆抽取、提醒、摘要后处理未注册 |
| 数据库 | MySQL 5.6（`ca_` 前缀，迁移 0001–0002） | 迁到 Postgres |
| 主动提醒 | 只有方案 | 全部待做 |
| Android | `agent-chat-client` 已改基于 `weifu-refactor`，编译通过，14 个单测通过 | 导航入口待批准；未推送 |

---

## 4. 需要先在原型里验证的点

DeerFlow 源码复核（`chat-agent-deerflow-message-flow.md`）留下的风险，都要在第 1 阶段用测试证实：

1. **合并重跑与 checkpoint**：首 token 前中止、带合并后的输入重跑时，上一次尝试已经写进 checkpoint 的用户消息会不会重复。预期：用稳定 id 后按 id 替换，不会重复。
2. **插话**：`SteerMiddleware` 注入的消息带稳定 id，能正确落进 checkpoint。
3. **取消**：取消后 checkpoint 里留下半截回复还是什么都没有；中断的回复如何标记。
4. **删除**：在会话锁内用 `aupdate_state` + `RemoveMessage(id)` 删除，模型下一轮确实看不到。
5. **摘要**：`DeerFlowSummarizationMiddleware` 在 SDK 路径显式开启后，按阈值把旧消息换成 `summary_text`，界面消息表不受影响。
6. **多副本**：两个进程交替处理同一会话，第二个进程从 Postgres checkpoint 接上上下文；checkpoint 只在持有会话锁时写入。
7. **DeerFlow 版本**：`deerflow-harness 2.3.0-dev` 来自本地 wheel，需要固定版本并记录来源。

---

## 5. 分阶段计划

### 阶段 0：收尾（约 1 天）

- 确认第 7 节的决策 1–3。
- 删除 `vendor/mem0/` 里遗留的 `.env.example`。
- 更新过时的文档：设计清单 2.8–2.10、T13 报告里的「接线未完成」。

### 阶段 1：DeerFlow + Postgres 原型（3–4 天）

- 本机起 Postgres；DeerFlow SDK 图接 `AsyncPostgresSaver`，`thread_id` = 会话 id。
- 消息写入 checkpoint 用稳定 id `m{message_id}`。
- 用脚本化模型跑完第 4 节 1–6 的验证，全部写成集成测试。
- 完成标志：多轮上下文可见；合并、插话、取消、删除、摘要、双进程的测试都通过。

### 阶段 2：迁移到 Postgres（约 1 周）

- 表结构移植：`ca_` 表 → Postgres，`MEDIUMTEXT` → `TEXT`、`JsonText` → `JSONB`；Alembic 新基线。
- 去掉 MySQL 5.6 的权宜做法：任务认领改用 `FOR UPDATE SKIP LOCKED`；时间戳不再截到秒。
- 记忆后端：Postgres 版 `MemoryPort`，通过一致性测试。
- 完成标志：全量测试在 Postgres + Redis 上通过；分层契约保持。

### 阶段 3：上下文与提示词（1–1.5 周）

- `serve.py` 改为通过 `build_platform` 启动，装配真实 DeerFlow 大脑（LiteLLM 模型）。
- 修复会话层围栏：锁续期失败立即停止产出，写回复带围栏号条件写。
- 角色扮演提示词第一版：角色卡字段、对话示例、按深度注入、世界书（主次关键词、常驻、插入位置与深度、顺序号、预算）；必需部分超预算直接报错，不截断人设。中文与阿拉伯语的匹配问题按 greenfield 文档 5.7 处理。
- 记忆 hook 流水线：回合前 recall（长期记忆 + 时间线），回合后 record（抽取写入）；后台任务化。
- 摘要：配置阈值；删除已被摘要覆盖的消息时的策略按第 7 节决策 3 实现。
- 完成标志：多轮角色扮演在测试中保持人设与情节；删除、编辑、重新生成的语义有测试。

### 阶段 4：主动提醒（约 1 周）

- 工具 `create_reminder(at, content, timezone)`，属于需确认的写操作。
- 调度表 `reminder`（到期时间、状态、租约）；worker 用 `SKIP LOCKED` 认领；崩溃后租约回收；`(reminder_id, occurrence)` 唯一去重。
- 到点生成一个主动回合，走正常回合路径；送达通过推送接口（客户端 FCM 后续接入）。
- 完成标志：双 worker 下提醒只发一次；用户可以查看、取消提醒。

### 阶段 5：真实模型与客户端联调

- 真实网关冒烟：千问、豆包、DeepSeek 的流式与工具调用兼容性（**需要你批准使用线上网关**），同时探测网关是否提供 embedding。
- Android 导航入口接入（**需要你批准**），端到端联调。
- 双实例压测。

### 后续

- 网关有 embedding 后：pgvector 语义召回。
- 换一个回答（swipe）与分支的界面与数据结构。
- 语音（LiveKit 调用同一套上下文组装 + 大脑）。
- 可观测性：回合级指标、上下文组装统计、摘要落后报警。

---

## 6. 风险

| 风险 | 应对 |
|---|---|
| DeerFlow 是开发版、变化快 | 固定版本与 wheel 来源；只用工厂与中间件接口；升级前跑全量测试 |
| checkpoint 写入没有租约检查 | 只在持有会话锁时写；补围栏号 |
| 角色扮演提示词工作量被低估 | 先写规格与真实角色卡测试用例；世界书分两期 |
| Postgres 迁移影响已有测试 | 阶段 2 单独做，完成前不改业务逻辑 |
| 网关没有 embedding | 先用摘要、世界书、词法召回三种不依赖 embedding 的记忆 |

---

## 7. 需要你决定的事

1. **大脑走 SDK 工厂**（推荐），还是 DeerFlow 网关？
2. **消息分工**：消息表管原始内容与界面，checkpoint 管模型上下文（推荐，见 2.2）。
3. **删除已被摘要覆盖的消息**：
   - 推荐：从消息表（排除已删除的）重新生成摘要，保证删掉的内容模型也看不到；
   - 或：接受摘要里仍保留它，只从后续上下文删除。
4. **记忆是否按角色隔离**（A 角色听到的事，B 角色是否知道）。
5. **是否做换一个回答（swipe）与分支**，决定消息表结构。
6. **世界书第一版范围**：推荐只做主次关键词、常驻、位置与深度、顺序号、预算。
7. **主动提醒先只做用户明确要求的提醒**（推荐），还是也做模型自己判断的主动联系。
8. **批准**：阶段 5 的线上网关冒烟与 embedding 探测。
