# 第六章 · 能力扩展（Skills / 工具 / 模型 / Goal / 子 Agent / 压缩 / 审批）

> **阅读顺序第 7 步**｜先读 [00-顶层设计与实体边界.md](./00-顶层设计与实体边界.md) 与 [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md)  
> 本章把「主干之外如何扩展能力」写成可落地的长文：**文件型 Skill**、Environment 工具目录、`(provider, model_id)` + AgentHub、Goal 外环、Subagent 深度帽、Compaction、ApproveFn/权限与决策树。  
> 写作标准：[DOC_QUALITY.md](./DOC_QUALITY.md)。权威行为仍以 `packages/core` 与官方 `packages/docs/content/` 为准。

### 本章要回答的问题

1. 为什么没有插件运行时，领域能力却还能扩展？Skill 进 Prompt 的哪一层、不进哪一层？
2. 九个内置工具各自**拥有**什么副作用？MCP 何时连、谁收尾？
3. 模型身份为什么必须是二元组？Session 锁模型、Agent 不锁模型意味着什么？
4. Goal 外环与 ContextEngine 内环怎么叠？谁写 `GOAL.yaml`、谁只读 `status`？
5. Subagent 继承什么、不继承什么？深度帽改哪里？
6. Compaction 成功时谁换 LLM、谁切 Trace？失败时为什么不能丢历史？
7. 审批在引擎里 await，但决策由谁做？权限 `r`/`rw` 和 `--approve` 四种模式如何咬合？

带着这七个问题往下读；每节都有**实体边界表**与**写入归属**，禁止只剩流程图。

---

## §0 设计目标与非目标

### 0.1 要解决什么

| 目标 | 落在哪个实体 / 机制 |
|------|---------------------|
| 领域知识可交付、可编辑、可自进化 | `agent_state/skills/<name>/SKILL.md`（文件即事实源） |
| 副作用可审计、可截断、永不裸抛 | `Environment.executeTool` 统一收尾 |
| 多厂商模型不渗入引擎 | `LLMInterface` 薄端口 + `@prismshadow/agenthub` |
| 长目标不必改 ReAct 内核 | Session 外环 `runGoalLoop` + 内环仍是 `ContextEngine` |
| 可派生子任务且不炸栈 | `run_subagent` + `MAX_SUBAGENT_DEPTH` |
| 长上下文可续跑 | Compaction（summarize/discard）+ Trace rotate + `createLLM` |
| Human 可控工具副作用 | `ApproveFn` + 工具 `permission` |

### 0.2 故意不做什么

| 不做 | 原因 / 谁承担类似职责 |
|------|------------------------|
| Cordis / Profile / Bundle 插件树 | 扩展用 Skill 文件 + MCP + 配置；**不是**热插 Driver |
| 专用「Skill 工具」 | 模型用 `read_file` / Shell 读 `SKILL.md` |
| core 直连厂商 SDK | 协议翻译在 AgentHub / `GenerativeModel` |
| Environment 做产品审批 | 只有引擎 `approve === allow` 后才 `executeTool` |
| Goal 另造第二套 transcript | 每轮仍是普通 Task；Trace 仍是真源 |
| 无限嵌套 Subagent | 默认深度帽 **1**（常量可调，但产品默认如此） |
| 压缩失败自动 discard | 失败保留原上下文与原 Trace 分片 |

### 0.3 与 PART1 / 00 的边界对齐

PART1 讲清了三接口、Session、ContextEngine、Trace。本章只补「能力扩展面」：文件怎么进 Prompt、工具表怎么装配、模型表怎么查、外环怎么叠、压缩怎么切文件。若与 [00](./00-顶层设计与实体边界.md) 的实体表冲突，**以 00 + 源码为准**，先改 00 再改本篇。

---

## §1 Skills：没有插件运行时的扩展路径

### 1.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **Skill / `SKILL.md`** | 目录 + Markdown 说明书；元数据进系统 Prompt，正文按需读 | 「提示词包 / runbook」 | Cordis 插件、npm 服务、可 `register()` 的运行时 |
| **`{{SKILL_METADATA}}`** | 系统 Prompt 里注入「已安装 Skill 索引行」的占位符 | 目录索引 / 卡片列表 | 把全文手册钉死在上下文 |
| **`[use_skills]`** | 用户消息前缀块，显式点名要用的 Skill | 显式 @技能 | 自动执行引擎；点名不等于立刻跑完 |
| **`preinstall: false`** | frontmatter：不进 `default_agent` 预装集合 | 「可选扩展包」 | 禁止安装；仍可手动装 |
| **渐进式加载** | 先索引后正文 | RAG 的「先检索再读全文」直觉 | 插件懒加载 / require 缓存 |

### 1.2 实体边界表

| 实体 | **拥有** | **不拥有** | 依赖谁 | 禁止渗入 |
|------|----------|------------|--------|----------|
| **Skill 目录** | `SKILL.md` 正文、可选 `icon.svg`、`reference/` 等附属文件；目录名即权威 id | 进程内服务注册表；工具执行权 | 安装进 `agent_state/skills/` | ContextEngine 私有状态 |
| **`listInstalledSkills` / 组装 Prompt** | 扫描盘上 Skill、注入元数据行 | 缓存 Skill 正文；替模型执行说明书 | `assembleSystemPrompt` / `skillMetadataSection` | 把 Skill 当插件 hook |
| **模型** | 决定何时 `read_file` 读正文并遵循 | 「Skill 运行时」对象 | 工具面（`read_file` / Shell） | 假设存在 `invoke_skill` 内置工具 |
| **`@prismshadow/penguin-skills`** | 内置库 tarball 源文件 | 已安装态（那是 agent_state） | 初始化/安装时拷贝 | Web 直接当执行引擎 |

### 1.3 形态与 frontmatter

一个 Skill = 一个目录：必有 `SKILL.md`，可选 `icon.svg` 与 `reference/` 等。目录名须匹配 `^[A-Za-z0-9_-]+$`。frontmatter 的 `name` **以目录名为准**——手写或网上下载的 Skill 若 frontmatter `name` 与目录不一致，**目录名永远赢**，否则模型会按注入名去读不存在的路径，API 也无法按注入名卸载。

| 字段 | 进 Prompt？ | 用途 |
|------|-------------|------|
| `name` | 元数据行里的反引号名 | 身份；实际以目录名为准 |
| `description` | **是**（英文单行） | 索引层：帮模型判断何时读正文 |
| `short_description(_zh)` | 否 | UI 卡片短标签 |
| `preinstall` | 否 | 仅 `false` 字面量排除预装 |
| `version` / `updated` | 否（元数据可带） | 库版本与展示 |

官方文档示例形态（概念对齐 `packages/docs/content/skills.zh.md`）：

```md
---
name: my-skill
description: One-line English description injected into the system prompt.
short_description: Short UI label.
short_description_zh: 简短的中文标签。
version: 1
updated: 2026-07-17
---

# My Skill

具体的步骤、边界与验收标准……
```

### 1.4 发现、安装、卸载（写入归属）

| 步骤 | 谁执行 | 改谁的内存 | 落哪份磁盘 |
|------|--------|------------|------------|
| 初始化 `default_agent` | `loadOrInitAgentState` | 无「Skill 缓存对象」 | 拷贝库中预装 Skill → `agent_state/skills/<name>/` |
| 安装 | `installSkill` | 无 | **整目录替换**：先 `rm` 再写 `SKILL.md` + icon + files |
| 列已装 | `listInstalledSkills` | 返回数组（当次） | 只读扫描；无 SKILL.md 的目录不计为 Skill |
| 组装系统 Prompt | Agent 开 Session / bootstrap 路径 | 系统 Prompt 字符串 | 不写盘；每次从盘读元数据拼进去 |
| 卸载 | `removeSkill` | 无 | 删整目录；幂等 |

源码把「没有专用 Skill 工具」写进初始化注释：

```190:196:packages/core/src/state/agent-state.ts
    // Only installs the Skills specified by preset (a plain newly created Agent gets none
    // pre-installed). A default_agent with no preset (e.g. created on first CLI run) still gets
    // the library's preinstalled set (Skills marked `preinstall: false` stay manual-install) —
    // the install policy follows Agent identity, not whether creation came from the server or
    // was done directly via SDK/CLI.
    // Skills have no dedicated tool: metadata is injected via {{SKILL_METADATA}}, and the model
    // reads SKILL.md with shell and follows it.
```

安装是整目录替换——重装会丢掉新版本不再携带的附属文件：

```450:456:packages/core/src/state/agent-state.ts
 * Installs a Skill into the target Agent: writes `skills/<name>/SKILL.md` verbatim (the full
 * SKILL.md content including frontmatter, ensuring a trailing newline). An optional icon.svg and
 * any auxiliary `files` the SKILL.md references (e.g. `reference/API.md`, subdirectories
 * preserved) are written alongside it. The directory is replaced wholesale first, so reinstalling
 * updates to the latest content and drops files the new version no longer ships — the directory
 * content always matches the Skill being installed. Each file path is checked to stay within the
 * skill directory before anything is written.
```

元数据注入格式（`{{SKILL_METADATA}}` 的替换值）：

```569:577:packages/core/src/state/agent-state.ts
/**
 * Skill metadata section: the replacement value for `{{SKILL_METADATA}}`, one line per Skill in
 * the form `- \`name\` — description` (just the name when description is empty); an empty array
 * returns an empty string. The full body is read by the model on demand via shell.
 */
export function skillMetadataSection(skills: SkillMetadata[]): string {
  return skills
    .map((s) => (s.description ? `- \`${s.name}\` — ${s.description}` : `- \`${s.name}\``))
    .join("\n");
}
```

默认 Skills 段提示（存进 `system_config.yaml`，Web Skills 页可改文案）明确要求「先读全文再遵循」：

```275:277:packages/core/src/state/default-config.ts
export const LEGACY_SKILLS_SECTION = `# Skills
Skills are reusable instruction packages at \`<app_data_dir>/agents/<agent_id>/agent_state/skills/<skill_name>/SKILL.md\`. When a task matches one below, or the user asks for one (the message may start with a [use_skills] block naming them), read that SKILL.md in full with read_file, then follow it. If a request names a skill without a concrete task, ask the user what they need first.
${SKILL_METADATA_PLACEHOLDER}`;
```

### 1.5 渐进式加载：进 Prompt 的两层

```text
已安装目录 agent_state/skills/
        │
        ├─ listInstalledSkills → skillMetadataSection
        │         │
        │         ▼
        │   系统 Prompt 的 {{SKILL_METADATA}} / {{SKILLS}}
        │   （索引层：name + description）
        │
        └─ 任务匹配或 [use_skills] 点名
                  │
                  ▼
            模型调用 read_file / Shell
                  │
                  ▼
            SKILL.md 全文进入对话上下文（正文层）
                  │
                  ▼
            按说明书用现有工具干活
```

| 层 | 何时进上下文 | 谁写入 Trace |
|----|--------------|--------------|
| 索引层 | 组装系统 Prompt 时 | 通常随 `session_meta.system_prompt` 记一份快照 |
| 正文层 | 模型主动读文件后 | 普通 `tool_call` + `tool_call_output`（读文件结果） |

**固定算法**：没有「Skill 执行器」分支。  
**扩展点**：加/改 `SKILL.md`；改 `system_config.skills.prompt` 文案；改库包 `packages/skills`。

### 1.6 内置库分组（直觉，非穷尽）

库分组以 `packages/skills/src/index.ts` 的 `SKILL_GROUPS` 与目录为准。建立直觉即可：

| 分组直觉 | 例子 | 备注 |
|----------|------|------|
| 软件工程 | `software-engineering` | 最小改动与验证 |
| 数据 / 分析 | `data-analysis` | 有界证据 |
| Agent 调优 | `agent-optimization`、`agent-evaluation`、`benchmark-design` | 配合 Benchmark/Snapshot |
| 基础设施模型 | `vllm`、`ollama`、`llamafactory`、`agenthub-models` | 教模型怎么配本地/网关 |
| 产品自身 | `penguin-cli`、`penguin-sdk`、`skill-porting` | 教怎么用 Penguin |
| 手动装 | `humanizer`、`remote-claude-code` 等 `preinstall: false` | 技能库页安装 |

### 1.7 协作过程（写入归属）

| 步骤 | 执行实体 | 写入归属 |
|------|----------|----------|
| 用户/Agent 安装 Skill | SDK `installSkill` 或 Web API → 同函数 | 磁盘 `skills/<name>/` |
| 开 Session | Agent 组装 Prompt | 内存系统 Prompt；Trace 记 meta |
| 用户带 `[use_skills]` | Human 输入 / markers | 用户消息进 Trace；Goal 时 round1 可保留块、objective 会 strip |
| 模型读 SKILL.md | Environment `read_file` 或 `exec_command` | 工具输出进流与 Trace |
| Agent 改写自己的 Skill | 同一套文件工具写回 `skills/` | **磁盘真源立刻变**；下次组装读到新元数据 |

### 1.8 固定 vs 扩展

| 层次 | 内容 | 怎么换 |
|------|------|--------|
| 固定 | 「无 Skill 工具；用 read_file」 | 改源码级产品契约 |
| 文件可扩 | 任意 SKILL.md | 丢文件 / 技能库安装 |
| 配置可扩 | skills section 开关与 prompt 文案 | `system_config.yaml` |
| 禁止误解 | 「装 Skill = 注册插件 hook」 | 不存在 |

### 1.9 本节小结

想给 Agent 加领域能力：**默认写 Skill**，不要找 Cordis。索引省 Token，正文按需读；文件无缓存，所以可被 Agent 自己改写并配合 Benchmark 做自进化。

---

## §2 Environment 与内置工具

### 2.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **Environment** | 工具端口实现：注册表 + MCP + `executeTool` | 「工具运行时 / sandbox 门面」 | 审批策略中心；ReAct 调度器 |
| **`executeTool`** | 已批准 tool_call 的唯一副作用入口 | RPC handler | 引擎内部私有方法（它是 Environment 公开契约） |
| **BuiltinTool** | 九个工厂表里的内置实现 | 内置命令 | MCP 工具 |
| **`mcp__server__tool`** | MCP 工具进入同一命名空间的命名约定 | 外部插件工具名 | 另一套审批通道 |
| **permission `r`/`rw`** | 工具定义上的只读/读写标注 | Unix 能力标签 | ApproveFn 本身 |

### 2.2 实体边界表

| 实体 | **拥有** | **不拥有** | 依赖谁 | 禁止渗入 |
|------|----------|------------|--------|----------|
| **Environment** | 工具实例表、workspace 相对路径、超时/截断/失败收敛、MCP 连接结果 | 何时发起 tool_call；产品 allow/deny | Workspace、可选 MCP、SubagentRunner | ContextEngine 的 MergeQueue |
| **Builtin 工厂表** | name→factory | 会话生命周期 | `ToolDefinitionConfig` | Web 渲染逻辑 |
| **MCP provider** | 懒连接、工具解析、`readOnlyHint`→permission | 引擎重试策略 | Session `ensureReady` / `listTools` | 绕过 `executeTool` 收尾 |
| **ApproveFn** | allow/deny 决策 | 工具怎么跑 | 表面注入；引擎 await | Environment 内部「再审批一次」 |

### 2.3 统一入口 `executeTool`（契约）

PART1 说过：副作用全在 Environment。引擎只决定「何时审批、何时并发、如何保序回填」。`executeTool` 的文件头把契约写死了：

```220:245:packages/core/src/environment/environment.ts
  /**
   * Executes an approved tool call, streaming `partial_tool_call_output` and a final
   * `tool_call_output`; nested messages carrying origin pass through unchanged. Dispatches by
   * looking up the tool name; any exception collapses into an explanatory output — never throws.
   *
   * The priority for deciding stop_reason is: user interruption > timeout > tool throw > tool
   * self-report. Interruption is determined by the `signal` held by Environment, and is
   * compatible with both a tool self-reporting aborted and an AbortError raised by the
   * interruption. An internal abort raised by a timeout does not count as a user interruption —
   * it's finalized as failed, with the timeout reason written into the output.
   * Docs: /docs/tools § "Execution contract".
   */
  async *executeTool(request: ToolExecutionRequest): AsyncGenerator<OmniMessage> {
    const payload = request.toolCall.payload;
    // tool_call_id is passed through unchanged, so context_engine and the LLM can associate the
    // request with its result.
    const toolCallId = payload.tool_call_id;
    const name = payload.name;

    // Every path is framed uniformly by Environment: entering execution emits start; the end
    // uniformly emits stop + the full message.
    yield partialToolCallOutput({ eventType: "start", toolCallId });

    // Builtin lookup first; an MCP-prefixed name resolves through the provider (which
    // connects on demand — resolution failures fall through to the unknown-tool reply).
    const tool = this.tools.get(name) ?? (await this.mcp?.resolveTool(name));
```

子 Agent 审批回调**透传**（不是 Environment 自创策略）：

```299:306:packages/core/src/environment/environment.ts
    const gen = tool.execute(args, {
      workspaceDir: this.workspaceDir,
      toolCallId,
      signal: ac.signal,
      // Pass through the parent's approve callback (run_subagent uses it so the child Session
      // inherits the parent's approval mode; other tools ignore it).
      ...(request.approve ? { approve: request.approve } : {}),
    });
```

### 2.4 九个内置工具目录（拥有什么）

工厂表是「加第十个工具」的唯一登记点：

```36:53:packages/core/src/environment/tools/registry.ts
/** Tool name -> factory. */
export const BUILTIN_TOOL_FACTORIES: Record<string, BuiltinToolFactory> = {
  [READ_FILE_NAME]: createReadFileTool,
  [EDIT_FILE_NAME]: createEditFileTool,
  [WRITE_FILE_NAME]: createWriteFileTool,
  [EXEC_COMMAND_NAME]: createExecCommandTool,
  [INPUT_COMMAND_NAME]: createInputCommandTool,
  [SUBAGENT_NAME]: createSubagentTool,
  [INPUT_SUBAGENT_NAME]: createInputSubagentTool,
  [READ_IMAGE_NAME]: createReadImageTool,
  // describe_image: the text-only-model variant of read_image (hands the image to the
  // configured vision model for description, returns text).
  // Which tool is used for which model class is declared by the config entry's forModel
  // annotation; before assembly, selectBuiltinToolsForModel has already filtered out entries
  // that don't apply to the session's model.
  [DESCRIBE_IMAGE_NAME]: (definition, services) =>
    createDescribeImageTool(definition, services?.visionDescriber ?? { modelId: null }),
};
```

| 工具 | permission | **拥有的副作用** | **不拥有** |
|------|------------|------------------|------------|
| `read_file` | r | Workspace 内分页读文本（`cat -n` 风格） | 改文件；审批决策 |
| `edit_file` | rw | 精确字符串替换 + unified diff 回显 | 模糊「差不多改一下」 |
| `write_file` | rw | 新建或整体覆写（注重原子写） | 审批；MCP |
| `exec_command` | rw | Workspace 内 `bash -lc`；可转后台得 `process_id` | 子 Agent 会话管理 |
| `input_command` | rw | 对后台命令写 stdin / Ctrl-C / 轮询 | 起新进程（那是 exec） |
| `run_subagent` | rw | 派同 Workspace 子 Session；前台窗口 + 可转后台 `subagent_id` | 父 Trace 嵌子全文 |
| `input_subagent` | rw | 轮询/空闲时追加 Prompt；转发挂起审批 | 突破深度帽 |
| `read_image` | r | vision 会话：把图带回模型上下文 | text-only 会话的代读 |
| `describe_image` | r | text-only：用 Project `vision_model` 代读成文字 | 自己当 vision 主模型 |

装配时按会话模型的 vision 标记过滤 `forModel: "vision" | "text-only"`。命令 / Subagent 类可带必填 `description` 参数供 UI 展示「这次在干什么」；可用 `call_description: false` 从 schema 滤掉。

默认工具配置（含 permission / timeout / maxOutputLength）在 `defaultBuiltinTools()`（`default-config.ts`），随 `system_config.yaml` 可改描述与限额，但**名字与工厂表**仍是源码级登记。

### 2.5 MCP 连接时机（写入归属）

| 时机 | 谁执行 | 流上事件 | 磁盘 |
|------|--------|----------|------|
| `createSession` | Agent | 通常还不连 MCP | 无 |
| 首次 `session.run` → `ensureReady` | Session + Environment.`listTools` | `mcp_connect_begin` / `mcp_connect_end` + `tool_list_ready` | Trace 记这些事件 |
| 之后 `executeTool` | Environment | 普通 tool 流 | Trace 记输出 |
| 用户中断连接中 | `cancelMcpConnect` | abort 相关 | 下次 listTools 重连 |

**懒连接**是产品选择：创建 Session 要快；第一次 run 可能慢，但 UI 能看见进度事件，而不是静默卡住。

### 2.6 收尾契约（引擎依赖的假设）

1. 工具只需 yield 增量；**start/stop/完整消息/截断**由 Environment 统一做。  
2. `timeoutMs`（工具各异，常见数十秒到 120s 量级）→ 终态 `failed`（超时**不算**用户中断）。  
3. `maxOutputLength`（常见约 16000 字符）从前截断保头；`note`（如 exit code）与图像挂在截断范围外。  
4. 错误**永不**向引擎抛裸异常——一律变成可记账的 `tool_call_output`。  
5. 过长输出可另存 Session scratchpad 的 recovery 文件；Trace/模型/UI 仍只看有界窗口 + 路径指针。  
6. 审批边界：**Environment 不做产品审批**。deny 时引擎自己合成 `Tool call denied by user.`。

### 2.7 协作：一次已批准工具调用

```text
ContextEngine（已 await ApproveFn → allow）
  └─ Environment.executeTool
        ├─ yield partial start
        ├─ builtin Map 或 mcp.resolveTool
        ├─ JSON.parse arguments（失败 → failed 输出）
        ├─ 合并 user signal + timeout AbortController
        ├─ tool.execute(... { approve? })
        ├─ 前截断 + 可选 archiveCapture
        └─ yield stop + 完整 tool_call_output（永不 throw）
```

| 步骤 | 执行实体 | 写入归属 |
|------|----------|----------|
| allow | ApproveFn（表面） | `approval_decision` 事件 → 流/Trace |
| 跑工具 | Environment + Builtin/MCP | Workspace/进程；输出 → 流/Trace |
| 截断归档 | Environment | scratchpad recovery（若有） |
| 回填模型历史 | ContextEngine | 内存上下文；完整消息已由 Trace 记录 |

### 2.8 本节小结

改「调度与保序」看 ContextEngine；改「副作用与收尾」看 Environment。扩展能力优先 **MCP 或 Skill 指导模型用现有工具**，只有现有契约盖不住时才加第十个内置工具（登记工厂表 + 文档同步）。

---

## §3 模型与 AgentHub

### 3.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **`(provider, model_id)`** | 模型身份二元组；任何环节禁止拼串猜测 | 「主键是两列」 | `provider/model` 单字符串；「只给一半让系统猜」 |
| **AgentHub** | `@prismshadow/agenthub`：厂商协议适配网关 | LLM SDK 路由器 | ContextEngine |
| **GenerativeModel** | core 侧薄适配，实现 `LLMInterface` | Adapter | 业务编排器 |
| **thinking level** | `none\|low\|medium\|high\|xhigh` | reasoning effort | 模型 id 的一部分 |
| **session 锁模型** | 创建 Session 时选定，该 Session 内不变 | 连接绑定 | Agent 永久绑定某一模型 |

### 3.2 实体边界表

| 实体 | **拥有** | **不拥有** | 依赖谁 | 禁止渗入 |
|------|----------|------------|--------|----------|
| **Project `.project_config.toml`** | 模型表、凭据、默认模型、可选 `vision_model`、`default_chat.thinking_level` | Trace 正文；ReAct | `PENGUIN_HOME/<project>/` | 手改成「半个引用」 |
| **Agent `system_config.model`** | Agent 默认 thinking、max_tokens、timeout | 具体厂商 HTTP | Agent State | 把 provider SDK 写进来 |
| **Session** | 本会话锁定的 `(provider, model_id)`、生效 thinking | 全局模型目录编辑 UI | Agent + Project 表 | 中途静默换模型 |
| **AgentHub / GenerativeModel** | 协议翻译、流式 token/tool_call | 何时停 Task | 凭据 + modelId | ContextEngine 内写 `if (claude)` |

### 3.3 二元组硬规则（源码）

创建 Session 时半个引用直接抛错——猜 provider 会把凭据发错厂商：

```188:199:packages/core/src/agent.ts
  async createSession(opts: CreateSessionOptions = {}): Promise<Session> {
    // Model is validated first (before creating the Workspace, so failure leaves no
    // temporary workspace behind): the reference must be the complete (provider, model_id)
    // pair — the config's unique key — and must name an entry in the Project config; a
    // reference outside the config throws immediately rather than passing silently,
    // otherwise credentials, pricing, and the context window would all be unavailable.
    // Half a reference is always an error: the missing half is never inferred, since a
    // guessed provider would send the entry's credential to a vendor nobody named.
    if ((opts.modelId === undefined) !== (opts.provider === undefined)) {
      throw new Error(
        "A model reference must be given as a (provider, model_id) pair: both must be specified, or neither (to use the Project's default model).",
      );
    }
```

`run_subagent` 同样强制成对：

```86:92:packages/core/src/environment/tools/run-subagent.ts
      // A model is referenced by the complete (provider, model_id) pair — never half of one.
      // Caught here rather than in createSession so the model is told which half it left out.
      if ((modelId === undefined) !== (provider === undefined)) {
        yield* fail(
          "[run_subagent error: `model_id` and `provider` must be given together (a model reference is the pair), or both omitted to inherit the parent session's model]",
        );
        return { stopReason: "failed" };
      }
```

### 3.4 Project 模型表字段（叙事）

`.project_config.toml`（隐藏、权限宜 0600），由 `penguin config model …` 或 Web 维护。常见字段：

| 字段 | 影响 |
|------|------|
| `provider` + `model_id` | 主键 |
| `context_window` | 压缩阈值与输出上限收敛；不填常按 128k 类假定——**小窗口模型会先撞硬限制** |
| `max_tokens` | 输出帽 |
| `client_type` | AgentHub 客户端类型（如 openai 兼容） |
| `vision` | 是否装配 `read_image` vs `describe_image` |
| `pricing` 三档 | 用量统计 |
| `api_key` / `base_url` | 可空 → 回退环境变量（如 `DEEPSEEK_API_KEY`；部分网关回退 `OPENAI_API_KEY`） |

自定义 / 本地 vLLM 常踩坑：**(1)** 必须开工具调用（vLLM 需 auto tool choice + parser），否则 tool_call 变纯文本；**(2)** `context_window` 必须真实。

### 3.5 Thinking 解析链

Session 的 thinking 是三态（见 `CreateSessionOptions` 注释）：

| 入参 | 含义 |
|------|------|
| `ThinkingLevelName` | 钉死该等级 |
| `undefined` | 走配置链：Agent `model.thinking_level` > Project `default_chat.thinking_level` > 内置 `"medium"` |
| `null` | **禁止**回落配置；不向 LLM 配置写入 thinking；meta 可回显 `"default"` |

子 Agent **总是**传父 Session 的生效值（或父为 none 时的 `null`），避免跨 Agent spawn 掉进子 Agent 自己的配置。

压缩请求用默认/会话工具集策略见 §6；`auth` 失败时 Web 锁输入——终态类别，引擎不重试。

### 3.6 Agent 不绑模型；`/model` = handoff

模型在 `createSession` 选定并锁定。会话内换模型 = 新建 Session（同 Agent、同 Workspace、新模型），首条可带 `[model_switch_from]` 指向源 Trace——历史不跨模型注入（部分模型要求 thinking/`fidelity` 逐字一致）；需要旧上下文时按路径自读源 JSONL。

### 3.7 `createLLM`：压缩后换新对象

组装层在 bootstrap 解析工具集后，提供 `createLLM(sessionTokens)`：成功压缩后换**新** `GenerativeModel`，带上同一套 system prompt + tools（前缀保持可缓存），并延续 session token 累计：

```838:845:packages/core/src/agent.ts
    const createLLM = (sessionTokens: TokenCounts): GenerativeModel => {
      if (llmConfig === null) {
        throw new Error("createLLM called before the session bootstrap resolved the toolset");
      }
      const next = new GenerativeModel(llmConfig);
      // Carries over the Session's cumulative Token counts, so token_usage.session stays continuous across compaction.
      next.sessionTokens = sessionTokens;
      return next;
    };
```

### 3.8 本节小结

core 保持薄模型层：换厂商、加 OpenAI 兼容端点，不应改 ContextEngine。身份永远是二元组；Session 锁模型、Agent 不锁——同一套行为定义可在不同 Session 用不同模型跑。

---


## §4 Goal 模式：外环多 Task，内环仍是 ContextEngine

### 4.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **Goal 模式** | 同一 Session 上反复跑 Task，直到目标终态 | 「外层 supervisor 循环」 | 另一套 ReAct 引擎 |
| **`GOAL.yaml`** | Session scratchpad 里的控制信箱 | 状态机 mailbox | Trace 真源；系统每次重写的权威 objective |
| **`goal_finished`** | 流上恰好一条终态事件 | 工作流 end event | 写回 GOAL.yaml 的系统 status |
| **预算** | 未缓存 input+output（含子 Session）累计上限 | token budget | 硬打断进行中的一轮（耗尽先给 wrap-up） |

### 4.2 实体边界表

| 实体 | **拥有** | **不拥有** | 依赖谁 | 禁止渗入 |
|------|----------|------------|--------|----------|
| **`runGoalLoop`** | 轮次协议、预算计数、硬轮帽、创建时写 GOAL.yaml、只读 status | 单轮 ReAct | `GoalRoundRunner`（Session 单 Task 路径） | 替代 ContextEngine |
| **`GOAL.yaml`** | 创建时的 objective+active；之后模型可写 complete/blocked | 系统侧 budget_limited/aborted 落盘 | scratchpad 路径 | 被当成「可篡改 objective 真源」 |
| **ContextEngine** | 每一轮 Task 的内环 | Goal 何时再开火 | 与普通 run 相同 | 解析 GOAL.yaml |
| **Server `goal_state` 表** | UI 可读的运行态索引 | 对话正文 | Goal 流事件 | 覆盖磁盘协议文件语义 |

### 4.3 入口与分流

`session.run(input, { goal: { budget } })` 是唯一 SDK 入口；Web `/goal`、CLI `/goal[:预算]`、`penguin run --goal`、Server body 带 `goal` 都落到同一选项。Session 顶层分流：

```296:308:packages/core/src/session.ts
  async *run(newMessages: OmniMessage[], opts?: SessionRunOptions): AsyncGenerator<OmniMessage> {
    if (opts?.goal) {
      // Rounds run with the caller's per-call options minus `goal` (each round is a plain Task).
      const { goal, ...roundOpts } = opts;
      yield* this.runGoal(newMessages, goal, roundOpts);
      return;
    }
    yield* this.runTask(newMessages, opts);
  }
```

### 4.4 `GOAL.yaml` 所有权（写死在注释里）

```1:17:packages/core/src/goal/goal-file.ts
/**
 * GOAL.yaml — the goal-mode control file, at `<agentDir>/scratchpad/<sessionId>/GOAL.yaml`
 * (path helper: `goalFilePath` in state/paths.ts; sibling of the model's PLAN.md convention).
 *
 * The system writes this file ONCE, when the goal starts, and never rewrites it:
 * - `objective`: recorded at creation for the model's (and a human's) reference; the
 *   canonical value lives in the loop's memory and is re-stated in every round's [goal]
 *   block, so a tampered file changes nothing.
 * - `status`: the model's only writable field, and only to `complete` / `blocked` — its
 *   mailbox back to the loop, read after every round. System-side endings (budget_limited /
 *   aborted) are reported on the stream (`goal_finished`) and in server state, never written
 *   here: the file always keeps the model's own last write, which is exactly the resume
 *   point an interrupted goal wants.
 *
 * Reading is deliberately tolerant: the model rewrites the file with shell tools, so a parse
 * failure, a missing file, or an out-of-protocol status all normalize to `blocked` — the loop
 * stops and hands back to the user instead of spinning on a broken control channel.
 */
```

路径助手：

```85:96:packages/core/src/state/paths.ts
/**
 * `<agentDir>/scratchpad/<sessionId>/GOAL.yaml`, the goal-mode control file of one Session
 * (sibling of the model's PLAN.md convention; see goal/goal-file.ts for field ownership).
 */
export function goalFilePath(
  root: string,
  projectId: string,
  agentId: string,
  sessionId: string,
): string {
  return path.join(sessionScratchpadDir(root, projectId, agentId, sessionId), "GOAL.yaml");
}
```

### 4.5 外环算法（写入归属逐步）

循环驱动注释把终止源列全了：

```1:31:packages/core/src/goal/goal-loop.ts
/**
 * Goal-mode loop driver: repeatedly runs Tasks until the goal file says stop. This is the
 * engine room of `session.run(input, { goal })` — Session supplies the per-round Task runner
 * (its own single-Task path, approval/signal/thinking level already applied) and this module
 * owns the round protocol; it is not part of the SDK surface.
 *
 * Each round's `[goal]`-prefixed user message is yielded **before** the round runs — the
 * Task runner never yields its own input, and subscribers need the round input on the stream
 * (the Trace is written by the engine as usual). The final yield is always exactly one
 * `goal_finished` event message carrying the outcome; there is no generator return value.
 *
 * Termination is decided from these sources only:
 * - the goal file's status (`complete` / `blocked`, written by the model; parse failures
 *   normalize to `blocked` — see goal-file.ts),
 * - the loop's own token accounting against the budget (internal counters; the budget
 *   line in each round's block is composed from them, never read from anywhere),
 * - a round the engine cut off rather than finished — a main-session abort (LLM failure,
 *   user interrupt) or a final assistant notice with `stop_reason: "failed"` (the engine's
 *   max_turns cutoff emits exactly that, and no abort event): the model never got to write
 *   the file, so re-firing would loop the same cutoff forever, and
 * - a hard round cap (`maxRounds`, default 100) as a runaway backstop independent of the
 *   budget — without it an unbudgeted goal whose model simply never writes the file would
 *   loop without bound; an explicit -1 disables the cap.
 * All of these stop the loop without re-firing. The loop writes GOAL.yaml exactly once,
 * at creation; afterwards it only READS `status` — every ending leaves the model's own
 * last write on disk (system endings exist only as the `goal_finished` outcome), which is
 * exactly the resume point an interrupted goal wants.
 *
 * Token accounting is incremental, "uncached input + output": every `token_usage` event on
 * the stream — including origin-marked ones from subagent sessions, which are part of the
 * goal's cost — contributes `request.total - request.cache_read`.
 */
```

| 步骤 | 谁执行 | 内存 | 磁盘 / 流 |
|------|--------|------|-----------|
| 启动 | `runGoalLoop` | 记 objective、used、rounds | **唯一一次** `writeGoalFile(active)` |
| 每轮开始 | loop | — | **先 yield** `[goal]` 用户消息，再 `session.run([input])` |
| 轮内 | ContextEngine | 普通 Task 上下文 | Trace 照常 append |
| 记账 | loop | `used += delta`（含子 origin） | `token_usage` 已在流上 |
| 轮后读 status | `readGoalStatus` | — | 只读文件；坏通道 → blocked |
| 预算耗尽 | loop | — | 再跑 **wrap-up** 一轮，然后 `goal_finished`（complete 或 budget_limited） |
| 结束 | loop | — | 恰好一条 `goal_finished`；**不**把 budget_limited 写进 YAML |

硬轮默认：

```66:67:packages/core/src/goal/goal-loop.ts
/** Default `maxRounds`: the runaway backstop for goals with no (or a huge) budget. */
export const GOAL_MAX_ROUNDS = 100;
```

### 4.6 图片在 Goal 路径上的特殊折法

Goal 路径上图片**总是**折成 `[attached image: …]` 路径行（与普通 Prompt「仅无视觉才折」不同）：objective 每轮当文本重注，图片无法以图像形态跟着走；作路径则可跨轮、跨压缩稳定存在，模型真要看时再 `read_image` / `describe_image`。

### 4.7 与 ContextEngine 的关系（防误解）

```text
session.run(..., { goal })
   └─ runGoalLoop          ← 外环（产品协议）
         └─ 每轮 runTask
               └─ ContextEngine.run / runTurn   ← 内环（固定 ReAct）
```

调试「Goal 不停」：先看 `GOAL.yaml` status、预算、硬轮上限、主会话 abort / max_turns failed——**不要**先怀疑 `runTurn` 写错了。

### 4.8 本节小结

Goal = Session 外环多 Task + GOAL.yaml 信箱；ContextEngine = 内环。系统写文件一次，此后只读 status；系统终态走 `goal_finished`，不污染模型的 resume 点。

---

## §5 Subagent

### 5.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **Subagent** | `run_subagent` 派生的子 Session | 「委派给子代理」 | 同一 transcript 里的函数调用 |
| **`origin`** | 嵌套消息上的跳点标签 | 调用栈帧 | 父 Trace 正文的一部分 |
| **`MAX_SUBAGENT_DEPTH`** | 派生深度帽（默认 1） | 递归深度限制 | UI 配置项（当前是源码常量） |
| **前台窗口 / 后台会话** | 与 exec_command 同构的两段式 | yield 超时转后台 | 无限前台挂起 |

### 5.2 实体边界表

| 实体 | **拥有** | **不拥有** | 依赖谁 | 禁止渗入 |
|------|----------|------------|--------|----------|
| **`SubagentRunner`（Agent 注入）** | spawn/run/dispose；深度检查；继承策略 | 工具收尾 | `createAgent`/`createSession` | Environment 自己 `new Agent` 绕过帽 |
| **`ManagedSubagentSession`** | 后台注册、挂起审批队列、轮询 | 父引擎 MergeQueue | Environment services | 父 JSONL 嵌子全文 |
| **父 Trace** | `subagent` 指针事件 | 子对话正文 | Writer | 把子 thinking 当父历史 |
| **子 Trace** | 子 Session 完整 JSONL | 父审批策略定义 | 子 Writer | — |

### 5.3 深度帽

```71:76:packages/core/src/agent.ts
/**
 * Maximum subagent spawn depth. Currently capped at 1 level (a subagent cannot spawn
 * another subagent); the depth mechanism is designed to support multiple levels —
 * raise this constant to allow deeper nesting.
 */
const MAX_SUBAGENT_DEPTH = 1;
```

spawn 时检查：

```613:617:packages/core/src/agent.ts
      async spawn({ agentId, modelId, provider }) {
        if (subagentDepth >= MAX_SUBAGENT_DEPTH) {
          throw new Error(
            `subagent depth limit ${MAX_SUBAGENT_DEPTH} reached; not spawning another subagent`,
          );
        }
```

抛错由 Environment 收敛为 failed 工具输出（对模型可见），而不是打崩 Task。

### 5.4 继承矩阵

| 项目 | 是否继承 | 说明 |
|------|----------|------|
| Workspace | 是 | 同目录；resume 也要求原 Workspace 仍在 |
| ApproveFn / 审批模式 | 是 | 子 run 透传父 callback；后台挂起审批下次 poll |
| thinking level | 是（父生效值 / null） | **不**回落子 Agent 自己的 config |
| 模型 | 默认同父；可显式成对指定 | 半个引用拒绝 |
| Agent id | 默认同父；可换已存在 agent | 跨 Agent 仍继承 proxyEnv 策略 |
| Trace | **否** | 子独立 JSONL；父只留指针 |
| 再派子 | 默认否 | depth≥1 拒绝 |

工具层叙事（`run-subagent.ts` 文件头）强调：工具不依赖 Agent/Session 类型，只持注入的 `SubagentRunner`，打破循环依赖；两段式语义镜像 `exec_command`。

### 5.5 协作过程（写入归属）

| 步骤 | 执行实体 | 写入归属 |
|------|----------|----------|
| 模型调 `run_subagent` | 引擎审批 → Environment | 父流上的 tool 帧 |
| spawn | SubagentRunner | 子 Session + 子 Trace 文件开始 |
| 前台窗口转发 | collectWindow | 带 `origin` 的消息进**父流**；父 Trace **跳过**嵌套正文（按设计） |
| 超时转后台 | manager 注册 | 返回 `subagent_id`；子继续跑 |
| `input_subagent` | 同管理器 | 追加 Prompt / 抽审批 |
| 结束 dispose | handle | 释放子资源 |

### 5.6 本节小结

Subagent 共享产品语义（工具、审批、Workspace），但是**独立会话上下文与 Trace**。把它理解成「同一 transcript 里的函数调用」会在 resume 与计费上踩坑。

---

## §6 Compaction（上下文压缩）

### 6.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **Compaction** | 引擎内一等公民的上下文压缩 | 会话摘要 / 开新窗口 | 外挂 cron 脚本 |
| **summarize** | 向旧上下文要 `[summary]`，包装为 `[context_summary]` 开新上下文 | map-reduce 摘要 | 静默丢历史 |
| **discard** | 直接丢旧上下文开新段 | clear 但留 Session | 失败回退路径 |
| **Trace rotate** | 压缩成功后切 `_002`、`_003`… 新 JSONL | WAL 分段 | 改写旧文件内容冒充新上下文 |
| **`createLLM`** | 压缩成功后换新 GenerativeModel 对象 | 新 client / 新 KV cache | 改 model_id |

### 6.2 实体边界表

| 实体 | **拥有** | **不拥有** | 依赖谁 | 禁止渗入 |
|------|----------|------------|--------|----------|
| **ContextEngine compaction** | 触发判定、summarize/discard 流程、事件对 | 磁盘路径公式细节 | `createLLM` + TraceSink.rotate | UI「假装压缩」 |
| **`system_config.compaction`** | mode、阈值、prompt | 运行中临时策略库 | Agent State | 与 Project 模型表抢 context_window |
| **Writer.rotate** | 新分片文件 + session_meta | 摘要文本生成 | Engine 成功路径 | 失败时仍 rotate |
| **resume** | 识别 compaction 收尾、重建 summary 前缀 | 自动再压一次 | 最新 index Trace | 把 SQLite 当历史 |

### 6.3 默认配置

```880:885:packages/core/src/state/default-config.ts
    compaction: {
      max_context_length: 128000,
      max_session_turns: -1,
      mode: "summarize",
      prompt: DEFAULT_COMPACTION_PROMPT,
    },
```

生效阈值还会被 `context_window − 2048` 夹住（见 `effectiveMaxContextLength`），避免小窗口模型先撞硬限制。

### 6.4 触发 reason

| reason | 何时 |
|--------|------|
| `context` | 上一轮 `token_usage.request.total` ≥ 阈值 |
| `turns` | Session 累计轮数（跨 Task）达阈值；默认常为不限（-1） |
| `manual` | `/compact` 或 `session.compact()` |

`session.compact` 只能在 Task 边界调用；未 bootstrap 的空 Session 是严格 no-op（避免留下「可 resume」假象）：

```569:581:packages/core/src/session.ts
  /**
   * User-initiated request to compact context (e.g. a CLI command): reuses the automatic
   * compaction flow but skips the threshold check (reason=manual). Only callable at Task
   * boundaries (between runs); streams out paired `compaction` events. The summarize digest
   * becomes the prefix of the next `run`'s input (merged with the next user Prompt). A no-op
   * if compaction isn't configured.
   * Docs: /docs/agent-loop § "Compaction".
   */
  async *compact(opts?: { signal?: AbortSignal }): AsyncGenerator<OmniMessage> {
    // Before the first run there is no context to compact: stay a strict no-op, without
    // bootstrapping — a session that never ran must not leave trace records (meta /
    // tool_list_ready) behind, or an untouched session would look resumable.
    if (!this.engine) return;
    yield* this.engine.compact(opts);
  }
```

`compactability()`：`ok | unsupported | empty | just_compacted`——调用方应据此给反馈，而不是触发静默空压。

### 6.5 summarize vs discard（写入归属）

**discard**：

```1255:1264:packages/core/src/engine/context-engine.ts
  /**
   * `discard` compaction: sends no compaction request, simply discards the old context —
   * swaps in a new LLM object and splits a new Trace file, with the next turn's input used
   * unchanged as the new object's first input. Only runs at a Task boundary (deferred by the
   * caller while mid-Task).
   */
  private async *discardContext(reason: CompactionReason): AsyncGenerator<OmniMessage> {
    yield* this.emitCompactionBegin(reason, "discard");
    yield* this.emitCompactionEnd(reason, "discard", "completed");
    await this.startNewContext();
  }
```

**summarize**（要点压缩进注释，务必读源码头）：

```1267:1292:packages/core/src/engine/context-engine.ts
  /**
   * `summarize` compaction: appends the compaction Prompt to the **old** LLM object (first
   * folding in all of this turn's tool results when mid-Task, to keep tool_use/tool_result
   * pairing), then extracts the `[summary]` and wraps it as `[context_summary]` user text. The
   * compaction request carries the session's toolset **unchanged** — the request prefix must
   * stay byte-identical to ordinary turns so the provider's prompt cache remains valid;
   * compaction runs exactly when the context is largest, where re-billing the whole
   * transcript uncached costs tens of times more (issue #84 — this is why tools are *not*
   * omitted and no `tool_choice` override is used). The
   * compaction request's streamed output is not pushed to the Human output stream (it emits
   * paired compaction events, plus every attempt's `token_usage` — positioned between the two
   * events, so the frontend stats and the server's usage records count the compaction's true
   * spend, rejected attempts included), but it is written
   * to the old Trace. Compaction succeeds only with a **valid summary** — non-empty extracted
   * text and no tool calls in the response. Everything short of that is one kind of failure,
   * handled exactly like an ordinary LLM request's (issue #170): an unusable committed
   * response (empty summary, or tool calls — answered with synthesized failed outputs and
   * retried behind a corrective note, see the loop body) and the transport failures
   * (failed/timeout/malformed) all reconnect under the one `compactionMaxReconnects` budget
   * (defaulting to the turn loop's budget and ladder — see RETRY_STATUSES); only `auth` stops
   * without retrying. Once the budget is exhausted the compaction fails; on failure/abort, the original
   * context and Trace index are kept — it does not fall back to discard. The first **committed**
   * attempt absorbs `pendingToolOutputs` into the old context's history (issue #85): later
   * resends carry only the repairs and the Prompt, and the result's `committed` flag tells
   * the caller the folded input must not be resent even though the compaction did not complete.
   * Docs: /docs/agent-loop § "Compaction".
   */
```

| 路径 | 成功时 | 失败时 |
|------|--------|--------|
| summarize | 新 LLM + Trace rotate + summary 作下轮前缀 | **保留**原上下文与原 Trace；下次再触发；**不**降级 discard |
| discard | 新 LLM + Trace rotate；下轮输入原样作新上下文首包 | （该模式本身无「摘要失败」） |

### 6.6 成功路径上的「一币两面」

```text
compaction_begin
  →（summarize：旧 LLM 上压缩请求；输出进旧 Trace，不进 Human 主气泡流）
  → compaction_end(completed)
  → createLLM(sessionTokens)     ← 新模型上下文对象
  → Trace.rotate()               ← 新 JSONL 分片，写 session_meta
  → 后续 run 以 [context_summary] 等为前缀
```

**一个 Trace 文件恒等于一份完整模型上下文**——这是 resume 读「最大 index」的前提。压缩收尾的 resume 行为见 `trace/resume.ts`（文件级 compaction closure → 空上下文 + 重建 summary）。

### 6.7 本节小结

压缩成功 = 新上下文段 + 新 Trace 分片 + 新 LLM 对象；压缩失败不应毁掉可恢复历史。工具集在压缩请求中保持不变，是为了前缀缓存，不是疏忽。

---

## §7 权限、ApproveFn 与工具的咬合

### 7.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **ApproveFn** | 每个完整 tool_call 一次 allow/deny 回调 | beforeTool 钩子 | Filter 链框架；Environment 内部服务 |
| **permission** | 工具定义上的 `r`/`rw` | 能力标签 | 最终决策（决策在 ApproveFn） |
| **approval mode** | allow-all / deny-all / read-only / always-ask | 策略预设 | Trace 格式字段（决策以事件落盘） |

### 7.2 边界表

| 实体 | **拥有** | **不拥有** |
|------|----------|------------|
| **工具 `permission`** | 标注只读/读写，供模式与 UI 查询 | 自动 allow |
| **ApproveFn** | 最终 allow/deny | 执行副作用 |
| **ContextEngine** | 串行 await 每个 tool_call 的审批；deny 时合成输出 | 替用户做安全策略产品文案 |
| **CLI `makeApprove`** | 把四种模式编译成 ApproveFn | 改工具实现 |
| **Server 持久化模式** | 按 Session 存模式，改完立即生效 | 引擎内核 |

接口定义：

```92:98:packages/core/src/interfaces.ts
/**
 * Per-tool approval callback: the Human boundary gives allow/deny for each complete `tool_call`.
 * `context_engine` calls it once per tool call within a turn. Subagents forward the parent's
 * approval callback, so the child Agent **inherits the parent Agent's approval mode**.
 * Docs: /docs/interfaces § "ApproveFn".
 */
export type ApproveFn = (toolCall: OmniMessage<ToolCallPayload>) => Promise<ApprovalDecision>;
```

CLI 四种模式：

```16:67:packages/cli/src/approval.ts
/**
 * Approval mode (derived from APPROVE_MODES, the single source of truth):
 *   - `allow-all`: auto-approve every tool (default mode);
 *   - `deny-all`: auto-reject every tool;
 *   - `read-only`: auto-approve read-only tools (permission === "r"), defer the rest to a human;
 *   - `always-ask`: interactive approval for each call.
 */
export type ApprovalMode = (typeof APPROVE_MODES)[number];
// ...
export function makeApprove(args: {
  mode: ApprovalMode;
  toolPermission: (name: string) => "r" | "rw" | undefined;
  interactivePrompt: ApproveFn;
}): ApproveFn {
  const { mode, toolPermission, interactivePrompt } = args;
  return async (toolCall) => {
    const name = toolCall.payload.name;
    switch (mode) {
      case "allow-all":
        return "allow";
      case "deny-all":
        return "deny";
      case "read-only":
        // Auto-approve read-only tools; defer read-write/unknown tools to a human.
        if (toolPermission(name) === "r") return "allow";
        return interactivePrompt(toolCall);
      case "always-ask":
      default:
        return interactivePrompt(toolCall);
    }
  };
}
```

Project 侧也有同名枚举常量（Web 草稿预填等）：`CHAT_APPROVAL_MODES` in `project-config.ts`。

### 7.3 写入归属

| 步骤 | 谁 | 落何处 |
|------|----|--------|
| 模型产出 tool_call | LLM → Engine | 流 + Trace |
| await approve | Engine 调表面回调 | — |
| 决策事件 | Engine | `approval_decision` → 流/Trace |
| allow → executeTool | Environment | 工具输出 |
| deny | Engine 合成 | 失败/拒绝说明进上下文与 Trace |

**一轮内审批串行、工具执行可并行**（PART1）：ApproveFn 不要做长时间阻塞的无关 IO，否则拖死整轮。

### 7.4 MCP 与 permission

`Environment.toolPermission`：内置查 config；MCP 在发现后用 server 的 `readOnlyHint` 注解回答。`read-only` 模式依赖这张表——未知工具应 defer 给人类，而不是当成 `r` 放行。

### 7.5 本节小结

权限标注是输入，ApproveFn 是决策，Environment 是执行。三者任一越界（例如在工具里再弹一次「产品审批」）都会造成双通道与 Trace 对不齐。

---

## §8 改代码决策树（哪里改 / 哪里不改）

```text
想加领域知识 / runbook
  → 写或装 Skill（SKILL.md）
  ✗ 不要找 plugin register / 不要改 ContextEngine

想加外部 SaaS 工具
  → MCP server + system_config.tools.mcpServers
  ✗ 不要先发明第十个内置工具（除非契约真盖不住）

想加第 N 个内置工具
  → environment/tools/* + BUILTIN_TOOL_FACTORIES + defaultBuiltinTools + docs/tools
  ✗ 不要在 Web 里「模拟」工具副作用

想换模型厂商 / 兼容端点
  → Project 模型表 + AgentHub 能力
  ✗ 不要在 ContextEngine 写 provider 分支

想改「允不允许跑」
  → 表面 ApproveFn / approval mode / permission 标注
  ✗ 不要改 Trace 格式来「表示拒绝」

想改「多轮直到没 tool」
  → ContextEngine（认清：固定内核，源码级）
  ✗ 不要指望装另一个 loop 插件

想改「长目标直到完成」
  → goal/* 与 GOAL.yaml 协议；或预算/硬轮参数
  ✗ 不要复制一套 Engine

想加深 Subagent 嵌套
  → 提高 MAX_SUBAGENT_DEPTH（并补测试/产品说明）
  ✗ 不要让子 Session 偷偷 subagentDepth: 0

想改压缩策略
  → system_config.compaction 或 summarizeContext 源码
  ✗ 失败时不要自动 discard；不要让 Web 假压缩

想改气泡怎么画
  → packages/web 订 OmniMessage
  ✗ 不要 import ContextEngine 私有方法抄近路
```

### 8.1 「表面 vs 内核」对照表

| 需求 | 正确落点 | 错误落点 |
|------|----------|----------|
| 换审批交互文案 | CLI i18n / Web 审批 UI | Environment |
| 换 ReAct 哲学 | fork Engine（产品边界外） | Skill |
| 换系统人设 | AGENTS.md / system_prompt | Server SQLite |
| 换默认思考等级 | system_config / Project default_chat | Trace |
| 看历史说了什么 | Trace JSONL | usage_records 表 |

---

## §9 本章总结

1. **扩展主路径是 Skill 文件**（渐进式元数据 + 按需读正文），不是 Cordis 插件树；文件无缓存，可自进化。  
2. **工具副作用在 Environment**：约 9 个内置 + MCP；统一超时/截断/失败收敛；审批在 Human/引擎边界。  
3. **模型在 AgentHub + Project 表**：`(provider, model_id)` 成对；Session 锁模型；`createLLM` 服务压缩换对象。  
4. **Goal / Subagent / Compaction** 都挂在 Session/Engine 产品语义上：外环不取代内环；子 Trace 独立；压缩失败保历史。  
5. **ApproveFn × permission × mode** 三层咬合；Environment 只执行已允许的调用。  
6. **改代码先爬决策树**：先文件/配置/表面，再端口，最后才动固定内核。

下一篇：[ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md)（包地图、三表面、数据目录、与 DSH/Pi 对照、扩展 cookbook）。术语：[GLOSSARY.md](./GLOSSARY.md)。


---

## §10 补遗：Skills 发现与 Prompt 组装细节

### 10.1 扫描容错规则（写入归属：只读）

`listInstalledSkills` 的契约：

| 情况 | 行为 |
|------|------|
| `skills/` 不存在 | 返回 `[]` |
| 子项不是目录 | 跳过 |
| 目录无 `SKILL.md` | **不计为 Skill** |
| frontmatter 解析失败 / 缺 name | 回退 `{ name: 目录名, description: "", version: 1, updated: "" }` |
| frontmatter name ≠ 目录名 | **目录名获胜** |
| `icon.svg` 缺失 | 省略 icon 字段（UI 默认书本图标） |
| 排序 | 按 name 稳定排序（Prompt 与 API 一致） |

### 10.2 `{{SKILLS}}` vs 内联 `{{SKILL_METADATA}}`

| 占位符 | 含义 |
|--------|------|
| `{{SKILLS}}` | 整段 Skills section（含说明文案 + 元数据注入点） |
| `{{SKILL_METADATA}}` | 仅元数据行；可出现在默认 section 文案末尾，或遗留模板内联处 |

`system_config.skills.enabled === false` 时，组装层应关掉 Skills 段（见 `assembleSystemPrompt` 路径），但磁盘上的 Skill **仍在**——仍可被显式 `[use_skills]` + `read_file` 用到（产品语义以当时 `default-config` / 组装函数为准：注释写明关闭段不等于删除文件）。

### 10.3 Agent 初始化策略矩阵

| Agent 类型 | 预装 Skill |
|------------|------------|
| `default_agent` 且无 preset | 库中预装集（排除 `preinstall: false`） |
| 带 preset | 仅 preset 列出的 skills |
| 普通新 Agent（非 default、无 preset） | **不预装** |
| `system_config.yaml` 已存在 | **只加载不覆盖**（preset 仅初始化生效） |

`system_config.yaml` **最后写**——存在即「初始化完成」标记；中途崩溃则下次仍走 init 自愈，避免半初始化缺 Skill。

### 10.4 手工安装最小步骤

```text
mkdir -p "$PENGUIN_HOME/<project>/agents/<agent>/agent_state/skills/my-skill"
# 编辑 SKILL.md（含 frontmatter description）
# 下一轮组装系统 Prompt 即出现在元数据索引
```

卸载：删整目录。无需重启「插件宿主」——因为没有插件宿主。

### 10.5 与 Benchmark / Snapshot 的产品闭环（叙事）

Penguin 把 Skill 做成可编辑文件，是为了让 Agent **改自己的说明书**成为合法路径：跑 Benchmark → 看 Trace → 改 `SKILL.md` → Snapshot 固化 `agent_state`。这不是 core 循环的一部分，而是产品层闭环；架构上仍落在「文件真源」同一条纪律。

---

## §11 补遗：工具装配与 forModel 过滤

### 11.1 装配流水线（写入归属）

| 步骤 | 谁 | 结果落在哪 |
|------|----|------------|
| 读 `system_config.tools.builtin` | Agent `buildRuntime` | 内存 ToolDefinitionConfig[] |
| `selectBuiltinToolsForModel` | 按 vision/text-only 过滤 | 去掉不适用的 read_image/describe_image 等 |
| Environment 构造 | 工厂表实例化 BuiltinTool | Environment.tools Map |
| `listTools`（首次） | Environment | 合并 MCP；触发连接；结果进 ensureReady 事件 |

### 11.2 `call_description` 与 UI

命令/Subagent 类工具的 `description` 参数是给**人类观察运行中任务**用的，不是给模型偷懒用的空话。装配期可用 `call_description: false` 从 schema 去掉该字段以省 Token——改配置即可，不必改工具实现。

### 11.3 截断与 recovery 文件

当输出超过 `maxOutputLength`：

| 观众 | 看到什么 |
|------|----------|
| 模型 / Trace 窗口 | 前截断文本 + 指针 |
| scratchpad recovery | 完整文本归档（若 Environment 配置了 session scratchpad） |
| UI | 与模型同一有界窗口，另可提供「打开 recovery」类体验（表面职责） |

删 Session 的既有清理路径会连带 scratchpad——recovery 不是永久备份。

### 11.4 未知工具与 MCP 解析失败

`executeTool`：builtin 未命中 → `mcp.resolveTool`；仍失败 → `Unknown tool: …` 的 failed 输出。**不会**抛到 Engine。这保证 MergeQueue / 配对逻辑总能收到可记账的 tool_call_output。

---

## §12 补遗：模型凭据与 session_meta

### 12.1 凭据解析顺序（叙事）

1. `createSession({ apiKey, baseUrl })` 显式参数  
2. Project 模型表条目的 `api_key` / `base_url`  
3. AgentHub 读环境变量  

创建 Session 时即用 bare LLM 构造探活（无网络），把「缺凭据」失败提前到 Session 出现之前，避免留下半截 Trace。

### 12.2 resume 时模型与工具

resume 注释写明：

- Workspace / `(provider, model_id)` 从原 Session meta 锁定，必须仍存在  
- **工具与 Environment 按当前 Agent State 重装**（工具定义每轮随 Request 走，不是历史的一部分）  
- **系统 Prompt 用 Trace 里记录的原文**（与原历史一致）  
- **vault 用当前值**（注入子进程，不进历史）  
- thinking：legacy meta 中的旧字段**故意忽略**，走当前配置链  

这解释了「我改了 Skill 再 resume」：新工具表会生效，但旧 system_prompt 快照仍按 Trace——若你要新 Prompt，通常应新开 Session 或接受产品提供的升级路径。

### 12.3 `/model` handoff 为何不注入跨模型历史

部分供应商要求 thinking / fidelity 与原请求逐字一致才能续写。跨模型硬塞历史会触发拒识或行为漂移。产品选择：**新 Session + 指针**，需要时模型自己 `read_file` 源 JSONL。

---

## §13 补遗：Goal 轮次消息与 strip 规则

### 13.1 round 1 vs 后续轮

| | round 1 | 后续 regular | wrap-up |
|--|---------|--------------|---------|
| body | 调用方原文（可含 `[use_skills]`） | strip 后的 objective | wrap-up 模板 |
| 目的 | 保留用户显式点名 Skill 等机器前缀 | 稳定重注任务 | 预算耗尽收尾 |

objective 的权威在 loop 内存；YAML 里的 objective 仅供参考，篡改文件**不改变**重注文本。

### 13.2 终止优先级（调试用）

```text
signal aborted（轮间）
  → hard maxRounds
  → 跑 regular round
  → main abort 事件
  → 读 status ≠ active（complete/blocked）
  → roundFailed（max_turns 等）
  → budget → wrap-up → goal_finished
```

主会话 abort **优先于**文件里的 status——工作区与 YAML 保持模型最后写入，作为 resume 点。

### 13.3 Server `goal_state` 与 YAML

| | GOAL.yaml | goal_state 表 |
|--|-----------|---------------|
| 面向 | 模型协议 | UI |
| complete/blocked | 模型写 | 反映 |
| budget_limited/aborted | **不写文件** | 可由流更新 UI |

---

## §14 补遗：Subagent 后台与审批队列

### 14.1 两段式时间线

```text
run_subagent(prompt, yield_time_ms?)
  ├─ spawn child Session（depth+1）
  ├─ 窗口内：转发 origin 消息；复制子文本为工具输出
  ├─ 子结束：返回终态；dispose
  └─ 窗口到期仍在跑：注册 background → 返回 subagent_id
        └─ input_subagent：poll / 追加 prompt / 抽离挂起审批
```

### 14.2 审批在后台

子 Session 在后台产生 tool_call 时，审批请求进入子会话队列；父侧通过 `input_subagent` 轮询时看到 hint（`approvalHint`：等待 N 个审批）。**模式仍继承父 ApproveFn**，不是子 Agent 自己的「另一套默认 allow-all」。

### 14.3 深度帽与「换 Agent」

跨 `agent_id` spawn：加载另一 Agent 的 state/vault，但 **proxyEnv 仍跟宿主进程策略**（Web 管理的代理设置）。深度帽按 spawn 链计算，不因换 Agent 重置为 0。

---

## §15 补遗：Compaction 与 prompt cache

### 15.1 为何压缩请求仍带全工具集

压缩发生在上下文**最大**时。若为了「省事」去掉 tools 或改 tool_choice，请求前缀与普通轮次不再 byte-identical，供应商 prompt cache 失效，整段 transcript 按未缓存计费——成本可高一个数量级。故 summarize **故意**保持工具集不变。

### 15.2 Human 流上看不见压缩正文

压缩模型输出写入**旧 Trace**，但不作为普通 assistant 气泡推给 Human（推的是 compaction 事件对 + token_usage）。前端统计与 server usage 仍能计入真实花费（含失败尝试）。

### 15.3 `just_compacted` 与下轮前缀

若最新 Trace 以完成的压缩收尾，resume 从空上下文起；summarize 模式把 summary 重建为下轮输入前缀。手动 `compact()` 后，下次 `run` 的用户 Prompt 与 summary **合并**，而不是丢用户句。

---

## §16 补遗：端到端「加一个办公 Skill」演练（写入归属）

| 步 | 操作者 | 改谁 |
|----|--------|------|
| 1 | 人类 | 创建 `agent_state/skills/invoice-triage/SKILL.md` |
| 2 | 下次 Session 组装 | 系统 Prompt 元数据多一行 |
| 3 | 用户 | `[use_skills] skills: invoice-triage` + 任务描述 |
| 4 | 模型 | `read_file` → 正文进上下文（工具输出进 Trace） |
| 5 | 模型 | 按说明书 `read_file`/`exec_command`… |
| 6 | （可选）模型 | `edit_file` 改 SKILL.md 自我改进 |
| 7 | （可选）人类 | Snapshot 固化 agent_state |

全程**零**插件注册 API。

---

## §17 固定算法 vs 扩展点（本章总表）

| 层次 | 内容 | 可换方式 |
|------|------|----------|
| 固定 | 无 Skill 运行时；executeTool 收尾契约；二元组模型身份；Goal 外环协议；深度帽机制；压缩失败不 discard；Approve 在 Engine await | 源码 |
| 端口 | LLM/Env/MCP/SubagentRunner | 实现与配置 |
| 文件 | Skill、GOAL、system_config、AGENTS、vault、schedule | 丢文件 |
| 表面 | ApproveFn、四种 mode、UI | CLI/Server/Web |
| 常量可调但属产品决策 | `MAX_SUBAGENT_DEPTH`、`GOAL_MAX_ROUNDS` | 改常量 + 测试 + 文档 |

---

## §18 本章自检（DOC_QUALITY）

- [x] Skills/Env/Model/Goal/Subagent/Compaction/Approve 均有拥有表  
- [x] 关键协作过程有写入归属  
- [x] 新词有对照  
- [x] 决策树明确「改哪不改哪」  
- [x] 代码引用真实路径  
- [x] 非仅目录/仅流程图  
