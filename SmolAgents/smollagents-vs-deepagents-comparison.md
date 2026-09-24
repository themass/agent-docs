# SmolAgents vs DeepAgents: Open Deep Research 对比分析

> **审查状态（2026-04-29）**: 已与 smolagents 1.24.x 源码比对并更新。修正了执行器类型（新增 Blaxel/Wasm）、MCP 集成支持、CallbackRegistry 等遗漏项。

## 📊 核心架构对比

### 1. Agent 创建方式

#### SmolAgents (open_deep_research/run.py)

```python
from smolagents import CodeAgent, ToolCallingAgent, LiteLLMModel

# 1. 创建模型
model = LiteLLMModel(
    model_id="o1",
    custom_role_conversions={"tool-call": "assistant", "tool-response": "user"},
    max_completion_tokens=8192,
)

# 2. 创建子代理（ToolCallingAgent）
text_webbrowser_agent = ToolCallingAgent(
    model=model,
    tools=WEB_TOOLS,
    max_steps=20,
    verbosity_level=2,
    planning_interval=4,
    name="search_agent",
    description="A team member that will search the internet...",
    provide_run_summary=True,
)

# 3. 创建管理器代理（CodeAgent）
manager_agent = CodeAgent(
    model=model,
    tools=[visualizer, TextInspectorTool(model, text_limit)],
    max_steps=12,
    verbosity_level=2,
    additional_authorized_imports=["*"],
    planning_interval=4,
    managed_agents=[text_webbrowser_agent],  # 子代理列表
)

# 4. 执行
answer = manager_agent.run(question)
```

#### DeepAgents (deep_research/agent.py)

```python
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

# 1. 创建模型
model = init_chat_model(
    base_url="https://newapi.yuaiweiwu.com/v1",
    api_key="sk-...",
    model="openai:claude-opus-4-6",
    temperature=0.0
)

# 2. 定义子代理（字典格式）
research_sub_agent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher.",
    "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
    "tools": [tavily_search, think_tool],
    "middleware": [ModelCallLoggingMiddleware()],  # ✅ 支持中间件
}

# 3. 创建文件系统后端（技能支持）
backend = FilesystemBackend(
    root_dir="/Users/gqli/work/deepagents/examples",
    virtual_mode=False
)

# 4. 创建主 Agent
agent = create_deep_agent(
    model=model,
    tools=[tavily_search, think_tool],
    system_prompt=INSTRUCTIONS,
    middleware=[ModelCallLoggingMiddleware()],  # ✅ 支持中间件
    subagents=[research_sub_agent],
    skills=["skills"],  # ✅ 支持技能系统
    backend=backend,  # ✅ 支持持久化后端
)

# 5. 执行
result = agent.invoke({"messages": [...]}, context=context)
```

---

## 🔑 关键差异

### 1. 执行模式

| 特性 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **Manager Agent** | `CodeAgent` - 生成 Python 代码执行 | `create_deep_agent` - 工具调用为主 |
| **Sub-Agent** | `ToolCallingAgent` - 直接调用工具 | 也是基于 LangGraph 的 Agent |
| **沙箱执行** | ✅ 本地沙箱 + 远程执行器（Docker/E2B/Modal/Blaxel/Wasm） | ❌ 无代码沙箱 |
| **代码生成** | ✅ LLM 生成任意 Python 代码 | ❌ 仅调用预定义工具 |
| **MCP 协议** | ✅ `MCPClient`（基于 `mcpadapt`） | ✅ 原生支持 |

**示例对比：**

SmolAgents CodeAgent 生成的代码：
```python
# LLM 生成的 Python 代码
import math
result = math.pow(2, 3.7384)
final_answer(result)
```

DeepAgents 的工具调用：
```python
# 直接调用工具
{
  "tool": "calculator",
  "arguments": {"base": 2, "exponent": 3.7384}
}
```

### 2. 中间件系统

| 特性 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **中间件支持** | ⚠️ `CallbackRegistry`（按 Step 类型注册回调） | ✅ AgentMiddleware |
| **日志记录** | 内置 `AgentLogger` + `Monitor`（token/timing 统计） | ModelCallLoggingMiddleware |
| **拦截点** | `step_callbacks`（ActionStep/PlanningStep 完成后触发） | before_agent, wrap_model_call, after_agent 等 |

**DeepAgents 中间件示例：**
```python
class ModelCallLoggingMiddleware(AgentMiddleware):
    def before_model(self, state: AgentState, runtime: Runtime):
        """在调用模型前记录"""
        logger.info(f"🔵 [before_model] Messages: {len(state['messages'])}")
    
    def wrap_model_call(self, call_next, state, runtime):
        """包装模型调用"""
        logger.info("🟡 [wrap_model_call] Calling model...")
        result = call_next(state, runtime)
        logger.info(f"🟢 [wrap_model_call] Got response")
        return result
```

### 3. 技能系统

| 特性 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **技能支持** | ❌ 无 | ✅ Skills |
| **加载方式** | - | `skills=["skills"]` |
| **存储后端** | - | FilesystemBackend |
| **渐进式披露** | - | ✅ 按需加载技能 |

**DeepAgents 技能配置：**
```python
backend = FilesystemBackend(root_dir="/path/to/examples")

agent = create_deep_agent(
    model=model,
    tools=[...],
    skills=["skills/public/search-skill"],  # 相对路径
    backend=backend,
)
```

### 4. 记忆与状态管理

| 特性 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **记忆系统** | `AgentMemory`（结构化步骤：`MemoryStep` 子类） | LangGraph State + Checkpointer |
| **持久化** | ❌ 仅内存（无内建持久化） | ✅ 支持多种后端 |
| **上下文管理** | `summary_mode` 双轨 + `max_steps` 硬限制 | Checkpointer 可恢复 |
| **线程管理** | 无 | thread_id + context |
| **检查点** | ❌ 无 | ✅ 可恢复执行 |

**DeepAgents 状态管理：**
```python
thread_id = str(uuid.uuid4())
context = {"thread_id": thread_id}

result = agent.invoke(
    {"messages": [...]},
    context=context  # 传递上下文
)
```

### 5. 工具系统

| 特性 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **工具定义** | 继承 Tool 类或 @tool 装饰器 | LangChain BaseTool |
| **MCP 工具** | ✅ `MCPClient`（基于 `mcpadapt`，支持 Stdio/HTTP 传输） | ✅ 原生 MCP 支持 |
| **序列化** | ✅ to_dict()/from_dict() | ❌ 无内置序列化 |
| **远程加载** | ✅ from_hub(), from_space() | ❌ 需手动实现 |
| **懒加载** | ✅ setup() 方法 | 依赖 LangChain |

**SmolAgents 工具序列化：**
```python
# 序列化工具
tool_dict = my_tool.to_dict()
# {
#   "name": "calculator",
#   "code": "class CalculatorTool(Tool): ...",
#   "requirements": ["math"]
# }

# 从字典恢复（⚠️ 执行远程代码）
tool = Tool.from_dict(tool_dict, trust_remote_code=True)
```

---

## 🏗️ 架构设计哲学

### SmolAgents: "小而美"

**核心理念：**
- ✅ 极简主义：代码量少，易于理解
- ✅ 灵活性：双模式执行（CodeAgent + ToolCallingAgent）
- ✅ 安全性：多层沙箱保护
- ✅ 生态整合：HuggingFace Hub、Gradio、MCP

**适用场景：**
- 快速原型开发
- 教育和学习 Agent 原理
- 需要代码生成的复杂任务
- 资源受限的环境

**优势：**
1. **代码生成能力**：CodeAgent 可以生成任意 Python 代码，灵活性极高
2. **沙箱安全**：AST 分析 + 白名单 + 资源限制
3. **轻量级**：核心代码仅 ~8600 行
4. **易扩展**：插件化设计

**劣势：**
1. ⚠️ 无完整中间件系统（仅有 `CallbackRegistry` 按 Step 类型注册回调）
2. ❌ 无技能管理
3. ❌ 状态管理简单（仅内存，无自动压缩）
4. ❌ 无持久化支持

---

### DeepAgents: "大而全"

**核心理念：**
- ✅ 企业级：完整的中间件、技能、状态管理系统
- ✅ 可扩展：模块化设计，易于定制
- ✅ 生产就绪：持久化、检查点、监控
- ✅ LangGraph 集成：利用成熟的图执行引擎

**适用场景：**
- 生产环境部署
- 复杂业务工作流
- 需要精细控制的场景
- 团队协作开发

**优势：**
1. **中间件系统**：灵活拦截和修改执行流程
2. **技能系统**：渐进式披露，按需加载
3. **状态管理**：LangGraph State + Checkpointer
4. **持久化**：支持多种后端（文件系统、数据库等）
5. **人机回环**：HumanInTheLoopMiddleware

**劣势：**
1. ❌ 复杂度较高
2. ❌ 学习曲线陡峭
3. ❌ 无代码生成能力
4. ❌ 依赖 LangGraph

---

## 📈 性能对比

### 执行效率

| 指标 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **启动时间** | ⚡ 快（纯 Python） | 🐢 慢（LangGraph 初始化） |
| **单步执行** | 取决于模式 | 相对稳定 |
| **Token 使用** | CodeAgent 可能更多 | 更可控 |
| **内存占用** | 低 | 中等 |

### 功能完整性

| 功能 | SmolAgents | DeepAgents |
|------|-----------|------------|
| ReAct 循环 | ✅ | ✅ |
| 子代理 | ✅ managed_agents | ✅ subagents |
| 规划能力 | ✅ planning_interval | ✅ 内置 todo 模式 |
| 流式输出 | ✅ generate_stream() | ✅ LangGraph 原生支持 |
| 中间件 | ⚠️ CallbackRegistry（按 Step 类型回调） | ✅ AgentMiddleware |
| MCP 协议 | ✅ MCPClient（mcpadapt） | ✅ 原生支持 |
| 技能系统 | ❌ | ✅ |
| 持久化 | ❌ | ✅ |
| 检查点 | ❌ | ✅ |
| 代码沙箱 | ✅ 多种执行器（local/Docker/E2B/Modal/Blaxel/Wasm） | ❌ |

---

## 🎯 选择建议

### 选择 SmolAgents 如果：

✅ 你需要**代码生成能力**（CodeAgent）  
✅ 你想要**快速原型开发**  
✅ 你关注**安全性和沙箱隔离**  
✅ 你的任务需要**灵活的 Python 代码执行**  
✅ 你喜欢**简洁的代码库**（易于理解和修改）  
✅ 你在**教育或研究环境**中使用  

**典型用例：**
```python
# 数学计算、数据处理、算法实现
agent = CodeAgent(tools=[calculator])
result = agent.run("Calculate the Fibonacci sequence up to 100")

# LLM 生成代码：
# fib = [0, 1]
# for i in range(2, 101):
#     fib.append(fib[-1] + fib[-2])
# final_answer(fib)
```

### 选择 DeepAgents 如果：

✅ 你需要**中间件系统**进行精细控制  
✅ 你需要**技能管理**和渐进式披露  
✅ 你需要**持久化和检查点**  
✅ 你在**生产环境**中部署  
✅ 你需要**人机回环**功能  
✅ 你的团队需要**标准化工作流**  

**典型用例：**
```python
# 企业级研究助手
agent = create_deep_agent(
    model=model,
    tools=[search, analyze],
    middleware=[LoggingMiddleware, AuthMiddleware],
    skills=["research", "writing"],
    backend=FilesystemBackend(...),
)

# 支持中断恢复、审计日志、权限控制
```

---

## 🔄 迁移指南

### 从 SmolAgents 迁移到 DeepAgents

**1. Agent 创建：**
```python
# SmolAgents
agent = CodeAgent(
    model=model,
    tools=[tool1, tool2],
    managed_agents=[sub_agent],
)

# DeepAgents
sub_agent_config = {
    "name": "sub-agent",
    "description": "...",
    "tools": [tool1, tool2],
}

agent = create_deep_agent(
    model=model,
    tools=[tool1, tool2],
    subagents=[sub_agent_config],
)
```

**2. 执行方式：**
```python
# SmolAgents
result = agent.run("task")

# DeepAgents
result = agent.invoke(
    {"messages": [{"role": "user", "content": "task"}]},
    context={"thread_id": "xxx"}
)
```

**3. 添加中间件：**
```python
# DeepAgents only
class CustomMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime):
        logger.info("Starting agent...")

agent = create_deep_agent(
    model=model,
    middleware=[CustomMiddleware()],
)
```

### 从 DeepAgents 迁移到 SmolAgents

**1. 移除中间件：**
```python
# DeepAgents
middleware=[LoggingMiddleware()]  # ❌ 移除

# SmolAgents - 使用内置日志
agent = CodeAgent(verbosity_level=2)  # ✅
```

**2. 移除技能系统：**
```python
# DeepAgents
skills=["skills"],  # ❌ 移除
backend=FilesystemBackend(...)  # ❌ 移除

# SmolAgents - 手动加载工具
tools = load_tools_from_directory("skills/")
agent = CodeAgent(tools=tools)
```

**3. 改用 CodeAgent 获得代码生成能力：**
```python
# DeepAgents - 仅工具调用
agent = create_deep_agent(tools=[...])

# SmolAgents - 代码生成
agent = CodeAgent(tools=[...])  # ✅ 可以生成任意 Python 代码
```

---

## 💡 最佳实践

### SmolAgents

1. **选择合适的 Agent 类型**
   ```python
   # 复杂逻辑 → CodeAgent
   code_agent = CodeAgent(tools=[...])
   
   # 简单 API 调用 → ToolCallingAgent
   tool_agent = ToolCallingAgent(tools=[...])
   ```

2. **启用规划**
   ```python
   agent = CodeAgent(planning_interval=4)  # 每 4 步重新规划
   ```

3. **设置合理的 max_steps**
   ```python
   agent = CodeAgent(max_steps=20)  # 避免无限循环
   ```

4. **使用远程执行器提高安全性**
   ```python
   # 方式 1: 通过 executor_type 参数（推荐）
   agent = CodeAgent(tools=[...], model=model, executor_type="docker")
   
   # 方式 2: 自定义执行器
   # 支持: local, docker, e2b, modal, blaxel, wasm
   agent = CodeAgent(tools=[...], model=model, executor_type="e2b")
   ```

### DeepAgents

1. **使用中间件进行日志记录**
   ```python
   agent = create_deep_agent(
       middleware=[ModelCallLoggingMiddleware()],
   )
   ```

2. **配置技能系统**
   ```python
   backend = FilesystemBackend(root_dir="/path/to/skills")
   agent = create_deep_agent(
       skills=["search", "analysis"],
       backend=backend,
   )
   ```

3. **启用检查点**
   ```python
   from langgraph.checkpoint.memory import MemorySaver
   
   checkpointer = MemorySaver()
   graph = agent.compile(checkpointer=checkpointer)
   ```

4. **使用人机回环**
   ```python
   from deepagents.middleware import HumanInTheLoopMiddleware
   
   agent = create_deep_agent(
       middleware=[HumanInTheLoopMiddleware()],
   )
   ```

---

## 📊 总结

| 维度 | SmolAgents | DeepAgents |
|------|-----------|------------|
| **复杂度** | ⭐⭐ 低 | ⭐⭐⭐⭐ 高 |
| **学习曲线** | 平缓 | 陡峭 |
| **灵活性** | ⭐⭐⭐⭐⭐ 极高 | ⭐⭐⭐⭐ 高 |
| **安全性** | ⭐⭐⭐⭐⭐ 沙箱保护 | ⭐⭐⭐ 依赖工具 |
| **可扩展性** | ⭐⭐⭐⭐ 好 | ⭐⭐⭐⭐⭐ 极好 |
| **生产就绪** | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 优秀 |
| **社区支持** | HuggingFace | LangChain 生态 |

**最终建议：**

- **研究和原型** → SmolAgents
- **生产和企业** → DeepAgents
- **需要代码生成** → SmolAgents CodeAgent
- **需要中间件/技能** → DeepAgents
- **两者结合** → 根据具体需求混合使用

---

*分析完成时间: 2026-04-09*  
*最后审查: 2026-04-29（已与 smolagents 1.24.x 源码比对并更新）*
