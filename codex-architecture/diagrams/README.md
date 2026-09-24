# Codex Archify 图解

> `showcase` 质量档 · `meta.locale: zh-CN` · 共 **9** 张交互式 HTML  
> 事实来源：[ARCHITECTURE_PART1.md](../ARCHITECTURE_PART1.md) · [JSONL_TREE_GUIDE.md](../JSONL_TREE_GUIDE.md) · [MULTI_AGENT_ARCHITECTURE.md](../MULTI_AGENT_ARCHITECTURE.md)

| # | 规格 | HTML | 类型 | 对应章节 |
|---|------|------|------|----------|
| 1 | `codex-runtime-stack.architecture.json` | [runtime-stack](./codex-runtime-stack.architecture.html) | architecture | §1.2 运行时分层总览 |
| 2 | `codex-e2e-prompt.sequence.json` | [e2e-prompt](./codex-e2e-prompt.sequence.html) | sequence | §6 端到端流程 |
| 3 | `codex-jsonl-tree.dataflow.json` | [jsonl-tree](./codex-jsonl-tree.dataflow.html) | dataflow | JSONL_TREE_GUIDE §2 三真相 |
| 4 | `codex-multi-agent.architecture.json` | [multi-agent](./codex-multi-agent.architecture.html) | architecture | §8 多 Agent |
| 5 | `codex-sandbox.workflow.json` | [sandbox](./codex-sandbox.workflow.html) | workflow | §4.6 工具沙箱执行 |
| 6 | `codex-dual-loop.workflow.json` | [dual-loop](./codex-dual-loop.workflow.html) | workflow | §2.6 双循环 |
| 7 | `codex-context-compaction.workflow.json` | [context-compaction](./codex-context-compaction.workflow.html) | workflow | §4.1.4 / §7 压缩双路径 |
| 8 | `codex-tool-pipeline.dataflow.json` | [tool-pipeline](./codex-tool-pipeline.dataflow.html) | dataflow | §4.6 工具执行管道 |
| 9 | `codex-thread-subagent.sequence.json` | [thread-subagent](./codex-thread-subagent.sequence.html) | sequence | §4.1.2 / §8 spawn 与投递 |

## 图解说明

### 核心心智模型

1. **运行时分层** — 客户端 → Entry → CodexThread → SessionIo → Session → run_turn → Responses API；ContextManager 与 Rollout jsonl 持久化。
2. **端到端时序** — submit(Op::TurnInput) → submission_loop → spawn_task → run_turn Step 循环 → TurnComplete。
3. **三真相投影** — run_turn 同时写出 ContextManager（模型）、EventMsg（UI）、Rollout jsonl（磁盘）。
4. **多 Agent** — 父子 Thread 隔离；spawn 异步；V1 send_input vs V2 邮箱协议。
5. **沙箱工作流** — FunctionCall → dispatch → ExecApproval → Sandbox attempt → record 输出。
6. **双循环** — 外层 submission_loop 只 dispatch；内层 RunningTask 跑 run_turn Step 循环。
7. **压缩双路径** — Auto inline（PreTurn/MidTurn）vs Op::Compact → CompactTask；内存 replace + JSONL append Compacted。
8. **工具管道** — try_run_sampling → ToolCallRuntime → ToolOrchestrator → 审批 → Sandbox → record。
9. **子 Agent spawn** — ToolRouter FunctionCall → AgentControl → 子 Session；send_input vs 邮箱投递。

## 重新生成

```bash
ARCHIFY=/Users/gqli/.cursor/skills/archify
DIR=docs/codex-architecture/diagrams
for f in "$DIR"/codex-*.json; do
  type=$(python3 -c "import json; print(json.load(open('$f'))['diagram_type'])")
  base=$(basename "$f" .json)
  node "$ARCHIFY/bin/archify.mjs" deliver "$type" "$f" "$DIR/${base}.html" --quality showcase
done
```

## 验证

```bash
# 规格校验
node "$ARCHIFY/bin/archify.mjs" validate architecture "$DIR/codex-runtime-stack.architecture.json" --quality showcase

# 浏览器证据
node "$ARCHIFY/bin/archify.mjs" visual-check "$DIR/codex-runtime-stack.architecture.html" --json
```
