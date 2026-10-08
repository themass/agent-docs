#!/usr/bin/env python3
"""Generate docs/*/diagrams/AGENT_MODULE_DIAGRAMS.md — per-module mermaid for four projects."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(f"wrote {path} ({body.count(chr(10))+1} lines)")


def codewhale() -> str:
    modules = [
        ("CW-01", "Engine 主循环与 Op 分派", "engine.rs", "flowchart",
         """flowchart TD
    RUN[Engine::run] --> SEL{rx_op.recv}
    SEL -->|UserMessage| RT[run_turn]
    SEL -->|Cancel| CAN[取消当前 Turn]
    SEL -->|Compact| CMP[触发压缩 Op]
    SEL -->|SetMode| MOD[更新 AgentMode]
    RT --> EVT[tx_event 推送]
    CAN --> EVT
    CMP --> EVT""",
         "Engine 单 Tokio 任务；所有外部输入经 Op 队列，禁止旁路调用 run_turn。"),
        ("CW-02", "run_turn 与 TurnContext", "turn_loop.rs", "sequence",
         """sequenceDiagram
    participant RT as run_turn
    participant TC as TurnContext
    participant PR as prepare_request
    participant ST as Step 循环
    RT->>TC: 构造 authority + budget
    loop until end_turn or limit
        RT->>PR: PrimaryTurnRequest
        PR->>ST: stream + tools
        ST-->>RT: tool_use → 执行 → 下一 Step
    end""",
         "TurnContext 每 Turn 一次；Step 可多次。"),
        ("CW-03", "process_stream 流解析", "turn_loop.rs", "flowchart",
         """flowchart TD
    S[Stream 入口] --> SEL[tokio::select]
    SEL --> EV[StreamEvent 分派]
    EV --> T[TextDelta]
    EV --> TU[ToolUse JSON 累积]
    EV --> MS[MessageStop + usage]
    MS --> RET{resume?}
    RET -->|StreamRetry| S
    RET -->|done| OUT[StreamOutcome]""",
         "多 ToolUse 用 block_index 映射；suspend 检测用 mono vs wall clock。"),
        ("CW-04", "plan_tool_calls 权限门", "turn_loop.rs", "flowchart",
         """flowchart TD
    TU[ToolUse 列表] --> RP[resolve_tool_permission]
    RP --> TA[TurnAuthority]
    TA --> EP[ExecPolicy per command]
    EP --> ASK{需审批?}
    ASK -->|是| UI[Approval Event]
    ASK -->|否| EX[execute_planned_tools]""",
         "TurnAuthority 会话级；ExecPolicy 命令级。"),
        ("CW-05", "prepare_primary_turn_request", "core/request.rs", "flowchart",
         """flowchart LR
    MSG[messages 快照] --> FR[fragments 组装]
    SYS[BASE_PROMPT 稳定前缀] --> FR
    TOOLS[tool catalog + deferred] --> FR
    IMG[图像省略/注入] --> FR
    FR --> OUT[Provider Request]""",
         "volatile facts 用 user message 追加，不改 system 前缀（KV cache）。"),
        ("CW-06", "Thread / Journal / branch", "core/session.rs", "classDiagram",
         """classDiagram
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
    Journal --> JournalEntry""",
         "分支只移动 leaf_id；历史 append-only。"),
        ("CW-07", "Session 热状态", "tui/core/session.rs", "classDiagram",
         """classDiagram
    class Session {
        +messages_revision
        +working_set WorkingSet
        +tool_activation_cache
    }
    class WorkingSet {
        +touched_paths
    }
    Session --> WorkingSet""",
         "Session 不落盘；Thread 落 SQLite。"),
        ("CW-08", "TurnAuthority 与 Mode", "authority.rs", "flowchart",
         """flowchart TD
    MODE[AgentMode] --> TA[TurnAuthority]
    PROV[Provenance] --> TA
    TA --> POL[approval_policy]
    POL --> TOOL[per-tool 决策输入]""",
         "子代理/checkpoint 来源可 provenance narrowing。"),
        ("CW-09", "ExecPolicy 规则引擎", "execpolicy/", "sequence",
         """sequenceDiagram
    participant PL as plan_tool_calls
    participant EP as execpolicy
    participant R as RuleSet
    PL->>EP: ParsedCommand
    EP->>R: match prefix/glob
    R-->>EP: Allow/Deny/Ask
    EP-->>PL: Decision""",
         "独立 crate，无 TUI 依赖，worker 可复用。"),
        ("CW-10", "tool_execution 并行批次", "tool_execution.rs", "flowchart",
         """flowchart TD
    BATCH[planned tools] --> PAR[并行批次]
    PAR --> G1[OperationSpanGuard]
    G1 --> HB[ToolHeartbeatGuard 长任务]
    HB --> RES[stdout/stderr]
    RES --> MSG[tool_result 消息]""",
         "LSP hooks 在特定工具前后触发。"),
        ("CW-11", "工具体系与 deferred schema", "tools/", "flowchart",
         """flowchart LR
    CAT[ToolCatalog] --> DEF[deferred 工具]
    DEF --> CACHE[ToolActivationCache]
    CACHE --> ACT[激活后完整 schema 进请求]
    BUILTIN[内置 bash/read/edit] --> CAT""",
         "降低每轮 token：未激活工具仅短描述。"),
        ("CW-12", "MCP 集成", "mcp.rs", "sequence",
         """sequenceDiagram
    participant E as Engine
    participant M as MCP manager
    participant S as MCP Server
    E->>M: list_tools / call
    M->>S: JSON-RPC
    S-->>M: result
    M-->>E: 与内置工具同路径 plan/execute""",
         "环境变量占位符 expand_env_placeholders。"),
        ("CW-13", "Compaction", "compaction.rs", "flowchart",
         """flowchart TD
    TRIG[token 阈值 / Op] --> SAFE[compact_messages_safe]
    SAFE --> SUM[摘要 LLM]
    SUM --> ATOM[原子 rename journal]
    ATOM --> PREFIX[冻结 system+tools 前缀]""",
         "压缩后 messages_revision 递增。"),
        ("CW-14", "memory crate", "memory/", "flowchart",
         """flowchart LR
    NATIVE[NativeMemory 工具] --> STORE[记忆条目]
    STORE --> INJ[注入 turn 上下文]
    INJ --> RT[run_turn]""",
         "与对话 compaction 不同域。"),
        ("CW-15", "state / SQLite", "state/", "erDiagram",
         """erDiagram
    THREADS ||--o{ MESSAGES : stores
    THREADS {
        string id PK
    }
    CHECKPOINTS }o--|| THREADS : links""",
         "Schema 迁移在 state crate。"),
        ("CW-16", "ModelClient 多 Provider", "tui/client/", "flowchart",
         """flowchart LR
    TRAIT[ModelClient] --> A[Anthropic]
    TRAIT --> O[OpenAI compat]
    TRAIT --> D[DeepSeek/Ollama]
    TRAIT --> U[Usage 合并]""",
         "SSE/chunked 解析为统一 StreamEvent。"),
        ("CW-17", "goal_loop / GoalBudget", "runtime/goal_loop.rs", "sequence",
         """sequenceDiagram
    participant GL as goal_loop
    participant GB as GoalBudget
    participant RT as run_turn
    GL->>GB: 检查 token/time/次数
    GB-->>GL: continue?
    GL->>RT: goal continuation turn""",
         "持久目标跨多个 Turn。"),
        ("CW-18", "Fleet / SubAgent", "fleet/", "flowchart",
         """flowchart TB
    MAIN[主 Engine] --> FM[FleetManager]
    FM --> LED[FleetLedger lease]
    FM --> EXEC[codewhale exec worker]
    EXEC --> SUB[子 Thread/Session 隔离]""",
         "Fleet 管资格；Runtime 管执行。"),
        ("CW-19", "Lane 工作树", "lane/", "flowchart",
         """flowchart LR
    LANE[Lane 身份] --> WS[隔离 workspace]
    WS --> RT[run_turn 在子树]""",
         "与 Fleet 编排配合。"),
        ("CW-20", "workflow", "workflow/", "flowchart",
         """flowchart TD
    WF[workflow 定义] --> STEP[步骤节点]
    STEP --> ENG[Engine 驱动 tool/LLM]
    ENG --> WF""",
         "高层任务编排，底层仍 run_turn。"),
        ("CW-21", "cli / exec 无 UI", "cli/", "sequence",
         """sequenceDiagram
    participant EX as codewhale exec
    participant E as Engine
    participant OUT as stream-json
    EX->>E: 同 TUI Engine
    E-->>OUT: Event 序列
    OUT-->>EX: resume checkpoint""",
         "与 TUI 共享 turn_loop。"),
        ("CW-22", "app-server", "app-server/", "flowchart",
         """flowchart LR
    HTTP[HTTP/daemon] --> PROXY[chat-completions 代理]
    PROXY --> ENG[Engine 或转发]""",
         "可选 headless 接入。"),
        ("CW-23", "hooks / telemetry", "hooks/ telemetry/", "flowchart",
         """flowchart LR
    RT[run_turn] --> HK[hooks 埋点]
    HK --> TEL[telemetry 导出]""",
         "可观测性不进入模型上下文。"),
        ("CW-24", "config / secrets", "config/ secrets/", "flowchart",
         """flowchart TD
    CFG[加载配置] --> FAIL[错误即 panic/明确 error]
    SEC[secrets] --> MC[ModelClient 凭证]""",
         "快速失败契约。"),
        ("CW-25", "protocol 消息类型", "protocol/", "classDiagram",
         """classDiagram
    class Op
    class Event
    class ToolSpec
    Op <|-- UserMessage
    Event <|-- TextDelta""",
         "跨 crate 共享类型；减少循环依赖。"),
        ("CW-26", "models 与路由", "models/", "flowchart",
         """flowchart LR
    CFG[config model id] --> RES[resolve provider]
    RES --> MC[ModelClient 实例]""",
         "多 provider 配置入口。"),
        ("CW-27", "command-contract", "command-contract/", "flowchart",
         """flowchart TD
    TOOL[bash 工具] --> PARSE[contract 解析]
    PARSE --> EP[execpolicy 输入]""",
         "结构化命令表示。"),
        ("CW-28", "Steer 与 pending_steers", "turn_loop.rs", "sequence",
         """sequenceDiagram
    participant U as 用户
    participant PS as process_stream
    participant RT as run_turn
    U->>PS: mid-stream steer
    PS->>PS: pending_steers 缓冲
    PS-->>RT: Turn 边界合并入 messages""",
         "steer 在 Step 边界提交，不撕裂 tool JSON。"),
        ("CW-29", "checkpoint / resume", "state/ exec", "sequence",
         """sequenceDiagram
    participant EX as exec
    participant ST as state
    participant E as Engine
    EX->>ST: 读 checkpoint
    ST->>E: resume Op
    E-->>EX: 续跑 stream-json""",
         "headless 恢复路径。"),
    ]
    body = render("Codewhale", "Codewhale/crates/", modules)
    body += appendix_codewhale()
    return body


def harness() -> str:
    modules = [
        ("HS-01", "Agent.__call__ 同步入口", "agent/agent.py", "sequence",
         """sequenceDiagram
    participant C as Caller
    participant A as Agent
    participant AS as run_async
    C->>A: __call__(input)
    A->>AS: invoke / stream bridge
    AS-->>C: AgentResult""",
         "并发锁与幂等 token 在 __call__ 边界。"),
        ("HS-02", "stream_async 管道", "agent/agent.py", "flowchart",
         """flowchart TD
    SA[stream_async] --> LIM[_validate_limits]
    LIM --> CONC[_concurrency.begin]
    CONC --> INT[_interrupt_state.resume]
    INT --> LOOP[_run_loop]""",
         "cancel_signal 挂载 watcher。"),
        ("HS-03", "event_loop_cycle", "event_loop/event_loop.py", "flowchart",
         """flowchart TD
    C0[cycle 开始] --> BM[BeforeModelCall]
    BM --> MD[model stream]
    MD --> BT{tool_use?}
    BT -->|是| BTL[BeforeTools + execute]
    BTL --> REC[recurse cycle]
    BT -->|否| STOP[EventLoopStopEvent]""",
         "async generator；invocation_state 跨 cycle。"),
        ("HS-04", "_handle_model_execution", "event_loop/event_loop.py", "sequence",
         """sequenceDiagram
    participant EL as event_loop
    participant M as Model
    participant HK as Hooks
    EL->>HK: BeforeModelCallEvent
    EL->>M: stream
    M-->>EL: chunks → assistant message""",
         "ContextWindowOverflow 可触发 reduce 重试。"),
        ("HS-05", "工具执行 ConcurrentToolExecutor", "tools/executors/", "flowchart",
         """flowchart TD
    TU[ToolUse 列表] --> POOL[并行 executor]
    POOL --> GEN[ToolGenerator async]
    GEN --> RES[ToolResultEvent]""",
         "背压与并发上限可配置。"),
        ("HS-06", "ToolRegistry", "tools/", "classDiagram",
         """classDiagram
    class ToolRegistry {
        +register(AgentTool)
        +get_all_tool_specs()
    }
    class AgentTool {
        +tool_name
        +stream()
    }
    ToolRegistry --> AgentTool""",
         "builtin + 动态注册。"),
        ("HS-07", "SessionManager / Snapshot", "session/", "sequence",
         """sequenceDiagram
    participant A as Agent
    participant SM as SessionManager
    participant ST as LocalFileStorage
    A->>SM: append on MessageAdded
    SM->>ST: snapshot JSON""",
         "跨进程 resume 读 snapshot。"),
        ("HS-08", "Checkpoint", "session/checkpoint", "flowchart",
         """flowchart LR
    INV[invocation] --> CP[checkpoint 写入]
    CP --> RES[interrupt 后恢复]""",
         "与 Session 正交。"),
        ("HS-09", "MemoryManager", "memory/", "flowchart",
         """flowchart TD
    TURN[对话结束] --> EXT[后台 extract]
    NEXT[下轮 BeforeInvocation] --> INJ[inject 语义记忆]
    INJ --> MSG[messages]""",
         "只读共享视图防写冲突。"),
        ("HS-10", "ContextManager + Stash", "experimental/context_manager/", "flowchart",
         """flowchart TD
    MSG[消息增长] --> RED[reduce_context 策略]
    RED --> ST[Stash 可检索]
    RED --> SUM[摘要替换]""",
         "设置后 ConversationManager → Null。"),
        ("HS-11", "ContextOffloader", "vended_plugins/context_offloader/", "sequence",
         """sequenceDiagram
    participant T as Tool result
    participant O as Offloader
    participant D as Disk
    T->>O: 超大 payload
    O->>D: 写入引用
    O-->>T: 缩短进 context""",
         "插件 init_agent 注册。"),
        ("HS-12", "HookRegistry", "hooks/", "flowchart",
         """flowchart LR
    EV[Event 类型] --> REG[handlers 列表]
    REG --> SYNC[同步/异步回调]""",
         "BeforeModel/BeforeTools/MessageAdded 等。"),
        ("HS-13", "Interventions", "interventions/", "flowchart",
         """flowchart TD
    BT[BeforeToolsEvent] --> H1[HumanInTheLoop]
    BT --> H2[Cedar]
    BT --> H3[LLM classifier]
    H1 --> R[allow/deny/interrupt]""",
         "harness 字符串语法解析为 Handler。"),
        ("HS-14", "create_harness", "strands_harness/agent.py", "flowchart",
         """flowchart TD
    CH[create_harness] --> M[resolve_model]
    CH --> MEM[memory]
    CH --> P[HARNESS_CONTRACT]
    CH --> PL[plugins + todos + env]
    CH --> I[interventions]
    M --> AG[Agent]""",
         "意见层一次性组装。"),
        ("HS-15", "Subagent / Axis", "tools/subagent.py", "flowchart",
         """flowchart TD
    PRE[Preset] --> AX[Fixed/Inherit/Open/Choice]
    AX --> CHILD[子 Agent 实例]
    CHILD --> EL[event_loop_cycle]""",
         "上下文分享：none/summary/full。"),
        ("HS-16", "multiagent Graph/Swarm", "multiagent/", "flowchart",
         """flowchart LR
    G[Graph 节点] --> A1[Agent]
    G --> A2[Agent]
    SW[Swarm] --> ROUTE[路由策略]""",
         "节点内仍 Agent.run。"),
        ("HS-17", "Model / stream", "models/ streaming.py", "flowchart",
         """flowchart TD
    M[Model.stream] --> PS[process_stream 状态机]
    PS --> EV[StreamEvent 类型]""",
         "Router 多模型。"),
        ("HS-18", "Middleware 洋葱", "_middleware/", "flowchart",
         """flowchart LR
    IN[请求] --> M1 --> M2 --> M3 --> CORE[terminal]
    CORE --> M3 --> M2 --> M1 --> OUT""",
         "AgentStreamStage。"),
        ("HS-19", "background_tasks", "background_tasks/", "flowchart",
         """flowchart TD
    POL[always/agentic/never] --> BG[后台任务队列]
    BG --> TOOL[长运行工具]""",
         "策略字典配置。"),
        ("HS-20", "telemetry", "telemetry/", "flowchart",
         """flowchart LR
    SPAN[OTel span] --> EL[event_loop_cycle_id]""",
         "与业务消息分离。"),
        ("HS-21", "sandbox", "sandbox/", "flowchart",
         """flowchart TD
    TOOL[工具] --> SB[沙箱策略]
    SB --> EXEC[子进程/限制]""",
         "与 interventions 叠加。"),
        ("HS-22", "vended_tools / web_fetch", "harness tools/", "sequence",
         """sequenceDiagram
    participant A as Agent
    participant W as web_fetch
    W->>W: URL 策略校验
    W-->>A: 截断正文""",
         "内置工具安全边界。"),
        ("HS-23", "types / AgentResult", "types/", "classDiagram",
         """classDiagram
    class AgentResult {
        +stop_reason
        +message
        +interrupts
        +structured_output
    }
    class EventLoopStopEvent
    AgentResult --> EventLoopStopEvent""",
         "stop_reason 枚举驱动分支。"),
        ("HS-24", "storage", "storage/", "flowchart",
         """flowchart LR
    SM[SessionManager] --> LS[LocalFileStorage]
    LS --> JSON[snapshot 文件]""",
         "可换自定义 Storage。"),
        ("HS-25", "injection / ContextInjector", "injection/", "sequence",
         """sequenceDiagram
    participant BI as BeforeInvocation
    participant I as ContextInjector
    participant A as Agent.messages
    BI->>I: 临时 facts
    I->>A: extend 仅本轮""",
         "不污染持久 session。"),
        ("HS-26", "handlers", "handlers/", "flowchart",
         """flowchart TD
    EV[stream events] --> H[handlers 链]
    H --> UI[CLI/UI 消费]""",
         "与 hooks 区别：对外展示。"),
        ("HS-27", "interrupt.py", "interrupt.py", "stateDiagram",
         """stateDiagram-v2
    [*] --> Running
    Running --> Interrupted: InterruptException
    Interrupted --> Running: resume payload
    Running --> [*]: end_turn""",
         "与 interventions interrupt 对齐。"),
        ("HS-28", "limits", "types/limits.py", "flowchart",
         """flowchart TD
    T[turn 计数] --> CHK[_check_limits]
    TOK[token 计数] --> CHK
    CHK -->|超限| STOP[limit_* stop]""",
         "Limits 在 cycle 边界检查。"),
        ("HS-29", "vended_memory_stores", "vended_memory_stores/", "flowchart",
         """flowchart LR
    MM[MemoryManager] --> VS[向量/文件 store 插件]""",
         "可选后端。"),
        ("HS-30", "harness plugins todos/env", "strands_harness/plugins/", "flowchart",
         """flowchart TD
    CH[create_harness] --> ENV[environment 注入]
    CH --> TODO[todos 临时任务表]""",
         "每轮 BeforeInvocation 注入。"),
        ("HS-31", "prompt HARNESS_CONTRACT", "strands_harness/prompt.py", "flowchart",
         """flowchart LR
    P[四节契约] --> SYS[system 拼接]
    SYS --> AG[Agent]""",
         "Action/Tools/Safety/Context。"),
        ("HS-32", "models resolve effort", "strands_harness/models.py", "flowchart",
         """flowchart TD
    ID[model id 字符串] --> R[resolve_model]
    R --> EFF[effort 映射]
    EFF --> M[Model 实例]""",
         "auto/off/minimal/.../max。"),
    ]
    body = render("Harness-SDK (Strands)", "harness-sdk/strands-py/", modules)
    body += appendix_harness()
    return body


def sol_pi() -> str:
    modules = [
        ("SP-01", "index.ts 扩展工厂", "index.ts", "sequence",
         """sequenceDiagram
    participant H as 宿主 session_start
    participant I as sol-pi index
    I->>I: load config validate
    I->>I: register 4 extensions
    I-->>H: tools + event handlers""",
         "session_start 只执行一次守卫。"),
        ("SP-02", "config.ts 校验", "config.ts", "flowchart",
         """flowchart TD
    RAW[配置 JSON] --> V[schema 校验]
    V -->|fail| ERR[抛错/禁用特性]
    V -->|ok| FLAGS[feature flags]""",
         "fail closed on invalid。"),
        ("SP-03", "action-fusion 注册", "action-fusion/index.ts", "flowchart",
         """flowchart LR
    REG[registerTool 包装 edit/write] --> TR[继承宿主 schema+render]
    TR --> EX[executeMutationThenRun]""",
         "then_run 追加参数。"),
        ("SP-04", "file-queue 串行", "file-queue.ts", "flowchart",
         """flowchart TD
    PATH[normalize 路径] --> Q[同文件队列]
    Q --> RUN[顺序执行 mutation]""",
         "防并发写同一文件。"),
        ("SP-05", "then-run 执行", "then-run.ts", "sequence",
         """sequenceDiagram
    participant AF as action-fusion
    participant H as 宿主 execute
    AF->>H: edit/write
    H-->>AF: ok
    AF->>H: 可选 bash then_run""",
         "SHA 可选防竞态。"),
        ("SP-06", "observation-pack context 钩", "observation-pack/index.ts", "sequence",
         """sequenceDiagram
    participant H as context 事件
    participant OP as obs-pack
    participant P as 投影 messages
    H->>OP: full entries
    OP->>P: 占位符/原文/sentCounts""",
         "磁盘 session 仍全文。"),
        ("SP-07", "observation.ts CAS", "observation.ts", "flowchart",
         """flowchart TD
    BIG[大 tool 输出] --> HASH[内容哈希]
    HASH --> STORE[O_EXCL 写 blob]
    STORE --> PH[placeholderFor]""",
         "收据前缀豁免打包。"),
        ("SP-08", "ledger.ts", "ledger.ts", "classDiagram",
         """classDiagram
    class Ledger {
        +placeholder records
        +recall metadata
    }""",
         "三种记录类型。"),
        ("SP-09", "obs_recall 工具", "observation-pack", "sequence",
         """sequenceDiagram
    participant LLM as 模型
    participant R as obs_recall
    participant L as ledger/CAS
    LLM->>R: offset
    R->>L: readRecallChunk
    R-->>LLM: page""",
         "分页召回。"),
        ("SP-10", "reducer candidate", "candidate.ts", "flowchart",
         """flowchart TD
    OUT[tool output] --> C{候选条件}
    C -->|是| RED[归约 LLM]
    C -->|否| PASS[透传]""",
         "体积与模式匹配。"),
        ("SP-11", "receipt 校验", "receipt.ts", "flowchart",
         """flowchart TD
    R[收据 JSON] --> V[validateReceipt]
    V --> Q[quote ⊆ 原文]
    Q -->|ok| EMIT[缩短结果]
    Q -->|fail| REJECT[回退 fail open]""",
         "防捏造引用。"),
        ("SP-12", "archive + journal", "archive.ts journal.ts", "flowchart",
         """flowchart LR
    RED[归约] --> ARC[分片 archive]
    RED --> JRN[journal 条目]""",
         "可审计。"),
        ("SP-13", "reducer provider", "provider.ts", "sequence",
         """sequenceDiagram
    participant R as reducer
    participant P as 归约模型
    R->>P: 日志摘录
    P-->>R: 收据草稿
    R->>R: validateReceipt""",
         "可注入 provider。"),
        ("SP-14", "online-compact extension", "extension.ts", "stateDiagram",
         """stateDiagram-v2
    [*] --> Idle
    Idle --> Evaluating: turn_end
    Evaluating --> Waiting: 需要 compact
    Waiting --> InFlight: 宿主 compact
    InFlight --> Idle""",
         "compactionInFlight 防重入。"),
        ("SP-15", "economics.ts", "economics.ts", "flowchart",
         """flowchart TD
    TOK[投影 token 估计] --> DEBT[cache debt]
    DEBT --> DEC[decideCompaction]
    DEC -->|breakeven| GO[触发 compact]
    DEC -->|否| SKIP[跳过]""",
         "首次宽容后续保守。"),
        ("SP-16", "update_plan 工具", "plan.ts tools.ts", "sequence",
         """sequenceDiagram
    participant LLM as 模型
    participant P as update_plan
    participant ST as OnlineState
    LLM->>P: 步骤状态
    P->>ST: boundary / epoch""",
         "CORRECTION 重置状态。"),
        ("SP-17", "runtime-paths", "runtime-paths.ts", "flowchart",
         """flowchart LR
    SD[sessionDir] --> RR[sol-pi/sessionId/]
    RR --> OBS[obs/ reducer/ ...]""",
         "会话级隔离。"),
        ("SP-18", "四机制串联", "全局", "sequence",
         """sequenceDiagram
    participant AF as Fusion
    participant OP as ObsPack
    participant ER as Reducer
    participant OC as OnlineCompact
    AF->>OP: 大输出
    OP->>ER: 日志候选
    ER->>OC: 投影 token
    OC->>OC: compact 决策""",
         "机制可独立开关。"),
    ]
    modules.append(("SP-19", "tui.ts 渲染", "tui.ts", "flowchart",
         """flowchart LR
    TOOL[工具 TUI] --> R[renderCall/renderResult]
    R --> AF[Action Fusion 包装 UI]""",
         "then_run 时展示后续命令。"))
    modules.append(("SP-20", "宿主事件总线", "ExtensionAPI", "flowchart",
         """flowchart TD
    E1[session_start] --> E2[context]
    E2 --> E3[tool_result]
    E3 --> E4[before_provider_request]
    E4 --> E5[turn_end]
    E5 --> E6[session_compact]""",
         "SoL-Pi 在各事件挂接点。"))
    body = render("SoL-Pi", "SoL-Pi/src/sol-pi/", modules)
    body += appendix_sol_pi()
    return body


def understand_anything() -> str:
    agent_specs = {
        "project-scanner": (
            """sequenceDiagram
    participant SK as /understand
    participant PS as project-scanner
    participant FS as 文件系统
    SK->>PS: 仓库根
    PS->>FS: 遍历+ignore
    PS-->>SK: scan-result + neighborMap""",
            "产出批次列表与跨文件邻居符号。",
        ),
        "file-analyzer": (
            """sequenceDiagram
    participant PS as scanner 批次
    participant FA as file-analyzer
    participant TS as Tree-sitter 脚本
    participant LLM as LLM
    PS->>FA: batchFiles + neighborMap
    FA->>TS: Phase1
    TS-->>FA: 结构 JSON
    FA->>LLM: Phase2 语义
    LLM-->>FA: batch 子图""",
            "两阶段；临时文件带 batchIndex。",
        ),
        "architecture-analyzer": (
            """flowchart TD
    G[合并图] --> AA[architecture-analyzer]
    AA --> L[layers 划分]
    AA --> E[模块级边聚合]""",
            "消费 file 层节点之上抽象。",
        ),
        "tour-builder": (
            """flowchart TD
    G[图+layers] --> TB[tour-builder]
    TB --> TS[TourStep 文案]
    TB --> SORT[拓扑排序]""",
            "步骤字数与覆盖约束在提示词。",
        ),
        "graph-reviewer": (
            """flowchart TD
    G[knowledge-graph] --> GR[graph-reviewer]
    GR --> C9[9 项检查]
    C9 --> R[报告/修复指令]""",
            "层覆盖率 Check4 最常失败。",
        ),
        "domain-analyzer": (
            """flowchart LR
    G --> DA[domain-analyzer]
    DA --> DN[domain 节点/边]""",
            "业务域归纳，可选阶段。",
        ),
        "design-analyzer": (
            """flowchart LR
    FIG[Figma/设计输入] --> DA[design-analyzer]
    DA --> DG[design 子图]""",
            "与 figma 包协作。",
        ),
        "assemble-reviewer": (
            """sequenceDiagram
    participant M as merge 后
    participant AR as assemble-reviewer
    AR->>AR: 组装一致性
    AR-->>M: 补丁建议""",
            "合并后完整性审查。",
        ),
        "article-analyzer": (
            """flowchart LR
    DOC[文档/文章] --> AA[article-analyzer]
    AA --> N[document 节点]""",
            "非代码资产入图。",
        ),
        "knowledge-graph-guide": (
            """flowchart LR
    U[用户问答] --> KG[knowledge-graph-guide]
    KG --> G[检索图+Tour]""",
            "对话式读图，非批处理流水线。",
        ),
    }
    modules = []
    for i, (name, (mermaid, note)) in enumerate(agent_specs.items(), 1):
        typ = "sequence" if mermaid.strip().startswith("sequence") else "flowchart"
        modules.append((f"UA-A{i:02d}", f"Agent: {name}", f"agents/{name}.md", typ, mermaid, note))
    core = [
        ("UA-C01", "GraphBuilder", "graph-builder", "classDiagram",
         """classDiagram
    class GraphBuilder {
        +addNode()
        +addEdge()
        +build()
    }""",
         "id 命名规则与去重。"),
        ("UA-C02", "schema validateGraph", "schema.ts", "flowchart",
         """flowchart TD
    G[graph JSON] --> T1[Tier1 结构]
    T1 --> T2[Tier2 类型]
    T2 --> T3[Tier3 引用]
    T3 --> T4[Tier4 拓扑]""",
         "Dashboard 加载前校验。"),
        ("UA-C03", "TreeSitterPlugin", "tree-sitter-plugin.ts", "flowchart",
         """flowchart TD
    WASM[grammar wasm] --> P[Plugin]
    P --> FULL[analyzeFileFull]
    P --> EXT[LanguageExtractor]
    EXT --> JSON[StructuralAnalysis]""",
         "strict vs full 模式。"),
        ("UA-C04", "fingerprint", "fingerprint.ts", "flowchart",
         """flowchart TD
    F[读文件] --> H[contentHash]
    H --> S[结构字段比对]
    S --> LV[NONE/COSMETIC/STRUCTURAL]""",
         "语言白名单控制结构指纹。"),
        ("UA-C05", "change-classifier", "change-classifier.ts", "flowchart",
         """flowchart TD
    A[ChangeAnalysis] --> CL[classifyUpdate]
    CL --> SKIP
    CL --> PART
    CL --> ARCH
    CL --> FULL""",
         "目录变化 → ARCHITECTURE_UPDATE。"),
        ("UA-C06", "staleness / freshness", "staleness.ts", "stateDiagram",
         """stateDiagram-v2
    [*] --> fresh
    fresh --> dirty: 工作区改动
    fresh --> stale: HEAD 前进
    stale --> [*]""",
         "unknown 时仍可读图。"),
        ("UA-C07", "persistence saveGraph", "persistence/", "sequence",
         """sequenceDiagram
    participant S as saveGraph
    participant SAN[sanitiseFilePaths]
    participant FS as knowledge-graph.json
    S->>SAN: 相对路径
    SAN->>FS: write""",
         "防绝对路径泄露。"),
        ("UA-C08", "merge-batch-graphs", "skills/脚本", "flowchart",
         """flowchart TD
    B1[batch1] --> MG[merge]
    B2[batch2] --> MG
    MG --> DEDUP[id 去重]
    DEDUP --> G[主图]""",
         "冲突写 meta.warnings。"),
        ("UA-C09", "Dashboard 加载", "dashboard", "sequence",
         """sequenceDiagram
    participant B as Browser
    participant API as API
    participant V as validateGraph
    participant W as Layout Worker
    B->>API: token + fetch
    API->>V: graph
    V->>W: 布局
    W-->>B: ReactFlow""",
         "五路并行 fetch。"),
        ("UA-C10", "embedding-search", "embedding-search.ts", "flowchart",
         """flowchart LR
    Q[自然语言] --> EMB[嵌入]
    EMB --> IDX[索引检索]
    IDX --> N[node ids]""",
         "辅助拓扑导航。"),
        ("UA-C11", "ignore-filter", "ignore-filter.ts", "flowchart",
         """flowchart TD
    SCAN[扫描] --> IGN[.understandignore]
    IGN --> SKIP[排除路径]""",
         "与 scanner 输出联动。"),
        ("UA-C12", "tour-generator", "analyzer/tour-generator.ts", "flowchart",
         """flowchart TD
    G[图+layers] --> KAHN[拓扑排序]
    KAHN --> STEPS[TourStep 列表]""",
         "质量约束在 agent 提示词。"),
        ("UA-C13", "figma merge", "figma/", "flowchart",
         """flowchart LR
    API[Figma API] --> PARSE[parse]
    PARSE --> MERGE[merge 进图]
    MERGE --> G[design 节点]""",
         "可选设计域。"),
        ("UA-C14", "file-analyzer 两阶段", "file-analyzer", "sequence",
         """sequenceDiagram
    participant FA as file-analyzer
    participant SC as 提取脚本
    participant LLM as LLM
    FA->>SC: Phase1
    SC-->>FA: 结构 JSON
    FA->>LLM: Phase2 语义
    LLM-->>FA: nodes/edges""",
         "neighborMap 跨批边。"),
        ("UA-C15", "graph-reviewer 检查", "graph-reviewer", "flowchart",
         """flowchart TD
    G[图] --> C1..C9[9 checks]
    C1..C9 -->|fail| FIX[修复建议]
    C1..C9 -->|pass| OK[发布]""",
         "层覆盖率最复杂。"),
    ]
    modules.extend(core)
    body = render("Understand-Anything", "understand-anything-plugin/", modules)
    body += appendix_ua()
    return body


def appendix_codewhale() -> str:
    return """

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
"""


def appendix_harness() -> str:
    return """

# 附录 A — Strands 包地图

```mermaid
flowchart TB
    subgraph harness_py[strands_harness]
        CH[create_harness]
    end
    subgraph agent[strands.agent]
        AG[Agent]
    end
    subgraph loop[strands.event_loop]
        EL[event_loop_cycle]
    end
    subgraph io[strands.session / memory / tools]
        IO[持久化+工具]
    end
    CH --> AG
    AG --> EL
    AG --> IO
```

```mermaid
sequenceDiagram
    participant H as Harness App
    participant A as Agent
    participant M as MemoryManager
    participant S as SessionManager
    H->>A: prompt
    A->>M: inject
    A->>A: event_loop
    A->>S: snapshot
    A-->>H: result
```

**读图**：一次 invocation 内 Memory 注入在 loop 前；Session 在消息追加时写入。
"""


def appendix_sol_pi() -> str:
    return """

# 附录 A — 扩展与宿主事件矩阵

```mermaid
flowchart LR
    subgraph Events
        C[context]
        TR[tool_result]
        BP[before_provider_request]
        TE[turn_end]
        SC[session_compact]
    end
    OP[observation-pack] --> C
    ER[reducer] --> TR
    OC[online-compact] --> TE
    OC --> SC
    AF[action-fusion] --> TR
```

**读图**：同一事件可能被多个机制订阅；顺序以宿主 dispatch 为准。
"""


def appendix_ua() -> str:
    return """

# 附录 A — 流水线泳道

```mermaid
flowchart TB
    subgraph S1[扫描]
        PS[project-scanner]
    end
    subgraph S2[文件语义]
        FA[file-analyzer x N]
    end
    subgraph S3[架构]
        MG[merge]
        AA[architecture-analyzer]
    end
    subgraph S4[产品化]
        TB[tour-builder]
        GR[graph-reviewer]
    end
    subgraph S5[消费]
        DB[Dashboard]
    end
    PS --> FA --> MG --> AA --> TB --> GR --> DB
```

```mermaid
erDiagram
    SCAN ||--o{ BATCH : splits
    BATCH ||--o{ FILE_NODE : produces
    FILE_NODE ||--o{ SYMBOL_NODE : contains
    MERGED_GRAPH ||--o{ LAYER : organizes
    MERGED_GRAPH ||--o{ TOUR : explains
```

**读图**：泳道为时间顺序；ER 为产物结构（非全部边类型）。
"""


def render(title: str, src_root: str, modules: list) -> str:
    lines = [
        f"# {title} — Agent 模块级图集（细粒度）",
        "",
        f"> 源码根：`{src_root}` · 与 [DIAGRAM_ATLAS.md](./DIAGRAM_ATLAS.md)（全局图）配套。",
        f"> **每个重要 Agent 相关模块**至少 1 张图；复杂模块含流程 + 时序/类图。",
        "",
        "## 模块索引",
        "",
        "| ID | 模块 | 源码锚点 | 图类型 |",
        "|----|------|----------|--------|",
    ]
    for mid, name, anchor, typ, _, _ in modules:
        lines.append(f"| {mid} | {name} | `{anchor}` | {typ} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    for mid, name, anchor, typ, mermaid, note in modules:
        lines.append(f"## {mid} {name}")
        lines.append("")
        lines.append(f"**源码**：`{anchor}`")
        lines.append("")
        lines.append("```mermaid")
        lines.append(mermaid.strip())
        lines.append("```")
        lines.append("")
        lines.append(f"**读图**：{note}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    mapping = {
        "codewhale-architecture": codewhale(),
        "harness-sdk-architecture": harness(),
        "sol-pi-architecture": sol_pi(),
        "understand-anything-architecture": understand_anything(),
    }
    for folder, body in mapping.items():
        write(DOCS / folder / "diagrams" / "AGENT_MODULE_DIAGRAMS.md", body)


if __name__ == "__main__":
    main()
