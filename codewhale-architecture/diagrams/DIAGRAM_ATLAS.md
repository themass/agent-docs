# Codewhale 架构图集（全局）

> 与 [ARCHITECTURE.md](../ARCHITECTURE.md) 配套。**每个 Agent 相关模块的细粒度图**见 **[AGENT_MODULE_DIAGRAMS.md](./AGENT_MODULE_DIAGRAMS.md)**（CW-01…CW-29 + 附录）。  
> 本文件：**全局** 架构图、类图、实体图、流程图、时序图。  
> 图源与 `Codewhale/crates/` 源码一致；图下附简短读图说明。

---

## 图目录

| 编号 | 类型 | 标题 |
|------|------|------|
| G1 | architecture | 五层运行时总览 |
| G2 | sequence | 端到端 Turn（用户输入 → 工具 → 回写） |
| G3 | classDiagram | 核心运行时类 |
| G4 | erDiagram | Thread / Journal / 持久化实体 |
| G5 | flowchart | Op / Event 双通道 |
| M1 | sequence | `run_turn` 内层 Step 循环 |
| M2 | flowchart | `process_stream` 流事件分派 |
| M3 | flowchart | `plan_tool_calls` → 执行管道 |
| M4 | sequence | ExecPolicy 审批与沙箱 |
| M5 | flowchart | Compaction 触发与落盘 |
| M6 | sequence | Fleet 任务投递 |
| M7 | flowchart | MCP 工具注册与调用 |

---

## G1 五层运行时总览

```mermaid
flowchart TB
    subgraph Access["接入层"]
        CLI[cli]
        TUI[tui App]
        Exec[exec stream-json]
    end
    subgraph Orch["编排层 tui/core"]
        Engine[Engine]
        RT[run_turn / turn_loop]
        Auth[TurnAuthority]
    end
    subgraph Model["模型层"]
        Prep[prepare_primary_turn_request]
        MC[ModelClient]
    end
    subgraph Tools["工具层"]
        TE[tool_execution]
        EP[execpolicy]
        MCP[mcp + tools catalog]
    end
    subgraph Persist["持久化"]
        ST[state SQLite]
        JN[Journal JSONL]
    end
    CLI --> TUI
    TUI --> Engine
    Exec --> Engine
    Engine --> RT
    RT --> Auth
    RT --> Prep --> MC
    RT --> TE
    TE --> EP
    TE --> MCP
    Engine --> ST
    Engine --> JN
```

**读图**：所有用户可见行为最终汇入 `Engine`；**唯一**内层循环在 `turn_loop.rs` 的 `run_turn`，其它 crate 不实现第二套 loop。

---

## G2 端到端 Turn 时序

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户/TUI
    participant E as Engine
    participant RT as run_turn
    participant PR as prepare_request
    participant LLM as ModelClient
    participant PS as process_stream
    participant PL as plan_tool_calls
    participant TX as tool_execution
    participant ST as state/Journal

    U->>E: Op::UserMessage / Steer
    E->>RT: 进入当前 Turn
    RT->>PR: 组装 messages + tools
    PR->>LLM: send(stream)
    loop 流式块
        LLM-->>PS: StreamEvent
        PS-->>U: Event::TextDelta / Thinking
    end
    PS-->>RT: StreamOutcome + tool_uses
    alt stop_reason = tool_use
        RT->>PL: 解析 ToolUse
        PL->>TX: execute_planned_tools
        TX-->>RT: tool results
        RT->>PR: 追加 tool_result 消息
        RT->>LLM: 下一轮 Step
    else end_turn
        RT->>ST: append / checkpoint
        RT-->>E: TurnComplete
        E-->>U: Event::TurnEnd
    end
```

**读图**：一个 Turn 可含**多个 Step**（每次 `tool_use` 后递归请求模型）；`TurnComplete` 前所有进入 API 的内容须可自 Journal 重建。

---

## G3 核心运行时类图

```mermaid
classDiagram
    class Engine {
        +rx_op: mpsc::Receiver~Op~
        +tx_event: mpsc::Sender~Event~
        +session: Session
        +run() loop
    }
    class Session {
        +session_id
        +thread: Thread
        +working_set
        +tool_activation_cache
    }
    class Thread {
        +thread_id
        +leaf_id
        +journal: Journal
        +workspace
    }
    class Journal {
        +append(entry)
        +branch_to(leaf)
    }
    class TurnContext {
        +authority: TurnAuthority
        +turn_budget
        +pending_steers
    }
    class TurnAuthority {
        +mode: AgentMode
        +approval_policy
    }
    Engine --> Session
    Session --> Thread
    Thread --> Journal
    Engine ..> TurnContext : per turn
    TurnContext --> TurnAuthority
```

**读图**：`Session` 为进程内热状态；`Thread` + `Journal` 为可持久化对话树；`TurnContext` 每 Turn 构造一次。

---

## G4 持久化实体关系

```mermaid
erDiagram
    THREADS ||--o{ JOURNAL_ENTRIES : contains
    THREADS {
        string thread_id PK
        string leaf_id
        string workspace
    }
    JOURNAL_ENTRIES {
        string entry_id PK
        string parent_id FK
        string kind
        blob payload
    }
    SESSIONS ||--|| THREADS : references
    CHECKPOINTS }o--|| THREADS : optional
```

**读图**：分支对话 = 移动 `leaf_id`，不删除 `JOURNAL_ENTRIES`；checkpoint 与 thread 关联用于 resume/exec。

---

## G5 Op / Event 双通道

```mermaid
flowchart LR
    subgraph Inbound["Inbound Op"]
        O1[UserMessage]
        O2[Cancel]
        O3[Compact]
        O4[SetMode]
    end
    subgraph Engine["Engine 单任务"]
        Q[rx_op 队列]
        H[状态机处理]
    end
    subgraph Outbound["Outbound Event"]
        E1[TextDelta]
        E2[ToolStart/End]
        E3[TurnEnd]
        E4[Error]
    end
    Inbound --> Q --> H
    H --> Outbound
```

**读图**：外部**只**通过 Op 驱动；UI/exec **只**订阅 Event，避免与内部锁竞争。

---

## M1 `run_turn` Step 循环

```mermaid
sequenceDiagram
    participant RT as run_turn
    participant Prep as prepare_primary_turn_request
    participant Stream as process_stream
    participant Plan as plan_tool_calls
    participant Exec as execute_planned_tools

    RT->>Prep: 当前 messages 快照
    Prep->>Stream: model stream
    Stream-->>RT: outcome
    alt 有 tool_uses
        RT->>Plan: 权限 + 计划
        Plan->>Exec: 并行批次
        Exec-->>RT: results → messages
        RT->>RT: 继续 Step（预算检查）
    else 结束
        RT-->>RT: return TurnResult
    end
```

---

## M2 `process_stream` 流程

```mermaid
flowchart TD
    A[开始 stream] --> B{tokio::select}
    B -->|chunk| C[解析 StreamEvent]
    C --> D{类型}
    D -->|TextDelta| E[累积 visible text]
    D -->|ToolUse block| F[tool_uses 状态机]
    D -->|MessageStop| G[stop_reason]
    B -->|超时/取消| H[提前返回]
    G --> I{pending_resume?}
    I -->|是| J[StreamRetryBudget]
    J --> A
    I -->|否| K[StreamOutcome]
```

---

## M3 工具计划与执行

```mermaid
flowchart TD
    TU[ToolUse 列表] --> PL[plan_tool_calls]
    PL --> AUTH{TurnAuthority}
    AUTH -->|Ask| UI[用户审批 Event]
    AUTH -->|Allow| EP[ExecPolicy::evaluate]
    EP -->|Deny| ERR[tool error 消息]
    EP -->|Allow| EX[execute_planned_tools]
    EX --> SB[沙箱 / 工作区 carve-out]
    SB --> RES[tool_result]
```

---

## M4 ExecPolicy 时序

```mermaid
sequenceDiagram
    participant PL as plan_tool_calls
    participant EP as execpolicy engine
    participant UI as 审批 UI
    participant SH as shell/exec

    PL->>EP: command + cwd + metadata
    EP-->>PL: Allow / Deny / Ask
    alt Ask
        PL->>UI: approval request
        UI-->>PL: approved/denied
    end
    PL->>SH: 执行（若允许）
    SH-->>PL: stdout/stderr/exit
```

---

## M5 Compaction 流程

```mermaid
flowchart TD
    TR[Turn 边界 / 阈值] --> CH{token 超预算?}
    CH -->|否| SKIP[跳过]
    CH -->|是| CMP[compact_messages_safe]
    CMP --> SUM[LLM 摘要]
    SUM --> ATOMIC[写新 journal 叶 + rename]
    ATOMIC --> KV[保持 system+tools 前缀稳定]
```

---

## M6 Fleet 并行

```mermaid
sequenceDiagram
    participant M as 主 Engine
    participant FM as FleetManager
    participant W as Worker exec
    participant L as FleetLedger

    M->>FM: spawn_task(spec)
    FM->>L: lease / 记录
    FM->>W: codewhale exec
    W-->>FM: stream events
    FM-->>M: 聚合 Event
    W->>L: complete / release
```

---

## M7 MCP 调用链

```mermaid
flowchart LR
    CAT[tools catalog] --> DEF[deferred schema]
    ACT[ToolActivationCache] --> CALL[MCP client]
    CALL --> SRV[外部 MCP Server]
    SRV --> RES[tool result]
    RES --> MSG[messages 追加]
```

---

## 与主文档对照

| 图 | ARCHITECTURE 章节 |
|----|-------------------|
| G1–G2 | I.0, I.5 |
| G3–G4 | I.3, I.6 |
| G5 | I.4 |
| M1–M2 | II.1, II.2 |
| M3–M4 | II.6, II.7 |
| M5 | II.10 |
| M6 | II.11 |
| M7 | II.9 |
