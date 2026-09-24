# Plan Mode、`update_plan` 与 Multi-Agent 源码级全览

> **源码根**：`codex/codex-rs/`  
> **多 Agent 架构导读（V1/V2 图表）**：[MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md)  
> **关联**：[ARCHITECTURE_PART1.md §8–§9](./ARCHITECTURE_PART1.md)、[FULL_LIFECYCLE_SEQUENCE.md](./FULL_LIFECYCLE_SEQUENCE.md)、[RUNTIME_PROMPTS.md](./RUNTIME_PROMPTS.md)、[**UPDATE_PLAN_REFERENCE.md**](./UPDATE_PLAN_REFERENCE.md)（`update_plan` 修订专文）

本文档合并 Plan / `update_plan` / Multi-Agent 的**机制、范式、对比与示例**，并校正常见误解（含「进度不进 history」「Execute/Pair 模式名」等）。

---

## 目录

1. [10 秒决策：用哪个？](#1-10-秒决策用哪个)
2. [`update_plan` 工具（源码详解）](#2-update_plan-工具源码详解)
3. [Plan Mode（协作模式）](#3-plan-mode协作模式)
4. [`update_plan` vs Plan Mode](#4-update_plan-vs-plan-mode)
5. [`update_plan` vs `followup_task`（MA V2）](#5-update_plan-vs-followup_taskma-v2)
6. [Multi-Agent 设计（V1 / V2）](#6-multi-agent-设计v1--v2)
7. [协作范式地图（ReAct / Plan-and-Execute / 协调器）](#7-协作范式地图)
8. [完整示例](#8-完整示例)
9. [常见误解校正表](#9-常见误解校正表)
10. [源码速查](#10-源码速查)

---

## 1. 10 秒决策：用哪个？

```text
用户想「先审方案、再动手」？
  → 切 CollaborationMode 到 Plan（ModeKind::Plan）

用户已在 Default 模式执行，只想看进度勾选？
  → 模型调 update_plan（需 config.update_plan_enabled）

想把子任务派给独立 Agent？
  → spawn_agent + send_message/followup_task（MA V2）或 send_input（MA V1）
```

| 机制 | 谁启用 | 模型怎么产出 | 要不要人批准 |
|------|--------|--------------|--------------|
| **Plan Mode** | 用户切模式 | 自然语言里的 `<proposed_plan>` 块 | **要**（TUI「Implement this plan?」） |
| **`update_plan`** | Default + 配置开关 | `FunctionCall(update_plan, JSON)` | **不要** |
| **Multi-Agent** | Feature + 模型 capability | `spawn_agent` 等 tool | 委派策略在 tool description 里 |

**硬互斥**：Plan Mode 下调用 `update_plan` → Handler **直接报错**（Rust 层，非 prompt 软约束）。

---

## 2. `update_plan` 工具（源码详解）

### 2.1 一句话定义

`update_plan` 是 **Default 协作模式下的执行期进度清单工具**：向客户端发 `PlanUpdate` 事件渲染 checklist，并向模型返回固定文本 `"Plan updated"`。**不修改文件、不 spawn 子 Agent、不写 followup 队列。**

| 文件 | 职责 |
|------|------|
| `core/src/tools/handlers/plan.rs` | `PlanHandler` 执行器 |
| `core/src/tools/handlers/plan_spec.rs` | JSON Schema / tool spec |
| `protocol/src/plan_tool.rs` | `UpdatePlanArgs`、`PlanItemArg`、`StepStatus` |

### 2.2 JSON Schema

```json
{
  "name": "update_plan",
  "parameters": {
    "explanation": "string | null",
    "plan": [
      { "step": "string", "status": "pending | in_progress | completed" }
    ]
  }
}
```

| 字段 | 说明 |
|------|------|
| `plan` | **必填**（schema required）；每项含 `step` + `status` |
| `explanation` | 可选，展示在「Updated Plan」卡片顶部 |
| `status` | `pending` / `in_progress` / `completed` |

**校正**：tool **description** 写明「同一时刻最多一个 `in_progress`」，但 **`PlanHandler` 未在 Rust 里校验**（无「plan 非空」「in_progress 唯一」的硬检查）。违反约束只靠模型自律；畸形 JSON 会在 `serde_json::from_str` 失败。

### 2.3 注册与门控

```1136:1138:codex/codex-rs/core/src/tools/spec_plan.rs
    if turn_context.config.update_plan_enabled {
        registry.add(PlanHandler);
    }
```

- 配置：`config.update_plan_enabled`
- Plan Mode 拒绝：`turn.mode() == ModeKind::Plan` → `FunctionCallError::RespondToModel`
- 协作模式名是 **`ModeKind::Default`**，不是「Execute / Pair」；serde 别名含 `execute`、`pair_programming`、`code`（见 `protocol/src/config_types.rs`）

### 2.4 执行链路

```text
LLM FunctionCall(update_plan)
  → ToolRouter → PlanHandler::handle_call
      → [Plan 模式?] 报错返回
      → parse UpdatePlanArgs
      → session.send_event(EventMsg::PlanUpdate(args))
      → ToolOutput "Plan updated" → FunctionCallOutput 回模型
```

Core 内部事件：`EventMsg::PlanUpdate(UpdatePlanArgs)`  
App-Server 对外：`turn/plan/updated`（`TurnPlanUpdatedNotification`）

```93:98:codex/codex-rs/core/src/tools/handlers/plan.rs
        let args = parse_update_plan_arguments(&arguments)?;
        session
            .send_event(turn.as_ref(), EventMsg::PlanUpdate(args))
            .await;

        Ok(boxed_tool_output(PlanToolOutput))
```

`PlanHandler` 标记为 `is_builtin_control_tool()`（内置控制面工具，非用户 MCP）。

### 2.5 产出与消费

| 消费者 | 收到什么 | 用途 |
|--------|----------|------|
| **TUI transcript** | `on_plan_update` → `PlanUpdateCell`（「Updated Plan」勾选列表） | 对话历史区展示 |
| **TUI 终端标题** | `last_plan_progress` → `Tasks {completed}/{total}` | 状态栏进度 |
| **模型下一轮** | `FunctionCall`（含完整 JSON 参数）+ `FunctionCallOutput("Plan updated")` | ReAct 继续；**结构化 plan 在 tool call 参数里** |
| **Rollout** | `FunctionCall` / `FunctionCallOutput` **持久化**；`PlanUpdate` **事件不持久化** | 见下节 |

**校正（重要）**：

- ❌ 「进度不进 ContextManager / 对话历史」——**不准确**。
- ✅ **`PlanUpdate` 事件**列为 rollout 的 **Transient, non-durable**（`rollout/src/policy.rs`），不重放为独立历史项。
- ✅ **`ResponseItem::FunctionCall`**（含 `update_plan` 的 arguments JSON）与 **`FunctionCallOutput`**（`"Plan updated"`）**会**写入 rollout，并进入后续 `for_prompt` 的模型上下文。
- 模型「记得」自己上报过的步骤，主要靠 **history 里的 FunctionCall 参数**，不是靠重放 `PlanUpdate` 事件。

TUI 侧 `last_plan_progress` 存于 `TranscriptState`（内存）；新 Turn 会 `reset_turn_flags`，但 **`last_plan_progress` 不在 reset 列表**，可能被下一次 `update_plan` 覆盖。

### 2.6 存储生命周期（精确表述）

| 数据 | 生命周期 |
|------|----------|
| `EventMsg::PlanUpdate` | 瞬时 EQ；**不**写入 rollout 持久事件 |
| `FunctionCall` + `FunctionCallOutput` | 随 thread rollout **持久化**（`should_persist_response_item`） |
| TUI `last_plan_progress` | ChatWidget 内存；非 Session 真相源 |
| MemoryStore | **不**因 `update_plan` 单独写入 |

---

## 3. Plan Mode（协作模式）

### 3.1 本质

`ModeKind::Plan` 是 **协作模式维度**（`CollaborationMode`），不是工具。通过 WorldState / catalog 注入 plan 专用 developer 指令（模板见 `collaboration-mode-templates/templates/plan.md`）。

与 `update_plan` **正交且互斥**（Plan 下禁用该工具）。

### 3.2 模型如何产出计划

模型在 assistant 回复中嵌入 **`<proposed_plan>...</proposed_plan>`**（流式解析，非 tool call）：

```text
run_turn → try_run_sampling_request (plan_mode=true)
  → AssistantMessageStreamParsers 分流
      → 普通文字 → AgentMessageContentDelta
      → plan 块   → PlanDelta（流式）→ 完成时 TurnItem::Plan(PlanItem)
  → strip_proposed_plan_blocks：plan 正文不进普通 AgentMessage history
```

源码锚点：`session/turn.rs`（`PlanModeStreamState`、`handle_plan_segments`）、`stream_events_utils.rs`（`strip_proposed_plan_blocks`）。

### 3.3 UI 与用户审批

| 阶段 | 事件 / UI |
|------|-----------|
| 流式 | `PlanDelta` → TUI「**Proposed Plan**」（Markdown） |
| 完成 | `TurnItem::Plan` → `new_proposed_plan` 历史卡片 |
| Turn 结束 | 弹窗 **「Implement this plan?」**（`plan_implementation.rs`） |

审批选项（**不是** `/apply-plan` slash）：

| 选项 | 行为 |
|------|------|
| Yes, implement this plan | 切 `ModeKind::Default`，提交 `"Implement the plan."` |
| Yes, clear context and implement | 清 UI + 新上下文，首条 user message 内嵌 plan 全文 |
| No, stay in Plan mode | 继续规划 |

### 3.4 Plan Mode 行为约束

| 约束 | 原因 |
|------|------|
| `update_plan` 拒绝 | 避免双通道计划语义 |
| `TurnStartKind::Automatic` 被拒（`PlanMode`） | 邮箱 / 子 Agent 不能自动开 Turn |
| `request_user_input` **blocking** | Plan 下等人输入 |

### 3.5 持久化

| 数据 | Rollout |
|------|---------|
| `PlanDelta` 事件 | ❌ 非 durable |
| `TurnItem::Plan`（`ItemCompleted`） | ✅ Paginated / Legacy 策略下持久化 |
| 剥 plan 后的 assistant 说明文字 | ✅ 作为 `AgentMessage` |

---

## 4. `update_plan` vs Plan Mode

| 维度 | `update_plan` | Plan Mode |
|------|---------------|-----------|
| 类型 | **工具**（`FunctionCall`） | **协作模式**（`ModeKind::Plan`） |
| 启用 | `update_plan_enabled` + Default | 用户切 `CollaborationMode` |
| 产出格式 | JSON `{ step, status }` | Markdown `<proposed_plan>` |
| UI 标题 | Updated Plan（勾选） | Proposed Plan（Markdown） |
| 用户审批 | 无 | Implement 弹窗 |
| 能否立刻 exec/edit | Default 下同 Turn 继续 | 批准后切 Default 再执行 |
| 结构化进度进 rollout 事件 | `PlanUpdate` 事件 ❌ | `PlanDelta` 事件 ❌ |
| 进模型 history | FunctionCall 参数 ✅ | `PlanItem` + 剥块后的 assistant ✅ |

---

## 5. `update_plan` vs `followup_task`（MA V2）

| 维度 | `update_plan` | `followup_task` |
|------|---------------|-----------------|
| 目的 | UI 进度黑板 | 向子 Agent **下发任务并唤醒** |
| 作用域 | 单 Thread | 跨 Thread（`AgentControl`） |
| 写入队列 | ❌ | ✅ 子 Session `input_queue` 邮箱 |
| `trigger_turn` | — | **true**（`MessageDeliveryMode::TriggerTurn`） |
| 实现 | `handlers/plan.rs` | `handlers/multi_agents_v2/followup_task.rs` → `message_tool.rs` |
| 与父子 Agent | 无感知 | `InterAgentCommunication` + `maybe_start_turn` |

```text
followup_task(target, message)
  → AgentControl::send_inter_agent_communication(trigger_turn=true)
  → 子 submission_loop → enqueue_mailbox → 子 run_turn
```

---

## 6. Multi-Agent 设计（V1 / V2）

> **架构导读（图表、notification vs 邮箱）**：[MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md)  
> 全链路时序：[FULL_LIFECYCLE_SEQUENCE.md](./FULL_LIFECYCLE_SEQUENCE.md)

### 6.1 核心原则

| 原则 | 含义 |
|------|------|
| 子 Agent = 新 Thread | 独立 `ThreadId`、Session、`run_turn` |
| 共享 `AgentControl` | 根 Session 创建 registry，子 clone |
| 无 `delegate` 工具 | 委派 = `spawn_agent` + 消息 + 可选 `wait` |
| 默认异步 | `spawn` 立即返回；关键路径才 `wait_agent` |

### 6.2 工具面对照

| | **V1**（`Feature::Collab` 默认） | **V2**（`multi_agent_v2`） |
|--|----------------------------------|----------------------------|
| 目录 | `handlers/multi_agents/` | `handlers/multi_agents_v2/` |
| 派工 | `spawn_agent`, `send_input` | `spawn_agent`, `send_message`, `followup_task` |
| 跨线程消息 | `Op::TurnInput` | `Op::InterAgentCommunication`（邮箱） |
| 等待 | `wait` | `wait_agent` |
| 风格 | 偏同步 orchestrator | 偏异步邮箱 + `trigger_turn` |

### 6.3 同步 / 异步

| 操作 | 父 `run_turn` 阻塞？ | 子完成通知 |
|------|---------------------|------------|
| `spawn_agent` | 否 | V2：`InterAgentCommunication` 进父邮箱 |
| `send_message` | 否 | `trigger_turn: false` |
| `followup_task` | 否 | `trigger_turn: true` 开子 Turn |
| `wait` / `wait_agent` | **是**（tool 挂起） | 同步返回状态文本 |

### 6.4 与 Plan 的交叉

| 组合 | 行为 |
|------|------|
| 父 Plan + 无子 Agent | 只出计划；自动 Turn / 邮箱 trigger 被拒 |
| 父 Default + 子 Agent | 常见：父协调，子执行 |
| 父 spawn planner → 子 coder | 最接近「两阶段 Plan-and-Execute」的 Codex 用法 |

### 6.5 与 `needs_follow_up`

`needs_follow_up` 是 **单 Thread `run_turn` Step 是否继续**的标志（`model_needs_follow_up || has_pending_input`），与「子 Agent 是否跑完」无关。子完成通过邮箱异步注入，可能让父后续 Step 的 `has_pending_input` 变 true。

---

## 7. 协作范式地图

Codex **没有**名为 ReAct / Plan-and-Execute 的类；范式体现在协议循环上。

| 业界范式 | Codex 对应 |
|----------|------------|
| **ReAct** | Default + `run_turn` Step 循环（采样 → tool → `needs_follow_up`） |
| **Plan-and-Execute（部分）** | Plan Mode（人门控）或 spawn + role 拆多 Thread |
| **Orchestrator-Workers** | Multi-Agent：`spawn` + `wait` / 邮箱 |
| **Human-in-the-loop** | Plan Implement 弹窗、`ExecApproval`、`request_user_input` |

**不是**这些：

| 名字 | 实际 |
|------|------|
| `ToolOrchestrator` | 单 Turn 内工具审批/沙箱管道 |
| `update_plan` | 进度 UI，非多 Agent 调度 |
| `followup_task` | 子 Agent 任务队列，非 checklist |

---

## 8. 完整示例

### 8.1 Plan Mode：先方案后执行

```text
[用户] 切 Plan Mode
[用户] 重构 auth 模块，先别改代码

[模型] <proposed_plan>
       - 读 middleware 现状
       - 设计 JWT 校验
       - 补测试
       </proposed_plan>

[UI] Proposed Plan 流式展示 → Turn 结束弹窗

[用户] Yes, implement → Default + "Implement the plan."

[模型] read / edit / test（可用 update_plan 勾进度，也可不用）
```

### 8.2 Default + `update_plan`：边做边勾

```text
[用户] Default：给三个 API 加 rate limit

[模型] update_plan: 4 步，第 1 步 in_progress
[模型] read_file(...)
[模型] update_plan: 第 1 步 completed，第 2 步 in_progress
[模型] edit_file(...)
       … 无弹窗、无模式切换
```

### 8.3 Multi-Agent：父协调子执行

```text
[父 Default]
  spawn_agent(role=coder, task="实现 foo 端点")  → 立即返回 thread_id
  … 父继续做不重叠工作 …
  wait_agent(coder)  → 阻塞至子 Turn 完成
  集成子返回的 patch
```

### 8.4 组合：Plan 批准后再委派

```text
Plan Mode 出方案 → 用户 Implement → Default 执行
  → spawn_agent(子任务 A) + spawn_agent(子任务 B)
  → followup_task 追加子任务细节（V2）
  → update_plan 在父 Thread 勾整体进度
```

---

## 9. 常见误解校正表

| 误解 | 事实 |
|------|------|
| 协作模式叫 Execute / Pair | 枚举是 `ModeKind::Default` / `Plan`；`execute`/`pair_programming` 仅为 Default 的 serde 别名 |
| `update_plan` 进度不进 history | **FunctionCall 参数**进 rollout 与模型上下文；**PlanUpdate 事件**不进 durable rollout |
| Turn 结束进度全丢 | rollout 里仍有 tool call 记录；丢的是 TUI 内存快照与瞬时事件 |
| Plan 审批用 `/apply-plan` | TUI 弹窗「Implement this plan?」；无此 slash |
| `in_progress` 唯一由 Rust 强制 | 仅 tool description 提示；Handler 不校验 |
| `plan` 数组非空由 Rust 强制 | 仅 JSON required；空数组可能通过 parse |
| Plan Mode 产出走 `turn/plan/updated` | Plan Mode 走 **`PlanDelta` / `PlanItem`**；`turn/plan/updated` 仅 **`update_plan` 工具** |
| Multi-Agent 有 `delegate` 工具 | 无；语义在 `spawn_agent` description |
| `update_plan` 会写 input_queue | 不会 |
| Plan Mode = Plan-and-Execute | 单模型 + **人门控**；非自动两阶段 executor |

---

## 10. 源码速查

| 要查的行为 | 文件 |
|------------|------|
| `update_plan` Handler | `core/src/tools/handlers/plan.rs` |
| Tool Schema | `core/src/tools/handlers/plan_spec.rs` |
| 类型定义 | `protocol/src/plan_tool.rs` |
| Plan Mode 流式 | `core/src/session/turn.rs` |
| 剥 plan 块 | `core/src/stream_events_utils.rs` |
| Plan 审批弹窗 | `tui/src/chatwidget/plan_implementation.rs` |
| TUI plan update 渲染 | `tui/src/history_cell/plans.rs` |
| Rollout 持久化策略 | `rollout/src/policy.rs` |
| MA V2 followup | `core/src/tools/handlers/multi_agents_v2/message_tool.rs` |
| Spawn / AgentControl | `core/src/agent/control.rs`, `tools/handlers/multi_agents/spawn.rs` |
| `needs_follow_up` | `core/src/session/turn.rs` |
| 协作模式枚举 | `protocol/src/config_types.rs` (`ModeKind`) |

---

## 阅读顺序建议

1. 本文 §1–§4（Plan vs `update_plan`）
2. [ARCHITECTURE_PART1.md §8.7–§8.9](./ARCHITECTURE_PART1.md)（范式 + MA 细节）
3. [FULL_LIFECYCLE_SEQUENCE.md](./FULL_LIFECYCLE_SEQUENCE.md)（时序 + OpenAI Agents SDK 对比）
4. [RUNTIME_PROMPTS.md](./RUNTIME_PROMPTS.md)（Prompt 拼装与 delegate 文案）
