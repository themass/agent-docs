# Pi 会话 JSONL 与 Entry 树导读

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
