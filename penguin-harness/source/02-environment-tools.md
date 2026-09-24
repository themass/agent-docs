# 附录 B · Environment 与工具源码走读

> 文件：`packages/core/src/environment/environment.ts` + `environment/tools/`  
> **阅读顺序**：建议先读 [01-context-engine.md](./01-context-engine.md)  
> 读法：白话 → 代码 → 注释 → 本节小结；文末 **本章总结**。  
> 官方对照：`packages/docs/content/tools.zh.md`。

### 本章你会搞懂什么

1. `BuiltinTool` 契约：工具作者最少要写什么
2. `executeTool` 如何统一收尾成可记账的 OmniMessage
3. 九个内置工具各自解决什么问题
4. 审批边界、超时与截断如何影响模型所见

---

## 0. 两层分工

### 白话

| 层 | 职责 | 不职责 |
|----|------|--------|
| ContextEngine | 何时 approve、何时并发、如何保序回填、写审批事件 | 真正读文件 / 起进程 |
| Environment | 查表派发、超时、截断、MCP、把一切收成 tool_call_output | 产品级「让不让跑」的 UX |

引擎假设：Environment **总是**能给出可记账结果（哪怕是 `Unknown tool` 或超时失败文案），**从不**向引擎抛裸异常。

### 本节小结

改「调度」看引擎；改「副作用与收尾」看 Environment。两边用 OmniMessage 对接。

---

## 1. `BuiltinTool` 契约

### 白话

所有内置工具实现同一接口：带 `name`、交给 LLM 的 `definition`、以及流式 `execute`。Environment 按名字查找；未知工具变成解释性 output。以后加新工具（若产品真需要）= 实现接口 + 注册表登记，不必改 Environment 主干。

工具作者的放松版契约：

- 自己的输出：yield **`partial_tool_call_output` 的 delta** 即可；start/stop/完整消息由 Environment 补。
- 嵌套转发：带 `origin` 的消息原样穿过（子 Agent 回流）。
- 终态：用生成器 **return value** `ToolResult`（`stopReason` / `note` / `images`）；抛错由 Environment 折叠。

### 代码

```51:78:packages/core/src/environment/tools/types.ts
/**
 * Builtin tool interface. `execute` receives the already-parsed tool argument object and the
 * execution context, streaming out OmniMessage as an async generator. Contract (a relaxed
 * version — framing and close-out are handled uniformly by Environment):
 *
 * - **Own output**: yielding the **delta** of `partial_tool_call_output` is enough; `start`/`stop`
 *   are optional (Environment ignores the tool's start/stop and frames it itself), and there's
 *   **no need** to produce a complete `tool_call_output` either (the complete message,
 *   maxOutputLength forward truncation, and close-out are all derived by Environment from the
 *   deltas). If a tool does produce a complete `tool_call_output` anyway, Environment uses it as
 *   the basis for content and stop reason (tolerated for compatibility, not recommended).
 * - **Nested forwarding**: yielding any message **tagged with origin** is passed through by
 *   Environment unchanged (e.g. run_subagent forwarding all of a child session's messages).
 * - **Stop reason**: reported via the generator's return value (defaults to completed); a throw
 *   is collapsed by Environment into aborted/failed based on interruption/error, never
 *   propagating up as an exception.
 * Docs: /docs/interfaces § "The inner tool contract: BuiltinTool"; /docs/tools § "Execution contract".
 */
export interface BuiltinTool {
  /** Tool name (corresponds to the tool_call.name returned by the LLM). */
  name: string;
  /** Tool definition handed to the LLM (including description / parameters / permission / maxOutputLength). */
  definition: ToolDefinitionConfig;
  /** Executes one tool call: args is the already-parsed argument object, ctx is the runtime context. */
  execute(
    args: Record<string, unknown>,
    ctx: ToolExecutionContext,
  ): AsyncGenerator<OmniMessage, ToolResult | void>;
}
```

`ToolExecutionContext` 携带 `workspaceDir`、`toolCallId`、`signal`，以及可选的父级 `approve`（给 `run_subagent` 继承审批模式）。

### 注释

| 字段 | 为何存在 |
|------|----------|
| `definition.permission` | CLI/Web 的 read-only 审批模式用 |
| `definition.forModel` | vision / text-only 分流装配 |
| `definition.timeoutMs` | Environment 统一强制；工具只需响应 signal |
| `ToolResult.note` | 截断外附加 exit code 等，避免长输出裁掉终态标记 |
| `ToolResult.images` | data URL；不计文本截断额度 |

### 本节小结

写工具时尽量「只产 delta + return note」；不要自己拼完整 `tool_call_output`，除非你在维护兼容路径。

---

## 2. `listTools` 与装配时机

### 白话

Session 首次 `ensureReady` → bootstrap → Environment 解析内置工厂 +（若配置了）连接 MCP 做工具发现 → 得到 `ToolDefinition[]` → 交给 GenerativeModel 进 schema。连接等待变成可见的 `mcp_connect_begin/end`，完整列表以 `tool_list_ready` 流出（Trace 里写在本轮用户输入之后，见 PART1）。

`system_config.yaml` 的 `tools.builtin` 语义是**整体替换而非合并**：写出即替换默认集，要保留的每个工具必须带完整 `parameters` JSON Schema。MCP 条目见官方 tools 文档：stdio / http / sse，懒连接，失败跳过不堵会话。

### 本节小结

「工具列表从哪来」= Agent State 配置 + 模型类别过滤 + MCP 发现快照（Session 生命周期内，忽略 list_changed）。

---

## 3. `executeTool` 流程

### 白话

引擎在 allow 之后调用这里。流程可以记成：

1. yield `partial_tool_call_output(start)`
2. 按 name 查内置，否则 MCP `resolveTool`；没有 → 失败文案收尾
3. `JSON.parse` 参数；失败 → 解释性失败（仍流式，前端可渲染）
4. 合并用户 `signal` 与超时 `AbortController`；超时标记 `timedOut`，终态按 **用户中断 > 超时 > 抛错 > 自报** 归并
5. 消费工具生成器：delta 做在线头截断；`origin` 消息原样 yield；捕获 return 的 `ToolResult`
6. 统一发 stop + 完整 `tool_call_output`；空输出补 `[no output]`；可选归档超长文本到 scratchpad recovery

### 代码（入口与派发）

```220:266:packages/core/src/environment/environment.ts
  /**
   * Executes an approved tool call, streaming `partial_tool_call_output` and a final
   * `tool_call_output`; nested messages carrying origin pass through unchanged. Dispatches by
   * looking up the tool name; any exception collapses into an explanatory output — never throws.
   *
   * The priority for deciding stop_reason is: user interruption > timeout > tool throw > tool
   * self-report. ...
   * Docs: /docs/tools § "Execution contract".
   */
  async *executeTool(request: ToolExecutionRequest): AsyncGenerator<OmniMessage> {
    const payload = request.toolCall.payload;
    const toolCallId = payload.tool_call_id;
    const name = payload.name;

    yield partialToolCallOutput({ eventType: "start", toolCallId });

    const tool = this.tools.get(name) ?? (await this.mcp?.resolveTool(name));
    if (!tool) {
      yield* emitFailure(toolCallId, `Unknown tool: ${name}`);
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(payload.arguments);
    } catch (err) {
      yield* emitFailure(toolCallId, describeArgumentsError(name, payload.arguments, err));
      return;
    }

    const args =
      parsed !== null && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};

    const maxOutputLength = tool.definition.maxOutputLength ?? DEFAULT_MAX_OUTPUT_LENGTH;
    const timeoutMs = tool.definition.timeoutMs ?? DEFAULT_TOOL_TIMEOUT_MS;
    const signal = request.signal;
```

超时与工具执行上下文（含父 approve 透传）：

```268:306:packages/core/src/environment/environment.ts
    const ac = new AbortController();
    if (signal?.aborted) ac.abort();
    const onAbort = (): void => ac.abort();
    signal?.addEventListener("abort", onAbort, { once: true });
    let timedOut = false;
    const timer =
      timeoutMs > 0
        ? setTimeout(() => {
            timedOut = true;
            ac.abort();
          }, timeoutMs)
        : null;
    timer?.unref?.();
    // ...
    const gen = tool.execute(args, {
      workspaceDir: this.workspaceDir,
      toolCallId,
      signal: ac.signal,
      // Pass through the parent's approve callback (run_subagent uses it so the child Session
      // inherits the parent's approval mode; other tools ignore it).
      ...(request.approve ? { approve: request.approve } : {}),
    });
```

### 注释

| 规则 | 人话 |
|------|------|
| 永不 throw 到引擎 | 失败也是消息 |
| 超时 ≠ 用户中断 | 超时 → failed + 超时说明 |
| 头截断 | 超 `maxOutputLength` 保开头；模型与 UI 同窗 |
| note / images | 截断外附加，终态标记不丢 |
| recovery 文件 | 可选完整/头尾归档；Trace 只记路径指针 |
| 「用户所见 = 模型所见」 | 双方同一有界窗口 |

### 本节小结

读 `executeTool` 时盯住三件事：派发、signal 合并、收尾优先级。工具 bug 应在工具内修；收尾策略变更要评估所有内置 + MCP。

---

## 4. 九个内置工具详解

### 白话

产品取向：文件精确读写专用工具；Shell 兜底；命令/子 Agent 两段式后台；图像按模型能力二选一。装配入口：`environment/tools/registry.ts`。默认超时等以 `default-config` / 各工具 definition 为准（下表为官方文档量级，便于建立直觉）。

#### 文件三件套

**`read_file`**：`cat -n` 风格，`offset`/`limit` 分页；超长单行截断；二进制 NUL 拒绝并提示改用 Shell/图像工具。  
**`edit_file`**：文件须已存在；`old_string` 默认恰好一次（或 `replace_all`）；成功回显 unified diff。  
**`write_file`**：创建或覆写；按需建父目录；覆写可附小型 diff。

三者非流式最终结果、不抛异常；失败文本 + `stop_reason: failed`。相对路径相对 Workspace，也接受绝对路径。

#### 命令两件套

**`exec_command`**：`bash -lc` 跑命令；前台窗口（`yield_time_ms`，默认约 60s）内结束则带回完整输出+退出码；否则转后台返回 `process_id`。  
**`input_command`**：按 `process_id` 写 stdin、发 Ctrl-C（Windows 上退化为杀进程树）、或空轮询。

后台命令会话有上限（如 64），满时优先淘汰已退出者，否则 LRU 空闲会话。

#### Subagent 两件套

**`run_subagent`** / **`input_subagent`**：同 Workspace 子 Session；深度 1；独立 Trace；`origin` 回流；继承父审批。前台默认更长（约 300s）。后台 Subagent 上限更紧（如 8），只淘汰已完成者。

#### 图像两件套

**`read_image`**（vision）：读 URL/路径，图像进 output。  
**`describe_image`**（text-only）：转交 Project `vision_model`，文字回答即输出。  
互斥装配；常见限制 png/jpeg/gif/webp、≤5MB。

### 调用描述 `description`

命令/Subagent 类工具可在 parameters 里要求模型先写一句「本次在干什么」，供 CLI/Web 展示。`call_description: false` 时装配期从 schema 滤掉该属性（不改 YAML 原文）。文件工具不靠它——`file_path` 本身已说明用途。

### 本节小结

九工具是产品选择：更少 schema Token、更清晰的失败面。加第十个之前，先问 Skill + Shell 是否已够。

---

## 5. 审批边界

### 白话

```ts
type ApproveFn = (toolCall: OmniMessage<ToolCallPayload>) => Promise<"allow" | "deny">;
```

| 面 | 行为 |
|----|------|
| SDK | 每次 `run` 注入；未注入则引擎默认全拒绝（保守） |
| CLI | `--approve`：allow-all / deny-all / read-only / always-ask |
| Web | 同四模式，按 Session 设置；决策前可读库；人工经 API |

**Environment 不参与产品审批。** 它只在 allow 之后执行。deny 由引擎合成 aborted output，并写 `approval_decision` 进 Trace。

### 本节小结

权限 UX 在 Human（CLI/Server）；执行在 Environment；审计在 Trace。三者缺一都会让「谁批准了什么」说不清。

---

## 6. 截断与超时：模型到底看见什么

### 白话

- **超时**：工具被 abort，输出说明超时，`stop_reason` 倾向 failed（非用户 abort）。模型应改策略（缩小命令、分页读文件），而不是假设「再试同一超长命令会好」。
- **截断**：头窗 + 截断提示 +（可选）recovery 绝对路径 note。Trace 与 Web/CLI 与模型同窗；完整正文若归档，在 scratchpad，不进 Trace 正文。
- **空输出**：补 `[no output]`，避免模型以为工具没跑。

工具错误**不**触发引擎 LLM 重连——它们作为 output 反馈，由模型决定下一步。

### 本节小结

调试「模型重复跑同一命令」时，先看它是否只看见了截断头、是否拿到了 recovery 路径、是否把超时当成「再试一次就好」。

---

## 本章总结

1. **BuiltinTool** 只产 delta + ToolResult；Environment 统一成帧与收尾。  
2. **`executeTool`** 派发内置/MCP，合并超时与用户中断，错误全部消息化。  
3. **九工具 + MCP** 覆盖文件、Shell、子会话、图像；审批在引擎/Human 边界。  
4. **截断/超时/空输出** 都有明确终态，保证「可记账、可回放、模型可调整」。

下一篇：[03-agent-session-trace.md](./03-agent-session-trace.md)。
