# TECH-API：HTTP、认证与接口契约

- **状态**：V1 已实现接口的开发约定
- **最后更新**：2026-10-16
- **权威来源**：FastAPI OpenAPI：本地 `/docs`（仅当 `JC_DOCS_ENABLED=true`）及 `backend/server/src/jc/api/` 的 Pydantic schema。

## 1. 对外边界

- API 根路径固定为 `/api/v1`；浏览器通过同域相对路径访问。
- 生产流量由 Nginx 把 `/api/v1/*` 转发到 FastAPI，前端不得内嵌服务端 host 或端口。
- OpenAPI 描述与 Pydantic 请求/响应模型是字段级接口契约；本文件不复制每个 schema，避免第二份过期 API 文档。

## 2. 资源分组

| 路由前缀 | 责任 |
|---|---|
| `/auth` | 注册、登录、登出、账户设置、双路径邮箱验证、密码找回与会话上下文 |
| `/profiles`、`/resumes` | 简历上传、**对话建档**、档案草稿/确认、证据补全、优化、导出前质检、导出（`pdf` / `docx` / `html`，三者内容一致） |
| `/jobs` | JD 粘贴/受限读取、解析、匹配与申请准备流程 |
| `/coach` | 模拟面试、题库、回答、真实面试归档 |
| `/agent` | Agent session、SSE 消息流、取消与历史消息 |
| `/campaign`、`/notifications` | 机会准备节奏、站内通知 |
| `/admin` | 受限运维/审计能力，必须额外鉴权 |

## 3. 接口规则

1. **身份与资源归属**：每个需登录的接口先解析 session，再检查 profile、job、session、export 等资源归属；不得仅相信客户端传入的 ID。
2. **版本与演进**：新增字段使用可选/可兼容的方式；破坏性变化通过 `/api/v2` 或明确迁移计划处理。
3. **输入验证**：在路由/Pydantic 边界完成格式、枚举、大小和权限校验；服务层接收已校验数据。
4. **错误格式**：业务错误统一返回 `{code, message}`。两个字段的受众不同，不要混用：
   - `code` 是**稳定契约**，供前端分支判断；改名等于破坏性变更。
   - `message` 是**给用户看的中文**，要说清处境并给出下一步。它不是日志文案——
     抛错处写的英文串会原样显示在界面上（曾经就发生过：`Invalid email or password`
     出现在中文登录表单里）。需要排查用的技术细节走日志，不进 `message`。
   - 不泄露堆栈、密钥或内部对象 key。
   - 前端有两道防线：`code → 文案` 映射，以及对「基本不含中文的长句」的兜底替换
     （`lib/api/user-error.ts`）。它们是兜底，不是写 `message` 时可以偷懒的理由。
   - **新增一个 `code` 时，要么同步 `CODE_MESSAGES`，要么把 `message` 写成中文。**
     `scripts/verify_error_copy.py` 会扫出两者都没有的 `raise` 并失败。抛错处写中文往往更好——
     它能带上那个处境特有的数字（同一个 `fetch_too_large` 在静态页是 500KB，动态页是另一个上限）。
   - 状态码要和语义对上：参数缺失是 400，不是 404。把它写成 404，用户会收到
     「请求的内容不存在」，然后去找一个他从没指定过的东西。
   - **读不出 `{code, message}` 意味着请求没到达我们的 API**（rewrite 失效、前置代理、
     网关页）。前端对这种情况给的是「没能连上服务」，不是「请求失败」，也不是调用方的
     域兜底——那会把一个没被拒绝的请求说成业务失败。门禁见
     [`QA-TESTING.md`](../operations/QA-TESTING.md)「失败文案是发布门禁」。
5. **状态变更**：确认档案、保存回答、创建导出等写操作必须可追踪；对可能被客户端重试的高价值写操作评估幂等性。
6. **流式响应**：Agent SSE 事件需有稳定事件类型和终止事件；取消、失败和工具调用必须可被客户端区分。

## 4. 账户与邮箱验证契约

- `GET /auth/account`、`PATCH /auth/account`：只允许已登录用户读取或更新自己的显示名称、界面语言和默认表达力度；V1 不支持直接修改邮箱。
- 注册和 `POST /auth/resend-verification` 会发送同一封验证邮件，邮件内同时包含一次性验证链接和 4 位数字验证码。
- `POST /auth/verify-email` 接收链接 token；`POST /auth/verify-email-code` 只允许已登录用户提交自己的 4 位验证码。
- 每次重发都会使旧链接和旧验证码失效；验证码采用 TTL、哈希存储和最多 5 次失败尝试限制。验证成功后两种凭据均失效。
- `POST /auth/forgot-password` 的响应文案带上链接有效期，取自 `jc_password_reset_ttl_hours`
  （默认 1 小时）。时效由后端给出而不是前端写死：它可配，前端写死任何数字都会漂。
- 同一个接口有两种「不发邮件」，处理方式刻意不同：
  - **邮箱未注册**：仍返回 200 与同样的文案。这是防邮箱枚举，不能改。
  - **SMTP 未配置**：返回 `email_not_configured`。早期这里是静默成功，于是用户会去等一封
    永远发不出的邮件。配置缺失是我们的问题，必须说出来。

## 5. 高风险接口附加约束

- **建档有四个入口，但只有一条解析链。** `POST /profiles/upload`（文件）与
  `POST /profiles/from-text`（粘贴文本）在服务端汇到一处：`from-text` 把文本写成 `.txt`
  source，再交给上传那条后台解析任务，所以解析状态机、阶段上报、失败文案、语言识别、
  草稿待确认态都只有一份实现。
  - **不要让 `from-text` 直接调 `ProfileStructurer`。** 那样会得到第二个解析入口，
    带着自己的一套状态与文案，然后与上传那条漂移。
  - `raw_text` 下限 80 字（`_MIN_TEXT_CHARS`），上限 50 000 字。下限不是格式洁癖：
    低于它结构器无可提取内容，会**按合理猜测编造一份档案**，用户拿到的是一段他没干过的经历。
    因此拒绝文案必须说清「该写什么」（公司、时间、做的事），而不只是「太短」。
  - 校验失败是 400 + `code: "invalid_upload"`。这个 code 被前端 `CODE_PREFERS_SERVER_MESSAGE`
    列为「优先用服务端原文」——一个 code 覆盖了类型不支持 / 文件过大 / 内容过短三种原因，
    而区别恰恰就是用户唯一需要知道的信息；固定文案只能写得含糊到三者都适用。
  - 另两个入口（对话建档、结构化问答）不新建档案源，见下方 `/intake` 条目。
- 档案事实变更只能由用户确认提交；模型产生的是建议或待确认 patch。
- `GET /profiles/{id}/evidence-gaps` 与 `POST /profiles/{id}/evidence-answers` 是**用户补充事实**的通道，
  不是模型写入通道：前者为确定性扫描（无模型调用），后者只向 `payload.evidence_answers` **追加**用户亲笔内容
  并递增 `version`，不修改任何既有要点。方法论与信任等级见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 9 节。
  - `evidence-gaps` 每项可带 `metrics: MetricCandidateItem[]`，用于前端渲染可点击的指标句式。
    字段为 `dimension` / `unit` / `direction` / `skeleton`。
    **契约：`skeleton` 永不包含数值**，只有维度、单位和留空符 `___`（前后端共用同一常量）。
    预填一个看似合理的数字会被用户直接接受并送到真实招聘方，代价全在用户身上。
  - `direction` 五个取值：`down`（越低越好）/ `up`（越高越好）/ `scale`（量级）/
    `self`（维度名本身已含方向，不要再加方向词）/ `unknown`（认不出，前端**不得**显示方向提示，
    默认 `up` 会错误地告诉用户错误率本该上升）。
  - `metrics` 仅在 `kind` 为 `missing_outcome` / `unquantified_outcome` / `vague_quantity` 时非空。
    其余 kind（如 `weak_ownership` 问的是担责程度）返回空数组——
    给它们挂指标句式等于索取错误类型的答案。门禁按 **kind** 而非按岗位族的
    `quantification_optional`：法务/HR 的问题一旦问出来，答案仍然是数字。
- `GET /profiles/{id}/writing-options` 与 `PUT /profiles/{id}/writing-options` 读写目标岗位族与包装角度
  （最多 2 个）。这两项是**纯呈现偏好**而非事实，因此允许直接写入 `payload.preferences`，
  无需走档案确认流程；未知 id 忽略而不报错，空值表示恢复岗位族推荐。角度**不放宽**审稿判定——
  例如 `ownership` 角度下把源文 `参与` 写成 `主导` 仍会被报为最高级别发现。方法论见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 11 节。
- `GET /profiles/{id}/export/review/stream` 是导出页面使用的 SSE 接口，参数与同步质检接口一致。
  - `progress` 事件依次报告 `read`（读档案与稿件）、`rules`（覆盖与篇幅）、`model`（事实与表达核对）、
    `save`（保存结论）；状态为 `running`、`done`，模型未得出结论时为 `unavailable`，不算完成。
  - `result.data` 为同步接口相同的最终结果；异常为 `error`，空闲期间发送 SSE 注释心跳。
  - 模型总预算默认 90 秒，单模型请求默认 25 秒并按回退链长度收紧；流的总预算另留 30 秒用于数据库操作。
  - 跳过、离开或切换稿件会取消请求；服务端等待 producer 退出后才关闭请求数据库会话。
  - 质检未完成不代表简历不合格，也不阻止用户选择下载；客户端不得把已耗时换算为完成百分比。
- `GET /profiles/{id}/export/review` 返回三态 `status`，**三态都不阻断导出**：
  - `passed` — 读过，无阻断发现；
  - `failed` — 读过，有发现。随附 `blocking_issue_count > 0`，前端据此要求用户确认一次
    （「我已了解，仍要下载」）后解锁下载，不是禁止下载；
  - `unavailable` — **没有结论**（网关不可达 / LLM 未开 / 返回不可解析 / 输入超长）。
    此时 `reviewed: false`，`issues` 里只有英文内部诊断，**不得呈现为简历的问题**，
    下载必须一开始就可用。落库 `reviewer_status = PENDING`（「没人检查过」的诚实记录）。
  - `reviewed: bool` 区分「读过稿子」与「没有结论」；`can_export` **已废弃且恒为 true**，
    仅为旧客户端保留，不要用它做任何判定。
  - `POST /profiles/{id}/export` **不再**返回 `reviewer_failed`：审稿结果只记录，不拦截导出。
  理由与三态契约见 [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) §6.3.1。
- `GET /profiles/{id}/export/review` 的 `diagnostics` 字段为确定性体检结果（篇幅、要点长度、岗位用词覆盖），
  **一律为建议级**（`severity: warning`），不计入 `blocking_issue_count`。
- 优化预览与导出前质检均返回 `coverage`（源档案要点是否仍在生成稿中）。**覆盖度一律为建议，
  不计入 `blocking_issue_count`**：合并重复要点有时是正确的编辑决定。判定标准与阈值依据见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 12 节。
- `GET /profiles/{id}/export/review` 的 `issues` 里，`code` 以 `invariant_` 开头的条目来自**确定性**
  不变量审计（`writing_invariants`），不是审稿模型的判断：它只断言「这个数字 / 这个主导动词在档案
  任何位置都找不到依据」。这类条目**一律 `severity: warning`**，不计入 `blocking_issue_count`——
  合并要点会打断归因，确定性阻断会在正确写作时误伤。
  审稿已就同一 `field` 报过的问题会被去重。判定类型与豁免见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 14 节。
- `GET /profiles/{id}/intake` 与 `POST /profiles/{id}/intake-answers` 是**从零建档**的通道。
  信任等级与证据答案相同（用户亲笔、无模型介入），区别只在于 intake 允许写**结构化字段**
  （`contact.name`、`experiences[i].scope`）——一个填不进姓名的访谈永远产不出文档。
  未识别的 `target_path` 只追加证据、不写结构。进度从 `evidence_answers` 里
  `kind="intake:{qid}"` 的条目恢复，**没有服务端会话**；档案全程 `draft`，用户仍要走确认流程。
  - **写入必须可核对，不只是可见。** 响应的 `applied` 每项带 `label`（档案位置的中文说法）
    与 `value`（存下来的原文）；`applied_paths` 仅为 API 兼容保留。
    `IntakeQuestionItem.label` 同理。**点路径不得出现在界面上**——
    用户无法从 `experiences[0].scope` 判断我们记下的对不对，回显就失去了意义。
  - **答过的问题要能改。** 它们从 `questions` 移到 `plan.answered`（留在 `questions` 会让
    计划不终止）。重答走**同一个** `intake-answers` 端点，服务端按 `question_id` 归一替换，
    并按 `target_path` 里的绝对 slot 原地覆盖 highlight（**不是 append**，否则修改会变成新增一条）。
  - **一段口述要能拆成多条。** `POST /profiles/{id}/intake-split` 按用户自己写的标点与列表符号
    把一段话拆开，返回每段的文本、将落入的空槽位、该槽位的中文标签，以及服务端按 plan
    同一规则生成的 `question_id`。**只读预览，不写任何东西**：边界位置是唯一可能拆错的地方，
    由用户确认或改完再走 `intake-answers`。槽位从问题指定的那个连号往后，不顶掉已有要点。
    不走模型，所以不可能改写或丢句——不变量是「拆分后内容字符与输入逐字相同」。
    非成果类问题（姓名、联系方式）只对应单一字段，返回 `split: false` 与一段原文。
  - **舟卡在聊天里也能推进同一个访谈。** 两个工具与上面的端点共用 plan 与写入实现：
    `jc_intake_plan`（只读，返回当前问题、`can_generate`、`blocking`）与
    `jc_intake_record`（写入用户在对话里给出的答案）。
    `jc_intake_record` 是 JC 里**唯一**一条模型不经确认卡写档案的路径——
    因为模型此刻不是在提议内容，而是在转录用户上一条消息，写进 plan 已经点名的槽位。
    守的边界是 plan 而非信任：`question_id` 必须当前开放（已答过的也拒），
    `target_path` 取自 plan（模型声明不一致则抛且不写），校验用完整 plan 而非面板的截断版。
    理由与完整约束见 [`TECH-AGENT.md`](TECH-AGENT.md)「`jc_intake_record` 为什么可以不走确认卡」。
  方法论见 [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 18 节，
  为什么不交给模型分段见 [`TECH-AGENT.md`](TECH-AGENT.md) §4。
- 优化预览与导出前质检额外返回两个字段，**两者都是确定性产物，不计入 `blocking_issue_count`**：
  - `structure`：文档级重组的结果（`section_order` 及调换原因、`summary_shape`、
    段内 bullet 的 `moves`）。重组**只重排、不改写任何一句话**，所以无需用户确认。
  - `blueprint`：岗位 blueprint 的 6 项检查（`met` / `total` / 逐项 `findings`）。
  对应的 `issues` 条目前缀为 `structure_*` 与 `blueprint_*`，**一律 `severity: warning`**。
  `structure_*` 按 `field` 去重（与审稿所报的同一字段），`blueprint_*` 按 `code` 去重——
  多项要求合法地指向同一个 field 却说着不同的事。方法论见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 16–17 节。
- `ProfileExperience.scope` 与 `ProfileProject.scope` 是**源事实字段**（团队规模、系统量级、
  业务范围），不能从要点推导。保存时空串必须归一为 `null` 而不是 `""`，否则 `profile_intake`
  会认为这题已答而不再问，用户会得到一份永远缺范围句的简历却不知道原因。
- `jc_job_fetch` 的 HTTP 读取属于受限服务端能力，详细网络边界见 [`TECH-AGENT.md`](TECH-AGENT.md)。
- 上传、导出、下载均需校验用户归属；对象存储 key 不构成授权凭据。
- **LLM 审计日志查询**（`/admin/llm/*`，均需 `require_admin`）：
  - `GET /admin/llm/calls`：按 `user_id` / `profile_id` / `scenario` / `caller` / `channel` / `status` / `trace_id` 筛选，分页。不返回 prompt 与响应原文。
  - `GET /admin/llm/calls/{call_id}`：含每次 endpoint 尝试（哪个模型失败、失败码、是否 `validator_failed`）。
    prompt / 响应 / 思考原文含**简历个人信息**，默认不返回，须显式 `include_payload=true`。
  - `GET /admin/llm/usage`：按 `scenario` / `caller` / `channel` / `final_model` / `status` 汇总调用数、失败数、token、成本与平均耗时。
    `group_by=final_model` 回答的是「真实在服务流量的是哪个模型」，而不是 `routing.yaml` 里配了谁。
  字段含义与留存策略见 [`TECH-LLM.md`](TECH-LLM.md) 第 4.1 节。

## 6. 变更流程

修改 API 前后必须同时检查：路由、Pydantic schema、前端 API client、鉴权/归属测试、OpenAPI 变化和 [`../operations/QA-TESTING.md`](../operations/QA-TESTING.md) 的回归范围。

## 申请准备与实际投递（2026-10-20）

- `POST /jobs/profiles/{id}/apply-pipeline` 仅进行岗位评估、生成和导出材料，**不会向雇主发送申请**。
- `create_application` 默认 `false`，HTTP 请求要求 JSON boolean；Web、Agent 工具声明及 MCP handler 的默认值一致。
- 保留显式 `true` 的兼容路径，但它表示用户明确确认实际已提交，不能从同意生成/导出材料推断。
- 导出成功而未确认投递时，返回 `application_id=null`；岗位评估产生的既有 `evaluated` 记录不因此变成 `applied`。
- MCP 与 HTTP 共用非阻断审稿策略。兼容保留旧拦截器工厂，但不再以「最新稿件审稿通过」提前拦截流程；归属授权、真实文件有效性、内容保留和存储错误仍由业务服务校验。
- 既有历史 `applied` 记录不自动回写或降级；系统无法判断过去记录是否真实提交。

## JD 正文诊断与 PDF 文本层诊断（2026-10-20）

- JD 解析结果新增 `integrity`：`version`、`untrusted_content`、`status`、`truncated`、`warnings[{code,count}]`。使用已有 JSON 存储，无迁移。
- URL 静态读取另在来源元数据中记录原始 HTML 的隐藏元素诊断；动态读取仅诊断已得到的正文，不宣称已检查所有 DOM/CSS 隐藏方式。
- 粘贴/URL/MCP 解析统一通过 `JdParserService`，在模型调用前生成诊断；模型不能覆盖服务端判定。原文不静默删除或改写。此机制是提示性启发规则，不是 prompt injection 防火墙。
- 模型收到的 JD 放入 JSON 数据 envelope，保持不可信输入规则；风险诊断没有命令/网络权限，不跟随正文内链。
- 导出的现有内容完整性检查使用 Unicode NFC 和印刷标点等价比较，避免排版引号/连接符误报；不改变原文、PDF 或数字。
- 新增 PDF 提取层替代字符、私用区字符和 Unicode 日期连接符警告，仅写入应用日志中的代码/计数，不记录简历正文或联系方式。现阶段未新增管理后台诊断展示，也不增加导出阻断条件。
- 不提供 ATS 得分/通过承诺；通用阅读顺序标为未评估，通过真实三模板回归测试验证指定样本的公司/要点顺序。

### career-ops 方法论增量（2026-10-20，第一批）

- Agent 每轮绑定档案版本，只附带小型索引、有限的选中字段和可容纳的纠正约束；不再首轮自动展开整份经历。`profile_context` 日志记录任务、版本与字符数，不记录正文。
- `jc_profile_get` 的模型调度和 MCP server 默认 `section=overview`。可按 `section` / `field_path` 读取，列表使用 `offset` / `limit`（1–20），结果披露 `total` / `next_offset` / `complete`。索引只含有限条目标题预览，不是完整事实。
- 超长字符串可用 `field_path` + `text_offset` / `text_limit`（1–4000）分块读取；返回 `total_chars` / `next_text_offset`。分块未读完不能断言材料不存在。单次普通读取上限 6000 字符，超限明确报错，不截断 JSON 或暗中丢弃事实。内部 legacy `profile_get(section=None)` 保留原全量契约。
- 写手、岗位匹配和审稿不重复加载头像渲染数据或整套 i18n 副本。匹配仍需完整相关档案；超过 100000 输入字符返回 `fit_input_too_large`，不发送被截断的 JSON。这里是字符保护，不是精确 token 预算，也不是历史消息压缩。
- `ProfilePayload.constraints.retracted_claims` 使用现有档案 JSON，字段为 `claim`、`correction`、`scope=profile|experience|project`、`entity_id`。经历/项目范围必须提供稳定 ID；通过原确认卡/CAS/版本快照保存。未确认提议不写档案，可通过确认修改删除约束。
- 写手/审稿/模拟面试遵守纠正范围；生产质检确定性标记同文复现为 `retracted_claim` warning，匹配证据排除同范围中仍带已否认文本的旧材料。不宣称能识别所有改写、翻译或缺少源 ID 的归属，亦不新增导出阻断。
- 匹配结果及已有 `jc_job.fit_report` 增加 `requirement_evidence` 和 `evidence_profile_version`。每项对应解析 JD 的明确要求，返回重要性依据、相关性建议、引用路径/原文/稳定 ID、待补问题。
- 服务器核验引用路径与源文；伪造、缺失、被纠正的证据不能标成核验通过。`citation_status=verified` 只代表出处存在，不代表代码已证明语义匹配。未知不等于候选人没有能力，估计的重要性不能成为硬性要求。
- Web 岗位匹配卡折叠展示“岗位要求与经历依据”和评估时档案版本；档案更新后需重新评估，旧报告不自动重算。旧报告缺该字段时不伪造证据行。

## 模拟面试：级别、系统记录作答、后台报告（2026-11-05）

- `GET /coach/mock/level-recommendation?profile_id=` 返回四个级别（`junior/mid/senior/expert`，含对照 P 序列、年限、要求）和按档案推荐的一个。推荐由 `jc.coach.level.level_for_profile` 用代码计算：经历按月合并年限，最近一段职位名可上调或下调一级；日期读不出时 `recommended=null`。P 序列只是对照，不是阿里的官方标准。
- `POST /coach/mock/sessions` 新增 `level`。未传时取推荐值；无推荐也未传则 409 `mock_level_required`，并且不占用完整模拟的月度额度。`MockSessionResponse` 增加 `level`（旧场次为 `null`）。
- 候选人的回答由服务在模型运行前写入：写到当前题（最后一个已登记、未跳过、未换掉的题）；没有当前题时（开场问候、自我介绍、跳过或换题之后）不记录。同一题的后续消息追加到同一条回答。面试官不再持有 `jc_answer_save_attempt`。换题后当前题为空，直到登记下一题（会话 `coverage.table_closed`）。
- `jc_mock_ask` 可直接传 `stem` 创建并登记新题（与 `question_id` 二选一，都传或都不传为 `ValueError`），返回里带 `question_id`。被拒绝时不留下新题。面试官也不再持有 `jc_question_upsert`；真实面试归档（`coach-archive`）仍使用它。
- 回答按场次隔离：同一道题库题在不同场次里复用时，不再把别的场次的回答当成本场的回答。
- `POST /agent/sessions/{id}/messages` 新增可选 `client_message_id`（至多 64 字符）：客户端为每条消息生成，重试同一条消息时沿用。服务端在 `jc_mock_session.coverage.recorded_messages` 里记住最近 50 个已写入回答的 id，同一 id 再来不重复记录；模型仍会再跑一轮（第一次可能没跑完）。不带 id 的请求不去重，同一句话换一个 id 是新消息（候选人可能真的说了两遍“是的”）。只有真正写进回答的消息才会被记住。
- 报告改为后台生成。场次结束时 `jc_mock_session.report_status` 置为 `queued`（没有提问的场次直接置 `failed`，原因“这场面试没有提问”）；API 进程里的 `run_mock_report_dispatcher` 用条件更新认领（`generating` 带 600 秒租约，最多 4 次运行），完成后置 `ready` 或 `failed`。迁移 `024` 对历史已结束场次：有报告为 `ready`，无报告为 `failed`，不自动排队。无报告的场次不写原因（`report_error` 为空），页面显示“这场面试的报告没有生成。”并允许重试。迁移不写任何文字，因为表的字符集若不是 Unicode，写中文会报 1366；所以迁移每一步先查再做，可重复执行，回填只动 `report_status` 为空的行。
- `GET /coach/mock/sessions/{id}/report` 只读：`status` 为 `active | pending | failed | ready`，`failed` 带原因和 `can_retry`。打开页面不再触发评审。已存储的报告即使状态还没跟上也按 `ready` 返回。
- `POST /coach/mock/sessions/{id}/report/retry`：把失败的报告重新排队。409 `mock_report_not_failed`（不是失败状态）或 `mock_report_retry_exhausted`（4 次运行已用完）。失败原因是给用户看的短句，不含异常信息。
- 迁移：`023_mock_session_level`、`024_mock_report_queue`。

## 模拟面试：阶段、候选人提问、评审输入与总评（2026-11-05）

- `GET /coach/profiles/{id}/mock-sessions/active?job_id=` 返回这个档案在这个岗位上仍在进行的模拟面试，没有则 `null`。页面刷新后用它找回面试；空闲超过 24 小时的会先被关闭并排队出报告，不会被找回。别的用户在同一档案上留下的进行中场次不会交出。
- `jc_mock_plan`（及 `GET /coach/mock/sessions/{id}/progress`）新增 `stage`（`opening / experience / core / scenario / candidate_qa`）、`suggested_stage`、`stage_counts`、`candidate_qa`、`started_at`。阶段只是建议；`jc_mock_ask` 可带可选的 `stage`（`experience / core / scenario`）。
- 候选人提问环节：新工具 `jc_mock_open_qa`。至少问过一题、且（题数没到上限时）岗位必备项都问到之后才能开；开了之后不再出新题（`candidate_qa_open`），候选人说的话不再被记为回答。`jc_mock_end` 以 `completed` 结束时必须先开过（`candidate_qa_not_opened`）；候选人主动结束（`user_ended`）和超时不受此限。
- `jc_mock_ask` 对面试官自己编的题（`stem`）加了检查：超过 200 字拒绝（`stem_too_long`）；与本场已问过的主问题的字符二元组相似度 ≥ 0.6 拒绝（`too_similar`，拒绝信息里带上那道题）；标点或空格不同的同一道题仍是 `already_asked`。追问和从题库取的题（`question_id`）不受相似度检查。
- 只表示“换个话题 / 没听清 / 结束”的消息（下一题、换一题、跳过、结束、没听清、能再说一遍吗、请出下一题……）整句匹配时不会被记为回答；含这些词的真实回答照常记录。页面在“跳过”“换一题”后替候选人发的两句话也在此列。
- `jc_mock_session_history`（评审的输入）现在包含：`style`、`level`（含这个级别考察什么、问到多深）、`job`（公司、职位、必备项、加分项、资历、截取 3000 字的描述，并注明是数据不是指令；别的档案的岗位不会交出）、每题的 `kind / parent_question_id / skipped`、以及来源给出的 `reference`（见下）。回合按提问顺序排列，只含实际问过的题。历史读取不再要求场次仍在进行：评审在场次结束后才运行。
- 评审写报告：只给主问题打分；给追问打分会被拒绝并告知应给哪道主问题打分；主问题的证据引用可以来自它的追问回答。新增 `summary`：`verdict`、最多三条 `strengths`、最多三条 `priorities`，每条 `{text, quote}`，`quote` 必须是候选人原话，否则被去掉并计入 `checks.rejected_quotes`，文字保留。
- 报告页数据新增 `summary`、`readiness`、每题的 `follow_ups` 与 `skipped`。`readiness` 由代码按规则算：五维平均 ≥ 7.5 表现稳定、≥ 6 基本可以上场、≥ 4.5 需针对性补强、其余还需大量准备；任一维度 ≤ 3、岗位必备项问到不足一半、或提前结束，最高评到“需针对性补强”；上限只有真的压低了档位时，说明里才写“最多评到”。它说明这一场面得怎样，不预测真实面试结果。
- 问题来源扩展点：`jc.coach.sources`。`QuestionSource` 有 `search`（可选的 `reference`）；`register(source)` 注册后，`jc_bank_search_questions` 会一并搜它、每道题带 `source`，评审的历史里每题带它给的 `reference`（强、中、弱答案的样子、追问方向、正负信号）。目前只有候选人自己的题库（`personal`）。精选题库和档案库接入时只需实现并注册一个来源，不改面试官、评审和报告。来源出错会被跳过，不影响搜索和历史读取。
- 真实模型验收清单：`jc.coach.acceptance`（`check_interviewer`、`check_reviewer`）。对一份录下来的面试逐条检查；代码判断不了的规则标为“需要人来读”。尚未对着真实模型输出跑过。

## 模拟面试：按岗位族、复核后的修正（2026-11-05）

- 面试按**目标岗位的岗位族**进行，而不是只看候选人过去的职位：`jc.coach.role_family.mock_role_family`，优先级是岗位已存的类别（`role_category`），其次岗位名称，最后候选人最近三段经历的职位名；都认不出时是 `general`，它不加任何指导，所以不会把面试带偏。别的档案名下的岗位不会被读取。后端工程师去面产品岗，按产品经理来面。
- 技能用元数据 `playbook: interview` 声明要岗位族的“面试视图”（`RolePlaybook.as_interview_block`）：这个岗位的成果通常怎么衡量、工作的对象是什么、三个追问方向，其中不含任何写简历的指令。简历类技能不变，仍是写作视图。`coach-mock` 和 `interview-reviewer` 都用面试视图；评审在 `run_subtask` 的 `extra` 里拿到 `role_family`。追问方向是初稿，需要各行业的专业人士审校；它是给模型的指引，不是题库。
- 面试官和评审的提示词都写明：服务互联网行业各类岗位，不要假设候选人是开发者，题目和追问按真实岗位来。级别描述去掉了研发专用的措辞；职位名的上调和下调覆盖各类岗位（主管、首席、Head of、Director、VP、Chief；管培、见习、Intern、Trainee），英文按整词匹配。
- 题型增加 `case`（案例/情景）和 `domain`（专业技能）；服务端存的是自由文本，所以不需要迁移。前端三处各自维护的题型名称合并为 `lib/question-types.ts`。
- 报告的“问到了什么”只看实际问出去的题：跳过的题不算覆盖必备项，评审没列出但问过并回答了的题仍算。准备度新增一条：主问题回答比例不到一半最高评到“需针对性补强”，追问不算题。上限只有真的压低了档位时才写“最多评到”。
- 候选人在自己的提问环节之后点“结束面试”记为 `completed`（正常结束），不再算提前结束；超时仍是超时。
- 引用（证据和总评）必须来自同一段回答，且至少四个字；拼在两段回答之间的、过短的，都被去掉并计入 `checks`。总评里被去掉的引用数在报告页显示。
- 只表示“下一题 / 换一题 / 跳过 / 结束 / 没听清”的消息前面有语气词（好的、嗯、那就）时仍是控制语句；单独的语气词仍是回答。
- 刷新页面、换岗位或换档案时，页面会丢掉不属于当前岗位和档案的进行中面试；通知的“查看报告”只属于开始它的那个岗位。
