# Hindsight 测试、评估与变更验证

## 1. 为什么不能只测 API 200

Hindsight 的一个请求可能同时涉及鉴权、Bank scope、LLM structured output、embedding、PostgreSQL、向量/文本索引、Worker、异步 operation、graph、consolidation 和 response serialization。单独 API happy-path 通过，仍可能出现：

- 跨 Bank/tenant 泄漏；
- retain 写入了原文但没有事实或向量；
- recall 因 filter/score/budget 漏掉关键证据；
- reflect 在工具失败后伪造回答；
- operation 卡在 processing；
- mental model refresh 用空内容覆盖旧页面；
- 某个可选 provider/backend 下不兼容。

## 2. 仓库测试分层

| 测试层 | 源码位置 | 目标 |
|---|---|---|
| 单元/模块测试 | `hindsight-api-slim/tests/` | extract、search、provider、store、config、错误边界 |
| API 测试 | `hindsight-api-slim/tests/` | schema、HTTP status、MCP、认证、附件 |
| 集成测试 | `hindsight-integration-tests/` | 对外 API/服务组合/宿主连接 |
| 系统测试 | `hindsight-system-tests/` | 从部署行为验证 retain/recall/reflect/operation 故事 |
| Eval/benchmark | `hindsight-system-evals/`、`hindsight-dev/benchmarks/` | 记忆准确率、consolidation、性能、成本 |
| 集成包测试 | `hindsight-integrations/<name>/tests` | Hook、wrapper、宿主适配 |

## 3. 功能变更的最低验证矩阵

### Retain

- 纯文本、批量、空内容、超长内容、文件、附件；
- world / experience 分类与 context；
- event/occurred/mentioned 时间；
- tags、metadata、document ID、重复重放；
- Memory Defense block/redact；
- provider 超时、structured output 失败、部分 batch 失败；
- 同步与异步结果一致性；
- source/document/chunk/fact/entity/link 是否可追溯。

### Recall

- semantic 同义问法；
- keyword 专名/版本号；
- graph 多跳；
- absolute/relative temporal query；
- Bank、fact type、tag/tag group、time filter；
- RRF、interleave、rerank fallback；
- max token、include chunks/entities、trace；
- 空 Bank、read replica 延迟、embedding/reranker 故障；
- result/source scores 的向后兼容性。

### Reflect

- mental model、observation、raw fact 的分层取证；
- source IDs 只能来自工具结果；
- directives、disposition、tag scope；
- max iteration/wall timeout；
- tool call 无效、工具抛错、provider 不支持工具调用；
- structured schema、语言、空证据与不可回答问题；
- refresh 失败不得覆盖已有 mental model。

### Async / security

- claim、retry、cancel、stuck、terminal write failure；
- parent/child operation 聚合；
- Bank/tenant/tag scope 在 Worker 内仍生效；
- export/import/clone/delete/reprocess；
- webhook 重试、签名、重复投递；
- audit 和不泄漏敏感原文。

## 4. 评估指标

| 层 | 指标 | 解释 |
|---|---|---|
| Retain | fact precision/recall、重复率、类型准确率、时间准确率 | 输入被正确转为可用事实 |
| Entity/graph | canonicalization、link precision、多跳覆盖 | 图是否提高而非污染召回 |
| Recall | Recall@k、MRR、nDCG、evidence coverage | 正确证据是否进入 prompt/结果 |
| Rerank | rerank gain、fallback rate、tail latency | 质量/时延权衡 |
| Reflect | answer correctness、citation validity、abstention quality | 回答是否有证据且不幻觉引用 |
| Consolidation | dedup、contradiction handling、freshness、source fidelity | 派生知识是否可靠 |
| Ops | p50/p95/p99、queue lag、failure/retry rate、cost | 系统是否可运营 |
| Security | isolation escape count、scope test coverage、redaction efficacy | 是否守住租户和数据边界 |

## 5. Golden datasets 与回归

建议维护可版本化的测试集：

1. **事实抽取集**：含语言、口语、否定、条件、多个时间、不同说话人；
2. **时间集**：绝对日期、相对日期、时间范围、冲突事件；
3. **实体集**：别名、拼写变体、同名实体、跨 Bank 同名；
4. **检索集**：语义、专名、图、时间和混合查询；
5. **冲突集**：新旧事实相反、观点与事实、撤回；
6. **安全集**：prompt injection、敏感数据、scope 绕过、恶意附件；
7. **长会话集**：长时序、token 压力、consolidation 和 mental model refresh。

每次调 prompt、embedding、reranker、fusion 或 provider 时，都应跑相同数据集并记录质量、成本、延迟，而不是凭单个 demo 判断提升。

## 6. 性能压测原则

- 分开测 retain、recall、reflect、consolidation，避免一个数字掩盖瓶颈；
- 用真实长度/附件比例/Bank 大小，而不是只有 10 条短文本；
- 同时测冷启动、热缓存、provider 限流和数据库索引刚重建后的状态；
- 收集每个 recall arm 的耗时和候选数；
- 测试 read replica 延迟和 Worker 堆积；
- 将 token、LLM、embedding、rerank 成本和吞吐绑定观察。

## 7. 发布前检查

```text
[ ] migration 可前进、可回滚/恢复，且备份路径已验证
[ ] API/OpenAPI/SDK response 兼容
[ ] Bank + tenant + tag scope 安全回归通过
[ ] retain / recall / reflect / async smoke 通过
[ ] provider failure 与 reranker fallback 通过
[ ] consolidation/mental model 不会覆盖健康旧数据
[ ] 关键 benchmark 无不可接受回退
[ ] 生产监控、告警和 dashboard 已覆盖新增能力
[ ] 文档、配置 reference、integration version 同步更新
```
