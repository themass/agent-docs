# Claude Code 的 Agent 设计模式

> 基于 2026-03-31 泄露的源码快照（`claude-code-main/src/`，约 512k 行 TypeScript / Bun 运行时 / React + Ink 终端 UI）整理。
> 所有代码引用为相对本仓库根目录的路径，可点击跳转。

**一句话概括**：Claude Code 的内核是一个「可流式、可中断、可递归自我复制」的 async generator 循环；围绕它建立了「统一工具抽象 + 分层权限」「声明式 agent 人格」「上下文经济学」三层设计。所有 agent——主会话、子 agent、队友、云端 agent——本质上都是同一个循环的不同包装。

---

## 目录

- [模式一：Generator-based 的 Agentic Loop（内核）](#模式一generator-based-的-agentic-loop内核)
- [模式二：统一的 Tool 抽象 + 分层权限](#模式二统一的-tool-抽象--分层权限)
- [模式三：子 Agent —— "递归地自我复制循环"](#模式三子-agent--递归地自我复制循环)
- [模式四：两种 Multi-Agent 拓扑](#模式四两种-multi-agent-拓扑)
- [模式五：声明式的 Agent 人格定义](#模式五声明式的-agent-人格定义)
- [模式六：上下文经济学（让对话"无限长"）](#模式六上下文经济学让对话无限长)
- [横切关注点](#横切关注点)
- [数据流总览](#数据流总览)
- [可借鉴的核心设计原则](#可借鉴的核心设计原则)
- [关键文件索引](#关键文件索引)

---

## 模式一：Generator-based 的 Agentic Loop（内核）

整个系统的心脏是 [claude-code-main/src/query.ts](claude-code-main/src/query.ts) 里导出的一个 **async generator `query()`**——不是类，而是一个生成器函数。`QueryEngine.ts` 只是它众多消费者之一（REPL 交互、SDK headless、子 agent、hook 各是一个消费者）。

```
query()  →  queryLoop()  →  while (true) { ... }   ← claude-code-main/src/query.ts:307
   yield: StreamEvent | Message | ...        (产出消息流给 UI/SDK)
   return: Terminal                          (终止原因)
```

**一次 "turn"（循环的一次迭代）的流水线**：

1. **准备上下文**——跳过压缩边界、snip、microcompact、context-collapse、autocompact（[query.ts:365-549](claude-code-main/src/query.ts#L365)）
2. **流式调模型**——`for await (const msg of deps.callModel(...))`（[query.ts:659](claude-code-main/src/query.ts#L659)），边到达边 `yield`
3. **判断是否继续**——唯一判据是「本轮模型有没有发出 `tool_use`」（`needsFollowUp`，[query.ts:826-845](claude-code-main/src/query.ts#L826)）
4. **无工具** → 跑 stop hooks / token budget → `return {reason:'completed'}`
5. **有工具** → 执行工具 → 把 `tool_result` 拼回消息历史 → `continue` 回到顶部

第 5 步的关键就一行：

```ts
messages: [...messagesForQuery, ...assistantMessages, ...toolResults]   // query.ts:1716
```

"把工具结果追加到历史，然后重新调模型"——这就是 agentic loop 的全部本质。

### 三个值得学习的设计决策

**① 不信任 `stop_reason`，只信 `tool_use` 的存在。** 代码注释明说 `stop_reason === 'tool_use'` 不可靠（[query.ts:553-556](claude-code-main/src/query.ts#L553)），所以退出条件是「收集到的 tool_use 数组是否为空」，而非 API 给的停止原因。这是对模型输出做防御性解析的典范。

**② 显式状态机，而非递归。** 历史上这里是递归调用，现已重构成 `while(true)` + 一个 `State` struct（[query.ts:204-217](claude-code-main/src/query.ts#L204)）。配置三层分离——不可变的 `QueryConfig`、可变的迭代 `State`、可变的 IO `ToolUseContext`——注释直言终点是把循环体抽成纯函数 `step(state, event, config)`。这是「为可测试性和未来 reducer 化铺路」的工程取舍。

**③ 防御性恢复优先于报错。** 循环里塞满了恢复逻辑：prompt 过长 → 反应式压缩重试；输出截断 → 升级 max_tokens 重试；可恢复错误 → 先"withhold 扣住不 yield"避免 SDK 消费者误杀会话（[query.ts:166-179](claude-code-main/src/query.ts#L166)）。每条恢复路径都配防死循环护栏（`hasAttemptedReactiveCompact`、`stopHookActive`），注释里记录着「曾经烧掉数千次 API 调用」的真实事故。

---

## 模式二：统一的 Tool 抽象 + 分层权限

所有工具是**同构的对象字面量**，经工厂函数 `buildTool()` 用 **fail-closed 默认值** 补全成完整接口（[Tool.ts:757-792](claude-code-main/src/Tool.ts#L757)）。接口定义见 [Tool.ts:362-695](claude-code-main/src/Tool.ts#L362)。

**核心契约方法**：

| 方法 | 作用 | 默认值（保守） |
|---|---|---|
| `inputSchema` | zod v4 输入校验 | 必填 |
| `call(args, ctx, canUseTool, ..., onProgress)` | 执行（**plain async + 回调**） | 必填 |
| `prompt()` | 注入给模型的工具说明 | 必填 |
| `isReadOnly()` | 是否只读 | `false`（假设会写）|
| `isConcurrencySafe()` | 是否可并发 | `false`（假设不安全）|
| `checkPermissions()` | 工具特有权限判断 | `allow`（交给通用层）|
| `mapToolResultToToolResultBlockParam()` | 结构化输出 → 给模型的 tool_result | 必填 |
| `render*()` 一组 | 结构化输出 → 给终端 UI 的 React 节点 | 可选 |

### 四个关键设计

**① 执行模型：「generator 在内、回调在边界」。** `call` 是普通 async 函数 + `onProgress` 回调，而非 async generator。引擎用一个 `Stream` 把进度事件和最终结果合流成单一异步可迭代（[services/tools/toolExecution.ts:492](claude-code-main/src/services/tools/toolExecution.ts#L492)，注释自嘲这是个 "hack"）。但工具**内部**可自由用 generator——BashTool 内部就是一个 yield 增量输出的 generator，在边界处转成 `onProgress` 回调。

**② 并发分批：只读并行，写串行。** `partitionToolCalls`（[toolOrchestration.ts:91](claude-code-main/src/services/tools/toolOrchestration.ts#L91)）把模型一次发出的多个 tool_use **按"连续的并发安全工具"分组**：连续只读工具并发执行（上限 10），遇到任何写工具就单独串行。还有一条更激进的 `StreamingToolExecutor` 路径——工具从模型流里一到达就开始执行。这正是 Claude Code "同时读 5 个文件"的原因。

**③ 权限分层 + fail-closed。** 中央裁决函数 `hasPermissionsToUseToolInner` 的决策顺序固定为 **deny → ask → allow**（[utils/permissions/permissions.ts](claude-code-main/src/utils/permissions/permissions.ts)）：先查全局 deny 规则，再查 ask 规则，再调工具自身 `checkPermissions`，最后才考虑 allow 规则和 bypass 模式。只读工具走 `checkReadPermissionForTool`、写工具走 `checkWritePermissionForTool`（后者对 `.git/`、`.claude/`、shell 配置等敏感路径强制 ask）。PermissionMode 有 `default / acceptEdits / bypassPermissions / dontAsk / plan` 等。

**④ ToolSearch 延迟加载——解决 context 膨胀。** 工具太多（尤其 MCP 工具）时，把所有 schema 都塞进 system prompt 会吃光 token。方案：初始只在 `<system-reminder>` 里列**工具名**，模型需要时用 `ToolSearchTool` 把 schema 取回（[tools/ToolSearchTool/](claude-code-main/src/tools/ToolSearchTool/)）。返回的是 `tool_reference` 块，由 API 侧展开 schema 而非塞回文本。

---

## 模式三：子 Agent —— "递归地自我复制循环"

这是最优雅的部分：**子 agent 不是另写一套引擎，而是用同一个 `query()` 循环 + 独立的 `ToolUseContext`**。父 agent 通过 `AgentTool` 派生子 agent（[tools/AgentTool/AgentTool.tsx](claude-code-main/src/tools/AgentTool/AgentTool.tsx)），子 agent 跑 `runAgent()` → `query()`，把消息逐条 yield 回父，最终取**最后一条 assistant 文本**作为返回结果包装成父看到的 `tool_result`。

### 设计要点

**① 子 agent 不受父的工具限制——独立装配工具池。** 注释明说 "workers aren't affected by the parent's tool restrictions"（[AgentTool.tsx:568-572](claude-code-main/src/tools/AgentTool/AgentTool.tsx#L568)）。子 agent 的工具集 = 全量工具 − 全局禁用集 − agent 定义的黑名单。

**② 嵌套靠"移除工具"而非"深度计数器"。** 默认子 agent 的工具池里**没有 `Agent` 工具**（`ALL_AGENT_DISALLOWED_TOOLS`，[constants/tools.ts](claude-code-main/src/constants/tools.ts)），所以无法再派生——除非 `USER_TYPE==='ant'`（内部用户）。这是一个用「能力可用性」而非「显式限制」来控制递归的巧思。

**③ 模型继承链。** `getAgentModel()` 优先级：环境变量 > 工具传入 > agent 定义 > **默认 `'inherit'`（继承父模型）**。

**④ Fork 是为 prompt cache 而生的特殊派生。** `forkSubagent` 继承父的**字节级一致**的 system prompt + 工具 + 上下文，只让末尾的 directive 不同，从而让并行子任务命中 prompt cache，把 API 开销压到最低。

**⑤ 隔离是可选的逃生舱。** `isolation:'worktree'` 给子 agent 一个独立 git worktree（`.claude/worktrees/<slug>`），完成后**无改动则自动删除、有改动则保留**；`isolation:'remote'` 整个跑到云端。

---

## 模式四：两种 Multi-Agent 拓扑

源码里其实有**两套并存**的多 agent 模式，区别在于通信拓扑：

### A. 分层（Hierarchical）——默认、安全、可预测

`AgentTool` 派生的子 agent 是**一次性委派**：spawn → 跑完 → 返回结果 → 终止。`coordinator` 模式（[coordinator/coordinatorMode.ts](claude-code-main/src/coordinator/coordinatorMode.ts)）是它的特例——把主 agent 重写成只负责"派发 worker + 综合结果"的协调者。这本质是一棵树：parent → workers，结果以 `tool_result` 或 `<task-notification>` 回流。

### B. 网状（Peer-to-Peer）——Teams / Swarm，真正的多 agent

`in_process_teammate` 是**长生命周期、可反复对话**的"队友"：

- 有 `name@team` 身份、独立 AbortController（故意不挂 leader，ESC 杀不掉）、靠 `AsyncLocalStorage` 在同进程内隔离
- 跑完一轮变 **idle 等下一条消息**，而非终止
- **基于文件的 mailbox**：`~/.claude/teams/{team}/inboxes/{name}.json`，用 `proper-lockfile` 加锁，轮询投递
- `SendMessageTool` 支持 leader↔队友、**队友↔队友、广播 `*`**
- 一个 **Team 1:1 对应一个共享 TODO 任务清单**，队友自主"认领"任务（`tryClaimNextTask`）

> ⚠️ **注意源码里有两套都叫 "Task" 的东西**：
> - **运行时任务**（`TaskType`：`local_bash / local_agent / remote_agent / in_process_teammate / dream` 等，是真在跑的进程级东西，见 [Task.ts:6-13](claude-code-main/src/Task.ts#L6)）
> - **TODO 待办清单**（`TaskCreateTool` 系列，给模型做 plan 跟踪，不执行任何东西）。Teams 用后者当协作底座。

### 统一任务抽象

所有"正在跑的异步东西"——后台 shell、子 agent、云 session、队友、甚至记忆整合的 `dream` 任务——共用同一个 `TaskStateBase`（[Task.ts:44-57](claude-code-main/src/Task.ts#L44)）+ 多态 `kill()` 接口，注册进同一个 `AppState.tasks`，共用一套轮询（`pollTasks` 每秒一次）、磁盘输出、UI（footer pill）和**通知回灌机制**：后台任务完成时生成一段 `<task-notification>` XML 作为 user 消息进入队列，下一轮主循环就喂给模型——所以模型被明确告知"不要轮询，完成会自动通知你"。

---

## 模式五：声明式的 Agent 人格定义

不同 agent type 的"人格"是**元数据驱动**的，分四层来源、可覆盖：

**内置 agent**（[tools/AgentTool/builtInAgents.ts](claude-code-main/src/tools/AgentTool/builtInAgents.ts)）：

| Agent | 工具 | 模型 | 人格设计 |
|---|---|---|---|
| `general-purpose` | 全部 | 继承 | 通用多步研究 |
| `Explore` | 只读（禁 Edit/Write/Agent）| `haiku` | `omitClaudeMd` 省 token，专攻检索 |
| `Plan` | 只读 | 继承 | 架构设计 |
| `verification` | 只读 | 继承 | `background:true`，"对抗式破坏验证" |
| `claude-code-guide` | Bash/Read/Web* | `haiku` | `dontAsk` 模式答 CC 问题 |

**关键**：每个 agent 的 `getSystemPrompt()` 是**函数**（spawn 时计算），不是静态串。Explore 用 haiku + 只读 + 省略 CLAUDE.md 来"廉价快速检索"，verification 用独立的"破坏式"人格——这是把不同认知任务匹配到不同成本/能力配置的体现。

**用户自定义 subagent**：放 `~/.claude/agents/` 或 `.claude/agents/` 的 **Markdown + YAML frontmatter** 文件（`name→agentType`、`description→whenToUse`、`tools/model/...`，正文即 system prompt）。优先级 managed > flag > project > user > plugin > built-in——同名可覆盖内置。

这些定义最终被 `formatAgentLine()` 渲染成 `- <type>: <whenToUse> (Tools: ...)` 注入 prompt——正是会话开头 system-reminder 里那份 agent 清单的来源。

---

## 模式六：上下文经济学（让对话"无限长"）

这是 Claude Code 最体现工程深度的部分——四层机制协同对抗有限的上下文窗口：

**① 渐进式披露（Progressive Disclosure）。** Skills 默认只展示 name + 截断描述，预算严格限制在**上下文窗口的 1%**（`SKILL_BUDGET_CONTEXT_PERCENT = 0.01`）；模型调用 `SkillTool` 时才加载完整正文。ToolSearch 对工具 schema 也是同理。把昂贵的上下文留给真正的推理。

**② 阈值触发的多级压缩。** 当 token 用量 ≥（有效窗口 − 13000）时触发 autocompact（[services/compact/autoCompact.ts:62](claude-code-main/src/services/compact/autoCompact.ts#L62)）。压缩前还有 snip / microcompact / context-collapse 等更轻量的层级。压缩 prompt 要求模型生成 9 段结构化总结（含"所有用户消息""当前工作""下一步"），且**禁止调用工具**。压缩后保留：总结 + 近期原始消息逐字 + 最近读的 ≤5 个文件 + 计划 + 已调用 skills。

**③ 双层持久记忆。** `SessionMemory`（会话内，后台 forked agent 周期性写 Markdown，压缩时直接复用当总结源）+ `memdir`（跨会话，`~/.claude/projects/<slug>/memory/`，分 user/feedback/project/reference 四类，通过 `MEMORY.md` 索引注入）。两者压缩后都被重新注入——这就是"对话不受上下文窗口限制"承诺的兑现方式。

**④ 缓存分段的 system prompt。** system prompt 是动态拼装的 `string[]`（[constants/prompts.ts:444](claude-code-main/src/constants/prompts.ts#L444)），用 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 标记把**稳定的"人格"段**（身份/代码规范/语气）放缓存边界前复用 prompt cache，**会话易变信息**（环境/MCP/memory）放后面，最小化缓存击穿成本。

---

## 横切关注点

- **可中断性是一等公民**：`AbortController` 贯穿全程，形成层级化中断树（parent → sibling → per-tool）。一个 Bash 失败能"连坐"杀兄弟子进程（因 shell 常有隐式依赖），但 Read/WebFetch 互相独立。
- **可测试性（轻量 DI）**：`query/deps.ts` 把 `callModel`/压缩等 IO 注入，测试可替换 fake；`query/config.ts` 快照运行时门控。但编译期 `feature()` 门控刻意保持内联，以支持 bundler tree-shaking——这是"可测试性 vs 打包体积"的务实折中。
- **Hooks**：27 种生命周期事件（PreToolUse/PostToolUse/Stop/SubagentStop/PreCompact...），`PreToolUse` 可返回 `allow/deny/ask` 甚至**改写工具入参**；退出码 2 可阻断并把信息反馈给模型。

---

## 数据流总览

```
用户输入
   │
   ▼
┌──────────────────────────────────────────────────────────┐
│  query() — async generator 主循环  (while true)           │
│                                                            │
│  ① 上下文准备 (snip→microcompact→collapse→autocompact)    │
│  ② 流式调模型 deps.callModel()  ──yield──▶ UI/SDK         │
│  ③ 有 tool_use?                                            │
│        否 → stop hooks → token budget → return completed   │
│        是 ↓                                                │
│  ④ 工具编排: 只读并行 / 写串行                             │
│        ├─ Bash/Read/Edit/...     (本地工具)               │
│        ├─ AgentTool ───────────▶ runAgent() ─┐            │
│        │                          (递归同一个 query())     │
│        └─ SendMessage ─────────▶ 队友 mailbox │            │
│  ⑤ tool_result 拼回 messages → continue ◀────┘            │
└──────────────────────────────────────────────────────────┘
        ▲                                    │
        │  <task-notification> 回灌          │ 后台任务完成
        └────────────────────────────────────┘
```

---

## 可借鉴的核心设计原则

1. **同构递归**——主 agent 和子 agent 是同一个循环，"派生 agent" = "递归调用自己 + 换一套 context"。这是整个架构能保持简洁的根源。
2. **fail-closed 默认值**——工具默认"会写、不可并发、需审批"；权限默认 deny 优先。安全性来自保守默认，而非记得加限制。
3. **能力即控制**——用"给不给某个工具"来约束 agent（禁递归 = 拿掉 Agent 工具，只读 = 拿掉 Edit/Write），而非散落的 if 判断。
4. **结构化输出 + 双序列化**——工具产出一份结构化 `Output`，分别序列化给「模型」和「UI」两条独立路径。
5. **上下文是稀缺资源**——渐进式披露、延迟加载、分层压缩、双层记忆、缓存分段，全都在围绕"省 token"做文章。
6. **防御性恢复 + 防死循环护栏**——能恢复就别让 turn 失败，但每条恢复路径都有显式的熔断计数器。

---

## 关键文件索引

| 子系统 | 关键文件 |
|---|---|
| **核心循环** | [query.ts](claude-code-main/src/query.ts)、[QueryEngine.ts](claude-code-main/src/QueryEngine.ts)、[query/deps.ts](claude-code-main/src/query/deps.ts)、[query/config.ts](claude-code-main/src/query/config.ts)、[query/tokenBudget.ts](claude-code-main/src/query/tokenBudget.ts)、[query/stopHooks.ts](claude-code-main/src/query/stopHooks.ts) |
| **工具系统** | [Tool.ts](claude-code-main/src/Tool.ts)、[tools.ts](claude-code-main/src/tools.ts)、[services/tools/toolExecution.ts](claude-code-main/src/services/tools/toolExecution.ts)、[services/tools/toolOrchestration.ts](claude-code-main/src/services/tools/toolOrchestration.ts)、[services/tools/StreamingToolExecutor.ts](claude-code-main/src/services/tools/StreamingToolExecutor.ts) |
| **权限** | [utils/permissions/permissions.ts](claude-code-main/src/utils/permissions/permissions.ts)、[utils/permissions/filesystem.ts](claude-code-main/src/utils/permissions/filesystem.ts)、[hooks/useCanUseTool.tsx](claude-code-main/src/hooks/useCanUseTool.tsx) |
| **子 agent / 任务** | [Task.ts](claude-code-main/src/Task.ts)、[tasks.ts](claude-code-main/src/tasks.ts)、[tools/AgentTool/](claude-code-main/src/tools/AgentTool/)、[utils/task/framework.ts](claude-code-main/src/utils/task/framework.ts)、[constants/tools.ts](claude-code-main/src/constants/tools.ts) |
| **agent 定义** | [tools/AgentTool/loadAgentsDir.ts](claude-code-main/src/tools/AgentTool/loadAgentsDir.ts)、[tools/AgentTool/builtInAgents.ts](claude-code-main/src/tools/AgentTool/builtInAgents.ts)、[tools/AgentTool/agentToolUtils.ts](claude-code-main/src/tools/AgentTool/agentToolUtils.ts) |
| **协作 / Teams** | [coordinator/coordinatorMode.ts](claude-code-main/src/coordinator/coordinatorMode.ts)、[tools/TeamCreateTool/](claude-code-main/src/tools/TeamCreateTool/)、[tools/SendMessageTool/](claude-code-main/src/tools/SendMessageTool/)、[tasks/InProcessTeammateTask/](claude-code-main/src/tasks/InProcessTeammateTask/) |
| **prompt / 人格** | [constants/prompts.ts](claude-code-main/src/constants/prompts.ts)、[constants/systemPromptSections.ts](claude-code-main/src/constants/systemPromptSections.ts)、[utils/systemPrompt.ts](claude-code-main/src/utils/systemPrompt.ts)、[constants/outputStyles.ts](claude-code-main/src/constants/outputStyles.ts) |
| **上下文 / 记忆** | [services/compact/](claude-code-main/src/services/compact/)、[services/SessionMemory/](claude-code-main/src/services/SessionMemory/)、[services/extractMemories/](claude-code-main/src/services/extractMemories/)、[memdir/memdir.ts](claude-code-main/src/memdir/memdir.ts) |
| **Skills** | [skills/](claude-code-main/src/skills/)、[tools/SkillTool/](claude-code-main/src/tools/SkillTool/) |
| **Hooks** | [utils/hooks.ts](claude-code-main/src/utils/hooks.ts)、[entrypoints/sdk/coreTypes.ts](claude-code-main/src/entrypoints/sdk/coreTypes.ts) |
