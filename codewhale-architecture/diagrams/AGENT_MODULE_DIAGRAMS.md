# Codewhale — Agent 模块级图集（细粒度）

> 源码根：`Codewhale/crates/` · 与 [DIAGRAM_ATLAS.md](./DIAGRAM_ATLAS.md)（全局图）配套。
> **每个重要 Agent 相关模块**至少 1 张图；复杂模块含流程 + 时序/类图。

## 模块索引

| ID | 模块 | 源码锚点 | 图类型 |
|----|------|----------|--------|
| CW-01 | Engine 主循环与 Op 分派 | `engine.rs` | flowchart |
| CW-02 | run_turn 与 TurnContext | `turn_loop.rs` | sequence |
| CW-03 | process_stream 流解析 | `turn_loop.rs` | flowchart |
| CW-04 | plan_tool_calls 权限门 | `turn_loop.rs` | flowchart |
| CW-05 | prepare_primary_turn_request | `core/request.rs` | flowchart |
| CW-06 | Thread / Journal / branch | `core/session.rs` | classDiagram |
| CW-07 | Session 热状态 | `tui/core/session.rs` | classDiagram |
| CW-08 | TurnAuthority 与 Mode | `authority.rs` | flowchart |
| CW-09 | ExecPolicy 规则引擎 | `execpolicy/` | sequence |
| CW-10 | tool_execution 并行批次 | `tool_execution.rs` | flowchart |
| CW-11 | 工具体系与 deferred schema | `tools/` | flowchart |
| CW-12 | MCP 集成 | `mcp.rs` | sequence |
| CW-13 | Compaction | `compaction.rs` | flowchart |
| CW-14 | memory crate | `memory/` | flowchart |
| CW-15 | state / SQLite | `state/` | erDiagram |
| CW-16 | ModelClient 多 Provider | `tui/client/` | flowchart |
| CW-17 | goal_loop / GoalBudget | `runtime/goal_loop.rs` | sequence |
| CW-18 | Fleet / SubAgent | `fleet/` | flowchart |
| CW-19 | Lane 工作树 | `lane/` | flowchart |
| CW-20 | workflow | `workflow/` | flowchart |
| CW-21 | cli / exec 无 UI | `cli/` | sequence |
| CW-22 | app-server | `app-server/` | flowchart |
| CW-23 | hooks / telemetry | `hooks/ telemetry/` | flowchart |
| CW-24 | config / secrets | `config/ secrets/` | flowchart |
| CW-25 | protocol 消息类型 | `protocol/` | classDiagram |
| CW-26 | models 与路由 | `models/` | flowchart |
| CW-27 | command-contract | `command-contract/` | flowchart |
| CW-28 | Steer 与 pending_steers | `turn_loop.rs` | sequence |
| CW-29 | checkpoint / resume | `state/ exec` | sequence |

---

## CW-01 Engine 主循环与 Op 分派

**源码**：`engine.rs`

```mermaid
flowchart TD
    RUN[Engine::run] --> SEL{rx_op.recv}
    SEL -->|UserMessage| RT[run_turn]
    SEL -->|Cancel| CAN[取消当前 Turn]
    SEL -->|Compact| CMP[触发压缩 Op]
    SEL -->|SetMode| MOD[更新 AgentMode]
    RT --> EVT[tx_event 推送]
    CAN --> EVT
    CMP --> EVT
```

**读图**：Engine 单 Tokio 任务；所有外部输入经 Op 队列，禁止旁路调用 run_turn。

---

## CW-02 run_turn 与 TurnContext

**源码**：`turn_loop.rs`

```mermaid
sequenceDiagram
    participant RT as run_turn
    participant TC as TurnContext
    participant PR as prepare_request
    participant ST as Step 循环
    RT->>TC: 构造 authority + budget
    loop until end_turn or limit
        RT->>PR: PrimaryTurnRequest
        PR->>ST: stream + tools
        ST-->>RT: tool_use → 执行 → 下一 Step
    end
```

**读图**：TurnContext 每 Turn 一次；Step 可多次。

---

## CW-03 process_stream 流解析

**源码**：`turn_loop.rs`

```mermaid
flowchart TD
    S[Stream 入口] --> SEL[tokio::select]
    SEL --> EV[StreamEvent 分派]
    EV --> T[TextDelta]
    EV --> TU[ToolUse JSON 累积]
    EV --> MS[MessageStop + usage]
    MS --> RET{resume?}
    RET -->|StreamRetry| S
    RET -->|done| OUT[StreamOutcome]
```

**读图**：多 ToolUse 用 block_index 映射；suspend 检测用 mono vs wall clock。

---

## CW-04 plan_tool_calls 权限门

**源码**：`turn_loop.rs`

```mermaid
flowchart TD
    TU[ToolUse 列表] --> RP[resolve_tool_permission]
    RP --> TA[TurnAuthority]
    TA --> EP[ExecPolicy per command]
    EP --> ASK{需审批?}
    ASK -->|是| UI[Approval Event]
    ASK -->|否| EX[execute_planned_tools]
```

**读图**：TurnAuthority 会话级；ExecPolicy 命令级。

---

## CW-05 prepare_primary_turn_request

**源码**：`core/request.rs`

```mermaid
flowchart LR
    MSG[messages 快照] --> FR[fragments 组装]
    SYS[BASE_PROMPT 稳定前缀] --> FR
    TOOLS[tool catalog + deferred] --> FR
    IMG[图像省略/注入] --> FR
    FR --> OUT[Provider Request]
```

**读图**：volatile facts 用 user message 追加，不改 system 前缀（KV cache）。

---

## CW-06 Thread / Journal / branch

**源码**：`core/session.rs`

```mermaid
classDiagram
    class Thread {
        +thread_id
        +leaf_id
        +journal Journal
    }
    class Journal {
        +append
        +branch_to
    }
    class JournalEntry {
        +parent_id
        +payload
    }
    Thread --> Journal
    Journal --> JournalEntry
```

**读图**：分支只移动 leaf_id；历史 append-only。

---

## CW-07 Session 热状态

**源码**：`tui/core/session.rs`

```mermaid
classDiagram
    class Session {
        +messages_revision
        +working_set WorkingSet
        +tool_activation_cache
    }
    class WorkingSet {
        +touched_paths
    }
    Session --> WorkingSet
```

**读图**：Session 不落盘；Thread 落 SQLite。

---

## CW-08 TurnAuthority 与 Mode

**源码**：`authority.rs`

```mermaid
flowchart TD
    MODE[AgentMode] --> TA[TurnAuthority]
    PROV[Provenance] --> TA
    TA --> POL[approval_policy]
    POL --> TOOL[per-tool 决策输入]
```

**读图**：子代理/checkpoint 来源可 provenance narrowing。

---

## CW-09 ExecPolicy 规则引擎

**源码**：`execpolicy/`

```mermaid
sequenceDiagram
    participant PL as plan_tool_calls
    participant EP as execpolicy
    participant R as RuleSet
    PL->>EP: ParsedCommand
    EP->>R: match prefix/glob
    R-->>EP: Allow/Deny/Ask
    EP-->>PL: Decision
```

**读图**：独立 crate，无 TUI 依赖，worker 可复用。

---

## CW-10 tool_execution 并行批次

**源码**：`tool_execution.rs`

```mermaid
flowchart TD
    BATCH[planned tools] --> PAR[并行批次]
    PAR --> G1[OperationSpanGuard]
    G1 --> HB[ToolHeartbeatGuard 长任务]
    HB --> RES[stdout/stderr]
    RES --> MSG[tool_result 消息]
```

**读图**：LSP hooks 在特定工具前后触发。

---

## CW-11 工具体系与 deferred schema

**源码**：`tools/`

```mermaid
flowchart LR
    CAT[ToolCatalog] --> DEF[deferred 工具]
    DEF --> CACHE[ToolActivationCache]
    CACHE --> ACT[激活后完整 schema 进请求]
    BUILTIN[内置 bash/read/edit] --> CAT
```

**读图**：降低每轮 token：未激活工具仅短描述。

---

## CW-12 MCP 集成

**源码**：`mcp.rs`

```mermaid
sequenceDiagram
    participant E as Engine
    participant M as MCP manager
    participant S as MCP Server
    E->>M: list_tools / call
    M->>S: JSON-RPC
    S-->>M: result
    M-->>E: 与内置工具同路径 plan/execute
```

**读图**：环境变量占位符 expand_env_placeholders。

---

## CW-13 Compaction

**源码**：`compaction.rs`

```mermaid
flowchart TD
    TRIG[token 阈值 / Op] --> SAFE[compact_messages_safe]
    SAFE --> SUM[摘要 LLM]
    SUM --> ATOM[原子 rename journal]
    ATOM --> PREFIX[冻结 system+tools 前缀]
```

**读图**：压缩后 messages_revision 递增。

---

## CW-14 memory crate

**源码**：`memory/`

```mermaid
flowchart LR
    NATIVE[NativeMemory 工具] --> STORE[记忆条目]
    STORE --> INJ[注入 turn 上下文]
    INJ --> RT[run_turn]
```

**读图**：与对话 compaction 不同域。

---

## CW-15 state / SQLite

**源码**：`state/`

```mermaid
erDiagram
    THREADS ||--o{ MESSAGES : stores
    THREADS {
        string id PK
    }
    CHECKPOINTS }o--|| THREADS : links
```

**读图**：Schema 迁移在 state crate。

---

## CW-16 ModelClient 多 Provider

**源码**：`tui/client/`

```mermaid
flowchart LR
    TRAIT[ModelClient] --> A[Anthropic]
    TRAIT --> O[OpenAI compat]
    TRAIT --> D[DeepSeek/Ollama]
    TRAIT --> U[Usage 合并]
```

**读图**：SSE/chunked 解析为统一 StreamEvent。

---

## CW-17 goal_loop / GoalBudget

**源码**：`runtime/goal_loop.rs`

```mermaid
sequenceDiagram
    participant GL as goal_loop
    participant GB as GoalBudget
    participant RT as run_turn
    GL->>GB: 检查 token/time/次数
    GB-->>GL: continue?
    GL->>RT: goal continuation turn
```

**读图**：持久目标跨多个 Turn。

---

## CW-18 Fleet / SubAgent

**源码**：`fleet/`

```mermaid
flowchart TB
    MAIN[主 Engine] --> FM[FleetManager]
    FM --> LED[FleetLedger lease]
    FM --> EXEC[codewhale exec worker]
    EXEC --> SUB[子 Thread/Session 隔离]
```

**读图**：Fleet 管资格；Runtime 管执行。

---

## CW-19 Lane 工作树

**源码**：`lane/`

```mermaid
flowchart LR
    LANE[Lane 身份] --> WS[隔离 workspace]
    WS --> RT[run_turn 在子树]
```

**读图**：与 Fleet 编排配合。

---

## CW-20 workflow

**源码**：`workflow/`

```mermaid
flowchart TD
    WF[workflow 定义] --> STEP[步骤节点]
    STEP --> ENG[Engine 驱动 tool/LLM]
    ENG --> WF
```

**读图**：高层任务编排，底层仍 run_turn。

---

## CW-21 cli / exec 无 UI

**源码**：`cli/`

```mermaid
sequenceDiagram
    participant EX as codewhale exec
    participant E as Engine
    participant OUT as stream-json
    EX->>E: 同 TUI Engine
    E-->>OUT: Event 序列
    OUT-->>EX: resume checkpoint
```

**读图**：与 TUI 共享 turn_loop。

---

## CW-22 app-server

**源码**：`app-server/`

```mermaid
flowchart LR
    HTTP[HTTP/daemon] --> PROXY[chat-completions 代理]
    PROXY --> ENG[Engine 或转发]
```

**读图**：可选 headless 接入。

---

## CW-23 hooks / telemetry

**源码**：`hooks/ telemetry/`

```mermaid
flowchart LR
    RT[run_turn] --> HK[hooks 埋点]
    HK --> TEL[telemetry 导出]
```

**读图**：可观测性不进入模型上下文。

---

## CW-24 config / secrets

**源码**：`config/ secrets/`

```mermaid
flowchart TD
    CFG[加载配置] --> FAIL[错误即 panic/明确 error]
    SEC[secrets] --> MC[ModelClient 凭证]
```

**读图**：快速失败契约。

---

## CW-25 protocol 消息类型

**源码**：`protocol/`

```mermaid
classDiagram
    class Op
    class Event
    class ToolSpec
    Op <|-- UserMessage
    Event <|-- TextDelta
```

**读图**：跨 crate 共享类型；减少循环依赖。

---

## CW-26 models 与路由

**源码**：`models/`

```mermaid
flowchart LR
    CFG[config model id] --> RES[resolve provider]
    RES --> MC[ModelClient 实例]
```

**读图**：多 provider 配置入口。

---

## CW-27 command-contract

**源码**：`command-contract/`

```mermaid
flowchart TD
    TOOL[bash 工具] --> PARSE[contract 解析]
    PARSE --> EP[execpolicy 输入]
```

**读图**：结构化命令表示。

---

## CW-28 Steer 与 pending_steers

**源码**：`turn_loop.rs`

```mermaid
sequenceDiagram
    participant U as 用户
    participant PS as process_stream
    participant RT as run_turn
    U->>PS: mid-stream steer
    PS->>PS: pending_steers 缓冲
    PS-->>RT: Turn 边界合并入 messages
```

**读图**：steer 在 Step 边界提交，不撕裂 tool JSON。

---

## CW-29 checkpoint / resume

**源码**：`state/ exec`

```mermaid
sequenceDiagram
    participant EX as exec
    participant ST as state
    participant E as Engine
    EX->>ST: 读 checkpoint
    ST->>E: resume Op
    E-->>EX: 续跑 stream-json
```

**读图**：headless 恢复路径。

---


# 附录 A — Crate 依赖与 Agent 数据流

```mermaid
flowchart TB
    subgraph UI[tui/cli]
        ENG[Engine]
    end
    subgraph Core[core/protocol]
        REQ[request/session]
    end
    subgraph Exec[execpolicy/tools/mcp]
        TE[tool_execution]
    end
    subgraph Data[state/memory]
        SQL[SQLite]
    end
    ENG --> REQ
    ENG --> TE
    ENG --> SQL
    TE --> execpolicy
```

```mermaid
sequenceDiagram
    participant UI as TUI
    participant E as Engine
    participant J as Journal
    participant L as LLM
    participant T as Tools
    UI->>E: Op
    E->>J: append user
    E->>L: Step
    L-->>E: tool_use
    E->>T: execute
    T-->>E: result
    E->>J: append tool
    E-->>UI: Event
```

**读图**：左为编译期分层；右为单 Step 消息落盘顺序。
