# Plugins 插件系统（Canonical）

<!-- legacy-review:start -->
> **2026-10-15 校订导航**：Hook、工具扩展和记忆 Provider 不是同一个扩展点。\
> **核对范围**：修正 pre_llm_call sidecar 的持久化说明；静态 Hook 表以源码 VALID_HOOKS 为准。\
> **适用基线**：本地源码 `60d00c5633ad`；不是最新发布版本声明。原稿版本、行号、性能数字与长代码块若未在校订范围内，仍按历史示例阅读。
> **先读当前结论**：[当前实现导读](CURRENT_IMPLEMENTATION.md#current-context) · **现行分卷**：[05-capabilities-extensions.md](../../volumes/05-capabilities-extensions.md) · [具体改动与未验证项](REVIEW_AND_CHANGES.md) · [返回全目录](README.md)

<!-- legacy-review:end -->
<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 体系设计与架构](#section-1)
  - [1.1 一句话](#section-1-1)
  - [1.2 设计原则](#section-1-2)
  - [1.3 插件种类（`plugin.yaml` → `kind`）](#section-1-3)
  - [1.4 能力面（`PluginContext.register_*`）](#section-1-4)
- [2. 插件开发流程](#section-2)
  - [2.1 最小骨架（standalone）](#section-2-1)
  - [2.2 开发步骤](#section-2-2)
  - [2.3 常见模式](#section-2-3)
  - [2.4 不要做的事](#section-2-4)
- [3. 插件配置流程](#section-3)
  - [3.1 配置落点](#section-3-1)
  - [3.2 配置 → 生效顺序](#section-3-2)
  - [3.3 解析键（`key`）](#section-3-3)
- [4. 插件加载流程](#section-4)
  - [4.1 谁触发](#section-4-1)
  - [4.2 发现扫描（四源）](#section-4-2)
  - [4.3 启用判定 → `_load_plugin`](#section-4-3)
  - [4.4 加载时序图](#section-4-4)
- [5. 插件执行流程](#section-5)
  - [5.1 总路径](#section-5-1)
  - [5.2 一轮对话里典型 Hook 序（示意）](#section-5-2)
  - [5.3 `pre_tool_call` → 执行/HITL](#section-5-3)
  - [5.4 Tool 插件执行](#section-5-4)
  - [5.5 与线程模型的关系](#section-5-5)
- [6. Hook / 注册能力速查](#section-6)
  - [6.1 VALID_HOOKS（摘要）](#section-6-1)
  - [6.2 为何不改 System Prompt](#section-6-2)
- [7. Hook 生命周期全表：触发点、参数与可改变的行为](#section-7)
  - [7.1 按生命周期总览](#section-7-1)
  - [7.2 逐个：作用 · 返回值 · 挂载点](#section-7-2)
  - [7.3 与 Agent Loop 的对应](#section-7-3)
  - [7.4 易混的三套「钩子」](#section-7-4)
- [8. 源码锚点](#section-8)
- [9. 变更说明（相对旧稿）](#section-9)
<!-- visible-toc:end -->




> **原稿文档状态（历史标签）**: Canonical · **Hermes**: 0.19.0 · **核对**: 2026-08-03 · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)\
> **源码**: `hermes_cli/plugins.py`（`PluginManager` / `PluginContext` / hooks）\
> **相关**: [HITL_APPROVAL_FLOW.md](HITL_APPROVAL_FLOW.md)（`pre_tool_call` → approve）· [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) · [CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md) · [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md)（exclusive memory provider）

---

<a id="1-体系设计与架构"></a>
<a id="section-1"></a>
## 1. 体系设计与架构

<a id="11-一句话"></a>
<a id="section-1-1"></a>
### 1.1 一句话

**插件是进程级全局扩展（微内核 + AOP），不是独立 Agent。**  
`PluginManager` 单例挂在 CLI/Gateway 进程上；主/子 `AIAgent` 在固定生命周期点 `invoke_hook` / `invoke_middleware`，插件被动响应。

```text
┌────────────────── Hermes 进程（CLI 或 Gateway）──────────────────┐
│  PluginManager（全局单例）                                         │
│    hooks / middleware / tools / slash / platforms / …              │
│                         │ invoke_hook / invoke_middleware          │
│              ┌──────────┼──────────┐                               │
│              ▼          ▼          ▼                               │
│         主 AIAgent   子 Agent A  子 Agent B                         │
└────────────────────────────────────────────────────────────────────┘
```

| | Agent | Plugin |
|--|-------|--------|
| LLM 循环 | 有 | 无（挂在宿主循环上） |
| 决策 | 自主 tool/推理 | 观察 / 拦截 / 注入 / 注册能力 |
| 身份 | `session_id` + messages | 无独立会话 |
| 数量 | 可多实例 | Manager 单例；各插件模块一份 |

<a id="12-设计原则"></a>
<a id="section-1-2"></a>
### 1.2 设计原则

| 原则 | 含义 |
|------|------|
| **Opt-in** | 默认不跑用户/第三方 standalone；显式 `plugins.enabled` |
| **四源发现** | bundled / `~/.hermes/plugins` / 项目 `.hermes/plugins` / pip entry-point |
| **kind 分流** | `standalone` / `backend` / `platform` / `exclusive` / `model-provider` 加载策略不同 |
| **Prompt-cache 友好** | `pre_llm_call` 注入 **user 侧**上下文，不改 `_cached_system_prompt` |
| **Fail-closed 策略** | `pre_tool_call` 的 `approve` 闸门失败 → block（见 HITL） |
| **子 Agent 安全** | 部分 hook（如 `subagent_stop`）回到父线程串行，避免插件作者扛并发 |

<a id="13-插件种类pluginyaml-→-kind"></a>
<a id="section-1-3"></a>
### 1.3 插件种类（`plugin.yaml` → `kind`）

| kind | 谁启用 | 加载行为 |
|------|--------|----------|
| **standalone**（默认） | `plugins.enabled` | 显式启用才 `import` + `register()` |
| **backend** | bundled 自动；用户装的仍要 enabled | 如 `image_gen/openai` |
| **platform** | bundled **延迟**注册；用户装的要 enabled | Gateway 首次用该平台才 import |
| **exclusive** | `<category>.provider`（如 memory） | 通用扫描只记清单，由分类 discovery 加载 |
| **model-provider** | providers 自己的 discovery | 通用扫描不二次 import |

<a id="14-能力面plugincontextregister_"></a>
<a id="section-1-4"></a>
### 1.4 能力面（`PluginContext.register_*`）

插件在 `register(ctx)` 里声明自己要挂什么：

- **Hooks** — 生命周期观察/拦截（§6）
- **Middleware** — 可改写请求/包装执行（与 observer hook 分开）
- **Tools** — 进 tool registry，模型可调
- **Slash / CLI commands** — `/foo` 或 `hermes foo`
- **Providers** — image/video/tts/web/browser/secret/…
- **Platform** — Gateway 适配器
- **Context engine** — 替换压缩引擎（全局一个）
- **Skills** — `plugin:name` 显式 `skill_view`（不进 system skills 索引）
- **`ctx.llm`** — 宿主模型，无需自带 Key（能力可用 `plugins.entries.<id>.llm.*` 收紧）

Memory 等 exclusive 后端走 **分类插件树**（`plugins/memory/…`），不靠本 Manager 的 opt-in 列表单独 import。

---

<a id="2-插件开发流程"></a>
<a id="section-2"></a>
## 2. 插件开发流程

<a id="21-最小骨架standalone"></a>
<a id="section-2-1"></a>
### 2.1 最小骨架（standalone）

```text
my-plugin/
  plugin.yaml      # 清单（必填）
  __init__.py      # 导出 register(ctx)
  my_plugin.py     # 可选：实现
```

**`plugin.yaml`（例）:**

```yaml
name: disk-cleanup
version: "2.0.0"
description: Clean ephemeral session files via hooks
author: hermes
kind: standalone          # 可省略，默认 standalone
provides_hooks:           # 清单声明（文档/introspection）；真正生效靠 register()
  - post_tool_call
  - on_session_end
```

仓库内真实插件可能用 `hooks:` 等别名字段作说明；**解析器认 `provides_hooks` / `provides_tools` 等**（见 `_parse_manifest`）。**运行时以 `register(ctx)` 注册为准。**
**`__init__.py`:**

```python
def register(ctx):
    def on_end(**kwargs):
        # kwargs 随 hook 变化；返回值多数 hook 可忽略
        ...
    ctx.register_hook("on_session_end", on_end)
    # 或: ctx.register_tool(...); ctx.register_command(...)
```

<a id="22-开发步骤"></a>
<a id="section-2-2"></a>
### 2.2 开发步骤

```text
1. 选 kind / 能力：只要 hook？还要 tool / slash / platform？
2. 写 plugin.yaml + register(ctx)
3. 放到发现路径之一：
     · 开发：仓库 plugins/<name>/ 或 ~/.hermes/plugins/<name>/
     · 发布：pip 包 + entry-point 组 hermes_agent.plugins
4. 配置启用（§3）：hermes plugins enable <key>
5. 重启进程或 discover_plugins(force=True)（长驻 Gateway 需 force/重启）
6. hermes plugins list / 打日志验证 hooks 注册
7. 用最小场景测执行路径（§5）
```

<a id="23-常见模式"></a>
<a id="section-2-3"></a>
### 2.3 常见模式

| 目标 | 做法 |
|------|------|
| 每轮给模型加 RAG 片段 | `pre_llm_call` → `{"context": "..."}` |
| 禁止或升级审批某工具 | `pre_tool_call` → `block` / `approve` |
| 改模型可见的 tool 结果 | `transform_tool_result`（first non-empty wins） |
| 新 IM 平台 | `kind: platform` + `ctx.register_platform` |
| 换记忆后端 | `kind: exclusive` + memory 分类 discovery + `memory.provider` |

<a id="24-不要做的事"></a>
<a id="section-2-4"></a>
### 2.4 不要做的事

- 在 hook 里改 system prompt 缓存字节（破坏 prefix cache；应用 `pre_llm_call`）。
- 假设 hook 在「主线程」——CLI 上常在 **Agent 线程**；Gateway 上常在 **executor 工作线程**（见 CLI_GATEWAY）。
- 覆盖核心 tool 名除非显式 `plugins.entries.<id>.allow_tool_override`。

---

<a id="3-插件配置流程"></a>
<a id="section-3"></a>
## 3. 插件配置流程

<a id="31-配置落点"></a>
<a id="section-3-1"></a>
### 3.1 配置落点

```yaml
# ~/.hermes/config.yaml（或当前 profile 覆盖）

plugins:
  enabled:                    # 白名单；缺省/空 = standalone 全不启用
    - disk-cleanup
    - langfuse
  disabled:                   # 显式禁用（优先于 enabled）
    - some-buggy-plugin
  entries:
    disk-cleanup:             # 每插件私有配置（可选）
      # ...
    my-plugin:
      llm:
        # 收紧 ctx.llm 能力
      allow_tool_override: false

# exclusive 示例（不靠 plugins.enabled import）
memory:
  provider: mem0              # 或 honcho / …

# backend 选用（bundled backend 已加载时由工具层选 provider）
# image_gen:
#   provider: openai
```

环境：

| 变量 | 作用 |
|------|------|
| `HERMES_SAFE_MODE=1` | **跳过**全部插件发现 |
| `HERMES_ENABLE_PROJECT_PLUGINS=1` | 允许扫描 `./.hermes/plugins` |

<a id="32-配置-→-生效顺序"></a>
<a id="section-3-2"></a>
### 3.2 配置 → 生效顺序

```text
编辑 config.yaml / hermes plugins enable <key>
  → 新进程：启动时 discover_and_load 读最新配置
  → 已运行 Gateway：需 restart 或 discover_plugins(force=True)
  → disabled 命中 → 记入 _plugins 但 enabled=False，不 import
  → exclusive / model-provider → 清单可见，加载交给分类系统
```

CLI：`hermes plugins list|enable|disable|…`（以 `hermes_cli` 实际子命令为准）。

<a id="33-解析键key"></a>
<a id="section-3-3"></a>
### 3.3 解析键（`key`）

- 扁平：`plugins/disk-cleanup/` → key `disk-cleanup`
- 分类：`plugins/image_gen/openai/` → key `image_gen/openai`  
`plugins.enabled` 用 **key**（兼容旧 bare `name`）。

---

<a id="4-插件加载流程"></a>
<a id="section-4"></a>
## 4. 插件加载流程

<a id="41-谁触发"></a>
<a id="section-4-1"></a>
### 4.1 谁触发

```text
CLI / Gateway / 其它入口
  → discover_plugins() 或 get_plugin_manager().discover_and_load()
  → 幂等：已 _discovered 且非 force 则直接返回
```

<a id="42-发现扫描四源"></a>
<a id="section-4-2"></a>
### 4.2 发现扫描（四源）

```text
1. bundled: <repo>/plugins/          （跳过顶层 memory/ context_engine/ model-providers/；
                                       platforms/ 单独再扫一层）
2. user:    ~/.hermes/plugins/
3. project: ./.hermes/plugins/       （需 HERMES_ENABLE_PROJECT_PLUGINS）
4. pip:     entry_points hermes_agent.plugins

同 key 后写覆盖先写：project > user > bundled（实现上 winners 字典后扫描覆盖）
```

清单要求：目录内有 **`plugin.yaml`**，且模块提供 **`register(ctx)`**。

<a id="43-启用判定-→-_load_plugin"></a>
<a id="section-4-3"></a>
### 4.3 启用判定 → `_load_plugin`

```text
for each winner manifest:
  if in disabled → skip (enabled=False)
  if kind == exclusive → 只记录，不 load
  if kind == model-provider → 只记录，providers 自己 load
  if bundled && backend → _load_plugin
  if bundled && platform → _register_deferred_platform（懒 import）
  else if key in plugins.enabled → _load_plugin
  else → skip (not enabled)
```

**`_load_plugin` 内部（概念）:**

```text
importlib 加载模块
  → PluginContext(manifest, manager)
  → module.register(ctx)
  → ctx.register_* 写入 manager._hooks / _middleware / tool registry / …
  → LoadedPlugin.enabled = True
```

失败：写入 `LoadedPlugin.error`，尽量不拖垮整个发现（具体以源码 try/except 为准）。

<a id="44-加载时序图"></a>
<a id="section-4-4"></a>
### 4.4 加载时序图

```mermaid
flowchart TD
    Start[discover_and_load] --> Safe{HERMES_SAFE_MODE?}
    Safe -->|yes| Empty[标记 discovered 跳过]
    Safe -->|no| Scan[扫描四源 manifests]
    Scan --> Dedup[按 key 去重 winners]
    Dedup --> Gate{disabled / kind / enabled?}
    Gate -->|skip| Rec[记录 LoadedPlugin enabled false]
    Gate -->|bundled platform| Defer[deferred platform registry]
    Gate -->|load| Import[import + register ctx]
    Import --> Reg[hooks tools commands providers]
```

---

<a id="5-插件执行流程"></a>
<a id="section-5"></a>
## 5. 插件执行流程

插件 **没有自己的 run loop**。宿主在固定点调用 Manager。

<a id="51-总路径"></a>
<a id="section-5-1"></a>
### 5.1 总路径

```text
Agent / Gateway / ToolExecutor 事件
  → invoke_hook("name", **kwargs)
  或 invoke_middleware("kind", **kwargs)
  或 已注册 tool handler（模型 tool_call → registry）
  或 slash / CLI 分发到 plugin command
```

<a id="52-一轮对话里典型-hook-序示意"></a>
<a id="section-5-2"></a>
### 5.2 一轮对话里典型 Hook 序（示意）

```text
on_session_start（会话首次）
  → （用户消息）
  → pre_llm_call          # 可返回 context → 拼进本轮 API user 侧；不覆盖原始 content，但 api_content sidecar 可写入 SessionDB
  → pre_api_request
  → （LLM）
  → post_api_request / api_request_error
  → post_llm_call
  → transform_llm_output  # 可选改最终文本
  → 若有 tool_calls:
       pre_tool_call      # block | approve → HITL | 放行
       （middleware / handler）
       transform_tool_result / transform_terminal_output
       post_tool_call
  → pre_verify（停前校验，可 continue）
  → …
on_session_end / on_session_finalize
```

Gateway 入站额外：`pre_gateway_dispatch`（`skip` / `rewrite` / `allow`）在鉴权与 agent 之前。

审批：`pre_approval_request` / `post_approval_response` **只观察**；要拦工具用 `pre_tool_call`。

<a id="53-pre_tool_call-→-执行hitl"></a>
<a id="section-5-3"></a>
### 5.3 `pre_tool_call` → 执行/HITL

```text
tool_executor._authorized_dispatch
  → resolve_pre_tool_block(...)
       · action=block  → 直接 error JSON，handler 不跑
       · action=approve → request_tool_approval → 与危险 shell 同一闸门
       · 其它 → 继续 handler
```

详见 [HITL_APPROVAL_FLOW.md](HITL_APPROVAL_FLOW.md) §5.0 / §10。

<a id="54-tool-插件执行"></a>
<a id="section-5-4"></a>
### 5.4 Tool 插件执行

```text
register_tool 时写入工具注册表
  → 模型在本轮 tools 列表里看到 schema（受 toolset / 白名单约束）
  → tool_call → 与内置工具同一执行管线（含上述 hook）
```

<a id="55-与线程模型的关系"></a>
<a id="section-5-5"></a>
### 5.5 与线程模型的关系

| 表面 | Hook/tool 通常跑在 |
|------|-------------------|
| CLI | **Agent `threading.Thread`**（不是 PT 主线程） |
| Gateway | **`run_in_executor` 工作线程** |
| 部分 gateway 钩子 | asyncio 循环上（如 `pre_gateway_dispatch`） |

插件若碰 UI/队列，需按表面选对线程；审批回调已由宿主处理。

---

<a id="6-hook--注册能力速查"></a>
<a id="section-6"></a>
## 6. Hook / 注册能力速查

<a id="61-valid_hooks摘要"></a>
<a id="section-6-1"></a>
### 6.1 VALID_HOOKS（摘要）

| Hook | 典型返回 |
|------|----------|
| `pre_llm_call` | `{"context": str}` |
| `pre_tool_call` | `{"action":"block"|"approve", "message", "rule_key"?}` |
| `transform_*` | 替换字符串（first wins） |
| `pre_verify` | `{"action":"continue","message"}` 等 |
| `pre_gateway_dispatch` | `skip` / `rewrite` / `allow` |
| `on_session_*` / `subagent_*` / `pre_approval_*` / `kanban_task_*` | 多为观察 |

完整集合以 `hermes_cli/plugins.py` 中 `VALID_HOOKS` 为准（含 `pre_verify`、`api_request_error`、kanban 等）。

<a id="62-为何不改-system-prompt"></a>
<a id="section-6-2"></a>
### 6.2 为何不改 System Prompt

```text
System（缓存稳定）  Identity + skills + memory 快照 …
User（每轮可变）    用户输入 + pre_llm_call context
```

中途改 system 会打穿 Anthropic/本地 prefix cache；built-in memory 也是「下轮/压缩再建」模型（见 MEMORY）。

---

<a id="hook-lifecycle-table"></a>
<a id="hook-生命周期全表触发点参数与可改变的行为"></a>
<a id="section-7"></a>
## 7. Hook 生命周期全表：触发点、参数与可改变的行为

> **主题归位**：本节从 `AGENT_LOOP_ARCHITECTURE.md` 的「11. Plugin Hook 全表」迁入；保留原有图表、示例和讨论。

> **权威名单**：`hermes_cli/plugins.py` → `VALID_HOOKS`\
> **注册**：`ctx.register_hook(name, callback)`\
> **分发**：`hermes_cli.lifecycle.invoke_hook` → plugins（shell hooks 事件名重叠，见用户文档）\
> **用户文档**：`website/docs/user-guide/features/hooks.md`\
> **深度单点**：`pre_llm_call` 的征集/拼装因果见 [§4 阶段 1.3](AGENT_LOOP_ARCHITECTURE.md#13-plugin-hook-pre_llm_call)

通则：

- 回调一律 **kwargs**；崩溃只打日志，不拖垮 Agent。
- **会改行为的少数**：`pre_tool_call`（block）、`pre_llm_call`（inject）、`pre_verify`（continue）、`pre_gateway_dispatch`（skip/rewrite）、三个 `transform_*`（替换字符串）。其余多为观测。

<a id="111-按生命周期总览"></a>
<a id="section-7-1"></a>
### 7.1 按生命周期总览

```text
Gateway 入站
  └─ pre_gateway_dispatch

Session 边界
  ├─ on_session_start          （新 session 第一 turn）
  ├─ on_session_end            （每轮 run_conversation 末 / 进程收尾）
  ├─ on_session_finalize       （真正拆 session：flush/统计）
  └─ on_session_reset          （/new /reset）

Turn（Agent Loop）
  ├─ pre_llm_call              ← 征集 ephemeral context
  ├─ pre_api_request / post_api_request / api_request_error   （每次打模型）
  ├─ pre_tool_call → 工具 → post_tool_call
  │     ├─ transform_terminal_output   （仅 terminal 内部）
  │     └─ transform_tool_result       （结果回模型前）
  ├─ pre_approval_* / post_approval_*  （危险命令审批）
  ├─ pre_verify                （改过代码、将结束前）
  ├─ transform_llm_output      （最终答复交给用户前）
  └─ post_llm_call             （本 turn 工具环结束后）

子 Agent
  ├─ subagent_start / subagent_stop

Kanban（另一进程模型）
  └─ kanban_task_claimed / completed / blocked
```

<a id="112-逐个作用--返回值--挂载点"></a>
<a id="section-7-2"></a>
### 7.2 逐个：作用 · 返回值 · 挂载点

| Hook | 作用 | 返回值 | 挂载点（生产） |
|------|------|--------|----------------|
| **`pre_gateway_dispatch`** | 网关收到用户消息、鉴权/派发前；可丢弃或改文案 | `skip` / `rewrite` / `allow` | `gateway/run.py` |
| **`on_session_start`** | 新 session 首 turn 初始化 | 忽略 | `agent/conversation_loop.py` |
| **`pre_llm_call`** | 征集临时上下文，拼进 API user（不改 Session 原话） | `{"context"}` / `str` | `agent/turn_context.py`（`build_turn_context`） |
| **`pre_api_request`** | 每次即将发 LLM HTTP 前（观测/计量） | 忽略 | `agent/conversation_loop.py` |
| **`post_api_request`** | 每次 LLM HTTP 成功返回后 | 忽略 | `agent/conversation_loop.py` |
| **`api_request_error`** | LLM 请求失败时 | 忽略 | `run_agent.py` |
| **`pre_tool_call`** | 任一工具执行前；可否决 | `{"action":"block","message"}` | `hermes_cli/plugins.py`（由 `model_tools.handle_function_call` 路径触发） |
| **`post_tool_call`** | 工具返回后（观测） | 忽略 | `model_tools.py` → `_emit_post_tool_call_hook` |
| **`transform_terminal_output`** | `terminal` 原始输出、截断/脱敏前 | `str` 替换 | `tools/terminal_tool.py` |
| **`transform_tool_result`** | 任意工具结果回模型前 | `str` 替换（首个非空） | `model_tools.py` |
| **`pre_approval_request`** | 危险命令进入审批前 | 忽略（不能否决；否决用 `pre_tool_call`） | `tools/approval.py` |
| **`post_approval_response`** | 审批有结果（once/deny/timeout/smart_*） | 忽略 | `tools/approval.py` |
| **`pre_verify`** | 本 turn 改过代码、将验证/收工前；可续跑 | `{"action":"continue","message"}` | `agent/conversation_loop.py`（经 plugins helper） |
| **`transform_llm_output`** | 最终答复交付用户前 | `str` 替换（首个非空） | `agent/turn_finalizer.py` |
| **`post_llm_call`** | 本 turn 工具环结束（同步/落库类观测） | 忽略 | `agent/turn_finalizer.py` |
| **`on_session_end`** | **每个** `run_conversation` 收尾（名含 session，实为 turn 末）+ CLI/TUI 退出兜底 | 忽略 | `turn_finalizer.py`；另 `cli.py` / `tui_gateway/server.py` |
| **`on_session_finalize`** | 真拆 session（flush/统计） | 忽略 | `lifecycle.finalize_session`；CLI/TUI/Gateway 边界 |
| **`on_session_reset`** | `/new`、`/reset` 换新 session key | 忽略 | `cli.py`、`gateway/slash_commands.py`、`tui_gateway` |
| **`subagent_start`** | `delegate_task` 子 Agent 已建、将跑 | 忽略 | `tools/delegate_tool.py` |
| **`subagent_stop`** | 子 Agent 退出 | 忽略 | `tools/delegate_tool.py` |
| **`kanban_task_claimed`** | 任务被认领（dispatcher 进程） | 忽略 | `hermes_cli/kanban_db.py` |
| **`kanban_task_completed`** | 任务完成（worker） | 忽略 | 同上 |
| **`kanban_task_blocked`** | 任务阻塞 | 忽略 | 同上 |

<a id="113-与-agent-loop-的对应"></a>
<a id="section-7-3"></a>
### 7.3 与 Agent Loop 的对应

```text
build_turn_context
  └─ pre_llm_call

while ReAct:
  └─ pre_api_request → LLM → post_api_request
       └─ (error → api_request_error)
  └─ pre_tool_call → tool → [transform_terminal_output]
                     → post_tool_call → transform_tool_result
  └─ (审批路径) pre_approval_request → … → post_approval_response
  └─ (收工前) pre_verify?

finalize_turn
  └─ transform_llm_output → post_llm_call → on_session_end
```

<a id="114-易混的三套钩子"></a>
<a id="section-7-4"></a>
### 7.4 易混的三套「钩子」

| 体系 | 是什么 |
|------|--------|
| **Plugin / shell hooks**（上表） | `VALID_HOOKS`，扩展点 |
| **MemoryProvider** | `prefetch` / `sync_turn` / `on_turn_start`… —— 记忆后端 API，不是 plugin hook |
| **AIAgent callbacks** | `stream_delta_callback` / `step_callback`… —— Surface 注入，也不是 hook |

---

<a id="7-源码锚点"></a>
<a id="section-8"></a>
## 8. 源码锚点

| 符号 | 文件 |
|------|------|
| `PluginManager.discover_and_load` / `_load_plugin` | `hermes_cli/plugins.py` |
| `PluginContext.register_*` | 同上 |
| `discover_plugins` / `invoke_hook` / `invoke_middleware` | 同上 |
| `resolve_pre_tool_block` | 同上 → HITL |
| 仓库插件示例 | `plugins/disk-cleanup/` |
| Memory exclusive | `plugins/memory/` + MEMORY 文档 |
| Platform 延迟加载 | `PluginManager._register_deferred_platform` |

---

<a id="变更说明相对旧稿"></a>
<a id="section-9"></a>
## 9. 变更说明（相对旧稿）

- 按用户五问重排：**架构 → 开发 → 配置 → 加载 → 执行**。
- 删除旧 §8 过时模板长文；开发以最小骨架 + 源码为准。
- Hook 列表与 `kind` 加载规则对齐 0.19 `plugins.py`。
