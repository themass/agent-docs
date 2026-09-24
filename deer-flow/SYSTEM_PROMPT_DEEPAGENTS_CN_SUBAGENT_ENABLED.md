# LangChain Deep Agents — 系统提示拼装（中文版，**默认 `create_deep_agent`**）

**配置**: 子智能体 / **`task`** = **启用**（`create_deep_agent` 默认行为）  
**快照版本**: `deepagents==0.5.1`  
**入口**: `deepagents.graph.create_deep_agent`

---

## 运行时完整提示词

下文 fenced 为**逻辑/结构快照**。要与已安装 **`deepagents`** wheel **逐字对齐**的 **默认 stock `create_deep_agent` 运行时 `system` 全文**与主要工具 **`description`**，见 **[`SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md`](./SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md)**。

---

## 说明

默认 **`create_deep_agent`** **始终**注册 **`SubAgentMiddleware`**，因此会：

1. 通过中间件把 **`TASK_SYSTEM_PROMPT`** 拼进**系统消息**；  
2. 注册 **`task` 工具**；其 **函数级 `description`** 由 **`TASK_TOOL_DESCRIPTION`** 模板经 `{available_agents}` 展开后，与 **tools** 一并提供给模型（**不属于** system 字符串本身）。

**其它工具同理**：`write_todos`、文件系统各工具、可选 `execute` 以及 **`task`** 都在 **`tools`** 通道带有 **description + 参数 schema**；下方 fenced 的 system 快照只与之**部分重叠**。完整对照见下文 **「完整性」**。

---

## 拼装后的系统消息（逻辑块）

占位符 `{user_system}`、`{agent_memory}`、`{skills_locations}`、`{skills_list}` 与 **关闭子 agent** 文档相同。

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
    （与「关闭子 agent」中文版相同：从文件加载、用 `edit_file` 更新、何时记/不记、安全红线等 —— 完整英文与示例见 `deepagents/middleware/memory.py`）
</memory_guidelines>

## 技能系统
（与「关闭子 agent」中文版相同；仅当 `skills=...` 时注入 —— 模板见 `deepagents/middleware/skills.py`）

## 文件系统工具 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`
（与「关闭子 agent」中文版相同）

## 执行工具 `execute`
（与「关闭子 agent」中文版相同；依赖支持沙箱的后端）

## `task`（子智能体生成器）

你可以使用 **`task` 工具**启动**短生命周期子智能体**来处理隔离任务。这些智能体是**临时的**——仅在该任务期间存在，并返回**单一结果**。

**何时使用 `task`：**
- 任务复杂、多步，且可以**完整委托**在隔离环境中完成  
- 任务与其他任务**独立**，可**并行**执行  
- 需要集中推理或大量 token/上下文，避免拖垮主会话  
- 沙箱能提高可靠性（如代码执行、结构化检索、数据整理）  
- 你只关心子智能体的**最终结果**，不关心其中间推理过程（例如大量调研后返回合成报告、多步计算/查询后返回简明答案）

**子智能体生命周期：**
1. **生成（Spawn）** — 给出清晰角色、指令与期望输出  
2. **运行（Run）** — 子智能体自主完成任务  
3. **返回（Return）** — 子智能体给出单一结构化结果  
4. **合并（Reconcile）** — 在主线程中吸收或综合该结果  

**何时不使用 `task`：**
- 你需要在子智能体结束后仍看到**中间推理或步骤**（`task` 会隐藏这些）  
- 任务很琐碎（少数几次工具调用或简单查询即可）  
- 委派不能降低 token、复杂度或上下文切换成本  
- 拆分只会增加延迟而没有收益  

## 使用 `task` 的重要备忘
- 在可能的情况下**并行**推进工作：对 **tool_calls** 与 **tasks（子智能体）** 皆然；彼此独立的步骤应并行发起，以节省用户时间。  
- 在多部分目标中，用 `task` **隔离**相互独立的子任务。  
- 当你有**复杂、多步且与其他待办相对独立**的任务时，应使用 `task`；这些子智能体能力强、效率高。
```

**说明**：`write_todos`、memory、skills、filesystem 的**英文真源**与 **关闭子 agent** 的英文文档一致；中文版在 **关闭** 文档中已全文翻译主要段落，**开启**版仅完整展开 **`task`** 段；memory/skills 长指南若需全文中文，可与关闭版合并维护。

---

## 完整性：system 消息 vs 完整模型输入

- **System 消息**：`user_system` + `BASE_AGENT_PROMPT` 叙事（含 `write_todos` **正文**、memory/skills/filesystem、**`TASK_SYSTEM_PROMPT`** 编排说明等）。  
- **Tool 定义**：**独立**负载 — 各工具的 **`description`** 与 **JSON schema**（`write_todos` 含 LangChain **`WRITE_TODOS_TOOL_DESCRIPTION`**，文件系统/execute，以及 **`task`** 的 **`TASK_TOOL_DESCRIPTION`** 与 `<example>` 等；下文「函数说明」仅为**摘要**，**不能保证**与线上一致）。  
- **其它**：历史消息；摘要中间件可能改写旧轮次；HITL / 缓存行为。

本文档为仓库内**维护用快照**；若要逐字节核对，请固定文档标注的包版本或对出站请求打日志。

---

## `task` 工具的函数说明（挂在工具上，不在 system 里）

模型实际还会看到 **工具 schema** 中的长描述，其内容由 `TASK_TOOL_DESCRIPTION` 经 `{available_agents}` 替换得到，例如默认包含：

- **`general-purpose`**：用于研究复杂问题、搜索文件与内容、执行多步任务；在关键词/文件搜索不确定能否前几轮命中时，应用该智能体代为搜索；**与主智能体拥有相同工具集**。

文中还包括：**并行启动多个子智能体**、**结果对用户不可见需主智能体摘要回传**、**每次调用无状态**、**何时不要用 task（极简单任务直接调工具）** 以及多段 `<example>`（见 **`deepagents/middleware/subagents.py`** 全文）。

---

## 默认中间件链（`create_deep_agent` 主图）

与英文 **`SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md`** 一致：

1. `TodoListMiddleware`  
2. `MemoryMiddleware`（若配置了 `memory`）  
3. `SkillsMiddleware`（若配置了 `skills`）  
4. `FilesystemMiddleware`  
5. **`SubAgentMiddleware`**  
6. `SummarizationMiddleware`  
7. `AnthropicPromptCachingMiddleware`  
8. `PatchToolCallsMiddleware`  
9. 用户传入的 `middleware`  
10. `HumanInTheLoopMiddleware`（若配置了 `interrupt_on`）

子智能体（如 `general-purpose`）自带 **Todo + Filesystem + Summarization + …** 栈，详见 `graph.py` 中 `gp_middleware`。

---

## `{skills_locations}` / `{skills_list}` 示例（三个本仓库技能）

与 **`SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md`** 中示例相同：由 `SkillsMiddleware` 生成。假设 `skills/public/` 映射为 `/skills/public/`：

**`{skills_locations}`**

```markdown
**Public Skills**: `/skills/public/`
```

**`{skills_list}`**

```markdown
- **bootstrap**: Generate a personalized SOUL.md through a warm, adaptive onboarding conversation. Trigger when the user wants to create, set up, or initialize their AI partner's identity — e.g., "create my SOUL.md", "bootstrap my agent", "set up my AI partner", "define who you are", "let's do onboarding", "personalize this AI", "make you mine", or when a SOUL.md is missing. Also trigger for updates: "update my SOUL.md", "change my AI's personality", "tweak the soul".
  -> Read `/skills/public/bootstrap/SKILL.md` for full instructions
- **deep-research**: Use this skill instead of WebSearch for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches. Use this proactively when the user's question needs online information.
  -> Read `/skills/public/deep-research/SKILL.md` for full instructions
- **frontend-design**: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics. (License: Complete terms in LICENSE.txt)
  -> Read `/skills/public/frontend-design/SKILL.md` for full instructions
```

**`task`**：编排说明在 **`TASK_SYSTEM_PROMPT`**（系统侧）；**完整**调用约定在工具侧的 **`TASK_TOOL_DESCRIPTION`**（`deepagents/middleware/subagents.py`），勿与 system 正文混为一谈。

---

## 源码索引

| 片段 | 模块 / 符号 |
|------|-------------|
| `BASE_AGENT_PROMPT`、主图中间件顺序 | `deepagents/graph.py` |
| `TASK_SYSTEM_PROMPT`、`TASK_TOOL_DESCRIPTION`、`GENERAL_PURPOSE_SUBAGENT` | `deepagents/middleware/subagents.py` |
| 其余块 | 同关闭版文档表 |

---

## 文档矩阵（Deep Agents 四象限）

| 文件 | 语言 | 子 agent / `task` |
|------|------|-------------------|
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md` | 英 | 无 |
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md` | 英 | 默认 |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md` | 中 | 无 |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md` | 中 | 默认（本文） |

---

*升级 `deepagents` / `langchain` 后请对照上游源码更新四个 Markdown 快照。*
