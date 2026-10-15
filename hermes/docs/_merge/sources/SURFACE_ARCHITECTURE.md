# Hermes 多 Surface 架构与流式推理

> **文档状态**：Canonical（v0.18+ 新增）  
> **Hermes 版本锚点**：`0.19.0`（`v2026.7.20`）· **核对**：2026-07-22  
> **HEAD 领先 tag**：主题 / Widget / Desktop SSH 等见 [VERSION_HISTORY.md](VERSION_HISTORY.md)「未发版」  
> **关联**：[ARCHITECTURE.md](ARCHITECTURE.md) §11、[WORKSPACE_VS_WEBUI.md](WORKSPACE_VS_WEBUI.md)、[CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md)

---

## 1. 为何需要本篇

`ARCHITECTURE.md` 以 **Agent 内核**（`run_agent` → `conversation_loop` → `tools`）为主轴，写于 v0.17 时代。  
v0.18–v0.19 起，Hermes 在 **呈现层** 发生结构升级：

| 变化 | 影响 |
|------|------|
| **四 Surface 并列** | CLI、Ink TUI、Electron Desktop、WebUI/Dashboard 共享同一 Gateway 事件总线 |
| **推理双流** | `thinking.delta`（等待态）与 `reasoning.delta`（真实推理）分离 |
| **思考回写** | 流式 reasoning 在 turn 结束时写入 transcript 的 `thinking` 字段 |
| **跨端 Skin** | 一份 YAML 同时主题化 CLI / TUI / Desktop |
| **TUI Widget 平台** | Registry 驱动的可插拔 overlay（modal + ambient） |
| **Desktop SSH** | 第三种连接模式：经 SSH 连远程 `hermes serve` |

读 v0.17 文档时若找不到上述概念，以本篇为准。

---

## 2. 四 Surface 逻辑分层

```text
                    ┌─────────────────────────────────────┐
                    │         AIAgent (run_agent)          │
                    │  conversation_loop · tools · memory  │
                    └─────────────────┬───────────────────┘
                                      │ callbacks
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
    ┌─────▼─────┐              ┌──────▼──────┐            ┌───────▼───────┐
    │  cli.py   │              │ tui_gateway │            │ web_server.py │
    │ HermesCLI │              │  server.py  │            │  (Dashboard)  │
    └─────┬─────┘              └──────┬──────┘            └───────┬───────┘
          │                           │                           │
    终端 Rich/                   ui-tui (Ink)              hermes-webui (SPA)
    prompt_toolkit              apps/desktop (Electron)
```

| Surface | 源码根 | 用户入口 | 权威职责 |
|---------|--------|----------|----------|
| **CLI** | `cli.py` | `hermes` / `hermes chat` | 终端 Rich 输出、reasoning box、流式 partial-line flush |
| **TUI** | `ui-tui/` | `hermes --tui` | Ink React 应用；`turnController` 管理 segment / thinking |
| **Desktop** | `apps/desktop/` | Hermes Desktop.app | Electron 壳；`use-message-stream` 消费 Gateway WS |
| **WebUI** | `hermes-webui/`（兄弟仓） | 浏览器 Dashboard | Transparent Stream / Worklog；与 Desktop 共享 WS 协议子集 |
| **桥接层** | `tui_gateway/` | `hermes dashboard --tui` | WebSocket 事件派发、skin watcher、session 状态 |

**设计不变量**：Agent 行为只在 `AIAgent` 实现一次；各 Surface 通过 **callback → Gateway 事件 → UI reducer** 渲染，不在 React/Ink 里重写 tool loop。

---

## 3. Gateway 事件总线（Surface 共用协议）

`tui_gateway/server.py` 的 `_agent_cbs(sid)` 把 Agent callback 映射为 WS 事件：

| Agent callback | WS 事件 | 载荷含义 |
|----------------|---------|----------|
| `thinking_callback` | `thinking.delta` | **等待态**文案（spinner 表情 + 动词），非模型推理 |
| `reasoning_callback` | `reasoning.delta` | **真实推理 token** 流（`reasoning_content` / `reasoning`） |
| `stream_delta_callback` | `message.delta` | 助手正文 token |
| `tool_*_callback` | `tool.start` / `tool.complete` / … | 工具生命周期 |
| — | `message.start` / `message.complete` | Turn 边界 |
| — | `skin.changed` | 主题热更新（见 §5） |

TUI 与 Desktop 均订阅同一事件集（`gatewayTypes.ts` / `gateway-event.ts`）。  
**不要**把 `thinking.delta` 当推理内容展示——Desktop 刻意忽略该事件，避免与 loading 指示重复。

---

## 4. 推理流式与「思考回写」

### 4.1 端到端路径

```text
Provider SSE chunk
  → agent/chat_completion_helpers.py  (优先解析 reasoning delta)
  → run_agent._fire_reasoning_delta()
  → reasoning_callback
  → tui_gateway _emit("reasoning.delta")
  → UI: recordReasoningDelta / appendReasoningDelta
  → turn 结束: msg.thinking 写入历史
```

Provider 层（`chat_completion_helpers.py`）在 content 之前处理 reasoning：

```python
reasoning_text = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
if reasoning_text:
    agent._fire_reasoning_delta(reasoning_text)
```

### 4.2 TUI 回写（`ui-tui/src/app/turnController.ts`）

- `recordReasoningDelta(text)`：累积 `reasoningText` / `activeReasoningText`
- `syncReasoningSegment()`：把当前推理写入 segment 消息的 `thinking` 字段（原地更新，非每 token 新建行）
- `message.complete` 后：流过的 reasoning 作为 **completed thinking panel** 留在 transcript（见 `createGatewayEventHandler.test.ts`）

### 4.3 Desktop 回写（`apps/desktop/.../use-message-stream/index.ts`）

- `appendReasoningDelta(sessionId, delta)`：写入 message parts 的 `reasoning` part
- `queueDelta` 批处理 + `flushQueuedDeltas`：工具事件前 flush，保证顺序

### 4.4 CLI 展示（`cli.py`）

- `display.show_reasoning`（默认 `true`）：开启 `_stream_reasoning_delta`
- 首个 reasoning token 打开 **Reasoning box**；**80 字符**强制 flush（无换行也先画）
- 正文 response box 沿用同样 partial-line flush（TTFT 感知优化）

### 4.5 API 回合-trip（多轮 tool call）

对 Moonshot / DeepSeek 等需要 `reasoning_content` 的 provider，`conversation_loop.py` 在下一轮 API 前通过 `_copy_reasoning_content_for_api` 把 thinking 写回 message——否则多轮 tool 链断裂。

### 4.6 配置键

| 键 | 默认 | 说明 |
|----|------|------|
| `display.show_reasoning` | `true` | 关闭则 TUI/Desktop 不展示推理（verbose reasoning 仍可走 `reasoning.delta` + `verbose: true`） |
| `display.reasoning_full` | `false` | CLI 结束后是否展开完整 reasoning recap |

### 4.7 「首包快」指什么

不是模型更快，而是 **感知 TTFT** 优化：

1. Reasoning token 先于正文到达并立即渲染  
2. CLI/TUI 80 字符 partial flush  
3. `_emit_wait_notice` → `thinking.delta` 在 provider 慢时更新状态行  
4. CLI idle 时后台 pre-import `run_agent` + `openai`（`cli.py` ~13139 行）  
5. Codex stream TTFB 检测：超时无首 event 则 kill 连接触发重试  

---

## 5. 跨 Surface 主题（Skin）系统

### 5.1 数据模型

- 皮肤文件：`~/.hermes/skins/<name>.yaml`（或 profile 对应 home）
- 解析：`hermes_cli/skin_engine.py` → `load_skin()`
- 激活：`display.skin` in `config.yaml` 或 `hermes config set display.skin <name>`
- 细调：`hermes skin set <token> <#rrggbb>`（`hermes_cli/skin_cmd.py`）——只改一个颜色，内置皮肤会 fork 为 `<name>-custom`

### 5.2 元素 token（v0.19+ HEAD）

| Token | 用途 |
|-------|------|
| `ui_accent` | 主强调色 |
| `ui_tool` | 工具块 |
| `ui_thinking` | 推理/思考文字 |
| `code_syntax_*` | 代码高亮.palette |

TUI：`ui-tui/src/theme.ts` 的 `fromSkin()`；Desktop：`apps/shared/src/skin.ts`。

### 5.3 热更新（Skin Watcher）

`tui_gateway/server.py::_ensure_skin_watcher()`：

- Gateway ready 时启动 daemon 线程，**0.5s** 轮询 config / skin mtime
- 变化时广播 `skin.changed` → 各 Surface 无需重启即重绘
- TUI 用 **OSC 11** 自绘终端背景（`feat(themes): TUI paints its own background`）

Agent 可通过 `skills/hermes-themes/SKILL.md` 编写并激活皮肤。

---

## 6. TUI Widget 平台

### 6.1 架构

```text
ui-tui/src/sdk/
  registry.ts      defineWidgetApp() → Map<id, WidgetApp>  （catalog = slash 补全来源）
  types.ts         WidgetApp 契约：init / reduce / render；mode: modal | ambient
  host.ts          openWidget / updateWidget
  userWidgets.ts   扫描 ~/.hermes/tui-widgets/*.mjs，fs.watch 热加载
  apps/            内置参考实现（weather, ticker, gridTest, …）
```

**契约要点**（`types.ts`）：

- `modal`：独占输入，阻塞 composer（默认）
- `ambient`：dock 区常驻，`zone` 指定位置；再次 launch 同 id 则 toggle 关闭
- Registry **即 catalog**：slash 命令与 `/` 补全从 `listWidgetApps()` 派生，无硬编码

### 6.2 用户扩展

1. 在 `$HERMES_HOME/tui-widgets/` 放置 `<name>.mjs`
2. `export default function register(sdk) { sdk.defineWidgetApp({...}) }`
3. 文件保存后自动热加载；错误只 log，不崩 TUI

信任模型同 `~/.hermes/plugins/`：用户文件以 TUI 进程权限执行。

---

## 7. Desktop 远程后端（Desktop SSH）

第三种连接模式，与 Local / Cloud 并列：

```text
Desktop SSH transport
  → 远程 spawn: hermes serve --ssh-session-token-file <path>
  → main.py 读取并 unlink token
  → web_server._apply_ssh_session_token()
  → WebSocket 等同远程 Dashboard backend
```

| 模块 | 职责 |
|------|------|
| `apps/desktop/` SSH 设置 UI | 连接模型、软切换 gateway |
| `hermes_cli/windows_ssh_runtime.py` | Windows 信任边界（ACL、spawn nonce） |
| `website/docs/user-guide/desktop.md` | OAuth vs Basic Auth 远程指引 |

---

## 8. 压缩与 Route 作用域（v0.19+ 稳定性）

`model.context_length` 描述**配置默认模型**的窗口。切换 `/model` 或 fallback 后若 pin 未清除，压缩阈值会算错并触发 **stale-budget retry loop**。

| 模块 | 职责 |
|------|------|
| `hermes_cli/route_identity.py` | `normalize_route_base_url()`、`should_clear_context_pin()` |
| `agent/agent_init.py` | 启动时 route-scope context pin |
| `agent/context_compressor.py` | handoff summary 作为 protected head；压缩后注入 MEMORY.md 权威提示 |

详见 `agent/conversation_loop.py` 与 `tests/run_agent/test_switch_model_context.py`。

---

## 9. 模块地图（Surface 专用）

### 9.1 `ui-tui/`

| 路径 | 说明 |
|------|------|
| `src/app/createGatewayEventHandler.ts` | WS 事件 → `turnController` |
| `src/app/turnController.ts` | Segment、reasoning、tool trail |
| `src/components/thinking.tsx` | Thinking 面板 UI |
| `src/sdk/` | Widget SDK |
| `packages/hermes-ink/` | Ink fork |

### 9.2 `tui_gateway/`

| 路径 | 说明 |
|------|------|
| `server.py` | Session、`_agent_cbs`、skin watcher |
| `ws.py` | WebSocket 协议 |
| `entry.py` | TUI 进程入口 |

### 9.3 `apps/desktop/`

| 路径 | 说明 |
|------|------|
| `electron/main.ts` | 进程生命周期、SSH |
| `src/app/session/hooks/use-message-stream/` | 流式消息状态机 |
| `src/store/` | Zustand stores（projects、connection） |
| `AGENTS.md` | Desktop 工程准则（state 权威、切换语义） |

### 9.4 `hermes_cli/`（Surface 相关）

| 路径 | 说明 |
|------|------|
| `skin_engine.py` / `skin_cmd.py` | 主题 |
| `web_server.py` | Dashboard API + WS |
| `windows_ssh_runtime.py` | Desktop SSH Windows 端 |

---

## 10. 与其它文档的关系

| 主题 | Canonical | 本篇覆盖 |
|------|-----------|----------|
| Agent 主循环 | `AGENT_LOOP_ARCHITECTURE.md` | 仅 callback 边界 |
| Gateway IM 平台 | `CLI_GATEWAY_SYSTEM.md` | 不重复 |
| CLI slash / 配置 | `CLI_GATEWAY_SYSTEM.md` | Skin、reasoning 配置见本文 |
| WebUI 性能 | `WORKSPACE_VS_WEBUI.md` | 选型，非实现 |
| 计费 TUI | `billing-lifecycle.md` | 互补 |

---

## 11. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-22 | 初版：四 Surface、推理回写、Skin、Widget、Desktop SSH、route-scoped compression |
