# Codex Rollout / JSONL 树形导读

> **定位**：Rollout / JSONL 持久化专题 — 理解 `~/.codex/sessions/*.jsonl` 行类型与三真相投影。  
> **图解速览**：[diagrams/design-thinking-series.html](./diagrams/design-thinking-series.html)  
> **循序渐进导读**：[DESIGN_THINKING_SERIES.md §8](./DESIGN_THINKING_SERIES.md#第-8-步持久化-harness-与三真相)  
> **深潜**：[ARCHITECTURE_PART3.md §0](./ARCHITECTURE_PART3.md#03-rolloutitem-与消费者的映射) · [ENTITY_AND_SEQUENCES.md](./ENTITY_AND_SEQUENCES.md)

---

## 1. 三层读者模型

| 读者 | 先看 | 再看 |
|------|------|------|
| 架构师 | §2 三真相 | DESIGN_THINKING_SERIES 第 8 幕 |
| 调试 Resume | §4 行类型 | `rollout/src/policy.rs` |
| 改 compact | §5 Compacted 树 | [CONTEXT_MANAGEMENT.md](./CONTEXT_MANAGEMENT.md) |

---

## 2. 三真相（不是一棵树，而是三个投影）

```text
                    run_turn 热路径
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
  ContextManager    EventMsg (EQ)    Rollout JSONL
  （模型 prompt）    （UI 流式）       （磁盘 append-only）
```

| 真相 | 载体 | 谁消费 |
|------|------|--------|
| **模型历史** | `SessionState.history` → `for_prompt()` | 下一轮采样 |
| **UI 事件** | `EventMsg::*` | TUI / app-server |
| **Rollout** | 每行一个 `RolloutItem` JSON | Resume、合规、Memories |

**校正**：`PlanUpdate` 等 **瞬时事件** 可能不进 durable rollout，但 `FunctionCall(update_plan)` 作为 `ResponseItem` **会**进（见 [UPDATE_PLAN_REFERENCE.md](./UPDATE_PLAN_REFERENCE.md)）。

---

## 3. Rollout 文件头与行流（简图）

```text
line 1: RolloutItem::SessionMeta { model, cwd, history_mode, parent_thread_id, … }
line 2+: RolloutItem 流（append-only）

典型一轮 Turn 的行序（Paginated 模式，概念）：
  TurnContext
  ResponseItem (user / developer fragments)
  ResponseItem (FunctionCall …)
  ResponseItem (FunctionCallOutput …)
  EventMsg::ItemCompleted(TurnItem::…)
  EventMsg::TurnComplete
  [可选] Compacted { replacement_history }
```

---

## 4. RolloutItem 变体速查

定义：`codex-history` / `history/src/lib.rs`（见 [ARCHITECTURE_PART3 §0.3](./ARCHITECTURE_PART3.md#03-rolloutitem-与消费者的映射)）

| 变体 | 含义 | 进模型？ | 进 UI？ |
|------|------|--------|--------|
| `SessionMeta` | 线程元数据（首行） | 间接 | 列表/Resume |
| `ResponseItem` | Responses API 项 + envelope | ✅ | 经 ItemCompleted |
| `Compacted` | 压缩/切窗检查点 | ✅ 替换历史 | ContextCompacted |
| `TurnContext` | 本轮 model/comp_hash | ❌ | ❌ |
| `WorldState` | 协作模式等快照 | 经 diff 注入 | ❌ |
| `EventMsg` | 生命周期/UI 事件 | 策略内部分 | ✅ |
| `InterAgentCommunication` | MA 跨线程消息 | 记入子/父 history | Collab EQ |
| `RealtimeItem` | Realtime 稀疏事实 | ❌ | Realtime UI |
| `TokenUsageRecord` | 用量行 | ❌ | TokenCount |

---

## 5. Compacted 切窗树（Token Budget）

Token Budget 切窗后，rollout 写入 `Compacted`，内含 `replacement_history`：

```text
… 旧 ResponseItem 行（逻辑上被替换）
Compacted {
  replacement_history: [ 新窗开头的 developer/user/assistant/… ],
  latest_token_usage_record: …
}
… 后续 Turn 继续 append 新 ResponseItem
```

源码测试：`core/src/session/tests.rs` `start_new_context_window_persists_checkpoint_state`  
机制：[CONTEXT_MANAGEMENT.md](./CONTEXT_MANAGEMENT.md)

---

## 6. 与 Pi JSONL 对照

| 概念 | Pi | Codex |
|------|-----|-------|
| 树节点 | `Entry` + `parentId` | `ResponseItem` 序列 + `Compacted` 检查点 |
| 压缩节点 | `type: compaction` | `RolloutItem::Compacted` |
| 可变状态 | value/list registers | `SessionState` / WorldState |
| 账本 | usage writes | `TokenUsageRecord`、rollout_budget |

→ [pi/docs/JSONL_TREE_GUIDE.md](../../pi/docs/JSONL_TREE_GUIDE.md)

---

## 7. 持久化策略入口

| 函数 | 文件 | 作用 |
|------|------|------|
| `should_persist_response_item` | `rollout/src/policy.rs` | ResponseItem 是否写 jsonl |
| `should_persist_event_msg` | 同上 | EventMsg 是否 durable |
| `should_persist_response_item_for_memories` | 同上 | Memories 子集 |

瞬时事件示例（`should_persist_event_msg` → false）：`PlanUpdate`、`PlanDelta`、`*Delta` 流式、多数 `*Begin` 标记。

---

## 8. Resume 重建路径

```text
load_rollout_items(path)
  → InitialHistory::Resumed
  → reconstruct_history_from_rollout
  → ContextManager 填充
  → 新 Session 可 run_turn
```

失配症状表 → [ARCHITECTURE_PART3 §0.5](./ARCHITECTURE_PART3.md#05-三种真相的同步与失配症状)

---

## 9. 源码速查

| 行为 | 路径 |
|------|------|
| RolloutItem 定义 | `codex-rs/history/`、`rollout/` |
| 写入 | `RolloutRecorder`、`persist_rollout_items` |
| 策略 | `rollout/src/policy.rs` |
| 模型历史 | `core/src/context_manager/history.rs` |
| Thread 存储 | `thread-store/`、`codex-state/` |

---

## 相关导读

- [DESIGN_THINKING_SERIES.md §8](./DESIGN_THINKING_SERIES.md#第-8-幕持久化-harness)
- [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md)
