# 本地 Mock Poetry Domain API

在内存里复刻 `vvv-poetry` 的 agent 面,用于本地离线演示和联调。**仅限本机使用,不进镜像,不连任何数据库。**
接口依据:`docs/handoff/A-contract.md` §3、§9、§14。

## 一键启动整条链路

```bash
make content-dev-offline                 # Mock(8080) → MCP 控制桥(8101) → worker(8102) → BFF(8100)
make content-dev-offline ARGS=--studio   # 另外起 Studio(5190,需要 content-agent/frontend 已 npm install)
make content-dev-offline-status          # 看各服务的 pid / 健康
make content-dev-offline-down            # 全部停止(只按 .run/*.pid 记录的 pid 动手)
```

- 全部使用脚本内固定的**本地假令牌**,不读取 `.env`;`DEERFLOW_ENABLED=false`,运行走确定性 STUB。
- 每个子进程用 `env -i` 加白名单环境变量启动,不会继承你 shell 里的真实密钥。
- pid 与日志在 `content-agent/deploy/dev-mock/.run/`(已被 `.gitignore` 忽略)。
- 重复运行是幂等的:已在运行且就绪的服务只提示,不会重启。
- 用 `uv run --frozen --package <包>` 启动,不修改 `pyproject.toml` / `uv.lock`。
- worker 入口 `agent_worker.app` 由 S3 实现;模块还不存在时脚本会提示并继续启动其余服务
  (加 `--require-worker` 则改为报错退出)。此时 `POST /tasks/{id}/run` 会因 worker 不可达而失败。

## 单独启动 Mock

```bash
PORT=8080 \
POETRY_AGENT_INTERNAL_TOKEN=fake-agent-token \
POETRY_STUDIO_REVIEWER_TOKEN=fake-studio-token \
MOCK_JSON_NAMING=snake \
uv run --frozen --package poetry-agent-bff python content-agent/deploy/dev-mock/mock_domain_api.py
```

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `PORT` / `HOST` | 8080 / 127.0.0.1 | 监听地址(默认只绑本机) |
| `POETRY_AGENT_INTERNAL_TOKEN` | 空 | agent 令牌。空 = 视为未配置,agent 面一律 403 |
| `POETRY_STUDIO_REVIEWER_TOKEN` | 空 | studio 人类写令牌。空 = 未配置,studio 一律 503 |
| `MOCK_JSON_NAMING` | `snake` | 默认与真实 Java 一致(见下);`camel` 仅用于模拟有问题的宿主 |
| `MOCK_SEED_V004_ANNOTATIONS` | 空 | 设为 `1` 载入 V004 里真实存在的 2 条种子注释(默认 0 条) |

## 令牌与状态码(与 Java 一致,两类令牌互不通用)

| 面 | 请求头 | 未配置 | 令牌错误/缺失 |
|---|---|---|---|
| agent 面(`agent-orchestration/*`、`works/{id}/snapshot|integrity-gap-report`、`draft/proposals*`) | `X-Poetry-Agent-Internal-Token` | 403 | 403,体为 `AgentResponse.rejected` |
| studio 面(`/studio/*`) | `X-Poetry-Studio-Reviewer-Token` | 503 | 401 |

- `snapshot` / `integrity-gap-report` / `draft/proposals*` 另外要求 `X-Poetry-Agent-Run-Id`、`X-Poetry-Agent-Mandate-Id`、
  `Idempotency-Key`(≤128 字符)、`X-Poetry-Agent-Role`(`CONTENT_EDITOR|HISTORICAL_REVIEWER`),缺任一项 403。
- `agent-orchestration/*`(含契约 §3.1 新读路由)只校验令牌,不要求 run/mandate 头。
- agent 令牌调 studio 一律 401;studio 令牌调 agent 面一律 403。

## 响应信封与错误

`{status, data, audit_refs, next_action}`。`status`:`OK` / `REVIEW_REQUIRED` / `REJECTED` / `CONFLICT`。
业务校验失败 400 + `REJECTED`,状态冲突 409 + `CONFLICT`,`data.reason` 给出原因。

两处与 Java 一致的特例:
- 请求体缺失或不是合法 JSON(旧端点):`400 {"status":400,"error":"Bad Request"}`(Spring 默认形状)。
- `apply` 里 `CREATE_ANNOTATION` 的词表/存在性失败:`400 {"errno":400,"data":null,"error":"…"}`
  (Java 里它抛 `PoetryDraftService.Invalid`,由 `PoetryAuthoringAdvice` 渲染,不是 `AgentResponse`)。

## `MOCK_JSON_NAMING`

**默认 `snake`,与真实 Java 一致**:Java 的 agent 面已用显式 `@JsonProperty` 把所有 JSON 键固定为 snake_case
(`audit_refs`/`next_action`、`work_info`/`dynasty_id`、`work_id`/`audit_checks`/`audit_non_zero`/`target_ref` 等),
不再依赖宿主的 Jackson 命名策略。编排端点的记录是 `Map`,键来自 SQL 别名,本来就是 snake_case。

`camel` 选项**只用于模拟一个有问题的宿主**,以验证 BFF/worker 的 camelCase→snake_case 兜底规范化:

| 对象 | `snake`(默认) | `camel`(模拟问题宿主) |
|---|---|---|
| 旧端点信封 | `audit_refs` / `next_action` | `auditRefs` / `nextAction` |
| `snapshot`、`integrity-gap-report` 的 data | snake_case | camelCase(`workInfo`、`entityType`…) |
| 任务、运行、事件、提案(Map) | 恒为 snake_case | 恒为 snake_case |
| 新端点(契约 §3.1/§3.2) | 恒为 snake_case | 恒为 snake_case |

**请求体同时接受 snake_case 与 camelCase**(Java 用 `@JsonAlias` 接受两者),与 `MOCK_JSON_NAMING` 无关。
未识别的取值一律按 `snake` 处理。

## 路由一览

既有:`POST/GET tasks`、`tasks/{id}/runs`(POST)、`runs/{id}`、`runs/{id}/admission|state`(PUT)、`runs/{id}/events`(POST/GET)、
`proposals/{id}`(均在 `/api/poetry/v1/agent-orchestration/` 下);`works/{id}/snapshot`、`works/{id}/integrity-gap-report`、
`draft/proposals`、`draft/proposals/{id}/reviews|apply`、`works/{id}/compile-requests`(在 `/api/poetry/v1/` 下)。

契约 §3.1 新读路由(`/api/poetry/v1/agent-orchestration/` 下):`GET tasks`、`tasks/{id}/runs`、`proposals`、`proposals/{id}/items`、
`works`、`works/{id}/coverage`、`works/{id}/studio-view`、`sources`。分页统一 `{items,limit,offset,has_more}`,`limit` 默认 50、上限 200。

契约 §3.2 人类写(`/api/poetry/v1/studio/`):`PUT citations/{claimId}/{sourceId}/locator`、`POST sources/{id}/verification`、
`PUT proposals/{id}/items`。署名 2–100 字,拒绝含 `agent|bot|deerflow|system|mcp|llm|ai` 的署名;核验/填 locator 只允许
`HISTORICAL_REVIEWER|PLATFORM_ADMIN`。每次写入追加审计行(`GET /__mock/check-log` 可看)。

Mock 自有(无令牌,仅本机,不对应任何生产路径):`POST /__mock/reset`、`GET /__mock/check-log`、`GET /__mock/health`
(`/health/live` 是它的别名,供脚本探活)。

## 种子数据

文字逐字取自 `V002__draft_seed.sql` 与 `V004__chunwang_context_draft.sql`,没有自编史实;所有来源 `PENDING`,所有 locator 保持 `待…` 占位词。

- `work-chun-wang`《春望》:8 行、1 个文本版本、SCENE/CITY/WORLD/PERSON 四层背景草稿(各关联 2 行)、4 个 `PENDING` 来源、0 条注释。
- `work-demo-empty`:仅标题,无版本(Mock 自有,用于"从空白起草"演示)。

**与契约示例的差异**(以真实 SQL 为准):
- 文本版本 id 是 `text-chun-wang-draft`,不是契约 §3.3 示例里的 `text-chun-wang-v1`。
- V004 实际带有 2 条注释(`ann-chun-wang-shanhe`、`ann-chun-wang-fenghuo`)。按任务要求默认 0 条;`MOCK_SEED_V004_ANNOTATIONS=1` 可载入。
- 契约 §3.3 示例里的"12 条 claim / 10 条 citation"无法由 V002+V004 复现:种子里与春望相关的 claim 共 13 条、citation 共 11 条。
- `source-chun-wang-candidate`(V002)没有 `source_kind` / `reliability`,所以**核验它会被发布闸门挡住**(`blocking` 里列出原因)。这是真实数据的状态,不是 Mock 的缺陷。

**claim 范围**:`snapshot` 与 Java 一致,只取 `subject_id = 作品` 的 claim(春望共 3 条,看不到背景的 claim)。
`coverage`、`studio-view`、`works` 放宽为"作品自身 + 其背景"的 claim(7 条),否则 Studio 无法渲染四层背景的可信度状态。
真实 Java 实现(S1)是否同样放宽,需要对照确认。

## 和 Java 的有意差异

- 审计:Java 的 106 项审计不重算,固定返回 `audit_checks=106`、`audit_non_zero=[]`。
- `locator_state` 的占位判定是启发式:空为 `MISSING`;以 `待` / `未核对` / `TBD` 开头为 `PLACEHOLDER`;其余为 `SET`。
  Java 的 `gap` 计算只看 locator 是否非空,所以带占位词的 citation 在 `snapshot`/gap 里仍算"有 locator",但在 Studio 核验里不算 `SET`。
- 事务:`apply` 失败时回滚本次已做的注释/claim 写入(Java 靠 `@Transactional`)。
- 与 Java 相同、值得留意的行为:`apply` 不校验注释的 `version_id` 是否属于提案的作品。

## 测试(只写不跑,留到最后统一运行)

根 `pyproject.toml` 的 `testpaths` 只含 `content-agent/agent`,**本目录的测试不会被 `make test-all` 带上**,需要单独运行:

```bash
uv run --frozen pytest content-agent/deploy/dev-mock/tests
```

覆盖:令牌隔离、信封形状与命名模式(默认 snake、camel 选项、请求体双键名)、编排状态机、提案评审与 apply 校验(Java 词表、存在性、原子性)、D7 逐项语义、
studio 写入与来源核验门槛、coverage/studio-view/sources 形状、reset、种子文字与 V002/V004 逐字一致。
