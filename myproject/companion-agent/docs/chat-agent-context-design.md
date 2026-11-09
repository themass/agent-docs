# 对话上下文设计：多副本、会话漂移、长上下文与遗忘

版本：草案 v1（2026-11-09）
状态：设计，未实现
配套：`chat-agent-prompt-skill-design.md` §2.3、§6.1、§6.6（无状态回合与历史窗口）；`chat-agent-design.md` §6（回合控制）、§8.1；`chat-agent-ops-design.md` §2（后台任务）、§10（数据保留）；`chat-agent-memory-hooks.md`（长期记忆）。

## 0. 现状

核实于当前代码：

- `DeerFlowBrain.start_turn` 只把本轮用户输入作为一条 `HumanMessage` 交给图，**历史没有传**，多轮上下文是断的。
- `domain/history/window.py::select_window` 存在，但没有调用方，也没有按回合分组。
- 图上没有 checkpointer；`config/deerflow/config.yaml` 里的 sqlite checkpointer 已删除（多副本不用 sqlite）。
- 没有会话摘要。原设计把「摘要」列为定时任务（A：不在请求路径上生成摘要），但只设计了跨会话的记忆摘要，没有设计**单个会话内**的摘要。

结论：长会话目前不是「会遗忘」，而是「每一轮都没有记忆」。本设计补齐这一层。

## 1. 原则

1. **回合无状态**。任何一台服务器都能处理任何一个回合；上下文每一轮从持久化存储重建，进程内不保存会话状态。
2. **MySQL 是唯一权威**。消息、摘要都在 MySQL；Redis 只负责回合控制与事件流（锁、控制流、SSE 事件），丢了可以重建，不存权威数据。
3. **摘要不进请求路径**。回合不等待摘要生成；摘要由后台任务异步产出，回合只读取「已有的最新摘要」。
4. **遗忘是可控的、可解释的**。哪些内容会被压缩、哪些会被丢弃，规则写死在本文；任何丢弃都有日志与指标。
5. **三层上下文各管一件事**：最近窗口（原文）、会话摘要（本会话的叙事）、长期记忆（跨会话的用户事实）。

## 2. 存储选型：消息适合放 MySQL 吗

适合，理由与边界如下。

| 访问模式 | MySQL 中的形态 | 成本 |
|---|---|---|
| 写：每回合 1 条用户消息 + 1 条助手消息（合并/插话时多条用户消息） | 追加写 `ca_chat_message` | 主键自增，顺序写 |
| 读：每回合取最近窗口 | `WHERE session_id=? AND deleted=0 AND id>? ORDER BY id DESC LIMIT 60`，命中已有索引 `ca_ix_message_session_deleted_id` | 一次索引范围扫描，≤ 60 行 |
| 读：客户端翻历史 | `list_before`，同一索引 | 同上 |
| 后台：摘要任务读一段区间 | `id > from AND id <= to`，同一索引 | 离线，不影响回合 |

不选其他方案的原因：

- **Redis 做权威存储**：共享实例，有淘汰策略，持久化不可依赖；消息必须真删、可审计、可回溯，Redis 都不擅长。Redis 只适合做可丢弃的缓存（见 §4.4）。
- **sqlite**：单机文件，多副本下不可用。
- **DeerFlow checkpointer**：把历史存进图状态，删除、编辑、审计都绕过了我们的表，而且需要共享的 checkpoint 存储（又是一套数据）。设计已决定不用。

规模上的边界：消息表随时间单调增长，单会话的读只看最近一段，增长不影响回合延迟。表总量大了以后，按保留策略（O §10）物理删除软删数据；更长期可以按 `created_at` 归档冷数据，这不改变本设计。

## 3. 三层上下文

```
system message
  [1]–[6] 平台、角色、方法、任务、输出、用户层（P §6.1，≤ 3500 token）
  [6.5] 会话摘要块 <session_summary>（≤ 600 token，数据，不是指令）
messages
  [7] 角色示例
  [8] 最近窗口：摘要截止点之后的原文消息，按回合分组（≤ 6000 token）
  [9] 当前输入（含合并/插话）
```

### 3.1 最近窗口（原文）

- 起点：会话摘要的截止消息 `upto_message_id` 之后（没有摘要则从会话开始）。
- **只取已完成的回合**：消息必须挂在一个已结束的回合上（`turn_id` 非空，且该回合不是当前回合）。两类消息必须排除：
  - `turn_id` 为空的用户消息：它们在队列里，属于未来的回合；把它们放进历史，模型会回答还没轮到的问题；
  - 当前回合的用户消息：`attach_turn` 已经在模型调用前把它们挂到当前回合，它们通过 [9] 当前输入传入，再进窗口就重复了。
- 截断单位是**回合**：一个回合 = 它覆盖的全部用户消息 + 它的助手回复，按 `turn_id` 分组，不截半个回合（P §6.6）。
- 预算：目标 6000 token 或 30 个回合，从最新往前取；摘要落后时可扩到硬上限 9000 token 或 45 个回合（§5.3）。
- 不进窗口的：工具调用中间过程、`interrupted=1` 且内容为空的助手消息、`deleted=1` 的消息。
- `interrupted=1` 但有内容的助手消息进窗口，并在末尾附「（回复被中断）」，让模型知道上一句没说完。

### 3.2 会话摘要（本会话的叙事）

解决「窗口装不下的那部分」。

- 内容：本会话里已经超出窗口的部分，压成一段叙述：发生过什么、用户提过的计划与承诺、未解决的话题、角色扮演中的剧情状态与设定。
- 形态：一段纯文本，按会话语言写，第三人称中性叙述。
- 位置：system message 的数据块 `<session_summary>`，放在用户层之后、历史之前。它在两次摘要更新之间不变，因此不会破坏 prompt 缓存的前缀。
- 预算：≤ 600 token。超出时摘要任务自己重写压缩，回合侧不截断。
- 增量：新摘要 = 摘要模型（上一版摘要 + 新落出窗口的回合）。每一版记录它覆盖到哪一条消息。

### 3.3 长期记忆（跨会话的用户事实）

由 `memory_hub` 负责（`chat-agent-memory-hooks.md`），本设计只约定分工：

| | 会话摘要 | 长期记忆 |
|---|---|---|
| 范围 | 一个会话 | 一个用户的所有会话（同一应用内） |
| 内容 | 叙事、剧情、本会话的话题与约定 | 稳定事实、偏好、重要事件 |
| 删除会话后 | 一起删除 | 保留（用户在记忆页单独删） |
| 进提示词 | `<session_summary>` | 用户层记忆块 |

摘要任务可以顺带把识别出的用户事实交给记忆写入组件（`Recorder`），但两者写入不同的存储，互不覆盖。

## 4. 多副本与会话漂移

### 4.1 已有的保证

- **单会话串行**：Redis 运行锁 `ca:sess:{sid}:lock`（SET NX PX 30000，每 10 秒续期）保证同一时刻一个会话只有一个回合在跑，不管在哪台服务器上。
- **事件流在 Redis**：SSE 事件写入 `ca:sess:{sid}:events`，客户端断线重连到任何一台服务器都能续传。

### 4.2 本设计新增的要求

1. **读己之写**：用户消息在回合开始前写入 MySQL；助手消息在回合结束、**释放锁之前**写入。因此下一个回合（无论在哪台机器）一定能读到上一回合的完整结果。现有 `_finish` 的顺序已满足（先 `append`，后 `release_lock`），实现时保持这个顺序并加测试守住。
2. **读主库**：如果以后为 MySQL 加只读副本，回合构建上下文必须读主库。副本延迟会让刚写入的上一轮回复「消失」。
3. **进程内不缓存会话状态**：窗口、摘要都每轮读取。允许的缓存只有 §4.4 那种「带版本号、可丢弃」的形式。
4. **锁丢失要停止写入（围栏）**：核实现状：续期失败时 `turn_runner._renew` 记日志 `lock lost` 并设置 `stop`，但 `stop` 只停掉续期与控制监听两个协程；`_attempt` 里的模型流不检查它，会继续产出，`_finish` 仍然写入助手消息。锁过期后另一台机器可能已经开了新回合，于是同一会话出现两条并行的助手回复，下一轮的窗口也会读到错乱的顺序。补充：
   - 加锁时拿到一个单调递增的**围栏号**（Redis `INCR ca:sess:{sid}:fence`），随回合传递。
   - 续期失败即设置「已失去所有权」（`_RunState.lost`），`_attempt` 在每个事件处检查并立即退出；`_finish` 不再写助手消息，按中断处理并发布 `error`（`code=turn_failed`）。
   - 写助手消息时带上围栏号，仓储层用条件写（围栏号不小于会话当前记录的围栏号）拒绝过期的写。会话表加一列 `fence`。

### 4.3 漂移场景逐一核对

| 场景 | 结果 |
|---|---|
| 连续两轮落在不同服务器 | 第二轮从 MySQL 重建上下文，与同一台机器一致 |
| 回合进行中服务器宕机 | 锁 30 秒后过期；用户消息已落库，下一轮可见；未完成的助手消息不落库（或以中断标记落库，取决于宕机时机） |
| 续期网络抖动，锁被他人抢到 | 围栏号让旧回合的写入失败，不会出现两条并行的助手回复 |
| 摘要任务在 A 机器，回合在 B 机器 | 摘要写入 MySQL；B 下一轮读到新摘要；摘要还没好时 B 用旧摘要 + 更长的窗口，不等待 |
| 客户端换设备继续聊 | 历史、摘要都在服务端，与设备无关；SSE 续传靠 Redis 事件流 |

### 4.4 可选的读缓存

只有当 MySQL 读成为瓶颈时才加，默认不加。

- 键：`ca:sess:{sid}:ctx:{last_message_id}:{summary_version}`，值是已组装的窗口，TTL 10 分钟。
- 键里带「最后一条消息 id」与「摘要版本」，任何新消息、编辑、删除、新摘要都会自然换键，旧键过期即可，不需要主动失效。
- 缓存丢失只多一次 MySQL 读，不影响正确性。

## 5. 摘要的触发与生成

### 5.1 触发：按体量，不按时间

不采用「每 N 分钟」或「每天」定时摘要：不活跃的会话白白花钱，活跃的会话在两次之间可能已经溢出窗口。

触发条件（回合结束后检查，满足任一即入队）：

- 摘要截止点之后的原文超过**窗口目标预算**（默认 6000 token）；
- 摘要截止点之后超过**窗口目标回合数**（默认 30 个回合）。

也就是窗口一旦装不下全部未摘要的原文，就开始摘要。从触发到新摘要写入的这段时间，窗口用 §5.3 的硬上限兜住，正常情况下不丢任何回合。

辅助触发：会话空闲 30 分钟且仍有未摘要的溢出部分，入队一次，为用户下次回来做准备。

入队用已有的 `agent_job`：`kind = "session.summarize"`，`dedupe_key = "{session_id}:{target_upto_id}"`，重复入队被去重。同一会话同一时刻只有一个摘要任务在跑（任务内部也用 Redis 锁 `ca:sess:{sid}:summarize`）。

### 5.2 生成：增量、留余量

- 选取范围：从当前摘要的 `upto_message_id` 之后开始，到「最近窗口预算的一半」之前为止。也就是说，摘要只吃掉最旧的那部分，**最近的 3000 token 永远保留原文**，避免刚说过的话立刻被压缩。
- 截止点必须落在回合边界上（不拆回合）。
- 输入：上一版摘要 + 选取范围内的原文消息；用便宜模型，场景 `session_summarize`（加进 `config/llm/routing.yaml`）。
- 输出约束（写进摘要提示词）：
  - 保留：人名、称呼、约定、计划、日期、未完成的话题、角色扮演的剧情状态与设定；
  - 不保留：寒暄、已解决的问题细节、工具结果原文；
  - 禁止清单与记忆抽取一致（证件号、卡号、密码、精确住址、医疗信息）；
  - 不超过 600 token，超出则在同一任务里再压一次。
- 写入：新增一行（不覆盖旧版本），`version` 加一；回合读取 `version` 最大的一行。

### 5.3 摘要落后时的降级

摘要是异步的，回合可能遇到「溢出了但新摘要还没好」：

1. 窗口先在硬上限内扩展：最多扩到 9000 token 或 45 个回合，覆盖摘要截止点到当前的全部原文；
2. 仍然装不下时，丢弃最旧的回合，记录指标 `context.dropped_turns` 与日志（不含原文），并确保摘要任务已入队；
3. 任何情况下都不阻塞回合等待摘要。

## 6. Token 预算与计数

| 部分 | 默认预算 |
|---|---|
| system message（[1]–[6]） | ≤ 3500 |
| 会话摘要 [6.5] | ≤ 600 |
| 角色示例 [7] | ≤ 600 |
| 最近窗口 [8] | ≤ 6000（摘要落后时最多 9000） |
| 当前输入 [9] | ≤ 2000（超出见下文） |
| 输出预留 | `max_tokens`（路由表当前 4096） |
| **合计** | ≤ 约 17,000–20,000 |

- 合计必须小于所选模型的上下文窗口。路由表为每个模型补一个 `context_window` 字段；组装时检查，超出就先压窗口，再压示例。
- 计数：不引入分词器依赖，用保守估算：CJK 每字 1 token，其他文字每 3 字符 1 token，再乘 1.1 的安全系数。估算只用于预算，宁可高估。真实用量以模型返回的 `usage` 为准，记入 `chat_turn.usage`，用于校准估算。
- 当前输入过长（用户粘贴大段文本）：超过 2000 token 时截断到预算并在消息里标注「（以下内容过长已截断）」；完整原文仍保存在消息表里。

## 7. 什么会被遗忘

| 内容 | 是否保留在上下文 | 去向 |
|---|---|---|
| 最近 3000–6000 token 的对话（摘要后至少保留 3000） | 原文保留 | 窗口 |
| 更早的对话 | 压缩 | 会话摘要 |
| 跨会话的用户事实 | 保留 | 长期记忆，按相关性召回 |
| 寒暄、已解决问题的细节、工具结果原文 | 有意丢弃 | 只在消息表里，可翻看，不进提示词 |
| 摘要落后且超过硬上限的最旧回合 | 暂时丢失，摘要追上后恢复 | 记指标 |
| 被用户删除或编辑的消息 | 以数据库为准 | 见 §8 |

用户能感知到的「遗忘」只会发生在第五行，而且是暂时的，并且可观测。

## 8. 编辑、删除、注销

- **编辑或删除的消息还在窗口内**：窗口每轮重算，自然生效。
- **编辑或删除的消息已经被摘要覆盖**：把 `upto_message_id >= 该消息 id` 的所有摘要版本标记为失效（`stale=1`），入队重新生成；在新摘要生成之前，回合使用「最近一版未失效的摘要」，并按 §5.3 扩展窗口。
- **删除会话**：摘要随会话软删，30 天后与消息一起物理删除（O §10）。
- **注销**：账号清理任务（O §3）必须同时删除 `ca_chat_session_summary`，纳入注销对账。

## 9. 数据模型

新增迁移 `0003_session_summary`：

```
ca_chat_session_summary
  id                BIGINT PK AUTO_INCREMENT
  session_id        BIGINT NOT NULL
  owner_id          BIGINT NOT NULL
  version           INT NOT NULL
  upto_message_id   BIGINT NOT NULL      -- 覆盖到哪条消息（含）
  content           MEDIUMTEXT NOT NULL
  token_estimate    INT NOT NULL
  model             VARCHAR(128) NULL
  prompt_version    VARCHAR(32) NULL
  stale             TINYINT(1) NOT NULL DEFAULT 0
  deleted           TINYINT(1) NOT NULL DEFAULT 0
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  UNIQUE (session_id, version)
  INDEX  (session_id, deleted, stale, version)

ca_chat_session  增加列
  fence             BIGINT NOT NULL DEFAULT 0   -- §4.2 第 4 条
```

MySQL 5.6 兼容：不用 JSON，不用函数默认值，DATETIME 精度到秒（与现有表一致）。

## 10. 组件与接口

沿用分层约束：`domain` 纯逻辑，`ports` 定义协议，`adapters` 实现，`bootstrap` 组装。

```python
# domain/history/window.py —— 纯函数，替换现有 select_window
def build_window(messages, *, after_id, budget_tokens, max_turns, estimate) -> Window

# domain/history/budget.py —— 估算与总预算分配
def estimate_tokens(text: str) -> int
def allocate(model_context_window, max_output, parts) -> Allocation

# ports/history.py
class HistoryReader(Protocol):
    async def list_after(self, *, owner_id, session_id, after_id, limit) -> list[MessageRecord]
class SummaryStore(Protocol):
    async def latest(self, *, owner_id, session_id) -> SessionSummary | None
    async def append(self, summary: SessionSummary) -> None
    async def invalidate_from(self, *, owner_id, session_id, message_id) -> int

# app/chat/context.py —— 每回合调用一次
class ContextAssembler:
    async def build(self, *, owner_id, session_id, current_input) -> ContextBundle
        # ContextBundle: messages, summary_block, stats(窗口回合数、估算 token、是否降级、丢弃回合数)

# app/jobs/summarize.py —— 后台任务 session.summarize
```

`DeerFlowBrain` 不再自己拼 `[HumanMessage(...)]`，改为接收 `ContextBundle.messages`；摘要块交给提示词组装。`TurnRequest` 增加 `history` 字段（原生消息列表）。

回合结束后，`turn_runner` 在释放锁之前调用 `maybe_enqueue_summary(session)`（只做体量检查与入队，不调用模型）。

## 10.1 消息列表的组装（DeerFlow 格式）

### 10.1.1 谁负责什么

- **system 内容不进消息列表**。平台、角色、方法、任务、输出、用户层、会话摘要块都放进 `context["system_prompt"]`，由 `PromptMiddleware` 写进 `request.system_message`（P §2.4）。消息列表里不出现 `SystemMessage`。
- **消息列表只含对话**：`[角色示例…, 历史…, 当前输入]`，类型只有 `HumanMessage` 与 `AIMessage`。
- 调用方式：`graph.astream({"messages": messages}, context=context, stream_mode="messages")`。没有 checkpointer，每次调用的图状态从这份列表开始，所以列表必须是**完整的**。

### 10.1.2 数据库行到 LangChain 消息的映射

| 数据库中的行 | 进入列表 | 类型 | 说明 |
|---|---|---|---|
| `role=user, kind=chat`，已挂到已结束回合 | 是 | `HumanMessage` | 同一回合的多条用户消息（合并、插话）合并为一条，用 `\n\n` 连接，与 `turn_runner._attempt` 一致 |
| `role=assistant, kind=chat`，内容非空 | 是 | `AIMessage` | 中断且有内容：末尾附「（回复被中断）」，只在列表中附加，不写回数据库 |
| `role=assistant`，内容为空 | 否 | — | 空的 `AIMessage` 会被部分模型拒绝 |
| `kind=action`（确认后的执行结果） | 是 | `AIMessage` | 文本即结果摘要，不带 `tool_calls` |
| `turn_id` 为空（排队中） | 否 | — | 属于未来回合（§3.1） |
| 当前回合的用户消息 | 否（作为当前输入传入） | — | 避免重复 |
| `deleted=1` | 否 | — | |
| 工具中间过程（`AIMessage.tool_calls`、`ToolMessage`） | 否 | — | 本来就不存库（P §6.6）。列表里不能出现没有配对的 `tool_calls`，否则模型端会报错 |

### 10.1.3 DeerFlow 对消息的要求（已核实源码）

核实位置：`deerflow/agents/middlewares/message_utils.py`、`dynamic_context_middleware.py`、`summarization_middleware.py`。

1. **最后一条必须是当前用户的 `HumanMessage`。** `latest_genuine_user_message` 取列表中最后一条「真实用户消息」来界定本回合；`genuine_user_turn_id` 用它的 `id` 作为回合级中间件的键。
2. **`id` 必须存在、唯一、稳定。** 格式：`m{message_id}`，即数据库主键前加前缀。当前输入的 `id` 取它对应数据库行的 id。空 `id` 会让回合级中间件失效。
3. **不要用 `name="summary"` 的 `HumanMessage` 表示摘要。** DeerFlow 的摘要中间件把它当作压缩产物处理，且 `is_genuine_user_message` 会把它排除。摘要只放进 system 块（§3.2）。
4. **不要伪造 `hide_from_ui`、`dynamic_context` 之类的标记。** 这些是 DeerFlow 内部的隐藏消息，我们没有用，混进来会被它的逻辑误处理。
5. **`AIMessage` 之后不能紧跟没有配对的工具结果。** 我们的历史没有工具消息，这一条自然满足。
6. **用户消息会经过输入护栏。** `requires_input_sanitization` 对真实用户消息返回真，护栏会转义框架标记。历史中的用户消息每轮都会重新经过护栏，因此**护栏必须对已转义的文本幂等**，否则每轮都会多转义一次。这一点需要在实现前用源码核实（见 §14 第 4 条）。
7. **上下文注入不能放在列表末尾。** DeerFlow 的 `insert_after_leading_system_messages` 说明：注入内容应在系统消息之后、对话之前，既不能在末尾（会被当作工具输出），也不能在系统消息之前。我们把摘要放进系统块，正好满足这一点。

### 10.1.4 组装步骤（每次尝试都重做）

`ContextAssembler.build(owner_id, session_id, current_texts)` 每次调用：

1. 读取会话摘要（最新未失效版本）。
2. 读取摘要截止点之后、已结束回合的消息（§3.1），按回合分组。
3. 按预算从最新往前取回合（§6）。
4. 逐条映射（§10.1.2），同一回合内的用户消息合并，相邻的同类消息合并，去掉空消息。
5. 角色示例放在最前（不入库，按会话语言挑选，P §6.6）。
6. 追加当前输入：`current_texts` 合并为一条 `HumanMessage`，`id` 取最新挂到当前回合的用户消息的 id。
7. 校验（§10.1.5），不通过则抛出内部错误，回合标记为失败，不发送给模型。

**为什么每次尝试都要重做**：合并（`MERGED`）会让运行器用新的 `texts` 重跑（`turn_runner._run` 的循环），这时当前输入变了，历史也可能因为新挂上的消息而变化。构造函数只接收 `current_texts`，历史从数据库读取，两者自然一致。`_attempt` 当前构造 `TurnRequest` 的方式要改成调用 `ContextAssembler`。

**插话（STEER）不经过这里**：插话由 `SteerMiddleware` 在图内注入到运行中的状态里，不改变本次构造的列表。

### 10.1.5 校验（每次构造后必跑）

- 列表非空，最后一条是 `HumanMessage`，且 `genuine_user_turn_id(messages)` 等于当前输入的 `id`；
- `has_ai_response_after_latest_user_message(messages)` 为假（否则 DeerFlow 会把它当作旧版本的进行中回合）；
- 所有 `id` 非空且唯一；
- 没有 `ToolMessage`，没有带 `tool_calls` 的 `AIMessage`；
- 没有内容为空的消息；
- 没有 `SystemMessage`；
- 估算总 token 不超过 §6 的预算。

校验失败是代码缺陷，不是用户输入问题，应在测试中拦住，线上只记录并降级为「只发当前输入」。

### 10.1.6 多模态与超长附件

- 用户消息带图片（上传，O §5）时，内容为块列表：`[{"type":"text",...}, {"type":"image_url",...}]`。图片占用的 token 远大于文字，所以**只有最近 2 个回合保留图片，更早的图片替换为文字占位「[图片]」**，占位符本身写进列表，不再读取图片。
- 占位规则也要算进预算。

### 10.1.7 测试

- 映射：每种数据库行对应的消息类型与内容；排队中、已删除、空内容、当前回合的消息都被排除。
- 合并：同一回合多条用户消息合并为一条，用 `\n\n` 连接。
- 校验：§10.1.5 的每一条都有一个让它失败的用例。
- DeerFlow 对接：用脚本化模型（已有先例，`ToolVisibilityMiddleware` 验证时使用）跑真实的工厂图，断言模型收到的消息与构造的列表一致，且 `genuine_user_turn_id` 与当前输入的 `id` 相同。
- 跨服务器：两个组装器实例读同一会话，得到相同的列表。

## 11. 可观测性

每回合记录（不含原文）：窗口回合数、窗口估算 token、是否使用摘要、摘要版本与落后量、是否降级、丢弃回合数、估算与真实输入 token 之比。

报警：`context.dropped_turns` 持续大于 0（摘要任务跟不上）；估算与真实之比偏离 1 超过 30%（需要校准）。

## 12. 测试

- 窗口：按回合分组不拆回合；预算截断；中断消息的标注；删除与编辑生效。
- 窗口排除：排队中（`turn_id` 为空）的用户消息与当前回合的用户消息都不进入历史。
- 锁丢失：续期失败后模型流立即停止，助手消息不落库。
- 摘要截止点：只落在回合边界；最近一半预算永远保留原文。
- 降级：摘要缺失或落后时窗口扩展到硬上限，再丢弃最旧回合，且不阻塞。
- 漂移：两个回合用两个独立的组装器实例（模拟两台服务器），第二个读到第一个的结果。
- 围栏：模拟续期失败，旧回合的助手消息写入被拒绝。
- 失效：编辑已被摘要覆盖的消息后，摘要被标记失效并重新入队。
- 线上 MySQL 上跑仓储与迁移测试（与现有 `test_mysql_stores.py` 一致）。

## 13. 实施顺序

1. `build_window` + `estimate_tokens` + `HistoryReader`，brain 传入历史（先不做摘要）。这一步就修复「每轮都没有上下文」。
2. 围栏号与锁丢失时停止写入。
3. `ca_chat_session_summary` 迁移、`SummaryStore`、`session.summarize` 任务、触发与降级。
4. 编辑/删除失效、注销清理、指标。
5. 路由表补 `session_summarize` 场景与各模型的 `context_window`。

## 14. 待决定

1. **窗口预算 6000 token、摘要 600 token 是否合适**：取决于所选聊天模型的上下文窗口与成本。可以先用默认值上线，用 `usage` 数据调整。
2. **摘要模型**：用现有的便宜模型（路由表里的 flash 档），还是单独配置。
3. **角色扮演会话的摘要是否保留更多剧情细节**：可以按角色类型给摘要提示词不同的保留规则，首期建议统一。
4. **摘要是否对用户可见**：首期不可见，只在服务端使用。
5. **护栏对历史的幂等性（实现前必须核实）**：历史中的用户消息每轮都会过输入护栏。如果护栏的转义不是幂等的，每轮都会多转义一次，历史会越来越乱。核实方法：找到护栏的转义函数，对同一段文本连续应用两次比较结果。如果不幂等，要么只对当前输入过护栏，要么在入库时只存一次转义后的文本。
