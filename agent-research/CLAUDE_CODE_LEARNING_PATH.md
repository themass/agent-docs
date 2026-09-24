# Claude Code 源码学习路线（4 周）

> 配合 [CLAUDE_CODE_MASTER_ARCHITECTURE.md](./CLAUDE_CODE_MASTER_ARCHITECTURE.md) 与 `claude-code-agent/src/` 使用。

---

## 前置

- 本机已安装 `claude` CLI（可选，用于对照行为）
- 已 clone：`claude-code/`、`claude-code-agent/`、`claude-agent-sdk-python/`
- 编辑器：能跳转 TS 定义；快照部分文件为 `.js` import 路径

---

## 第 1 周：脊柱

| 日 | 阅读 | 动手 |
|----|------|------|
| 1 | Master §0–§1，`00-overview` | 画三层同心圆 + 产品三层 |
| 2 | `01-agent-loop-core` | 读 `src/query.ts`：`query` / `queryLoop` 签名 |
| 3 | 续 01 | 列全 `Terminal.reason` 表，在源码搜 `return { reason` |
| 4 | `03-state-persistence` | 区分 `Message[]` vs `State` 簿记字段 |
| 5 | `02-agent-loop-recovery` 前半 | 跟一条 413 恢复分支 |
| 6 | `02` 后半 + thinking | 笔记：withheld errors |
| 7 | 复盘 | 用 mermaid 重画单回合流程（不看文档） |

**验收**：能口头说明 `needsFollowUp` 为何取代 `stop_reason`。

---

## 第 2 周：工具与安全

| 日 | 阅读 | 动手 |
|----|------|------|
| 1 | `04-tool-contract` | 读一个具体 Tool（如 Glob）全文 |
| 2 | `05-tool-registry-schema` | 理解工具排序与 cache |
| 3 | `06-tool-execution` | 读 `StreamingToolExecutor` 状态机 |
| 4 | `07-permission-engine` | 写表：`deny > ask > allow` 在哪几处出现 |
| 5 | `08-rule-matching-classifier` | 试一条 Bash 规则归一化 |
| 6 | `09-hooks` + `claude-code/examples/hooks/` | 跑一个官方 PreToolUse 示例 |
| 7 | CHANGELOG 搜 `PreToolUse` | 标 3 条 binary-only 行为 |

**验收**：画出从 `tool_use` 到 `tool_result` 的完整序列图（含 hook）。

---

## 第 3 周：上下文与多 Agent

| 日 | 阅读 | 动手 |
|----|------|------|
| 1 | `13-system-prompt-cache` | 找 `DYNAMIC_BOUNDARY` |
| 2 | `14-claudemd-nested-memory` | 项目根放 `CLAUDE.md` 观察注入 |
| 3 | `15-compaction` | 对比 `agent-framework/docs/COMPACTION_SOURCE.md` |
| 4 | `16-persistent-memory` | 理解 memdir taxonomy |
| 5 | `17-tokens-cost-spill` | `<persisted-output>` 格式 |
| 6 | `10` + `11` 多 agent | 跟 `runAgent` 调用栈 |
| 7 | `12-coordinator-teams-messaging` | 可选：Teams 消息路由 |

**验收**：解释「万物皆消息」的 4 种注入类型。

---

## 第 4 周：扩展与集成

| 日 | 阅读 | 动手 |
|----|------|------|
| 1 | `18-extensibility` | Skill frontmatter vs 正文加载 |
| 2 | `claude-code/plugins/plugin-dev/` | 读 SKILL 作者指南 |
| 3 | 选一个官方 plugin（如 `security-guidance`） | 全文拆解 hooks/agents |
| 4 | `claude-agent-sdk-python` 文档 | 最小 stream-json 脚本 |
| 5 | `QueryEngine.ts` 输出路径 | 对照 SDK 事件类型 |
| 6 | Master §8 | 与 `libs/deepagents` middleware 对照表 |
| 7 | 写一篇 1 页笔记 | 「若重写 Harness，抄哪 3 块、删哪 3 块」 |

**验收**：能写一个带 PreToolUse 的最小 plugin 骨架（不必发布）。

---

## 习题库（自测）

1. `query()` 与 `queryLoop()` 为何要把 command `completed` 放在外层？
2. PostToolUse hook `continueOnBlock: true` 改变的是哪一步？
3. 子 agent 结果如何回到父循环？消息 tag 是什么？
4. autocompact 与 micro-compact 触发条件有何不同？
5. 官方 GitHub 仓能否回答「StreamingToolExecutor 有几态」？应去哪读？

**答案索引**：01、09、11、15、Master §0。

---

## 延伸

- 其他 Agent 项目 → [OSS_AGENT_RESEARCH_CATALOG.md](./OSS_AGENT_RESEARCH_CATALOG.md)
- 多框架记忆/压缩 → `OpenHarness/docs/framework-comparison/README.md`
