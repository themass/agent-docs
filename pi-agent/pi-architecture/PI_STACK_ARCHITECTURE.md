# Pi 栈架构图（含 Prime 封装层）

> **读图方式**：**灰色 = Pi 各包固有能力**；**橙色 = Prime 产品封装**（在 `pi-coding-agent` + `prime-agent-runtime` 里实现）。  
> **效果对照**：[PI_AND_PRIME.md §4](../prime-agent-architecture/_archive/PI_AND_PRIME.md#4-prime-在-pi-之上封装了什么)

---

## 1. 总览：一张图看全栈

```mermaid
flowchart TB
    subgraph L0["L0 客户端 · pi-tui + modes"]
        TUI["TUI / ACP / RPC / JSON"]
        CONN["AgentConnection"]
    end

    subgraph L4P["L4 🟧 Prime 产品语义"]
        direction TB
        P_RLM["RLM · rlm.run() 子 Session"]
        P_GOL["Goals / Autonomous / Heartbeat"]
        P_HAR["Continual Harness · /refine"]
        P_BRAND["~/.prime 配置与发行"]
        P_PY["prime-agent-runtime Python"]
    end

    subgraph L3P["L3 🟧 Prime 封装在 pi-coding-agent"]
        direction TB
        P_DM["DaemonSupervisor · 协议 v7"]
        P_WK["Session Worker · AgentSessionRuntime"]
        P_SM["SessionManager · JSONL 树"]
        P_KM["KernelManager"]
        P_IPY["IPython 主工具 + host.request"]
        P_CMP["Compaction · Extensions"]
        P_RLMH["rlm-runtime host"]
    end

    subgraph L2["L2 Pi 心脏 · pi-agent-core"]
        AG["Agent · 外环 runLoop"]
        RAL["runAgentLoop · 内环"]
        SQ["steeringQueue"]
        FQ["followUpQueue"]
        AT["AgentTool.execute 抽象"]
    end

    subgraph L1["L1 Pi 协议 · pi-ai"]
        MSG["AgentMessage / Provider Message"]
        STR["streamSimple"]
        PRV["多 Provider"]
    end

    TUI --> CONN
    CONN --> P_DM
    P_DM --> P_WK
    P_WK --> P_SM
    P_WK --> AG
    AG --> RAL
    RAL --> STR
    STR --> PRV
    RAL --> AT
    AT --> P_IPY
    P_IPY --> P_KM
    P_KM --> P_PY
    P_PY --> P_RLMH
    P_RLMH --> P_RLM
    P_WK --> P_GOL
    P_WK --> P_HAR
    P_SM --> P_CMP
    SQ --> RAL
    FQ --> AG
```

### 图例

| 标记 | 含义 | 能否单独 `npm install` 嵌入 |
|------|------|------------------------------|
| **L1–L2 灰底** | **Pi 循环与 LLM 协议** | ✅ `pi-ai` + `pi-agent-core` 即可跑 loop |
| **L3 橙底** | **coding-agent 产品壳**（Prime 默认全开） | 需 `pi-coding-agent` |
| **L4 橙底** | **Prime Intellect 产品决策** | 同仓库 + Python runtime |

---

## 2. 封装边界：Prime 能力画在 Pi 哪一层上

**这是你问的「Prime 封装了什么」在架构图上的落点：**

```mermaid
flowchart LR
    subgraph PI_CORE["pi-agent-core（Pi 不提供以下任何一项）"]
        direction TB
        C1["stream ↔ tool"]
        C2["steer / followUp 队列"]
    end

    subgraph PI_CODING["pi-coding-agent + Prime"]
        direction TB
        subgraph P_PROC["🟧 进程"]
            D["Daemon"]
            W["Worker"]
        end
        subgraph P_STATE["🟧 状态"]
            J["JSONL Session 树"]
            B["buildSessionContext"]
        end
        subgraph P_EXEC["🟧 执行"]
            K["KernelManager"]
            I["IPython tool"]
            H["host.request"]
        end
        subgraph P_MULTI["🟧 多 Agent"]
            R["rlm.run → 子 Session"]
        end
        subgraph P_LONG["🟧 长期运行"]
            G["Goals"]
            A["Autonomous"]
            F["Harness /refine"]
        end
        AS["AgentSession 编排"]
    end

    PI_CORE --> AS
    AS --> P_PROC
    AS --> P_STATE
    AS --> P_EXEC
    AS --> P_MULTI
    AS --> P_LONG
```

| 你听到的名词 | 在图上位置 | Pi 有没有 | Prime 加了什么 **效果** |
|--------------|------------|-----------|-------------------------|
| **Daemon** | L3 `P_DM` | ❌ | 后台门卫；**关 UI 会话还在**；attach 重放 |
| **Worker** | L3 `P_WK` | ❌ | 一会话一间办公室；**loop 不在 TUI 进程** |
| **IPython** | L3 `P_IPY` | ❌（可有别的 tool） | **单主工具**；状态在变量里 |
| **KernelManager** | L3 `P_KM` | ❌ | 真 Jupyter 进程；注入 `rlm` |
| **RLM** | L3 `P_RLMH` + L4 `P_RLM` | ❌ | cell 里 `rlm.run()` → **子 Session** |
| **Goals** | L4 `P_GOL` | ❌ | **跨多轮总目标**，不是单句 prompt |
| **steer** | L2 `SQ` | ✅ **Pi 原生** | Prime 用 Daemon `steer` **注入**该队列 |
| **runAgentLoop** | L2 `RAL` | ✅ **Pi 原生** | Prime 在 Worker 里 **调用**它 |

---

## 3. 双环：Pi 心脏在图中的位置

Prime 所有「办公室 / 笔记本 / 隔间」都 **包在** 这对环外面。

```mermaid
flowchart TB
    subgraph OUTER["外环 · Agent（pi-agent-core）"]
        direction TB
        O1["prompt() 入口"]
        O2["followUpQueue · turn 结束后还跑吗"]
        O3["state.messages 内存"]
    end

    subgraph INNER["内环 · runAgentLoop（pi-agent-core）"]
        direction TB
        I1["streamSimple（pi-ai）"]
        I2["tool_calls"]
        I3["steeringQueue · turn 内插队"]
        I4["cur_iter / max_iters"]
    end

    subgraph PRIME_WRAP["🟧 Prime 包裹层（AgentSession）"]
        direction TB
        W1["每次 prompt 前 buildSessionContext"]
        W2["事件流 → append JSONL"]
        W3["工具面配置为 IPython"]
        W4["Daemon generation/sequence"]
    end

    O1 --> PRIME_WRAP
    PRIME_WRAP --> INNER
    INNER --> I2
    I2 --> W3
    I3 -.->|Daemon steer| I1
    INNER --> O2
```

| 环 | 回答的问题 | 没有 Prime 时 |
|----|------------|----------------|
| **内环** | 这一轮里：采样 → 工具 → 要否 steer？ | 同进程 SDK 照样转 |
| **外环** | 这一轮结束后：还有 follow-up 吗？ | 同左 |
| **🟧 包裹层** | 记在哪、谁持久跑、用什么工具、子任务怎么拆？ | **不存在** → 只是内存 loop |

---

## 4. 运行时数据流（同一张图的「动」）

用户发一句 `prompt` 时，**数据**经过哪些层（对照上图编号）：

```mermaid
sequenceDiagram
    participant L0 as L0 Client
    participant L3D as L3 Daemon
    participant L3W as L3 Worker/AgentSession
    participant L3S as L3 SessionManager
    participant L2 as L2 runAgentLoop
    participant L3K as L3 Kernel/IPython
    participant L4 as L4 rlm Python

    L0->>L3D: prompt
    L3D->>L3W: 路由 session
    L3W->>L3S: buildSessionContext JSONL→messages
    L3W->>L2: runAgentLoop
    L2->>L2: stream LLM
    L2->>L3K: ipython cell
    opt 子任务
        L3K->>L4: rlm.run()
        L4->>L3W: spawn 子 Session
        L3W->>L2: 子 loop
        L4-->>L3K: 摘要结果
    end
    L3K-->>L2: tool result
    L2-->>L3W: AgentEvent
    L3W->>L3S: append JSONL
    L3W-->>L3D: generation events
    L3D-->>L0: SSE/JSONL 流
```

---

## 5. 两种用法：图上剪哪一层

```mermaid
flowchart TB
    subgraph MODE_A["模式 A · 仅 Pi SDK"]
        A1["pi-ai"]
        A2["pi-agent-core"]
        A3["你的 App 自己持久化"]
        A1 --> A2 --> A3
    end

    subgraph MODE_B["模式 B · Prime 产品（默认）"]
        B1["pi-ai"]
        B2["pi-agent-core"]
        B3["pi-coding-agent 全 L3"]
        B4["Prime L4 + runtime"]
        B1 --> B2 --> B3 --> B4
    end
```

| | **模式 A** | **模式 B（Prime）** |
|--|------------|---------------------|
| **典型入口** | `new Agent(); agent.prompt()` | `AgentConnection.prompt()` → Daemon |
| **持久化** | 你自己 | JSONL 树 + compaction |
| **工具** | 任意 `AgentTool[]` | **IPython 主路径** |
| **子 Agent** | 你自己编排 | `rlm.run()` |
| **提升** | 轻、可嵌入 | **长时 coding + 可重连 + 可审计** |

---

## 6. 包 ↔ 图层对照（改代码时用）

| npm 包 | 图层 | 核心类型 |
|--------|------|----------|
| `pi-tui` | L0 | TUI 组件 |
| `pi-ai` | L1 | `streamSimple`, `Message` |
| `pi-agent-core` | L2 | `Agent`, `runAgentLoop`, queues |
| `pi-coding-agent` | L3 🟧 | `AgentSession`, `Daemon`, `Kernel`, `SessionManager` |
| `prime-agent-runtime` | L4 🟧 | `rlm`, `harness`（Python） |

构建顺序：`tui` → `ai` → `agent` → `coding-agent`。

---

## 7. 延伸阅读

| 主题 | 文档 |
|------|------|
| Prime 封装六决策（文字） | [PI_AND_PRIME §4](../prime-agent-architecture/_archive/PI_AND_PRIME.md) |
| Agent vs AgentSession 表 | [PI_AND_PRIME §5](../prime-agent-architecture/_archive/PI_AND_PRIME.md) |
| 源码目录树 | [ARCHITECTURE_PART1 §1.2.5](../prime-agent-architecture/_archive/ARCHITECTURE_PART1.md) |
| 跨项目 steer 对照 | [CROSS_AGENT_CONCEPT_MAP](../agent-doc-template/CROSS_AGENT_CONCEPT_MAP.md) |
| 九幕设计思想 | [DESIGN_THINKING_SERIES](../pi-agent/DESIGN_THINKING_SERIES.md) |
