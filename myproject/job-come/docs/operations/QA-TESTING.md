# QA-ACCEPTANCE：V1 验收与发布门禁

- **状态**：当前 V1 验收基线
- **最后更新**：2026-10-17

## 1. 当前结论

**V1 是可上线候选版本，已完成本地代码与构建验证；尚未获得生产发布批准。**

已完成的最近本地验证（2026-10-17）：

- Python：`648 passed, 6 skipped`（受限沙箱下 `641 passed, 7 failed`，失败全部是
  Chromium 起不来），在可启动 Chromium 的环境下**全套无失败**；
- `scripts/verify_error_copy.py`：8 项失败文案断言 + 「每个 `code` 都有用户文案」结构性门禁
  （39 个 code，其中 3 个来自响应体字面量；36 个在前端有映射，2 个运维 code 豁免）全部通过，
  并做了 6 次变异测试（见下）。本轮该门禁自身补了一个漏洞：它原先只扫 `raise`，
  扫不到异常处理器里直接写进响应体的 code——详见下文；
- 前端：`rm -rf .next && npm run build` 全新构建成功（21 条路由）；`npx tsc --noEmit` 通过；
- `ruff check`（`backend/server` 全量）**零告警**。alembic 版本文件对 E501 做了 per-file-ignore，理由见 [`ADR-004`](../decisions/ADR-004-layered-agent-architecture.md) §1.1；其余 60 处长行已实际改短，不是豁免掉的；
- `scripts/audit_visual.py`：9 个页面对比度/无效类/溢出审计 **clean**（2 个禁用控件按 WCAG 1.4.3 豁免）；
- `scripts/verify_ui.py`：真实 Chromium + 构建产物，JD 读取契约、匹配结果、错误恢复、页面水合无 page error；
- `scripts/verify_resume_steps.py`：真实 Chromium 驱动简历**第 1/3/4 步**，校验写作偏好、证据问答、
  对话建档（必答题、blocking 文案、`applied_paths` 回显、可点句式插入后光标落在 `___` 上、
  一段口述拆成多条且取消不丢原文）、blueprint 面板（达标计数、未达项与改法、
  跨面板打开证据面板）、`scope_line` 与项目经历节在结构化预览中可见、覆盖度点名、篇幅提示、
  警告级问题不阻断导出，并量化版面（见下）；
- `scripts/verify_export_gate.py`：真实 Chromium，断言**导出永不被质检拦住**。三个 case 分别覆盖
  「读到发现」「没有结论」「请求一直不返回」——见下文「导出门禁」。
- `scripts/verify_error_copy.py`：**不需要浏览器**，用项目自己的 TypeScript 编译
  `lib/api/errors.ts` 与 `lib/api/user-error.ts` 并断言失败时用户读到的文案——
  见下文「失败文案是发布门禁」。已接入 `scripts/test-local.sh`。
- `scripts/verify_auth_errors.py`：真实 Chromium，驱动登录页与忘记密码页的失败路径
  （错密码、无 code 的英文串、请求没到达、成功/失败分别渲染）。需要先起好前端生产构建，
  `--base` 指定地址。与上一条覆盖同一批行为，区别是**它验证页面真的把文案渲染出来**。
- `scripts/verify_agent_rail.py`：真实 Chromium + 构建产物，驱动舟卡侧栏的收起/展开闭环。
  核心断言是**收起不卸载**：脚本先挂起 `/messages` 的响应、在运行**在途**时收起，
  放行后确认流式回复仍然到达、重新展开后仍在线程里。另外断言条宽 ≤ 48px、竖排标签不超出条宽、
  侧栏布局宽度归 0、收起时无 `role="separator"`、文档列变宽、三态文案与 `aria-label` 正确、
  读过后未读徽标清零。跑法与端口注意见
  [`OPS-DEVELOPMENT.md`](OPS-DEVELOPMENT.md)；
- 新增侧不变量（`writing_invariants`）与写作语义验收脚本的判定函数均有单测覆盖，
  见下文门禁 1 的说明；
- LLM 故障转移与调用审计共 54 条单测（`test_llm_call_log.py` 26 +
  `test_v1_reviewer.py` 17 + `test_chat_litellm_adapter.py` 7 +
  `test_llm_router_response_validation.py` 4），覆盖故障链每跳只试一次、`final_model` 必须是
  **真实生效**的那个、`validator_failed` 与网关失败的区分、迟到的失败事件不得覆盖已记录的成功、
  缺 key 记 `skipped`、payload 开关与截断、多维筛选与用量汇总；外加一次 SQLite 冒烟
  （建表 → 写 2 万字中文正文 → 各维度筛选 → `usage_rollup`）。
  这批测试**不再 mock 整个 litellm 模块**，只伪造最外层网关应答（`tests/conftest.py`
  的 `fake_gateway`），因此真实 `litellm.Router` 的 fallback 解析、cooldown 与
  `post_call_rules` 都真的跑到了——旧写法下这些顺序与次数全是测试自己的发明。
  本轮做了 9 次变异测试，其中 2 次暴露了覆盖空洞（见下）。见下文「LLM 审计日志」；
- 角色定义**只有一处**：`config.yaml` 里每个 subagent 的 `system_prompt` 现在存的是指针
  `skill:resume-writer`，启动时由 `jc.skills.composer.compose_role_baseline` 从 skill 包组装。
  这条有 3 条单测（`test_deerflow_config.py`）：源文件里不得出现第二份手写契约、
  组装结果必须等于 skill 正文、指针指向不存在或组装为空时必须抛。
  做了 2 次变异（静默回退到字面量、删掉「组装为空」那层守卫），均被抓到。
  原状态是每个角色在 `config.yaml` 里有三行英文摘要，与 101 行的 skill 契约并存——
  两份不一致时没有任何东西会失败；
- 对话建档的**口述拆分**共 13 条单测（`test_intake_dictation.py`），核心是一条不变量：
  **拆分后的内容字符与输入逐字相同**。这条让这个功能可以默认提供——按用户自己写的标点拆，
  既不会改写也不会丢句；能拆错的只是边界位置，所以接口是预览而非直接写入，由用户确认。
  另有「`1.5 倍` 不得被当成列表序号而吞掉数字」「上限截断不得丢尾部」
  「每段落在各自的空槽位、不覆盖已有要点」「每段带用户看得懂的位置标签」。
  做了 2 次变异（所有段落写同一槽位、去掉小数守卫），均被抓到；
  真机断言在 `verify_resume_steps.py`（拆分卡片、分段可编辑、取消不得清空原文）；
- 按角色分包的 skill 组装共 26 条单测（`test_skill_packages.py` 15 +
  `test_resume_task.py` 的 coach guidance 8 + `test_resume_elevator.py` 的 prompt 分层 3），
  断言**方法论真的到达了模型**而不是停在磁盘上：岗位族片段按 `role_family` 切换、
  定性岗位只认 `playbook.quantification_optional` 这一个信号、缺 skill 必须抛而不得降级、
  coach guidance 必须排在用户原话之前、每个族都解析到真实片段或基线。
  做了 5 次变异测试，5 次全部被抓到（含「所有岗位同一套方法论」这条退化）。
  `profile-interview` 作为宿主组装型 skill 也在管理端 inventory 里如实显示为启用、
  工具面与 coach 相同且不含导出闸门 `jc_resume_review`（2 条断言 + 1 次变异）。
  背景见 [`TECH-AGENT.md`](../architecture/TECH-AGENT.md)：
  harness 只把 skill 的名称与路径渲进 system prompt，正文要靠模型自己读文件，
  而 V1 刻意不给 agent 文件访问——所以 SKILL.md 正文此前在 agent 路径上**完全不可达**；
- 文档级重组、岗位 blueprint、对话建档三个模块共 59 条单测
  （`test_resume_structure.py` / `test_resume_blueprint.py` / `test_profile_intake.py`），
  其中「访谈问得完一定能生成」这条不变量**断言端状态而非阈值常量**——
  两个阈值此前各自漂移过一次，导致访谈永远停在距离可生成差一条的地方。
- 舟卡的两个建档工具 `jc_intake_plan` / `jc_intake_record` 共 9 条单测
  （`test_intake_tools.py`，真 SQLAlchemy + 内存库），守的是**唯一一条模型无确认卡写档案的
  路径**的边界：问题必须当前开放、路径取自 plan 而非模型声明、已答问题不可盲改、
  越权档案两个工具都拒。做了 3 次变异（去掉开放性判定、采信模型声明的路径、
  校验用截断 plan），均被抓到。设计理由见
  [`TECH-AGENT.md`](../architecture/TECH-AGENT.md) §4；
- `scripts/verify_intake_flow.py`：**离线端到端走查**建档全链路，已接入 `test-local.sh`。
  建档是 JC 里唯一「用户与档案之间没有模型」的路径，所以整条链路是确定性的——
  不需要模型、浏览器或 MySQL，0.7 秒跑完，因此它是默认门禁而不是手动开关。
  见下文「建档走查」。

### 版面量化门禁

第 3 步曾把简历本体推到首屏之外——建议面板叠在文档之上，用户看不到自己的简历，
读起来就是「不知道要干嘛」。「默认折叠」只把偏移从 1082px 压到 707px，
并在用户点开任一面板时失效；真解法是给文档一列自己的空间。现在这条由脚本量化并断言：

| 指标 | 当前值 | 门禁 |
|---|---|---|
| 预览区距第 3 步顶部 | 2px | 见下表（按列模式分别判定）|
| 文档列宽度 | 834px（两列）/ 930px（堆叠）| ≥ 600px |
| 第 3 步内容高度（折叠态） | 2317px / 3.2 屏 | 观察项 |
| 第 3 步内容高度（展开态） | 2707px / 3.7 屏 | 观察项 |
| 第 4 步内容高度 | 1168px / 1.5 屏 | 观察项 |
| 左栏字号档数 | 3（11 / 12.5 / 13.5px）| ≤ 3，且无 > 13.6px |
| 收起后文档列宽度 | 1122px → 1522px | 必须严格变宽；收起条 ≤ 48px |

| 列模式 | 断言 |
|---|---|
| 两列（`display: grid`） | 文档列 ≥ 600px；两列高度差 ≤ 2px；**无祖先在滚**；grid 自身不滚；左栏必须能滚；预览标签偏移 < 120px |
| 堆叠 | 文档列 ≥ 600px，文档在控件**之前**，偏移 < 400px |

两列那一行是**结构性**断言，不是距离。上一版只量像素偏移，而坏版面同样满足它——
一个「一个滚动条推两列」的缺陷因此带着通过的门禁活了一整轮。
现在判据是「每列是否拥有自己的滚动条」，坏结构无法伪装成好结构。

**两种模式必须都被执行到。** 1440×900 下 studio 面板只有 930px，低于 60rem 容器阈值，
单次运行**只会走堆叠分支**，两列规则完全没被断言。阈值在**容器**上，加宽窗口是唯一办法：
脚本现在切到 1760×1000 再测一次，先断言确实进入两列模式，再跑同一组判定。

**左栏字号也必须量，不能评审。** `.badge` / `.label-meta` 用 `@apply text-micro` 定义，
而 Tailwind 的 `@apply` 会克隆「选择器里提到被 apply 类」的每一条规则——
一条 `.studio-rail .text-micro { font-size: inherit }` 让编译器凭空多产出
`.studio-rail .badge { font-size: inherit }`，于是 badge 的字号取决于谁包着它
（`div` 里 16px，`li` 里 12.5px）。`tsc` 不看 CSS，样式表源码读起来完全正确，
**唯一能看见它的是浏览器里的 computed style**。`_assert_rail_type` 因此断言：
无 > 13.6px 文字、同一组件类不得出现两种字号、总档数 ≤ 3。

**测量自身必须被自检。** 第 3 步有两个嵌套 `.scroll-area` 都包含预览标签；取外层那个
会把它的滚动位置混进来，一度得到 `-1279px`，而当时的断言 `offset < 400` 对这个垃圾值成立——
脚本带着一项不可信的测量通过了。现在重置**每个** scroller、取**最内层**那个、
并断言 `offset >= 0`。新增的任何版面断言都要带这类自检：**永远通过的门禁比没有门禁更糟。**

### 版面门禁必须做变异测试

一条新断言写完之后，**必须把它要防的缺陷故意放回去，确认它失败**。本轮两次都做了：

| 变异 | 结果 |
|---|---|
| CSS 退回 `position: sticky` 写法 | 如期失败：`the columns are 2079px and 818px tall; one is sizing to its content` |
| 字号规则退回 `.studio-rail .text-micro { inherit }` | 如期失败，并点名 8 个 16px 元素 |
| 收起时把侧栏改成条件卸载 | 如期失败：`the sidebar was unmounted on collapse, which aborts the in-flight run and discards the streamed reply` |
| `downloadable` 退回按质检结果锁按钮 | 如期失败：`the user acknowledged the findings and still cannot download their resume` |
| `unavailable` 恒为 false（混掉「没有结论」与「有发现」） | 如期失败：`the reviewer was unavailable and the download was withheld; the user cannot fix our gateway` |
| 兜底文案退回 `"请求失败"` | 如期失败：`verify_error_copy.py` 的「unreachable service is named」 |
| 把「请求没到达」并入 5xx（`own ?? USER_SERVICE_UNAVAILABLE`） | 如期失败：两种处境给出同一句话，用户无从判断 |
| 去掉 `looksForeign` 这道防线 | 如期失败：无 `code` 的英文串原样渲染 |
| 请求没到达时返回调用方的域兜底（`fallback`） | 如期失败：一个没被拒绝的请求被说成「登录失败」 |
| 新增一个 `code` 但文案写成英文、也不进映射 | 如期失败并点名文件与行号 |
| 已有 `code` 的中文文案退回英文，同时删掉映射条目 | 如期失败并列出全部 2 处 |
| 删掉 `_get_runnable_config` 里的 handler 注入 | 如期失败：舟卡对话一条都不入库 |
| `final_model = chain[0].model`（记配置里的首选而非真实生效的） | 如期失败 2 处 |
| `record_call` 的 `except` 改成 `raise` | 如期失败：日志故障会把用户的请求一起打挂 |
| `if settings.jc_llm_log_payload` 改成 `if True` | 如期失败：开关关掉后正文仍然落库 |

理由很直接：**断言通过有两种原因**——真的符合，或者根本没测到那个元素/那个分支。
两者在输出里长得一模一样，只有变异测试能区分。两列分支此前就属于后者。

上面后两次变异给出了一个实测证据：**`verify_resume_steps.py` 在两次变异下都仍然 PASS**。
它的夹具是「质检通过」，根本进不到失败与不可用分支。所以导出门禁必须有自己的脚本
（`verify_export_gate.py`），不能靠扩充既有脚本的断言。

### 建档走查：访谈必须能走完

单测断言的是单步转移——这个问题会出现、那个答案会落地、关掉的问题会被拒。没有一条
**反复取 plan 直到问完**，而这正是这个功能在使用中真正坏掉的方式：

- **走不完。** 要点问题的 id 曾按「还差几条」推导，于是每答一条下一问就重新编号，
  plan 重新发出一个刚刚被答掉的 id，访谈永远停在距离可生成差一条的地方。
  没有任何东西失败，用户只是永远答不完。
- **答案不落结构化字段。** 答案被存成 evidence 但没写进 `experiences[i].highlights[j]`，
  `count_written_evidence` 永远数不到它，于是那个问题一直开着。
  从任何单一路径都看不出来。

所以 `verify_intake_flow.py` 用同样的档案跑两遍完整访谈——一遍全走 `IntakeService`
（面板路径），一遍全走 `jc_intake_plan` / `jc_intake_record`（舟卡聊天路径），
要求两者都到达 `can_generate`，且**主经历真的被填满**。

两条走查的答题粒度**刻意不同**：面板一次提交一个阶段，agent 一次答一题——这正是两者
真实的驱动方式，也是唯一能观察到 id 重编号的条件（一次答满一个阶段会在 plan 重算前
把槽位全部填上，按差额推导的 id 就没有机会漂移）。

| 起始模式 | 断言 |
|---|---|
| `empty` | 从零问到可生成；每个必答问题都写进结构化字段 |
| `skeleton` | 同上；另外覆盖「已有一条要点」时槽位不被覆盖 |
| `stale` | **当前工作是插入而不是编辑**：旧公司必须还在，且新公司必须排到最前 |

三条通用断言：plan 不得重发已发过的 id；主经历的要点数必须达到 3 条（**只数主经历，
不数总数**——可选的第二段经历也贡献要点，总数会掩盖「主经历仍然单薄」）；
不得留下空要点（渲染出来就是一个子弹形状的空洞）。另外每轮走查都让一条口述答案
走拆分路径，确认多点段落真的被拆开。

做了 3 次变异：把 `stale` 的插入位置改成 1（新工作没排到最前）、
要点 id 恢复成按差额推导（主经历停在 2 条）、要点答案不再写结构化字段，
均被抓到。

一次否证值得记下来：把 `jc_intake_plan` 的 `answered_ids` 改成空集**不会失败**。
原因不是覆盖空洞，而是建档问题**全部由档案形态派生**——名字填了，姓名问题就不再被生成，
与「有没有记得它被答过」无关。`answered_ids` 是冗余保险而非主机制，
所以文档里不应宣称这条走查在守它。

### 架构分层门禁

`tests/test_architecture_layers.py` 把分层规则变成会失败的测试。它存在的理由很具体：
分层写在文档里时，违例是「下次重构时再说」；写成测试后，违例是「这次提交过不去」。
规则本身与每层「不得依赖谁」的完整表格见
[`ADR-004`](../decisions/ADR-004-layered-agent-architecture.md)。这里只说验收时的注意点。

**第一，必须遍历函数体内的 `import`。** 上一轮的 `services/ ↔ mcp/` 循环依赖就藏在函数内部——
模块顶部看起来干净，循环靠「延迟导入」掩盖着，`import` 一提到文件顶部就立刻报
`ImportError`。所以这个测试用 AST 走完整棵树，不只看顶层语句。只检查文件头部的版本
对那个真实存在过的循环是瞎的。

**第二，多模态线格式只允许一个生产者。** 断言 `"image_url": {` 这种构造只出现在
`jc/llm/vision.py`。注意 `jc/llm/call_log.py` 里也出现 `image_url` 字面量，但那是**读**
（脱敏时判断 `type == "image_url"` 以免把 base64 图片写进审计表），是消费者不是生产者。
门禁的正则必须区分构造与出现，否则要么漏判要么误判。

**第三，`domain/` 层必须零 I/O。** 禁止 import sqlalchemy / aiomysql / redis / litellm /
httpx / requests。这层放的是方法论与岗位族判定这类纯函数，一旦它能碰数据库，
`services/` 与 `skills/` 之间那条循环就会以另一种形式长回来。

这 4 个测试做了 4 次变异（函数体内的循环 import、`llm/ → services/`、`domain/` 引入
sqlalchemy、第二处手拼 `image_url`），4 次全部被抓到。和版面门禁同理：
验收这块请以「变异能否被抓到」为准。

### 路径与启动目录：一个「测试因为错误的原因通过」的案例

`tests/test_paths.py` 守住两件事：仓库布局只有一个所有者（`jc/paths.py`），以及**从任意工作目录都能启动**。

值得专门记一笔的是这个缺陷**怎么躲过了全套测试**。`llm/router.py` 把 server 根目录算成了 `src/`（少一层），于是：

- `.env` 找不到 → 静默 return，从未真正加载；
- `routing.yaml` 只能靠兜底候选命中 → 进程**必须从 `backend/server` 启动**，换目录就 `FileNotFoundError`。

三处降级都是静默的（缺 `.env` 不报错、缺 prompt 得空串、缺 skill 目录得空列表），所以没有任何测试变红。
**更关键的是，它让两个测试因为错误的原因通过**：那两个用例 `delenv("JC_LLM_API_KEY")` 来断言「这个端点没配，必须记成 skipped」，
而真实的 `.env` 从未被加载，所以断言在任何机器上都成立。把路径修对之后，它们立刻红了——因为开发者机器上确实配了网关。

两条由此而来的验收要求：

1. **测试不得读开发者的 `.env`。** `tests/conftest.py` 有 autouse fixture 置空 `ensure_dotenv_loaded`。
   否则「某 key 未配」这类断言的结果取决于跑测试的机器，CI 绿、本机红，两边都证明不了什么。
2. **「从任意目录启动」必须用 `chdir` 实测**，不能用读代码确认。`parents[]` 差一层在行里看不出来，
   所以 `paths.py` 在**导入时**就 assert 目录名，`test_paths.py` 再在 `tmp_path` 下重新加载 router 与 skills。

两次变异都被抓到：把 `SERVER_ROOT` 改成 `parents[1]`（在 collect 阶段就炸），以及在某个 service 里恢复手算路径
（被 `test_layout_knowledge_is_not_recomputed_outside_paths_module` 点名）。

### 聊天附件：两个测试环境看不见的缺陷

`tests/test_agent_attachments.py` 盯住图片/语音的两类回归，它们都不是"代码写错了"那种缺陷，
而是**测试结构上看不见**的那种，所以断言方式要专门说一下。

**第一，列容量测不出来，只能断言字符串。** 附件的 base64 曾整段写进
`jc_agent_message.payload_json`，而该列是 MySQL `TEXT`（65,535 字节）——
一张摄像头照片超限 6 倍，手机相册照片超 40 倍，上线必炸。
测试全绿的原因是**测试跑 SQLite，其 `TEXT` 无长度限制**。
这和路径那个缺陷是同一类：测试环境与生产的差异，测试看不见。
所以这里不去期待数据库报错，而是把 payload 按 `AgentMessageStore.append` 的方式序列化，
直接断言 `"data:" not in serialized` 且字节数 < 65,535。

**第二，不幂等的函数要盯调用点，不是盯行为。**
`flatten_message_for_text_agent` 把 OCR 文本追加进消息，再跑一次就二次调用 vision
并追加第二份。`AgentService` flatten 过之后又把原始 attachments 传给了 harness，
于是每张图被 OCR 两次、转写在 prompt 里出现两份——vision 费用直接翻倍，而没有任何断言
在数调用次数。修法是在 `AgentService` 侧不传 `attachments`；
回归用 **AST 断言那个调用点没有 `attachments=` 关键字**。
行为测试要看到这件事就得把整个 harness 架起来，而缺陷只是一个 kwarg。

配套：前端 `lib/attachment-limits.ts` 的常量必须与 `agent_attachment_service` 成对维护
（前端是提前提示，服务端是权威），新增的 `attachment_too_large` / `attachment_rejected`
两个 code 必须在 `lib/api/user-error.ts` 有文案，否则 `scripts/verify_error_copy.py` 会红。

**第三，语音的「存好了」不等于「还有用」。** 本版本服务端没有 STT，
识别在浏览器做，所以 `transcript` 是这段录音**唯一可读的形式**。
由此有四条独立的回归，分别对应四种各自会静默发生的损坏：

| 断言 | 不写会怎样 |
|---|---|
| offload 后的行里有 `transcript` / `duration_ms` | TOS 里一堆音频，表里只有文件名：搜不到、读不了、引用不了 |
| 同一句话在 prompt 里只出现一次 | 听写本来就把文字打进了输入框，再追加一次等于用户重复了一遍，语音链路 token 翻倍 |
| 输入框被改写后仍带上原话 | 用户听写完又清空/改写，录音成了唯一记录，这时**必须**补 |
| 没识别出文字时模型被明确告知读不了 | 早期静默丢掉，结果 agent 在回答一条它根本没收到的消息 |

还有两条是**前端契约**，但项目里没有 JS 测试 runner，所以用 Python 读源码断言
（`PROJECT_ROOT` 可直达前端文件）：气泡筛选音频时**不能**以「有可播放地址」为条件
（上传失败时文字还在，按地址筛会让用户自己发的消息凭空消失）；
composer 必须用独立的 `dictatedRef` 累积本次录音的文字，
**不能在发送时读输入框**（框里可能本来就有打好的字，且事后还能改，读它会把错的话绑到录音上）。
这类「读源码断言」看着粗糙，但缺陷正好就是一行筛选条件和一个取值位置，
行为测试要覆盖它得先有浏览器。

### 身份传递与并发（原「全进程串行」事故已修复，见 ADR-004）

曾经的 `_HARNESS_RUN_LOCK` 把跨用户对话全部串行化，因为身份走 `os.environ` 而 MCP
连接池是进程全局的。现已改为身份随每次调用显式传递（`authz_attributes` → MCP
`identity_interceptor` 覆写），**跨用户不再排队，锁与相关测试已删除**
（`tests/test_harness_queue.py` 不再存在）。

唯一仍存在的排队是同一用户同一会话内的 followup / steer（`useAgentSession` 的两个
前端队列），这是**正确行为**：防止两轮并行互相覆盖同一份档案，与并发容量无关。

验收时要确认的是身份隔离，不是排队提示：**两个不同用户同时发消息，各自的回复、
工具调用结果、档案读写必须互不可见、互不影响**；用两个浏览器/两个账号同时操作验证。

### 建档入口：后端通了不等于用户能用

`from-text` 端点连同 12 个测试先上线，**前端没有入口**——一个绿色测试套件完全看不见的缺口。
所以 `test_profile_text_ingest.py` 末尾有两条断言读前端源码：客户端函数确实调了
`/profiles/from-text`，且表单的字数下限与服务端 `_MIN_TEXT_CHARS` 相同。
后者防的是「表单收 40 字、提交后被拒」这种纯粹浪费用户时间的不一致。

同一处还断言「从零建档」给的是**两个**选择。原先只有一个按钮写着「用对话建一份简历」，
点下去打开的是结构化问答**表单**：承诺了对话，交付了表单。两种能力都真实存在，
所以正确的修法是分成两个入口，而不是改个措辞。

### 导出门禁：质检只告知，不扣住文件

`downloadable` 由四处 state 合成，而这里的回归是**静默**的——一个禁用的下载按钮看起来像是
深思熟虑的决定，不像故障。所以三种处境各有一个真机 case：

| case | 断言 |
|---|---|
| 读到发现（`status: failed`） | 发现**必须先被看见**（此时按钮锁，否则提示来不及读到就没意义）；点「我已了解，仍要下载」后**三种格式全部可用**；文案不出现「必须修改」 |
| 没有结论（`status: unavailable`） | 结论落地后下载**必须可用**；出现「这次没有完成检查，不影响下载」；**不出现**「建议先确认」「必须修改」「有问题需要先处理」，也不泄漏 `RuntimeError` 等内部诊断 |
| 请求一直不返回 | 转圈时「不等了，直接下载」可见可点，点后立即解锁；**迟到的结果不会重新锁住**已放行的下载 |

第二个 case 的顺序是刻意的：先等「没有结论」这个结论呈现，再断言按钮可用。在结论到达之前
页面处于「检查进行中」，那是第三个 case 的事；混在一起测会得到一个随网络时序闪烁的断言。

三态契约与「为什么审稿不再是门禁」见
[`TECH-RESUME-WRITING.md`](../architecture/TECH-RESUME-WRITING.md) §6.3.1。

### 失败文案是发布门禁

一位用户报「登录和发密码都报错」，表单上写着「请求失败」。那四个字是**响应体读不出来**时的
兜底——而我们的 API 永远回 `{code, message}`，所以读不出来只意味着请求压根没到后端
（rewrite 没生效、前面有代理、网关页）。于是唯一不说明原因的那句话，恰好只在用户最无法
自行判断的处境下出现。他反复重输了一个从来没错过的密码。

同一个故障还有另一半：服务端的 `message` 当时是写给日志看的英文串
（`Invalid email or password`）。`looksTechnical` 放行它们——散文里没有 URL、没有栈帧、
没有状态码——所以它们原样出现在中文表单上。

两个缺陷都是**静默**的：错误框里有字，看起来就像在正常工作。断言因此必须落在
「用户实际读到的那行字」上，而不是「有没有报错」：

| 处境 | 必须读到 | 不得读到 |
|---|---|---|
| 凭据被拒（401 + `invalid_credentials`）| 说明是邮箱或密码的问题 | 任何英文串；任何基本不含中文的长句 |
| 无 `code` 的英文 `message` | 中文文案 | 服务端原文 |
| 请求没到达（响应不是我们的信封）| 说明没连上服务、给出下一步 | 「请求失败」；任何怪到用户凭据上的说法；调用方的域兜底（如「登录失败」）|
| 5xx 且无响应体 | 说明是我们的服务 | 与「没连上」同一句话 |
| 重置邮件发送成功 | 成功样式 + 有效期 + 可重发 | 任何错误框 |
| 重置邮件发送失败 | 错误样式 + 原因 | 「已发送，请查收」之类的成功文案 |

两个层次各有分工：`code → 文案` 映射是可靠层（不依赖服务端措辞），`looksForeign` 是兜底层
（覆盖我们还没编目的端点）。**两者都要留**：映射里的文案能比抛异常处写的句子更具体地说清下一步。

这条门禁有过一个**它自己看不见的漏洞**，值得记下来：它只扫 `raise ...code="x"`，
而异常处理器是把 code 直接写进响应体的（`JSONResponse(content={"code": "invalid_upload"...})`）。
于是 `invalid_upload` 在前端没有任何文案的情况下，门禁一直是 PASS。
现在脚本额外扫 `content={... "code": "..."}`，并且对这类 code **要求必须有映射条目**
（而不是「中文原文或映射二选一」）——因为处理器转发的是异常自带的 message，
语言不受控，映射是唯一可保证的那一层。

匹配刻意锚定在 `content=` 上：裸 `"code"` 还被另外两个与 HTTP 错误无关的命名空间使用——
审稿发现（`issues=[{"code": "llm_disabled"}]`，由审稿 UI 自行措辞）与
MCP 工具结果（`{"code": "review_required"}`，收件人是模型而不是人）。
把它们拖进用户文案映射会逼出一堆没人会读到的条目。

`invalid_upload` 的处理方式本身也是个样例：它被列入前端 `CODE_PREFERS_SERVER_MESSAGE`，
优先展示服务端原文。一个 code 覆盖了类型不支持 / 文件过大 / 内容过短三种原因，
而区别正是用户唯一需要的信息；固定文案只能含糊到三者都适用。
但「优先」不等于「无条件」——上传校验仍会对不支持的扩展名抛英文，
所以仍要过 `looksTechnical` / `looksForeign`，不合格就回落到映射文案。
两条断言都在 `scripts/lib/error-copy-checks.mjs` 里。

还有一条**结构性**门禁，它防的是以后再漏：脚本扫出后端所有带 `code` 的 `raise`，
要求每一处**要么**在前端映射里有条目，**要么**抛错处本身就是中文。两者缺一不可的写法反而是错的——
`fetch_too_large` 在静态页是 500KB、在动态页是另一个上限，压成一条映射会丢掉用户需要的那个数字。
两道都没有的话请求会落到 `statusFallback`（404 得到「请求的内容不存在。」），既没说原因也没给下一步。

这条门禁上线时立刻找出 33 处英文 `message`（`Profile not found`、`Draft not found`、
`Question not found` 之类），其中 28 处连 `code` 都没有，用户看到的就是上面那句泛化兜底。
现在它们都有了具体中文与稳定 `code`。两个 admin 接口刻意保留英文并在脚本里显式豁免——
那是运维面，读它的人是持 token 的人，不是正在做事的用户。

顺带修掉一处状态码错用：`POST /jobs/fit` 缺少 `job_id` 与 `raw_jd` 时抛的是 404，
于是用户被告知「请求的内容不存在」，会去找一个他从没指定过的职位。那不是找不到，是参数缺失。

`message` 现在是给用户看的中文，`code` 仍是稳定契约——详见
[`TECH-API.md`](../architecture/TECH-API.md)。`forgot-password` 在 SMTP 未配置时不再静默
返回成功（那会让用户永远等一封发不出的邮件）；账号不存在仍静默返回，这是防邮箱枚举，
两者的区别在 `request_password_reset` 的 docstring 里写明了。

### LLM 审计日志

每次模型调用现在都落一行 `jc_llm_call`，故障链里的每一跳落一行 `jc_llm_call_attempt`。
失败转移本身由进程内的 `litellm.Router` 执行，审计是旁观者：**成功由调用方在返回后显式上报，
失败走 litellm 的回调**。时序原因、表结构与开关见
[`TECH-LLM.md`](../architecture/TECH-LLM.md) §4.1。这里只说验收时容易看错的几件事。

**第一，「用了哪个模型」必须是真实生效的那个。** 这是用户提这张表的原始动机。
故障链配了三个端点，前两个挂掉、第三个成功时，`final_model` 必须是第三个。
写成 `chain[0].model` 的版本在所有「首选就成功」的用例下都通过——而那恰好是绝大多数用例。
所以这条断言必须用「前面的跳故意失败」的夹具，不能靠正常路径。

**第二，HTTP 200 不等于成功。** JC 的失败定义比网关宽：`response_validator` 不通过
（返回了 200 但 JSON 用不了，也就是用户见过的 `Expecting value: line 1 column 1`）
在 JC 里算失败并继续故障转移。`attempt.validator_failed` 就是为了把这两类分开记：

| `validator_failed` | 含义 | 运维该做什么 |
|---|---|---|
| `true` | 网关通了，模型守不住输出格式 | 调 prompt 或换模型，别查网络 |
| `false` | 请求压根没成功（超时、鉴权、解析不到域名） | 查网关与凭据，别改 prompt |

缺 API key 的跳记为 `status="skipped"` + `error_code="missing_api_key"`，不占失败率——
那是部署没配好，不是模型不行。

**第三，日志故障不能影响用户的请求。** `record_call()` 自开短 session 并吞掉所有异常
（只留 warning）。审计表写不进去的时候，用户的简历必须照样生成完。把那个 `except` 改成
`raise` 的变异如期失败。

**第四，两个端点的故障链测不出 fallback 配错。** litellm 的 fallback 必须写成扁平的
`[{s-0: [s-1, s-2]}]`；写成嵌套的 `[{a: [b, c]}, {b: [c]}]` 时**最后一跳会被调用两次**
（实测调用签名 `a, b, c, c`）。但两端点的夹具下这两种写法的可观察行为完全一致，
所以审计行数与「每跳只试一次」这条必须用**三端点**的链来断言。

**第五，有两类缺陷「全套测试通过」并不能排除。** 本轮 9 次变异里有 2 次原本无人察觉：
去掉「迟到的失败事件不得覆盖已记录的成功」那层守卫，以及删掉
`JCChatLiteLLM._astream` 让 LangChain 用同步实现派生异步流。后者的真实后果不是
「流变成一个 chunk」，而是同步路径被跑在 worker 线程上、审计行从 sink 离开而不落库——
异步调用方没装 sink，**行被静默丢弃**。两处都已补测试，重新施加变异后被抓到。
验收这块时请以「变异能否被抓到」为准，不要以通过数为准。

两条关于正文的验收项：`JC_LLM_LOG_PAYLOAD=false` 时三列正文必须为空而指标仍在；
管理端详情接口默认**不返回**正文，必须显式 `include_payload=true`。
这是「记录全面」与「日志不落简历正文」之间的那个取舍点——
生产要不要开这个开关属于发布前决策，见下文门禁 6。

跑测试注意：`test_export_pdf.py`、`test_export_quality.py` 与 `test_public_browser.py` 需要
Playwright Chromium。受限沙箱里它们会报 7 个失败——**这是环境限制，不是缺陷**，
这三个文件共 14 个用例，其中 7 个在无 Chromium 时失败、7 个通过；
在可启动 Chromium 的环境里 14 个全部通过。判断是否可发布必须在后者跑完整套件。

证据文件保存在 [`../evidence/acceptance/`](../evidence/acceptance/)；它们反映对应环境与夹具，不等价于真实生产依赖已验证。

## 2. V1 功能验收

| 闭环 | 必须通过 |
|---|---|
| 建档（上传） | 上传 PDF/DOCX/图片，解析为草稿，用户可编辑并确认 |
| 建档（粘贴） | 把简历原文或一段自述贴进输入框即可建档；走**与上传同一条**解析/进度/确认流程；低于 80 字被拒且提示说清该写什么（公司、时间、做的事）而不只说「太短」 |
| 建档（对话） | 空档案/多年未更新可通过访谈补齐；进度跨刷新恢复；**问得完一定能生成** |
| 建档入口可达 | 四个入口在空态页面上**都能看见**：上传、粘贴、和舟卡聊着写、按问题逐项填写；后两个是两个独立按钮（不是一个按钮打开表单）；选「聊着写」后舟卡**主动开口**提第一个问题，不是把空输入框丢给用户 |
| 建档写入可核对 | 写入回显给出中文字段名 + 存下的原文，界面上**不出现点路径**；答过的问题可回看与修改，重答为替换而非新增 |
| 简历 | 已确认档案可优化、展示变更、审稿、导出 HTML/PDF/DOCX |
| 写作偏好 | 岗位族与包装角度可切换且立即重新生成；角度不新增事实、不放宽审稿门禁 |
| 覆盖度 | 源档案被漏掉的要点在第 3、4 步均被点名；一律建议不阻断导出 |
| 事实不变量 | 无源数字与动词升级在导出前质检中被点名（`warning`）；审稿已报过的同一要点不重复呈现 |
| 导出永不被质检拦住 | 质检失败、没跑起来、一直不返回，三种情况下用户**都能下载**；有发现时需确认一次（「我已了解，仍要下载」）；「没有结论」不呈现为简历的问题，也不泄漏内部诊断 |
| 文档级重组 | 范围句、结论先行摘要、段首最强证据、节序调整在预览与导出中**一致可见**；重组不改任何一句话 |
| 岗位 blueprint | 6 项检查结果与「这类岗位怎么写」对用户可见；未达项一律 `warning` 不阻断；`general` 显式提示未识别 |
| 指标候选项 | 缺成果类问题下给出可点击的指标句式；点击**追加**到输入框并把光标落在留空处；**句式中不含任何数值**；非数值类问题（如 `weak_ownership`）不出现句式 |
| 舟卡可收起 | 收起后文档变宽 ≥ 300px、条宽 ≤ 48px；**运行中收起不丢流**，回复仍到达且重新展开后在线程里；收起期间到达的回复在条上计数，读过清零；收起状态跨刷新保留 |
| 第 3 步版面 | 两列各自滚动、无祖先 scroller、堆叠态只有一个滚动条；左栏问题获得焦点时右侧对应要点滚入视野并高亮；左栏字号 ≤ 3 档 |
| 覆盖度文案 | 提示给出**缺失条数**与被漏原文摘录（标点处回退截断 + `…`），并说明「重新生成」与「可以不管」两个分支 |
| JD | 粘贴 JD 或受限公开读取，保留来源，生成匹配/差距分析且不阻断导出 |
| 面试 | warmup/target 规则正确；答案、反馈、最佳答案、真实题归档可保存与检索 |
| 账户 | 注册、登录、登出、个人配置、链接/4 位码邮箱验证、密码重置/修改与 cookie 生命周期正确；**失败提示为中文且可操作**——不泄漏内部英文串，「请求没到达」与「凭据被拒」说法不同，重置邮件的成功与失败不共用一个提示框 |
| LLM 审计 | 每次调用都入库；`final_model` 是**真实生效**的模型而非配置首选；格式不合规与网关失败在 `validator_failed` 上可区分；缺 key 记为 `skipped`；日志写失败不影响用户请求；`JC_LLM_LOG_PAYLOAD=false` 时不落正文 |
| Agent | 会话、SSE、skill、`jc_*` 工具、取消与重启恢复在真实依赖环境可用 |
| 语音留档 | 发一条语音后：气泡里**既有播放器也有文字**；**刷新页面**后两者都还在（录音按 `storage_key` 重签）；TOS 的 `jc/<env>/agent/<sid>/attachments/` 下能看到对应对象；同一句话在气泡里只出现一遍，不是说了两次 |
| 语音降级 | Safari（无 `SpeechRecognition`）里麦克风按钮**可见但禁用**且 tooltip 说清换 Chrome/Edge 或直接打字——**不能直接消失**；录了音但一个字没识别出来时，舟卡应说自己读不了这段录音并请用户打字，**不能假装听见了** |
| 并发隔离 | 两个浏览器用不同账号同时发消息，必须互不等待、各自立即开始处理；一方的回复、工具结果、档案读写对另一方不可见；取消一方的对话不影响另一方 |
| 隔离 | 跨用户档案、职位、会话、导出物、题库访问全部拒绝 |

## 3. 发布前未关闭门禁

1. **真实依赖端到端**：MySQL、Redis、LLM、DeerFlow、TOS、邮件与 API/Agent 的完整 E2E。
   其中**写作语义**这一项已经有了可执行的验收手段：`scripts/evaluate_writing.py`
   用真实档案与真实模型断言「换角度真的换讲法」「任何角度都不新增无源事实」
   「`ownership` 角度下审稿仍阻断动词升级」，并输出覆盖度阈值在真实输出上的误报分布。
   脚本已就位且其判定逻辑有单测（`tests/test_evaluate_writing_script.py`），
   **但尚未在可访问 LLM 网关的环境跑过**——当前开发沙箱解析不到网关域名。
   跑法：`python scripts/evaluate_writing.py <真实简历> --job-title "<目标岗位>" --verbose`，
   报告落在 `docs/evidence/writing-evaluation.json`。这条在报告产出前不得视为关闭。
2. **动态浏览器运行验收**：真实部署环境的 UI、Agent 流式回复、异常恢复、受限 JD 读取。
   跑法：先起生产构建（`cd frontend/web && npm run build && npm start`）与 API，
   再 `./scripts/v1_acceptance.sh --skip-export --skip-concurrency`，
   或单独跑其中任一 `verify_*.py --base http://127.0.0.1:3000`（见 `scripts/README.md`）。
3. **文档解析评测**：文本 PDF、Word/表格 Word、扫描件/OCR 的代表样本、失败样本和质量阈值；同时验证 Route A → MarkItDown Route B → Vision 的触发顺序、输入/输出上限、超时和来源记录。
   `scripts/evaluate_documents.py`（已在 `test-local.sh` 跑）用的是程序合成样本，
   只验证解析路径走没走对；**真实文件质量**需手跑
   `python scripts/evaluate_writing.py <真实简历文件> --job-title "<目标岗位>" --verbose`，
   对文本 PDF、扫描件 PDF、表格 Word 以及至少一个故意损坏/空白的文件各跑一次，
   确认失败时是明确报错而不是静默退化成 `mock_fallback`。
4. **导出质量与回归**：中文/英文/双语、分页、字体、链接、下载、对象存储、失败可见性与新增功能全量回归。
   跑法：`python scripts/verify_export_regression.py --base http://127.0.0.1:8000/api/v1`
   （需要 `JC_E2E_EMAIL`/`JC_E2E_PASSWORD`）；遍历 pdf/docx/html × zh-CN/en-US/zh-en
   九种组合，真实下载后检查 PDF 页数与字体嵌入、PDF/DOCX/HTML 的超链接目标、下载体非空。
5. **可靠性与安全**：并发隔离、取消、服务重启恢复、限流/容量、日志告警、备份和回滚演练。
   并发隔离 + 取消 + 重启恢复的端到端脚本：`scripts/verify_concurrency_resilience.py`
   （见下一条，同一个脚本覆盖）。限流/容量、日志告警、备份回滚演练仍无自动化脚本，
   需人工走一遍部署文档里的对应步骤。
6. **并发实测**：身份传递已改为显式参数（ADR-004），不再有跨用户进程锁，
   理论并发不再受制于「整轮对话串行」。验证脚本：
   `python scripts/verify_concurrency_resilience.py --base http://127.0.0.1:8000/api/v1 --users 30`，
   N 个并发会话同时发消息，用「单独跑的延迟」与「并发下的延迟」比值判断是否仍有串行化；
   同一脚本还覆盖「取消一个会话的对话不影响该会话后续消息」，
   加 `--with-restart` 则在中途暂停等你手动重启 API 进程，确认会话历史与后续消息在重启后仍可用。
   若比值异常升高，先查数据库连接池或 LiteLLM 网关侧瓶颈，而不是怀疑 agent harness 本身。
7. **LLM 审计日志的生产策略**：已决定，取中间档——生产 `JC_LLM_LOG_PAYLOAD=true`，
   正文保留 14 天，整行保留 90 天，由 `scripts/prune_llm_log.sh` 按 cron 强制执行。

   理由：关掉正文等于放弃「这份简历当时模型到底回了什么」的追溯能力，而本项目至今最严重
   的一类问题（简历改不动、写手冒领数字）只能靠读当时的 prompt 与回复定位——没有正文，
   复盘就是猜。永久保留同样不可接受：审计表里存的是用户简历里的真实个人信息。14 天覆盖
   「用户投诉某次改写」到「工程读到那条记录」的现实间隔；90 天保留指标与失败码用于趋势。

   `JC_LLM_LOG_PAYLOAD=true` 只有在裁剪真的在跑时才站得住，所以这条的关闭条件是
   **cron 已配置并至少成功执行一次**，不是改完配置就算：

   ```cron
   17 4 * * *  cd /srv/jc && ./scripts/prune_llm_log.sh >> /var/log/jc/prune.log 2>&1
   ```

   窗口由 `.env` 的 `JC_LLM_LOG_RETENTION_DAYS=90` 与 `JC_LLM_LOG_PAYLOAD_DAYS=14`
   控制（后者是 `prune_llm_log.sh` 读的环境变量，默认 14）。脚本默认 `--apply`；
   先看效果用 `JC_PRUNE_DRY_RUN=1 ./scripts/prune_llm_log.sh`。

   剩余待办：`009_llm_call_log` 迁移需在真实 MySQL 上执行（`./scripts/db_upgrade.sh`，
   沙箱内连不上数据库），以及上面那条 cron 的落地。

任一门禁未关闭时，发布结论必须保持“候选版本”，不得表述为生产已上线。

## 4. 首批用户验收建议

选择覆盖研发、产品/运营、设计/市场等不同互联网知识岗位的首批用户。每位用户至少完成一次：上传 → 核对确认 → 目标 JD → 简历导出 → 模拟面试 → 真实题/复盘记录。收集任务完成率、耗时、失败点、导出可用性、建议可信度和是否愿意再次使用。

## 5. 验收记录原则

- 每项写明环境、版本、时间、输入、预期、实际结果和证据位置；
- “跳过”必须说明所缺凭据/环境，不能写成通过；
- 外部服务、浏览器、模型结果与静态单元测试分别记录；
- 新增功能合入前更新本文件的门禁影响和回归范围。
