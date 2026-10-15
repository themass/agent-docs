# Prime Agent 技术参考

> **主指南（是什么 / 为什么 / 怎么做）**：[ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md)  
> **归档全文**：[_archive/](./_archive/)（PART1–3、ENTITY、WALKTHROUGH 原稿）

---

## 目录

- [1. 三层真相模型](#1-三层真相模型)
- [2. JSONL 与 buildSessionContext](#2-jsonl-与-buildsessioncontext)
- [3. Daemon v7 协议要点](#3-daemon-v7-协议要点)
- [3.1 host.request（执行面）](#31-hostrequest执行面)
- [4. runAgentLoop 内层步骤](#4-runagentloop-内层步骤)
- [5. 实体关系图](#5-实体关系图)
- [6. 走查场景](#6-走查场景)
- [7. 源码速查](#7-源码速查)

---

## 1. 三层真相模型

```mermaid
flowchart TB
    subgraph A["① 权威：JSONL 树"]
        H["SessionHeader"]
        E["SessionEntry × N"]
        C["CompactionEntry"]
    end

    subgraph B["② 运行时：AgentState.messages"]
        M["Worker 内存工作集"]
    end

    subgraph C2["③ 视图：buildSessionContext()"]
        V["折叠后 messages[]"]
    end

    A -->|attach / load| B
    A --> C2
    C2 --> LLM["本轮 streamSimple"]
    B -->|append 同步| A
```

| 层 | 易错点 |
|----|--------|
| JSONL | **有** `parentId` 可分支；compaction **不删**旧行 |
| Turn 事件 | **无** turn_id 落盘；UI「一轮」≠ 表一行 |
| buildSessionContext | 每次 prompt **重新算**；与磁盘 messages 数组 **不同构** |

---

## 2. JSONL 与 buildSessionContext

### 2.1 Entry 类型（常见）

| type | 含义 |
|------|------|
| `message` | user / assistant / tool |
| `compaction` | 摘要节点 + cutoff 指针 |
| `custom` | Goals 等扩展状态 |

### 2.2 Compaction 在树上的位置

```mermaid
flowchart LR
    E1["entry: user"] --> E2["entry: assistant"]
    E2 --> E3["entry: tool…"]
    E3 --> CP["entry: compaction<br/>summary + cutoffId"]
    CP --> E4["entry: user 新轮"]
    E4 --> E5["…"]
```

**buildSessionContext 逻辑（概念）**：

```text
walk JSONL tree from root
  skip entries before latest compaction cutoff（或按策略折叠）
  merge Harness / Goals 片段到 system/developer
  return messages[] for runAgentLoop
```

### 2.3 attach / resume

```mermaid
sequenceDiagram
    participant C as Client
    participant D as Daemon
    participant W as Worker

    Note over C,W: 客户端断开后再连
    C->>D: attach(sessionId, lastGeneration?)
    D->>W: 确保 Worker 存活或拉起
    W->>W: load JSONL → AgentState.messages
    D-->>C: 重放 generation 之后的事件
    Note over C: UI 与 Worker 状态对齐
```

---

## 3. Daemon v7 协议要点

```mermaid
flowchart LR
    C["Client"] <-->|Unix socket / JSONL 行协议| D["DaemonSupervisor"]
    D -->|按 sessionId| W1["Worker A"]
    D -->|按 sessionId| W2["Worker B"]
```

| 概念 | 作用 |
|------|------|
| **generation** | 连接代次；attach 时对齐 |
| **sequence** | 事件单调序号；重放游标 |
| **steer** | 转发到 Worker → steeringQueue |
| **prompt** | 新 turn / follow-up |

**边界**：Daemon **不**跑 `runAgentLoop`、**不**开 Kernel。

→ 完整说明（含 capability、命令族、与 host.request 对照）：[**RUNTIME_BRIDGES.md**](./RUNTIME_BRIDGES.md)

### 3.1 host.request（执行面）

| 项 | 说明 |
|----|------|
| **形态** | Jupyter Comm target `"host.request"` |
| **方向** | Python cell → `KernelManager` → `AgentSession.dispatchHostRequest` |
| **用途** | 读/写文件、bash、`rlm.run` 子 Session、MCP、Goals 等特权 IO |
| **与 Daemon 关系** | Daemon = 客户端控制面；host.request = Worker 内 kernel↔TS，客户端不可见 |

```text
模型 ipython cell → 纯 Python 在 kernel
  → 需副作用时 host.request → TS 策略校验 → 结果回 cell → tool result
```

→ 时序、类型表、安全语义：[RUNTIME_BRIDGES.md §二](./RUNTIME_BRIDGES.md#二hostrequest)

---

## 4. runAgentLoop 内层步骤

```mermaid
flowchart TD
    START["进入 runAgentLoop"] --> STEER{"steeringQueue<br/>有消息?"}
    STEER -->|是| INJ["插入 steering user"]
    STEER -->|否| STREAM
    INJ --> STREAM["streamSimple"]
    STREAM --> TC{"tool_calls?"}
    TC -->|否| END["return"]
    TC -->|是| EXEC["AgentTool.execute<br/>（Prime: IPython）"]
    EXEC --> APPEND["append tool results"]
    APPEND --> ITER{"cur_iter < max?"}
    ITER -->|是| STEER
    ITER -->|否| END
```

| 参数 | 典型来源 |
|------|----------|
| `messages` | `buildSessionContext()` |
| `tools` | `[ipython]` + extensions |
| `getSteeringMessages` | `Agent.steeringQueue` drain |

**源码**：`packages/agent/src/agent/run-agent-loop.ts`（路径以仓库为准）

---

## 5. 实体关系图

```mermaid
erDiagram
    DaemonSupervisor ||--o{ WorkerProcess : manages
    WorkerProcess ||--|| AgentSessionRuntime : hosts
    AgentSessionRuntime ||--|| AgentSession : wraps
    AgentSession ||--|| SessionManager : persists
    AgentSession ||--|| Agent : runs
    AgentSession ||--o| KernelManager : kernel
    SessionManager ||--o{ SessionEntry : jsonl
    Agent ||--o{ AgentMessage : "state.messages"
    KernelManager ||--|| JupyterKernel : zmq

    DaemonSupervisor {
        pid int "守护主进程PID"
    }
    WorkerProcess {
        worker_id string "Worker进程ID"
    }
    AgentSessionRuntime {
        runtime_id string "运行时实例ID"
    }
    AgentSession {
        session_id string "会话唯一ID"
    }
    Agent {
        agent_id string "Agent实例ID"
    }
    AgentMessage {
        msg_id string "消息ID"
        role string "user/assistant/tool"
        content text "消息内容"
    }
    SessionEntry {
        snapshot_ts timestamp "快照时间"
    }
    KernelManager {
        zmq_endpoint string "zmq连接地址"
    }
    JupyterKernel {
        kernel_pid int "jupyter内核PID"
    }
```

---

## 6. 走查场景

### 6.1 场景 A：第二句话（同 Session 续聊）

```mermaid
sequenceDiagram
    participant U as 用户
    participant AS as AgentSession
    participant SM as SessionManager
    participant R as runAgentLoop

    Note over U,R: 第一句已写完 JSONL
    U->>AS: prompt("再加单元测试")
    AS->>SM: buildSessionContext（含历史）
    AS->>R: runAgentLoop
    R-->>AS: 完成
    AS->>SM: append 新 assistant/tool
```

### 6.2 场景 B：steer 中途改道

```text
Turn 进行中 → 用户 steer → steeringQueue
→ 当前 iter 结束 → drain steer 消息进 messages
→ 继续 stream（不新开 Session）
```

### 6.3 场景 C：rlm.run 子任务

```text
cell: out = rlm.run("扫描 TODO", timeout=120_000)
→ 子 Worker + 子 jsonl
→ 子 loop 完整执行
→ 返回字符串给 out
→ 父 Session 仅多一条 tool result
```

### 6.4 场景 D：auto-compact

```text
token 超阈值 → 插入 CompactionEntry
→ 下次 buildSessionContext 用摘要替代 cutoff 前内容
→ JSONL 原行仍在（审计）
```

→ 更细步骤见 [_archive/CORE_RUNTIME_WALKTHROUGH.md](./_archive/CORE_RUNTIME_WALKTHROUGH.md)

---

## 7. 源码速查

| 主题 | 路径（`prime-agent/` 下） |
|------|---------------------------|
| runAgentLoop | `packages/agent/src/` |
| AgentSession | `packages/coding-agent/src/` |
| SessionManager / JSONL | `packages/coding-agent/src/session/` |
| Daemon | `packages/coding-agent/src/daemon/` |
| KernelManager | `packages/coding-agent/src/kernel/` |
| rlm-runtime | `packages/coding-agent/src/rlm/` |
| goals | `packages/coding-agent/src/goals/` |
| Python rlm | `prime-agent-runtime/` |

---

**返回**: [ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md) · [README.md](./README.md)


---

## 2026 源码校准补充：当前 Rust 主线

> 以下为追加内容，前文完整保留作为历史设计。核对基线：`d592d5e7746408fe9097541af96d3239e263f7a1`（2026-10-15）。当前实现为 Rust workspace + Python runtime，不应把旧 TypeScript/Pi 模块名称直接当成当前源码路径。

### 后端契约与常量索引

| 契约 | 当前值/语义 | 源码 |
|---|---|---|
| daemon protocol/schema | 7 / 30 | `pa-types/src/daemon/mod.rs` |
| worker in-flight | 128 | `pa-daemon/src/backpressure.rs` |
| broadcast / targeted event queue | 各 4096 | 同上 |
| client outbound | 32768 response bundles | 同上，不是字节容量 |
| client dispatch concurrency | 64，读 socket 前控制并发 | 同上 |
| direct grant TTL / registration timeout | 10000ms / 3000ms | `peer_tickets.rs` |
| compaction reserve / keep recent | 16384 / 20000 tokens | `session_engine/compaction.rs` |
| threshold ratio / combined headroom floor | 0.95 / 4096 tokens | 同上 |

这些值是当前基线，不是跨版本 API 承诺。worker 饱和时 client request 得到 typed `worker_overloaded`；supervisor internal route 在自己的 timeout 内等待 slot。不能把所有满队列概括成“丢弃”或“无阻塞”。

### Session 数据关系

```mermaid
erDiagram
  SESSION ||--o{ ENTRY : contains
  ENTRY o|--o{ ENTRY : parent_of
  SESSION ||--o| GOAL_STATE : latest_custom_state
  SESSION ||--o{ COMPACTION_ENTRY : records
  SESSION ||--o{ BRANCH_LABEL : annotates
```

这是 JSONL 逻辑关系图，不代表关系数据库表。entry 的 id/parent_id 决定当前分支；goal state 使用 custom entry；compaction summary 与 first-kept boundary 重建模型窗口。`build_session_context` 带 visited set，避免沿损坏 parent 关系无限回溯。

### 持久化契约核对清单

- 普通 append：写失败回滚候选 entry，成功后更新窗口与索引。
- retained append：已进入 loop 的消息在写失败时保留内存，记录错误。
- first assistant 之前：部分 entry 延迟 flush；`flush_now` 提供显式落盘边界。
- rewrite：临时文件、write、sync、rename；不要从这一点推出所有平台的目录 fsync/掉电恢复已验证。
- lease：session ownership 具有 process-start identity；direct ticket 的 process identity 缺口是另一个边界，不应混为一谈。

### 建议补充的协议文档

字段升级规则、错误码和重试矩阵、partial replay 客户端降级、attach 与 stream 顺序、direct ticket 权限模型。源码实现了很多机制，但正式规范仍需把这些合同固定为可执行测试。
