# 多 Agent 协作

> **合并说明**：由以下文档去重合并（2026-08-04）。

---


---

## 多 Agent 实现对比

> **前提**: 「多 Agent」在不同项目里可能是工具委托、子进程、图节点、或声明式 Task 链——本文先分类再逐项目展开。

---

## 1. 协作模式 taxonomy

| 模式 ID | 名称 | 机制 | 父 Agent 可见什么 |
|---------|------|------|-------------------|
| **MA1 工具委托** | 主 Agent 调 `task` / `delegate_task` | 同步/异步子 run | 子 Agent 最终 tool result（压缩） |
| **MA2 子进程 Worker** | Coordinator fork 子进程 | IPC / 协议 | 结构化结果 + metadata |
| **MA3 Handoff** | 切换 active agent | Runner 换 agent 上下文 | 下一 agent 接管对话 |
| **MA4 Crew / Task 图** | 声明式任务依赖 | kickoff 按 Process 执行 | Task output 链式传递 |
| **MA5 GroupChat 路由** | 选人发言 | 路由模型/规则 | 共享 thread |
| **MA6 固定 LangGraph 节点** | 预定义角色节点 | 图边 + 条件路由 | 共享 graph state |
| **MA7 编排器 + Archetype** | Orchestrator spawn 专角色 | 独立 tool scope | compact result only |
| **MA8 Kanban 工作流** | 卡片状态机驱动 | WorkflowEngine 调度 | 卡片 artifact |

---

## 2. 对比维度

| 子维度 | 含义 |
|--------|------|
| **触发方式** | tool call / Flow 阶段 / 图拓扑 / 规则引擎 |
| **并发** | 串行 / 有限并行 / 无限制 |
| **状态隔离** | 独立 thread / 共享 state / 不回流 parent |
| **结果合并** | merge todos? merge messages? 仅 final string? |
| **权限/沙箱** | 子 agent 工具子集、readonly 等 |

---

## 3. Tier 1 总览对照表

| 项目 | 主模式 | 触发 API | 并发上限 | 状态隔离 |
|------|--------|----------|----------|----------|
| **deepagents** | MA1 | `task` tool + SubAgentMiddleware | 可配置 | 独立 thread；**todos 不 merge 回父** |
| **deer-flow** | MA1 | `task` + SubagentLimitMiddleware | `MAX_CONCURRENT_SUBAGENTS=3` | 独立 thread |
| **OpenHarness** | MA2 | Coordinator `--task-worker` | BackgroundTaskManager | 子进程隔离 |
| **Hermes** | MA1 | `delegate_task` + kanban | `delegation.max_concurrent_children` | 子 Agent 独立 terminal |
| **OpenManus** | Flow 单 executor | PlanningFlow while | 1 executor | Flow 内顺序 |
| **OpenAI Agents** | MA3 | handoffs | Runner 管理 | 切换 agent |
| **crewAI** | MA4 | `Crew.kickoff()` | Process 定义 | Task output 传递 |
| **MetaGPT** | MA4 | `Team.run_project()` SOP | 角色流水线 | 产物文件 |
| **AutoGen** | MA5 | GroupChat | 路由策略 | 共享 context |
| **AgentScope** | MA1 + Team 服务 | `Task` / Agent Team RPC | 服务配置 | v2 文档 + 沙箱 |
| **OpenHands** | 单会话为主 | 插件/sub | 依 preset | 事件流 |
| **smolagents** | MA1 轻量 | managed agents | 有限 | 子 agent 历史 |
| **Letta** | Sleeptime multi | 服务端模式 | — | multi-agent 记忆 |
| **nanobot** | MA1 | `SubagentManager` / subagent 工具 | `max_concurrent_subagents` | session 隔离，父 loop 通过 pending injection 接收结果 |
| **LangGraph** | MA6 | 多节点图 | 图定义 | checkpointer per thread |

---

## 4. MA1 工具委托 — 深度对比

### 4.1 deepagents

```
User → create_deep_agent → ReAct loop
                              ↓ task(description, subagent_type)
                         SubAgentMiddleware 起子 graph
                              ↓
                         子 run 完成 → ToolMessage 回父
```

- **关键文件**：`libs/deepagents/deepagents/middleware/subagent.py`
- **隔离**：子 thread 独立 checkpoint；父仅见摘要结果。
- **不 merge**：父 `todos` 不受子 Agent 影响。

### 4.2 deer-flow

- 与 deepagents 同族 `task` 工具。
- **SubagentLimitMiddleware**：硬限并发 3。
- 子 Agent 可带独立 sandbox 路径（per-user 隔离）。

### 4.3 Hermes

- **`delegate_task`**：可选 kanban 卡片跟踪。
- 子 Agent **独立 terminal cwd**；适合并行 coding。
- **配置**：`delegation.max_concurrent_children`。

### 4.4 examples 模式

| 示例 | 模式 |
|------|------|
| `repl_swarm` | QuickJS skill 并行 `tools.task` |
| `async-subagent-server` | FastAPI + AsyncSubAgent middleware |
| `deep_research` | 并行 research sub-agents + reflection |
| `rlm_agent` | 递归 REPL + PTC subagent chain |

### 4.5 nanobot

- **触发点**：`AgentLoop` 初始化 `SubagentManager`，工具层把子 Agent 任务提交给 manager。
- **隔离**：父 turn 仍由 `AgentRunner._run_core()` 驱动；子 Agent 的完成结果不是直接篡改父消息，而是经 session pending queue / injection 进入父 runner。
- **并发控制**：配置项 `max_concurrent_subagents` 约束子 Agent 数量；`AgentLoop` 同时用 `_session_locks` 保证同一 session 串行。
- **状态恢复**：父 runner 执行工具前后写 checkpoint，取消后 `_restore_runtime_checkpoint()` 可把已经产生的 assistant/tool 片段恢复到 session。

详见 [nanobot 源码级实现导读](11-product-deep-dives.md)。

---

## 5. MA2 子进程 — OpenHarness

```
QueryEngine.run_query()
    ↓ 复杂任务
Coordinator.spawn_task_worker()
    ↓ subprocess
--task-worker CLI（独立 QueryEngine 实例）
    ↓
结果 JSON 回主进程 → tool_metadata
```

- **差异化**：强 **PermissionMode**（含 PLAN 只读）在 worker 同样生效。
- **BackgroundTaskManager**：并发任务队列。

---

## 6. MA4 声明式 — crewAI vs MetaGPT

| | crewAI | MetaGPT |
|--|--------|---------|
| **单元** | Agent + Task + Process | Role + Action + SOP |
| **入口** | `Crew.kickoff()` | `Team.run_project()` |
| **输出** | Task result 对象 | 完整代码仓库 + 文档 |
| **循环** | 非单 ReAct；按 Task 依赖 | 固定公司流程 |

---

## 7. MA6 固定图 — TradingAgents（Tier 2）

```
Analysts (可选) → Bull/Bear 辩论 → Research Manager
    → Trader → Risk 三方辩论 → Portfolio Manager → END
```

- **入口**：`TradingAgentsGraph.propagate()` → `StateGraph.stream()`
- **路径**：`TradingAgents/tradingagents/graph/trading_graph.py`
- **轮次**：`max_debate_rounds` / `max_risk_discuss_rounds`
- **与 Tier 1 差异**：拓扑 **固定**，非 middleware 组合；领域金融专用。

---

## 8. MA7 — openhuman Orchestrator

- **引擎**：`run_turn_engine()` 三处共用（主 turn、channel、subagent）。
- **Archetypes**：planner, researcher, code_executor, critic, summarizer, archivist…
- **配置**：`agents/<name>/agent.toml` — tool scope + model hint。
- **隔离**：**子 agent 历史不回流 parent**；parent 只见 compact tool result。
- **路径**：`openhuman/src/openhuman/agent/harness/engine/core.rs`

---

## 9. MA8 — FastAgent Kanban（Tier 2）

```
HostAgent（规划分解）→ Kanban 卡片
    ↓ WorkflowEngine 轮询规则
GroundingAgent（gui/shell/mcp/web 执行）
    ↓ 可选
EvalAgent（评估 grounding 结果）
```

- **入口**：`FastAgent.run()` → `WorkflowEngine`
- **路径**：`FastAgent/fastagent/workflow/engine.py`
- **差异化**：GUI 桌面自动化为一等公民，非通用 SDK。

---

## 10. Tier 2 其他项目

| 项目 | 多 Agent | 说明 |
|------|----------|------|
| **GenericAgent** | 轻量 | `/btw` side-agent；plan 模式可 spawn 验证 subagent |
| **DeepTutor** | 单 capability 多 stage | deep_solve / deep_research 内 planning→reasoning→writing，非独立进程 |
| **FM-Agent** | 无 | 单 pipeline + OpenCode CLI |
| **agentmemory** | N/A | memory 服务，非 agent |
| **agency-agents** | persona 库 | 预写角色分工，宿主工具加载 |

---

## 11. 并发与隔离速查

| 项目 | 并行 subagent | 父可见子 todos | 子 sandbox |
|------|---------------|----------------|------------|
| deepagents | 可配置 | ❌ | 依 backend |
| deer-flow | max 3 | ❌ | per-thread 路径 |
| Hermes | configurable | N/A（todo 独立 store） | 独立 terminal |
| OpenHarness | BackgroundTaskManager | metadata | harness 沙箱 |
| OpenAI Agents | handoff 串行为主 | — | Sandbox Agents |
| crewAI | Process.sequential/hierarchical | — | 无统一 |

---

## 12. 选型建议

```text
要 LangGraph 内 task 工具 + middleware？
  └─ deepagents 或 deer-flow（后者限并发+deferred MCP）

要子进程强隔离 + 权限 Plan？
  └─ OpenHarness Coordinator

要桌面 GUI + Kanban 多角色？
  └─ FastAgent

要固定领域辩论图（金融等）？
  └─ TradingAgents 参考实现

要声明式业务流程（非 ReAct）？
  └─ crewAI 或 MetaGPT

要 OpenAI handoffs + guardrails？
  └─ OpenAI Agents SDK

要 Rust 桌面 + archetype 编排？
  └─ openhuman

要并行 research subagent 范例？
  └─ examples/deep_research, repl_swarm
```

---

## 13. 相关文档

| 文档 | 内容 |
|------|------|
| [01-overview.md](./01-overview.md) | §10 摘要 |
| [05-plan-mode.md](05-plan-mode.md) | Plan 与 subagent 交织 |
| [06-memory.md](06-memory.md) | 子 agent 记忆是否回流 |

---

**最后更新**: 2026-06-08

