# LangChain Deep Agents — System Prompt Assembly (English, **default `create_deep_agent`**)

**Configuration**: Subagent / **`task`** = **enabled** (default `create_deep_agent`)  
**Package snapshot**: `deepagents==0.5.1`  
**Agent entrypoint**: `deepagents.graph.create_deep_agent`

---

## Runtime system message and tools

The fenced blocks below are **logical / structural snapshots**. For the **full default stock** runtime **`system` string** and the main tool **`description`** texts (aligned with the installed `deepagents` wheel), see **[`SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md`](./SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md)**.

---

## Important note

Default **`create_deep_agent`** **always** registers **`SubAgentMiddleware`**, which:

1. Appends **`TASK_SYSTEM_PROMPT`** to the system message (via middleware `wrap_model_call`).  
2. Registers the **`task`** tool whose **function `description`** is built from **`TASK_TOOL_DESCRIPTION`** with `{available_agents}` filled from registered subagents (at minimum **`general-purpose`**).

The **`task` tool description is not part of the system string**; it is sent as **tool schema** to the model alongside the system message.

**Same caveat for every tool**: filesystem tools, `write_todos`, optional `execute`, and **`task`** each carry a **function `description` + parameters** in the **`tools`** channel. The fenced system snapshot below overlaps that text only partially; see **Completeness** after the assembly block.

---

## Assembled system message (logical blocks)

Placeholders: `{user_system}`, `{agent_memory}`, `{skills_locations}`, `{skills_list}` as in the disabled variant.

```
{user_system}

In order to complete the objective that the user asks of you, you have access to a number of standard tools.

## `write_todos`

You have access to the `write_todos` tool to help you manage and plan complex objectives.
Use this tool for complex objectives to ensure that you are tracking each necessary step and giving the user visibility into your progress.
This tool is very helpful for planning complex objectives, and for breaking down these larger complex objectives into smaller steps.

It is critical that you mark todos as completed as soon as you are done with a step. Do not batch up multiple steps before marking them as completed.
For simple objectives that only require a few steps, it is better to just complete the objective directly and NOT use this tool.
Writing todos takes time and tokens, use it when it is helpful for managing complex many-step problems! But not for simple few-step requests.

## Important To-Do List Usage Notes to Remember
- The `write_todos` tool should never be called multiple times in parallel.
- Don't be afraid to revise the To-Do list as you go. New information may reveal new tasks that need to be done, or old tasks that are irrelevant.

<agent_memory> … </agent_memory> + <memory_guidelines> …
(only if memory=… configured — same as disabled doc)

## Skills System …
(only if skills=… configured)

## Filesystem Tools `ls`, `read_file`, … 
## Execute Tool `execute`
(execution paragraph only if backend supports sandbox execution)

## `task` (subagent spawner)

You have access to a `task` tool to launch short-lived subagents that handle isolated tasks. These agents are ephemeral — they live only for the duration of the task and return a single result.

When to use the task tool:
- When a task is complex and multi-step, and can be fully delegated in isolation
- When a task is independent of other tasks and can run in parallel
- When a task requires focused reasoning or heavy token/context usage that would bloat the orchestrator thread
- When sandboxing improves reliability (e.g. code execution, structured searches, data formatting)
- When you only care about the output of the subagent, and not the intermediate steps (ex. performing a lot of research and then returned a synthesized report, performing a series of computations or lookups to achieve a concise, relevant answer.)

Subagent lifecycle:
1. **Spawn** → Provide clear role, instructions, and expected output
2. **Run** → The subagent completes the task autonomously
3. **Return** → The subagent provides a single structured result
4. **Reconcile** → Incorporate or synthesize the result into the main thread

When NOT to use the task tool:
- If you need to see the intermediate reasoning or steps after the subagent has completed (the task tool hides them)
- If the task is trivial (a few tool calls or simple lookup)
- If delegating does not reduce token usage, complexity, or context switching
- If splitting would add latency without benefit

## Important Task Tool Usage Notes to Remember
- Whenever possible, parallelize the work that you do. This is true for both tool_calls, and for tasks. Whenever you have independent steps to complete - make tool_calls, or kick off tasks (subagents) in parallel to accomplish them faster. This saves time for the user, which is incredibly important.
- Remember to use the `task` tool to silo independent tasks within a multi-part objective.
- You should use the `task` tool whenever you have a complex task that will take multiple steps, and is independent from other tasks that the agent needs to complete. These agents are highly competent and efficient.
```

Full verbatim **`WRITE_TODOS_SYSTEM_PROMPT`** and **memory/skills/filesystem** blocks are identical to **`SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md`**; this file only adds the **`task`** section above.

---

## Completeness: system message vs full model input

- **System message**: narrative from `user_system` + `BASE_AGENT_PROMPT` (write_todos *prose*, memory/skills/filesystem, **`TASK_SYSTEM_PROMPT`** narrative for orchestration, …).  
- **Tool definitions**: **separate** payload — per-tool **`description`** and **JSON schema** for `write_todos` (including **`WRITE_TODOS_TOOL_DESCRIPTION`**), filesystem tools, optional `execute`, and **`task`** (**`TASK_TOOL_DESCRIPTION`** + examples — the section below is an **excerpt**, not a guarantee of wire equality).  
- **Other**: message history; summarization may rewrite older turns; HITL / caching.

Treat this repo doc as a **maintainer snapshot**. For exact bytes, use the pinned package versions or log outbound requests.

---

## `task` tool — function description (bound to tool, not system text)

After formatting `{available_agents}` with a bullet list of `name: description` for each subagent, the model receives something like:

```
Launch an ephemeral subagent to handle complex, multi-step independent tasks with isolated context windows.

Available agent types and the tools they have access to:
- general-purpose: General-purpose agent for researching complex questions, searching for files and content, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. This agent has access to all tools as the main agent.
- … (custom subagents from `subagents=[...]`)

When using the Task tool, you must specify a subagent_type parameter to select which agent type to use.

## Usage notes:
1. Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses
2. When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.
3. Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.
4. The agent's outputs should generally be trusted
5. Clearly tell the agent whether you expect it to create content, perform analysis, or just do research (search, file reads, web fetches, etc.), since it is not aware of the user's intent
6. If the agent description mentions that it should be used proactively, then you should try your best to use it without the user having to ask for it first. Use your judgement.
7. When only the general-purpose agent is provided, you should use it for all tasks. It is great for isolating context and token usage, and completing specific, complex tasks, as it has all the same capabilities as the main agent.

### Example usage …
(see full template including `<example>` blocks in `deepagents/middleware/subagents.py` → `TASK_TOOL_DESCRIPTION`)
```

**Canonical source**: `deepagents/middleware/subagents.py` — `TASK_TOOL_DESCRIPTION` (string template).

---

## Default middleware chain (`create_deep_agent`, main graph)

Order in `deepagents/graph.py`:

1. `TodoListMiddleware`  
2. `MemoryMiddleware` — if `memory` is not `None`  
3. `SkillsMiddleware` — if `skills` is not `None`  
4. `FilesystemMiddleware`  
5. **`SubAgentMiddleware(backend=..., subagents=all_subagents)`**  
6. `SummarizationMiddleware`  
7. `AnthropicPromptCachingMiddleware`  
8. `PatchToolCallsMiddleware`  
9. User `middleware=[...]`  
10. `HumanInTheLoopMiddleware` — if `interrupt_on` is not `None`

**Subagent stack** (e.g. `general-purpose`): `TodoListMiddleware`, `FilesystemMiddleware`, `SummarizationMiddleware`, optional `SkillsMiddleware`, optional `HumanInTheLoopMiddleware`, `AnthropicPromptCachingMiddleware`, `PatchToolCallsMiddleware` — see `graph.py` `gp_middleware`.

---

## Example `{skills_locations}` + `{skills_list}` (three repo skills)

Same layout as **`SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md`** — produced by `SkillsMiddleware` (`deepagents/middleware/skills.py`). Illustrative backend paths if this monorepo’s `skills/public/` is exposed as `/skills/public/...`:

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

**`task`**: orchestration narrative = `TASK_SYSTEM_PROMPT` (middleware); **full** spawn instructions = **`TASK_TOOL_DESCRIPTION`** on the tool object (`deepagents/middleware/subagents.py`), not the system string alone.

---

## Source pointers

| Piece | Module / symbol |
|-------|-------------------|
| `BASE_AGENT_PROMPT`, middleware order | `deepagents/graph.py` |
| `TASK_SYSTEM_PROMPT`, `TASK_TOOL_DESCRIPTION`, `GENERAL_PURPOSE_SUBAGENT` | `deepagents/middleware/subagents.py` |
| Todo / filesystem / memory / skills | same as disabled doc |

---

## Document matrix

| File | Language | Subagent / `task` |
|------|----------|-------------------|
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md` | EN | Absent |
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md` | EN | **Default** (this file) |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md` | CN | Absent |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md` | CN | **Default** |

---

*When upgrading `deepagents` or `langchain`, diff upstream and refresh all four Markdown snapshots.*
