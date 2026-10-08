#!/usr/bin/env python3
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]

HARNESS = r'''# Strands Harness SDK（Python）架构设计文档

> **范围**：`harness-sdk/strands-py` + `harness-py`  
> **导读**：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架)
- [I.1 产品说明](#i1-产品说明)
- [I.2 分层与包边界](#i2-分层与包边界)
- [I.3 类图与实体](#i3-类图与实体)
- [I.4 端到端时序](#i4-端到端时序)
- [I.5 Session / Memory / Context](#i5-session--memory--context)

## Part II 目录

1. [`event_loop_cycle`](#1-模块event_loop_cycle)
2. [`Agent.__call__`](#2-模块agent__call__)
3. [`create_harness`](#3-模块create_harness)
4. [Interventions 与 Sandbox](#4-interventions-与-sandbox)

---

# Part I

## I.0 总体框架

**Harness** 是在 Strands SDK 上的 **默认装配层**：`create_harness()` 提供编码向模型、工具、本地 session、memory 注入、context offloader、subagent。**循环唯一实现在** `strands/event_loop/event_loop.py` 的 `event_loop_cycle`；Harness **不包含**第二套 while。

### I.0.1 分层

```mermaid
flowchart TB
    subgraph L0["L0"]
        CH[create_harness]
        APP[应用 agent 调用]
    end
    subgraph L1["L1 循环"]
        EL[event_loop_cycle]
        REC[recurse_event_loop]
    end
    subgraph L2["L2 能力"]
        TR[ToolRegistry]
        SM[SessionManager]
        MM[MemoryManager]
        CM[ContextManager]
        PL[Plugins]
    end
    subgraph L3["L3 模型"]
        MD[Model / Router]
    end
    L0 --> APP --> EL --> REC
    EL --> TR & SM & MM & CM & PL --> MD
```

### I.0.2 类图（运行时）

```mermaid
classDiagram
    class Agent {
        +__call__(prompt)
        +session_manager
        +memory_manager
        +tool_registry
    }
    class EventLoop {
        +event_loop_cycle()
        +recurse_event_loop()
    }
    class SessionManager {
        +initialize()
        +append_message()
        +sync_agent()
    }
    class MemoryManager {
        +search_memory()
        +injection
    }
    Agent --> EventLoop
    Agent *-- SessionManager
    Agent *-- MemoryManager
```

---

## I.1 产品说明

**是什么**：可嵌入的 Python Agent SDK + 「电池 included」的 `create_harness` 工厂。  
**能做什么**：仓库编码任务、跨会话 memory、大 tool result offloader、审批策略、后台 subagent。  
**怎么做**：`agent("…")` → BeforeInvocation → 若干 **cycle**（模型→工具→recurse）→ AfterInvocation → Session sync。

---

## I.2 分层与包边界

| 路径 | 职责 |
|------|------|
| `strands/agent/agent.py` | Agent 门面 |
| `strands/event_loop/event_loop.py` | **唯一 cycle** |
| `strands_harness/agent.py` | 默认装配，无 loop |

---

## I.3 类图与实体

见 I.0.2。`invocation_state.request_state` **跨 cycle**；`event_loop_cycle_id` 用于取消与追踪。

---

## I.4 端到端时序

```mermaid
sequenceDiagram
    autonumber
    participant A as 应用
    participant AG as Agent
    participant EL as event_loop_cycle
    participant M as Model
    participant T as Tools
    participant SM as SessionManager

    A->>AG: __call__(prompt)
    AG->>AG: BeforeInvocationEvent
    loop 每个 cycle
        AG->>EL: 驱动生成器
        EL->>M: 流式或跳过模型
        M-->>EL: tool_use
        EL->>T: execute
        T-->>EL: results
        EL->>EL: recurse_event_loop
    end
    AG->>SM: sync_agent
    AG-->>A: AgentResult
```

**读图说明**：Limits 在 **cycle 顶**检查；checkpoint 可在 `after_model`/`after_tools` 停住 invocation 供恢复。

---

## I.5 Session / Memory / Context

- **Session**：默认 `./.agent/sessions`，续聊需显式 `session.id`。  
- **Memory**：`./.agent/memory`，turn 前 injection。  
- **Offloader**：超大 tool result 落盘 + preview。

---

# Part II

## 1. 模块：`event_loop_cycle`

```mermaid
flowchart TB
    START[cycle 开始] --> LIM[_check_limits]
    LIM --> CKPT[checkpoint 恢复?]
    CKPT --> MODEL{需要模型?}
    MODEL -->|是| HM[_handle_model_execution]
    MODEL -->|否| TOOL
    HM --> TOOL{tool_use?}
    TOOL -->|是| HT[_handle_tool_execution]
    HT --> REC[recurse_event_loop]
    REC --> START
    TOOL -->|否| STOP[EventLoopStopEvent]
```

## 2. 模块：`Agent.__call__`

装配 model/tools/plugins → 执行 event loop 生成器 → 汇总 `AgentResult`（stop_reason、metrics）。

## 3. 模块：`create_harness`

合并默认模型、工具、碰撞检测、SnapshotSessionManager、MemoryManager、ContextOffloader、subagent 工厂。

## 4. Interventions 与 Sandbox

工具执行前策略短路；`Agent(sandbox=…)` 包装环境；Harness `_drop_sandbox_tools` 去重。
'''

SOLPI = r'''# SoL-Pi 架构设计文档

> **范围**：`SoL-Pi/src/sol-pi/` 扩展 · 宿主 `pi/packages/coding-agent`  
> **导读**：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架)
- [I.1 四机制与产品价值](#i1-四机制与产品价值)
- [I.2 与宿主 Agent 的边界](#i2-与宿主-agent-的边界)
- [I.3 类图](#i3-类图)
- [I.4 端到端时序（四机制）](#i4-端到端时序四机制)

## Part II 目录

1. [Action Fusion](#1-action-fusion)
2. [ObservationPack](#2-observationpack)
3. [Evidence-Preserving Reducer](#3-evidence-preserving-reducer)
4. [Online Context Compact](#4-online-context-compact)

---

# Part I

## I.0 总体框架

SoL-Pi 是宿主 Coding Agent 上的 **TypeScript 扩展**：四套 **可开关** 机制降低 token 与 turn 数。**不实现**宿主内的 LLM↔工具循环；只挂 `ExtensionAPI` 与替换部分 tool `execute`。

```mermaid
flowchart TB
    subgraph Host["宿主"]
        AS[AgentSession]
        SM[SessionManager]
        RL[runLoop]
        CMP[Compaction]
    end
    subgraph SOL["SoL-Pi"]
        AF[Fusion]
        OP[Pack]
        RD[Reducer]
        OC[Compact]
    end
    AS --> SM --> RL
    AS --> CMP
    AF --> RL
    OP --> AS
    RD --> RL
    OC --> CMP
```

## I.1 四机制与产品价值

| 机制 | 解决的问题 |
|------|------------|
| Fusion | 编辑后自动跑验证，少一轮 LLM |
| Pack | 大 tool 输出投影占位，JSONL 不变 |
| Reducer | 可核对收据的压缩，失败用原文 |
| Compact | 计划边界触发宿主原生压缩 |

## I.2 与宿主 Agent 的边界

| 能力 | 宿主 | SoL-Pi |
|------|------|--------|
| runLoop | ✅ | ❌ |
| JSONL 真源 | ✅ | 只读 + 侧车目录 |
| Compaction 算法 | ✅ | 仅触发/经济性 |
| edit/write execute | ✅ | Fusion 替换实现 |

## I.3 类图

```mermaid
classDiagram
    class SolPiConfig {
        +fusion enabled
        +pack enabled
        +reducer enabled
        +compact enabled
    }
    class ExtensionFactory {
        +register(pi)
    }
    class Observation {
        +id hash bytes
    }
    ExtensionFactory --> SolPiConfig
```

## I.4 端到端时序（四机制）

```mermaid
sequenceDiagram
    participant U as 用户
    participant AS as AgentSession
    participant SP as SoL-Pi
    participant RL as runLoop
    participant M as 模型

    U->>AS: prompt
    AS->>SP: context 事件
    SP-->>AS: 投影后 messages
    AS->>RL: runLoop
    RL->>M: 请求
    M-->>RL: tool_use edit+then_run
    Note over SP: Fusion 一次完成编辑+命令
    RL->>SP: tool_result
    SP-->>RL: 可选 Reducer 替换
    AS->>SP: compact 决策
    SP->>AS: 触发宿主 compaction
```

---

# Part II

## 1. Action Fusion

`then_run` 合并突变与 bash；编辑失败不跑命令；命令非零保留编辑。

## 2. ObservationPack

`context` 事件改投影；`obs_recall` 分页；ledger 审计。

## 3. Evidence-Preserving Reducer

`tool_result` 钩；quote 校验；journal。

## 4. Online Context Compact

`update_plan` → `PendingBoundary` → `economics.decideCompaction` → 宿主 compact。
'''

UA = r'''# Understand-Anything 架构设计文档

> **范围**：`Understand-Anything/understand-anything-plugin/`  
> **导读**：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架)
- [I.1 产品说明](#i1-产品说明)
- [I.2 分层与流水线](#i2-分层与流水线)
- [I.3 图模型类图](#i3-图模型类图)
- [I.4 `/understand` 端到端](#i4-understand-端到端)

## Part II 目录

1. [`packages/core` 图引擎](#1-packagescore-图引擎)
2. [扫描与合并脚本](#2-扫描与合并脚本)
3. [子 Agent 编排](#3-子-agent-编排)
4. [持久化与 Dashboard](#4-持久化与-dashboard)

---

# Part I

## I.0 总体框架

**Loop 在宿主 IDE Agent**；本仓库提供 **知识图谱流水线** + `packages/core` 引擎 + Dashboard/Skills。

```mermaid
flowchart TB
    subgraph Host["宿主 Agent"]
        LOOP[ReAct loop]
    end
    subgraph UA["本插件"]
        SK[Skills]
        AG[agents/*.md]
        SCR[*.mjs 脚本]
        CORE[packages/core]
        G[(KnowledgeGraph)]
    end
    LOOP --> SK --> AG --> SCR --> CORE --> G
    G --> DASH[Dashboard]
```

## I.1 产品说明

**是什么**：把仓库编成带类型节点/边的 **KnowledgeGraph**，落盘 `.ua/`。  
**能做什么**：全量/增量 `/understand`、可视化、chat/diff/explain Skills。  
**怎么做**：脚本做确定性结构，子 Agent 补语义，schema 校验后写盘。

## I.2 分层与流水线

```mermaid
flowchart LR
    SCAN[scan-project] --> BATCH[file batches]
    BATCH --> TS[tree-sitter 结构]
    BATCH --> LLM[file-analyzer 语义]
    TS --> MERGE[merge + validate]
    LLM --> MERGE
    MERGE --> DISK[knowledge-graph.json]
```

## I.3 图模型类图

```mermaid
classDiagram
    class KnowledgeGraph {
        +nodes GraphNode[]
        +edges GraphEdge[]
        +layers Layer[]
        +tour TourStep[]
    }
    class GraphNode {
        +id type name
        +filePath lineRange
        +summary tags
    }
    class GraphEdge {
        +source target type
        +weight direction
    }
    KnowledgeGraph *-- GraphNode
    KnowledgeGraph *-- GraphEdge
```

## I.4 `/understand` 端到端

```mermaid
sequenceDiagram
    participant U as 用户
    participant H as 宿主
    participant SK as Skill
    participant SC as scanner Agent
    participant FA as file-analyzer
    participant MG as merge
    participant VAL as schema.validate

    U->>H: /understand
    H->>SK: 编排说明
    SK->>SC: 范围叙事
    SK->>FA: 并行 batch
    FA-->>MG: nodes/edges JSON
    MG->>VAL: sanitize/autoFix/validate
    VAL-->>SK: 落盘 .ua/
```

---

# Part II

## 1. `packages/core` 图引擎

GraphBuilder + TreeSitterPlugin + extractors；`validateGraph` 失败不写坏图。

## 2. 扫描与合并脚本

禁止 Skill 手写目录 walk；增量靠 `fingerprints.json`。

## 3. 子 Agent 编排

file-analyzer **不得再 spawn** Agent；assemble-reviewer 以 schema 为准修补。

## 4. 持久化与 Dashboard

路径消毒；Dashboard **只读** 图文件。
'''

def main():
    mapping = {
        "harness-sdk-architecture": HARNESS,
        "sol-pi-architecture": SOLPI,
        "understand-anything-architecture": UA,
    }
    for folder, text in mapping.items():
        p = DOCS / folder / "ARCHITECTURE.md"
        p.write_text(text.strip() + "\n", encoding="utf-8")
        print(folder, len(text.splitlines()), "lines")


if __name__ == "__main__":
    main()
