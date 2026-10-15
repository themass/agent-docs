# Pi 会话 JSONL 与 Entry 树导读
> **2026-10-15 源码校正**：原正文保留；请同时阅读本文末尾新增的当前源码补充和 [全景入口](./PI_SOURCE_DEEP_DIVE_2026.md)。涉及旧 Harness 路径、消息类型、第三方插件版本的描述不能直接视为当前实现。

> **定位**：图解第 8 幕的 **专用入口**——用树形示意理解 `entries`、压缩与投影。  
> **完整示例与字段说明**：见 [ARCHITECTURE.md Part II §3](./ARCHITECTURE.md#3-完整-jsonl-会话文件示例)（**不重复删除**，本文提炼 + 扩展阅读路径）。

---

## 1. 三层读者模型

| 读者 | 先看 | 再看 |
|------|------|------|
| 产品 / 架构 | 本文 §2 树图 | DESIGN_THINKING_SERIES 第 8 幕 |
| 集成方 | §3 JSONL 行类型 | ARCHITECTURE §3 完整 jsonl |
| 改存储的开发者 | `harness/session/jsonl/` | `session-manager` 迁移 §3.2 |

---

## 2. Entry 树（一张图）

Session 在磁盘上是一棵 **只追加** 的树；`parentId` 指向上一个 entry。

```text
null
 └── 00000001  user: "读 src/index.ts"
      └── 00000002  assistant + toolCall(read)
           └── 00000003  toolResult
                └── 00000004  assistant 回复
                     └── 00000005  thinking_level_change  ← 投影 0 条 LLM 消息
                          └── 00000006  user: "改端口"
                               └── …
                                    └── 00000010  compaction  ← 摘要节点
                                         └── 00000011  user: "加 health check"
                                              └── 00000012  assistant
                                                   └── 00000013  leaf
```

**Leaf**：标记当前分支尖端；切换分支时 fork 出新子树。

---

## 3. JSONL 行类型速查

| `type` | 作用 | 进 LLM 投影？ |
|--------|------|----------------|
| `session` | 文件头：version、cwd、id | 否 |
| `message` | user / assistant / toolResult | 是（按规则） |
| `compaction` | 上下文压缩摘要 | 变为 `CompactionSummaryMessage` |
| `branch_summary` | 分支摘要 | 按策略 |
| `thinking_level_change` | 推理档位 | 否 |
| `leaf` | 分支尖端指针 | 否 |
| `custom` | 扩展类型 | 由 `EntryProjector` 决定 |

当前 schema 类型定义：`packages/agent/src/harness/session/types.ts`（`Entry`、`MessageEntry`、`CompactionEntry`）。

---

## 4. 压缩后模型看见什么

压缩 entry `00000010` 之后，**`firstKeptEntryId` 之前** 的消息被摘要替代：

```text
LLM messages[] =
  [ CompactionSummaryMessage,   ← 来自 00000010
    user: "再加 health check",    ← 00000011
    assistant: "好的…" ]         ← 00000012
```

详见 [ARCHITECTURE §3.1 树图与投影结果](./ARCHITECTURE.md#31-关键结构解读)。

---

## 5. 三种持久化（对照图解）

| 图解名 | Pi 机制 | 写入 API |
|--------|---------|----------|
| **entries** | JSONL `type:*` 行 / DB 行 | `insertEntry` |
| **registers** | namespace 下 value / list | `commit.ts` value/list writes |
| **usage ledger** | usage 行 | `insertUsage` |

一次 **commit** 可批量包含 entry + usage + value（`PreparedCommit.writes`）。

---

## 6. Lane 与并行

| Lane 示例 | 用途 |
|-----------|------|
| `main` | 主对话轨 |
| `slack-thread` | 外部队列轨（若配置） |
| `subagent` | 子 agent 轨 |

配置：`LaneConfiguration`（model、thinkingLevel、activeToolNames）。  
运行时：`harness/runtime/lane.ts` 序列化 mutation line。

---

## 7. 版本迁移

| 版本 | 要点 |
|------|------|
| v1 | 无 id/parentId；`firstKeptEntryIndex` |
| v2 | 树结构 + `firstKeptEntryId` |
| v3 | `hookMessage` → `custom` |

→ [ARCHITECTURE §3.2](./ARCHITECTURE.md#32-版本迁移说明)

---

## 8. 源码速查

| 要查 | 路径 |
|------|------|
| Entry 类型 | `harness/session/types.ts` |
| JSONL codec | `harness/session/jsonl/` |
| Commit 批量写 | `harness/session/commit.ts` |
| Session 编排 | `coding-agent` SessionManager |
| 投影为 LLM | `messages.ts` / Part II §2 |

---

## 9. 相关导读

- [DESIGN_THINKING_SERIES.md §8](./DESIGN_THINKING_SERIES.md#第-8-幕harness-让-agent-变成可恢复的持久化运行时)
- [ARCHITECTURE.md Part II §3](./ARCHITECTURE.md#3-完整-jsonl-会话文件示例)（**完整 jsonl 原文**）


---

## 10. 当前源码校正：两种 JSONL，不是一份 schema（2026-10-15）

本节追加校正，前文保留作历史导读。当前 CLI 的 schema 来自 [`core/session-manager.ts`](../../pi/packages/coding-agent/src/core/session-manager.ts)，不是已经不存在的 `agent/src/harness/session/types.ts`。

### 10.1 CLI session v3 的实际类型

当前 `SessionEntry` 联合包含 `message`、`thinking_level_change`、`model_change`、`usage`、`compaction`、`branch_summary`、`custom`、`custom_message`、`context_edit`、`label`、`session_info`。`SessionHeader` 是单独的 `type: session` 文件头。

**没有 `type: leaf` 联合成员**。`leafId` 是 SessionManager 的当前分支指针；前文树图的“leaf”可理解为指针示意，不能当作当前 JSONL 行类型。

| 类型 | 当前模型可见性 |
|---|---|
| `custom` | 保存扩展状态，不贡献模型消息 |
| `custom_message` | 通过投影贡献自定义消息，再转换为模型可接受的消息 |
| `context_edit` | append-only 替换/移除 earlier entry 的上下文贡献，不改历史原文 |
| `usage` | 费用/缓存等统计元数据，不等于 toolResult |
| `message` 中的 `system` | 支持 prompt sections 与 tool declarations 的位置更新 |

例如同一段历史可以保持原 entry 不变，只追加 context edit：

```mermaid
flowchart LR
  H[历史 message：大段日志] --> KEEP[完整历史仍保留]
  E[追加 context_edit
  targetId 指向原消息] --> P[buildSessionProjection]
  H --> P
  P --> M[模型仅看替换后内容或不看该条]
```

### 10.2 Durable JSONL 保存的是提交协议

Durable 的 `storage/jsonl/storage.ts` 保存 `main.jsonl` commit markers 及 task/document sidecars。它使用 conversation/entry/task/submission/document 五类记录，不是 CLI 的 `SessionEntry` JSONL。

前文的 `registers`、`LaneConfiguration` 和旧 `harness/runtime/lane.ts` 不应作为当前路径：当前 backend 请读 [BACKEND_RUNTIME.md](./BACKEND_RUNTIME.md)，其中解释 mutation line、Document scope/fork、UsageDoc 和任务恢复。

### 10.3 文件写入时机与 durability 限制

CLI `_persist()` 在已有 conversation 且未 flushed 时以 `wx` 创建文件、写入所有已缓存 entries；以后 append 新 entry。普通 append 不在这里显式执行 fsync，不能把“写 JSONL”理解为数据库级事务或任意掉电条件下持久保证。

源码：[`SessionManager._persist`](../../pi/packages/coding-agent/src/core/session-manager.ts)、[`JsonlStorage.commit`](../../pi/packages/durable/src/storage/jsonl/storage.ts)。
