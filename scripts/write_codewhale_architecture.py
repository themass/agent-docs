#!/usr/bin/env python3
"""Generate docs/codewhale-architecture/ARCHITECTURE.md (rich diagrams, no external doc refs)."""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "codewhale-architecture" / "ARCHITECTURE.md"

CONTENT = r'''# Codewhale 架构设计文档

> **范围**：`Codewhale/` Rust workspace（TUI、`exec`、Runtime API、Fleet）  
> **阅读顺序**：Part I 建立整体地图 → Part II 按模块对照源码  
> **图解导读**：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)  
> **上游产品文档**：`Codewhale/docs/`（ARCHITECTURE、AGENT_RUNTIME、MODES、CACHE）

---

## 文档结构

| 部分 | 内容 |
|------|------|
| **Part I** | 总体框架、整体设计、类图、端到端与时序、Session/权限/Memory |
| **Part II** | 核心模块：关系图、内部流程、模块级时序与说明 |

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架)
- [I.1 产品是什么、能做什么](#i1-产品是什么能做什么)
- [I.2 整体设计：分层与 Crate 边界](#i2-整体设计分层与-crate-边界)
- [I.3 核心实体与完整类图](#i3-核心实体与完整类图)
- [I.4 子系统协作图](#i4-子系统协作图)
- [I.5 端到端流程与时序（详细）](#i5-端到端流程与时序详细)
- [I.6 Session、Checkpoint、Thread](#i6-sessioncheckpointthread)
- [I.7 Memory 与 Compaction](#i7-memory-与-compaction)
- [I.8 权限、模式与沙箱](#i8-权限模式与沙箱)
- [I.9 子 Agent 与 Fleet](#i9-子-agent-与-fleet)
- [I.10 运行时不变量](#i10-运行时不变量)

## Part II 目录

1. [模块：`Engine` 与 `run_turn`](#1-模块engine-与-run_turn)
2. [模块：`turn_loop` 内层状态机](#2-模块turn_loop-内层状态机)
3. [模块：`session` 与上下文重建](#3-模块session-与上下文重建)
4. [模块：`core` 请求拼装](#4-模块core-请求拼装)
5. [模块：`execpolicy` 与 `authority`](#5-模块execpolicy-与-authority)
6. [模块：工具执行与 LSP](#6-模块工具执行与-lsp)
7. [模块：流式 `client` 与 tool JSON](#7-模块流式-client-与-tool-json)
8. [端到端示例：修失败测试](#8-端到端示例修失败测试)

---

# Part I · 高层架构

## I.0 总体框架

Codewhale 是 **终端优先的编码 Agent**：在仓库目录中用自然语言驱动模型 **读代码、改文件、跑命令、根据输出继续推进**。所有用户入口最终进入 **同一条** `Engine::run_turn`（`crates/tui/src/core/engine/turn_loop.rs`）；`crates/core` **只负责**把「这一轮发给模型的字节」拼好，**不拥有**「何时再调模型」的循环逻辑。

**一句话**：呈现层（TUI / `exec` / HTTP / Fleet） + **Engine** + **Session 账本** + **execpolicy** + **模型与工具能力**。

### I.0.1 逻辑分层

```mermaid
flowchart TB
    subgraph L0["L0 · 入口"]
        TUI["TUI 作曲框"]
        EXEC["codewhale exec"]
        HTTP["runtime_api HTTP/SSE"]
        FLEET["Fleet / Lane 选人"]
    end

    subgraph L1["L1 · 引擎"]
        ENG["Engine 状态机"]
        RT["run_turn / turn_loop"]
        TC["TurnContext"]
    end

    subgraph L2["L2 · 策略与状态"]
        SESS["Session 热路径"]
        AUTH["authority"]
        POL["execpolicy"]
        CK["checkpoint"]
    end

    subgraph L3["L3 · 能力与协议"]
        TOOL["tools + MCP"]
        CORE["core: PrimaryTurnRequest"]
        CLI["client.rs 流式"]
        MOD["models"]
    end

    subgraph L4["L4 · 持久化"]
        ST["state SQLite / Thread"]
        TASK["task_manager"]
        SNAP["side-git snapshot"]
    end

    L0 --> ENG
    ENG --> RT
    RT --> TC
    RT --> SESS & AUTH & POL
    RT --> TOOL & CORE
    CORE --> CLI --> MOD
    RT --> CK & ST & TASK & SNAP
    FLEET --> EXEC
    EXEC --> ENG
    HTTP --> ENG
    TUI --> ENG
```

**读图要点**

- **L1** 是产品心脏：一次用户回合（Turn）可包含 **多次** 模型↔工具往返，但预算、steer、工具计数在 **同一个** `run_turn` 内结算。  
- **L2** 的 Session 是拼请求用的热数据；**L4** 的 SQLite/checkpoint 服务恢复与线程元数据，不等于「模型看见的全文」。  
- **Fleet** 不实现第二套 loop：它选人/配置，执行仍落到 Runtime worker 的 `run_turn`。

### I.0.2 运行时对象图（一次 `run_turn` 期间）

```mermaid
classDiagram
    direction TB

    class Engine {
        +handle_op(Op)
        +run_turn(TurnContext, policy)
        -session: Session
        -model_client
        -config
    }

    class TurnContext {
        +id: TurnId
        +client: ModelClient
        +tool_policy
        +pending_steers
    }

    class Session {
        +messages
        +usage: Usage
        +tool_activation_cache
        +working_set
        +prefix_stability
    }

    class Thread {
        +id
        +status
        +goal?
    }

    class PrimaryTurnRequest {
        +frozen_prefix
        +append_messages
    }

    class ToolExecutionPlan {
        +plans
        +hook_contexts
        +batch_sandbox_policy
    }

    class ExecPolicy {
        +resolve_permission()
        +ApprovalMode
    }

    class ModelClient {
        <<trait>>
        +stream()
    }

    Engine *-- Session
    Engine --> TurnContext : 每 turn 创建/绑定
    Engine --> run_turn
    TurnContext --> ToolExecutionPlan
    TurnContext --> ExecPolicy
    TurnContext --> ModelClient
    run_turn ..> PrimaryTurnRequest : core 拼装
    run_turn ..> ModelClient : 流式
    Session --> Thread : 身份/恢复
```

**读图要点**

- **Engine** 消化 UI/CLI 的 `Op`（用户句、审批结果、模式切换等），在 `run_turn` 里驱动模型与工具。  
- **TurnContext** 承载 **本轮** 临时状态；跨 turn 的对话内容在 **Session.messages** 里累积。  
- **ToolExecutionPlan** 是「模型意图」到「可执行批」的边界对象；权限在 plan 之后、执行之前再次收敛。

### I.0.3 三条主数据通路

| 通路 | 方向 | 载荷 | 关键模块 |
|------|------|------|----------|
| **用户 IO** | 人 → TUI/exec/API | 文本、审批、斜杠命令 | `repl`、`cli`、`runtime_api` |
| **推理环** | run_turn → client → 模型 | FrozenPrefix + Append messages → 流式 assistant/tool | `turn_loop`、`core`、`client.rs` |
| **副作用环** | tool → Session | tool result、LSP 合成 user、usage | `tool_execution`、`session.rs`、`lsp_hooks` |
| **恢复环** | checkpoint / state | 发请求前快照、Thread 元数据 | `checkpoint`、`crates/state` |

---

## I.1 产品是什么、能做什么

**是什么**：跨平台 CLI + 全屏 TUI；可选无头 `codewhale exec`、HTTP `serve`、多 Agent Fleet。连接 hosted 或本地模型，在真实仓库上产生 **可审计的副作用**（写文件、shell）。

**能做什么（典型）**

- 修测试 / 修 bug：跑测试 → 读失败 → 改代码 → 再验证 → 文字说明变更。  
- Plan 探查后 Work 落地：`/mode plan` 禁止写盘与危险 shell，确认方案后 `/mode work`。  
- CI/脚本：`codewhale exec`，机器可读 stream-json。  
- 长任务与多角色：Fleet 选不同 Agent 配置，共享 Runtime 语义。  
- 扩展：MCP、Skills、shell hooks，不 fork 主循环。

**怎么工作（用户视角）**：你给出目标句 → 引擎循环「模型提议工具 → 审批/沙箱 → 执行 → 结果入账 → 再问模型」直到完成或你中断。

---

## I.2 整体设计：分层与 Crate 边界

### I.2.1 Crate 依赖（编译期）

```mermaid
flowchart LR
    CLI[crates/cli] --> TUI[crates/tui]
    TUI --> CORE[crates/core]
    TUI --> POL[crates/execpolicy]
    TUI --> STATE[crates/state]
    TUI --> MODELS[crates/models]
    TUI --> MCP[crates/mcp]
    TUI --> MEM[crates/memory]
    TUI --> PROTO[crates/protocol]
    RUNTIME[crates/runtime] -.拆分中.-> TUI
```

| Crate | 职责 | 明确不是 |
|-------|------|----------|
| `cli` | 二进制门面、auth/update；run/exec 进 tui | turn loop |
| `tui` | UI + **唯一** `run_turn` + 工具实现 | 纯展示（含引擎） |
| `core` | `prepare_primary_turn_request`、Thread 类型、parser | agent loop |
| `execpolicy` | 规则、审批、sandbox 决策 | UI |
| `state` | SQLite thread/session | 模型 prompt 全文 |
| `protocol` | Thread RPC、EventFrame | — |

### I.2.2 运行时调用关系（文字）

```text
TUI / exec / HTTP
  → engine.rs 处理 Op
  → run_turn (turn_loop.rs)
        → session 读/写 messages
        → core 拼 PrimaryTurnRequest
        → client.rs 流式
        → plan_tool_calls → authority/execpolicy
        → tool_execution + lsp_hooks
        → 循环或 TurnOutcomeStatus
```

---

## I.3 核心实体与完整类图

| 实体 | 职责 |
|------|------|
| `Engine` | 总状态机；连接 UI 事件与 `run_turn` |
| `TurnContext` | 单 turn 的 client、policy、steer、度量 |
| `Session` | messages、usage、ToolActivationCache、WorkingSet、前缀稳定性 |
| `Thread` | 可 resume/fork 的会话身份 |
| `StreamOutcome` | 单次流式累积：text、thinking、tool_use、pending_steers |
| `ToolCallSource` | `Model` 直接 tool_use vs `CodeMode` 嵌套 `execute_tools` |
| `ToolActivationCache` | `tool_search` 激活的延迟 schema（≤8 名 / 16KB） |
| `PendingSteer` | 流中途用户插入；消息边界提交 |

（类图见 I.0.2；与源码字段以 `session.rs`、`turn_loop.rs` 为准。）

---

## I.4 子系统协作图

```mermaid
flowchart LR
    subgraph Entry
        A[TUI]
        B[exec]
        C[HTTP turn]
        D[Fleet worker]
    end
    E[Engine::run_turn]
    Entry --> E
    E --> S[Session]
    E --> C2[core 拼请求]
    E --> M[模型 API]
    E --> P[execpolicy]
    E --> T[tools/MCP]
    T --> LSP[LSP 诊断]
    LSP --> S
    S --> C2
    E --> DB[state/checkpoint]
```

**说明**：LSP 诊断不钉进 FrozenPrefix，而作为 **Append 段** 的合成 user 消息进入 Session，保证模型看见诊断且前缀仍可缓存（见 `Codewhale/docs/CACHE.md`）。

---

## I.5 端到端流程与时序（详细）

### I.5.1 用户 Turn 总览（活动图）

```mermaid
flowchart TB
    START([用户输入 / Op]) --> CKPT[写 checkpoint latest]
    CKPT --> PREP[prepare_primary_turn_request]
    PREP --> STREAM[process_stream 流式模型]
    STREAM --> HAS_TOOL{tool_use?}
    HAS_TOOL -->|否| END_TURN{end_turn?}
    END_TURN -->|是| STOP([Turn 结束])
    END_TURN -->|否| STREAM
    HAS_TOOL -->|是| PLAN[plan_tool_calls]
    PLAN --> PERM[resolve_tool_permission]
    PERM --> DENY{拒绝/Ask?}
    DENY -->|Ask 未批| WAIT[等待用户审批]
    WAIT --> PERM
    DENY -->|允许| EXEC[execute_planned_tools]
    EXEC --> RESULT[process_tool_results + LSP]
    RESULT --> APPEND[Session 入账]
    APPEND --> STREAM
```

**读图说明**：这是一个 **用户 Turn** 内的循环，不是「一次 HTTP = 一次图」。`ToolCallBudget`、墙钟 `TurnWallClock`、连续空块等退出条件在 `run_turn` 各分支实现（见 Part II §1–§2）。

### I.5.2 时序：TUI 与 `exec` 共用内核

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant E as Engine
    participant CK as checkpoint
    participant S as Session
    participant C as core
    participant L as client/LLM
    participant P as execpolicy
    participant T as tools
    participant H as shell hooks

    U->>E: 用户任务句
    E->>CK: 发送前 latest.json
    E->>S: 读历史 + revalidate tool cache
    E->>C: prepare_primary_turn_request
    Note over C,S: FrozenPrefix = BASE_PROMPT + 工具目录<br/>Append = 历史 + 用户句
    C->>L: 流式请求
    L-->>E: assistant 增量 + tool_use
    E->>P: resolve_tool_permission(每个 tool)
    alt Ask 且未批准
        E-->>U: 审批 UI / stream-json 事件
        U->>E: 批准/拒绝
    end
    E->>H: pre hooks
    E->>T: sandbox 内执行
    E->>H: post hooks
    E->>S: tool observation 入账
    opt 写/改文件
        E->>E: LSP flush → 合成 user 消息
        E->>S: 入账诊断
    end
    E->>C: 下一轮 Append 含 observation
    C->>L: 再请求
    L-->>E: 终稿或更多 tool
    E->>CK: 成功则清除 checkpoint
    E-->>U: 完成 / 事件流结束
```

**读图说明（按序号）**

1. **checkpoint** 在「即将发模型」前写入，崩溃后可从该点恢复，与 Session 全量历史不同。  
2. **FrozenPrefix** 不含「当前失败测试名」等瞬态事实；失败栈应作为 **tool 结果** 进入 Append。  
3. **审批** 发生在计划层与执行层之间；Plan 模式在 plan 层即拒副作用。  
4. **LSP** 在文件变更后可能改变 **下一轮** 可见上下文，但不破坏前缀缓存策略。  
5. 同一 `run_turn` 可重复 11–15 步直到无 tool 或触发 stop 条件。

---

## I.6 Session、Checkpoint、Thread

| 概念 | 作用 | 常见误解 |
|------|------|----------|
| **Session（内存）** | 当前对话 messages、usage、cache | 等于磁盘全部列 |
| **Thread / SQLite** | 线程身份、元数据、恢复 | 等于发给模型的 prompt |
| **checkpoint** | 发模型前的轻量恢复点 | 等于会话归档 |

**不变量**：模型下一轮看到的内容，必须能从 **Session 账本** 重建。换会话必须 `ToolActivationCache::clear()`。

---

## I.7 Memory 与 Compaction

| 能力 | 用户感知 | 模块 |
|------|----------|------|
| 长对话压缩 | 上下文变短 | `tui/src/compaction/` |
| Purge | 主动删改历史片段 | `purge.rs` |
| memory + remember | 结构化记忆库 | `crates/memory` |

三者正交：分别解决 **长度**、**外科式历史编辑**、**结构化事实**；不要混为一个「记忆开关」。

---

## I.8 权限、模式与沙箱

| 姿态 | 行为 |
|------|------|
| Ask | 高风险 tool 停住等人批 |
| Auto-Review | 策略 + Guardian 自动裁决部分 |
| Full Access | 仍受 deny 规则与 sandbox |
| `/mode plan` | 拒写盘与危险 shell（非第二 loop） |
| `/mode work` | 允许副作用，同一 Session 继续 |

决策链：`resolve_tool_permission` → execpolicy 规则层 → sandbox 执行包装 → shell hooks 可改变 gate 结果。

---

## I.9 子 Agent 与 Fleet

- **Fleet**：身份、资格、Lane 上的任务归属。  
- **Runtime worker**：无头环境执行 **同一** `run_turn`。  
- **`agent` 工具**：模型启动子任务；父 UI 见摘要与计数，不默认灌入子全 transcript。  

详见 `Codewhale/docs/AGENT_RUNTIME.md`。

---

## I.10 运行时不变量

1. 仅在 `turn_loop` 实现 agent loop；`crates/core/tests/single_turn_loop.rs` 守卫。  
2. 新上下文必须声明：FrozenPrefix vs Append-only。  
3. 延迟工具经 `tool_search` + cache 上限；换会话 clear cache。  
4. 子 Agent 终态与 durable worker 同形。

---

# Part II · 模块设计

## 1. 模块：`Engine` 与 `run_turn`

**位置**：`crates/tui/src/core/engine.rs`、`turn_loop.rs`（`run_turn` @ ~L896）

### 1.1 模块在整体中的位置

```mermaid
flowchart TB
    OP[Op 队列] --> ENG[Engine::handle_op]
    ENG --> RT[run_turn]
    RT --> EV[Event 回 TUI/exec]
```

### 1.2 `run_turn` 入口职责（说明）

进入 `run_turn` 时：启动 `TurnWallClock`；`tool_activation_cache.revalidate`；初始化 `ToolCallBudget`；可选 `FleetDenialGuard`；然后进入 **model↔tool** 循环直到 `TurnOutcomeStatus`。

---

## 2. 模块：`turn_loop` 内层状态机

### 2.1 内层循环（逻辑）

```mermaid
stateDiagram-v2
    [*] --> Streaming
    Streaming --> Planning: message 完整
    Planning --> Permission: 有 tool_use
    Permission --> Executing: 允许
    Permission --> Streaming: Ask 等待后 / 拒绝处理
    Executing --> Results: 工具完成
    Results --> Streaming: 继续本 turn
    Results --> [*]: 无更多 tool / stop
    Streaming --> [*]: end_turn 无 tool
```

### 2.2 关键子过程时序（单步 model→tool）

```mermaid
sequenceDiagram
    participant RT as run_turn
    participant PS as process_stream
    participant PL as plan_tool_calls
    participant EX as execute_planned_tools
    participant PR as process_tool_results

    RT->>PS: 流式直到 assistant 完整
    PS-->>RT: StreamOutcome
    RT->>PL: Model 或 CodeMode 源
    PL-->>RT: ToolExecutionPlan
    RT->>EX: batch + sandbox
    EX-->>RT: ToolResult[]
    RT->>PR: 入账 + LSP 排队
    PR-->>RT: Session 更新
```

**说明**

- **`process_stream`**：处理 steer 边界、chunk 超时、reasoning-only/empty-stop 有限重试。  
- **`plan_tool_calls`**：allowed/disallowed tools、Plan 模式、hook_gate。  
- **CodeMode** 嵌套调用必须与 Model 源共用 permission gate。

---

## 3. 模块：`session` 与上下文重建

**位置**：`crates/tui/src/core/session.rs`

```mermaid
flowchart LR
    MSG[messages 追加] --> SESS[Session]
    CACHE[ToolActivationCache] --> SESS
    WS[WorkingSet] --> SESS
    PST[PrefixStabilityManager] --> SESS
    SESS --> CORE[prepare_primary_turn_request]
```

**ToolActivationCache 规则**：LRU ≤8 名、schema ≤16KB；`SyncSession` 必须 `clear()`；每 turn `revalidate(catalog)`。

---

## 4. 模块：`core` 请求拼装

**职责**：`prepare_primary_turn_request` 产出 **FrozenPrefix**（system + 稳定工具目录）与 **Append**（历史、tool 结果、合成 user）。

```mermaid
flowchart TB
    SP[BASE_PROMPT + 工具目录] --> FP[FrozenPrefix]
    HIST[Session.messages] --> AP[Append 段]
    FP --> REQ[PrimaryTurnRequest]
    AP --> REQ
    REQ --> CLIENT[client.rs]
```

**禁止**：把易变事实 splice 进 FrozenPrefix（见 CACHE 文档）。

---

## 5. 模块：`execpolicy` 与 `authority`

```mermaid
flowchart TB
    TU[tool_use] --> AUTH[authority.rs]
    AUTH --> RS[Ruleset 层叠]
    RS --> MODE[ApprovalMode]
    MODE --> SB[sandbox 包装]
    SB --> RUN[handler 执行]
```

| 层 | 内容 |
|----|------|
| BuiltinDefault | 基线 |
| Agent | 角色规则 |
| User | 用户 toml |
| denied_prefixes | 硬拒 |

---

## 6. 模块：工具执行与 LSP

```mermaid
sequenceDiagram
    participant PL as plan
    participant PRE as pre hooks
    participant SB as sandbox
    participant H as handler
    participant POST as post hooks
    participant LSP as lsp_hooks
    participant S as Session

    PL->>PRE: 每 tool
    PRE->>SB: 包装执行
    SB->>H: 实际副作用
    H->>POST: 结果
    POST->>S: observation
    opt 修改文件
        H->>LSP: 排队诊断
        LSP->>S: 下次请求前合成 user
    end
```

**十步管线（概念）**：tool_use → registry → pre → 审批 → sandbox → 执行 → post → metadata → LSP → flush 合成 user → 回 loop。

---

## 7. 模块：流式 `client` 与 tool JSON

- 流式累积 tool 参数 JSON → `finalize_streamed_tool_input`  
- `StreamOutcome` 与 `ToolUseState` 在 `turn_loop` / `client` 协作  
- 协议完整但无可见内容时走 empty/reasoning-only 恢复路径（有预算上限）

---

## 8. 端到端示例：修失败测试

**场景**：`tests/test_app.py` 失败；用户：`修失败测试并解释改了什么`。

叙述要点：

1. `exec` 或 TUI 同一 `run_turn`。  
2. 第一次模型调用 → `bash pytest` → 栈入账（不进 system 前缀）。  
3. 第二次 → `edit` → LSP 可能追加 diagnostic user。  
4. 再 `pytest` → 通过后自然语言总结。  
5. checkpoint 清除；可选 snapshot。

（与 I.5.2 时序图序号对应，便于对照源码断点调试。）

---

**文档完** · 改引擎从 Part II §1–§2 起 · 改权限从 §5 · 改上下文从 §3–§4
'''

def main():
    OUT.write_text(CONTENT.strip() + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(CONTENT.splitlines())} lines)")


if __name__ == "__main__":
    main()
