# Harness-SDK（Strands）架构图集（全局）

> 配套 [ARCHITECTURE.md](../ARCHITECTURE.md)。**模块级 HS-01…HS-32**：[AGENT_MODULE_DIAGRAMS.md](./AGENT_MODULE_DIAGRAMS.md)。  
> 源码根：`harness-sdk/strands-py`、`harness-sdk/harness-py`。

---

## 图目录

| 编号 | 类型 | 标题 |
|------|------|------|
| G1 | architecture | SDK + Harness 两层 |
| G2 | classDiagram | Agent 与周边组件 |
| G3 | sequence | `agent(prompt)` 端到端 |
| G4 | flowchart | `event_loop_cycle` 决策树 |
| G5 | erDiagram | Session / Checkpoint / Messages |
| M1 | sequence | 单 cycle：模型流 → 工具 |
| M2 | flowchart | Interventions 门卫 |
| M3 | sequence | Interrupt / Resume |
| M4 | flowchart | ContextManager vs ConversationManager |
| M5 | sequence | 子智能体 spawn |
| M6 | flowchart | `create_harness` 组装 |

---

## G1 两层架构

```mermaid
flowchart TB
    subgraph Harness["harness-py strands_harness"]
        CH[create_harness]
        MOD[models / memory / prompt]
        INT[interventions presets]
        SUB[subagent presets]
    end
    subgraph SDK["strands-py strands"]
        AG[Agent]
        EL[event_loop_cycle]
        TR[ToolRegistry]
        SM[SessionManager]
        MM[MemoryManager]
        CM[ContextManager]
        HK[HookRegistry]
    end
    CH --> AG
    AG --> EL
    EL --> TR
    AG --> SM
    AG --> MM
    AG --> CM
    AG --> HK
```

**读图**：Harness 是**意见层**；循环与状态均在 `strands.Agent`。

---

## G2 核心类图

```mermaid
classDiagram
    class Agent {
        +messages: Message[]
        +model: Model
        +tool_registry: ToolRegistry
        +session_manager: SessionManager
        +memory_manager: MemoryManager
        +hooks: HookRegistry
        +__call__(input) AgentResult
    }
    class ToolRegistry {
        +register(tool)
        +get_all_tool_specs()
    }
    class SessionManager {
        +append_message()
        +load_snapshot()
    }
    class MemoryManager {
        +inject_context()
        +extract_async()
    }
    class ContextManager {
        +reduce_context()
    }
    Agent --> ToolRegistry
    Agent --> SessionManager
    Agent --> MemoryManager
    Agent --> ContextManager
```

---

## G3 端到端调用时序

```mermaid
sequenceDiagram
    autonumber
    participant App as 应用
    participant AG as Agent.__call__
    participant EL as event_loop_cycle
    participant MD as Model.stream
    participant HK as Hooks
    participant TE as ToolExecutor
    participant SM as SessionManager

    App->>AG: prompt / messages
    AG->>HK: BeforeInvocationEvent
    loop 每个 cycle
        AG->>EL: async generator
        EL->>HK: BeforeModelCallEvent
        EL->>MD: stream
        MD-->>EL: assistant + tool_calls?
        alt tool_use
            EL->>HK: BeforeToolsEvent
            EL->>TE: execute tools
            TE-->>EL: tool results
            EL->>AG: append messages
        else end_turn
            EL-->>AG: EventLoopStopEvent
        end
    end
    AG->>SM: persist snapshot
    AG-->>App: AgentResult
```

---

## G4 `event_loop_cycle` 决策树

```mermaid
flowchart TD
    START([cycle 开始]) --> INT{有 interrupt 恢复?}
    INT -->|是| RESUME[注入 interrupt 消息]
    INT -->|否| MODEL[调用模型]
    RESUME --> MODEL
    MODEL --> STOP{stop_reason}
    STOP -->|tool_use| TOOL[执行工具]
    TOOL --> REC{recurse?}
    REC -->|是| MODEL
    STOP -->|end_turn| END([yield stop])
    STOP -->|max_tokens / limit| END
    STOP -->|cancelled| END
    STOP -->|interrupt| HITL[保存 interrupt 状态]
    HITL --> END
```

---

## G5 会话与检查点实体

```mermaid
erDiagram
    AGENT_STATE ||--o{ MESSAGE : holds
    SESSION_SNAPSHOT ||--|| AGENT_STATE : serializes
    CHECKPOINT ||--o| SESSION_SNAPSHOT : optional
    MESSAGE {
        string role
        json content
    }
    SESSION_SNAPSHOT {
        string session_id
        datetime updated_at
    }
```

---

## M1 单 Cycle 模型-工具时序

```mermaid
sequenceDiagram
    participant EL as event_loop_cycle
    participant M as Model
    participant IV as Interventions
    participant EX as ConcurrentToolExecutor

    EL->>M: stream(messages, tools)
    M-->>EL: tool_use blocks
    EL->>IV: BeforeToolsEvent
    IV-->>EL: allow/deny/interrupt
    par 并行工具
        EL->>EX: tool A
        EL->>EX: tool B
    end
    EX-->>EL: ToolResultEvent[]
    EL->>EL: append + recurse
```

---

## M2 Interventions 流程

```mermaid
flowchart LR
    BT[BeforeToolsEvent] --> H1{Handler 链}
    H1 --> ASK[HumanInTheLoop]
    H1 --> CEDAR[CedarAuthorization]
    H1 --> LLM[LLM classifier]
    ASK --> R{Result}
    CEDAR --> R
    LLM --> R
    R -->|allow| EXEC[执行工具]
    R -->|deny| SKIP[写入错误结果]
    R -->|interrupt| PAUSE[InterruptException]
```

---

## M3 Interrupt / Resume

```mermaid
sequenceDiagram
    participant EL as event_loop
    participant IV as Intervention
    participant App as 应用
    participant AG as Agent

    EL->>IV: risky tool
    IV-->>EL: interrupt
    EL-->>App: AgentResult.interrupts
    App->>App: 用户决策
    App->>AG: 带 resume payload 再调用
    AG->>EL: 从 interrupt 状态继续
```

---

## M4 上下文压缩互斥

```mermaid
flowchart TD
    CFG[Agent 配置] --> Q{ContextManager 已设?}
    Q -->|是| NULL[ConversationManager = Null]
    Q -->|否| SL[SlidingWindow / Summarizing]
    CM[ContextManager pipeline] --> STASH[Stash 检索]
    OFF[ContextOffloader 插件] --> BIG[大 tool result 落盘]
```

---

## M5 子智能体

```mermaid
sequenceDiagram
    participant Parent as 父 Agent
    participant Tool as subagent tool
    participant Child as 子 Agent
    participant Axis as Preset/Axis 解析

    Parent->>Tool: invoke(task)
    Tool->>Axis: Fixed/Inherit/Open/Choice
    Axis->>Child: 构造 messages + tools
    Child->>Child: event_loop_cycle*
    Child-->>Tool: 汇总结果
    Tool-->>Parent: tool_result
```

---

## M6 `create_harness` 组装

```mermaid
flowchart TD
    A[create_harness 参数] --> M[resolve_model]
    A --> MEM[resolve_memory]
    A --> P[HARNESS_CONTRACT prompt]
    A --> T[builtin_tools + plugins]
    A --> I[interventions 字符串]
    M --> AG[Agent 实例]
    MEM --> AG
    P --> AG
    T --> AG
    I --> AG
```

---

## 章节对照

| 图 | ARCHITECTURE |
|----|----------------|
| G1–G3 | §1, §2.1–2.2 |
| G4 | §2.1 |
| G5 | §2.3 |
| M2 | §2.6 |
| M3 | 第三部分 P3.3 |
| M4 | §2.5 |
| M5 | §2.8 |
| M6 | §2.7 |
