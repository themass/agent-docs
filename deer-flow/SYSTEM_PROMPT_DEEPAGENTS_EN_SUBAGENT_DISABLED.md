# LangChain Deep Agents — System Prompt Assembly (English, **no `task` / subagents**)

**Configuration**: Subagent / `task` tool = **not present** (custom assembly; see note below)  
**Package snapshot**: `deepagents==0.5.1` (your install may differ; diff upstream when upgrading)  
**Agent entrypoint**: `create_deep_agent(...)` **without** `SubAgentMiddleware`, or plain `create_agent` with a subset of Deep Agents middleware.

---

## Runtime system message and tools

This file describes a **custom** stack **without** `SubAgentMiddleware`. For **byte-accurate** reference text, see **[`SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md`](./SYSTEM_PROMPT_RUNTIME_DEEPAGENTS.md)** — especially **§2.1** (system **without** the `task` subagent block) and **§3** (tool descriptions). The **default stock** **`create_deep_agent`** full system is in **§2**.

---

## Important note (vs default `create_deep_agent`)

The stock **`create_deep_agent`** in `deepagents/graph.py` **always** appends `SubAgentMiddleware`, which registers the **`task`** tool and injects **`TASK_SYSTEM_PROMPT`**. There is **no official boolean** to turn subagents off in that helper.

This document describes the **logical system prompt** you get if you build an agent that uses the **same middleware stack as the main graph minus subagent pieces**: planning (`write_todos`), optional memory/skills, filesystem (+ optional `execute`), summarization, caching, patch tool calls — **but no `task` block and no `task` tool**.

---

## Assembled system message (logical blocks, in typical wrap order)

Placeholders:

- `{user_system}` — your `system_prompt` argument to `create_agent`, if any.  
- `{agent_memory}` — loaded memory body or `(No memory loaded)`.  
- `{skills_locations}` / `{skills_list}` — from `SkillsMiddleware` when `skills=...` is configured.

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

<agent_memory>
{agent_memory}
</agent_memory>

<memory_guidelines>
    The above <agent_memory> was loaded in from files in your filesystem. As you learn from your interactions with the user, you can save new knowledge by calling the `edit_file` tool.

    **Learning from feedback:**
    - One of your MAIN PRIORITIES is to learn from your interactions with the user. These learnings can be implicit or explicit. This means that in the future, you will remember this important information.
    - When you need to remember something, updating memory must be your FIRST, IMMEDIATE action - before responding to the user, before calling other tools, before doing anything else. Just update memory immediately.
    - When user says something is better/worse, capture WHY and encode it as a pattern.
    - Each correction is a chance to improve permanently - don't just fix the immediate issue, update your instructions.
    - A great opportunity to update your memories is when the user interrupts a tool call and provides feedback. You should update your memories immediately before revising the tool call.
    - Look for the underlying principle behind corrections, not just the specific mistake.
    - The user might not explicitly ask you to remember something, but if they provide information that is useful for future use, you should update your memories immediately.

    **Asking for information:**
    - If you lack context to perform an action (e.g. send a Slack DM, requires a user ID/email) you should explicitly ask the user for this information.
    - It is preferred for you to ask for information, don't assume anything that you do not know!
    - When the user provides information that is useful for future use, you should update your memories immediately.

    **When to update memories:**
    - When the user explicitly asks you to remember something (e.g., "remember my email", "save this preference")
    - When the user describes your role or how you should behave (e.g., "you are a web researcher", "always do X")
    - When the user gives feedback on your work - capture what was wrong and how to improve
    - When the user provides information required for tool use (e.g., slack channel ID, email addresses)
    - When the user provides context useful for future tasks, such as how to use tools, or which actions to take in a particular situation
    - When you discover new patterns or preferences (coding styles, conventions, workflows)

    **When to NOT update memories:**
    - When the information is temporary or transient (e.g., "I'm running late", "I'm on my phone right now")
    - When the information is a one-time task request (e.g., "Find me a recipe", "What's 25 * 4?")
    - When the information is a simple question that doesn't reveal lasting preferences (e.g., "What day is it?", "Can you explain X?")
    - When the information is an acknowledgment or small talk (e.g., "Sounds good!", "Hello", "Thanks for that")
    - When the information is stale or irrelevant in future conversations
    - Never store API keys, access tokens, passwords, or any other credentials in any file, memory, or system prompt.
    - If the user asks where to put API keys or provides an API key, do NOT echo or save it.

    **Examples:** (see source `deepagents/middleware/memory.py` for full example block)
</memory_guidelines>

## Skills System

You have access to a skills library that provides specialized capabilities and domain knowledge.

{skills_locations}

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you see their name and description above, but only read full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches a skill's description
2. **Read the skill's full instructions**: Use the path shown in the skill list above
3. **Follow the skill's instructions**: SKILL.md contains step-by-step workflows, best practices, and examples
4. **Access supporting files**: Skills may include helper scripts, configs, or reference docs - use absolute paths

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "research X" -> web-research skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

**Executing Skill Scripts:**
Skills may contain Python scripts or other executable files. Always use absolute paths from the skill list.

Remember: Skills make you more capable and consistent. When in doubt, check if a skill exists for the task!

## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`

You have access to a filesystem which you can interact with using these tools.
All file paths must start with a /.

- ls: list files in a directory (requires absolute path)
- read_file: read a file from the filesystem
- write_file: write to a file in the filesystem
- edit_file: edit a file in the filesystem
- glob: find files matching a pattern (e.g., "**/*.py")
- grep: search for text within files

## Execute Tool `execute`

You have access to an `execute` tool for running shell commands in a sandboxed environment.
Use this tool to run commands, scripts, tests, builds, and other shell operations.

- execute: run a shell command in the sandbox (returns output and exit code)

(The `execute` tool and extended execution guidance are only injected when the backend implements sandbox execution — see `FilesystemMiddleware` in `deepagents/middleware/filesystem.py`.)
```

## Completeness: system message vs full model input

The fenced block is a **snapshot of the system role string** (middleware-assembled narrative). It is **not** everything the runtime sends to the model API:

| Channel | What the model gets |
|--------|----------------------|
| **System message** | `user_system` + `BASE_AGENT_PROMPT` sections — `write_todos` *prose*, memory/skills/filesystem narrative, etc. |
| **Tool definitions** | A **separate** list: each tool’s **`description`** and **JSON parameter schema** (`write_todos`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, optional `execute`, …). Text here is **not** fully duplicated in the system string; **`WRITE_TODOS_TOOL_DESCRIPTION`** (LangChain) can differ in wording from the `## write_todos` section while both apply. |
| **Other** | Conversation history; `SummarizationMiddleware` may rewrite past turns; optional HITL / caching behavior. |

**Not included in this variant (by design)**

- **`## task` (subagent spawner)** — `TASK_SYSTEM_PROMPT` from `deepagents/middleware/subagents.py`  
- **`task` tool** — no `SubAgentMiddleware`

**Dynamic / conditional**

- **`SummarizationMiddleware`** — may rewrite history when context limits are hit (not a static prefix).  
- **`AnthropicPromptCachingMiddleware`**, **`PatchToolCallsMiddleware`** — behavior middleware; minimal or no extra system text.  
- **`HumanInTheLoopMiddleware`** — if `interrupt_on` is set.

For byte-accurate strings, read the pinned **`deepagents` / `langchain`** versions or log the outbound request body.

---

## Middleware chain reference (main agent, minus subagents)

Approximate stack when mirroring `create_deep_agent` **without** `SubAgentMiddleware`:

1. `TodoListMiddleware`  
2. `MemoryMiddleware` — if `memory=[...]`  
3. `SkillsMiddleware` — if `skills=[...]`  
4. `FilesystemMiddleware`  
5. `SummarizationMiddleware`  
6. `AnthropicPromptCachingMiddleware`  
7. `PatchToolCallsMiddleware`  
8. Optional `HumanInTheLoopMiddleware` — if `interrupt_on`  
9. Any extra `middleware=[...]` you pass

Base string passed to `create_agent`: `user_system + "\n\n" + BASE_AGENT_PROMPT` with `BASE_AGENT_PROMPT` from `deepagents/graph.py`.

---

## Example `{skills_locations}` + `{skills_list}` (three real skill descriptions)

`SkillsMiddleware._format_skills_locations()` and `_format_skills_list()` build the two placeholders in `SKILLS_SYSTEM_PROMPT` (`deepagents/middleware/skills.py`). Paths are **backend virtual paths** — they must match how you mount this repo’s `skills/public/` (e.g. `FilesystemBackend` root + `sources`).

**Illustrative `{skills_locations}`** (one source pointing at public skills):

```markdown
**Public Skills**: `/skills/public/`
```

**Illustrative `{skills_list}`** — same three skills as in the DeerFlow docs (`skills/public/bootstrap`, `deep-research`, `frontend-design`), formatted as the middleware does (name + description + optional license line + `Read \`path\` for full instructions`):

```markdown
- **bootstrap**: Generate a personalized SOUL.md through a warm, adaptive onboarding conversation. Trigger when the user wants to create, set up, or initialize their AI partner's identity — e.g., "create my SOUL.md", "bootstrap my agent", "set up my AI partner", "define who you are", "let's do onboarding", "personalize this AI", "make you mine", or when a SOUL.md is missing. Also trigger for updates: "update my SOUL.md", "change my AI's personality", "tweak the soul".
  -> Read `/skills/public/bootstrap/SKILL.md` for full instructions
- **deep-research**: Use this skill instead of WebSearch for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches. Use this proactively when the user's question needs online information.
  -> Read `/skills/public/deep-research/SKILL.md` for full instructions
- **frontend-design**: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics. (License: Complete terms in LICENSE.txt)
  -> Read `/skills/public/frontend-design/SKILL.md` for full instructions
```

**`write_todos`**: long instruction text lives in **`langchain.agents.middleware.todo`** (`WRITE_TODOS_SYSTEM_PROMPT` / tool description), appended by `TodoListMiddleware` — not repeated here.

---

## Source pointers

| Piece | Module / symbol |
|-------|-------------------|
| `BASE_AGENT_PROMPT` | `deepagents/graph.py` |
| `WRITE_TODOS_*` | `langchain.agents.middleware.todo` |
| `MEMORY_SYSTEM_PROMPT` | `deepagents/middleware/memory.py` |
| `SKILLS_SYSTEM_PROMPT` | `deepagents/middleware/skills.py` |
| `FILESYSTEM_SYSTEM_PROMPT`, `EXECUTION_SYSTEM_PROMPT` | `deepagents/middleware/filesystem.py` |
| Default **with** subagents | `deepagents/graph.py` → `SubAgentMiddleware` |

---

## Document matrix

| File | Language | Subagent / `task` |
|------|----------|-------------------|
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_DISABLED.md` | EN | Absent (this file) |
| `SYSTEM_PROMPT_DEEPAGENTS_EN_SUBAGENT_ENABLED.md` | EN | Default `create_deep_agent` |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_DISABLED.md` | CN | Absent |
| `SYSTEM_PROMPT_DEEPAGENTS_CN_SUBAGENT_ENABLED.md` | CN | Default `create_deep_agent` |

---

*When upgrading `deepagents` or `langchain`, diff the upstream files above and refresh all four Markdown snapshots.*
