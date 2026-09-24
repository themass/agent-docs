# OpenHarness Permissions & MCP深度分析

> **版本**: v1.1  
> **最后更新**: 2026-06-08（对照 `permissions/checker.py` 修订）  
> **包版本**: 0.1.9 · **同步说明**: [ARCHITECTURE_DOCS_SYNC.md](./ARCHITECTURE_DOCS_SYNC.md)
> **作者**: OpenHarness Community  
> **文档类型**: 技术架构设计(权限系统与MCP集成专项)

---

## 📋 目录

- [1. 概述](#1-概述)
- [2. 权限系统架构](#2-权限系统架构)
  - [2.1 PermissionMode定义](#21-permissionmode定义)
  - [2.2 PermissionChecker核心逻辑](#22-permissionchecker核心逻辑)
  - [2.3 敏感路径保护](#23-敏感路径保护)
- [3. 权限决策流程](#3-权限决策流程)
  - [3.1 评估优先级](#31-评估优先级)
  - [3.2 Path Rules机制](#32-path-rules机制)
  - [3.3 Command Deny Patterns](#33-command-deny-patterns)
- [4. 权限模式详解](#4-权限模式详解)
  - [4.1 DEFAULT模式](#41-default模式)
  - [4.2 PLAN模式](#42-plan模式)
  - [4.3 FULL_AUTO模式](#43-full_auto模式)
- [5. UI集成](#5-ui集成)
  - [5.1 Permission Dialog](#51-permission-dialog)
  - [5.2 用户交互流程](#52-用户交互流程)
- [6. MCP系统集成](#6-mcp系统集成)
  - [6.1 MCP架构概览](#61-mcp架构概览)
  - [6.2 MCP Client Manager](#62-mcp-client-manager)
  - [6.3 Stdio Transport](#63-stdio-transport)
  - [6.4 HTTP Transport](#64-http-transport)
- [7. MCP工具动态注册](#7-mcp工具动态注册)
  - [7.1 工具发现流程](#71-工具发现流程)
  - [7.2 McpToolAdapter实现](#72-mcptooladapter实现)
  - [7.3 资源访问机制](#73-资源访问机制)
- [8. 安全最佳实践](#8-安全最佳实践)
  - [8.1 敏感路径保护](#81-敏感路径保护)
  - [8.2 命令过滤](#82-命令过滤)
  - [8.3 MCP认证管理](#83-mcp认证管理)
- [9. 竞品对比](#9-竞品对比)
- [10. 典型使用场景](#10-典型使用场景)

---

## 1. 概述

### 1.1 职责定位

**Permissions模块**负责OpenHarness的权限控制系统,决定Agent的工具调用是否需要用户审批。

**核心职责**:
1. **权限评估**: 根据PermissionMode和规则判断工具是否可执行
2. **敏感路径保护**: 硬编码禁止访问SSH密钥、AWS凭证等敏感文件
3. **模式切换**: 支持DEFAULT/PLAN/FULL_AUTO三种模式
4. **Path Rules**: 基于glob模式的细粒度路径控制
5. **Command Deny**: 阻止危险命令如`rm -rf /`

**MCP (Model Context Protocol)模块**负责与外部MCP Servers通信,扩展Agent能力。

**核心职责**:
1. **连接管理**: 支持Stdio和HTTP两种Transport
2. **工具发现**: 自动列举MCP Server提供的tools和resources
3. **工具调用**: 代理Agent请求到MCP Server
4. **资源读取**: 访问MCP资源(文件、API响应等)
5. **状态监控**: 跟踪每个Server的连接状态

**核心价值**:
1. **安全防护**: 多层防御(敏感路径+命令过滤+权限模式)
2. **灵活控制**: 3种模式适应不同场景(开发/生产/自动化)
3. **生态扩展**: MCP标准接入大量外部Services(GitHub/Slack/Database等)
4. **无缝集成**: MCP Tools与内置Tools使用方式完全一致

---

## 2. 权限系统架构

### 2.1 PermissionMode定义

**源码**: `permissions/modes.py`

```python
from enum import Enum

class PermissionMode(str, Enum):
    """Supported permission modes."""
    
    DEFAULT = "default"      # 默认模式:只读自动允许,写操作询问
    PLAN = "plan"            # 计划模式:阻止所有修改操作
    FULL_AUTO = "full_auto"  # 全自动模式:所有操作自动允许
```

**模式对比**:

| 模式 | 只读工具 | 写工具 | Bash命令 | 适用场景 |
|------|---------|--------|----------|----------|
| **DEFAULT** | ✅ 自动允许 | ⚠️ 询问用户 | ⚠️ 询问用户 | 日常开发(默认) |
| **PLAN** | ✅ 自动允许 | ❌ 阻止 | ❌ 阻止 | 代码审查/规划阶段 |
| **FULL_AUTO** | ✅ 自动允许 | ✅ 自动允许 | ✅ 自动允许 | 可信环境/自动化 |

#### **系统提示词动态指示 (Dynamic Prompt Permission Mode Guidance)**
为了确保 LLM 了解当前会话拥有的真实执行权限，OpenHarness 将当前运行期的权限状态（`PermissionMode`）动态注入到系统提示词中：
- **注入实现**：在 `src/openharness/prompts/context.py` 中，`build_runtime_system_prompt` 函数会在初始化或重构系统提示词时调用 `_build_permission_mode_section` 动态追加当前权限指引（如 Plan 模式下向模型警告“不要调用任何写工具，只能执行只读工具进行分析规划”）。
- **动态重载机制**：在 UI 的交互中，当用户使用斜杠命令（例如 `/plan on`）切换权限模式时，系统会在 `src/openharness/ui/runtime.py` 中调用 `refresh_runtime_client`，这会动态地刷新底层的运行期客户端设置（包括 model、effort 级和新实例化权限检查器 `PermissionChecker`），并自动重新构造系统提示词，让模型在下一轮 ReAct 交互中即时感知到权限模式的变更。

### 2.2 PermissionChecker核心逻辑

**源码**: `permissions/checker.py:57-156`

`PermissionChecker.evaluate()` 按以下顺序评估（**非**旧文档所称的「9 层」；字段名以源码为准）：

| 步骤 | 检查 | 配置字段 / 行为 |
|------|------|-----------------|
| 1 | 内置敏感路径 `SENSITIVE_PATH_PATTERNS` | 硬编码 fnmatch，**不可覆盖** |
| 2 | 工具 deny | `PermissionSettings.denied_tools` |
| 3 | 工具 allow | `PermissionSettings.allowed_tools` |
| 4 | 路径规则 | `path_rules[]` → `PathRule(pattern, allow: bool)` |
| 5 | 命令 deny | `PermissionSettings.denied_commands`（fnmatch） |
| 6 | `FULL_AUTO` 模式 | 允许所有 |
| 7 | 只读工具 | `is_read_only=True` → 允许 |
| 8 | `PLAN` 模式 | **阻止所有 mutating 工具**（非 per-tool 白名单） |
| 9 | `DEFAULT` 模式 | mutating → `requires_confirmation=True` |

返回类型：`PermissionDecision(allowed, requires_confirmation, reason)`（**非** `requires_approval`）。

#### 以下为历史伪代码（已过时，仅供对照）

```python
# permissions/checker.py - 完整的9层权限检查实现

from pathlib import Path
import fnmatch
from typing import Literal

PermissionMode = Literal["DEFAULT", "PLAN", "FULL_AUTO"]

class PermissionDecision:
    """权限决策结果"""
    def __init__(self, allowed: bool, reason: str, requires_approval: bool = False):
        self.allowed = allowed
        self.reason = reason
        self.requires_approval = requires_approval

# Layer 1: 敏感路径保护(硬编码,不可覆盖)
SENSITIVE_PATH_PATTERNS = (
    "*/.ssh/*",              # SSH密钥
    "*/.aws/credentials",    # AWS凭证
    "*/.aws/config",
    "*/.config/gcloud/*",    # GCP凭证
    "*/.azure/*",            # Azure凭证
    "*/.gnupg/*",            # GPG密钥
    "*/.docker/config.json", # Docker凭证
    "*/.kube/config",        # Kubernetes凭证
    "*/.openharness/credentials.json",  # OpenHarness凭证
    "*/.openharness/copilot_auth.json",
    "/etc/shadow",           # 系统密码文件
    "/etc/passwd",
)

class PermissionChecker:
    def __init__(self, settings):
        self._settings = settings
        self._deny_list = settings.permissions.deny_list or []
        self._allow_list = settings.permissions.allow_list or []
        self._path_rules = settings.permissions.path_rules or []
        self._command_deny_list = settings.permissions.command_deny_list or []
    
    def evaluate(
        self,
        tool_name: str,
        *,
        is_read_only: bool,
        file_path: str | None = None,
        command: str | None = None,
    ) -> PermissionDecision:
        """
        9层权限检查链(从高到低优先级):
        
        Layer 1: Sensitive Path Protection (硬编码保护,不可覆盖)
        Layer 2: Deny List (用户配置的禁止路径/命令)
        Layer 3: Allow List (用户配置的允许路径/命令)
        Layer 4: Path Rules (通配符规则)
        Layer 5: Command Deny List (禁止的危险命令)
        Layer 6: FULL_AUTO Mode (自动允许所有工具)
        Layer 7: Read-only Tools (只读工具始终允许)
        Layer 8: PLAN Mode (规划模式,仅允许read/grep/glob)
        Layer 9: DEFAULT Mode (写工具需要用户审批)
        """
        
        # ========== Layer 1: 敏感路径保护 ==========
        if file_path:
            for candidate_path in _policy_match_paths(file_path):
                for pattern in SENSITIVE_PATH_PATTERNS:
                    if fnmatch.fnmatch(candidate_path, pattern):
                        return PermissionDecision(
                            allowed=False,
                            reason=f"Blocked: {file_path} matches sensitive path pattern '{pattern}'. "
                                   f"This path is protected and cannot be overridden."
                        )
        
        # ========== Layer 2: Deny List ==========
        if file_path and file_path in self._deny_list:
            return PermissionDecision(
                allowed=False,
                reason=f"Blocked: {file_path} is in the deny list"
            )
        
        if command and command in self._deny_list:
            return PermissionDecision(
                allowed=False,
                reason=f"Blocked: command '{command}' is in the deny list"
            )
        
        # ========== Layer 3: Allow List ==========
        if file_path and file_path in self._allow_list:
            return PermissionDecision(
                allowed=True,
                reason=f"Allowed: {file_path} is in the allow list"
            )
        
        if command and command in self._allow_list:
            return PermissionDecision(
                allowed=True,
                reason=f"Allowed: command '{command}' is in the allow list"
            )
        
        # ========== Layer 4: Path Rules (通配符) ==========
        if file_path:
            for rule in self._path_rules:
                if fnmatch.fnmatch(file_path, rule.pattern):
                    if rule.action == "allow":
                        return PermissionDecision(
                            allowed=True,
                            reason=f"Allowed: {file_path} matches path rule '{rule.pattern}'"
                        )
                    elif rule.action == "deny":
                        return PermissionDecision(
                            allowed=False,
                            reason=f"Blocked: {file_path} matches path rule '{rule.pattern}'"
                        )
        
        # ========== Layer 5: Command Deny List ==========
        if command:
            for dangerous_pattern in self._command_deny_list:
                if fnmatch.fnmatch(command, dangerous_pattern):
                    return PermissionDecision(
                        allowed=False,
                        reason=f"Blocked: command matches dangerous pattern '{dangerous_pattern}'"
                    )
        
        # ========== Layer 6: FULL_AUTO Mode ==========
        if self._settings.mode == PermissionMode.FULL_AUTO:
            return PermissionDecision(
                allowed=True,
                reason="FULL_AUTO mode allows all tools without approval"
            )
        
        # ========== Layer 7: Read-only Tools ==========
        if is_read_only:
            return PermissionDecision(
                allowed=True,
                reason="Read-only tools are always allowed"
            )
        
        # ========== Layer 8: PLAN Mode ==========
        if self._settings.mode == PermissionMode.PLAN:
            plan_mode_allowed_tools = {"read_file", "grep", "glob", "ls", "cat"}
            if tool_name in plan_mode_allowed_tools:
                return PermissionDecision(
                    allowed=True,
                    reason=f"PLAN mode allows read-only tool '{tool_name}'"
                )
            return PermissionDecision(
                allowed=False,
                reason=f"PLAN mode blocks write/exec tool '{tool_name}'. "
                       f"Switch to DEFAULT mode to allow this tool.",
                requires_approval=False,  # PLAN模式下不允许审批,必须切换模式
            )
        
        # ========== Layer 9: DEFAULT Mode (需要用户审批) ==========
        return PermissionDecision(
            allowed=False,
            reason=f"DEFAULT mode requires user approval for tool '{tool_name}'",
            requires_approval=True,  # 用户可以审批通过
        )


def _policy_match_paths(file_path: str) -> list[str]:
    """生成所有可能的路径匹配候选(绝对路径、相对路径、basename)"""
    path = Path(file_path)
    candidates = [str(path)]
    
    # 如果是相对路径,添加绝对路径
    if not path.is_absolute():
        candidates.append(str(Path.cwd() / path))
    
    # 添加basename
    candidates.append(path.name)
    
    return candidates
```

**评估顺序详解**（见上表）：

**关键设计决策**:
- ✅ **早期返回**: 一旦匹配规则立即返回,性能优化
- ✅ **详细原因**: 每个决策都附带人类可读的原因说明
- ✅ **不可覆盖**: Step 1敏感路径保护始终生效
- ✅ **多路径匹配**: `_policy_match_paths()`生成多个候选路径,确保匹配准确

### 2.3 敏感路径保护

**硬编码保护列表** (`permissions/checker.py:18-37`):

```python
SENSITIVE_PATH_PATTERNS: tuple[str, ...] = (
    # SSH keys and config
    "*/.ssh/*",
    # AWS credentials
    "*/.aws/credentials", "*/.aws/config",
    # GCP credentials
    "*/.config/gcloud/*",
    # Azure credentials
    "*/.azure/*",
    # GPG keys
    "*/.gnupg/*",
    # Docker credentials
    "*/.docker/config.json",
    # Kubernetes credentials
    "*/.kube/config",
    # OpenHarness own credential stores
    "*/.openharness/credentials.json",
    "*/.openharness/copilot_auth.json",
)
```

**防护机制**:
- 🔒 **防御Prompt注入**: 即使Agent被恶意Prompt诱导,也无法读取密钥
- 🔒 **Defense-in-Depth**: 即使用户配置错误,硬编码保护仍然生效
- 🔒 **不可覆盖**: 无法通过allowed_tools或path_rules绕过

### 2.4 Windows (win32) 平台兼容性与锁硬化
为了支持在 Windows 环境下的高稳定运行，系统针对平台检测及 Swarm 文件锁定进行了优化硬化：
- **win32 别名识别**：平台检测模块 `src/openharness/platforms.py` 中，`detect_platform` 不仅检测标准的 `windows` 标识，还支持识别 `win32` 别名作为 Windows 操作系统，确保 Windows 环境判定覆盖更全面。
- **锁定模块异常安全包装**：在 `src/openharness/utils/file_lock.py` 中，排他锁实现需要导入操作系统特定模块（Linux 下使用 `fcntl`，Windows 下使用 `msvcrt`）。如果这些底层的原生锁定模块由于运行平台限制导入失败（例如测试环境 Mocking 或非标准 Python 裁剪版），系统会将捕获到的 `ImportError` 统一转换并包装为 `SwarmLockUnavailableError` 抛出，而不是直接泄漏原始异常，这极大地改善了在跨平台环境和测试链条下 Swarm 锁检测的鲁棒性。

---

## 3. 权限决策流程

### 3.1 评估优先级

`evaluate()` 从步骤 1 起顺序执行，**任一步返回即停止**。这种设计确保了:
- **安全性优先**: 敏感路径和Deny List最先检查
- **灵活性**: 用户规则可以覆盖Mode默认行为
- **性能优化**: 早期返回避免不必要检查

### 3.2 Path Rules机制

**配置示例** (`~/.openharness/config.yaml`):

```yaml
permissions:
  path_rules:
    # 禁止访问测试目录
    - pattern: "*/tests/fixtures/*"
      allow: false
    
    # 允许访问文档目录
    - pattern: "*/docs/**"
      allow: true
```

**Glob模式支持**: `*` (任意字符), `**` (递归子目录), `?` (单字符), `[seq]` (字符集)

### 3.3 Command Deny Patterns

**配置示例**:

```yaml
permissions:
  denied_commands:
    - "rm -rf /"
    - "rm -rf /*"
    - "mkfs.*"
    - "dd if=* of=/dev/*"
```

**防护的危险命令**: `rm -rf /` (删除根目录), `mkfs.*` (格式化磁盘), `dd` (直接写设备)

---

## 4. 权限模式详解

### 4.1 DEFAULT模式

**行为**:
- ✅ **只读工具**: 自动允许(`read_file`, `grep`, `glob`)
- ⚠️ **写工具**: 需要用户确认(`write_file`, `edit_file`, `bash`)

**适用场景**: 日常开发、代码审查、生产环境

### 4.2 PLAN模式

**行为**:
- ✅ **只读工具**: 自动允许
- ❌ **所有写工具**: 阻止(包括`write_file`, `bash`, `edit_file`)

**适用场景**: 规划阶段、Code Review、学习模式

**退出方式**: `/exit_plan_mode` Slash命令

### 4.3 FULL_AUTO模式

**行为**:
- ✅ **所有工具**: 自动允许(包括`bash`, `write_file`)
- ⚠️ **例外**: 敏感路径保护仍然生效(不可覆盖)

**适用场景**: 自动化脚本、沙箱环境、快速原型

**风险提示**: 仅在可信环境或沙箱中使用!

---

## 5. UI集成

### 5.1 Permission Dialog

当PermissionChecker返回`requires_confirmation=True`时,UI显示确认对话框:

```
┌────────────────────────────────────────┐
│ ⚠️ Agent wants to modify a file        │
│                                        │
│ File: src/main.py                      │
│ Action: Write (create/overwrite)       │
│                                        │
│ [Approve] [Deny] [Always approve]     │
└────────────────────────────────────────┘
```

### 5.2 用户交互流程

1. Agent尝试调用工具
2. PermissionChecker评估权限
3. 如需确认,UI显示Dialog
4. 用户选择Approve/Deny/Always approve
5. 执行或拒绝工具调用

---

## 6. MCP系统集成

### 6.1 MCP架构概览

**Model Context Protocol (MCP)**: Anthropic提出的标准协议,允许LLM访问外部资源和服务。

**关键概念区分**:
- **MCP Client**: OpenHarness 中的 `McpClientManager`,负责发起连接和调用(**主进程**)
- **MCP Server**: 外部服务,提供 tools/resources,有两种部署方式:
  - **Stdio Server**: 由 OpenHarness 主进程通过 `subprocess.Popen` 启动的**本地子进程**
  - **HTTP Server**: 独立部署的**远程或本地服务**,OpenHarness 通过 HTTP 连接

**OpenHarness MCP架构**:

```
┌─────────────────────────────────────────────────────────┐
│         OpenHarness CLI (主进程 - Python asyncio)        │
│                                                         │
│  Agent → ToolRegistry → McpClientManager               │
│                              ↓                          │
│              ┌───────────────┴───────────────┐          │
│              ↓                               ↓          │
│     HTTP 连接 (网络)                  Stdio 连接 (本地)  │
│              ↓                               ↓          │
│  ┌─────────────────────┐    ┌──────────────────────┐   │
│  │ Remote/Local MCP    │    │ Local MCP Servers    │   │
│  │ Servers             │    │ (OH启动的子进程)      │   │
│  │ (独立部署,非OH启动)  │    │                      │   │
│  │ • GitHub API        │    │ • Filesystem Server  │   │
│  │ • Slack API         │    │ • Database Server    │   │
│  │ • 可以是localhost   │    │ • Git Server         │   │
│  └─────────────────────┘    └──────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**重要说明**:
- ✅ **所有 MCP 管理逻辑都在主进程**: `McpClientManager`、`ClientSession`、`ToolRegistry`
- ✅ **Stdio Server 是子进程**: 但它是外部程序(如 Node.js),不是 OpenHarness 的代码
- ✅ **HTTP Server 是独立服务**: 完全独立,可能由第三方运营或在本地运行
- ✅ **通信是跨进程/网络的**: stdio 通过管道,HTTP 通过网络

### 6.2 MCP Client Manager

**源码**: `mcp/client.py`

**核心功能**:
1. **连接管理**: `connect_all()`, `reconnect_all()`, `close()`
2. **工具发现**: `list_tools()` → List[McpToolInfo]
3. **资源发现**: `list_resources()` → List[McpResourceInfo]
4. **工具调用**: `call_tool(server_name, tool_name, arguments)` → str
5. **资源读取**: `read_resource(server_name, uri)` → str
6. **状态监控**: `list_statuses()` → List[McpConnectionStatus]

### 6.3 Stdio Transport

**适用场景**: 本地 MCP Server,通过 stdin/stdout 与 OpenHarness 主进程通信

**重要说明**: 
- MCP Server 是**独立的子进程**,不是 OpenHarness 的代码模块
- OpenHarness 主进程通过 `subprocess.Popen` **启动并管理**该子进程
- `ClientSession` 对象存储在 OpenHarness **主进程内存**中
- **必须是本地进程**: stdio 无法跨网络连接远程服务

**配置示例**:

```json
{
  "servers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"],
      "env": {
        "ALLOWED_DIRS": "/home/user/project"
      }
    }
  }
}
```

**连接流程** (在 OpenHarness **主进程**中执行):

1. **启动外部子进程**: 
   ```python
   subprocess.Popen(["npx", "-y", "@modelcontextprotocol/server-filesystem"])
   ```
   - 子进程是**独立的 MCP Server**（通常是 Node.js/Python 程序）
   - OpenHarness 不控制其内部逻辑,仅通过 stdio 通信

2. **在主进程中建立异步流**:
   ```python
   read_stream, write_stream = await stdio_client(StdioServerParameters(...))
   ```
   - 创建 `asyncio.StreamReader/StreamWriter`
   - 用于主进程读写子进程的 stdin/stdout

3. **在主进程中初始化会话**:
   ```python
   session = ClientSession(read_stream, write_stream)
   self._sessions[name] = session  # 存储在主进程内存
   ```
   - **关键点**: `ClientSession` 是主进程的对象,不是子进程的一部分

4. **主进程调用子进程**:
   ```python
   tool_result = await session.list_tools()
   # ↑ 通过 stdio 向子进程发送 JSON-RPC 请求
   # ↑ 子进程处理后通过 stdout 返回结果
   # ↑ 主进程解析响应并返回
   ```

5. **在主进程中注册工具**:
   ```python
   registry.register(McpToolAdapter(mcp_manager, tool_info))
   # ↑ McpToolAdapter 在主进程中持有 Manager 引用
   ```

**进程交互示意**:
```
主进程 (OpenHarness)              子进程 (MCP Server)
     |                                    |
     |--- subprocess.Popen ------------->| 启动
     |                                    |
     |--- JSON-RPC request (stdin) ---->| 接收请求
     |                                    | 处理逻辑
     |                                    | (Node.js/Python)
     |<-- JSON-RPC response (stdout) ---| 返回结果
     |                                    |
     | 解析响应并更新 ToolRegistry        |
```

### 6.4 HTTP Transport

**适用场景**: 远程或本地 MCP Server，通过 **streamable HTTP** 通信（`McpClientManager` 实现 **stdio + HTTP**；`McpWebSocketServerConfig` 类型存在但 client **未实现** WebSocket 连接）

**重要说明**:
- HTTP Server 是**完全独立的服务**,不由 OpenHarness 启动或管理
- 可能是第三方提供的服务(如 GitHub MCP Server),也可能是本地运行的服务
- OpenHarness 仅作为客户端发起 HTTP 请求
- **可以是本地或远程**: HTTP 支持 localhost 和远程服务器

**配置示例**:

```json
{
  "servers": {
    "github": {
      "type": "http",
      "url": "https://api.github.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_TOKEN}"
      }
    },
    "local-database": {
      "type": "http",
      "url": "http://localhost:3000/mcp",
      "headers": {}
    }
  }
}
```

**连接流程** (在 OpenHarness **主进程**中执行):

1. **创建HTTP客户端**: 
   ```python
   http_client = httpx.AsyncClient(headers=config.headers)
   ```
   - 在主进程中创建的异步 HTTP 客户端

2. **建立HTTP流**: 
   ```python
   read_stream, write_stream, _ = await streamable_http_client(url, http_client=http_client)
   ```
   - 创建与服务器的持久连接

3. **在主进程中初始化会话**: 
   ```python
   session = ClientSession(read_stream, write_stream)
   self._sessions[name] = session  # 存储在主进程内存
   ```
   - **关键点**: `ClientSession` 对象存储在 OpenHarness **主进程**内存中

4. **主进程发送HTTP请求**:
   ```python
   tool_result = await session.list_tools()
   # ↑ 通过 HTTP POST 发送 JSON-RPC 请求
   # ↑ 远程/本地服务器处理后返回 HTTP 响应
   # ↑ 主进程解析响应并返回
   ```

5. **在主进程中注册工具**:
   ```python
   registry.register(McpToolAdapter(mcp_manager, tool_info))
   # ↑ McpToolAdapter 在主进程中持有 Manager 引用
   ```

**网络交互示意**:
```
主进程 (OpenHarness)              远程/本地 MCP Server
     |                                    |
     |--- HTTP POST /mcp               -->|  接收请求
     |     Content-Type: application/json |
     |     {"jsonrpc":"2.0",              |
     |      "method":"list_tools",        |
     |      "id":1}                       |
     |                                    |  处理逻辑
     |                                    |  (可能在其他机器)
     |<-- HTTP 200 OK                  ---|  返回响应
     |     {"jsonrpc":"2.0",              |
     |      "result":{"tools":[...]},     |
     |      "id":1}                       |
     |                                    |
     | 解析响应并更新 ToolRegistry        |
```

---

## 7. MCP工具动态注册

### 7.1 工具发现流程

```
Step 1: McpClientManager.connect_all()
  ↓ 遍历所有配置的servers
  ↓ for name, config in server_configs.items():
  
Step 2: 建立连接(stdio或http)
  ↓ session = ClientSession(read_stream, write_stream)
  ↓ await session.initialize()
  
Step 3: 列举工具
  ↓ tool_result = await session.list_tools()
  ↓ tools = [
  ↓   McpToolInfo(
  ↓     server_name=name,
  ↓     name=tool.name,
  ↓     description=tool.description,
  ↓     input_schema=tool.inputSchema
  ↓   )
  ↓   for tool in tool_result.tools
  ↓ ]
  
Step 4: 更新状态
  ↓ self._statuses[name] = McpConnectionStatus(
  ↓   state="connected",
  ↓   tools=tools,
  ↓   resources=resources
  ↓ )
  
Step 5: 动态注册到ToolRegistry
  ↓ for tool_info in mcp_manager.list_tools():
  ↓   registry.register(McpToolAdapter(mcp_manager, tool_info))
```

### 7.2 McpToolAdapter实现

**源码**: `tools/mcp_tool.py`

```python
class McpToolAdapter(BaseTool):
    """Adapter that wraps an MCP tool as an OpenHarness tool."""
    
    def __init__(self, mcp_manager, tool_info: McpToolInfo):
        self.mcp_manager = mcp_manager
        self._tool_info = tool_info
        self.name = f"{tool_info.server_name}_{tool_info.name}"
        self.description = tool_info.description
        self.input_model = self._build_input_model(tool_info.input_schema)
    
    async def execute(self, arguments: BaseModel, context: ToolExecutionContext) -> ToolResult:
        try:
            result = await self.mcp_manager.call_tool(
                server_name=self._tool_info.server_name,
                tool_name=self._tool_info.name,
                arguments=arguments.model_dump(),
            )
            return ToolResult(output=result)
        except Exception as e:
            return ToolResult(output=f"Error: {str(e)}", is_error=True)
```

**特点**:
- ✅ **命名空间**: 工具名格式 `{server_name}_{tool_name}`,避免冲突
- ✅ **Schema转换**: MCP JSON Schema → Pydantic模型
- ✅ **错误处理**: 捕获异常,返回友好错误消息

### 7.3 资源访问机制

**MCP Resources**: 类似文件的资源,可通过URI访问

**示例**:
- `file:///etc/hosts` - 文件系统资源
- `https://api.example.com/data` - HTTP资源
- `db://users/table` - 数据库资源

**访问流程**:
```python
# Agent调用
read_mcp_resource(server_name="github", uri="https://api.github.com/repos/langchain-ai/openharness")

# McpClientManager处理
result = await session.read_resource(uri)
text = result.contents[0].text

# 返回给Agent
return ToolResult(output=text)
```

### 7.4 进程模型总结

**常见误解澄清**:

❌ **错误理解**: "MCP Server 是 OpenHarness 的子模块,运行在子进程中"

✅ **正确理解**:
```
OpenHarness 主进程 (Python asyncio)
  ├─ McpClientManager (主进程内存)
  │    ├─ ClientSession for GitHub (HTTP 连接 → 远程/本地服务器)
  │    └─ ClientSession for Filesystem (stdio 连接 → 本地子进程)
  │
  ├─ ToolRegistry (主进程内存)
  │    └─ McpToolAdapter 实例 (持有 Manager 引用)
  │
  └─ Agent Loop (主进程)
       └─ 调用工具 → McpToolAdapter.execute() → Manager.call_tool()

外部进程/服务:
  ├─ Filesystem MCP Server (本地子进程,由 OH 启动)
  │    └─ 通过 stdio 与 OH 主进程通信
  │
  └─ GitHub MCP Server (远程 HTTPS 服务,独立部署)
       └─ 通过 HTTP 与 OH 主进程通信
```

**关键要点**:

| 维度 | Stdio Transport | HTTP Transport |
|------|----------------|---------------|
| **MCP Server 位置** | 本地子进程（由 OH 启动） | 远程或本地服务器（独立部署） |
| **谁启动 Server？** | OpenHarness 主进程 | 第三方/运维团队/用户 |
| **通信协议** | stdin/stdout 管道 | HTTP/HTTPS |
| **ClientSession 位置** | **主进程内存** | **主进程内存** |
| **数据解析位置** | **主进程** | **主进程** |
| **生命周期管理** | OH 负责启动/停止 | OH 仅负责连接/断开 |
| **能否远程？** | ❌ 不能（依赖本地进程） | ✅ 可以（通过网络） |

1. **所有 MCP 管理逻辑都在主进程**: `McpClientManager`、`ClientSession`、`ToolRegistry`
2. **Stdio Server 是子进程**: 但它是外部程序(如 Node.js),不是 OpenHarness 的代码
3. **HTTP Server 是独立服务**: 完全独立,可能由第三方运营或在本地运行
4. **通信是跨进程/网络的**: stdio 通过管道,HTTP 通过网络
5. **Agent 无感知**: 对 Agent 来说,MCP 工具与内置工具使用方式完全一致

> **💡 核心原则**
> 
> **无论是 Stdio 还是 HTTP Transport**：
> - ✅ **ClientSession** 始终在 OpenHarness **主进程**内存中
> - ✅ **ToolRegistry** 始终在 OpenHarness **主进程**中
> - ✅ **所有业务逻辑**（权限检查、工具调用、结果处理）都在**主进程**执行
> 
> **区别仅在于通信方式**：
> - **Stdio**: 与本地子进程通过管道通信（子进程由 OH 启动）
> - **HTTP**: 与远程/本地服务器通过网络通信（服务器独立部署）
> 
> **对 Agent 透明**：Agent 调用 MCP 工具时，无需关心底层是 stdio 还是 HTTP，统一通过 `McpToolAdapter` 代理。

---

## 8. 安全最佳实践

### 8.1 敏感路径保护

**原则**: 永远不要信任Agent对敏感文件的访问请求

**防护措施**:
1. **硬编码黑名单**: SENSITIVE_PATH_PATTERNS不可覆盖
2. **最小权限**: 仅授予必要的文件访问权限
3. **审计日志**: 记录所有文件访问尝试

### 8.2 命令过滤

**危险命令示例**:
- `rm -rf /` - 删除根目录
- `mkfs.*` - 格式化磁盘
- `dd if=* of=/dev/*` - 直接写设备
- `chmod 777 /` - 全局可执行

**配置建议**:
```yaml
permissions:
  denied_commands:
    - "rm -rf *"
    - "mkfs.*"
    - "dd *"
    - "> /dev/sd*"
```

### 8.3 MCP认证管理

**原则**: 不要在配置文件中明文存储密钥

**推荐做法**:
```json
{
  "servers": {
    "github": {
      "type": "http",
      "url": "https://api.github.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_TOKEN}"  // 环境变量
      }
    }
  }
}
```

**环境变量注入**:
```bash
export GITHUB_TOKEN=ghp_xxx
openharness
```

### 8.4 Scoped API Key 环境变量解析优先级
在解析大模型 Provider 的 API Key 时，系统设计了精细的专有密钥别名机制，确保多 Profile 共存时能够获取正确的密钥，避免原生环境变量间的串扰：
- **专有前缀优先解析**：系统在 `src/openharness/config/settings.py` 中引入了 `resolve_auth_env_value`，优先解析以 `OPENHARNESS_` 为前缀的 Provider 专有环境变量（例如：`OPENHARNESS_ANTHROPIC_API_KEY`、`OPENHARNESS_OPENAI_API_KEY` 等）。
- **回退与容错**：如果配置的活跃 Profile（例如 `active_profile = "openai-compatible"`）对应的 OpenHarness 专有环境变量未设置，才会回退到标准的 native 环境变量（如 `OPENAI_API_KEY`）或扁平字段。
- **环境遗传**：OpenHarness 专有的 scoped API 密钥（例如 `OPENHARNESS_OPENAI_API_KEY`、`OPENHARNESS_ANTHROPIC_API_KEY`）会自动通过 `build_inherited_env_vars` 注入并转发给生成的 Swarm Teammates，保证 Swarm 子代理具有与主 Coordinator 完全一致的模型访问权限。

---

## 9. 竞品对比

| 维度 | OpenHarness | hermes-agent | deepagents | deer-flow |
|------|-----------|-------------|-----------|----------|
| **权限系统** | ✅ 3种模式+Path Rules | ❌ 无 | ⚠️ Human-in-loop only | ❌ 无 |
| **敏感路径保护** | ✅ 硬编码,不可覆盖 | ❌ 无 | ❌ 无 | ❌ 无 |
| **Command Deny** | ✅ Glob模式过滤 | ❌ 无 | ❌ 无 | ❌ 无 |
| **MCP支持** | ✅ Stdio + HTTP | ❌ 无 | ❌ 无 | ❌ 无 |
| **工具动态注册** | ✅ MCP自动发现 | ❌ 静态 | ❌ 静态 | ❌ 静态 |
| **Permission Sync** | ✅ 父子Agent共享 | ❌ 无 | ❌ 无 | ❌ 无 |

**OpenHarness优势**:
1. **多层防御**: 敏感路径+命令过滤+权限模式三重保护
2. **生态兼容**: 唯一支持MCP的框架,可扩展性强
3. **细粒度控制**: Path Rules实现路径级权限管理
4. **Worker安全**: Permission Sync减少重复询问

---

## 10. 典型使用场景

### 场景1: 日常开发(DEFAULT模式)

```
用户: "Fix the bug in auth.py"
       ↓
Agent尝试: read_file("src/auth.py")
       ↓ PermissionChecker: is_read_only=True → ALLOW
✅ 自动执行

Agent尝试: edit_file("src/auth.py", ...)
       ↓ PermissionChecker: requires_confirmation=True
⚠️ UI显示Dialog: [Approve] [Deny]
       ↓ 用户点击Approve
✅ 执行修改

Agent尝试: bash("pytest tests/test_auth.py")
       ↓ PermissionChecker: requires_confirmation=True
⚠️ UI显示Dialog
       ↓ 用户点击Approve
✅ 运行测试
```

### 场景2: Code Review(PLAN模式)

```
用户: /permissions plan
       ↓
用户: "Review the security of our codebase"
       ↓
Agent尝试: grep(pattern="password", path="src/")
       ✅ 自动执行(只读)

Agent尝试: read_file("src/auth.py")
       ✅ 自动执行(只读)

Agent尝试: write_file("security_report.md", ...)
       ❌ PermissionChecker: mode=PLAN → DENY
       ↓ Agent报告: "I found issues, but cannot create report in PLAN mode"
       
用户: /exit_plan_mode
       ↓
用户: "Now create the report"
       ↓
Agent尝试: write_file("security_report.md", ...)
       ⚠️ 需要确认 → 用户批准
```

### 场景3: MCP集成(GitHub PR管理)

```
配置: ~/.openharness/mcp_config.json
{
  "servers": {
    "github": {
      "type": "http",
      "url": "https://api.github.com/mcp",
      "headers": {"Authorization": "Bearer ${GITHUB_TOKEN}"}
    }
  }
}

启动: openharness
       ↓ McpClientManager.connect_all()
       ↓ 连接到GitHub MCP Server
       ↓ 列举工具: create_issue, list_pull_requests, add_comment
       ↓ 动态注册: github_create_issue, github_list_prs, ...

用户: "Create a GitHub issue for the auth bug"
       ↓
Agent看到可用工具: github_create_issue
       ↓
Agent调用: github_create_issue(owner="langchain-ai", repo="openharness", title="Auth Bug", ...)
       ↓ McpToolAdapter.execute()
       ↓ mcp_manager.call_tool("github", "create_issue", {...})
       ↓ HTTP POST to GitHub API
       ↓
✅ Agent报告: "Created issue #123: https://github.com/.../issues/123"
```

---

## 📚 相关文档

- [Tools & Swarm](./ARCHITECTURE_TOOLS_SWARM.md) - 工具执行与权限控制集成
- [Engine模块](./ARCHITECTURE_ENGINE.md) - ReAct循环中的权限检查点
- [Skills模块](./ARCHITECTURE_SKILLS_PLUGINS.md) - Skills如何受权限控制

---

**文档版本**: v1.1 (基于最新代码库) | **最后更新**: 2026-05-30

---

## 附录 · MCP 集成要点与示例

> 合并自 `ARCHITECTURE_PERMISSIONS_MCP.md`（2026-08-05）

> 基于OpenHarness架构分析的MCP工具与资源系统详解  
> **版本**: v1.0 | **最后更新**: 2026-04-20

---

## 📋 目录

1. [完整实例](#1-完整实例)
2. [McpToolAdapter工作原理](#2-mcptooladapter工作原理)
3. [MCP Resources详解](#3-mcp-resources详解)
4. [动态注册机制](#4-动态注册机制)
5. [使用方式](#5-使用方式)

---

## 1. 完整实例

### 1.1 示例文件

OpenHarness提供完整的MCP示例代码:

- **Server**: [`examples/mcp_complete_example_server.py`](file:///Users/gqli/work/deepagents/OpenHarness/examples/mcp_complete_example_server.py)
  - 天气服务MCP Server
  - 3个Tools + 3个Resources
  - 展示多种参数类型和错误处理

- **Client**: [`examples/mcp_complete_example_client.py`](file:///Users/gqli/work/deepagents/OpenHarness/examples/mcp_complete_example_client.py)
  - 完整客户端演示
  - 连接、发现、调用全流程
  - 7个步骤详细注释

### 1.2 运行示例

```bash
# 从OpenHarness仓库根目录执行
uv run python examples/mcp_complete_example_client.py
```

### 1.3 示例功能

**MCP Tools (3个)**:
1. `get_current_weather(city)` - 获取实时天气
2. `get_weather_forecast(city, days, unit)` - 多日天气预报
3. `compare_cities_weather(cities, metric)` - 城市天气对比

**MCP Resources (3个)**:
1. `weather://api-docs` - API文档
2. `weather://supported-cities` - 支持的城市列表
3. `weather://units-reference` - 温度单位换算参考

---

## 2. McpToolAdapter工作原理

### 2.1 Name和Description的来源

**问题**: MCP Server返回的工具元数据如何转换为OpenHarness可用的Tool?

**答案**: MCP协议自动从Python函数提取元数据

```python
# MCP Server声明(以FastMCP为例)
@server.tool()
def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city.
    
    Use this when you need real-time weather data including temperature,
    humidity, wind speed, and conditions (sunny, rainy, etc.).
    
    Args:
        city: Name of the city (e.g., "Beijing", "New York", "London")
    
    Returns:
        JSON string with weather data
    """
    # ... implementation ...
```

**MCP协议自动提取**:
1. **函数名** → `tool.name` = `"get_current_weather"`
2. **Docstring第一行** → `tool.description` = `"Get current weather conditions for a city."`
3. **参数注解** → `tool.inputSchema` = `{"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}`

### 2.2 OpenHarness转换流程

**Step 1: MCP Client调用session.list_tools()** ([`mcp/client.py:225`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/mcp/client.py#L225))

```python
tool_result = await session.list_tools()
```

**Step 2: 为每个MCP工具创建McpToolInfo** ([`mcp/client.py:232-240`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/mcp/client.py#L232-L240))

```python
tools = [
    McpToolInfo(
        server_name=name,              # e.g., "weather"
        name=tool.name,                # e.g., "get_current_weather"
        description=tool.description or "",  # Docstring第一行
        input_schema=dict(tool.inputSchema or {"type": "object", "properties": {}}),
    )
    for tool in tool_result.tools
]
```

**Step 3: McpToolAdapter构造** ([`mcp_tool.py:17-24`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/tools/mcp_tool.py#L17-L24))

```python
class McpToolAdapter(BaseTool):
    def __init__(self, manager: McpClientManager, tool_info: McpToolInfo) -> None:
        self._manager = manager
        self._tool_info = tool_info
        
        # 生成唯一工具名(避免不同Server的同名工具冲突)
        server_segment = _sanitize_tool_segment(tool_info.server_name)  # "weather"
        tool_segment = _sanitize_tool_segment(tool_info.name)           # "get_current_weather"
        self.name = f"mcp__{server_segment}__{tool_segment}"            # → "mcp__weather__get_current_weather"
        
        # 直接使用MCP Server提供的description
        self.description = tool_info.description or f"MCP tool {tool_info.name}"
        
        # 动态生成Pydantic输入模型(从JSON Schema转换)
        self.input_model = _input_model_from_schema(self.name, tool_info.input_schema)
```

### 2.3 Input Schema转换逻辑

**JSON Schema → Pydantic模型** ([`mcp_tool.py:49-63`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/tools/mcp_tool.py#L49-L63))

```python
def _input_model_from_schema(tool_name: str, schema: dict[str, object]) -> type[BaseModel]:
    """Convert MCP JSON Schema to Pydantic BaseModel."""
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return create_model(f"{tool_name.title()}Input")
    
    fields = {}
    required = set(schema.get("required", []))
    
    for key in properties:
        prop = properties[key] if isinstance(properties[key], dict) else {}
        # JSON类型 → Python类型映射
        py_type = _JSON_TYPE_MAP.get(str(prop.get("type", "")), object)
        
        if key in required:
            fields[key] = (py_type, Field(default=...))  # 必填字段
        else:
            fields[key] = (py_type | None, Field(default=None))  # 可选字段
    
    return create_model(f"{tool_name.title().replace('-', '_')}Input", **fields)

_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}
```

**转换示例**:

```python
# 输入: MCP Server返回的JSON Schema
{
  "type": "object",
  "properties": {
    "city": {"type": "string"},
    "days": {"type": "integer"},
    "unit": {"type": "string"}
  },
  "required": ["city"]
}

# 输出: Pydantic模型
class GetWeatherForecastInput(BaseModel):
    city: str                    # 必填
    days: int | None = None      # 可选
    unit: str | None = None      # 可选
```

### 2.4 关键点总结

- ✅ **Name自动生成**: `mcp__{server}__{tool}` 命名空间,保证全局唯一
- ✅ **Description透传**: 直接使用MCP Server的docstring,无需额外配置
- ✅ **Schema动态转换**: JSON Schema → Pydantic模型,支持类型验证
- ✅ **全部注册**: 启动时遍历所有MCP Servers的所有Tools,一次性注册到Registry

---

## 3. MCP Resources详解

### 3.1 什么是MCP Resources?

Resources是MCP协议中的**只读数据源**,类似于文件系统或API端点,但通过统一接口访问。

### 3.2 与Tools的区别

| 维度 | MCP Tools | MCP Resources |
|------|-----------|---------------|
| **用途** | 执行操作(写/查询/计算) | 读取静态或动态数据 |
| **副作用** | 可能有(如创建Issue) | 无(纯读取) |
| **调用方式** | `call_tool(name, args)` | `read_resource(uri)` |
| **参数** | 结构化(JSON Schema) | URI字符串 |
| **示例** | `create_issue()`, `query_db()` | `file:///etc/hosts`, `https://api.github.com/...` |

### 3.3 典型应用场景

1. **文档访问**: API文档、配置说明、最佳实践指南
2. **静态数据**: 城市列表、货币代码、时区信息
3. **动态数据**: GitHub仓库元数据、数据库schema、系统状态
4. **参考材料**: 单位换算表、错误码字典、术语表

### 3.4 OpenHarness实现

提供2个专用工具访问Resources:

#### **`list_mcp_resources`** (列举资源)

[`list_mcp_resources_tool.py`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/tools/list_mcp_resources_tool.py)

```python
class ListMcpResourcesTool(BaseTool):
    name = "list_mcp_resources"
    description = "List MCP resources available from connected servers."
    
    async def execute(self, arguments, context) -> ToolResult:
        resources = self._manager.list_resources()
        if not resources:
            return ToolResult(output="(no MCP resources)")
        
        # 格式化输出: server:uri description
        return ToolResult(
            output="\n".join(
                f"{item.server_name}:{item.uri} {item.description}".strip() 
                for item in resources
            )
        )
```

**输出示例**:
```
weather:weather://api-docs Weather API Documentation
weather:weather://supported-cities Complete list of cities with weather data coverage
weather:weather://units-reference Guide for temperature unit conversions and usage
github:https://api.github.com/repos/langchain-ai/openharness GitHub repository info
```

#### **`read_mcp_resource`** (读取资源)

[`read_mcp_resource_tool.py`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/tools/read_mcp_resource_tool.py)

```python
class ReadMcpResourceTool(BaseTool):
    name = "read_mcp_resource"
    description = "Read an MCP resource by server and URI."
    
    class InputModel(BaseModel):
        server: str = Field(description="MCP server name")
        uri: str = Field(description="Resource URI")
    
    async def execute(self, arguments, context) -> ToolResult:
        try:
            output = await self._manager.read_resource(arguments.server, arguments.uri)
        except McpServerNotConnectedError as exc:
            return ToolResult(output=str(exc), is_error=True)
        return ToolResult(output=output)
```

**使用示例**:

```python
# Agent调用
read_mcp_resource(
    server="weather",
    uri="weather://supported-cities"
)

# 返回结果
{
  "total_cities": 8,
  "cities": [
    {"name": "Beijing", "country": "China", "timezone": "Asia/Shanghai"},
    {"name": "Shanghai", "country": "China", "timezone": "Asia/Shanghai"},
    ...
  ],
  "note": "Use these exact city names when calling weather tools"
}
```

### 3.5 Resource URI规范

URI格式由MCP Server定义,常见模式:
- **自定义协议**: `weather://supported-cities`, `db://users/schema`
- **文件协议**: `file:///etc/hosts`, `file:///path/to/config.yaml`
- **HTTP协议**: `https://api.github.com/repos/owner/repo`
- **数据库协议**: `postgres://localhost/mydb/tables`

---

## 4. 动态注册机制

### 4.1 注册流程

**源码**: [`tools/__init__.py:89-93`](file:///Users/gqli/work/deepagents/OpenHarness/src/openharness/tools/__init__.py#L89-L93)

```python
def create_default_tool_registry(mcp_manager=None) -> ToolRegistry:
    registry = ToolRegistry()
    
    # Step 1: 注册38个内置工具
    for tool in (BashTool(), FileReadTool(), ..., AgentTool()):
        registry.register(tool)
    
    # Step 2: 如果MCP Manager存在,动态注册MCP工具
    if mcp_manager is not None:
        # 2.1 注册2个Resource访问工具(固定)
        registry.register(ListMcpResourcesTool(mcp_manager))
        registry.register(ReadMcpResourceTool(mcp_manager))
        
        # 2.2 遍历所有MCP Servers的所有Tools,为每个创建Adapter
        for tool_info in mcp_manager.list_tools():
            # tool_info = McpToolInfo(server_name, name, description, input_schema)
            registry.register(McpToolAdapter(mcp_manager, tool_info))
    
    return registry
```

### 4.2 注册策略: 启动时全量注册(非懒加载)

```
┌─────────────────────────────────────────────────────┐
│          MCP Tools Registration Flow                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Step 1: McpClientManager.connect_all()             │
│  ┌───────────────────────────┐                     │
│  │ for each configured server:│                     │
│  │   - Establish connection   │                     │
│  │   - Call session.initialize()                    │
│  │   - Call session.list_tools()  ← RPC调用         │
│  │   - Store McpToolInfo[]    │                     │
│  └───────────────────────────┘                     │
│                        ↓                            │
│  Step 2: mcp_manager.list_tools()                  │
│  ┌───────────────────────────┐                     │
│  │ Aggregate all tools from  │                     │
│  │ all connected servers     │                     │
│  │                           │                     │
│  │ Returns:                  │                     │
│  │ [                         │                     │
│  │   McpToolInfo(            │                     │
│  │     server_name="weather",│                     │
│  │     name="get_current_weather",                 │
│  │     description="...",    │                     │
│  │     input_schema={...}    │                     │
│  │   ),                      │                     │
│  │   McpToolInfo(...),       │                     │
│  │   ... (N tools total)     │                     │
│  │ ]                         │                     │
│  └───────────────────────────┘                     │
│                        ↓                            │
│  Step 3: Create McpToolAdapter for each            │
│  ┌───────────────────────────┐                     │
│  │ for tool_info in tools:   │                     │
│  │   adapter = McpToolAdapter(                     │
│  │     manager, tool_info    │                     │
│  │   )                       │                     │
│  │   # adapter.name = "mcp__weather__get_current_weather"                                 │
│  │   # adapter.description = tool_info.description │
│  │   # adapter.input_model = dynamically generated │
│  │   registry.register(adapter)                    │
│  └───────────────────────────┘                     │
│                        ↓                            │
│  Step 4: Generate complete tool schemas            │
│  ┌───────────────────────────┐                     │
│  │ registry.to_api_schema()  │                     │
│  │ → [                       │                     │
│  │   {name: "bash", ...},    │                     │
│  │   {name: "read_file", ...},                      │
│  │   ...,                    │                     │
│  │   {name: "mcp__weather__get_current_weather", ...},                                    │
│  │   ... (38 + N tools)      │                     │
│  │ ]                         │                     │
│  │ → Inject into LLM Prompt  │                     │
│  └───────────────────────────┘                     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 4.3 为什么全量注册?

1. ✅ **LLM需要完整工具列表**: System Prompt中必须声明所有可用工具,让模型自主选择
2. ✅ **性能开销极小**: Adapter只是轻量级包装器,真正的延迟在执行时(call_tool RPC)
3. ✅ **架构简化**: 统一通过`registry.get(name)`获取,无需运行时动态查找
4. ✅ **一致性**: 内置工具和MCP工具使用相同接口,Agent无感知

---

## 5. 使用方式

有3种使用方式,从高层到低层:

### 5.1 方式1: Agent自动调用(推荐)

Agent在ReAct循环中看到MCP工具后,会自动决定调用:

```python
# Step 1: LLM看到可用工具(在System Prompt中)
available_tools = [
  {"name": "bash", "description": "Execute shell commands"},
  {"name": "mcp__weather__get_current_weather", 
   "description": "Get current weather conditions for a city",
   "input_schema": {
     "type": "object",
     "properties": {"city": {"type": "string"}},
     "required": ["city"]
   }
  },
  ...
]

# Step 2: LLM决定调用MCP工具
tool_use = {
  "name": "mcp__weather__get_current_weather",
  "arguments": {"city": "Beijing"}
}

# Step 3: Engine执行工具
result = await registry.get("mcp__weather__get_current_weather").execute(
    arguments,
    context
)
# → McpToolAdapter.execute() 
# → mcp_manager.call_tool("weather", "get_current_weather", {"city": "Beijing"})
# → HTTP POST to MCP Server
# → 返回天气数据

# Step 4: Agent报告结果
"Current weather in Beijing: 22°C, sunny, humidity 45%"
```

### 5.2 方式2: 手动调用(调试/测试)

参考 [`examples/mcp_complete_example_client.py`](file:///Users/gqli/work/deepagents/OpenHarness/examples/mcp_complete_example_client.py):

```python
from openharness.mcp.client import McpClientManager
from openharness.tools import create_default_tool_registry

# Step 1: 创建MCP Manager并连接
manager = McpClientManager({
    "weather": McpStdioServerConfig(
        command="python",
        args=["examples/mcp_complete_example_server.py"],
    )
})
await manager.connect_all()

# Step 2: 创建Tool Registry(自动注册MCP Tools)
registry = create_default_tool_registry(manager)

# Step 3: 获取MCP工具
weather_tool = registry.get("mcp__weather__get_current_weather")

# Step 4: 执行工具
ctx = ToolExecutionContext(cwd=Path.cwd())
result = await weather_tool.execute(
    weather_tool.input_model.model_validate({"city": "Beijing"}),
    ctx,
)
print(result.output)  # '{"city": "Beijing", "temperature_c": 22, ...}'
```

### 5.3 方式3: 直接调用MCP Manager(底层API)

```python
# 绕过Tool Registry,直接调用MCP Client
output = await manager.call_tool(
    server_name="weather",
    tool_name="get_current_weather",
    arguments={"city": "Beijing"}
)
print(output)  # '{"city": "Beijing", "temperature_c": 22, ...}'

# 读取Resource
output = await manager.read_resource(
    server_name="weather",
    uri="weather://supported-cities"
)
print(output)  # '{"total_cities": 8, "cities": [...]}'
```

---

## 📚 相关文档

- [ARCHITECTURE_TOOLS_SWARM.md §3.5](file:///Users/gqli/work/deepagents/OpenHarness/docs/ARCHITECTURE_TOOLS_SWARM.md#35-mcp集成工具) - 完整版MCP集成工具章节
- [MCP_AGENT_AND_TOOLS.md](file:///Users/gqli/work/deepagents/OpenHarness/docs/MCP_AGENT_AND_TOOLS.md) - MCP与Agent关系详解
- [ARCHITECTURE_PERMISSIONS_MCP.md](file:///Users/gqli/work/deepagents/OpenHarness/docs/ARCHITECTURE_PERMISSIONS_MCP.md) - MCP权限控制

---

**文档版本**: v1.0 | **最后更新**: 2026-04-20
