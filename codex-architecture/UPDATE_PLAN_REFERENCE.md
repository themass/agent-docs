# `update_plan` 工具源码级完整详解（codex-rs · 修订版）

> **源码锚点**  
> - Handler：`codex-rs/core/src/tools/handlers/plan.rs`  
> - Tool Spec：`codex-rs/core/src/tools/handlers/plan_spec.rs`  
> - 类型定义：`codex-rs/protocol/src/plan_tool.rs`  
> - Rollout 策略：`codex-rs/rollout/src/policy.rs`  
> - TUI 渲染：`codex-rs/tui/src/history_cell/plans.rs`、`tui/src/chatwidget/turn_runtime.rs`  
>
> **关联文档**：[PLAN_AND_MULTI_AGENT.md](./PLAN_AND_MULTI_AGENT.md)（Plan Mode / MA 合一）

---

## 核心事实（先行）

1. **`update_plan` ≠ Plan Mode**。二者互斥：Plan Mode 内调用 `update_plan` 会在 Rust Handler 层**硬拦截报错**，不是 prompt 软约束。
2. **`update_plan` 是执行期进度清单工具**：只发 UI 事件 + 向模型返回 `"Plan updated"`；**不**改文件、**不**调度任务、**不** spawn 子 Agent、**不**写 `input_queue`。
3. **协作模式名是 `ModeKind::Default` / `Plan`**，不是「Execute / Pair」；`execute`、`pair_programming` 等仅为 Default 的 serde 配置别名。
4. **持久化要分两条线**：`PlanUpdate` **事件**不落 durable rollout；同次调用的 **`FunctionCall` + `FunctionCallOutput`** 会进 rollout 与后续模型上下文。

---

## 一、一句话定义

`update_plan`：**Default 协作模式下的 Checklist 进度上报工具**。

Agent 通过结构化 JSON 上报任务步骤与状态；Core 发出 `EventMsg::PlanUpdate` 供 TUI / App-Server 渲染 checklist；同时向模型返回固定成功回执 `"Plan updated"`。

- 仅在 `config.update_plan_enabled == true` 时注册进工具表。
- 仅在 **`ModeKind::Default`** 下可用（Plan Mode 拒绝）。

---

## 二、工具 JSON Schema（源码定义）

定义位置：`plan_spec.rs` → `create_update_plan_tool()`；参数类型：`protocol/src/plan_tool.rs`。

```json
{
  "name": "update_plan",
  "parameters": {
    "explanation": "string | null",
    "plan": [
      {
        "step": "string",
        "status": "pending | in_progress | completed"
      }
    ]
  }
}
```

### 参数逐项解析

| 字段 | 必填 | 说明 |
|------|------|------|
| `plan` | ✅（schema required） | 步骤数组 |
| `plan[].step` | ✅ | 步骤简短描述 |
| `plan[].status` | ✅ | `pending` / `in_progress` / `completed` |
| `explanation` | ❌ | 本次更新说明，展示在 UI「Updated Plan」顶部 |

### 关于约束的校正

- Tool **description** 写明：「同一时刻最多一个 `in_progress`」。
- **`PlanHandler` 未在 Rust 中校验**「plan 非空」或「in_progress 唯一」；违反约束仅靠模型自律。
- 畸形 JSON 在 `serde_json::from_str<UpdatePlanArgs>` 失败，返回 `RespondToModel` 错误。

---

## 三、后端完整执行链路

```text
LLM FunctionCall(update_plan)
    → ToolRouter::build_tool_call
        → PlanHandler::handle_call
            → [1] turn.mode() == Plan ? 报错返回
            → [2] parse UpdatePlanArgs
            → [3] session.send_event(EventMsg::PlanUpdate(args))
            → [4] ToolOutput → FunctionCallOutput("Plan updated")
```

### 事件命名（校正）

| 层级 | 名称 |
|------|------|
| Core 内部 | `EventMsg::PlanUpdate(UpdatePlanArgs)` |
| App-Server 对外 | `turn/plan/updated`（`TurnPlanUpdatedNotification`） |

### 源码执行步骤

**1. 协作模式前置校验（硬阻断）**

```rust
// plan.rs — 逻辑等价
if turn.mode() == ModeKind::Plan {
    return Err(FunctionCallError::RespondToModel(
        "update_plan is a TODO/checklist tool and is not allowed in Plan mode".to_string(),
    ));
}
```

**2. 解析入参** — `parse_update_plan_arguments` → `UpdatePlanArgs`

**3. 无业务副作用** — 不生成 `followup_task`、不 `spawn_agent`、不改文件、不写任何 `input_queue`

**4. 发 UI 事件**

```rust
session.send_event(turn.as_ref(), EventMsg::PlanUpdate(args)).await;
```

**5. 返回工具结果** — 固定文本 `"Plan updated"`（`PlanToolOutput`）

`PlanHandler` 实现 `is_builtin_control_tool() == true`（内置控制面工具）。

---

## 四、产出如何被使用（校正版）

### 4.1 三条消费路径

| 消费者 | 收到什么 | 用途 |
|--------|----------|------|
| **TUI transcript** | `on_plan_update` → `PlanUpdateCell` | 历史区展示「**Updated Plan**」勾选列表 |
| **TUI 终端标题** | `last_plan_progress` → `Tasks {completed}/{total}` | 可选状态栏进度（`status_surfaces.rs`） |
| **模型下一轮** | `FunctionCall`（含完整 JSON 参数）+ `FunctionCallOutput("Plan updated")` | ReAct 继续；步骤内容在 **tool call 参数**里 |
| **App-Server 客户端** | `turn/plan/updated` | IDE / 外部 UI 同步 checklist |

> **校正**：不是「侧边栏」专用面板，而是 **transcript 历史卡片 + 可选终端标题**。

### 4.2 与 Context / History 的关系（重要）

| 数据 | 是否进模型 prompt / rollout |
|------|----------------------------|
| `EventMsg::PlanUpdate` | ❌ rollout 标为 **Transient, non-durable**（`rollout/src/policy.rs`） |
| `ResponseItem::FunctionCall`（`update_plan` + arguments JSON） | ✅ `should_persist_response_item` |
| `ResponseItem::FunctionCallOutput`（`"Plan updated"`） | ✅ 同上 |

**结论**：

- ❌ 错误：「进度完全不进对话历史 / ContextManager」
- ✅ 正确：**瞬时 UI 事件**不进 durable rollout；**tool call 记录**进 rollout，模型下一轮能看到自己上报过的 JSON 参数。

---

## 五、存储生命周期（精确表述）

| 数据 | 生命周期 |
|------|----------|
| `PlanUpdate` EQ 事件 | 当前连接瞬时推送；**不**作为 durable rollout 事件重放 |
| `FunctionCall` / `FunctionCallOutput` | 写入 thread **rollout.jsonl**（随 thread 持久化） |
| TUI `last_plan_progress` | `ChatWidget.transcript` 内存；新 Turn `reset_turn_flags` 不重置此项，由下次 `update_plan` 覆盖 |
| MemoryStore | **不**因 `update_plan` 单独写入 |

`update_plan` 的 **UI 快照**是辅助展示；**rollout 里的 FunctionCall** 才是会话可恢复的结构化记录之一。

---

## 六、`update_plan` vs Plan Mode

| 项目 | `update_plan`（工具） | Plan Mode（`ModeKind::Plan`） |
|------|----------------------|------------------------------|
| 本质 | Default 下执行期 **TODO checklist** | 协作模式：先调研、产出 **方案** |
| 源码位置 | `handlers/plan.rs` | `ModeKind` + `collaboration-mode-templates/templates/plan.md` 等 |
| 模型产出方式 | `FunctionCall(update_plan, JSON)` | 自然语言 `<proposed_plan>...</proposed_plan>`（流式解析） |
| Core 事件 | `PlanUpdate` → App-Server `turn/plan/updated` | `PlanDelta`（流式）+ `TurnItem::Plan` |
| UI 展示 | **Updated Plan**（勾选列表） | **Proposed Plan**（Markdown） |
| 可用模式 | **Default**（`update_plan_enabled`） | Plan；**禁止** `update_plan` |
| 用户审批 | 无；同 Turn 内继续执行 | Turn 结束弹窗 **「Implement this plan?」**（非 `/apply-plan`） |
| 审批后 | — | 切 Default + `"Implement the plan."` 或清上下文实现 |
| 进 rollout（事件） | `PlanUpdate` ❌ | `PlanDelta` ❌ |
| 进 rollout（内容） | FunctionCall 参数 ✅ | `PlanItem` ✅ |
| 自动开 Turn（邮箱/子 Agent） | Default 下正常 | `TurnStartKind::Automatic` → `PlanMode` 拒绝 |

---

## 七、`update_plan` vs `followup_task`（MA V2）

| 项目 | `update_plan` | `followup_task` |
|------|---------------|-----------------|
| 角色 | 单 Thread 进度 UI | 跨 Agent **任务下发 + 唤醒** |
| 动作 | 仅 `send_event(PlanUpdate)` | `InterAgentCommunication` + `trigger_turn=true` |
| 队列 | 不写 `input_queue` | 写入**子 Session** 邮箱 → `maybe_start_turn` |
| 多 Agent | 无感知 | `AgentControl::send_inter_agent_communication` |
| 实现 | `handlers/plan.rs` | `handlers/multi_agents_v2/followup_task.rs` → `message_tool.rs` |

```text
followup_task(target, message)
  → AgentControl → 子 Session submission_loop
  → enqueue_mailbox_communication
  → trigger_turn=true → 子 run_turn
```

---

## 八、完整示例

### 示例 A — Default + `update_plan`（边做边勾）

```text
[用户] Default：给 /api/foo、/bar、/baz 加 rate limit

[模型] update_plan({
  "explanation": "拆成四步",
  "plan": [
    { "step": "读 middleware", "status": "in_progress" },
    { "step": "改 foo", "status": "pending" },
    { "step": "改 bar/baz", "status": "pending" },
    { "step": "跑测试", "status": "pending" }
  ]
})
[UI] Updated Plan 勾选列表；终端标题 Tasks 0/4
[模型] read_file(...) → edit_file(...) → update_plan(第1步 completed, 第2步 in_progress) …
[history] 每次 FunctionCall 参数写入 rollout；模型下一轮可见
```

### 示例 B — Plan Mode（与 update_plan 互斥）

```text
[用户] 切 Plan Mode：重构 auth，先别改代码

[模型] <proposed_plan>
- 读 middleware
- 设计 JWT 校验
- 补测试
</proposed_plan>

[UI] Proposed Plan 流式 Markdown
[Turn 结束] 弹窗 Implement this plan?
[用户] Yes → Default + "Implement the plan."
[模型] 开始 read/edit（此时可用 update_plan 勾进度）
```

若在 Plan Mode 误调 `update_plan` → Handler 立即返回错误字符串，模型需改用 `<proposed_plan>` 或等用户切 Default。

---

## 九、源码速查

| 行为 | 文件 |
|------|------|
| Handler | `core/src/tools/handlers/plan.rs` |
| Schema | `core/src/tools/handlers/plan_spec.rs` |
| 类型 | `protocol/src/plan_tool.rs` |
| 工具注册门控 | `core/src/tools/spec_plan.rs`（`update_plan_enabled`） |
| Rollout 持久化 | `rollout/src/policy.rs` |
| TUI 渲染 | `tui/src/history_cell/plans.rs` |
| Plan Mode 审批 | `tui/src/chatwidget/plan_implementation.rs` |
| 集成测试 | `core/tests/suite/tool_harness.rs`（`update_plan_tool_*`） |

---

## 延伸阅读

- [PLAN_AND_MULTI_AGENT.md](./PLAN_AND_MULTI_AGENT.md) — Plan / MA / 范式地图 / 误解表
- [ARCHITECTURE_PART1.md §8–§9](./ARCHITECTURE_PART1.md) — 架构分章
- [FULL_LIFECYCLE_SEQUENCE.md](./FULL_LIFECYCLE_SEQUENCE.md) — 主子 Agent 时序
