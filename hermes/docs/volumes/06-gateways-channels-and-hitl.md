# 卷六 · IM Gateway：启动、会话、收发、忙时、投递与 HITL

> **卷标准**：[`VOLUME_STANDARD.md`](VOLUME_STANDARD.md) · **完成度**：[`MANIFEST.md`](MANIFEST.md)  
> **本卷边界**：包 **`gateway/`**（IM 网关进程）+ 同进程挂上的 **cron 出站**、**hosted room**、**看板调度**。呈现网关 `tui_gateway/` → [卷二](02-surface-and-presentation.md)。审批状态机细节 → [卷八](08-security-and-governance.md)。  
> **权威源码**：`gateway/run.py`（`GatewayRunner`、`start_gateway`）、`run_startup.py`、`run_inbound.py`、`run_busy.py`、`run_turn.py`、`platforms/base.py`、`delivery.py`、`delivery_ledger.py`、`session.py`  
> **相邻卷**：[01](01-platform-and-architecture.md#sec-ch1) · [02](02-surface-and-presentation.md) · [08](08-security-and-governance.md) · [对比](../../compare/CHANNEL_AGENTSCOPE_VS_HERMES.md)

---

## 📋 目录

- [第1章：两个网关与本卷范围](#sec-g1)
- [第2章：启动与连接](#sec-g2)
- [第3章：会话键、活跃槽、Agent 缓存](#sec-g3)
- [第4章：入站一条消息（完整）](#sec-g4)
- [第5章：忙时 `busy_input_mode`](#sec-g5)
- [第6章：出站 Delivery 与 ledger](#sec-g6)
- [第7章：每个门户的设计](#sec-g7)
- [第8章：IM 上的 HITL 审批卡](#sec-g8) — [8.1](#sec-g8-1) · [8.2](#sec-g8-2) · [8.3](#sec-g8-3) · [8.4](#sec-g8-4) · [8.5](#sec-g8-5) · [8.6](#sec-g8-6) · [8.7](#sec-g8-7)
- [第9章：Cron 出站（不经 `_handle_message`）](#sec-g9)
- [第10章：Hosted Room](#sec-g10)
- [第11章：网关里的看板调度](#sec-g11)
- [第12章：和 AgentScope Channel 对照](#sec-g12)
- [第13章：包地图（grep）](#sec-g13)

---

<a id="sec-g1"></a>

## 第1章：两个网关与本卷范围

口语「网关」在仓库里是 **两套 Python 服务**：

| | **呈现网关 `tui_gateway/`** | **IM 网关 `gateway/`（本卷）** |
|--|---------------------------|--------------------------------|
| 启动 | `python -m tui_gateway.entry` / Desktop 后端 | `start_gateway` / `hermes gateway` |
| 听什么 | JSON-RPC：`prompt.submit`、`session.create` | 平台 SDK 推送 / webhook |
| 出站 | `_emit` → stdio 或 WebSocket | `Delivery` → `adapter.send` + **ledger** |
| 忙时 | `queued_prompt` | `_pending_messages` + `busy_input_mode` |
| 谁跑 Agent | 同一呈现网关进程 | **同一 IM 网关进程**（适配器不 import Agent） |

IM **不会** `import` Gateway 循环。启动时 Gateway **把 handler 登记进适配器**；平台推消息后 **回调** `_handle_message`。长连接在 **跑 Gateway 的那个进程**里，没有单独的 channel worker（这是和 AgentScope 的第一差别）。

---

<a id="sec-g2"></a>

## 第2章：启动与连接

入口：`gateway/run.py` 的 `start_gateway(config, …)` → 构造 `GatewayRunner` → `run_startup` 拉适配器、cron、看板 watcher。

```mermaid
sequenceDiagram
    participant CLI as hermes gateway
    participant ST as start_gateway
    participant GR as GatewayRunner
    participant REG as platform_registry
    participant AD as BasePlatformAdapter
    participant CR as cron scheduler
    participant KB as KanbanDispatcher

    CLI->>ST: start_gateway
    ST->>GR: construct
    GR->>REG: load enabled platforms
    loop each adapter
        GR->>AD: set_message_handler
        GR->>AD: connect long-poll or webhook
    end
    GR->>CR: start tick if enabled
    GR->>KB: start watchers if enabled
```

| 符号 | 文件 | 作用 |
|------|------|------|
| `start_gateway` | `gateway/run.py` | 进程入口 |
| `GatewayRunner` | `run.py` Mixin 拼装 | 会话槽、入站、出站、关机 |
| `run_startup.py` | 启动序 | 配适配器、心跳、plugin rewire |
| `platform_registry.py` | 平台名 → 类 | telegram / feishu / weixin / … |
| `connect()` | `platforms/base.py` 子类 | 长连接或 webhook `tcp_site` |

关机：`run_shutdown.py`、`run_shutdown_session_end.py` — 活跃 turn 收尾，ledger 未完成义务尽量送出。

---

<a id="sec-g3"></a>

## 第3章：会话键、活跃槽、Agent 缓存

IM 一条消息必须落到 **一个 `session_key`**，再占 **活跃槽**，再拿到 **`AIAgent`**。

| 概念 | 谁 mint | 用途 |
|------|---------|------|
| **`session_key`** | `_session_key_for_source`（`run.py`）+ `gateway/session.py` 命名空间 | SessionDB 行、busy 字典、ledger |
| **`_active_sessions`** | Runner | 该 key 是否正在 `run_conversation` |
| **Agent 缓存** | `run_agent_cache.py` | 同 key 复用 `AIAgent`，避免每条消息重建 |
| **profile** | `profile_routing.py` | 多 profile 时 key 带命名空间 |

```mermaid
flowchart LR
    EV[MessageEvent]
    SK[_session_key_for_source]
    SLOT[_claim_active_session_slot]
    CACHE[agent cache]
    AG[AIAgent]

    EV --> SK --> SLOT --> CACHE --> AG
```

和呈现层 `sid`（8 位 UI 窗口）**不是同一个 id**。IM 身份是 `session_key`；压缩后 `AIAgent.session_id` 可能转，key 策略见 `gateway/session.py`。

未授权入站：`run_inbound_unauthorized.py`。配对：`pairing.py`。

---

<a id="sec-g4"></a>

## 第4章：入站一条消息（完整）

主路径文件拆开，不是单函数包办：

| 阶段 | 文件 | 函数 |
|------|------|------|
| 适配器收到 SDK 事件 | `platforms/base.py` | 转 `MessageEvent` |
| 入站总入口 | `run_inbound.py` | `_handle_message` |
| 媒体 | `run_inbound_media.py` | 图/语音下载与清洗 |
| 消费 | `run_inbound_consumer.py` | 过滤、slash、是否丢弃 |
| 忙时 | `run_inbound.py` + `run_busy.py` | 见第5章 |
| 真正跑轮 | `run_turn.py` | `_handle_message_with_agent` |
| 插件改写 | `run_plugin_injection.py` | 入站文本 hook |

```mermaid
sequenceDiagram
    participant IM as platform server
    participant AD as adapter
    participant IN as run_inbound
    participant TR as run_turn
    participant A as AIAgent
    participant D as Delivery

    IM->>AD: push
    AD->>IN: _handle_message MessageEvent
    IN->>IN: session_key media slash
    alt busy
        IN->>IN: busy_input_mode branch
    else idle
        IN->>TR: _handle_message_with_agent
        TR->>A: run_conversation
        A-->>TR: final_response
        TR->>D: deliver
        D->>AD: send
        AD->>IM: outbound
        D->>D: record_obligation
    end
```

Slash（`/busy`、`/steer`、`/new`…）在进 Agent **之前** 由网关命令层吃掉一部分；其余当用户文本。

---

<a id="sec-g5"></a>

## 第5章：忙时 `busy_input_mode`

配置：`interrupt`（**默认**）| `queue` | `steer`。用户 `/busy` 切换（`gateway/slash_commands.py`）。

会话已在 `_active_sessions` 时：

| 模式 | 行为 | 源码 |
|------|------|------|
| **interrupt** | 打断当前 `run_conversation`；子 agent / 压缩中可 **降级 queue** | `run_inbound._hm_handle_running_session_message` |
| **queue** | merge 进 `adapter._pending_messages[session_key]`，本轮结束 drain | `BasePlatformAdapter` + `_spawn_drain_task` |
| **steer** | 调内核 `running_agent.steer(text)`，写入 `AIAgent._pending_steer`；失败再落入 `_pending_messages` | `run_busy._hm_steer_agent` |

**queue 的槽在适配器，steer 的槽在正在跑的 Agent。** queue 本轮结束后再开一轮；steer 在本轮工具批之后或下一次组请求前吃掉。对照 [卷一 §2.3.2](01-platform-and-architecture.md#sec-2-3-2)。

这不是 SessionDB 租约等待，也不是 Desktop `queueDelta`。对照 [卷二 §3.0](02-surface-and-presentation.md#30-忙时再点发送用户话排队不是-messagedelta-的-queuedelta)。

活跃会话上的适配器路径：`platforms/base.py` `_handle_message_while_active`。

---

<a id="sec-g6"></a>

## 第6章：出站 Delivery 与 ledger

循环返回 `final_response` 之后，IM **必须**走投递，不能 `print`。

| 类型 | 文件 | 职责 |
|------|------|------|
| `DeliveryTransport` / `DeliveryTarget` / `DeliveryRouter` | `delivery.py` | 按平台切分长度、媒体、路由到哪个 chat |
| `delivery_ledger.record_obligation` | `delivery_ledger.py` | **最终回复必达**：失败重试、进程重启仍欠账 |
| `lifecycle_ledger` | `lifecycle_ledger.py` | 会话生命周期侧义务 |
| `run_delivery_queue_watch` | 同名 | 盯 cron/网关投递队列 |

```mermaid
flowchart LR
    FR[final_response]
    DV[Delivery.deliver]
    AD[adapter.send]
    IM[platform]
    LED[delivery_ledger]

    FR --> DV --> AD --> IM
    DV --> LED
```

和呈现 `_emit` 的差别：IM 出站受平台 API 限制（字数、媒体、风控），所以有 Router + ledger；TUI 是同一条 JSON-RPC 上推 event。

---

<a id="sec-g7"></a>

## 第7章：每个门户的设计

人碰到 Hermes 的每一种方式都是一个门户。内核只有 `run_conversation`。差别只在五件事：**谁持有连接、会话怎么切开、忙时下一句放哪、回复从哪条路回去、危险操作怎么让人点头。**

<a id="sec-g7-shells"></a>

### 7.1 人机壳（不在 `gateway/` 进程里）

这些壳自己持有界面。呈现细节在卷二，这里把设计和 IM 对齐，避免只在总表里留一行。

| 门户 | 连接 | 会话怎么切 | 忙时 | 回复 | 审批 |
|------|------|------------|------|------|------|
| **CLI** `hermes chat` | 本进程 TTY | 终端里当前会话；`-q` 一次一进程 | `_pending_input`；也认 `busy_input_mode` | 终端 callback | 终端提示 `approval_prompt` |
| **TUI** Ink | stdio JSON-RPC → `tui_gateway` | 窗口 `sid`（8 位）映射库 `session_key` | `queued_prompt`，收尾 `_drain_queued_prompt` | `_emit` | 呈现事件，人在 TUI 上点 |
| **Desktop** | 同一条 JSON-RPC，WebSocket 或 stdio | 同 TUI | 同 TUI | `handleMessageStreamEvent` 画气泡 | 同 TUI |
| **Web Dashboard** | Dashboard 页连 `tui_gateway`（远程时是整台 `hermes serve`） | 同 TUI 的 `sid` | 同 TUI | 同 `_emit` | 同 TUI |
| **Compute host** | 父进程仍是呈现网关；子进程跑 Agent | 父进程的 `sid`；父进程 **vouch** 租约给子进程 | 同 TUI，drain 可走 host | 子进程事件镜像回父进程 `_emit` | 父进程表面 |
| **ACP** | IDE 用 Agent Client Protocol 连 `acp_adapter` | 每个 ACP session 一个 Agent | `queued_prompts` | `session_update`，不走 `_emit` | IDE 侧；循环里挂 `step_callback` |
| **Batch** | `batch_runner` worker，无长连接 | 每行一个 task，`platform=batch` | 无（一行跑完即走） | 写结果文件 | 批跑默认无人等着点 |
| **Codex app-server** | 不是入口壳：`api_mode=codex_app_server` 时整轮旁路 | 仍是当前会话 | 原生 `turn/steer` | 走 Codex 传输 | 视该传输 |

CLI / TUI / Desktop 的一轮时序 → [卷二 §3–§4](02-surface-and-presentation.md#3-tui--desktop一轮怎么走完)。Compute host / ACP → [卷二 §11–§12](02-surface-and-presentation.md#11-compute-hostturn-隔离子进程)。Batch / Codex → [卷三第5章](03-runtime-session-and-loop.md#sec-ch5)。

<a id="sec-g7-contract"></a>

### 7.2 IM 与机器门户共用的合同

凡是 `BasePlatformAdapter` 子类，都活在 **同一个 gateway 进程**里：`connect()` 自己收消息，回调 `_handle_message`，不另起 channel worker。

| 合同 | 设计 |
|------|------|
| **会话键** | `build_session_key`（`gateway/session.py`）。形如 `<ns>:<platform>:<chat_type>[:slack scope][:chat_id][:thread][:user]`。私聊按 chat 隔离，没有 chat_id 才退到发送者。群默认按人切开；线程默认共享，除非 `thread_sessions_per_user` |
| **忙时** | 全部走 `busy_input_mode`（interrupt / queue / steer）。槽在适配器 `_pending_messages`；steer 才进内核 `_pending_steer` |
| **出站** | `Delivery` 按平台切长度和媒体，`delivery_ledger` 记必达。例外见下表「回复」列 |
| **审批** | 工具执行前 `register_gateway_notify(session_key)`，人点完 `resolve_gateway_approval`。卡片长什么样由通道决定，卡点不在收消息时 |
| **准入** | 各通道自己的 allowlist / @ / pairing；不过准入的消息进不了 Agent |

Telegram 论坛话题：General 的 thread id 空或 `"1"` 都当根；回复若被剥掉 thread，会钉回这个用户上次活跃的话题，避免 `/model` 这类命令写到另一把钥匙上。

<a id="sec-g7-channels"></a>

### 7.3 每条通道只写和合同不同的地方

插件在 `plugins/platforms/<name>/`，仓内适配器在 `gateway/platforms/`。登记：`platform_registry.py`。

| 通道 | 连接 | 和公共合同的差别 |
|------|------|------------------|
| **Telegram** | `python-telegram-bot` 长轮询，或带 secret 的 webhook | 话题/thread 进会话键；可流式改自己的消息；审批用 inline keyboard |
| **Discord** | discord.py 网关 | 频道里第一条会按「即将进入的线程」切键，后续跟帖才能对上；语音模式、角色鉴权私聊 |
| **Slack** | slack-bolt **Socket Mode**（要 bot token + app token） | 会话键比别人多一截 workspace `scope_id`；审批是 Block Kit |
| **飞书 / Lark** | 官方 SDK，WebSocket 或 webhook；`FEISHU_DOMAIN` 分中国/国际 | 群里要 @ 才说话；文档评论、会议邀请也是入站事件 |
| **钉钉** | Stream Mode SDK | 群 @、自由回复会话；cron 可走静态机器人 webhook |
| **企业微信** | 两条：`wecom` 智能机器人 WebSocket；`wecom_callback` 自建应用 HTTP + AES | 两个平台名，两套密钥，会话键前缀不同 |
| **微信个人** | iLink `getupdates` 长轮询 | 每条回复必须带回对方最新 `context_token`；媒体走 AES CDN；扫码登录 |
| **QQ** | 官方 Bot API v2：入站 WebSocket，出站 `api.sgroup.qq.com` | 私聊/群各自 allowlist 或 pairing；语音先试免费转写再 STT |
| **WhatsApp** | 两条：插件是本机 Node 桥（WhatsApp Web）；`whatsapp_cloud.py` 是 Cloud API | 私聊 id 要先规范化再进会话键 |
| **Signal** | 本机 `signal-cli` HTTP：入站 SSE，出站 JSON-RPC | 没有官方云 SDK，守护进程挂了通道就断 |
| **iMessage · BlueBubbles** | 本机 BlueBubbles：入站 webhook，出站 REST | 依赖一台 macOS 上的 BlueBubbles |
| **iMessage · Photon** | Photon gRPC，经 Node sidecar 长流 | 不需要公网 URL 和签名 secret |
| **元宝** | 自己的 WebSocket（鉴权、心跳、重连） | 入站是一条中间件管道：解码、去重、撤回、路由、准入，然后才变成 `MessageEvent` |
| **LINE** | aiohttp webhook，HMAC 校验 | 优先用免费 reply token，过期再走按条计费的 Push |
| **Google Chat** | HTTP 回调，或 Pub/Sub 拉订阅 | 附件要用户在私聊里 `/setup-files` 做一次 OAuth |
| **Teams** | Bot Framework webhook（默认端口 3978） | 审批是 Adaptive Card |
| **Matrix** | mautrix，可选端到端加密 | 房间级 allowlist；线程进会话键 |
| **Mattermost** | v4 REST + WebSocket | 回复可钉在线程里 |
| **IRC** | 标准库 asyncio，无第三方 SDK | 频道或私信；断线重连由适配器自己做 |
| **Email** | IMAP 轮询收，SMTP 发 | 一封信一个线程；没有「正在输入」 |
| **SMS** | Twilio REST + 入站 webhook | Markdown 剥成纯文本；一条短信有字数上限，靠 Delivery 切 |
| **SimpleX** | 本机 simplex-chat 守护进程 WebSocket | 没有稳定用户 id，联系人 id 在连上时才生成 |
| **ntfy** | HTTP 流订阅话题，POST 回复 | 没有用户身份，一个话题一把会话 |
| **Buzz** | 社区 relay（Nostr），调 `buzz` CLI | 传输可 WebSocket 或轮询 |
| **A2A** | 入站：`/.well-known/agent-card.json` + JSON-RPC 任务。出站工具是另一方向 | 没配 token 就只绑本机；进来的文本过注入过滤 |
| **Raft** | 本机回环 HTTP，只收「该醒了」 | 正文不在 webhook 里；Agent 再用 Raft CLI 去读和发 |
| **Webhook** | 通用 HTTP POST | 没有人在等：自动续跑要做完被打断的活，不要反问「接下来呢」 |
| **API Server** | 网关进程里的 aiohttp：`/v1/chat/completions`、`/v1/responses`、`/v1/runs` | `send()` 是空的，**不走** Delivery 必达；客户端靠 HTTP/SSE 把回复拿走。也没有人点「会话已恢复」 |

媒体缓存：`media_cache.py`、`gateway/media_fetch.py`。新通道怎么挂进注册表：`platforms/ADDING_A_PLATFORM.md`。

<a id="sec-g7-side"></a>

### 7.4 同进程、但不是「人发来一条 IM」

| 门户 | 连接 | 会话 | 忙时 | 回复 | 审批 |
|------|------|------|------|------|------|
| **Cron** | 时钟 `scheduler_tick`，不是平台推送 | job 自己的会话 | 无用户跟进槽；`skip_background_review` | 网关已连上就 `_deliver_result`，否则 `delivery_queue` 等适配器 | 无人值守，危险工具按策略拒绝或跳过 |
| **Hosted Room** | 成员话仍从某条 IM 适配器进来，再变成 `prompt.submit` | 呈现侧 `sid` + room 任务表 | 同 TUI `queued_prompt` | 回到那个群通道 | 同该 IM |
| **看板调度** | 网关里 `tick_once`，然后 **spawn** `hermes --cli chat -q` | worker 子进程自己的会话，`HERMES_SESSION_SOURCE=kanban` | 无（短进程） | 看板数据库里的任务状态，不是聊天气泡 | worker 是 CLI，终端那套 |

Cron 出站时序 → [第9章](#sec-g9)。Room 状态机 → [第10章](#sec-g10)。看板 spawn → [第11章](#sec-g11)、[卷七 §4](07-multi-agent-and-kanban.md#4-看板-worker-端到端)。

---

<a id="sec-g8"></a>

## 第8章：IM 上的 HITL 审批卡

**一句话**：模型要跑被判危险的动作时，**跑 tool 的那条线程**在 `tools/approval.py` 里停住；Gateway 把审批推到 IM；人点完 `resolve_gateway_approval` 后 **同一条调用栈** 继续 execute 或写 BLOCKED tool 结果。**Deny 不结束 turn**（那是 `interrupt`）。

检测 **不在** `_handle_message`、也不在适配器收包时。入站只负责把话送进 `run_conversation`；危险 shell 在 `terminal_tool` 里 `check_dangerous_command` → `_run_approval_gate`（插件 `pre_tool_call` 的 `approve` 走同一闸门，但堵点更靠前，见 [卷八 §2.2](08-security-and-governance.md#sec-8-2-2)）。

人类等待 **不计入** 固定 batch deadline（`approval_human_wait.human_wait_ceiling`）。

<a id="sec-g8-1"></a>

### 8.1 和 interrupt、clarify 别混

| | **审批 Approval** | **Interrupt** | **Clarify** |
|--|-------------------|---------------|-------------|
| 触发 | 危险命令 / 插件 escalate / 写文件闸门 | `/stop`、`AIAgent.interrupt()` | 模型调 `clarify` |
| IM 表现 | 审批卡 / `/approve` | 本轮收尾、可能半截 tool | 澄清卡片或编号选项 |
| 线程 | **工具线程** `Event.wait` 或 pending | 循环边界退出 | 工具线程等答案 |
| 答完后 | 同一次 `run_conversation` 继续 | turn 结束 | tool 结果回模型 |
| 源码 | `tools/approval.py` | `AIAgent.interrupt()` | `tools/clarify_tool.py` |

闸门语义、地板命令顺序、deny 后库里长什么样 → [卷三 6.3](03-runtime-session-and-loop.md#sec-6-3)。

<a id="sec-g8-2"></a>

### 8.2 会话开跑时登记：notify 不是 Agent 回调槽

IM **没有** `im_*` 回调字段。审批用的是 **进程内全局表**（`tools/approval.py`），键是 **`session_key`**（与 SessionDB / busy 字典一致，不是 TUI `sid`）。

| 时机 | 谁调 | 干什么 |
|------|------|--------|
| 本轮 `run_turn` 开跑前 | Gateway（`run_turn.py` 路径） | `register_gateway_notify(session_key, cb)` |
| `cb(approval_data)` | **Agent 线程**里同步调用 | Gateway 必须把「发卡」**schedule 到 asyncio 循环**（注释：sync→async 桥） |
| 回合结束 / interrupt / 换 Agent 缓存 | `unregister_gateway_notify(session_key)` | 摘掉 cb，并 **`event.set()` 唤醒** 所有还在等的 entry，避免线程挂死 |

`approval_data` 里常有 `request_id`、`command`/`description`、`pattern_key` 等，供各平台画卡与 `/approve <id>` 精确命中。

<a id="sec-g8-3"></a>

### 8.3 阻塞式路径（有 notify）：和 CLI 同一心智，原语换成 Event

| | CLI / TUI | Gateway IM |
|--|-----------|------------|
| **等人** | Agent 线程 `queue.Queue.get()` | Agent 线程 `threading.Event.wait()`（`approval_gateway_wait._await_gateway_decision`） |
| **人怎么答** | 主线程审批面板 Enter | 按钮或 slash：`/approve` `/deny` `/always`，`/approve all` |
| **谁唤醒** | UI `queue.put(choice)` | `resolve_gateway_approval(session_key, choice)` → `entry.result` + `event.set()` |
| **继续 loop** | tool 返回 → ToolMessage → 下一轮 LLM | **完全相同** |

```mermaid
sequenceDiagram
    participant Model as LLM
    participant Term as TerminalTool
    participant Gate as ApprovalGate
    participant Q as _gateway_queues
    participant GW as GatewayRunner
    participant AD as adapter
    actor Human

    Note over GW: register_gateway_notify at turn start
    Model->>Term: tool_call terminal
    Term->>Gate: check_dangerous_command
    Gate->>Gate: _run_approval_gate
    Gate->>Q: append _ApprovalEntry FIFO
    Gate->>GW: notify_cb approval_data
    GW->>AD: send card or text
    AD->>Human: IM
    Note over Gate: agent thread Event.wait loop
    Human->>GW: button or slash
    GW->>Gate: resolve_gateway_approval
    Gate->>Q: pop or match request_id set result
    Q-->>Gate: waiter resumes
    alt deny or timeout
        Gate-->>Term: BLOCKED JSON
    else once session always
        Gate-->>Term: approved then env.execute
    end
    Term-->>Model: tool result same run_conversation
```

**Gateway 进程没有整体 pause**：async 事件环仍收别的 chat；堵的是 **执行 tool 的同步线程**。

并发危险命令：`_approval_lock` + `tool_executor` authorization gate，**同一时刻只处理一扇窗**；多扇排队 FIFO（`session_key` 维度 `_gateway_queues`）。

超时默认 `approvals.timeout` → 按 **deny** 处理。`/stop`、会话 interrupt → `unregister` 或 withdraw，等待方不能无限挂起。

<a id="sec-g8-4"></a>

### 8.4 Pending 路径（没法同步等人）

**没有** `register_gateway_notify`，或 notify 调度失败时：**不能** 让 Agent 线程无限 `Event.wait`（用户可能永远看不到卡）。

| 步骤 | 行为 |
|------|------|
| `submit_pending(session_key, approval)` | 记入 pending 表，**立刻**返回 `approved: false`，状态 `pending_approval` |
| tool 结果 | 命令 **未执行**；模型在同一 turn 看到「请用户批准」类 JSON |
| 人稍后批准 | **force 重放**路径（不是同一条栈上的 wait 醒来） |

阻塞式 = CLI 的 IM 版；pending = 无人可答时的 fail-soft。Cron / 无人值守默认走 deny 或 auto，不弹 IM 卡（[卷八 §2.5](08-security-and-governance.md#sec-8-2-5)）。

<a id="sec-g8-5"></a>

### 8.5 用户选择与持久化

| 选择 | 含义 | 持久化 |
|------|------|--------|
| `once` | 仅此次 | 不写 |
| `session` | 本 `session_key` 同 `pattern_key` 免问 | `_session_approved` |
| `always` | session + 永久 allowlist | `approve_permanent` + 落盘 |
| `deny` | 拒绝 | BLOCKED tool 结果；**turn 继续** |

`/deny <reason>` 的自由文本会进 BLOCKED 消息（`resolve_gateway_approval(..., reason=)`）。

<a id="sec-g8-6"></a>

### 8.6 Slash 与运维 API（网关侧）

| 用户输入 | 效果 |
|----------|------|
| `/approve` | 解队头一条（FIFO） |
| `/approve all` | `resolve_all=True`，一次解完该 session 队列 |
| `/approve <request_id>` | 精确匹配 `approval_data.request_id` |
| `/deny` | 队头 deny；可带 reason |

实现入口：`gateway/run.py` 与 slash 层；解阻塞一律进 `resolve_gateway_approval`。

其它 API（运维 / 多客户端）：

| 函数 | 作用 |
|------|------|
| `list_gateway_approvals(session_key)` | 未决审批快照 |
| `withdraw_gateway_approval(session_key, request_id, cause)` | 客户端画不出卡时撤回，唤醒为 **cancelled**（不是用户 deny） |
| `register_gateway_settle(session_key, request_id, settle)` | 无论哪条路径结束，跑一次 `settle(reason)` |

<a id="sec-g8-7"></a>

### 8.7 各通道「卡」长什么样（合同相同，皮不同）

[第7章](#sec-g7-channels) 里每个适配器自己画 UI，但都服从 **8.2–8.3** 的合同：

| 通道 | 典型审批 UI |
|------|-------------|
| **Telegram** | Inline keyboard（once / session / deny…） |
| **Slack** | Block Kit 按钮 |
| **Teams** | Adaptive Card |
| **Discord** | 组件按钮（频道线程键见 §7.3） |
| **飞书 / 钉钉 / 企微** | 各 SDK 的交互消息或卡片 |
| **SMS / Email** | 常退化为纯文本 + slash（无富交互） |

共同点：**卡点都在 tool 执行前**；出站仍走 `Delivery` + ledger；审批消息本身也是一次 `adapter.send`。

子 Agent：`delegate_tool` 子线程 `set_approval_callback(parent_cb)`，危险命令仍可能弹 **父会话** 的 Gateway 卡（同一 `session_key` 策略见 `tools/delegate_tool.py`）。子 Agent **没有** `clarify_callback`。

**配置速查**（全表面，不只 IM）：`approvals.mode` / `timeout` / `cron_mode` / `deny`；环境变量 `HERMES_YOLO_MODE`、`HERMES_GATEWAY_SESSION`、`HERMES_CRON_SESSION` 等 → [卷八 §2.5](08-security-and-governance.md#sec-8-2-5)。

CLI 双线程 + Queue 详解（对照读本卷 8.3）→ [卷八 §2.3](08-security-and-governance.md#sec-8-2-3)。

---

<a id="sec-g9"></a>

## 第9章：Cron 出站（不经 `_handle_message`）

定时任务 **不是** IM 入站的一条 `MessageEvent`。

```mermaid
sequenceDiagram
    participant SCH as scheduler_tick
    participant RJ as run_job
    participant AG as AIAgent
    participant DQ as cron delivery_queue
    participant AD as adapter

    SCH->>RJ: claim due job
    RJ->>RJ: preflight scan
    RJ->>AG: run_conversation job prompt
    AG-->>RJ: final_response
    alt gateway not ready
        RJ->>DQ: enqueue_and_wait
        SCH->>DQ: drain_delivery_queue
        DQ->>AD: send
    else inline
        RJ->>AD: _deliver_result
    end
```

| 模块 | 作用 |
|------|------|
| `cron/scheduler.py` `run_job` | 建 Agent、跑一轮、记 job |
| `scheduler_tick.py` | 时钟 |
| `scheduler_detached_worker.py` | 子进程，避免堵死 Gateway 事件环 |
| `delivery_queue.py` | 持久化出站 |
| `scheduler_delivery.py` | `last_delivery_queued`、incident |
| `blueprint_catalog.py` | 任务模板 |
| `quota_hold.py` | 配额 |

网关可 `run_delivery_queue_watch` 帮 cron 把队列送出去。

---

<a id="sec-g10"></a>

## 第10章：Hosted Room

多成员群：成员消息经 IM 适配器进网关，再变成呈现路径上的 `prompt.submit`，带 `_hosted_task` / `_hosted_terminal_callback`。

任务状态机：`gateway/hosted_room_driver.py`（表 `hosted_room_driver_tasks`：queued / running / settled / failed / cancelled…）。fencing：`execution_generation` + `cancel_generation`。

| 文件 | 职责 |
|------|------|
| `hosted_rooms.py` | probe、room 元数据 |
| `hosted_room_driver.py` | 任务 SM、lease |
| `hosted_room_peer.py` | 成员协议 |
| `tui_gateway/hosted_room_peer_transport.py` | 与呈现网关互传 |
| `tui_gateway/methods_prompt.py` | `_hosted_submit_error`、`_lock_in_submit_turn` |

hook：`on_room_member_activity`。忙时与 TUI 相同：`queued_prompt`。不是 `delegate_task`（那是父 turn 内子 Agent）。

---

<a id="sec-g11"></a>

## 第11章：网关里的看板调度

`_KanbanDispatcher` **住在 gateway 进程**，但 **不** `_handle_message`：

`tick_once` → `hermes_cli/kanban_db_dispatch.dispatch_once` → `_default_spawn` → `hermes -p PROFILE --cli chat -q`。

环境：`HERMES_SESSION_SOURCE=kanban`。人看的是看板行状态，不是 IM 气泡。→ [卷七 §4](07-multi-agent-and-kanban.md#4-看板-worker-端到端)。

相关：`kanban_watchers.py`、`kanban_watchers_dispatcher.py`、`kanban_watchers_notifier.py`。

---

<a id="sec-g12"></a>

## 第12章：和 AgentScope Channel 对照

| | Hermes Gateway | AgentScope App |
|--|----------------|----------------|
| 长连接谁持有 | **本进程**适配器 | 可拆 channel worker |
| 回复怎么回去 | 同进程 `Delivery` + ledger | `session_events` + 节点 REST |
| 忙时 | `busy_input_mode` 三分支 | inbox + wakeup |
| 会话真源 | `SessionDB` 在 Agent 上，循环内 flush | `Storage` 在 `ChatService` |
| 出站必达 | `delivery_ledger` | 总线不保证 IM 投递语义 |

全文：[CHANNEL_AGENTSCOPE_VS_HERMES.md](../../compare/CHANNEL_AGENTSCOPE_VS_HERMES.md)。

---

<a id="sec-g13"></a>

## 第13章：包地图（grep）

| 路径 | 职责 |
|------|------|
| `gateway/run.py` | `GatewayRunner`、`start_gateway`、`_session_key_for_source` |
| `run_startup.py` / `run_shutdown*.py` | 起停 |
| `run_inbound.py` / `run_inbound_*.py` | 入站 |
| `run_busy.py` | steer / queue |
| `run_turn.py` | `_handle_message_with_agent` |
| `run_agent_cache.py` | Agent 复用 |
| `platforms/base.py` | 适配器基类、pending |
| `delivery.py` / `delivery_ledger.py` | 出站 |
| `session.py` | key 命名空间 |
| `hosted_room_*.py` | Room |
| `kanban_watchers*.py` | 看板 |
| `cron/scheduler.py` | 定时 |
| `tools/approval.py` | IM 审批卡 |

呈现对照：卷二 `_emit`。入口总表：卷一 §2.4。
