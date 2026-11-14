# QA-PERF-PATHS 执行结论

- **状态**：已执行（2026-11-14）
- **任务书**：`docs/operations/QA-PERF-PATHS.md`
- **基线**：agentkit `29 → 40` passed；server 原 `983 passed / 1 failed`（`test_export_lifecycle[pdf]`，与本轮无关）

## 1. 新增/修改的测试文件

| 文件 | 覆盖 |
|---|---|
| `libs/agentkit/tests/test_caching_session_store.py` | T1 会话缓存撤销 / 负缓存 / 命中不打 Redis / ttl=0 |
| `libs/agentkit/tests/test_observability.py`（追加） | T4 双进程合并、无 env 不写 mmap、残留文件、mark_worker_exit 实态 |
| `backend/server/tests/test_agent_trace_batch.py` | T2 append_batch 连续性 / 显式 seq / 空批 / 并发 |
| `backend/server/tests/test_llm_audit_queue.py` | T3 队列满丢弃、告警节流、关闭 drain、开关关闭 |
| `backend/server/tests/test_commit_now_flush.py` | T5 confirm 先落库、soft 可攒批、异常丢 pending（xfail） |

## 2. 变异测试记录（改坏 → 红 → 改回）

| 项 | 变异 | 结果 |
|---|---|---|
| **T1** | `CachingSessionStore.revoke` 内 `publish` 改为 `pass` | `test_peer_cache_drops_on_broadcast` **FAIL**（peer 缓存仍命中）；恢复后 PASS |
| **T2** | `append_batch` 改为每条 `next_seq` | 在 sqlite + 模拟锁下并发测试因 `database is locked` 红（sqlite 局限，非“仍绿”）；恢复后 6 PASS。结论：并发唯一性依赖锁；sqlite 不能替代 Postgres `FOR UPDATE` |
| **T3** | `stop_audit_writer` 跳过 `queue.join()` | `test_stop_waits_for_queue_drain` **FAIL**（written=0）；恢复后 PASS |
| **T4** | （已有）不设 `PROMETHEUS_MULTIPROC_DIR` | `MULTIPROCESS_MODE=False` 且目录文件数 0 — PASS |
| **T5** | `_COMMIT_NOW_EVENT_TYPES` 去掉 `confirm` | `test_confirm_is_committed_before_it_is_yielded` **FAIL**；恢复后 PASS |

## 3. 哪几条优化「有证据」，哪几条「看起来对」

### 有证据
- **T1 会话缓存 + 撤销广播**：本地 cache 命中时 Redis `GETEX` 次数为 0；revoke 后本进程 key 消失且会 publish；双实例共享 fake pubsub 时 peer 缓存被清掉。去掉 publish 后 peer 测试必红。
- **T2 批量 seq（单连接路径）**：两次 `append_batch` 得到 `0..n` 连续无洞；空列表不推进；显式 `seq` 不被覆盖。
- **T3 审计队列**：满队列 `submit_call` 不抛不堵；每 100 丢弃告警一次；`jc_llm_log_enabled=false` 不入队；`stop_audit_writer` 会等到 drain（变异去掉 join 即红）。
- **T4 多进程合并**：A+3 / B+2 → scrape count=5；无 env 不写 mmap。
- **T5 confirm 先提交**：流式 yield `confirm` 时库中已有对应行；去掉 confirm∈COMMIT_NOW 测试红。thinking/tool_start 允许攒批（中途读库行数可小于终态）。

### 仍然「看起来对」或已证伪
1. **BUG — `mark_worker_exit` 对 histogram 无效**  
   `prometheus_client.multiprocess.mark_process_dead` **只删 gauge_*.db**。`record_agent_phase` 是 histogram，调用 `mark_worker_exit()` 后死 worker 的样本仍计入（2+7=9）。注释承诺「不再计入」对当前指标族不成立。`backend.sh` 清空 mmap 目录仍是唯一可靠兜底（与任务书已知项一致，但 **mark_worker_exit 本身不能当证据**）。
2. **BUG — 回合中途异常丢失 pending soft events**  
   `stream_message` 无 `finally` 刷 `pending_rows`。boom 在 thinking/tool_start 入队之后时，库里只剩 `system_prompt`/`user_message`。测试 `test_exception_mid_turn_still_persists_accumulated_rows` 以 **`xfail(strict=True)`** 钉住，未改产品代码。
3. **T2 并发在 sqlite 上不能证明生产锁**  
   无应用层锁时双连接 `append_batch` 撞 `UNIQUE(session_id,seq)`。有模拟锁则唯一。生产依赖 Postgres 行锁 — **本轮未连生产库验证**。

## 4. 性能数字（本地，当前值）

| 指标 | 测法 | 结果 |
|---|---|---|
| 认证 Redis 命令数 | FakeRedis 计数 | 缓存命中 **0**；`ttl_seconds=0` 时 **1** |
| `submit_call` 入队耗时 | 1000 次平均 | **~212 ns/次**（不阻塞） |
| 回合 commit 次数 | 未做完整前后对比；T5 行为测试表明 soft 事件可攒批、confirm 立即 commit | — |

## 5. T6 端到端

未跑完整本地服务回合（本轮优先 T1–T5「能红」）。T2/T5 的 sqlite 集成路径已覆盖「batch 落库 / confirm 先于 yield」；真实 harness 回合可作为后续补项。

## 6. 真 bug 清单（未顺手修）

1. `mark_worker_exit()` 无法从合并 scrape 中剔除 histogram/counter 死 worker 样本。
2. `AgentService.stream_message` 在流中异常时不 flush `pending_rows`，已攒 soft events 丢失。
