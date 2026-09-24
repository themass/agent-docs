# Deep Agents CLI 与 App/Code 架构设计文档

> **本文目标**：解析 Deep Agents 的终端交互与部署层架构（包括已拆分的 `deepagents-code` 交互 REPL TUI 以及 `deepagents-cli` 部署工具）。  
> **参考 DeerFlow 范式**：采用分层架构图 + 核心模块详解的风格。  
> **适用版本**：`deepagents-code==0.1.x`、`deepagents-cli==0.1.x`（与 SDK `deepagents==0.6.6` 配套）。

---

## 阅读地图

| 章节 | 内容 |
|------|------|
| [一、CLI 架构总览](#一cli-架构总览) | 三层模型、启动流程 |
| [二、Textual TUI 设计](#二textual-tui-设计) | 核心组件、交互模式 |
| [三、配置管理系统](#三配置管理系统) | config.toml、模型提供商、MCP 服务器 |
| [四、会话持久化](#四会话持久化) | 存储结构、恢复机制 |
| [五、MCP 集成](#五-mcp-集成) | 服务器连接、工具注册 |
| [六、源码索引](#六源码索引) | 关键文件路径 |

---

## 一、分包与架构总览

### 1.1 两大终端包分工
自 v0.6.6 SDK 起，终端交互与部署工具分为两个独立的发布包：
1. **`deepagents-code` (`libs/code/`)**：提供交互式 TUI 编程环境（运行命令为 `dcode`）。
2. **`deepagents-cli` (`libs/cli/`)**：提供部署编排子命令（运行命令为 `deepagents`，含 `init`、`dev`、`deploy`）。

### 1.2 三层架构模型 (针对 `deepagents-code`)

```
┌─────────────────────────────────────┐
│   Presentation Layer (TUI)          │  ← Textual App、Widgets、消息渲染
│   (app.py, textual_adapter.py)      │  ← 位于 libs/code/
├─────────────────────────────────────┤
│   Business Logic Layer              │  ← Agent 会话、工具调用、流式处理
│   (agent.py, sessions.py)           │  ← 位于 libs/code/
├─────────────────────────────────────┤
│   Infrastructure Layer              │  ← 配置加载、MCP 连接、SDK 调用
│   (config.py, mcp_tools.py, main.py)│  ← 位于 libs/code/
└─────────────────────────────────────┘
         ↓ 调用
┌─────────────────────────────────────┐
│   Deep Agents SDK                 │  ← create_deep_agent、Middleware Chain
│   (libs/deepagents/)                │
└─────────────────────────────────────┘
```

### 1.2 启动流程

1. **CLI 入口**：`deepagents` 命令 → `main.py:cli_main()`。
2. **参数解析**：`argparse` 解析命令行参数（`-a agent_name`、`-r thread_id` 等）。
3. **依赖检查**：检查 `textual`、`requests`、`python-dotenv` 等可选依赖。
4. **配置加载**：读取 `~/.deepagents/config.toml`，解析模型提供商、MCP 服务器、Skills 目录。
5. **初始化 Textual App**：创建 `DeepAgentsApp` 实例，加载主题、快捷键、历史会话。
6. **启动 TUI**：`app.run()` 进入事件循环，等待用户输入。

---

## 二、Textual TUI 设计

### 2.1 核心组件

**主应用**：`app.py:DeepAgentsApp`（260KB，核心交互逻辑）

**关键 Widgets**（`widgets/` 目录）：

| Widget | 作用 |
|--------|------|
| `ChatWindow` | 消息列表渲染（支持 Markdown、代码高亮、工具调用可视化） |
| `InputBox` | 用户输入框（支持多行、快捷键、自动补全） |
| `ToolPanel` | 实时显示工具调用状态、参数、结果摘要 |
| `StatusBar` | 显示当前模型、token 用量、连接状态 |
| `Sidebar` | 会话列表、文件浏览器、设置面板 |
| `MessageBubble` | 单条消息渲染（区分 Human/AI/Tool 消息） |

### 2.2 交互模式

**流式输出**：
- 模型响应逐字显示，非阻塞。
- 使用 `textual.workers` 异步接收 SSE 流。
- 实时更新 `ChatWindow`，避免卡顿。

**工具可视化**：
- 工具调用时显示进度条。
- 展开/折叠工具参数和结果。
- 错误消息高亮显示（红色背景）。

**中断处理**：
- 用户可按 `Ctrl+C` 中断当前任务。
- 触发 `PatchToolCallsMiddleware` 修补悬空 tool_calls。
- 保存 checkpoint，允许后续恢复。

**会话切换**：
- 左侧边栏列出所有 threads。
- 点击切换，自动加载历史消息和 state。
- 支持搜索、过滤、删除会话。

### 2.3 主题与样式

**主题文件**：`app.tcss`（5.3KB）

**示例样式**：
```css
ChatWindow {
    background: $surface;
    border: solid $primary;
}

MessageBubble.human {
    background: $boost;
    color: $text;
}

MessageBubble.ai {
    background: $surface-lighten-1;
    color: $text;
}

ToolCall.error {
    background: $error-darken-2;
    color: $text;
}
```

**自定义主题**：用户可在 `config.toml` 中指定 `theme = "dark"` 或 `"light"`。

---

## 三、配置管理系统

### 3.1 配置文件结构

**路径**：`~/.deepagents/config.toml`

**示例配置**：

```toml
[models]
default = "anthropic:claude-sonnet-4-6"

[models.providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"
default_model = "claude-sonnet-4-6"

[models.providers.openai]
api_key_env = "OPENAI_API_KEY"
default_model = "gpt-4o"

[mcp.servers]
filesystem = { command = "npx", args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"] }
github = { url = "https://api.github.com/mcp", headers = { Authorization = "Bearer ${GITHUB_TOKEN}" } }

[skills]
sources = ["/skills/public/", "/skills/user/"]

[memory]
files = ["/memory/AGENTS.md"]

[agents.recent]
last_used = "agent"

[ui]
theme = "dark"
sidebar_width = 30
chat_font_size = 14

[warnings]
suppress = ["ripgrep", "tavily"]
```

### 3.2 配置加载流程

**源码**：`config.py:load_config()`

1. **读取文件**：`tomllib.load(open("~/.deepagents/config.toml"))`。
2. **验证 schema**：检查必填字段（如 `models.default`）。
3. **解析环境变量**：替换 `${GITHUB_TOKEN}` 为实际值。
4. **缓存配置**：单例模式，避免重复读取。
5. **传递给 SDK**：调用 `create_deep_agent(model=config["models"]["default"], ...)`。

### 3.3 模型提供商管理

**源码**：`model_config.py`

**支持的提供商**：
- Anthropic（`anthropic:*`）
- OpenAI（`openai:*`）
- Google（`google:*`）
- Azure OpenAI（`azure_openai:*`）
- Ollama（`ollama:*`）

**自动检测**：
```python
from langchain.chat_models import init_chat_model

model = init_chat_model("anthropic:claude-sonnet-4-6")
# 自动从 ANTHROPIC_API_KEY 环境变量读取密钥
```

---

## 四、会话持久化

### 4.1 存储结构

**根目录**：`~/.deepagents/agents/<agent_name>/threads/<thread_id>/`

**文件清单**：

| 文件/目录 | 作用 |
|-----------|------|
| `messages.json` | 完整对话历史（JSON 数组） |
| `state.json` | AgentState（含 todos、artifacts、async_tasks 等） |
| `workspace/` | 工作目录（模型创建的文件） |
| `uploads/` | 用户上传的文件 |
| `outputs/` | 模型生成的产物（通过 `present_files` 上架） |
| `checkpoint.json` | LangGraph checkpoint（用于恢复执行） |

### 4.2 恢复机制

**流程**：

1. **CLI 启动**：读取 `agents.recent` 确定默认 agent。
2. **用户选择 thread**：从侧边栏点击会话。
3. **加载历史**：
   ```python
   messages = json.load(open(f"~/.deepagents/agents/{agent}/threads/{thread_id}/messages.json"))
   state = json.load(open(f"~/.deepagents/agents/{agent}/threads/{thread_id}/state.json"))
   ```
4. **恢复资源句柄**：
   - `sandbox_id`：重新连接沙箱实例。
   - `workspace_path`：映射到虚拟路径 `/mnt/user-data/`。
5. **继续对话**：调用 `agent.invoke({"messages": messages}, config={"configurable": {"thread_id": thread_id}})`。

### 4.3 Checkpoint 同步

**时机**：
- 每轮对话结束后，LangGraph 自动保存 checkpoint。
- 用户中断时，立即保存当前状态。
- CLI 退出时，强制 flush 所有未保存的更改。

**格式**：
```json
{
  "thread_id": "abc123",
  "checkpoint_ns": "",
  "channel_values": {
    "messages": [...],
    "todos": [...],
    "artifacts": [...]
  },
  "channel_versions": {...},
  "pending_sends": []
}
```

---

## 五、 MCP 集成

### 5.1 服务器连接

**源码**：`mcp_tools.py`

**工作流程**：

1. **配置声明**：在 `config.toml` 中声明 `[mcp.servers]`。
2. **启动时连接**：
   ```python
   from langchain_mcp_adapters.client import MultiServerMCPClient
   
   client = MultiServerMCPClient({
       "filesystem": {
           "command": "npx",
           "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"]
       },
       "github": {
           "url": "https://api.github.com/mcp",
           "headers": {"Authorization": "Bearer ghp_..."}
       }
   })
   
   tools = await client.get_tools()
   ```
3. **工具注册**：每个 MCP 服务器的 `tools/list` 响应转换为 `StructuredTool`。
4. **传递给 SDK**：`create_deep_agent(tools=tools, ...)`。

### 5.2 工具注册

**转换逻辑**：
```python
from langchain_core.tools import StructuredTool

def mcp_tool_to_langchain(mcp_tool):
    return StructuredTool(
        name=mcp_tool.name,
        description=mcp_tool.description,
        args_schema=mcp_tool.inputSchema,
        func=lambda **kwargs: call_mcp_tool(mcp_tool.name, kwargs),
    )
```

**延迟加载**（DeerFlow 特有）：通过 `DeferredToolFilterMiddleware` 过滤不常用工具，节省 context token。Deep Agents CLI 暂无此优化。

### 5.3 安全考虑

**MCP 信任机制**：
- 首次连接 MCP 服务器时，提示用户确认。
- 保存信任列表到 `~/.deepagents/mcp_trust.json`。
- 已信任的服务器自动连接，无需再次确认。

**权限隔离**：
- 文件系统 MCP 服务器限制在指定目录（如 `/home/user`）。
- GitHub MCP 服务器使用细粒度 PAT（Personal Access Token）。

---

## 六、源码索引

### 6.1 `deepagents-code` (交互式 TUI) 核心文件 (`libs/code/deepagents_code/`)

| 文件 | 作用 |
|------|------|
| `main.py` | `dcode` 命令行入口、参数解析 |
| `app.py` | Textual TUI 主应用 |
| `agent.py` | Agent 会话管理、消息流处理 |
| `config.py` | 配置加载（`config.toml`）、模型提供商管理 |
| `textual_adapter.py` | Textual 组件封装、消息渲染 |
| `widgets/` | UI 组件（ChatWindow、InputBox、ToolPanel 等） |
| `mcp_tools.py` | MCP 服务器连接与工具注册 |
| `sessions.py` | 会话持久化、历史记录管理 |
| `theme.py` | 主题管理、样式加载 |

### 6.2 `deepagents-cli` (部署编排) 核心文件 (`libs/cli/deepagents_cli/`)

| 文件 | 作用 |
|------|------|
| `main.py` | `deepagents` 命令行入口，路由到 `init`、`dev` 和 `deploy` 子命令 |

### 6.2 关键类与方法

**`DeepAgentsApp`**（`app.py`）：
- `on_mount()`：初始化应用，加载历史会话。
- `handle_user_input(message: str)`：处理用户输入，调用 Agent。
- `stream_agent_response()`：异步接收 SSE 流，实时更新 UI。
- `switch_thread(thread_id: str)`：切换会话，加载历史。

**`AgentSession`**（`agent.py`）：
- `invoke(message: str)`：调用 SDK Agent，返回响应。
- `interrupt()`：中断当前任务。
- `save_checkpoint()`：保存当前状态。

**`ConfigManager`**（`config.py`）：
- `load()`：读取并验证配置。
- `get_model_provider(name: str)`：获取模型提供商配置。
- `get_mcp_servers()`：获取 MCP 服务器列表。

---

## 总结

Deep Agents CLI 的设计遵循以下原则：

1. **分层清晰**：Presentation / Business Logic / Infrastructure 三层分离。
2. **响应式 UI**：基于 Textual 的异步事件循环，流式输出无卡顿。
3. **配置驱动**：`config.toml` 集中管理模型、MCP、Skills、Memory。
4. **持久化完善**：会话历史、checkpoint、workspace 全部落盘，支持断点续传。
5. **安全优先**：MCP 信任机制、路径隔离、API 密钥环境变量化。

**下一步**：
- 阅读 [Deep Agents 框架完整设计方案](./DEEPAGENTS_FRAMEWORK_COMPLETE_DESIGN.md)。
- 阅读 [Deep Agents Middleware Chain 深度设计文档](./DEEPAGENTS_MIDDLEWARE_CHAIN_DEEP_DESIGN.md)。
- 阅读 [Deep Agents Prompt 系统完整运行时文档](./DEEPAGENTS_PROMPT_RUNTIME_COMPLETE.md)。

---

**维护说明**：
- 升级 `deepagents-cli` 后请对照上游源码更新本文档。
- 新增 UI 组件或配置项时，请同步更新对应章节。
