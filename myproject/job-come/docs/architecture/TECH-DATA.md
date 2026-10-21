# TECH-DATA：MySQL、Redis、TOS 与命名规范

- **状态**：已确认的 V1 数据与存储约定
- **最后更新**：2026-10-15

## 1. 依赖与用途

| 依赖 | 是否使用 | 用途 |
|---|---|---|
| MySQL | 是 | 用户、档案、职位、面试、应用漏斗、会话关联等持久业务数据 |
| Redis | 是 | 登录/访客会话、邮件验证、密码重置、一次性确认与短期缓存 |
| Volcengine TOS（S3 兼容） | 是 | 原始上传、导出 PDF/DOCX/HTML 等对象 |
| 本地对象目录 | 仅开发兜底 | 未配置 TOS AK/SK 时的本地存储，不用于生产 |

连接配置均在 `backend/server/.env`，模板为 `backend/server/.env.example`；`.env` 不得提交或写入文档。

## 2. 命名硬规则

### Redis

所有 Redis key 使用：

```text
jc:{environment}:{namespace}:{identifier}
```

示例：`jc:dev:guest:<id>`、`jc:prod:email-verify:<token-hash>`。

- `JC_REDIS_KEY_PREFIX` 必须以 `jc:{env}:` 形式配置；
- 禁止使用无前缀、`jobcome:` 或其他项目的 key；
- key 必须设置与业务匹配的 TTL，短期令牌不得无限期保留。

### TOS

所有对象 key 使用：

```text
jc/{environment}/{resource-category}/{resource-id}/...
```

示例：`jc/prod/profile-source/<profile-id>/resume.pdf`。

- 桶可以共享，但对象前缀必须是 `jc/`；
- 下载使用有时效的 presigned URL 或签名 CDN URL；
- 不把原始对象 key 直接当作永久公开链接；
- 原始上传和用户导出物按用户/资源归属校验后访问。

### MySQL

JC 的业务表统一使用 `jc_` 前缀；schema 演进在：

```text
backend/server/alembic.ini      # Alembic 入口（与迁移目录同处 server 工程根）
backend/server/alembic/
```

不要在 JC 项目根保留单独的 `alembic.ini`（旧布局遗留会导致 `script_location` 找不到）。未上线期间不保留旧 `jobcome_*` 兼容表或双写逻辑。所有 schema 修改必须包含 Alembic migration 和回归测试。

### MySQL 会话与连接生命周期

JC **不使用显式事务控制**：没有 `FOR UPDATE`、没有隔离级别覆写、没有 savepoint、没有 `async with db.begin()` 块。原因是 V1 的写入模式本身不需要——绝大多数端点是单表写，少数跨表写只要在同一个 `commit()` 里即可。规则：

1. 一个 HTTP 请求一个 `AsyncSession`（`get_db_session` 依赖注入），`expire_on_commit=False`。
2. 写入靠 SQLAlchemy 默认 autobegin + 一次 `commit()`。Store 层只 `flush()`，**不 commit**；提交点由 Service 决定。
3. 并发写冲突用**乐观锁**而非行锁：`jc_profiles.version` 自增，`PATCH /profiles` 校验 `expected_version`，Agent 侧档案 patch 走 compare-and-swap（版本不符直接拒绝并要求重新生成预览）。
4. 下列操作必须在**同一次 commit** 内完成，拆开会产生无主数据或可重用凭据：

   | 操作 | 涉及表 |
   |---|---|
   | 注册 / 登录（含访客资产认领） | user + session + profile + guest_session |
   | 访客冲突解决 | profile ×2 + guest_session |
   | 重置密码 | user + password_reset（token 置为已用） |
   | 新建档案 | profile + user_meta.active_profile_id |
   | 匹配评分落库 | job + application |
   | 投递流水线 | application + job.tag |
   | 生成双语优化稿 | resume_draft ×2（中/英） |

5. **调模型之前必须释放连接。** 简历生成、简历审稿、JD 解析单次可运行数分钟，连接挂在池里不动会被远端 MySQL 掐断 socket，表现为 API 连接重置（`ECONNRESET` / socket hang up）。统一调用：

   ```python
   from jc.db.session import release_db_connection
   await release_db_connection(self._db)
   ```

   这是**连接寿命问题，不是原子性问题**：调用点之前没有待写数据，rollback 只丢弃读快照。调用之后仍需要的 ORM 对象**必须重新 `get_by_id` 加载**，否则读到的是已脱离活动事务的行。

6. 后台任务（`jc/tasks.py`）自行用 `AsyncSessionLocal()` 开独立 session，不复用请求 session。
7. **LLM 审计日志同理**：`jc/llm/call_log.py` 自己开短 session 写入，不接受外部 session。理由就是第 5 条——到要落日志时，业务请求的那个 session 已经为了调模型被 rollback 释放了。写入失败只记 warning，不影响业务调用。

### 审计与留存

| 表 | 内容 | 留存 |
|---|---|---|
| `jc_llm_call` | 一次逻辑模型调用：分类、调用方、真实生效模型、token、成本、耗时、状态、trace | `JC_LLM_LOG_RETENTION_DAYS`（默认 90 天） |
| `jc_llm_call_attempt` | 链上每次 endpoint 尝试：模型、失败码、是否 `validator_failed`、各自用量 | 跟随父记录 |

`jc_llm_call` 的 `prompt_text` / `response_text` / `reasoning_text` 含**简历正文**，属个人数据：

- 只在 `JC_LLM_LOG_PAYLOAD=true` 时写入，单列上限 `JC_LLM_LOG_PAYLOAD_MAX_CHARS`（默认 6 万字符），超出截断并置 `payload_truncated`；
- 列类型是 `LONGTEXT`（`jc/db/types.py` 的 `LongText`）—— 一份 2 万字中文简历在 utf8mb4 下已超过 `TEXT` 的 64 KB；
- 清理用 `scripts/prune_llm_log.py`（默认 dry-run，`--apply` 执行）。`--forget-payload-after N` 只清正文、保留成本与可靠性指标；
- 管理端详情接口默认不返回这三列，需显式 `include_payload=true`。

设计说明见 [`TECH-LLM.md`](TECH-LLM.md) 第 4.1 节。

### 大对象不进数据表

二进制与媒体一律进对象存储，表里只留 `storage_key`。已有三处遵循同一范式：
简历源文件（`profile_service.upload`）、导出件（`resume_service`）、
舟卡聊天附件（`agent_attachment_service.offload_for_persistence`）。

`jc_agent_message.payload_json` 是 `Text`（MySQL 64 KB），**不是 `LongText`**，
所以聊天里的图片与语音必须先上传再入库。
一张 1280×720 摄像头照片 base64 后约 400 KB，内联写入必然超限。

这里有一个测试结构上看不见的陷阱：**测试跑 SQLite，其 `TEXT` 没有长度限制**，
所以"列放不下"这类缺陷在测试环境永远是绿的。
因此针对列容量的回归必须断言**序列化后的字符串/字节数**，不能指望数据库报错
（见 `tests/test_agent_attachments.py`）。

### 语音：录音在 TOS，文字在表里，两者必须同行

一条语音消息落成两份数据，缺任一份都会让另一份大幅贬值：

| 数据 | 落在哪 | 没有它会怎样 |
|---|---|---|
| 原始录音 | TOS `jc/<env>/agent/<sid>/attachments/<mid>-<i>.<ext>`，行里留 `storage_key` | 「这个数字他到底有没有亲口说过」无从回答 |
| 转写文字 `transcript` | `payload_json` 的 attachment 行内（纯文本，不占容量） | 聊天记录退化成一串谁也搜不到、读不了、引用不了的播放器；本版本服务端无 STT，模型直接读不到这条消息 |
| 时长 `duration_ms` | 同上 | 气泡无法显示长度（webm/opus 容器常报 `duration: Infinity`，问 `<audio>` 元素不可靠，所以由浏览器按墙钟计时上报） |

上传失败时 `storage_key` 为 `null` 并置 `storage_error: true`，同时打一条 warning。
行为上**不抛异常**（轮次已跑完，答案已在回，不能因为存档失败吞掉用户的消息），
但也**不静默** —— 失败行原先与「用户没发媒体」无从区分，是唯一事后查不出来的状态。
`transcript` 在这种情况下仍然保留，所以消息依然值得展示。

## 3. 数据边界

| 数据 | 归属/安全要求 |
|---|---|
| 档案、简历版本、导出物 | 用户私有；用户确认是事实变更的唯一提交点 |
| `payload.evidence_answers` | 用户亲笔补充的源事实，只追加不改写；写入即递增 `profile.version`。模型可引用但不可代写 |
| `payload.preferences.role_family` / `jc_job.role_category` | 岗位族归属。前者是用户的显式选择并优先于一切推断，后者在 JD 解析时写入 |
| `payload.preferences.framing_emphases` | 包装角度（最多 2 个，有序）。**纯呈现偏好、不含事实**，故允许直接写入，不走档案确认；空列表表示回落岗位族推荐 |
| 职位与匹配报告 | 与 profile/user 绑定；来源与读取时间需保留 |
| 模拟面试、真实题、回答 | 个人私有；共享能力后置且需脱敏、显式授权 |
| 密码重置/邮箱验证 | Redis 内保存哈希凭据与用户关联；验证链接和 4 位码共享 TTL，重发/成功即同时失效，验证码最多 5 次失败尝试 |
| Agent 会话 | 用户和业务资源双重归属校验；运行态与业务持久化分离 |
| 聊天附件（图片/语音） | 字节存 `jc/<env>/agent/<session_id>/attachments/`，消息行只留 `storage_key`；下载走短期签名 URL，每次读历史重签 |
| 语音转写文字（`attachment.transcript`） | 用户亲口说的话，与简历正文同级的个人数据。由浏览器识别，与录音写在同一行；本版本服务端无 STT，**它是录音唯一可读的形式** |
| LLM 调用审计（`jc_llm_call`） | 指标与失败码可长期保留；prompt/响应/思考原文含简历正文，受 `JC_LLM_LOG_PAYLOAD` 控制并按留存窗口清理 |

## 4. 配置检查

上线前确认：MySQL 可连接且迁移成功；Redis key 前缀是 `jc:prod:`；TOS bucket、endpoint、region、AK/SK 正确并可读写 `jc/prod/`；CDN/签名下载策略符合域名和时效要求；`JC_LLM_LOG_PAYLOAD` 的取值与留存窗口已明确，并已安排 `scripts/prune_llm_log.py` 定时执行。
