# 主脑框架选型复核：DeerFlow 是否适合

日期：2026-11-09
状态：分析结论，待决定
范围：只评估「一次回合内，模型如何调用、如何用工具」这一层。回合控制、消息状态、多副本、主动消息不在框架里，见 §2。

## 1. 结论

**DeerFlow 适合 job-come 那类任务型 agent，不适合作为浅聊（角色扮演）的主脑框架。建议改用 LangChain 的 `create_agent`（DeerFlow 自己就建在它之上），保留现有全部中间件与回合控制。**

理由一句话：我们为了把 DeerFlow 用在浅聊上，已经关掉了它几乎全部的能力，剩下的部分 LangChain 本身就提供；而它带来的依赖、版本风险和隐藏行为是实打实的成本。

这不是推翻已有工作：迁移的改动面只在 `adapters/brain/` 两个文件（共 345 行），回合控制、消息、SSE、工具授权、确认、记忆都不受影响。

## 2. 先厘清：哪些需求根本不归框架管

你担心的几项，在我们的架构里都不由主脑框架承担：

| 需求 | 由谁负责 | 与 DeerFlow 的关系 |
|---|---|---|
| 多服务器部署 | 回合无状态 + MySQL 权威 + Redis 锁与事件流 | 无。我们不用 checkpointer，图每轮从头跑 |
| 消息的各种状态（排队、合并、插话、中断、撤回、确认） | `chat_message`、`chat_queue`、`chat_turn`、`action_confirmation` 表；Redis Lua 判定 | 无。只有「插话」用到图内的 `before_model` 钩子，那是 LangChain 的标准钩子 |
| 定时主动对话 | `app/proactive/`（调度、策略、循环）通过 `conversation.start_turn` 发起回合 | 无。主动消息就是一个由服务端发起的普通回合 |
| 角色扮演 | 提示词分层（平台、角色、方法……）+ 历史窗口 + 会话摘要 | 无。系统提示词由我们的 `PromptMiddleware` 每轮写入 |
| 语音 | LiveKit agent 重写 `llm_node` 调用主脑 | 只依赖 `BrainPort` 接口，不依赖 DeerFlow 本身 |

所以选型问题收窄为：**一次回合里调模型、跑工具、挂中间件，用 DeerFlow 工厂还是用 LangChain `create_agent`。**

## 3. 实测：我们从 DeerFlow 用了什么

核实于当前代码与已安装的 `deerflow-harness 2.3.0-dev`。

### 3.1 引用面

全部 DeerFlow 引用只有 5 处，集中在 `adapters/brain/`：

| 引用 | 用途 | LangChain 是否已有 |
|---|---|---|
| `create_deerflow_agent` | 建图 | 有：`langchain.agents.create_agent` |
| `RuntimeFeatures` | 功能开关，我们关掉了沙箱、记忆、摘要、子 agent、视觉、标题、护栏 | 不需要：不装就是关 |
| `Next` / `Prev` | 中间件排序锚点 | 不需要：`create_agent` 按列表顺序执行 |
| `SystemMessageCoalescingMiddleware` | 仅作为锚点目标 | 去掉锚点后不需要 |
| `ToolErrorHandlingMiddleware` | 仅作为锚点目标 | 去掉锚点后不需要；工具报错要转成 `ToolMessage`，需要我们自己写一个小中间件（约 30 行） |

### 3.2 我们的五个图内中间件都是标准 LangChain 中间件

`PromptMiddleware`、`ToolVisibilityMiddleware`、`SteerMiddleware`、`ToolAuditMiddleware`、`ToolAuthorizationMiddleware` 都继承 `langchain.agents.middleware.AgentMiddleware`。

已实测：把这五个直接交给 `create_agent`，图能正常构建并返回回复；节点只剩 `model`、`tools`、`SteerMiddleware.before_model`。

### 3.3 DeerFlow 即使全关也会塞进来的东西

全部功能关闭时，工厂建出的图仍有这些节点：

| 中间件 | 作用 | 对我们 |
|---|---|---|
| `DurableContextMiddleware` | 从图状态读目标、摘要、委派记录、skill，注入隐藏消息 | 没有 checkpointer 时状态为空，**直接返回原请求，无效果**。但它在每次模型调用的路径上，DeerFlow 升级若改变行为，会悄悄影响我们的提示词 |
| `ClarificationMiddleware` | 模型调用 `ask_clarification` 时中断图，等待用户 | 与「非交互、回合内不中断」冲突。我们靠 `ToolVisibilityMiddleware` 过滤掉该工具、并在上下文里设 `interaction_mode=autonomous` 兜底，是**在绕过它** |
| `LoopDetectionMiddleware` | 检测重复工具调用（1000 行） | 有用，但浅聊工具很少，简单的「同一工具同一参数连续 N 次就停」约 40 行即可 |
| `TokenBudgetMiddleware` | 单次运行的 token 上限（388 行） | 有用；我们的上下文预算在组装阶段已经控制（上下文设计 §6），回合级上限约 30 行即可 |

### 3.4 依赖与版本成本

- 版本：`deerflow-harness==2.3.0.dev0`，开发版，从本地 wheel 安装，没有稳定发布线。
- 体积：22 MB，770 个 Python 文件。
- 直接依赖 40 余个，包括 `kubernetes`、`e2b-code-interpreter`、`agent-sandbox`、`duckdb`、`langgraph-api`、`langgraph-cli`、`langgraph-checkpoint-sqlite`、`aiosqlite`、`firecrawl-py`、`tavily-python`、`exa-py`、`ddgs`、`langfuse`，以及 Anthropic、Google、DeepSeek 三家模型 SDK。浅聊一个都不用。
- 已经踩过的坑：`mcp` 2.x 让 deerflow 导入失败，被迫锁 `mcp==1.30.0` 与 `langchain-mcp-adapters==0.2.2`（清单 2.9）。DeerFlow 锁住的版本会传导成我们整个依赖树的约束。
- 安全面：依赖越多，供应链审计与漏洞修复的范围越大，且其中不少是联网、执行代码类的库。

## 4. 场景逐项对照

| 场景需求 | DeerFlow | LangChain `create_agent` |
|---|---|---|
| 系统提示词完全自控、每轮重算 | 可以，靠我们的中间件覆盖其占位提示词 | 可以，同一个中间件 |
| 原生多轮 messages，无状态 | 可以，但其内部中间件按「线程 + checkpoint」设计（如 `DurableContextMiddleware`、`genuine_user_turn_id` 的旧版兼容逻辑），我们必须满足它的消息约定（上下文设计 §10.1.3） | 可以，约定只有 LangChain 的消息类型 |
| 回合内插话（steer） | 可以，`before_model` 钩子 | 同一个钩子 |
| 工具白名单、授权、确认、审计 | 可以，我们自己的中间件 | 同 |
| 回合内绝不中断等人 | 要绕过强制的 `ClarificationMiddleware` | 不存在这个问题 |
| 流式（`stream_mode="messages"`） | 可以 | 同（都是 LangGraph） |
| 多模型（LiteLLM 网关） | 我们自己构造 `ChatOpenAI` | 同 |
| 可预测性：升级不改变提示词 | 风险：隐藏中间件随版本变化 | 只有我们装的中间件 |
| 依赖与锁版本 | 重，开发版 | 轻，`langchain` + `langgraph`，我们已经在用 |
| 将来需要长任务（子 agent、沙箱、checkpoint） | 强项 | 需要自建，或对那个功能单独用 DeerFlow |

## 5. DeerFlow 真正适合的地方

job-come 的面试、简历审阅那类 agent：多步骤、要读文件、调多个 MCP 工具、要子 agent 委派、可能要沙箱执行、单次运行时间长、需要中途恢复。这些正是 DeerFlow 的 lead agent、skills、子 agent、checkpoint 的用武之地。job-come 继续用 DeerFlow 是合理的。

浅聊的回合是「短、频繁、强人设、低工具、强实时」，几乎用不到这些。

## 6. 不选的其他方案

| 方案 | 不选的原因 |
|---|---|
| 直接调 LiteLLM，自己写工具循环 | 要重写流式、工具调用解析、并行工具、错误处理；`create_agent` 已经做好，且与现有中间件兼容 |
| LangGraph 手写 StateGraph | 可行但没必要；`create_agent` 就是一个预制的 StateGraph，需要时可以下沉 |
| 其他 agent 框架（如 PydanticAI、OpenAI Agents SDK） | 要重写全部五个中间件与流式适配，收益不明确 |

## 7. 迁移方案（如果决定换）

改动只在 `adapters/brain/`：

1. `build_turn_graph` 改用 `create_agent(model, tools, system_prompt=占位, middleware=[...])`，中间件顺序按列表写死：
   `PromptMiddleware → ToolVisibilityMiddleware → SteerMiddleware → ToolAuthorizationMiddleware → ToolAuditMiddleware → ToolErrorMiddleware → TurnBudgetMiddleware → LoopGuardMiddleware`
2. 去掉 `@Next` / `@Prev` 锚点。
3. 新增三个小中间件：工具报错转 `ToolMessage`、回合 token 上限、重复工具调用保护。
4. 移除 `default_features` 与 `ask_clarification` 相关的过滤与兜底（问题不再存在）。
5. `pyproject.toml` 去掉 `deerflow-harness`；`mcp` 与 `langchain-mcp-adapters` 的锁版本按我们自己的需要重新评估。
6. `config/deerflow/` 目录不再需要。

验证：现有的脚本化模型测试（工具路由、确认流程不执行副作用工具、合并竞态、插话）全部原样跑；外加一次真实网关冒烟。

风险：DeerFlow 的工具错误处理覆盖了较多边界情况（856 行），我们的简化版要用测试覆盖「工具抛异常、超时、返回非字符串」三类。

## 8. 第二轮：更大范围的选型（2026-11-09）

前提修正：我们确实需要框架，因为后面要接 skill、tool、MCP、记忆、会话管理。所以这一轮问的不是「要不要框架」，而是「哪个框架承担哪一层」。

调研分三路，前两路已完成：
- 本地框架资料（`docs/` 下 40 余个框架的架构笔记，以及 `框架对比/` 系列）：评分表；
- GitHub 上的角色扮演、陪伴类与记忆项目：是否能作为库或服务集成；
- SillyTavern 源码：用户正在下载，待补（§8.5）。

### 8.1 框架评分（摘要）

全量评分表与出处由本地调研产出，以下只列结论。出处均为 `/Users/gqli/work/deepagents/docs/` 下的路径。

| 候选 | 能否无状态传入历史 | 插话 | 钩子 | 工具确认不阻塞进程 | MCP / Skill | 记忆 | 多服务器就绪 | 依赖 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| **LangChain `create_agent`**（1.4.9，MIT） | 能，checkpointer 可选，我们已经这样跑 | 我们的 `SteerMiddleware`（`before_model`）原样可用 | 模型前后、包裹模型调用、包裹工具调用；五个中间件已实测可用 | 自带的 HITL 依赖中断加 checkpoint，**不用**；保留我们自己的授权与确认 | `langchain-mcp-adapters`；Skill 可移植 deepagents 的 `SkillsMiddleware` | 无内置长期记忆，走我们的 `MemoryPort` | 无隐藏状态 | 轻，已在用 | **首选** |
| **Microsoft Agent Framework**（Python 1.21.0） | 能，`SessionStore` 可插拔，核心明确不做跨进程一致性，由应用负责 | 自带消息注入中间件 | agent 层、工具层、ContextProvider；「每次模型调用前」的钩子未在资料中确认 | 资料中最严谨的审批状态机（含重放保护） | 有 / 有 | mem0、redis 等 provider | 由应用加锁，与我们一致 | 模块化，总量未核实 | **备选** |
| AgentScope v2 | 能，`Agent(state=…)` 每轮重建 | 无一等 API，近似 `InboxMiddleware` | 7 个钩子 | `PermissionEngine` 发确认事件后挂起，事件恢复 | 有 / 有 | 外接 mem0、ReMe | App 层用 Redis 总线（会话锁、收件箱、SSE 续传、唤醒队列），与我们几乎一一对应；但 Offloader 写本地文件 | 未核实 | **最佳参考设计**，不作依赖（v2 仍在大改） |
| OpenAI Agents SDK（0.17.x） | 能，传入输入列表 | 无，只能取消重跑 | 只能观察，不能改写模型请求 | `needs_approval` + 可序列化 `RunState`，契合度好 | 有 / 仅沙箱内 | 仅沙箱内 | 会话后端有 Redis、SQLAlchemy | 轻 | 不选：无插话、无改写钩子，压缩绑定 Responses API |
| Agno（3.1.12） | 依赖数据库，DB 不可用则运行失败 | 未覆盖 | pre/post/tool hooks | 审批表只支持 Postgres、SQLite，**不支持 MySQL** | 有 / 有 | LLM 驱动的记忆管理，无向量 | **同一会话没有锁**，并发运行会交错 | 重 | 不选：与我们的 MySQL 权威重复，且缺锁 |
| DeerFlow（2.3.0-dev） | 能，但内置中间件按线程与 checkpoint 设计 | 2.3.0 有原生插话，但在网关与 lead agent 链上、存 Postgres，**SDK 工厂路径没有** | 钩子加锚点 | `ClarificationMiddleware` 强制追加在最后 | 强 / 强 | DeerMem，`memory.json` | 多实例**要求 Postgres 加 Redis 流桥接**，否则拒绝启动 | 22 MB、40 余依赖；两个月 1000+ 提交、54 个迁移 | 不选（浅聊）；**job-come 继续用** |

不入围的框架、理由与出处，见本地调研报告：
- 编码 CLI：Codex、OpenCode、Claude Code；
- 仅 TypeScript：Pi、TanStack AI；
- 单机本地状态：Hermes、nanobot、CowAgent、OpenHarness；
- SOP 多角色编排：MetaGPT、crewAI，资料明确不建议用于低延迟对话；
- smolagents 没有会话层；
- PydanticAI 在本地资料中没有分析，未评分。

### 8.2 GitHub 同类项目（摘要）

观察日期 2026-11-09，星数为近似值。

- **能作为库或服务集成的**（Python、宽松许可、服务端、多租户）：mem0、Memobase、MemOS、LangMem、Graphiti、LiveKit Agents。
- **只能参考设计的**：
  - 许可证限制：RisuAI（GPL）、Agnai（AGPL）、Talemate（AGPL）、MaiBot（GPL）；
  - 桌面优先或许可不清：AIRI、Open-LLM-VTuber、KouriChat、memU。
- **完整的 agent 运行时只有 Letta**：它自带循环、状态模型和 Postgres + pgvector，会替换掉我们的回合层，而不是嵌进来，而且产品方向仍在变化。不选。
- **主动消息**：没有任何项目提供可复用的服务端多租户调度器，这部分要我们自己做（现有 `app/proactive/`）。

### 8.3 记忆的新选项（补充到 `chat-agent-memory-selection.md`）

不下载模型、能落地的路线，按与现有栈的贴合度排序：

1. **自建，全部在 MySQL**：滚动摘要（会话摘要已设计）、结构化画像、世界书关键词匹配，模型调用走 LiteLLM。向量召回以后再按需接远程 embedding。这是 RisuAI SupaMemory、Memobase 的模式。
2. **Memobase 自托管**：画像 + 时间线；可以 `enable_event_embedding: false` 完全不用 embedding。要新增 Postgres。风险是最后一次提交在 2026-01。
3. **mem0 自托管**：embedding 走 LiteLLM 网关（支持 `openai_base_url`），但需要向量库（Qdrant、pgvector 或 Redis Stack）。普通的共享 Redis 不够。
4. MemOS（Neo4j + Qdrant）、Graphiti（Neo4j/FalkorDB，且有自定义 base_url 产生 NaN embedding 的未解决问题）：太重。

托管服务（mem0 云、Zep 云、MemOS 云）都意味着把用户聊天发给第三方，需要单独做合规决定。

### 8.4 成熟角色扮演产品收敛出的模式（值得照搬的设计）

- **提示词结构**：系统 → 卡片字段（描述、性格、场景）→ 按位置或深度插入的世界书 → 摘要与记忆 → 历史 → 历史后指令。Character Card V3 已把这些形式化（`insertion_order`、`token_budget`、`scan_depth`、递归扫描、`@@depth`/`@@position` 修饰符）。V3 还新增多语言 `creator_notes_multilingual`，对中英阿有用。**建议导入支持 V3，导出保持 V2 兼容**（`domain/roles/card.py` 已能导入 V3）。
- **分层记忆**：递归滚动摘要 + 关键词世界书 + 结构化画像，向量或图召回只作为补充。抽取都在回合外异步做，每次固定调用次数。与我们的上下文设计和 hook 设计一致。
- **消息树**：每条消息可分叉，「换一个回答」（swipe）是同一父节点下的备选。建议 MySQL 加 `parent_id` 与「当前活动叶子」指针，摘要按消息区间引用。**这一条需要确认产品是否要做「换一个回答」与分支**。
- **按（用户, 角色）隔离记忆**：Talemate 的「角色只知道它见过的」、MemOS 的 cube、LangMem 的 namespace，都是同一个思路。我们现在的记忆按（应用, 用户）隔离，**没有按角色分**。这是一个需要你决定的产品问题：用户告诉 A 角色的事，B 角色该不该知道。

### 8.5 SillyTavern（待补）

源码由用户下载，下载完成后补充：提示词组装顺序与 token 分配、世界书触发规则、Summarize 与 Vector Storage 扩展、聊天文件格式（swipe、分支、群聊）、工具调用与扩展钩子、多服务器下的问题。

许可证需要核实（预期是 AGPL-3.0）。如果是 AGPL，**只能借鉴设计，不能把代码拷进闭源服务端**。

### 8.6 第二轮结论

1. **主脑框架：LangChain `create_agent`**，保留我们的中间件、回合控制与确认流程。第二轮没有找到更合适的；备选是 Microsoft Agent Framework。
2. **分层分工**：
   - 框架层（`create_agent` + 中间件）：一次回合内的模型、工具、MCP、skill、插话、授权、审计。
   - 我们的平台层（MySQL + Redis）：会话、消息状态、队列、合并、确认、上下文组装、会话摘要、主动消息。任何框架都不提供这一层的多服务器版本，这一点在三路调研里一致。
   - 记忆层（`MemoryPort` + hook 协议）：后端可替换，先自建 MySQL 方案。
3. **向 AgentScope v2 的 App 层借设计**：它的会话锁、收件箱、SSE 续传、唤醒队列、调度器、存储与总线分离，和我们的回合层几乎一一对应，可以拿来逐项核对我们的实现有没有漏项。
4. **角色扮演的提示词与记忆**：照搬 Character Card V3 与世界书语义，等 SillyTavern 分析补完后定稿。

## 9. 待决定

1. **是否换掉 DeerFlow**：建议换。如果保留，至少要把 `ClarificationMiddleware` 与 `DurableContextMiddleware` 的行为写成回归测试，防止升级时悄悄改变。
2. **项目层面的影响**：之前的方向是「DeerFlow 作为两个产品共同的主脑」。换成 `create_agent` 后，浅聊与 job-come 的共同点是 LangChain 中间件这一层（工具授权、审计、记忆 hook），而不是同一个工厂。这需要你确认可以接受。
3. **记忆是否按角色隔离**（§8.4）：用户告诉 A 角色的事，B 角色该不该知道。
4. **是否做「换一个回答」与对话分支**（§8.4）：决定消息表要不要改成树结构。
5. **许可证核实**：LangChain 1.4.9、LangGraph 1.2.20 已从安装元数据确认为 MIT；DeerFlow 的 wheel 元数据里没有填写许可证；其余候选未核实，采用前逐个核对。
