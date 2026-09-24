# Codex 架构设计文档中心

> **项目**: [openai/codex](https://github.com/openai/codex)（本仓库路径 `codex/`）  
> **分析版本**: 本地 checkout（Rust workspace `codex-rs/`，2026-08 快照）  
> **体例参照**: [`software-agent-sdk/docs`](../../software-agent-sdk/docs/README.md)、[`claude-code-agent/docs/architecture`](../../claude-code-agent/docs/architecture/00-overview.md)

OpenAI Codex CLI 是一个**本地运行的编码 Agent**：TUI / IDE / exec / app-server 共用同一套 `codex-core` 运行时。核心不变量是 **SQ/EQ 协议**（客户端提交 `Op`，运行时异步回 `EventMsg`）以及 **增量、不可改写的模型上下文**。

本文档是源码级设计整理，不是官方产品手册。官方用户文档在 [developers.openai.com/codex](https://developers.openai.com/codex)。Codex 仓库自己的 `codex/docs/` 只放安装、配置、sandbox 等产品说明，架构分析刻意放在本目录。

---

## 完整大纲

| 类别 | 文档 | 说明 |
|------|------|------|
| **入口** | [ARCHITECTURE.md](./ARCHITECTURE.md) | 10 分钟主题表 |
| **同步** | 本 README | 分类大纲与阅读路径 |

### A. 架构分章（按源码模块）

| 文档 | 章节 | 关键源码 |
|------|------|----------|
| [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | …、**§8.7 协作范式**（ReAct/协调器）、§9 Plan Mode | `multi_agents*`、`turn.rs`、`collaboration_mode` |
| [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | Ch0–11：工具、MCP、Skills、Sandbox/Guardian、Hooks、Plugins、Code Mode（**~1830 行**，53 图） | `core/src/tools/`、`codex-mcp`、`skills/` |
| [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | Rollout、ThreadStore、History Mode、Realtime、Observability、ADR、设计取舍（**~1600 行**，34 图） | `rollout/`、`thread-store/`、`hooks/` |

### B. 实体与时序（源码级，推荐）

| 文档 | 内容 |
|------|------|
| [**ENTITY_AND_SEQUENCES.md**](./ENTITY_AND_SEQUENCES.md) | **四篇合一**：实体 ER、端到端时序、12+ 模块深潜（submission_loop / run_turn 分阶段 / ToolOrchestrator / compact / Guardian…）、JSON 示例 |

### C. 运行时深潜

| 文档 | 内容 |
|------|------|
| [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md) | 冷启动、同 Session 第二次提问、Resume、压缩窗口、Prompt 组装实例 |
| [**RUNTIME_PROMPTS.md**](./RUNTIME_PROMPTS.md) | **运行时访问大模型的完整 Prompt**（中文）：各模式、压缩、MCP/Skill/Plugin 封装、主子同步/异步、delegate 语义 |
| [**PLAN_AND_MULTI_AGENT.md**](./PLAN_AND_MULTI_AGENT.md) | **Plan Mode / `update_plan` / Multi-Agent 合一**：范式地图、示例与误解表 |
| [**MULTI_AGENT_ARCHITECTURE.md**](./MULTI_AGENT_ARCHITECTURE.md) | **多 Agent 架构导读**：协作版 vs 邮箱版、派活与通知时机（设计原理 + 图表） |
| [**FULL_LIFECYCLE_SEQUENCE.md**](./FULL_LIFECYCLE_SEQUENCE.md) | **全链路时序**：压缩、子 Agent、继续提问、Phase1/2；对比 OpenAI Agents Python SDK Handoff |
| [**UPDATE_PLAN_REFERENCE.md**](./UPDATE_PLAN_REFERENCE.md) | **`update_plan` 修订版专文**：可直接引用的源码级详解（基于用户草稿校正） |
| [**CONTEXT_MANAGEMENT.md**](./CONTEXT_MANAGEMENT.md) | **Token Budget / notes / history 切窗**：四类状态、与 compaction 关系、配置校正（对照微信架构文） |
| [**SECURITY_ARCHITECTURE.md**](./SECURITY_ARCHITECTURE.md) | **安全架构导读**：威胁模型、注入面、控制面四层、扩展供应链、网络/审计（图表为主） |
| [**DESIGN_THINKING_SERIES.md**](./DESIGN_THINKING_SERIES.md) | **循序渐进设计导读**（运行路径、三真相、needs_follow_up、Plan/MA 校正） |
| [**diagrams/design-thinking-series.html**](./diagrams/design-thinking-series.html) | **浏览器图解速览**（绿主题，可本地打开） |
| [**JSONL_TREE_GUIDE.md**](./JSONL_TREE_GUIDE.md) | **Rollout / JSONL 树形导读**（三真相、RolloutItem、Compacted 切窗） |

---

## 10 秒心智模型

```
客户端 (TUI / IDE / exec / MCP host)
        │  Submission { id, op: Op }
        ▼
 ThreadManager ──创建/恢复──► Session（内存运行时，一 Thread 至多一个 ActiveTurn）
        │
        ▼
 submission_loop → turn_input → spawn_task(RegularTask) → run_turn() Step 循环
        │
        ▼
 EventMsg 流（TurnStarted / AgentMessage / ExecCommand* / TurnComplete）
        │
        ▼
 Rollout 文件（append-only）+ ThreadStore（可 Resume）
```

---

## 阅读路径

| 角色 | 路径 | 约 |
|------|------|-----|
| 新手 | [PART1 §1–3](./ARCHITECTURE_PART1.md) → [WALKTHROUGH 冷启动](./CORE_RUNTIME_WALKTHROUGH.md) | 2h |
| 运行时开发 | [PART1 §4 Agent Loop 四层深潜](./ARCHITECTURE_PART1.md#第4章agent-loop--四层循环与源码级设计) → [ENTITY §9](./ENTITY_AND_SEQUENCES.md) → [PART2 工具](./ARCHITECTURE_PART2.md) | 4h |
| 安全 / 沙箱 | [PART2 Sandbox](./ARCHITECTURE_PART2.md) → [PART1 权限 fragments](./ARCHITECTURE_PART1.md) | 2h |
| 架构师 | [PART1 全文](./ARCHITECTURE_PART1.md) → [PART3 取舍](./ARCHITECTURE_PART3.md) → 对照 [software-agent-sdk](../../software-agent-sdk/docs/README.md) | 6h |

---

## 与本仓库其它 Agent 文档对照

| 项目 | 文档 |
|------|------|
| Software Agent SDK（OpenHands） | [`software-agent-sdk/docs`](../../software-agent-sdk/docs/README.md) |
| DeepTutor | [`docs/deeptutor-architecture`](../deeptutor-architecture/README.md) |
| Claude Code Agent | [`claude-code-agent/docs/architecture`](../../claude-code-agent/docs/architecture/00-overview.md) |
| 多项目横向 | [`docs/AGENT_SDKS_COMPREHENSIVE_DESIGN_GUIDE.md`](../AGENT_SDKS_COMPREHENSIVE_DESIGN_GUIDE.md) |

---

**维护者**: Deep Agents Team · **整理日期**: 2026-09-01
