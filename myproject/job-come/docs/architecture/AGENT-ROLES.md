# 角色体系：最终方案（草稿）

状态：进行中。§10 的第 1、2、4 步已完成并提交，第 3、7 步部分完成，其余未做。依据 2026-11-04 的代码。
上位文档：[AGENTS-DESIGN.md](AGENTS-DESIGN.md)（产品承诺与隔离规则）。本文回答：每个 AI 步骤属于哪个角色，
角色和技能各是什么，这些定义放在哪里，以及现在哪里不一致。

## 1. 原则

1. **每个 AI 步骤都属于一个角色。** 没有裸 prompt。
2. **一个含义只有一个定义点。** 角色的技能、工具、运行方式、模型场景、委派关系、所属产品，全部只在一份声明里写一次；
   代码里其余各处从它派生，或者用测试校验它。不允许同一个含义出现第二个变量、第二张表、第二个名字。
3. **角色和技能是两个概念。** 角色是"这个智能体是谁、能做什么"（产品、入口、运行方式、模型场景）；
   技能是"一种工作方式"（一个方法论包，加这种工作方式需要的工具、委派和常驻片段）。一个角色拥有一个或多个技能。
4. **一次运行只以一个技能运行，只持有该技能的工具。** 简历顾问在档案不足时以 `profile-interview` 技能运行，
   这一轮才持有 `jc_intake_record`；平时它不持有。会话的角色不变，变的是这一轮用哪个技能。
5. **需要多角色协作才加子角色；不需要委派的就是主角色自己。** `task` 工具只给声明了委派的**技能**，
   同一角色的其他技能（如 `coach-archive`）拿不到。
6. **工具是权限的唯一边界。** 一次运行能做什么，由它的技能的工具白名单决定；技能文本只能描述白名单里有的工具。

## 2. 角色与技能

**角色（role）**

| 字段 | 含义 |
|---|---|
| 运行方式 `mode` | `session`（来回对话，一个或多个技能）/ `subtask`（被委派，自己取数、判断、写结果，一个技能）/ `single`（输入已在 prompt 里，一次输出结构化结果，一个技能，没有工具） |
| 模型场景 `scenario` | `routing.yaml` 里的一条链：`coach` `reviewer` `writer` `flash` `ingest_fast` `vision`；DeerFlow 模型名为 `jc-<scenario>` |
| 产品 `product` | `resume` `interview` `apply` `shared`，用于隔离测试 |
| 对外 `entry` | 用户能否直接开会话；只有 session 角色能对外 |
| 计划模式 `plan_mode` | 是否用 DeerFlow 计划模式 |
| 子任务限制 | `max_turns`、`timeout_seconds`，子任务角色必填 |

**技能（skill）**，是角色下的子项，键就是技能 id，id 全局唯一，并且对应 `skills/public/<id>/` 一个包：

| 字段 | 含义 |
|---|---|
| `tools` | 这个技能的完整工具白名单 |
| `mcp` | 外部 MCP 工具，预留，现阶段为空 |
| `delegates` | 这个技能的运行可以通过 `task` 委派给哪些子任务角色 |
| `always_loaded` | 包里 `references/` 的哪些片段每次组合都带上，按 prompt 顺序；岗位族与定性片段由组合器按请求选择 |

角色的第一个技能是默认技能，id 与角色同名。

## 3. 唯一的声明：`backend/agent/roles.yaml`

```yaml
resume-coach:
  product: resume
  entry: true
  mode: session
  scenario: coach
  skills:
    resume-coach:
      tools: [jc_profile_photo_set, jc_profile_get, jc_profile_patch, jc_intake_plan]
      always_loaded: [method]
    profile-interview:
      tools: [jc_profile_photo_set, jc_profile_get, jc_profile_patch, jc_intake_plan, jc_intake_record]
      always_loaded: [method]
```

由它派生（替换现在各处的手写表）：

| 原来的位置 | 内容 | 现在 |
|---|---|---|
| `roles.py` `SKILL_SCOPE` | 技能可达范围 | 删除；`skill()` / `role_of()` 从声明派生 |
| `tool_catalog.py` `SKILL_TOOLS` | 技能到工具 | 删除；读技能的 `tools` |
| `deerflow_harness_client.py` `_SKILL_MODEL`、`DELEGATES`、`_PLAN_MODE_SKILLS` | 模型、委派、计划模式 | 删除；读角色的 `scenario`、`plan_mode` 与技能的 `delegates` |
| `config.yaml` `custom_agents` | 子 agent 的工具、技能、模型 | 启动时从声明生成，写了会报错 |
| `config.yaml` `models`（`jc-coach` `jc-reviewer` `jc-writer`） | 场景到 DeerFlow 模型名 | 名字由场景派生（`jc-<scenario>`），测试校验已声明 |
| `composer.py` `_ALWAYS_LOADED`、`_REGISTERED_AGENT_SKILL` | 技能片段与主技能 | 删除；片段读技能的 `always_loaded`，"是否带身份文本"读角色的默认技能 |
| `tests/test_agent_isolation.py` `PRODUCT_OF_ROLE` | 所属产品 | 删除；读 `product` |
| `extensions_config.json` `skills.<id>.enabled` | 技能开关 | 仍存在，测试校验它与声明的技能集合一致；待第 8 步删除 |
| `agent_service.py` `skill in {...}` 分支 | 按角色包装消息 | 仍是按技能名分支，待第 8 步 |
| 前端 `skillHint="..."` | 页面对应的角色 | 仍写死，测试校验它们都是对外角色；待第 8 步改为后端下发 |

## 4. 工具：一份定义

现在每个工具在三处各写一遍：`tool_catalog.py` 的 `OPENAI_TOOLS`（schema）、`mcp/server.py`（FastMCP 注册）、
`mcp/handlers.py`（`TOOL_HANDLERS`）。目前 20 / 20 / 20 一致，但只靠人维护；清单页只是报告差异，没有测试挡住。

方案：以 `mcp/server.py` 的注册为准（FastMCP 从函数签名生成 schema，是真正被模型看到的那份），
`OPENAI_TOOLS` 改为从它生成，或在确认没有其他使用方后删除。新增一个测试：`roles.yaml` 里出现的每个工具必须在
MCP 服务里注册、有处理函数。

## 5. 核对后的最终角色清单

下表每一行是一个技能，按角色分组。"持有的工具"是这个技能的运行持有的全部工具。

| 角色（运行方式、场景） | 对外 | 技能 | 常驻片段 | 持有的工具 | 委派 |
|---|---|---|---|---|---|
| `resume-coach` 简历顾问（session，`coach`） | 是 | `resume-coach` | `method` | `jc_profile_get` `jc_profile_patch` `jc_profile_photo_set` `jc_intake_plan` | 无 |
| | | `profile-interview` 档案访谈（档案不足的那一轮） | `method` | 上述四个加 `jc_intake_record` | 无 |
| `coach-mock` 面试教练（session，`coach`） | 是 | `coach-mock` | 无 | `jc_profile_get` `jc_bank_search_questions` `jc_question_upsert` `jc_answer_save_attempt` `jc_mock_session_history` `jc_mock_plan` `jc_mock_ask` `jc_mock_end` `jc_mock_review`（委派接入后删除） | `interview-reviewer` |
| | | `coach-archive` 面试记录（尚无入口，第 7 步接入） | 无 | `jc_profile_get` `jc_question_upsert` `jc_interview_save` | 无 |
| `apply-pipeline` 投递经理（session，计划模式，`coach`） | 是 | `apply-pipeline` | 无 | `jc_profile_get` `jc_job_fetch` `jc_job_parse` `jc_fit_score` `jc_profile_patch` `jc_apply_pipeline` | 无 |
| `interview-reviewer` 独立评审（subtask，`reviewer`） | 否 | `interview-reviewer` | 无 | `jc_profile_get` `jc_mock_session_history` `jc_mock_report_write` | 无 |
| `resume-reviewer` 导出质检（single，`flash`；第 6 步改 subtask 与 `reviewer`） | 否 | `resume-reviewer` | `severity` `method` `structure` `evidence` | 无（第 6 步加 `jc_profile_get` `jc_resume_review_write`） | 无 |
| `resume-writer` 简历撰写（single，`writer`） | 否 | `resume-writer` | `structure` `method` `targeting` | 无 | 无 |
| `jd-parser` JD 解析（single，`ingest_fast`） | 否 | `jd-parser`（正文就是那次调用的 prompt） | 无 | 无 | 无 |
| `fit-scorer` 匹配度评分（single，`flash`；第 7 步新建） | 否 | `fit-scorer` | 无 | 无 | 无 |

岗位族片段（`family-*`）和定性片段（`qualitative-outcomes`）由组合器按请求选择，不在声明里列。

权限取舍：档案访谈与面试记录**是所属角色下的技能**，不是单独的角色，也不是把工具合并给角色。这样简历顾问平时不持有
`jc_intake_record`，面试教练平时不持有 `jc_interview_save`，符合最小权限；委派也按技能给，`coach-archive`
拿不到 `task`。

说明：

- `single` 角色没有工具，输入全部在 prompt 里。
- 外部 MCP 工具在技能的 `mcp` 字段里，现阶段全部为空，所以不单列一列。

数据处理管线，保留为登记过场景的单次调用，不算角色：简历文本结构化（`ingest_fast`）、简历图片识别（`vision`）、
档案中英互译（`flash`）。

已删除：`coach-answer`（无入口，工具早已在 `coach-mock` 范围内）。
变动：`jc_mock_review` 删除，评审改为 `coach-mock` 用 `task` 委派 `interview-reviewer`。
`jc_resume_review` 保留为导出质检的触发点，由服务以子任务方式运行 `resume-reviewer`。

## 6. 技能、提示词

- 技能文本只能描述该技能持有的工具。已有测试：SKILL.md 里出现的 `jc_*` 必须在该技能的 `tools` 里。
  这条规则抓到过 `coach-mock` 的一处错误（要求用 `jc_job_fetch`，该技能没有这个工具），已改文本。
- 单次调用的角色，其 SKILL.md 就是那次调用的 prompt 契约，不再写"调用某工具"的流程。
  `jd-parser` 已按这个做；`resume-writer`、`resume-reviewer` 本来就是。
- 方法论片段（`references/`）由技能的 `always_loaded` 引用，已不再散在 `composer.py`。
- 提示词文件（`prompts/`）与技能文本不重复定义同一角色。`jd-parser` 已合并；`prompts/ingest/` 里剩下的
  结构化、图片识别、匹配度评分，以及 `prompts/coach/`，第 7 步逐个处理。

## 7. 钩子与中间件

现有的钩子只有两类：

- `JCProductRulesMiddleware`：注入产品规则、语言、角色族方法论，真实使用。保留。
- `jc.mcp.identity_interceptor`：用运行上下文覆盖 `jc_*` 身份参数，是隔离的关键，保留。

`jc.mcp.interceptors.build_apply_pipeline_review_interceptor` 是空实现，只为兼容已部署配置而留，在
`extensions_config.json` 和示例里仍被引用。方案：两个配置文件和代码同一次提交里删除，并在部署文档里写明
服务器上的配置要同步删除。

## 8. 外部 MCP

`roles.yaml` 里预留 `mcp: []`，不接入。接入时每个外部工具必须显式写进某个角色的 `mcp` 清单，
不因接入而对所有角色可见；凭据按用户隔离。候选：飞书/钉钉文档（导入 JD 与简历、导出）、Playwright（抓取 JD，
要考虑站点条款，倾向让用户粘贴正文）。

## 9. 审计发现（均已对照代码）

1. **角色定义散在十处。** 见 §3 的表。已经漂移过：`resume-reviewer` 在 `config.yaml` 里是 `jc-coach`，
   代码里实际走 `flash`。
2. **场景名和模型名是同一个含义的两个名字。** `coach` ↔ `jc-coach`、`reviewer` ↔ `jc-reviewer`、`writer` ↔ `jc-writer`
   一一对应。
3. **会话的 `kind`（resume/coach）和 `skill_hint` 表达同一个信息**（会话属于哪个产品），都存在会话表里，
   `kind` 用于列表筛选。方案：`kind` 由角色的 `product` 派生。数据库列是否保留需要看迁移成本，我还没评估。
4. **`skill_hint` 是客户端传的自由字符串，后端原来没有校验。** 客户端理论上可以用内部角色或不存在的名字开会话。
   我没有确认这是否能走到 `jc_mock_report_write`（该工具还要求运行身份里有 `mock_session_id`，这个值来自哪里需要进一步看）。
   现在开会话只接受 `entry: true` 的角色；发消息时遇到已下线的角色会返回 `agent_retired`，而不是以空工具面继续跑。
5. **三份工具定义**，见 §4。
6. **悬空与过时内容。** `coach-answer`、`coach-archive` 无入口；`jd-parser` 技能与实际不符；空实现的拦截器仍被引用。
7. **会话内的技能切换仍写死在两处。** `resume_task.coach_skill_for` 决定简历顾问这一轮用哪个技能，
   `agent_service` 按技能名分支包装消息。技能归属已经在声明里，切换条件还没有；这是第 8 步。

## 10. 实施顺序（带进度）

每一步单独提交、单独通过测试。

1. **已完成。** 建 `roles.yaml` 和加载器 `jc.agent.roles`，加载时校验结构；`tests/test_roles.py` 校验它与技能包、
   路由场景、DeerFlow 模型、工具目录、扩展配置、前端 `skillHint` 一致。
2. **已完成。** 工具面、模型、委派、计划模式、子 agent 定义、管理端 inventory、组合器的片段表都从它派生，
   手写表已删除；角色拥有技能，工具、委派、片段挂在技能上；`skill_hint` 只接受 `entry: true` 的角色；
   `config.yaml` 不再允许声明 `custom_agents`。
3. **部分完成。** 目录、MCP 注册、处理函数三处是否一致已有测试把守；但仍是三份各写一遍，没有收成一份。
4. **已完成。** 技能文本只能提到角色持有的工具，已进测试。`coach-mock` 的 `jc_job_fetch` 是技能文本写错
   （该工具读 URL，不读 `job_id`；必备项由 `jc_mock_plan` 提供），已改文本，没有放宽工具。
5. 未做。接入委派：`coach-mock` 委派 `interview-reviewer`，删除 `jc_mock_review`。
6. 未做。导出质检改子任务，新增 `jc_resume_review_write`。此前 `jc_resume_review` 没有任何角色持有，
   这一步完成后才能加"目录里每个工具都有持有者"的测试。
7. **部分完成。** `jd-parser` 的 prompt 已并入技能包，服务从技能包读取，旧的 `prompts/ingest/jd_parser.md` 已删；
   `coach-answer` 已删。未做：补 `fit-scorer`，`coach-archive` 接入面试教练。
8. 未做。清理空拦截器与会话的 `kind`；技能切换条件（`coach_skill_for`）和消息包装迁入声明；
   扩展配置里的技能开关删除；前端公开角色清单改由后端下发。
9. 未做。有密钥的环境里跑完整模拟面试，验证委派身份、工具隔离、`jc-reviewer` 模型。

## 11. 不在本迭代

语音模拟面试、会议辅助、外部 MCP 的实际接入。
