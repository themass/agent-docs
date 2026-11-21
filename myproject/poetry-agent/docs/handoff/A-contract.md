# 任务 A 内部接口契约(Java ↔ 控制桥 ↔ BFF ↔ Worker ↔ Studio)

日期:2026-11-06。本文是任务 A 内部各部分的**唯一接口依据**。Java 新端点、Mock、MCP 控制桥、BFF、Worker、Studio 都按本文实现;改动先改本文。约束以 `docs/specs/2026-11-06-parallel-work-contract.md` 为准(不跑测试、不 git 提交、不连真实库、不执行 migrate-*、V001–V008 不可改、MySQL 5.6、不外泄密钥、不读 `.env` 的值)。

## 0. 现状事实(已读代码核实)

- Java 已有:`/api/poetry/v1/agent-orchestration/*`(任务/运行/事件/提案读,头 `X-Poetry-Agent-Internal-Token`)、`/api/poetry/v1/works/{id}/snapshot|integrity-gap-report`、`/draft/proposals`(创建/评审/应用,头同上加 `X-Poetry-Agent-Run-Id/Mandate-Id/Role`、`Idempotency-Key`)。
- Java 词表(`Vocabulary.java`):audience=`PRIMARY|JUNIOR|SENIOR`;certainty=`KNOWN|LIKELY|DISPUTED|UNKNOWN`;annotation_kind=`WORD|PHRASE|ALLUSION|IMAGE|RHYME|OTHER`;claim_kind=`FACT|INTERPRETATION|DRAMATIZATION`;layer=`SCENE|CITY|WORLD|PERSON`;source verification=`PENDING|VERIFIED|REJECTED`。
- **已发现的不一致(本任务修复)**:BFF `AnnotationDraftPayload` 与 `pipeline/contracts/proposal.schema.json` 的 audience(`PRIMARY|MIDDLE|GENERAL`)、certainty(`HIGH|MEDIUM|LOW|UNKNOWN`)与 Java 词表不符,批准后应用必被 Java 拒绝。统一改为 Java 词表。
- **Jackson 命名风险(已处理,不再依赖宿主配置)**:宿主的全局 Jackson 命名策略在仓库内找不到(可能在远程配置)。已用一次性程序在 Jackson 2.16.2 下实测:无显式名的 record 输出键随宿主配置在 `workInfo`/`work_info` 间变化;带 `@JsonProperty` 的字段在默认、SNAKE_CASE、LOWER_CAMEL 三种配置下输出一致。处理方式:agent 面的请求 record(`TaskCreate`、`RunCreate`、`RuntimeAdmission`、`RunStateChange`、`EventAppend`、`ProposalCreate`、`ProposalReview`、`ProposalApply`、`CompileRequest`)与响应 record(`AgentResponse`、`Gap`、`GapReport`)全部加显式 snake_case 名,请求字段另加 `@JsonAlias` 接受 camelCase;`Snapshot` 内嵌的共享 `Draft*` record 不改(authoring 端点仍用原格式),改由 `PoetryAgentWire.snake()` 在 agent 控制器里转成固定 snake_case。编排端点返回 `Map`,键来自 SQL 别名,本来就是 snake_case。`PoetryAgentWireContractTest` 固化上述行为(已 test-compile,未运行)。
- 现有 `deerflow-profile/config/config.yaml` 是自创格式,不是 DeerFlow 2.2.0 的真实配置;必须按 `deploy/upstream/deer-flow-v2.2.0/config.example.yaml`(config_version 63)重写。
- 不允许 worker 绕过 DeerFlow 直接调模型(`docs/deerflow-integration.md`)。无 DeerFlow/无网关/无密钥时走**确定性 STUB**(不调模型,基于 Java 快照做真实分析)。

## 1. 决定记录(影响接口)

| # | 决定 | 理由 |
|---|---|---|
| D1 | 人类写入口(填 locator、核验来源、逐项评审)由 BFF **直连 Java**,使用独立的 `POETRY_STUDIO_REVIEWER_TOKEN`,不经 MCP 控制桥 | agent 链路(DeerFlow→MCP、worker→控制桥)任何环节都拿不到该令牌;即使控制桥被误用也写不了来源 |
| D2 | 运行时选择在 BFF `POST /tasks/{id}/run` 时决定:`DEERFLOW`(`DEERFLOW_ENABLED=true`)或 `STUB`;可由请求体 `runtime` 显式覆盖为 `STUB` | 失败后 Studio 提供"用确定性运行时重试" |
| D3 | **agent-worker 独占运行执行**(提交/监控 DeerFlow、STUB 计算、预算/超时/重试/熔断、校验、写事件与提案);BFF 只创建记录并向 worker 派发 | 一个执行者承担治理,BFF 保持无状态 |
| D4 | DeerFlow 失败(重试耗尽/熔断)→ run `FAILED` + 事件 `RUNTIME_FAILED`,**不静默降级为 STUB** | 不把确定性结果冒充模型结果 |
| D5 | DeerFlow agent **不调用** `create_draft_proposal`;它在最终消息里输出 ```json 围栏的 `agent-output/1`,由 worker 校验后经控制桥写入提案。`create_draft_proposal` 工具保留但从 lead 的 allow 列表移除 | 校验在确定性代码里,不依赖模型是否正确调用工具 |
| D6 | v1 提案 schema(`proposal.schema.json`)**结构不变**,只修正 audience/certainty 枚举;事实/解释/演绎的区分靠 `classification` + 固定正文前缀(见 §5)表达 | 保持 Java 校验与既有 schema 兼容 |
| D7 | 逐项批准/驳回:新增表 `poetry_agent_proposal_item`;Java `apply` 仅执行被**明确 APPROVE** 的可执行项;提案下完全没有逐项记录时按旧行为全部执行(向后兼容) | 满足逐项审核而不破坏旧调用 |
| D8 | Studio 无真实登录;`actor`(id+role)由前端提交,BFF 校验角色白名单。**这是已知缺口**(无身份认证),handoff 写明 | 范围内不做 SSO |
| D9 | `agent-authoring`(Node)降级为离线 CLI 规划工具,不再是运行路径;不删除 | 避免破坏已有用法 |

## 2. 令牌与网络边界

| 令牌(环境变量) | 持有者 | 作用 |
|---|---|---|
| `POETRY_AGENT_INTERNAL_TOKEN` | MCP 进程 | MCP→Java 的 agent 面(读快照、写提案、评审记录、应用) |
| `POETRY_DOMAIN_MCP_TOKEN` | DeerFlow、MCP | DeerFlow→MCP `/mcp` |
| `POETRY_DOMAIN_CONTROL_TOKEN` | BFF、**worker**、MCP | →MCP 控制桥 `/internal/*`(仅 agent-orchestration 读写 + 只读转发) |
| `POETRY_DOMAIN_REVIEW_TOKEN` | **BFF、MCP**(worker **不持有**) | 提案的评审与应用。与 control 令牌分开，所以持 control 令牌的 worker **无法批准自己产出的提案**（A-05 已收口）。不设时评审路由 503 |
| `POETRY_STUDIO_REVIEWER_TOKEN` | **仅 BFF** 与 Java | BFF→Java `studio` 人类写入口。**不得出现在 MCP、worker、DeerFlow 的环境里** |
| `POETRY_WORKER_TOKEN` | BFF、worker | BFF→worker 派发 |
| `POETRY_LLM_*` | **仅 DeerFlow 容器** | 模型网关 |

## 3. Java 新端点(`vvv-poetry`,V009+)

响应沿用 `AgentResponse` 信封 `{status,data,audit_refs,next_action}`;新 record 全部显式 `@JsonProperty`(snake_case)。分页统一 `{items,limit,offset,has_more}`,`limit` 默认 50、上限 200。

### 3.1 读(头 `X-Poetry-Agent-Internal-Token`,经控制桥转发,不要求 run/mandate 头)

路径前缀 `/api/poetry/v1/agent-orchestration`:

| 方法 路径 | 返回 data |
|---|---|
| `GET /tasks?work_id&status&task_type&limit&offset` | 分页任务,倒序 `created_at` |
| `GET /tasks/{id}/runs` | `{items:[run...]}` 倒序 |
| `GET /proposals?work_id&status&review_status&run_id&task_id&limit&offset` | 分页提案摘要:`proposal_id,work_id,run_id,task_id,mandate_id,status,review_status,review_id,reviewed_by,review_comment,created_at,applied_at,proposal_json`;`status`/`review_status` 过滤值取列值 |
| `GET /proposals/{id}/items` | `{items:[{item_index,decision,reviewer,comment,created_at}]}` |
| `GET /works?limit&offset` | 分页作品:`work_id,title,status,genre,dynasty_id,line_count,version_count,background_count,annotation_count,claim_count,pending_source_count` |
| `GET /works/{id}/coverage` | 见 §3.3 |
| `GET /works/{id}/studio-view` | 见 §3.4 |
| `GET /sources?verification_status&limit&offset` | 分页来源,每条含 `citations:[{claim_id,claim_value,claim_kind,claim_status,locator,evidence_excerpt,locator_state}]`,`locator_state=MISSING|PLACEHOLDER|SET`(占位词:空、待核查、待人工、未核对、TBD) |

另有 worker 需要的两个读(头 `X-Poetry-Agent-Internal-Token` + `X-Poetry-Agent-Run-Id` + `X-Poetry-Agent-Mandate-Id` + `Idempotency-Key` 即现有 agent 面,**已存在**):`GET /api/poetry/v1/works/{id}/snapshot`、`GET /api/poetry/v1/works/{id}/integrity-gap-report`。

### 3.2 人类写(头 `X-Poetry-Studio-Reviewer-Token`;配置 `poetry.studioReviewerToken`;未配置→503,错令牌→401;与 agent 令牌相互独立,agent 令牌调用一律 401)

前缀 `/api/poetry/v1/studio`。请求体都含 `reviewer`(署名,2–100 字,**拒绝**匹配 `(?i)agent|bot|deerflow|system|mcp|llm|ai` 的署名)与 `reviewer_role`(`HISTORICAL_REVIEWER|PLATFORM_ADMIN|CONTENT_EDITOR`;核验/填 locator 只允许前两者)。每次写入追加审计表 `poetry_studio_check_log`。

| 方法 路径 | 体 | 行为 |
|---|---|---|
| `PUT /citations/{claimId}/{sourceId}/locator` | `{locator, evidence_excerpt?, reviewer, reviewer_role, note?}` | 更新既有 citation 的 locator(拒绝空/占位词/超 300 字);citation 不存在 404/400;**不改来源的 verification_status** |
| `POST /sources/{id}/verification` | `{decision:"VERIFY"\|"REJECT", reviewer, reviewer_role, note?}` | `VERIFY` 复用 `PoetryReviewService.publish("source", …)`(含发布闸门与 106 项审计);另要求该来源下**每条** citation 的 locator 均为 `SET`,否则 409 列出缺失项;`REJECT` 复用 `retract("source", …)` |
| `PUT /proposals/{id}/items` | `{decisions:[{item_index, decision:"APPROVE"\|"REJECT", comment?}], reviewer, reviewer_role}` | 写/覆盖逐项记录(仅提案 `review_status=PENDING` 时允许);`item_index` 必须在提案 `changes` 范围内,仅可执行项(有 `draft_payload`)才有意义,非可执行项记录但不影响应用 |

### 3.3 `GET /works/{id}/coverage` 的 data

```json
{
  "work_id": "work-chun-wang",
  "totals": {"lines":8,"versions":1,"backgrounds":4,"annotations":0,"claims":12,"sources":4,"citations":10},
  "claims_by_status": {"DRAFT":12,"PUBLISHED":0},
  "claims_checkable": {"checkable":0,"total":12},
  "sources_by_verification": {"PENDING":4,"VERIFIED":0,"REJECTED":0},
  "layers": {"SCENE":{"count":1,"linked_lines":0},"CITY":{},"WORLD":{},"PERSON":{}},
  "lines": [{"version_id":"text-chun-wang-v1","line_seq":1,"content":"国破山河在","annotation_count":0,"background_count":1,"layers":["CITY"]}],
  "gap_codes": ["CLAIM_VERIFIED_CITATION_MISSING","TEXT_SOURCE_NOT_VERIFIED"],
  "publication": {"work_status":"DRAFT","published_claims":0,"audit_checks":106,"audit_non_zero":[]}
}
```

### 3.4 `GET /works/{id}/studio-view` 的 data

即 `snapshot`(`work, work_info, versions, lines, claims, citations, backgrounds, annotations, sources`)加:`background_lines:[{background_id,version_id,line_seq}]`、`claim_status_by_id`、`content_status_by_id`(作品与各背景 `poetry_content.status`)、`version_status_by_id`、`source_verification_by_id`、`coverage_rows:[{id,entity_type,from_year,to_year,coverage_kind,status,note}]`(`poetry_coverage`,可为空)、`gap_report`(同 integrity-gap-report 的 data)。worker 与 BFF 读上下文都用它(经控制桥 `/internal/works/{id}/studio-view`)。

### 3.5 迁移 `V009__studio_governance.sql`(只写文件,不执行;MySQL 5.6;无外键、无 JSON、无 CHECK;索引 ≤767 字节)

- `poetry_agent_proposal_item(proposal_id VARCHAR(64) utf8mb4_bin, item_index INT, decision VARCHAR(16), reviewer VARCHAR(100), comment TEXT, created_at TIMESTAMP, updated_at DATETIME, PRIMARY KEY(proposal_id,item_index))`
- `poetry_studio_check_log(id BIGINT AI PK, action VARCHAR(32), source_id VARCHAR(64) bin, claim_id VARCHAR(64) bin NULL, proposal_id VARCHAR(64) bin NULL, locator VARCHAR(300) NULL, evidence_excerpt TEXT NULL, decision VARCHAR(16) NULL, reviewer VARCHAR(100), reviewer_role VARCHAR(32), note TEXT NULL, created_at TIMESTAMP, KEY(source_id,id), KEY(proposal_id,id), KEY(reviewer,id))`
- 列表用索引:`poetry_agent_task(status, created_at)`、`poetry_agent_proposal(created_at)`(新增 `ix_*`,不改旧索引)
- 账本:`INSERT INTO poetry_schema_version (version_no, description) VALUES (9, …)`
- 附 `docs`:`V009` 需要用户执行;回滚 SQL 单独文件 `V009_rollback.sql`(`DROP TABLE` 两张新表与新增索引)放 `db/poetry/recovery/`

### 3.6 对现有代码的最小修改(允许,写入 handoff)

- `PoetryAutoConfiguration`:注册新 mapper/service/controller bean(新增方法,不改旧 bean)。
- `PoetryAgentService.apply`:按 D7 仅执行被 APPROVE 的可执行项;无逐项记录时旧行为。
- 新类全部放 `com.timeline.poetry.*` 既有包内的新文件,前缀 `PoetryStudio*`。

## 4. MCP 控制桥新增路由(`poetry-domain-mcp`,头 `X-Poetry-Domain-Control-Token`,只读转发到 §3.1)

`GET /internal/tasks`、`/internal/tasks/{task_id}/runs`、`/internal/proposals`(列表,**注意与已有 `POST /internal/proposals` 同路径不同方法**)、`/internal/proposals/{id}/items`、`/internal/works`、`/internal/works/{work_id}/coverage`、`/internal/works/{work_id}/studio-view`、`/internal/sources`、`/internal/works/{work_id}/snapshot?run_id&mandate_id`、`/internal/works/{work_id}/gap-report?run_id&mandate_id`(后两个由桥补齐 Java 要求的 run/mandate/Idempotency-Key 头,`Idempotency-Key=control:read:<run_id>:<path-hash>`)。查询参数白名单、值正则校验(`work_id` 等沿用既有锚定正则)。**人类写入口不在桥上。**

## 5. 提案内容分类约定(事实/诠释/演绎)

v1 `changes[]` 不变。编译自 `agent-output/1` 时(§6)固定:

| epistemic | change_type | classification | body 前缀 | 可带 draft_payload |
|---|---|---|---|---|
| `FACT_REQUEST`(事实性条目:只能提"来源请求") | `CLAIM` | `UNKNOWN` | `【来源请求】` | 否 |
| `INTERPRETATION` | `ANNOTATION`/`BACKGROUND`/`CLAIM` | `INTERPRETATION` | `【解释】` | 仅 ANNOTATION 且满足 §6 约束 |
| `DRAMATIZATION` | `SCRIPT`/`BACKGROUND` | `INTERPRETATION` | `【演绎】` | 否 |
| `DRAFT_TEXT`(教学表述草稿,不含史实断言) | 任意 | `DRAFT` | `【草稿】` | 仅 ANNOTATION |
| `UNKNOWN` | 任意 | `UNKNOWN` | `【未考】` | 否 |
| 缺口(GAP) | `GAP_REPORT` | `DRAFT` | `【缺口】` | 否 |

## 6. `agent-output/1`(DeerFlow 最终消息 / STUB 内部结构)

```json
{
  "schema": "agent-output/1",
  "task_type": "GAP_ANALYSIS|ANNOTATION_DRAFT|SCRIPT_DRAFT|COMPILE_TRIAGE",
  "summary": "…≤1500字",
  "items": [{
    "kind": "GAP|ANNOTATION|BACKGROUND_NOTE|SCRIPT_BEAT|SOURCE_REQUEST|TRIAGE_ITEM",
    "epistemic": "FACT_REQUEST|INTERPRETATION|DRAMATIZATION|DRAFT_TEXT|UNKNOWN",
    "target_ref": "line:text-chun-wang-v1#1 | claim:… | background:… | null",
    "body": "…≤7000字",
    "evidence_refs": ["snapshot 中真实存在的 id"],
    "severity": "HIGH|MEDIUM|LOW|null",
    "annotation": {"version_id":"…","line_seq":1,"annotation_kind":"WORD","audience":"PRIMARY","content":"…","claim_value":"…","certainty":"LIKELY|DISPUTED|UNKNOWN","source_id":null},
    "source_request": {"claim_ref":"claim-… | null","what_to_verify":"…","suggested_source_kind":"OFFICIAL_HISTORY|…|null","suggested_source_title":"…|null"}
  }],
  "unknowns": ["…"],
  "human_review_question": "恰好一个可回答的问题"
}
```

确定性校验(worker,全部必须过,否则整次输出被拒并记 `OUTPUT_REJECTED` 事件,不写提案):

1. JSON 结构、枚举、长度;`schema`/`task_type` 与任务一致。
2. `evidence_refs` 中每个 id 必须存在于本次快照(content/version/line/claim/background/annotation/source id 集合)。
3. 事实性内容(`FACT_REQUEST`)只允许带 `source_request`,**禁止** `annotation`;`body` 与 `source_request` 内不得出现**不在快照中**的卷页/页码/编号式定位(正则:`卷[一二三四五六七八九十百零\d]+`、`第?\s*\d+\s*[页頁]`、`\bp{1,2}\.?\s*\d+`、`\bvol\.?\s*\d+`、`《[^》]{2,40}》\s*卷?\s*[\d一二三四五六七八九十]+`);`locator` 一律强制为 null。
4. `annotation`:`version_id` 存在于快照;`line_seq` 存在于该版本的行;`annotation_kind/audience/certainty` 取 Java 词表;`certainty` 不允许 `KNOWN`;`source_id` 为 null 或属于快照来源;`content` ≤ 8000;同一提案内 (version_id,line_seq,annotation_kind,content) 去重。编译时 worker 生成 `id=ann-<run8>-<n>`、`claim_id=claim-ann-<run8>-<n>`(符合 `^[A-Za-z][A-Za-z0-9_-]{1,63}$`)。
5. 不得出现禁止能力名作为指令(`publish/retract/verify_source/set_verified/delete_content/execute_sql` 作为"请执行"语义):出现则拒绝;仅描述性提及(如"不能 publish")不算,实现用"祈使/请求"启发式 + 单测样例固定边界。
6. `items` ≤ 50;`unknowns` ≤ 50;任何条目不得设 `VERIFIED`、`PUBLISHED`、`status` 字样为已确认(正则拒绝"已核验|已验证|已发布"作为断言)。
7. 注入防护:快照与网页材料进入模型提示前统一包裹 `<untrusted_material source="…">`,剥离 HTML/脚本/零宽字符,截断(单块 ≤ 6000 字);模型输出一律视为不可信数据。
8. 预算:`max_tool_calls`、`max_wall_seconds`、`max_output_chars`、重试次数、熔断阈值来自 `deerflow-profile/config/budgets.yaml`(见 §12)。

## 7. BFF API(前缀 `/api/poetry/v1/agent`,供 Studio 使用)

统一错误体 `{"error":{"code","message","details?"}}`;所有列表 `{items,limit,offset,has_more}`;时间 ISO-8601 UTC。

### 7.1 任务与运行
- `GET /tasks?work_id&status&task_type&limit&offset`
- `POST /tasks`(已有;`task_type` 四类均生效;**去掉**对 `publish` 子串的粗暴拒绝,改为拒绝"祈使式控制请求"启发式并在 422 里说明;`instructions` 作为不可信材料转交)
- `GET /tasks/{id}`、`GET /tasks/{id}/runs`
- `POST /tasks/{id}/run` 体 `{"runtime"?:"STUB"}` → `Run`(202);已有 `RUNNING` 运行 → 409 `{code:"RUN_ALREADY_ACTIVE",details:{run_id}}`
- `POST /runs/{id}/cancel` → `Run`(幂等)
- `GET /runs/{id}`、`GET /runs/{id}/events`(SSE,`id:` 为事件序号,支持 `Last-Event-ID`)、`GET /runs/{id}/budget`
- `GET /health/live|ready`(ready 增加 `worker_configured`、`reviewer_token_configured`)

`Run` 扩展字段:`budget`(最近一次 `BUDGET_UPDATE` 汇总,可空)、`runtime`(`DEERFLOW|STUB`)。

事件类型(`events[].event_type`,`payload` 对象):`RUN_CREATED, RUNTIME_ADMISSION, RUN_STATE_CHANGED, RUN_STARTED, CONTEXT_LOADED{snapshot_hash,counts}, STEP{name,detail}, TOOL_CALL{tool,outcome,ms}, MODEL_USAGE{model,input_tokens,output_tokens,ms,degraded}, BUDGET_UPDATE{tool_calls,max_tool_calls,elapsed_s,max_wall_s,tokens,max_tokens}, OUTPUT_ACCEPTED{items,sha256}, OUTPUT_REJECTED{rules:[…]}, PROPOSAL_RECORDED, RETRY{attempt,reason}, CIRCUIT_OPEN{target,reopens_in_s}, RUNTIME_FAILED{reason}, PROPOSAL_APPROVED, PROPOSAL_REJECTED, DRAFT_APPLICATION_COMPLETED, RUN_CANCELLED`。日志与事件**只记元数据**(模型名、耗时、token、是否降级),不记提示词全文/模型原文。

### 7.2 提案与评审
- `GET /proposals?work_id&status&run_id&task_id&limit&offset` → `Proposal[]`(含 `payload`)
- `GET /proposals/{id}`(含 `items`:逐项决定)
- `GET /proposals/{id}/diff` → `{proposal_id, work_id, snapshot_taken_at, changes:[{index, change_type, classification, label:"来源请求|解释|演绎|草稿|未考|缺口", executable:boolean, target_ref, before:object|null, after:string, annotation:object|null, risks:string[], item_decision:{decision,comment,reviewer}|null}]}`;`before` 为对应行/背景/已有注释(取自 studio-view);`risks` 由规则生成(如"certainty=DISPUTED"、"无出处"、"引用行不存在")
- `POST /proposals/{id}/review` 体 `{actor, decision:"APPROVE"|"REJECT", comment?, item_decisions?:[{item_index,decision,comment?}]}`。角色限制:`CONTENT_EDITOR|HISTORICAL_REVIEWER`;`APPROVE` 且存在可执行项时,`item_decisions` 必须覆盖**全部**可执行项(否则 422 `ITEM_DECISIONS_REQUIRED`);先写逐项记录(直连 Java studio),再写整体评审
- `POST /proposals/{id}/apply`(已有,仅 APPROVED 且角色 `CONTENT_EDITOR|HISTORICAL_REVIEWER|RELEASE_MANAGER`;无任何被批准的可执行项时 409 `NOTHING_TO_APPLY`,提案可标记为"仅留存")
- `ProposalStatus` 不变;`Proposal` 增加 `items:[…]`、`executable_count`、`approved_executable_count`

### 7.3 作品、覆盖、来源、出处核查、发布前检查
- `GET /works`、`GET /works/{id}/overview`(=studio-view)、`GET /works/{id}/coverage`、`GET /works/{id}/gap-report`
- `GET /works/{id}/precheck` → `{work_id, evaluated_at, bundle:{state:"EVALUATED|NOT_AVAILABLE", script_id?, script_version?}, rules:[{id:"R1"…"R12", name, evaluation:"DATA|BUNDLE", status:"PASS|FAIL|NOT_EVALUATED", details:string[]}], verdict:"READY_FOR_HUMAN_PUBLISH|BLOCKED|INCOMPLETE"}`。规则名与 `pipeline/tools/scene-validator/rules.mjs` 一致(R1 reference exists / R2 published only / R3 basis / R4 fallback / R5 coverage declared / R6 unknown dates / R7 annotations from base / R8 line link / R9 hash / R10 rights+meaning / R11 no pile-up / R12 free movement)。有 bundle(`POETRY_BUNDLE_DIR` 下可读的 `bundle.json`)时用 Python 移植实现评估 bundle 规则;否则只评估能由 Java 数据判断的前置条件,其余 `NOT_EVALUATED` 并写明"需要 bundle"。**`READY_FOR_HUMAN_PUBLISH` 不等于已发布,界面不得出现"发布"动作。**
- `GET /sources?verification_status&limit&offset`
- `PUT /sources/citations/{claim_id}/{source_id}/locator` 体 `{actor, locator, evidence_excerpt?, note?}`;`POST /sources/{id}/verification` 体 `{actor, decision:"VERIFY"|"REJECT", note?}`。仅 `HISTORICAL_REVIEWER|PLATFORM_ADMIN`;其余 403 `SOURCE_REVIEW_ROLE_REQUIRED`。BFF 直连 Java studio 端点。

## 8. Worker API(`agent-worker`,端口 8102,头 `X-Poetry-Worker-Token`)

- `POST /internal/dispatch` 体 `{run_id, task_id, mandate_id, work_id, task_type, instructions, runtime, profile_fingerprint, actor_role}` → 202 `{accepted:true}`;同 `run_id` 重复派发 → 200 `{accepted:true, duplicate:true}`(幂等)
- `POST /internal/runs/{run_id}/cancel` → 200
- `GET /health/live`、`/health/ready`(`deerflow:{enabled,reachable,circuit}`、`control_bridge:{configured,reachable}`、`active_runs`;worker 不持有模型密钥,不报告 LLM 配置)
- 入口:`python -m agent_worker.app`(端口取 `PORT`,默认 8102)
- worker 经控制桥读快照/缺口并写事件、状态、提案(`POST /internal/proposals`);提案幂等键 `worker:proposal:<run_id>`;重启后对 `RUNNING` 且未派发的运行,由 BFF 或用户重新派发(handoff 说明,不做自动续跑)

## 9. 本地 Mock Poetry Domain API(`content-agent/deploy/dev-mock/`)

内存实现(Python,依赖 BFF 已有的 fastapi/uvicorn)。**同时实现** Java 现有的 `agent-orchestration/*`、`works/{id}/snapshot|integrity-gap-report`、`draft/proposals*` 与 §3 全部新端点,令牌校验与 Java 相同(agent 令牌 / studio reviewer 令牌互不通用),响应信封与错误码一致。种子:《春望》作品(8 行诗句、1 个文本版本、4 层背景草稿、12 条 claim、4 个 `PENDING` 来源、0 条注释),字段取自 `pipeline/contracts/facts.chun-wang.json` 与 V004 种子的**真实内容**;另一首空作品用于"从空白起草"。`apply` 对 `CREATE_ANNOTATION` 做与 Java 同样的词表与存在性校验。仅本地使用,不进镜像(`.dockerignore` 已排除或在 Dockerfile 中不 COPY)。

## 10. Studio 页面(`content-agent/frontend`,React + Vite + TS;设计遵循 `docs/design/DESIGN.md` 与 `tokens.css`)

每页必须有 loading / empty / error 三态与键盘可达性(焦点可见、`aria-live`、语义地标、列表项可回车进入、对话框焦点陷阱与 Esc 关闭):

1. 工作台(任务列表、筛选、创建任务:作品/类型/指令)
2. 任务详情 + 运行观测(SSE 事件流、状态、预算条、取消、STUB 重试)
3. 提案审核(列表 → 结构化 diff、逐项批准/驳回、角色选择、整体评审、应用 DRAFT)
4. 内容缺口与覆盖看板(Java gap report、逐句覆盖矩阵、层覆盖、来源核验占比)
5. 出处核查工作台(4 个 PENDING 来源;人工署名 + locator + 摘录;核验/驳回;明确标注"agent 无此权限")
6. 作品内容浏览(四层背景、逐句注释、claim 与引用,史实/解释/演绎/未考四态视觉契约)
7. 发布前检查清单(12 条规则,显示 DATA/BUNDLE、通过/失败/未评估;无"发布"按钮)

可信三态的视觉契约(`DESIGN.md §4`)在 Studio 里同样遵守:史实=靛青下划线、解释=青绿左线、演绎=朱砂底+"演绎"前缀、未考=灰虚线。PUBLISHED 与 DRAFT 永久视觉区分。

## 11. 一键本地演示

`scripts/content-agent/dev-offline.sh`(Makefile 目标 `content-dev-offline` / `content-dev-offline-down`):起 Mock(8080)→ MCP 控制桥(8101)→ worker(8102,`STUB`)→ BFF(8100)→ 可选 Studio(5190);全部使用脚本内固定的**本地假令牌**,不读取 `.env`;日志与 pid 写 `content-agent/deploy/dev-mock/.run/`(在 `.gitignore` 追加这一行;**不要新建平台顶层目录**,否则 `check-layout` 失败)。


## 12. `budgets.yaml` 结构(version 2;S5 写入,worker 读取)

```yaml
version: 2
profiles:
  authoring:
    max_turns: 18
    max_subagents: 0
    max_tool_calls: 24
    max_wall_seconds: 900
    max_output_chars: 60000
    max_tokens: 200000
    require_human_review_before_apply: true
    retry: {max_attempts: 3, backoff_seconds: [2, 5, 15]}
    circuit_breaker: {failure_threshold: 3, open_seconds: 120}
    per_task_type:
      GAP_ANALYSIS: {max_wall_seconds: 300}
      ANNOTATION_DRAFT: {max_wall_seconds: 600}
      SCRIPT_DRAFT: {max_wall_seconds: 900}
      COMPILE_TRIAGE: {max_wall_seconds: 300}
```

`per_task_type` 覆盖同名顶层字段。缺文件或缺字段时 worker 用代码内的保守默认值并发 `STEP{name:"budget_defaults"}` 事件。

## 13. 并行子任务分工与共同规则

| 子任务 | 拥有路径(只改这些) |
|---|---|
| S1 Java | `/Users/gqli/work/testserverV/vvv-poetry/**` |
| S2 Mock+脚本 | `content-agent/deploy/dev-mock/**`、`scripts/content-agent/**`(新增文件)、`Makefile` 与 `.gitignore` 只追加行 |
| S3 Worker | `content-agent/agent/agent-worker/**`、`content-agent/pipeline/contracts/agent-output.schema.json` |
| S4 BFF+控制桥 | `content-agent/agent/agent-bff/**`、`content-agent/agent/poetry-domain-mcp/**`、`content-agent/pipeline/contracts/{proposal,review,mandate,event,tool-receipt}.schema.json` |
| S5 Profile+部署 | `content-agent/agent/deerflow-profile/**`、`content-agent/deploy/{compose.yaml,.env.example,k8s/**}`、`content-agent/pipeline/tools/dev/**` |
| S6 Studio | `content-agent/frontend/**` |

共同规则:

1. 不运行测试套件:禁止 `pytest`、`vitest`、`mvn test`、`make test-all`、`verify*.mjs`、任何 `migrate-*`;不 `git add/commit/push`;不连接任何真实数据库;不启动 Docker 容器;V001–V008 不可改。**可以写测试**,不运行。
2. 允许:`ruff`、`python3 -m py_compile`、`bash -n`、`npm install`、`npm run build`、`tsc --noEmit`、`mvn -o compile`/`mvn -o test-compile`(只编译)、`docker compose config`、`make check-layout`、导入检查,以及**手工启动你自己做的本地进程**(仅 localhost、仅内存 Mock)并用 curl 查看行为。凡运行过的,在报告里逐条写命令与结果。
3. 密钥:不打印、不记录、不写入任何密钥值;**不要读取** `content-agent/deploy/.env` 的内容,更不要读 `job-come` 项目的 `.env`;测试与脚本里只用明显的假令牌。日志只记元数据(模型名、耗时、token 数、是否降级),不记提示词全文、模型原文、学生数据。
4. 不要新建 `content-agent/`、`student-app/`、平台根的顶层条目(会违反 `layout-allowlist.txt`)。`content-agent/` 顶层不放 README;说明文档放到你拥有的子目录内。
5. shell 习惯:zsh 下给 glob/`--include=` 加引号;用绝对路径;不要依赖持久的 `cd`(用子 shell `( cd … && … )`);`echo` 含 `=` 的分隔线要加引号。
6. 契约有歧义或需要偏离时:自己决定,偏离尽量小,写进报告"偏差/决定记录"。契约里标注"未核实"的事,不要假设为真。
7. 所有面向用户的说明、注释、文档用中文;代码标识符用英文。Python ≥ 3.12,`ruff` 行宽 100。
8. 报告:先写详细说明到 `/Users/gqli/work/xuexi/poetry-agent-platform/docs/handoff/A-parts/<你的编号>.md`(新建目录可以),最终回复 ≤ 600 字,按三段:①已实际运行并验证(命令+结果)②已写但没有运行③没有做到/需要用户或其他子任务处理;之后附"偏差与决定记录"。

## 14. 环境变量、命名规范化与跨层校验

**命名规范化**:Java agent 面恒为 snake_case(见 §0)。消费方(worker `control.py`、BFF `domain_control.py`)仍保留**递归 camelCase→snake_case 键名规范化**,作为纵深防御(防止未来有人新增未加显式名的 record)。Mock 用 `MOCK_JSON_NAMING=snake|camel`:默认 `snake`(与真实 Java 一致),`camel` 仅用于模拟有问题的宿主、验证兜底。Mock 请求体同时接受 snake_case 与 camelCase。

| 进程 | 环境变量 |
|---|---|
| Mock | `PORT`(默认 8080)、`POETRY_AGENT_INTERNAL_TOKEN`、`POETRY_STUDIO_REVIEWER_TOKEN`、`MOCK_JSON_NAMING` |
| MCP(含控制桥) | 沿用现有:`PORT`、`POETRY_API_BASE_URL`、`POETRY_API_TIMEOUT_SECONDS`、`POETRY_AGENT_INTERNAL_TOKEN`、`MCP_INTERNAL_TOKEN`、`POETRY_DOMAIN_CONTROL_TOKEN`、`POETRY_DOMAIN_REVIEW_TOKEN`、`POETRY_AGENT_ACTOR_ROLE` |
| Worker | `PORT`、`POETRY_AGENT_PROFILE_ROOT`、`POETRY_DOMAIN_CONTROL_URL`、`POETRY_DOMAIN_CONTROL_TOKEN`、`POETRY_WORKER_TOKEN`、`DEERFLOW_ENABLED`、`DEERFLOW_GATEWAY_URL`、`DEERFLOW_GATEWAY_TOKEN`、`DEERFLOW_ASSISTANT_ID`、`WORKER_MAX_CONCURRENT_RUNS`(默认 2) |
| BFF | `PORT`、`POETRY_AGENT_PROFILE_ROOT`、`POETRY_DOMAIN_CONTROL_URL`、`POETRY_DOMAIN_CONTROL_TOKEN`、`POETRY_API_BASE_URL`(直连 Java studio)、`POETRY_STUDIO_REVIEWER_TOKEN`、`POETRY_WORKER_URL`、`POETRY_WORKER_TOKEN`、`POETRY_STUDIO_ORIGINS`(CORS 白名单,逗号分隔,默认 `http://localhost:5190,http://127.0.0.1:5190`)、`POETRY_BUNDLE_DIR`(可选) |
| DeerFlow Gateway | `POETRY_LLM_API_BASE`、`POETRY_LLM_API_KEY`、`POETRY_LLM_MODEL_PRIMARY`、`POETRY_LLM_MODEL_FALLBACK`、`POETRY_DOMAIN_MCP_TOKEN`、`DEER_FLOW_*`;**不得**含 `POETRY_DOMAIN_CONTROL_TOKEN`、`POETRY_STUDIO_REVIEWER_TOKEN`、`POETRY_WORKER_TOKEN` |

**Profile 指纹输入集**(S4 `profile.py` 实现,S5 保证这些文件存在且不含密钥值):`config/config.yaml`、`config/extensions_config.json`、`config/mcp-policy.yaml`、`config/budgets.yaml`、`config/roles.yaml`、`prompts/core-soul.md`、`prompts/roles/*.md`、`agents/**/config.yaml`、`agents/**/SOUL.md`、`skills/*/SKILL.md`(均按相对路径排序)。

**跨层校验(同一规则在三处各实现一次,防止单点失守)**:worker(编译后)、BFF `record_proposal`(入口)、MCP `DraftProposalRequest`(写 Java 前)。可执行 `draft_payload` 额外规则:`locator` 必须为 null;`certainty` 不得为 `KNOWN`;`audience` 取 `PRIMARY|JUNIOR|SENIOR`;`certainty` 取 `LIKELY|DISPUTED|UNKNOWN`(agent 来源)。测试里加一条"三处枚举与 `proposal.schema.json` 一致"的对照用例。

**沟通方式**:Studio ↔ BFF 只用 §7;BFF ↔ worker 只用 §8;worker/BFF ↔ Java 只经控制桥 §4(人类写入口 §3.2 除外,BFF 直连)。
