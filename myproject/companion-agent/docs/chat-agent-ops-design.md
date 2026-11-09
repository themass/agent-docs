# 运维与可靠性设计：任务、恢复、删除、观测、上传、错误、限流、配置

日期：2026-11-09。配套：`chat-agent-design.md`、`chat-agent-architecture.md`、`chat-agent-tool-mcp-design.md`。

本文补齐「一个能上线的服务」必须回答、但前几份文档没有回答的问题。

## 0. 对已有设计的修订

| 原说法 | 修订 | 原因 |
|---|---|---|
| 「没有 worker 进程」（design §1） | **新增 `agent-worker` 进程** | L2/L3 汇总、确认过期、卡死回合巡检、注销清理都是后台任务；汇总要调大模型，放在 API 进程里会抢请求延迟 |
| 「副本崩溃后，由任意一个请求触发排空」（design §6.5） | 由 worker 的巡检任务负责（第 2 节） | 用户不再发消息时，队列永远不会被排空 |
| 记忆抽取「中间件里异步落库」 | 改为写入后台任务表，由 worker 执行 | 进程内 `create_task` 在进程退出时丢失，且无法重试 |

## 1. 进程拓扑

```
agent-api     ×N   每台机器 4 个独立进程（systemd 模板单元，不用 uvicorn --workers，见 P §3.5）；只处理请求与回合执行
agent-worker  ×1   后台任务与定时任务；同一份代码，入口不同：python -m companion.worker
```

- 回合仍然在 API 进程里跑：它是请求的直接后果，延迟敏感，且需要就近写事件流。
- 其余所有「不在请求路径上」的事都进 worker。
- worker 可以先只部署一个实例；任务认领用数据库租约（第 2.1 节），将来扩到多个实例不需要改代码。
- 角色扮演上线时，LiveKit 的 agent worker 是**另一个**进程（`agent-livekit`），不与这个 worker 合并：前者是实时语音，后者是批处理，资源画像完全不同。

## 2. 后台任务

### 2.1 机制：数据库任务表 + 租约认领

与 job-come 的做法一致（`jc/tasks.py` 用数据库认领 + worker id），不引入 Celery / arq：

```sql
agent_job(
  id BIGINT PK, kind VARCHAR(64), payload JSON,
  status ENUM('queued','running','done','failed','dead'),
  attempts INT, max_attempts INT,
  run_after DATETIME,            -- 可延迟执行
  lease_owner VARCHAR(64), lease_until DATETIME,
  dedupe_key VARCHAR(191) NULL,  -- 唯一索引，防止同一任务重复入队
  last_error TEXT, created_at, updated_at
)
索引 (status, run_after)；唯一 (dedupe_key)
```

认领：

```sql
SELECT id FROM agent_job
 WHERE status='queued' AND run_after <= NOW()
 ORDER BY run_after LIMIT 10
 FOR UPDATE SKIP LOCKED;
-- 然后在同一事务里：status='running', lease_owner=?, lease_until=NOW()+INTERVAL 5 MINUTE
```

- MySQL 8 支持 `SKIP LOCKED`，多个 worker 不会抢同一条。
- 执行中每分钟续租；租约过期的 `running` 任务由下一轮认领重新拿走（视为崩溃）。
- 失败按指数退避重试（1、4、16 分钟），超过 `max_attempts` 置 `dead` 并报警。
- **任务必须幂等**：重试与崩溃重领都可能让同一任务执行两次。每种任务在下表里写明幂等手段。

### 2.2 任务清单

| kind | 触发 | 做什么 | 幂等手段 |
|---|---|---|---|
| `memory.extract` | 回合结束后入队 | 从本回合抽取 L1 事实写入 memory_hub | `dedupe_key = turn_id`；写入前按内容指纹查重 |
| `memory.summarize_scenario` | 定时，每用户每日一次 | L1 → L2 场景 | `dedupe_key = user_id:date` |
| `persona.rebuild` | 定时，每用户每周一次；或 L2 有更新 | L1/L2 → L3 画像 Markdown | 新版本写新行，`persona_profile.version` 递增 |
| `session.title` | 会话第 2 条消息后入队 | 生成会话标题 | 已有标题（含用户改过的）就跳过 |
| `turn.sweep` | 定时，每分钟 | 回收卡死回合（2.3） | 状态机条件更新 |
| `queue.drain_orphans` | 定时，每分钟 | 排空无人触发的队列（2.3） | 走正常的取锁排空，拿不到锁就跳过 |
| `confirmation.expire` | 定时，每 10 分钟 | 过期的确认置 `expired` | 条件更新 |
| `account.purge` | `DELETE /me` 或对账入队 | 跨存储删除（第 3 节） | 每一步可重复执行 |
| `account.reconcile` | 定时，每日 | 对比 Java 用户表，找出已注销的用户（第 3 节） | 只读比对；超过阈值暂停 |
| `upload.gc` | 定时，每日 | 删除 24 小时内未被消息引用的上传 | 按引用计数判断 |
| `softdelete.purge` | 定时，每日 | 软删除超过 30 天的会话与消息物理删除（第 10 节） | 条件删除 |
| `audit.trim` | 定时，每日 | 工具审计超 90 天删除；确认记录处理完 7 天后清除参数原文 | 条件更新 |
| `events.trim` | 定时，每小时 | 清理过期的 Redis 事件流 | Redis 本身幂等 |

### 2.3 卡死回合与孤儿队列

```
turn.sweep：
  找 state='running' 且 started_at < NOW()-5min 且 Redis 运行锁不存在 的回合
  → state='failed'，error='orphaned'
  → 若该回合已有部分输出：落库为助手消息（标记 interrupted）
  → 向事件流补发 error{code:"turn_interrupted", retryable:true}（与错误码表一致，评审 M7）
  → 入队 queue.drain_orphans

queue.drain_orphans：
  找 chat_queue 中 status='queued' 且 所属会话没有运行中回合 的会话
  → 对每个会话尝试取运行锁；取到就按正常流程排空（design §6.4）
```

判定「卡死」同时要求「超时」与「锁不存在」：锁还在说明进程还活着、只是慢，不能误杀。

## 3. 账号注销：跨存储删除

（修订，评审 M13）上一版要求 Java 调用 Python 的内部接口，这违反了「Java 不删、不改」，而且 Python 只监听 `127.0.0.1`、nginx 只转发 `/api/agent/`，Java 也根本访问不到。改为两条路，都不需要改 Java：

**主路径：App 发起。** 新 App 的「注销账号」流程先调用 Python，再调用 Java：

```
DELETE /api/agent/v1/me        （用户自己的 Bearer token 鉴权）
→ 入队 account.purge，立即返回 202
App 收到 202 后再调用 Java 的 /api/user/del.json
```

顺序是先删 Python 再删 Java：反过来的话，Java 删完 token 就失效了，App 再也无法证明身份来删 Python 的数据。

**兜底：对账任务。** 用户可能在旧 App 或其他渠道注销，Python 不会收到通知。worker 每日执行 `account.reconcile`：

- 用**只读账号**查询 Java 库的用户表，找出 `agent` 库里有数据、但 Java 用户表里已不存在的 `owner_id`。
- 对每个这样的 id 入队 `account.purge`。
- 需要运维给 Python 一个只读访问 Java 用户表的数据库账号（只授予该表的 `SELECT`）。这是对 Java **数据库**的只读访问，不改 Java 代码。
- 单次对账的删除数超过阈值（默认 100）时暂停并报警，不自动执行——防止 Java 侧误操作（比如表被清空）导致 Python 批量删除。

`account.purge` 按顺序执行，每一步可重复：

| 步骤 | 存储 | 动作 |
|---|---|---|
| 1 | MySQL | 标记该用户所有会话为删除中，拒绝新回合 |
| 2 | Redis | 删除 `sess:{id}:events`、`sess:{id}:lock`、`sess:{id}:turn`、`turn:{tid}:*`（D §6.2） |
| 3 | memory_hub | `delete_user`（先逐条删向量与记录，再 `delete_all` 兜底，沿用现有 mem0 适配器的做法） |
| 4 | OSS | 删除该用户的上传前缀 `uploads/{user_id}/` |
| 5 | MySQL | 物理删除 `chat_message`、`chat_queue`、`chat_turn`、`chat_session`、`role`、`upload`、`persona_profile`、确认记录 |
| 6 | MySQL | 审计表只保留指纹与时间，删除与该用户关联的可识别字段 |
| 7 | — | 写一条 `account_purge_log`（user_id 的哈希、完成时间），不存原 id |

- 任一步失败则任务重试，已完成的步骤再执行一次无副作用。
- 用户主动删除单个会话、单条记忆，走各自的接口，不走这条链。
- 「软删除」只用于用户误删可恢复的场景（会话、消息）；注销是**物理删除**。

## 4. 可观测性

### 4.1 日志

- 结构化 JSON，字段：`ts`、`level`、`event`、`request_id`、`turn_id`、`user_hash`、`session_id`、`latency_ms`、`error_code`。
- **不记原文**：用户消息、模型回复、记忆内容、工具参数一律不进日志；只记长度与指纹。
- `user_id` 记哈希（`sha256(user_id + LOG_SALT)[:16]`），排查时用同一个函数反查。
- `UserPo` 里的 `pwd`、`pwdHash` 在解析处丢弃（design §4），日志里不可能出现；加一个测试对日志输出做敏感字段扫描。

### 4.2 指标（Prometheus）

| 指标 | 类型 | 标签 |
|---|---|---|
| `turn_total` | counter | `product`、`state`（done/failed/cancelled）、`skill` |
| `turn_ttft_seconds` | histogram | `scenario`、`model` —— 首 token 延迟，最重要的体验指标 |
| `turn_duration_seconds` | histogram | `scenario` |
| `turn_disposition_total` | counter | `disposition`（started/merged/steered/queued） |
| `turn_restart_total` | counter | `scenario` —— 合并导致的重跑次数（D §6.3），监控被浪费的调用 |
| `steer_requeued_total` | counter | —— steer 未被注入、回合结束时转回队列的次数（D §6.4） |
| `queue_depth` | gauge | —— 所有会话队列长度之和 |
| `llm_fallback_total` | counter | `scenario`、`from_model`、`to_model` |
| `llm_tokens_total` | counter | `model`、`direction`（in/out） |
| `tool_call_total` | counter | `tool`、`status` |
| `sse_connections` | gauge | —— 当前长连数 |
| `job_total` | counter | `kind`、`status` |
| `job_dead_total` | counter | `kind` —— 需要报警 |

### 4.3 链路

- 每个请求一个 `request_id`（从 `X-Request-Id` 读，没有就生成），回合一个 `turn_id`，两者贯穿日志、事件与后台任务。
- 模型调用的追踪：OpenTelemetry 导出到自建或云上的后端；不默认接 Langfuse 一类会存原文的平台。如果要接，必须先关闭原文采集。

### 4.4 报警（最小集合）

| 条件 | 级别 |
|---|---|
| `turn_ttft_seconds` P95 > 4s 持续 10 分钟 | 警告 |
| 回合失败率 > 5% 持续 5 分钟 | 严重 |
| `llm_fallback_total` 突增（主模型不可用） | 警告 |
| `job_dead_total` 增加 | 警告 |
| `/readyz` 失败 | 严重 |

## 5. 上传

| 项 | 规则 |
|---|---|
| 类型 | 只接受 `image/jpeg`、`image/png`、`image/webp`、`image/heic`；**按文件头判断**，不信扩展名和 Content-Type |
| 大小 | 单张 ≤ 8 MB；解码后像素 ≤ 4096×4096 |
| 处理 | 服务端解码后重新编码为 JPEG（质量 85），**去除 EXIF**（含 GPS 位置）；长边缩到 2048 |
| 存储 | OSS 私有桶，key `uploads/{user_id}/{ulid}.jpg`，不可公网直接访问 |
| 读取 | 发给视觉模型时用 5 分钟有效的签名 URL；客户端回看历史图片也用签名 URL |
| 归属 | 回合引用 `upload_id` 时校验 `owner_id`，别人的 id 一律 404 |
| 生命周期 | 被消息引用的跟随消息删除；未引用的 24 小时后由 `upload.gc` 删除 |
| 频率 | 每用户每分钟 10 张 |

为什么要服务端重新编码：一是去 EXIF，用户拍题时照片里常带位置；二是统一格式和尺寸，避免各家视觉模型对 HEIC、超大图支持不一致。

## 6. 错误码

### 6.1 响应格式

```json
{"error": {"code": "queue_full", "message": "消息太多了，等这一轮回答完再发", "retryable": true, "request_id": "…"}}
```

- `message` 按请求语言返回（`zh-CN`、`en`、`ar`），客户端可以直接展示。
- `code` 稳定，客户端据它决定行为；`message` 可以随时改文案。

### 6.2 错误码表

| code | HTTP | retryable | 客户端行为 |
|---|---|---|---|
| `unauthorized` | 401 | 否 | 跳登录 |
| `forbidden` | 403 | 否 | 提示无权限（如改系统角色） |
| `not_found` | 404 | 否 | 刷新列表；他人的资源也返回这个 |
| `invalid_request` | 422 | 否 | 提示具体字段（`detail` 里给字段名） |
| `conflict` | 409 | 是 | 例如排空中点了重新生成；稍后重试 |
| `queue_full` | 429 | 是 | 提示等当前回答结束 |
| `rate_limited` | 429 | 是 | 读 `Retry-After` 头，倒计时后重试 |
| `upload_too_large` | 413 | 否 | 提示压缩或换图 |
| `upload_unsupported` | 415 | 否 | 提示换格式 |
| `model_unavailable` | 503 | 是 | 所有候选模型都失败；提示稍后重试 |
| `upgrade_required` | 426 | 否 | App 版本过旧（D §7.4），引导升级 |
| `turn_interrupted` | —（事件） | 是 | 回合被中断，已显示的部分保留；「继续」调用 `POST /sessions/{id}/messages/{mid}/continue`（D §6.7） |
| `gone` | —（事件） | 否 | 续传缓冲已过期，重新拉历史 |
| `internal` | 500 | 是 | 通用失败，带 `request_id` 便于反馈 |

- 领域异常到错误码的映射只在 `api/http/errors.py` 一处。
- 未映射的异常一律 `internal`，日志里带完整堆栈，**响应里不带**。

## 7. 限流与并发

服务自我保护，与「内容安全、成本控制」（已决定先忽略）是两回事。

| 层面 | 限制 | 实现 |
|---|---|---|
| 单用户发消息 | 每分钟 30 条，每小时 300 条 | Redis 滑动窗口 |
| 单用户并发会话流 | 同时 5 条 SSE 长连 | Redis 计数，连接断开时释放 |
| 单会话队列 | 20 条（design §6.4） | QueueStore |
| 单进程模型调用并发 | 64 | `asyncio.Semaphore`；满了新回合排队等待，等待超过 10 秒返回 `model_unavailable` |
| 单回合工具调用 | 4 次 | 图内计数（tool-mcp 文档第 4 节） |
| 单回合 token | 输入 16k、输出 4k | `token_budget` 中间件 |
| 上传 | 见第 5 节 | |

模型并发上限要按网关配额设置：上限之和（副本数 × 64）不能超过网关允许的并发，否则限流会发生在网关侧，表现为大量 `model_unavailable`。

## 8. 配置

### 8.1 原则

1. **一个来源一种东西**：密钥只在环境变量；结构化配置（路由、记忆、MCP、产品）在仓库的 yaml；数据资产（角色、skill）在仓库目录。
2. **启动时全部校验**：类型、取值范围、引用关系（路由里引用的模型、角色引用的 skill、MCP 引用的环境变量）。任何一项不过就拒绝启动。
3. **不热更新**：改配置就重启。热更新带来的「一半请求用旧配置」比重启的几秒停顿难排查得多。
4. **领域层不读配置**：配置在组合根解析成不可变对象，注入到需要的地方（architecture §4 的 `domain-pure` 契约）。

### 8.2 文件

| 文件 | 内容 |
|---|---|
| `/etc/agent-api/env` | 全部密钥与地址（权限 600） |
| `config/llm/routing.yaml` | 场景 → 模型链（design §8.2） |
| `config/memory.yaml` | memory_hub 的应用与后端（design §10.4） |
| `config/mcp.yaml` | MCP server（tool-mcp 文档 3.3） |
| `config/products.yaml` | 产品声明：skill、中间件启用、工具白名单 |
| `config/limits.yaml` | 第 7 节的所有数值 |
| `config/deerflow/runtime.yaml` | 仅在 P0 验证需要时才存在（prompt-skill 文档 3.3） |

### 8.3 环境

| 环境 | `COMPANION_ENV` | 差异 |
|---|---|---|
| 本地 | `dev` | 允许 `allow_all` 验证器与 Fake 大脑；MySQL/Redis 用 docker compose |
| 测试 | `test` | 单测全部用 Fake 端口；集成测试用真实适配器 + 假服务 |
| 预发 | `staging` | 与生产同配置、同代码，独立的库和桶；真实模型 |
| 生产 | `prod` | 全部启动检查生效（`allow_all`、Fake 大脑、缺失配置都拒绝启动） |

### 8.4 现有配置文件的问题与处理

| 文件 | 问题 | 处理 |
|---|---|---|
| `config/deerflow/config.yaml` | sqlite checkpointer 与无状态设计冲突，多副本下不可用；模型、skill 段在工厂路径下不再需要 | P0 删除 |
| `config/llm/routing.yaml` | 只有 `companion_chat` 等 3 个场景，缺 `chat`、`solve_text`、`solve_vision`、`title` | P0 按 design §8.2 补齐 |
| `src/companion/config.py` | `Settings` 是全局单例，被 `prompt/`、`server/` 直接 import | 改为只在组合根实例化 |

## 9. 发布与回滚

- 数据库迁移只做**向前兼容**的变更：先加列、双写，下一个版本再删旧列。这样任何时候都能回滚到上一版代码。
- 发布：新版本实例起来 → `/readyz` 通过 → 切流量 → 旧实例 SIGTERM（回合有 45 秒收尾，见 prompt-skill 文档 3.5）。
- 回滚：切回旧版本即可；不回滚迁移。
- 提示词与配置改动随代码发布，记录在 `chat_turn.prompt_version`，回滚代码即回滚提示词。

## 10. 数据保留

| 数据 | 保留 |
|---|---|
| 会话与消息 | 直到用户删除或注销 |
| 软删除的会话、消息 | 30 天后物理删除（`softdelete.purge`） |
| 回合事件流（Redis） | 空闲 30 分钟后过期 |
| 工具审计 | 90 天；确认记录的参数原文处理完 7 天后清除 |
| 未引用的上传 | 24 小时 |
| 日志 | 30 天 |
| 记忆（L1–L3） | 直到用户删除或注销 |

## 11. 容量估算与备份

### 11.1 容量估算

估算的瓶颈是**同时在生成的回合数**，不是用户数：回合大部分时间在等模型的 token，CPU 很空，资源占用主要是内存里的长连与协程。

| 假设 | 取值 |
|---|---|
| 日活 | 1 万 |
| 高峰小时在线占日活 | 15% → 1500 人在线 |
| 在线用户中正在等回复的比例 | 10% → 150 个并发回合 |
| 单回合平均时长 | 8 秒（首 token 1.5 秒 + 输出） |
| 每个在线用户的 SSE 长连 | 1 条 → 1500 条 |

推导：
- 150 个并发回合 ÷ 每进程模型并发上限 64（§7）→ **至少 3 个 API 进程**，取 4 个留余量。一台 4 核 8G 起 4 个 worker 进程即可。
- 1500 条 SSE 长连：每条约 50 KB 内存，合计约 75 MB，不是瓶颈；nginx 的 `worker_connections` 需要 ≥ 4096。
- Redis：事件流按每个活跃会话 2000 条上限、每条约 300 字节估算，1500 个活跃会话约 900 MB 上限；空闲 30 分钟过期后实际远小于此。给 2 GB。
- 模型网关：150 并发是硬性要求，**必须先确认网关配额**，否则扩 API 进程没有意义。

日活到 10 万时，按同样比例是 1500 个并发回合：API 扩到 24 个进程（6 台），Redis 换成集群，网关配额成为第一约束。

压测在 P1 结束时做：用 §14 端到端脚本的「连发」场景，逐步加并发直到首 token P95 超过 4 秒，记录拐点。

### 11.2 备份与恢复

| 存储 | 备份 | RPO | 恢复 |
|---|---|---|---|
| MySQL `agent` 库 | 每日全量 + binlog | ≤ 5 分钟 | 全量恢复后回放 binlog；每季度做一次恢复演练 |
| Qdrant | 每日 snapshot（每个 collection） | ≤ 24 小时 | 恢复 snapshot；**L1 记忆可以从 MySQL 的消息重新抽取**，所以向量库丢失是可恢复的，只是要时间 |
| Redis | 不备份 | — | 只有缓存、锁与 30 分钟内的事件流；丢失后客户端收到 `gone` 重新拉历史 |
| OSS | 开启版本控制，删除保留 7 天 | — | 误删可恢复；注销删除的对象在 7 天后才真正消失，需要在隐私政策里写明 |
| 配置与数据资产 | 在 git 仓库里 | — | 重新部署 |

注意：备份里包含已注销用户的数据，直到备份过期。备份保留 30 天，隐私政策要写明「注销后 30 天内从备份中清除」。
