# 实现计划（给 Cursor 执行）

日期：2026-11-09。读者：负责写代码的 Cursor（或任何 AI 编码代理）。

这份文件是**执行说明**，不是设计。设计在 `docs/chat-agent-*.md`，每个任务都会指明要读哪一节。遇到设计没覆盖的地方，**停下来写进 `docs/implementation/open-questions.md`，不要自己发明**。

## 0. 全局规则（每个任务都必须遵守）

1. **设计是权威。** 实现与设计冲突时，以设计为准；如果你认为设计错了，写 open-question，不要悄悄偏离。
2. **只改 `companion-agent/` 与 `docs/implementation/`。** 不改 `testserverV`（Java，只读参考）、不改 `job-come`、不改 `libs/agentkit/vendor/deer-flow`。
3. **不提交（不 commit、不 push、不开 PR），除非用户明确说。** 每个任务结束时把改动留在工作区，并在任务报告里列出改了哪些文件。
4. **测试节奏：开发期间只写测试，不运行全量测试。** 用户的要求是"全部开发完，最后统一测试"。每个任务可以跑该任务新增的、最小范围的导入检查（`python -c "import …"`），其余测试留到 T13。
5. **边界靠 import-linter 守护（A §4.1）。** 每个任务结束前运行 `lint-imports`（若已配置）；不通过就不算完成。
6. **禁止行为**：domain 层 import fastapi/sqlalchemy/redis/httpx/os；把密钥写进仓库；在日志里打印用户消息原文或 token；用 `allow_all` 验证器跑非 dev 环境；在请求路径上做 LLM 调用之外的长耗时工作。
7. **每个任务的报告格式**（写到 `docs/implementation/reports/T<n>.md`）：做了什么 / 改了哪些文件 / 设计偏离（若有）/ open-questions 编号 / 下一任务的前置条件。

## 1. 任务顺序与依赖

```
T0 spikes ──► T1 包结构 ──► T2 持久化 ──┬─► T5 回合控制面 ──► T6 SSE 接口 ──┐
                                        ├─► T3 身份                          │
                                        ├─► T4 图与提示词 ──► T5              │
                                        ├─► T7 角色                          ├─► T13 端到端与全量测试
                                        ├─► T8 工具与确认 ───────────────────┤
                                        ├─► T9 记忆 ─────────────────────────┤
                                        ├─► T10 worker ──────────────────────┤
                                        └─► T11 解题与上传 ──────────────────┘
T12 Android 客户端：与 T6 并行（接口契约来自 D §7，不必等服务端实现）
```

T0 是门槛：它的结果决定 T4 的做法。**T0 不通过，不开始 T1。**

## 2. 任务

### T0 — 三项实测（门槛）

- **读**：P §2.5、§2.2；D §8.3。
- **做**：
  1. 在 `/tmp` 下建一个只含 `create_deerflow_agent` 的最小脚本，**不放任何 DeerFlow 配置文件**，用假 OpenAI 端点（本地 `httpx` 假服务即可）跑通一轮流式。记录是否读取了配置、报了什么错。
  2. 解决 `mcp` 版本问题：在独立 venv 里找出能导入 `deerflow` 的 `mcp` 版本，记录版本号。
  3. 记录 `graph.astream(..., stream_mode="messages")` 产出的每一种事件（文本块、工具调用块、结束块）的真实结构，附样例 JSON。
- **交付**：`docs/implementation/spike-results.md`，三项各一节，写清结论与证据（命令、输出片段）。
- **验收**：三项都有明确结论。若第 1 项需要最小配置，写出最小配置内容。
- **不做**：不写产品代码。

### T1 — 包结构迁移（A §3、§4.3、§7）

- **读**：A 全文。
- **做**：按 A §3 的目标结构建立 `domain/ ports/ app/ api/ adapters/ bootstrap/ products/`，按 A §4.3 的映射表搬迁现有模块；先搬 `domain`，再 `adapters`，最后拆 `server`。**每搬一批就跑 `lint-imports`**。
- **注意**：这一步只搬家、不改行为。搬完后现有接口的签名与返回值应保持不变。
- **交付**：`.importlinter` 配置（A §4.1 的契约）；迁移后的包；`docs/implementation/reports/T1.md` 里列出映射执行情况。
- **验收**：`lint-imports` 全绿；`python -c "import companion.api, companion.app, companion.domain, companion.adapters, companion.bootstrap"` 不报错。
- **已知越界**（A §4.3，必须修）：`middleware → actions/prompt`、`server → container/turn_pipeline`、`agent → container`、`persona_guard` 默认 `expected_script="cjk"` 检查的是输入（应按会话语言、检查回复）。

### T2 — 持久化（D §3、O §2.1）

- **读**：D §3 全部、O §2.1、§9（迁移策略）、§10（数据保留）。
- **做**：
  1. Alembic 初始迁移，建 D §3.1–3.4 与 O §2.1 的全部表，含索引与唯一约束。
  2. `ports/store.py` 定义 D §3 对应的端口（`SessionStore`、`MessageStore`、`TurnStore`、`QueueStore`、`RoleStore`、`ConfirmationStore`、`AgentJobStore`），接口见 A §2.1 的表。
  3. `adapters/store/mysql/` 实现它们。查询全部带 `owner_id` 过滤（用户隔离）。
  4. 状态转移用条件更新（`UPDATE … WHERE status=?`），返回受影响行数判断成功，不要先读后写。
- **交付**：迁移文件；端口；MySQL 实现；`docs/implementation/reports/T2.md`。
- **验收**：迁移在空库上 `alembic upgrade head` 成功；`alembic downgrade base` 成功（迁移可逆）。
- **禁止**：在 `domain` 里写 SQL。

### T3 — 身份（D §4）

- **读**：D §4；O §4.1（日志脱敏）。
- **做**：`adapters/auth/redis_token.py` 实现 `LoginTokenStore`：键格式校验（Base64 字母表 + 前缀 + 长度，见 D §4）；只解析 `id` 与 `level`；`pwd`、`pwdHash` 立即丢弃。`api/http/deps.py` 的 `current_user` 依赖只依赖这个端口。
- **验收**（写进 T13 的测试清单，本任务不跑）：非法键格式 401；合法键但 Redis 无此键 401；`pwd` 不出现在任何日志或异常文本中（用一个"哨兵字符串"测试）。
- **注意**：`AllowAllVerifier` 仅在 `COMPANION_ENV=dev` 可用，T3 要把它接到启动检查（A §5.5）。

### T4 — 图与提示词（P §2、§6；T §1；D §8.1）

- **读**：P §2.2–2.6、§6 全部；T §1；D §8.1。
- **做**：
  1. `adapters/brain/deerflow.py`：用 `create_deerflow_agent` 构造图，**只实现异步钩子**，`features` 按 P §2.2 表设置（沙箱关、记忆关、摘要关、子 agent 关、token_budget 开）。
  2. 中间件（图内，全部异步，锚点按 P §2.4 表）：`PromptMiddleware`、`ToolVisibilityMiddleware`（过滤掉 `ask_clarification`）、`SteerMiddleware`（只声明，T5 接线）、`ToolAuditMiddleware`、`ToolAuthorizationMiddleware`（只声明，T8 接线）。装配后断言最终顺序（P §2.4）。
  3. `domain/prompt/assemble.py`：纯函数，按 P §6.1 的分层与顺序组装；`domain/prompt/templates/` 放平台层与输出层模板，带 `PROMPT_VERSION`。
  4. `domain/history/window.py`：按回合分组的历史窗口（D §8.1、P §6.6）。
  5. 图片走多模态内容块（P §2.6）。
- **交付**：上述模块；`docs/implementation/reports/T4.md`。
- **验收**：`python -c "from companion.adapters.brain.deerflow import build_graph"` 能导入；按 T0 结论，在无配置文件环境下能构造图。
- **禁止**：图内中间件实现同步钩子；把提示词编译进图（P §2.4，图必须可缓存复用）。

### T5 — 回合控制面（D §6、A §5.1–5.3）

- **读**：D §6 全部；A §5.1–5.3。
- **做**：
  1. `domain/turn/`：`TurnPhase`（`pre_output` / `output` / `tool`）、disposition 判定规则（D §6.1 的四种）、队列状态转移表（D §3.3，非法转移拒绝）、`ControlMessage`。**纯逻辑，无 I/O。**
  2. `adapters/cache/redis/`：D §6.2 的全部键；判定与投递用 **Lua 脚本原子执行**（读 phase → 决定 → 写控制流或队列）。
  3. 回合控制协程：`XREAD BLOCK turn:{tid}:ctl`，分派 `merge`（中止模型调用、同一 turn_id 重跑，`restarts<2`）、`steer`（进收件箱）、`cancel`。
  4. `app/chat/submit.py`：幂等 → safety → 落库 → Lua 判定 → `started` 时取锁启动回合；取锁失败则回到判定（D §6.1、A §5.1 第 5 步）。
  5. `app/chat/drain.py`：一批最多 10 条；失败回到 `queued` 并 `drain_attempts+1`；3 次后 `failed`（D §6.5）。
  6. 锁：`SET NX PX 30000`，每 10 秒续租（D §6.2）。
- **交付**：上述模块；`docs/implementation/reports/T5.md`。
- **验收**：本任务不跑测试；用 `python -c` 确认 Lua 脚本能被 Redis 加载（需要本地 Redis，若没有就在报告里写明"待 T13 验证"）。
- **禁止**：在任何判定路径上使用进程内对象代替 Redis 状态（D §6.2 的核心约束）。

### T6 — SSE 接口与事件（D §7）

- **读**：D §7 全部；A §5.4；P §3.5（停机）。
- **做**：
  1. `api/sse/encoder.py`：事件编码（`id:` 用 Redis Stream id，`event:`，`data:` JSON）；`: keepalive` 每 15 秒。
  2. `api/sse/stream.py`：`GET /sessions/{id}/events`，首连发 `turn.snapshot`（若有运行中回合），`Last-Event-ID` 续传，超出缓冲发 `gone`。
  3. 增量合并：`message.delta` 每 50 毫秒或 64 字符写一次（D §7.3）。
  4. 停机：`companion/__main__.py` 用编程方式启动 uvicorn，子类覆盖 `handle_exit`，按 P §3.5 的 6 步执行（draining 标记 → `reconnect` 事件 → 新发送返回 503 → 回合收尾 45 秒 → 父类 handle_exit）。
  5. 其余 REST 端点按 D §7.1 唯一列表实现（包括 `/queue` 撤回、`/retry`、`/continue`、`/me`）。
- **交付**：上述模块；`docs/implementation/reports/T6.md`。
- **验收**：`python -c "from companion.api.http.app import create_app"` 可导入；本任务不跑测试。
- **注意**：客户端只认 D §7.2 表中的事件；未知事件的处理是客户端的责任（D §7.4）。

### T7 — 角色与语言（P §4、§5；D §5）

- **读**：P §4.1–4.5；D §5、§3.2。
- **做**：
  1. 把 `catalog.json` 与 `catalog-zh.json` 复制进 `roles/catalog/`，连同 `NOTICE`。
  2. `domain/roles/`：`Role` 模型（P §4.3）、`RoleTraits`、`RoleId` 命名空间校验（系统 id 不得以 `u_` 开头，启动时校验）。
  3. 内置人设拆分为 `roles/builtin/*.yaml`（P §4.4），`builtin-ava` 为默认角色。
  4. `app/chat/roles.py` + `api/http/routers/roles.py`：D §5.3 的接口；用户角色私有，别人的 id 404。
  5. 语言协商（D §5.2）：`Accept-Language` 与 `locale` 参数，`dir` 字段。
- **交付**：上述模块；`docs/implementation/reports/T7.md`。
- **验收**：启动时加载目录，id 冲突或命名空间违规拒绝启动（`python -c` 验证一次）。
- **注意**：阿拉伯语展示字段暂用英文占位，标记 `"machine_translated": true`，**不要编造翻译**——翻译由人工或独立工具产出（见 open-questions）。

### T8 — 工具、授权、确认（T §2、§3）

- **读**：T §2 全部、T §3（MCP 只做接入层，不接外部 server）。
- **做**：
  1. `domain/tools/spec.py`：`ToolSpec`、`Permission`、`SideEffect`，构造期校验（T §2.1 表格的四条规则）。
  2. `domain/tools/registry.py`：按产品与白名单过滤。
  3. `app/tools/*.py`：T §2.6 的首批工具。身份从 `ToolContext` 注入，参数模型不含身份字段（注册时校验）。
  4. `ToolAuthorizationMiddleware` 接线（T §2.3 流程）；`ToolAuditMiddleware` 写 `tool_call` 表，参数存指纹。
  5. 确认闭环（T §2.4）：`POST /actions/{id}/confirm`、`GET /actions/pending`，确认后用快照参数执行，**不再调用模型**，写 `kind='action'` 消息。
  6. MCP 接入层（T §3）：`McpServerSpec`、白名单默认拒绝、禁用模式双重过滤、熔断。**不接任何真实外部 server**。
- **交付**：上述模块；`docs/implementation/reports/T8.md`。
- **验收**：构造期校验的每条规则都能用一个 `python -c` 语句触发拒绝。
- **禁止**：模型参数里的 `user_id` 被采信；CONFIRM 工具在确认前执行。

### T9 — 记忆（D §10、P §6.5）

- **读**：D §10 全部。
- **做**：
  1. `memory_hub/`（独立包，两个应用都会用）：`MemoryHub.from_config`、`for_app(app)`，隔离字段为复合 `app:uid`（D §10.1）。
  2. mem0 后端：演进自现有 `memory/mem0.py`（D §10.3 的说明），不要重写。
  3. Qdrant 每应用一个 collection 与一个令牌（D §10.7）。
  4. `api/http/routers/memory.py`：D §7.1 的记忆端点。
  5. 召回中间件 `memory_recall` 在回合外链执行（T §1）。
- **交付**：上述模块；`docs/implementation/reports/T9.md`。
- **注意**：`agent_id` 只记录来源，**召回不按它过滤**（D §10.5）。
- **验收**：`python -c "from memory_hub import MemoryHub"` 可导入；隔离测试留到 T13（需要真实 Qdrant）。

### T10 — worker 与后台任务（O §1–2、§3）

- **读**：O §1、§2 全部、§3。
- **做**：
  1. `companion/worker.py`：独立进程入口，循环认领 `agent_job`（`FOR UPDATE SKIP LOCKED`，租约 5 分钟，每分钟续租）。
  2. 任务实现（O §2.2 表）：`memory.extract`、`session.title`、`turn.sweep`、`queue.drain_orphans`、`confirmation.expire`、`account.purge`、`account.reconcile`、`upload.gc`、`softdelete.purge`、`audit.trim`。
  3. 每个任务写明幂等手段（O §2.2），重复执行结果不变。
  4. 重试：指数退避 1、4、16 分钟；超过次数置 `dead`。
  5. `account.reconcile` 超过阈值（默认 100）暂停并报警，不自动执行（O §3）。
- **交付**：上述模块；`docs/implementation/reports/T10.md`。
- **验收**：`python -c "import companion.worker"` 可导入。
- **禁止**：在 API 进程里启动后台任务循环（P §3.1 的进程模型）。

### T11 — 解题与上传（D §9、O §5、P §2.6）

- **读**：D §9；O §5；P §5.5（`problem-solving` skill 的定义）。
- **做**：
  1. `skills/public/problem-solving/`：SKILL.md 按 P §5.2 格式；`steerable: false`；`model_scenario: solve_text`，有图片时切 `solve_vision`。
  2. `POST /uploads`：按文件头判类型、≤ 8 MB、解码后重新编码为 JPEG（质量 85）、去 EXIF、长边 2048（O §5）。OSS 私有桶，签名 URL 5 分钟。
  3. `step` 事件（D §7.2）：解题过程中由 skill 产出，步骤结构存进 `chat_message.meta`。
- **交付**：上述模块；`docs/implementation/reports/T11.md`。
- **验收**：本任务不跑测试。
- **注意**：解题图片的 EXIF 去除是**隐私要求**，不是可选优化（O §5 的理由）。

### T12 — Android 客户端（C 全文）

- **在独立仓库工作**：`/Users/gqli/work/myandroidTest/.claude/worktrees/weifu-refactor`（分支 `weifu-refactor`）。**本任务不改服务端代码。**
- **读**：C 全文；D §7（接口契约）。
- **做**：按 C §2 的分层新增 `AgentChatRepository` 与 data 层实现；`AgentEventSource` 手写 SSE 解析（不引库，C §2.2）；`reduce(state, event)` 纯函数（C §2.3）；界面按 C §3；RTL 按 C §5；离线缓存按 C §9。**旧的 `ChatRepository` 保留，不删除。**
- **交付**：代码 + `docs/implementation/reports/T12.md`。
- **验收**：本任务不跑单元测试（同规则 4）；`./gradlew :app:compileChatDebugKotlin` 通过即可。
- **注意**：用户 Android 工作区里已有未提交的改动（`build.gradle` 等）。**不要 `git stash`、不要 `git checkout .`**；只在自己的文件里改。

### T13 — 端到端与全量测试（D §14）

- **这是唯一运行全量测试的任务。**
- **做**：
  1. 按 D §14 的测试策略补齐所有测试（T0–T12 中跳过的 `pytest`）。
  2. 启动 docker compose：MySQL、Redis、Qdrant、假 OpenAI 端点、agent-api、agent-worker。
  3. 运行端到端脚本：建会话 → 连发 3 条 → 断开重连 → 解题 → 确认工具 → 删记忆 → 注销（D §14 最后一条）。
  4. 运行 Android 单元测试与构建。
- **交付**：测试报告 `docs/implementation/reports/T13.md`，**逐条列出通过与失败**。失败不得略过；无法修复的写进 open-questions。
- **验收**：全部 import-linter 契约通过；全量 pytest 通过；端到端脚本通过；Android 测试与 `assembleChatDebug` 通过。

## 3. open-questions

实现中遇到设计没覆盖或设计有误的地方，记在 `docs/implementation/open-questions.md`：

```
### Q-001 <标题>
- 任务：T<n>
- 问题：<设计哪一节、缺什么或哪里矛盾>
- 我的假设：<如果需要继续，你做了什么假设>
- 需要的决定：<谁来决定>
```

## 4. 分派建议

- 一次只给 Cursor 一个任务，按第 1 节的顺序。
- 每个任务的开头粘贴：`请先阅读 docs/implementation/IMPLEMENTATION-PLAN.md 的第 0 节和本任务 T<n> 的内容，然后只做 T<n>。`
- 任务报告没写完，不开始下一个。
- T0 的结论出来后，再让我看 `spike-results.md`，我据此调整 T4 之前的任务。
