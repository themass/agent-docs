# Claude Code：SDK ↔ CLI 整体交互与架构

> 把两份材料合成一张图：  
> **CLI**（闭源 `claude` 二进制）里跑 Agent Loop；  
> **SDK**（`claude-agent-sdk` Python）不实现 Loop，只 spawn 这个二进制并用 stdin/stdout NDJSON 驱动它。  
> SDK 细节以 [CLAUDE_AGENT_SDK_GUIDE.md](./CLAUDE_AGENT_SDK_GUIDE.md) 为准（可读源码）。  
> CLI 内部以 [CLAUDE_CODE_ARCHITECTURE_GUIDE.md](./CLAUDE_CODE_ARCHITECTURE_GUIDE.md) 为准（闭源；Loop 由 CHANGELOG、插件行为与 wire 协议反推，不是逐行源码）。

---

## 0. 一句话

同一个 `claude` 进程有两种壳：

| 壳 | 怎么启动 | 人看见什么 |
|----|----------|------------|
| 交互 TUI | 终端里直接跑 `claude` | 全屏 UI |
| SDK / headless | `--input-format stream-json --output-format stream-json` | 无 TUI，一行一个 JSON |

SDK 是第二种壳的类型化遥控器。模型调用、内置工具、权限、压缩、session 文件都在 CLI 进程里。Python 只负责：找到二进制、拼 argv、读写 JSONL、在控制面上执行 Hook / SDK MCP / `can_use_tool`。

---

## 1. 进程拓扑

```text
┌──────────────── 你的进程（Python / FastAPI / CI）────────────────┐
│  query() 或 ClaudeSDKClient                                      │
│       │                                                          │
│       ▼                                                          │
│  InternalClient ── materialize session（可选）                   │
│       │                                                          │
│       ▼                                                          │
│  Query                         控制面状态只活在这里：             │
│   · 后台读 stdout               hook_0 → Python 函数             │
│   · 分流 data / control         sdk mcp server instance          │
│   · 写 stdin                    can_use_tool 回调                │
│       │                                                          │
│  SubprocessCLITransport                                          │
└───────┼──────────────────────────────────────────────────────────┘
        │  stdin / stdout  NDJSON（同一对管道，两类帧混流）
        │  stderr 日志
        ▼
┌──────────────── claude 子进程（闭源）────────────────────────────┐
│  stream-json 入口（无 TUI）                                      │
│       │                                                          │
│       ▼                                                          │
│  Agent Loop                                                      │
│   组装 prompt → Anthropic API → tool_use → 权限/Hook → 执行工具  │
│       │              │                    │                      │
│       │              │                    ├─ 内置 Read/Bash/Grep │
│       │              │                    ├─ 外部 MCP 子进程     │
│       │              │                    ├─ Skill / Agent 子 Loop│
│       │              │                    └─ 需要 Python 时     │
│       │              │                         control_request   │
│       ▼              ▼                                          │
│  session.jsonl    Anthropic Messages API                        │
└──────────────────────────────────────────────────────────────────┘
```

CLI 找不到时 SDK 报 `CLINotFoundError`。查找顺序：wheel 里的 `_bundled/claude` → `PATH` 的 `claude` → `~/.local/bin`、`~/.npm-global/bin` 等。

子进程环境：继承当前环境，删掉 `CLAUDECODE`（避免嵌套 CLI 误判），写入 `CLAUDE_CODE_ENTRYPOINT=sdk-py` 和 SDK 版本。`ANTHROPIC_API_KEY` 由调用方放进 `options.env`，CLI 自己去调 API。SDK 不持有 HTTP 客户端。

---

## 2. 职责切分

| 能力 | SDK | CLI |
|------|:---:|:---:|
| `while` 模型 ↔ 工具循环 | | ✅ |
| 调 Anthropic API | | ✅ |
| Read / Write / Bash / Grep / Glob | | ✅ |
| 上下文压缩、CLAUDE.md、settings 合并 | | ✅ |
| session JSONL 的权威读写 | mirror | ✅ |
| spawn、argv、stdin/stdout | ✅ | 消费 |
| 把 JSON 收成 `AssistantMessage` 等 | ✅ | 只出 raw JSON |
| Python Hook 函数本体 | ✅ | 只存 `hook_0` 这类 id，到点回调 |
| `@tool` 同进程 MCP | ✅ 执行 | 发 `mcp_message` |
| 外部 MCP（stdio/SSE/HTTP） | 把配置放进 `--mcp-config` | ✅ 自己拉起 |
| `interrupt` / `set_model` | 发 control | ✅ 执行 |

---

## 3. 启动时序（`query()` 一次跑完）

`query()` 本身只有三行：默认 options、建 `InternalClient`、把 generator 转出去。真正的顺序在 `InternalClient._process_query_inner`：

| 步 | 谁 | 做什么 |
|:--:|----|--------|
| 1 | SDK | `can_use_tool` 配了字符串 prompt → 直接 `ValueError`。要审批回调，prompt 必须是 async iterable |
| 2 | SDK | 有 `can_use_tool` 时强制 `permission_prompt_tool_name="stdio"`，让 CLI 用管道问，而不是弹 TUI |
| 3 | SDK | 若配置了远程 `SessionStore`：先把 transcript materialize 到临时 `CLAUDE_CONFIG_DIR`，再 `--resume` |
| 4 | SDK | `SubprocessCLITransport.connect()` spawn |
| 5 | SDK | 从 `mcp_servers` 抽出 `type=="sdk"` 的 `instance`（Python 对象，不进 argv） |
| 6 | SDK | `Query.start()`：后台任务开始读 stdout |
| 7 | SDK → CLI | stdin：`control_request` / `initialize`（hooks、agents、skills） |
| 8 | CLI → SDK | stdout：`control_response` success。此后 CLI 才接受用户消息 |
| 9 | SDK → CLI | stdin：首条 `user` JSONL |
| 10 | CLI | **进程内**跑 Loop。SDK 不再参与「要不要再调一次模型」 |
| 11 | CLI → SDK | stdout：`assistant` / `tool` 进度 / `system` … 应用层能看到的帧 |
| 12 | CLI ↔ SDK | 穿插 control：Hook、SDK MCP、`can_use_tool`（应用层默认看不见） |
| 13 | CLI → SDK | stdout：`result`（`num_turns`、费用、`is_error`）。对 SDK 来说这是本轮结束，不管 CLI 内部打了几轮工具 |
| 14 | SDK | 字符串 prompt 路径：见到 `result` 就关 stdin |
| 15 | SDK | `query.close()` → stdin EOF，等 5s，SIGTERM，再 kill |
| 16 | SDK | **先**停子进程，**再**删 materialize 临时目录。顺序反了，CLI 还在写 transcript 时目录已经没了 |

固定 argv 前缀：

```text
claude --output-format stream-json --verbose
       …options 映射成 flag…
       --input-format stream-json
```

`--input-format stream-json` 是持续 stdin 模式。字符串 prompt 若塞进 argv，Linux 单参数约 128KiB 会 `E2BIG`；走 stdin 没有这个限制。

---

## 4. 两条平面，一根管道

stdout/stdin 上所有帧都是 NDJSON。`Query._read_messages()` 按 `type` 分流：

```text
                    stdout 一行 JSON
                           │
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
   control_response   control_request    其它
   唤醒等待中的       异步处理，不进      assistant / user /
   request_id         应用队列            result / system /
           │               │              transcript_mirror
           │               ├ hook_callback ──► Python 函数
           │               ├ can_use_tool ──► PermissionResult
           │               └ mcp_message  ──► 同进程 MCP
           │               │
           │               └── stdin 写 control_response
           ▼
     应用层 receive_messages()
     → parse_message() → 强类型 Message
```

控制帧 `continue`，不进应用队列。`transcript_mirror` 也吞掉，交给 batcher 写 `SessionStore`。只有数据帧（以及 `include_hook_events` 时的观测帧）会变成 `AssistantMessage`、`ResultMessage` 等。

未知 `type`：`parse_message` 打日志并返回 `None`，用来兼容更新的 CLI。

### 4.1 数据面（应用看得到）

SDK 写给 CLI 的用户消息：

```json
{
  "type": "user",
  "session_id": "",
  "message": {"role": "user", "content": "..."},
  "parent_tool_use_id": null
}
```

CLI 写回来的典型帧：

| type | 含义 |
|------|------|
| `assistant` | 文本、thinking，或 `tool_use` block。工具还没执行完，只是模型决定要调 |
| `result` | 本轮结束。`subtype`、`num_turns`、`total_cost_usd`、`is_error` |
| `system` | 状态、hook 观测（`hook_started` 等，需打开 `include_hook_events`） |

`tool_use` 出现在 `assistant` 内容里，不代表 Python 要自己执行 Read/Bash。执行发生在 CLI。SDK 只是把这一帧转成 `ToolUseBlock` 给调用方看。

### 4.2 控制面（应用默认看不到）

SDK → CLI（stdin，和 user 消息抢同一把写锁）：

```json
{
  "type": "control_request",
  "request_id": "req_1_abcd",
  "request": {"subtype": "initialize", "hooks": {}, "agents": null, "skills": []}
}
```

CLI → SDK 的三类请求，SDK 处理后把 `control_response` 写回 stdin：

| subtype | CLI 在等什么 | SDK 做什么 |
|---------|--------------|------------|
| `hook_callback` | Python Hook 的 allow/deny/改写 | `hook_callbacks[callback_id](...)`。函数从不序列化过去，CLI 只有 `hook_0` |
| `can_use_tool` | 这次工具批不批准 | 返回 `behavior: allow/deny` |
| `mcp_message` | JSON-RPC：`initialize` / `tools/list` / `tools/call` | 路由到 `create_sdk_mcp_server` 的 handler |

SDK 主动问 CLI 也走同一条 `_send_control_request`：写 stdin，等 stdout 上匹配 `request_id` 的 `control_response`。`interrupt`、`set_model`、`set_permission_mode`、`get_context_usage` 都是这样。

`control_cancel_request` 用来取消还在飞的控制请求。

---

## 5. 一次工具调用怎么跨过进程边界

下面是 SDK 模式下，模型要跑一条 Bash 时两边同时在干什么。CLI 内部步骤是概念模型；跨进程那几跳是 SDK 源码里的真实协议。

```text
CLI 内 Agent Loop                          Python SDK
─────────────────                          ──────────
组装 system（CLAUDE.md、skills、settings）
        │
        ▼
POST Anthropic API（tools schema）
        │
        ▼
模型返回 tool_use: Bash
        │
        ├─ stdout: assistant / tool_use ──────────► 应用看到 ToolUseBlock
        │
        ▼
权限：deny 列表 → allow 列表 → permission_mode
        │
        ├─ 需要显式批准？
        │     control_request can_use_tool ───────► can_use_tool()
        │     ◄──────── control_response ──────────
        │
        ▼
PreToolUse
  · settings/plugin 的 command hook：CLI 自己起脚本，stdin JSON，exit 2 即拒绝
  · SDK 注册的 hook：
        control_request hook_callback ───────────► await Python
        ◄──────── control_response ──────────────
        │
        ▼
执行 Bash / Read / MCP / Agent / Skill
        │
        ▼
PostToolUse（同样可能再回调 SDK）
        │
        ▼
tool_result 追加进上下文，再调 API
        │
        … 直到没有 tool_use，或 max_turns / budget
        ▼
Stop hook（command hook 可以拒绝结束，把输出喂回成下一轮 user）
        │
        ├─ 写 session.jsonl；必要时 PreCompact
        └─ stdout: result ────────────────────────► ResultMessage，SDK 视为本轮结束
```

两条权限通道不要混：

| | 何时发生 | 谁执行 |
|--|----------|--------|
| PreToolUse | 匹配上的工具都会走 | CLI 的 command hook，或 SDK 的 Python 回调 |
| `can_use_tool` | 只有权限系统决定「要问人」时 | 仅 SDK。交互 TUI 里这是弹窗；SDK 模式里弹窗被 stdio 回调替换 |

概念上的评估顺序：`disallowed_tools` → `allowed_tools`（自动放行，不从工具集删掉）→ `permission_mode` → `can_use_tool` 或交互询问 → PreToolUse 仍可 deny。

Bash 沙箱只包 Bash，不自动包 Read/Write/MCP。

---

## 6. CLI 里的 Loop（闭源侧）

SDK 的 `Query` 类名容易误导：那里的循环是 **读 stdout**，不是 `while turn < max_turns`。后者在二进制里。从协议和 CHANGELOG 能确定的行为：

```text
用户消息进入
  → system：CLAUDE.md、已启用 Skill 的 description、plugin 注入、settings
  → Messages API（带 tools schema）
  → 文本和/或 tool_use
  → 有 tool_use：权限 → PreToolUse → 执行 → PostToolUse → tool_result → 再请求
  → 停：无 tool_use，或 max_turns / max_budget_usd / task_budget
  → Stop hook（可阻止结束）
  → session.jsonl；PreCompact 可能压缩
  → SDK 模式下再发 result 帧
```

内置工具（Read、Bash、Grep…）、外部 MCP、Skill 加载、子 Agent、压缩，全部在这一侧。SDK 只透传 stdout。

子 Agent：主循环调用 Agent 工具后，运行时再开一层 loop，transcript 落在 `subagents/agent-*.jsonl`。流上能看到 `TaskStarted` / `TaskProgress` / `TaskNotification`，结束走 `SubagentStop`。CHANGELOG 记载嵌套最深约 5 层。`AgentDefinition` 不进 argv，只在 `initialize` 里交给 CLI。

三种入口共享这个 Loop，差在 I/O：

| 模式 | 入口 | Loop |
|------|------|------|
| 交互 TUI | `claude` | 同一套，结果画到终端 |
| Headless | `claude -p "..."` | 同一套，适合短脚本 |
| SDK | stream-json 双向 | 同一套，结果变成 JSONL |

---

## 7. 配置从 Python 到 CLI 的三条路

`ClaudeAgentOptions` 不是整包 JSON 丢给子进程。字段分四类：

| 去向 | 例子 | 机制 |
|------|------|------|
| argv | `model`、`max_turns`、`permission_mode`、`resume`、`allowedTools` | `_build_command()` |
| 环境 | `ANTHROPIC_API_KEY`、materialize 后的 `CLAUDE_CONFIG_DIR` | `open_process(env=)` |
| initialize | `hooks`、`agents`、`skills` | 第一条 control，在 user 消息之前 |
| 留在 SDK | `can_use_tool`、SDK MCP 的 `instance`、`session_store`、自定义 `transport` | CLI 只看到 id 或完全看不到对象 |

`skills="all"` 时 SDK 会把 `Skill` 加进 `allowedTools`，并默认加载 user + project settings。外部 MCP 配置去掉 `instance` 后放进 `--mcp-config`；CLI 自己起那些子进程。SDK MCP 的 server 对象留在 `Query.sdk_mcp_servers`，工具名在模型侧是 `mcp__{server}__{tool}`。

项目里的 plugin、`.claude/settings.json`、command hook，不经过 SDK 对象。CLI 按自己的配置层级加载（managed → user → project → local）。SDK 只是多挂了一批「回调 id」。

---

## 8. 两种 SDK 会话

底层都是 `InternalClient` + `Query` + `SubprocessCLITransport`。`Query` 在 SDK 里始终是 streaming 模式（先读 stdout，再握手，再写 user）。

| | `query()` | `ClaudeSDKClient` |
|--|-----------|-------------------|
| 进程寿命 | 一次 generator，见到 result 就拆 | `connect()` 到 `disconnect()` |
| 后续用户消息 | 没有 | `client.query(text)` 再写一条 user JSONL |
| `session_id` | 首条常常是 `""`，由 CLI 分配 | 多轮应传同一个 id |
| 动态控制 | 基本没有 | `interrupt` / `set_model` / `set_permission_mode` / `get_context_usage` |

`connect()` 之后读循环绑在当前 anyio 上下文上，不能把同一个 client 拿到另一个 TaskGroup 里复用。

多轮时 CLI 里的 Loop 照旧：每一条 user 是新的一轮，上下文、压缩、session 文件仍由 CLI 持有。SDK 不拼接历史消息去调 API。

---

## 9. Session：权威在 CLI，SDK 只做搬运

```text
远程 Store（Redis/S3…）
    │  resume 前
    ▼
materialize_resume_session
    把 transcript 写成临时目录（布局同 ~/.claude/projects/...）
    CLAUDE_CONFIG_DIR=该目录
    CLI --resume <session_id>
    │
    ▼
CLI 读写自己的 session.jsonl     ← 权威
    │  运行中，若开了 --session-mirror
    ▼
stdout: transcript_mirror
    → SDK batcher → session_store.append
    │
    ▼
子进程退出后才 cleanup 临时目录
```

Mirror 不是记忆系统，也不做压缩。压缩是 CLI 的 PreCompact。Mirror 只是把 CLI 已经写下的 transcript 抄一份到远程 Store，方便下次再 materialize。

---

## 10. 关掉与出错

正常结束：`result` → flush mirror → 关 stdin → 等 CLI 自己退出。

异常：

| 现象 | SDK 行为 |
|------|----------|
| 找不到二进制 | `CLINotFoundError` |
| 没 connect 就写、或进程已死 | `CLIConnectionError` |
| stdout 一行拼不出 JSON，或超过 `max_buffer_size`（默认 1MB） | `CLIJSONDecodeError` |
| CLI 非零退出 | `ProcessError` |
| 先发了 `result.is_error=true` 再故意非零退出 | 用 CLI 已给出的错误文本替换笼统的 `ProcessError`，和 TypeScript SDK 的 `lastErrorResultText` 对齐 |

父进程崩溃时，模块级 `atexit` 会杀掉仍登记着的 CLI 子进程，避免孤儿 `claude`。

单元测试 mock `Transport`，不 spawn。协议行为以 e2e（真 CLI + API key）为准。

---

## 11. 反向嵌套：CLI 的 Hook 再拉起 SDK

插件 `security-guidance` 的 Hook 脚本跑在 **CLI 子进程之外的又一个进程**里。它要用模型看 diff 时，不能在 Hook 里再实现一套 Loop，而是 `from claude_agent_sdk import query`，于是：

```text
外层 claude（用户或上一次 SDK）
  └─ command hook 进程
        └─ claude_agent_sdk.query()
              └─ 内层 claude --input-format stream-json
                    └─ 又一套 Agent Loop
```

内层必须用 async iterable prompt，才能强制 stream-json，避开 argv 长度限制。环境上要清掉外层的 OAuth token 和 CCR 的 websocket fd，否则内层 `initialize` 会超时或 401。费用读内层 `ResultMessage.total_cost_usd`。

这是唯一一条「CLI → SDK → 再 spawn CLI」的实现级样本。它说明 SDK 没有私有运行时：内层和外层是同一个二进制。

另一类「看起来像外层 Loop」的东西是 Stop hook（例如 ralph-wiggum）：CLI 已经打算结束，hook 读 transcript，把上一轮 assistant 输出当成下一轮 user 塞回去。那是用户态挂钩，不是 SDK，也不是二进制里的 `max_turns` 循环。

---

## 12. 证据边界

| 说法 | 依据 |
|------|------|
| spawn 参数、initialize、control 三分流、Hook id、SDK MCP 手写 JSON-RPC、清理顺序 | Python SDK 源码 |
| 数据帧字段（`user` / `assistant` / `result`） | SDK 写出的 JSON 与 `parse_message` |
| CLI 内 prompt 组装、工具执行、压缩、子 Agent transcript 路径 | 闭源行为模型：CHANGELOG、插件、官方 settings/hook 示例。公开的 `anthropics/claude-code` 仓库没有 Loop 的 TypeScript |
| `while (turn < maxTurns)` 的具体函数名、队列实现 | **没有**。不要把 SDK 的 `Query._read_messages` 当成它 |

TypeScript Agent SDK 走同一套 CLI wire，差别在语言绑定，不在 Loop。

---

## 阅读顺序

1. 本文：进程、时序、一次工具调用的跨进程路径。  
2. [CLAUDE_AGENT_SDK_GUIDE.md](./CLAUDE_AGENT_SDK_GUIDE.md) §4–§7：协议帧和 `Query` / Transport 源码。  
3. [CLAUDE_CODE_ARCHITECTURE_GUIDE.md](./CLAUDE_CODE_ARCHITECTURE_GUIDE.md) §2、§5、§7、§8：闭源 Loop、Hook 事件、子 Agent、权限。  
4. [CLAUDE_AGENT_SDK_ANALYSIS_SUMMARY.md](./CLAUDE_AGENT_SDK_ANALYSIS_SUMMARY.md)：和 OpenAI Agents SDK 的对照（Loop 在 Python 里 vs 在 CLI 里）。
