# Codex 全链路端到端时序（压缩 · 子 Agent · 记忆 · 继续提问）

> **版本**: 1.0（2026-09-03）  
> **源码**: `codex/codex-rs/`  
> **关联**: [ARCHITECTURE_PART1 §8](./ARCHITECTURE_PART1.md#第8章多-agent)、[RUNTIME_PROMPTS.md](./RUNTIME_PROMPTS.md)、[memory.md](./memory.md)

---

## 0. 当前生效的多 Agent 版本

| 配置 | Feature | 默认 | 生效版本 |
|------|---------|------|----------|
| 开箱默认 | `multi_agent`（`Feature::Collab`） | **enabled** | **MA V1** |
| 显式升级 | `multi_agent_v2`（`Feature::MultiAgentV2`） | disabled | **MA V2**（覆盖 V1） |
| 关闭 | `agents.enabled = false` | — | `MultiAgentVersion::Disabled` |

解析链（`config/mod.rs`）：

```text
multi_agent_version_for_model()
  ← multi_agent_version_override()   // V2 feature 开 → V2；agents 关 → Disabled
  ← model catalog capability
  ← multi_agent_version_from_features()  // Collab 开 → V1，否则 Disabled
```

**结论（2026-09 源码默认）**：未开 `multi_agent_v2` 时，**生产默认是 MA V1**（`multi_agent.spawn_agent` / `send_input` / `wait`）。开启 `multi_agent_v2` 后切到 V2（`spawn_agent` / `send_message` / `followup_task` / `wait_agent` + 邮箱）。

下文时序图在关键分叉处标注 **V1 / V2**。

---

## 1. 全景时序（一次用户会话的完整生命）

覆盖：冷启动 → 多轮对话 → 上下文压缩 → 委派子 Agent → 异步/同步汇合 → 用户继续提问 → Session 空闲后 Phase1/2 记忆。

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户 / 客户端
    participant SQ as submission_loop
    participant PR as 父 Session / run_turn
    participant PM as 父模型
    participant TO as Tool 层
    participant AC as AgentControl
    participant CS as 子 Session
    participant CR as 子 run_turn
    participant PJ as 父 rollout.jsonl
    participant CJ as 子 rollout.jsonl
    participant MEM as memories Phase1/2

  rect rgb(240,248,255)
    Note over U,PJ: 阶段 A — 冷启动与首轮 Turn
    U->>SQ: Op::TurnInput（用户消息）
    SQ->>PR: run_turn 开始
    PR->>PR: build_initial_context_with_world_state
    PR->>PJ: 写入 developer/user 初始片段 + SessionMeta
    PR->>PM: Step 1 sampling（Prompt = instructions + history + tools）
    PM-->>PR: assistant + 可能 tool_calls
    loop 父 Step 循环
        PR->>TO: 执行 tools
        TO->>PJ: FunctionCall / FunctionCallOutput
        PR->>PM: 下一 Step sampling
    end
    PR->>PJ: TurnComplete 等 EventMsg
    PR-->>U: EventMsg 流（UI 投影）
  end

  rect rgb(255,248,240)
    Note over PR,PJ: 阶段 B — 上下文压缩（Pre-turn 示例）
    U->>SQ: Op::TurnInput（继续提问，token 已超限）
    SQ->>PR: run_turn
    PR->>PR: context_window_token_status → limit reached
    PR->>PR: run_auto_compact（local / remote / token-budget 分支）
    PR->>PM: 压缩专用 sampling（SUMMARIZATION_PROMPT + 全历史）
    PM-->>PR: 摘要文本
    PR->>PR: replace_compacted_history
    PR->>PJ: append RolloutItem::Compacted（append-only）
    Note over PJ: 内存 history 变为 summary + 保留用户消息
    PR->>PM: 继续本 Turn 或下轮重装 initial context
  end

  rect rgb(240,255,240)
    Note over PM,CJ: 阶段 C — 委派子 Agent（默认不阻塞父）
    PM->>PR: FunctionCall(spawn_agent)
    PR->>TO: SpawnAgentHandler
    TO->>AC: spawn_agent_with_metadata + send_input(子首条消息)
    AC->>CS: 新建 Thread（SessionSource::SubAgent）
    opt fork_context
        AC->>CJ: InitialHistory::Forked（复制父 rollout 前缀）
    end
    AC->>CR: 子 submission_loop → run_turn
  TO->>PJ: spawn FunctionCallOutput（agent_id only）
  TO-->>PR: 立即返回（不等子完成）
  PR->>PM: 父下一 Step（可并行其它 tool）

    par 子后台
        CR->>CJ: 子 Step 循环 + tool 记录
        CR->>CS: TurnComplete
    and 父继续
        PM->>PR: 其它 tool / 推理
    end

    alt V1 完成回调
        AC->>PR: inject SubagentNotification（无新 Turn）
        PR->>PJ: user 片段 subagent_notification（Phase1 会过滤）
    else V2 完成回调
        CS->>AC: forward_child_completion_to_parent
        AC->>PR: InterAgentCommunication（trigger_turn=false）→ 父邮箱
        PR->>PJ: 可选持久化 IAC 行
    end

    opt 父显式同步
        PM->>PR: FunctionCall(wait / wait_agent)
        PR->>TO: subscribe_status 阻塞至终态
        TO->>PJ: wait tool output（含 Completed 摘要）
    end
  end

  rect rgb(248,240,255)
    Note over U,PJ: 阶段 D — 用户继续提问（同 Session）
    U->>SQ: Op::TurnInput
    SQ->>PR: 新 Turn（或 steer 当前 Turn）
    PR->>PR: WorldState diff + 可能 drain 邮箱邮件
    PR->>PM: sampling（history 含 spawn/wait/notification）
    PM-->>U: 集成子结果后继续回答
    PR->>PJ: 追加新 Turn 记录
  end

  rect rgb(255,255,240)
    Note over PR,MEM: 阶段 E — 记忆流水线（根 Session 旁路，不阻塞 run_turn）
    U->>SQ: 又一次 TurnInput（触发 startup 检查）
    SQ->>MEM: start_memories_startup_task（仅根 Session）
    Note over CS: 子 Session is_non_root_agent → 跳过
    MEM->>MEM: Phase1 claim 其它 idle 的 enabled thread
    MEM->>PJ: load_rollout_items → 过滤 → extract_model
    MEM->>MEM: stage1_outputs + rollout_summaries/*.md
    MEM->>MEM: Phase2 全局锁 → Consolidation Agent
    MEM->>MEM: 重写 MEMORY.md + memory_summary.md
  end
```

---

## 2. 父调子：逐步拆解

### 2.1 `spawn_agent`（父视角的一次 tool）

| 步 | 动作 | 父是否阻塞 |
|----|------|-----------|
| 1 | 模型 `FunctionCall(spawn_agent)` | — |
| 2 | `SpawnAgentHandler` → `AgentControl::spawn_agent_internal` | — |
| 3 | `ThreadManager` 创建子 Thread + 独立 `RolloutRecorder` | — |
| 4 | `send_input` 投递子首条 `UserInput` → 子 `run_turn` | — |
| 5 | 返回 `FunctionCallOutput { agent_id, nickname }` | **否** |
| 6 | 父 `run_turn` Step 循环继续 | — |

### 2.2 子 Agent 内部

与父完全相同的 `submission_loop` → `run_turn` → Step sampling → tools，但：

- `SessionSource::SubAgent(ThreadSpawn { parent_thread_id, depth, agent_path, … })`
- 不写父 `ContextManager`
- 独立 `rollout.jsonl`（`thread_source: Subagent`）

### 2.3 结果回父的三条通道

| 通道 | 时机 | 父模型如何看到 |
|------|------|----------------|
| spawn output | spawn 完成瞬间 | 仅 `agent_id` |
| 异步通知 | 子 `TurnComplete` | V1: `<subagent_notification>`；V2: 邮箱 `InterAgentCommunication` |
| `wait` / `wait_agent` | 父显式调用 | tool output 含 `AgentStatus::Completed(Some(msg))` |

### 2.4 父继续 Step 推理

```text
run_turn inner loop:
  sampling → tools → record outputs → needs_follow_up?
  = model 还要 tool OR TurnState.pending_input 非空 OR（邮箱 drain 后）有待处理邮件
```

子完成通知若在父 Turn 进行中到达：

- V1 notification → `inject_fragment_without_turn` → 下轮 `for_prompt` 可见 → 详见 [MULTI_AGENT_ARCHITECTURE.md §4](./MULTI_AGENT_ARCHITECTURE.md#4-子--父完成后怎么通知核心)
- V2 邮箱 + `trigger_turn: false` → 等父 Turn 结束或 `needs_follow_up` drain 邮箱

---

## 3. JSONL 与记忆提炼

### 3.1 双文件模型（不合并）

```text
~/.codex/sessions/.../rollout_<parent_id>.jsonl   ← 父
~/.codex/sessions/.../rollout_<child_id>.jsonl    ← 子（独立）
```

压缩时父文件 **append** `RolloutItem::Compacted`；子文件自有 Compacted（若子也超限）。

### 3.2 记忆 Phase1 读谁？

| 来源 | 是否启动 pipeline | 是否典型原料 |
|------|------------------|-------------|
| 根 Session | ✅ `start_memories_startup_task` | ✅ 主原料 |
| 子 Session | ❌ `is_non_root_agent()` 跳过 | ❌ 非设计目标 |
| 父 jsonl 内 `<subagent_notification>` | — | ❌ `serialize_filtered` 过滤 |
| 父 jsonl 内 `wait_agent` output | — | ✅ 可进 Phase1（父视角摘要） |

Phase1 还可能 claim **其它 idle 的根 thread** 的 rollout（`claim_stage1_jobs_for_startup`），与当前是否在跑子 Agent 无关。

### 3.3 Phase2

批量读 `stage1_outputs` → Git 工作区 → Consolidation Agent 重写 `MEMORY.md` / `memory_summary.md`。与子 Agent 无直接调用关系。

---

## 4. 与 OpenAI Agents Python SDK 时序对比

对比对象：`openai-agents-python/`（Handoff 模型），**不是** OpenHands TaskToolSet。

| 维度 | Codex（MA V1 默认） | OpenAI Agents Python SDK |
|------|---------------------|--------------------------|
| **多 Agent 机制** | 工具 `spawn_agent` + 可选 `wait` | Agent 定义上的 **`handoffs[]`**（特殊 tool） |
| **运行时实体** | 独立 Thread + Session + rollout | 同 `Runner` 内 **`RunState._current_agent` 切换** |
| **委派时父是否阻塞** | **否**（spawn 立即返回） | Handoff 在**同一 turn loop** 内同步切换 agent |
| **子运行时** | 子 Session 独立 `run_turn` | 子 Agent 继续同一 `RunLoop`，换 `current_agent` |
| **结果回传** | tool output / notification / wait | Handoff 后子 agent 输出进入**同一 session 输入列表** |
| **上下文** | 父子 `ContextManager` 隔离；fork 可选 | 默认**共享** `Session` 输入历史（可配置过滤） |
| **控制平面** | `AgentControl`（spawn/消息/状态） | 无对等组件；`Runner` + `Handoff` 回调 |
| **持久化** | 双 rollout.jsonl | `Session` persistence / `RunItem` 列表 |
| **记忆** | 旁路 Phase1/2 + `MEMORY.md` | SDK Session persistence；无 Codex 式 MEMORY 管道 |

OpenAI SDK Handoff 时序（简化，见 `OPENAI_AGENTS_SDK_ARCHITECTURE_PART1.md` §3）：

```mermaid
sequenceDiagram
    participant R as Runner / RunLoop
    participant A as Triage Agent
    participant M as Model
    participant B as Delegate Agent

    R->>A: turn start
    A->>M: sampling（含 handoff tools）
    M-->>R: transfer_to_delegate handoff call
    R->>R: NextStepHandoff → 切换 _current_agent
    R->>B: 同一 RunLoop 继续
    B->>M: sampling
    M-->>R: 子任务完成
    R->>R: NextStepRunAgain 或结束
    Note over R: 全程同一 Session 输入列表，无独立 rollout 文件
```

**核心差异一句话**：OpenAI SDK Handoff 是**同进程、同 Session、同步切 agent**；Codex 是**跨 Thread、默认异步 spawn、可选 wait 同步**。

---

## 5. 源码索引

| 主题 | 文件 |
|------|------|
| MA 版本解析 | `core/src/config/mod.rs` → `multi_agent_version_from_features` |
| Feature 默认 | `features/src/lib.rs` → `Collab` default true, `MultiAgentV2` default false |
| spawn | `core/src/tools/handlers/multi_agents/spawn.rs`, `agent/control/spawn.rs` |
| wait | `core/src/tools/handlers/multi_agents/wait.rs` |
| V1 完成通知 | `core/src/agent/control.rs` → `maybe_start_completion_watcher` |
| V2 完成转发 | `core/src/session/mod.rs` → `forward_child_completion_to_parent` |
| 压缩 | `core/src/compact.rs`, `session/turn.rs` → `run_auto_compact` |
| 记忆入口 | `memories/write/src/start.rs` |
| OpenAI SDK handoff | `openai-agents-python/src/agents/run_internal/run_loop.py` |

---

## 6. 阅读顺序

1. 本文 §0–§2 — 版本与父调子  
2. 本文 §3 — JSONL + 记忆  
3. [RUNTIME_PROMPTS.md](./RUNTIME_PROMPTS.md) — Prompt 拼装  
4. [memory.md](./memory.md) — `~/.codex/memories/` 产物  
5. [openai-agents-python/docs/OPENAI_AGENTS_SDK_ARCHITECTURE_PART1.md](../../openai-agents-python/docs/OPENAI_AGENTS_SDK_ARCHITECTURE_PART1.md) — Handoff 对照
