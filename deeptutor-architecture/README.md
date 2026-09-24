# DeepTutor 架构设计文档中心

> **项目**: [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)（本仓库路径 `DeepTutor/`）  
> **分析版本**: 本地 checkout（2026-08 快照）  
> **体例参照**: [`software-agent-sdk/docs`](../../software-agent-sdk/docs/README.md)、[`docs/codex-architecture`](../codex-architecture/README.md)

DeepTutor 是 **Agent-Native 个性化学习辅导系统**（[HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)）：把 Chat、解题、出题、掌握度路径、研究、沉浸阅读/视频、Book 等 **学习形态** 接到同一套 **TurnCapability + AgentLoop** 运行时，并用 **L1–L3 Memory** 沉淀学习者画像。

| 类别 | 文档 | 说明 |
|------|------|------|
| **整合稿（推荐）** | [**all.md**](./all.md) | 全模块 + **第十篇图解血肉**（流程/时序/框架 + 解读，~2900 行） |
| **图解血肉（可单独读）** | [MODULE_DEEP_DIVES.md](./MODULE_DEEP_DIVES.md) | 与 all.md 第十篇同步；Mastery/Quiz/RAG/Partners 等 24 专题 |
| **入口** | [ARCHITECTURE.md](./ARCHITECTURE.md) | 10 分钟主题表 |
| **图解导读（推荐先读）** | [**DESIGN_THINKING_SERIES.md**](./DESIGN_THINKING_SERIES.md) | 循序渐进：七层架构、双层插件、三层投影（**图表为主**） |
| **专题** | [CONTEXT_AND_PROJECTION.md](./CONTEXT_AND_PROJECTION.md) | StreamEvent / messages / LLM input 四层投影 |
| **同步** | 本 README | 分类大纲与阅读路径 |

### A. 架构分章（源码级深潜，改代码时用）

| 文档 | 章节 | 主题 |
|------|------|------|
| [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | 定位、七层架构、Orchestrator、双层插件、Message、E2E、Session、Memory | 核心运行时 |
| [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | RAG、Skills、MCP/Partners、Sandbox、Capabilities 详解 | 扩展与垂直能力 |
| [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | i18n、Learning/Mastery、设计取舍 | 产品与权衡 |

### B. 实体与时序（字段 / 函数级）

| 文档 | 内容 |
|------|------|
| [**ENTITY_AND_SEQUENCES.md**](./ENTITY_AND_SEQUENCES.md) | 实体 ER、端到端时序、模块深潜、JSON 示例 |

### C. 运行时深潜

| 文档 | 内容 |
|------|------|
| [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md) | CLI/WS 冷启动、第二问、regenerate、切换 capability |

---

## 10 秒心智模型

```
CLI / WebSocket / SDK
        │
        ▼
 ChatOrchestrator.handle(UnifiedContext)
        │
        ├── active_capability ──► Capability.run()  [deep_solve | deep_research | chat | ...]
        │
        └── 默认 chat ──► AgenticChatPipeline ──► AgentLoop (单会话多轮 tool loop)
                │
                ▼
         StreamBus ──► StreamEvent ──► 客户端 / DB 持久化
```

---

## 阅读路径

| 角色 | 路径 | 约 |
|------|------|-----|
| **先搞懂产品** | [all.md §零](./all.md#零产品认知) → [DESIGN_THINKING_SERIES](./DESIGN_THINKING_SERIES.md) | 45min |
| **新手（运行时）** | [all.md](./all.md) 第一篇 → [CONTEXT_AND_PROJECTION](./CONTEXT_AND_PROJECTION.md) → [WALKTHROUGH](./CORE_RUNTIME_WALKTHROUGH.md) | 2h |
| Chat 开发 | 导读 → [ENTITY AgentLoop](./ENTITY_AND_SEQUENCES.md) → PART1 §5–7 | 3h |
| Capability 开发 | 导读 → [PART2 §4](./ARCHITECTURE_PART2.md) | 4h |
| 架构师 | 导读全文 → PART → 对照 [Codex](../codex-architecture/README.md) | 6h |

---

## 与 Codex / SDK 对照

| 维度 | DeepTutor | Codex | software-agent-sdk |
|------|-----------|-------|-------------------|
| 垂直领域 | 教育辅导 | 编码 | 通用企业 Agent |
| 插件层 | Tool + Capability | Tool + MCP + Skill 文件 | tools_map + MCP |
| 流协议 | `StreamEvent` | `EventMsg` | `Event` + View |
| 会话 | SQLite turn 事件 | Rollout jsonl | FileStore events |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-01
