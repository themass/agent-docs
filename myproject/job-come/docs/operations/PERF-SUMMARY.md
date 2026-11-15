# 性能优化：方案与步骤总结

- **状态**：已完成部分 + 未完成清单
- **最后更新**：2026-11-15
- **适用**：JC 全部服务端路径；组件部分可复制到其它 agent 服务
- **相关**：ADR-009（回合延迟）、ADR-010（请求路径）、[`QA-FULL-VERIFICATION.md`](QA-FULL-VERIFICATION.md)

## 0. 一句话结论

这套系统的慢**几乎都不是模型慢**，而是三件事：**跨地域数据库 × 高频往返**、
**把用不到的数据取回来**、**预算给了不够的时间**。三次优化都是先量后改。

---

## 1. 方法与顺序（这套流程可以复用）

1. **先分段打点，再谈优化。** 没有分段数据时，所有判断都是猜。
   第一轮把「615 次 MCP 握手」读成「缓存失效」，白查一轮——实测 4 次调用只有 1 次重建。
2. **把「总耗时」拆成「往返次数 × 单次往返耗时」。** 这一拆就发现了根因：
   生产机到数据库 ping **169ms**，是跨地域链路，不是内网。
3. **改动前测量，改动后同一口径再测。** 否则无法判断是"改了"还是"改对了"。
4. **把结论钉成测试。** 每条优化都配一个在其被回退时会失败的测试（见 §5）。

---

## 2. 已完成的优化

### 2.1 回合耗时：checkpoint 从 85 次往返降到 3 次

| 指标 | 改前 | 改后 |
|---|---|---|
| 单回合 checkpointer 往返 | 85（55 次写） | 3 |
| 单回合数据库耗时 | ~25 秒 | 0.6 秒 |
| 预热后回合总耗时 | 16.5 秒 | **4.1–4.5 秒** |

**根因**：LangGraph 默认 `durability="async"`，每个图步骤写一次 checkpoint。
一回合 28 个步骤 → 28 次 `put` + 27 次 `put_writes`。默认假设数据库在近处，而这里在 169ms 外。

**修法**：`CONFIG_KEY_DURABILITY: "exit"`，放 runnable config 而非 `stream()` 参数
（子图会继承前者，后者覆盖不到）。

**为什么安全**：JC 的图从不调 `interrupt()`；取消会保留已落库的消息；跨回合记忆实测正常。
`tests/test_checkpoint_durability.py` 钉住这三条，有人装 HITL 中间件会失败——那是唯一会让
`exit` 不安全的改动。

### 2.2 请求路径：数据库和 Redis 移出请求热路径

见 ADR-010。要点：鉴权与台账不在每个请求上做写操作。

### 2.3 管理后台列表：不再取 1.35MB 的无用列

| 指标 | 改前 | 改后 |
|---|---|---|
| `select *` limit 100 | 1190 ms | — |
| 去掉 payload 列 | — | **374 ms** |
| 接口端到端 limit=100 | 2818 ms | 1784 ms |

**根因**：`select(LlmCall)` 会把 `prompt_text`/`response_text`/`reasoning_text` 三个 LongText
全部取回——113 行里共 **1.35MB**（其中 prompt 1.19MB），而全部其它列加起来只有 ~9KB。
列表接口的响应模型根本没有这些字段，取回来就丢。

**修法**：列表查询加 `defer()`；详情接口不受影响（它按 id 取一行，`include_payload` 决定是否返回）。

**测试**：断言**生成的 SQL 不含这三列**，而不是断言耗时——耗时测试需要真实远端库才会失败，
而 SQL 断言在 `defer` 被删掉的那一刻就失败，那才是真正的回归。

### 2.4 简历修复轮：40 秒预算必然超时

**现象**：生产日志里 8 次修复有 **4 次** 是 `Preview repair unavailable; keeping first draft:
TimeoutError`，没有一次是被拒绝——全是时钟。

**根因**：修复轮复用完整 writer prompt（约 14k input tokens，为了让"事实"只有一个定义），
输入是第一遍的数倍，却只给 40 秒；而 writer 整条链 120 秒、两跳，每跳约 48 秒。

**为什么一直没被发现**：它优雅降级——用户拿到第一稿，预览照常成功，只是修复功能看起来
从没触发过。只有审计日志能看出区别。

**修法**：提到 60 秒（writer 120 + repair 60 + 开销仍在 240s SSE 预算与 255s 浏览器看门狗内）。

**测试**：钉住**预算关系**（repair ≥ 一跳 writer；两者之和 < 流预算），而不是耗时。

### 2.5 组件化观测（`agentkit.observability`）

- 指标：`llm_calls` / `llm_call_duration_seconds` / `llm_attempts_per_call` /
  `agent_phase_duration_seconds` / `agent_turns` / `agent_turns_in_flight` /
  `method_duration_seconds` / `method_calls`
- 端点：`/metrics`（Prometheus）、`/metrics/snapshot`（JSON，管理后台用）
- 多进程：`PROMETHEUS_MULTIPROCESS_DIR` 在 Python 启动前导出；死进程的 live gauge 由
  `prune_dead_workers()` 在读路径清理
- 多服务：`JC_METRICS_PEERS` + 管理后台服务切换

§2.1 的结论正是靠它才拿到的——只看总耗时看不出是数据库。

### 2.6 冷启动预热

`JC_DEERFLOW_PREWARM`（默认开）：启动时构建 entry role 的图，把冷启动的 4–8 秒
从「部署后第一个用户」挪到启动阶段。

### 2.7 前端等待反馈

等待提示原先只出现约 0.6 秒——判断条件要求"没有任何活动"，而 harness 几乎立刻发 `skill` 事件。
改为判断"还没产出回答文本"，10–16 秒静默期始终有反馈。

---

## 3. 当前耗时基线（2026-11-15 生产实测）

| 路径 | 实测 | 判断 |
|---|---|---|
| 单次 DB 往返 | 175 ms | 跨地域，是很多问题的乘数 |
| 纯对话回合（coach） | 28–41 s | 偏慢，见 §4 |
| coach 场景 LLM 调用 | avg 7.5s / p50 6.8s / p95 12.9s | 正常 |
| **writer 场景 LLM 调用** | **avg 29.4s / p50 23.7s / p95 73.7s / max 82.9s** | **慢，见 §4** |
| 导出 HTML | 20.2 s | 偏慢但可接受 |
| 导出 PDF | 13.7 s | 可接受 |
| 导出 DOCX | 4.8 s | 正常 |
| `/admin/llm/calls?limit=100` | 1.8 s | 已从 2.8s 改善，仍偏慢 |
| `/admin/metrics` | 0.9–1.6 s | 可接受 |

---

## 4. 仍未解决（明确列在这里，不含糊）

| 事项 | 现状 | 下一步 |
|---|---|---|
| **writer 场景 LLM 慢**（p95 73.7s） | 已定位：平均 prompt 5243 tokens，输出长文档；`max_tokens` 默认 100000 | 按实际输出长度设上限；评估换模型；分块生成 |
| **纯对话回合 28–41s** | 其中模型约 7.5s，其余在建图、工具、checkpoint | 继续分段计时，看 20s 花在哪 |
| **`/admin/llm/calls` 1.8s** | 已去掉 1.35MB payload；剩余是 4 次往返 × 175ms + 返回体 | 合并计数查询；减少往返 |
| 数据库跨地域 175ms | 结构性 | 迁移或加读副本——这是所有延迟的地基 |

---

## 5. 怎么验证这些优化没被回退

```bash
cd docs/myproject/job-come/backend/server
.venv/bin/python -m pytest tests/test_checkpoint_durability.py \
  tests/test_llm_call_list_columns.py \
  tests/test_preview_budget_relationship.py -q
```

三个测试的共同设计：**断言机制，不断言耗时**。
耗时测试需要真实远端数据库或网关才会失败，而机制断言在改动被回退的瞬间就失败。

---

## 6. 步骤回顾（如果要再做一次）

1. 分段打点（`agentkit.observability`），拿到 ttft / generate / turn / tool 各段耗时。
2. 算「往返次数 × 单次往返」，找出被放大的那一项。
3. 只改一项，用同一口径复测。
4. 把结论写成测试。
5. 更新本文件的基线表。
