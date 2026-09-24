# LangChain Deep Agents — 系统提示拼装（中文版，**无 `task` / 子智能体**）

**配置**: 子智能体 / **`task` 工具** = **不存在**（需自定义装配；见下文说明）  
**快照版本**: `deepagents==0.5.1`（你本地安装版本可能不同；升级时请 diff 上游）  
**入口**: 不使用 `SubAgentMiddleware` 的 `create_agent`，或仅挂载 Deep Agents 部分中间件。

---

## 运行时完整提示词

本文描述**去掉** `SubAgentMiddleware` 的**自定义**栈。可与安装包 **逐字对照** 的参考正文见 **[`SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md`](./SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md)**（**§2.1**：无 `task` 段的 system；**§3**：工具 `description`）。**默认 stock** `create_deep_agent` 的完整 system 见该文 **§2**。

---

## 与默认 `create_deep_agent` 的关系

官方 **`create_deep_agent`**（`deepagents/graph.py`）**始终**挂载 **`SubAgentMiddleware`**，会注册 **`task` 工具**并注入 **`TASK_SYSTEM_PROMPT`**。该辅助函数**没有**「关闭子智能体」的官方开关。

本文描述的是：**与默认主图相同、但去掉子智能体相关能力**时的**逻辑系统提示**：保留规划（`write_todos`）、可选 memory/skills、文件系统（及可选 `execute`）、摘要、缓存、工具调用修补等 —— **不包含 `task` 相关段落，也无 `task` 工具**。

---

## 拼装后的系统消息（逻辑块，典型包裹顺序）

占位符：

- `{user_system}` — 传入 `create_agent` 的 `system_prompt`（若有）。  
- `{agent_memory}` — 从文件加载的记忆正文，或 `(No memory loaded)`。  
- `{skills_locations}` / `{skills_list}` — 配置 `skills=...` 时由 `SkillsMiddleware` 注入。

```
{user_system}

为了完成用户向你提出的目标，你可以使用若干标准工具。

## `write_todos`

你可以使用 `write_todos` 工具来管理和规划复杂目标。
对于复杂目标，应使用该工具，确保跟踪每一个必要步骤，并让用户看到你的进展。
该工具非常有助于规划复杂目标，并将较大的复杂目标拆解为更小的步骤。

关键在于：每完成一步就要尽快将对应待办标为完成，不要把多步攒在一起才勾选。
对于只需少数几步的简单目标，最好直接完成目标，**不要**使用该工具。
写待办会消耗时间与 token；仅在管理复杂、多步问题时使用；简单、步数少的请求不要用。

## 待办列表使用要点（务必记住）
- **不要**在同一轮里**并行**多次调用 `write_todos`。
- 执行过程中可以随时**修订**待办列表：新信息可能带来新任务，或使旧任务失效。

<agent_memory>
{agent_memory}
</agent_memory>

<memory_guidelines>
    上述 <agent_memory> 从文件系统加载。随着与用户交互，你可以通过调用 `edit_file` 工具保存新知识。

    **从反馈中学习：**
    - 你的**主要优先事项之一**是从与用户的互动中学习；这些学习可以是显式或隐式的。
    - 当你需要记住某件事时，更新记忆必须是**第一时间的即时动作**——在回复用户之前、在调用其他工具之前、在做任何其他事之前，先更新记忆。
    - 当用户说某事更好/更差时，要捕捉**原因**并编码为可复用模式。
    - 每次纠正都是永久改进的机会——不要只修眼前问题，要更新你的说明/记忆。
    - 用户在工具调用过程中打断并给反馈时，是更新记忆的良机：应先更新记忆，再改工具调用。
    - 关注纠正背后的**原则**，而非单次笔误。
    - 用户未必明说「请记住」，但只要信息对未来有用，就应立即写入记忆。

    **索取信息：**
    - 若缺少执行动作所需上下文（例如发 Slack DM 需要用户 ID/邮箱），应**明确询问**用户。
    - 优先**询问**而非臆测你不知道的信息。
    - 用户提供对未来有用的信息时，应立即更新记忆。

    **何时应更新记忆：**（用户明确要求记住、角色/行为描述、对工作的反馈、工具所需 ID、可复用的工具使用模式、新发现的偏好与流程等）

    **何时不应更新记忆：**（临时状态、一次性任务、无长期偏好价值的简单问答、寒暄、已过时信息；**绝不**存储 API 密钥、令牌、密码；用户若提供密钥，不要回显或保存。）

    **示例：**（完整英文例见源码 `deepagents/middleware/memory.py`）
</memory_guidelines>

## 技能系统（Skills System）

你可以访问技能库，获得专门能力与领域知识。

{skills_locations}

**可用技能：**

{skills_list}

**如何使用技能（渐进披露）：**

技能采用**渐进披露**：上面只看到名称与描述，需要时再读取完整说明。

1. **判断任务是否匹配某技能**  
2. **按列表中的路径读取技能全文**  
3. **遵循 SKILL.md 中的流程与最佳实践**  
4. **引用资源时使用绝对路径**

**何时使用技能：** 用户请求匹配技能领域、需要结构化工作流或成熟模式时。

**执行技能脚本：** 若技能内含脚本，**务必**使用技能列表给出的绝对路径。

## 文件系统工具 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`

你可以通过下列工具与文件系统交互。**所有路径必须以 `/` 开头。**

- ls：列出目录（需绝对路径）  
- read_file：读文件  
- write_file：写文件  
- edit_file：编辑文件  
- glob：按模式找文件（如 `**/*.py`）  
- grep：在文件中搜索文本  

## 执行工具 `execute`

在支持沙箱的后端下，可使用 `execute` 在沙箱环境中执行 shell 命令（返回输出与退出码）。

（仅当后端实现沙箱执行协议时注入更长的执行规范；见 `deepagents/middleware/filesystem.py`。）
```

## 完整性：system 消息 vs 完整模型输入

上方 fenced 块是 **系统角色字符串** 的快照（中间件拼装的叙事）。**不等于** 运行时发往模型 API 的全部内容：

| 通道 | 模型实际收到的内容 |
|------|-------------------|
| **System 消息** | `user_system` + `BASE_AGENT_PROMPT` 各段 — 含 `write_todos` 的**正文说明**、memory/skills/filesystem 叙事等。 |
| **Tool 定义** | **独立**列表：每个工具的 **`description`** 与 **参数 JSON schema**（`write_todos`、`ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`、可选 `execute` 等）。这些内容**不会**在 system 里全文重复；LangChain 的 **`WRITE_TODOS_TOOL_DESCRIPTION`** 与 system 里 `## write_todos` 段落**可能措辞不一致**，但**都会对行为生效**。 |
| **其它** | 对话历史；`SummarizationMiddleware` 可能改写历史消息；可选 HITL、缓存相关行为。 |

**本变体不包含（刻意裁掉）**

- **`## task`（子智能体生成器）** — 即 `subagents.py` 中的 `TASK_SYSTEM_PROMPT`  
- **`task` 工具**

**动态行为**

- **`SummarizationMiddleware`**：接近上下文上限时可能摘要历史（非静态前缀）。  
- **`AnthropicPromptCachingMiddleware`、`PatchToolCallsMiddleware`**：以行为为主。  
- **`HumanInTheLoopMiddleware`**：配置 `interrupt_on` 时启用。

若要核对**与线上一致的逐字节**字符串，请固定本文档标注的 **`deepagents` / `langchain`** 版本，或对出站请求体打日志。

---

## 中间件链参考（主智能体，无子智能体）

与 `create_deep_agent` 对齐、但**去掉** `SubAgentMiddleware` 时的典型顺序：

1. `TodoListMiddleware`  
2. `MemoryMiddleware` — 若 `memory=[...]`  
3. `SkillsMiddleware` — 若 `skills=[...]`  
4. `FilesystemMiddleware`  
5. `SummarizationMiddleware`  
6. `AnthropicPromptCachingMiddleware`  
7. `PatchToolCallsMiddleware`  
8. 可选 `HumanInTheLoopMiddleware`  

传给 `create_agent` 的基底字符串：`user_system + "\n\n" + BASE_AGENT_PROMPT`（`BASE_AGENT_PROMPT` 见 `deepagents/graph.py`）。

---

## `{skills_locations}` / `{skills_list}` 示例（三个本仓库技能）

由 `SkillsMiddleware`（`deepagents/middleware/skills.py`）中 `_format_skills_locations`、`_format_skills_list` 填入 `SKILLS_SYSTEM_PROMPT`。路径为 **Backend 虚拟路径**，需与你的 `FilesystemBackend` 根目录及 `sources` 一致；下例假设将本仓库 `skills/public/` 挂到 `/skills/public/`。

**`{skills_locations}` 示例：**

```markdown
**Public Skills**: `/skills/public/`
```

**`{skills_list}` 示例**（与 DeerFlow 文档中相同的 `bootstrap`、`deep-research`、`frontend-design`，格式同上游中间件）：

```markdown
- **bootstrap**: Generate a personalized SOUL.md through a warm, adaptive onboarding conversation. Trigger when the user wants to create, set up, or initialize their AI partner's identity — e.g., "create my SOUL.md", "bootstrap my agent", "set up my AI partner", "define who you are", "let's do onboarding", "personalize this AI", "make you mine", or when a SOUL.md is missing. Also trigger for updates: "update my SOUL.md", "change my AI's personality", "tweak the soul".
  -> Read `/skills/public/bootstrap/SKILL.md` for full instructions
- **deep-research**: Use this skill instead of WebSearch for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches. Use this proactively when the user's question needs online information.
  -> Read `/skills/public/deep-research/SKILL.md` for full instructions
- **frontend-design**: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics. (License: Complete terms in LICENSE.txt)
  -> Read `/skills/public/frontend-design/SKILL.md` for full instructions
```

**`write_todos`**：长说明在 **`langchain.agents.middleware.todo`**（`WRITE_TODOS_SYSTEM_PROMPT` 与工具描述），由 `TodoListMiddleware` 注入，本文逻辑块仅摘要。

---

## 源码索引

| 片段 | 模块 / 符号 |
|------|-------------|
| `BASE_AGENT_PROMPT` | `deepagents/graph.py` |
| `WRITE_TODOS_*` | `langchain.agents.middleware.todo` |
| `MEMORY_SYSTEM_PROMPT` | `deepagents/middleware/memory.py` |
| `SKILLS_SYSTEM_PROMPT` | `deepagents/middleware/skills.py` |
| `FILESYSTEM_SYSTEM_PROMPT`、`EXECUTION_SYSTEM_PROMPT` | `deepagents/middleware/filesystem.py` |
| **默认含子智能体** | `deepagents/graph.py` → `SubAgentMiddleware` |

---

## 文档矩阵（Deep Agents 四象限）

| 文件 | 语言 | 子 agent / `task` |
|------|------|-------------------|
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md` | 英 | 无 |
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md` | 英 | 默认 |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md` | 中 | 无（本文） |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md` | 中 | 默认 |

---

*升级 `deepagents` / `langchain` 后请对照上游源码更新上述四个 Markdown 快照。*
