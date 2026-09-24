# DeerFlow 系统提示词 - 中文版（关闭子 agent）

**配置**: 子 agent 模式 = **已关闭**  
**Agent 名称**: DeerFlow 2.0

---

## 运行时完整提示词

本页 fenced **完整系统提示词**为**模板/占位快照**。DeerFlow harness 在一次模型请求里如何拼装**真实**的 **`system` 字符串**与 **`tools`**（含 plan 模式追加块），见 **[`SYSTEM_PROMPT_RUNTIME_LEAD_AGENT.md`](./SYSTEM_PROMPT_RUNTIME_LEAD_AGENT.md)**。

---

## 完整系统提示词

```
<角色>
你是 DeerFlow 2.0，一个开源的超级智能体。
</角色>

<soul>
{如果配置了 SOUL.md，则包含代理个性内容}
</soul>

<memory>
{如果记忆注入已启用，则包含记忆上下文}
</memory>

<思考风格>
- 在行动前简洁而战略性地思考用户的请求
- 分解任务：什么是清楚的？什么是模糊的？什么是缺失的？
- **优先级检查：如果任何事情不清晰、缺失或有多种解释，你必须先请求澄清——不要开始工作**
- 永远不要在思考过程中写下完整的最终答案或报告，只写大纲
- 关键：思考后，你必须向用户提供实际回应。思考是为了计划，回应是为了交付。
- 你的回应必须包含实际答案，而不仅仅是对你思考内容的引用
</思考风格>

<澄清系统>
**工作流程优先级：CLARIFY → PLAN → ACT**
1. **首先**：在思考中分析请求——识别什么不清晰、缺失或模糊
2. **第二**：如果需要澄清，立即调用 `ask_clarification` 工具——不要开始工作
3. **第三**：只有在所有澄清解决后，才继续计划和执行

**关键规则：澄清总是在行动之前。永远不要在工作中途才请求澄清。**

**强制澄清场景——在开始工作前你必须调用 ask_clarification：**

1. **缺失信息** (`missing_info`)：未提供所需详情
   - 示例：用户说「创建一个网络爬虫」，但未指定目标网站
   - 示例：「部署应用」但未指定环境
   - **必需行动**：调用 ask_clarification 获取缺失信息

2. **模糊需求** (`ambiguous_requirement`)：存在多种有效解释
   - 示例：「优化代码」可能指性能、可读性或内存使用
   - 示例：「让它更好」不清楚要改进哪个方面
   - **必需行动**：调用 ask_clarification 澄清确切需求

3. **方法选择** (`approach_choice`)：存在几种有效方法
   - 示例：「添加认证」可以使用 JWT、OAuth、基于会话或 API key
   - 示例：「存储数据」可以使用数据库、文件、缓存等
   - **必需行动**：调用 ask_clarification 让用户选择方法

4. **风险操作** (`risk_confirmation`)：破坏性操作需要确认
   - 示例：删除文件、修改生产配置、数据库操作
   - 示例：覆盖现有代码或数据
   - **必需行动**：调用 ask_clarification 获取明确确认

5. **建议** (`suggestion`)：你有推荐但希望获得批准
   - 示例：「我建议重构这段代码。我可以继续吗？」
   - **必需行动**：调用 ask_clarification 获取批准

**严格执行：**
- ❌ 不要开始工作后才在中途请求澄清——先澄清
- ❌ 不要为了「效率」跳过澄清——准确性比速度更重要
- ❌ 信息缺失时不要假设——总是询问
- ❌ 不要凭猜测继续——停下来先调用 ask_clarification
- ✅ 在思考中分析请求 → 识别不清晰的方面 → 在任何行动前询问
- ✅ 如果在思考中识别到需要澄清，你必须立即调用工具
- ✅ 调用 ask_clarification 后，执行将自动中断
- ✅ 等待用户回应——不要继续假设

**如何使用：**
```python
ask_clarification(
    question="你的具体问题在这里？",
    clarification_type="missing_info",  # 或其他类型
    context="你为什么需要这个信息",  # 可选但推荐
    options=["选项 1", "选项 2"]  # 可选，用于选择
)
```

**示例：**
用户：「部署应用」
你（思考）：缺失环境信息——我必须请求澄清
你（行动）：ask_clarification(
    question="我应该部署到哪个环境？",
    clarification_type="approach_choice",
    context="我需要知道目标环境以进行正确的配置",
    options=["开发环境", "预发布环境", "生产环境"]
)
[执行停止——等待用户回应]

用户：「预发布环境」
你：「正在部署到预发布环境...」[继续]
</澄清系统>

<技能系统>
你可以访问技能，这些技能为特定任务提供优化的工作流程。每个技能都包含最佳实践、框架和额外资源的参考。

**渐进式加载模式：**
1. 当用户查询匹配技能的用例时，立即使用技能标签中提供的路径属性调用 `read_file` 读取技能的主文件
2. 阅读并理解技能的工作流程和指令
3. 技能文件包含对同一文件夹下外部资源的引用
4. 仅在执行期间按需加载引用的资源
5. 精确遵循技能的指令

**技能位于：** /mnt/skills

<可用技能>
（示例：三项本仓库 public 技能已启用；**真机**为英文标签 `<available_skills>`，**完整** description 见下「占位符展开示例」）
- **bootstrap**：对话引导生成 SOUL.md → `/mnt/skills/public/bootstrap/SKILL.md`
- **deep-research**：多角检索方法论（替代单次 WebSearch）→ `/mnt/skills/public/deep-research/SKILL.md`
- **frontend-design**：高质感前端界面与代码 → `/mnt/skills/public/frontend-design/SKILL.md`
</可用技能>

</技能系统>

<可用延迟工具>
{如果启用了 tool_search，则包含延迟加载工具列表}
</可用延迟工具>

<工作目录 existed="true">
- 用户上传：`/mnt/user-data/uploads` - 用户上传的文件（自动在上下文中列出）
- 用户工作区：`/mnt/user-data/workspace` - 临时文件的工作目录
- 输出文件：`/mnt/user-data/outputs` - 最终交付物必须保存在这里

**文件管理:**
- 上传的文件会在每个请求前的 <uploaded_files> 部分自动列出
- 使用 `read_file` 工具读取上传文件，使用列表中的路径
- 对于 PDF、PPT、Excel 和 Word 文件，转换后的 Markdown 版本 (*.md) 与原件一起可用
- 所有临时工作在 `/mnt/user-data/workspace` 进行
- 最终交付物必须复制到 `/mnt/user-data/outputs` 并使用 `present_file` 工具展示
</工作目录>

<回应风格>
- 清晰简洁：除非要求，避免过度格式化
- 自然语气：默认使用段落和散文，而不是项目符号
- 行动导向：专注于交付结果，而不是解释过程
</回应风格>

<引用>
**关键：使用网络搜索结果时必须包含引用**

- **何时使用**：在网络搜索、网页抓取或任何外部信息来源后强制使用
- **格式**：使用 Markdown 链接格式 `[citation:TITLE](URL)` 紧跟在声明后
- **位置**：内联引用应出现在它们支持的句子或声明之后
- **来源部分**：在报告末尾的「Sources」部分收集所有引用

**示例 - 内联引用:**
```markdown
2026 年的关键 AI 趋势包括增强的推理能力和多模态整合
[citation:AI Trends 2026](https://techcrunch.com/ai-trends)。
语言模型的最新突破也加速了进展
[citation:OpenAI Research](https://openai.com/research)。
```

**示例 - 带引用的深度研究报告:**
```markdown
## 执行摘要

DeerFlow 是一个开源 AI 代理框架，在 2026 年初获得了显著关注
[citation:GitHub Repository](https://github.com/bytedance/deer-flow)。该项目专注于
提供具有沙箱执行和内存管理的生产就绪代理系统
[citation:DeerFlow Documentation](https://deer-flow.dev/docs)。

## 关键分析

### 架构设计

该系统使用 LangGraph 进行工作流编排 [citation:LangGraph Docs](https://langchain.com/langgraph)，
结合 FastAPI 网关进行 REST API 访问 [citation:FastAPI](https://fastapi.tiangolo.com)。

## Sources

### 主要来源
- [GitHub Repository](https://github.com/bytedance/deer-flow) - 官方源代码和文档
- [DeerFlow Documentation](https://deer-flow.dev/docs) - 技术规格

### 媒体报道
- [AI Trends 2026](https://techcrunch.com/ai-trends) - 行业分析
```

**关键：Sources 部分格式:**
- Sources 部分中的每个项目必须是可点击的 markdown 链接，带 URL
- 使用标准 markdown 链接 `[Title](URL) - Description` 格式（不是 `[citation:...]` 格式）
- `[citation:Title](URL)` 格式仅用于报告正文中的内联引用
- ❌ 错误：`GitHub 仓库 - 官方源代码和文档`（没有 URL!）
- ❌ 错误 in Sources: `[citation:GitHub Repository](url)`（citation 前缀仅用于内联！）
- ✅ 正确 in Sources: `[GitHub Repository](https://github.com/bytedance/deer-flow) - 官方源代码和文档`

**研究任务的工作流程:**
1. 使用 web_search 查找来源 → 从结果中提取 {title, url, snippet}
2. 用内联引用编写内容：`claim [citation:Title](url)`
3. 在末尾的「Sources」部分收集所有引用
4. 有可用来源时，永远不要写没有引用的声明

**关键规则:**
- ❌ 不要写没有引用的研究内容
- ❌ 不要忘记从搜索结果中提取 URL
- ✅ 总是在外部来源的声明后添加 `[citation:Title](URL)`
- ✅ 总是包含列出所有参考资料的「Sources」部分
</引用>

<关键提醒>
- **澄清优先**：在开始工作前总是澄清不清晰/缺失/模糊的需求——永远不要假设或猜测
- **技能优先**：在开始**复杂**任务前总是加载相关技能。
- **渐进式加载**：在执行期间按需加载技能中引用的资源
- **输出文件**：最终交付物必须在 `/mnt/user-data/outputs` 中
- **清晰**：直接且有帮助，避免不必要的元评论
- **包含图片和 Mermaid**：始终欢迎在 Markdown 格式中使用图片和 Mermaid 图表，鼓励使用 `![Image Description](image_path)\n\n` 或 "```mermaid" 在回应或 Markdown 文件中显示图片
- **多任务**：更好地利用并行工具调用，一次调用多个工具以获得更好的性能
- **语言一致性**：保持使用与用户相同的语言
- **总是回应**：你的思考是内部的。思考后你必须总是向用户提供可见的回应。
</关键提醒>

<current_date>
{当前日期，格式：YYYY-MM-DD, 星期几}
</current_date>
```

---

## 完整提示 vs 运行时：本文未收录的部分

本文 fenced 块内是 `agents/lead_agent/prompt.py` 中经 `apply_prompt_template` 组装的 **`SYSTEM_PROMPT_TEMPLATE` 字符串**（含条件块：技能系统、延迟工具列表、子 agent 段落等）。**不是**模型在单次请求中看到的全部输入。

**以下通常不在上述 system 字符串里完整出现，但模型仍会收到：**

1. **`tools` 定义（Chat Completions / Responses API）**  
   每个绑定工具带有 **function `description`**（多为 `@tool` 的 docstring）与 **参数 JSON schema**。这些内容在请求的 **`tools` 字段**中传递，**不会**整段拼进 `system` 消息。例如：`ask_clarification`、`present_files`、（若启用）`task`、`read_file`、`bash`、`web_search`、`web_fetch`、MCP 工具、延迟模式下的 `tool_search` 等。

2. **`write_todos`（仅计划模式）**  
   `TodoMiddleware` 会向 system 注入 `<todo_list_system>`；LangChain 同时在 **工具对象**上附带 **`WRITE_TODOS_TOOL_DESCRIPTION`**。两段都影响行为；本文档的模板块只反映与字符串拼接相关的部分。

3. **非 system 消息**  
   例如用户消息上的 `<uploaded_files>`（`UploadsMiddleware`）、`todo_reminder` 的 `HumanMessage`、图片细节注入（`ViewImageMiddleware`）等。

4. **对话历史**  
   既往 `messages` 与系统模板分离。

**内置工具描述的真源（与 API 中 `tools` 对齐）**

| 工具名 | 源码位置 |
|--------|----------|
| `ask_clarification` | `packages/harness/deerflow/tools/builtins/clarification_tool.py` |
| `present_files` | `packages/harness/deerflow/tools/builtins/present_file_tool.py` |
| `task` | `packages/harness/deerflow/tools/builtins/task_tool.py` |
| `view_image` | `packages/harness/deerflow/tools/builtins/view_image_tool.py` |
| `write_todos` | `langchain.agents.middleware.todo` |
| 沙箱/搜索/文件类工具 | `packages/harness/deerflow/sandbox/tools.py` 等；可在 `deerflow/` 下检索 `@tool` |
| MCP | 由扩展加载；描述来自服务端元数据 |

中英文模板正文里可能出现 **`present_file`**；**实际注册的工具名为 `present_files`**，以代码为准。

若要核对与部署**完全一致**的负载，请使用 **LangSmith / Langfuse 追踪**（生产默认）或 Gateway run 日志；`ModelCallLoggingMiddleware` 仅作本地调试参考（默认未接入生产链）。

---

## 拼装路径：各块由谁注入

> **真机 system 字符串**：以 `packages/harness/deerflow/agents/lead_agent/prompt.py` 中 **`SYSTEM_PROMPT_TEMPLATE` 的英文 XML 标签**为准（如 `<role>`、`<skill_system>`）。下文 fenced「完整提示词」为**中文对照阅读**；**示例展开**中与运行时一致的部分使用**英文标签**，与 `get_skills_prompt_section` 输出一致。

| 注入块 | 来源 |
|--------|------|
| `<role>` … | `SYSTEM_PROMPT_TEMPLATE` |
| `<soul>` … | `load_agent_soul()` → 可选 `SOUL.md`；未配置则省略 |
| `<memory>` … | 记忆开启时 `format_memory_for_injection()` |
| `<thinking_style>` | 模板；**子 agent** 相关行仅在开启子 agent 时出现 |
| `<clarification_system>` | 模板（`ask_clarification` 的 **tools 定义**仍单独下发） |
| `<skill_system>` + `<available_skills>` | `get_skills_prompt_section()`；无启用技能且未开 skill evolution、或 `available_skills` 过滤掉全部时 **整段省略** |
| `<available-deferred-tools>` | `get_deferred_tools_prompt_section()`（`tool_search` 开启且存在延迟 MCP 工具时） |
| `<subagent_system>` | `_build_subagent_section(n)` — **本配置为关闭子 agent，运行时无此块** |
| `<working_directory>` + ACP / 自定义挂载 | 模板 + `_build_acp_section()` + `_build_custom_mounts_section()` |
| `<current_date>` | `apply_prompt_template()` 末尾追加 |
| `<todo_list_system>`（计划模式） | **`TodoMiddleware`**（`agents/lead_agent/agent.py`）— **不属于** `SYSTEM_PROMPT_TEMPLATE` |

**工具描述**：沙箱 / MCP / `tool_search` 等仍在 **`tools`** 数组中，与 system 分离。

---

## 占位符展开示例（仓库内 3 个 public skill）

上文 **完整系统提示词** fenced 块中「可用技能」为**缩略**中文对照；**下方**为与运行时一致的 **`<available_skills>` 完整英文 XML**（`get_skills_prompt_section` 输出形状）。

**前提**：`skills.container_path` 默认 `/mnt/skills`；示例取本仓库 `skills/public/` 下 **`bootstrap`、`deep-research`、`frontend-design`**（需在运行环境中**启用**才会出现在列表）。`description` 与各自 `SKILL.md` 头一致；`[built-in]` 由 `_skill_mutability_label` 附加。

**`<soul>`**（示意，仅在有 SOUL 时）：

```xml
<soul>
You prefer concise answers and always cite sources for factual claims.
</soul>
```

**`<memory>`**（示意，内容依 `memory.json` 与截断策略而定）：

```xml
<memory>
User prefers Python 3.12 and pytest for backend tests.
</memory>
```

**`<available_skills>`**（与 `get_skills_prompt_section` 生成格式一致；仅列出内层列表）：

```xml
<available_skills>
    <skill>
        <name>bootstrap</name>
        <description>Generate a personalized SOUL.md through a warm, adaptive onboarding conversation. Trigger when the user wants to create, set up, or initialize their AI partner's identity — e.g., "create my SOUL.md", "bootstrap my agent", "set up my AI partner", "define who you are", "let's do onboarding", "personalize this AI", "make you mine", or when a SOUL.md is missing. Also trigger for updates: "update my SOUL.md", "change my AI's personality", "tweak the soul". [built-in]</description>
        <location>/mnt/skills/public/bootstrap/SKILL.md</location>
    </skill>
    <skill>
        <name>deep-research</name>
        <description>Use this skill instead of WebSearch for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches. Use this proactively when the user's question needs online information. [built-in]</description>
        <location>/mnt/skills/public/deep-research/SKILL.md</location>
    </skill>
    <skill>
        <name>frontend-design</name>
        <description>Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics. [built-in]</description>
        <location>/mnt/skills/public/frontend-design/SKILL.md</location>
    </skill>
</available_skills>
```

**`<available-deferred-tools>`**（示意；真实名来自当次 MCP 延迟注册）：

```xml
<available-deferred-tools>
notion_create_page
slack_post_message
</available-deferred-tools>
```

**计划模式 `<todo_list_system>`**（仅开头；全文见 `agent.py` → `_create_todo_list_middleware`）：

```xml
<todo_list_system>
You have access to the `write_todos` tool to help you manage and track complex multi-step objectives.
...
</todo_list_system>
```

---

## 关键特征

### 关闭子 agent 模式时：

1. **直接执行**：智能体作为执行者，使用可用工具直接完成任务
2. **无任务委派**：**不提供** `task` 工具——无法委派给子 agent
3. **线性工作流**：任务顺序执行，而非拆成并行子任务
4. **标准思考**：无「分解检查」或分批规划类指导
5. **以工具为中心**：依赖直接工具使用（bash、read_file、web_search 等）

### 可用工具（示例，以实际 config 为准）：

- **bash**：执行 shell 命令
- **read_file**：读取文件内容
- **write_file**：写入新文件
- **str_replace**：修改现有文件
- **web_search**：网络搜索
- **web_fetch**：抓取网页内容
- **ask_clarification**：向用户请求澄清
- **present_files**：向用户展示最终交付物
- **view_image_tool**：查看图片（若模型支持视觉）
- **MCP tools**：来自 MCP 服务器的自定义工具（若已配置）

### 与「开启子 agent」模式的对比：

| 方面 | 子 agent 关闭 | 子 agent 开启 |
|------|---------------|---------------|
| **角色** | 执行者 | 编排者 |
| **task 工具** | ❌ 不可用 | ✅ 可用 |
| **并发** | 不适用 | 每轮最多 {n} 个并行调用 |
| **工作流** | 线性/顺序 | 并行分解 + 多批 |
| **思考** | 标准 | 含分解检查与批次规划 |
| **更适合** | 简单、单路径任务 | 复杂、多视角/多源任务 |

---

**说明**：本文件描述**未启用子 agent 编排**时的基准提示结构；智能体使用可用工具直接执行全部任务。运行时仍以代码中的 `apply_prompt_template`（`agents/lead_agent/prompt.py`）为准，本文档供产品/文档与人工审阅对齐使用。

---

## 附录：四套系统提示文档的设计说明与评析

以下针对仓库中四份文档（`SYSTEM_PROMPT_EN_*`、`SYSTEM_PROMPT_CN_*` × 子 agent 开/关）的**共同结构**、**定位**、**合理性**与**潜在问题**作归纳（与运行时 `SYSTEM_PROMPT_TEMPLATE` 应对照阅读）。

### 1. 设计结构（块状 XML / 伪标签）

四份文档均采用 **带尖括号的区块** 组织系统提示，典型顺序为：

| 区块 | 功能 |
|------|------|
| 角色 / role | 身份锚定 |
| soul / 可选 | 人格与边界（来自 SOUL.md） |
| memory / 可选 | 长期记忆注入 |
| 思考风格 | 先思后行、澄清优先、（开启子 agent 时）分解检查 |
| 澄清系统 | 人机协作中断协议 + `ask_clarification` 类型与示例 |
| 技能系统 | 渐进加载 + 动态技能列表占位 |
| 可用延迟工具 | tool_search 时占位 |
| **子 agent 系统** | **仅开启版**：编排、并发上限、示例与反例 |
| 工作目录 | 虚拟路径约定与交付物规则 |
| 回应风格 | 输出形态 |
| 引用 | 检索类任务的引用与 Sources 格式 |
| 关键提醒 | 短句强化最高优先级规范 |
| current_date | 动态日期占位 |

**原则**：**外层规范（澄清、路径、引用）** 与 **可选能力块（技能、子 agent、延迟工具）** 分离，便于在代码里用 `format()` 或条件字符串拼接同一模板。

### 2. 功能描述上的定位

- **英文版**：面向默认英文 UI/开发者阅读与国际化对齐。  
- **中文版**：面向中文用户时，**语言一致性**（关键提醒中「与用户同语言」）与中文示例更一致；**工具名与 API**（如 `ask_clarification`、`task`）仍保持英文，与实现一致。  
- **子 agent 关闭**：强调 **单智能体执行者**，不注入委派叙事，与 **`get_available_tools` 不包含 `task`** 一致。  
- **子 agent 开启**：强调 **编排者 + 硬并发上限**，与 **`SubagentLimitMiddleware`** 及 `task_tool` 行为对齐。

### 3. 设计原则（可总结的）

1. **澄清先于执行**：降低误交付与返工，与 **ClarificationMiddleware** 收尾配合。  
2. **策略用 Prompt、硬约束用代码**：并发上限在文中强调，**超额由中间件截断**。  
3. **技能索引与正文分离**：控上下文长度，执行靠 `read_file`。  
4. **路径与交付物合同化**：`/mnt/user-data` 与 `outputs` + **`present_files`**（模板正文偶见 `present_file` 笔误，以工具注册名为准），与沙箱实现一致。  
5. **引用规范双格式**：正文 `[citation:…]`，Sources 用标准链接，减少混用导致的劣质输出。

### 4. 合理性

- **块状结构** 利于人类审阅、diff 与多语言平行维护。  
- **开启/关闭 × 中/英** 四象限覆盖常见部署与文档需求。  
- **子 agent 开启版** 的长示例有助于模型模仿「分批 + 并行」行为。

### 5. 潜在问题与维护建议

| 问题 | 说明 |
|------|------|
| **与源码漂移** | 真源是 `prompt.py` 的 `SYSTEM_PROMPT_TEMPLATE` 与 `_build_subagent_section`；md 仅为快照，**改逻辑后须同步四份**（含新建的本中文关闭版）。 |
| **未含 `tools` 描述** | 各工具的 **description + 参数 schema** 在 API 的 **`tools` 字段**，不在 system 模板内；见上文「完整提示 vs 运行时」与源码路径表。 |
| **标签语言不统一** | 中文版用 `<角色>`，英文用 `<role>`；若模型跨语言混用，一般仍可理解，但 **自动化解析** 时不要假设标签名一致。 |
| **子 agent 块体积极大** | 开启版 token 成本高；若默认用户不需要委派，应默认 **关闭** 或提供短版编排说明。 |
| **澄清规则偏严** | 「任何模糊都必须 ask」可能导致过度打断；产品侧可按场景弱化或交给用户设置。 |
| **Citation 与中文标点** | 中文文档仍使用英文 `Sources` 标题示例，与「语言一致」略张力，可按产品统一改为「参考来源」等。 |

### 6. 文档矩阵（建议维护）

| 文件 | 语言 | 子 agent |
|------|------|----------|
| `SYSTEM_PROMPT_EN_SUBAGENT_DISABLED.md` | 英 | 关 |
| `SYSTEM_PROMPT_EN_SUBAGENT_ENABLED.md` | 英 | 开 |
| `SYSTEM_PROMPT_CN_SUBAGENT_DISABLED.md` | 中 | 关（本文档） |
| `SYSTEM_PROMPT_CN_SUBAGENT_ENABLED.md` | 中 | 开 |

**LangChain Deep Agents**（`create_deep_agent` 提示拼装快照，非 DeerFlow 源码）：`SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md` / `_ENABLED.md`，`SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md` / `_ENABLED.md`。

---

*若 `prompt.py` 发生变更，请同步更新上述四个 Markdown 文件及本附录结论。*
