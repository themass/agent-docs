# 浅聊 Agent 设计（chat-agent）

日期：2026-11-08。状态：设计稿，待评审后实施。

## 0. 定位：重做，不是迁移

Java 的 AI 接口保持原样，不删、不改、不转发。Python 这边按新 App 的需要重新实现：

- 新接口、新 App、没有老用户，所以**不做数据迁移，不做协议兼容**。
- 唯一要对接的存量是账号体系：登录仍由 Java 完成，Python 只验证登录态（第 4 节）。
- 浅聊是角色扮演的地基。两者共用同一个内核（DeerFlow 大脑、中间件链、记忆），区别只在能力集与传输层。
- 记忆层要能被**第三个应用**（job-come）共用，所以单独封成库（第 10 节）。

目标：角色（列表、选择、用户自建增删改查）、**连续对话**（用户会不停发消息）、解题（文字与拍照）、记忆。
语言：中文、英文、阿拉伯语，预留其他中东语言。

非目标：LiveKit、语音、形象、主动推送（角色扮演）；内容审核与成本控制（先忽略，保留中间件挂载点）。

## 1. 整体架构

```
Android App
   │  HTTPS：REST（JSON）+ 一条长连 SSE（每个会话）
   │  Authorization: Bearer <登录 token>
   ▼
┌───────────────────── agent-api（FastAPI，无状态，可多副本）─────────────────────┐
│ transport/sse     会话事件流：SSE 编码、心跳、Last-Event-ID 续传                  │
│ products/chat     角色、会话、回合状态机、解题 API                                │
│ kernel            TurnPipeline → 中间件链 → BrainPort(DeerFlow)                  │
│                   能力注册（skill/tool/MCP）、i18n、模型路由                       │
│ memory_hub        ★ 多应用共享的记忆库（本服务 + job-come + 角色扮演）             │
│ persistence       端口 + 实现                                                    │
└──────┬───────────────┬───────────────┬────────────────┬───────────────┬──────────┘
       │               │               │                │               │
     MySQL           Redis           Qdrant          对象存储        LLM 网关
  会话/消息/角色   登录态 + 回合      mem0 向量       图片附件     通义/豆包/DeepSeek/GPT
                   事件流 + 队列
```

服务清单（浅聊阶段）：

| 服务 | 说明 |
|---|---|
| agent-api | 唯一的自研进程，uvicorn 多副本，水平扩展 |
| MySQL | 新库 `agent`，不与 Java 的 `vpn` 库共表 |
| Redis | 三个用途：验证 Java 登录态；会话事件流（续传）；回合队列与运行锁 |
| Qdrant | mem0 向量库，**每个应用一个 collection** |
| 对象存储 | 解题图片，沿用阿里云 OSS |
| LLM 网关 | OpenAI 兼容端点，经 LiteLLM 路由 |

没有 worker，没有 LiveKit。角色扮演上线时才加 worker 与 LiveKit。

## 2. 复用与新增

已写好并测过的部分直接复用，不搬家、不重命名：

| 复用 | 说明 |
|---|---|
| `middleware/*` | 安全、记忆召回、事件抽取、人设守卫、授权、成本、观测，顺序固定 |
| `memory/port.py` | MemoryPort 协议与数据形状（mem0 适配器会升级到 `memory_hub`） |
| `timeline/*` | 重要日子 |
| `brain/deerflow.py` | DeerFlow 适配（需补强，见第 8 节） |
| `server/memory_api.py` | 记忆与事件的增删改查，已有用户隔离与分页边界的测试 |
| `server/support.py`、`server/deps.py` | 分页夹取、身份依赖 |

新增：`transport/sse`、`products/chat`、`persistence`、`kernel/i18n`、`kernel/models`、`memory_hub`。
不把现有模块整体搬进 `kernel/`：搬家会让 300 多个测试的 import 全变，收益只是目录好看。边界靠依赖方向保证。

依赖方向：`products` → `kernel` → 端口；`transport` 只依赖 `products` 的服务接口。内核不 import 产品。

## 3. 数据模型

库 `agent`，MySQL 8，SQLAlchemy 2（async）+ Alembic。

### 3.1 role（用户自建角色）

| 列 | 说明 |
|---|---|
| id | BIGINT 自增；`public_id` 单独一列，对外是 `u_` + 26 位 ULID，唯一索引 |
| owner_id | 创建者，所有查询必带 |
| name / tagline / description / prompt | 文本；按创建者语言存一份，不做多语言映射 |
| locale | 创建时的语言 |
| avatar | 可选，对象存储 key |
| created_at / updated_at / deleted | 软删除 |

用户自建角色**私有**：不审核、不分发、无分享接口，别人的 id 一律 404。

### 3.2 角色 id 的语义（已确认）

`roleId` 是字符串，`VARCHAR(128)`，三种来源共用一个命名空间，靠前缀区分：

| 来源 | 形式 | 例子 |
|---|---|---|
| 系统目录（283 个 agency-agents 角色） | 目录原有 slug | `academic-anthropologist` |
| 陪伴人设（角色扮演） | 人设卡文件名 | `linche`、`sudai` |
| 用户自建 | `u_` + ULID | `u_01JC8…` |

系统 id 不得以 `u_` 开头，目录加载时校验，违反就拒绝启动。已核对：Java 库的 `chat_session.roleId` 是 `VARCHAR(128)`，目录 `RoleItem.id` 是字符串，两边一致。

### 3.3 会话与回合

```
chat_session: id, owner_id, role_id, name, locale, created_at, updated_at, deleted
              索引 (owner_id, deleted, updated_at)

chat_message: id, session_id, owner_id, role('user'|'assistant'), content (MEDIUMTEXT),
              kind('chat'|'solve'|'action'), meta (JSON), client_message_id, turn_id,
              interrupted (BOOL), created_at, deleted
              索引 (session_id, deleted, id)；唯一 (session_id, client_message_id)

chat_turn:    id (ULID), session_id, owner_id,
              state('pending'|'running'|'done'|'failed'|'cancelled'),
              model, prompt_version, role_id, skills (JSON), usage (JSON),
              error_code, started_at, finished_at
              索引 (state, started_at)              —— 卡死回合巡检用（O §2.3）

chat_queue:   id, session_id, owner_id, message_id, client_message_id, text, attachments (JSON),
              status('queued'|'draining'|'drained'|'merged'|'steered'|'withdrawn'|'dropped'|'failed'),
              turn_id NULL, drain_attempts INT DEFAULT 0, created_at
              索引 (session_id, status, id)

upload:       id, owner_id, key, mime, size, width, height, referenced (BOOL), created_at
```

`chat_queue` 落库而不只放 Redis：用户中途杀进程，重新打开时队列还在；Redis 只做热路径。
`status` 的转移只有这几条，其余一律视为非法并拒绝：

```
queued → draining → drained        正常排空
queued → merged | steered          被并入或注入运行中的回合
queued → withdrawn                 用户撤回
queued → dropped                   超过上限或会话被删除
queued → steered → queued          交给回合但没被注入，回合结束时转回队列（§6.4）
draining → queued                  排空失败，原样塞回，drain_attempts+1（§6.5）
draining → failed                  连续失败 3 次（§6.5）
failed → queued                    用户点重试
```

### 3.4 工具、记忆与后台任务相关的表

```
action_confirmation:  id (ULID), owner_id, session_id, turn_id, tool,
                      args (JSON, 处理完 7 天后清空), args_fingerprint,
                      title, summary, status('pending'|'executed'|'declined'|'expired'|'failed'),
                      expires_at, decided_at, created_at
                      索引 (owner_id, status)、(status, expires_at)

tool_call:            id, turn_id, owner_id, tool, permission, args_fingerprint,
                      status('executed'|'needs_confirmation'|'denied'|'failed'|'timeout'),
                      latency_ms, result_chars, created_at
                      索引 (turn_id)、(created_at)      —— 90 天后删除（O §10）

persona_profile:      id, owner_id, app, version, markdown (TEXT), source ('auto'|'user_edited'),
                      generated_from (JSON: L1/L2 的 id 范围), created_at
                      唯一 (owner_id, app, version)；读取取最大 version
                      用户编辑过的版本不会被定时任务覆盖，自动生成的新版本作为「建议」等用户采纳

agent_job:            见 O §2.1
account_purge_log:    user_hash, requested_at, finished_at   —— 不存原 user_id
```

## 4. 身份验证

登录、注册、改密仍在 Java。Python 只验证。

已核对 Java 机制：登录成功后 `token_<hash>` 作为 Redis 键，值是 `UserPo` 的 JSON，TTL 24 小时；Java 拦截器用 `GET <token>` 取用户。**Python 直接读同一个 Redis**，不回调 Java，不需要额外的只读账号。

要点：
- **键必须校验**：只接受匹配 `^token_[A-Za-z0-9+/]{8,512}={0,2}$` 的字符串，否则 401。
  已核对：Java 的 token 是 `"token_" + AuthUtil.nameToToken(name)`，后者返回 `Base64.encodeBase64String(...)`，即**标准 Base64**，包含 `+`、`/` 与 `=` 填充（`AuthUtil.java:53`）。校验的目的不是验证 token 真伪（真伪由 Redis 里有没有这个键决定），而是不让客户端用任意字符串去探测 Redis 里的其他键：固定前缀 + Base64 字母表 + 长度上限即可做到。
  （修订：上一版的 `[A-Za-z0-9_-]` 会拒绝所有真实 token，评审 B1。）
- Java 现在原样 `GET` 客户端传来的头，客户端能指定任意键；Python 不能照抄这一点。
- **只取 `id` 和 `level`**。`UserPo` 里有 `pwd`、`pwdHash`，反序列化后立刻丢弃，不进日志、异常信息或任何下游。
- 客户端发 `Authorization: Bearer <token>`。Java 的 `Sex-Token` / `Vpn-Token` 头不出现在新接口里。
- 验证器是 `CredentialVerifier` 的实现（`RedisTokenVerifier`），接口已存在。
- 生产检查：`COMPANION_ENV=prod` 且验证器是 `allow_all` 时拒绝启动，写进代码。

## 5. 角色与多语言

### 5.1 系统目录

Java 的 `catalog.json`（283 个角色，MIT，来自 agency-agents）与 `catalog-zh.json` 复制进 `companion-agent/roles/`，连同 NOTICE。Python 不依赖 Java 仓库。
陪伴人设（`characters/*.v2.json`）作为同一目录的另一个来源，加载进同一个 `RoleCatalog`。

### 5.2 语言

- 支持 `zh-CN`、`en`、`ar`；预留 `fa`、`tr`、`ur`、`he`。
- 展示语言取 `Accept-Language`，可被 `locale` 参数覆盖，默认 `zh-CN`。
- 需要翻译的是展示字段（名称、简介、分类名）；`prompt` 保持英文，由系统提示要求模型用会话语言回复。
- 阿拉伯语展示字段：离线批量机翻产出 `catalog-ar.json`，标记为机翻待校对。缺失按 `ar → en` 回退。
- 响应带 `locale`（实际语言）与 `dir`（`ltr` / `rtl`），客户端据此排版。
- 会话语言：创建时记录；用户换语言提问时，回复跟随用户输入。

### 5.3 接口

前缀 `/api/agent/v1`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/divisions` | 分类列表 |
| GET | `/roles` | 系统角色 + 自己的自建角色；`division`、`q`、`mine`、`locale`、`limit`、`offset` |
| GET | `/roles/{id}` | 详情 |
| POST | `/roles` | 新建 |
| PUT | `/roles/{id}` | 修改（仅本人；系统角色 403） |
| DELETE | `/roles/{id}` | 删除（仅本人） |

分页：`limit` 默认 20、最大 100；`offset` 最大 1000。别人的自建角色与不存在的 id 同样 404。

## 6. 连续对话：回合状态机（核心）

用户会不断发消息，不可能一问一答。模型是**每个会话最多一个运行中的回合 + 一个输入队列**，并且**所有跨请求的协调都经过 Redis**：API 有多个副本、每个副本多个 worker 进程，发消息、取消的请求几乎一定落在「不是正在跑这个回合的那个进程」上，进程内对象一律不能作为协调手段。

（修订 2026-11-09：根据独立评审的 B2、B3、M4、M5、m17 重写本节。）

### 6.1 四种处置（服务端决定，回执里告诉客户端）

| disposition | 条件 | 含义 |
|---|---|---|
| `started` | 会话空闲（没有运行中的回合） | 这条消息开启一个新回合 |
| `merged` | 有运行中的回合，且它**还没有产出任何可见 token、也没有执行过工具** | 并入这个回合：中止正在进行的模型调用，用合并后的输入重新开始（6.3） |
| `steered` | 回合已产出内容，但回合的 skill 声明 `steerable`，且 `steer_budget` 未用完 | 交给运行中的回合，在下一次模型调用前注入（6.4） |
| `queued` | 其余情况 | 入队；当前回合结束后整批合并成一个新回合（6.5） |

回执：

```json
{"message_id": "881", "turn_id": "01JC…", "disposition": "queued", "queue_position": 2}
```

- **客户端永远不需要处理 409**，也不需要判断会话状态。
- `steered` 是「已交给运行中的回合」，不是「已被模型看到」。真正注入时发 `input.steered`；回合结束还没被注入的，服务端改为入队并发 `input.queued`（6.4）。客户端以事件为准更新气泡。
- **每条输入在得到 disposition 之前先过 `safety` 检测**（在 `app/chat/submit.py` 里，不是回合开始时）。这样合并、插话、排队三条路径上的文本都被检测过——回合外的 `safety` 中间件只看回合开始时的输入，覆盖不到中途注入的文本。

### 6.2 回合控制面（Redis）

| 键 | 类型 | 内容 | 写者 | 读者 |
|---|---|---|---|---|
| `sess:{id}:lock` | string，`SET NX PX 30000` | 持有者 `{process_id}:{turn_id}` | 回合所在进程（每 10 秒续租） | 所有进程 |
| `sess:{id}:turn` | hash | `turn_id`、`phase`（`pre_output` / `output` / `tool`）、`restarts`、`steer_used`、`started_at` | 回合所在进程 | submit 判定 disposition |
| `turn:{tid}:ctl` | stream | 控制消息：`merge{message_id}`、`steer{message_id}`、`cancel` | 任意进程（submit、cancel 接口） | 回合所在进程（`XREAD BLOCK`） |
| `turn:{tid}:text` | string（`APPEND`） | 已产出的正文 | 回合所在进程 | 首连快照（7.3）、崩溃回收（O §2.3） |
| `sess:{id}:events` | stream | 对外事件（7.2） | 回合所在进程、submit | SSE |

disposition 的判定读 `sess:{id}:turn` 的 `phase`，**判定与投递用一个 Lua 脚本原子完成**：读 phase → 决定 disposition → 把控制消息写进 `turn:{tid}:ctl`（或写队列）。这样不会出现「判定时还是 `pre_output`，投递时已经开始吐字」的竞态。

回合所在进程有一个控制协程，`XREAD BLOCK` 读 `turn:{tid}:ctl`，把消息分派给本进程内的回合对象。这是**唯一**把跨进程消息变成进程内动作的地方。

### 6.3 合并：中止并重启，不加等待

上一版的「回合开始后 1.2 秒合并窗口」作废：模型请求在回合开始时就已经发出，`before_model` 也已经执行过，窗口内到达的输入进不了这次调用；要让它进得去，只能让每个回合都先等 1.2 秒，等于所有回答的首 token 都晚 1.2 秒。

改为：

1. 回合开始立即调用模型，不等待。单条消息的首 token 延迟不受影响（这是最常见的情况）。
2. 在 `phase=pre_output` 期间收到 `merge`：取消正在进行的模型调用，把新输入并进本回合的输入，**用同一个 `turn_id` 从头重跑图**（图无状态、不用 checkpointer，重跑是干净的）。`restarts += 1`。
3. 以下任一发生，`phase` 离开 `pre_output`，之后的输入不再走 `merged`：
   - 产出第一个可见 token（`phase=output`）；
   - 执行了任何工具（`phase=tool`）——工具可能有副作用，不能撤销后重来；
   - `restarts` 达到 2——用户一直在打字时，不能无限重启。

代价：被中止的那次调用已经产生了输入 token 的费用。按首 token 前约 1.5 秒估算，只有「连续快发」时才发生，可以接受；`turn_restart_total` 指标监控它的频率（O §4.2）。

### 6.4 插话（steer）：中间件 + 控制流

`SteerMiddleware`（图内，`abefore_model`）：

```python
class SteerMiddleware(AgentMiddleware):
    async def abefore_model(self, state, runtime):
        items = runtime.context["steer_inbox"].take_all()   # 本进程内的收件箱，由控制协程填充
        if not items:
            return None
        await runtime.context["events"].emit_steered(items)  # 发 input.steered
        return {"messages": [*state["messages"], HumanMessage(content=render_steer_block(items))]}
```

- **只实现异步钩子**：图用 `astream` 驱动，只有同步钩子的中间件在异步路径下会抛 `NotImplementedError`（`langchain/agents/middleware/types.py` 约 638 行）。所有图内中间件都按此实现。
- `runtime.context` 是一个 **Mapping**（`TypedDict`），不是 dataclass：DeerFlow 的部分逻辑只在 context 是 Mapping 时才读取它（`deerflow/agents/interaction_policy.py`）。
- **没被注入的不会丢**：回合结束时，收件箱里剩下的 steer 项写回 `chat_queue`（排在队首，状态 `queued`），并逐条发 `input.queued`，由下一次排空回答。服务端在 POST 时无法预知还有没有下一次模型调用，所以必须在回合结束时兜底。
- 注入的是用户输入，已在 submit 时过了 `safety`（6.1）。
- 能力边界不变：注入点是「下一次模型调用之前」。纯文本一次性生成的回合里通常没有下一次调用，steer 会落到「回合结束时转入队列」这条路上。

### 6.5 队列排空

沿用 DeerFlow `buffer_followups_on_busy` 的做法（`manager.py` 的 `_drain_followups_for_thread`）：

- **一批最多 10 条**。只弹最老的一批；积压更深时，这一批回答完再排下一批，不拼成一个超长输入。
- **合并成一个输入块**，带定界标记：

```
<followups-while-busy>
A previous answer was still being written when these arrived. They are
delivered together as one turn:
1. 那第二个呢？
2. 顺便问下价格
</followups-while-busy>
```

  文本按 `escape(quote=False)` 处理。
- **去重**：按 `client_message_id`。
- **有界**：每会话最多 20 条，超出返回 `queue_full`。
- **失败回填，但有上限**：排空失败时，这一批状态从 `draining` 回到 `queued`，`drain_attempts += 1`。连续失败 3 次后，这一批置 `failed`，发 `error{code:"model_unavailable", retryable:true}`，不再自动重试——避免模型持续不可用时，巡检任务每分钟重起一个注定失败的回合。用户点重试时调用 `POST /sessions/{id}/queue/retry`，把 `failed` 的项恢复成 `queued`。
- **顺序**：严格按到达顺序。

### 6.6 运行锁与恢复

- 锁见 6.2。进程崩溃后租约 30 秒内过期。
- 锁过期但回合仍是 `running`、或队列里有 `queued` 项却没有运行中的回合：由 worker 的 `turn.sweep` 与 `queue.drain_orphans` 处理（O §2.3），不依赖下一个用户请求。

### 6.7 与取消、重试、重新生成、继续的关系

| 操作 | 接口 | 适用 | 行为 |
|---|---|---|---|
| 取消 | `POST /sessions/{id}/cancel` | 运行中的回合 | 写 `cancel` 到控制流；回合结束为 `cancelled`，已产出部分落库（`interrupted=true`），发 `turn.cancelled`。**不清队列** |
| 重试 | `POST /sessions/{id}/turns/{turn_id}/retry` | 失败的回合（无论是否产出过内容） | 用该回合的原始输入重新跑一个回合 |
| 重新生成 | `POST /sessions/{id}/messages/{mid}/regenerate` | 已有的助手回复 | 软删这条回复，用同样的输入重跑；排空进行中返回 `409 conflict` |
| 继续 | `POST /sessions/{id}/messages/{mid}/continue` | `interrupted=true` 的助手回复 | 新回合，输入为「接着上一条未完成的回答继续」，产出追加到原消息之后的新消息 |
| 撤回 | `DELETE /sessions/{id}/queue/{message_id}` | `queued` 的项 | 置 `withdrawn`，对应用户消息软删 |
| 清空队列 | `POST /sessions/{id}/queue/clear` | 全部 `queued` 项 | 逐条撤回 |

区分「重试」与「重新生成」：失败且没有产出的回合**没有助手消息**（空回复不落库），无法对它「重新生成」，只能按回合重试。

## 7. 协议

### 7.1 资源

本节是全部对外接口的**唯一权威列表**，其他文档引用接口时以这里为准。前缀 `/api/agent/v1`。

| 方法 | 路径 | 说明 | 定义见 |
|---|---|---|---|
| GET | `/divisions` | 角色分类 | §5.3 |
| GET/POST | `/roles` | 角色列表 / 新建自建角色 | §5.3 |
| GET/PUT/DELETE | `/roles/{id}` | 角色详情 / 修改 / 删除（仅本人） | §5.3 |
| GET/POST | `/sessions` | 会话列表（`updated_at` 倒序）/ 新建（`role_id` 必填，`locale` 可选） | |
| PATCH/DELETE | `/sessions/{id}` | 改名 / 软删除 | |
| GET | `/sessions/{id}/messages` | 历史，`before` 游标，倒序 | |
| POST | `/sessions/{id}/messages` | **发消息**：立即返回回执，不返回流 | §6.1 |
| GET | `/sessions/{id}/events` | **会话事件流**（SSE 长连），`Last-Event-ID` 续传 | §7.2–7.3 |
| POST | `/sessions/{id}/cancel` | 取消当前回合（不清队列） | §6.6 |
| GET | `/sessions/{id}/queue` | 当前排队的输入 | |
| DELETE | `/sessions/{id}/queue/{message_id}` | **撤回一条排队中的消息**；已被排空或合并的返回 `409 conflict` | |
| POST | `/sessions/{id}/queue/clear` | 清空队列 | §6.6 |
| POST | `/sessions/{id}/messages/{mid}/regenerate` | 重新生成；排空进行中返回 `409` | §6.6 |
| PATCH/DELETE | `/messages/{id}` | 编辑 / 删除（仅用户消息可编辑） | |
| POST | `/uploads` | 上传解题图片，返回 `upload_id` | O §5 |
| POST | `/actions/{confirmation_id}/confirm` | 确认或拒绝工具动作（body `{accept: bool}`） | T §2.4 |
| GET | `/actions/pending` | 当前用户待确认的动作 | T §2.4 |
| GET/POST | `/memory/facts` | 事实记忆列表 / 手动添加 | §10.5 |
| PATCH/DELETE | `/memory/facts/{id}` | 修改 / 删除 | §10.5 |
| GET/POST | `/memory/events` | 重要日子列表 / 手动添加 | §10.5 |
| PATCH/DELETE | `/memory/events/{id}` | 修改 / 删除 | §10.5 |
| GET | `/memory/profile` | L3 画像（P4） | §10.6 |
| GET | `/healthz`、`/readyz` | 健康检查（无前缀） | P §3.6 |
| POST | `/sessions/{id}/turns/{turn_id}/retry` | 重试失败的回合 | §6.7 |
| POST | `/sessions/{id}/messages/{mid}/continue` | 继续被中断的回答 | §6.7 |
| POST | `/sessions/{id}/queue/retry` | 把排空失败的项恢复为排队 | §6.5 |
| DELETE | `/me` | 删除我在本服务的全部数据（App 内注销时调用） | O §3 |

（O = chat-agent-ops-design.md，T = chat-agent-tool-mcp-design.md，P = chat-agent-prompt-skill-design.md）

撤回的语义：只能撤回 `chat_queue.status='queued'` 的项，撤回后置 `withdrawn`，对应的用户消息软删除。正在排空的批次不能撤回——那几条已经交给模型了。

**每个会话一条 SSE，而不是每次请求一条。** 这是连续对话的关键：排队消息被回答时，新回合的事件直接出现在同一条流上，客户端不需要管理多条连接，也不需要轮询「我排的队到哪了」。

### 7.2 事件

本节是全部事件的唯一权威列表。每个事件带 `id:`（单调递增，见 §7.3）与 `event:`，`data` 是 JSON：

| event | data | 说明 |
|---|---|---|
| `message.created` | `{message_id, client_message_id, role, kind, content, created_at}` | 一条用户消息已落库。**每条用户输入都发**（不论 disposition），多端据此同步显示 |
| `turn.snapshot` | `{turn_id, user_message_ids, text, steps}` | 只在 SSE 首连且有运行中的回合时发一次，给出已产出的内容（7.3） |
| `turn.started` | `{turn_id, user_message_ids}` | 回合开始；本回合覆盖的用户消息（含合并进来的）一并给出 |
| `turn.restarted` | `{turn_id, user_message_ids}` | 合并导致回合重跑（§6.3）；客户端清空该回合的占位气泡 |
| `message.delta` | `{turn_id, delta}` | 助手正文增量 |
| `step` | `{turn_id, kind, title, detail}` | 解题步骤，`kind`：`read`/`reason`/`check`/`answer` |
| `input.merged` | `{message_id, turn_id}` | 一条输入并入正在进行的回合（与 POST 回执冗余，保证多端一致） |
| `input.steered` | `{message_id, turn_id}` | 一条输入被注入运行中的回合 |
| `input.queued` | `{message_id, queue_position}` | 入队 |
| `input.withdrawn` | `{message_id}` | 撤回成功 |
| `queue.drained` | `{turn_id, message_ids}` | 一批排队输入被合并成新回合 |
| `message.done` | `{turn_id, assistant_message_id, steered_message_ids, usage}` | 正常结束，助手消息已落库；空回复时 `assistant_message_id` 为 null |
| `action.confirm_required` | `{confirmation_id, tool, title, summary, expires_at}` | 工具需要用户确认（T §2.3） |
| `action.done` | `{confirmation_id, status, message_id}` | 确认处理完成；`status`：`executed`/`declined`/`expired`/`failed` |
| `turn.cancelled` | `{turn_id, assistant_message_id?}` | 回合被取消；已产出部分落库为 `interrupted=true` 的消息（若有） |
| `error` | `{turn_id?, code, message, retryable}` | 失败；已生成的部分已落库。`code` 见 O §6.2 |
| `gone` | `{}` | 续传缓冲已过期，客户端应重新拉历史 |
| `reconnect` | `{after_ms}` | 服务端进程即将停机，客户端在 `after_ms` 后带 `Last-Event-ID` 重连（P §3.5） |

- 心跳：每 15 秒一条注释帧 `: keepalive`。
- 响应不做额外加密封装，靠 TLS + Bearer。Java 的 AES 密钥随客户端分发，实际只是混淆。

### 7.3 事件流存储与续传

- 每个会话一个 Redis Stream：`sess:{id}:events`。`XADD` 写入，`MAXLEN ~ 5000`，空闲 30 分钟后过期。
- **增量要合并后再写**：`message.delta` 每 50 毫秒或每 64 个字符合并成一个事件，不是每个 token 一个事件。一个 4k token 的长回答约 150–300 个事件，不会把自己的开头挤出缓冲（评审 M9）。
- 正文另外 `APPEND` 到 `turn:{tid}:text`（§6.2），不依赖事件流恢复：首连快照与崩溃回收都读这里。
- **首连**（无 `Last-Event-ID`）：若会话有运行中的回合，先发一条 `turn.snapshot`（已产出的文本与步骤），再转入实时订阅；没有运行中的回合则直接实时订阅。这解决了「回合进行到一半时打开会话，只收到半截增量」的问题（评审 M8）。
- 事件 id 用 Redis Stream 自己的 id（`<毫秒>-<序号>`），跨回合单调递增，`Last-Event-ID` 直接对应 `XREAD` 的起点。
- 回合作为后台任务运行，与 SSE 连接解耦：**客户端断网不会取消回合**，结果照常落库，事件照常进流。
- 重连带 `Last-Event-ID` 接着收；超出缓冲返回 `error(code=gone)`，客户端改拉历史。
- `GET /sessions/{id}/events` 在会话空闲时也可以挂着，用于接收其他端发起的回合事件（多端同步）。

### 7.4 版本策略

- 路径带主版本 `/v1`。**同一主版本内只做加法**：可以新增字段、事件、错误码，不能删除或改变已有字段的含义。
- 客户端必须忽略不认识的字段与事件（C §2.2 的解析器按此实现），这样服务端加东西不需要客户端同步发版。
- 需要破坏性变更时开 `/v2`，`/v1` 至少保留到最低支持的 App 版本不再调用它为止；服务端按 `User-Agent` 里的 App 版本统计 `/v1` 的调用量来决定下线时间。
- 请求头 `X-App-Version` 必带。服务端可据此对过旧的版本返回 `426 upgrade_required`（错误码表补充见 O §6.2）。

## 8. 内核：DeerFlow 怎么接

### 8.1 历史输入

**修订（2026-11-09）**：上一版的「转录文本」方案作废。详见 `chat-agent-prompt-skill-design.md` 第 2、6 节。

- 不用 `DeerFlowClient` 与 lead agent，改用 DeerFlow 的 SDK 工厂 `create_deerflow_agent`：系统提示词由我们给，返回的 LangGraph 图可以直接传原生多轮 messages。
- 每个回合**无状态**调用，不用 checkpointer；历史以 MySQL 为唯一权威。
- `HistoryWindow` 从最近一条往前取原生 `user`/`assistant` 消息，按 token 预算（默认 6000）或 30 条截断，以完整一问一答为单位。
- 系统提示词按回合计算，由 `PromptMiddleware` 在 `awrap_model_call` 中写入 `request.system_message`，图本身可缓存复用。

### 8.2 模型路由

Java 现状是随机挑一个模型、非流式重试 3 次、只有 3 个模型接了流式。重做改成配置化场景路由（LiteLLM `routing.yaml`），按能力打标签：

| 场景 | 要求 | 候选（按顺序故障转移） |
|---|---|---|
| `chat` | 流式 | DeepSeek → 通义 → 豆包 → GPT |
| `solve_text` | 流式、强推理 | DeepSeek（推理）→ GPT → 通义 |
| `solve_vision` | 视觉输入 | 通义视觉 → 豆包视觉 → GPT |
| `title` | 便宜、短输出 | 轻量模型 |
| `memory_extract` | 结构化 JSON | 轻量模型 |

- 故障转移**只在第一个 token 之前**生效：之前失败就换下一个；开始吐字后失败，发 `error`，部分内容落库，不换模型重来（否则用户会看到前后矛盾的两段话）。
- 具体名单以网关实际可用的模型为准，上线前逐个验证流式与视觉能力。Java 现有的接入：DeepSeek（三条通道）、通义、豆包、Gemini、GPT-4、Kimi。

### 8.3 必须先解决的阻塞项

1. 环境里 `mcp` 是 2.3.0，`McpError` 更名为 `MCPError`，`deerflow` 包导入失败（工厂与客户端在同一个包里，换入口也绕不开）。要锁依赖到可导入的版本（需实测）。
2. `pyproject.toml` 没有声明 `deerflow`、`fastapi`、`uvicorn`、`sqlalchemy`、`redis` 等运行时依赖，要补齐并锁版本。
3. `create_container()` 默认 `FakeBrain`，生产会静默回退。改为 prod 未配置大脑即拒绝启动，只有 `dev`/`test` 允许 Fake。
4. 加冒烟测试：真实 `create_deerflow_agent` 图 + 本地假 OpenAI 端点，在**没有 DeerFlow 配置文件**的环境里跑通一轮流式，防止再出现「测试全绿、真实路径从没跑过」。

## 9. 解题

一个 skill（`skills/public/problem-solving`），不是独立接口。

- 输入：文字题或图片附件（先 `POST /uploads` 拿 `upload_id`，图片存对象存储，回合只传 id）。
- 路由：有图片走 `solve_vision`，纯文字走 `solve_text`。
- 流程：读题 → 分析 → 分步推理 → 校验 → 答案，每步发 `step` 事件。
- 存储：助手消息 `kind='solve'`，正文是完整解答，步骤结构进 `meta`，历史回放可还原。
- 语言：题目什么语言就用什么语言解答；阿拉伯语题用阿拉伯语，数学符号用通用写法，客户端按 `dir` 排版（公式保持 LTR）。
- 与连续对话的交互：解题回合有多个模型调用步，期间的输入走 `steered` 会真正改变后续推理（第 6.2 节）。但这有代价：把新指令插进「已经算到一半的推理」里，可能让结论前后矛盾。所以**解题 skill 默认关闭 steer**，只接受排队；用户可以在设置里打开。这是 skill 级的能力声明（`steerable: false`），由回合状态机读取。

## 10. 记忆：多应用共享（memory_hub）

三个应用要用同一套外部记忆：**浅聊/角色扮演（companion）**、**job-come**，将来可能更多。
所以记忆不写进 `products/chat`，而是抽成独立库：`memory_hub`。

### 10.0 后端选型：三个方案都评估了

| 方案 | 优势 | 问题 | 结论 |
|---|---|---|---|
| **mem0 + Qdrant**（本设计原方案） | 轻，一个库 + 一个向量库；Python 原生；API 简单 | 只有扁平的 fact 抽取，没有会话分层；没有知识库；没有现成的多应用模型 | **P0–P3 用它**，能最快跑通 |
| **TencentDB Agent Memory**（腾讯开源） | L0 会话 / L1 原子 / L2 场景 / L3 人格四层，正是「Her」要的画像式记忆；自带 Memory Hub 的多 Agent 装配与 ACL；带知识库（Wiki + CodeGraph）；PersonaMem 48%→76% | 三套服务（Memory Core / Hub / Panel）+ MongoDB/向量库 + 两套 LLM 参数，部署面比整个 agent-api 还大；Node ≥ 22；Python SDK 成熟度待验证；v3 还在快速迭代 | **P4 评估接入**，见 10.6 |
| **Markdown 摘要文档** | 零依赖，人可读，改起来直观 | 不可检索、并发写冲突、无法按用户隔离、随会话增长会撑爆上下文；本质是「人肉记忆」 | **不单独用**，可以作为 L3 人格层的可读投影（见 10.6） |

**决策**：先用 mem0 把整条链路跑通（记忆不是这个阶段的瓶颈），把 `memory_hub` 的端口设计成后端可换。
TencentDB 的那套分层与知识库，正好对应角色扮演要的「她记得你这个人」；等 P4 用真实数据评测后再决定是否整体换过去。

### 10.1 隔离模型

mem0 原生只认 `user_id` / `agent_id` / `run_id` 三个标识符（已核对官方文档；不同向量库支持度不同，**Weaviate 只过滤这三个**，其余静默丢弃）。所以：

| 层级 | mem0 字段 | 取值 |
|---|---|---|
| 应用 | 编进 `user_id`（复合） | `companion:{user_id}` / `jobcome:{user_id}` |
| 用户 | `user_id` 的后半段 | 业务用户 id |
| 角色 / 主体 | `agent_id` | 角色 id（companion）、职位或候选人（job-come） |
| 会话 | `run_id` | 会话 id |
| 记忆类型 | metadata | `kind`：`fact` / `preference` / `event` / `resume_fact`… |

**应用隔离靠复合 `user_id`，不靠 metadata 过滤。** 原因：metadata 过滤在某些后端不可用（Weaviate 全丢，Chroma 降级），而 `user_id` 在所有后端都是原生过滤。metadata 里仍然写一份 `app`，只用于排查与统计。
这是关键决定：只要隔离依赖 metadata，换一个向量库就会静默跨应用串数据。

同样的约束适用于换后端：不管是 mem0、TencentDB 还是自研，「应用 + 用户」这一层隔离必须是存储原生支持的过滤字段，不能只写在 metadata 里。

### 10.2 物理隔离

Qdrant 每个应用一个 collection：`mem_companion`、`mem_jobcome`。

理由：不同应用的 embedding 模型可能不同；删库、备份、迁移按应用独立；单个应用的数据量不影响另一个。
collection 在 Qdrant 里很便宜，不值得为了省一个 collection 去做软隔离。

### 10.3 接口

```python
hub = MemoryHub.from_config("config/memory.yaml")
mem = hub.for_app("companion")     # 返回 MemoryPort 形状的客户端

await mem.add(user_id, items)      # 内部自动加 app 前缀与 metadata.app
await mem.search(user_id, query, limit=5, kinds=["fact"])   # 不按 agent_id 过滤：记忆跨角色共享
await mem.list_for_user(user_id, limit=20, offset=0)
await mem.delete_one(user_id, memory_id)
await mem.delete_user(user_id)     # 账号注销：先逐条删，再 delete_all 兜底
```

- `for_app` 做的是作用域绑定，不是新建连接：同一进程内共享底层客户端池。
- 应用自己定义记忆类型（`kinds`），`memory_hub` 只管存取与隔离，不理解业务语义。
- 上层（companion 的内核）只依赖 `MemoryPort` 协议，换后端不改调用方。
- 已有 `memory/mem0.py` 的适配逻辑（同步/异步客户端、翻页去重、删除校验归属）直接演进为 `memory_hub` 的一个后端，不重写。

### 10.4 配置

```yaml
# config/memory.yaml
default_app: companion
apps:
  companion:
    backend: mem0
    collection: mem_companion
    qdrant_token_env: QDRANT_TOKEN_COMPANION   # 只能访问 mem_companion
    embedding: {model: bge-m3, dim: 1024}
    extraction: {scenario: memory_extract}
  jobcome:
    backend: mem0
    collection: mem_jobcome
    qdrant_token_env: QDRANT_TOKEN_JOBCOME     # 只能访问 mem_jobcome；只配置在 job-come 的环境里
    embedding: {model: bge-m3, dim: 1024}
    extraction: {scenario: memory_extract}
qdrant: {url_env: QDRANT_URL}
# 每个应用自己的凭据，见 10.7；这里不再有一个全局的 api_key
```

### 10.5 接口（HTTP）

挂到 `/api/agent/v1/memory/*`：事实与重要日子的增删改查。复用现有 `MemoryApi` 的用户隔离、404 语义、分页夹取，都已测过。
记忆跨角色共享，每条记录来源角色与来源消息；删除是真删除（向量同步删除）。召回由 `memory_recall` 中间件在回合前完成。
路径以 §7.1 为准（`/memory/facts`、`/memory/events`）；现有代码 `server/memory_api.py` 的 `/companion/memory`、`/companion/events` 在 P0 改名。

### 10.7 隔离要强制，不能靠自觉（修订，评审 M12）

`memory_hub` 是一个库，三个应用各自在自己的进程里使用它。如果三个应用共用一个 Qdrant 凭据，任何一个应用都能读其他应用的 collection——「两个应用的数据互不可见」就只是约定。所以：

- **字段与语义**：
  - `user_id`（复合 `app:uid`）是隔离字段，必须是存储原生过滤（10.1）。
  - `agent_id` 只用于记录来源角色，**召回不按它过滤**（记忆跨角色共享）。
  - `kinds` 是普通的元数据过滤。我们的后端是 Qdrant，它完整支持 payload 过滤，所以可以用；这与「隔离不能依赖元数据」不矛盾——`kinds` 过滤失效的后果是召回不准，不是跨用户泄露。
- **凭据按应用分开**：Qdrant 开启 JWT RBAC，每个应用一个只能访问自己 collection 的令牌（`apps.<name>.qdrant_token_env`）。companion 的进程只持有 `mem_companion` 的令牌，job-come 的进程只持有 `mem_jobcome` 的令牌。
- **验证**：P4 的验收用例直接拿 companion 的令牌去读 `mem_jobcome`，必须被 Qdrant 拒绝；只在应用代码里断言是不够的。
- Qdrant 的 JWT RBAC 按 collection 授权的能力需要在 P4 用实际部署的版本确认；如果不满足，退路是每个应用一个独立的 Qdrant 实例。

### 10.6 分层记忆与知识库（P4，为「Her」准备）

mem0 只覆盖「原子事实」这一层。角色扮演要的「懂用户的人」，需要更完整的层：

| 层 | 内容 | 谁产出的 | 存储 |
|---|---|---|---|
| L0 会话原文 | 原始对话 | 已有 `chat_message` | MySQL（已有） |
| L1 原子事实 | 事实、偏好、约束、事件 | mem0 抽取（已有中间件） | mem0 |
| L2 场景 | 「他这三个月在准备面试」这类上下文块 | 定期汇总任务 | mem0，`kind=scenario` |
| L3 人物画像 | 稳定的人格特征与沟通偏好 | 定期汇总任务 | 见下 |
| 知识库 | 用户上传的文档、codegraph | 用户 | 独立（TencentDB 的 MemoryKnowledge 或自建） |

**L3 用 Markdown 文档**，这是你提的第三种方案——但它不该单独当记忆用，而适合作为**可读、可编辑的投影**：

- 存 MySQL 的 `persona_profile` 表：一人一条 Markdown 正文 + 版本 + 更新时间。
- 由定时任务从 L1/L2 汇总生成，用户可以在 App 里直接看、直接改（「她眼里的我」页面）。
- 对话时把这份 Markdown 注入系统提示（几百字），提供稳定的「她记得你这个人」的感觉。
- 优点：用户可读可改，可解释性极强；缺点：不参与检索，所以不能替代 L1 的向量召回——两者并存，各管一段。

这就是为什么「Markdown 摘要文档」不单独用：它是 L3 的交付形态，不是整个记忆系统。

评估 TencentDB 的触发条件（P4 做）：
- 用真实会话评测 mem0 方案在 PersonaMem 类任务上的表现；如果明显不足，再接入。
- 接入时 `memory_hub` 加一个 `backend: tencentdb`，隔离模型不变（它的 Team/User/Agent ACL 能直接映射我们的 app/user/agent 三层）。
- 它的知识库能力只在「用户上传文档」这个需求成立时才需要，浅聊阶段不做。

## 11. 为角色扮演预留的扩展点

只有三个：

1. **能力集**：`CapabilityRegistry.for_product("chat" | "roleplay")`。浅聊注册 `problem-solving` 与记忆工具；角色扮演再加动作、形象指令。
2. **传输适配器**：`TurnTransport` 接收 `TurnRequest`、发出 `TurnEvent`，含 `steer()` 占位。浅聊是 SSE，角色扮演是 LiveKit，共用同一个回合管线与状态机。
3. **中间件链**：顺序固定（安全 → 记忆召回 → 事件抽取 → 人设 → 授权 → 成本 → 观测），产品只能声明启用哪些，不能改顺序。

形象、主动性、语音只存在于 `products/roleplay`，内核不感知。

## 12. 配置

| 变量 | 说明 |
|---|---|
| `COMPANION_ENV` | `dev` / `test` / `prod`，prod 启用全部启动检查 |
| `COMPANION_AUTH_VERIFIER` | `redis_token`（生产）/ `allow_all`（仅 dev） |
| `AUTH_REDIS_URL` | 读 Java 登录态（与事件流可用同一实例，不同 db） |
| `EVENTS_REDIS_URL` | 会话事件流、运行锁、队列热路径 |
| `COMPANION_MYSQL_URL` | `agent` 库 |
| `COMPANION_LLM_ROUTING_PATH` / `_API_BASE` / `_API_KEY` | 模型路由与网关 |
| `COMPANION_MEMORY_CONFIG` | `config/memory.yaml` |
| `QDRANT_URL` / `QDRANT_API_KEY` | 向量库 |
| `COMPANION_UPLOAD_*` | OSS 桶与前缀 |
| `COMPANION_DEFAULT_LOCALE` | 默认 `zh-CN` |
| `COMPANION_MAX_RESTARTS` | 一个回合因合并而重跑的上限，默认 2（§6.3） |
| `COMPANION_STEER_BUDGET` | 一个回合最多注入几次，默认 3（§6.4） |
| `COMPANION_QUEUE_MAX` | 每会话队列上限，默认 20 |

## 13. 实施阶段

按你的要求，测试在全部开发完之后统一跑。每个阶段同时包含后端、worker 与客户端的工作，阶段结束时整条链路可用。
（P = chat-agent-prompt-skill-design.md，T = chat-agent-tool-mcp-design.md，O = chat-agent-ops-design.md，C = chat-agent-client-design.md，A = chat-agent-architecture.md）

| 阶段 | 后端 | worker / 运维 | 客户端 | 完成标志 |
|---|---|---|---|---|
| P0 地基 | 锁依赖（含 `mcp`）；包结构迁移与 import-linter（A §7）；`create_deerflow_agent` 工厂接入与冒烟（P §2.5 三项实测）；`PromptMiddleware` 与平台层（P §6）；MySQL schema（§3）+ Alembic；`RedisTokenVerifier`；模型路由场景补齐；启动检查 | 删 `config/deerflow/config.yaml`；`/etc/agent-api/env`；nginx 与 systemd（P §3）；结构化日志与指标骨架（O §4） | `AgentApi`、`AgentEventSource`（C §2.2），能连上并打印事件 | 在没有 DeerFlow 配置文件的环境里，用真实模型跑通一轮流式；import-linter 全绿 |
| P1 连续对话 | 回合状态机（started/merged/steered/queued）、Redis 回合控制面（§6.2）、合并即重跑、队列与排空、撤回、重试与继续、运行锁、事件流（合并增量、首连快照、续传）、取消与重新生成；图内中间件链（T §1，全部异步钩子）、`SteerMiddleware` | `agent-worker` 进程与任务表（O §2.1）；`turn.sweep`、`queue.drain_orphans`；限流（O §7） | `reduce` 状态机、发送与接收解耦、排队/合并/插话的气泡、连接状态机（C §3–4） | 连发 5 条只得到一个连贯回答；**发消息与取消的请求落在别的进程上也生效**；多步回合中 steer 生效、未注入的转入队列；回合进行中打开会话能看到已产出内容；断网重连接着收；杀掉一个 API 进程后卡死回合在 5 分钟内被回收 |
| P2 角色与语言 | 目录与内置人设迁移（P §4）、用户角色 CRUD、注入检测、`zh-CN`/`en`/`ar` 与 `dir` | 阿拉伯语展示字段机翻产出 | 角色选择换数据源、「我的角色」、RTL 与公式 LTR（C §5–6） | 阿拉伯语会话在真机上排版正确；用户人设里的注入样例被拦截 |
| P3 解题与工具 | `problem-solving` skill、视觉路由、`step` 事件；ToolSpec、授权、审计、确认闭环、首批工具（T §2）；上传（O §5） | `confirmation.expire`、`upload.gc`；确认记录与审计的清理 | 上传、步骤折叠、确认卡片（C §3.4、§7） | 文字题与图片题样例集通过；CONFIRM 工具在确认前不执行；图片 EXIF 被去除 |
| P4 记忆 | `memory_hub`（§10）、Qdrant 双 collection、记忆接口；MCP 接入层（T §3，先不接外部 server） | `memory.extract`、`memory.summarize_scenario`、`persona.rebuild`；`account.purge`（O §3）；备份（O §11） | 「她记得的」页面（C §8） | 两个应用的数据互不可见；注销后所有存储里查不到该用户；TencentDB 评测给出是否换后端的数据 |
| 之后 | 角色扮演（LiveKit、形象、主动性、语音）；job-come MCP 互通 | `agent-livekit` 进程 | 陪伴界面 | 见 R §17 |

## 14. 测试策略

- 内核：中间件顺序（回合外与图内两套）、取消、故障转移（只在首 token 前）、语言回退。
- **连续对话**（重点）：首 token 前到达的输入触发重跑且并入同一回合；`restarts` 到 2 后转入队列；执行过工具后不再合并；判定与投递原子（并发发送不出现竞态）；**发送、取消、合并请求落在非回合所在进程时生效**；steer 未被注入时回合结束转回队列；一批排空合并成一个回合；积压深时分批链式排空；去重；队列上限；排空失败原样塞回；撤回；取消不清队列；多副本抢锁；`SteerMiddleware` 注入后不重复回答、`steer_budget` 到顶后降级为排队、`steerable=false` 的 skill 不吃 steer；队列状态的非法转移被拒绝。
- 接口：用户隔离、分页边界、404 语义、幂等、版本头。
- SSE：`Last-Event-ID` 跨回合续传、心跳、`gone`、未知事件被客户端忽略。
- 身份：非法键格式一律 401；`pwd` 不出现在日志与异常里。
- 记忆：两个 app 的 `user_id` 前缀隔离；删账号后搜不到。
- 工具与 MCP：见 T §5。
- 后台任务：每种任务执行两次结果不变（幂等）；租约过期的任务被重新认领。
- 真实路径：真实 `create_deerflow_agent` 图 + 假 OpenAI 端点的集成测试，进 CI。
- **端到端**：docker compose 起 MySQL、Redis、Qdrant、假 OpenAI 端点与 agent-api、agent-worker；用一个脚本客户端走完「建会话 → 连发 3 条 → 断开重连 → 解题 → 确认工具 → 删记忆 → 注销」，校验每一步的事件序列与数据库状态。Android 端用同一套环境做手工冒烟，不在 CI 里跑真机。

## 15. 风险与待确认

1. **steer 的边界**：`before_model` 只能在模型调用之间注入，不能打断正在生成的字流。纯聊天回合里它多半退化成 `merged`，只有多步回合（解题、检索）才有增益。这不是缺陷，是这一层的物理上限；产品上不要承诺「边听边说边改」。
2. **合并的感知**：首 token 前补发的话会被合并进同一个回答，用户可能觉得「我发的第二条没被单独回答」。UI 需要给「已合并」的提示（C §3.2）。
8. **合并重跑的费用**：被中止的模型调用仍计输入 token；用 `turn_restart_total` 监控频率（§6.3）。
3. **阿拉伯语翻译质量**：机翻只是起步，上线前需要母语者校对，尤其是 283 个角色的名称。
4. **视觉与流式能力**：第 8.2 节候选要逐个实测，不能凭模型名推断。
5. **转录式历史的上限**：长会话输入会变长，后续需要摘要或换原生多轮消息。
6. **mem0 版本与向量库组合**：不同版本对 `indexed_fields` 与过滤语法支持不同，选型时要用 P4 的隔离测试验证，不能只看文档。
7. **记忆后端可能换**：TencentDB Agent Memory 的分层（L0–L3）与知识库明显比 mem0 更贴「Her」的长期目标，但部署面大、仍在快速迭代。`memory_hub` 的端口要保证换后端不改上层；P4 用真实数据评测后再定。
