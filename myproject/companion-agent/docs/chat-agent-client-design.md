# Android 客户端设计（接入 chat-agent）

日期：2026-11-09。配套：`chat-agent-design.md`（协议）、`chat-agent-ops-design.md`（错误码）。
范围：新 App 的对话、角色、解题、记忆四块如何接入 Python 服务。现有对话界面（`com.openapi.chat`）已经跑通，本设计在它上面改，不重写。

## 0. 现状与必须改的地方

现有代码（`weifu-refactor` 分支）的分层是对的：`domain` 只认 `ChatMessage` / `ChatStreamEvent`，协议细节在 `data` 层。问题出在交互模型：

| 现状 | 问题 |
|---|---|
| `ChatRepository.sendMessageStream(...)`：**一次发送返回一条 Flow**，Flow 结束即本轮结束 | 与「一个会话一条长连事件流」的后端模型不匹配 |
| `ChatUiState.canSend = … && !sending` | **发送期间不能再发**。这正是要解决的「用户会不停发消息」的反面 |
| 人设用 `characterId: Int?` + `roleId: String?` 两个参数，互斥 | 新后端只有 `role_id`，且固定在会话上，续聊不再传 |
| `ChatStreamEvent` 只有 `Delta` / `Done` / `Error` | 缺 `turn.started`、`step`、`input.queued`、`queue.drained`、`action.confirm_required` |
| 用户消息 id 等 `Done` 帧才拿到 | 新协议在 POST 回执里立刻给出 |

所以要改的是 **data 层与 ViewModel 的交互模型**，domain 的消息模型和 UI 组件大部分可以复用。

## 1. 新的交互模型

```
              发送（REST，立即返回回执）
  输入栏 ───────────────────────────────▶  POST /sessions/{id}/messages
                                             ← {message_id, turn_id, disposition, queue_position}

              接收（一条长连 SSE，按会话）
  消息列表 ◀──────────────────────────────  GET /sessions/{id}/events
                                             turn.started / message.delta / step /
                                             message.done / input.queued / queue.drained /
                                             action.confirm_required / error
```

- 发送和接收**解耦**。发送永远不阻塞，输入栏永远可用（受限流与队列上限约束，见 4.3）。
- 进入会话页时打开事件流，离开时关闭；后台超过 60 秒关闭，回到前台用 `Last-Event-ID` 续传。
- 列表的真相是「服务端历史 + 事件流增量」，本地 Room 只做离线缓存（与现在一致）。

## 2. 分层与模块

### 2.1 domain（`com.openapi.chat.domain`）

```kotlin
interface AgentChatRepository {
    suspend fun createSession(roleId: String, locale: String): ChatSession
    suspend fun loadHistoryPage(sessionId: String, before: String?, limit: Int = 30): HistoryPage
    suspend fun submit(sessionId: String, input: TurnInput): SubmitReceipt
    fun events(sessionId: String): Flow<SessionEvent>          // 冷流；收集即连接，取消即断开
    suspend fun cancel(sessionId: String)
    suspend fun queued(sessionId: String): List<QueuedInput>
    suspend fun withdraw(sessionId: String, messageId: String)
    suspend fun clearQueue(sessionId: String)
    suspend fun regenerate(sessionId: String, messageId: String)
    suspend fun pendingActions(): List<ConfirmCard>
    suspend fun confirmAction(confirmationId: String, accept: Boolean)
    suspend fun retryTurn(sessionId: String, turnId: String)          // 失败的回合，无论有没有产出
    suspend fun retryFailedQueue(sessionId: String)                   // 排空失败 3 次后
    suspend fun continueReply(sessionId: String, messageId: String)   // interrupted 的回复
    suspend fun deleteMyData()                                        // 注销：先调它，再调 Java（O §3）
}

data class SubmitReceipt(
    val messageId: String,
    val turnId: String?,
    val disposition: Disposition,      // STARTED / MERGED / STEERED / QUEUED（D §6.1）
    val queuePosition: Int?,
)

// 与服务端 D §7.2 一一对应；不认识的事件在解析层丢弃（D §7.4）
sealed interface SessionEvent {
    val eventId: String
    data class TurnStarted(…, val turnId: String, val userMessageIds: List<String>) : SessionEvent
    data class Delta(…, val turnId: String, val text: String) : SessionEvent
    data class Step(…, val turnId: String, val kind: StepKind, val title: String, val detail: String) : SessionEvent
    data class InputMerged(…, val messageId: String, val turnId: String) : SessionEvent
    data class InputSteered(…, val messageId: String, val turnId: String) : SessionEvent
    data class InputQueued(…, val messageId: String, val position: Int) : SessionEvent
    data class InputWithdrawn(…, val messageId: String) : SessionEvent
    data class QueueDrained(…, val turnId: String, val messageIds: List<String>) : SessionEvent
    data class Done(…, val turnId: String, val assistantMessageId: String?, val steeredMessageIds: List<String>) : SessionEvent
    data class ConfirmRequired(…, val confirmationId: String, val tool: String, val title: String, val summary: String, val expiresAt: Instant) : SessionEvent
    data class ActionDone(…, val confirmationId: String, val status: ActionStatus, val messageId: String?) : SessionEvent
    data class Failed(…, val turnId: String?, val code: String, val retryable: Boolean) : SessionEvent
    data class MessageCreated(…, val messageId: String, val clientMessageId: String?, val content: String) : SessionEvent  // 多端同步
    data class TurnSnapshot(…, val turnId: String, val userMessageIds: List<String>, val text: String, val steps: List<Step>) : SessionEvent
    data class TurnRestarted(…, val turnId: String, val userMessageIds: List<String>) : SessionEvent  // 合并导致重跑，清空占位气泡
    data class TurnCancelled(…, val turnId: String, val assistantMessageId: String?) : SessionEvent
    data class Reconnect(…, val afterMs: Long) : SessionEvent        // 服务端进程停机，稍后重连
    data object Gone : SessionEvent                            // 续传缓冲过期，需重新拉历史
}
```

HTTP 请求统一带 `Authorization: Bearer`、`X-App-Version`、`Accept-Language`、`X-Request-Id`（D §7.4、O §4.3）。

旧的 `ChatRepository` 保留给 Java 接口（`/api/chat/*`），新 App 走 `AgentChatRepository`。两者并存，由 `ChatDependencies` 按开关装配，不在同一个类里写两套协议。

### 2.2 data（`com.openapi.ks.myapp.data.agent`）

| 类 | 职责 |
|---|---|
| `AgentApi` | OkHttp + JSON 的 REST 调用，统一错误解析（`{error:{code,…}}` → `AgentError`） |
| `AgentEventSource` | SSE 长连：解析 `id:` / `event:` / `data:`、忽略 `:` 注释帧、记录最后的 event id |
| `AgentEventReconnector` | 断线重连：指数退避（1s、2s、4s… 上限 30s），重连带 `Last-Event-ID`，收到 `Gone` 时触发历史重拉 |
| `AgentChatRepositoryImpl` | 组合上面三者，并把事件写进 Room 缓存 |
| `AgentAuth` | 从现有登录态读 token，加 `Authorization: Bearer` 头；401 时通知 `LoginGate` |

SSE 不用 Android 的 `EventSource`（WebView 才有），也不额外引入库：OkHttp 读 `ResponseBody.source()` 按行解析即可，逻辑约 150 行，可以完整单测。

### 2.3 presentation（`com.openapi.chat.presentation`）

`ChatViewModel` 改为两条独立的协程：

```
eventsJob   = repository.events(sessionId).collect { reduce(it) }   // 进页面启动，离开取消
submitJob_n = 每次点发送一个，调用 submit() 并处理回执，互不阻塞
```

状态由一个纯函数 `reduce(state, event) -> state` 计算，这样所有事件组合（合并、插话、排队、失败、重连）都能用单测覆盖，不需要起界面。

## 3. 界面状态

### 3.1 新的 UI 状态

```kotlin
data class ChatUiState(
    val messages: List<ChatItem>,
    val activeTurn: ActiveTurn?,          // 正在生成的回合（含已产出的步骤）
    val queued: List<QueuedInput>,        // 排队中的输入，按 position 排
    val input: String,
    val drafts: List<DraftAttachment>,
    val connection: StreamConnection,     // CONNECTED / RECONNECTING / OFFLINE
    val pendingConfirmations: List<ConfirmCard>,
    val role: RoleSummary,
    val dir: LayoutDirection,             // 由会话语言决定，见第 5 节
    …
) {
    val canSend get() = (input.isNotBlank() || drafts.isNotEmpty()) && queued.size < QUEUE_MAX
}
```

**`canSend` 不再依赖「正在生成」。** 这是本设计最关键的一行改动。

### 3.2 一条用户消息的生命周期

| 状态 | 触发 | 气泡表现 |
|---|---|---|
| `sending` | 点发送，POST 未返回 | 正常气泡 + 小转圈 |
| `started` | 回执 `disposition=STARTED` | 正常气泡；下方出现她的占位气泡 |
| `merged` | 回执 `disposition=MERGED` 或 `InputMerged` | 正常气泡，与同一回合的其他消息用细线连起来（表示「这几句一起回答」）；随后的 `TurnRestarted` 让占位气泡清空重来 |
| `steer_pending` | 回执 `disposition=STEERED` | 正常气泡 + 角标「正在补充给她」 |
| `steered` | `InputSteered` | 角标变为「已补充给她」 |
| （steer 未生效） | 回合结束时收到 `InputQueued` | 转为 `queued`：服务端没来得及注入，改为排队回答（D §6.4） |
| `queued` | 回执 `disposition=QUEUED` 或 `InputQueued` | 半透明气泡 + 「排队中 · 第 N 条」；可长按撤回 |
| `answered` | `TurnStarted.userMessageIds` 或 `QueueDrained.messageIds` 包含它 | 恢复正常 |
| `failed` | POST 失败 | 红色感叹号，点击重试（复用同一个 `client_message_id`，服务端去重） |
| `withdrawn` | 撤回成功，或收到 `InputWithdrawn` | 从列表移除 |

「合并」与「插话」必须有可见提示，否则用户会以为自己的第二句没被看到（design §15 风险 2）。

### 3.3 生成中的回合

- 文本按 `Delta` 追加到占位气泡（与现在一致）。
- 解题回合：`Step` 事件显示成可折叠的步骤列表（读题 / 分析 / 推理 / 校验 / 答案），默认展开当前步骤、折叠已完成的。
- 停止按钮调用 `cancel()`；**取消只结束当前回合，不清空排队**（design §6.6）。排队区另有「清空排队」。

### 3.4 待确认的动作

`ConfirmRequired` 显示为对话流里的一张卡片：标题、摘要、「允许」「不用了」。点击后调 `confirmAction()`，卡片变为已处理状态。
卡片也在会话列表上显示角标：用户离开会话后，确认请求不会被忘记。

## 4. 连接、失败与恢复

### 4.1 连接状态机

```
CONNECTED ──断开──▶ RECONNECTING ──成功（带 Last-Event-ID）──▶ CONNECTED
    │                   │
    │                   ├── 收到 Gone ──▶ 重拉最新一页历史 ──▶ CONNECTED
    │                   └── 连续失败 > 5 次 ──▶ OFFLINE（顶部提示条，手动重试）
    └── 收到 Reconnect(afterMs) ──▶ 等 afterMs ──▶ RECONNECTING（不计入失败次数）

首次进入会话：若服务端有运行中的回合，第一条事件是 TurnSnapshot，用它填充占位气泡。
```

- `RECONNECTING` 期间输入栏仍然可用：发送走 REST，与长连无关。
- 收到 `Gone` 时不尝试拼接，直接用服务端历史覆盖当前列表——服务端是权威。

### 4.2 错误码处理

客户端只看 `code`，`message` 直接展示（服务端已按语言返回）：

| code | 行为 |
|---|---|
| `unauthorized` | 跳登录页，登录后回到当前会话 |
| `rate_limited` | 读 `Retry-After`，输入栏显示倒计时 |
| `queue_full` | Toast「等这一轮回答完再发」，不清空输入框 |
| `model_unavailable` | 回合失败气泡 +「重试」，调 `retryTurn(turnId)`；排空失败的批次调 `retryFailedQueue()`。不能用 `regenerate()`：失败且没有产出的回合没有助手消息可供重新生成（评审 m18） |
| `turn_interrupted` | 保留已显示的部分，气泡底部「继续」，调 `continueReply(messageId)` |
| `upload_too_large` / `upload_unsupported` | 草稿上标红，提示原因 |
| 其他 | 通用失败 + 「复制错误编号」（`request_id`），方便反馈 |

### 4.3 前台与后台

- 进入后台 60 秒后断开事件流；回合在服务端继续跑，结果照常落库。
- 回到前台：先续传，再刷新会话列表的未读角标。
- 不做后台常驻连接，不申请前台服务：浅聊没有「她主动找你」，那是角色扮演的推送通道。

## 5. 多语言与 RTL

- 界面语言跟随系统；会话语言在创建会话时确定（默认等于界面语言），存在会话上。
- 阿拉伯语会话：消息列表 `LayoutDirection.Rtl`；气泡左右对调；**数学公式与代码块强制 LTR**（`CompositionLocalProvider(LocalLayoutDirection provides Ltr)` 包住公式渲染），与服务端输出层的规则一致。
- 混排：一条阿拉伯语消息里夹着英文或数字时，用 `TextDirectionHeuristics.FIRSTSTRONG_LTR` 的等价处理（Compose 里设置 `TextStyle(textDirection = TextDirection.Content)`），按首个强方向字符决定段落方向。
- 字符串资源：新增 `values-ar/`；所有带位置含义的图标（返回、发送）用 `AutoMirrored` 版本。现有代码已经在用 `Icons.AutoMirrored.Filled.Send`，保持。
- 角色列表的展示字段用服务端返回的 `locale` 版本；响应里的 `dir` 只用于该条目的排版，不改变整个页面方向。

## 6. 角色

- 角色选择沿用现有 `RolePickerSheet`，数据源换成 `GET /api/agent/v1/roles`（分类、搜索、分页）。
- 选角色 = 新建会话（`POST /sessions {role_id, locale}`）。**续聊不再传角色**；同一会话不能换角色——换角色就开新会话。这与现有「`characterId` 与 `roleId` 互斥、每次发送都带」的做法不同，`selectedCharacterId` 字段删除。
- 用户自建角色：新增「我的角色」页，表单字段 = 名称、简介、人设正文（≤ 2000 字）、开场白、头像；保存失败时展示服务端的 `invalid_request.detail`（例如人设里有被拦截的注入模式）。
- 自建角色只在自己的列表里出现，没有分享入口。

## 7. 解题

- 入口沿用现有的附件能力（`AttachmentStager`）：拍照 / 相册 → 本地压缩到长边 2048 → `POST /uploads` → 拿到 `upload_id` → 随消息提交。
- 本地压缩只是为了省流量；服务端仍会重新编码并去 EXIF（ops 文档第 5 节），客户端不能依赖本地处理来保护隐私。
- 显式的「解题」入口在提交时带 `skill=problem-solving`；普通对话里发图片也会被服务端选中解题 skill，客户端不判断。
- 公式渲染：现有 `MarkdownText` 已支持单 `$` 公式，保持服务端输出层「公式用单个 $」的约定。

## 8. 记忆

- 新增「她记得的」页：两个标签页——事实、重要日子。数据源 `GET /api/agent/v1/memory/{facts,events}`，分页。
- 每条可删除；删除是真删除，确认弹窗里写明「删除后她将不再记得这件事」。
- 重要日子可手动添加（标题 + 时间）。
- 「她眼里的我」（L3 画像）是 P4 的内容，客户端届时再加，接口预留在 `GET /api/agent/v1/memory/profile`。

## 9. 离线缓存（Room）

服务端是权威，本地只做两件事：冷启动时先显示上次的内容，以及离线时能看历史。

```
agent_session:    id (服务端 id), role_id, name, locale, updated_at, last_event_id
agent_message:    id (服务端 id), session_id, role, kind, content, meta_json,
                  client_message_id, local_state ('synced'|'sending'|'failed'), created_at
                  索引 (session_id, created_at)；唯一 (client_message_id)
agent_role_cache: id, payload_json, locale, fetched_at      —— 角色列表，1 小时过期
```

规则：

- **只缓存每个会话最近 100 条**，更早的只在线拉取；缓存是窗口，不是镜像。
- 发送时先写一条 `local_state='sending'` 的消息（`client_message_id` 本地生成），回执到达后用服务端 id 替换并置 `synced`；失败置 `failed`，重试复用同一个 `client_message_id`。
- 拉到服务端历史后，**以服务端为准覆盖**同一时间范围内的本地记录；本地有、服务端没有的 `synced` 消息视为已被删除，直接删掉。
- `last_event_id` 存在会话上，App 被杀后重新打开也能续传。
- 不缓存：排队状态、确认卡片、步骤——它们都是短期状态，重新进入会话时从 `GET /sessions/{id}/queue` 与 `GET /actions/pending` 重新拉。
- 账号退出时清空全部三张表。

## 10. 测试

| 层 | 测什么 |
|---|---|
| `AgentEventSource` | 分帧、多行 `data:`、注释帧、半包、`id:` 记录 |
| `AgentEventReconnector` | 退避节奏、`Last-Event-ID` 携带、`Gone` 触发重拉、超过次数进 OFFLINE |
| `reduce(state, event)` | 合并 / 插话 / 排队 / 排空 / 取消不清队列 / 失败重试复用 id / 重连后去重（同一 event id 只应用一次） |
| `AgentApi` | 错误体解析成 `AgentError`、401 回调 `LoginGate` |
| 界面 | Robolectric：RTL 下气泡方向与公式 LTR；排队气泡的展示与撤回 |

## 11. 与现有代码的迁移

| 现有 | 处理 |
|---|---|
| `ChatRepository` / `ChatRepositoryImpl` | 保留，供旧接口；不再扩展 |
| `ChatStreamEvent` | 保留，供旧接口；新事件用 `SessionEvent` |
| `ChatViewModel` | 抽出 `reduce`；通过 `ChatDependencies` 选择旧/新仓库 |
| `ChatUiState.sending` 驱动的 `canSend` | 改为基于队列上限 |
| `selectedCharacterId` / `characters` | 删除（新后端只有 `role_id`） |
| `RolePickerSheet`、`MarkdownText`、`AttachmentStager`、`ChatSessionsSheet` | 复用，换数据源 |
| `companion/` 包（LiveKit 版陪伴界面） | 角色扮演专用，与本设计无关，保持不动 |
