# 任务 A 交接:内容生产 agent + Poetry Studio

日期:2026-11-07。约束依据 `docs/specs/2026-11-06-parallel-work-contract.md`:本任务期间**没有**运行 pytest / vitest / `mvn test` / `make test-all` / `verify*.mjs` / 任何 `migrate-*`,没有 git 提交,没有连接真实数据库,没有读取 `.env` 的值,V001–V008 未改。

配套文档:

| 文档 | 内容 |
|---|---|
| `docs/handoff/A-contract.md` | 任务 A 内部接口契约(Java ↔ 控制桥 ↔ BFF ↔ worker ↔ Studio),带决定记录 D1–D9 |
| `docs/handoff/A-parts/S1.md` `S2.md` `S3.md` `S5.md` `S6.md` | 各部分的详细报告(含 DeerFlow 上游源码 file:line 依据) |
| `docs/api/agent-bff.md` | BFF 接口(含登录与账号) |
| `testserverV/vvv-poetry/docs/studio-governance-api.md` | Java 新增端点 |

## 1. 做了什么

```text
Poetry Studio ──(Bearer 会话令牌)──> agent-bff ──> poetry-domain-mcp 控制桥 ──> Java /api/poetry/v1 ──> MySQL
   (React/Vite)                          │  └──(审核令牌,直连)──> Java /studio/*   (人类写入口)
                                         └──> agent-worker ──> STUB 确定性运行时 | DeerFlow 2.2.0 网关 ──> MCP ──> Java
```

- **agent-worker**(原 15 行占位)现在是运行执行者:派发、预算、超时、重试、熔断、取消、幂等、输出校验、事件审计、提案写入。
- **两种运行时**:`STUB`(不调模型,基于 Java 快照做真实分析,离线可演示)和 `DEERFLOW`(`DEERFLOW_ENABLED=true`)。DeerFlow 失败时 run 记为 `FAILED`,**不会**静默降级成 STUB。
- **四类任务**:`GAP_ANALYSIS`、`ANNOTATION_DRAFT`、`SCRIPT_DRAFT`、`COMPILE_TRIAGE`,各有 skill、提示词模板、`agent-output/1` schema 和 8 条确定性校验。
- **事实/诠释/演绎分类**:事实性内容只能是"来源请求"(`【来源请求】`,classification=UNKNOWN,不带 locator);解释、演绎、草稿、未考、缺口各有固定前缀与分类。校验会拒绝伪造的卷页/页码、不存在的证据引用、`KNOWN` 确定度、非空 locator、"已核验/VERIFIED"之类的断言。
- **DeerFlow profile**:按上游 `config.example.yaml`(config_version 63)重写;`POETRY_LLM_*` 通过 `$VAR` 引用接入,配置里没有密钥值。
- **Java 侧**(`vvv-poetry`,新增 V009):提案/任务/来源/作品列表、覆盖率看板、studio-view、逐项评审、locator 与来源核验的人工写入口(人工署名 + 审计表 + 独立令牌)。
- **Studio**:7 个页面 + 登录,全部有 loading / empty / error 三态和键盘可达。
- **本地 Mock**:`content-agent/deploy/dev-mock/`,内存实现,覆盖 Java 的 agent 面与新端点。

## 2. 入口命令

| 目的 | 命令 |
|---|---|
| 离线整链路演示 | `make content-dev-offline`(加 Studio:`make content-dev-offline ARGS=--studio`);停止 `make content-dev-offline-down`;状态 `make content-dev-offline-status` |
| 进程内整链路检查(不开端口、不起进程) | `uv run --offline --frozen --no-sync python content-agent/deploy/dev-mock/chain_check.py` |
| 校验 DeerFlow profile | `make content-profile-check` |
| 补齐 `.env` 缺的变量(会写真实 `.env`) | `make content-env-sync` |
| 检查模型网关(只请求模型列表) | `make content-llm-check` |
| Studio 开发 / 构建 | `cd content-agent/frontend && npm run dev` / `npm run build` |
| 创建 Studio 账号 | `python -m agent_bff.users add --file <仓库外的文件> --id <id> --role <角色>`(口令交互输入) |

离线演示用 `POETRY_STUDIO_AUTH=off`,界面会显示警告横幅。

## 3. 令牌与边界

| 令牌 | 持有者 | 作用 |
|---|---|---|
| `POETRY_AGENT_INTERNAL_TOKEN` | MCP | MCP → Java agent 面 |
| `POETRY_DOMAIN_MCP_TOKEN` | DeerFlow、MCP | DeerFlow → MCP |
| `POETRY_DOMAIN_CONTROL_TOKEN` | BFF、worker、MCP | → 控制桥(只读转发 + 编排写入) |
| `POETRY_STUDIO_REVIEWER_TOKEN` | **仅 BFF 与 Java** | 人类写入口。MCP、worker、DeerFlow 都没有 |
| `POETRY_WORKER_TOKEN` | BFF、worker | BFF → worker 派发 |
| `POETRY_STUDIO_SESSION_SECRET` | **仅 BFF** | 会话令牌签名,≥32 字符,`change-me` 开头的占位值会被拒绝 |
| `POETRY_LLM_*` | **仅 DeerFlow 网关** | 模型网关 |

人类写入口(填 locator、核验来源、逐项评审)不在控制桥上,agent 链路拿不到审核令牌。

## 4. 对既有代码的改动(请审阅)

**Java(`vvv-poetry`,均为最小改动)**:`PoetryAutoConfiguration` 末尾追加 5 个 bean;`PoetryAgentMapper` 加 1 个方法;`PoetryAgentService.apply` 改为"有逐项记录时只执行被 APPROVE 的可执行项,没有任何逐项记录时保持旧行为";`PoetryAgentModels`、`PoetryAgentOrchestrationModels` 的字段加显式 snake_case 名并保留 camelCase 别名;`PoetryAgentController` 的 snapshot / gaps 返回类型改为 `JsonNode`(经新类 `PoetryAgentWire` 转 snake_case)。其余为新增文件(`PoetryStudio*`、`PoetryAgentWire`、`V009`、`recovery/V009_rollback.sql`、测试)。

**共享文件(只追加)**:`Makefile`(5 个目标 + `.PHONY` + `help` 一行);`.gitignore`(`content-agent/deploy/dev-mock/.run/`)。未改 `pyproject.toml`、`uv.lock`、`layout-allowlist.txt`。`uv lock --check --offline` 通过。

**契约文件**:`content-agent/pipeline/contracts/proposal.schema.json` 的 `audience` 改为 `PRIMARY|JUNIOR|SENIOR`,`certainty` 改为 `KNOWN|LIKELY|DISPUTED|UNKNOWN`。原值(`MIDDLE`、`HIGH` 等)与 Java 词表不符,批准后应用必被 Java 拒绝。`student-app` 下没有这份 schema 的副本,`check-copies` 不比较它。

## 5. 决定记录

契约里的 D1–D9 见 `A-contract.md` §1。之后补充的决定:

| # | 决定 | 理由 |
|---|---|---|
| 10 | **Jackson 命名**:agent 面全部显式 `@JsonProperty` snake_case,请求字段另加 `@JsonAlias` 接受 camelCase;快照 / 缺口经固定 snake_case 映射器输出。BFF 与 worker 仍保留键名规范化作兜底 | 宿主的全局命名策略在仓库里找不到(可能在远程配置)。已用 Jackson 2.16.2 实测:无显式名的字段随宿主配置变化,显式名在三种配置下一致 |
| 11 | **Studio 真实登录**:口令 scrypt 哈希,账号文件在仓库外,HMAC 会话令牌 8 小时,账号状态每个请求都查(删号 / 改角色立即生效),5 次失败锁定,SSE 用 60 秒单 run 票据,`POETRY_STUDIO_AUTH` 只有字面量 `off` 才关闭 | 取代 D8 的"请求自己声明身份" |
| 12 | 删除无鉴权的 `POST /runs/{id}/proposals` | 它是浏览器可达的提案注入口,提案只应由 worker 写 |
| 13 | `DomainControlRejected` 与 `DomainControlError` 分开:Java 的 400/409/422 在 BFF 返回 409/422 并带原因,真正的不可用才返回 503 | 进程内联调发现:非法注释应用被误报为 503 服务不可用 |
| 14 | worker 守卫新增"直接/径直/干脆/directly"等只作用于规则 5 的请求词,不影响否定豁免 | 联调抽检发现"直接 verify_source …"没被拦;"不要直接 publish"仍放行 |
| 15 | 守卫与清洗器源码里的不可见字符改成 `\uXXXX` 转义(AST 对比证明语义不变) | 字面双向控制字符是 Trojan Source 写法,且评审时看不见 |
| 16 | DeerFlow 2.2.0 没有自动模型回退,`poetry-fallback` 只是第二个可选模型,换备用要显式传 `context.model_name` 并记 `degraded=true` | 上游源码核实 |
| 17 | 从所有角色移除 `request_compile`;lead 的 allow 列表移除 `create_draft_proposal` | 提案由 worker 校验后写入,不依赖模型是否正确调用工具 |
| 18 | compose 新增非 internal 的 `poetry-agent-egress` 网络,只给网关、MCP、BFF;发布端口默认绑 `127.0.0.1` | 原 `internal: true` 会让网关访问不了模型网关、MCP 和 BFF 访问不了 Java |
| 19 | 署名规则不做 `ai` 子串匹配,只拒大写独立词 `AI`、与角色词同现等 | 否则 Lai / Bai / Kai 被误杀。已知误伤 `Reagent`、`li-ai`,漏判 `Ai Claude` |

## 6. 验证状态

### 6.1 已实际运行并验证

| 命令 / 方法 | 结果 |
|---|---|
| `uv run --offline ruff check content-agent/agent`(即 `make lint` 范围) | 通过。曾有 63 条(全在 agent-worker,S3 报告为全绿,与我的结果不符),已修:52 条安全自动修复、其余手改 |
| `ruff check content-agent/deploy/dev-mock` | 通过 |
| `python3 -m py_compile`(全部 .py) | 通过 |
| `bash -n scripts/content-agent/*.sh`(12 个) | 通过 |
| `make check-layout`(含 `docker compose config` 解析、bind mount、Dockerfile COPY) | 全 ok,无 FAIL |
| `make content-profile-check` | 通过(DeerFlow 2.2.0 config v63、5 个 skill、只读 MCP 策略、令牌切分、网络) |
| `uv lock --check --offline` | 通过(53 个包) |
| `make -n` 五个新目标 | 可解析 |
| `cd /Users/gqli/work/testserverV && mvn -o -q -pl vvv-poetry -am compile` 与 `test-compile` | 通过(只编译,未运行测试) |
| `cd content-agent/frontend && npx tsc --noEmit` | 通过 |
| `cd content-agent/frontend && npm run build` | 通过(58 个模块,JS 332 kB);TypeScript 7.0.2 + Vite 8.3.6 + React 19.3.1 无需调整版本 |
| 一次性 Java 程序(`/tmp`,已删) | Jackson 2.16.2 下,默认 / SNAKE_CASE / LOWER_CAMEL 三种配置:显式名输出一致,snake 与 camel 输入都能读 |
| 内存 H2(MySQL 模式)逐条执行 V001–V004、V007、V009、V009 回滚(S1 的临时脚本,不是 JUnit) | 成功;真实 V008 在 H2 上因多列 ALTER 失败,测试改用 `V008_h2_equivalent.sql` |
| **`chain_check.py`:进程内串联 Mock → 控制桥 → worker → BFF** | **60/60 通过**。覆盖:令牌隔离;四类任务各自到达 `AWAITING_REVIEW`、写出审计事件和恰好一份 DRAFT v1 提案;diff 标签与风险;逐项评审门槛(422);批准 → 应用 → 注释以 DRAFT 写入;被驳回的项不写入;非法注释应用返回带原因的 4xx;4 个 PENDING 来源;编辑不能填 locator / 核验;占位 locator 与 agent 式署名被拒;VERIFY 在缺 locator 时 409;precheck 为 BLOCKED 且需要 bundle 的规则为 NOT_EVALUATED;空作品也能产出可审核提案;指令注入 422 |
| 一次性脚本:四类 STUB × 两种键风格夹具 → 校验 → 编译 | 全部通过;每类变更数稳定(28 / 10 / 12 / 10);STUB 输出中没有卷页式字符串;清洗器去除 script / 注释 / 零宽 / 双向控制符 |
| 一次性脚本:BFF 登录探测 | 无令牌 / 篡改 / 伪造角色 / 越权 / 账号被删后令牌失效 / 锁定 / 票据串用均按预期拦截 |
| 手工起 Mock(S2,假令牌,内存,端口 18080-82,已按 PID 停止) | 令牌隔离、信封、gap、提案幂等、D7、locator 门槛、reset 均符合预期 |
| 手工检查 12 条指令守卫样例 | 描述性提及放行,祈使式拦截 |

### 6.2 已写但没有运行

| 文件 | 应满足的行为 |
|---|---|
| `agent-bff/tests/test_bff_governance.py`、`test_bff_auth.py`、`conftest.py`、`test_bff_path_ids.py`(已更新) | 评审 / 应用门槛、角色限制、人类写入口、precheck、diff、worker 不可达、runtime 选择、拒绝 ≠ 故障(409/422 对 503)、登录全流程、枚举与 schema 一致性 |
| `poetry-domain-mcp/tests/test_control_reads.py` | 新增只读转发路由的鉴权、查询参数校验、snapshot 头补齐、桥上无人类写路由、agent 注释的词表限制 |
| `agent-worker/tests/`(11 个模块,约 181 个测试函数) | 校验器每条规则、守卫边界、清洗、compile 映射、四类 STUB、重试 / 熔断 / 预算 / 取消 / 幂等、DeerFlow 成功 / 超时 / 5xx / 畸形 JSON、三层枚举对照 |
| `deploy/dev-mock/tests/`(5 个文件) | 令牌与信封、状态机、apply 校验、D7、reset。单独运行:`uv run --frozen pytest content-agent/deploy/dev-mock/tests`(根 `testpaths` 未改) |
| `vvv-poetry` 的 JUnit(Rules / Write / Apply / Read / SchemaAndJson / `PoetryAgentWireContractTest`,及辅助) | V009 装载与回滚、令牌隔离、署名与 locator 规则、VERIFY 缺 locator → 409、逐项评审的 apply(含向后兼容与表缺失时 fail-closed)、列表过滤与分页、Jackson 绑定 |
| `content-agent/frontend/src/**/*.test.ts(x)`(9 个文件) | 页面三态、键盘操作、逐项决定门槛、角色禁用、SSE 取票据重连、登录页、precheck 无发布按钮。通过了类型检查,**能否全部通过未知**,对话框焦点陷阱、fake timers、无障碍描述断言最可能要微调 |
| `dev-offline.sh`、`dev-offline-down.sh`、`dev-offline-status.sh`、`env-sync.sh` | 只做了 `bash -n` 与 `make -n` |

**第一次统一测试时请重点留意**:`test_bff_auth.py`(依赖 mtime 刷新账号缓存,可能需要调整)、前端测试、`vvv-poetry` 新增的 JUnit(H2 上的 SQL 行为、106 项审计在测试里是桩)。

## 7. 没有做到 / 需要你做

### 7.1 需要你执行或提供

1. **在真实库执行 `V009__studio_governance.sql`,并且要先于部署新 Java 代码**。表不存在时,新的 `apply` 会失败,这是有意不回退成"全部执行"。回滚用 `recovery/V009_rollback.sql`。执行后建议 `SELECT version_no FROM poetry_schema_version ORDER BY version_no`(应有 1–9)。
2. 配置 `poetry.studioReviewerToken`,必须不同于 `poetry.agentInternalToken`,相同则写路由返回 503。
3. `.env` 补 `POETRY_WORKER_TOKEN`、`POETRY_STUDIO_REVIEWER_TOKEN`、`POETRY_STUDIO_SESSION_SECRET`(`make content-env-sync` 可生成随机值,它会写你的真实 `.env`,我没有运行)。Java 侧的审核令牌要和 BFF 的 `POETRY_STUDIO_REVIEWER_TOKEN` 同值。
4. 创建 Studio 账号:`python -m agent_bff.users add --file <仓库外文件> --id <id> --role <HISTORICAL_REVIEWER 等>`;容器里用 `docker compose exec agent-bff … --file /studio-auth/users.json`。
5. **一次无副作用的 Jackson 核实**:对新版本 POST `/api/poetry/v1/agent-orchestration/tasks`,体为 `{"task_id":"task_probe_1"}`。返回 "invalid work id" 说明字段已绑定;返回 "invalid task_ identifier" 说明没绑上。
6. **手动运行 `make content-dev-offline`**(S2 的脚本被权限分类器连续拒绝三次)和 **`make content-llm-check`**(我运行了两次都被拒绝)。我没有绕开,也没有替子任务执行被拒的命令。这两个命令从未真正执行过。`dev-offline.sh` 里待验证的点:`env -i` 白名单环境下 `uv run --frozen --package` 能否找到 uv 缓存和 `.venv`、`uv run` 子进程是否被干净结束。
7. 联网环境下 `npm install` 已完成并生成了 `package-lock.json`;`uv.lock` 里 worker 已是 0.2.0 且依赖已锁,请在联网时再跑一次 `uv lock --check` 确认。
8. 运行统一测试(见 6.2)。

### 7.2 未做到

- **从未连过真实 DeerFlow 和真实模型**:网关的认证、CSRF、路由、线程作用域运行全部来自源码阅读加 `MockTransport`。未验证:网关实机启动、thinking / `reasoning_content` 处理、`max_tokens=8192` 截断、skill 遵从度、模型是否真的会输出合法的 `agent-output/1`。
- k8s:需要先建 4 个 Secret 和 2 个 ConfigMap;网关 Deployment 与 `POETRY_BUNDLE_DIR` 挂载没做;未 dry-run。
- `DEERFLOW_FALLBACK_MODEL` 默认关闭,未写入 compose。
- `audit_integrity_checks.sql` 没有加新表(`poetry_agent_proposal_item`、`poetry_studio_check_log`)的核查。
- `precheck` 的 bundle 规则只有挂载了 `POETRY_BUNDLE_DIR/bundle.json` 才评估,compose 默认不挂载。
- 登录:无注册、改密码、多因素;令牌不能单独吊销(只能删号或换密钥);限速和票据都是进程内的,多副本不共享。
- 署名规则的已知误伤 / 漏判(见决定 19)。
- Studio:未联调真实 BFF,未做浏览器、读屏、截图验收;BFF 只给 `proposal_json` 时摘要显示"(无摘要)";轮询回退时看不到事件明细;令牌失效会丢失未提交的表单草稿。
- 重启后不会自动续跑 `RUNNING` 但未派发的运行,需要在 Studio 里重新发起。
- 输出被校验拒绝时不会自动"修复重试",直接 `FAILED`,Studio 可"用确定性运行时重试"。

### 7.3 其他提醒

- 会话列表里有一个我没有启动的会话"只读对抗审查:V009 迁移与 agent 边界"(`code-review-a`),我没有碰它,也没有看它的结果。
- 先前的 Docker 基础镜像拉取问题(状态文档里记录的代理问题)未验证是否已解决,本任务没有构建镜像。
- 文本版本 id 的真实值是 `text-chun-wang-draft`(不是契约示例的 `-v1`);《春望》相关实际是 13 条 claim / 11 条引用 / 4 个来源,V004 默认带 2 条注释。`gap-report.sql` 里也引用了 `text-chun-wang-v1`,同样对不上,未改(不在我的路径内)。

## 8. 下一步建议

1. 先做 7.1 的 1–3 与 5(执行 V009、配令牌、核实 Jackson),再手动跑 `make content-dev-offline --studio`,用 Mock 把 Studio 完整点一遍。
2. 统一测试,优先看 6.2 里标出的三处。
3. 真实库上用 `HISTORICAL_REVIEWER` 账号为《春望》的 4 个 PENDING 来源填 locator 并核验(只能人做),这是 bundle 编译的当前阻塞。
4. 起 DeerFlow 网关(`make deerflow-bootstrap` 之后 `docker compose --profile deerflow up`),先用 `GAP_ANALYSIS` 跑一次真实模型,观察输出被校验拒绝的比例,再决定是否需要"拒绝后自动重试一次"。
5. 补 `audit_integrity_checks.sql` 对新表的核查,并给 Studio 接入真实 SSO(替换本地账号文件)。

## 9. 审查修复记录(2026-11-07,依据 docs/review/A-delivered-review.md)

审查原文未改动。下表逐条给出处理结果。"已修"的都有证据(列在第 9.2 节);"接受/待决定"的写明原因。

### 9.1 逐条结果

| 编号 | 结果 | 做了什么 | 证据 |
|---|---|---|---|
| A-01 严重 | 已修 | `build_app()` 的外层 Starlette 现在转发内层 MCP 应用的 lifespan(session manager 的任务组)。之前带合法令牌的 `/mcp` 全部 500 | 9.2 探针 1 |
| A-02 | 已修 | `V009` 不可重入的两条索引仍是 `CREATE INDEX`(MySQL 5.6 无 IF NOT EXISTS),但文件头给出了按步骤续跑的说明;回滚脚本改为每步独立、报 1146/1091 可跳过 | 文件本身 |
| A-03 | 已修 | 回滚不再 DROP 审计表,改为 `ALTER TABLE … RENAME TO …_rolledback_20261107`(保留主键与索引,可逆)。不再建议 CTAS 备份 | `recovery/V009_rollback.sql`;H2 测试已同步 |
| A-04 | 已修 | 审计 SQL 新增 C10 共 12 条(V009 两张新表),头注释的 106 改为实际 156(C1–C10)。已用 H2 执行验证 | 9.2 探针 3、4 |
| A-05 | 待用户决定 | 见第 10 节 | — |
| A-06 | 待用户决定 | 见第 10 节 | — |
| A-07 | 已修 | Java `createRun` 先做条件 UPDATE 原子占用任务,输家回滚;BFF 把冲突映射为 409 `RUN_ALREADY_ACTIVE`;Mock 同样语义 | 9.2 探针 5(联调) |
| A-08 | 已修 | 控制桥查询白名单补上 `mandate_id`;snapshot / gap-report 返回 200 并带齐 Java 头 | 9.2 探针 2 |
| A-09 | 已修 | CORS `allow_headers` 加入 `Authorization`;外部来源仍被拒绝 | 9.2 探针 6 |
| A-10 | 已修 | Java 已应用但状态回写失败:apply / review 返回 200 + `warnings`(`RUN_STATE_NOT_UPDATED` 等);重试会补记(`RECONCILED`),不会重复应用 | 9.2 探针 6 |
| A-11 | 已修 | `dev-offline.sh` 的 BFF 显式 `POETRY_STUDIO_AUTH=off`,界面有离线横幅 | 脚本 |
| A-12 | 已修(部分) | HTTP 暴露的工具集默认只有两个只读工具;写工具必须由 `POETRY_MCP_EXPOSED_TOOLS` 显式点名,未知名启动即失败。另见第 10 节的 worker 与令牌拆分问题 | 9.2 探针 1、pytest 用例 |
| A-13 | 已修 | 来源无任何 citation 与 text version 引用时 VERIFY 拒绝(`NOTHING_TO_VERIFY`);REJECT 前检查已发布内容的依赖(`SOURCE_IN_USE`,409 列出依赖项);版本的 `source_locator` 未填写会在响应里报告,不阻断 | Java 代码;JUnit 未运行 |
| A-14 | 已修 | Python 两处与 Java 两处令牌比较改为常量时间(`hmac.compare_digest` / `MessageDigest.isEqual`);空配置永不匹配 | 9.2 探针 2 |
| A-15 | 已修 | 面向浏览器的错误文案固定,附参考编号;异常原文与内部主机名只进日志。覆盖 BFF 的领域服务、人工评审通道、事件流、profile | 9.2 探针 6 |
| A-16 | 已修 | Java 人工写入口改为先校验令牌、再按字节上限(400 KB)读取请求体 | Java 代码;JUnit 未运行 |
| A-17 | 已修(部分) | SSE 连接数上限(`POETRY_STUDIO_MAX_EVENT_STREAMS`,默认 20,超出 429);取消运行只允许发起人或平台管理员;登录限流改为"按(账号,地址)+按地址"两道,淘汰策略不再清空整表。**未修**:多副本共享限流(需要外部存储,登记在第 10 节) | 9.2 探针 6 |
| A-18 | 已修(部分) | MCP 不再对宿主机发布端口;离线演示绑定 127.0.0.1(原先 0.0.0.0);k8s 清单补 `POETRY_STUDIO_AUTH`、`POETRY_STUDIO_USERS_FILE`、BFF Service,并在头部列出部署方必须补齐的 Secret / PVC / profile 卷。**未修**:k8s 的 profile 卷与账号 PVC 需要部署方决定存储,清单里只写了说明 | compose / k8s 文件 |
| A-19 | 已修(部分) | `drop_poetry_objects.sql` 补上 V007–V009 的表(仅开发库回退脚本,未执行);审计计数已更新。**接受、未修**:`PoetryStudioRules` 不做同形字符归一化(经 BFF 不可利用,仅直接持有审核令牌者可触发,风险极低);`student-app` 素材路径的两项待核实项不在本路径内 | 文件本身 |

### 9.2 本轮实际运行的检查(不是测试套件)

所有检查都是一次性脚本或进程内调用,没有运行 pytest / vitest / mvn test / make test-all,没有连接数据库,没有执行迁移。

1. **A-01 MCP 握手探针**(`/tmp/a01-probe/probe_mcp.py`,修复前后各跑一次)
   - 命令:`PYTHONPATH=content-agent/agent/poetry-domain-mcp/src uv run --offline --frozen --no-sync python -B -I /tmp/a01-probe/probe_mcp.py`
   - 修复前:`initialize with a valid token -> 200` 失败,实际 `500 Internal Server Error`;`tools/list`、`tools/call` 同样失败。
   - 修复后:无令牌 401、错误令牌 401、`initialize` 200 且 serverInfo 为 poetry-domain、`tools/list` 200(默认只返回 `get_integrity_gap_report`、`get_work_snapshot`)、`tools/call` 200 并返回 `DOMAIN_API_UNAVAILABLE`(未配置 Java 时不伪造成功)、三个写工具经 HTTP 调用被拒。结果 `ALL PASSED`。
   - 对应 pytest 用例 `poetry-domain-mcp/tests/test_mcp_endpoint.py` 已写,**未运行**。
   - 注意:本机 `.venv` 中 `mcp` 为 2.3.0,与 `uv.lock` 一致(已核对)。
2. **A-08 / A-14 探针**(`/tmp/a01-probe/probe_a08.py`):snapshot 与 gap-report 200,Java 路径与 Agent 头正确;错误或缺失 `mandate_id` 为 400;令牌比较函数对空、缺失、相等、不等、非 ASCII 的结果符合预期。
3. **审计 SQL 在 H2 上整条执行**(`/tmp/a04-scratch/AuditProbe.java`,一次性 Java,非 JUnit):载入 V001–V009 后执行 `audit_integrity_checks.sql` 的 156 条检查,结果 `nonZero=[]`。说明:H2 的 MySQL 模式对 `UNION ALL` 检查可接受,**不等于 MySQL 5.6 上的行为**。
4. **C10 正反例探针**(`/tmp/a04-scratch/C10Probe.java`):正常数据 0 条误报;12 条 C10 分别对一行坏数据都能触发。
5. **BFF 与 Studio 联调**(`content-agent/deploy/dev-mock/chain_check.py`,进程内、不开端口):**60/60 通过**,覆盖 A-07 的冲突、A-10 的修复路径(在探针 6 中)、令牌隔离、评审门槛、来源核验等。
6. **BFF 行为探针**(`/tmp/a01-probe/probe_bff.py`):**16/16 通过**。覆盖 A-09 预检、A-10 apply / review 写回失败与自愈、A-15 错误文案不含主机名、A-17 连接上限与限流淘汰。
7. 静态:`ruff check content-agent` 通过;全部 `.py` `py_compile` 通过;`bash -n` 通过;`make check-layout` 无 FAIL;`mvn -o test-compile`(vvv-poetry)退出码 0;审计 H2 探针与 C10 探针在本轮最后一次改动后复跑通过。

## 10. 待用户决定(产品与安全语义,未改行为)

### 10.1 A-05:agent 令牌持有者能否自批自用;CONTROL 令牌拆分;无逐项记录时的旧行为

现状(已证实):持有 `POETRY_AGENT_INTERNAL_TOKEN` 的调用方可以 `createProposal` → `reviewProposal(APPROVE, 任意 reviewer_id)` → `apply`,全程不写 `poetry_agent_proposal_item`,因为无逐项记录时 `apply` 执行全部可执行项(D7 为向后兼容保留)。`/reviews` 与 `/apply` 挂在 CONTROL 令牌下,而 worker 也持有 CONTROL 令牌,所以"人工评审"的真实保证目前是"worker 代码不去调用这两个路由",而不是服务端检查。提示注入本身不能直接走到这里(DeerFlow 没有这两个令牌),需要 worker 代码缺陷或令牌泄露。

| 方案 | 做法 | 代价 | 我的建议 |
|---|---|---|---|
| A. 拆 CONTROL 令牌 | worker 只拿读与运行状态的令牌;`/reviews`、`/apply` 只接受 BFF 专用令牌 | 需要改 compose / k8s 的 Secret 与 BFF、worker 配置;部署一次 | **建议做**,代价小,直接消除"worker 被攻破即可自批"的路径 |
| B. 拒绝无逐项记录的 apply | 有可执行项时必须先有逐项记录(或明确全部 APPROVE 的记录) | 旧调用会失败;需要确认没有依赖旧行为的调用方(目前只有 BFF 调用,且 BFF 已总是写逐项记录) | **建议做**,BFF 已满足新规则,影响有限 |
| C. 评审人不能等于提案创建人、评审人必须是人 | 复用 `PoetryStudioRules.reviewerProblems` 类规则 | 规则误伤风险(署名规则已知误伤 Reagent 等) | 可选,优先级低于 A、B |

**需要你决定**:是否同意做 A 与 B;若同意,B 的旧行为是否需要保留一个过渡开关。

### 10.2 A-06:改写已 VERIFIED 来源或已 PUBLISHED 断言下的 locator

现状(已证实):`setLocator` 不检查来源状态与 claim 状态。来源已 VERIFIED、claim 已 PUBLISHED 时,改 locator 返回 200,来源仍显示 VERIFIED,学生端读到的是未经核验的出处。变更只进 `poetry_studio_check_log`,发布与撤回才进 `poetry_review_log`。

| 方案 | 做法 | 代价 | 我的建议 |
|---|---|---|---|
| A. 拒绝 | 来源 VERIFIED 或 claim PUBLISHED 时 409,提示先撤回 | 修正笔误也要先撤回,操作繁琐 | 严格但可靠 |
| B. 降级并留痕 | 允许改写,但把来源回退为 PENDING,并写入 `poetry_review_log`(新的 action) | 需要重新核验;需要 `poetry_review_log` 接受新 action(它的词表在审计里) | **建议**:既能改笔误,又不会让未核验的出处保持 VERIFIED |
| C. 只留痕 | 允许改写,写 `poetry_review_log` 说明 | 来源仍显示 VERIFIED,问题依旧 | 不建议 |

**需要你决定**:选 A 还是 B。我的建议是 B,但它会改变 `poetry_review_log` 的使用方式,需要你确认。

### 10.3 A-12 的剩余部分:worker 与令牌拆分

HTTP 工具集已在服务端收窄为只读,但 MCP 令牌仍是同一个。若要让"持有 MCP 令牌的人也不能写",需要把写工具放到另一个令牌下,或只保留在 `/internal/*`。这与 10.1-A 是同一件事,建议一起做。

### 10.4 其他需要你拍板的事

- **多副本登录限流**:目前进程内,两个副本各算各的。要真正限流需要共享存储(Redis 或 Java 侧的表),这是新的依赖。
- **k8s 存储**:BFF 的 profile 卷与 Studio 账号 PVC 由部署方决定。
- **`AGENT_BIND_HOST`**:默认 127.0.0.1;若要局域网访问 BFF,需要你确认。MCP 已不再发布端口。

## 11. 验收标准(docs/specs/2026-11-07-runnable-demo-acceptance.md)中内容生产侧的逐条结果

按该文件的 R0/R1 口径(离线 + mock 大模型网关 + 占位素材)。**"通过"只写本轮实际做过的验证;需要真实启动服务、截图、无头浏览器的部分由联调会话统一走查,这里不写成通过。**

| 编号 | 结论 | 说明 |
|---|---|---|
| C-01 一键启动 | **未经验证** | 命令为 `make content-dev-offline`(加 Studio:`make content-dev-offline ARGS=--studio`)。脚本已做静态核对(启动顺序、端口、入口模块都存在,监听地址已限定 127.0.0.1)。**本轮两次尝试运行该脚本都被自动审批拦截,没有绕过,从未真正启动。** |
| C-02 创建任务 | 接口已验证 | 进程内联调中四类任务均可创建(BFF `POST /tasks`);Studio 界面点击未验证 |
| C-03 运行与观测 | 接口已验证 | 状态到 `AWAITING_REVIEW`、事件写入 Java、SSE 端点与续传由代码与探针覆盖;真实 SSE 流未用浏览器观测;预算字段由 BFF `/runs/{id}/budget` 提供 |
| C-04 提案审核 | 接口已验证 | 出现恰好一份 DRAFT v1 提案;diff 的标签与风险;逐项批准、驳回门槛(422);角色受限(403)。界面未验证 |
| C-05 应用 DRAFT | 接口已验证 | 批准后注释以 DRAFT 写入、被驳回的项不写入、重复应用被拒。覆盖看板数字变化由 `coverage` 接口提供,界面未验证 |
| C-06 agent 不能越权 | **已验证** | agent 令牌调 `/studio/*` 被拒(401/403);BFF 人工写入口需要审核角色;控制桥上无人工写路由(chain_check 与探针) |
| C-07 `/mcp` 带合法令牌 | **已验证** | 9.2 探针 1:initialize 与 tools/list 均 200(修复前为 500) |
| C-08 出处核查工作台 | 接口已验证 | 4 个 PENDING 来源可见;填写 locator 后状态不变;agent 令牌不能写;占位 locator 被拒(422)。界面未验证 |
| C-09 发布前检查清单 | 接口已验证 | 12 条规则,真实结论为 BLOCKED;bundle 规则在无 bundle 时为 NOT_EVALUATED(不判为通过);不含"发布"动作 |
| C-10 无 DeerFlow | 接口已验证 | `DEERFLOW_ENABLED=false` 时 STUB 产出基于快照的缺口分析提案(chain_check 与一次性脚本) |
| C-11 loading/empty/error | **未验证** | Studio 代码中有三态(S6 报告,9 个 vitest 文件**未运行**)。需要联调会话在浏览器里手工触发并截图 |

**卡点汇总**(不硬做、写明原因):
- C-01 与 C-02–C-04、C-08 的界面部分:依赖一次真实的 `make content-dev-offline` 启动,被权限拦截,需要你或联调会话在有权限的环境运行。
- C-11 与界面截图:需要无头浏览器,本会话不做。
- R2/R3 项(真实模型、真实 MySQL)不在本轮范围,按验收文件登记为待办。

## 12. 一键命令、端口、停止方法(供联调会话)

| 目的 | 命令 |
|---|---|
| 内容生产离线整链路 | `make content-dev-offline` |
| 加 Studio 前端 | `make content-dev-offline ARGS=--studio`(需先 `cd content-agent/frontend && npm install`,已完成) |
| 状态 | `make content-dev-offline-status` |
| 停止 | `make content-dev-offline-down` |
| 进程内联调(无端口) | `uv run --offline --frozen --no-sync python content-agent/deploy/dev-mock/chain_check.py` |

| 服务 | 端口 | 监听 | 说明 |
|---|---|---|---|
| Mock 域 API | 8080 | 127.0.0.1 | 内存数据,重置 `POST http://127.0.0.1:8080/__mock/reset` |
| MCP 控制桥 | 8101 | 127.0.0.1 | 假令牌 |
| worker | 8102 | 127.0.0.1 | 假令牌;DEERFLOW 关闭 |
| BFF | 8100 | 127.0.0.1 | `POETRY_STUDIO_AUTH=off`(离线横幅) |
| Studio | 5190 | 127.0.0.1 | 仅 `--studio` |

停止:`make content-dev-offline-down` 只按 `content-agent/deploy/dev-mock/.run/` 里记录的 PID 结束进程,不按进程名或端口杀进程;日志保留在同目录。
注意:脚本里的令牌全是本地假令牌,只对 127.0.0.1 上的内存 Mock 有意义,脚本不读取 `.env`。

## 13. 本轮没有做到的

- 没有真正启动 `make content-dev-offline`(被自动审批拦截两次,未绕过)。
- 没有运行任何 pytest / vitest / JUnit;新增的 BFF、MCP、worker、Mock、Java 测试只写未跑(包括本轮新增的 `test_mcp_endpoint.py`、回滚测试断言的同步)。
- 没有连接真库,没有执行 V009,没有 git 提交。
- 没有真实 DeerFlow 与真实模型(仍然只有源码阅读与 MockTransport)。
- 第 10 节的三项待决定事项需要你拍板后才能继续。


## 14. 架构审查 P0-6 / P0-5 / P0-1 / P0-2 / 第 7 节(2026-11-07,依据 docs/review/architecture-review.md)

P0-4、P0-3 归用户与 student-app,本轮未碰。

### 14.1 完成项与核验方式

| 编号 | 改动 | 核验（只读或编译，未跑测试） |
|---|---|---|
| P0-6 | `scene-validator/rules.mjs` 去掉 import 时的 argv 与 `process.exit(2)`，改为返回 `executed` / `skipped`；`compile.mjs` 无 `--facts` 时 `BLOCKED`（不落盘，无覆盖开关）；`rules_passed` 取真实执行的编号规则条数（R1–R12，R0 为前置形状检查，单列在 `rules_executed`）；`validate.mjs` 无 facts 不再输出 `COMPILES (unverified)` | `node --check` 三文件通过；`import` rules.mjs 无副作用；compile 无 facts → exit 1 且 `/tmp` 无输出；真实 `facts.chun-wang.json` → BLOCKED（R2、R3、R7 报出大量未发布/未核验项,这是正确结论,对应验收 C-09）；用 `/tmp` 下**临时全发布 facts**（非仓库文件，标注 PROBE-ONLY）跑成功路径 → `rules_passed: 12`，`rules_skipped: []` |
| P0-5 | 新增 `content-agent/pipeline/contracts/vocabulary.json`（唯一来源：asset_kind 7 种、media_level L0–L4、claim_kind、step、layer）；`bundle.schema.json` 两份副本改为 7 种 kind + L0–L4（去掉 frames / parallax / scene3d / L1.5，**加入 video**）；`scripts/maintenance/check-vocabulary.mjs` 逐项比对 schema、bundle.ts、degrade.ts、rules.mjs、Java `PoetryMediaService.KINDS/LEVELS`；`check-copies.sh` 增加该比对，并把 `vocabulary.json` 纳入学生端副本 | `check-copies.sh` 全部 same，exit 0；负例（schema 多加 `frames`）→ DIFFERS，exit 1；Java 仓库缺失时该项 SKIPPED（不算通过） |
| P0-1 | 脚本发布：`POST /api/poetry/v1/draft/script/{id}/{version}/publish`，人工令牌（`X-Poetry-Studio-Reviewer-Token`）；条件 `DRAFT→PUBLISHED`；校验 text version 与全部素材已 PUBLISHED；读取 `{poetry.bundleRoot}/{hash32}/manifest.json` 核对 bundle_hash、script_id、script_version；审计失败整体回滚 | `mvn -o -q -pl vvv-poetry -am test-compile` exit 0；`PoetryPublishTest`（mock，**未运行**）覆盖：成功、bundleRoot 未配置拒绝、manifest 指向别的脚本、未发布 text、未发布素材、非 DRAFT、hash 重复、hash/时间格式、审计 dirty 回滚、agent 令牌 401、未配置 503 |
| P0-2 | 素材发布：`POST /api/poetry/v1/draft/asset/{id}/publish`，人工令牌；条件 `DRAFT→PUBLISHED`；重新校验 rights 与 meaning；fallback 链每一级都必须已 PUBLISHED、严格降级、到达 L0 | 同上（`PoetryPublishTest` 中的素材用例，**未运行**） |
| 第 7 节 | 写 V010 草案（两张新表，不在迁移目录，未编号入账）与春望行偏移检索计划；**未建 FTS5，未写脚本，未改迁移** | 草案 DDL 在 H2 MySQL 模式下加载成功（仅语法层面）；索引字节按 767 上限核算，核对表主键改为 BIGINT 自增以避免 768 字节超限；只读 grep 确认春望首句在四份语料中的行号 |

### 14.2 新增与修改的文件

- `vvv-poetry`（content-studio 写侧）：新增 `api/PoetryPublishModels.java`、`api/PoetryPublishController.java`、`persistence/PoetryPublishMapper.java`、`service/PoetryPublishService.java`、`test/.../PoetryPublishTest.java`；修改 `config/PoetryAutoConfiguration.java`（新增 4 个 Bean，`poetry.bundleRoot` 未配置则脚本发布拒绝）、`api/PoetryAuthoringAdvice.java`（把新控制器加入异常映射，只加了一个类名）。**没有新增迁移文件**，没有改 V001–V009。
- `poetry-agent-platform`：`content-agent/pipeline/tools/scene-validator/{rules,validate}.mjs`、`content-agent/pipeline/tools/scene-compiler/compile.mjs`、`content-agent/pipeline/contracts/{bundle.schema.json,vocabulary.json}`、`student-app/runtime/contracts/{bundle.schema.json,vocabulary.json}`（字节一致）、`scripts/maintenance/{check-copies.sh,check-vocabulary.mjs}`、`docs/handoff/A-parts/{V010-poetry-corpus.draft.sql,corpus-chunwang-locator-plan.md}`、本文件。

### 14.3 需要你拍板（P0-1 / P0-2 的发布语义，目前按建议实现）

1. **谁能发布**：目前只有人工令牌（复用 `poetry.studioReviewerToken`，且必须不同于 `poetry.agentInternalToken`）。作者令牌与 agent 令牌都不能发布。
2. **脚本发布的前置条件**：text version 与全部素材 PUBLISHED；manifest 必须能在 `poetry.bundleRoot` 下找到。**`poetry.bundleRoot` 未配置时脚本发布一律拒绝**——这是 fail-closed 的选择，需要你确认部署时一定配置它。
3. **素材发布的前置条件**：fallback 链上每一级都已 PUBLISHED，且严格降级到 L0。若你希望允许「先发布顶层、降级链稍后补」，需要改成学生端对 DRAFT 的降级行为。
4. **manifest 完整性**：目前只核对 manifest 的文本字段，**没有签名**，也没有用 canonical JSON 重算 bundle 的哈希。篡改磁盘上的 manifest 仍能通过。要不要签名或重算，需要你决定。
5. 发布 SQL 只有条件 `UPDATE`，没有在 DB 上做 `WHERE bundle_hash IS NULL` 以外的并发控制；并发双发布由条件更新挡住（第二个返回 0 行被拒）。

### 14.4 本轮没有做到 / 未验证

- Java 测试**未运行**（`PoetryPublishTest` 只编译，未执行）；控制器的 MockMvc 端到端未写。
- 没有连接真库，没有执行任何 SQL，V009 与 V010 草案均未执行。
- `check-copies.sh` 的 Java 比对依赖本机的 `~/work/testserverV/vvv-poetry`（可用 `VVV_POETRY` 覆盖）；在别的机器上会显示 SKIPPED。
- 词表的其它枚举（audience、certainty、annotation_kind、verification）未纳入 `vocabulary.json`，它们不在本次审查的 P0-5 范围内。
- `vocabulary.json` 只覆盖脚本/素材相关的枚举；`student-app/production/contracts/asset-registry.schema.json` 的 `render` 列表未纳入比对。
- 春望的繁简字形（國 / 国）需要你定：见 `docs/handoff/A-parts/corpus-chunwang-locator-plan.md` §2 与 §7。
- 第 7 节的语料许可**全部未核实**。
