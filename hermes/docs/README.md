# Hermes Agent 文档中心

> **当前发版**: `0.19.0`（`v2026.7.20`）— 见 `hermes_cli/__init__.py`  
> **文档核对**: 2026-07-31（主题文档合并）  
> **英文用户手册**: [`website/docs/`](../website/docs/)（Docusaurus）

---

## 结构怎么变了（一句话）

| 以前（~0.17 文档心智） | 现在（0.19） |
|------------------------|--------------|
| CLI + Gateway + `run_agent` 大循环 | **Surface（CLI/TUI/Desktop/WebUI）** + `tui_gateway` 事件桥 + **`conversation_loop`** 主循环 |
| 换肤 = CLI 本地 theme | **跨端 Skin** + gateway watcher 热更新 |
| 同主题多份 Deep/COMPLETE/OVERVIEW | **每域一篇 Canonical**（旧文按 Part 全文并入） |

---

## 必读三篇

| 文档 | 用途 |
|------|------|
| [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md) | **v0.18+ Canonical**：四 Surface、推理回写、Skin、Widget、Desktop SSH |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Agent 内核总览 |
| [VERSION_HISTORY.md](VERSION_HISTORY.md) | v0.10–v0.19 + 未发版快照 |

辅助：[WORKSPACE_VS_WEBUI.md](WORKSPACE_VS_WEBUI.md) · [HERMES_ATLAS_TRENDING.md](HERMES_ATLAS_TRENDING.md) · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)

---

## 本 monorepo：Content Studio Agent

深度内容生成栈（Hermes Profile + Open Notebook + MPT + 脚本）见：

**[../content-studio-agent/README.md](../content-studio-agent/README.md)**

---

## 合约与运维

| 文档 | 说明 |
|------|------|
| [session-lifecycle.md](session-lifecycle.md) | Gateway 会话生命周期 |
| [billing-lifecycle.md](billing-lifecycle.md) | TUI/Desktop 计费 |
| [relay-connector-contract.md](relay-connector-contract.md) | Relay（实验性） |
| [chronos-managed-cron-contract.md](chronos-managed-cron-contract.md) | Chronos cron |

---

## 学习路线图

### 阶段 0：Surface（~1h）

1. [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md)

### 阶段 1：心智模型（~3h）

| # | 文档 |
|---|------|
| 1 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 2 | [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) |
| 3 | [PROMPT_SYSTEM_ARCHITECTURE.md](PROMPT_SYSTEM_ARCHITECTURE.md)（扁平 §1–§17） |
| 4 | [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md)（§1 三层总览） |
| 5 | [CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md)（CLI + Gateway；旧 CLI/GATEWAY 为 stub） |

### 阶段 2：核心实现（~6h）

| # | 文档 |
|---|------|
| 6 | [PROMPT_SYSTEM_ARCHITECTURE.md](PROMPT_SYSTEM_ARCHITECTURE.md) 深入 §3–§13 · [SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md](SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md) |
| 7 | [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) §3–§9 实现 / 用法 / Provider / 扩展 |
| 8 | [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) §4.2.0+ |

### 阶段 3：扩展（~4h）

| # | 文档 | 注意 |
|---|------|------|
| 9 | [MULTI_AGENT_ARCHITECTURE.md](MULTI_AGENT_ARCHITECTURE.md) | §12 中断/HITL；伪代码 Part 2 已删除 |
| 10–13 | [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) · [SKILLS](SKILLS_SYSTEM.md) · [PLUGINS](PLUGINS_SYSTEM.md) · [MCP](MCP_INTEGRATION.md) · [HITL 审批](HITL_APPROVAL_FLOW.md) |

### 阶段 4：按需

[CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md) · [KANBAN_MULTIAGENT_DEEP_ANALYSIS.md](KANBAN_MULTIAGENT_DEEP_ANALYSIS.md) · [EXECUTION_FLOW_ANALYSIS.md](EXECUTION_FLOW_ANALYSIS.md)（Historical）

---

## Canonical 地图（合并后）

| 主题 | Canonical（唯一） |
|------|-------------------|
| Surface | `SURFACE_ARCHITECTURE.md` |
| Agent 循环 | `AGENT_LOOP_ARCHITECTURE.md` |
| 总览 | `ARCHITECTURE.md` |
| Prompt | `PROMPT_SYSTEM_ARCHITECTURE.md` |
| 多 Agent | `MULTI_AGENT_ARCHITECTURE.md` |
| Gateway / CLI 交互面 | `CLI_GATEWAY_SYSTEM.md` |
| Tools | `TOOLS_SYSTEM.md` |
| Memory | `MEMORY_SYSTEM.md` |
| MCP | `MCP_INTEGRATION.md` |

已删除的平行文档列表见 [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)。

---

## 读时跳过

| 现象 | 处理 |
|------|------|
| 寻找 `*_OVERVIEW` / `*_DEEP` / `*_COMPLETE` | 已并入对应 Canonical 的 Part |
| Memory「六层」当主 API | 用 `MEMORY_SYSTEM.md` §1 三层 |
| `run_agent` 含全部主循环 | 主循环在 `conversation_loop.py` |

---

## 整理策略

- 同主题一篇 **Canonical**；旧文全文进 Part，不丢内容
- 新结论只写 Canonical，勿再拆平行文件
- 发版以 **git tag + VERSION_HISTORY** 为准

**反馈**: 与 `0.19.x` 不符 → 改 Canonical 或开 issue。
