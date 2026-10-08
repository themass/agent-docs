# Hindsight 开源项目架构文档

> 本目录是对本地 `../hindsight` 源码仓库的工程化整理，不是官方 API 文档的替代品。官方文档负责“如何使用”；本文档负责“系统为什么这样设计、请求如何流动、数据如何落库、后台如何运行以及改代码从哪里开始”。
>
> **源码快照**：`../hindsight` · **仓库提交**：`fb11ddfea` · **整理日期**：2026-10-08

## 先读哪一份？

| 文档 | 用途 |
|---|---|
| [ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md) | 主文档：从产品边界到运行时、三条核心管线、异步任务、数据一致性和扩展点 |
| [DATA_MODEL.md](./DATA_MODEL.md) | 数据模型：Bank、Document、MemoryUnit、Entity、Link、Observation、Mental Model、Knowledge Base 的关系 |
| [CODE_MAP.md](./CODE_MAP.md) | 源码导航：目录、关键类/函数、阅读顺序、修改某个能力应该触碰哪些文件 |
| [OPERATIONS.md](./OPERATIONS.md) | 部署与运维：进程、数据库、Worker、配置、健康检查、失败恢复、性能排查 |
| [SECURITY.md](./SECURITY.md) | 租户隔离、认证授权、tag scope、Memory Defense、审计与数据导出边界 |
| [INTERFACES.md](./INTERFACES.md) | REST/SDK/MCP 接口心智模型、核心调用示例、宿主生命周期和异步操作契约 |
| [TESTING_AND_EVALUATION.md](./TESTING_AND_EVALUATION.md) | 测试分层、质量指标、回归集和发布前验证清单 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 一页式速查：核心概念、请求路径、决策表和常见问题 |
| [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) | 设计动机：为什么不是简单的向量 RAG，为什么拆成 retain/recall/reflect |
| [INTEGRATIONS.md](./INTEGRATIONS.md) | 集成方式与宿主 Agent 接入边界 |
| [MEMORY_LANDSCAPE.md](./MEMORY_LANDSCAPE.md) | 与其他 Agent Memory / RAG / Agent Framework 的选型对比 |

## 一句话定位

Hindsight 是一个**服务化的 Agent 长期记忆系统**：宿主 Agent 通过 HTTP、MCP、SDK、LLM wrapper 或集成插件，将内容 `retain` 到隔离的 Memory Bank；系统把内容加工为带时间、来源、实体和关系的事实，使用语义、关键词、图和时间四类检索 `recall`，并通过工具调用循环 `reflect` 生成带证据的回答；后台 Worker 再把原始事实巩固为 observations，并维护图、索引和 mental models。

```text
宿主 Agent / CLI / Workflow
        │
        ├─ REST / SDK
        ├─ MCP（HTTP 或 stdio）
        ├─ LLM Wrapper / Hook / Integration
        │
        ▼
FastAPI API + RequestContext + TenantExtension
        │
        ▼
MemoryEngine（Bank 级隔离、配置解析、授权、编排）
        │
        ├─ Retain：parse → chunk → extract → resolve → embed → persist
        ├─ Recall：analyze → 4 arms → fuse → rerank → budget
        ├─ Reflect：mental models → observations → recall → expand → answer
        └─ Async：consolidation / graph / index / refresh / transfer / webhook
        │
        ├─ PostgreSQL + pgvector/可选向量扩展 + 文本搜索扩展
        ├─ 可选 Oracle 后端
        ├─ 对象存储（attachments / file storage）
        └─ LLM、Embedding、Reranker providers
```

## 重要边界

- Hindsight **不是** Agent loop、任务规划器或工具执行器；它提供记忆能力，宿主负责决定何时调用它。
- `recall` 是证据检索，默认不负责替用户生成最终答案；`reflect` 才是带推理和工具调用的回答接口。
- Bank 是最小的记忆隔离单元；同一部署可以有多个 Bank，但跨 Bank 查询不是默认行为。
- 原始事实、observations、mental models、knowledge pages 是不同层次，不能混为“摘要”。
- 本文档按源码确认事实描述；如果官方文档、当前代码和历史文档冲突，应以当前代码和对应测试为准。

## 阅读路线

1. 先读主文档 §2–§4，建立系统边界和运行时心智模型。
2. 再读 §5–§9，理解 retain、recall、reflect、consolidation 的数据流。
3. 想改代码时直接查 [CODE_MAP.md](./CODE_MAP.md)。
4. 想部署或排障时查 [OPERATIONS.md](./OPERATIONS.md)。
5. 想做多租户、插件或安全评审时查 [SECURITY.md](./SECURITY.md)。

## 源码入口

- API 服务：`../hindsight/hindsight-api-slim/hindsight_api/`
- 核心引擎：`.../engine/memory_engine.py`
- 写入管线：`.../engine/retain/`
- 检索管线：`.../engine/search/` 与 `.../engine/memories/pg/recall.py`
- 反思管线：`.../engine/reflect/`
- 巩固：`.../engine/consolidation/`
- 后台 Worker：`.../worker/`
- 数据库迁移：`.../alembic/versions/`
- HTTP/MCP：`.../api/http.py`、`.../api/mcp.py`、`.../mcp_tools.py`
- 集成：`../hindsight/hindsight-integrations/`
- 系统测试：`../hindsight/hindsight-system-tests/`、`../hindsight/hindsight-integration-tests/`
