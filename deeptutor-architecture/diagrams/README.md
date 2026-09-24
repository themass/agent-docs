# DeepTutor Archify 图解

> `showcase` 质量档 · `meta.locale: zh-CN` · 共 **8** 张交互式 HTML  
> 事实来源：[ARCHITECTURE_PART1.md](../ARCHITECTURE_PART1.md) · [CONTEXT_AND_PROJECTION.md](../CONTEXT_AND_PROJECTION.md)

| # | 规格 | HTML | 类型 | 对应章节 |
|---|------|------|------|----------|
| 1 | `deeptutor-stack.architecture.json` | [stack](./deeptutor-stack.architecture.html) | architecture | §1.2 六层运行时分层 |
| 2 | `deeptutor-turn.sequence.json` | [turn](./deeptutor-turn.sequence.html) | sequence | §4 TurnRuntimeManager |
| 3 | `deeptutor-orchestrator.workflow.json` | [orchestrator](./deeptutor-orchestrator.workflow.html) | workflow | §3 ChatOrchestrator |
| 4 | `deeptutor-context-projection.dataflow.json` | [context-projection](./deeptutor-context-projection.dataflow.html) | dataflow | CONTEXT_AND_PROJECTION §2–6 |
| 5 | `deeptutor-e2e.sequence.json` | [e2e](./deeptutor-e2e.sequence.html) | sequence | CORE_RUNTIME_WALKTHROUGH 场景 A |
| 6 | `deeptutor-memory.dataflow.json` | [memory](./deeptutor-memory.dataflow.html) | dataflow | §10 Memory L1–L3 |
| 7 | `deeptutor-agent-loop.workflow.json` | [agent-loop](./deeptutor-agent-loop.workflow.html) | workflow | §7 AgentLoop 状态机 |
| 8 | `deeptutor-compaction.workflow.json` | [compaction](./deeptutor-compaction.workflow.html) | workflow | §9 ContextBuilder 压缩 |

## 图解说明

### 核心心智模型

1. **六层分层** — L7 Web/CLI → L6 WS → L5 TRM/Orchestrator → L4 Capability → L3 AgentLoop → L2 工具 → L1 SQLite。
2. **Turn 时序** — start_turn → handle → capability.run → AgentLoop → stream → flush turn_events + add_message。
3. **编排工作流** — UnifiedContext → handle → Registry → capability.run → AgentLoop → RESULT/DONE。
4. **四层投影** — Capability 并行写出 StreamEvent / turn_events / messages；ContextBuilder 另算 LLM 输入。
5. **端到端冷启动** — deeptutor chat → ensure_session → ChatCapability → AgentLoop → DONE → 落库。
6. **Memory L1–L3** — L1 trace → consolidator → L2 PROFILE / L3 slots → memory_context 注入。
7. **AgentLoop** — narration（有工具）vs finish（无工具）；dispatch 并行；Settlement / Forced finish 见卡片。
8. **ContextBuilder** — 预算检查 → 摘要 → watermark；AgentLoop._guard_context_window 为第二防线。

## 重新生成

```bash
ARCHIFY=/Users/gqli/.cursor/skills/archify
DIR=docs/deeptutor-architecture/diagrams
for f in "$DIR"/deeptutor-*.json; do
  type=$(python3 -c "import json; print(json.load(open('$f'))['diagram_type'])")
  base=$(basename "$f" .json)
  node "$ARCHIFY/bin/archify.mjs" deliver "$type" "$f" "$DIR/${base}.html" --quality showcase
done
```

## 验证

```bash
# 规格校验
node "$ARCHIFY/bin/archify.mjs" validate architecture "$DIR/deeptutor-stack.architecture.json" --quality showcase

# 浏览器证据
node "$ARCHIFY/bin/archify.mjs" visual-check "$DIR/deeptutor-stack.architecture.html" --json
```
