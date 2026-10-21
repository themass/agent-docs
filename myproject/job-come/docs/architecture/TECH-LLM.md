# TECH-LLM：模型路由、文档解析与可观测性

- **状态**：V1 实现与发布检查依据
- **最后更新**：2026-10-20

## 1. LLM 路由

- 路由配置：`backend/agent/llm/routing.yaml`；模板：`routing.example.yaml`。
- 服务端通过 `backend/server/src/jc/llm/` 调用模型，业务代码不得散落直连供应商 HTTP 请求。
- **凭证分层**：`routing.yaml` 只写模型 slug 与 **provider 名**；`providers.*` 把每个 profile 映射到 `.env` 里的 `api_base_env` / `api_key_env` 变量名（密钥不进 Git）。同一 scenario 内可按条目指定不同 `provider`，或内联 `api_base_env` / `api_key_env`。
- 逻辑开关：`JC_LLM_ENABLED`、`JC_LLM_ROUTING_PATH`。默认文本网关 `JC_LLM_API_*`，视觉 `JC_LLM_VISION_*`；多供应商时在 `.env` 增加如 `JC_LLM_ANTHROPIC_API_BASE` 并在 `providers` 注册。
- **故障转移交给进程内的 `litellm.Router`**：构建点只有一个，`backend/server/src/jc/llm/transport.py`。没有 litellm Proxy，不起独立进程。换模型等价于改 `routing.yaml`；低风险试法是把新模型放在链的第二位。
- scenario 的 endpoint 链翻译成 litellm 的 `fallbacks`，按 pinned SDK 的行为测试维护，改动前先读 `transport.py` 的模块注释：
  - **每个 endpoint 一个 `model_name`**（`{scenario}-{index}`）。共用一个名字会变成在链内**负载均衡**，而不是按顺序 failover——后面的模型是备胎，不是对等节点。
  - **fallback 映射按位置逐跳声明**（`[{s-0:[s-1,s-2]}, {s-1:[s-2]}]`），单条扁平映射只能覆盖第一跳，第二个模型失败可能使后续模型不可达。回归测试验证所有 endpoint 都被尝试且只调用一次，避免重复请求与重复计费。
  - `num_retries=0`：链本身就是重试策略，让 litellm 再重试同一个 endpoint 会成倍放大延迟。
- **缺 API key 的 endpoint 不进 Router**，但会以 `skipped` 写进审计表。没发起过的尝试不是失败的端点，不该进故障率；可是链头静默失配会让每个请求都由第二个模型应答，成本和模型都变了，审计必须看得见。
- 场景 `scenario` 即 `routing.yaml` 里的键（`ingest_fast` / `writer` / `coach` / `vision` / `flash`），也是审计日志的"分类"维度。
- **舟卡对话走同一条链**：DeerFlow 的 `backend/agent/deerflow/config.yaml` 绑定 `jc.llm.chat_litellm:ChatLiteLLMRouter`，其 `model:` 写的是 **scenario 名**（`coach` / `writer`），不是模型 slug。模型只在 `routing.yaml` 命名一次，harness 不再持有第二份会偷偷漂移的副本。
- `JC_LLM_ENABLED=true` 才执行真实解析/优化；无有效模型配置时应明确失败或降级，不得伪造成功结果。
- LiteLLM 使用本地 model cost map（`LITELLM_LOCAL_MODEL_COST_MAP=true`），启动时不应为了加载成本表访问通用互联网。

### 1.1 谁在调模型：工程直连 vs Agent

一个常被问错的问题是「我们是不是所有地方都走 agent」。不是，而且这是刻意的。
两种调用方式**都经同一条 litellm 链**（所以故障转移与审计一致），区别在有没有 agent 循环：

- **工程直连**：确定性任务——给定输入、要求固定形状的输出。走 `jc/llm/` 直接请求，
  方法论由宿主侧 `compose_writing_prompt` 组装进 prompt（见
  [`TECH-AGENT.md`](TECH-AGENT.md) §4）。没有 agent 循环，因为没有要规划的事。
- **Agent**：只有多轮对话一条。用户的意图要在对话里才成形，模型需要读写档案、
  按进度决定下一步问什么，这才需要工具与循环。

| 入口 | 执行者 | 方式 | scenario |
|---|---|---|---|
| `POST /profiles/upload` | `profile_structurer` | 工程直连 | `ingest_fast` |
| 同上（扫描件 / 图片） | `profile_vision` | 工程直连 | `vision` |
| `POST /jobs` | `jd_parser_service` | 工程直连 | `ingest_fast` |
| `POST /jobs/profiles/{id}/fit` | `fit_score_service` | 工程直连 | `flash` |
| `POST /profiles/{id}/elevate` | `resume_elevator` | 工程直连（`compose_writing_prompt`） | `writer` |
| `POST /profiles/{id}/export/review` | `resume_reviewer` | 工程直连（`compose_writing_prompt`） | `flash` |
| `POST /profiles/{id}/localize` | `localize_service` | 工程直连 | `flash` |
| `POST /agent/sessions/{id}/messages` | DeerFlow harness | **Agent** | `coach` |
| 同上（消息带图片） | `agent_message_vision` | 工程直连 | `vision` |

舟卡那一行的角色是**运行时判定**的：档案够生成简历时是 `resume-coach`，
不够时是 `profile-interview`，工具面随之不同。见
[`TECH-AGENT.md`](TECH-AGENT.md)「访谈轮的角色与工具面」。

**完全不调模型的路径**，列出来是因为它们容易被误认为需要模型：
`POST /profiles/{id}/intake`、`/intake-answers`、`/intake-split`，
以及工具 `jc_intake_plan`、`jc_intake_record`。建档是 JC 唯一一条
**用户与档案之间没有模型**的路径，口述拆分按用户自己的标点做，
理由见 [`TECH-AGENT.md`](TECH-AGENT.md)「对话建档」。

## 2. 文档解析流水线

```text
上传文件（PDF / DOCX / TXT / 图片；旧版 .doc 提示转 docx）
  → MIME/大小/权限校验
  → 本地文字提取与页面检查（无模型）
  → 必要时本地备用提取（无模型）
  → 选择一次解析策略：文本结构化 或 视觉结构化
  → 在统一截止时间内执行（模型失败只在同一 scenario 内回退）
  → 成功保存草稿 / 失败保存失败状态，不写入伪成功档案
  → 用户核对与确认
```

| 格式 | Route A（确定性） | Route B（本地增强） | 视觉路由 |
|------|-------------------|------------------|----------|
| **PDF** | 可读文字层 → `ingest_fast` | 文字不足且未发现扫描页时，仅尝试本地 MarkItDown，再选择路线 | 扫描/混合页 → 整份渲染 → `vision`；超过 5 页明确失败，禁止静默截断 |
| **DOCX** | 可读原生文字 → `ingest_fast` | 本地文字不足时先 MarkItDown；不是模型失败后的重跑 | 仍无可读文字时才使用内嵌图片 → `vision` |
| **TXT** | 全文 → `ingest_fast` | — | — |
| **图片** | — | — | 整文件 → `vision` |
| **.doc** | 不支持 | — | 返回友好提示，请另存为 docx |

- Route B 是服务端受控依赖 `markitdown==0.1.5`：仅接收本次上传的内存 bytes、禁用插件、不提供 URL 或任意服务器路径；输入不超过 10 MB，转换在工作线程执行并有 12 秒超时，输出最多保留 50,000 字符；它不是 Agent/MCP 工具，不扩大浏览器、网络或文件系统权限。
- 策略与执行分离：`ingest_plan.py` 是无 I/O 的策略函数；`DocumentExtractor` 提供本地证据；`ProfileIngestService` 负责有截止时间的流水线；模型切换只由 `LLMRouter` 负责，不叠加另一套 fallback。
- 字段稀疏、模型超时、格式错误不再触发 OCR。正常头像/Logo 不作为 OCR 依据。PDF 扫描页采用“文字稀少 + 大幅图片”启发式检测；混合 PDF 目前整份视觉解析，尚未实现逐页 OCR 合并。
- 解析默认总预算 `JC_INGEST_TIMEOUT_SECONDS=90` 秒；结构化文本流单模型最多 `JC_INGEST_STREAM_ATTEMPT_SECONDS=30` 秒，读空闲/视觉请求上限 `JC_INGEST_ATTEMPT_TIMEOUT_SECONDS=25` 秒。所有模型尝试共享总预算，不按 fallback 次数叠加；本地提取和 PDF 渲染在线程执行，不阻塞异步轮询。线程取消不等于强制终止原生转换代码。
- 上传接受后以 `jc_profile_source` 作为持久队列；每个 API 实例的 dispatcher 每 10 秒检查 pending / lease 过期任务，数据库条件更新提供跨实例原子 claim，默认每实例最多并行 2 份。lease 240 秒，大于受限的单次解析预算，worker 崩溃后自动重领；部署此行为前必须应用 migration `017_profile_parse_lease`。这是每实例并发上限，多实例总并发随实例数相乘，应按模型供应商吞吐配置。
- 原始简历成功解析后递增 `jc_profile.version`，与快照 `(profile_id, version_after)` 唯一键保持一致；每次派生 track 写入使用独立版本，避免解析成功后因版本冲突导致后续步骤失败。
- 生产模型失败标记来源为 `failed` 并保留原档案，不再把模型不可用转换成成功占位稿。LLM 关闭或旧 `.doc` 的显式降级兼容行为未在本次移除。
- 前端解析期间保持“上传解析”，锁定后续步骤；阶段展示区分本地提取、扫描识别和结构化，不再向终端用户展示查日志指令。
- 文档解析输出是**草稿**，不是用户已确认事实。
- **可复制的 PDF 文字层**走 `ingest_fast`；**扫描页 / 图片 / 内嵌图**走 `vision`（如 `qwen-vl-ocr`），与文本链分离。
- JSON 任务把空响应、非 JSON、无 choices/message 和 schema 不匹配视为可控的 endpoint 失败；同一 scenario 会继续尝试下一个模型。这类失败 HTTP 状态是 200，litellm 视为成功，JC 不认，因此审计表用 `validator_failed` 标记、`error_code=invalid_response` 分组。
- **判定必须发生在调用栈内部**：`response_validator` 通过 `litellm.post_call_rules` 执行（`transport.validation_rule`），抛错后 Router 把它当作该 endpoint 失败并换下一个。调用返回之后再 `json.loads` 是**换不了模型**的——那只会把异常扔给用户。所有结构化 JSON 调用都必须用 `response_validator=` 这个形式。
- **应用日志**（`logger.*`、JSON 日志）只保留错误类别、文件名、路由与响应元信息，不得写入简历正文、密钥或模型响应全文。模型 payload 的唯一落地位置是第 4.1 节的审计表，由 `JC_LLM_LOG_PAYLOAD` 单独控制。
- 文档解析评测应使用固定样本、可比较指标和错误样例；机器结果写入 `docs/evidence/document-evaluation.json`，不替代发布结论。

## 3. 简历生成与导出质量

1. 从已确认档案生成优化稿；
2. 用 reviewer prompt 做事实、结构、语言与岗位针对性检查；
3. 保留 `elevation_map`，使用户能看见表达上的变化；
4. 生成 HTML、PDF、DOCX；
5. 对中英文、分页、字体、链接和下载链做实际检查。

浏览器不可用、生成失败、TOS 上传失败必须以可见错误结束；不得把缺失导出物当作成功。

## 4. 可观测性

### 4.1 LLM 调用审计日志

两张表，`jc_llm_call`（一次逻辑调用）+ `jc_llm_call_attempt`（链上每次 endpoint 尝试）。拆两张是因为一次业务操作在 failover 下可能打到三个模型，合成一行就答不出这个日志存在的意义：**用户看到的那个答案究竟是哪个模型产出的，它前面那些失败在失败什么**。

| 关键列 | 含义 |
|---|---|
| `scenario` | 分类：`routing.yaml` 的场景键，或 agent 路径的 skill |
| `caller` | 哪段代码发起（`resume_elevator` / `profile_structurer` / `agent` …） |
| `channel` | `router`（确定性服务）或 `harness`（舟卡对话） |
| `final_model` | **真实生效的模型**，不是链里配置的头一个；全链失败时为空 |
| `attempt_count` / `error_code` | 试了几次、按稳定码分组的失败原因 |
| token / `cost_micro_usd` | 用量与成本（整数微美元，避免浮点累计漂移） |
| `trace_id` / `user_id` / `profile_id` / `session_id` | 追溯与按用户、按分类聚合 |
| `prompt_text` / `response_text` / `reasoning_text` | 输入、输出、思考原文，**仅在 `JC_LLM_LOG_PAYLOAD=true` 时写入** |

**审计是观察者，不是 router 代码**（`jc/llm/audit_hook.py`）。调用方只声明"一次逻辑调用"的边界——因为只有它知道边界在哪；litellm 每次**物理**尝试各发一个事件，没有边界就会一次 failover 写出三行，成本重复计、"失败了几次调用"也答不出来。

**成功由调用方上报，失败由回调收集**，这个分工是实测结果不是风格选择：

| | litellm 事件时序 | 所以 |
|---|---|---|
| 失败 | **内联**触发，在下一跳之前，拿得到 model 与异常 | 由 `JCAuditLogger.log_failure_event` 收集；这也是调用方唯一看不到的那些尝试 |
| 成功 | 丢进 `GLOBAL_LOGGING_WORKER` 后台队列，**在调用方拿到响应并关闭 scope 之后**才跑 | 由调用方 `report_success(response)` 上报——它手上就有真实 model、usage、cost，不需要等 |

早期版本两边都从 callback 取，结果**每一次成功的 failover 都被记成失败**，因为成功事件到得比写行晚。响应对象自带 `model` / `usage` / `_hidden_params.response_cost`，"成功"这件事根本不需要等回调。

迟到的失败事件**不允许覆盖已记录的成功**（`scope.status != "success"` 才覆写）：litellm 会把回调通过复制的 context 派发到其他线程，事件可能在答案已记录之后才落地，放过去就会把一次恢复成功的链记成故障——而且行本身格式完好，线上根本看不出来。

两个 scope flavour，因为 harness 用**同步**路径从 worker 线程流式输出（`deerflow/client.py` 的 `stream()` 是 sync generator）：`llm_call_scope`（async，直接落库）与 `sync_call_scope`（同步，经 sink 回请求 loop）。`ChatLiteLLMRouter` 四个生成方法全部显式实现——`_astream` 若让 LangChain 从同步版派生，行会在没有 event loop 的线程上产出，于是从 sink 离开而不是落库；async 调用方没装 sink，**行就被静默丢弃**，agent 的用量会直接从审计表消失。

硬约束：

- **写日志失败绝不影响业务调用**，`record_call` 内部吞掉所有异常只留 warning。
- 审计写入**自己开短 session**，不复用业务请求的那个 —— `release_db_connection` 要求调模型前先结束读事务，到要落日志时业务 session 已被回滚。
- agent 路径跑在 worker 线程，不碰数据库：async engine 的连接池属于请求 loop，在该线程不可用，所以行经 `audit_sink` 回到请求 loop 再落库。身份（user/profile/session）也在该线程重新绑定——`threading.Thread` 不继承调用方的 ContextVar。见 `adapters/deerflow_harness_client.py` 的 `_audit_context`。
- `prompt_text` 等三列含**简历个人信息**。留存由 `JC_LLM_LOG_RETENTION_DAYS`（默认 90 天）+ `scripts/prune_llm_log.py` 执行；该脚本另有 `--forget-payload-after` 只清正文、保留成本与可靠性指标。
- 查询接口 `GET /api/v1/admin/llm/calls`、`/llm/calls/{id}`、`/llm/usage`（见 `TECH-API.md`）。详情默认**不返回** payload，需显式 `include_payload=true`。

开关：`JC_LLM_LOG_ENABLED`、`JC_LLM_LOG_PAYLOAD`、`JC_LLM_LOG_PAYLOAD_MAX_CHARS`、`JC_LLM_LOG_RETENTION_DAYS`。

### 4.2 Trace 后端

- Langfuse 是可选的 LLM trace 后端。配置 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST` 后开启 `LANGFUSE_TRACING=true`。
- Trace 应关联请求、用户匿名标识/会话、模型、skill/tool、耗时、token、错误与取消；不要记录明文密码、密钥或不必要的完整敏感档案。
- 生产发布必须有 API 错误日志、Agent/工具调用审计、依赖健康检查和告警策略。详细操作见 [`../operations/OPS-DEVELOPMENT.md`](../operations/OPS-DEVELOPMENT.md)。


### 结构化解析的流式传输边界

`ProfileStructurer` 通过 `LLMRouter.acompletion(buffered_stream=True)` 接收模型流。
传输层按已有配置的别名逐一尝试，禁用 SDK 内层 fallback，包含消费中断和校验拒绝的故障切换；
不能把“收到 HTTP 响应头”当成功。只有流正常结束、finish_reason=stop、JSON/schema 与非空事实校验通过后，
才将完整档案交给业务层保存。取消/总截止时间不触发下一模型，连接在退出时关闭。
每次调用仍是一条 LLM 审计，失败尝试附在同一记录，日志不打印简历正文。

`llm_buffered_stream` 日志记录 start/first_chunk/validated/failed、模型别名及耗时，
用于区分“首包一直没有到”和“流活跃但生成耗时长”。这些是后端传输日志，不代表前端已展示部分档案。
目前 ingest_fast 三个候选均经过 gateway；模型切换不能等同于跨网关容灾。

### 生成参数与 token 预算（2026-10-20）

输出上限统一由 `backend/agent/llm/routing.yaml` 持有：

```yaml
defaults:
  max_tokens: 100000
```

所有业务场景（解析、writer、coach、flash 质检、vision）继承默认值；某个 endpoint
可以显式覆盖 `max_tokens`，适用于已经确认网关实际支持较小上限的情况。该值必须为正数。
已移除 reviewer 的 4096 硬编码及 DeerFlow 模型配置中的独立输出上限，避免后者覆盖
各 fallback endpoint 的配置。调用接口仍允许显式 `max_tokens` 覆盖，受控测试中的
小 token 请求不属于业务默认值，不做机械替换。

| 控制 | 配置位置 | 当前基线 | 作用 |
|---|---|---|---|
| 单次输出上限 | routing.yaml `defaults.max_tokens` | 100000 | 请求允许的最大输出，不是输出长度目标 |
| 模型上下文容量 | `JC_MODEL_CONTEXT_WINDOW` / DeerFlow 模型元数据 | 200000 | 独立于输出上限；实际模型/网关容量需验证 |
| 上下文压缩触发 | `JC_SUMMARIZATION_TRIGGER_TOKENS` 或 ratio | 自动值约 32000，可被环境覆盖 | 不是输出截断阈值 |
| 整轮累计用量 | `JC_TOKEN_BUDGET_MAX_TOKENS` | 150000 | 整轮 input+output 累计预算，不是单次输出容量 |
| 提取任务思考策略 | ingest_fast endpoint 参数 | none / disabled | 只影响解析，不改 Agent 对话策略 |
| HTTP/流/业务截止时间 | 场景 timeout 和 `JC_INGEST_*`、review 配置 | 按任务分别配置 | 不因输出上限增大自动取消 deadline |
| temperature | routing 默认 / 调用显式覆盖 | 0.1；reviewer 0.0 | 保留任务差异，不统一机械替换 |

边界：100000 是当前请求策略，**不是已验证的模型能力声明**。这些网关模型别名的
最大输出、思考开关方言、以及 input+output 总容量仍需要有界真实调用/网关文档确认。
不猜测模型上限，也不在失败时静默缩小并保存截断内容。结构化任务仍须完整结束且通过
JSON/schema 校验。输出上限变大不能解决 reasoning-only 超时、上游过载或慢首包。
