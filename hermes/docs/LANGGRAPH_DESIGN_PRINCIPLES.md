# LangGraph 设计原理与底层框架深度解析

> **文档状态**: 外部框架研读 · **非 Hermes 规范** · 核对 2026-06-10
## 目录

**第一部分：架构全景**
1. [概述](#1-概述)
2. [分层架构设计](#2-分层架构设计)
3. [模块设计与依赖关系](#3-模块设计与依赖关系)

**第二部分：核心抽象**
4. [六大核心抽象](#4-六大核心抽象)
5. [State 与 Channel 设计](#5-state-与-channel-设计)
6. [表达式解析与 Runnable 协议 (LCEL)](#6-表达式解析与-runnable-协议-lcel)

**第三部分：编译与执行**
7. [编译流程：StateGraph 到 Pregel](#7-编译流程stategraph-到-pregel)
8. [执行模型：Super-Step 详解](#8-执行模型super-step-详解)
9. [ReAct Agent 完整执行时序](#9-react-agent-完整执行时序)

**第四部分：持久化与流式**
10. [Checkpoint 持久化系统设计](#10-checkpoint-持久化系统设计)
11. [Streaming 流式输出架构](#11-streaming-流式输出架构)

**第五部分：高级编排**
12. [子图与多 Agent 编排](#12-子图与多-agent-编排)
13. [Command 控制流机制](#13-command-控制流机制)

**第六部分：项目集成**
14. [Deep Agents SDK 中的 LangGraph 集成](#14-deep-agents-sdk-中的-langgraph-集成)

**附录**
- [关键源码文件索引](#附录关键源码文件索引)

---

# 第一部分：架构全景

## 1. 概述

LangGraph 是 LangChain 团队开发的**低层编排框架**，将 Agent 的执行流建模为一张**有状态的有向图**。

| 维度 | 说明 |
|------|------|
| 设计灵感 | Google Pregel 图计算模型（BSP 并行计算） |
| 核心抽象 | 有状态计算图 — 节点是计算步骤，边是控制流 |
| 与 LangChain 关系 | LangChain Agent 编译后就是 LangGraph 图 |
| 适用场景 | 多步推理、工具调用循环、多 Agent 协作、Human-in-the-Loop |

---

## 2. 分层架构设计

### 2.1 分层架构图

```mermaid
block-beta
  columns 1

  block:user["用户代码层"]
    A["create_deep_agent() / StateGraph Builder API"]
  end

  block:sdk["Deep Agents SDK 层"]
    B["graph.py 中间件栈 子Agent编排 系统提示词"]
  end

  block:langgraph["LangGraph 框架层"]
    columns 3
    C["StateGraph 声明式图定义"]
    D["Pregel 执行引擎"]
    E["Checkpoint 持久化"]
    F["Channel 通道系统"]
    G["StreamMux 流式输出"]
    H["Store 跨线程存储"]
  end

  block:langchain["LangChain Core 层"]
    columns 3
    I["Runnable 协议 LCEL"]
    J["ChatModel LLM抽象"]
    K["BaseTool Message类型"]
  end

  block:infra["基础设施层"]
    columns 3
    L["LLM Provider OpenAI Anthropic"]
    M["PostgreSQL Redis"]
    N["LangGraph Platform"]
  end

  user --> sdk
  sdk --> langgraph
  langgraph --> langchain
  langchain --> infra
```

### 2.2 各层职责

| 层级 | 职责 | 关键模块 |
|------|------|---------|
| **用户代码层** | 定义业务逻辑、工具、提示词 | `StateGraph`, `create_deep_agent()` |
| **SDK 层** | 中间件编排、子 Agent、权限、技能 | `graph.py`, `middleware/`, `backends/` |
| **LangGraph 框架层** | 图编译、Pregel 执行、Checkpoint、流式 | `pregel/`, `graph/`, `checkpoint/`, `stream/` |
| **LangChain Core 层** | Runnable 协议、LLM 抽象、消息类型 | `runnables/`, `chat_models/`, `messages/` |
| **基础设施层** | LLM API 调用、数据库存储、部署平台 | OpenAI API, PostgreSQL, LangGraph Cloud |

---

## 3. 模块设计与依赖关系

### 3.1 LangGraph 核心模块依赖图

```mermaid
graph TB
    subgraph UserAPI["用户 API"]
        SG["StateGraph<br/>图构建器"]
        MG["MessagesState<br/>预置状态"]
    end

    subgraph Compiler["编译器"]
        COMP["compile()<br/>图验证 + Channel映射"]
    end

    subgraph Runtime["运行时引擎"]
        PR["Pregel<br/>Super-Step调度"]
        CSG["CompiledStateGraph<br/>编译后的图"]
    end

    subgraph ChannelSys["Channel 系统"]
        LV["LastValue<br/>后写覆盖"]
        BOA["BinaryOperatorAggregate<br/>Reducer聚合"]
        EV["EphemeralValue<br/>临时值"]
        TP["Topic<br/>发布订阅"]
    end

    subgraph Persistence["持久化"]
        BCS["BaseCheckpointSaver<br/>抽象接口"]
        IMS["InMemorySaver"]
        PGS["PostgresSaver"]
        SQS["SqliteSaver"]
    end

    subgraph Streaming["流式输出"]
        SM["StreamMux<br/>多路复用"]
        SC["StreamChannel<br/>流通道"]
        GRS["GraphRunStream<br/>运行流"]
    end

    subgraph Types["类型系统"]
        CMD["Command<br/>控制流"]
        INT["Interrupt<br/>中断"]
        OW["Overwrite<br/>状态覆写"]
        RT["Runtime<br/>运行时上下文"]
    end

    subgraph LangChainCore["LangChain Core"]
        RUN["Runnable<br/>统一接口"]
        CM["ChatModel"]
        BT["BaseTool"]
        MSG["BaseMessage"]
    end

    SG --> COMP
    MG --> SG
    COMP --> CSG
    CSG --> PR
    COMP --> LV
    COMP --> BOA
    COMP --> EV
    COMP --> TP
    PR --> SM
    PR --> BCS
    SM --> SC
    SM --> GRS
    BCS --> IMS
    BCS --> PGS
    BCS --> SQS
    CSG -.->|implements| RUN
    PR --> CMD
    PR --> INT
    CM -.->|implements| RUN
    BT -.->|implements| RUN
```

### 3.2 模块职责清单

| 模块 | 源码位置 | 核心职责 |
|------|---------|---------|
| `graph/state.py` | StateGraph | 声明式图定义：添加节点、边、条件路由 |
| `pregel/__init__.py` | Pregel | BSP 执行引擎：Super-Step 调度、Barrier 同步 |
| `channels/` | Channel 系统 | 状态存储与 Reducer 合并：LastValue、BinaryOperatorAggregate |
| `checkpoint/` | 持久化 | Checkpoint 保存/恢复/列举/删除 |
| `stream/` | 流式输出 | StreamMux 多路复用、Transformer 管线、StreamChannel |
| `types.py` | 类型定义 | Command、Interrupt、Checkpointer、Overwrite |
| `config.py` | 配置 | get_config、get_store — 运行时配置访问 |
| `store/` | 跨线程存储 | BaseStore、Item — 持久化键值存储 |
| `runtime.py` | 运行时 | Runtime、get_runtime — 运行时上下文注入 |
| `errors.py` | 错误体系 | GraphRecursionError、GraphInterrupt、NodeError 等 |

---

# 第二部分：核心抽象

## 4. 六大核心抽象

### 4.1 抽象关系总览

```mermaid
graph LR
    subgraph BuildTime["构建时"]
        SG["StateGraph"]
        N["Node 节点"]
        E["Edge 边"]
        ST["State TypedDict"]
    end

    subgraph CompileTime["编译时"]
        CH["Channel 通道"]
        RD["Reducer 归约器"]
    end

    subgraph RunTime["运行时"]
        PG["Pregel 引擎"]
        CP["Checkpoint"]
    end

    SG -->|add_node| N
    SG -->|add_edge| E
    SG -->|state_schema| ST
    ST -->|Annotated 解析| CH
    ST -->|metadata 提取| RD
    RD --> CH
    SG -->|compile| PG
    CH --> PG
    PG -->|每步保存| CP
```

### 4.2 核心抽象对照表

| 抽象 | Pregel 对应 | 生命周期 | 用户可见性 |
|------|------------|---------|-----------|
| **StateGraph** | — | 构建时 | 直接操作 |
| **Node** | Vertex | 构建时定义 运行时执行 | 直接操作 |
| **Edge** | — | 构建时定义 编译时转换 | 直接操作 |
| **State/Reducer** | Message | 编译时解析 运行时生效 | 声明式（TypedDict） |
| **Channel** | Message Channel | 编译时创建 运行时读写 | 不可见（内部） |
| **Pregel** | Pregel Engine | 运行时 | 间接（通过 invoke/stream） |
| **Checkpoint** | Checkpoint | 运行时 | 可查询（get_state） |

---

## 5. State 与 Channel 设计

### 5.1 TypedDict 到 Channel 的映射流程

```mermaid
flowchart TD
    A["定义 State TypedDict"] --> B{"遍历每个字段"}
    B --> C{"是否有 Annotated 注解?"}
    C -->|是| D["提取 base_type 和 reducer"]
    C -->|否| E["base_type = 原始类型<br/>reducer = None"]
    D --> F{"reducer 类型?"}
    E --> G["创建 LastValue Channel<br/>后写覆盖"]
    F -->|operator.add| H["创建 BinaryOperatorAggregate<br/>列表追加合并"]
    F -->|add_messages| I["创建 BinaryOperatorAggregate<br/>智能消息合并"]
    F -->|自定义函数| J["创建 BinaryOperatorAggregate<br/>自定义合并逻辑"]
    G --> K["Channel 注册到 Pregel"]
    H --> K
    I --> K
    J --> K

    style A fill:#e1f5fe
    style K fill:#c8e6c9
```

### 5.2 Channel 类型体系

```mermaid
classDiagram
    class BaseChannel {
        <<abstract>>
        +update(values) void
        +get() T
        +checkpoint() snapshot
        +restore(snapshot) void
    }

    class LastValue~T~ {
        -value: T
        +update(values) 取最后一个值
        +get() 返回当前值
    }

    class BinaryOperatorAggregate~T~ {
        -value: T
        -operator: Callable
        +update(values) 通过 operator 逐个合并
        +get() 返回聚合结果
    }

    class EphemeralValue~T~ {
        -value: T or EMPTY
        +update(values) 设置值
        +get() 返回值 Step结束后清除
    }

    class Topic~T~ {
        -values: list of T
        +update(values) 累积所有值
        +get() 返回值列表
    }

    BaseChannel <|-- LastValue
    BaseChannel <|-- BinaryOperatorAggregate
    BaseChannel <|-- EphemeralValue
    BaseChannel <|-- Topic
```

### 5.3 Reducer 并发写入合并示例

```mermaid
flowchart LR
    subgraph SuperStep["Super-Step N: 并发执行"]
        NB["Node B<br/>返回 aggregate: B"]
        NC["Node C<br/>返回 aggregate: C"]
    end

    subgraph Barrier["同步屏障"]
        R["Reducer: operator.add"]
    end

    subgraph Result["合并结果"]
        V["aggregate = B, C"]
    end

    NB --> R
    NC --> R
    R --> V
```

---

## 6. 表达式解析与 Runnable 协议 (LCEL)

### 6.1 LCEL 是什么

LCEL（LangChain Expression Language）是 Python 级的**组合式 API**，通过 `|` 操作符串联计算步骤。所有 LangChain/LangGraph 组件都实现 `Runnable` 协议。

### 6.2 Runnable 协议类图

```mermaid
classDiagram
    class Runnable~Input Output~ {
        <<protocol>>
        +invoke(input config) Output
        +ainvoke(input config) Output
        +stream(input config) Iterator
        +astream(input config) AsyncIterator
        +batch(inputs config) list
        +__or__(other) RunnableSequence
        +with_config(config) Runnable
        +with_retry(max_attempts) Runnable
        +with_fallbacks(fallbacks) Runnable
    }

    class RunnableSequence {
        -first: Runnable
        -middle: list of Runnable
        -last: Runnable
        +invoke() 顺序执行
    }

    class RunnableParallel {
        -steps: dict of str to Runnable
        +invoke() 并行执行 返回dict
    }

    class RunnableLambda {
        -func: Callable
        +invoke() 调用函数
    }

    class RunnableBranch {
        -branches: list of condition Runnable
        -default: Runnable
        +invoke() 条件路由
    }

    class ChatModel {
        +invoke() 调用 LLM
    }

    class CompiledStateGraph {
        +invoke() 执行整个图
        +stream() 流式执行
    }

    Runnable <|-- RunnableSequence
    Runnable <|-- RunnableParallel
    Runnable <|-- RunnableLambda
    Runnable <|-- RunnableBranch
    Runnable <|-- ChatModel
    Runnable <|-- CompiledStateGraph
```

### 6.3 LCEL 组合流程图

```mermaid
flowchart LR
    subgraph Chain["chain = prompt | model | parser"]
        P["PromptTemplate<br/>Runnable"]
        M["ChatModel<br/>Runnable"]
        PA["OutputParser<br/>Runnable"]
    end

    IN["输入 dict"] --> P
    P -->|"格式化后的<br/>messages"| M
    M -->|"AIMessage<br/>stream chunks"| PA
    PA -->|"解析后的<br/>结构化输出"| OUT["输出"]

    style IN fill:#fff3e0
    style OUT fill:#e8f5e9
```

### 6.4 TypedDict 注解解析流程

```mermaid
flowchart TD
    A["class MyState(TypedDict):<br/>  messages: Annotated[list, add_messages]<br/>  context: str"]
    A --> B["get_type_hints(MyState, include_extras=True)"]
    B --> C["遍历 hints"]
    C --> D{"get_origin(hint) is Annotated?"}
    D -->|是| E["get_args(hint)<br/>base_type=list<br/>reducer=add_messages"]
    D -->|否| F["base_type=str<br/>reducer=None"]
    E --> G["BinaryOperatorAggregate(list, add_messages)"]
    F --> H["LastValue(str)"]
    G --> I["channels dict"]
    H --> I

    style A fill:#e3f2fd
    style I fill:#c8e6c9
```

### 6.5 条件边求值流程

```mermaid
flowchart TD
    A["agent 节点执行完毕"] --> B["写入 state Channels"]
    B --> C["同步屏障 Barrier"]
    C --> D["读取最新 state"]
    D --> E["调用 route_function(state)"]
    E --> F{"返回值?"}
    F -->|continue| G["写入 branch:to:tools Channel"]
    F -->|end| H["写入 branch:to:END Channel"]
    G --> I["下个 Super-Step: tools 节点执行"]
    H --> J["图执行结束"]

    style A fill:#e3f2fd
    style I fill:#fff3e0
    style J fill:#ffebee
```

### 6.6 Runnable 嵌套统一性

```mermaid
graph TB
    subgraph outer["CompiledStateGraph (Runnable)"]
        subgraph nodeA["Node A: RunnableSequence"]
            A1["PromptTemplate"] --> A2["ChatModel"] --> A3["OutputParser"]
        end

        subgraph nodeB["Node B: RunnableLambda"]
            B1["tool_executor()"]
        end

        subgraph nodeC["Node C: CompiledStateGraph 子图"]
            subgraph subX["Sub Node X"]
                X1["函数"]
            end
            subgraph subY["Sub Node Y"]
                Y1["函数"]
            end
            X1 --> Y1
        end

        nodeA -->|"条件边"| nodeB
        nodeB -->|"无条件边"| nodeA
        nodeA -->|"条件边"| nodeC
    end

    style outer fill:#f3e5f5
```

---

# 第三部分：编译与执行

## 7. 编译流程：StateGraph 到 Pregel

### 7.1 编译全流程图

```mermaid
flowchart TD
    subgraph Input["输入: StateGraph"]
        A1["state_schema: TypedDict"]
        A2["nodes: dict"]
        A3["edges: set"]
        A4["conditional_edges: dict"]
        A5["checkpointer"]
    end

    subgraph Phase1["阶段1: 类型解析"]
        B1["解析 TypedDict 字段"]
        B2["提取 Annotated 元数据"]
        B3["为每个字段创建 Channel"]
    end

    subgraph Phase2["阶段2: 节点编译"]
        C1["函数包装为 PregelNode"]
        C2["绑定 Channel 读写规则"]
        C3["注入 RunnableConfig 传递"]
    end

    subgraph Phase3["阶段3: 边编译"]
        D1["无条件边 -> Channel 写入触发"]
        D2["条件边 -> Branch Channel + 路由函数"]
        D3["创建内部 branch: 前缀的 Channel"]
    end

    subgraph Phase4["阶段4: 图验证"]
        E1["检查 START 到 END 可达性"]
        E2["检测无效环路"]
        E3["检查孤立节点"]
    end

    subgraph Phase5["阶段5: 组装"]
        F1["注入 checkpointer"]
        F2["注入 store"]
        F3["设置 recursion_limit"]
        F4["生成 CompiledStateGraph"]
    end

    subgraph Output["输出: Pregel 实例"]
        G["CompiledStateGraph<br/>(也是 Runnable)"]
    end

    A1 --> B1
    A2 --> C1
    A3 --> D1
    A4 --> D2
    B1 --> B2 --> B3
    B3 --> C2
    C1 --> C2 --> C3
    D1 --> D3
    D2 --> D3
    C3 --> E1
    D3 --> E1
    E1 --> E2 --> E3
    E3 --> F1
    A5 --> F1
    F1 --> F2 --> F3 --> F4
    F4 --> G

    style G fill:#c8e6c9
```

### 7.2 编译前后对比

| 编译前（StateGraph） | 编译后（Pregel） |
|---------------------|-----------------|
| `TypedDict` 字段 | `Channel` 实例 |
| Python 函数 | `PregelNode`（含读写规则） |
| `add_edge("A", "B")` | A 完成后触发 B 的调度 Channel |
| `add_conditional_edges(...)` | `branch:` Channel + 路由函数 |
| `checkpointer=InMemorySaver()` | 注入到 Pregel，每步自动保存 |
| 无 `recursion_limit` | 默认 25，防止无限循环 |

---

## 8. 执行模型：Super-Step 详解

### 8.1 Pregel BSP 执行模型

LangGraph 的 Pregel 引擎基于 **BSP（Bulk Synchronous Parallel）**模型：

```mermaid
flowchart TD
    START["START"] --> SS0

    subgraph SS0["Super-Step 0"]
        SS0_exec["执行可调度节点"]
        SS0_write["写入 Channel 更新"]
    end

    SS0 --> B0["同步屏障 Barrier<br/>Reducer 合并写入"]
    B0 --> CP0["Checkpoint 保存"]
    CP0 --> CHECK0{"有节点需要执行?"}

    CHECK0 -->|是| SS1
    subgraph SS1["Super-Step 1"]
        SS1_exec["执行可调度节点"]
        SS1_write["写入 Channel 更新"]
    end

    SS1 --> B1["同步屏障 Barrier<br/>Reducer 合并写入"]
    B1 --> CP1["Checkpoint 保存"]
    CP1 --> CHECK1{"有节点需要执行?"}

    CHECK1 -->|是| SS2["Super-Step N..."]
    CHECK1 -->|否| DONE["到达 END<br/>返回最终 State"]
    CHECK0 -->|否| DONE

    SS2 --> BN["..."]
    BN --> DONE

    style START fill:#e3f2fd
    style DONE fill:#c8e6c9
    style CP0 fill:#fff3e0
    style CP1 fill:#fff3e0
```

### 8.2 节点调度算法

```mermaid
flowchart TD
    A["Super-Step 开始"] --> B["遍历所有节点 N"]
    B --> C{"N 订阅的 Channel<br/>有新版本?"}
    C -->|"channel_versions > versions_seen"| D["加入本步执行队列"]
    C -->|"没有新数据"| E["跳过（保持 halt）"]
    D --> F["并发执行队列中所有节点"]
    E --> B
    F --> G["收集所有输出"]
    G --> H["通过 Reducer 合并写入 Channel"]
    H --> I["更新 channel_versions"]
    I --> J["保存 Checkpoint"]

    style A fill:#e3f2fd
    style J fill:#c8e6c9
```

### 8.3 并行扇出/扇入时序图

```mermaid
sequenceDiagram
    participant S as 调度器
    participant A as Node_A
    participant B as Node_B
    participant C as Node_C
    participant D as Node_D
    participant CH as Channels
    participant CP as Checkpoint

    Note over S,CP: Super-Step 0
    S->>A: 执行 Node_A
    A->>CH: 写入 aggregate: A
    CH->>CP: Checkpoint 保存

    Note over S,CP: Super-Step 1 并发
    S->>B: 并发执行 Node_B
    S->>C: 并发执行 Node_C
    B->>CH: 写入 aggregate: B
    C->>CH: 写入 aggregate: C
    Note over CH: Reducer合并: B + C = B,C
    CH->>CP: Checkpoint 保存

    Note over S,CP: Super-Step 2
    S->>D: 执行 Node_D
    Note over D: 看到 aggregate: A,B,C
    D->>CH: 写入 aggregate: D
    CH->>CP: Checkpoint 保存
```

---

## 9. ReAct Agent 完整执行时序

### 9.1 带工具调用的完整时序图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Graph as CompiledStateGraph
    participant Sched as Pregel调度器
    participant AgentNode as agent节点
    participant ToolNode as tools节点
    participant CH as Channels
    participant LLM as LLM_API
    participant ToolExec as 工具执行器
    participant CP as Checkpointer

    User->>Graph: invoke(messages: 查看当前目录文件)
    Graph->>CP: 加载最新 Checkpoint (thread_id)
    Graph->>CH: 写入 messages Channel

    Note over Sched,CP: === Super-Step 0: agent 节点 ===
    Sched->>AgentNode: 调度执行
    AgentNode->>CH: 读取 state.messages
    AgentNode->>LLM: 发送消息 + 工具定义
    LLM-->>AgentNode: 返回 tool_calls: terminal(ls)
    AgentNode->>CH: 写入 messages: AIMessage(tool_calls)
    Note over CH: 条件边求值: has_tool_calls -> tools
    CH->>CP: Checkpoint 保存 (step=0)

    Note over Sched,CP: === Super-Step 1: tools 节点 ===
    Sched->>ToolNode: 调度执行
    ToolNode->>CH: 读取 messages (含 tool_calls)
    ToolNode->>ToolExec: 执行 terminal(ls)
    ToolExec-->>ToolNode: file1.py file2.py
    ToolNode->>CH: 写入 messages: ToolMessage(file1.py...)
    Note over CH: 无条件边: tools -> agent
    CH->>CP: Checkpoint 保存 (step=1)

    Note over Sched,CP: === Super-Step 2: agent 节点再次 ===
    Sched->>AgentNode: 调度执行
    AgentNode->>CH: 读取 state.messages (3条)
    AgentNode->>LLM: 发送完整对话历史
    LLM-->>AgentNode: 返回纯文本: 当前目录有file1 file2...
    AgentNode->>CH: 写入 messages: AIMessage(纯文本)
    Note over CH: 条件边求值: no_tool_calls -> END
    CH->>CP: Checkpoint 保存 (step=2)

    Graph-->>User: 返回最终 state
```

### 9.2 ReAct 循环状态图

```mermaid
stateDiagram-v2
    [*] --> agent: START

    agent --> tools: has_tool_calls
    agent --> [*]: no_tool_calls (END)

    tools --> agent: 工具结果返回

    state agent {
        [*] --> 读取messages
        读取messages --> 调用LLM
        调用LLM --> 写入响应
        写入响应 --> [*]
    }

    state tools {
        [*] --> 解析tool_calls
        解析tool_calls --> 执行工具
        执行工具 --> 写入ToolMessage
        写入ToolMessage --> [*]
    }
```

---

# 第四部分：持久化与流式

## 10. Checkpoint 持久化系统设计

### 10.1 Checkpoint 类图

```mermaid
classDiagram
    class BaseCheckpointSaver {
        <<abstract>>
        +put(config checkpoint metadata new_versions) RunnableConfig
        +put_writes(config writes task_id) void
        +get_tuple(config) CheckpointTuple
        +list(config filter before limit) Iterator
        +delete_thread(thread_id) void
        +get_next_version(current channel) str
    }

    class InMemorySaver {
        -storage: dict
        +put() 写入内存dict
        +get_tuple() 从dict查询
    }

    class PostgresSaver {
        -conn: Connection
        +put() INSERT INTO checkpoints
        +get_tuple() SELECT FROM checkpoints
    }

    class SqliteSaver {
        -conn: sqlite3.Connection
        +put() INSERT INTO checkpoints
        +get_tuple() SELECT FROM checkpoints
    }

    class CheckpointTuple {
        +config: RunnableConfig
        +checkpoint: Checkpoint
        +metadata: CheckpointMetadata
        +parent_config: RunnableConfig
        +pending_writes: list
    }

    class Checkpoint {
        +v: int
        +ts: str
        +id: str
        +channel_values: dict
        +channel_versions: dict
        +versions_seen: dict
    }

    BaseCheckpointSaver <|-- InMemorySaver
    BaseCheckpointSaver <|-- PostgresSaver
    BaseCheckpointSaver <|-- SqliteSaver
    BaseCheckpointSaver ..> CheckpointTuple
    CheckpointTuple *-- Checkpoint
```

### 10.2 Checkpoint 读写时序图

```mermaid
sequenceDiagram
    participant PR as Pregel引擎
    participant CH as Channels
    participant CP as Checkpointer
    participant DB as 存储后端

    Note over PR,DB: --- 恢复阶段 ---
    PR->>CP: get_tuple(thread_id, checkpoint_id)
    CP->>DB: 查询最新 checkpoint
    DB-->>CP: CheckpointTuple
    CP-->>PR: checkpoint + pending_writes
    PR->>CH: 从 channel_values 恢复所有 Channel

    Note over PR,DB: --- 执行阶段 (每个节点完成后) ---
    PR->>CP: put_writes(config, writes, task_id)
    CP->>DB: INSERT INTO checkpoint_writes
    Note over DB: 中间写入已持久化 (容错)

    Note over PR,DB: --- 提交阶段 (Super-Step 结束) ---
    PR->>CH: 通过 Reducer 合并所有 pending_writes
    PR->>CH: 生成新的 channel_values
    PR->>CP: put(config, new_checkpoint, metadata)
    CP->>DB: INSERT INTO checkpoints
    Note over DB: 新 Checkpoint 持久化完成
```

### 10.3 两阶段提交流程图

```mermaid
flowchart TD
    subgraph Phase1["阶段1: 执行 Execute"]
        A["Super-Step N 开始"] --> B["Node A 执行完成"]
        B --> C["put_writes(writes_A, task_A)"]
        C --> D["Node B 执行完成"]
        D --> E["put_writes(writes_B, task_B)"]
        E --> F{"所有节点完成?"}
        F -->|否 此时崩溃| RECOVER["恢复: 跳过已完成节点<br/>重试未完成节点"]
    end

    subgraph Phase2["阶段2: 提交 Commit"]
        F -->|是| G["合并所有 pending_writes"]
        G --> H["Reducer 聚合"]
        H --> I["生成新 channel_values"]
        I --> J["put(new_checkpoint)"]
        J --> K["Checkpoint 持久化完成"]
    end

    K --> L["清空 pending_writes"]
    L --> M["进入 Super-Step N+1"]

    style RECOVER fill:#ffebee
    style K fill:#c8e6c9
```

### 10.4 版本向量增量检测

```mermaid
flowchart LR
    subgraph VersionVector["版本向量对比"]
        CV["channel_versions<br/>messages: v3<br/>context: v2"]
        VS["versions_seen[agent]<br/>messages: v2<br/>context: v2"]
    end

    CV --> CMP{"逐字段比较"}
    VS --> CMP

    CMP -->|"messages: v3 > v2"| NEW["有新数据!<br/>调度 agent 节点"]
    CMP -->|"context: v2 == v2"| SKIP["无变化 跳过"]

    style NEW fill:#c8e6c9
    style SKIP fill:#e0e0e0
```

### 10.5 时间旅行与分叉

```mermaid
flowchart LR
    S0["Checkpoint<br/>Step 0<br/>input"] --> S1["Checkpoint<br/>Step 1<br/>agent"]
    S1 --> S2["Checkpoint<br/>Step 2<br/>tools"]
    S2 --> S3["Checkpoint<br/>Step 3<br/>agent"]
    S3 --> S4["Checkpoint<br/>Step 4<br/>END"]

    S2 -->|"update_state<br/>注入新消息"| S2F["Fork<br/>Step 2*"]
    S2F --> S3F["Fork<br/>Step 3*"]
    S3F --> S4F["Fork<br/>Step 4*"]

    style S2F fill:#fff3e0
    style S3F fill:#fff3e0
    style S4F fill:#fff3e0
```

### 10.6 存储后端对比

| 后端 | 持久性 | 性能 | 并发 | 适用场景 |
|------|--------|------|------|---------|
| InMemorySaver | 进程内 | 最快 | 单进程 | 开发测试 |
| SqliteSaver | 文件级 | 中等 | 单写者 | 单机原型 |
| PostgresSaver | 完全持久 | 依赖网络 | 多进程安全 | 生产环境 |
| RedisSaver | 可配置 | 低延迟 | 多进程安全 | 高频读写 |

### 10.7 PostgresSaver 表结构

```mermaid
erDiagram
    checkpoints {
        text thread_id PK
        text checkpoint_ns PK
        text checkpoint_id PK
        text parent_checkpoint_id
        text type
        bytea checkpoint
        jsonb metadata
        timestamptz created_at
    }

    checkpoint_writes {
        text thread_id PK
        text checkpoint_ns PK
        text checkpoint_id PK
        text task_id PK
        int idx PK
        text channel
        text type
        bytea value
    }

    checkpoints ||--o{ checkpoint_writes : "has pending"
```

---

## 11. Streaming 流式输出架构

### 11.1 Streaming 数据流

```mermaid
flowchart LR
    subgraph Engine["Pregel 引擎"]
        PE["产出 ProtocolEvent"]
    end

    subgraph Mux["StreamMux 多路复用"]
        T1["MessageTransformer"]
        T2["SubgraphTransformer"]
        T3["LifecycleTransformer"]
        SEQ["分配 seq 编号"]
    end

    subgraph Channels["StreamChannel"]
        SC1["updates Channel"]
        SC2["messages Channel"]
        SC3["events Channel"]
    end

    subgraph Consumer["消费者"]
        C1["graph.stream(mode=updates)"]
        C2["graph.stream(mode=messages)"]
        C3["graph.astream_events()"]
    end

    PE --> T1 --> T2 --> T3 --> SEQ
    SEQ --> SC1 --> C1
    SEQ --> SC2 --> C2
    SEQ --> SC3 --> C3
```

### 11.2 流模式对比

| stream_mode | 输出内容 | 粒度 | 典型用途 |
|------------|---------|------|---------|
| `updates` | 每个节点的 state 更新 | 节点级 | 追踪 Agent 步骤 |
| `messages` | LLM 输出的 token chunks | Token 级 | 实时打字效果 |
| `events` | 所有内部事件（含子图） | 事件级 | 调试/监控 |
| `custom` | 节点内自定义输出 | 自定义 | 进度通知 |

---

# 第五部分：高级编排

## 12. 子图与多 Agent 编排

### 12.1 子图嵌套执行时序图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Parent as 父图 Pregel
    participant PNode as 父图节点
    participant SubGraph as 子图 Pregel
    participant SubA as 子图 Node_A
    participant SubB as 子图 Node_B
    participant PCP as 父图 Checkpoint
    participant SCP as 子图 Checkpoint

    User->>Parent: invoke(input)

    Note over Parent,SCP: === 父图 Super-Step 0 ===
    Parent->>PNode: 执行 pre_process 节点
    PNode-->>Parent: 返回更新
    Parent->>PCP: Checkpoint step=0

    Note over Parent,SCP: === 父图 Super-Step 1: 子图节点 ===
    Parent->>SubGraph: 将父图 state 传入子图

    Note over SubGraph,SCP: --- 子图 Super-Step 0 ---
    SubGraph->>SubA: 执行 Node_A
    SubA-->>SubGraph: 返回更新
    SubGraph->>SCP: 子图 Checkpoint (checkpoint_ns=sub)

    Note over SubGraph,SCP: --- 子图 Super-Step 1 ---
    SubGraph->>SubB: 执行 Node_B
    SubB-->>SubGraph: 返回更新
    SubGraph->>SCP: 子图 Checkpoint

    SubGraph-->>Parent: 子图输出写回父图 state
    Parent->>PCP: Checkpoint step=1

    Note over Parent,SCP: === 父图 Super-Step 2 ===
    Parent->>PNode: 执行 post_process 节点
    PNode-->>Parent: 返回更新
    Parent->>PCP: Checkpoint step=2

    Parent-->>User: 返回最终结果
```

### 12.2 子图状态共享策略

```mermaid
flowchart TD
    subgraph Strategy1["策略1: 共享 State 同 schema"]
        P1["父图 State"]
        S1["子图 State"]
        P1 <-->|"同名字段自动读写"| S1
    end

    subgraph Strategy2["策略2: 独立 State + 映射"]
        P2["父图 ParentState"]
        CONV1["输入转换函数"]
        S2["子图 SubState"]
        CONV2["输出转换函数"]
        P2 --> CONV1 --> S2
        S2 --> CONV2 --> P2
    end

    subgraph Strategy3["策略3: Command.PARENT"]
        S3["子图节点"]
        CMD["Command(update, goto, graph=PARENT)"]
        P3["父图 state + 路由"]
        S3 --> CMD --> P3
    end
```

---

## 13. Command 控制流机制

### 13.1 Command 工作流程

```mermaid
flowchart TD
    A["节点执行"] --> B{"返回类型?"}
    B -->|"普通 dict"| C["写入 Channel<br/>按正常边路由"]
    B -->|"Command 对象"| D["解析 Command"]
    D --> E["Command.update<br/>写入 state 更新"]
    D --> F["Command.goto<br/>指定下一个节点"]
    D --> G{"Command.graph?"}
    G -->|"None (默认)"| H["在当前图内路由"]
    G -->|"Command.PARENT"| I["向父图发送<br/>ParentCommand"]
    E --> J["合并到 Channel"]
    F --> J
    H --> J
    I --> K["父图处理 ParentCommand"]
```

### 13.2 Command vs 传统边的对比

| 特性 | 传统 Edge | Command |
|------|-----------|---------|
| 定义位置 | 构建时（静态） | 运行时（动态） |
| 状态更新 | 通过节点返回值 | `Command.update` |
| 路由 | `add_conditional_edges` | `Command.goto` |
| 跨图通信 | 不支持 | `Command.graph=PARENT` |
| 灵活性 | 路由逻辑与节点分离 | 路由逻辑在节点内部 |

---

# 第六部分：项目集成

## 14. Deep Agents SDK 中的 LangGraph 集成

### 14.1 集成架构图

```mermaid
graph TB
    subgraph DeepAgents["Deep Agents SDK"]
        GA["graph.py<br/>create_deep_agent()"]

        subgraph MW["中间件栈"]
            M1["TodoMiddleware"]
            M2["FilesystemMiddleware"]
            M3["SubAgentMiddleware"]
            M4["SummarizationMiddleware"]
            M5["SkillsMiddleware"]
            M6["MemoryMiddleware"]
            M7["PermissionMiddleware"]
        end

        subgraph BE["后端"]
            SB["StateBackend<br/>Channel read/send"]
            STB["StoreBackend<br/>BaseStore CRUD"]
        end
    end

    subgraph LG["LangGraph"]
        CSG2["CompiledStateGraph"]
        PR2["Pregel"]
        CH2["Channels"]
        CP2["Checkpoint"]
        ST2["Store"]
        RT2["Runtime"]
    end

    GA --> MW
    MW --> CSG2
    SB -->|"CONFIG_KEY_READ<br/>CONFIG_KEY_SEND"| CH2
    STB -->|"get_store()"| ST2
    M3 -->|"Command"| PR2
    M4 -->|"get_config()"| PR2
    M5 -->|"ToolRuntime"| RT2
    CSG2 --> PR2
    PR2 --> CH2
    PR2 --> CP2

    style GA fill:#e3f2fd
    style CSG2 fill:#c8e6c9
```

### 14.2 StateBackend 数据流

```mermaid
sequenceDiagram
    participant Tool as 文件操作工具
    participant SB as StateBackend
    participant Config as Pregel Config
    participant CH as files Channel
    participant CP as Checkpointer

    Tool->>SB: write(path, content)
    SB->>Config: _get_config()
    Config-->>SB: CONFIG_KEY_READ + CONFIG_KEY_SEND

    SB->>CH: read("files", fresh=False)
    CH-->>SB: 当前 files 快照

    SB->>SB: 构建更新 dict
    SB->>CH: send("files", update)
    Note over CH: Reducer 合并: dict merge

    CH->>CP: Super-Step 结束时自动 Checkpoint
    Note over CP: files 变更随图状态一起持久化
```

### 14.3 中间件与 LangGraph 类型映射

| 中间件 | 使用的 LangGraph 类型 | 用途 |
|--------|---------------------|------|
| SubAgentMiddleware | `Command` | 路由到子 Agent |
| AsyncSubAgentMiddleware | `Command` + `langgraph_sdk` | 远程 Agent 调用 |
| FilesystemMiddleware | `Command`, `Runtime` | 文件操作路由 |
| SummarizationMiddleware | `Command`, `get_config` | 获取 thread_id 做历史压缩 |
| PatchToolCallsMiddleware | `Runtime`, `Overwrite` | 修正工具调用参数 |
| SkillsMiddleware | `Runtime`, `ToolRuntime` | 动态注册技能工具 |
| PermissionMiddleware | `Command` | 权限校验后路由 |

---

## 附录：关键源码文件索引

| 文件路径 | 作用 |
|---------|------|
| `langgraph/graph/state.py` | `StateGraph` 类定义，图构建 API |
| `langgraph/pregel/__init__.py` | `Pregel` 执行引擎核心 |
| `langgraph/channels/` | Channel 实现（`LastValue`, `BinaryOperatorAggregate`, `Topic`） |
| `langgraph/checkpoint/base.py` | `BaseCheckpointSaver`, `CheckpointTuple` 定义 |
| `langgraph/checkpoint/memory.py` | `InMemorySaver` 实现 |
| `langgraph/checkpoint/postgres/` | PostgreSQL Checkpoint 后端 |
| `langgraph/checkpoint/sqlite/` | SQLite Checkpoint 后端 |
| `langgraph/types.py` | `Command`, `Interrupt`, `Checkpointer`, `Overwrite` 等类型 |
| `langgraph/config.py` | `get_config`, `get_store` 运行时配置 |
| `langgraph/store/base.py` | `BaseStore`, `Item` 持久存储抽象 |
| `langgraph/runtime.py` | `Runtime`, `get_runtime` 运行时上下文 |
| `langgraph/stream/` | Streaming v2 实现 (`StreamMux`, `StreamChannel`, `GraphRunStream`) |
| `langgraph/errors.py` | 错误类型体系 |
| `langgraph/graph/message.py` | `add_messages` Reducer 实现 |
| `langchain_core/runnables/base.py` | `Runnable`, `RunnableSequence`, `RunnableParallel` 核心定义 |
| `langchain_core/runnables/branch.py` | `RunnableBranch` 条件分支 |
| `libs/deepagents/deepagents/graph.py` | Deep Agents 对 LangGraph 的封装入口 |
| `libs/deepagents/deepagents/backends/state.py` | 基于 Channel read/send 的文件系统后端 |
| `libs/deepagents/deepagents/backends/store.py` | 基于 BaseStore 的持久文件系统后端 |
