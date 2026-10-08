# Hindsight 架构速查

## 1. 系统是什么

Hindsight 是 Agent 的长期记忆数据平面，不拥有宿主 Agent 的主循环。它围绕一个 Bank 提供三种核心操作：

| 操作 | 输入 | 输出 | 主要职责 |
|---|---|---|---|
| `retain` | 文本、结构化内容、文件或附件 | 写入结果 / operation | 把输入变成可检索事实、文档、实体、链接和向量 |
| `recall` | 查询、过滤、预算 | 排序后的事实、分数、来源、可选 chunk/entity | 多路检索证据，不负责最终回答 |
| `reflect` | 问题、上下文、预算 | 带证据的自然语言或结构化回答 | 通过工具调用循环分层取证并综合 |

后台任务负责 consolidation、图维护、向量索引维护、mental model refresh、数据导入导出和 webhook 投递。

## 2. 核心请求路径

```text
HTTP/MCP/SDK
  → RequestContext（认证、租户、scope、取消信号）
  → FastAPI route
  → MemoryEngine
  → ConfigResolver + TenantExtension + memory store
  → PostgreSQL/Oracle + LLM/Embedding/Reranker
```

每个请求必须明确 `bank_id`。引擎在入口处解析租户和 Bank 权限，在各个读写阶段继续执行 tag scope 和 operation validator 检查。

## 3. 记忆分层

```text
Raw source
  ├─ documents / chunks / attachments
  └─ memory_units（world / experience / opinion / observation）
       ├─ entities + unit_entities
       ├─ memory_links
       └─ observation_history / mental_model_history

Curated / derived
  ├─ observations：后台由事实巩固得到
  ├─ mental_models：可配置查询驱动的知识页
  ├─ directives：反思时遵守的行为规则
  └─ knowledge_pages：可组织的知识库树
```

## 4. Recall 四路检索

```text
query
  ├─ semantic：embedding + vector index
  ├─ keyword：BM25 / full text
  ├─ graph：entity/link expansion
  └─ temporal：日期解析 + 时间窗口
        ↓
RRF 或 interleave fusion
        ↓
cross-encoder / fallback reranker
        ↓
recency + temporal + proof + score filters
        ↓
token budget / response
```

## 5. 最重要的源码文件

| 能力 | 文件 |
|---|---|
| 总编排和公共入口 | `hindsight-api-slim/hindsight_api/engine/memory_engine.py` |
| API 对外路由 | `hindsight-api-slim/hindsight_api/api/http.py` |
| retain 编排 | `.../engine/retain/orchestrator.py` |
| 事实抽取 | `.../engine/retain/fact_extraction.py` |
| 实体处理 | `.../engine/retain/entity_processing.py`、`.../memories/pg/entity_resolver.py` |
| 图链接 | `.../engine/retain/link_creation.py`、`.../memories/pg/link_expansion.py` |
| 检索与融合 | `.../engine/search/retrieval.py`、`fusion.py`、`reranking.py` |
| Reflect agent | `.../engine/reflect/agent.py`、`tools.py` |
| Consolidation | `.../engine/consolidation/consolidator.py`、`.../memories/pg/consolidation.py` |
| 后台任务 | `.../engine/task_backend.py`、`.../worker/poller.py` |
| 配置 | `.../config.py`、`.../config_resolver.py` |

## 6. 常见误解

1. `recall` 不是“只做向量搜索”：它有 query analysis、四路检索、融合、重排和预算裁剪。
2. `reflect` 不是把 `recall` 包一层 prompt：它有 mental model / observation / raw fact 的分层工具调用和完成工具。
3. observation 不是原文摘要的别名：它是巩固产物，有来源、历史和可能的失效/更新过程。
4. Bank 不是数据库名：它是逻辑隔离边界，底层可能使用 schema、bank_id 或租户扩展共同实现。
5. 异步 operation 不是简单的线程池：任务写入数据库、由 Worker claim、持久化状态并支持重试、取消和父子操作聚合。
