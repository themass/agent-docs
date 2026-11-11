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
| 记忆 | `domain/memory/hooks.py`、`pipeline.py` | `app/memory/recorder.py`、`extraction.py` | `adapters/memory/recallers.py`、`adapters/store/sql/memory.py` |
| 工具与确认 | `domain/tools/` | `app/tools/` | `adapters/brain/tools.py` |
| 定时提醒（主动消息） | `domain/reminders.py` | `app/proactive/reminders.py` | `adapters/store/sql/reminders.py`、`adapters/push/` |
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

## 7. 进程与部署

| 进程 | 入口 | 做什么 |
|---|---|---|
| API（多副本） | `python -m companion.serve` | HTTP / SSE；回合在接到请求的进程里跑 |
| worker（可多副本） | `python -m companion.worker_jobs` | 任务队列（确认过期、审计清理、记忆写入、摘要重建）+ 提醒调度；主动回合在 worker 里跑 |

两种进程用同一个 `build_platform`，`Platform.astart()` 在事件循环里打开 checkpoint 连接池并建表（幂等）。

配置（环境变量）：`COMPANION_DATABASE_URL`（Postgres，`postgresql+psycopg://…`）、`COMPANION_REDIS_URL`、`COMPANION_CHECKPOINT_URL`（可省，从数据库地址推导）、`COMPANION_LLM_API_BASE` / `COMPANION_LLM_API_KEY`、`COMPANION_SUMMARY_TRIGGER_TOKENS`、`COMPANION_SUMMARY_KEEP_MESSAGES`、TOS（可省，省略时不挂上传接口）。

迁移：`alembic upgrade head`。Postgres 的 `0001` 直接建出完整结构；MySQL 走 0001 → 0002 → 0003。

## 8. 客户端（Android，`agent-chat-client` 分支）

- `AgentApi` / `AgentChatRepository`：新增删除、编辑消息，提醒列表与取消。
- `AgentChatViewModel`：删除、编辑、提醒；409 提示「正在回复中，请稍后再试」。
- 界面：长按消息出现「编辑 / 删除」；顶部显示待发送的提醒，可取消；「重新生成」改为传被回答的用户消息 id（原实现传了助手消息 id，服务端会返回 404）。
- 主动回合的内部指令（`kind=proactive`）在实时事件与历史里都不显示。
- 导航入口仍未接入（等待确认）。

## 9. 尚未实现

- 推送：只有日志实现，FCM / 厂商通道待接。
- 账号注销：没有跨存储清理（消息、线程 checkpoint、记忆、提醒）。
- 换一个回答（同位置多候选）与对话分支：数据结构未做，待产品决定。
- 记忆按角色隔离：未做，待产品决定（召回查询已带 role_id，来源可以据此过滤）。
- 时间线仍是进程内实现，重启即丢。
- 真实模型冒烟：需要批准使用线上网关。
