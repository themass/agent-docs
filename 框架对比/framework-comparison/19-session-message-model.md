# Session / Message 术语与 JSON 模型

> **设计导读** · 完整字段表与 Canonical 对照：[_archive/19-session-message-model.md](./_archive/19-session-message-model.md)  
> **应先读**：[21-session-message-architecture](./21-session-message-architecture.md)（五平面设计）

---

## 1. 本文 vs 21

| 文档 | 层级 | 内容 |
|------|------|------|
| **[21](./21-session-message-architecture.md)** | **设计** | S/W/L/T/U、六族范式、选型 |
| **本文 19** | **术语** | JSON 字段、别名、互操作 |

读架构 **先 21**；改序列化 / 对接 API **再 19**。

---

## 2. 核心术语

| 术语 | 含义 |
|------|------|
| **Session** | 一次可恢复对话边界（含 id、元数据） |
| **Message** | 单条 role + content（或 parts） |
| **Event** | append-only 原子（B 族） |
| **Turn** | 用户一次输入到助手终稿 |
| **Thread** | 逻辑会话键（常 = session_id） |
| **Checkpoint** | 图/运行可恢复快照（C 族） |
| **Rollout** | 带审计的 run 记录（Codex B） |

---

## 3. Role 与 content 形态

| 形态 | 用途 | 注意 |
|------|------|------|
| `user` / `assistant` / `system` | Chat 标准 | tool 消息归属 |
| `tool` + `tool_call_id` | 工具结果 | 与 assistant tool_calls 配对 |
| **parts[]** | 多模态 | 投影时可能折叠 |
| **synthetic user** | interjection | 非真人输入 |

---

## 4. 六族与存储（速查）

| 族 | 真源形状 | 典型序列化 |
|----|----------|------------|
| **A** | messages 列表 | JSONL / JSON array |
| **B** | event log | SQLite rows / NDJSON |
| **C** | graph checkpoint | blob + channel versions |
| **D** | 双平面 | event + workspace |
| **E** | 外部黑盒 | CLI stream-json |
| **F** | 事件优先 | AgentScope 风格 |

→ 设计取舍：[21 §12](./21-session-message-architecture.md)

---

## 5. 互操作原则

1. **W→L 投影可丢字段** — U 轨永不进模型。  
2. **tool_call_id 全局唯一** — 跨压缩代可追溯。  
3. **压缩代标记** — `parent_id` / epoch / condensation event。  
4. **不要静默改 role** — synthetic 要显式 reason。  
5. **导入导出保真 W** — L 是派生。

---

## 6. 深潜

各项目 JSON 样例、字段映射表 → [_archive/19-session-message-model.md](./_archive/19-session-message-model.md)
