# B-1 修复方案：worker 死亡导致的消息丢失与孤儿附件

状态：**已实施，本地全绿，待产线验证**（2026-11-18）。§2.1/§2.2 已落地；实现期间发现并修掉了两个连带缺陷：`upload_pending_attachments` 原地改 committed payload 导致 SQLAlchemy 脏检查失效、`storage_pending` 永久落库（现返回新副本）；`resign` 投影未清除内部标记（现投影为 `storage_error` 后弹出 `storage_pending`）。验收测试 `backend/server/tests/test_agent_stream_persistence.py`（9 项，双侧）。产线事故证据见 `CURSOR-TEST-PLAN-2026-11-18.md` 附录 B-1。
撰写日期：2026-11-18。关联提交：`c720cbf`（B-2 单 worker、B-3 毒任务行，均已上线）。

## 1. 现状与丢失窗口

`AgentService.stream_message`（`backend/server/src/jc/services/agent_service.py`）里，用户消息
的 ledger 行（`user_message`，表 `jc_agent_trace`）**不是收到请求就写**，而是作为
`trace_user_message_pending` 在内存中暂存，直到流里出现 `system_prompt_rendered` 事件才随批
落盘（`agent_service.py:417-435, 505-537`）。原因是 `system_prompt` 必须占 seq 0，而它的文本
要到 DeerFlow 惰性构建 agent 后才可知，seq 由 `next_seq()`（锁父行读 max）顺序分配，先写的行
会占掉 seq 0。

于是从请求进来到落盘之间存在一个**只存在于内存和对象存储里**的窗口，且窗口内恰好都是慢操作：

| 步骤（代码顺序） | 耗时来源 | 崩溃后果 |
|---|---|---|
| `offload_for_persistence` 上传附件（`:321`） | 网络 PUT | 对象已入库，**无人引用** |
| `flatten_message_for_text_agent`（`:351`） | **视觉模型调用，秒级** | 消息内容只在内存 |
| provider 包装 / interview 记录（`:383-408`） | DB 查询 | 同上 |
| 首个 `system_prompt_rendered`（`:505`） | agent build / 首 token 前 | 同上 |

worker 进程死亡（SIGKILL / OOM）时 `finally`（`:642-651`）根本没有机会跑——不是不 flush，
是进程没了。2026-11-18 18:06 UTC 生产实测：发图消息中途 worker 377676 死亡（无 Python
traceback，疑似 OOM），该条消息在历史里**完全消失**，图片对象
`jc/prod/agent/agsn_pd8w0k6bu4yzq5ft/attachments/...` 成为永久孤儿。

孤儿无法回收的两个原因：
1. GC 只扫 `jc/<env>/uploads/` 前缀，从不扫 `agent/`；
2. TOS bucket policy 拒绝 `ListObjectsV2 jc/prod/agent/`（`InvalidPathAccess`，见 B-4），
   就算想扫也扫不了。

B-2（`JC_API_WORKERS` 默认 2→1）降低了 worker 被 OOM 杀的概率，但**消息持久化不能依赖
"worker 不会死"**——这是设计问题，不是容量问题。

## 2. 方案（推荐）

### 2.1 用户消息行提前落盘 + `system_prompt` 用显式 `seq=0` 补插

关键观察：`AgentTraceStore.append` / `append_batch` **已经支持显式传 `seq`**
（`stores/agent_trace_store.py:78, 137-141`），只有缺省路径走 `next_seq()`。所以"seq 0 必须
先占"不是必须暂存整行的理由：

- 附件上传完成后（`:325` 之后、`flatten` 之前）立即写 `user_message` 行，`seq` 用 `next_seq()`
  正常分配（首行为 seq 1，seq 0 留空）；行内 `content` = 用户原文，`payload` 带 attachments /
  ui_context，`payload.text`（模型实际收到的包装文本）暂缺。
- 流里 `system_prompt_rendered` 到达时，用**显式 `seq=0`** 插 `system_prompt` 行
  （`append(..., seq=0)`），再把 `payload.text` UPDATE 回用户行。
- `next_seq()` 取 max+1，永远轮不到 0，无碰撞；行锁仍由 `lock_session` 保证。

崩溃窗口从"flatten + agent build + 首事件"缩到"附件 PUT 与行 INSERT 之间的毫秒级"。
worker 死亡后用户刷新历史，消息（含图片）仍在；最多缺一个稍后补齐的 `payload.text`。

需要一并处理：

- 暂存逻辑与 `trace_needs_system_prompt` 判断保留，但只用于 `system_prompt` 行本身，不再
  扣留用户行；`finally` 的 flush 兜底不变。
- 重放顺序：`ORDER BY seq` 下 `system_prompt(0)` 永远第一，`user_message(1)` 次之，与现状
  一致。若第一轮在 `system_prompt` 落盘前崩溃，第二轮补写的 `system_prompt` 仍会落在 seq 0、
  排在两条用户消息之前——顺序合法，仅"归属轮次"错位；`has_system_prompt` 防重语义不变，
  `context_usage.py` 的 token 展示不受影响。**记录为已知取舍。**
- 同一 `message_id` 的行只写一次；重复请求（前端重试）不幂等是**现状既有行为**
  （`client_message_id` 目前只透传给 mock 面试记录，无去重），本方案不扩大它，也先不引入
  去重表——那属于独立的幂等设计。

### 2.2 附件改为"键先行"：孤儿从不可见变为可见可修

现在：PUT 成功 → 写行；崩在中间 → 对象有、行无 → GC 看不见（前缀扫不了）→ 永久泄漏。

改为：key 本来就是 `message_id` 确定性派生（`agent_attachment_service.py:189-194`），
**先写行（含 `storage_key` + `storage_pending: true`），后 PUT，成功后清 pending**。
崩在中间 → 行有、对象无 → 历史里正常渲染并带 `storage_error`（该标记与前端"录音没保存成功"
文案已有，`:223-227`），无对象、无费用、无人看不见的泄漏。方向反过来，泄漏类别从
"不可审计"变成"一条 SQL 可数"。

失败路径保持既有契约：PUT 异常仍不抛出（答案已经在路上，不能因归档失败丢消息），
只记 `logger.warning`（不含 blob、不含预签名 URL，ADR §7.4）。

### 2.3 不做的事

- **不做** WAL / 请求重放队列：2.1 已把丢失面压到毫秒级，重放会把"至少一次"变成
  "重复执行模型调用"的成本与幂等问题，收益不成比例。
- **不动** GC 扫 `agent/` 前缀：TOS policy 拒绝列举（B-4），且 2.2 之后不再产生
  "对象有行无"类别，无需列举。若未来要审计存量孤儿，走 DB 表全量 key + 逐个 HEAD。
- **不改** `finally` flush、`_COMMIT_NOW_EVENT_TYPES`、批次提交策略：与本缺陷正交。

## 3. 验收（双侧，缺一不可）

| # | 通过路径 | 拒绝路径 |
|---|---|---|
| 1 | 发送带图消息 → 历史立即含该行（含 storage_key） | flatten 中途杀任务（monkeypatch 抛进程级异常后重开 service）→ 历史仍含该行 |
| 2 | 正常轮重放顺序 system(0) < user(1) < 其余单调 | 首轮崩在 system_prompt 前 → 第二轮重放仍单调、无重复 system、`has_system_prompt` 只写一次 |
| 3 | PUT 成功 → 行无 pending、URL 可取 | PUT 前杀在行提交后 → 行渲染带 `storage_error`，无悬挂播放器；桶内无该 key |
| 4 | `payload.text` 在 system_prompt 后补齐 | 永远等不到 system_prompt（mock 面试轮）→ 行为与现状一致，text 兜底不缺 |
| 5 | 双账号：历史与图片路由隔离不回退（P1 回归） | 越权 404/403 断言不变 |

测试基座沿用 `tests/test_agent_attachments.py` 的 fixture；进程死亡无法在 pytest 内真模拟，
用"在写行与 PUT 之间抛确定性异常 + 全新 service 实例重新读历史"等价覆盖。

## 4. 改动范围与工作量

| 文件 | 改动 |
|---|---|
| `services/agent_service.py` | 用户行提前写；system_prompt 显式 `seq=0`；payload.text 回填 |
| `services/agent_attachment_service.py` | 键先行 + `storage_pending`/`storage_error` 时序 |
| `stores/agent_trace_store.py` | 预计零改动（seq 入参已有）；若 UPDATE payload 需辅助函数则加一个 |
| `tests/` | 新增 `test_agent_stream_persistence.py`（表 3 全部行，双侧） |

预估半天实现 + 半天测试。无需迁移（无新列；`payload_json` 内加键不涉 schema）。
前端：`storage_pending` 对外表现复用现有 `storage_error` 渲染，无前端改动。

## 5. 上线顺序

1. 本地全绿（含 `./scripts/test-local.sh` 回归）。
2. 生产 `publish.sh --deploy --restart -- --skip-frontend`。
3. 生产复跑附录 B 的图片旅程 + 人工 kill worker 复演一次（`kill -9` uvicorn worker，
   验证消息仍在历史），记录为 B-1 关闭证据。
