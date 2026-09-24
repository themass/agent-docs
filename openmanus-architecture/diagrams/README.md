# OpenManus Archify 图解

> `showcase` 质量档 · `meta.locale: zh-CN` · 共 **11** 张交互式 HTML  
> 事实来源：[ARCHITECTURE_PART1.md](../ARCHITECTURE_PART1.md) · [ARCHITECTURE_PART2.md](../ARCHITECTURE_PART2.md) · [PLAN_MODE_SOURCE_WALKTHROUGH.md](../PLAN_MODE_SOURCE_WALKTHROUGH.md)

| # | 规格 | HTML | 类型 | 层级 | 对应章节 |
|---|------|------|------|------|----------|
| 1 | `openmanus-five-layer.architecture.json` | [five-layer](./openmanus-five-layer.architecture.html) | architecture | Tier0 | §1.2 五层架构 |
| 2 | `openmanus-baseagent-run.sequence.json` | [baseagent-run](./openmanus-baseagent-run.sequence.html) | sequence | Tier0 | §4.2 BaseAgent.run 外层循环 |
| 3 | `openmanus-think-act.sequence.json` | [think-act](./openmanus-think-act.sequence.html) | sequence | Tier0 | §5 think/act 内层 ReAct |
| 4 | `openmanus-planningflow.workflow.json` | [planningflow](./openmanus-planningflow.workflow.html) | workflow | Tier1 | §6 PlanningFlow 外层编排 |
| 5 | `openmanus-tool-pipeline.dataflow.json` | [tool-pipeline](./openmanus-tool-pipeline.dataflow.html) | dataflow | Tier1 | §4.5 ToolCollection |
| 6 | `openmanus-mcp.architecture.json` | [mcp](./openmanus-mcp.architecture.html) | architecture | Tier1 | Part2 §2 MCP 双向扩展 |
| 7 | `openmanus-agent-state.lifecycle.json` | [agent-state](./openmanus-agent-state.lifecycle.html) | lifecycle | Tier1 | §3.2 AgentState 状态机 |
| 8 | `openmanus-e2e-planning.sequence.json` | [e2e-planning](./openmanus-e2e-planning.sequence.html) | sequence | Tier1 | §7 main.py vs run_flow.py |
| 9 | `openmanus-plan-mode-example.sequence.json` | [plan-mode-example](./openmanus-plan-mode-example.sequence.html) | sequence | Tier2 | Plan 模式完整示例时序 |
| 10 | `openmanus-plan-message-stores.dataflow.json` | [plan-message-stores](./openmanus-plan-message-stores.dataflow.html) | dataflow | Tier2 | 规划瞬时消息 / plans / executor Memory |
| 11 | `openmanus-plan-mode-loop.workflow.json` | [plan-mode-loop](./openmanus-plan-mode-loop.workflow.html) | workflow | Tier2 | PlanningFlow 外环逐步执行 |

## 图解说明

### Tier0 — 核心心智模型

- **五层架构**：L0 入口 → L1 flow → L2 Agent 内核 → L3 协议/LLM → L4 ToolCollection
- **外层循环**：`BaseAgent.run()` 的 `while step < max_steps`、状态机与卡住检测
- **内层 ReAct**：`ToolCallAgent` 的 `think()`（`ask_tool`）与 `act()`（`execute`）

### Tier1 — 深潜专题

- **PlanningFlow**：双 LLM 规划 + 每 step 独立 `run()`，Memory 不跨 step 共享
- **工具管线**：`to_params()` → `tool_calls` → `ToolCollection.execute` → BaseTool 插件
- **MCP 双向**：客户端 MCPClients → MCPClientTool 并入 ToolCollection；服务端 FastMCP 暴露工具
- **AgentState 生命周期**：IDLE → RUNNING → FINISHED（Terminate）；max_steps/ERROR 见卡片说明
- **端到端对比**：main.py 单轮 ReAct vs run_flow.py PlanningFlow 多 step 编排

### Tier2 — Plan 模式源码导读

- **完整示例时序**：用户 prompt → Flow.llm 建计划 → Manus / DataAnalysis 逐步 `run()` → 总结
- **三本账**：规划器瞬时 messages、`PlanningTool.plans`、executor Memory（Manus 跨步累积）
- **外环工作流**：create → 取 active step → `[AGENT]` 路由 → `executor.run` → mark completed → finalize

## 重新生成

```bash
ARCHIFY=/Users/gqli/.cursor/skills/archify
DIR=docs/openmanus-architecture/diagrams
for f in "$DIR"/*.json; do
  case "$f" in *.visual-check.json) continue ;; esac
  type=$(python3 -c "import json; print(json.load(open('$f'))['diagram_type'])")
  base=$(basename "$f" .json)
  node "$ARCHIFY/bin/archify.mjs" deliver "$type" "$f" "$DIR/${base}.html" --quality showcase
done
```

## 验收记录

每张图均通过 `validate --quality showcase`（9 项 artifact checks，0 errors / 0 warnings）、`deliver` 确定性渲染，以及 `visual-check` 桌面视口检测。
