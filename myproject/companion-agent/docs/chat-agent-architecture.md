# 浅聊 Agent 架构：分层、模块、包结构约束、流程

日期：2026-11-09。配套文档：`chat-agent-design.md`（业务与协议设计）、`2026-11-06-roleplay-design.md`（角色扮演）。

本文回答四个问题：系统分成几层、每层有哪些模块、包与包之间允许什么依赖、关键流程怎么走。
所有约束都是可校验的（第 5 节的 import-linter 契约进 CI），不是口头约定。

## 1. 分层

四层 + 一个组合根。依赖只能自上而下，跨层只能经过端口。

```
┌──────────────────────────────────────────────────────────────┐
│ L1 接口层  api/                                               │
│   协议适配：HTTP 路由、SSE 编码、DTO 校验、错误码映射          │
│   只做「协议 ↔ 用例」的翻译，不含业务判断                      │
├──────────────────────────────────────────────────────────────┤
│ L2 应用层  app/                                               │
│   用例编排：一个用例一个入口函数，事务边界在这里               │
│   回合的 disposition 判定、队列排空、角色 CRUD、记忆 CRUD       │
├──────────────────────────────────────────────────────────────┤
│ L3 领域层  domain/                                            │
│   纯逻辑：回合管线、中间件链、队列状态机、角色目录、i18n、策略  │
│   无 I/O、无框架、不 import fastapi / sqlalchemy / redis        │
├──────────────────────────────────────────────────────────────┤
│ L4 基础设施  adapters/                                        │
│   端口实现：MySQL、Redis、mem0、DeerFlow、OSS、LiteLLM         │
└──────────────────────────────────────────────────────────────┘
        ports/   端口定义（Protocol），被 L2/L3 依赖，由 L4 实现
        bootstrap/  组合根：唯一同时知道四层的地方
        products/    产品装配：声明能力集与中间件启用，不写实现
```

### 1.1 每层的职责与禁止事项

| 层 | 职责 | 禁止 |
|---|---|---|
| `api/` | 解析请求、校验、调用用例、把结果编码成 HTTP/SSE | 判断业务规则；直接访问数据库或缓存；import `adapters` |
| `app/` | 用例编排、事务边界、调用领域逻辑、组装端口调用 | 写 SQL；拼提示词；做协议编码；import `api` |
| `domain/` | 回合管线、策略、状态机、纯计算 | 任何 I/O；import `fastapi`/`sqlalchemy`/`redis`/`httpx`；读环境变量 |
| `adapters/` | 实现端口 | 被 `domain` 直接 import；包含业务判断（只做数据形状转换） |
| `bootstrap/` | 装配、启动检查 | 被任何层 import |
| `products/` | 声明产品：用哪些 skill、启用哪些中间件 | 包含实现；被 `domain` import |

### 1.2 依赖矩阵

`✓` 允许，`✗` 禁止，`→` 只能经端口（Protocol）调用。

| 从 \ 到 | api | app | domain | adapters | bootstrap | products | ports |
|---|---|---|---|---|---|---|---|
| **api** | ✓ | ✓ | ✓（只用 DTO 无关的类型） | ✗ | ✗ | ✗ | ✓ |
| **app** | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| **domain** | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ |
| **adapters** | ✗ | ✗ | ✓（只为实现端口所需的数据形状） | ✓ | ✗ | ✗ | ✓ |
| **bootstrap** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **products** | ✗ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ |
| **ports** | ✗ | ✗ | ✓（复用领域模型） | ✗ | ✗ | ✗ | ✓ |

三条容易违反、必须写进契约的规则：

1. **`domain` 不 import `adapters`。** 领域只知道端口，不知道实现。
2. **`api` 不 import `adapters` 与 `bootstrap`。** 路由拿到的依赖全部由 FastAPI `Depends` 注入。
3. **没有任何包 import `bootstrap`。** 组合根是程序的入口，不是库。

## 2. 模块设计

### 2.1 端口（`ports/`）

端口是领域与应用层对世界的全部假设。每个端口一个文件，只有 `Protocol` 与数据形状，没有实现。

| 端口 | 方法（要点） | 实现 |
|---|---|---|
| `BrainPort` | `start_turn(request) -> BrainTurn`，`BrainTurn.tokens/cancel` | `adapters/brain/deerflow.py`、`fake.py` |
| `MemoryPort` | `add / search / list_for_user / delete_one / delete_user` | `memory/mem0/`、`fake.py` |
| `SessionStore` | `create / get / list_for_owner / rename / soft_delete` | `adapters/store/mysql/` |
| `MessageStore` | `append / list_before / get / edit / soft_delete` | 同上 |
| `TurnStore` | `create / mark_running / finish(state, usage)` | 同上 |
| `QueueStore` | `enqueue / pop_batch / requeue / clear / size` | 同上（MySQL 为权威），热量在 Redis |
| `RoleStore` | `list_system / get / list_owned / create / update / delete` | 同上 |
| `EventStream` | `append(turn_id, event) / read_after(session_id, last_id) / expire` | `adapters/cache/redis/` |
| `RunLock` | `acquire(session_id, ttl) / renew / release` | 同上 |
| `LoginTokenStore` | `resolve(token) -> UserRef \| None` | `adapters/auth/redis_token.py` |
| `ModelRouter` | `for_scenario(name) -> ModelSpec`，支持故障转移链 | `adapters/llm/litellm.py` |
| `ObjectStorage` | `put / presign_get / delete` | `adapters/storage/oss.py` |
| `Clock` | `now()` | `adapters/clock/system.py`、`fake.py` |

`Clock` 单独成端口，是因为合并重跑上限、队列 TTL、租约续期、确认过期都依赖时间，测试里必须能拨表。

### 2.2 领域模块（`domain/`）

| 模块 | 职责 | 关键类型 |
|---|---|---|
| `domain/turn/` | 回合管线与状态机 | `TurnRequest`、`TurnEvent`、`TurnState`、`TurnPipeline` |
| `domain/turn/queue.py` | disposition 判定规则、队列状态机、排空策略 | `Disposition`、`TurnPhase`、`QueueTransition`、`DrainPolicy` |
| `domain/turn/steer.py` | steer 收件箱与注入块渲染 | `SteerInbox`、`SteerBudget`、`render_steer_block` |
| `domain/turn/control.py` | 回合控制消息（merge / steer / cancel）的形状 | `ControlMessage` |
| `domain/middleware/` | 中间件链（顺序固定） | `MiddlewareChain`、各 `*Middleware` |
| `domain/roles/` | 角色模型、id 命名空间、多语言回退 | `Role`、`RoleId`、`LocaleResolver` |
| `memory/` | 召回策略、记忆分类 | `RecallPolicy`、`MemoryKind` |
| `domain/tools/` | 动作授权模型 | `Permission`、`ActionSpec`、`ToolRegistry` |
| `domain/text/` | 断句、事件渲染、流式分块 | `SentenceSplitter`、`render_*` |
| `domain/session/` | 会话与消息的领域规则 | `Message`, `QueueLimits` |

**中间件分两套，顺序在这里、且只在这里定义**（修订，评审 M11；分工的依据见 T §1）：

```
TURN_CHAIN（回合外，我们自己的 MiddlewareChain，包在整个回合外面）：
  memory_recall → event_extraction → persona_guard → cost → observability

GRAPH_CHAIN（图内，DeerFlow/LangChain AgentMiddleware，只实现异步钩子）：
  PromptMiddleware → ToolVisibilityMiddleware → SteerMiddleware
  → ToolAuditMiddleware → ToolAuthorizationMiddleware
  （各自的锚点见 P §2.4）
```

- **`safety` 不在任何一条链里**，在 `app/chat/submit.py` 中对**每一条**用户输入执行，发生在 disposition 判定之前。这样合并、插话、排队三条路径的文本都被检测过；如果放在回合外链里，中途注入的文本就绕过了它。
- `persona_guard` 是**输出后检查**（看助手回复是否跳出人设），不是输入关卡。
- `tool_authorization` 必须在图内：工具调用发生在图内部，回合外链看不到。
- 产品可以声明两条链各启用哪些，不能改顺序。装配时校验，不一致就拒绝启动。

### 2.3 应用模块（`app/`）

| 模块 | 用例 |
|---|---|
| `app/chat/sessions.py` | 建会话、列表、改名、软删；创建时解析并固化 `role_id` 与 `locale` |
| `app/chat/submit.py` | **发消息**：幂等检查 → disposition 判定 → 合并/steer/入队 → 返回回执 |
| `app/chat/turn_runner.py` | 执行一个回合：取锁 → 建回合 → 跑管线 → 落库 → 发事件 → 排空 |
| `app/chat/drain.py` | 排空一批队列，合并成一个回合；失败原样塞回 |
| `app/chat/roles.py` | 角色列表/详情/自建 CRUD |
| `app/chat/solve.py` | 解题用例：选 skill、选模型场景、发 `step` 事件 |
| `app/chat/uploads.py` | 附件上传与校验 |
| `memory/service.py` | 记忆 CRUD（复用现有 `MemoryApi` 的逻辑） |
| `app/proactive/` | 主动性（角色扮演启用，浅聊不装配） |

用例函数的形状统一：`async def execute(ctx: AppContext, cmd: Command) -> Result`。
`AppContext` 是一个只含端口的 dataclass，由组合根构造；用例不拿容器、不拿配置、不拿全局。

### 2.4 接口模块（`api/`）

| 模块 | 职责 |
|---|---|
| `api/http/routers/*.py` | 一个资源一个文件：`sessions`、`messages`、`roles`、`memory`、`uploads`、`health` |
| `api/http/deps.py` | 身份依赖（`current_user`）、分页参数、`AppContext` 注入 |
| `api/http/errors.py` | 领域异常 → HTTP 状态码的单点映射 |
| `api/sse/encoder.py` | `TurnEvent` → SSE 帧（`id:` / `event:` / `data:`）、心跳 |
| `api/sse/stream.py` | 会话事件流端点：`Last-Event-ID` 续传、断线检测 |
| `api/schema/*.py` | pydantic DTO，与领域模型分离 |
| `api/livekit/` | 角色扮演（后期） |

**DTO 与领域模型分离**：`api/schema` 里的类只描述线格式，`to_domain()` / `from_domain()` 做转换。
理由：领域模型改动不该直接改变对外协议；反过来，协议里的兼容性字段也不该污染领域。

### 2.5 产品装配（`products/`）

```python
# products/chat.py
CHAT = Product(
    name="chat",
    skills=("problem-solving",),
    turn_middlewares=("memory_recall", "event_extraction", "persona_guard", "cost", "observability"),
    graph_middlewares=("prompt", "tool_visibility", "steer", "tool_audit", "tool_authorization"),
    tools=("recall_facts", "recall_events", "remember_fact", "remember_event",
           "read_skill_reference", "get_current_time"),
    transport="sse",
)
```

产品只声明，不实现。组合根读声明、校验顺序、装配。

## 3. 目标包结构

```
companion-agent/
├── src/companion/
│   ├── __main__.py                  # uvicorn 入口
│   ├── config.py                    # 环境变量 → Settings（只被 bootstrap 读）
│   │
│   ├── domain/                      # L3 领域层：纯逻辑，零 I/O
│   │   ├── turn/{models,pipeline,queue,steer,events}.py
│   │   ├── middleware/{chain,safety,memory_recall,extraction,
│   │   │               persona_guard,tool_auth,cost,observability,render}.py
│   │   ├── roles/{model,catalog,locale}.py
│   │   ├── memory/{policy,kinds}.py
│   │   ├── tools/{spec,registry}.py
│   │   ├── session/{model,limits}.py
│   │   └── text/{splitter,events}.py
│   │
│   ├── ports/                       # 端口：只有 Protocol 与数据形状
│   │   ├── brain.py  store.py  cache.py  memory.py
│   │   ├── auth.py  llm.py  storage.py  clock.py
│   │
│   ├── app/                         # L2 应用层：用例编排
│   │   ├── context.py               # AppContext（只含端口）
│   │   ├── chat/{sessions,submit,turn_runner,drain,roles,solve,uploads}.py
│   │   ├── memory/service.py
│   │   └── proactive/               # 角色扮演才装配
│   │
│   ├── api/                         # L1 接口层
│   │   ├── http/{deps,errors}.py
│   │   ├── http/routers/{sessions,messages,roles,memory,uploads,health}.py
│   │   ├── sse/{encoder,stream}.py
│   │   ├── schema/*.py
│   │   └── livekit/                 # 后期
│   │
│   ├── adapters/                    # L4 基础设施
│   │   ├── brain/{deerflow,fake}.py
│   │   ├── store/mysql/{session,message,turn,queue,role}.py
│   │   ├── cache/redis/{events,lock,queue}.py
│   │   ├── memory/{mem0,memory_hub,fake}/...
│   │   ├── auth/{redis_token,allow_all}.py
│   │   ├── llm/litellm.py
│   │   ├── storage/oss.py
│   │   └── clock/system.py
│   │
│   ├── bootstrap/                   # 组合根
│   │   ├── container.py             # 装配 AppContext
│   │   ├── products.py              # 产品声明加载与校验
│   │   └── checks.py                # 启动检查（fail-closed）
│   │
│   └── products/{chat,roleplay}.py
│
├── roles/                           # 数据资产：目录、人设、skill
├── skills/
├── config/{llm,deerflow,memory}.yaml
├── migrations/                      # Alembic
├── docs/
└── tests/
    ├── unit/{domain,app}/           # 纯单测
    ├── contract/{api,sse}/          # 协议契约
    └── integration/                 # 真实适配器 + 假服务
```

## 4. 包结构约束（可校验）

### 4.1 import-linter 契约

```ini
# .importlinter
[importlinter]
root_package = companion

[importlinter:contract:layers]
name = 分层：api → app → domain，adapters 只能被 bootstrap 与 ports 反向依赖
type = layers
layers =
    companion.api
    companion.app
    companion.domain

[importlinter:contract:domain-pure]
name = 领域层不得依赖任何 I/O 库
type = forbidden
source_modules = companion.domain
forbidden_modules =
    fastapi
    sqlalchemy
    redis
    httpx
    motor
    pymysql
    aiomysql
    livekit
    os
    pathlib

[importlinter:contract:no-bootstrap]
name = 只有入口与组合根可以 import bootstrap
type = forbidden
source_modules =
    companion.domain
    companion.app
    companion.api
    companion.adapters
    companion.ports
forbidden_modules = companion.bootstrap

[importlinter:contract:no-adapters-in-api]
name = 接口层不得直接依赖适配器
type = forbidden
source_modules = companion.api
forbidden_modules = companion.adapters

[importlinter:contract:ports-independent]
name = 端口只依赖领域模型
type = forbidden
source_modules = companion.ports
forbidden_modules =
    companion.api
    companion.app
    companion.adapters
    companion.bootstrap

[importlinter:contract:products-declare-only]
name = 产品包只声明，不实现
type = forbidden
source_modules = companion.products
forbidden_modules =
    companion.adapters
    companion.bootstrap
```

### 4.2 其他规则

| 规则 | 校验方式 |
|---|---|
| 一个模块一个职责，文件超过 400 行就拆分 | CI 里的行数检查 |
| 公共 API 由 `__init__.py` 的 `__all__` 显式导出 | ruff 规则 `PLC0415` + 人工评审 |
| 领域层不读环境变量 | 上面的 `forbidden_modules` 已含 `os` |
| 中间件顺序只在 `domain/middleware/chain.py` 定义 | 装配时断言产品声明与常量表一致 |
| 端口的方法签名变更必须同步改所有实现 | 契约测试导入全部实现并跑 `isinstance` 检查 |

### 4.3 现有代码的迁移映射（含已发现的越界）

实测的包间依赖里，有四处违反上面的契约，必须在 P0 修掉：

| 现状 | 违规 | 处理 |
|---|---|---|
| `middleware/ → actions/` | 领域层依赖动作执行器 | 中间件改依赖 `ports.ToolAuthorizer` 端口，`ActionRegistry` 移到 `adapters/tools` |
| `middleware/ → prompt/` | 领域层依赖提示词组装 | `render_*` 移入 `domain/text/render.py`；`persona_guard` 只依赖渲染函数 |
| `server/ → container / turn_pipeline / conversation / proactive` | 接口层穿过应用层直达实现 | `server` 拆成 `api/http` + `api/sse`；用例移到 `app/chat`；装配移到 `bootstrap` |
| `agent/ → container` | 传输适配器自己装配 | `agent` 改名 `api/livekit`，容器由 `bootstrap` 注入 |
| `middleware/persona_guard.py` 默认 `expected_script="cjk"`，检查的是 `ctx.message`（用户输入） | 不是包依赖越界，是**行为错误**：英语、阿拉伯语会话会被误判；而且它检查的是输入不是回复（评审 m20） | 改为按会话语言选择期望的文字系统，检查助手回复；无法判断语言时不判定 |

模块搬迁对照：

| 现有 | 目标 |
|---|---|
| `conversation.py` + `turn_pipeline.py` | `domain/turn/pipeline.py` |
| `middleware/*` | `domain/middleware/*`（`render` 拆到 `domain/text`） |
| `memory/{port,fake,mem0,extraction}.py` | `memory/port.py` + `memory/*` + `memory/policy.py` |
| `prompt/*` | `domain/roles/*`（角色） + `domain/text/render.py` |
| `actions/*` | `domain/tools/*`（模型） + `adapters/tools/*`（执行） |
| `timeline/*` | `domain/timeline/*` + `adapters/store/*` |
| `proactive/*` | `domain/proactive/*` + `app/proactive/*` |
| `server/*` | `api/http/*`、`api/sse/*`、`app/chat/*`、`bootstrap/*` |
| `agent/*`、`worker.py`、`livekit_bridge.py` | `api/livekit/*` |
| `voice/*`、`text/*`、`llm/*`、`mcp/*` | 见上表按职责归位 |

**搬迁策略**：按契约分批搬，每批搬完跑一次全量测试。先搬 `domain`（无 I/O，最容易），再搬 `adapters`，最后拆 `server`。
不做一次性大迁移——314 个测试是唯一的安全网，一次改完就无法定位是哪一步坏了。

## 5. 流程设计

### 5.1 发消息（disposition 判定）

```
客户端                api/http              app/chat/submit        domain/turn/queue
  │                      │                       │                        │
  │ POST /messages       │                       │                        │
  ├─────────────────────>│                       │                        │
  │                      │ 校验 DTO、取当前用户    │                        │
  │                      ├──────────────────────>│                        │
  │                      │                       │ 1. 幂等：client_message_id
  │                      │                       │    已存在？→ 直接返回旧回执
  │                      │                       │ 2. safety 检测（每条都做）
  │                      │                       │ 3. 落库用户消息，发 message.created
  │                      │                       │                        │
  │                      │                       │ 4. Redis Lua 原子执行：  │
  │                      │                       │    读 sess:{id}:turn.phase
  │                      │                       │    无回合   → started   │
  │                      │                       │    pre_output → merged  │
  │                      │                       │       （写 merge 到 turn:{tid}:ctl）
  │                      │                       │    output 且可 steer → steered
  │                      │                       │       （写 steer 到 turn:{tid}:ctl）
  │                      │                       │    其余     → queued    │
  │                      │                       │       （写 chat_queue）  │
  │                      │                       │                        │
  │                      │                       │ 5. started → 本进程取锁并启动回合
  │                      │                       │    （取锁失败说明并发的另一条刚启动了回合，
  │                      │                       │      回到第 4 步重新判定）
  │                      │                       │ 6. 发 input.merged / input.steered /
  │                      │                       │    input.queued 事件      │
  │<─────────────────────┼───────────────────────┤                        │
  │ 200 {message_id, turn_id, disposition, queue_position}
```

耗时目标：这一步不调模型，只有两次索引查询与一次写，**P99 < 50ms**。
`disposition` 由服务端决定并在响应里返回，客户端不推断、不重试。
跨进程的关键：第 4 步只往 Redis 写控制消息，**不碰任何进程内对象**。回合可能在另一个副本的另一个进程里，由它的控制协程读取控制流（D §6.2）。

### 5.2 回合执行

```
app/chat/turn_runner      domain/turn/pipeline     domain/middleware      adapters/brain
       │                         │                       │                      │
       │ 1. 取运行锁（Redis SET NX PX，租约续期）                              │
       │ 2. 建 turn 记录 state=running                                          │
       │ 3. 发 turn.started（含 merged_message_ids）                            │
       ├────────────────────────>│                       │                      │
       │                         │ 4. 组装 TurnRequest    │                      │
       │                         │    （历史窗口 + 记忆 + 当前输入）             │
       │                         ├──────────────────────>│                      │
       │                         │                       │ safety               │
       │                         │                       │ memory_recall        │
       │                         │                       │ event_extraction     │
       │                         │                       │ persona_guard        │
       │                         │                       │ [steer 注入点]       │
       │                         │                       │ tool_authorization   │
       │                         │                       ├─────────────────────>│
       │                         │                       │                      │ DeerFlow
       │<────────────────────────┼───────────────────────┼──────────────────────┤
       │ message.delta ← 每个 token 一个事件                                    │
       │                         │                       │ cost / observability │
       │ 5. 落库助手消息（空回复不落库）                                        │
       │ 6. message.done + usage（含 steered_message_ids）                       │
       │ 7. 释放锁                                                              │
       │ 8. 队列非空 → 触发排空                                                 │
```

要点：
- 回合在后台任务里跑，与 SSE 连接解耦；客户端断开不取消回合（6.4 节所述）。
- 增量每 50 毫秒或 64 个字符合并成一个事件写进 Redis Stream，同时 `APPEND` 到 `turn:{tid}:text`；SSE 只是订阅者（D §7.3）。
- 回合所在进程同时运行一个**控制协程**：`XREAD BLOCK` 读 `turn:{tid}:ctl`，收到 `merge` 中止当前模型调用并重跑（D §6.3），收到 `steer` 放进本进程的 steer 收件箱，收到 `cancel` 取消回合。取消请求来自哪个进程都一样。
- 回合结束时，steer 收件箱里没被注入的项写回队列（D §6.4）。
- 取消的结果：已产出部分落库（`interrupted=true`），`state=cancelled`，发 `turn.cancelled`。

### 5.3 排空

```
app/chat/drain
  │
  │ 1. QueueStore.pop_batch(session_id, limit=10)   ← 一批，不是全部
  │    空 → 返回
  │
  │ 2. 合并成 <followups-while-busy> 输入块
  │    按 id 升序，escape(quote=False)，换行对齐
  │
  │ 3. 起一个正常回合（turn_runner）
  │    失败（模型不可用/取锁失败）→ 3a. requeue 原样塞回队首，等下次
  │
  │ 4. 回合结束后再查队列：还有内容 → 回到 1（链式，不一次吞完）
```

不一次吞完整个积压，是为了避免拼出一个超长输入把上下文撑爆；链式排空让每个回答都有合理的边界。

### 5.4 SSE 首连与重连

```
首连：GET /sessions/{id}/events
  │ 没有 Last-Event-ID：
  │   会话有运行中的回合 → 先发 turn.snapshot（读 turn:{tid}:text 与步骤），再实时订阅
  │   没有 → 直接实时订阅
  │ → 200 text/event-stream，立刻发一条 : keepalive 表明通道可用
  │ 不发完整历史：历史走 GET /messages；快照只补「正在进行的这一个回合」

重连：GET /sessions/{id}/events  +  Last-Event-ID: 42
  │ 1. EventStream.read_after(session_id, 42)
  │    有 → 逐条补发，然后转入实时订阅
  │    无（超出 MAXLEN 或已过期）→ 发 gone 事件，客户端改拉历史
  │
任何时候：每 15 秒一条 : keepalive
客户端断开：不取消回合；30 秒无连接也不停止回合
进程停机：先发 reconnect 事件并关闭所有长连，再进入 uvicorn 停机（P §3.5）
```

为什么「首连不发历史」：历史走 `GET /messages` 分页拉，SSE 只负责增量。混在一起会让客户端要处理两套数据形状。

### 5.5 启动检查（fail-closed）

```
bootstrap/checks.py，在 lifespan 启动时按顺序执行：
  1. COMPANION_ENV=prod → 验证器不得是 allow_all
  2. prod → BrainPort 不得是 Fake
  3. 产品声明的中间件顺序与常量表一致
  4. 角色目录加载：系统 id 不得以 u_ 开头（命名空间校验）
  5. 端口实现齐全：所有 Protocol 都有实现，否则列出缺失项
  6. 数据库迁移版本与代码期望一致（alembic check）
任一失败 → 拒绝启动并打印具体项。不允许「先起来再说」。
```

### 5.6 请求路径上没有的东西

明确列出，避免后来的人「顺手加一下」：

- 请求路径上不建数据库连接池以外的长连接。
- 不在请求路径上调用第二次模型（除解题的显式分步）。
- 不在请求路径上做记忆写入（抽取是中间件里异步落库，失败只记日志，不影响回复）。
- 不在请求路径上生成摘要、画像（这些是定时任务）。

## 6. 与角色扮演的关系

角色扮演复用 L3 与 L2，只替换 L1 的传输适配器：

| 层 | 浅聊 | 角色扮演 |
|---|---|---|
| L1 | `api/http` + `api/sse` | `api/livekit` |
| L2 | `app/chat/*`（不发主动性） | `app/chat/*` + `app/proactive/*` |
| L3 | `domain/*`（同一套） | 同一套 + `domain/avatar`、`domain/proactive` |
| L4 | 同一套适配器 + LiveKit | 同一套 |

`TurnPipeline` 的输入输出与传输无关（`TurnRequest` → `TurnEvent` 流），所以两个产品共用它。
这是分层最大的收益：新增一个传输层不需要碰领域逻辑。

## 7. 落地顺序

1. **P0-a 契约先行**：把 `.importlinter` 加进 CI，先只对**新代码**生效（`api/`、`app/`、`domain/`、`ports/`、`adapters/`、`bootstrap/` 这些新目录），存量代码不动。
2. **P0-b 搬 domain**：无 I/O，最容易搬，搬完跑全量测试。
3. **P0-c 搬 adapters**：端口实现归位，接口签名不变。
4. **P0-d 拆 server**：`api/http` + `api/sse` + `app/chat` + `bootstrap`。
5. **P0-e 契约全量生效**：所有包纳入检查，包括 `products/`。
6. 之后按 `chat-agent-design.md` 的 P1–P4 推进业务。
