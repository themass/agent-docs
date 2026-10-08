# OpenCode 架构文档索引

本目录描述 **anomalyco/opencode**（`deepagents/opencode/`）的 V2 Session 内核。避免在一份 9000+ 行合并稿里来回翻页：按任务选入口。

## 推荐阅读顺序

| 顺序 | 文档 | 适合 |
|------|------|------|
| 1 | [ARCHITECTURE.md](./ARCHITECTURE.md) **§0–§16** | 运行时主线：admit → Drain → Provider Turn、Epoch、Tool、持久化 |
| 2 | [AGENT_AND_MULTI_AGENT.md](./AGENT_AND_MULTI_AGENT.md) | **Agent 抽象**、build/plan、主子 session、`task`、与社区插件边界 |
| 3 | [PLUGINS.md](./PLUGINS.md) | **官方生态插件表** + Core 内置插件（provider/agent/config） |
| 4 | [diagrams/README.md](./diagrams/README.md) | Archify 交互图 |

## `ARCHITECTURE.md` 体例说明（重要）

`ARCHITECTURE.md` 由多份历史文档 **拼接** 而成：

| 区块 | 行号区间（约） | 状态 |
|------|----------------|------|
| 导读 + **总控篇** | 文首 → `# 分卷原文：ARCHITECTURE_PART1` 之前 | **主 spine**，优先读 §0–§16、§17–§30 |
| `分卷原文：ARCHITECTURE_PART1/2` … | 各 `# 分卷原文：…` 标题起 | **存档**：与 spine 重复，按需检索 |
| `分卷原文：multi-agent.md` | 已替换为短链接 | 完整内容见 [AGENT_AND_MULTI_AGENT.md](./AGENT_AND_MULTI_AGENT.md) |

**不要**把「分卷原文」里的过时描述（如 `agent_create`、`plan.create` 工具链、仅 md 定义内置 Agent）当作当前源码真相；以 `opencode/packages/core` + `packages/opencode` 为准，专题 MD 已按 2026-03 源码校对。

## 源码根路径

| 包 | 路径 | 职责 |
|----|------|------|
| Core | `opencode/packages/core/src/` | Session、Event、Tool、AgentV2、SQLite |
| App 宿主 | `opencode/packages/opencode/src/` | 部分内置 Agent 定义（V1 路径）、`task` / `plan_exit` 工具 |
| Schema | `opencode/packages/schema/src/` | `AgentV2.Info` 等契约 |

## 其他文件

| 文件 | 说明 |
|------|------|
| `multi-agent.md` | 若存在则为旧稿；以 `AGENT_AND_MULTI_AGENT.md` 为准 |
| `OpenCode 完整内核架构全量文档…md` | 对话复盘整编，不维护 |
| `OhMyOpenAgent.md` | 社区插件说明，非 Core |
