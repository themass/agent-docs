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

## 4. 配置检查

上线前确认：MySQL 可连接且迁移成功；Redis key 前缀是 `jc:prod:`；TOS bucket、endpoint、region、AK/SK 正确并可读写 `jc/prod/`；CDN/签名下载策略符合域名和时效要求。
