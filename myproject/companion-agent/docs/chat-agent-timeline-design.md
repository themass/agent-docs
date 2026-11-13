# 时间线持久化设计（与聊天对齐）

日期：2026-11-11
状态：已实现（本文第 1–8 节即实现依据；第 10 节是当时的待确认项，已按默认值实现，见 §11）
范围：`myproject/companion-agent`。替换现在的进程内时间线（`adapters/timeline/memory.py`，重启即丢、多副本互不可见）。

---

## 1. 时间线是什么，和别的东西怎么分

| 东西 | 例子 | 存在哪 | 谁来用 |
|---|---|---|---|
| 消息 | 「我下周三下午两点面试」 | `ca_chat_message` | 界面、原始存档 |
| 事实记忆 | 「用户在找前端的工作」 | `ca_memory_item`（按角色分空间） | 召回进提示词 |
| **时间线事件** | 「下周三 14:00 面试」 | **`ca_timeline_event`（新）** | 召回进提示词、`recall_events` 工具、记忆页 |
| 提醒 | 「周三 13:30 叫我出门」 | `ca_reminder` | worker 到点发起主动回合 |

- 时间线记的是**用户生活里带时间点的事**，本身不会触达用户。
- 提醒是**要服务端到点去做的事**，会触达用户，所以必须经用户确认。
- 两者可以关联：一条事件可以挂一条提醒（`reminder_id`），但提醒的创建、认领、发送只走 `ca_reminder` 这一条路径。现在旧的 `InitiativeScheduler.due_between` 扫时间线的做法退役。

## 2. 对齐聊天的四个原则

1. **同一个隔离范围**：和记忆一样按「用户 + 角色」隔离。和林澈说的面试，苏黛不知道。
2. **能追溯到消息**：每条从对话里得来的事件都记下 `source_message_id`（用户消息的 id）。消息被删除或编辑时，由它得来的事件跟着删除或作废，和对话线程的处理方式一致（见第 5 节）。
3. **写入点和记忆一样**：回合里由工具写（`remember_event`），回合后由 `Recorder` 写（后台任务，按 `turn_id` 幂等）。不再用进程内中间件。
4. **只放在 Postgres**：没有进程内状态，多副本、API 与 worker 读到的是同一份。注销时按 `owner_id` 一起删除（实现时把新表加进 `SqlAccountStore` 的删除列表；现在注销调用的是进程内时间线的 `delete_user`）。

## 3. 表结构

```sql
CREATE TABLE ca_timeline_event (
  id                 BIGSERIAL PRIMARY KEY,
  public_id          VARCHAR(26)  NOT NULL UNIQUE,     -- ULID，对外暴露
  owner_id           BIGINT       NOT NULL,
  role_id            VARCHAR(128) NOT NULL,            -- 空串 = 用户级（记忆页手动添加）
  session_id         BIGINT       NULL,
  source_message_id  BIGINT       NULL,                -- 由哪条用户消息得来；手动添加为空
  origin             VARCHAR(16)  NOT NULL,            -- tool | extracted | manual
  kind               VARCHAR(16)  NOT NULL,            -- interview | birthday | exam | appointment | anniversary | trip | other
  title              VARCHAR(60)  NOT NULL,
  at_utc             TIMESTAMP    NOT NULL,            -- 首次发生时间（UTC）
  timezone           VARCHAR(64)  NOT NULL DEFAULT 'Asia/Shanghai',
  all_day            BOOLEAN      NOT NULL DEFAULT FALSE,  -- 生日、纪念日按当地日期，不按时刻
  recurrence         VARCHAR(16)  NOT NULL DEFAULT 'none', -- none | yearly | monthly | weekly
  next_at_utc        TIMESTAMP    NULL,                -- 下一次发生时间，写入与状态变化时重算，用于按时间查
  status             VARCHAR(16)  NOT NULL DEFAULT 'scheduled', -- scheduled | done | cancelled | missed | stale
  confidence         REAL         NOT NULL DEFAULT 1.0,
  reminder_id        BIGINT       NULL,                -- 挂了提醒时指向 ca_reminder
  dedupe_key         VARCHAR(64)  NOT NULL,            -- 见下
  created_at, updated_at TIMESTAMP NOT NULL,
  UNIQUE (owner_id, role_id, dedupe_key)
);
CREATE INDEX ca_ix_tl_owner_role_next ON ca_timeline_event (owner_id, role_id, status, next_at_utc);
CREATE INDEX ca_ix_tl_source ON ca_timeline_event (source_message_id);
```

- `dedupe_key` = 标题归一化后 + 当地日期的哈希。同一件事被工具和回合后抽取各记一次，只留一条（后写的补全字段，不新增）。
- `next_at_utc`：重复事件（生日）的「下一次」由领域代码算好存下来，查询直接按索引取，不在查询时循环。
- 每月重复改为按日历月推进（现在的实现是加 30 天，会漂移）。

## 4. 端口

现在的 `TimelinePort` 用字符串 `user_id`、没有角色维度。改成与提醒、记忆一致：

```python
class TimelineStore(Protocol):
    async def upsert(self, event: TimelineEventDraft) -> TimelineRecord: ...          # 按 dedupe_key 幂等
    async def upcoming(self, *, owner_id: int, role_id: str, now: datetime,
                       horizon: timedelta, limit: int) -> list[TimelineRecord]: ...
    async def recent_past(self, *, owner_id: int, role_id: str, now: datetime,
                          window: timedelta, limit: int) -> list[TimelineRecord]: ...
    async def list_for_owner(self, *, owner_id: int, role_id: str | None, include_past: bool,
                             limit: int, offset: int) -> list[TimelineRecord]: ...
    async def set_status(self, *, owner_id: int, public_id: str, status: str) -> bool: ...
    async def delete(self, *, owner_id: int, public_id: str) -> bool: ...
    async def by_source(self, *, owner_id: int, message_id: int) -> list[TimelineRecord]: ...
    async def mark_stale(self, *, owner_id: int, message_id: int) -> int: ...
```

实现：`adapters/store/sql/timeline.py`（Postgres，兼容 MySQL）。`InMemoryTimeline` 保留为测试替身，实现同一个协议。

## 5. 和聊天操作的联动

| 聊天里发生了什么 | 时间线怎么变 |
|---|---|
| 用户说「下周三两点面试」 | 回合里模型调用 `remember_event`（`origin=tool`）；回合后 `TimelineRecorder` 再抽取一次（`origin=extracted`），按 `dedupe_key` 合并 |
| 用户删除这条消息 | `HistoryService.delete` 同时删除 `source_message_id` 指向它、`origin≠manual` 的事件；挂着的提醒一起取消 |
| 用户把消息改成「面试改到周四」 | `HistoryService.edit` 把旧事件置 `stale`，入队 `timeline.reextract`（只针对这一条消息重抽，按新内容写入） |
| 重新生成回复 | 不影响：事件只从用户的话里来 |
| 删除整个会话 | 会话软删除时，该会话来源的事件置 `stale`（不删：用户可能还想在记忆页看到）；会话物理清理时删除 |
| 注销账号 | 按 `owner_id` 物理删除（注销链路已实现，新表加入删除列表即可） |
| 用户在记忆页删除 / 标记完成 | `delete` / `set_status`；挂着的提醒一起取消 |

所有联动都在 `HistoryService` 已经拿着会话锁的地方做，与回合互斥，不会出现回合正在写入、同时被删除的情况。

## 6. 读：进提示词的方式

`TimelineRecaller` 改为两段：

- **将来的**：`upcoming(horizon=14 天, limit=5)`，渲染成「11-20 周三 14:00 面试」。
- **刚过去的**：`recent_past(window=2 天, limit=2)`，让角色能自然地问「面试怎么样了」。之后状态由模型调用工具或回合后抽取更新为 `done` / `missed`，不再被提起。

都只取当前角色、`status=scheduled`（刚过去的也包括 `scheduled`，表示「还不知道结果」）。

## 7. 和提醒的关系

- `create_reminder` 工具（需确认）建 `ca_reminder`；如果这次提醒对应一件事（「面试前半小时叫我」），同时 `upsert` 一条事件并写入 `reminder_id`。
- 只从事件**自动**推导提醒（例如生日当天主动祝福）是产品决定，默认关闭；打开时也走同一个 `ReminderService`，并且只对 `confidence ≥ 0.9` 且用户确认过的事件生效。一次误报的打扰，比少一次提醒代价大。
- 旧的 `InitiativeScheduler` 与 `domain/proactive/policy.py` 里按时间线扫描的逻辑在新栈里不再使用，迁移完成后删除。

## 8. 接口（客户端）

沿用 `/api/agent/v1/memory/events`，增加 `role_id` 查询参数（已经加了过滤），响应里的 `id` 改为 `public_id`，增加 `status`、`all_day`、`recurrence`、`reminder_id`。`PATCH /events/{id}` 现在返回 501，改为真正更新状态。

## 9. 实施步骤

1. 迁移 `0004_timeline`（Postgres 的 `0001` 基线同步加表）、`SqlTimelineStore`、领域里的 `next_occurrence` 改日历月并计算 `next_at_utc`。
2. 端口换成 `TimelineStore`；`InMemoryTimeline` 改成同一协议。
3. 工具（`remember_event`、`recall_events`、`create_reminder`）与 `TimelineRecaller` 改用新端口。
4. `TimelineRecorder`（回合后抽取，后台任务，按 `turn_id` 幂等）。
5. `HistoryService` 的删除、编辑联动和 `timeline.reextract` 任务。
6. 记忆页接口的状态更新；Android 端的事件列表（如需要）。
7. 测试：Postgres 集成测试覆盖幂等合并、按角色隔离、删除或编辑消息后的联动、重复事件的下一次时间、注销。

## 10. 待确认

- 刚过去的事件要不要主动追问（「面试怎么样了」）？设计里只在用户来聊天时自然提起，不主动发消息。
- 生日、纪念日要不要自动生成提醒（第 7 节，默认关闭）？
- 用户级事件（记忆页手动添加、`role_id` 为空）是否对所有角色可见？设计默认**不可见**，与「记忆按角色隔离」一致；如果希望手动添加的事情所有角色都知道，可以改为用户级事件对所有角色可见。

## 11. 实现记录（与设计的差异）

已实现，代码位置：

| 部分 | 位置 |
|---|---|
| 表 | `ca_timeline_event`（schema + `0001` 基线 + `0004` 迁移） |
| 存储 | `adapters/store/sql/timeline.py`；测试替身 `adapters/timeline/memory.py` 同协议 |
| 协议 | `ports/timeline.py` |
| 回合后抽取 | `app/timeline/recorder.py` + `timeline.record` 任务（按用户消息 id 去重） |
| 联动 | `app/chat/history.py` 的删除 / 编辑 |
| 工具 / 召回 / 接口 | `app/tools/builtin.py`、`memory/recallers.py`、`api/http/routers/memory_v1.py` |

与本文设计的差异：

1. `at` 统一按 UTC 存（`at_utc`），`timezone` 列保留但暂不使用：客户端与 Java 侧传的时间已经带时区，
   按 UTC 比较与展示都正确；分时段问候需要当地时区时再接。
2. 重复事件的下一次直接从原始时间按日历推进（1 月 31 日的每月事件不会漂到 28 日），没有逐次累积。
3. 会话**软删除**时不处理事件（用户可能还会在记忆页看到）；只有会话物理清理时删除。注销时随关系库删除。
4. 模型不按 `timezone` 做「三天后」的换算：抽取提示词要求输出 ISO8601 绝对时间，模型从对话上下文推断。
5. §10 的三个待确认项按默认值实现：刚过去的事只在用户来聊天时提起（不主动发消息）；生日不自动生成提醒；
   手动添加的事件（`role_id` 为空）不对任何角色可见。
