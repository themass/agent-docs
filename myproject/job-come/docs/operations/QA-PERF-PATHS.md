# QA-性能改动验收：认证缓存、账本批量写、审计队列、多 worker 指标

- **状态**：已执行（见 QA-PERF-PATHS-RESULT.md）
- **目标读者**：Cursor（执行）、项目负责人（验收结论）
- **背景**：ADR-009 / ADR-010 落了 4 项性能改动，其中 3 项**没有测试**。
  本文不是「再跑一遍全量测试」，而是**专门攻击这些改动的假设**。

## 0. 为什么需要这一轮

本轮改动的共同特征：**每一条都是为了减少往返，每一条都能在出错时表现得像正常。**

已实测过一次同类事故：`enable_multiprocess()` 返回 `True`、不写任何文件、
每个 worker 各算各的——面板照常渲染，数字少一半。它不是"没实现"，而是"看起来实现了"。

所以本轮的验收标准不是「测试通过」，而是：**如果这条优化失效了，测试会不会红？**

## 1. 当前基线（先确认，不是结论）

```bash
cd backend/server
PYTHONPATH=/Users/gqli/work/deepagents/libs/agentkit/src \
  JC_BOOTSTRAP_SKIP_REEXEC=1 /Users/gqli/work/deepagents/venv/bin/python \
  -m pytest tests -q          # 984 passed
cd /Users/gqli/work/deepagents/libs/agentkit
PYTHONPATH=src /Users/gqli/work/deepagents/venv/bin/python -m pytest tests -q   # 29 passed
```

**已知缺口（Python，全部无测试）：**

| 符号 | 位置 | 风险 |
|---|---|---|
| `CachingSessionStore` | `agentkit/redis/session.py:150` | 登录态缓存；错了 = 登出不生效 |
| `RedisSessionStore.get_and_touch` | `agentkit/redis/session.py:63` | GETEX；错了 = 登录失效 |
| `AgentTraceStore.append_batch` | `jc/stores/agent_trace_store.py:80` | seq 分配；错了 = 聊天记录顺序错乱/丢失 |
| `call_log.submit_call` | `jc/llm/call_log.py:413` | 审计队列；错了 = 丢审计行 |
| `call_log.stop_audit_writer` | `jc/llm/call_log.py:444` | 关闭时 flush；错了 = 丢在途行 |

## 2. 测试任务（按优先级，每项都要「能红」）

### T1（最高）会话缓存的撤销语义

**要证明的**：登出之后，**另一个 worker** 的缓存也必须失效。

这不是性能问题，是安全问题。缓存 TTL 是 60 秒，广播是兜底之外的唯一手段。

必须覆盖：
1. `revoke()` 之后本进程 `_cache` 里该 key 消失
2. `revoke()` 会 `PUBLISH` 到预期 channel（用 fake redis 断言调用，不要连真 Redis）
3. 收到广播的**另一个** `CachingSessionStore` 实例丢弃自己的缓存
   —— 用两个实例共享一个 fake pubsub 模拟两个 worker
4. **缺失的 session 也被缓存**（负缓存），并在 `revoke` 后不再命中
5. 缓存命中时**不调用** `store.get_and_touch`
   —— 这条是「缓存真的在生效」的唯一证据，否则测了个寂寞
6. `ttl_seconds=0` 时缓存禁用

**必须能红的验证**：把 `revoke()` 里的 `publish` 注释掉，第 3 条测试必须失败。
请在 PR 描述里贴出这个变异测试的结果。

### T2（最高）`append_batch` 的序号连续性

**要证明的**：批量写不产生重复 seq，也不留空洞。

必须覆盖：
1. 同一 session 连续两次 `append_batch`，seq 严格递增且不重复
2. 显式传 `seq` 的项不被覆盖
3. 空列表不分配 seq（不推进计数器）
4. **并发**：两个 batch 同时写同一 session，seq 仍然唯一
   （这是 `next_seq` 的锁在保证的，批量写绕过了它逐条路径）
5. `done` 事件之前所有行已经在库里
   —— 用 fake db 断言 flush 顺序，或在集成测试里打断点

**必须能红的验证**：把 `append_batch` 里的 `start = await self.next_seq(...)`
改成每个 item 都 `seq = await self.next_seq(...)`，第 4 条并发测试应该仍然通过
（那是原来的行为）——所以第 4 条要**真的并发**，不能串行 await。

### T3（高）审计队列的丢弃与关闭

**要证明的**：队列满了丢行而不是卡住；关闭时尽量不丢。

必须覆盖：
1. 队列满时 `submit_call` **不抛异常、不阻塞**
2. 丢弃计数每 100 条才警告一次（不要日志洪水）
3. `stop_audit_writer` 会等待队列排空（最多 5 秒）
4. `jc_llm_log_enabled=false` 时直接 return，不入队

### T4（高）多 worker 指标是真共享

**要证明的**：设了 `PROMETHEUS_MULTIPROC_DIR` 后，两个进程的计数器真的合并。

这一项必须**开两个子进程**（一个进程内测不出来，这正是上轮的 bug）。

1. 进程 A 记 3 次，进程 B 记 2 次 → 合并后 scrape 到 5
2. 不设环境变量时 → `MULTIPROCESS_MODE=False`，不写 mmap 文件
3. `mark_worker_exit()` 之后，该 worker 的数值不再计入
4. 目录里有残留文件时（模拟 SIGKILL）→ 说明现行为如何，并写明是否需要
   `backend.sh` 的清空动作来兜底

参考已有实现：`agentkit/tests/test_observability.py` 的 `_run()` 辅助函数。

### T5（中）`_COMMIT_NOW_EVENT_TYPES` 的边界

**要证明的**：`confirm` / `error` / `done` 确实在 `yield` 之前落库。

这是「批量写」唯一可能伤到用户的地方：用户点了确认，但那一行还没提交。

1. 断言 `confirm` 事件 yield 时，对应 trace 行已 commit
2. `thinking` / `tool_start` 等**不必**立即 commit（允许攒批）
3. 回合中途抛异常时，已攒的行**不丢**（最终 flush 仍执行）

### T6（中）端到端真实回合

用真实服务跑一轮（本地 sqlite 即可，不需要生产）：

1. 建会话 → 发一条消息 → 收完整流
2. 查 `jc_agent_trace`：**同一个回合内 seq 连续、无重复**
3. 查 `jc_llm_call`：有一条对应记录（证明审计队列真的落库了）
4. 中途 abort 流，确认已产生的行仍可读到

## 3. 性能验证（可选，但请给数字）

不需要生产。本地即可，记录改动前后或至少记录当前值：

| 指标 | 怎么测 | 期望 |
|---|---|---|
| 一次认证的 Redis 命令数 | 用 fake redis 计数 | 缓存命中时 0，未命中 1（不是 2） |
| 一个回合的 trace 提交次数 | 计数 `db.commit()` | 显著少于事件数 |
| 审计写入是否阻塞事件流 | 在 `submit_call` 前后打时间戳 | 纳秒级，不是毫秒级 |

## 4. 不要做的事

- **不要连生产数据库**。所有测试用 sqlite 或 fake。
- **不要改生产 `.env`**。
- **不要为了让测试通过而放宽断言**。如果某条测试写不出「能红」的版本，
  在结论里说明原因，而不是删掉它。
- 不要修改 `libs/agentkit` 的公开 API 来适配测试。

## 5. 交付物

1. 新增/修改的测试文件清单
2. **每个 T1–T5 的变异测试记录**（改坏 → 测试红 → 改回）
3. 一份结论：哪几条优化**有证据**，哪几条**仍然只是「看起来对」**
4. 如果发现真 bug，单独列出，不要顺手修完再一起报

## 6. 已知的、不必再报的问题

- `backend.sh` 每次启动清空 mmap 目录 —— 是有意的
- ADR-010 里 `enable_multiprocess` 的描述 —— 已加修正说明，保留原文是刻意的
- `agentkit` 目录当前不在任何 git 仓库里 —— 已知，另行处理
