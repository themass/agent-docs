# DeerFlow 消息链路规格：模型输入、界面消息、压缩、删除

日期：2026-11-09
状态：源码复核结果（DeerFlow 检出 `235b5556e`，harness `2.3.0-dev`）+ 我们现状核实。未实现。
目的：回答「模型看到什么、界面看到什么、压缩后怎么办、删除后怎么办」，并列出必须我们自己决定的点。

标记：`(推断)` = 依赖 LangGraph / LangChain 源码，不在本仓库内，未直接核实。

---

## 0. 先说结论

DeerFlow 把数据分成三份，各管一件事：

| 数据 | 存在哪 | 谁读 | 作用 |
|---|---|---|---|
| **checkpoint**（图状态，含 `messages`、`summary_text`） | `checkpoints` / `checkpoint_blobs` / `checkpoint_writes`（postgres / sqlite / memory） | 模型调用、重新生成、分叉 | **模型的记忆**，是模型输入的权威 |
| **run_events**（每个事件一行，`seq` 递增） | 表 `run_events`（db）/ jsonl / memory | 界面历史接口 | **界面的权威** |
| **runs**（运行元数据、租约、所有权） | 表 `runs` | 调度、恢复、并发控制 | 多实例安全 |

**压缩只改 checkpoint，不改 run_events。** 所以界面历史永远完整，模型的上下文被压缩。

我们现在的情况是：只有一份 MySQL 消息表（`ca_chat_message`），界面读它，**模型不读它**（模型只拿到本轮一句话）。这正是上下文断裂的根因。

---

## 1. 我们现状（已核实）

| 项目 | 现状 | 出处 |
|---|---|---|
| 界面消息 | MySQL `ca_chat_message`，`GET` 历史接口直接读 | `api/http/routers/chat.py:158` |
| 模型输入 | 只有本轮用户输入一条 `HumanMessage` | `adapters/brain/deerflow.py` `start_turn` |
| 历史进入模型 | **没有**。`select_window` 存在但无调用方 | `domain/history/window.py` |
| 上下文压缩 | **没有**。唯一的 summary 字样是工具确认卡片标题 | `app/tools/runtime.py:30, 168` |
| 删除消息 | 软删（`deleted=1`），只影响界面列表 | `adapters/store/mysql/repositories.py:159` |
| 重试 / 继续 | 从回合里取用户输入重跑，不读历史 | `chat.py:245` |
| 记忆 | MySQL `ca_memory_item`；召回中间件只在旧组合根 `container.py:73` 接入，新平台链路未接入 | `adapters/store/mysql/memory.py` |
| 会话摘要 | 设计已写（`chat-agent-context-design.md`），未实现 | — |

---

## 2. DeerFlow：一次运行的请求路径

```
POST /threads/{id}/runs/stream                       thread_runs.py:1069
  └ start_run                                        services.py:2154
      ├ normalize_input / 补消息 id                  services.py:2277, 2297
      ├ 可能追加隐藏的「只读对话引用」HumanMessage    services.py:2483
      └ run_agent(graph_input, config)               worker.py:996
          └ agent.astream({"messages": [新消息]}, config)   worker.py:1596
              LangGraph 先加载该 thread 的最新 checkpoint，
              再把输入经 reducer 合并进 state（推断）
              └ model 节点：中间件链 wrap_model_call → 模型
```

- **请求体只带新消息**。历史不由网关拼接，而是 LangGraph 从 checkpoint 恢复。
- 指定旧 checkpoint 时（重新生成、编辑重生成），先用 `apply_checkpoint_to_run_config`（`services.py:1844`）切换，必要时整理 checkpoint 头（`worker.py:1486–1546`）。
- `ThreadState`（`agents/thread_state.py:379`）的关键字段：`messages`、`summary_text`（`:397`）、待办、目标等。

---

## 3. 模型实际收到的消息（组装顺序）

### 3.1 checkpoint 里的消息

- 从上次压缩之后、该 thread 的全部消息。**没有固定窗口**，窗口由压缩决定。
- reducer 按 id 追加、按 id 替换、支持 `RemoveMessage` 与 `REMOVE_ALL_MESSAGES`（`thread_state.py:431–485`，delta 模式下的 `merge_message_writes`）。

### 3.2 请求时才注入、不保存的消息（`wrap_model_call` 里 `request.override(messages=...)`）

| 注入物 | 类型 | 文件 | 持久化 |
|---|---|---|---|
| 持久的 system 提示词 | `SystemMessage` | lead_agent | 否 |
| 运行时提醒（日期、记忆块、用户副本） | `SystemMessage` / `HumanMessage` | `dynamic_context_middleware.py:506–620` | **是**（在 `before_agent` 写入 state） |
| 项目、客户端上下文、语言偏好 | `HumanMessage`（`hide_from_ui`） | `dynamic_context_middleware.py:734–805` | 否 |
| 持久上下文（授权契约 + 数据块：摘要、委派、skill、目标） | `SystemMessage` + `HumanMessage` | `durable_context_middleware.py:400–451`，渲染 `:98–125` | 否 |
| 待办提醒 | `HumanMessage` | `todo_middleware.py:146` | 是（在 state 中） |
| 运行输入相关 | 多种 | `run_input_middleware.py` | 视情况 |

**插入位置**：`insert_after_leading_system_messages`（`message_utils.py`）把注入物放在系统消息之后、对话之前。注入顺序由中间件外层到内层决定，后插入的落在前面（推断）。

**结果的近似顺序**：系统提示词 → 持久上下文（授权契约、摘要、目标）→ 语言与客户端块 → 项目块 → state 里的消息（含已持久化的提醒，尾部是最新用户消息）。

### 3.3 我们需要的形态（与 DeerFlow 对齐）

- system 内容（角色、世界书、作者注、人设）走系统消息，每轮重算。
- 摘要走持久上下文，不作为假消息（DeerFlow 的 `name="summary"` 做法在它自己的过滤里有特殊处理，我们不要模仿）。
- 历史由 checkpoint 提供；我们不要再从 MySQL 拼一份历史。

---

## 4. 界面消息从哪里来

- 历史接口读 `run_events`：`GET /threads/{id}/messages`（`thread_runs.py:1546`）、`/messages/page`（`:1686`）、`/runs/{run_id}/messages`（`:1714`）。
- 写入方是 `RunJournal`（`runtime/journal.py:298`）：助手回复记为 `llm.ai.response`（`:591`），人类输入按规则记录（`:146`）。
- 旧线程若 `run_events` 为空，从 checkpoint 头回填一次（`services.py:1903–1963`）。
- 隐藏规则：`_is_hidden_or_control_message`（`thread_runs.py:524`）隐藏 `type=remove`、`name=summary`、`hide_from_ui` 的消息。
- **界面与模型不做逐行对账**。两者各自是自己的权威。

---

## 5. 压缩（summarization）

### 5.1 触发

- `DeerFlowSummarizationMiddleware`（`summarization_middleware.py:123`），在 `before_model` 检查（`:746`，`:988`）。
- 阈值三种：`fraction`（占模型窗口的比例）、`tokens`、`messages`（`summarization_config.py:18`）。默认关闭（`:60`）。
- 计数时用一条只用于计数的摘要消息，不持久化（`:563–566`）。

### 5.2 保留什么

- 默认保留最后 20 条消息（`DEFAULT_KEEP = ("messages", 20)`）。
- 最新一条真实用户消息永远保留（`:786–790`）。
- 系统消息、标记为动态上下文的提醒、当前用户请求不参与摘要（`_preserve_required_context`，`:1014–1047`）。
- 待办提醒在切分前排除（`:762–770`）。

### 5.3 写回

```
return {
  "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *preserved],
  "summary_text": summary,
}
```
（`summarization_middleware.py:988–1002`）

- checkpoint 的消息列表被整体覆盖。**旧 checkpoint 仍在**，历史可回溯。
- 摘要文本在 `summary_text` 通道，不是消息（`thread_state.py:397`）。
- 摘要通过持久上下文的数据块回到提示词（`durable_context_middleware.py:98–125`，标题「Conversation summary so far」）。
- **界面不受影响**：压缩路径不调用事件存储（`:884–935`）。

### 5.4 手动压缩

`POST /threads/{id}/compact`（`threads.py:1558`）→ `compact_thread_context`（`runtime/context_compaction.py`），写一个新 checkpoint。运行中调用返回 409。

### 5.5 摘要的版本

没有显式的「摘要版本号」。摘要绑定在它所在的 checkpoint 上，checkpoint 谱系就是版本（推断）。

---

## 6. 删除、编辑、重新生成（压缩之后）

DeerFlow **没有就地删除或编辑消息**的接口。能改变历史的只有：

| 操作 | 接口 | 对 checkpoint | 对 run_events | 对摘要 |
|---|---|---|---|---|
| 压缩 | `/compact` | 写新 checkpoint（覆盖消息） | 不动 | 更新 `summary_text` |
| 编辑后重新生成 | `/runs/edit-regenerate/prepare`（`thread_runs.py:1040`） | 从源用户消息之前的 checkpoint 分叉 | 不删，旧运行在界面隐藏（`default_history_hidden_run_ids`） | 随分叉点的 checkpoint 带回旧摘要（推断） |
| 重新生成 | `/runs/regenerate/prepare`（`:1029`） | 同上 | 同上 | 同上 |
| 删除线程 | `DELETE /threads/{id}` | 删 | 删 | 删 |
| 撤回排队输入 | `DELETE .../inputs/{id}` | — | — | — |

**关键的后果**：
- 编辑一条**已经被压缩进摘要的**旧消息，分叉点会回到更早的 checkpoint，那里的摘要还是旧的，也就是说摘要不会因编辑而失效，而是随分叉回退。这在对话连续性上是合理的（新分支从自己的历史出发），但意味着**我们不能指望「删一条消息，摘要自动修正」**。
- 我们的设计（`chat-agent-context-design.md` §8）要求「编辑已被摘要覆盖的消息 → 标记摘要失效 → 重建」。DeerFlow 的做法是分叉回退。两种都可以，但**要二选一**，不能混用。

### 6.1 谱系

- `checkpoint_id` 在 `_checkpoint_response`（`thread_runs.py:567`）。
- 父子关系：`history_parent_index`（`checkpoint_lineage.py:254`）、`parent_from_history_index`（`:266`）。
- 找「某条消息之前的 checkpoint」：沿父链走；父链缺失时按时间回退（`:428`）；不安全的谱系返回 409（`thread_runs.py:741–750`）。

---

## 7. 多实例安全

已有的保护：
- **运行准入**：`runs` 表上的线程操作约束，默认 `reject`（`manager.py:2365–2377`，`persistence/run/model.py:28`）。两个实例不会同时跑同一线程。
- **运行所有权**：`runs` 行上的租约（`owner_worker_id`、`lease_expires_at`，`run/model.py:58–59`）；状态更新带所有者与租约条件（`sql.py:472–474, 671`）。
- **检查点的外部写入**（compact、state）：`reserve_checkpoint_write`（`services.py:142–158`）。
- **run_events 序号**：Postgres 用线程级 advisory 锁，加 `(thread_id, seq)` 唯一约束（`events/store/db.py:164–188, 223–257`）。

**已知缺口**（DeerFlow 自己在代码里承认的）：
- 线程内的 checkpoint 锁、目标锁是进程内 asyncio 锁（`worker.py:285`，`runtime/goal.py:84`），不跨进程。
- SQLite 的 run_events 没有跨进程围栏（`db.py:186–188`）。**我们用 Postgres，不受影响**。
- run_events 的生产者围栏默认关闭（`run_events_config.py:24`）。租约过期后旧 worker 仍可能写事件；只有 Postgres 的 strict 模式会拒绝（`db.py:223–257`）。**需要确认我们启用 strict。**
- 在 `worker.py` 里没找到每次 checkpoint 写入前的租约检查（推断：不存在）。租约丢失后，旧 worker 可能继续写 checkpoint，直到它自己察觉。

---

## 8. 我们要自己定的事

DeerFlow 的模型是「checkpoint 管模型、run_events 管界面」。我们之前的设计是「MySQL 是唯一权威、每回合无状态重建上下文」。**两者冲突，必须二选一。**

### 方案 A：采用 DeerFlow 的模型（推荐）

- 模型历史 = checkpoint（Postgres）。摘要、重新生成、分叉、多实例的正确性全部由它提供。
- 界面历史 = run_events（Postgres）。
- 我们的业务数据（角色、用户、会话列表、记忆）仍放 MySQL 或 Postgres 均可。
- 代价：我们的消息结构（候选回复、分支、隐藏）要映射到 run_events 与 checkpoint 的结构上；Swipe 要靠分叉实现，不是「同位置多候选」。

### 方案 B：保留我们的模型（MySQL 权威）

- 每回合从 MySQL 构造 `messages` 发给 DeerFlow，checkpointer 关掉（或只做短期缓存）。
- 摘要、分支、候选回复全部自己做。
- 代价：DeerFlow 的压缩、重新生成、多实例保护都要绕开或重写；与 DeerFlow 的 `ThreadState` 中间件（摘要、持久上下文、待办）大量冲突。

**建议方案 A。** 理由：它把「模型记忆」「界面历史」「并发安全」三件事都交给经过多实例验证的机制。我们的 MySQL 留给业务数据即可。

### 其他需要决定的

1. **接入方式**：我们是直接用 SDK 工厂 `create_deerflow_agent`（当前做法），还是通过网关（`/threads/...` 的 HTTP API）调用？网关路径带 20 个中间件，包括日期、记忆、项目、客户端上下文注入，但也更重、更任务导向；SDK 路径干净，但这些注入要我们自己补。
2. **界面接口**：我们的 `/api/agent/v1` 是否直接透传 DeerFlow 网关的 run_events 接口，还是我们自己在 Postgres 上做一层投影？
3. **摘要的编辑策略**：分叉回退（DeerFlow 做法）还是摘要失效重建（我们之前的设计）？建议分叉回退，实现最少，且与 DeerFlow 一致。
4. **run_events 严格模式**：是否启用 Postgres 的 strict 生产者围栏。建议启用。

---

## 9. 与 SDK 路径的差距（当前 `DeerFlowBrain` 使用的路径）

SDK 工厂不包含网关 lead agent 的以下中间件：日期与记忆注入（DynamicContext）、客户端与语言块、skill 激活、延迟工具、MCP 路由、输入消毒、工具输出预算、LLM 错误处理、工具回执、产物捕获、只读检查、终止响应、长度与安全结束原因处理、token 统计、运行输入准入。

SDK 工厂**包含**：ThreadData、Uploads、Sandbox、DanglingToolCall、Guardrail、ToolErrorHandling、PiiRedaction、DurableContext、SystemMessageCoalescing、Summarization（需显式传入）、Todo、Title、Memory、ViewImage、SubagentLimit、LoopDetection、TokenBudget、ModelContentCompatibility、Clarification。

**含义**：如果保留 SDK 路径，就要自己补上需要的注入（通常是 `wrap_model_call` 里覆盖 `request.messages`），并显式提供摘要中间件。若选网关路径，这些已经有了，但要接受它的任务型提示词与更重的依赖。

---

## 10. 未核实的点（需要在原型里验证）

- LangGraph 的 checkpoint 读写细节（标注为推断的几处）。
- 摘要分叉后的摘要版本行为。
- `DynamicContext` 写入 state 的提醒，在分叉后是否会重复。
- 网关路径中，把发给模型的系统提示词整份替换为我们的组装结果，是否仍保留运行输入、调度、流桥接（这是第 4.5 节的验证项）。
