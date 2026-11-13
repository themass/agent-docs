# 服务端运行时架构与流程（实现版）

日期：2026-11-11
范围：`myproject/companion-agent`（`main` 分支）当前代码的实际结构与运行流程。设计依据见 `chat-agent-next-plan.md`；本文只写代码已经做到的。

---

## 1. 分层与职责

依赖方向固定，由 `.importlinter` 的 7 条契约自动检查：

```
api（HTTP / SSE 路由）──▶ app（用例编排）──▶ domain（纯规则）
                              │                    ▲
                              ▼                    │
                          ports（协议）────────────┘
                              ▲
adapters（Postgres、Redis、DeerFlow、LiteLLM、推送……）
bootstrap（组合根：只有它知道具体实现）
```

| 层 | 放什么 | 不允许 |
|---|---|---|
| `domain` | 世界书、提示词计划、角色视图、记忆编排、提醒规则、摘要模板、回合判定表 | I/O、框架、依赖 app / adapters |
| `ports` | 存储、对话线程、提醒、推送、大脑、回合控制的协议与记录类型 | 依赖 app / adapters |
| `app` | 回合执行、提交、上下文组装、历史操作、摘要重建、提醒调度、工具与确认 | 依赖 adapters |
| `adapters` | SQL 仓储、Redis 控制面、DeerFlow 大脑与对话线程、记忆召回、推送 | — |
| `api` | 路由、鉴权、错误码映射 | 依赖 adapters、bootstrap |
| `bootstrap` | `build_platform`、模型构造、FastAPI 装配 | — |

## 2. 模块地图

| 能力 | 领域 | 应用 | 适配器 |
|---|---|---|---|
| 回合控制（合并、插话、排队、取消、围栏） | `domain/turn` | `app/chat/submit.py`、`turn_runner.py`、`drain.py` | `adapters/cache/redis/control.py` |
| 大脑 | — | （经 `Produce` 注入） | `adapters/brain/deerflow.py`、`graph_middleware.py` |
| 对话线程（模型上下文） | — | `app/chat/history.py`、`resummarize.py` | `adapters/brain/conversation_state.py` |
| 角色扮演提示词 | `domain/prompt/roleplay.py`、`plan.py`、`domain/lorebook/`、`domain/roles/profile.py` | `app/chat/context.py`、`app/roles/resolver.py` | `adapters/roles/` |
| 记忆 | `memory/hooks.py`、`pipeline.py` | `memory/recorder.py`、`extraction.py` | `memory/recallers.py`、`memory/sql.py` |
| 工具与确认 | `domain/tools/` | `app/tools/` | `adapters/brain/tools.py` |
| 定时提醒（主动消息） | `domain/reminders.py` | `app/proactive/reminders.py` | `adapters/store/sql/reminders.py`、`adapters/push/` |
| 账号注销 | — | `app/account/purge.py` | `adapters/store/sql/account.py`、Redis `purge_session`、`CheckpointThreadEraser` |
| 时间线（带时间点的事） | `domain/timeline/` | `app/timeline/recorder.py` | `adapters/store/sql/timeline.py` |
| 存储 | — | — | `adapters/store/sql/`（Postgres，兼容 MySQL） |

## 3. 数据：三份，各管一件事

| 数据 | 存储 | 职责 | 权威 |
|---|---|---|---|
| 消息表 `ca_chat_message` | Postgres | 界面历史、原始存档、编辑与删除的依据 | 原始内容 |
| 对话线程（LangGraph checkpoint，`thread_id = session-{id}`） | Postgres | 模型看到的最近消息与 `summary_text` | 模型输入 |
| 事件流 `ca:sess:{id}:events` | Redis | SSE 推送与续传 | 不是权威，可丢 |

两边用稳定 id 对齐：用户消息在线程里是 `m{message_id}`；助手回复的线程 id 记在助手消息 `meta.lc_ids`；中断回复的补记是 `a{message_id}`。

## 4. 一个回合

```
POST /sessions/{id}/messages
  SubmitService.submit
    幂等 → 安全检测 → 落库（role、kind）→ Redis Lua 判定
      ├ STARTED：拿锁 → 取围栏号（Redis INCR）→ 写到会话 → 启动 TurnRunner
      ├ MERGED / STEERED：控制消息已写入，运行中的回合接手
      └ QUEUED：入队，回合结束后排空
TurnRunner.run
  加载本回合的用户消息（逐条带 id）
  produce(request, inbox)                                   ← bootstrap 注入
    ContextBuilder.build：角色 → 世界书扫描（最近消息）→ 记忆召回 → PromptPlan
    DeerFlowBrain.run：astream({新消息}, thread_id=session-{id})
      LangGraph 从 checkpoint 恢复历史；PromptMiddleware 写系统提示词并按深度注入（只进请求）
      SteerMiddleware 注入插话（id = m{message_id}）
      ToolAuthorizationMiddleware 经 ToolRuntime 执行或请求确认
      摘要中间件：超阈值时把较早的消息压成 summary_text
  事件：文本增量 → SSE；工具开始 / 结束 → step；线程消息 id → 记录
  控制：首 token 前合并 → 中止并用同样的 id 重跑（按 id 覆盖，不重复）；取消；续租失败 → 停止
收尾（持锁）
  写助手消息（带围栏号的条件写；围栏过期则不写）
  after_turn：中断回复补记到线程；入队记忆写入任务
  释放锁 → 排空队列
```

## 5. 编辑、删除、重新生成

全部经 `HistoryService`，需要会话锁；回合进行中返回 409。

| 操作 | 消息表 | 对话线程 | 已被摘要覆盖时 |
|---|---|---|---|
| 删除 | 软删 | 按 id 移除 | 入队 `session.resummarize`：从未删除的消息重建摘要 |
| 编辑（用户消息） | 改正文 | 按 id 替换 | 入队重建摘要 |
| 重新生成 / 重试 | 旧回复保留 | 移除该用户消息之后的助手回复 | — |

## 6. 定时提醒（主动消息）

```
用户：「明天下午 3 点叫我开会」
  模型先 get_current_time，再调用 create_reminder(title, at=带时区的绝对时间, timezone)
  工具需要确认 → 用户确认 → 执行（按确认 id 幂等）→ ca_reminder 一条 pending
worker 每 5 秒：claim_due（Postgres SKIP LOCKED，租约 2 分钟；租约过期可被他人接手）
  会话已删除 → 结束，不推送
  提交主动回合：system/proactive 消息（带标记的指令）→ 正常回合路径（忙时排队）
  标记 sent → 推送「你有一条新消息」（当前实现只记日志）
客户端：kind=proactive 的指令不显示；角色的回复照常出现
```

## 6.0 时间线

存 `ca_timeline_event`（Postgres，按「用户 + 角色」隔离）。来源有三种：工具写的（`remember_event`、
`create_reminder`）、回合后抽取的（`timeline.record` 任务）、记忆页手动加的。

- 同一件事只留一条（`dedupe_key` = 标题归一化 + 当地日期）：工具记过、抽取再记一次会合并。
- 每条事件记 `source_message_id`：删除用户消息 → 由它得来的事件置 `stale`；编辑 → 同样置 `stale`，
  新的内容在下一轮抽取时写回来。手动添加的不受影响。都在会话锁内做。
- 读：`upcoming`（14 天内）+ `recent_past`（2 天内、还不知道结果的）进提示词；`recall_events` 工具同源。
- 事件本身不会触达用户；会主动找用户的只有 `ca_reminder`。
- 注销时随关系库一起物理删除。设计见 `chat-agent-timeline-design.md`。

## 6.0.1 换一个回答（左右滑动）

`ca_chat_message` 加了 `alt_group` / `alt_selected`：同一次提问的多个候选回复同属一组（组 id = 第一条回复的消息 id），
只有 `alt_selected` 的一条进历史、进模型上下文，其余候选只通过 `alt_ids` 暴露给客户端。

- 重新生成：路由先找出这条用户消息当前的回复（`find_reply`，只在最新一轮才有），作为 `alt_of` 一路传到回合收尾；
  新回复写入时成为组内选中的一条，旧回复保留为候选。`message.done` 事件带 `alt_group`，客户端据此重拉历史。
- 切换：`POST /messages/{id}/select`。在会话锁内把线程里当前那条的 id 移除、把目标候选的最终文本作为助手消息放到末尾。
  只允许在最新一轮切换（之后还有别的消息 → 409 `not_latest`），回合进行中 409 `busy`。工具调用的中间步骤不会随切换还原。
- 删除：删的是未选中的候选 → 只软删；删的是选中的 → 最新一轮由最新的剩余候选顶上，否则整组删除。
- 历史接口：有多个候选的消息带 `alt_group`、`alt_index`、`alt_count`、`alt_ids`。

## 6.0.2 形象发布

`ca_avatar_release`：形象包（zip + manifest.json，格式见 `domain/avatar/package.py`）存对象存储，库里只存元数据和状态。
运营接口 `/api/agent/v1/admin/avatars`（`X-Admin-Token`，`COMPANION_ADMIN_TOKEN` 为空则关闭）：上传 → 草稿 → 上线 / 下线；
上线新版本会让同一个形象的旧在线版本自动下线。客户端 `GET /avatars?role_id=&app_version=` 取该角色可用的最新在线版本，
返回 sha256 与一小时有效的下载地址。客户端内置一个默认形象，包校验失败或断网时保持原样。没配对象存储就不挂这组接口。

## 6.0.3 用户画像

角色对「这个人」的归纳理解，和事实记忆分开（`domain/persona/`）。依据：`docs/her-research` 的建议 1。

- **存储**：`ca_persona_entry`，按「用户 + 角色」隔离。每条是 话题 / 备忘 / 段（static 长期、dynamic 近况）/ 是否推断 / 置信度 / 来源事实 id / 双日期。
  **只增不改**：新信息不覆盖旧条目，旧条目标 `superseded_by`，历史可查可回滚。
- **对话路径只读**：`ContextBuilder` 每回合读当前有效的条目，渲染进系统提示词（独立的 700 字预算，不和召回的记忆抢；超预算时先丢低置信度推断和 dynamic，最后才动 static 事实）。推测的条目标「推测，不确定」，提示词要求用试探口气。
- **只有后台任务写**：回合收尾只累计用户发言字数（`ca_persona_cursor`），攒够 600 字才入队 `persona.update`，不在回合里抽取、不等模型。
  抽取提示词里事实用本次的短编号（F1、F2…），解析时不在列表里的编号一律丢弃，模型编造不出指向真实记忆的 id。
- **合并规则（`plan_merge`，纯规则）**：同话题被「别再提」压住 → 放弃；备忘没变 → 放弃；推断不能覆盖用户明说的事实 → 放弃；否则取代旧条目。推断的置信度封顶 0.6；身份证、银行卡、住址、病情、性取向、宗教、政治倾向等话题不进画像。
- **用户控制**（`/api/agent/v1/memory/profile`）：`GET ?role_id=`（`include_history` 看「为什么记得」）、`POST /profile/{id}/suppress`（别再提）、`DELETE /profile/{id}`。删除或改写一条事实记忆时，只靠这条事实归纳的画像条目一并删除。
- 注销时随关系库一起删除；`persona.update` 任务执行前确认会话还在。

## 6.0.4 每日整理（目前只做时间线）

worker 每小时检查一次今天的 `timeline.sweep` 任务是否已入队（按日期去重，多个 worker 只有一条）。任务把「一次性、仍是 scheduled、
发生时间已过 2 天以上」的事件置 `missed`；重复事件和 2 天内的不动。纯规则、分批、可重复执行，不调模型。

**没做的整合**：事实记忆的去重与矛盾消解、把过期事件的说法改写成过去时、画像的定期重建。原因：记忆接口只有增、查、删，没有「取代」，
直接删会丢证据；报告建议先给事实表加 `is_latest` / `supersedes_id`（接口变更），这一步需要你确认后再做。

## 6.0.5 合规底座

依据《人工智能拟人化互动服务管理暂行办法》（2026-07-15 施行）与纽约 GBL、加州 SB 243，取最严口径。**不是法律意见**。

| 能力 | 实现 | 说明 |
|---|---|---|
| 训练用途单独同意 | `ca_user_consent.training_consent`，默认关闭，`PATCH /consent` 打开 | 不捆绑在服务条款里 |
| 主动联系总开关 | `ca_user_consent.proactive_enabled`，`submit_proactive` 前必须为真 | 关掉后调度器不再发起；用户明确要求的提醒仍会到点执行（兑现请求，不是主动打扰） |
| 连续使用提醒 | `ca_usage_span`，每次发消息记一次活跃；同类一段 30 分钟无活跃即重新计时；到 120 分钟推一条 `usage.reminder` SSE，一段只提醒一次 | 国内 2 小时、纽约 3 小时，取最严 |
| 数据导出 | `GET /api/agent/v1/export`，JSON 下载：会话、消息、画像、时间线、提醒、同意 | 某一块读不到会在 `partial_errors` 里标明，不假装完整 |
| 注销清理 | 同意与使用计时随关系库一起物理删除 | — |

**没做**：显式 AI 标识的界面展示（需要客户端）、未成年人年龄识别与隔离、紧急联系人流程、危机识别的模型侧判定（提示词第 5 条已有基本处理）。

## 6.0.6 事实的取代

`ca_memory_item` 加 `is_latest` / `supersedes_id`：改写一条事实不再是「删除再新增」，而是新条目 `is_latest=1`、
旧条目 `is_latest=0` 并保留。召回与默认列表只取当前有效的；`GET /memory/facts?include_history=true` 能看改过什么。
好处：用户说「我说错了」时能查清是哪条取代了哪条，画像的依据也不会因为一次改写而丢失。

## 6.1 记忆按角色隔离

记忆主体 id = `{owner}.{role}`（`memory/subject.py`），memory_hub 再加上 `companion:` 前缀。
召回（`MemoryPortRecaller`）、回合后写入（`ExtractionRecorder`）、工具（`recall_facts` / `remember_fact`）都用当前角色的主体，
所以任何满足记忆接口的后端都自动隔离。时间线事件按 `source_character_id` 过滤。
记忆接口 `/api/agent/v1/memory/facts|events` 带可选的 `role_id`；不带是用户级空间（手动添加的记忆）。

## 6.2 账号注销

```
DELETE /api/agent/v1/me  → 关闭全部会话（标记删除 + 推进围栏）→ 入队 account.purge → 202
worker：再关一次会话 → Redis（取消回合、删锁 / 回合状态 / 事件流）→ 删 checkpoint 线程
      → 每个角色的记忆空间 + 用户级空间 → 时间线 → 对象存储 → 关系库物理删除（含未执行的记忆写入任务）
      → ca_account_purge_log 只记哈希
```

每一步可重复执行，失败整体重试。记忆写入任务执行前会确认会话还在，注销后不会把记忆写回来。

## 7. 进程与部署

三种进程，各自独立启动、独立扩缩，**缺哪一种，对应的功能就静默失效**：

| 进程 | 入口 | 做什么 | 不部署会怎样 |
|---|---|---|---|
| **API**（多副本） | `python -m companion.serve` | 手机 App 的 HTTP / SSE 请求：发消息、拉历史、角色、记忆、偏好、建语音房间（`/v1/voice/sessions`）；文字回合在接到请求的进程里跑 | App 什么都用不了 |
| **后台循环**（默认在 API 进程内） | 无独立入口；`COMPANION_JOBS_IN_API=true`（默认） | 不接 HTTP：回合后写记忆/画像/时间线、会话摘要重建、到期清理、账号注销、提醒到点发送、按时间线事件主动找用户。也可用 `python -m companion.worker_jobs` 单独跑 | 关掉且没单独跑：聊天照常，但记忆不更新、提醒不响、主动消息不发、注销不执行——任务堆在 `ca_agent_job` 表里，没有任何报错 |

**为什么最终放进了 API 进程**：一度拆成独立进程，理由是"多副本时每个都扫会重复发"和"不该和用户请求抢资源"。
但代价是多一个必须记得部署的进程，漏部署时是静默失效。现在的处理是：默认跟着 API 跑，多副本时只在一个副本上打开
`COMPANION_JOBS_IN_API`，其余关掉。重复发的问题本来就靠数据库行锁（`FOR UPDATE SKIP LOCKED`）和 Redis 抢占解决，
所以两种部署方式都安全。

**为什么语音 worker 必须独立**：它启动后连到 LiveKit 注册自己是一个可用节点，房间由 LiveKit 派单，且默认
`JobExecutorType.PROCESS`——**一个房间一个进程**。进程数由房间数决定，所以它的连接池和房间上限必须单独算，
不能和 API 混在一起。

**语音 worker 的配置要和 API 一致**，指的是这几个环境变量必须指向**同一个**库、同一个 Redis、同一个模型网关：
`COMPANION_DATABASE_URL`（或分开的 `COMPANION_DB_*`）、`COMPANION_REDIS_URL`、`COMPANION_LLM_API_BASE` /
`COMPANION_LLM_API_KEY`。原因：语音回合现在走和文字同一个回合引擎，会话历史在数据库、会话锁和事件流在 Redis，
一旦指到不同的库或 Redis，语音和文字就又变回两份互不相干的历史，还会各自拿各自的锁、互相踩。
（语音 worker 不需要 `COMPANION_AUTH_VERIFIER`：它不接用户请求，房间身份由 API 建房间时写进房间元数据，客户端改不了。）

**语音房间并发上限 `COMPANION_VOICE_MAX_ROOMS`（单个 worker 进程，默认 5，0 = 不限）**：

- LiveKit 默认按 **CPU 占用**判断一个 worker 满没满（生产默认到 70% 才满）。语音 agent 大部分时间在等网络，
  CPU 很低，所以按 CPU 永远不会满，房间会一直接。而我们的瓶颈是**数据库连接**：每个房间是一个独立进程，
  各占一份连接池（峰值 6 条）。
- 现在改成按房间数：当前房间数 / 上限，到 1.0 就报“已满”，LiveKit 不再把新房间派给这个 worker。
- **总容量 = 上限 × worker 进程数**。要多撑房间，加 worker 进程，但每多一个房间都占库的连接，见下面的预算。
- **全部 worker 都满了会怎样：这个我没解决。** LiveKit 派不出 agent，用户进了房间但没人应答（静音）。
  建房间的接口（`/v1/voice/sessions`）目前不知道 worker 满没满，没法提前拒绝或提示。需要的话要另做容量查询。
- 这个上限只在单测里验证过（负载函数、和 SDK 真实的 `WorkerOptions` 对接、生产模式校验）；
  **没有在真实 LiveKit 派单下验证过“满了之后确实不再派”**。

**连接数预算**（库 `max_connections=100`，预留 10 给运维，探测时别的服务已占约 6，剩 84）：

| 进程 | 每进程峰值连接 |
|---|---|
| API | 30 |
| 后台任务 | 12 |
| 每个语音房间 | 6 |

1 个 API + 1 个后台任务 = 42，剩 42，**峰值下最多 7 个语音房间**；2 个 API + 1 个后台任务 = 72，剩 12，**最多 2 个**。
这是**峰值上界**，真实用量通常低得多（池是按需建连接，不是启动就占满），所以这个数偏保守，但上线前应该按这个算，
再用 `pg_stat_activity` 看真实占用（连接带 `application_name`，能分清是哪类进程）。

迁移：`alembic upgrade head`。Postgres 的 `0001` 直接建出完整结构；MySQL 走 0001 → 0002 → 0003 → 0004。

## 8. 客户端（Android，`agent-chat-client` 分支）

- `AgentApi` / `AgentChatRepository`：新增删除、编辑消息，提醒列表与取消。
- `AgentChatViewModel`：删除、编辑、提醒；409 提示「正在回复中，请稍后再试」。
- 界面：长按消息出现「编辑 / 删除」；顶部显示待发送的提醒，可取消；「重新生成」改为传被回答的用户消息 id（原实现传了助手消息 id，服务端会返回 404）。
- 主动回合的内部指令（`kind=proactive`）在实时事件与历史里都不显示。
- 导航入口仍未接入（等待确认）。

## 9. 尚未实现

- 推送：只有日志实现，FCM / 厂商通道待接。
- 账号注销的兜底对账（`account.reconcile`，对比 Java 用户表）：未做，需要只读账号。
- 换一个回答（同位置多候选）与对话分支：数据结构未做，待产品决定。
- 画像与事实：事实已有「取代」，但还没有自动的矛盾消解和时态改写（需要后台任务判断哪条被哪条取代）；中文检索未实测。
- 时间线：生日 / 纪念日的自动提醒（`InitiativeScheduler` 那条旧路径）没有迁到新栈；旧栈仍在用它。
- 真实模型冒烟：需要批准使用线上网关。
