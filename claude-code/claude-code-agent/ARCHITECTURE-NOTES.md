# Claude Code 架构解剖 · 阅读索引

> 基于 2026-03-31 公开源码快照的**函数级**架构学习笔记。供学习用途；原始代码归 Anthropic 所有。
> 共 19 篇（00 总览 + 01–18 深度讲解），逐层通读了主循环、Tool 契约、权限管线、多 Agent 编排、上下文与记忆等子系统。每篇都带**真实代码片段 + `file:line` + 示例数据 + mermaid 图**，可边看边对照源码。

**从这里开始 →** [docs/architecture/00-overview.md](docs/architecture/00-overview.md)（心智模型、三层架构、八条全局设计原则）

---

## 全部篇目

### 主循环与状态（地基）
| # | 文档 | 一句话 |
|---|---|---|
| 00 | [总览](docs/architecture/00-overview.md) | 心智模型 + 三层同心圆 + "万物皆消息" + 8 条全局原则 |
| 01 | [Agent 主循环（核心）](docs/architecture/01-agent-loop-core.md) | `while(true)` + `State` 结构 + `needsFollowUp` 退出信号 + 下一回合历史拼接 |
| 02 | [主循环（重试/恢复/thinking/终止）](docs/architecture/02-agent-loop-recovery.md) | 三套 fallback、413 与 max_output_tokens 恢复、withheld 错误、thinking 规则、Terminal 全枚举 |
| 03 | [跨回合状态与转录持久化](docs/architecture/03-state-persistence.md) | `mutableMessages`、JSONL 转录、`appendEntry`、tombstone 截断、resume、8 个簿记字段的作用域×落盘表 |

### 工具系统
| # | 文档 | 一句话 |
|---|---|---|
| 04 | [Tool 契约与 buildTool](docs/architecture/04-tool-contract.md) | `Tool` 接口逐方法解剖、fail-closed 默认值、`GlobTool` 真实范例 |
| 05 | [工具池组装、API schema 与 ToolSearch](docs/architecture/05-tool-registry-schema.md) | `getAllBaseTools`（DCE）、缓存稳定分区排序、`toolToAPISchema`、延迟加载 |
| 06 | [工具执行与并发调度](docs/architecture/06-tool-execution.md) | `checkPermissionsAndCallTool` 全流水线、`StreamingToolExecutor` 状态机、有序发出、sibling abort |

### 安全闸门
| # | 文档 | 一句话 |
|---|---|---|
| 07 | [权限决策引擎](docs/architecture/07-permission-engine.md) | 编排器/决策引擎分离、`deny > ask > allow` 评估顺序、权限模式作为变换、bypass carve-out |
| 08 | [规则匹配、Bash 归一化与 auto 分类器](docs/architecture/08-rule-matching-classifier.md) | exact/prefix/wildcard 匹配、"允许从严拒绝从宽"、`toAutoClassifierInput`、fail-open/closed killswitch |
| 09 | [Pre/PostToolUse Hook 与闸门协调](docs/architecture/09-hooks.md) | hook stdout JSON、`resolveHookPermissionDecision`、hook 只能收紧/受限放宽 |

### 多 Agent 编排
| # | 文档 | 一句话 |
|---|---|---|
| 10 | [多 Agent：递归与上下文隔离](docs/architecture/10-multi-agent-isolation.md) | `runAgent` 递归调 `query()`、`createSubagentContext` 逐字段隔离、工具过滤限深 |
| 11 | [多 Agent：异步结果回注与前后台](docs/architecture/11-multi-agent-orchestration.md) | `<task-notification>` 作为注入消息、通知队列按 agentId drain、前后台 race 交接、任务注册表 |
| 12 | [协调者、团队与 SendMessage 路由](docs/architecture/12-coordinator-teams-messaging.md) | coordinator system prompt、`agentNameRegistry` 路由、排队/自动恢复/广播、文件邮箱 |

### 上下文与记忆
| # | 文档 | 一句话 |
|---|---|---|
| 13 | [系统提示词与三段可缓存前缀](docs/architecture/13-system-prompt-cache.md) | `getSystemPrompt` 有序数组、`DYNAMIC_BOUNDARY` 哨兵、section 缓存、cache breakpoints |
| 14 | [CLAUDE.md、嵌套记忆与 attachments](docs/architecture/14-claudemd-nested-memory.md) | 记忆文件优先级、`@include`、按需注入 nested memory、双 Set 去重、attachments 流水线 |
| 15 | [上下文压缩](docs/architecture/15-compaction.md) | 阈值+buffer+熔断、8 段式定长摘要、post-compact 重新水化、micro/session 压缩 |
| 16 | [持久记忆（memdir/提取/召回）](docs/architecture/16-persistent-memory.md) | 四类 taxonomy + MEMORY.md 索引、异步 fork "图书管理员"写入、便宜选择器召回 |
| 17 | [Token 计数、成本与结果落盘](docs/architecture/17-tokens-cost-spill.md) | `tokenCountWithEstimation`、超大结果落盘 `<persisted-output>`、`ContentReplacementState` 冻结决策 |

### 可扩展性
| # | 文档 | 一句话 |
|---|---|---|
| 18 | [Skill 渐进披露 / MCP / 插件](docs/architecture/18-extensibility.md) | SKILL.md frontmatter 常驻+正文按需加载、MCP 连接、插件加载、三条扩展通道对比 |

---

## 搬进你的项目（分阶段落地）

别一上来抄全套。这套架构的价值在于**分层可增量**——先跑通最小闭环，再逐层加安全、加上下文管理、加多 agent。

1. **最小闭环**：`Tool = { name, inputSchema(Zod), call() }` + 一个 `async function*`：流式调模型 → 收 tool_use → 结果作为 user 消息拼回历史 → 循环到没有 tool_use。→ 参见 [01](docs/architecture/01-agent-loop-core.md) · [04](docs/architecture/04-tool-contract.md)
2. **加安全闸门**：`call()` 前插 `parse → validate → gate`；决策引擎独立成纯函数，`deny > ask > allow`；规则归一化后匹配，允许从严拒绝从宽。→ 参见 [06](docs/architecture/06-tool-execution.md) · [07](docs/architecture/07-permission-engine.md) · [08](docs/architecture/08-rule-matching-classifier.md)
3. **加上下文管理**：请求前缀拆"静态可缓存段 + 动态边界 + 消息"；逼近上限用定长 schema 总结并续写；超大结果落盘留路径+预览并冻结决策跨轮重放。→ 参见 [13](docs/architecture/13-system-prompt-cache.md) · [15](docs/architecture/15-compaction.md) · [17](docs/architecture/17-tokens-cost-spill.md)
4. **加多 Agent**：子 agent = 用隔离上下文再调同一个循环，过滤掉 Agent 工具限深；异步结果作为注入消息回父循环；统一任务注册表 + 极小多态 `kill` 接口。→ 参见 [10](docs/architecture/10-multi-agent-isolation.md) · [11](docs/architecture/11-multi-agent-orchestration.md)
5. **加持久记忆与可扩展性**：类型化 markdown + 常驻索引，异步 fork agent 写入、便宜选择器召回；能力扩展走 Tool / Skill / MCP 三条平行通道。→ 参见 [16](docs/architecture/16-persistent-memory.md) · [18](docs/architecture/18-extensibility.md)

---

## 关于本套文档的生成与校对状态

- 18 篇正文由多 agent 工作流实地通读源码生成，每篇作者**逐一核对了行号、常量真值与代码原文**，并在开头/脚注标注了本快照中缺失的类型定义文件（如 `src/query/transitions.js`、`src/types/message.ts` 等 type-only import 或被 bundler 裁剪的模块），相应字段以实际使用点反推并明确说明。
- 计划中的**独立保真校对**（第二道工序）因触发账号 session 限额未能跑完；正文可信度以作者自检为准。如需对某篇做逐行复核，可单独触发校对。
- 所有示例数据均据源码真实结构（Zod schema / TS 类型 / 常量 / 测试 fixture）构造并标注"（示例，据源码构造）"，未臆造字段名或 API。
