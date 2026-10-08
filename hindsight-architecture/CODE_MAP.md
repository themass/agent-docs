# Hindsight 源码地图与阅读指南

## 1. Monorepo 视角

| 目录 | 责任 | 是否运行时关键 |
|---|---|---|
| `hindsight-api-slim` | 核心 API、MemoryEngine、数据库、Worker | 是 |
| `hindsight-api` | 完整发行包/可选能力聚合 | 是，打包层 |
| `hindsight-all` / `hindsight-all-slim` | Python 发行组合 | 否，安装入口 |
| `hindsight-clients` | Python/TypeScript/Go/Rust 客户端 | 否，调用入口 |
| `hindsight-cli` | CLI 命令 | 否，运维/开发入口 |
| `hindsight-embed` | 无独立远程服务的嵌入式/daemon 模式 | 视部署方式 |
| `hindsight-control-plane` | Web 管理界面 | 否，控制面 |
| `hindsight-extensions` | tenant、API key 等扩展 | 可选 |
| `hindsight-integrations` | Agent SDK、CLI、MCP、wrapper 集成 | 可选 |
| `hindsight-docs` | Docusaurus 官方文档、示例、配置参考 | 否 |
| `hindsight-system-tests` | 黑盒系统验证 | 测试 |
| `hindsight-system-evals` / `hindsight-dev` | benchmark、实验与性能评测 | 测试/研究 |

## 2. 进程和入口

```text
hindsight-api
  → hindsight_api.main / server
  → MemoryEngine.initialize()
  → FastAPI app + HTTP/MCP routes

hindsight-worker
  → hindsight_api.worker.main
  → WorkerPoller
  → async_operations claim
  → MemoryEngine.execute_task()

hindsight-local-mcp
  → mcp_local.py / mcp_tools.py
  → stdio MCP transport
```

HTTP 路由集中在 `hindsight-api-slim/hindsight_api/api/http.py`，它负责 Pydantic 请求/响应、错误映射、取消信号、附件上传和调用 MemoryEngine；真正的业务编排不要从路由文件开始追到底，而应跳到 `MemoryEngine`。

## 3. MemoryEngine 分层

`engine/memory_engine.py` 是当前实现的“应用服务总入口”，职责多但边界清楚：

1. 初始化连接池、embedding、reranker、模型和任务后端；
2. 解析 Bank、tenant、config、tag scope；
3. 调用 retain/recall/reflect 子模块；
4. 提交和执行异步 operation；
5. 暴露 document、memory、entity、mental model、knowledge base、directive、transfer、webhook 管理能力；
6. 对失败、取消、operation 状态和审计做统一处理。

如果要拆分新能力，应优先在独立子模块完成算法/存储细节，再让 MemoryEngine 做授权、配置和生命周期编排。

## 4. Retain 阅读顺序

```text
memory_engine.retain_async / retain_batch_async
  → retain/orchestrator.py
    → chunk_storage.py
    → fact_extraction.py
    → entity_processing.py / entity_labels.py
    → embedding_processing.py / embedding_utils.py
    → fact_storage.py
    → link_creation.py
  → memories/pg/retain.py / writes.py
  → submit consolidation / graph / vector maintenance
```

关注点：

- 输入 canonicalization：文本、结构化 blocks、image/file attachments；
- chunk size、token budget、batch coalescing；
- LLM structured output 和失败重试；
- world/experience 分类、event dates、metadata/tags；
- entity resolution 和 link creation；
- idempotency/content hash/replay；
- Memory Defense 在抽取前的 block/redact；
- 写入成功与后台维护成功的边界。

## 5. Recall 阅读顺序

```text
memory_engine.recall_async
  → query_analyzer.py / temporal_extraction.py
  → search/retrieval.py
      ├─ semantic retrieval
      ├─ BM25 / keyword
      ├─ graph_retrieval.py
      └─ temporal retrieval
  → search/fusion.py
  → search/reranking.py
  → recall_boost.py / time_filter.py
  → response_models.py
```

数据库实现主要在 `engine/memories/pg/recall.py`、`expand.py`、`graph.py`。需要保留的诊断信息在 `search/types.py`：每条结果可以带 semantic、keyword、RRF、reranker、recency、temporal、proof 等分数。

## 6. Reflect 阅读顺序

```text
memory_engine.reflect_async
  → reflect/agent.py
  → reflect/tools_schema.py
  → reflect/tools.py
  → reflect/presentation.py / structured_doc.py
  → response_models.py
```

Reflect 是受预算限制的工具调用循环，不应把它简化成“先 recall 再 prompt”。典型工具层次：

1. 搜索/读取 mental models；
2. 搜索/读取 observations；
3. 调用 recall 取得原始 facts；
4. expand 事实上下文、实体和 chunk；
5. done 返回答案和已验证的 source IDs。

`disposition`、`directives`、tag scope、response schema 和语言设置在 MemoryEngine/ConfigResolver 层注入。

## 7. Consolidation 与维护

- `engine/consolidation/consolidator.py`：LLM 巩固策略和提示；
- `engine/memories/pg/consolidation.py`：候选选择、来源、写入和历史；
- `engine/graph_maintenance.py`：实体/链接维护队列；
- `engine/maintenance.py`：周期性清理、统计和保养；
- `engine/vector_index_health.py`：向量索引健康和维护；
- `engine/mental_model_refresh.py`：mental model 的异步 refresh；
- `engine/task_backend.py`：任务提交、claim、进度和状态。

## 8. 修改场景 → 文件

| 修改目标 | 首查文件 | 还要看 |
|---|---|---|
| 新增 API 字段 | `api/http.py`、`engine/response_models.py` | 客户端生成、OpenAPI tests |
| 改事实抽取 | `engine/retain/fact_extraction.py` | prompts、structured output、extract tests |
| 改切块/附件 | `engine/retain/chunk_storage.py`、`attachment_*` | token tests、multimodal tests |
| 新检索策略 | `engine/search/retrieval.py`、`types.py` | `fusion.py`、trace、recall tests |
| 改排序 | `reranking.py`、`recall_boost.py` | score response、latency fallback |
| 改 reflect 工具 | `reflect/tools.py`、`tools_schema.py` | agent loop、引用校验、structured response |
| 新异步任务 | `task_backend.py`、`memory_engine.execute_task`、`worker/poller.py` | operation parent/child、retry/cancel |
| 新租户策略 | `extensions/tenant.py`、`extensions/loader.py` | RequestContext、scope 和 bank tables |
| 新数据库字段 | Alembic migration + models/store | PostgreSQL/Oracle、transfer、rollback |
| 新宿主集成 | `hindsight-integrations/<name>` | README、tests、release script |

## 9. 测试策略

- 单元测试：围绕 retain/search/reflect/store 的局部行为；
- API 测试：HTTP schema、错误码、认证、MCP；
- 系统测试：真实数据库和多阶段 operation；
- integration tests：外部宿主 Agent 或 provider；
- benchmark/eval：LongMemEval、LoCoMo、性能、成本、consolidation 质量。

改动检索或抽取时，不要只跑 happy path；至少验证 Bank 隔离、空结果、超时、LLM provider 失败、重复 retain、删除/retraction、异步失败和可选扩展未安装的情形。
