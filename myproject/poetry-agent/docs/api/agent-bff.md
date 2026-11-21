# Agent BFF API v1(Poetry Studio 专用)

基础路径 `/api/poetry/v1/agent`。权威契约见 `docs/handoff/A-contract.md` §7;本文记录 BFF **实际实现**的行为。

- 统一错误体:`{"error":{"code","message","details?"}}`。请求校验失败为 422 `VALIDATION_ERROR`,`details=[{loc,message}]`(不回显输入原文)。
- 列表统一 `{items,limit,offset,has_more}`;`limit` 默认 50、上限 200。
- BFF 无状态:任务、运行、授权书、事件、提案、评审都在 Java 底座(经 MCP 控制桥)。BFF 不执行 agent 运行(由 `agent-worker` 执行),也不访问 DeerFlow 网关。
- **身份(服务端决定)**:默认必须登录。身份取自会话令牌;请求体里的 `actor` 可省略,若带了必须与令牌一致,否则 403 `ACTOR_MISMATCH`。`POETRY_STUDIO_AUTH=off` 才退回“请求自己声明身份”,仅限离线演示(`/auth/me` 与 `/health/ready` 会报告该模式)。详见下文“登录与账号”。

## 任务与运行

| 端点 | 作用 | 备注 |
|---|---|---|
| `GET /tasks` | 任务列表 | 过滤 `work_id` `status` `task_type` |
| `POST /tasks` | 创建任务 | 四类任务;作品不存在 → 404 `WORK_NOT_FOUND`;指令含祈使式控制请求 → 422 |
| `GET /tasks/{id}` / `GET /tasks/{id}/runs` | 任务 / 该任务的运行列表 | |
| `POST /tasks/{id}/run` | 创建运行并派发给 worker | 体可省略或 `{"runtime":"STUB"}`;`409 RUN_ALREADY_ACTIVE` `409 TASK_NOT_RUNNABLE` `503 WORKER_UNAVAILABLE` |
| `POST /runs/{id}/cancel` | 取消运行 | 已终态则幂等返回;取消后 `FAILED`,原因“已由编辑取消” |
| `GET /runs/{id}` | 运行回执 | 含最近一次 `budget`(可空) |
| `GET /runs/{id}/budget` | 预算消耗 | `{run_id,budget,event_id}` |
| `GET /runs/{id}/events` | SSE 事件流 | 支持 `Last-Event-ID` 或 `?after_event_id=`;连接由服务端保持;15 秒心跳 |

运行时选择:`DEERFLOW_ENABLED=true` 时为 `DEERFLOW`,否则 `STUB`(确定性运行时,不调用模型);编辑可强制 `STUB`,不能强制 `DEERFLOW`。DeerFlow 失败不会静默降级为 STUB(决定 D4)。

## 提案与评审

| 端点 | 作用 | 备注 |
|---|---|---|
| `GET /proposals` | 提案列表 | `status` ∈ `REVIEW_REQUIRED` `APPROVED` `REJECTED` `APPLIED`;列表项不含 `items` |
| `GET /proposals/{id}` | 提案详情 | 含逐项决定 `items`、`executable_count`、`approved_executable_count` |
| `GET /proposals/{id}/diff` | 结构化对照 | 每项:`label`(来源请求/解释/演绎/草稿/未考/缺口)、`executable`、`before`、`after`、`risks`、`item_decision` |
| `POST /proposals/{id}/review` | 人工评审 | 仅 `CONTENT_EDITOR` `HISTORICAL_REVIEWER`;批准且含可执行项时必须给出覆盖全部可执行项的 `item_decisions`,否则 422 `ITEM_DECISIONS_REQUIRED` |
| `POST /proposals/{id}/apply` | 把被批准的可执行项写入 **DRAFT** | 体必须含 `actor`;`409 NOTHING_TO_APPLY`;`503 ITEMS_UNAVAILABLE`(读不到逐项决定时拒绝盲目应用) |

提案只由 worker 经控制桥写入;**BFF 不提供提案写入口**(旧的 `POST /runs/{id}/proposals` 已删除,它没有鉴权,会成为注入通道)。

v1 里只有 `changes[].draft_payload.operation=CREATE_ANNOTATION` 可执行;其余类型批准后只作为编辑记录留存。批准而无可应用项时,运行直接记为 `COMPLETED`。

## 作品、覆盖与发布前检查

| 端点 | 作用 |
|---|---|
| `GET /works` | 作品列表与计数 |
| `GET /works/{id}/overview` | 内容总览(快照 + 背景—诗句关联 + 状态映射 + 缺口) |
| `GET /works/{id}/coverage` | 覆盖看板数据 |
| `GET /works/{id}/gap-report` | Java 完整性缺口报告 |
| `GET /works/{id}/precheck` | 发布前检查清单(R1–R12) |

`precheck`:规则名与 `pipeline/tools/scene-validator/rules.mjs` 一致。`DATA` 规则由 Java 数据判断;`BUNDLE` 规则需要编译后的 bundle(`POETRY_BUNDLE_DIR/bundle.json`),没有则为 `NOT_EVALUATED`,**不会判为通过**。`verdict`:有失败 → `BLOCKED`;有未评估 → `INCOMPLETE`;全部通过 → `READY_FOR_HUMAN_PUBLISH`(只表示可交给发布人判断,不是已发布,界面没有发布动作)。

## 出处核查(仅人工)

| 端点 | 作用 | 备注 |
|---|---|---|
| `GET /sources` | 来源列表(含引用与 `locator_state`) | 过滤 `verification_status` |
| `PUT /sources/citations/{claim_id}/{source_id}/locator` | 填写 locator 与摘录 | 占位词 → 422 `LOCATOR_PLACEHOLDER` |
| `POST /sources/{id}/verification` | 核验 / 驳回来源 | `decision` ∈ `VERIFY` `REJECT` |

两个写端点仅 `HISTORICAL_REVIEWER` `PLATFORM_ADMIN` 可用(403 `SOURCE_REVIEW_ROLE_REQUIRED`),由 BFF **直连 Java** 的 `studio` 端点,使用只有 BFF 与 Java 持有的 `POETRY_STUDIO_REVIEWER_TOKEN`。agent 链路(DeerFlow → MCP → 控制桥 → worker)没有该令牌,控制桥上也没有这些路由。

## 示例:创建缺口分析任务

```json
{
  "work_id": "work-chun-wang",
  "title": "核对《春望》发布前缺口",
  "task_type": "GAP_ANALYSIS",
  "actor": {"actor_id": "editor_001", "role": "CONTENT_EDITOR"},
  "instructions": "列出已观察到的缺口、证据引用和需要人工确认的问题。",
  "requested_profile": "authoring"
}
```

## 事件类型

`RUN_CREATED` `RUNTIME_ADMISSION` `RUN_STATE_CHANGED` `RUN_STARTED` `CONTEXT_LOADED` `STEP` `TOOL_CALL` `MODEL_USAGE` `BUDGET_UPDATE` `OUTPUT_ACCEPTED` `OUTPUT_REJECTED` `PROPOSAL_RECORDED` `RETRY` `CIRCUIT_OPEN` `RUNTIME_FAILED` `PROPOSAL_APPROVED` `PROPOSAL_REJECTED` `DRAFT_APPLICATION_COMPLETED` `RUN_CANCELLED`。事件只记元数据(模型名、耗时、token 数、是否降级),不记提示词与模型原文。

## 环境变量

`PORT` `POETRY_AGENT_PROFILE_ROOT` `POETRY_DOMAIN_CONTROL_URL` `POETRY_DOMAIN_CONTROL_TOKEN` `POETRY_API_BASE_URL` `POETRY_API_TIMEOUT_SECONDS` `POETRY_STUDIO_REVIEWER_TOKEN` `POETRY_WORKER_URL` `POETRY_WORKER_TOKEN` `POETRY_STUDIO_ORIGINS` `DEERFLOW_ENABLED` `POETRY_BUNDLE_DIR`(可选)。

## 登录与账号

| 端点 | 作用 | 备注 |
|---|---|---|
| `POST /auth/login` | 账号口令换会话令牌 | 体 `{user_id,password}` → `{token,expires_at,actor}`;`401 LOGIN_FAILED`(不区分账号不存在与口令错误)、`429 LOGIN_LOCKED`(带 `Retry-After`)、`503 AUTH_NOT_CONFIGURED`、`409 AUTH_DISABLED` |
| `GET /auth/me` | 当前身份 | `auth_mode` 为 `off` 时 `actor` 为 null 并带 `warning` |
| `POST /auth/events-ticket/{run_id}` | 事件流票据 | `EventSource` 不能带请求头:换 60 秒有效、只对该 run 有效的票据,再连 `/runs/{id}/events?ticket=…` |

除 `/health/*` 与 `/auth/login` 外,所有接口都要 `Authorization: Bearer <token>`;缺失或无效 → `401 AUTH_REQUIRED`。

- **令牌**:HMAC-SHA256 签名,8 小时有效,密钥 `POETRY_STUDIO_SESSION_SECRET`(≥32 字符;以 `change-me` 开头的占位值会被拒绝)。
- **账号**:JSON 文件 `POETRY_STUDIO_USERS_FILE`,口令只存 scrypt 哈希,文件放仓库外。文件改动立即生效且**每个请求都会查**:删除账号或改角色后,已签发的令牌马上失效。
- **限速**:同一(账号, 来源地址)5 分钟内失败 5 次即锁定。进程内计数,重启清零,多副本时不共享。
- **管理账号**(口令交互输入,不接受命令行参数):

```bash
python -m agent_bff.users add --file /安全位置/studio-users.json --id wang-reviewer --role HISTORICAL_REVIEWER --name 王审核
python -m agent_bff.users list --file /安全位置/studio-users.json
python -m agent_bff.users remove --file /安全位置/studio-users.json --id wang-reviewer
python -m agent_bff.users gen-secret
```

容器里:`docker compose exec agent-bff python -m agent_bff.users add --file /studio-auth/users.json --id … --role …`(账号文件在命名卷 `studio-auth`)。

## 已知缺口

- 没有注册、改密码、多因素;口令找回由运维重置。
- 令牌无法单独吊销(只能删账号或换密钥);8 小时有效期内的令牌随账号状态实时校验。
- 登录限速与票据都是进程内的,不适用于多副本。
