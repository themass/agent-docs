# Agent harness 选型：从零评估（完整分析）

日期：2026-11-09
状态：分析完成。全部候选已核实（2026-11-09）；最终路线待一周原型验证（第 11 节第 1 条）。

前提：
- **忽略已经开发的代码**。复用现有中间件、改动面小，都不计分。
- **数据库不限**（不再限定共享的 MySQL 5.6），按场景需要自选。

依据：
- 本地资料：`/Users/gqli/work/deepagents/docs/` 下 40 余个框架的架构笔记、`框架对比/` 系列、`第三方memory/`；
- GitHub 同类项目调研（观察日期 2026-11-09）；
- DeerFlow 2.3.0-dev 与 LangChain 1.4.9 的安装包实测；
- SillyTavern 1.19.0 源码（提交 `06bde939`，AGPL-3.0），三路只读分析。

---

## 0. 结论

1. **这个场景是四层，框架通常只管其中一层：**

   | 层 | 内容 | 谁能提供 |
   |---|---|---|
   | A. 回合内 harness | 调模型、跑工具、MCP、skill、中间件、插话、确认的暂停点 | agent 框架 |
   | B. 会话层 | 排队、合并、取消、重新生成、swipe、分支、跨服务器串行、SSE 续传、主动消息调度 | **AgentScope v2 App 层、Agno AgentOS 大部分提供**（均已核实）；LangGraph 只在付费的 Agent Server 里有；其余都要自建 |
   | C. 角色扮演提示词引擎 | 角色卡、世界书、作者注、人设、示例、按深度注入、token 预算 | **没有 Python 框架提供**；SillyTavern 有最成熟的设计，但是 AGPL、单用户、浏览器端 |
   | D. 记忆 | 会话摘要、长期记忆、向量召回 | 记忆库（mem0、LangMem、Memobase 等）或自建 |

2. **三条可行路线：**

   | | 路线一：AgentScope v2 | 路线二：Agno + AgentOS | 路线三：PydanticAI + 自建会话层 |
   |---|---|---|---|
   | 定位 | 框架 + 会话层平台 | 框架 + 会话层平台 | 回合引擎库，平台自建 |
   | 插话（C3） | ✅ 有，但**只在 `main`，未发布** | ✗ **没有**（源码核实），要自建 | ✅ **原生 `AgentRun.enqueue(priority='asap'\|'when_idle')`**，可从别的任务或线程调用（已发布） |
   | 取消 | ✅ 跨服务器 | ✅ 跨服务器（Redis） | ✅ 细粒度：保留已完成部分、未完成的工具调用补「已中断」结果 |
   | 工具确认不阻塞（C4） | ✅ 挂起持久化，任意进程恢复 | ✅ 写审批表，任意副本恢复（**仅 Postgres、SQLite**） | ✅ 延迟工具调用结束本轮，用新一轮恢复，任意进程可做（我们持久化） |
   | 跨服务器串行 | ✅ Redis 会话锁 | ◐ 每会话一个回合只在后台 / 持久化路径上，**2026-10 才加**；前台运行无锁 | 自建 |
   | SSE 续传 | ✅ | ✅（Redis 事件流） | 自建 |
   | 主动消息调度 | ◐ 单进程、无故障转移 | ✅ 多副本认领（`SKIP LOCKED`） | 自建 |
   | swipe / 分支 | 自建 | ◐ 有重新生成、fork、存档点 | 自建（历史由我们传入，最容易对上我们的模型） |
   | 每次模型调用前改写请求（C1） | ✅ `on_model_call` | ◐ pre hook 每次运行一次，工具循环内每次调用前的改写**未找到** | ✅ `before_model_request`，工具调用后的每次请求也会执行 |
   | 历史的权威 | 它的会话记录与 `AgentState` | **它的数据库是权威**，DB 不可用即失败 | **我们的消息表** |
   | 主要风险 | 排队与插话未发布；v1→v2 重写；App 层强主张 | API 面大、变化快；会话队列太新，需压测；功能完整性只在同步 Postgres 上 | 平台层工作量大；Harness（skill、记忆、压缩）还是 0.x |
   | 许可 | Apache-2.0 | Apache-2.0 | MIT |

3. **建议（修订，2026-11-09）：路线一（直接用 AgentScope v2，App 层 + 内核）为主选，路线三（PydanticAI + 自建平台）为退路。**

   上一版把路线三放在前面，理由经源码复核后站不住（详见第 4.4 节）：
   - 「排队与插话未发布」：发布节奏约两周一次（v2.0.11 于 10-27），`main` 已领先 91 个提交，下一个版本大概率很快带上；可以先固定提交。**是短期风险，不是否决理由。**
   - 「历史在它的数据模型里，swipe、分支难做」：它的消息表是扁平的（`session_id, msg_id, created_at, payload`），没有父子或候选结构，这一点属实。但我们可以**让自己的消息树（候选、分支）做权威**，每回合运行前把 `AgentState.context` 按当前活动分支重建，它的 `context` 只当本回合的缓存——这和我们原本「历史以消息表为权威、每回合无状态传入」的设计是同一个思路。
   - 「App 层强主张」：它按「每个用户拥有自己的 agent」设计，但访问控制是可插拔的（`ResourceAccessPolicyBase`），283 个预置角色可以作为系统账号拥有的 agent，通过自定义策略共享给所有用户。
   - 「提示词不受控」：内核默认会追加时间、计划等运行时提示（`inject_runtime_state`，可关），并把 skill 说明拼进系统提示词；但 `on_model_call` 中间件拿到的是发给模型的**完整** `messages` 与 `tools`，可以整份替换成我们的角色扮演组装结果。
   - 而另一边，路线三要自建的会话层（会话锁、持久化队列、插话、跨服务器取消、SSE 重放、审批挂起与任意节点恢复）约 6–9 人周，且是最容易出错的部分；AgentScope 已经按多副本做好。

   **「只用 AgentScope 的 App 层、内核换成 PydanticAI」不建议**（第 4.4 节）：插话、审批恢复、中断、压缩都实现在 AgentScope 的 `Agent` 内核里，App 层只是驱动它。换内核等于写一个适配器 `Agent`，把 PydanticAI 的事件翻译成 AgentScope 的约 60 种事件、把它的历史转成 `list[Msg]`、再按 AgentScope 的语义重做插话与审批恢复——PydanticAI 的优势（原生 `enqueue`、延迟工具调用）全被翻译层吃掉，还要同时跟两个快速变化的框架。

   一周验证（第 11 节第 1 条）改为以路线一为主：重点验证「我们的消息树做权威 + 每回合重建 `context`」、`on_model_call` 整份替换提示词、多副本、换掉本地文件的 Offloader。通过就定路线一；不通过再走路线三，并把 AgentScope App 层（Apache-2.0）当参考实现。

4. **淘汰与降级：**
   - **LangChain `create_agent` / LangGraph**：钩子与内置中间件最强、有**官方 LiveKit 插件**、`interrupt()` 跨进程恢复最成熟。但开源版**没有插话、没有会话锁**，确认要靠 checkpointer（checkpoint 变成历史的权威）；我们需要的「双发处理」（排队、中断、回滚）、SSE 续传、定时任务、运行队列**只在商业 Agent Server 里**，要许可证密钥并向 `beacon.langchain.com` 上报。作为路线三的替代 A 层仍然可行，但插话要自建。
   - **Microsoft Agent Framework**：内核好，但插话队列在进程内、没有分布式会话存储、没有调度器、小版本常带破坏性变更。
   - **Letta**：**Python 服务端已退役**（转为 TypeScript 的 letta-code），自托管状态在本地磁盘（不满足多服务器），App Server 允许 agent 在宿主机执行 shell，跨机器要用闭源的 Letta Cloud。它的记忆设计（自编辑记忆块、「睡眠时」反思）值得借鉴。
   - **OpenAI Agents SDK**：无插话，钩子不能改写请求。
   - **DeerFlow**：只看 SDK 工厂路径时不适合；**全栈（网关 + lead agent）是第二平台候选**，见第 4.5 节。平台层很完整，但提示词模板与 checkpoint 权威和角色扮演冲突。

5. **C 层自建，按 SillyTavern 的语义做洁净室实现**（第 5 节）。三条路线都需要。
6. **D 层：Postgres + pgvector**，会话摘要按 SillyTavern 的增量方式做；长期记忆接口可替换（第 7 节）。
7. **存储：Postgres（含 pgvector）+ Redis。**
8. **语音**：LiveKit 只有 LangChain 有官方插件；选 PydanticAI 时要自己写 `llm_node` 桥接（把 token 流接给 LiveKit），工作量小但要做。

---

## 1. 场景

- Android 陪伴 / 角色扮演聊天；中、英、阿拉伯语。
- 角色：几百个预置角色加用户自建角色，格式是 SillyTavern Character Card V2/V3；以后可能有群聊。
- 回合短、频繁、人设重、工具少、对延迟敏感、全程流式。
- 服务端会主动发起对话（定时问候、事件提醒），不只是被动应答。

## 2. 约束与能力权重

### 2.1 硬约束

| # | 约束 | 说明 |
|---|---|---|
| H1 | 多服务器、进程无状态 | 任何进程能处理任何会话的任何回合；进程内、本地文件、sqlite 里不能有权威状态 |
| H2 | ~~共享的 MySQL 5.6~~ **已取消** | 存储自选。评分看「框架在它最合适的存储上，多服务器模式是否有官方支持」。数据库数量仍计入运维成本 |
| H3 | 不下载、不运行本地模型 | 模型与 embedding 都走远程 OpenAI 兼容网关（LiteLLM） |
| H4 | 多模型 | 千问、豆包、DeepSeek、GPT 等，经同一个网关 |
| H5 | 工具确认不能占住进程 | 等用户确认期间不阻塞；确认可能落在另一台服务器上 |
| H6 | 许可证允许闭源服务端使用 | AGPL、GPL 的代码不能进服务端 |

### 2.2 能力权重

3 = 核心；2 = 重要；1 = 加分。

| # | 能力 | 权重 | 所在层 |
|---|---|---|---|
| C1 | 每次模型调用前可完全改写请求（系统提示词、历史、注入） | 3 | A |
| C2 | token 级流式 + 工具开始/结束事件 | 3 | A |
| C3 | 回合中途插话与取消 | 3 | A + B |
| C4 | 工具确认（满足 H5） | 3 | A + B |
| C5 | 会话与消息状态（排队、合并、swipe、分支、中断、跨服务器串行） | 3 | B |
| C6 | 长期记忆 | 2 | D |
| C7 | 会话摘要 / 上下文压缩 | 2 | D |
| C8 | 服务端主动消息 | 2 | B |
| C9 | MCP 客户端 | 2 | A |
| C10 | Skill（按需加载的说明 + 工具） | 2 | A |
| C11 | 语音（LiveKit 能把它当大脑调用） | 1 | A |
| C12 | 可观测性（OpenTelemetry） | 1 | A |
| C13 | 多租户隔离 | 2 | B + D |
| C14 | 成熟度、依赖重量、厂商绑定 | 2 | — |
| C15 | 角色扮演提示词引擎（卡片、世界书、作者注、深度注入） | 3 | C |

---

## 3. A 层：回合内 harness 的候选评估

标记：✅ 有，且满足；◐ 有，但需要绕过或自己补；✗ 没有或不满足。OpenAI Agents SDK 的许可证未核实（已淘汰，不影响结论）。

### 3.1 对照表

| 能力 | LangChain `create_agent` | Microsoft Agent Framework | AgentScope v2 | PydanticAI | OpenAI Agents SDK | Agno | DeerFlow |
|---|---|---|---|---|---|---|---|
| H1 无状态、历史由我们传入 | ✅ checkpointer 可选 | ✅ 核心明确不做跨进程一致性 | ✅ `Agent(state=…)` 每轮重建 | ✅ 传入 `message_history` / `Conversation`，核心库无数据库 | ✅ 传入输入列表 | ◐ 依赖它的 DB，DB 不可用即失败 | ◐ 内置中间件按线程 + checkpoint 设计 |
| H4 多模型 / 自定义 base_url | ✅ `ChatOpenAI(base_url=…)` | ✅ `OpenAIChatClient(base_url=…)` | ✅ `credential.base_url` | ✅ OpenAI 兼容 base_url | ✅ `LitellmModel` | ✅ `models/litellm` | ✅ |
| H6 许可证 | ✅ MIT（安装元数据确认） | ✅ MIT | ✅ Apache-2.0（本地检出确认） | ✅ MIT | **未核实** | ✅ Apache-2.0（本地检出确认） | wheel 元数据未填 |
| C1 改写模型请求 | ✅ `wrap_model_call` / `before_model` | ✅ `ChatMiddleware` 包裹每次模型调用 | ✅ `on_model_call`、`on_system_prompt` | ✅ `before_model_request`，工具调用后的每次请求也执行 | ✗ 钩子只能观察 | ◐ pre hook 每次运行一次；工具循环内每次调用前的改写**未找到** | ✅，但有隐藏中间件注入 |
| C2 流式 | ✅ `stream_mode="messages"` | ✅ `ResponseStream` | ✅ `AgentEvent` 块 | ✅ `PartDeltaEvent` 等 | ✅ | ✅ | ✅ |
| C3 插话 | ◐ 无内置；`before_model` 钩子可实现 | ◐ 核心中间件、不依赖 Foundry，但队列在进程内，**不能跨服务器** | ✅ `SteeringMiddleware` + App 层持久化队列（**仅 `main`，未发布**） | ✅ **原生 `AgentRun.enqueue`**（`asap` / `when_idle`），可跨任务、线程调用 | ✗ 只能取消重跑 | ✗ 源码中没有插话原语 | ◐ 原生插话只在网关链路，SDK 工厂没有 |
| C4 工具确认不阻塞 | ◐ 内置 HITL 用 `interrupt()`，**需要 checkpointer**；不用它则在 `wrap_tool_call` 里自建 | ◐ 审批严谨（含重放保护），但挂起状态在 `AgentSession`，跨进程恢复要自建共享存储 | ✅ 挂起持久化，确认后任意进程恢复 | ✅ `requires_approval` / `ApprovalRequired` 结束本轮、返回延迟请求，用新一轮恢复，任意进程可做 | ✅ `needs_approval` + 可序列化 `RunState` | ✅ 写审批表、任意副本恢复（仅 Postgres、SQLite） | ◐ 强制 `ClarificationMiddleware` 会中断等人 |
| C7 摘要 / 压缩 | ✅ `SummarizationMiddleware`、`ContextEditingMiddleware` | ✅ 压缩 provider | ✅ `compress_context` | ◐ 核心只支持厂商原生压缩；Harness 有滑动窗口、LLM 摘要、分层策略 | ◐ 绑定 Responses API | ✅ SessionSummary | ✅ |
| C9 MCP | ✅ `langchain-mcp-adapters` | ✅ | ✅ | ✅ `MCPToolset` | ✅ | ✅ | ✅ |
| C10 Skill | ◐ 可移植 deepagents `SkillsMiddleware` | ✅ `SkillsProvider` + `load_skill` | ✅ | ◐ 在 Harness（0.x）里，`SKILL.md` 按需加载 | ◐ 仅沙箱 | ✅ `SKILL.md` | ✅ |
| C11 语音 | ✅ **官方 `livekit-plugins-langchain`**（候选中唯一） | ✗ 没有 LiveKit | ◐ 有 realtime、WebRTC、TTS/ASR；没有 LiveKit | ◐ 没有 LiveKit 插件，需自写 `llm_node` 桥接 | ◐ 有 Realtime | ◐ 没有 LiveKit | ◐ |
| C12 OpenTelemetry | ◐ 主推 LangSmith；OTel 需配置 | ✅ 内置 | ✅ OTel 是核心依赖 | ✅ 原生 OTel（GenAI 语义约定），Logfire 可选 | ✅ tracing | ✅ OpenInference，追踪存库 | ◐ Langfuse |
| C14 成熟度 / 依赖 | ✅ 生态最大；依赖轻；v1 API 较新 | ◐ 1.25.0；每周小版本，常带破坏性变更；`-core` 不拉 Azure | ◐ v2.0.11；v1→v2 重写，约两周一个补丁 | ✅ v2.66.0；大版本内不破坏兼容；小版本 2–5 天一个；Harness 0.36（pre-1.0） | ◐ 0.x | ◐ v3.1.12；1–4 天一个版本；Agno 3 是重写；API 面大 | ✗ 开发版，两个月 1000+ 提交、54 个迁移，22 MB、40+ 依赖 |

LangChain 1.4.9 实际带的中间件（安装包核实）：`SummarizationMiddleware`、`ContextEditingMiddleware`、`HumanInTheLoopMiddleware`、`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ModelFallbackMiddleware`、`ModelRetryMiddleware`、`ToolRetryMiddleware`、`ToolErrorMiddleware`、`ModelRefusalMiddleware`、`PIIMiddleware`、`LLMToolSelectorMiddleware`、`ProviderToolSearchMiddleware`、`TodoListMiddleware`、`LLMToolEmulator`，以及文件搜索与 shell 两个编码向的中间件。其中 `HumanInTheLoopMiddleware` 基于 `langgraph.types.interrupt`，必须配 checkpointer 才能恢复。

### 3.2 逐个结论

**LangChain `create_agent` / LangGraph（降为备选回合引擎，已核实）**
- MIT；langgraph 1.2.20、langchain 1.4.9；v1.0 承诺到 2.0 前不破坏兼容。
- 强项：钩子最全（`wrap_model_call` 每次调用都能替换请求、`wrap_tool_call`）；内置中间件最多（本节开头列出）；`interrupt()` + `Command(resume)` 跨进程恢复最成熟，1.2.20 加了拒绝过期答复的严格模式；**官方 LiveKit 插件**；Store 支持 pgvector 语义检索。
- 决定性缺口：开源版**没有插话、没有会话锁**；内置人工确认要求 checkpointer，checkpoint 会变成历史的权威，和我们的消息模型冲突。我们需要的「双发处理」（拒绝、排队、中断、回滚）、SSE 续传、定时任务、运行队列**只在商业 Agent Server 里**：需要 `LANGGRAPH_CLOUD_LICENSE_KEY`，默认向 `beacon.langchain.com` 做许可校验与用量上报；文档把 Docker 部署定位为开发用、生产走 Helm/K8s。
- 结论：选它等于「付费买会话层」或「自建插话 + 自建会话层」。技术上强，但插话（权重 3）不如 PydanticAI 原生。

**Microsoft Agent Framework（降级，已核实）**
- 核实对象：本地检出 `agent-framework`（core 1.22.0），上游最新 python-1.25.0（2026-11-07），MIT。
- 强项：`ChatMiddleware` 包裹每一次模型调用，可以改写消息与选项（C1 ✅）；`MessageInjectionMiddleware` 是核心中间件，**不依赖 Foundry**；审批有出现次序绑定与重放保护；压缩策略丰富（截断、滑动窗口、摘要、token 预算等）；OTel 一等公民；`agent-framework-core` 单独安装不拉 Azure 依赖（元包 `agent-framework` 会拉）。
- 决定性缺口：插话队列放在 `session.state`、靠进程内线程锁，**跨服务器的插话不支持**；没有分布式 `SessionStore`、锁或 CAS，文档明确把「单写者」交给应用；没有调度器；没有 LiveKit；多租户由应用实现。会话层要从零建，约 6–9 人周。
- 风险：大约每周一个小版本，小版本常带 `[BREAKING]`；Postgres、Redis、mem0、hosting 等集成包还是 alpha 或 beta。
- 结论：好的 agent 内核库，**不适合作为这个场景的运行时**。

**AgentScope v2（路线一的候选，已核实）**
- 是唯一一个提供多服务器会话层的框架（第 4.2 节）：排队、插话、跨服务器取消、SSE 续传、审批挂起与任意节点恢复，官方多副本布局是 Postgres + Redis。
- 内核：`on_model_call`（洋葱模型，可改写发出的消息）、`on_system_prompt`（流水线）、`on_reasoning`；token 级事件（文本、思考、工具调用开始/增量/结束、工具结果增量）直接对应 SSE；OpenAI 兼容 `base_url` 可接 LiteLLM；MCP 是核心依赖；有 skill 加载器；Mem0 与 ReMe 记忆中间件，不需要本地模型。
- 风险：排队与插话未发布；v1 → v2 是重写，约两周一个补丁版本；App 层有自己的路由与数据模型；Offloader 默认写本地文件；调度器单进程；阿里云生态的默认值较多（DashScope 等）。

**PydanticAI（路线三的回合引擎，已核实）**
- MIT；v2.66.0（2026-11-04）；v2.0.0 于 2026-06-23 发布，承诺大版本内不破坏兼容，V2 里弃用的东西到 V3 前都保留。另有 `pydantic-ai-harness`（v0.36，pre-1.0）提供 skill、记忆、压缩。
- **插话原生**：`AgentRun.enqueue(*content, priority='asap'|'when_idle')`。`asap` 在下一次模型请求时注入，或在 agent 本来要结束时转向；`when_idle` 只在 agent 本来要结束时注入，不打断进行中的工作；可以从别的任务或线程调用；运行结束后调用会报错。（官方 API 文档核实）
- **取消**：`AgentRun.cancel()` 结束整个运行，之前完成的内容保留在历史里，可以作为下一次的 `message_history` 继续；`StreamedRunResult.cancel()` 只停当前这次模型响应、运行继续。未完成的工具调用会被补上「已中断」的结果，历史保持合法。
- **工具确认**：`requires_approval=True` 或抛 `ApprovalRequired` → 本轮结束、返回延迟工具请求 → 用新一轮带上 `message_history` 与 `DeferredToolResults` 恢复，任意进程都可以。需要我们自己持久化 `Conversation`；文档提醒这「不是授权边界」，授权仍由我们做。
- **改写请求**：capability 的 `before_model_request` 可以替换消息，**工具调用之后的每一次请求也会执行**；另有动态指令、历史处理器。
- 流式：文本与思考的 token 增量、工具参数增量、工具调用与结果事件、`EnqueuedMessagesEvent`。没有 SSE 续传缓冲。
- 状态：核心库**无状态、无数据库**，历史由我们传入；Harness 的步骤持久化有 Postgres（我们提供连接池）。没有会话锁。
- 缺口：服务端、SSE 续传、会话锁与队列、合并、swipe、调度器、向量记忆、群聊、LiveKit 桥接、多租户——即整个平台层。

**OpenAI Agents SDK（不选）**：没有插话，钩子不能改写模型请求（C1、C3 缺失）。审批的可序列化设计值得参考。

**Agno + AgentOS（路线二，已核实）**
- Apache-2.0（本地检出 `c92d1ad72` 确认）；v3.1.12（2026-10-29）；1–4 天一个版本；Agno 3 是重写。
- 是候选中**最完整的可自托管平台**：审批写库、任意副本 `continue`；Redis 事件流支持跨副本 SSE 续传；Redis 取消管理器支持跨副本取消；持久化任务队列；**多副本调度器**（`FOR UPDATE SKIP LOCKED` 认领）；有重新生成、fork、存档点；压缩与摘要；skill；MCP；OTel。
- 缺口：**没有插话原语**（本地源码检索 `steer` / `inject` / `pending_message` 均无）；每会话一个回合（`queue_per_session`，默认开）只作用于后台 / 持久化路径，2026-10 才加入，前台运行无锁；工具循环内每次模型调用前改写请求的钩子未找到；记忆召回不是语义的；审批、压缩、调度的完整功能只在同步 Postgres 与 SQLite 上。
- 历史以它的数据库为权威，swipe、分支要服从它的数据模型。
- 结论：「平台现成」最多，但缺插话、会话队列太新、对历史的控制弱。需要压测后才能信任。

**Letta（淘汰，已核实）**
- **Python 服务端已退役**：仓库 README 说 V1 API 服务端在 `archive` 分支，活跃项目应使用 letta-code（TypeScript）；Docker 镜像「不再是积极维护或支持的产品」。
- 自托管的 App Server 把状态放在本地磁盘（`~/.letta/...`），不满足多服务器；App Server 允许 agent 在宿主机执行 shell 与访问文件，不适合面向消费者的聊天应用；跨机器状态要用闭源的 Letta Cloud。
- 它的陪伴式记忆设计（自编辑的记忆块、「睡眠时」反思）值得借鉴到 D 层。

**DeerFlow**：SDK 工厂路径不适合（强制 `ClarificationMiddleware`、隐藏中间件、依赖重）。全栈另行评估，见第 4.5 节：平台层完整，提示词控制与历史权威是问题。

---

## 4. B 层：会话层

### 4.1 为什么没有框架能完整提供

这一层的需求全部来自「聊天产品」而不是「agent」：

- 用户在回复生成中继续发消息：排队、合并（首 token 前中止重来）、插话；
- 取消、重新生成、swipe（同一位置多个候选回复）、分支；
- 断线重连后 SSE 续传；
- 同一会话跨服务器串行；
- 服务端定时发起回合，多副本不重复发送。

三路调研（本地 40 余个框架、GitHub 同类项目、SillyTavern）结论一致：框架管「一次回合内」，这一层都要自己做。SillyTavern 也没有做——它的服务端没有回合、队列、生成状态的概念，全在浏览器标签页里。

### 4.2 AgentScope v2 App 层（已核实）

核实对象：本地检出 `/Users/gqli/work/deepagents/agentscope`，`main` 提交 `85f1a9df`（2026-11-09），最新发布 v2.0.11（2026-10-27），Apache-2.0。本地资料 `agentscope/AGENTSCOPE.md`、`TOPICS_AND_GAPS.md`（2026-10-13）说「没有插话、忙时返回 409」，**已经过时**：之后 `main` 加了持久化会话队列（`2350af90`，10-30）和插话（`9a2d631f`，11-02）。

| 需求 | AgentScope v2 | 出处（相对 `src/agentscope/`） |
|---|---|---|
| 是正式发布的包 | 是。`agentscope.app` 在 wheel 里，服务端需要 `[service]` 额外依赖 | `pyproject.toml` |
| 跨服务器串行 | Redis 会话锁覆盖整个运行 | `app/_service/_chat.py:830, 924` |
| 排队 | 每会话持久化 FIFO，带认领、重试、恢复租约；接口可查看、重排、修改、删除 | `app/_manager/_chat_input_queue.py`；`app/_router/_chat.py:101–339` |
| 插话 | 在推理边界注入（不在模型调用或工具执行中途）；文本输出中途到达的输入可以丢弃当前回答、触发新一轮 | `middleware/_steering.py`；`app/middleware/_steering_middleware.py` |
| 合并（首 token 前中止重来） | **没有内置**，需要在中断 + 重新入队上补一层 | — |
| 取消 | `POST /sessions/{id}/interrupt`，取消广播让正在运行它的那台服务器停止 | `app/_router/_session.py:434–442`；`app/_manager/_cancel_dispatcher.py` |
| SSE 续传 | 先重放缓冲日志再订阅实时，带重放游标与 30 秒心跳 | `app/_router/_session.py:832–868` |
| 工具确认不阻塞 | 权限引擎返回「询问」→ 发确认事件 → 运行挂起并持久化 → 确认结果进唤醒队列 → 任意进程恢复 | `app/_router/_chat.py`；`AGENTSCOPE.md` §6、§11.3 |
| 调度器 | APScheduler，内存任务存储；记录在 Storage；触发写收件箱 + 唤醒，任意进程执行。**只能一个进程持有定时器，没有选主与故障转移**；只支持 cron | `app/_manager/_scheduler/_scheduler_manager.py` |
| 存储 | `RedisStorage`、`AsyncSQLAlchemyStorage`（SQLite、Postgres、MySQL/MariaDB；Alembic 迁移）；官方多副本布局是 Postgres + Redis 总线 | `_storage.py`；`_app.py:225–250` |
| 本地文件 | App 总是把工作区作为 Offloader，`LocalWorkspace` 写 `{workdir}/sessions/{id}/context.jsonl`（违反 H1）；它是 Protocol，可以换成远程工作区或自定义实现 | `workspace/_offload_protocol.py`；`app/_service/_chat.py:1317` |
| swipe / 重新生成 / 中断记录 | 没有 | — |
| 多租户 | 有访问层、`get_current_user_id`、会话归属检查（404）；认证自己接 | `app/access/` |
| 语音 | 有 realtime（OpenAI、DashScope、Gemini、xAI）、WebRTC、TTS/ASR 中间件；**没有 LiveKit** | `realtime/`；`app/_service/_webrtc_session.py` |
| 可观测性 | OpenTelemetry 是核心依赖，`TracingMiddleware` | `middleware/_tracing/` |

**排队与插话不在已发布版本里**：`app/_manager/_chat_input_queue.py` 与 `middleware/_steering.py` 在 `main` 上存在，在 `v2.0.11` 标签下不存在（本地 `git cat-file` 核实）。

**关键的未知**：它的会话记录与 `AgentState.context` 是它自己的数据模型。我们需要的 swipe（同一位置多个候选）、分支、隐藏消息、世界书定时状态，能不能放进去而不 fork 它的 App 层，是决定路线一成败的问题。

无论是否采用，都用这张表做检查清单。

### 4.3 会话层的设计要点

| 要点 | 做法 |
|---|---|
| 跨服务器串行 | Redis 会话锁（SET NX PX，定期续期）+ **围栏号**：续期失败立即停止产出，写入按围栏号做条件写，拒绝过期写入 |
| 读己之写 | 用户消息在回合开始前落库；助手消息在释放锁前落库；构建上下文读主库 |
| 排队 / 合并 / 插话判定 | 一个原子操作（Redis Lua）根据「锁是否被持有、回合阶段、重跑次数、插话预算」决定去向 |
| SSE 续传 | 事件写 Redis Stream（带 MAXLEN），客户端用 `Last-Event-ID` 续传；回合结束后快照事件 |
| 取消 | 控制流（Redis Stream）通知持锁进程；保留已生成部分并标记中断 |
| 主动消息 | 调度器只负责「到点入队」，不直接生成；入队后与用户消息走同一条回合路径；用唯一键去重，保证多副本只发一次 |
| 工具确认 | 见 6.4 |

---

### 4.4 能不能「只用 App 层」？直接用 AgentScope 的接法（源码复核）

核实对象：本地检出 `agentscope`（`main` `85f1a9df`）。路径相对 `src/agentscope/`。

**规模**：App 层 217 个文件、58,815 行；内核 `Agent` 类单文件 4,004 行（`agent/_agent.py`）。

**App 层和内核之间的接缝**：

| 接缝 | 出处 | 说明 |
|---|---|---|
| 构造 agent | `app/_service/_chat.py:1307` | `self._agent_cls(name, system_prompt, model, toolkit, model_config, context_config, react_config, state, middlewares, offloader)`；可通过 `custom_agent_cls` 传入子类（`_chat.py:170, 272`） |
| 驱动回合 | `app/_service/_chat.py:1400, 1543` | `async for event in agent.reply_stream(inputs=...)` |
| 持久化 | `app/_service/_chat.py:1657–1690` | 回合结束时在会话锁内写消息与 `agent.state`，再推进事件游标 |
| 状态 | `state/_state.py:209` | `AgentState`：`session_id`、`summary`、`context: list[Msg]`、回合上下文 |
| 事件 | `app/` 全目录 | App 层引用约 60 种事件类型（文本、思考、工具调用、工具结果、确认请求与结果、外部执行、中断、AG-UI 投影等） |

**插话、审批恢复、中断都在内核里**：
- 插话：`middleware/_steering.py` 的 `SteeringMiddleware` 在内核的推理边界检查来源、注入 `HintBlock`，文本输出后到达的输入可以压掉这次回答、让内核再跑一轮。
- 审批恢复：`agent/_agent.py:1849` `_check_incoming_event`、`:1932` `_handle_incoming_event` 接收 `UserConfirmResultEvent` / `ExternalExecutionResultEvent`，从挂起处继续。
- 权限：`agent/_agent.py:2345` `_check_permission`。
- 压缩：`agent/_agent.py:372` `compress_context` 等。

所以 App 层提供的是「会话锁、队列、总线、重放、唤醒分发」，**语义本身由内核实现**。换掉内核，这些语义要在适配器里重做一遍。

**直接用 AgentScope 时的接法**：

| 需求 | 接法 | 出处 |
|---|---|---|
| 角色扮演提示词完全受控 | 写一个 `on_model_call` 中间件，用我们组装的结果整份替换 `input_kwargs["messages"]`（与 `tools`） | `middleware/_base.py:213` |
| 去掉框架追加的提示 | `InjectionConfig.inject_runtime_state=False`；不启用 skill 与工作区说明，或在 `on_system_prompt` 里过滤 | `agent/_config.py:224`；`agent/_agent.py:3290` |
| 消息树（swipe、分支）做权威 | 自己的候选与分支表；继承 `ChatService`，在构造 agent 前按当前活动分支重建 `AgentState.context`；重新生成 = 删掉 AgentScope 侧最后一条助手消息（`delete_message`）后重跑 | `app/storage/_base.py:757`；`_chat.py:1304` |
| 预置角色共享给所有用户 | 系统账号拥有这些 agent，自定义 `ResourceAccessPolicyBase` 子类放开读取 | `app/access/_policy.py:79` |
| 不在节点磁盘写文件 | 换掉 Offloader（远程工作区或自定义实现） | `workspace/_offload_protocol.py` |
| 主动消息 | 用我们自己的到期表 + 选主租约，到点调用它的收件箱 + 唤醒路径 | `app/_manager/_scheduler/` |
| 合并（首 token 前中止重来） | 在中断 + 重新入队上补一层 | `app/_manager/_chat_input_queue.py` |
| 存储 | `AsyncSQLAlchemyStorage` on Postgres + `RedisMessageBus`（官方多副本布局） | `app/_app.py:225–250` |

**仍然存在的问题**（验证时重点看）：
- 两份记录：我们的消息树与它的 `messages` 表、`AgentState.context` 会并存。要守住「我们的表是权威，它的是每回合重建的缓存」，否则会重演 checkpointer 的不一致问题。
- 它的内核是为任务型 ReAct agent 设计的（压缩、计划、迭代上限），陪伴聊天用不到大部分；需要确认关掉之后没有副作用。
- 跟随 `main` 的风险：在正式版本带上排队与插话之前，要固定提交并自己承担回归。

### 4.5 DeerFlow 全栈（网关 + lead agent）复核

之前对 DeerFlow 的否定基于两个前提：只看了 SDK 工厂路径（`create_deerflow_agent`），且数据库限定 MySQL 5.6。这两个前提都已取消，所以按与 AgentScope 相同的标准重评它的**全栈**。

核实对象：本地检出 `/Users/gqli/work/deepagents/deer-flow`，提交 `235b5556e`（2026-11-04），`deerflow-harness` 2.3.0-dev，MIT（字节跳动）。检出里最新标签是 `v2.1.0-rc0`，与本地资料所说「2.2.0 已发布」不一致，发布状态需要在上游再确认。网关 `backend/app` 159 个文件、63,321 行；lead agent 装配 20 个中间件。路径相对 `backend/`。

| 需求 | DeerFlow 全栈 | 出处 |
|---|---|---|
| 多副本 | **官方支持且有启动闸门**：开多进程时强制要求 Postgres、运行事件存数据库、运行所有权心跳、Redis 流桥接、调度器多实例模式、IM 通道选主租约，任一不满足直接拒绝启动并说明原因 | `app/gateway/deps.py:189–259` |
| 运行中追加输入 | 每个运行有一个有界、持久化的输入队列（最多 16 条），两种模式 `queue` / `steer`；接口可提交、列出、撤回、重试 | `app/gateway/run_inputs.py:22`；`app/gateway/routers/thread_runs.py:88–106` |
| 插话语义 | 每次模型调用前投递新输入；**如果模型刚规划了工具调用、而用户又发了新消息，计划的工具调用不执行**，改成一句说明并让模型重跑（中文环境提示「任务已更新，刚才计划的操作尚未执行」）。比 AgentScope 更细 | `packages/harness/deerflow/agents/middlewares/run_input_middleware.py:53–79` |
| 忙时的新请求 | `multitask_strategy`：`reject`（默认）/ `rollback` / `interrupt` | `app/gateway/run_models.py:55` |
| 重新生成 / 编辑后重新生成 | **原生**：按 checkpoint 谱系回到父节点重跑 | `thread_runs.py:1029, 1040` |
| 取消、断线重连 | 取消接口、`join`、按运行重新订阅流（经 Redis 桥接跨副本） | `thread_runs.py:1345, 1406, 1516` |
| 主动消息调度 | 调度器带租约与过期认领恢复，支持多实例 | `app/scheduler/service.py:215–453`；`deps.py:189–213` |
| 历史的权威 | **checkpointer**（`memory` / `sqlite` / `postgres`），消息接口从 checkpoint 与运行事件读 | `packages/harness/deerflow/config/checkpointer_config.py:9` |
| 提示词控制 | **对角色扮演不友好**：lead agent 用固定模板，开头是「You are {agent_name}, an open-source super agent」；角色设定（`SOUL.md`）被 HTML 转义后放进 `<soul>` 数据块；用户输入被包进 `--- BEGIN USER INPUT ---` 标记并做 HTML 实体编码 | `packages/harness/deerflow/agents/lead_agent/prompt.py:662–672, 1029–1040` |
| 依赖与变化 | 22 MB、40+ 直接依赖（含 kubernetes、e2b、多个搜索 SDK）；本地资料记录两个月 1000+ 提交、54 个迁移 | 安装包实测；`deer-flow/DEERFLOW_UPDATE_2026Q4.md` |

**与 AgentScope v2 对比**：

| | AgentScope v2 | DeerFlow 全栈 |
|---|---|---|
| 多副本 | ✅ Postgres + Redis | ✅ Postgres + Redis，**启动闸门更严谨** |
| 排队 / 插话 | ✅（未发布） | ✅（2.3.0-dev，发布状态待确认）；插话会丢弃过期的工具计划，**更细** |
| 重新生成 / 编辑重生 | ✗ 要自建 | ✅ 原生（checkpoint 谱系） |
| 主动消息调度 | ◐ 单进程，要换 | ✅ 多实例、带租约 |
| 提示词完全受控 | ✅ 内核模板很薄，`on_model_call` 可整份替换 | ✗ 固定「super agent」模板 + 人设转义 + 输入标记；要么改走自定义图（网关能力是否保留**未核实**），要么在 `wrap_model_call` 里整份替换并逐个确认 20 个中间件不再注入 |
| 历史的权威 | 它的消息表 + `AgentState`（可以每回合重建） | checkpointer；重新生成依赖 checkpoint 谱系，**让我们的消息树做权威会和它的重生机制冲突** |
| 设计初衷 | 通用 agent 应用平台 | 任务型「超级 agent」（沙箱、子 agent、目标模式、todo） |
| 重量 | 中 | 重 |
| 团队熟悉度 | 无 | **job-come 已在用**，运维与排障经验可以复用 |

**结论**：DeerFlow 全栈是一个**真正的平台候选**，之前低估了它——平台层（多副本、插话、重生、调度）它在几项上比 AgentScope 更完整。它的问题集中在「这是为任务型 agent 写的」：提示词模板与输入包装是为安全的任务执行设计的，和角色扮演需要的「提示词完全由我们组装」正面冲突；历史以 checkpoint 为权威，与我们要的消息树冲突。

排序：**AgentScope v2 仍为主选**（提示词控制与历史可控是角色扮演的硬需求），**DeerFlow 全栈列为第二平台候选**，并加入一周验证：决定性的一项是「在网关路径下，能否把发给模型的提示词完全换成我们的组装结果，同时保留运行输入队列、插话、调度、流桥接」。如果能，它凭「平台更完整 + job-come 共用一套」可能反超。

## 5. C 层：角色扮演提示词引擎（SillyTavern 的设计）

SillyTavern 1.19.0，`/Users/gqli/work/SillyTavern`，提交 `06bde939`。以下是三路源码分析的提炼；出处到行号的原始报告留在调研记录里，本节只保留需要照着实现的语义。

### 5.1 许可与可用性

- AGPL-3.0（`LICENSE`、`package.json` 已确认）。第 13 条：修改后通过网络提供服务，必须向用户提供该程序的源码。
- **不能作为库**：核心逻辑（提示词组装、swipe、工具循环、群聊调度）在 `public/script.js` 等浏览器端文件里，绑定 jQuery、DOM 与模块级全局变量，没有可导入的无头 API。
- **作为独立服务也没有意义**：它的服务端只是文件存储加 API 密钥代理，不组装提示词，没有回合与锁。
- 结论：**只借鉴设计，洁净室实现。** 想法、数据形状、事件顺序不受版权保护；不要逐行移植代码，包括格式转换函数。

### 5.2 提示词块的默认顺序（Chat Completion）

| # | 块 | 默认角色 | 来源 |
|---|---|---|---|
| 1 | main（系统提示词） | system | 全局；角色卡 `system_prompt` 可覆盖，覆盖文本里 `{{original}}` 展开为全局原文 |
| 2 | 世界书（前） | system | 世界书 |
| 3 | 用户人设 | system | 人设，位置可配置 |
| 4 | 角色描述 | system | 卡片 `description` |
| 5 | 角色性格 | system | 卡片 `personality`，套格式模板 |
| 6 | 场景 | system | 卡片 `scenario`，套格式模板 |
| 7 | 增强定义 | system | 默认关闭 |
| 8 | 辅助提示词 | system | 默认空 |
| 9 | 世界书（后） | system | 世界书 |
| 10 | 对话示例 | system，带 `example_user` / `example_assistant` 名字 | 卡片 `mes_example`，按 `<START>` 分块 |
| 11 | 聊天历史 | user / assistant | 消息 |
| 12 | 历史后指令 | system | 全局；卡片 `post_history_instructions` 可覆盖 |

关键语义：**块的位置由用户配置的顺序决定，代码里的调用顺序只决定预算优先级。** 这让「位置」和「谁先被裁掉」可以分开配置。

### 5.3 token 预算

- 预算 = 模型上下文 − 最大回复长度 − 3（assistant 起始标记）− 工具定义。
- **必须完整放下、不裁剪的**：main、世界书前后、角色描述、性格、场景、人设、辅助、历史后指令、注入到 main 的扩展提示词、工具定义。放不下就**直接报错**（「必需提示词超出上下文」），不会悄悄截断人设。
- **按剩余预算填充的**：
  - 历史：**从最新往最旧**逐条前插，**遇到第一条放不下的就停**（不会跳过它去塞更旧、更短的）；工具调用与它的结果整组保留或整组丢弃。
  - 示例：按 `<START>` 整块，从最旧往新，整块放得下才放。
  - 顺序：默认先历史后示例；「固定示例」时先示例后历史。

对我们的启示：人设与世界书是「合同」，必须完整；历史是「尽量多」。这与我们上下文设计里的预算分配一致，只是要补上「必需部分超预算时报错而不是截断」。

### 5.4 按深度注入（in-chat injection）

很多角色卡依赖这个能力，必须支持。

- 一段提示词可以标记为「在聊天里第 N 条消息之前插入」，带角色（system / user / assistant）和顺序号。深度 0 = 最后一条消息之后；深度 N = 倒数第 N 条之前。
- 同一深度上：按顺序号从高到低分组；每组内按 system → user → assistant 各合并成一条消息。
- 用到它的：角色卡 `extensions.depth_prompt`（角色备注，默认深度 4、system）、作者注（默认深度 4）、世界书的「@深度」条目、会话摘要（默认深度 2）、人设（可选）。
- 注入的消息本身也计入后续深度的计数；比截止点更深的注入会随历史一起被裁掉。

### 5.5 世界书（World Info / Lorebook）

这是角色扮演里「按需记忆」的核心机制：条目平时不进提示词，聊天里出现关键词才激活。

**条目字段（要支持的）**：主关键词、次关键词与逻辑（任一 / 非全部 / 全不 / 全部）、正则关键词、大小写、整词匹配、常驻、概率、顺序号、插入位置与深度与角色、扫描深度、递归控制（不触发递归 / 不被递归触发 / 延迟到第 N 层递归）、定时效果（粘滞 sticky、冷却 cooldown、延迟 delay）、包含组（组名、组内权重、组覆盖、按命中数打分）、角色过滤、触发的生成类型、额外扫描来源（人设、角色描述、性格、场景、作者备注）。

**扫描算法**：

1. 预算 = 上下文总量 × 百分比（默认 25%），可设上限。
2. 收集条目：会话绑定的书 → 人设绑定的书 → 全局与角色的书（按策略合并：均匀 / 角色优先 / 全局优先），各自按顺序号降序；同一本书只处理一次。
3. 扫描文本 = 最近 N 条消息（默认 2，最新在前，带「名字: 」前缀）+ 勾选的卡片字段 + 标记为可扫描的扩展提示词 + 递归缓冲区。
4. 对每个条目按以下顺序判定，第一条适用的规则决定结果：
   - 已激活、本轮已掷骰失败、禁用、生成类型不符、角色过滤不符 → 跳过；
   - 延迟未到、冷却中（且不粘滞）→ 跳过；
   - 递归层级不符 → 跳过；
   - 常驻、粘滞中、被外部强制激活 → 激活；
   - 无关键词 → 跳过；
   - 主关键词任一命中，且次关键词满足逻辑 → 候选。
5. 候选排序（粘滞优先），按包含组筛选（组内只留一个：粘滞优先 → 打分最高 → 组覆盖 → 按权重随机）。
6. 逐个：掷概率；展开宏；累计 token 超预算则标记溢出、停止激活非「忽略预算」的条目。
7. 有新的可递归内容、未溢出、开了递归 → 把新内容加入递归缓冲区，再扫一轮；或未达最少激活数 → 扫描深度加 1 再扫。
8. 输出：按顺序号升序拼接，分发到各位置（世界书前、世界书后、作者注上下、@深度、示例前后、命名出口）。
9. 持久化粘滞与冷却状态（按会话、按条目）；重新生成时会重新掷骰。

### 5.6 作者注、人设、宏

- **作者注**：按会话保存；每隔 N 条用户消息插入一次（N=1 每轮都插，0 关闭）；位置默认「深度 4」。另有按角色的备注，可替换、前置或追加到会话备注。
- **人设**：用户自己的设定描述，位置可选：提示词内、作者注上下、按深度注入、不使用。
- **宏**：`{{char}}`、`{{user}}`、`{{persona}}`、时间日期、最近消息、变量等，在每次组装时展开（卡片字段、世界书关键词与内容、扩展提示词）。**用户消息在发送时展开一次并以展开后的文本保存**，历史不重复展开。

### 5.7 中文、阿拉伯语与多服务器下必须修掉的问题

这些是 SillyTavern 的实现缺陷，照搬会出 bug：

| 问题 | SillyTavern 的行为 | 我们的做法 |
|---|---|---|
| 整词匹配 | 用 `\W` 判断词边界，没有 Unicode 标志：中文、阿拉伯文的每个字都算「非单词字符」，整词匹配基本失效 | 中文默认子串匹配（「猫」命中「猫咪」通常是想要的）；阿拉伯语做规范化（去变音符、统一 alef/ya 写法）并处理粘连前缀（و、ال、ب） |
| 大小写与规范化 | 只做 `toLowerCase`，没有 Unicode 规范化 | 统一 NFKC；全角半角统一 |
| 摘要触发的字数统计 | 用 ASCII 正则数「词」，中文、阿拉伯语约等于 0 词，**按字数触发的摘要永远不触发** | 一律按 token 计 |
| 示例与群聊的名字分隔 | 只认半角冒号 `{{user}}:` | 同时认全角 `：`；名字含空格时不误切 |
| 正则关键词 | JavaScript 正则语法与标志 | 导入时校验并转换为 Python 语法；多租户下防 ReDoS（超时、复杂度限制） |
| 随机性 | 概率与组内随机用 `Math.random` | 用（会话 id + 消息序号）做种子，保证重新生成、重放可复现，并记录到日志 |
| 宏里的时间 | 浏览器时钟与语言区域 | 用用户的时区与语言区域 |
| 定时效果状态 | 存在会话元数据里，按 `chat.length` 计算 | 持久化到数据库，按会话与条目存；swipe 与重新生成要幂等 |
| 作者注与角色备注 | 存在客户端设置文件里，按卡片文件名做键 | 存数据库，按角色 id 做键 |

### 5.8 映射到角色卡 V2/V3 字段

| 卡片字段 | 引擎中的位置 |
|---|---|
| `description`、`personality`、`scenario` | 第 4、5、6 块 |
| `system_prompt` | 覆盖 main，`{{original}}` = 全局 main |
| `post_history_instructions` | 覆盖历史后指令 |
| `mes_example` | 对话示例，按 `<START>` 分块 |
| `first_mes` + `alternate_greetings` | 第一条助手消息及其备选（swipe） |
| `extensions.depth_prompt` | 按深度注入 |
| `character_book` | 角色绑定的世界书 |
| `creator_notes` | 不进提示词；可作为世界书扫描来源 |

V3 新增的 `creator_notes_multilingual`、`nickname`、`group_only_greetings`、世界书修饰符（`@@depth`、`@@position`、`@@activate` 等）对中英阿和群聊有用，导入要支持。

---

## 6. 数据模型（会话、消息、回合）

### 6.1 消息与候选回复（swipe）

SillyTavern 的做法：同一个助手位置上存多个候选回复，一个指针指向当前选中的；每个候选有自己的生成元数据；只把选中的那个发给模型；只有最后一个位置可以生成新候选；第一条消息的备选就是角色卡的 `alternate_greetings`。

建议表结构（Postgres）：

```
session(id, owner_id, role_id, title, locale, parent_session_id NULL, fork_message_id NULL,
        kind ['main'|'branch'|'checkpoint'], fence BIGINT, created_at, deleted_at NULL)

message(id, session_id, owner_id, seq BIGINT,            -- 会话内单调序号
        role ['user'|'assistant'|'system'|'narrator'], kind ['chat'|'action'|'proactive'|'tool_result'],
        turn_id NULL, active_variant_id NULL,            -- 只有助手位置用
        prompt_visibility ['include'|'hidden'|'ui_only'],
        content TEXT NULL,                               -- 用户消息直接存；助手消息看 variant
        display_content TEXT NULL,                       -- 可选：显示与提示词不同
        client_message_id NULL, created_at, deleted_at NULL,
        UNIQUE(session_id, seq), UNIQUE(session_id, client_message_id))

message_variant(id, message_id, variant_index, turn_id, content TEXT, reasoning TEXT NULL,
                interrupted BOOL, meta JSONB, created_at, deleted_at NULL,
                UNIQUE(message_id, variant_index))
```

- 重新生成 = 在最后一个助手位置插入新候选并设为当前，不再新建一条消息。
- 切换历史中间位置的候选，隐式使后续消息失效：只允许切换最后一个位置；或切换时自动建分支。
- 「从提示词里隐藏」用独立的 `prompt_visibility`，**不要像 SillyTavern 那样复用 `is_system`**（它因此不得不对工具消息做特殊处理）。

### 6.2 分支与存档点

- 分支 = 新会话，记录 `parent_session_id` 与 `fork_message_id`。首期直接复制分叉点之前的消息行（简单可靠），以后再考虑引用父会话的行。
- 存档点 = 同样结构，`kind='checkpoint'`，带用户命名。
- **用 id 关联，不用文件名**（SillyTavern 用文件名，改名或删除会留下悬空链接）。

### 6.3 回合与生成元数据

```
turn(id, session_id, owner_id, state, trigger ['user'|'proactive'|'regenerate'|'continue'],
     model, provider, prompt_version, prompt_hash, input_tokens, output_tokens, ttft_ms,
     started_at, finished_at, finish_reason, error_code)

turn_prompt_snapshot(turn_id, parts JSONB)   -- 各块的 token 数与来源（世界书激活了哪些条目），
                                              -- 不存原文或按保留策略清理；用于排查「为什么模型这样回答」
```

SillyTavern 把每条消息实际发送的提示词明细存在浏览器 IndexedDB，服务端看不到。我们放在服务端，用于排查与审计。

### 6.4 工具调用与确认（满足 H5）

不用 LangGraph 的 `interrupt()`（它要求把图状态存进 checkpointer，形成第二个权威）。做法：

1. 模型请求有副作用的工具 → `wrap_tool_call` 中间件不执行，写一行 `tool_confirmation(id, turn_id, tool, args, args_fingerprint, status='pending', expires_at)`，向客户端发确认事件，**回合正常结束**（助手回复「我需要你确认一下……」）。
2. 用户确认 → 任意服务器收到请求 → 执行工具（参数指纹必须一致）→ 写入执行结果消息（`kind='action'`）→ 发起一个新回合，让模型基于结果继续。
3. 拒绝或过期 → 写入结果消息，不执行。

工具调用记录：`tool_call(id, turn_id, tool, args_fingerprint, status, result_chars, latency_ms, signature NULL, reasoning NULL)`。`signature` 与 `reasoning` 来自 SillyTavern 的经验：部分模型要求在后续回合回放推理签名。

### 6.5 不要照搬的

| SillyTavern 的做法 | 为什么不行 |
|---|---|
| 每次保存重写整个聊天文件、客户端防抖保存 | 多服务器下必然互相覆盖；我们按行追加与更新 |
| 浏览器持有完整聊天并整体推送 | 服务端必须是权威，客户端只发意图 |
| 提示词组装与工具循环在浏览器里 | 工具必须在服务端、经过确认门 |
| 完整性 UUID + 让用户输入 `OVERWRITE` | 用行版本、条件更新、会话锁 |
| 停止生成后保留部分回复但不做标记 | 我们要标记中断 |
| 浏览器定时器做自动模式、主动消息 | 必须是服务端调度器 |
| 群聊发言人选择用不带种子的随机 | 要可复现、记日志 |

### 6.6 值得照搬的事件顺序

SillyTavern 的生成事件可以直接作为我们会话层与 harness 之间的钩子点：

```
turn.started → input.commands（可短路）→ user_message.persisted
→ context.interceptors(messages, budget, abort)   # 记忆、摘要、世界书在这里注入，可中止
→ lore.activated → prompt.ready(messages)（可改）→ request.ready(payload)（可改）
→ stream.token → assistant_message.persisted → turn.ended | turn.stopped
旁路：message.edited / deleted / variant_switched、tool.performed
```

- 拦截器按配置顺序执行，任一可中止。
- 工具按请求动态决定是否注册（`shouldRegister`），用于按角色、按会话开放的 skill 与 MCP 工具。
- 「静默工具」：有副作用但不触发后续生成（例如「设置心情」）。
- 工具循环有轮数上限（SillyTavern 默认 5）。

---

## 7. D 层：记忆

### 7.1 三种记忆，三种机制

| 记忆 | 机制 | 是否需要 embedding |
|---|---|---|
| 本会话的情节 | 滚动增量摘要，按深度注入 | 否 |
| 设定、人物关系、地点等 | 世界书（关键词触发） | 否 |
| 跨会话的用户事实与偏好 | 长期记忆库（抽取 → 存储 → 召回） | 可选 |
| 久远对话片段的语义召回 | 向量检索 | 是（远程网关） |

### 7.2 会话摘要：照搬与修正

照搬 SillyTavern 的「原始增量」模式：
- 系统提示词只放摘要指令；用户内容 = 上一版摘要 + 新增消息（`名字:\n内容`）；
- **排除最新一条**（它可能还会被 swipe）；
- 受 token 预算与单次最多消息数双重限制；
- 指令要点：最重要的事实与事件、以已有摘要为基础扩展、长度上限、只输出摘要；
- 双触发：距上次摘要 N 条消息，**或** token 量达到阈值（不用字数）；
- 冻结开关、手动编辑、恢复上一版；
- 生成期间会话有变化（新消息、编辑）则丢弃结果。

修正：
- **存独立的版本表**，不要存在消息的 `extra` 上（SillyTavern 只在编辑最后一条消息时失效摘要，编辑更早的消息不会使已有摘要失效；分支会继承过期的摘要）。
- 规则：编辑或删除 `upto_message_id` 及之前的任一消息 → 标记失效 → 从上一版有效摘要重建。
- **由服务端后台任务触发**，不依赖客户端在线。
- 不用「经典模式」（把整份角色扮演提示词重新发一遍再要求总结）：贵，且会混入人设指令。

### 7.3 向量召回（可选，pgvector）

数据库不再受限后，向量直接放 Postgres：

```
memory_vector(id, app, owner_id, session_id NULL, source_type, source_id, chunk_idx,
              content_hash, model, dim, embedding vector(N), text, created_at)
INDEX (app, owner_id, model); ivfflat 或 hnsw 索引
```

照搬 SillyTavern 的同步方式：按内容哈希做差集，新增的嵌入、消失的删除；编辑与 swipe 产生新哈希，自然替换。修正：
- 哈希用 SHA-1 或全文，不用它的 53 位哈希（短消息会误合并）；
- 分数阈值作用在真正使用的结果上（它的服务端有一个阈值对聊天消息不生效的 bug）；
- 排除已经在历史窗口里的最近消息；
- 嵌入在后台任务里做，不在生成路径上（它在首次生成时同步嵌入，用户要等）；
- 模型名进键，换模型即换索引。

embedding 走 LiteLLM 网关（H3）。网关是否提供 embedding 模型尚未验证，需要一次小的调用确认。

### 7.4 长期记忆的后端

接口保持可替换（已有 `MemoryPort` 规范与一致性测试）。数据库放开后的选项：

| 选项 | 存储 | embedding | 评价 |
|---|---|---|---|
| 自建 | Postgres + pgvector | 网关 | 首选：与其他数据同库，删除与注销一致 |
| LangMem | LangGraph `BaseStore`（官方有 Postgres store） | 网关 | 与 A 层同生态；后台记忆管理器的模式值得借鉴 |
| mem0 | pgvector 可用 | 网关（支持 `openai_base_url`） | 成熟；多一套抽取逻辑 |
| Memobase | Postgres + Redis | 可完全不用 | 画像 + 时间线模式好；最近更新在 2026-01，维护节奏是风险 |

### 7.5 记忆的隔离粒度（需要产品决定）

成熟产品普遍按（用户, 角色）隔离：Talemate 的「角色只知道它亲历或被告知的」，MemOS 的 cube，LangMem 的 namespace。我们现在按（应用, 用户）隔离，即 A 角色听到的事 B 角色也知道。

---

## 8. 存储选型

| 用途 | 选择 | 理由 |
|---|---|---|
| 会话、消息、候选、回合、队列、确认、摘要、世界书、角色、记忆、向量 | **Postgres + pgvector** | 一个库覆盖关系数据与向量；JSONB；`SKIP LOCKED` 做任务认领；LangGraph、LangMem、mem0 都有官方 Postgres 支持 |
| 会话锁、围栏号、控制流、SSE 事件流、调度唤醒、限流 | **Redis** | 低延迟、Stream、Lua 原子判定；丢了可以重建，不存权威数据 |
| 图片、附件 | 对象存储 | |

**不用 LangGraph checkpointer 作为会话存储**，即使数据库是 Postgres：
- 消息表要支持 swipe、分支、编辑、删除、隐藏、分页、注销清理；checkpoint 是线性的图状态快照，按它的格式做这些很别扭；
- 两份历史（消息表与 checkpoint）会不一致；
- 每回合无状态重建，任何服务器都能处理，checkpoint 带来的「恢复中断的图」我们用确认表 + 新回合实现了。

以后如果出现「单个长任务中途暂停、等人、恢复，中间状态重算代价高」的功能，再只对那个功能单独开 checkpointer。

---

## 9. 推荐架构

```
Android ──HTTP/SSE──▶ API（FastAPI，无状态，多副本）
                          │
                          ▼
              ┌──── 会话层（B，自建）─────────────────────────┐
              │ 提交判定（排队/合并/插话，Redis Lua）           │
              │ 会话锁 + 围栏号、控制流、SSE 事件流（Redis）     │
              │ 调度器：主动消息到点入队（多副本去重）           │
              │ 确认表：工具确认 → 执行 → 新回合                │
              └───────────────┬───────────────────────────────┘
                              │ 每回合
                              ▼
              ┌──── 上下文组装 ────────────────────────────────┐
              │ C 层：角色卡 + 世界书扫描 + 作者注 + 人设        │
              │      + 示例 + 按深度注入 + token 预算           │
              │ D 层：会话摘要（深度注入）+ 长期记忆召回         │
              │      + 可选向量召回                            │
              │ 历史窗口（按回合，只取已完成回合的当前候选）      │
              └───────────────┬───────────────────────────────┘
                              │ messages + system
                              ▼
              ┌──── A 层：PydanticAI（无状态，历史由我们传入）───┐
              │ before_model_request：注入组装好的请求          │
              │ AgentRun.enqueue：插话（会话层从 Redis 收件箱    │
              │   读到新消息后调用）                           │
              │ AgentRun.cancel：取消（保留已完成部分）          │
              │ requires_approval：确认门 → 延迟工具请求        │
              │ 工具白名单、授权、审计（capability / hooks）     │
              │ MCPToolset、Skill（按会话/角色动态注册）         │
              └───────────────┬───────────────────────────────┘
                              │ LiteLLM 网关（多模型、embedding）
                              ▼
  Postgres + pgvector（唯一权威）      Redis（控制面，可重建）

后台任务（同一套代码，独立进程）：会话摘要、记忆抽取、向量同步、过期确认、注销清理
语音：LiveKit agent 的 llm_node 调用同一个「上下文组装 + A 层」
```

关键边界：**A 层只看到「这一回合要发什么」**，不知道会话、swipe、分支、主动消息。

上图按路线三（PydanticAI + 自建会话层）画，便于看清各层边界；**主选是路线一**。各路线的差别：
- **路线一（AgentScope v2，主选）**：「会话层」框里的会话锁、排队、插话、取消、SSE 续传、审批挂起与恢复由 AgentScope App 层提供；调度器换成我们自己的（到期表 + 选主租约），复用它的收件箱与唤醒路径；「A 层」换成 AgentScope 内核，提示词注入走 `on_model_call` / `on_system_prompt`。
- **路线二（Agno + AgentOS）**：审批、SSE 续传、取消、调度器由 AgentOS 提供；插话与前台运行的会话锁要自建。
- **A 层换成 `create_agent`**：插话改用 `before_model` 钩子读收件箱自建；确认门在 `wrap_tool_call` 里自建（不用需要 checkpointer 的内置人工确认）；语音可以用官方 LiveKit 插件。
- 「上下文组装」（C、D 层）三条路线完全相同，是我们自己的模块。

所以 C、D 层与数据模型（第 5–7 节）可以先开工，不用等路线决定。会话层（第 4.3 节）在路线三下也要自建，同样可以先按 AgentScope App 层的结构开工。

---

## 10. 风险

| 风险 | 影响 | 应对 |
|---|---|---|
| C 层工作量被低估 | 世界书算法、按深度注入、预算、宏、V3 修饰符，加中阿适配，是这个产品最大的自建模块 | 先做规格与测试用例（用真实角色卡），再实现；首期可以不做递归、包含组、定时效果 |
| 回合引擎 API 变化（PydanticAI 小版本 2–5 天一个；Harness 是 0.x） | 升级成本 | A 层只放一个适配器；插话、取消、确认通过我们自己的接口调用框架；Harness 只取需要的部分（或自己实现 skill 与压缩） |
| 平台层自建的正确性 | 会话锁、队列、SSE 续传、调度出错会直接表现为丢消息、重复回复 | 参照 AgentScope App 层的结构；多副本集成测试（两个进程 + Redis + Postgres）列为必须 |
| 网关不提供 embedding | 向量召回不可用 | 先做不依赖 embedding 的三种记忆（摘要、世界书、长期记忆的词法召回） |
| AGPL 污染 | 法律风险 | 只看设计文档与本文提炼的规格；实现者不对照源码逐行翻译 |
| 摘要质量 | 情节丢失、人设漂移 | 摘要提示词版本化，用评测集比较 |
| 多语言的世界书匹配 | 误触发或不触发 | 每种语言准备匹配用例 |

---

## 11. 待决定

1. **选路线：一周验证，以路线一为主。**

   **(a) AgentScope v2（主选，路线一）**，固定 `main` 的一个提交，两个进程 + Redis + Postgres：
   - **消息树做权威**：我们的候选（swipe）与分支表 + 继承 `ChatService`、每回合按当前活动分支重建 `AgentState.context`；验证重新生成、切换候选、从中间分叉后，它的 `messages` 表与 `context` 不会和我们的表打架；
   - **提示词完全受控**：`on_model_call` 整份替换 `messages` 与 `tools`，关掉 `inject_runtime_state` 等追加内容；抓包确认发给网关的就是我们组装的那一份；
   - **多副本**：排队、插话、跨服务器取消、SSE 续传、审批在另一个进程恢复；
   - **本地文件**：换掉 Offloader 后，应用节点磁盘上不写任何东西；
   - **共享角色**：系统账号拥有的 agent + 自定义访问策略，普通用户能用、不能改；
   - **合并模式**：在中断 + 重新入队上实现「首 token 前中止重来」需要改多少；
   - **关掉不用的内核能力**（压缩、计划、迭代上限）后没有副作用；
   - **LiveKit**：`llm_node` 能否拿到 token 流；
   - **版本**：排队与插话进入正式版本的时间。

   **(b) PydanticAI 最小原型（退路，路线三）**，只做 A 层：`AgentRun.enqueue` 插话、`cancel()`、`requires_approval` 跨进程恢复、`before_model_request` 改写、LiteLLM 多模型流式。目的是在 (a) 不通过时，退路已经验证过，不用再花一周。

   判定：
   - (a) 通过 → **路线一**。
   - (a) 的「消息树做权威」或「提示词完全受控」不通过 → **路线三**，会话层参照 AgentScope App 层实现（Apache-2.0，可保留声明后借用代码）。
   - (a) 只有版本问题 → 先跟固定提交开发，正式版本出来后再升级。
   - 路线二（Agno）只在 (a)、(b) 都不理想时再评估。

   **(c) DeerFlow 全栈对照**（与 (a) 并行，半周即可）：在网关路径下，把发给模型的提示词整份换成我们的组装结果（自定义图，或 `wrap_model_call` 替换系统消息与输入包装），确认运行输入队列、插话、调度、流桥接仍然可用；再看重新生成能否和我们的消息树共存。通过则与 (a) 比较，重点权衡「平台更完整 + job-come 共用」与「更重、为任务型 agent 设计」。

2. **记忆是否按角色隔离**（7.5）。
3. **是否做 swipe（换一个回答）与分支**（6.1、6.2）。做的话，消息表从一开始就按候选结构设计。
4. **世界书首期范围**：建议首期只做主次关键词、常驻、插入位置与深度、顺序号、预算；递归、包含组、定时效果、概率放二期。
5. **群聊**：是否在路线图上。影响消息的发言人字段与提示词里的名字前缀。
6. **用户能否编辑角色卡里的世界书**：影响正则关键词的安全处理（ReDoS）。
7. **网关 embedding 验证**：需要批准一次小的调用。
