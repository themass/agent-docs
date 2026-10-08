# Hindsight 部署、运维与故障排查

## 1. 部署拓扑

### 1.1 最小单机

```text
┌──────────────────────────────────────┐
│ hindsight-api :8888                  │
│   ├─ FastAPI                         │
│   ├─ MemoryEngine                    │
│   ├─ HTTP + MCP                      │
│   └─ optional embedded pg0           │
│                                      │
│ hindsight-worker（可选独立进程）      │
│   └─ poll async_operations            │
└──────────────────────────────────────┘
                 │
                 ▼
        PostgreSQL + vector/text ext
                 │
        LLM / Embedding / Reranker
```

开发和自包含 Docker 可以使用 embedded pg0；生产更推荐独立、备份、监控和可扩展的 PostgreSQL。官方发行包也支持 Oracle 后端，但具体特性要以当前 backend 实现和迁移兼容性为准。

### 1.2 生产拓扑

```text
Client / Agent
    │ TLS / auth proxy
    ▼
API replicas ───────► read replica（recall，可选）
    │                         │
    ├───────────────► primary PostgreSQL ◄──── Worker replicas
    │                         │
    ├───────────────► object storage（attachments）
    └───────────────► LLM / embedding / reranker endpoints
```

API 是无状态的（除了连接池、模型缓存和进程级并发控制），可横向扩展；任务状态、队列和 operation 结果在数据库中持久化，因此 Worker 可以独立扩缩容。

## 2. 启动顺序

1. 准备数据库和必需扩展；
2. 设置 LLM provider、API key、embedding/reranker 配置；
3. 运行 migration；
4. 启动 API；
5. 启动 Worker（如果使用异步 retain/consolidation/refresh）；
6. 检查 health、LLM health、vector/text index health；
7. 用一个独立 Bank 做 retain → recall → reflect 冒烟测试。

`MemoryEngine.initialize()` 会加载连接池、embedding、cross-encoder 等依赖，并初始化数据库/模型；因此启动时失败通常代表配置、扩展、网络或模型资源问题，不要把它归因于单个请求。

## 3. 关键配置族

配置定义集中在 `hindsight_api/config.py`。实际环境变量前缀通常是 `HINDSIGHT_API_`。

| 配置族 | 典型内容 | 影响 |
|---|---|---|
| Database | URL、backend、schema、pool、read replica | 连接、租户 schema、读写路由 |
| Vector/Text | vector extension、text search extension、ANN 参数 | Recall semantic/keyword arm |
| LLM | provider、model、timeout、retry、strict schema | retain/reflect/consolidation 默认模型 |
| Per-operation LLM | `RETAIN_*`、`REFLECT_*`、`CONSOLIDATION_*` | 把抽取、回答、后台巩固解耦 |
| Embeddings | provider、model、batch、max input | 写入向量和查询向量 |
| Reranker | provider、candidate cap、timeout、fallback | recall 延迟和排序质量 |
| Retain | chunk size、并发、fact budget、语言 | 写入成本、吞吐和事实粒度 |
| Recall | budget、max tokens、temporal、boost | 检索范围、延迟和上下文大小 |
| Reflect | max iterations、context、wall timeout | 工具调用循环成本和安全上限 |
| Worker | slot reservations、poll、stuck threshold | 后台并发和交互请求隔离 |
| HTTP/observability | gzip、tracing、metrics、audit | 运营可见性和网络开销 |

### 并发原则

LLM 请求同时受全局 cap 和 operation-specific cap 约束；retain/consolidation/refresh 不应耗尽所有 provider 或 CPU 资源，否则 interactive reflect 会排队。Worker 的 slot reservation 是隔离后台任务和前台请求的重要机制。

### 成本原则

- 低预算 recall 不等于低质量，只意味着候选和 token 上限更小；
- retain 是写入成本，包含抽取、embedding、实体和可能的链接；
- consolidation 是后台成本，可延迟但不能无限积压；
- reflect 是在线多轮成本，应设置 wall timeout、iteration 和 output token 上限；
- reranker 失败时应根据配置 fallback 到 RRF/interleave，而不是让整个 recall 永久不可用。

## 4. Health 与可观测性

至少区分以下状态：

1. **API liveness**：进程和 event loop 是否活着；
2. **DB readiness**：连接池、迁移、主库可写；
3. **LLM health**：retain、reflect、consolidation 使用的 provider 是否可用；
4. **Embedding health**：写入和 recall query embedding 是否可用；
5. **Reranker health**：是否超时、降级或积压；
6. **Worker health**：pending/processing 数量、stuck task、terminal write 失败；
7. **Data freshness**：last memory write、last consolidation、mental model stale；
8. **Index health**：vector/text index 是否存在、是否需要维护。

建议把指标按 `bank_id` 做谨慎聚合，不要把高基数原始 Bank ID 无限制写入 metrics label。详细请求和 LLM request 的内容要考虑隐私，默认只记录必要的延迟、token、provider、状态和 operation ID。

## 5. 异步任务生命周期

```text
submit
  → async_operations.status=pending
  → Worker claim（事务/锁）
  → processing + retry_count
  → stage/progress 更新
  → completed / failed / cancelled
  → 可选 webhook delivery
```

批量 retain、文件 retain、consolidation、graph maintenance、vector index maintenance、mental model refresh、bank transfer、webhook delivery 都可能异步。父 operation 等待子 operation 完成并聚合结果；失败优先于取消，避免吞掉根因。

### 取消与重试

- HTTP 客户端断开可触发 cooperative cancellation，阶段边界检查取消信号；
- Worker 重试必须考虑幂等性：任务可能已完成部分写入；
- retry 应有最大次数、退避和最终失败记录；
- terminal status 写入本身失败时不能简单把任务重新排队，否则可能重复执行；
- 操作员应优先查看 `error_message`、stage、retry_count、child operations 和 LLM request。

## 6. 典型故障排查

### 6.1 retain 成功但 recall 查不到

按顺序检查：

1. recall 是否使用了相同 Bank 或 Bank alias；
2. 请求是否被 tag scope、fact_type、时间过滤排除；
3. document/chunk/memory_unit 是否写入；
4. embedding 是否生成、向量维度是否匹配；
5. text search index 是否可用；
6. graph/maintenance 是否尚未完成（不应影响 semantic/basic keyword，但会影响图臂）；
7. recall budget、max_tokens、min_scores 是否过于严格；
8. read replica 是否延迟；
9. 租户 schema 是否正确。

### 6.2 recall 变慢

观察阶段耗时：query analysis、embedding、每个 retrieval arm、fusion、rerank、serialization。常见原因：

- reranker candidate cap 太高；
- embedding/reranker provider retry 或网络退避；
- temporal parser 在大量语言上做自动检测；
- graph expansion 或 entity lookup 扩张过大；
- 数据库 ANN/text index 不健康；
- read replica 延迟或连接池耗尽。

优先做限流、候选上限和 provider timeout，而不是直接提高 API worker 数量。

### 6.3 consolidation backlog

检查 pending/failed 数、每个 operation 的 stage 和 LLM provider 错误。积压可能来自：

- consolidation 并发过低；
- 单个 Bank 事实大量写入；
- provider rate limit；
- observation dedup/graph 查询变慢；
- Worker 被长任务占满；
- operation terminal update 失败。

处理方式：先修复 provider/DB，再调整 slot；不要无脑扩 Worker 导致 LLM、数据库和 reranker 级联过载。

### 6.4 reflect 返回失败或空答案

Reflect 对 tool error、无法生成工具调用、没有 done 结果通常应失败，而不是伪造“没有相关信息”。检查：

1. mental model/observation/raw recall 工具是否可用；
2. provider 是否支持 tool calling 和 structured output；
3. reflect wall timeout / max iterations；
4. evidence 是否被 tag scope 或预算过滤；
5. response schema 是否过严；
6. `disposition`、directives 或 context 是否导致问题不可答。

### 6.5 Bank 数据串租户

立即停止扩大流量，保存 request ID、tenant ID、bank ID、schema 和 audit log；检查 RequestContext、TenantExtension、bank table/schema 路由、tag scope、read replica 和缓存。多租户隔离是安全问题，不应只当作“过滤条件 bug”。

## 7. 备份、迁移与转移

- PostgreSQL 物理/逻辑备份应覆盖 Bank 数据、operation、history、directives、knowledge base 和审计；
- attachments 若在对象存储，数据库备份不包含二进制，需要独立备份；
- Alembic migration 必须在与 API 兼容的版本窗口内执行；
- bank export/import 是逻辑迁移，需验证 source IDs、时间、tags、entities、links、observations 和 mental models；
- 在生产执行 reprocess、delete、clone、import 前先导出并验证恢复路径。
