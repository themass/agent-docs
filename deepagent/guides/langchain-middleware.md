> **归类**：OpenHarness 文档 · [guides](./README.md)（非 OpenHarness 本体，供对照学习）

# LangChain AgentMiddleware 详解

本文档详细说明 LangChain AgentMiddleware 的返回值类型、框架用途以及如何影响 agent 执行流程。

## 目录

- [一、AgentMiddleware 框架概述](#一agentmiddleware-框架概述)
- [二、核心方法及其返回值类型](#二核心方法及其返回值类型)
- [三、方法详解与示例](#三方法详解与示例)
- [四、中间件如何影响流程](#四中间件如何影响流程)
- [五、实际案例分析](#五实际案例分析)
- [六、最佳实践](#六最佳实践)

---

## 一、AgentMiddleware 框架概述

### 1.1 什么是 AgentMiddleware？

`AgentMiddleware` 是 LangChain Agents 框架中的**中间件模式**实现，允许在 agent 执行生命周期的关键节点插入自定义逻辑，无需修改 agent 核心代码。

**核心价值**:
- **解耦**: 将横切关注点（如日志、权限、状态管理）从业务逻辑中分离
- **可扩展**: 通过组合多个中间件实现复杂功能
- **可复用**: 中间件可以在不同 agent 之间共享
- **灵活性**: 可以拦截和修改请求/响应

### 1.2 中间件在架构中的位置

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Middleware Stack (Ordered)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ MW 1     │→ │ MW 2     │→ │ MW 3     │→ ...         │
│  └──────────┘  └──────────┘  └──────────┘              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Agent Core Logic                            │
│  - State Management                                      │
│  - Tool Execution                                        │
│  - Model Invocation                                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    Response                              │
└─────────────────────────────────────────────────────────┘
```

### 1.3 内置中间件示例

DeepAgents 中使用的标准中间件栈：

```python
deepagent_middleware = [
    TodoListMiddleware(),           # 任务列表管理
    FilesystemMiddleware(backend),  # 文件系统工具
    SubAgentMiddleware(...),        # 子代理管理
    SummarizationMiddleware(...),   # 上下文摘要
    AnthropicPromptCachingMiddleware(),  # Prompt 缓存
    PatchToolCallsMiddleware(),     # 修复悬空 tool calls
]

# 可选添加
if skills is not None:
    deepagent_middleware.append(SkillsMiddleware(backend=backend, sources=skills))

if interrupt_on is not None:
    deepagent_middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))
```

---

## 二、核心方法及其返回值类型

AgentMiddleware 提供以下生命周期方法，每个方法都有特定的返回值类型：

### 2.1 返回值类型总览

| 方法 | 返回类型 | 用途 | 是否必须 |
|------|---------|------|---------|
| `before_agent()` | `dict \| TypedDict \| None` | 更新 agent state | 可选 |
| `wrap_model_call()` | `ModelResponse` | 拦截模型调用 | 可选 |
| `awrap_model_call()` | `ModelResponse` | 异步拦截模型调用 | 可选 |
| `after_agent()` | `None` | agent 执行后清理 | 可选 |

### 2.2 详细类型定义

#### before_agent() 返回值

```python
from typing import TypedDict

# 方式 1: 返回 dict（灵活但无类型检查）
def before_agent(self, state: AgentState, runtime: Runtime, config: RunnableConfig) -> dict | None:
    return {"custom_field": "value"}

# 方式 2: 返回 TypedDict（推荐，有类型安全）
class MyStateUpdate(TypedDict):
    custom_field: str
    another_field: int

def before_agent(self, state: MyState, runtime: Runtime, config: RunnableConfig) -> MyStateUpdate | None:
    return MyStateUpdate(custom_field="value", another_field=42)

# 方式 3: 返回 None（不更新 state）
def before_agent(self, state: AgentState, runtime: Runtime, config: RunnableConfig) -> None:
    # 只执行副作用，不更新 state
    logger.info("Agent started")
    return None
```

**关键点**:
- 返回 `None`: 不更新 state
- 返回 `dict`: 合并到当前 state（浅合并）
- 返回 `TypedDict`: 类型安全的 state 更新

#### wrap_model_call() 返回值

```python
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from collections.abc import Callable

def wrap_model_call(
    self,
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """
    必须返回 ModelResponse 类型
    
    两种方式:
    1. 直接调用 handler（不修改请求）
    2. 修改 request 后调用 handler
    """
    # 方式 1: 不修改，直接传递
    return handler(request)
    
    # 方式 2: 修改后传递
    modified_request = request.override(system_message=new_system_message)
    return handler(modified_request)
```

**关键点**:
- **必须**调用 `handler()` 并返回其结果
- 可以通过 `request.override()` 创建修改后的请求
- 不能跳过 `handler()` 调用（除非你想完全阻止模型调用）

---

## 三、方法详解与示例

### 3.1 before_agent() - Agent 执行前

**签名**:
```python
def before_agent(
    self, 
    state: AgentState, 
    runtime: Runtime, 
    config: RunnableConfig
) -> dict | TypedDict | None
```

**参数说明**:
- `state`: 当前 agent state（包含 messages、files 等）
- `runtime`: 运行时上下文（包含 context、store、stream_writer）
- `config`: 可运行配置（包含 thread_id、metadata 等）

**返回值作用**:
- `None`: 不更新 state
- `dict/TypedDict`: 合并到 state 中

#### 示例 1: SkillsMiddleware - 加载技能元数据

```python
class SkillsMiddleware(AgentMiddleware):
    def before_agent(
        self, 
        state: SkillsState, 
        runtime: Runtime, 
        config: RunnableConfig
    ) -> SkillsStateUpdate | None:
        # 如果已加载，跳过
        if "skills_metadata" in state:
            return None
        
        # 加载 skills
        backend = self._get_backend(state, runtime, config)
        all_skills = {}
        
        for source_path in self.sources:
            source_skills = _list_skills(backend, source_path)
            for skill in source_skills:
                all_skills[skill["name"]] = skill
        
        skills = list(all_skills.values())
        
        # 返回 state 更新
        return SkillsStateUpdate(skills_metadata=skills)
```

**效果**:
```python
# before_agent 执行前
state = {
    "messages": [...],
    "files": {...}
}

# before_agent 执行后
state = {
    "messages": [...],
    "files": {...},
    "skills_metadata": [  # ← 新增字段
        {
            "name": "web-research",
            "description": "...",
            "path": "/skills/user/web-research/SKILL.md",
            ...
        }
    ]
}
```

#### 示例 2: MemoryMiddleware - 加载记忆内容

```python
class MemoryMiddleware(AgentMiddleware):
    def before_agent(
        self, 
        state: MemoryState, 
        runtime: Runtime, 
        config: RunnableConfig
    ) -> MemoryStateUpdate | None:
        if "memory_contents" in state:
            return None
        
        backend = self._get_backend(state, runtime, config)
        contents = {}
        
        for path in self.sources:
            content = self._load_memory_from_backend_sync(backend, path)
            if content:
                contents[path] = content
        
        return MemoryStateUpdate(memory_contents=contents)
```

#### 示例 3: PatchToolCallsMiddleware - 修复悬空 tool calls

```python
class PatchToolCallsMiddleware(AgentMiddleware):
    def before_agent(
        self, 
        state: AgentState, 
        runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        messages = state["messages"]
        if not messages:
            return None
        
        last_message = messages[-1]
        
        # 如果最后一条是 AIMessage 且有 tool_calls，但没有对应的 ToolMessage
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # 检查是否有未完成的 tool calls
            tool_call_ids = {tc['id'] for tc in last_message.tool_calls}
            response_tool_ids = {
                msg.tool_call_id 
                for msg in messages 
                if isinstance(msg, ToolMessage)
            }
            
            missing_ids = tool_call_ids - response_tool_ids
            
            if missing_ids:
                # 创建空的 ToolMessage 来修复
                patch_messages = [
                    ToolMessage(
                        content="Tool execution was interrupted.",
                        tool_call_id=call_id
                    )
                    for call_id in missing_ids
                ]
                
                return {"messages": patch_messages}
        
        return None
```

### 3.2 wrap_model_call() - 拦截模型调用

**签名**:
```python
def wrap_model_call(
    self,
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse
```

**参数说明**:
- `request`: 即将发送给模型的请求（包含 messages、tools、system_message 等）
- `handler`: 下一个处理函数（可能是另一个中间件或最终的模型调用）

**返回值**: 必须是 `ModelResponse` 类型

#### 示例 1: SkillsMiddleware - 注入 skills 到 system prompt

```python
class SkillsMiddleware(AgentMiddleware):
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        # 修改请求：注入 skills 信息
        modified_request = self.modify_request(request)
        
        # 调用 handler（传递给下一个中间件或模型）
        return handler(modified_request)
    
    def modify_request(self, request: ModelRequest) -> ModelRequest:
        skills_metadata = request.state.get("skills_metadata", [])
        skills_locations = self._format_skills_locations()
        skills_list = self._format_skills_list(skills_metadata)
        
        skills_section = self.system_prompt_template.format(
            skills_locations=skills_locations,
            skills_list=skills_list,
        )
        
        # 追加到 system message
        new_system_message = append_to_system_message(
            request.system_message, 
            skills_section
        )
        
        # 创建新的请求（不可变模式）
        return request.override(system_message=new_system_message)
```

**效果**:
```python
# 原始 request
request.system_message = "You are a helpful assistant."

# 经过 SkillsMiddleware 后
request.system_message = """
You are a helpful assistant.

## Skills System

**Available Skills:**
- **web-research**: Structured approach to conducting thorough web research
  -> Read `/skills/user/web-research/SKILL.md` for full instructions
...
"""
```

#### 示例 2: FilesystemMiddleware - 动态添加工具和 system prompt

```python
class FilesystemMiddleware(AgentMiddleware):
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        # 检查 backend 是否支持 execute
        has_execute_tool = any(
            tool.name == "execute" 
            for tool in request.tools
        )
        
        backend_supports_execution = False
        if has_execute_tool:
            backend = self._get_backend(request.runtime)
            backend_supports_execution = _supports_execution(backend)
            
            # 如果不支持，过滤掉 execute 工具
            if not backend_supports_execution:
                filtered_tools = [
                    tool 
                    for tool in request.tools 
                    if tool.name != "execute"
                ]
                request = request.override(tools=filtered_tools)
                has_execute_tool = False
        
        # 动态构建 system prompt
        prompt_parts = [FILESYSTEM_SYSTEM_PROMPT]
        
        if has_execute_tool and backend_supports_execution:
            prompt_parts.append(EXECUTION_SYSTEM_PROMPT)
        
        system_prompt = "\n\n".join(prompt_parts)
        
        if system_prompt:
            new_system_message = append_to_system_message(
                request.system_message, 
                system_prompt
            )
            request = request.override(system_message=new_system_message)
        
        return handler(request)
```

#### 示例 3: LoggingMiddleware - 记录模型调用

```python
class ModelCallLoggingMiddleware(AgentMiddleware):
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        # 记录请求
        logger.info(f"🟡 [wrap_model_call] Sending {len(request.messages)} messages to model")
        
        # 记录 tools
        tool_names = [
            tool.name if hasattr(tool, "name") else tool.get("name")
            for tool in request.tools
        ]
        logger.info(f"🟡 Available tools: {', '.join(tool_names)}")
        
        # 调用 handler
        response = handler(request)
        
        # 记录响应
        logger.info(f"🟡 [wrap_model_call] Received response from model")
        
        return response
```

#### 示例 4: SubAgentMiddleware - 注入子代理指令

```python
class SubAgentMiddleware(AgentMiddleware):
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        if self.system_prompt is not None:
            # 追加子代理使用说明
            new_system_message = append_to_system_message(
                request.system_message, 
                self.system_prompt
            )
            return handler(request.override(system_message=new_system_message))
        
        # 没有额外指令，直接传递
        return handler(request)
```

### 3.3 awrap_model_call() - 异步版本

**签名**:
```python
async def awrap_model_call(
    self,
    request: ModelRequest,
    handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
) -> ModelResponse
```

**使用场景**: 需要异步操作时（如异步数据库查询、网络请求）

#### 示例: 异步日志中间件

```python
class AsyncLoggingMiddleware(AgentMiddleware):
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # 异步记录请求
        await self.log_to_database(request)
        
        # 调用异步 handler
        response = await handler(request)
        
        # 异步记录响应
        await self.log_response_to_database(response)
        
        return response
    
    async def log_to_database(self, request: ModelRequest):
        # 异步数据库操作
        pass
```

### 3.4 after_agent() - Agent 执行后（较少使用）

**签名**:
```python
def after_agent(
    self, 
    state: AgentState, 
    runtime: Runtime, 
    config: RunnableConfig
) -> None
```

**用途**: 清理资源、记录最终状态、发送通知等

#### 示例: 清理临时文件

```python
class TempFileCleanupMiddleware(AgentMiddleware):
    def after_agent(
        self, 
        state: AgentState, 
        runtime: Runtime, 
        config: RunnableConfig
    ) -> None:
        # 清理临时文件
        temp_files = state.get("temp_files", [])
        for file_path in temp_files:
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")
```

---

## 四、中间件如何影响流程

### 4.1 中间件链的执行顺序

中间件按照**注册顺序**形成责任链：

```python
middleware_stack = [
    MiddlewareA(),  # 第 1 个
    MiddlewareB(),  # 第 2 个
    MiddlewareC(),  # 第 3 个
]
```

**执行流程**:

```
User Request
    ↓
┌─────────────────────────────────────────┐
│ MiddlewareA.before_agent()              │ → 更新 state
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ MiddlewareB.before_agent()              │ → 更新 state
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ MiddlewareC.before_agent()              │ → 更新 state
└──────────────┬──────────────────────────┘
               ↓
          Agent Loop
               ↓
┌─────────────────────────────────────────┐
│ MiddlewareA.wrap_model_call()           │ → 修改 request
│   ↓                                     │
│   MiddlewareB.wrap_model_call()         │ → 修改 request
│       ↓                                 │
│       MiddlewareC.wrap_model_call()     │ → 修改 request
│           ↓                             │
│           Model Call (LLM)              │ → 生成 response
│           ↓                             │
│       MiddlewareC returns response      │
│       ↓                                 │
│   MiddlewareB returns response          │
│   ↓                                     │
│ MiddlewareA returns response            │
└──────────────┬──────────────────────────┘
               ↓
          Continue Loop
               ↓
┌─────────────────────────────────────────┐
│ MiddlewareA.after_agent()               │ → 清理
│ MiddlewareB.after_agent()               │ → 清理
│ MiddlewareC.after_agent()               │ → 清理
└─────────────────────────────────────────┘
               ↓
          Final Response
```

### 4.2 wrap_model_call() 的洋葱模型

`wrap_model_call()` 采用**洋葱模型**（嵌套调用）：

```python
# 伪代码展示调用链
def middleware_A_wrap(request, handler):
    print("A: before")
    modified_request_A = A_modify(request)
    response = handler(modified_request_A)  # 调用 B
    print("A: after")
    return response

def middleware_B_wrap(request, handler):
    print("B: before")
    modified_request_B = B_modify(request)
    response = handler(modified_request_B)  # 调用 C
    print("B: after")
    return response

def middleware_C_wrap(request, handler):
    print("C: before")
    modified_request_C = C_modify(request)
    response = handler(modified_request_C)  # 调用 Model
    print("C: after")
    return response

# 实际执行顺序:
# A: before
#   B: before
#     C: before
#       Model Call
#     C: after
#   B: after
# A: after
```

**实际输出**:
```
A: before
  B: before
    C: before
      [LLM generates response]
    C: after
  B: after
A: after
```

### 4.3 State 更新的合并机制

多个中间件的 `before_agent()` 返回的 state 更新会**浅合并**：

```python
# MiddlewareA
def before_agent(self, state, runtime, config):
    return {"field_a": "value_a", "shared": "from_A"}

# MiddlewareB
def before_agent(self, state, runtime, config):
    return {"field_b": "value_b", "shared": "from_B"}

# 最终 state（B 覆盖 A 的 shared 字段）
state = {
    "field_a": "value_a",
    "field_b": "value_b",
    "shared": "from_B"  # ← 后执行的中间件覆盖前面的
}
```

**注意**: 
- 这是**浅合并**（shallow merge），嵌套字典会被整体替换
- 执行顺序决定优先级（后面的覆盖前面的）

### 4.4 Request 修改的累积效应

每个中间件都可以修改 `ModelRequest`，修改会**累积**：

```python
# 初始 request
request = ModelRequest(
    system_message="You are helpful.",
    tools=[tool1, tool2],
    messages=[...]
)

# MiddlewareA: 添加工具
request_A = request.override(
    tools=[*request.tools, tool3]
)

# MiddlewareB: 修改 system message
request_B = request_A.override(
    system_message=request_A.system_message + "\n\nAdditional instructions."
)

# MiddlewareC: 再次修改 system message
request_C = request_B.override(
    system_message=request_B.system_message + "\n\nMore instructions."
)

# 最终发送给模型的 request
final_request = request_C
# system_message: "You are helpful.\n\nAdditional instructions.\n\nMore instructions."
# tools: [tool1, tool2, tool3]
```

---

## 五、实际案例分析

### 5.1 案例 1: SkillsMiddleware 完整流程

**目标**: 让 agent 能够发现和使用 skills

#### 步骤 1: before_agent() 加载 skills

```python
def before_agent(self, state, runtime, config):
    if "skills_metadata" in state:
        return None  # 已加载，跳过
    
    # 从文件系统扫描 skills
    backend = self._get_backend(state, runtime, config)
    all_skills = {}
    
    for source_path in self.sources:
        source_skills = _list_skills(backend, source_path)
        for skill in source_skills:
            all_skills[skill["name"]] = skill  # 后加载的覆盖先加载的
    
    return SkillsStateUpdate(skills_metadata=list(all_skills.values()))
```

**效果**:
```python
state["skills_metadata"] = [
    {
        "name": "web-research",
        "description": "Structured web research",
        "path": "/skills/user/web-research/SKILL.md",
        "allowed_tools": ["web_search", "read_file"]
    }
]
```

#### 步骤 2: wrap_model_call() 注入到 prompt

```python
def wrap_model_call(self, request, handler):
    skills_metadata = request.state.get("skills_metadata", [])
    
    # 格式化 skills 列表
    skills_list = self._format_skills_list(skills_metadata)
    # 输出:
    # - **web-research**: Structured web research
    #   -> Allowed tools: web_search, read_file
    #   -> Read `/skills/user/web-research/SKILL.md` for full instructions
    
    skills_section = SKILLS_SYSTEM_PROMPT.format(
        skills_locations=self._format_skills_locations(),
        skills_list=skills_list
    )
    
    # 追加到 system message
    new_system_message = append_to_system_message(
        request.system_message, 
        skills_section
    )
    
    modified_request = request.override(system_message=new_system_message)
    return handler(modified_request)
```

**最终 Prompt**:
```markdown
You are a helpful assistant.

## Skills System

**User Skills**: `/skills/user/` (higher priority)

**Available Skills:**

- **web-research**: Structured web research
  -> Allowed tools: web_search, read_file
  -> Read `/skills/user/web-research/SKILL.md` for full instructions

**How to Use Skills:**
1. Recognize when a skill applies
2. Read the skill's full instructions using the path shown
3. Follow the skill's workflow
...
```

#### 步骤 3: LLM 决策并使用 skill

```
User: "Research quantum computing developments"

LLM 思考:
1. 看到 "web-research" skill 可用
2. 调用 read_file("/skills/user/web-research/SKILL.md")
3. 读取完整的 skill 指令
4. 按照 skill 的工作流执行
```

### 5.2 案例 2: FilesystemMiddleware 动态工具管理

**目标**: 根据 backend 能力动态添加/移除工具

#### 关键逻辑

```python
def wrap_model_call(self, request, handler):
    # 检查是否有 execute 工具
    has_execute_tool = any(
        tool.name == "execute" 
        for tool in request.tools
    )
    
    if has_execute_tool:
        backend = self._get_backend(request.runtime)
        backend_supports_execution = _supports_execution(backend)
        
        if not backend_supports_execution:
            # 过滤掉 execute 工具
            filtered_tools = [
                tool 
                for tool in request.tools 
                if tool.name != "execute"
            ]
            request = request.override(tools=filtered_tools)
            has_execute_tool = False
    
    # 动态构建 system prompt
    prompt_parts = [FILESYSTEM_SYSTEM_PROMPT]
    
    if has_execute_tool and backend_supports_execution:
        prompt_parts.append(EXECUTION_SYSTEM_PROMPT)
    
    system_prompt = "\n\n".join(prompt_parts)
    
    if system_prompt:
        new_system_message = append_to_system_message(
            request.system_message, 
            system_prompt
        )
        request = request.override(system_message=new_system_message)
    
    return handler(request)
```

**效果对比**:

**场景 A: StateBackend（不支持 execute）**
```python
# Tools passed to LLM
tools = ["ls", "read_file", "write_file", "edit_file", "glob", "grep"]
# 没有 "execute"

# System prompt
"""
## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`
...
"""
# 没有 "Execute Tool" 部分
```

**场景 B: SandboxBackend（支持 execute）**
```python
# Tools passed to LLM
tools = ["ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute"]
# 包含 "execute"

# System prompt
"""
## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`
...

## Execute Tool `execute`
...
"""
# 包含 "Execute Tool" 部分
```

### 5.3 案例 3: 多个中间件协作

**场景**: Skills + Filesystem + SubAgent 三个中间件协同工作

```python
middleware_stack = [
    FilesystemMiddleware(backend),
    SubAgentMiddleware(subagents),
    SkillsMiddleware(backend, sources=["/skills/user/"]),
]
```

**执行流程**:

```python
# 1. before_agent 阶段（按顺序）
FilesystemMiddleware.before_agent()
  → 无 state 更新（return None）

SubAgentMiddleware.before_agent()
  → 无 state 更新（return None）

SkillsMiddleware.before_agent()
  → 返回 {"skills_metadata": [...]}

# State 现在是:
state = {
    "messages": [...],
    "files": {...},
    "skills_metadata": [...]  # ← SkillsMiddleware 添加
}

# 2. wrap_model_call 阶段（洋葱模型）
FilesystemMiddleware.wrap_model_call(request, handler)
  ↓ 修改 request（添加 filesystem tools + prompt）
  SubAgentMiddleware.wrap_model_call(modified_request, handler)
    ↓ 修改 request（添加 subagent instructions）
    SkillsMiddleware.wrap_model_call(modified_request, handler)
      ↓ 修改 request（添加 skills section）
      Model Call (LLM)
      ↑ 返回 response
    SkillsMiddleware returns response
    ↑ 返回 response
  SubAgentMiddleware returns response
  ↑ 返回 response
FilesystemMiddleware returns response
↑ 返回最终 response
```

**最终发送给 LLM 的 Request**:
```python
request = ModelRequest(
    system_message="""
You are a helpful assistant.

## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`
...

## `task` (subagent spawner)
You have access to a `task` tool to launch short-lived subagents...

## Skills System

**User Skills**: `/skills/user/`

**Available Skills:**
- **web-research**: Structured web research
  -> Read `/skills/user/web-research/SKILL.md` for full instructions
...
""",
    tools=[
        # From FilesystemMiddleware
        ls_tool, read_file_tool, write_file_tool, edit_file_tool, glob_tool, grep_tool,
        # From SubAgentMiddleware
        task_tool,
        # Custom tools
        ...
    ],
    messages=[...]
)
```

---

## 六、最佳实践

### 6.1 设计原则

#### ✅ 推荐做法

1. **单一职责**: 每个中间件只做一件事
   ```python
   # ✅ 好：专门的 logging middleware
   class LoggingMiddleware(AgentMiddleware):
       def wrap_model_call(self, request, handler):
           logger.info(f"Calling model with {len(request.messages)} messages")
           return handler(request)
   
   # ❌ 不好：一个中间件做太多事
   class MegaMiddleware(AgentMiddleware):
       def wrap_model_call(self, request, handler):
           # 日志 + 权限检查 + 数据转换 + ...
           ...
   ```

2. **不可变性**: 使用 `request.override()` 而不是直接修改
   ```python
   # ✅ 好：创建新对象
   modified_request = request.override(system_message=new_message)
   return handler(modified_request)
   
   # ❌ 不好：直接修改（可能导致副作用）
   request.system_message = new_message
   return handler(request)
   ```

3. **类型安全**: 使用 TypedDict 定义 state 更新
   ```python
   # ✅ 好：类型安全
   class MyStateUpdate(TypedDict):
       field_a: str
       field_b: int
   
   def before_agent(self, state, runtime, config) -> MyStateUpdate | None:
       return MyStateUpdate(field_a="value", field_b=42)
   
   # ❌ 不好：裸 dict，容易出错
   def before_agent(self, state, runtime, config):
       return {"field_a": "value", "field_b": 42}
   ```

4. **短路优化**: 提前返回避免不必要的工作
   ```python
   # ✅ 好：检查是否已加载
   def before_agent(self, state, runtime, config):
       if "skills_metadata" in state:
           return None  # 跳过重复加载
       # ... 加载逻辑
   ```

5. **错误处理**: 优雅地处理异常
   ```python
   # ✅ 好：捕获异常
   def wrap_model_call(self, request, handler):
       try:
           modified_request = self.modify_request(request)
           return handler(modified_request)
       except Exception as e:
           logger.error(f"Middleware error: {e}")
           return handler(request)  # 降级：使用原始 request
   ```

#### ❌ 避免的做法

1. **不要跳过 handler 调用**（除非明确要阻止模型调用）
   ```python
   # ❌ 危险：完全阻止模型调用
   def wrap_model_call(self, request, handler):
       return ModelResponse(...)  # 没有调用 handler!
   
   # ✅ 正确：总是调用 handler
   def wrap_model_call(self, request, handler):
       return handler(request)
   ```

2. **不要在 before_agent 中执行耗时操作**
   ```python
   # ❌ 不好：阻塞 agent 启动
   def before_agent(self, state, runtime, config):
       time.sleep(10)  # 阻塞 10 秒！
       return {...}
   
   # ✅ 好：快速返回，异步加载
   def before_agent(self, state, runtime, config):
       # 立即返回，后续异步加载
       return None
   ```

3. **不要依赖中间件执行顺序**
   ```python
   # ❌ 危险：假设另一个中间件已经执行
   def before_agent(self, state, runtime, config):
       # 假设 skills_metadata 已经被 SkillsMiddleware 设置
       skills = state["skills_metadata"]  # 可能不存在！
   
   # ✅ 安全：自己检查和处理
   def before_agent(self, state, runtime, config):
       skills = state.get("skills_metadata", [])
       if not skills:
           # 自己加载或跳过
           ...
   ```

### 6.2 调试技巧

#### 技巧 1: 添加日志中间件

```python
class DebugMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime, config):
        logger.info(f"🔵 before_agent: state keys = {state.keys()}")
        return None
    
    def wrap_model_call(self, request, handler):
        logger.info(f"🟡 wrap_model_call:")
        logger.info(f"   - Messages: {len(request.messages)}")
        logger.info(f"   - Tools: {[t.name for t in request.tools]}")
        logger.info(f"   - System prompt length: {len(request.system_message)}")
        
        response = handler(request)
        
        logger.info(f"🟢 Model response received")
        return response
```

#### 技巧 2: 检查中间件顺序

```python
# 打印中间件栈
for i, mw in enumerate(middleware_stack):
    logger.info(f"Middleware {i}: {type(mw).__name__}")

# 输出:
# Middleware 0: FilesystemMiddleware
# Middleware 1: SubAgentMiddleware
# Middleware 2: SkillsMiddleware
```

#### 技巧 3: 验证 state 更新

```python
# 在 agent 执行后检查
result = agent.invoke({"messages": [...]})
print("State keys:", result.keys())
print("Skills metadata:", result.get("skills_metadata"))
print("Memory contents:", result.get("memory_contents"))
```

### 6.3 性能优化

#### 优化 1: 缓存昂贵的计算

```python
class CachedSkillsMiddleware(AgentMiddleware):
    def __init__(self, backend, sources):
        super().__init__()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    def before_agent(self, state, runtime, config):
        if "skills_metadata" in state:
            return None
        
        cache_key = tuple(self.sources)
        now = time.time()
        
        # 检查缓存
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if now - timestamp < self._cache_ttl:
                return SkillsStateUpdate(skills_metadata=cached_data)
        
        # 加载并缓存
        skills = self._load_skills()
        self._cache[cache_key] = (skills, now)
        
        return SkillsStateUpdate(skills_metadata=skills)
```

#### 优化 2: 懒加载

```python
class LazyMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self._initialized = False
    
    def before_agent(self, state, runtime, config):
        if not self._initialized:
            # 只在第一次执行时初始化
            self._expensive_init()
            self._initialized = True
        
        return None
```

### 6.4 测试策略

#### 测试 1: 单元测试 before_agent

```python
def test_skills_middleware_before_agent():
    backend = MockBackend()
    middleware = SkillsMiddleware(backend=backend, sources=["/skills/user/"])
    
    # 模拟空 state
    state = {}
    runtime = MockRuntime()
    config = {}
    
    # 调用 before_agent
    result = middleware.before_agent(state, runtime, config)
    
    # 验证返回值
    assert result is not None
    assert "skills_metadata" in result
    assert len(result["skills_metadata"]) > 0
```

#### 测试 2: 集成测试 wrap_model_call

```python
def test_skills_middleware_injects_prompt():
    backend = MockBackend()
    middleware = SkillsMiddleware(backend=backend, sources=["/skills/user/"])
    
    # 创建 mock handler
    captured_request = None
    
    def mock_handler(request):
        nonlocal captured_request
        captured_request = request
        return ModelResponse(...)
    
    # 创建 request
    request = ModelRequest(
        system_message="Base prompt",
        state={"skills_metadata": [{"name": "test-skill", ...}]},
        tools=[],
        messages=[]
    )
    
    # 调用 wrap_model_call
    middleware.wrap_model_call(request, mock_handler)
    
    # 验证 system message 被修改
    assert "Skills System" in captured_request.system_message
    assert "test-skill" in captured_request.system_message
```

---

## 七、常见问题 FAQ

### Q1: 中间件的执行顺序重要吗？

**A**: 非常重要！

- `before_agent()`: 按注册顺序执行，后面的可以覆盖前面的 state 更新
- `wrap_model_call()`: 洋葱模型，先注册的在外层，后注册的在内层（更接近模型）

**建议**: 
- 通用中间件放前面（如 logging）
- 特定业务逻辑放后面（如 skills、subagents）

### Q2: 如何在中间件之间共享数据？

**A**: 通过 `state` 共享：

```python
# MiddlewareA: 写入 state
def before_agent(self, state, runtime, config):
    return {"shared_data": "value"}

# MiddlewareB: 读取 state
def wrap_model_call(self, request, handler):
    shared_data = request.state.get("shared_data")
    # 使用 shared_data...
    return handler(request)
```

### Q3: 可以阻止模型调用吗？

**A**: 可以，但不推荐：

```python
def wrap_model_call(self, request, handler):
    # 某些条件下阻止调用
    if should_block(request):
        return ModelResponse(
            message=AIMessage(content="Request blocked")
        )
    
    return handler(request)
```

**更好的做法**: 在 `before_agent` 中设置标志，让 agent 逻辑决定是否调用模型。

### Q4: 如何处理异步中间件？

**A**: 实现 `awrap_model_call()` 而不是 `wrap_model_call()`:

```python
class AsyncMiddleware(AgentMiddleware):
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # 异步操作
        await self.async_operation()
        
        # 调用异步 handler
        response = await handler(request)
        
        return response
```

### Q5: 中间件会影响性能吗？

**A**: 轻微影响，但通常可以忽略：

- `before_agent()`: 增加 agent 启动时间
- `wrap_model_call()`: 增加每次模型调用的开销

**优化建议**:
- 缓存昂贵计算
- 避免在 hot path 中执行 I/O
- 使用短路优化

---

## 八、总结

### 核心要点

1. **AgentMiddleware 是强大的扩展机制**
   - 在不修改核心代码的情况下增强 agent 功能
   - 支持组合和复用

2. **两个主要方法**
   - `before_agent()`: 更新 state，返回 `dict | TypedDict | None`
   - `wrap_model_call()`: 拦截模型调用，返回 `ModelResponse`

3. **执行顺序很重要**
   - `before_agent()`: 顺序执行，后面的覆盖前面的
   - `wrap_model_call()`: 洋葱模型，嵌套调用

4. **最佳实践**
   - 单一职责
   - 不可变性
   - 类型安全
   - 错误处理
   - 性能优化

5. **实际应用**
   - SkillsMiddleware: 渐进式披露 skills
   - FilesystemMiddleware: 动态工具管理
   - SubAgentMiddleware: 注入子代理指令
   - LoggingMiddleware: 调试和监控

### 下一步

- 阅读源码: `libs/deepagents/deepagents/middleware/*.py`
- 查看测试: `libs/deepagents/tests/unit_tests/middleware/`
- 实践: 创建自己的中间件

---

**文档版本**: 1.0  
**最后更新**: 2026-04-09  
**参考资料**: 
- LangChain Agents Documentation
- DeepAgents Implementation
- Agent Skills Specification
