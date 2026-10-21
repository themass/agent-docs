# TECH-AGENT：DeerFlow、Prompt、Skill 与 MCP

- **状态**：已确认的 V1 Agent 边界
- **最后更新**：2026-10-17

## 1. V1 方案

V1 采用 **vendored DeerFlow 源码 + 非 editable 安装**。上游源码固定在：

```text
/Users/gqli/work/deepagents/libs/agentkit/vendor/deer-flow/
```

生产依赖通过 [`../../scripts/install-production.sh`](../../scripts/install-production.sh) 执行：

```bash
uv sync --frozen --no-dev --no-editable
```

这让生产构建使用锁定源代码，而不是漂移的远程包版本。业务服务在 `backend/server/`，配置与可审查 Agent 资产在 `backend/agent/`。

## 2. 资产布局

```text
backend/agent/
├── deerflow/       # config.yaml、product_rules.md、extensions config
├── skills/         # public/ 自研能力；custom/ 审核后引入的外部能力
├── prompts/        # ingest、elevate、coach、export 等非 Agent prompt
└── llm/            # routing.yaml（全项目唯一命名模型的地方）
```

`deerflow/config.yaml` 里 `models[].model:` 写的是 **scenario 名**（`coach` / `writer`），不是模型 slug；`use:` 绑定 `jc.llm.chat_litellm:ChatLiteLLMRouter`，链在调用时从 `routing.yaml` 读。该文件里**没有** `base_url` / `api_key` / 模型名——改模型请改 `routing.yaml`，否则就又会出现两份互相漂移的模型清单（曾经 `jc-writer` 指向 deepseek，而 `writer` 链头是 gpt，同名不同模型）。细节见 [`TECH-LLM.md`](TECH-LLM.md) 第 1 节。

原 `backend/agent/litellm/`（LiteLLM Proxy 配置）已删除：不起独立进程，failover 由进程内的 `litellm.Router` 承担。

DeerFlow 的运行态不写入项目根历史缓存，而写入：

```text
backend/server/.data/deerflow/runtime/
```

checkpoint 默认使用 SQLite（路径由 `JC_DEERFLOW_CHECKPOINT_*` 配置）；生产可根据并发与恢复需求评审专用持久化后端。

## 3. 权限与安全边界（不可放宽）

| 能力 | V1 策略 |
|---|---|
| 通用浏览器控制 | **不开放** |
| 通用网络访问 | **不开放** |
| 真实个人档案事实 patch | 模型不能自行确认；必须由用户一次性确认 |
| 数据库访问 | 不提供裸 SQL MCP；经业务服务和资源归属检查 |
| 文件访问 | 业务文件走 TOS/API；不向 Agent 暴露宿主机任意文件系统 |
| 外部 MCP | 默认关闭；按最小权限、白名单、审查和测试逐项启用 |

### 公开 JD 读取的例外

`jc_job_fetch` 是任务专用的受限工具，不是通用网络能力：仅允许白名单 skill 读取公开职位页；在请求前完成资源归属、DNS/IP/私网/重定向/体积/超时检查；禁止登录态、上传、点击、POST、任意请求头和任意方法。页面内容一律视为不可信输入，不能绕过档案确认规则。

## 4. 方法论如何到达模型（宿主组装，不靠模型读文件）

这一节记录一个必须知道的事实，否则很容易把方法论写进文件却以为它生效了。

**harness 只把 skill 的名称、描述与路径渲进 system prompt。** 正文（SKILL.md 的 body
与 `references/` 下的片段）要靠模型自己调 `read_file` 去取——上游称之为
Progressive Loading。而 JC 在 V1 刻意**不给 agent 宿主文件访问**（见第 3 节），
`backend/server/src/jc/adapters/deerflow_harness_client.py` 的工具白名单会把
`read_file` 与 `describe_skill` 一并剔除。

两件事叠起来的后果是：**SKILL.md 正文在 agent 路径上曾完全不可达**，模型一个字都读不到。

所以方法论改为**在宿主侧组装成 prompt 文本**，agent 仍然没有文件访问权：

```text
backend/server/src/jc/skills/
├── loader.py     读 skills/<scope>/<id>/SKILL.md 与 references/*.md，剥 frontmatter，缓存
└── composer.py   按层序拼成一份 system prompt，并记录用了哪些层（溯源）
```

层序从普适到具体，**只有第 4 层随岗位变化**：

| # | 层 | 内容 | 是否随岗位变 |
|---|---|---|---|
| 1 | `base` | SKILL.md 正文：身份、输出契约、硬禁令 | 否 |
| 2 | `method` | 任何一条经历怎么写（动作 + 对象 + 结果） | 否 |
| 3 | `structure` | 整篇怎么组织（结论先行、scope line、节序） | 否 |
| 4 | `family-<id>` | 这个族的读者看什么、哪些规则在这里放宽 | **是** |
| 5 | `qualitative-outcomes` | 仅当 `playbook.quantification_optional` 为真时加载 | 是 |
| 6 | playbook / blueprint | 该文档的可量化达标线 | 是 |

这样拆的理由：「一份 prompt 管所有岗位」会让律师的 prompt 把最强指令花在用不上的指标阶梯上；
「十六份 prompt」会把诚信规则复制十六份，一个月内必然漂移。**「永不编造事实」这条必须只存在一份**，
因此它写在共享层而不是每个族里，族片段可以改「找什么证据、用什么词汇、什么算具体」，
但不能改「什么算事实」。

配套约束：

- 缺 skill 时 `require_skill()` **抛 `LookupError`，不降级**。悄悄丢了方法论的 writer 仍会返回
  一份简历，用户只会收到一份莫名变差的文档；
- `playbook.quantification_optional` 是 writer 与 reviewer **共用的那一个信号**，
  不得再维护第二份「定性岗位」清单；
- `public/` 优先于 `custom/`：外部引入的 skill 不得顶替本产品行为所依据的那份；
- skill 内容是**第一方、随仓库发布**的，所以可以作为 system prompt 的可信输入
  （与 profile / JD 这类用户数据不同，后者一律按不可信处理）。

`_SKILL_SCOPE` 只决定**工具面**（哪个角色能调哪些 `jc_*`），不决定方法论可达性。
这两件事容易混为一谈，改动前请分清。

### 角色只能定义一次

`config.yaml` 把 JC 的角色声明为 DeerFlow subagent，而 harness 的 schema 要求每个
subagent 带一个 `system_prompt` 字符串。这个要求曾经直接导致同一个角色有两份定义：
`config.yaml` 里三行英文摘要，和 skill 包里 101 行的完整契约。两份不一致时，
**没有任何东西会失败**——这跟 `jc-writer` 指向 deepseek 而 `writer` 链头是 gpt 是同一类错误，
在同一个文件里，出于同一个原因。

所以现在存的是指针：

```yaml
subagents:
  custom_agents:
    resume-writer:
      system_prompt: skill:resume-writer
```

启动时 `deerflow_harness_client.resolve_subagent_prompts_in_config` 把它替换成
`jc.skills.composer.compose_role_baseline(skill_id)` 的结果，写到
`.data/deerflow/config.runtime.yaml`，再把 `DEER_FLOW_CONFIG_PATH` 指向那份。
指针指向不存在的 skill，或组装出空串，都**抛异常而不回退**——
静默回退意味着某个角色拿自己的 id 当指令运行，或者拿空 prompt 运行，而配置看起来是好的。

`compose_role_baseline` 只放**与读者无关**的那几层（skill 自身契约 + 始终加载的方法论）。
岗位族那一层是**按请求选的**（取决于用户的目标岗位），而启动时写的文件没有请求。
这是一条有意留下的接缝，不是遗漏：真正跑在线上的 elevate / review 路径走的是
`compose_writing_prompt`，它在请求内完成完整分层。管理端 inventory 会把指针解析回正文显示，
因为运维问的是「这个 agent 现在带着什么」，答案不该是一个指针。

### 对话建档：一段口述拆成多条要点

`profile-interview/references/method.md` 要求「用户一段话说了很多就当场拆开」。
这条指令此前对表单式访谈是**无法执行的**：一个 textarea 只能写进一个 `highlights[slot]`，
所以用户一口气说的五件事会变成一条 300 字的要点——最长、最难读，而且最强的四件被埋在第一件里面。

`services/intake_dictation.split_dictation` 补上这一半，并且**刻意不走模型**：
建档是 JC 唯一一条用户与档案之间没有模型的路径（见 `schemas/intake.py` 的信任分级）。
把这段话交给模型分段，会顺手改写措辞、合并它认为相似的两条、偶尔丢掉它觉得最无趣的那条，
而用户看着一份整齐的列表**无从察觉**。按用户自己写的标点和列表符号拆，
既不可能发明也不可能丢失，不变量是「拆分后内容字符与输入逐字相同」，由测试直接断言。

能拆错的只有边界位置，所以 `POST /profiles/{id}/intake-split` 是**只读预览**：
返回每段的文本、它将落入的空槽位、以及这个槽位的中文标签，由用户确认或改完再作为普通回答提交。
槽位从问题指定的那个开始**连号往后**，所以不会顶掉任何已有要点；
每段的 `question_id` 由服务端按 plan 的同一条规则生成——客户端自己推导 id
会出现「答案标记了错误的问题」这种静默故障，表现是访谈反复问一条已经有了的要点。

### 访谈轮的角色与工具面

舟卡在一轮对话里**不是同一个角色**：档案已经够生成简历时是 `resume-coach`（优化已有内容），
还不够时是 `profile-interview`（把档案问出来）。这个判定在
`services/agent_service.stream_message` 里完成。

一个必须知道的实现约束：**工具面只由 `metadata.skill_hint` 决定**。
`deerflow_harness_client._get_tools` 读的是 `_get_embedded_client(config, metadata.skill_hint)`
解析出的 skill，再据此查 `agent/tool_catalog.py` 的 `SKILL_TOOLS`。所以：

- 只在 registry 里加 `SKILL_TOOLS["profile-interview"]` 条目而不切换 `skill_hint`，
  那个条目就是**死代码**，永远不会被查到；
- `metadata` 必须在 skill 判定**之后**构造。原来的顺序下 `metadata` 先建好，
  判定结果无处可去，于是访谈轮始终带着 `resume-coach` 的工具面跑——
  这是「对话建档」一直不好用的结构原因。

两个角色的工具面是包含关系，不是相等：

| 角色 | 工具面 |
|---|---|
| `resume-coach` | `jc_profile_get`、`jc_profile_patch`、`jc_intake_plan`、`jc_resume_review` |
| `profile-interview` | `jc_profile_get`、`jc_profile_patch`、`jc_intake_plan`、**`jc_intake_record`** |

`resume-coach` 也拿到 `jc_intake_plan`：一份可生成的档案上仍然有开放问题，
那些是补充提示，读一下是有用的。但它**没有** `jc_intake_record`——
可生成档案上的开放问题不是访谈答案。反过来，`profile-interview` 没有 `jc_resume_review`：
访谈阶段还没有稿子可审，导出闸门不该出现在这个角色手上。

### `jc_intake_record` 为什么可以不走确认卡

这是 JC 里**唯一**一条模型不经确认卡写档案的路径，与第 3 节「模型不能自行确认档案 patch」
是刻意的例外，需要明确记录。

`jc_profile_patch` 的确认卡守的是「模型提议修改一份用户已经审阅确认过的档案」。
那个场景下确认卡是对的。访谈不是那个场景：模型没有在提议内容，它在**转录用户一分钟前说的话**，
写进 plan 已经点名的槽位。把这个走确认卡，等于请用户再确认一遍自己刚说的句子——
这正是聊天建档卡住的原因：每个答案都变成一张卡，而 agent 看不到卡有没有被接受。

替代它的边界比确认卡更窄，守的是 **plan 而不是信任**：

1. `question_id` 必须是**当前开放**的问题。已答过的也会被拒——重答走面板，
   那里用户能看见旧值；agent 重提已答问题是「plan 读旧了」的信号。
2. `target_path` **取自 plan**。模型可以声明，但声明与 plan 不一致时直接抛，且不写入。
   模型无法发明路径，也无法把答案改道到访谈不覆盖的字段。
3. 校验用的是 `limit=10_000` 的**完整 plan**，不是面板渲染的那份截断 plan。
   超出显示上限的开放问题仍然是合法答案。
4. 写入走 `record_intake_answers`，与面板**同一实现**。
   那段代码危险的一半不是结构化写入，而是 `evidence_answers` 的记账：
   记错 kind 的答案 plan 永远数不到，访谈就会反复问一条用户已经答过的问题，而且是静默的。

返回值带 `applied`（含用户语言的标签与存下的原文）、`can_generate`、`blocking`、
`next_questions`——plan 是服务端状态，一个会写它的 agent 必须能读回来。
原来 shortfall 以文本注入（`coach_shortfall_for`），那是**开轮之前的快照**：
agent 写完两条之后无从得知档案已经达标，于是要么继续访谈一份已经可以生成的档案，
要么在还差两条时宣称完成。

## 4.5 智能体架构：三个增强点与一个已知瓶颈

JC 是智能体产品，所以功能增强应该落在 **hook / 中间件 / 拦截器**，而不是散落在业务代码里。
完整契约见 [`../decisions/ADR-004-layered-agent-architecture.md`](../decisions/ADR-004-layered-agent-architecture.md)，这里只记运行时要点。

### 三个增强点（新增横切功能只能落在其中之一）

```text
用户消息
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│ Agent 轮次中间件  JCProductRulesMiddleware.before_agent  │ ← 产品规则、会话上下文、回复语言
│ jc/deerflow_middleware.py                                │
└───────────────────────┬─────────────────────────────────┘
                        ▼
              ┌──────────────────┐
              │  DeerFlow 轮次    │
              └───┬──────────┬───┘
                  │          │
    ┌─────────────▼──┐   ┌───▼─────────────────────────────┐
    │ 工具调用拦截器  │   │ 模型调用 hook                    │
    │ jc/mcp/        │   │ jc/llm/audit_hook.py（审计/token）│
    │ interceptors.py│   │ jc/llm/transport.py（响应校验 →   │
    │（如导出前审稿） │   │ 拒答触发 failover）              │
    └────────────────┘   └─────────────────────────────────┘
```

判断落点的方法：这个能力是「每次模型调用都要做」、「每个 agent 轮次都要做」，还是「每次工具调用都要做」。
**不要引入第四种机制。**

### 身份传递：显式参数，不是进程环境变量（已解决，原「全进程串行」事故见 ADR-004）

`adapters/deerflow_harness_client.py` 曾用 `_HARNESS_RUN_LOCK` 把**整轮对话**串行化——
身份（`JC_MCP_USER_ID` 等）写进 `os.environ`，而内嵌的 MCP 连接池是进程全局、跨用户复用的，
锁掩盖的是「下一个用户的请求会覆写这个环境变量」的越权风险。现已改为：

- 身份随每次 `client.stream(...)` 调用通过 `authz_attributes` 参数传递
  （`jc_profile_id` / `jc_session_id` / `jc_job_id` / `jc_mock_session_id` / `jc_agent_skill` /
  `jc_reply_locale`），经 DeerFlow 的 `_EMBEDDED_AUTHORIZATION_CONTEXT_KEYS` 白名单进入
  `runtime.context["authz_attributes"]`，对单次调用只读，不会被并发调用篡改。
  `user_id` 走 `client.stream(..., user_id=...)` 和 DeerFlow 自带的 `resolve_runtime_user_id`。
- `jc` MCP 工具把 `jc_user_id` / `jc_profile_id` / `jc_session_id` 等声明成普通参数（模型可能看到、
  可能尝试填），但 `jc/mcp/identity_interceptor.py` 在请求到达 `jc/mcp/server.py` 前，
  用 `request.override(args=...)` 强制覆写成从 `runtime.context["authz_attributes"]` 解析出的
  真实值——模型填什么都不影响结果，信任边界在拦截器，不在「隐藏参数」。
- **没有进程级锁，跨用户不再排队。** 唯一存在的排队是同一用户同一会话内的
  `followUpQueue` / `steerQueue`（前端 `useAgentSession`，正确行为：防止两轮并行互相覆盖
  同一份档案），和本节描述的架构无关。
- `_CLIENT_CACHE` 仍是进程级缓存，但 key 不含身份（`extensions_config_path` /
  `checkpoint_dsn` / 排序后的 `available_skills`），可跨请求安全复用；不再有运行期可写的
  `_jc_skill` 实例属性。

新增横切身份相关的能力时，默认用显式参数 / `authz_attributes`，不要退回环境变量或其他
进程级可变状态——这是本次事故唯一要记住的教训。

### 多模态的唯一入口

图片进入模型只有一条路：`jc/llm/vision.py`。

- `ImageRef.from_bytes(...)` —— 上传的原始字节（简历图片、PDF 渲染页、文档内嵌图）
- `ImageRef.from_data_url(...)` —— 浏览器聊天附件
- `build_vision_content(intro=, images=, part_labels=)` —— 拼多模态 content；
  `part_labels` 给多页文档加 `--- Part n ---`，否则模型无法说清某字段来自第几页，会乱序合并
- `describe_image(...)` —— 图转文，供纯文本下游（DeerFlow harness 的聊天模型是纯文本的）

路由、重试、failover、审计仍走 `LLMRouter` 的 `vision` scenario，这个模块只拥有**消息形状**。
线格式此前在简历 OCR 与聊天附件两处各手写一份，有测试禁止再出现第二处。

### 附件进出的两条路（语音与图片）

舟卡输入框能收图片与语音，两者在后端是**不同能力级别**的，必须分清。

```text
浏览器                                     服务端
┌──────────────────────────────┐
│ 图片：选文件 / 粘贴 / 摄像头   │
│   → data: URL                 │
│ 语音：MediaRecorder            │──┐
│   → data: URL（原始音频）      │  │
│ 语音文字：Web Speech API       │  │  ← 文字在浏览器就已生成
│   → 输入框 + attachment.       │  │     两份一起发：录音是存档
│     transcript（两处都要）     │  │     transcript 是模型唯一能读的形式
└──────────────────────────────┘  │
                                   ▼
            POST /api/v1/agent/sessions/{id}/messages
                                   │
          ┌────────────────────────┴────────────────────────┐
          ▼                                                 ▼
  ① 发送前校验                                      ② 本轮模型输入
  validate_inline_attachments                flatten_message_for_text_agent
  （单附件 8 MB / 单条消息 24 MB，                每张图 describe_image()
   只收 image/* 与 audio/*）                      → OCR 文本拼进 prompt
          │                                                 │
          ▼                                                 ▼
  ③ 入库（不含字节）                            harness 只收纯文本
  offload_for_persistence                      （client.stream_message
  字节 → TOS: jc/<env>/agent/<sid>/              不再传 attachments）
       attachments/<mid>-<i>.<ext>
  行里留 storage_key / size_bytes
  语音还留 transcript / duration_ms
  失败则 storage_error=true 并打 warning
          │
          ▼
  ④ 回放历史
  resign_persisted_attachments
  按 storage_key 重签 download_url
```

四条必须守住的约束：

1. **`payload_json` 里永远不能出现 `data:`。** 该列是 MySQL `TEXT`（65,535 字节），
   一张 1280×720 摄像头照片 base64 后约 400 KB，是上限的 6 倍。
   **测试跑 SQLite，其 TEXT 无长度限制，这类缺陷测不出来** ——
   所以 `tests/test_agent_attachments.py` 直接断言序列化后的字节数，不依赖数据库报错。
2. **flatten 只能做一次。** `flatten_message_for_text_agent` 不是幂等的：
   它把 OCR 文本追加进消息，再跑一次就会二次调用 vision 并追加第二份。
   `AgentService` 已经 flatten 过，所以调 harness 时**不传 `attachments`**；
   harness 自己保留 flatten 是给尚未展开的调用方用的。有测试用 AST 盯住这个调用点。
3. **签名 URL 是缓存，`storage_key` 才是记录。** 下载签名 15 分钟过期
   （`JC_DOWNLOAD_URL_TTL_SEC`），聊天记录不过期，因此每次读历史都要重签。
4. **上传失败不能抢走用户的消息。** 轮次已经跑完、答案已经在回，
   offload 失败只降级成一条没有媒体的记录，不抛异常。
   但**不能静默**：原先失败后那一行与「用户本来就没发媒体」无从区分，
   是唯一事后查不出来的状态。现在会打一条 warning（带 session/message/index 与
   异常类型，**不带字节**）并在行里置 `storage_error: true`，
   前端据此显示「录音没保存成功」而不是渲染一个点不动的播放器。
5. **语音的 transcript 和录音必须写在同一行。** 只存录音，等于存了一段谁也搜不到、
   读不了、引用不了的音频；只存文字，等于丢掉「这个数字他到底有没有亲口说过」的唯一证据。
   `offload_for_persistence` 把 `transcript` / `duration_ms` 一起落进 attachment 行。
6. **transcript 不能重复进 prompt。** 浏览器的听写本来就把文字打进了输入框，
   所以 transcript 通常**已经是**消息正文。再追加一次会让用户的同一句话在 prompt 里
   出现两遍（读起来像用户自己重复了一次），语音链路的 token 量直接翻倍。
   `audio_text_part(att, existing_text=...)` 只在文字**不在**正文里时才补 ——
   用户听写完又改写或清空输入框时，录音就是唯一记录，这时必须补。

超限的拒绝发生在**模型调用之前**，前端 `lib/attachment-limits.ts` 还会提前量一遍
（和服务端常量成对维护），这样用户在选完文件的那一刻就知道图太大，
而不是等完一次 vision 调用才被告知。

**语音在服务端没有 STT，这是本版本的既定取舍。** 识别在浏览器做
（Web Speech API），录音与文字一起发给后端：录音进 TOS 留档，文字进 prompt 供推理。
服务端 STT 与 LiveKit 实时面试同批，属于下个版本。

由此产生一个**必须在 UI 上说清、不能靠文档兜住**的后果：
`SpeechRecognition` 缺失的浏览器（Safari、部分 Android）识别不出任何文字。
此时照样录音，只会往 TOS 存一段本版本谁也读不了的音频，用户却以为舟卡听见了。
所以这些浏览器里麦克风按钮**保持可见但禁用**，tooltip 写明「请改用 Chrome 或 Edge，
或直接打字」——控件直接消失会被当成页面坏了，而不是浏览器不支持。

判断必须放在 effect 里而不是 render 期：`getSpeechRecognitionCtor()` 读 `window`，
服务端渲染时不存在，在 render 期算会让两端对这个按钮的结论不一致，
React 会丢弃整段 markup。未判定时按「支持」渲染，因为绝大多数用户是支持的。

录音确实录上但一个字都没识别出来时，消息里保留 `[Voice message: ...]` 占位并**明确告诉
模型它读不了这段音频**（`AUDIO_UNREADABLE_SUFFIX`）。早期版本把这种情况静默丢掉，
结果 agent 在回答一条它根本没收到的消息。

## 5. Skill 与 MCP 责任分离

- **Skill**：定义可执行任务的指令、范围、输入输出和获准工具；例如简历辅导、JD 解析、模拟面试、真实题归档。
- **MCP tool**：服务端可验证的窄能力，统一以 `jc_*` 命名；实现用户身份、资源归属、输入校验与审计。
- **Prompt**：用于结构化解析、简历优化、审稿等确定性较强的模型调用，不应为此额外引入 Agent 循环。
- **API**：用户界面与外部调用的稳定边界；Agent 不能跳过 API/服务层直接触碰数据基础设施。

V1 的工具包括档案读取/提议变更、题库检索、面试归档、回答保存、JD 解析、匹配分析及受限 JD 读取。实际目录以 `backend/server/src/jc/agent/tool_catalog.py`（工具清单与角色工具面）、`backend/server/src/jc/mcp/`（处理器与 stdio 服务）和 `backend/agent/deerflow/extensions_config*.json` 为准。

## 6. 变更检查清单

新增或修改一个 skill/tool 前，必须确认：

1. 是否确实需要 Agent，而非普通 API/Prompt；
2. 最小输入、输出、权限与可访问资源是什么；
3. 是否做了用户/资源归属校验、参数校验、限流与审计；
4. 是否会触及外部网络、文件、会议音频或敏感档案；
5. 是否已有覆盖成功、拒绝、越权、取消和失败恢复的测试；
6. 是否同步更新本文件与 [`../discussions/DISCUSSION-INTEGRATIONS.md`](../discussions/DISCUSSION-INTEGRATIONS.md) 的选型状态。
