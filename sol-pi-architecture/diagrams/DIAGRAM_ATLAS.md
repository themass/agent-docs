# SoL-Pi 架构图集（全局）

> 配套 [ARCHITECTURE.md](../ARCHITECTURE.md)。**模块级 SP-01…SP-20**：[AGENT_MODULE_DIAGRAMS.md](./AGENT_MODULE_DIAGRAMS.md)。  
> 源码：`SoL-Pi/src/sol-pi/`。

---

## 图目录

| 编号 | 类型 | 标题 |
|------|------|------|
| G1 | architecture | 宿主循环 vs 扩展边界 |
| G2 | flowchart | 四机制总览 |
| G3 | sequence | 四机制全开 E2E |
| G4 | classDiagram | 扩展工厂与配置 |
| G5 | erDiagram | 会话侧存储实体 |
| M1 | flowchart | Action Fusion |
| M2 | sequence | Observation Pack 投影 |
| M3 | flowchart | Evidence Preserving Reducer |
| M4 | stateDiagram | Online Context Compact |
| M5 | sequence | `obs_recall` 分页 |

---

## G1 宿主与扩展边界

```mermaid
flowchart TB
    subgraph Host["宿主 coding-agent"]
        RL[runLoop]
        SM[SessionManager]
        TR[内置 edit/write/bash...]
    end
    subgraph SoL["SoL-Pi Extension"]
        IDX[index.ts 工厂]
        AF[action-fusion]
        OP[observation-pack]
        ER[evidence-reducer]
        OC[online-context-compact]
    end
    RL --> SM
    IDX --> AF
    IDX --> OP
    IDX --> ER
    IDX --> OC
    AF -.包装.-> TR
    OP -.context 事件.-> SM
    ER -.tool 结果.-> SM
    OC -.compact 边界.-> RL
```

**读图**：SoL-Pi **不实现** turn loop；只挂钩 ExtensionAPI 与事件。

---

## G2 四机制协作

```mermaid
flowchart LR
    MUT[文件变更工具] --> AF[Action Fusion<br/>合并 then_run]
    AF --> OBS[大 tool 输出]
    OBS --> OP[Observation Pack<br/>占位符]
    OBS --> ER[Evidence Reducer<br/>收据压缩]
    OP --> CTX[投影后 context]
    CTX --> OC[Online Compact<br/>经济型 compact]
    OC --> RL[触发宿主 compact]
```

---

## G3 四机制全开时序

```mermaid
sequenceDiagram
    autonumber
    participant H as 宿主 runLoop
    participant AF as Action Fusion
    participant T as edit+then_run
    participant OP as Obs Pack
    participant ER as Reducer
    participant OC as Online Compact

    H->>AF: tool: edit
    AF->>T: 队列路径规范化
    T-->>H: mutation 结果
    H->>OP: context 投影
    OP-->>H: 占位符替换大输出
    H->>ER: 候选大段日志
    ER-->>H: 收据写入 + 缩短结果
    H->>OC: turn 结束评估
    OC-->>H: 请求 compact / 等待
    H->>H: 宿主 compact()
```

---

## G4 扩展类图（逻辑模块）

```mermaid
classDiagram
    class SolPiExtension {
        +session_start(ctx)
        +registerTools()
        +subscribeEvents()
    }
    class Config {
        +validate()
        +featureFlags
    }
    class FileQueue {
        +enqueue(path)
        +normalize()
    }
    class ObservationLedger {
        +store(content)
        +placeholderFor()
    }
    class ReducerArchive {
        +receipts
        +journal
    }
    class OnlineState {
        +decideCompaction()
        +compactionInFlight
    }
    SolPiExtension --> Config
    SolPiExtension --> FileQueue
    SolPiExtension --> ObservationLedger
    SolPiExtension --> ReducerArchive
    SolPiExtension --> OnlineState
```

---

## G5 会话目录实体

```mermaid
erDiagram
    SESSION_DIR ||--o{ OBS_BLOB : content-addressed
    SESSION_DIR ||--o{ REDUCER_RECEIPT : stores
    SESSION_DIR ||--o{ PACK_LEDGER : stores
    SESSION_DIR {
        string session_id
        path root
    }
    OBS_BLOB {
        string hash PK
        bytes payload
    }
    REDUCER_RECEIPT {
        string id
        json quotes
    }
```

---

## M1 Action Fusion 流程

```mermaid
flowchart TD
    E[edit/write 调用] --> N[路径规范化]
    N --> Q[file-queue 串行]
    Q --> SHA[可选 SHA 防竞态]
    SHA --> RUN[执行宿主 execute]
    RUN --> TR{then_run?}
    TR -->|是| NXT[追加后续命令]
    TR -->|否| DONE[返回]
    NXT --> DONE
```

---

## M2 Observation Pack 投影时序

```mermaid
sequenceDiagram
    participant SM as SessionManager
    participant OP as observation-pack
    participant CAS as 内容寻址存储
    participant LLM as 模型可见 context

    SM->>OP: context 事件（全量 entries）
    OP->>OP: 计数 sentCounts
    alt 超过阈值且非前 N 次
        OP->>CAS: 存全文
        OP->>LLM: 占位符 + obs_id
    else 首次或收据豁免
        OP->>LLM: 原文或收据
    end
```

---

## M3 Evidence Reducer 流程

```mermaid
flowchart TD
    IN[大型 tool 输出] --> CAND{候选?}
    CAND -->|否| PASS[透传]
    CAND -->|是| LLM[归约模型]
    LLM --> RCPT[生成收据 + 引用校验]
    RCPT --> ARC[Archive 分片]
    RCPT --> OUT[缩短后的 tool_result]
    OP2[Obs Pack] -->|见收据前缀| SKIP[跳过二次打包]
```

---

## M4 Online Compact 状态

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Evaluating: turn 结束
    Evaluating --> WaitingHost: 需要 compact
    WaitingHost --> InFlight: 宿主 compact 中
    InFlight --> Idle: 完成
    Evaluating --> Idle: 不满足经济性
```

---

## M5 `obs_recall` 分页

```mermaid
sequenceDiagram
    participant M as 模型
    participant T as obs_recall 工具
    participant L as Ledger/CAS

    M->>T: recall(obs_id, offset)
    T->>L: readRecallChunk
    L-->>T: 分页字节
    T-->>M: 片段 + next_offset
```

---

## 章节对照

| 图 | ARCHITECTURE |
|----|----------------|
| G1–G3 | Part I |
| G4–G5 | §20–§23, 附录 |
| M1–M5 | action-fusion / observation-pack / reducer / online-compact 各节 |
