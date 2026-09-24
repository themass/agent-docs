# OpenCode Archify 图解

> 质量档 `showcase` · 语言 `zh-CN` · 流水线见 [ARCHIFY_DIAGRAM_PROGRAM.md](../../ARCHIFY_DIAGRAM_PROGRAM.md)

| 规格 | HTML | 类型 | 说明 |
|------|------|------|------|
| `opencode-runtime-stack.architecture.json` | [stack](./opencode-runtime-stack.architecture.html) | architecture | 分层总览 |
| `opencode-e2e-prompt.sequence.json` | [e2e](./opencode-e2e-prompt.sequence.html) | sequence | 标准 Prompt 端到端 |
| `opencode-cold-start.workflow.json` | [cold-start](./opencode-cold-start.workflow.html) | workflow | Session 冷启动 |
| `opencode-dual-loop.workflow.json` | [dual-loop](./opencode-dual-loop.workflow.html) | workflow | 外环 / 内环 Drain |
| `opencode-queue-steer.workflow.json` | [queue-steer](./opencode-queue-steer.workflow.html) | workflow | session_input 队列与 steer |
| `opencode-compaction.workflow.json` | [compaction](./opencode-compaction.workflow.html) | workflow | ContextEpoch 压缩 |
| `opencode-session-lifecycle.lifecycle.json` | [lifecycle](./opencode-session-lifecycle.lifecycle.html) | lifecycle | Created → Idle ↔ Draining |
| `opencode-tool-pipeline.dataflow.json` | [tool-pipeline](./opencode-tool-pipeline.dataflow.html) | dataflow | ToolRegistry 管线 |
| `opencode-multi-agent.architecture.json` | [multi-agent](./opencode-multi-agent.architecture.html) | architecture | 多 Agent 与子 Session |

**共 9 张** showcase HTML（每张含 visual-check sidecar）。
