# MCP 集成

> **文档状态**: Canonical（去重重构版）  
> **Hermes 版本锚点**: 0.19.0 · **核对**: 2026-07-31 · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)  
> **重构说明**: 删除重复的 Handler 教程 / 双份「最佳实践」/ stub 动态发现；保留命名、Schema、事件循环、OAuth、Sampling、错误模型各一份。  
> **源码**: `tools/mcp_tool.py`

---

## 目录

1. [概述](#1-概述)
2. [MCP 协议简介](#2-mcp-协议简介)
3. [Hermes MCP 客户端](#3-hermes-mcp-客户端)
4. [OAuth](#4-mcp-oauth-认证)
5. [添加 MCP Server](#5-mcp-服务器集成流程)
6. [工具调用](#6-mcp-工具调用)
7. [与原生工具对比](#7-与原生工具对比)
8. [Sampling](#8-mcp-sampling-支持)
9. [性能与监控](#9-性能优化与监控)
10. [最佳实践](#10-最佳实践)
11. [总结](#总结)

---


## 1. 概述

### 1.1 什么是 MCP?

**MCP (Model Context Protocol)** 是一个开放协议,允许 AI 模型通过标准化接口访问外部数据源和工具。由 Anthropic 提出,旨在解决"AI 模型如何安全访问外部资源"的问题。

### 1.2 Hermes MCP 集成价值

| 价值 | 说明 |
|------|------|
| **生态兼容** | 接入 MCP 生态系统(100+ servers) |
| **标准化** | 统一的工具调用接口 |
| **OAuth 支持** | 安全的用户授权流程 |
| **动态发现** | 自动发现 MCP 提供的 tools/resources |
| **无缝集成** | 与原生工具同等对待 |

---

## 2. MCP 协议简介

### 2.1 核心概念

```mermaid
graph LR
    Host[MCP Host<br/>Hermes Agent] <--> Transport[Transport Layer<br/>stdio/sse]
    Transport <--> Server[MCP Server<br/>External Service]
    
    Server --> Tools[Tools<br/>可执行操作]
    Server --> Resources[Resources<br/>数据源]
    Server --> Prompts[Prompts<br/>模板]
```

**组件**:
- **Host**: MCP 客户端(Hermes Agent)
- **Server**: MCP 服务端(GitHub、Slack、PostgreSQL等)
- **Transport**: 通信层(stdio/SSE)
- **Tools**: 可执行函数
- **Resources**: 数据源(文件、数据库记录等)
- **Prompts**: 预定义模板

### 2.2 支持的 Transports

| Transport | 适用场景 | 示例 |
|-----------|---------|------|
| **stdio** | 本地进程 | `npx -y @modelcontextprotocol/server-github` |
| **SSE** | 远程服务 | `https://mcp-server.example.com/sse` |
| **Streamable HTTP** | 现代 HTTP | `https://mcp-server.example.com/mcp` |

---

### 2.3 Hermes MCP 实现架构

Hermes Agent 采用**混合架构**：底层使用官方 MCP Python SDK，上层进行大量工程化封装。

#### **架构分层**

```mermaid
graph TB
    subgraph "Hermes Agent Layer"
        A1[Tool Registry<br/>工具注册系统]
        A2[Circuit Breaker<br/>熔断器]
        A3[OAuth Recovery<br/>认证恢复]
        A4[Dynamic Discovery<br/>动态发现]
        A5[Image Cache<br/>图片缓存]
        A6[Schema Normalization<br/>Schema标准化]
    end
    
    subgraph "Integration Layer"
        B1[Background Event Loop<br/>后台事件循环]
        B2[Cross-thread Scheduling<br/>跨线程调度]
        B3[Handler Factory<br/>Handler工厂]
        B4[Security Filter<br/>安全过滤]
    end
    
    subgraph "Official MCP SDK"
        C1[ClientSession<br/>会话管理]
        C2[stdio_client<br/>标准IO传输]
        C3[sse_client<br/>SSE传输]
        C4[streamable_http_client<br/>HTTP传输]
        C5[Type Definitions<br/>类型定义]
    end
    
    subgraph "MCP Protocol"
        D1[JSON-RPC 2.0]
        D2[Transport Layer]
        D3[Message Format]
    end
    
    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1
    A5 --> B1
    A6 --> B1
    
    B1 --> C1
    B2 --> C1
    B3 --> C1
    B4 --> C2
    
    C1 --> D1
    C2 --> D2
    C3 --> D2
    C4 --> D2
    C5 --> D3
```

#### **职责划分**

| 层级 | 功能 | 实现方式 |
|------|------|----------|
| **协议层** | JSON-RPC、消息格式、传输协议 | ✅ 官方 SDK |
| **传输层** | stdio/SSE/HTTP 连接管理 | ✅ 官方 SDK |
| **会话层** | ClientSession、初始化、工具发现 | ✅ 官方 SDK |
| **集成层** | 后台事件循环、跨线程调度、Handler工厂 | 🔧 Hermes 自研 |
| **业务层** | 工具注册、熔断器、OAuth恢复、动态发现 | 🔧 Hermes 自研 |
| **增强层** | Schema标准化、图片缓存、安全过滤 | 🔧 Hermes 自研 |

#### **为什么需要封装？**

**问题 1: 同步 vs 异步** — Hermes 主循环是同步的，MCP SDK 是异步的，必须经后台事件循环桥接（见 [§3.5](#35-后台事件循环架构) / 下文事件循环节）。

其余封装动机（熔断、OAuth、Schema 标准化、动态发现）见本章后续小节与 [§6.3 错误处理](#63-错误处理机制)。

## 3. Hermes MCP 客户端


### 3.1 MCP 工具注册流程

Hermes Agent **不会**将 MCP 工具直接注册为 `mcp_call`，而是**自动发现并注册每个 MCP 服务器的具体工具**。

#### **完整注册流程**

```mermaid
sequenceDiagram
    participant Start as Hermes启动
    participant Config as 加载配置
    participant EventLoop as MCP后台事件循环
    participant Server as MCPServerTask
    participant SDK as MCP SDK
    participant Registry as ToolRegistry
    
    Start->>Config: 读取 ~/.hermes/config.yaml
    Config->>EventLoop: register_mcp_servers(servers)
    EventLoop->>EventLoop: _ensure_mcp_loop()<br/>创建后台线程
    EventLoop->>Server: _connect_server(name, config)
    Server->>SDK: stdio_client/http_client<br/>建立连接
    SDK-->>Server: (read_stream, write_stream)
    Server->>SDK: ClientSession(read, write)
    Server->>SDK: session.initialize()
    SDK-->>Server: InitializeResult
    Server->>SDK: session.list_tools()
    SDK-->>Server: ListToolsResult
    Server->>Server: _register_server_tools()
    
    Note over Server,Registry: 遍历每个MCP工具并注册
    Server->>Registry: registry.register(name, toolset, schema, handler, check_fn)
    Server->>Registry: registry.register_toolset_alias(server_name, toolset_name)
```

#### **关键步骤详解**

**步骤 1：加载配置**

```python
# tools/mcp_tool.py:L3042-3100
def register_mcp_servers(servers: Dict[str, dict]) -> List[str]:
    """Connect to explicit MCP servers and register their tools."""
    
    # 1. 过滤已连接的服务器
    with _lock:
        new_servers = {
            k: v for k, v in servers.items()
            if k not in _servers and _parse_boolish(v.get("enabled", True))
        }
    
    # 2. 确保后台事件循环运行
    _ensure_mcp_loop()  # L2026-2039
    
    # 3. 并行连接所有服务器
    async def _discover_all():
        results = await asyncio.gather(
            *(_discover_one(name, cfg) for name, cfg in new_servers.items()),
            return_exceptions=True,
        )
    
    _run_on_mcp_loop(_discover_all())

### 3.2 MCP 工具命名规则

#### **工具名称生成**

```python
# tools/mcp_tool.py:L2677-2706
def sanitize_mcp_name_component(value: str) -> str:
    """Sanitize MCP name component for tool naming."""
    # 将所有非字母数字字符替换为下划线
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value or ""))


def _convert_mcp_schema(server_name: str, mcp_tool) -> dict:
    """Convert MCP tool to Hermes registry schema format."""
    safe_tool_name = sanitize_mcp_name_component(mcp_tool.name)
    safe_server_name = sanitize_mcp_name_component(server_name)
    
    # 生成前缀名称：mcp_{server}_{tool}
    prefixed_name = f"mcp_{safe_server_name}_{safe_tool_name}"
    
    return {
        "name": prefixed_name,
        "description": mcp_tool.description or f"MCP tool {mcp_tool.name} from {server_name}",
        "parameters": _normalize_mcp_input_schema(mcp_tool.inputSchema),
    }
```

**实际示例**：

| MCP 服务器 | MCP 工具 | Hermes 工具名 |
|-----------|---------|--------------|
| `github` | `create_issue` | `mcp_github_create_issue` |
| `filesystem` | `read_file` | `mcp_filesystem_read_file` |
| `slack-bot` | `send_message` | `mcp_slack_bot_send_message` |

**命名规则详解**：

```python
# 示例 1：简单名称
server_name = "github"
tool_name = "create_issue"

safe_server_name = sanitize_mcp_name_component("github")
# → "github" （无需转换）

safe_tool_name = sanitize_mcp_name_component("create_issue")
# → "create_issue" （无需转换）

prefixed_name = f"mcp_{safe_server_name}_{safe_tool_name}"
# → "mcp_github_create_issue"


# 示例 2：包含特殊字符的名称
server_name = "slack-bot"
tool_name = "send.message"

safe_server_name = sanitize_mcp_name_component("slack-bot")
# → "slack_bot" （连字符替换为下划线）

safe_tool_name = sanitize_mcp_name_component("send.message")
# → "send_message" （点号替换为下划线）

prefixed_name = f"mcp_{safe_server_name}_{safe_tool_name}"
# → "mcp_slack_bot_send_message"


# 示例 3：包含空格和特殊符号
server_name = "My Server"
tool_name = "get data!"

safe_server_name = sanitize_mcp_name_component("My Server")
# → "My_Server" （空格替换为下划线）

safe_tool_name = sanitize_mcp_name_component("get data!")
# → "get_data_" （空格和感叹号替换为下划线）

prefixed_name = f"mcp_{safe_server_name}_{safe_tool_name}"
# → "mcp_My_Server_get_data_"
```

**为什么需要前缀？**

```python
# 问题：多个 MCP 服务器可能有同名工具
# GitHub 服务器有 "list_repositories"
# GitLab 服务器也有 "list_repositories"

# 如果没有前缀，会发生冲突：
registry.register(name="list_repositories", ...)  # 第一次注册成功
registry.register(name="list_repositories", ...)  # 第二次注册失败或覆盖

# 使用前缀后，每个工具都有唯一名称：
registry.register(name="mcp_github_list_repositories", ...)    # ✓
registry.register(name="mcp_gitlab_list_repositories", ...)    # ✓

# Agent 可以明确指定调用哪个服务器的工具：
# - 调用 GitHub: "use mcp_github_list_repositories"
# - 调用 GitLab: "use mcp_gitlab_list_repositories"
```

---

### 3.3 工具描述（Schema）转换

#### **输入 Schema 标准化**

```python
# tools/mcp_tool.py:L2569-2674
def _normalize_mcp_input_schema(schema: dict | None) -> dict:
    """Normalize MCP input schemas for LLM compatibility.
    
    修复常见的 MCP Schema 问题：
    1. 将 definitions 转换为 $defs（Kimi/Moonshot 要求）
    2. 补全缺失的 type="object"
    3. 补全缺失的 properties={}
    4. 修剪 required 数组（只保留存在的属性）
    5. 折叠 nullable unions（Anthropic 不接受 null 类型）
    """
    if not schema:
        return {"type": "object", "properties": {}}
    
    def _rewrite_local_refs(node):
        # 将 #/definitions/X 转换为 #/$defs/X
        if isinstance(node, dict):
            if "$ref" in node:
                node["$ref"] = node["$ref"].replace("#/definitions/", "#/$defs/")
            for key, value in node.items():
                node[key] = _rewrite_local_refs(value)
        elif isinstance(node, list):
            return [_rewrite_local_refs(item) for item in node]
        return node
    
    normalized = _rewrite_local_refs(dict(schema))
    
    # 补全缺失的 type
    if normalized.get("type") is None and "properties" in normalized:
        normalized["type"] = "object"
    
    # 补全缺失的 properties
    if normalized.get("type") == "object" and "properties" not in normalized:
        normalized["properties"] = {}
    
    # 修剪 required 数组
    if "required" in normalized and "properties" in normalized:
        valid_props = set(normalized["properties"].keys())
        normalized["required"] = [
            r for r in normalized["required"] if r in valid_props
        ]
    
    return normalized
```

**实际示例**：

```json

**为什么需要这些转换？**

```python
# 问题 1: Kimi/Moonshot 模型不支持 #/definitions 引用
# 错误示例:
# {
#   "$ref": "#/definitions/User"
# }
# Kimi API 返回: "Invalid JSON Schema: unknown reference '#/definitions/User'"

# 解决方案: 转换为 #/$defs
# {
#   "$ref": "#/$defs/User"
# }
# Kimi API 接受 ✓


# 问题 2: Anthropic Claude 不接受 nullable unions
# 错误示例:
# {
#   "anyOf": [{"type": "string"}, {"type": "null"}]
# }
# Claude API 返回: "Invalid schema: anyOf with null is not supported"

# 解决方案: 折叠为单一类型
# {
#   "type": "string"
# }
# Claude API 接受 ✓


# 问题 3: 缺失的 required 字段导致 LLM 生成无效参数
# 错误示例:
# {
#   "required": ["owner", "repo", "title", "nonexistent_field"]
# }
# LLM 尝试生成: {"owner": "...", "repo": "...", "title": "...", "nonexistent_field": null}
# MCP 服务器返回: "Unknown parameter: nonexistent_field"

# 解决方案: 修剪 required 数组
# {
#   "required": ["owner", "repo", "title"]
# }
# LLM 生成有效参数 ✓
```

---


### 3.4 工具 Handler 工厂

#### **什么是工厂函数？**

`_make_tool_handler` 是一个**工厂函数**（Factory Function），它的作用是**动态生成**一个工具调用处理器。

**为什么需要工厂函数？**

```python
# 问题：我们有多个 MCP 服务器，每个服务器有多个工具
# - github 服务器: create_issue, list_repositories, ...
# - filesystem 服务器: read_file, write_file, ...
# - slack 服务器: send_message, list_channels, ...

# 如果为每个工具写一个 handler 函数，会有几百个重复的函数！
def handle_github_create_issue(args):
    # 连接检查
    # 调用 MCP
    # 错误处理
    ...

def handle_github_list_repositories(args):
    # 连接检查
    # 调用 MCP
    # 错误处理
    ...

# 解决方案：用工厂函数动态生成
github_create_issue_handler = _make_tool_handler("github", "create_issue", 120)
github_list_repos_handler = _make_tool_handler("github", "list_repositories", 120)
filesystem_read_handler = _make_tool_handler("filesystem", "read_file", 60)
```

**工厂函数的优势**：
- ✅ 代码复用：所有工具共享同一套逻辑
- ✅ 参数化：通过闭包捕获 `server_name` 和 `tool_name`
- ✅ 一致性：统一的错误处理和熔断机制

---

#### **核心概念：闭包（Closure）**

```python
def _make_tool_handler(server_name: str, tool_name: str, tool_timeout: float):
    """工厂函数：返回一个同步的 handler 函数"""
    
    def _handler(args: dict, **kwargs) -> str:
        # 这个内部函数可以访问外部函数的变量：
        # - server_name (例如: "github")
        # - tool_name (例如: "create_issue")
        # - tool_timeout (例如: 120)
        
        # ... 完整的调用逻辑 ...
        
    return _handler  # 返回内部函数（闭包）


# 使用示例
handler = _make_tool_handler("github", "create_issue", 120)
# handler 现在是一个函数，但它"记住"了：
# - server_name = "github"
# - tool_name = "create_issue"
# - tool_timeout = 120

# 调用时只需要传 args
result = handler({"owner": "NousResearch", "repo": "hermes-agent", ...})
```

**闭包的工作原理**：

```python
# 步骤 1: 调用工厂函数
handler1 = _make_tool_handler("github", "create_issue", 120)
# 创建了一个闭包，捕获了 server_name="github", tool_name="create_issue"

handler2 = _make_tool_handler("github", "list_repos", 120)
# 创建了另一个闭包，捕获了 server_name="github", tool_name="list_repos"

# 步骤 2: 两个 handler 独立工作
result1 = handler1({"owner": "...", "title": "..."})
# 内部调用: session.call_tool("create_issue", args)

result2 = handler2({"owner": "..."})
# 内部调用: session.call_tool("list_repos", args)

# 虽然都连接到 "github" 服务器，但调用的工具不同
```

---

#### **完整执行流程详解**

让我们用一个实际例子来跟踪整个执行过程：

**场景**：用户说"帮我创建一个 GitHub issue"

```python
# ===== 阶段 1: 注册工具（启动时）=====

# 在 _register_server_tools 中调用
handler = _make_tool_handler(
    server_name="github",
    tool_name="create_issue",
    tool_timeout=120
)

# 此时 _make_tool_handler 执行：
# 1. 接收参数: server_name="github", tool_name="create_issue", tool_timeout=120
# 2. 定义内部函数 _handler（但不执行）
# 3. 返回 _handler 函数对象

# registry.register 保存这个 handler
registry.register(
    name="mcp_github_create_issue",
    handler=handler,  # ← 保存的是函数对象
    ...
)


# ===== 阶段 2: 调用工具（运行时）=====

# Agent 决定调用工具
entry = registry.get_entry("mcp_github_create_issue")
args = {
    "owner": "NousResearch",
    "repo": "hermes-agent",
    "title": "Bug: Login fails",
    "body": "When I try to login, I get a 500 error."
}

# 调用 handler
result = entry.handler(args)
# 这实际上是在调用之前创建的 _handler 函数


# ===== 阶段 3: _handler 内部执行 =====

def _handler(args: dict, **kwargs) -> str:
    # 此时 _handler 可以访问：
    # - server_name = "github" (从闭包捕获)
    # - tool_name = "create_issue" (从闭包捕获)
    # - tool_timeout = 120 (从闭包捕获)
    # - args = {...} (调用时传入)
    
    # --- 步骤 1: 熔断器检查 ---
    if _server_error_counts.get("github", 0) >= 5:
        # 如果之前失败了 5 次，直接拒绝
        opened_at = _server_breaker_opened_at.get("github", 0.0)
        age = time.monotonic() - opened_at
        if age < 60:  # 冷却期 60 秒
            remaining = max(1, int(60 - age))
            return json.dumps({
                "error": f"MCP server 'github' is unreachable after 5 consecutive failures. Auto-retry available in ~{remaining}s."
            })
    # → 假设通过了检查
    
    # --- 步骤 2: 获取服务器实例 ---
    with _lock:
        server = _servers.get("github")
    # server = MCPServerTask(name="github", session=<ClientSession>, ...)
    
    if not server or not server.session:
        _bump_server_error("github")
        return json.dumps({"error": "MCP server 'github' is not connected"})
    # → 假设服务器已连接
    
    # --- 步骤 3: 定义异步调用函数 ---
    async def _call():
        # 这个协程会在后台事件循环中执行
        
        # 3.1 获取 RPC 锁（防止并发请求冲突）
        async with server._rpc_lock:
            # 3.2 调用 MCP SDK
            result = await server.session.call_tool(
                "create_issue",  # ← 从闭包捕获的 tool_name
                arguments=args   # ← 调用时传入的参数
            )
        
        # 3.3 处理响应
        # result = CallToolResult(
        #     content=[TextBlock(text="Issue #123 created...")],
        #     isError=False,
        #     structuredContent=None
        # )
        
        if result.isError:
            # 收集错误信息
            error_text = "".join(block.text for block in result.content)
            return json.dumps({"error": _sanitize_error(error_text)})
        
        # 3.4 收集文本内容块
        parts = []
        for block in result.content:
            if hasattr(block, "text") and block.text:
                parts.append(block.text)
            # 如果有图片，缓存并生成标签
            image_tag = _cache_mcp_image_block(block)
            if image_tag:
                parts.append(image_tag)
        
        text_result = "\n".join(parts)
        # text_result = "Issue #123 created successfully. URL: ..."
        
        # 3.5 合并 structuredContent（如果有）
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            if text_result:
                return json.dumps({
                    "result": text_result,
                    "structuredContent": structured
                })
            return json.dumps({"result": structured})
        
        return json.dumps({"result": text_result})
    
    # --- 步骤 4: 包装为同步调用 ---
    def _call_once():
        # 将异步协程调度到后台事件循环
        return _run_on_mcp_loop(_call(), timeout=120)
    
    # --- 步骤 5: 执行并处理异常 ---
    try:
        result = _call_once()
        # _call_once() 内部：
        # 1. asyncio.run_coroutine_threadsafe(_call(), loop)
        # 2. 轮询等待结果（支持中断）
        # 3. 返回 JSON 字符串
        
        # --- 步骤 6: 更新熔断器状态 ---
        try:
            parsed = json.loads(result)
            # parsed = {"result": "Issue #123 created..."}
            
            if "error" in parsed:
                _bump_server_error("github")
                # _server_error_counts["github"] += 1
            else:
                _reset_server_error("github")
                # _server_error_counts["github"] = 0
        except (json.JSONDecodeError, TypeError):
            _reset_server_error("github")
        
        return result

#### **可用性检查函数**

```python
# tools/mcp_tool.py:L2554-2562
def _make_check_fn(server_name: str):
    """Return a check function that verifies the MCP connection is alive."""
    
    def _check() -> bool:
        with _lock:
            server = _servers.get(server_name)
        return server is not None and server.session is not None
    
    return _check
```

**用途**：注册时传入 `check_fn`，每次工具调用前自动检查服务器是否连接。

**实际使用示例**：

```python
# 注册工具时
registry.register(
    name="mcp_github_create_issue",
    toolset="mcp-github",
    schema=schema,
    handler=_make_tool_handler("github", "create_issue", 120),
    check_fn=_make_check_fn("github"),  # ← 传入检查函数
    ...
)

# Agent 调用工具前自动检查
entry = registry.get_entry("mcp_github_create_issue")

# 检查可用性
if entry.check_fn and not entry.check_fn():
    # 服务器未连接，返回错误
    return tool_error("Tool 'mcp_github_create_issue' is not available")

# 通过检查，继续调用
result = entry.handler(args)


# check_fn 的实现细节
def _make_check_fn(server_name: str):
    def _check() -> bool:
        with _lock:
            server = _servers.get(server_name)
        # 检查两个条件：
        # 1. 服务器实例存在
        # 2. session 已初始化
        return server is not None and server.session is not None
    
    return _check

# 示例场景

# 场景 1: 服务器正常连接
_servers["github"] = MCPServerTask(session=<ClientSession>)
check_fn = _make_check_fn("github")
result = check_fn()
# → True ✓


# 场景 2: 服务器未连接
_servers["github"] = None
check_fn = _make_check_fn("github")
result = check_fn()
# → False ✗


# 场景 3: session 断开
_servers["github"] = MCPServerTask(session=None)
check_fn = _make_check_fn("github")
result = check_fn()
# → False ✗
```

---


### 3.5 后台事件循环架构

#### **为什么需要后台事件循环？**

Hermes Agent 的主循环是**同步的** (`run_conversation`)，但 MCP SDK 基于 **asyncio**。解决方案：

```python
# tools/mcp_tool.py:L2026-2039
def _ensure_mcp_loop():
    """Start the background event loop thread if not already running."""
    global _mcp_loop, _mcp_thread
    with _lock:
        if _mcp_loop is not None and _mcp_loop.is_running():
            return
        
        # 创建新的事件循环
        _mcp_loop = asyncio.new_event_loop()
        _mcp_loop.set_exception_handler(_mcp_loop_exception_handler)
        
        # 在守护线程中运行
        _mcp_thread = threading.Thread(
            target=_mcp_loop.run_forever,
            name="mcp-event-loop",
            daemon=True,
        )
        _mcp_thread.start()
```

**实际运行示例**：

```python
# 场景 1: Hermes Agent 启动时首次调用
print("Starting Hermes Agent...")

# 第一次调用 register_mcp_servers
register_mcp_servers(servers_config)
# 内部调用 _ensure_mcp_loop()

# _ensure_mcp_loop() 执行流程：
# 1. 检查 _mcp_loop 是否为 None
#    → _mcp_loop = None，需要创建

# 2. 创建新的事件循环
_mcp_loop = asyncio.new_event_loop()
# _mcp_loop = <_UnixSelectorEventLoop running=False closed=False>

# 3. 设置异常处理器
_mcp_loop.set_exception_handler(_mcp_loop_exception_handler)
# 当协程抛出未捕获异常时，记录日志而不是崩溃

# 4. 创建守护线程
_mcp_thread = threading.Thread(
    target=_mcp_loop.run_forever,
    name="mcp-event-loop",
    daemon=True  # 主线程退出时自动终止
)
_mcp_thread.start()
# 启动线程，开始运行事件循环

# 5. 线程内部执行
# Thread target: _mcp_loop.run_forever()
# while True:
#     await next_coroutine()
#     ...

print("MCP event loop started in background thread")
# 输出: Starting Hermes Agent...
#       MCP event loop started in background thread


# 场景 2: 第二次调用（已经运行）
register_mcp_servers(another_server_config)
# 内部再次调用 _ensure_mcp_loop()

# _ensure_mcp_loop() 执行流程：
# 1. 检查 _mcp_loop 是否正在运行
#    → _mcp_loop.is_running() = True

# 2. 直接返回，不创建新线程
return

print("Reusing existing MCP event loop")
# 不会重复创建线程
```

**架构示意图**：

```
┌─────────────────────────────────────────┐
│         Main Thread (Sync)              │
│  run_conversation()                     │
│    ↓                                    │
│  entry.handler(args)  ← 调用 MCP 工具   │
│    ↓                                    │
│  _run_on_mcp_loop(coro) ← 跨线程调度    │
└──────────────┬──────────────────────────┘
               │ asyncio.run_coroutine_threadsafe()
               ↓
┌─────────────────────────────────────────┐
│      Background Thread (Async)          │
│  mcp-event-loop (daemon)                │
│    ↓                                    │
│  _mcp_loop.run_forever()                │
│    ↓                                    │
│  Process coroutines:                    │
│    - _connect_server()                  │
│    - session.call_tool()                │
│    - session.list_tools()               │
│    - ...                                │
└─────────────────────────────────────────┘
```

**为什么不用 async/await 重构整个 Agent？**

### 3.6 动态工具发现（notifications/tools/list_changed）

MCP 服务器可以在运行时动态添加/删除工具，Hermes 通过**通知机制**自动同步：

```python
# tools/mcp_tool.py:L1013-1054
def _make_message_handler(self):
    """Build a message_handler callback for ClientSession."""
    async def _handler(message):
        if _MCP_NOTIFICATION_TYPES and isinstance(message, ServerNotification):
            match message.root:
                case ToolListChangedNotification():
                    logger.info("MCP server '%s': received tools/list_changed", self.name)
                    # 在后台任务中刷新工具（避免阻塞当前 RPC）
                    self._schedule_tools_refresh()
                    await asyncio.sleep(0)  # yield control
                case PromptListChangedNotification():
                    logger.debug("MCP server '%s': prompts/list_changed (ignored)", self.name)
                case ResourceListChangedNotification():
                    logger.debug("MCP server '%s': resources/list_changed (ignored)", self.name)
    return _handler


async def _refresh_tools(self):
    """Re-fetch tools from the server and update the registry."""
    from tools.registry import registry
    
    async with self._refresh_lock:
        old_tool_names = set(self._registered_tool_names)
        
        # 1. 重新获取工具列表
        async with self._rpc_lock:
            tools_result = await self.session.list_tools()
        new_mcp_tools = tools_result.tools if hasattr(tools_result, "tools") else []
        
        # 2. 移除已不存在的工具
        stale_tool_names = old_tool_names - {
            f"mcp_{sanitize_mcp_name_component(self.name)}_"
            f"{sanitize_mcp_name_component(tool.name)}"
            for tool in new_mcp_tools
        }
        for tool_name in stale_tool_names:
            registry.deregister(tool_name)
        
        # 3. 重新注册（增量更新）
        self._tools = new_mcp_tools
        self._registered_tool_names = _register_server_tools(self.name, self, self._config)
        
        # 4. 记录变更
        new_tool_names = set(self._registered_tool_names)
        added = new_tool_names - old_tool_names
        removed = old_tool_names - new_tool_names
        if added or removed:
            logger.warning(
                "MCP server '%s': tools changed — added: %s, removed: %s",
                self.name, added, removed
            )
```

**触发场景**：
- MongoDB MCP 服务器在启动后立即发送 `tools/list_changed`
- 插件式 MCP 服务器动态加载新工具
- 配置热更新后重新发现工具

**实际运行示例**：


### 3.7 服务器配置


```yaml
# ~/.hermes/mcp_servers.yaml

mcp_servers:
  github:
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
  
  slack:
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-slack"
    env:
      SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
  
  postgresql:
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-postgres"
      - "postgresql://user:pass@localhost/db"
```

---


```

## 4. MCP OAuth 认证

### 4.1 OAuth 流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant H as Hermes Agent
    participant M as MCP Server
    participant O as OAuth Provider
    
    U->>H: 配置 MCP server
    H->>M: 请求授权
    M->>O: 重定向到 OAuth
    O->>U: 登录页面
    U->>O: 授权
    O->>M: 返回 authorization code
    M->>O: 交换 access token
    O->>M: 返回 token
    M->>H: 授权成功
    H->>U: 保存配置
```

### 4.2 OAuth 管理器

```python
# tools/mcp_oauth_manager.py

class MCPOAuthManager:
    """MCP OAuth 认证管理器"""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.tokens = self._load_tokens()
    
    def authenticate(self, server_name: str) -> bool:
        """
        执行 OAuth 流程
        
        Returns:
            True 如果认证成功
        """
        server_config = self._get_server_config(server_name)
        
        if not server_config.get("oauth"):
            # 不需要 OAuth
            return True
        
        # 1. 生成 PKCE
        code_verifier, code_challenge = self._generate_pkce()
        
        # 2. 构建授权 URL
        auth_url = self._build_auth_url(
            server_config["oauth"]["authorization_endpoint"],
            server_config["oauth"]["client_id"],
            code_challenge,
        )
        
        # 3. 打开浏览器
        webbrowser.open(auth_url)
        
        # 4. 等待回调
        auth_code = self._wait_for_callback()
        
        # 5. 交换 token
        token_response = self._exchange_token(
            server_config["oauth"]["token_endpoint"],
            auth_code,
            code_verifier,
        )
        
        # 6. 保存 token
        self.tokens[server_name] = token_response
        self._save_tokens()
        
        return True
    
    def get_access_token(self, server_name: str) -> str:
        """获取 access token(自动刷新)"""
        token = self.tokens.get(server_name)
        
        if not token:
            raise ValueError(f"No token for server: {server_name}")
        
        # 检查是否过期
        if self._is_expired(token):
            # 刷新 token
            token = self._refresh_token(server_name, token["refresh_token"])
            self.tokens[server_name] = token
            self._save_tokens()
        
        return token["access_token"]
```

---


## 5. MCP 服务器集成流程

### 5.1 添加新 MCP Server

**步骤 1**: 安装服务器
```bash
# 示例: GitHub MCP Server
npm install -g @modelcontextprotocol/server-github
```

**步骤 2**: 配置服务器
```yaml
# ~/.hermes/mcp_servers.yaml

mcp_servers:
  github:
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
```

**步骤 3**: 设置环境变量
```bash
# ~/.hermes/.env

GITHUB_TOKEN=ghp_xxx
```

**步骤 4**: 测试连接
```bash
hermes mcp test github

# 输出:
# ✓ Connected to GitHub MCP server
# ✓ Available tools: 15
#   - create_issue
#   - list_repositories
#   - get_pull_request
#   ...
```


## 6. MCP 工具调用

### 6.1 调用流程详解

当 Agent 决定调用一个 MCP 工具时，完整的执行链路如下：

```mermaid
sequenceDiagram
    participant LLM as LLM
    participant Agent as AIAgent
    participant Registry as ToolRegistry
    participant Handler as MCPHandler
    participant EventLoop as BackgroundLoop
    participant Server as MCPServerTask
    participant SDK as MCPSDK
    participant ExtServer as ExternalMCPServer
    
    LLM->>Agent: assistant message with tool calls
    Agent->>Registry: get entry by tool name
    Registry-->>Agent: return tool entry
    
    Agent->>Handler: call handler with args
    Handler->>Handler: check connection
    Handler->>EventLoop: schedule on loop
    
    Note over EventLoop: Cross thread scheduling
    EventLoop->>Server: acquire lock
    Server->>SDK: call tool
    SDK->>ExtServer: send request
    ExtServer-->>SDK: return result
    SDK-->>Server: process result
    
    alt Success
        Server->>Server: collect text
        Server->>Server: cache images
        Server->>Server: merge content
        Server-->>EventLoop: return result
    else Error
        Server->>Server: sanitize error
        Server-->>EventLoop: return error
    end
    
    EventLoop-->>Handler: return JSON
    Handler->>Handler: update counter
    Handler-->>Agent: return JSON
    Agent->>Agent: persist if needed
    Agent->>LLM: send tool message
```


### 6.3 错误处理机制

#### **1. 熔断器（Circuit Breaker）**

```python
# tools/mcp_tool.py:L2176-2189
if _server_error_counts.get(server_name, 0) >= _CIRCUIT_BREAKER_THRESHOLD:
    opened_at = _server_breaker_opened_at.get(server_name, 0.0)
    age = time.monotonic() - opened_at
    if age < _CIRCUIT_BREAKER_COOLDOWN_SEC:
        remaining = max(1, int(_CIRCUIT_BREAKER_COOLDOWN_SEC - age))
        return json.dumps({
            "error": (
                f"MCP server '{server_name}' is unreachable after "
                f"{_server_error_counts[server_name]} consecutive failures. "
                f"Auto-retry available in ~{remaining}s. "
                f"Do NOT retry this tool yet — use alternative approaches."
            )
        })
```

**配置**：
- `_CIRCUIT_BREAKER_THRESHOLD = 5`（连续失败 5 次触发）
- `_CIRCUIT_BREAKER_COOLDOWN_SEC = 60`（冷却时间 60 秒）

**工作流程**：
```
正常状态 → 失败 1 次 → ... → 失败 5 次 → 熔断器打开
                                              ↓
                                    拒绝所有请求 60 秒
                                              ↓
                                    冷却期结束 → 半开状态
                                              ↓
                                   允许 1 次探测请求
                                              ↓
                                  成功 → 重置计数器
                                  失败 → 重新进入熔断
```

#### **2. OAuth 认证恢复**

```python
# tools/mcp_tool.py:L1725-1832
def _handle_auth_error_and_retry(server_name, exc, retry_call, op_description):
    """Attempt auth recovery and one retry."""
    
    if not _is_auth_error(exc):  # 检查是否是 401 错误
        return None
    
    from tools.mcp_oauth_manager import get_manager
    manager = get_manager()
    
    # 1. 尝试 OAuth 恢复（检查磁盘是否有新 token）
    recovered = _run_on_mcp_loop(manager.handle_401(server_name, None), timeout=10)
    
    if recovered:
        # 2. 设置重连事件，触发服务器重建会话
        srv = _servers.get(server_name)
        if srv:
            _mcp_loop.call_soon_threadsafe(srv._reconnect_event.set)
            # 等待最多 15 秒直到会话就绪
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if srv.session and srv._ready.is_set():
                    break
                time.sleep(0.25)
        
        # 3. 重试一次
        try:
            result = retry_call()
            if "error" not in json.loads(result):
                _reset_server_error(server_name)
                return result
        except Exception:
            pass
    
    # 4. 恢复失败，返回结构化错误
    _bump_server_error(server_name)
    return json.dumps({
        "error": f"MCP server '{server_name}' requires re-authentication. "
                 f"Run `hermes mcp login {server_name}`.",
        "needs_reauth": True,
        "server": server_name,
    })
```

#### **3. Session 过期恢复**

```python
# tools/mcp_tool.py:L1881-1961
def _handle_session_expired_and_retry(server_name, exc, retry_call, op_description):
    """Trigger transport reconnect on session expiry (not auth error)."""
    
    if not _is_session_expired_error(exc):  # 检查错误消息是否包含 "session expired"
        return None
    
    srv = _servers.get(server_name)
    if not srv:
        return None
    
    # 1. 触发重连（不经过 OAuth，因为 token 仍然有效）
    _mcp_loop.call_soon_threadsafe(srv._reconnect_event.set)
    
    # 2. 等待会话就绪
    deadline = time.monotonic() + 15
    ready = False
    while time.monotonic() < deadline:
        if srv.session and srv._ready.is_set():
            ready = True
            break
        time.sleep(0.25)
    
    if not ready:
        return None
    
    # 3. 重试一次
    try:
        result = retry_call()
        if "error" not in json.loads(result):
            _server_error_counts[server_name] = 0
            return result
    except Exception:
        pass
    
    return None
```

**Session 过期检测**：
```python
_SESSION_EXPIRED_MARKERS = (
    "invalid or expired session",
    "expired session",
    "session expired",
    "session not found",
    "unknown session",
    "closedresourceerror",
    "transport is closed",
    "connection closed",
    "broken pipe",
)

def _is_session_expired_error(exc):
    msg = str(exc).lower()
    return any(marker in msg for marker in _SESSION_EXPIRED_MARKERS)
```

#### **4. 凭证脱敏**

```python
# tools/mcp_tool.py:L268-280, L306-312
_CREDENTIAL_PATTERN = re.compile(
    r"(?:"
    r"ghp_[A-Za-z0-9_]{1,255}"           # GitHub PAT
    r"|sk-[A-Za-z0-9_]{1,255}"           # OpenAI-style key
    r"|Bearer\s+\S+"                      # Bearer token
    r"|token=[^\s&,;\"']{1,255}"         # token=...
    r"|key=[^\s&,;\"']{1,255}"           # key=...
    r"|API_KEY=[^\s&,;\"']{1,255}"       # API_KEY=...
    r"|password=[^\s&,;\"']{1,255}"      # password=...
    r"|secret=[^\s&,;\"']{1,255}"        # secret=...
    r")",
    re.IGNORECASE,
)

def _sanitize_error(text: str) -> str:
    """Strip credential-like patterns from error text."""
    return _CREDENTIAL_PATTERN.sub("[REDACTED]", text)
```

**示例**：
```python
# 原始错误消息
error = "Authentication failed: token=ghp_abc123xyz456 is invalid"

# 脱敏后
sanitized = _sanitize_error(error)
# "Authentication failed: token=[REDACTED] is invalid"
```

---

### 6.4 图片内容支持

MCP 工具可以返回图片（如截图、图表），Hermes 通过 **MEDIA 标签**自动渲染：

```python
# tools/mcp_tool.py:L443-484
def _cache_mcp_image_block(block) -> str:
    """Cache an MCP ImageContent block and return MEDIA:<path> tag."""
    import base64
    
    data = getattr(block, "data", None)
    mime_type = getattr(block, "mimeType", None)
    
    if data is None or not mime_type.startswith("image/"):
        return ""
    
    try:
        raw_bytes = base64.b64decode(data)
    except Exception as exc:
        logger.warning("MCP image block decode failed: %s", exc)
        return ""
    
    try:
        from gateway.platforms.base import cache_image_from_bytes
        image_path = cache_image_from_bytes(
            raw_bytes,
            ext=_mcp_image_extension_for_mime_type(mime_type)
        )
    except Exception as exc:
        logger.warning("MCP image block cache failed: %s", exc)
        return ""
    
    return f"MEDIA:{image_path}"
```

**使用场景**：
- Playwright MCP 服务器返回网页截图
- Blockbench MCP 服务器返回 3D 模型预览
- 数据可视化 MCP 服务器返回图表

**示例**：
```python
# MCP 服务器返回
result.content = [
    TextContent(text="Here's the screenshot:"),
    ImageContent(
        mimeType="image/png",
        data="iVBORw0KGgoAAAANSUhEUgAA..."  # base64
    )
]

# Hermes 处理后
{
  "result": "Here's the screenshot:\nMEDIA:/tmp/hermes-images/screenshot_abc123.png"
}

# Gateway 渲染时识别 MEDIA: 标签并显示图片
```

---

### 6.5 结构化内容（structuredContent）

MCP 协议支持同时返回**文本内容**和**结构化数据**：

```python
# tools/mcp_tool.py:L2236-2248
structured = getattr(result, "structuredContent", None)
if structured is not None:
    if text_result:
        return json.dumps({
            "result": text_result,
            "structuredContent": structured,
        })
    return json.dumps({"result": structured})
return json.dumps({"result": text_result})
```

**示例**：
```python
# MCP 服务器返回
CallToolResult(
    content=[TextContent(text="Found 3 repositories")],
    structuredContent={
        "repositories": [
            {"name": "hermes-agent", "stars": 1234},
            {"name": "fastagent", "stars": 567},
            {"name": "crewAI", "stars": 890}
        ],
        "total_count": 3
    }
)

# Hermes 返回给 Agent
{
  "result": "Found 3 repositories",
  "structuredContent": {
    "repositories": [...],
    "total_count": 3
  }
}
```

**用途**：
- Agent 可以阅读文本获取摘要
- 后续工具可以使用结构化数据进行精确操作
- 避免从非结构化文本中解析数据

---

## 7. 与原生工具对比

### 7.1 对比矩阵

| 特性 | MCP 工具 | 原生工具 |
|------|---------|---------|
| **开发难度** | 低(标准协议) | 中(需了解 registry) |
| **部署方式** | 独立进程 | 内置 Python 模块 |
| **更新频率** | 社区维护 | Hermes 团队维护 |
| **性能** | 中(进程间通信) | 高(直接调用) |
| **生态丰富度** | ✅ 100+ servers | ⚠️ 40+ tools |
| **安全性** | ✅ OAuth 支持 | ⚠️ API keys |
| **适用场景** | 第三方服务集成 | 核心功能 |

### 7.2 选择建议

**使用 MCP 工具当**:
- ✅ 需要集成第三方服务(GitHub、Slack、Notion等)
- ✅ 希望利用社区生态
- ✅ 需要 OAuth 认证

**使用原生工具当**:
- ✅ 核心功能(read_file、terminal等)
- ✅ 性能敏感
- ✅ 简单 API key 认证即可

---


## 8. MCP Sampling 支持

### 8.1 什么是 MCP Sampling?

**MCP Sampling** 允许 MCP Server 主动向 Client (Hermes Agent) 请求 LLM 补全,实现双向交互:

```
传统模式: Hermes → MCP Server (调用工具)
Sampling模式: MCP Server → Hermes (请求 LLM 推理)
```

**典型场景**:
- MCP Server 需要理解用户意图 (例如: GitHub PR 审查建议)
- MCP Server 需要生成自然语言回复 (例如: Slack 智能回复)
- MCP Server 需要决策下一步操作 (例如: 数据库查询优化建议)

### 8.2 Sampling 配置

```yaml
# ~/.hermes/config.yaml

mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
    
    # Sampling 配置
    sampling:
      enabled: true              # 启用 Sampling
      model: "gemini-3-flash"    # 使用的模型 (可选)
      max_tokens_cap: 4096       # 最大 Token 数
      timeout: 30                # LLM 调用超时 (秒)
      max_rpm: 10                # 每分钟最大请求数
      allowed_models: []         # 允许的模型白名单 (空=全部)
      max_tool_rounds: 5         # 工具循环次数 (0=禁用)
      log_level: "info"          # 审计日志级别
```

### 8.3 Sampling 流程

```mermaid
sequenceDiagram
    participant Server as MCP Server
    participant Hermes as Hermes Agent
    participant LLM as LLM API
    
    Server->>Hermes: sampling/createMessage request
    Hermes->>Hermes: 检查权限 + 限流
    Hermes->>LLM: 调用 LLM (使用配置的 model)
    LLM-->>Hermes: 返回补全结果
    Hermes->>Server: CreateMessageResult
    
    alt 需要工具调用
        Server->>Hermes: tool call request
        Hermes->>Server: 执行工具
        Server->>Hermes: 工具结果
        Hermes->>LLM: 继续推理 (max_tool_rounds)
    end
```

### 8.4 安全机制

**1. 权限控制**:

```python
# tools/mcp_tool.py

def _handle_sampling_request(self, server_name: str, request: dict):
    """处理 MCP Server 的 Sampling 请求"""
    
    config = self._get_server_config(server_name)
    
    # 检查是否启用
    if not config.get("sampling", {}).get("enabled", False):
        raise PermissionError(
            f"Sampling is disabled for server '{server_name}'"
        )
    
    # 检查模型白名单
    allowed = config["sampling"].get("allowed_models", [])
    requested_model = request.get("model")
    
    if allowed and requested_model not in allowed:
        raise PermissionError(
            f"Model '{requested_model}' not in allowed list for '{server_name}'"
        )
```

**2. 限流保护**:

```python
def _check_rate_limit(self, server_name: str):
    """检查 RPM 限制"""
    
    config = self._get_server_config(server_name)
    max_rpm = config["sampling"].get("max_rpm", 10)
    
    now = time.time()
    window_start = now - 60  # 1分钟窗口
    
    # 统计最近 1 分钟的请求数
    recent_requests = [
        ts for ts in self._sampling_timestamps[server_name]
        if ts > window_start
    ]
    
    if len(recent_requests) >= max_rpm:
        raise RateLimitError(
            f"Sampling rate limit exceeded for '{server_name}': "
            f"{len(recent_requests)}/{max_rpm} RPM"
        )
    
    # 记录本次请求
    self._sampling_timestamps[server_name].append(now)
```

**3. Token 预算**:

```python
def _enforce_token_cap(self, server_name: str, prompt_tokens: int):
    """强制 Token 上限"""
    
    config = self._get_server_config(server_name)
    max_tokens = config["sampling"].get("max_tokens_cap", 4096)
    
    if prompt_tokens > max_tokens:
        raise TokenLimitError(
            f"Prompt exceeds token cap for '{server_name}': "
            f"{prompt_tokens} > {max_tokens}"
        )
```

---

## 9. 性能优化与监控

### 9.1 连接复用

**问题**: 每次工具调用都重新连接 MCP Server 会导致:
- ❌ 启动延迟 (~500ms-2s)
- ❌ 资源浪费 (进程创建/销毁)
- ❌ 状态丢失 (会话上下文)

**解决方案**: 长连接 + 后台事件循环

```python
# tools/mcp_tool.py

class MCPServerManager:
    def __init__(self):
        # 后台事件循环 (守护线程)
        self._mcp_loop = asyncio.new_event_loop()
        self._mcp_thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="MCP-EventLoop",
        )
        self._mcp_thread.start()
        
        # 服务器实例缓存
        self._servers: Dict[str, MCPServerInstance] = {}
    
    def _run_loop(self):
        """运行后台事件循环"""
        asyncio.set_event_loop(self._mcp_loop)
        self._mcp_loop.run_forever()
    
    async def get_or_create_server(self, server_name: str) -> ClientSession:
        """获取或创建 MCP Server 连接"""
        
        if server_name in self._servers:
            return self._servers[server_name].session
        
        # 创建新连接
        session = await self._connect_to_server(server_name)
        self._servers[server_name] = MCPServerInstance(session)
        
        return session
```

### 9.2 自动重连

```python
async def _connect_with_retry(self, server_name: str, max_retries: int = 5):
    """带指数退避的自动重连"""
    
    for attempt in range(max_retries):
        try:
            session = await self._create_session(server_name)
            logger.info("Connected to MCP server: %s", server_name)
            return session
        
        except Exception as e:
            wait_time = min(2 ** attempt * 1, 30)  # 指数退避,最大30s
            
            logger.warning(
                "Failed to connect to '%s' (attempt %d/%d): %s. "
                "Retrying in %.1fs...",
                server_name, attempt + 1, max_retries, e, wait_time
            )
            
            await asyncio.sleep(wait_time)
    
    raise ConnectionError(
        f"Failed to connect to MCP server '{server_name}' after {max_retries} attempts"
    )
```

### 9.3 错误消息脱敏

**问题**: MCP Server 的错误消息可能包含敏感信息 (API Keys、路径等)

**解决方案**: 自动脱敏

```python
def _sanitize_error_message(self, error: str, server_name: str) -> str:
    """脱敏错误消息中的敏感信息"""
    
    config = self._get_server_config(server_name)
    
    # 移除环境变量中的密钥
    for key, value in config.get("env", {}).items():
        if "KEY" in key.upper() or "TOKEN" in key.upper() or "SECRET" in key.upper():
            error = error.replace(value, "***REDACTED***")
    
    # 移除常见密钥模式
    error = re.sub(r'ghp_[a-zA-Z0-9]{36}', '***GITHUB_TOKEN***', error)
    error = re.sub(r'sk-[a-zA-Z0-9]{48}', '***API_KEY***', error)
    error = re.sub(r'Bearer [a-zA-Z0-9._-]+', 'Bearer ***TOKEN***', error)
    
    return error
```

### 9.4 监控指标

```python
class MCPMetrics:
    def __init__(self):
        self.call_count = 0
        self.error_count = 0
        self.total_latency = 0.0
        self.reconnection_count = 0
    
    def record_call(self, latency: float, success: bool):
        self.call_count += 1
        self.total_latency += latency
        if not success:
            self.error_count += 1
    
    def record_reconnection(self):
        self.reconnection_count += 1
    
    def get_stats(self) -> dict:
        return {
            "total_calls": self.call_count,
            "error_rate": self.error_count / max(self.call_count, 1),
            "avg_latency_ms": (self.total_latency / max(self.call_count, 1)) * 1000,
            "reconnections": self.reconnection_count,
        }
```

**查看 MCP 统计**:

```bash
hermes mcp stats

# 输出示例:
# === MCP Server Stats ===
# Connected Servers: 3
# Total Calls: 156
# Error Rate: 2.1%
# Avg Latency: 245ms
# Reconnections: 5
#
# Per-Server:
#   github: 89 calls, 1.1% errors, 180ms avg
#   slack: 45 calls, 4.4% errors, 320ms avg
#   postgresql: 22 calls, 0% errors, 150ms avg
```

---


## 10. 最佳实践

### 10.1 配置管理

**✅ 推荐**: 使用环境变量注入敏感信息

```yaml
# ~/.hermes/config.yaml

mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}  # ✅ 从环境变量读取
```

```bash
# 设置环境变量
export GITHUB_TOKEN="ghp_xxx"
hermes start
```

**❌ 避免**: 硬编码密钥

```yaml
# ❌ 不要这样做!
mcp_servers:
  github:
    env:
      GITHUB_TOKEN: "ghp_abc123..."  # 泄露风险!
```

### 10.2 超时设置

根据服务器类型调整超时:

```yaml
mcp_servers:
  # 本地文件系统 - 快速响应
  filesystem:
    timeout: 30          # 30s 足够
    connect_timeout: 10  # 10s 连接
  
  # GitHub API - 中等延迟
  github:
    timeout: 120         # 2min (API 限流)
    connect_timeout: 60  # 1min
  
  # 远程数据库 - 可能慢查询
  postgresql:
    timeout: 300         # 5min (复杂查询)
    connect_timeout: 30  # 30s
```

### 10.3 错误处理

**在 Agent Prompt 中说明 MCP 限制**:

```markdown
# MCP Tool Usage Guidelines

When using MCP tools:

1. **Check availability first**: Not all MCP servers may be connected.
   Use `mcp_list_servers` to see what's available.

2. **Handle errors gracefully**: MCP calls can fail due to:
   - Network issues
   - Authentication failures
   - Rate limiting
   - Server downtime

3. **Retry strategy**: If an MCP call fails, wait 5 seconds and retry once.
   If it fails again, report the error to the user.

4. **Timeout awareness**: Some MCP operations (e.g., database queries) 
   can take up to 5 minutes. Be patient and inform the user.
```

### 10.4 性能优化

**1. 批量操作**:

```python
# ❌ 低效: 逐个调用
for file in files:
    mcp_call("filesystem", "read_file", {"path": file})

# ✅ 高效: 批量读取 (如果 MCP Server 支持)
mcp_call("filesystem", "read_multiple_files", {"paths": files})
```

**2. 缓存结果**:

```python
# 对于不变的数据,缓存结果
if cache.has("github_repos"):
    repos = cache.get("github_repos")
else:
    repos = mcp_call("github", "list_repositories")
    cache.set("github_repos", repos, ttl=3600)  # 缓存 1 小时
```

**3. 并行调用**:

```python
# 并发调用多个 MCP Servers
import asyncio

async def fetch_all():
    github_task = asyncio.create_task(
        mcp_call_async("github", "get_pr_details", {"pr_id": 123})
    )
    slack_task = asyncio.create_task(
        mcp_call_async("slack", "get_channel_info", {"channel": "general"})
    )
    
    github_result, slack_result = await asyncio.gather(
        github_task, slack_task
    )
    
    return {"github": github_result, "slack": slack_result}
```

### 10.5 安全考虑

**1. 最小权限原则**:

```yaml
# 只授予必要的权限
mcp_servers:
  github:
    env:
      # ❌ 不要使用 admin token
      # GITHUB_TOKEN: "ghp_admin_xxx"
      
      # ✅ 使用只读 token
      GITHUB_TOKEN: "ghp_readonly_xxx"
```

**2. 网络隔离**:

```yaml
# 限制 MCP Server 的网络访问
mcp_servers:
  internal_api:
    url: "https://internal.company.com/mcp"
    # ✅ 通过 VPN/内网访问
    # ❌ 不要暴露到公网
```

**3. 审计日志**:

```yaml
# 启用详细日志
logging:
  level: INFO
  mcp_audit: true  # 记录所有 MCP 调用
```

```bash
# 查看 MCP 审计日志
tail -f ~/.hermes/logs/mcp-audit.log

# 输出示例:
# [2026-04-25 10:30:15] CALL github.list_repositories by user=admin
# [2026-04-25 10:30:16] RESULT github.list_repositories (245ms, success)
# [2026-04-25 10:30:20] CALL postgresql.execute_query by user=admin
# [2026-04-25 10:30:22] RESULT postgresql.execute_query (1.8s, success)
```

---

## 总结

Hermes MCP 集成的核心优势:

1. **生态兼容** - 接入 100+ MCP servers
2. **OAuth 支持** - 安全的用户授权
3. **动态发现** - 自动注册工具
4. **标准化** - 统一调用接口
5. **灵活配置** - YAML + 环境变量
6. **Sampling 支持** - MCP Server 可请求 LLM 推理
7. **长连接复用** - 后台事件循环,避免重复连接
8. **自动重连** - 指数退避,最多 5 次重试
9. **安全脱敏** - 自动移除错误消息中的密钥
10. **监控完善** - 实时统计 + 审计日志

通过这些设计,Hermes 实现了**开放、安全、可扩展的 MCP 集成**。

---

**最后更新**: 2026-04-25 (补充 Sampling、性能优化、最佳实践)  
**维护者**: Hermes Agent Community  
**相关文档**: 
- [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) - 原生工具系统
- [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) - 外部记忆提供者
- [PLUGINS_SYSTEM.md](PLUGINS_SYSTEM.md) - 插件系统
