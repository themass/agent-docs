# Software Agent SDK 文档中心

> **项目**: [software-agent-sdk](https://github.com/All-Hands-AI/OpenHands/tree/main/software-agent-sdk)（uv workspace monorepo）  
> **轻量导航**: [ARCHITECTURE.md](./ARCHITECTURE.md) · **最后整理**: 2026-08-05

企业级 Python Agent 框架：本地/远程 Conversation、事件溯源、插件与 Skills、双层安全、`tools_map` 统一工具表。

---

## 完整大纲

| 类别 | 文档 | 说明 |
|------|------|------|
| **入口** | [ARCHITECTURE.md](./ARCHITECTURE.md) | 10 分钟主题表 |
| **同步** | 本 README | 分类大纲与阅读路径 |

### A. 架构分章（按源码模块）

| 文档 | 章节 | 关键源码 |
|------|------|----------|
| [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | §1–8：概览、Agent、Conversation、Tool、E2E、Memory、多 Agent、Plan | `agent/`、`conversation/`、`context/` |
| [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | §0 工具注册、§5 Tool、§6 MCP、§7 Security、§8 包地图 | `tool/`、`mcp/`、`security/` |
| [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | §8 Persistence、§9 Observability、§10 Testing | `io/`、`observability/`、`testing/` |

### B. 运行时深潜（与 PART1 互补，不重复删节）

| 文档 | 内容 |
|------|------|
| [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md) | 折叠 / Event→View→messages、实体 T0–T5、Condensation 磁盘 JSON、工具·MCP·Agent 切换 |
| [SDK_RUNTIME_PROMPTS.md](./SDK_RUNTIME_PROMPTS.md) | Default / Planning 运行时 system、`tools[]`、`messages[]` 中文全文 |
| [COMPRESSION_SCHEMES_COMPARISON.md](./COMPRESSION_SCHEMES_COMPARISON.md) | 多项目压缩 Prompt 结构与中文译文对照 |

### C. 关联项目文档

| 项目 | 路径 |
|------|------|
| OpenHands 平台（Web / Sandbox） | [`../OpenHands/docs/`](../OpenHands/docs/)（若存在） |
| 全工程框架对比 | [`../../OpenHarness/docs/framework-comparison/`](../../OpenHarness/docs/framework-comparison/README.md) |

---

## PART1 章节速查

| 章 | 主题 |
|----|------|
| §1 | 项目概览与核心架构 |
| §2 | Agent 核心（延迟初始化、工具解析） |
| §3 | Conversation（step/turn/run、[§3.6 loop 中 send_message](./ARCHITECTURE_PART1.md#36-loop-过程中-send_message-时序)、事件持久化、Fork） |
| §4 | Tool 工具系统 |
| §5 | 端到端流程与双循环（`run` / `arun`） |
| §6 | Memory（View、Condensation、MEMORY.md）→ 深潜见 [WALKTHROUGH](./CORE_RUNTIME_WALKTHROUGH.md) |
| §7 | 多 Agent（Delegate、Subagent、GoalController） |
| §8 | Plan 模式（preset、PLAN.md、两段 Conversation） |

## PART2 章节速查

| 章 | 主题 |
|----|------|
| §0 | **必读** — `tools_map`、MCP、Skills 三条路径 |
| §5 | Tool 深度（§5.1 Toolkit 为设计示意） |
| §6 | MCP 协议与 Client |
| §7 | Security Analyzer、Confirmation、纵深防御 |
| §8 | Monorepo [四包功能封装](./ARCHITECTURE_PART2.md#81-workspace-包一览)（§8.1.1–8.1.6）+ 模块地图 + 初始化时序（原 `PACKAGE_MODULES.md`） |

## WALKTHROUGH 部分速查

合并自已删除的 `VIEW_FOLD`、`ENTITY_RELATIONSHIP`、`CONDENSATION`、`DELEGATE_AND_TASK`。

| 部分 | 主题 |
|------|------|
| 第零部分 | 无「一次 `run()` 先 Plan 再执行」 |
| 第一部分 | 折叠与 Event → View → messages |
| 第二部分 | 实体关系 T0–T5 |
| 第三部分 | Condensation 磁盘 JSON 全文走查 |
| 第四部分 | 工具挂载、MCP、`task` vs `delegate`、Agent 切换 |

---

## 阅读路径

| 角色 | 路径 | 约 |
|------|------|-----|
| 新手 | [PART1 §1–3](./ARCHITECTURE_PART1.md)（含 [§3.3.0 step/turn/run](./ARCHITECTURE_PART1.md#330-术语stepturnrun-怎么对应)）→ [WALKTHROUGH 第一部分](./CORE_RUNTIME_WALKTHROUGH.md) | 3h |
| Agent 开发者 | [PART2 §0](./ARCHITECTURE_PART2.md#第0章工具注册全景mcp--skills--内置工具) → [SDK_RUNTIME_PROMPTS](./SDK_RUNTIME_PROMPTS.md) → [PART1 §6](./ARCHITECTURE_PART1.md#第6章memory-体系与运行时-message-变化) | 4h |
| 安全 / 集成 | [PART2 §6–7](./ARCHITECTURE_PART2.md) → [PART3 §8](./ARCHITECTURE_PART3.md) | 3h |
| 架构师 | [PART2 §8 四包封装](./ARCHITECTURE_PART2.md#81-workspace-包一览) → [framework-comparison](../../OpenHarness/docs/framework-comparison/README.md) → PART1 全文 | 6h |

---

## 合并说明（2026-08-05）

| 已删除 / 旧文件 | 现行位置 |
|-----------------|----------|
| `PACKAGE_MODULES.md` | [ARCHITECTURE_PART2.md §8](./ARCHITECTURE_PART2.md#第8章monorepo-源码包与模块地图) |
| `VIEW_FOLD.md` 等 4 份走查稿 | [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md)（此前已合并） |

**刻意保留多文件**（角色不同）：PART1 概述 + WALKTHROUGH 深潜；`SDK_RUNTIME_PROMPTS` 与 PART1 §6 Prompt 段落互补。

---

## 文档特点

- **源码锚点**：章节标注文件路径与行号范围
- **Mermaid**：架构图、时序图、状态机
- **对照表**：机制对比与选型建议

## 官方资源

- SDK 文档: https://docs.all-hands.dev/modules/sdk/
- 仓库根: `/Users/gqli/work/deepagents/software-agent-sdk`

---

**维护者**: Deep Agents Team
