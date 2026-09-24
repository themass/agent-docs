# Deep Agents 框架完整设计方案（深度归档）

> **本文目标**：将 LangChain Deep Agents (`libs/deepagents`) 从「零散源码」整理成可学习的**完整设计方案、思想与原理**，涵盖 SDK、dcode/CLI、App 三层架构（包括 deepagents-cli 与 deepagents-code 的分工）。  
> **参考 DeerFlow 文档范式**：采用 DeerFlow Harness 的深度归档风格（见 `deer-flow/backend/docs/DEERFLOW_FRAMEWORK_QA_ARCHIVE.md`），但聚焦于 **Deep Agents 原生设计**。  
> **维护**：新增问答请在文末 [追加记录](#第十五章-追加记录) 按日期追加；重大设计与代码变更请同步更新前文并标注日期。

---

## 阅读地图

| 章节 | 内容 |
|------|------|
| [〇、文档说明与学习目标](#〇文档说明与学习目标) | 怎么读本文、学完应建立什么心智模型 |
| [一、设计思想总论](#一设计思想总论) | Deep Agents 的核心取舍与范式；含 **§1.6 不变量** |
| [二、分层与运行时](#二分层与运行时) | SDK / CLI / App 三层架构 |
| [三、状态与消息](#三状态与消息) | AgentState、reducer、checkpoint |
| [四、主 Agent：工厂与 Prompt](#四主-agent工厂与-prompt) | `create_deep_agent`、系统提示结构 |
| [五、工具系统与 Skills](#五工具系统与-skills) | Tools、Skills、MCP、渐进披露 |
| [六、子 Agent：同步与异步](#六子-agent同步与异步) | `SubAgentMiddleware`、`AsyncSubAgentMiddleware` |
| [七、中间件链](#七中间件链) | 全量顺序与钩子表、10 个中间件详解 |
| [八、记忆系统](#八记忆系统) | MemoryMiddleware、AGENTS.md、防抖队列 |
| [九、摘要与缓存](#九摘要与缓存) | SummarizationMiddleware、AnthropicPromptCachingMiddleware |
| [十、CLI 与 App 端](#十-cli-与-app-端) | Textual TUI、配置管理、会话持久化 |
| [十一、对比与生态](#十一对比与生态) | 与 DeerFlow Harness、OpenHands 等框架对比 |
| [十二、源码索引](#十二源码索引) | 关键文件路径 |
| [第十三章 追加记录](#第十三章-追加记录) | 历史问答与补充 |

---

## 〇、文档说明与学习目标

**学完应能回答：**

1. **Deep Agents 的「行为」由谁塑造？** —— 模型 + **系统提示（规范）** + **可用工具集合（动作空间）** + **中间件（硬约束）**；Deep Agents 不实现独立「推理引擎」，而是 **Orchestration harness**。
2. **Skills 和 Tools 本质区别？** —— **差别在「如何声明 / 如何被发现」**：Tools 的 **name/description/schema** 绑定在 Chat API 的 **`tools` 字段**；Skills 只在 system 里放 **短索引（路径 + 描述）**，**不把 SKILL 正文绑进 schema**。**相同的是「进历史的形状」**：模型一旦发起工具调用，**执行结果都以 `ToolMessage` 追加进 `messages`**。Skills **没有第二条魔法通道**——读 `SKILL.md` 就是调 **`read_file`**，**整份文件内容即该次调用的 tool 返回值**。
3. **子 Agent 是不是另一张图？** —— **是**；是主会话里 **`task` 工具** 触发的 **第二个 `create_agent` 实例**，线程池跑完结果 **以一坨 ToolMessage 回来**。
4. **CLI 与 SDK 的关系？** —— CLI 是 **Textual TUI 产品层**，SDK 是 **LangGraph 框架层**；CLI 通过 `DeerFlowClient` 或 HTTP Gateway 调用 SDK。

**适合读者**：要在 LangGraph/LangChain 栈上做多工具、沙箱、委派、MCP 的产品或框架开发者。

---

## 一、设计思想总论

### 1.1 核心范式：**声明式配置 + 反射 + 标准 Agent 循环**

- **配置**：`create_deep_agent()` 参数描述模型、工具、中间件、子 Agent 等；CLI 层用 `config.toml` 描述模型提供商、MCP 服务器、Skills 目录。
- **反射**：`deepagents._models.resolve_model()` 在运行时把字符串解析成 `BaseChatModel` 实例。
- **运行时**：`langchain.agents.create_agent` 提供 **模型 ↔ 工具** 的 **ReAct 式闭环**；Deep Agents **不手写**每一步消息 append，而靠 LangChain 实现 + `AgentState` 扩展字段。

**思想**：把「易变部分」（换模型、换工具组、换沙箱实现）**数据化**；把「稳定部分」（状态形状、中间件顺序、虚拟路径协议）**代码化**。

### 1.2 **SDK 与 CLI/Code 分离**

- **CLI / Code**：
  - **`deepagents-code`** (`libs/code/`，运行命令为 `dcode`）：产品与协议适配层，基于 Textual 构建交互式终端 UI（以前属于 `deepagents-cli` 的交互 REPL 功能已迁移至此）。
  - **`deepagents-cli`** (`libs/cli/`，运行命令为 `deepagents`）：提供部署管理相关的命令行子命令（如 `init`、`dev` , `deploy`）。
- **依赖方向**：`deepagents_cli → deepagents` 以及 `deepagents_code → deepagents` 均为单向依赖；CI 保证 **无反向 import**。

**思想**：**框架可复用**、**产品可换壳**；与「单体后端」相比，测试与二次集成成本更低。

### 1.3 **三种「能力」三条通路**

| 能力类型 | 如何进入模型 | 如何「执行」 |
|----------|----------------|--------------|
| **规范（Policy）** | 写进 **system prompt**（澄清优先、引用格式、子 Agent 编排说明） | 模型 **遵守或偏离**；中间件对特定工具做 **图级中断** |
| **Skills** | **Prompt 索引**（name/description/**路径**） | 模型调 **`read_file`** → **文件内容作为该工具返回值** → **`ToolMessage`**；后续回合 **按文档行事** |
| **Tools** | **API `tools` 数组**（或 SDK `bind_tools`） | **ToolNode** 执行 Python/MCP/沙箱 → 结果 **`ToolMessage`** |

**回写共性**：上表两类在 **「声明」** 上分路（索引在 system vs schema 在 `tools`），在 **「执行之后」** 并轨：**凡是工具调用，返回值都进入 `messages` 里的 `ToolMessage`**。因此读 `SKILL.md` 时，**全文占的是某条 ToolMessage 的 content**，不是「悄悄注入进 system」；后续轮次模型再基于这条历史继续推理。

**思想**：不要把一切都塞进 prompt（伤 token、难版本化）；**结构化工具**走 **native tool calling**；**长链路方法论**走 **可版本控制的 Markdown + 渐进加载**（正文晚到，以 **文件工具返回值** 的形式进入历史）。

### 1.4 **子 Agent：进程内委派，非分布式调度**

- 无中心 Scheduler 服务；**委派 = 一次特殊的工具调用**，内部再起 Agent。
- **同步子 Agent**（`SubAgentMiddleware`）：阻塞式执行，结果立即返回。
- **异步子 Agent**（`AsyncSubAgentMiddleware`）：后台任务，通过 LangGraph SDK 连接远程服务器。

**思想**：实现简单、延迟可控；代价是 **`task` 路径阻塞**、线程池与并发需 **限流中间件** 兜底。

### 1.5 **Sandbox：抽象环境 + 虚拟路径**

- 模型与 prompt 只谈 **`/mnt/user-data`**、**`/mnt/skills`**；主机路径由 **tools 层** 映射并 **校验/脱敏**。
- Backend 协议（`BackendProtocol`、`SandboxBackendProtocol`）隔离具体实现（本地文件系统、Docker、远程沙箱）。

**思想**：**可移植叙事**（本地/Docker 一致）；**安全边界**集中在路径解析，而不是每个工具各写一套。

### 1.6 读后续章节时建议带着的三条**系统不变量**

下文各节若在罗列「有什么」，可回到这三条问「它维护了哪条不变量、破坏了会怎样」。

1. **ReAct 消息协议（对话侧）**  
   一次合法的「工具回合」在抽象上是：`AIMessage` 带 `tool_calls` → 每条 call 对应一条 `ToolMessage`（含 `tool_call_id`）→ 下一次模型调用再读入上述历史。若用户中断、崩溃或流式断开，会出现 **悬空的 tool_calls**（模型以为工具会执行，历史上却没有对应 ToolMessage）。**PatchToolCallsMiddleware** 的存在说明：这不是边缘情况，而是 **分布式/流式 UI 下的常态**；修补的目标是让后续 `create_agent` 图调度仍满足供应商/SDK 对交替消息的检查。

2. **状态 = checkpoint 存盘的那一坨（持久化侧）**  
   **先用人话想**：开了 checkpointer 之后，每隔几步 LangGraph 会把 **当前这条线程的全部状态** 写进存储（像游戏存档）。**读档**时恢复的也是这一整包，而不是只恢复「最后一句聊天」。  
   **和聊天列表并列的**还有：`todos`、`artifacts`、`async_tasks`、`skills_metadata`、`memory_contents` 等——这些都在 **`AgentState`** 里声明。  
   **为什么要强调这个？** 若某信息只放在 **Python 全局变量、单例缓存、函数闭包** 里，**一重启进程或换副本就丢**，也不会写进存档；**该进 `AgentState` 的就必须进 schema**，才能跟 `messages` 一起被 checkpoint。  
   **「reducer / merge」又是啥？** 同一轮里 **多个工具并行** 回写同一条字段时，图里会多次合并更新。若合并语义是 **「新来的整段盖住旧的」**（last-write-wins），后完成的工具会 **抹掉** 先完成的工具写进 `artifacts` 的路径 → UI 少文件。**自定义 reducer** 做的是 **旧列表 + 新列表拼起来再按顺序去重**，让并行 `present_files` **都保留**。

3. **三类控制的反馈回路（行为侧）**  
   - **Prompt**：改模型的先验与话术，**无强制力**，成本低、可 A/B。  
   - **Tools**：改 **动作空间**（能调用什么 API）；多一个 `task` 或多 50 个 MCP，**策略分布**会变。  
   - **Middleware**：改 **轨迹级约束**（超限截断、错误吞成 ToolMessage、澄清时 `goto END`）。  
   产品上要「既温柔又硬」，通常是 **Prompt 解释为什么 + Middleware 执行真的边界**；只写文档不写代码，模型会漂移；只写代码不写 Prompt，模型不知道何时触发工具。

---

## 二、分层与运行时

### 2.1 三层架构

```
┌─────────────────────────────────────┐
│         CLI / App Layer             │  ← Textual TUI、配置管理、会话持久化
│  (deepagents_cli/)                  │
├─────────────────────────────────────┤
│         SDK Layer                   │  ← create_deep_agent、Middleware Chain
│  (libs/deepagents/deepagents/)      │
├─────────────────────────────────────┤
│     LangGraph / LangChain Core      │  ← create_agent、ToolNode、Checkpoint
└─────────────────────────────────────┘
```

- **LangGraph Server**：加载 `langgraph.json`，入口 **`make_lead_agent`**（DeerFlow 特有）。
- **Gateway**（`app`）：模型列表、MCP/Skills 配置、上传、产物、记忆 API；**与 Agent 进程通过文件 + HTTP 协作**（DeerFlow 特有）。
- **DeepAgentsClient**：同套 `deepagents` 模块 **进程内** 跑 agent，无需 LangGraph HTTP。

### 2.2 运行时启动流程

1. **CLI 启动**：`deepagents` 命令 → `main.py:cli_main()` → 解析 `config.toml` → 初始化 Textual App。
2. **SDK 调用**：`create_deep_agent(model="anthropic:claude-sonnet-4-6", tools=[...], middleware=[...])` → 构建 LangGraph StateGraph。
3. **首次运行**：用户输入 → `HumanMessage` → 注入 system prompt → 模型调用 → 工具执行 → 循环直到完成。

---

## 三、状态与消息

### 3.1 `AgentState`（源码：`langchain.agents.middleware.types.AgentState`）

**定位**：在 LangChain **基础状态** 上扩展，使 LangGraph checkpoint **同时持久化对话与线程级资源**。`create_deep_agent`、子 Agent（`task`）路径、以及 `ToolRuntime[..., AgentState]` 的工具共用 **同一 `state_schema`**，避免各层各用一套 dict。

**基类（概念）**：`messages` 使用 **`add_messages`** 归约；框架还可含 `jump_to`、`structured_response` 等；Deep Agents 不重复定义这些，只在下表 **追加**字段。

| 字段 | 作用 |
|------|------|
| `todos` | Plan 模式任务列表（`TodoListMiddleware`）。 |
| `artifacts` | 见下 **[「artifacts」是什么](#artifacts-是什么)**：本质是 **`present_files` 登记进状态的「给用户看的产物」路径列表**。 |
| `async_tasks` | 异步子 Agent 任务追踪（`AsyncSubAgentMiddleware`）。 |
| `skills_metadata` | Skills 加载元数据（`SkillsMiddleware`）。 |
| `memory_contents` | 记忆文件内容（`MemoryMiddleware`）。 |

<a id="artifacts-是什么"></a>

#### 「artifacts」是什么？

**一句话**：`artifacts` 是 **`AgentState` 里的一个 `list[str]`**，记录 **「应该出现在产品 UI 里、供用户查看/下载的最终产物」** 在 **虚拟路径**下的位置；**不是**「线程目录里所有文件」的自动快照。

**从哪来**：几乎只通过内置工具 **`present_files`**（`tools/builtins/present_file_tool.py`）写入。模型在 **`/mnt/user-data/outputs`**（仅该目录）里生成或拷贝好交付物后，**主动调用** `present_files`，工具把路径 **规范化**为形如 **`/mnt/user-data/outputs/...`** 的字符串，并以 `Command(update={"artifacts": [...], "messages": [...]})` 合并进状态。  
**为何需要这一层**：文件在磁盘上存在 ≠ 产品要展示；中间过程、临时文件可以留在 `workspace` 而不进列表。**`present_files` = 显式「上架」**，把「给用户的结果」和「代理自己用的垃圾」分开。

**谁用**：客户端 / Gateway 根据这些虚拟路径拼 **产物 URL**，前端才能渲染卡片、预览、下载。**随 checkpoint 持久化**，重连同一线程仍知道「这一会话已经交付过哪些文件」。

**`merge_artifacts`**：同一轮里可 **并行**多次 `present_files`；reducer 把多段更新 **按顺序拼接再去重**，避免「后一次覆盖前一次」导致 UI 少文件。

**不是什么**：① 不是上传区列表（那是 `uploaded_files` 等链路）；② 不是模型读过的所有路径；③ 非 `outputs` 下的路径会被 `present_files` **拒绝**（工具内校验）。

### 3.2 `messages` 谁写入？主 Agent 与子 Agent 是否共用一份 checkpoint？

#### 主会话里，谁在改 `messages`？

- **`create_agent` 图**：**Model 节点**产出 `AIMessage`（含可选 `tool_calls`）；**Tool 节点**执行工具后追加 **`ToolMessage`**。这是默认主路径。
- **中间件**：例如 **`PatchToolCallsMiddleware`** 在 `wrap_model_call` 里 **改写即将送给模型的那份** `messages` 列表（补占位 `ToolMessage`）；**摘要中间件**会把旧消息压成摘要 + 保留近窗——最终仍会反映到 **checkpoint 里的 `messages`**。
- **返回 `Command(update={...})` 的工具**：如 **`present_files`** 用 **LangGraph `Command`** 一次写入 **`artifacts` + `messages`**。
- **进程内 Client / 入口**：可在发起 run 前注入 **`HumanMessage`** 等。

**原理**：Deep Agents **遵循** LangChain 的消息协议；额外写入集中在 **中间件** 与 **少数工具的 Command**。

#### 子 Agent 会把「过程消息」写进主线程的 `AgentState` 吗？

**不会。** 要分清三件事：

| 概念 | 实际情况 |
|------|----------|
| **类型** | 子 run 也用 **`AgentState` 作 `state_schema`**（与主会话 **同一套字段类型**），工具里 `ToolRuntime[..., AgentState]` 形状一致。 |
| **存活的 state 实例** | **两套内存里的图状态**：主图一份、`task` 内部 **`create_agent` 再起的一份**。子 run **不传**与主线程共享的 **checkpointer**，子图自己的 `messages` **只活在当次子任务执行期间**。 |
| **写回主图** | 子 run 结束后，**只有** `task` 工具在 **主图**里对应的那条（些）**`ToolMessage`**（内容为成功/失败摘要字符串等）进入 **主** `messages`；子图里的多轮 **Human/AI/Tool 交替** **不会**逐条 merge 进主 checkpoint。 |

**为何这样设计**：子任务常常是 **多轮 ReAct**，若全过程并进主 `messages`，主线程上下文会 **二次爆炸**；产品上通常只需要 **结论**，过程可通过 **流式事件** 旁路展示。

---

## 四、主 Agent：工厂与 Prompt

### 4.1 `create_deep_agent`（源码：`deepagents/graph.py`）

**签名**：
```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    response_format: ResponseFormat[ResponseT] | type[ResponseT] | dict[str, Any] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph[...]
```

**核心逻辑**：
1. **解析模型**：`resolve_model(model)` → `BaseChatModel` 实例。
2. **组装中间件链**：按固定顺序插入 10 个中间件（见 §7）。
3. **注册工具**：`write_todos`、文件系统工具、`execute`、`task`、异步子 Agent 工具。
4. **拼装 system prompt**：`user_system + "\n\n" + BASE_AGENT_PROMPT` + 中间件注入片段。
5. **调用 `create_agent`**：传入模型、工具、中间件、状态 schema 等。

### 4.2 `BASE_AGENT_PROMPT`（源码：`deepagents/graph.py:50-91`）

**完整英文原文**（中文翻译见附录）：
```
You are a deep agent, an AI assistant that helps users accomplish tasks using tools. You respond with text and tool calls. The user can see your responses and tool outputs in real time.

## Core Behavior
- Be concise and direct. Don't over-explain unless asked.
- NEVER add unnecessary preamble ("Sure!", "Great question!", "I'll now...").
- Don't say "I'll now do X" — just do it.
...
```

**设计要点**：
- **简洁直接**：禁止冗余寒暄。
- **专业客观**：优先准确性而非迎合用户。
- **任务导向**：理解 → 行动 → 验证，持续迭代直到完成。
- **澄清策略**：只问最小必要问题，避免过度追问。

### 4.3 Prompt 拼装逻辑

**完整 system prompt =**：
```
{user_system}                          # 用户自定义前缀（可选）

{BASE_AGENT_PROMPT}                    # 核心行为规范

{WRITE_TODOS_SYSTEM_PROMPT}            # TodoListMiddleware 注入
{MEMORY_SYSTEM_PROMPT}                 # MemoryMiddleware 注入（若配置 memory）
{SKILLS_SYSTEM_PROMPT}                 # SkillsMiddleware 注入（若配置 skills）
{FILESYSTEM_SYSTEM_PROMPT}             # FilesystemMiddleware 注入
{TASK_SYSTEM_PROMPT}                   # SubAgentMiddleware 注入
{ASYNC_TASK_SYSTEM_PROMPT}             # AsyncSubAgentMiddleware 注入（若有异步子 Agent）
{EXECUTION_SYSTEM_PROMPT}              # FilesystemMiddleware 注入（若支持沙箱）
```

**注意**：上述片段中，**只有 `BASE_AGENT_PROMPT` 是静态字符串**；其余由中间件在 `wrap_model_call` 或 `before_agent` 阶段动态注入。

---

## 五、工具系统与 Skills

### 5.1 内置工具清单

| 工具名 | 来源 | 作用 |
|--------|------|------|
| `write_todos` | `langchain.agents.middleware.todo` | 管理待办列表（Plan 模式） |
| `ls` | `deepagents/middleware/filesystem.py` | 列出目录 |
| `read_file` | `deepagents/middleware/filesystem.py` | 读取文件 |
| `write_file` | `deepagents/middleware/filesystem.py` | 写入文件 |
| `edit_file` | `deepagents/middleware/filesystem.py` | 编辑文件 |
| `glob` | `deepagents/middleware/filesystem.py` | 按模式找文件 |
| `grep` | `deepagents/middleware/filesystem.py` | 在文件中搜索文本 |
| `execute` | `deepagents/middleware/filesystem.py` | 执行 shell 命令（需沙箱） |
| `task` | `deepagents/middleware/subagents.py` | 启动同步子 Agent |
| `start_async_task` | `deepagents/middleware/async_subagents.py` | 启动异步子 Agent |
| `check_async_task` | `deepagents/middleware/async_subagents.py` | 检查异步任务状态 |
| `update_async_task` | `deepagents/middleware/async_subagents.py` | 更新异步任务指令 |
| `cancel_async_task` | `deepagents/middleware/async_subagents.py` | 取消异步任务 |
| `list_async_tasks` | `deepagents/middleware/async_subagents.py` | 列出所有异步任务 |

### 5.2 Skills 系统（渐进披露）

**核心思想**：Skills 不是「独立运行时」，而是 **Markdown 文档 + 文件读取工具** 的组合。

**工作流程**：
1. **发现阶段**：`SkillsMiddleware` 扫描配置的 `skills` 目录，提取每个 `SKILL.md` 的 **名称、描述、路径**。
2. **索引注入**：在 system prompt 中插入 **`{skills_locations}`** 和 **`{skills_list}`**（短文本，~50-200 tokens）。
3. **按需加载**：模型判断任务匹配某 Skill → 调用 `read_file("/skills/public/deep-research/SKILL.md")` → 获得完整指南（可能 ~2000-5000 tokens）。
4. **执行技能**：模型按照 SKILL.md 中的流程操作，可能需要多次调用其他工具。

**示例**（`{skills_list}` 片段）：
```markdown
- **deep-research**: Use this skill instead of WebSearch for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches.
  -> Read `/skills/public/deep-research/SKILL.md` for full instructions
```

**优势**：
- **Token 高效**：不在每次请求都携带长篇指南。
- **版本控制**：SKILL.md 可作为普通文件纳入 Git。
- **可组合**：Skill 内部可引用其他 Skill 或脚本。

### 5.3 MCP（Model Context Protocol）

**集成方式**：通过 `deepagents_cli/mcp_tools.py` 将 MCP 服务器暴露为 LangChain Tools。

**工作流程**：
1. **配置 MCP 服务器**：在 `config.toml` 中声明 `[mcp.servers]`。
2. **启动时连接**：CLI 启动时通过 `langchain-mcp-adapters` 连接各服务器。
3. **工具注册**：每个 MCP 服务器的 `tools/list` 响应转换为 `StructuredTool`。
4. **延迟加载**：通过 `DeferredToolFilterMiddleware`（DeerFlow 特有）过滤不常用工具，节省 context token。

---

## 六、子 Agent：同步与异步

### 6.1 同步子 Agent（`SubAgentMiddleware`）

**源码**：`deepagents/middleware/subagents.py`

**工作机制**：
1. **注册 `task` 工具**：模型调用 `task(description="...", subagent_type="general-purpose")`。
2. **创建子 Agent**：内部调用 `create_agent(model=subagent.model, tools=subagent.tools, system_prompt=subagent.system_prompt, ...)`。
3. **执行子任务**：子 Agent 在自己的 `AgentState` 中运行，可能经历多轮 ReAct。
4. **返回结果**：子 Agent 的最后一条消息提取为字符串，包装成 `ToolMessage` 返回主 Agent。

**典型配置**：
```python
subagents = [
    {
        "name": "general-purpose",
        "description": "用于研究复杂问题、搜索文件与内容、执行多步任务",
        "system_prompt": "你是一个通用研究助手...",
        "tools": [...],  # 可选，默认继承主 Agent 工具
        "model": "openai:gpt-4o",  # 可选，覆盖主模型
    }
]
```

**限制**：
- **阻塞式**：主 Agent 等待子 Agent 完成才能继续。
- **无 HITL**：子 Agent 不支持 `ask_clarification`（避免子 thread checkpoint 复杂性）。
- **无独立 checkpoint**：子任务过程不持久化，只有结果进入主 checkpoint。

### 6.2 异步子 Agent（`AsyncSubAgentMiddleware`）

**源码**：`deepagents/middleware/async_subagents.py`

**工作机制**：
1. **注册 5 个异步工具**：`start_async_task`、`check_async_task`、`update_async_task`、`cancel_async_task`、`list_async_tasks`。
2. **启动后台任务**：模型调用 `start_async_task(description="...", subagent_type="researcher")` → 通过 LangGraph SDK 连接远程服务器 → 立即返回 `task_id`。
3. **监控进度**：模型或用户可随时调用 `check_async_task(task_id="...")` 获取状态。
4. **发送更新**：通过 `update_async_task(task_id="...", message="新指令")` 中断当前运行并启动新 run。
5. **收集结果**：当状态为 `"success"` 时，结果包含在响应中。

**状态追踪**：
```python
class AsyncTask(TypedDict):
    task_id: str          # 唯一标识（同 thread_id）
    agent_name: str       # 子 Agent 类型
    thread_id: str        # 远程服务器上的线程 ID
    run_id: str           # 当前执行的 run ID
    status: str           # running/success/error/cancelled
    created_at: str       # ISO-8601 时间戳
    last_checked_at: str  # 最后检查时间
    last_updated_at: str  # 最后更新时间
```

**优势**：
- **非阻塞**：主 Agent 可继续与其他用户交互。
- **长期运行**：适合耗时任务（数小时的数据处理、大规模调研）。
- **可更新**：中途可发送新指令调整方向。

**适用场景**：
- 批量数据处理
- 跨多源头的深度调研
- 需要人工中途干预的长任务

---

## 七、中间件链

### 7.1 完整中间件顺序（`create_deep_agent` 主图）

**源码**：`deepagents/graph.py:284-304`

```
1. TodoListMiddleware                  # Plan 模式待办管理
2. SkillsMiddleware                    # Skills 渐进加载（若配置 skills）
3. FilesystemMiddleware                # 文件系统工具注册
4. SubAgentMiddleware                  # 同步子 Agent（task 工具）
5. SummarizationMiddleware             # 上下文压缩
6. PatchToolCallsMiddleware            # 修补悬空 tool_calls
7. AsyncSubAgentMiddleware             # 异步子 Agent（若有 async subagents）

--- 用户自定义 middleware 插入此处 ---

8. Profile extra_middleware            # 提供商特定中间件（若有）
9. _ToolExclusionMiddleware            # 排除特定工具（若配置）
10. AnthropicPromptCachingMiddleware   # Anthropic 缓存优化（无条件挂载，非 Anthropic 模型 no-op）
11. MemoryMiddleware                   # 记忆系统（若配置 memory）
12. HumanInTheLoopMiddleware           # 人机协同中断（若配置 interrupt_on）
13. _PermissionMiddleware              # 文件系统权限控制（始终最后）
```

**设计原则**：
- **前置中间件**（1-7）：负责 **工具注册、prompt 注入、消息预处理**。
- **后置中间件**（8-13）：负责 **缓存优化、记忆加载、安全控制**。
- **用户中间件**：插入中间位置，可访问已注册的工具和完整的 system prompt。

### 7.2 关键中间件详解

#### 7.2.1 `TodoListMiddleware`

**作用**：管理 Plan 模式的待办列表。

**注入 prompt**：
```
## `write_todos`

你可以使用 `write_todos` 工具来管理和规划复杂目标。
对于复杂目标，应使用该工具，确保跟踪每一个必要步骤，并让用户看到你的进展。
...
```

**工具 schema**：来自 `langchain.agents.middleware.todo.WRITE_TODOS_TOOL_DESCRIPTION`。

**使用规则**：
- **不要并行调用**：同一轮只能调用一次 `write_todos`。
- **及时标记完成**：每完成一步立即勾选，不要攒多步。
- **简单任务不用**：少于 3 步的任务直接执行，不要写待办。

#### 7.2.2 `SkillsMiddleware`

**作用**：Skills 渐进披露与加载。

**注入 prompt**：
```
## 技能系统（Skills System）

你可以访问技能库，获得专门能力与领域知识。

**Public Skills**: `/skills/public/`

**可用技能：**
- **deep-research**: Use this skill instead of WebSearch for ANY question requiring web research.
  -> Read `/skills/public/deep-research/SKILL.md` for full instructions
...

**如何使用技能（渐进披露）：**
1. 判断任务是否匹配某技能
2. 按列表中的路径读取技能全文
3. 遵循 SKILL.md 中的流程与最佳实践
4. 引用资源时使用绝对路径
```

**状态字段**：`skills_metadata`（记录已加载的 Skills 元数据）。

#### 7.2.3 `FilesystemMiddleware`

**作用**：注册文件系统工具并注入使用规范。

**注入 prompt**：
```
## 文件系统工具 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`

你可以通过下列工具与文件系统交互。**所有路径必须以 `/` 开头。**

- ls：列出目录（需绝对路径）
- read_file：读文件
...
```

**沙箱执行**：若后端实现 `SandboxBackendProtocol`，额外注入 `execute` 工具及安全规范。

#### 7.2.4 `SubAgentMiddleware`

**作用**：注册 `task` 工具并注入子 Agent 编排说明。

**注入 prompt**（`TASK_SYSTEM_PROMPT`）：
```
## `task`（子智能体生成器）

你可以使用 **`task` 工具**启动**短生命周期子智能体**来处理隔离任务。这些智能体是**临时的**——仅在该任务期间存在，并返回**单一结果**。

**何时使用 `task`：**
- 任务复杂、多步，且可以**完整委托**在隔离环境中完成
- 任务与其他任务**独立**，可**并行**执行
- 需要集中推理或大量 token/上下文，避免拖垮主会话
...
```

**工具 schema**（`TASK_TOOL_DESCRIPTION`）：包含可用子 Agent 列表及使用示例。

#### 7.2.5 `SummarizationMiddleware`

**作用**：上下文压缩，防止超出模型窗口限制。

**工作机制**：
1. **检测阈值**：当 `messages` 总 token 数超过 `max_tokens_before_summary`（默认 ~80% 窗口）。
2. **选择压缩范围**：保留最近 N 条消息（`keep_recent_messages`，默认 10-15 条）。
3. **生成摘要**：调用 LLM 对旧消息生成结构化摘要（13 字段，包括目标、关键发现、待办状态等）。
4. **替换消息**：用摘要 + 保留的近窗消息替换原始历史。

**配置示例**：
```python
from deepagents.middleware.summarization import create_summarization_middleware

summary_mw = create_summarization_middleware(
    model="anthropic:claude-sonnet-4-6",
    max_tokens_before_summary=100000,
    keep_recent_messages=12,
)
```

**优势**：
- **保持连贯性**：摘要保留关键上下文，不像简单截断那样丢失信息。
- **自动化**：无需手动干预，达到阈值自动触发。

#### 7.2.6 `PatchToolCallsMiddleware`

**作用**：修补悬空的 `tool_calls`（模型叫了工具但历史上没有对应 `ToolMessage`）。

**算法**（与 DeerFlow `DanglingToolCallMiddleware` 一致）：
1. **收集已有回应**：遍历 `messages`，把所有 `ToolMessage` 的 `tool_call_id` 放进集合。
2. **判断是否需要修补**：遍历每条 `AIMessage`，若存在某个 `tool_call.id` 不在集合中，则置 `needs_patch = true`。
3. **构造新列表**：对每个悬空 call，在其紧后插入合成的 `ToolMessage`：
   - `content`: `"[Tool call was interrupted and did not return a result.]"`
   - `tool_call_id`: 与悬空 call 一致
   - `name`: 来自 `tool_calls[i].get("name", "unknown")`
   - `status="error"`

**为何不用 `before_agent` 直接改 state？** 模块注释写明：若只靠 **`add_messages` 归约** 往列表末尾追加 synthetic `ToolMessage`，**无法保证**占位消息紧跟在「发出 `tool_calls` 的那条 `AIMessage`」之后；供应商与 LangChain 期望的是 **交替合法序列**。因此必须在 **模型请求路径** 上 **按序重建 `messages` 列表**。

#### 7.2.7 `AsyncSubAgentMiddleware`

**作用**：注册异步子 Agent 工具并注入使用说明。

**注入 prompt**（`ASYNC_TASK_SYSTEM_PROMPT`）：
```
## Async subagents (remote LangGraph servers)

你有权访问异步子 Agent 工具，它们在远程 LangGraph 服务器上启动后台任务。

### Tools:
- `start_async_task`: 启动新后台任务。立即返回 task ID。
- `check_async_task`: 获取任务当前状态和结果。
- `update_async_task`: 向运行中的任务发送新指令。
- `cancel_async_task`: 停止运行中的任务。
- `list_async_tasks`: 列出所有追踪的任务及实时状态。

### Workflow:
1. **Start** — 使用 `start_async_task` 启动任务。向用户报告 task ID 并停止。
   不要立即检查状态 — 任务在后台运行，你和用户可继续其他工作。
2. **Check (on request)** — 仅在用户明确要求状态更新或结果时使用 `check_async_task`。
   若状态为 "running"，报告并停止 — 不要轮询。
...
```

**状态字段**：`async_tasks: dict[str, AsyncTask]`（追踪所有异步任务）。

#### 7.2.8 `AnthropicPromptCachingMiddleware`

**作用**：优化 Anthropic 模型的 prompt caching。

**工作机制**：
- 对 Anthropic 模型，标记 system prompt 和早期消息为 **cacheable**。
- 对非 Anthropic 模型，no-op（无操作）。

**优势**：降低重复请求的 token 成本（Anthropic 对缓存命中部分收费更低）。

#### 7.2.9 `MemoryMiddleware`

**作用**：加载和管理 AGENTS.md 记忆文件。

**注入 prompt**（`MEMORY_SYSTEM_PROMPT`）：
```
<agent_memory>
{agent_memory}
</agent_memory>

<memory_guidelines>
    上述 <agent_memory> 从文件系统加载。随着与用户交互，你可以通过调用 `edit_file` 工具保存新知识。

    **从反馈中学习：**
    - 你的**主要优先事项之一**是从与用户的互动中学习；这些学习可以是显式或隐式的。
    - 当你需要记住某件事时，更新记忆必须是**第一时间的即时动作**——在回复用户之前、在调用其他工具之前、在做任何其他事之前，先更新记忆。
    ...
</memory_guidelines>
```

**记忆文件**：`AGENTS.md`（可从多个路径加载，如 `/memory/AGENTS.md`、`/project/AGENTS.md`）。

**更新机制**：模型调用 `edit_file` 修改记忆文件 → 下次会话自动加载最新内容。

**防抖队列**：DeerFlow 特有，防止频繁写入导致 I/O 风暴（Deep Agents 暂无此优化）。

#### 7.2.10 `HumanInTheLoopMiddleware`

**作用**：在特定工具调用前中断，等待用户确认。

**配置示例**：
```python
interrupt_on = {
    "edit_file": True,  # 每次编辑文件前暂停
    "execute": {"tools": ["rm", "mv"], "mode": "always"},  # 危险命令总是暂停
}
```

**工作流程**：
1. 模型调用 `edit_file(...)`。
2. 中间件检测到 `interrupt_on["edit_file"]` → 抛出 `Interrupt`。
3. LangGraph 暂停执行，保存 checkpoint。
4. 用户通过 CLI 或 API 审查并批准/拒绝。
5. 恢复执行，继续下一轮。

#### 7.2.11 `_PermissionMiddleware`

**作用**：文件系统权限控制（始终最后执行）。

**规则示例**：
```python
from deepagents.middleware.permissions import FilesystemPermission

permissions = [
    FilesystemPermission(path="/mnt/user-data/secrets/", action="deny"),
    FilesystemPermission(path="/mnt/user-data/", action="allow"),
]
```

**评估逻辑**：
- 按声明顺序匹配，第一条匹配的规则生效。
- 若无规则匹配，默认允许。

**子 Agent 继承**：子 Agent 继承父 Agent 的权限规则，除非显式指定自己的 `permissions` 字段。

---

## 八、记忆系统

### 8.1 设计理念

**核心思想**：记忆不是「数据库」，而是 **可版本控制的 Markdown 文件**。

**与传统 RAG 的区别**：
| 维度 | 传统 RAG | Deep Agents Memory |
|------|---------|-------------------|
| **存储格式** | 向量数据库 | 纯文本 Markdown |
| **检索方式** | 相似度搜索 | 启动时全量加载 |
| **更新机制** | 增量嵌入 | 模型调用 `edit_file` |
| **版本控制** | 困难 | 天然支持 Git |
| **可解释性** | 黑盒 | 人类可读可编辑 |

### 8.2 工作流程

1. **启动时加载**：`MemoryMiddleware` 读取配置的 `memory` 路径（如 `["/memory/AGENTS.md"]`）。
2. **注入 prompt**：将文件内容包裹在 `<agent_memory>` 标签中，附加 `<memory_guidelines>` 使用说明。
3. **模型更新**：模型识别需要记忆的信息 → 调用 `edit_file("/memory/AGENTS.md", content="...")`。
4. **持久化**：文件写入后端（本地磁盘或远程存储）。
5. **下次会话**：重新加载最新内容。

### 8.3 记忆指南（`MEMORY_SYSTEM_PROMPT` 核心要点）

**何时应更新记忆**：
- 用户明确要求记住（「请记住我喜欢 Python」）。
- 角色/行为描述（「我是后端工程师，偏好 TypeScript」）。
- 对工作的反馈（「上次生成的代码风格太冗长」）。
- 工具所需 ID（「我的 Slack user ID 是 U123456」）。
- 可复用的工具使用模式（「部署前先运行 lint」）。
- 新发现的偏好与流程（「周报用 Markdown 格式」）。

**何时不应更新记忆**：
- 临时状态（「我现在很忙」）。
- 一次性任务（「今天帮我查天气」）。
- 无长期偏好价值的简单问答。
- 寒暄（「你好」「谢谢」）。
- 已过时信息。
- **绝不**存储 API 密钥、令牌、密码。

**示例**：
```markdown
## User Preferences
- Preferred language: Chinese (Simplified)
- Coding style: Concise, avoid verbose comments
- Deployment workflow: Always run `pytest` before `git push`

## Project Context
- Tech stack: React + TypeScript + Vite
- Database: PostgreSQL with Prisma ORM
- CI/CD: GitHub Actions
```

---

## 九、摘要与缓存

### 9.1 `SummarizationMiddleware` 深度机制

**触发条件**：
```python
if total_tokens > max_tokens_before_summary:
    trigger_summary()
```

**压缩策略**：
1. **廉价预压缩**：清除旧的工具结果（无需 LLM 调用）。
2. **确定压缩范围**：计算需要压缩的消息区间（保留最近 N 条）。
3. **生成结构化摘要**：调用 LLM 生成 13 字段的结构化摘要：
   - 用户目标
   - 关键发现
   - 已完成步骤
   - 待办状态
   - 技术决策
   - 遇到的问题
   - 下一步计划
   - ...
4. **组装压缩后消息**：保留 head（系统消息）+ 插入 summary + 保留 tail（近窗消息）。
5. **清理孤立工具对**：确保每个 `tool_call` 都有对应的 `tool_result`。

**配置参数**：
```python
create_summarization_middleware(
    model="anthropic:claude-sonnet-4-6",
    max_tokens_before_summary=100000,  # 触发阈值
    keep_recent_messages=12,            # 保留最近消息数
    summary_token_budget=3000,          # 摘要最大 token 数
)
```

**性能考量**：
- **摘要成本**：每次触发需额外调用一次 LLM（~3000 tokens）。
- **收益**：避免超出窗口限制导致的错误，保持长期对话连贯性。
- **最佳实践**：设置阈值为模型窗口的 70-80%，预留缓冲。

### 9.2 `AnthropicPromptCachingMiddleware`

**工作原理**：
- Anthropic 模型支持 **prompt caching**：标记某些消息为可缓存，后续请求若未变化则复用缓存。
- 中间件自动标记 system prompt 和早期对话为 cacheable。
- 缓存命中率越高，token 成本越低（Anthropic 对缓存命中部分收取 ~10% 费用）。

**适用模型**：
- ✅ `claude-3-5-sonnet-*`
- ✅ `claude-3-opus-*`
- ❌ 非 Anthropic 模型（no-op）

**注意事项**：
- 缓存有 TTL（通常几分钟），不适合长时间间隔的请求。
- 频繁变化的 prompt 会降低命中率。

---

## 十、CLI 与 App 端 (deepagents-cli & dcode)

### 10.1 CLI 与 Code 架构

Deep Agents 提供两套终端工具面：
1. **`deepagents-code` (`dcode`)**：运行交互式终端 UI（Textual TUI）以进行日常对话与编码任务。其源码位于 `libs/code/`。
2. **`deepagents-cli` (`deepagents`)**：专注于部署编排（`init` / `dev` / `deploy`），源码位于 `libs/cli/`。

**`deepagents-code` 核心模块（位于 `libs/code/deepagents_code/`）**：
| 模块 | 作用 |
|------|------|
| `main.py` | `dcode` CLI 入口、参数解析、依赖检查 |
| `app.py` | Textual TUI 主应用（核心交互逻辑） |
| `agent.py` | Agent 会话管理、消息流处理 |
| `config.py` | 配置加载（`config.toml`）、模型提供商管理 |
| `textual_adapter.py` | Textual 组件封装、消息渲染 |
| `widgets/` | UI 组件（聊天窗口、工具面板、状态栏等） |
| `mcp_tools.py` | MCP 服务器连接与工具注册 |
| `sessions.py` | 会话持久化、历史记录管理 |

### 10.2 配置管理（`config.toml`）

**示例配置**：
```toml
[models]
default = "anthropic:claude-sonnet-4-6"

[models.providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"

[mcp.servers]
filesystem = { command = "npx", args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"] }
github = { url = "https://api.github.com/mcp", headers = { Authorization = "Bearer ${GITHUB_TOKEN}" } }

[skills]
sources = ["/skills/public/", "/skills/user/"]

[memory]
files = ["/memory/AGENTS.md"]

[agents.recent]
last_used = "agent"
```

**加载流程**：
1. CLI 启动时读取 `~/.deepagents/config.toml`。
2. 解析模型提供商、MCP 服务器、Skills 目录等。
3. 传递给 `create_deep_agent()` 或 HTTP Gateway。

### 10.3 Textual TUI 设计

**核心组件**：
- **ChatWindow**：消息列表渲染（支持 Markdown、代码高亮、工具调用可视化）。
- **InputBox**：用户输入框（支持多行、快捷键）。
- **ToolPanel**：实时显示工具调用状态。
- **StatusBar**：显示当前模型、token 用量、连接状态。
- **Sidebar**：会话列表、文件浏览器、设置面板。

**交互模式**：
- **流式输出**：模型响应逐字显示，非阻塞。
- **工具可视化**：工具调用时显示进度条、参数、结果摘要。
- **中断处理**：用户可按 `Ctrl+C` 中断当前任务。
- **会话切换**：左侧边栏切换不同 thread，自动加载历史。

### 10.4 会话持久化

**存储位置**：`~/.deepagents/agents/<agent_name>/threads/<thread_id>/`

**存储内容**：
- `messages.json`：完整对话历史。
- `state.json`：AgentState（含 todos、artifacts、async_tasks 等）。
- `workspace/`：工作目录（模型创建的文件）。
- `uploads/`：用户上传的文件。
- `outputs/`：模型生成的产物（通过 `present_files` 上架）。

**恢复机制**：
1. CLI 启动时读取 `agents.recent` 确定默认 agent。
2. 用户选择 thread → 加载 `messages.json` 和 `state.json`。
3. 恢复 workspace 路径、sandbox_id 等资源句柄。
4. 继续对话，checkpoint 自动更新。

---

## 十一、对比与生态

### 11.1 Deep Agents vs DeerFlow Harness

| 维度 | Deep Agents | DeerFlow Harness |
|------|-------------|------------------|
| **定位** | LangChain 官方 SDK | 社区增强版 Harness |
| **子 Agent** | 同步 + 异步 | 仅同步（`task` 工具） |
| **记忆系统** | AGENTS.md 文件 | 文件 + 防抖队列 + summarization hook |
| **中间件数量** | 10 个 | 19 个（含 guardrails、reflection、tracing） |
| **CLI** | Textual TUI | 无（依赖 LangGraph Server） |
| **MCP 支持** | 通过 `mcp_tools.py` | 原生集成 + deferred filtering |
| **Sandbox** | Backend 协议抽象 | 线程隔离 + 路径虚拟化 |

**选择建议**：
- **Deep Agents**：适合快速原型、需要官方支持、简化架构。
- **DeerFlow**：适合生产环境、需要高级特性（guardrails、tracing）、细粒度控制。

### 11.2 Deep Agents vs OpenHands

| 维度 | Deep Agents | OpenHands |
|------|-------------|-----------|
| **核心场景** | 通用任务自动化 | 软件开发代理 |
| **工具集** | 文件系统 + MCP + 子 Agent | Git、IDE、测试框架 |
| **沙箱** | Backend 协议 | Docker 容器 |
| **UI** | Textual TUI | Web 界面 |
| **扩展性** | Middleware 插件 | Skill 系统 |

**选择建议**：
- **Deep Agents**：通用办公自动化、数据分析、文档处理。
- **OpenHands**：代码生成、Bug 修复、项目重构。

### 11.3 Deep Agents vs hermes-agent

| 维度 | Deep Agents | hermes-agent |
|------|-------------|--------------|
| **记忆架构** | 单层 AGENTS.md | 六层记忆（短期/长期/语义/程序/用户/元） |
| **上下文压缩** | SummarizationMiddleware | 5 阶段压缩（预压缩 + 结构化摘要 + 清理） |
| **插件系统** | Middleware Chain | 插件化架构（工具/记忆/压缩可插拔） |
| **复杂度** | 中等 | 高 |

**选择建议**：
- **Deep Agents**：中等复杂度任务，快速上手。
- **hermes-agent**：长期运行代理、需要精细记忆管理。

---

## 十二、源码索引

### 12.1 SDK 核心文件

| 文件 | 作用 |
|------|------|
| `libs/deepagents/deepagents/graph.py` | `create_deep_agent` 主入口、中间件组装 |
| `libs/deepagents/deepagents/middleware/subagents.py` | 同步子 Agent（`SubAgentMiddleware`、`TASK_SYSTEM_PROMPT`） |
| `libs/deepagents/deepagents/middleware/async_subagents.py` | 异步子 Agent（`AsyncSubAgentMiddleware`、5 个异步工具） |
| `libs/deepagents/deepagents/middleware/filesystem.py` | 文件系统工具、沙箱执行 |
| `libs/deepagents/deepagents/middleware/skills.py` | Skills 渐进加载 |
| `libs/deepagents/deepagents/middleware/memory.py` | 记忆系统（`MEMORY_SYSTEM_PROMPT`） |
| `libs/deepagents/deepagents/middleware/summarization.py` | 上下文压缩 |
| `libs/deepagents/deepagents/middleware/patch_tool_calls.py` | 修补悬空 tool_calls |
| `libs/deepagents/deepagents/middleware/permissions.py` | 文件系统权限控制 |
| `libs/deepagents/deepagents/backends/` | Backend 协议实现（StateBackend、FilesystemBackend） |

### 12.2 CLI 与 Code 核心文件

**`deepagents-code` 交互式 TUI 端文件（`libs/code/deepagents_code/`）**：
| 文件 | 作用 |
|------|------|
| `main.py` | `dcode` 交互入口、参数解析 |
| `app.py` | Textual TUI 主应用 |
| `agent.py` | Agent 会话管理 |
| `config.py` | 配置加载 |
| `mcp_tools.py` | MCP 服务器集成 |
| `sessions.py` | 会话持久化 |
| `textual_adapter.py` | Textual 组件封装 |
| `widgets/` | UI 组件 |

**`deepagents-cli` 部署 CLI 端文件（`libs/cli/deepagents_cli/`）**：
| 文件 | 作用 |
|------|------|
| `main.py` | `deepagents` 入口、`init`/`dev`/`deploy` 命令路由 |

### 12.3 文档矩阵（Deep Agents 四象限）

| 文件 | 语言 | 子 Agent / `task` |
|------|------|-------------------|
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md` | 英 | 无 |
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md` | 英 | 默认 |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md` | 中 | 无 |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md` | 中 | 默认 |

---

## 第十三章 追加记录

*（待补充历史问答与更新日志）*

---

**维护说明**：
- 升级 `deepagents` / `langchain` 后请对照上游源码更新本文档。
- 新增功能请在对应章节追加，并在本章记录变更日期与内容摘要。
- 保持与 DeerFlow 文档范式一致，便于跨框架对比学习。
