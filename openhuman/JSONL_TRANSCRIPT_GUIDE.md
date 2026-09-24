# OpenHuman 会话 Transcript 与五本账导读

> **定位**：持久化专题 — thread 消息如何变换、落盘、投影；QueueMode 动哪本账。  
> **循序渐进导读**：[DESIGN_THINKING_SERIES.md §8](./DESIGN_THINKING_SERIES.md#第-8-步五本账与记忆双通路) · [图解 HTML](./diagrams/design-thinking-series.html)  
> **深潜**：[ARCHITECTURE.md §I.6–I.9](./ARCHITECTURE.md#i6-多份对话副本谁才是真相) · `threads/transcript_view/`

---

## 先回答一个问题

**用户发了一句 chatSend，这句话最后落在哪？**

答案不是「一个 JSONL 文件」这么简单。OpenHuman 同时维护 **五本账**（概念账本），UI 只见其中一本的 **Socket 投影**。读 bug 时先问：**哪本账错了？**

---

## 1. 与 Pi / Codex 对照（迁移心智用）

| 概念 | Pi | Codex | OpenHuman |
|------|-----|-------|-----------|
| 磁盘主格式 | JSONL `Entry` 树 | Rollout `RolloutItem` 行 | transcript 行 + sqlite memory |
| 模型当前所见 | entries 投影 | `ContextManager` | harness 工作集（账 B） |
| UI 所见 | AgentEvent / TUI | `EventMsg` | Socket `chat_delta`（账 A） |
| 长记忆 | notes 扩展 | Memories pipeline | **vault / memory tree** |
| 中途输入 | steer 队列 | `pending_input` 邮箱 | **QueueMode** 五态 |

**校正**：OpenHuman **没有** Codex 式三真相分裂到三个子系统；但 **A/B/E/vault 仍可能短暂不一致**（例如 Steer 已注入 B，E 尚未 append）。

---

## 2. 五本账速查

| 账 | 符号 | 存储 | 权威消费者 | QueueMode 谁动它 |
|----|------|------|------------|------------------|
| **Socket 投影** | A | 无（流） | React UI | 随 request 生命周期 |
| **harness 工作集** | B | 内存 | 当前 turn LLM | **Steer / Collect** 注入 |
| **history / transcript** | E | 持久 | 下轮 prompt、Resume | **Interrupt** 换新；**Parallel** 快照后 append |
| **memory vault** | V | sqlite 等 | MEMORY.md 注入 | **ingest** 异步，非 steer |
| **turn_state** | T | 运行时 store | 审批 mirror | 绑 `request_id` |

### 为什么需要五本账

| 若只有一本 | 会出的问题 |
|------------|------------|
| 只有 Socket 流 | 无法 Resume、无法审计 |
| 只有 transcript | Steer 中途注入无法在不落盘前让模型看见 |
| 只有 vault | 对话 compact 会污染长期画像 |
| 合并 B 与 E | Steer 会破坏 user/assistant pairing |

→ 产品哲学：[ARCHITECTURE.md §I.6](./ARCHITECTURE.md#i6-多份对话副本谁才是真相)

---

## 3. 四层消息变换（一次请求的变换树）

**为什么先看这里**：调试「UI 有字但模型不知道」「history 有但界面没更新」时，要能对上 **当前在第几层**。

```text
L0  用户输入 (React)
      ↓ chatSend
L1  start_chat 规范化
      · 附件预处理（FILE/IMAGE → 占位符，避免 MB 级 data URI 进扫描/JSONL）
      · prompt 注入扫描
      ↓
L2  Agent turn 输入（run_chat_task 组装）
      ↓
L3  harness 消息（LLM API 形：role/content/tool_calls）
      ↓
L4  transcript 持久化行（账 E）
      ↓
L5  Socket 投影 chat_delta / chat_done（账 A）
```

| 层 | 典型 bug 症状 | 先查 |
|----|---------------|------|
| L1 | 附件导致 embed 失败 | `ops_part_02.rs` ingress 预处理 |
| L3 | 工具结果未回注 | harness `turn.rs` |
| L4 | Resume 后缺消息 | `threads/` persist |
| L5 | RPC 成功但 UI 空白 | Socket 订阅 / `request_id` 关联 |

**权威顺序**：L3–L4 以 harness + `threads/` 为准；**L5 不可当真相**。

---

## 4. Thread / Session / Agent 关系树

```text
Thread（用户可见对话 thread_id）
│
├── web_chat 编排态
│     ├── IN_FLIGHT[thread_id]        主 turn 槽（至多一个）
│     ├── PARALLEL_IN_FLIGHT[request_id]  旁路 turn
│     └── RunQueue                      steer / followup / collect 积压
│
├── THREAD_SESSIONS[thread_id]          Agent 实例缓存（Parallel 禁止写入）
│     └── Agent
│           └── harness.invoke → tool_loop
│
└── 持久层
      ├── transcript / history（账 E）
      ├── turn_state[request_id]（账 T）
      └── memory vault（账 V，thread 可关联）
```

### Parallel 分叉树（与主 turn 并列）

```text
主 turn (fork=false)
  └── 复用 THREAD_SESSIONS → 读写共享 Agent

Parallel turn (fork=true)
  └── 历史快照 at-start → 新 Agent → 完成后 append 到 E
  └── 永不写入 THREAD_SESSIONS（防 clobber）
```

→ [MODULES.md §3.2–3.3](./MODULES.md) · `run_task.rs` `fork` 参数

---

## 5. QueueMode × 账本动作矩阵

**为什么先看这里**：改 QueueMode 或修并发 bug，必须明确 **动哪本账、是否 cancel**。

| 模式 | 账 B | 账 E | 账 A | IN_FLIGHT | 旧 turn |
|------|------|------|------|-----------|---------|
| **interrupt** | 丢弃 | 新 turn 新 user | 旧 `chat_error` + 新流 | 替换 | cancel drop |
| **steer** | checkpoint 注入 | 滞后 append | 继续当前流 | 保持 | 继续 |
| **collect** | 同 steer + 上下文前缀 | 滞后 | 继续 | 保持 | 继续 |
| **followup** | 不变 | turn 结束后再写 | 当前流结束后新流 | 保持→drain | 跑完再开 |
| **parallel** | 独立 B' | 快照 + 完成后 append | 独立 Socket 流 | 旁路槽 | 主 turn 不受影响 |

### Steer 时序（账 B 先于 E）

```text
turn 进行中（账 B 已有 assistant+tool）
  → start_chat(steer) → RunQueue → SteeringForwarder
  → harness 下一 iteration：B 注入 [User steering message]
  → 模型在**同一 turn**内看见新 user
  → turn 结束 → E 批量落盘
```

**校正**：Steer **不**等于 Interrupt；工具可在 checkpoint 前跑完。

→ [IMPLEMENTATION.md §1.4](./IMPLEMENTATION.md)

---

## 6. 记忆双通路（两棵不同的树）

**一句话**：**compact 动对话树；ingest 动知识树**——不要混写成一个「记忆模块」。

```text
通路 A — 短时对话（账 E）
  user/assistant/tool 行
    → token 压力 → compact 摘要/裁剪
    → 仍在 transcript 语义内

通路 B — 长效知识（账 V）
  对话片段 / 文件 / 多源 ingest
    → memory vault / tree 节点
    → MEMORY.md（或等价注入块）→ 下轮 L2 prompt
```

| 操作 | 影响通路 | 用户感知 |
|------|----------|----------|
| 对话 compact | A only | 「它还记得刚才吗」（短时） |
| vault ingest | B | 「它记得我是谁」（长期） |
| Steer | B（当次）| 立刻改当前 turn 方向 |

### 读写时序（概念）

```text
读：build prompt 时
  E 最近 N 轮 + V 注入块（MEMORY.md）+ 系统/技能 prompt

写：turn 结束后
  E append；异步 ingest 可能更新 V（与 turn 解耦）
```

→ [ARCHITECTURE.md §I.9](./ARCHITECTURE.md#i9-记忆双通路短期对话-vs-长期知识库)

---

## 7. 失配症状与排查

| 症状 | 可能账本 | 排查方向 |
|------|----------|----------|
| UI 无字，RPC 有 request_id | A | Socket 连接、`request_id` 过滤 |
| 模型「失忆」上一轮 | E 或 B | Interrupt 是否 cancel；Parallel 是否看错 thread |
| Steer 无效 | B | IN_FLIGHT 是否存在；是否误用 interrupt |
| 长期画像错误 | V | ingest 源；compact 是否误写 vault |
| 审批卡住 | T | `turn_state` mirror；审批 RPC 短路 |
| Parallel 互相覆盖 | THREAD_SESSIONS | 是否 `fork: true`；测试注释 thread_id 唯一键 |

---

## 8. 源码速查

| 行为 | 路径 |
|------|------|
| chatSend 入口 | `app/` chatService → Tauri RPC |
| start_chat / QueueMode | `web_chat/ops_part_02.rs` 等 |
| run_chat_task / fork | `web_chat/run_task.rs` |
| QueueMode 枚举 | `agent/harness/run_queue/types.rs` |
| Steer 队列 | `RunQueue` + SteeringForwarder |
| Transcript 投影 | `threads/transcript_view/` |
| Turn 状态 / 审批 | `threads/turn_state/` |
| Harness turn | `agent/harness/session/turn.rs` |
| Memory tree | `memory/` · `docs/MEMORY_TREE_AND_STORE.md` |

---

## 9. 阅读路径

```text
DESIGN_THINKING_SERIES（运行路径 + QueueMode）
    → 本文件（五本账 + 变换树）
    → IMPLEMENTATION §1 时序图（改代码）
    → ARCHITECTURE §I.6–I.9（图表权威）
```

## 相关

- [diagrams/design-thinking-series.html](./diagrams/design-thinking-series.html) — 浏览器速览  
- [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) — 循序渐进全文
