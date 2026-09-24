# 开源 Agent 项目研究与拆解目录

> **范围**：本 monorepo 已 clone 的 Agent 相关仓库 + 2026 年 7 月 GitHub 日榜及经典框架。
> **目的**：按 **源码可学性** 与 **架构层次** 选型，避免重复造轮子。
> **最后更新**：2026-07-27

---

## 1. 三层分类（读任何项目前先贴标签）

| 层 | 定义 | 典型代表 |
|----|------|----------|
| **L1** | 模型 API / Tool Calling 封装 | `openai-agents-python`、`anthropic-sdk` |
| **L2** | **Harness**：循环、工具、权限、压缩、会话 | `deepagents`、`claude-code-agent` 快照、`OpenHands/software-agent-sdk`、`Hermes` |
| **L2.5** | **Deliberation / Skill**（无独立运行时） | `council-of-high-intelligence`、各 `SKILL.md` |
| **L3** | **ADE / 编排 / 通信**（多 Agent、多实例路由） | `orca`、`herdr`、`buzz`、LangGraph Platform UI |
| **L4** | **评测 / 基准** | `libs/evals`、`tau-bench`、Harbor |

**学习优先级**：先 L2 Harness（主循环怎么写），再 L3（怎么管很多 Agent），L2.5 当扩展面案例。

---

## 2. 本 monorepo 内 — Tier 1（建议精读）

| 项目 | 路径 | 学什么 | 文档入口 |
|------|------|--------|----------|
| **Deep Agents SDK** | `libs/deepagents/` | LangGraph 上 L2 Harness：middleware、subagent、filesystem、sandbox | `AGENTS.md`、官方 docs |
| **Deep Agents Code** | `libs/code/` | Textual REPL、slash、MCP、skills 宿主 | `libs/code/AGENTS.md` |
| **OpenHarness** | `OpenHarness/` | 多框架统一 Harness 抽象、Hermes | `docs/ARCHITECTURE_ENGINE.md` |
| **framework-comparison** | `OpenHarness/docs/framework-comparison/` | 20+ 框架横向：记忆、压缩、持久化 | [README.md](OpenHarness/docs/framework-comparison/README.md)（01–11 编号专题） |
| **Claude Code 官方 clone** | `claude-code/` | **扩展面**：plugins、hooks、skills、settings | `docs/CLAUDE_CODE_ARCHITECTURE_GUIDE.md` |
| **Claude Code 运行时快照** | `claude-code-agent/` | **闭源 CLI 内部**：`queryLoop`、QueryEngine、工具编排 | `docs/architecture/00-overview.md` |
| **Claude Agent SDK (Py)** | `claude-agent-sdk-python/` | 子进程 spawn CLI、`stream-json` 协议 | `docs/` |
| **agent-framework** | `agent-framework/` | 自研 compaction / 中间件实验 | `docs/COMPACTION_SOURCE.md` |
| **deer-flow** | `deer-flow/` | 中文社区 L2+L3 工作流 Agent | 各子包 README |
| **OpenHands** | `openhands/` + `software-agent-sdk/` | 2026 控制面 + SDK 三层记忆 | `framework-comparison/10-openhands.md` |

---

## 3. 本 monorepo 内 — Tier 2（按需深潜）

| 项目 | 路径 | 学什么 |
|------|------|--------|
| **LangGraph** | 依赖 / 子模块 | StateGraph、checkpoint、human-in-the-loop |
| **CrewAI / AutoGen / Agno** | `OpenHarness` 对比文档引用 | 多 Agent 角色分工模式 |
| **AgentScope** | 对比文档 | Redis 会话、分布式 |
| **Microsoft Agent Framework** | `agent-framework/` 周边 | Provider vs Middleware |
| **ponytail** | `.cursor/skills/ponytail*` | 工程极简主义（元技能，非 Harness） |
| **github-daily-rank** | `github-daily-rank/` | 热点项目发现与分类笔记 |

---

## 4. 仓外 — 2026-07 GitHub 日榜 Agent 向（值得拆解）

来源：`github-daily-rank/2026/07/GITHUB_2026_07_REPORT.md`（7/1–7/26，59 项）

| 项目 | 层次 | 为何值得学 |
|------|------|------------|
| **[orca](https://github.com/mariozechner/orca)** | L3 | 多 CLI Agent 编排、Hermes 等作后端；**通信与路由** |
| **[herdr](https://github.com/herdr/herdr)** | L3 | Agent 群 + 持久化身份；对比 OpenHands 多实例 |
| **[buzz](https://github.com/charmbracelet/buzz)** | L3 | TUI 多 Agent 工作台；Charm 生态 UX |
| **[graphify](https://github.com/...)** | L2/L3 | 图式 Agent 编排（见日榜条目） |
| **[DeepTutor](https://github.com/...)** | L2 垂直 | 教育场景完整产品链 |
| **[council-of-high-intelligence](https://github.com/parcadei/council-of-high-intelligence)** | L2.5 | 18 人格 Skill；已装 `~/.cursor/skills/council/` |

**注意**：日榜项目 **不等于** 工程质量最高；用于发现 **新范式**（编排、通信、Skill 协议）。

---

## 5. 仓外 — 经典框架（长期参考）

| 项目 | 层次 | 拆解重点 |
|------|------|----------|
| **LangGraph** | L2 | Graph + checkpoint + 子图 |
| **LangChain `deepagents` 竞品** | L2 | `smolagents`、`pydantic-ai`、`google-adk` |
| **OpenAI Agents SDK** | L2 | Session、handoff、tracing |
| **Letta (MemGPT)** | L2 | 长期记忆、core/archival 分层 |
| **SWE-agent / OpenHands** | L2 代码 | 软件工程 Agent 工具面 |
| **Aider / Continue** | L2 代码 | IDE 内嵌循环（对比 Claude Code） |
| **Cursor / Windsurf** | 闭源 | 产品层参考；无完整源码 |
| **Anthropic `claude-code` npm** | L2 闭源 | 仅快照 + 官方插件仓可学 |

---

## 6. 按学习目标选型

| 你想搞懂… | 先读 | 再读 |
|-----------|------|------|
| **Agent 主循环** | `claude-code-agent` 01、03 | `libs/deepagents` middleware |
| **上下文压缩** | `agent-framework/docs/COMPACTION_SOURCE.md` | `claude-code-agent` 07、OpenHands condenser |
| **多实例 / 会话存储** | `OpenHarness/docs/framework-comparison/06-memory.md` | OpenHands app_server、Letta |
| **插件 / Hook / Skill** | `claude-code/plugins/` | `claude-code-agent` 15-extensibility |
| **多 Agent 编排** | orca、LangGraph | OpenHarness swarm 示例 |
| **评测与回归** | `libs/evals` | tau-bench、Harbor |

---

## 7. 拆解方法论（通用）

1. **找入口**：`main` / `query` / `run` / `AgentExecutor`
2. **画循环**：谁调模型、谁跑工具、何时终止
3. **标状态**：内存 vs 磁盘 vs Redis；单进程 vs 多 Pod
4. **标扩展点**：Hook、Middleware、Skill、MCP
5. **标信任边界**：权限、沙箱、用户确认
6. **写一页对比**：放进 `framework-comparison/` 或本目录

---

## 8. 与本目录其他文档

- Claude Code 合并设计 → [CLAUDE_CODE_MASTER_ARCHITECTURE.md](./CLAUDE_CODE_MASTER_ARCHITECTURE.md)
- Claude Code 阅读周计划 → [CLAUDE_CODE_LEARNING_PATH.md](./CLAUDE_CODE_LEARNING_PATH.md)
