# Deep Agents 框架文档索引

> **本文档**：提供 Deep Agents 完整设计方案系列文档的导航与快速检索。  
> **更新时间**：2026-09-01  
> **适用版本**：`deepagents==0.6.6`、`deepagents-code==0.1.x`、`deepagents-cli==0.1.x`

---

## 🧭 源码级架构（2026-09 新增）

体例对齐 [`software-agent-sdk/docs`](../software-agent-sdk/docs/README.md)：分章 + 运行时走查 + 源码锚点 + 流程图。

| 项目 | 文档中心 | 先读（§1.2 实体全景） | 规模（PART1 行数） |
|------|----------|----------------------|-------------------|
| **Codex** | [codex-architecture/README.md](./codex-architecture/README.md) | [PART1 §1.2](./codex-architecture/ARCHITECTURE_PART1.md#12-分层架构) · [PART2](./codex-architecture/ARCHITECTURE_PART2.md) · [PART3](./codex-architecture/ARCHITECTURE_PART3.md) | PART1 ~2660 · PART2 ~1830 · PART3 ~1600 |
| **DeepTutor** | [deeptutor-architecture/README.md](./deeptutor-architecture/README.md) | [PART1 §1.2](./deeptutor-architecture/ARCHITECTURE_PART1.md#12-分层架构) TurnRuntime + Orchestrator | ~1280 |
| **Prime Agent** | [prime-agent-architecture/README.md](./prime-agent-architecture/README.md) | [**ARCHITECTURE_GUIDE**](./prime-agent-architecture/ARCHITECTURE_GUIDE.md)（Pi 关系 + 端到端图） · [REFERENCE](./prime-agent-architecture/ARCHITECTURE_REFERENCE.md) | GUIDE + REF · 归档 [_archive/](./prime-agent-architecture/_archive/) |
| OpenHands Software Agent SDK | [software-agent-sdk/docs](../software-agent-sdk/docs/README.md) | 已有完整 PART1–3 |

DeepTutor 仓库内旧长文 [`DeepTutor/docs/DEEPTUTOR_DEEP_DIVE.md`](../DeepTutor/docs/DEEPTUTOR_DEEP_DIVE.md) 部分章节（两段式 exploring loop、双层记忆）已过时，以 `docs/deeptutor-architecture/` 为准。

---

## 📚 核心文档清单

### 0c. [Agent 审批回调与主子 Agent 通信（多项目横向）](./AGENT_PERMISSION_AND_SUBAGENT_COMMUNICATION.md)

**内容**：12+ 项目的 Tool HITL 审批族、通信时序（含 OpenHarness React IPC）、主子 Agent spawn/IPC/再次调度、OpenHarness `BackgroundTaskManager` 边界、三项目速查表。

**适合读者**：对比 OpenHarness / DeerFlow / deepagents 审批与子 agent 行为，或需要端到端时序图的架构师。

**OpenHarness spawn I/O 专题**：[ARCHITECTURE_TOOLS_SWARM.md](../OpenHarness/docs/ARCHITECTURE_TOOLS_SWARM.md)（进程/协程/PIPE/log 数量与通信链路图）。

---

### 0. [Agent SDK 体系化设计指南（多项目总览）](./AGENT_SDKS_COMPREHENSIVE_DESIGN_GUIDE.md)

**内容**：`software-agent-sdk`、`openai-agents-python`、`deepagents`、`deer-flow` 的统一参考模型、流程图、选型矩阵与延伸阅读索引。

**适合读者**：需要在多个 Agent SDK / Harness 之间选型或建立统一心智模型的架构师与资深开发者。

---

### 0b. [Agent SDK 源码级深读（图解 + 注释）](./AGENT_SDKS_SOURCE_LEVEL_DEEP_DIVE.md)

**内容**：按 **文件路径** 锚定 `run_single_turn`、`Agent.step`、`create_deep_agent`、`make_lead_agent` 等关键边界；Mermaid 流程图带 **源码注释式说明**；附「改行为该打开哪个文件」速查表。

**适合读者**：要在四个栈上做二次开发、排查一轮推理边界、或写内部培训的开发者。

---

### 1. [Deep Agents 框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md)

**篇幅**：937 行  
**内容**：
- 设计思想总论（声明式配置 + 反射 + 标准 Agent 循环）
- 三层架构（SDK / CLI / App）
- 状态与消息（AgentState、reducer、checkpoint）
- 主 Agent 工厂与 Prompt（`create_deep_agent`）
- 工具系统与 Skills（渐进披露）
- 子 Agent：同步与异步
- 中间件链总览（10+ 个中间件）
- 记忆系统（AGENTS.md、防抖队列）
- 摘要与缓存（SummarizationMiddleware）
- CLI 与 App 端概览
- 与 DeerFlow Harness、OpenHands、hermes-agent 对比

**适合读者**：首次接触 Deep Agents，需要建立整体心智模型。

---

### 2. [Deep Agents Middleware Chain 深度设计文档](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md)

**篇幅**：1469 行  
**内容**：
- 中间件链总览（完整顺序、洋葱模型、钩子类型）
- 前置中间件详解（TodoList、Skills、Filesystem、SubAgent）
- 核心中间件详解（Summarization、PatchToolCalls、AsyncSubAgent）
- 后置中间件详解（Profile extra、ToolExclusion、Caching、Memory、HITL、Permission）
- 中间件执行流程（请求/响应路径、状态变更时序图）
- 自定义中间件开发（钩子选择、最佳实践、常见陷阱）

**适合读者**：需要深入理解中间件机制、开发自定义中间件的开发者。

---

### 3. [Deep Agents Prompt 系统完整运行时文档](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md)

**篇幅**：813 行  
**内容**：
- Prompt 拼装逻辑（中间件顺序、占位符替换、动态注入）
- 完整 System Prompt（默认配置，~1800 tokens）
- Plan 模式：`write_todos` 完整提示（System + Tool Description）
- 同步子 Agent：`task` 完整提示（System + Tool Description + 示例）
- 异步子 Agent：5 个异步工具完整提示
- Skills 与 Memory 注入片段（渐进披露模板）
- 本地重打印脚本（验证当前安装版本的 prompt）

**适合读者**：需要调试 prompt、优化 token 用量、理解模型行为的开发者。

---

### 4. [Deep Agents CLI 与 App 端架构设计文档](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md)

**篇幅**：370 行  
**内容**：
- CLI 架构总览（三层模型、启动流程）
- Textual TUI 设计（核心组件、交互模式、主题样式）
- 配置管理系统（config.toml、模型提供商、MCP 服务器）
- 会话持久化（存储结构、恢复机制、checkpoint 同步）
- MCP 集成（服务器连接、工具注册、安全考虑）
- 源码索引（关键文件路径、类与方法）

**适合读者**：需要定制 CLI、开发 GUI 前端、集成 MCP 的开发者。

---

## 🔍 快速检索

### 按主题查找

| 主题 | 相关文档 | 章节 |
|------|---------|------|
| **架构设计** | [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) | §一、§二 |
| **中间件链** | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | 全文 |
| **Prompt 拼装** | [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) | §一、§二 |
| **Plan 模式** | [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) | §三 |
| **子 Agent** | [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) | §六 |
| | [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) | §四、§五 |
| **记忆系统** | [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) | §八 |
| | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §4.4 |
| **Skills 系统** | [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) | §5.2 |
| | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §2.2 |
| **CLI 架构** | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | 全文 |
| **配置管理** | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | §三 |
| **会话持久化** | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | §四 |
| **MCP 集成** | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | §五 |
| **框架对比** | [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) | §十一 |

### 按代码模块查找

| 模块 | 相关文档 | 章节 |
|------|---------|------|
| `graph.py` | [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) | §4.1 |
| `middleware/subagents.py` | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §2.4 |
| | [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) | §四 |
| `middleware/async_subagents.py` | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §3.3 |
| | [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) | §五 |
| `middleware/summarization.py` | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §3.1 |
| `middleware/skills.py` | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §2.2 |
| `middleware/memory.py` | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §4.4 |
| `middleware/filesystem.py` | [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md) | §2.3 |
| `cli/app.py` | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | §二 |
| `cli/config.py` | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | §三 |
| `cli/mcp_tools.py` | [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md) | §五 |

---

## 📖 阅读建议

### 新手入门路径

1. **第一步**：阅读 [框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md) §一、§二，建立整体心智模型。
2. **第二步**：运行 `deepagents` CLI，体验交互式 TUI。
3. **第三步**：阅读 [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) §二，理解模型看到的完整 prompt。
4. **第四步**：尝试配置 MCP 服务器和 Skills，扩展 Agent 能力。

### 进阶开发路径

1. **第一步**：深入阅读 [Middleware Chain 深度设计](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md)，理解中间件机制。
2. **第二步**：开发自定义中间件（参考 §六）。
3. **第三步**：阅读 [CLI 与 App 端架构](./DEEPAGENTS_CLI_APP_ARCHITECTURE.md)，定制 UI 或开发 GUI 前端。
4. **第四步**：贡献代码到上游，修复 bug 或新增功能。

### 调试与优化路径

1. **第一步**：运行 [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) §七的本地重打印脚本，验证当前 prompt。
2. **第二步**：检查 token 用量，优化 Skills 索引和 Memory 文件。
3. **第三步**：启用 `SummarizationMiddleware`，防止超出窗口限制。
4. **第四步**：使用 `PatchToolCallsMiddleware` 日志，诊断悬空 tool_calls 问题。

---

## 🔗 外部参考

### DeerFlow Harness 对比文档

- [DeerFlow Framework QA Archive](../deer-flow/backend/docs/DEERFLOW_FRAMEWORK_QA_ARCHIVE.md)（2333 行）
- [SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md](../deer-flow/backend/docs/SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md)（405 行）
- [SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md](../deer-flow/backend/docs/SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md)
- [SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md](../deer-flow/backend/docs/SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md)

### 官方文档

- [LangChain Deep Agents Overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph)
- [Textual TUI Framework](https://textual.textualize.io/)

### 源码仓库

- [deepagents SDK](../libs/deepagents/)
- [deepagents Code](../libs/code/)
- [deepagents CLI](../libs/cli/)
- [Skills Examples](../skills/)

---

## 📝 维护说明

### 更新策略

1. **升级依赖后**：
   - 运行 [Prompt 系统完整运行时](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md) §七的本地重打印脚本。
   - 对比输出与文档，若有差异则更新。
   - 在文档末尾记录变更日期与版本。

2. **新增功能后**：
   - 在对应文档的新增章节。
   - 更新本索引的"快速检索"表。
   - 在文末追加记录中说明变更内容。

3. **修复错误后**：
   - 直接修正对应文档的错误段落。
   - 在本索引末尾记录修复内容。

### 文档规范

- **语言**：中文为主，关键技术术语保留英文原文。
- **代码块**：使用 Markdown fenced code blocks，标注语言（```python、```json）。
- **链接**：使用相对路径，便于本地浏览。
- **图表**：使用 Mermaid 语法绘制流程图、时序图。
- **引用**：注明源码路径（如 `deepagents/graph.py:50-91`）。

---

## 📅 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-09-01 | v1.6 | Prime Agent 全套扩写至 Codex §1.2/§4 深度（7 文件共 ~3130 行，§1.2 实体全景 + §7 runAgentLoop 五层深潜） |
| 2026-09-01 | v1.5 | Codex PART2/PART3 扩写至 PART1 §4 深度（1828 + 1601 行，87 张 Mermaid 图） |
| 2026-09-01 | v1.4 | DeepTutor 全套扩写至 Codex §1.2/§4 深度（PART1–3 + ENTITY，共 ~3720 行） |
| 2026-09-01 | v1.3 | 新增 Prime Agent 源码级架构系列（`docs/prime-agent-architecture/`），体例对齐 Codex / DeepTutor |
| 2026-09-01 | v1.2 | Codex / DeepTutor 新增 `ENTITY_AND_SEQUENCES.md`（实体字段、ER、端到端+模块时序、JSON 示例） |
| 2026-09-01 | v1.1 | 新增 Codex / DeepTutor 源码级架构系列（`docs/codex-architecture/`、`docs/deeptutor-architecture/`），体例对齐 software-agent-sdk |
| 2026-04-26 | v1.0 | 初始版本，创建 4 个核心文档 + 索引 |

---

**最后更新**：2026-09-01  
**维护者**：Deep Agents 文档团队  
**反馈渠道**：提交 Issue 或 PR 到 [deepagents 仓库](../)
