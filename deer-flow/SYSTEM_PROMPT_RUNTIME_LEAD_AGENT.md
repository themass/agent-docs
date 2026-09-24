# DeerFlow Lead Agent — Runtime prompt assembly（运行时拼装）

**目的**：说明 **一次模型调用前**，进入 Chat API 的 **`system` 侧内容** 与 **同请求内 `tools` 通道** 如何与 `SYSTEM_PROMPT_TEMPLATE` 文档快照区分。  
**真源**：`packages/harness/deerflow/agents/lead_agent/agent.py`（`make_lead_agent`、`_create_todo_list_middleware`）、`prompt.py`（`apply_prompt_template`）。

---

## 1. 拼装顺序（逻辑等价）

LangChain **`create_agent(..., system_prompt=..., middleware=[...])`** 中，Lead 的 **基座 system** 来自 **`apply_prompt_template(...)`**。  
**仅当** `RunnableConfig.configurable["is_plan_mode"] is True` 时，再挂上 **`TodoMiddleware`**（`TodoListMiddleware` 子类），其 **`system_prompt`** 与基座 **合并**进最终送给模型的 system 内容（与 **`write_todos` 工具的 JSON schema / description** 仍 **分离**，见 §3）。

| 段 | 条件 | 来源 |
|----|------|------|
| **A. 基座 system** | 总是 | `apply_prompt_template` → `SYSTEM_PROMPT_TEMPLATE.format(...)` + 末尾 `<current_date>` |
| **B. `<todo_list_system>`** | `is_plan_mode` | `agent.py` → `_create_todo_list_middleware` → `TodoMiddleware(system_prompt=..., tool_description=...)` 的 **`system_prompt`**（全文见 §2） |
| **C. `write_todos` 工具定义** | `is_plan_mode` | 同上 **`tool_description`**，经 LangChain 进入 **`tools`** 数组，**不是** system 字符串的一部分（全文见 §3） |

其余中间件（`SummarizationMiddleware`、`DanglingToolCallMiddleware`、`MemoryMiddleware`、`ViewImageMiddleware`、`ClarificationMiddleware` 等）主要改 **`messages`**、绑定工具列表或短路工具调用，**不**再向基座 system 追加与上表同级的长固定文案（以当前 harness 为准）。

---

## 2. 运行时追加的 system：`is_plan_mode` 时的 `<todo_list_system>`（全文）

以下与 **`agent.py`** 中字符串 **逐字一致**（仅作文档镜像；若代码变更请以仓库为准）。

```
<todo_list_system>
You have access to the `write_todos` tool to help you manage and track complex multi-step objectives.

**CRITICAL RULES:**
- Mark todos as completed IMMEDIATELY after finishing each step - do NOT batch completions
- Keep EXACTLY ONE task as `in_progress` at any time (unless tasks can run in parallel)
- Update the todo list in REAL-TIME as you work - this gives users visibility into your progress
- DO NOT use this tool for simple tasks (< 3 steps) - just complete them directly

**When to Use:**
This tool is designed for complex objectives that require systematic tracking:
- Complex multi-step tasks requiring 3+ distinct steps
- Non-trivial tasks needing careful planning and execution
- User explicitly requests a todo list
- User provides multiple tasks (numbered or comma-separated list)
- The plan may need revisions based on intermediate results

**When NOT to Use:**
- Single, straightforward tasks
- Trivial tasks (< 3 steps)
- Purely conversational or informational requests
- Simple tool calls where the approach is obvious

**Best Practices:**
- Break down complex tasks into smaller, actionable steps
- Use clear, descriptive task names
- Remove tasks that become irrelevant
- Add new tasks discovered during implementation
- Don't be afraid to revise the todo list as you learn more

**Task Management:**
Writing todos takes time and tokens - use it when helpful for managing complex problems, not for simple requests.
</todo_list_system>
```

**`is_plan_mode` 为 false**：上块 **不出现**；且 **无** `write_todos` 工具绑定（见工厂与工具装配逻辑）。

---

## 3. 同一请求内、`tools` 通道：`write_todos` 的 function `description`（全文）

以下与 **`agent.py`** 中传入 `TodoMiddleware(..., tool_description=...)` 的字符串 **逐字一致**。模型在 **tool 定义**里看到它，**不会**因本段重复而自动出现在 **system** 里。

```
Use this tool to create and manage a structured task list for complex work sessions.

**IMPORTANT: Only use this tool for complex tasks (3+ steps). For simple requests, just do the work directly.**

## When to Use

Use this tool in these scenarios:
1. **Complex multi-step tasks**: When a task requires 3 or more distinct steps or actions
2. **Non-trivial tasks**: Tasks requiring careful planning or multiple operations
3. **User explicitly requests todo list**: When the user directly asks you to track tasks
4. **Multiple tasks**: When users provide a list of things to be done
5. **Dynamic planning**: When the plan may need updates based on intermediate results

## When NOT to Use

Skip this tool when:
1. The task is straightforward and takes less than 3 steps
2. The task is trivial and tracking provides no benefit
3. The task is purely conversational or informational
4. It's clear what needs to be done and you can just do it

## How to Use

1. **Starting a task**: Mark it as `in_progress` BEFORE beginning work
2. **Completing a task**: Mark it as `completed` IMMEDIATELY after finishing
3. **Updating the list**: Add new tasks, remove irrelevant ones, or update descriptions as needed
4. **Multiple updates**: You can make several updates at once (e.g., complete one task and start the next)

## Task States

- `pending`: Task not yet started
- `in_progress`: Currently working on (can have multiple if tasks run in parallel)
- `completed`: Task finished successfully

## Task Completion Requirements

**CRITICAL: Only mark a task as completed when you have FULLY accomplished it.**

Never mark a task as completed if:
- There are unresolved issues or errors
- Work is partial or incomplete
- You encountered blockers preventing completion
- You couldn't find necessary resources or dependencies
- Quality standards haven't been met

If blocked, keep the task as `in_progress` and create a new task describing what needs to be resolved.

## Best Practices

- Create specific, actionable items
- Break complex tasks into smaller, manageable steps
- Use clear, descriptive task names
- Update task status in real-time as you work
- Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
- Remove tasks that are no longer relevant
- **IMPORTANT**: When you write the todo list, mark your first task(s) as `in_progress` immediately
- **IMPORTANT**: Unless all tasks are completed, always have at least one task `in_progress` to show progress

Being proactive with task management demonstrates thoroughness and ensures all requirements are completed successfully.

**Remember**: If you only need a few tool calls to complete a task and it's clear what to do, it's better to just do the task directly and NOT use this tool at all.
```

---

## 4. 基座 system（段 A）如何得到「字节级」当前值？

段 A 含 **动态** 内容：`<current_date>`、`<soul>`、`<memory>`、`<skill_system>`、`<available-deferred-tools>`、`<subagent_system>`（若开子 agent）等，**不应**在 Markdown 里复制第二份以免与 `prompt.py` 漂移。

在已配置好 `backend` 环境的前提下，可从仓库根执行：

```bash
cd backend
uv run python -c "
from deerflow.agents.lead_agent.prompt import apply_prompt_template
# 与 make_lead_agent 一致的参数示例：关子 agent、无 agent 级 skills 过滤时用 None
print(apply_prompt_template(subagent_enabled=False, max_concurrent_subagents=3, agent_name=None, available_skills=None))
"
```

将 **`subagent_enabled=True`**、传入 **`agent_name`**、**`available_skills`** 可与实际 run 对齐。  
**计划模式**下，将 §2 全文 **接在** 上述输出之后，即为 **system 侧** 与代码路径一致的拼装（具体是一条 `SystemMessage` 还是多段合并，以 LangChain `create_agent` / 中间件实现为准，**语义上等价于 A+B**）。

---

## 5. 与「完整模型输入」还差什么？

| 通道 | 内容 |
|------|------|
| **system** | §1 段 **A**（打印见 §4）+ 条件 **B**（§2） |
| **tools** | 全部绑定工具的名称、**description**、parameters schema（含 §3、以及 `ask_clarification`、`read_file`、MCP、`task` 等） |
| **messages** | 用户消息（可含 `<uploaded_files>`）、历史 `ToolMessage` / `AIMessage`、条件 **`todo_reminder`** `HumanMessage` 等 |

抓取 **HTTP/SDK 级完整负载**：启用 **`ModelCallLoggingMiddleware`**（`packages/harness/deerflow/agents/middlewares/model_call_logging_middleware.py`）或在外层代理抓包。

---

## 6. 与 `SYSTEM_PROMPT_*_SUBAGENT_*.md` 的关系

| 文档 | 内容 |
|------|------|
| `SYSTEM_PROMPT_EN_*.md` / `SYSTEM_PROMPT_CN_*.md` | 基座模板 **阅读用快照**（中文 fenced 为对照）；**不是**唯一真源 |
| **本文** | **运行时**在 system / tools 上 **多出来的固定块**（§2、§3）+ **如何打印段 A**（§4） |
| [`SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md`](./SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md) | LangChain **Deep Agents**（`create_deep_agent`）stock 路径下的 **完整运行时 `system`** 与主要工具 **`description`** |
