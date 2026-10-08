# Understand-Anything 架构图集（全局）

> 配套 [ARCHITECTURE.md](../ARCHITECTURE.md)。**各 Agent + core 模块**：[AGENT_MODULE_DIAGRAMS.md](./AGENT_MODULE_DIAGRAMS.md)。  
> 源码：`Understand-Anything/understand-anything-plugin/`。

---

## 图目录

| 编号 | 类型 | 标题 |
|------|------|------|
| G1 | architecture | 宿主 · 技能 · Core · Dashboard |
| G2 | erDiagram | 知识图谱节点/边域 |
| G3 | sequence | 全量分析流水线 |
| G4 | flowchart | 增量更新决策 |
| G5 | classDiagram | GraphBuilder / Schema |
| M1 | sequence | file-analyzer 两阶段 |
| M2 | flowchart | merge + graph-reviewer |
| M3 | sequence | Dashboard 加载 |
| M4 | flowchart | Tree-sitter 插件 |
| M5 | sequence | Tour 生成 |

---

## G1 系统总览

```mermaid
flowchart TB
    subgraph Host["IDE 宿主 Agent"]
        SK[/understand 技能]
        DISPATCH[子 Agent 调度]
    end
    subgraph Plugin["understand-anything-plugin"]
        AGENTS[agents/*.md]
        SKILLS[skills/*]
        CORE[packages/core]
    end
    subgraph Artifacts[".ua/ 产物"]
        G[knowledge-graph.json]
        FP[fingerprints.json]
        TOUR[tours.json]
    end
    subgraph UI["Dashboard"]
        API[静态服务 + Token]
        RF[ReactFlow + Worker 布局]
    end
    SK --> DISPATCH
    DISPATCH --> AGENTS
    AGENTS --> CORE
    CORE --> Artifacts
    Artifacts --> API --> RF
```

---

## G2 图谱实体（逻辑 ER）

```mermaid
erDiagram
    PROJECT ||--o{ FILE_NODE : contains
    FILE_NODE ||--o{ SYMBOL_NODE : contains
    SYMBOL_NODE ||--o{ EDGE : participates
    LAYER ||--o{ FILE_NODE : groups
    TOUR ||--o{ TOUR_STEP : contains
    TOUR_STEP }o--o{ FILE_NODE : references
    FILE_NODE {
        string id PK
        string type
        string filePath
    }
    EDGE {
        string type
        string source FK
        string target FK
    }
```

**读图**：27 种节点 / 38 种边在 `schema.ts` 枚举；ER 为概念聚合。

---

## G3 全量流水线时序

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant PS as project-scanner
    participant FA as file-analyzer x N
    participant MG as merge-batch-graphs
    participant AA as architecture-analyzer
    participant TB as tour-builder
    participant GR as graph-reviewer
    participant DB as Dashboard

    U->>PS: 扫描仓库
    PS-->>FA: batches + neighborMap
    par 并行批次
        FA->>FA: Phase1 脚本 + Phase2 LLM
    end
    FA-->>MG: batch graphs
    MG-->>AA: 合并图
    AA-->>TB: layers + 模块边
    TB-->>GR: tours 草稿
    GR-->>U: 校验 / 修复建议
    U->>DB: 打开 Dashboard
```

---

## G4 增量更新决策

```mermaid
flowchart TD
    GIT[git / 工作区变更] --> FP[构建 FingerprintStore]
    FP --> CMP[逐文件 NONE/COSMETIC/STRUCTURAL]
    CMP --> CL[classifyUpdate]
    CL --> SKIP[SKIP]
    CL --> PART[PARTIAL_UPDATE]
    CL --> ARCH[ARCHITECTURE_UPDATE]
    CL --> FULL[FULL_UPDATE]
    PART --> FA2[重跑部分 file-analyzer]
    ARCH --> AA2[+ architecture + tour]
    FULL --> ALL[全量 /understand]
```

---

## G5 核心类图

```mermaid
classDiagram
    class GraphBuilder {
        +addNode()
        +addEdge()
        +build() KnowledgeGraph
    }
    class TreeSitterPlugin {
        +analyzeFileFull()
        +analyzeFileStrict()
    }
    class validateGraph {
        +tier1..4
    }
    class FingerprintStore {
        +files: Record
        +gitCommitHash
    }
    class classifyUpdate {
        +UpdateDecision
    }
    GraphBuilder --> validateGraph
    FingerprintStore --> classifyUpdate
    TreeSitterPlugin --> GraphBuilder : 脚本输出
```

---

## M1 file-analyzer 两阶段

```mermaid
sequenceDiagram
    participant A as file-analyzer Agent
    participant S as 捆绑提取脚本
    participant TS as TreeSitterPlugin
    participant LLM as 宿主 LLM

    A->>S: batch JSON 输入
    S->>TS: 每文件 AST
    TS-->>S: 结构 JSON
    S-->>A: Phase1 结果
    A->>LLM: 结构 + 源码片段
    LLM-->>A: nodes/edges/summary
    A->>A: 写批次子图文件
```

---

## M2 合并与审阅

```mermaid
flowchart TD
    B1[batch graph 1] --> MG[merge]
    B2[batch graph 2] --> MG
    MG --> DEDUP[id 去重 + 边合并]
    DEDUP --> G[knowledge-graph.json]
    G --> GR[graph-reviewer 9 checks]
    GR -->|FAIL| FIX[定向重跑 Agent]
    GR -->|PASS| SHIP[发布 / Dashboard]
```

---

## M3 Dashboard 加载时序

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as 静态 API
    participant V as validateGraph
    participant Z as Zustand store
    participant W as ForceLayout Worker
    participant R as ReactFlow

    B->>API: Token + 并行 fetch 五路
    API-->>B: graph/meta/tours/...
    B->>V: 校验图谱
    V-->>Z: normalized graph
    Z->>W: 布局计算
    W-->>R: positions
    R-->>B: 可交互图
```

---

## M4 Tree-sitter 管线

```mermaid
flowchart LR
    REG[LanguageRegistry] --> WASM[grammar wasm]
    WASM --> PLG[TreeSitterPlugin]
    PLG --> EXT[LanguageExtractor]
    EXT --> OUT[StructuralAnalysis JSON]
    OUT --> FA[file-analyzer / 测试]
```

---

## M5 Tour 生成

```mermaid
sequenceDiagram
    participant TB as tour-builder
    participant G as 合并图
    participant LLM as LLM
    participant TOPO as Kahn 拓扑排序

    TB->>G: layers + 关键边
    TB->>LLM: 步骤文案 + 约束
    LLM-->>TB: TourStep 列表
    TB->>TOPO: 依赖排序
    TOPO-->>TB: tours.json
```

---

## 章节对照

| 图 | ARCHITECTURE |
|----|----------------|
| G1–G3 | §1–§3 |
| G4 | §41–§42 |
| G5 | §6–§8 |
| M1 | §9 file-analyzer |
| M2 | §18, §35 |
| M3 | §11 |
| M4 | §8 |
| M5 | §4 |
