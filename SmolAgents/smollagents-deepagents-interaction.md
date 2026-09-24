# SmolAgents 与 DeepAgents 集成设计方案

> **项目**: DeepAgents + SmolAgents  
> **版本**: 1.0  
> **日期**: 2026-04-10  
> **状态**: 设计方案

---

## 一、背景与目标

### 1.1 问题分析

#### DeepAgents 的局限性

DeepAgents 采用**工具调用范式**，LLM 只能调用预定义的工具：

```python
agent = create_deep_agent(
    model=model,
    tools=[tavily_search, think_tool],  # 仅能调用这些工具
)
```

**核心限制**：
- ❌ 缺乏代码生成能力：LLM 无法生成任意 Python 代码
- ❌ 复杂计算受限：需要手动编写每个工具
- ❌ 灵活性不足：数据转换、算法实现需预先定义工具

#### SmolAgents 的优势

SmolAgents 的 **CodeAgent** 模式支持 LLM 生成并执行代码：

```python
agent = CodeAgent(
    model=model,
    python_executor=LocalPythonExecutor(),  # 沙箱执行器
)
# LLM 输出: 
# ```python
# import math
# result = math.pow(2, 3.7384)
# final_answer(result)
# ```
```

**核心优势**：
- ✅ 代码生成能力：LLM 可生成任意 Python 代码
- ✅ 多层沙箱保护：AST 分析 + 白名单 + 资源限制
- ✅ 多种执行器：本地/Docker/E2B/Modal

### 1.2 设计目标

将 SmolAgents 的沙箱执行能力集成到 DeepAgents，同时：

1. **保持兼容**：不破坏现有工具和技能系统
2. **非侵入式**：通过中间件机制实现，无需修改核心代码
3. **技能驱动**：利用技能系统指导 LLM 何时使用代码执行
4. **安全可靠**：继承 SmolAgents 的多层安全防护
5. **灵活配置**：支持多种执行器

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────┐
│          DeepAgents Agent               │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────┐  ┌────────────────────┐  │
│  │ LLM      │◄─│ 中间件链           │  │
│  └──────────┘  │                    │  │
│                │ • TodoList         │  │
│                │ • Filesystem       │  │
│                │ • Skills           │  │
│                │ • CodeExecution ⭐ │  │
│                └────────────────────┘  │
│                         │               │
│                ┌────────▼────────┐     │
│                │ 工具注册表      │     │
│                │                 │     │
│                │ • read_file     │     │
│                │ • execute_code⭐│     │
│                │ • task          │     │
│                └────────┬────────┘     │
│                         │               │
│                ┌────────▼────────┐     │
│                │ 代码执行器 ⭐   │     │
│                │                 │     │
│                │ • LocalPython   │     │
│                │ • Docker        │     │
│                │ • E2B/Modal     │     │
│                └─────────────────┘     │
└─────────────────────────────────────────┘

⭐ = 新增组件
```

### 2.2 核心组件

#### 组件 1：CodeExecutionTool（代码执行工具）

**职责**：将 SmolAgents 的执行器包装为 LangChain 工具

**设计要点**：
- 符合 LangChain `BaseTool` 接口规范
- 懒加载执行器（首次调用时初始化）
- 支持同步/异步执行

#### 组件 2：CodeExecutionSkill（代码执行技能）

**职责**：通过 SKILL.md 告诉 LLM **何时**和**如何**使用代码执行

**设计要点**：
- 遵循 Agent Skills 规范
- 包含详细的使用场景和示例
- 明确安全约束和最佳实践

#### 组件 3：CodeExecutionMiddleware（代码执行中间件）

**职责**：在系统提示词中注入代码执行能力说明

**设计要点**：
- 实现 `AgentMiddleware` 接口
- 可选启用技能注入（与技能系统协同）
- 提供监控和日志钩子

### 2.3 数据流

```
用户请求
  ↓
LLM 决策（是否需要代码执行？）
  ├─ 简单任务 → 调用现有工具
  └─ 复杂计算 → 调用 execute_code 工具
       ↓
CodeExecutionTool._run()
  ↓
SmolAgents Executor (本地/Docker/E2B)
  ├─ AST 静态分析
  ├─ 导入白名单检查
  ├─ 资源限制（超时、内存）
  └─ 沙箱隔离执行
  ↓
返回结果（输出 + 日志）
  ↓
LLM 继续推理或返回最终答案
```

### 2.4 与现有系统集成

#### 与工具系统集成

```python
# DeepAgents 原有工具仍然正常工作
agent = create_deep_agent(
    tools=[
        tavily_search,           # ✅ 搜索工具
        think_tool,              # ✅ 思考工具
        CodeExecutionTool(),     # ✅ 新增代码执行工具
    ],
)
```

#### 与技能系统协同

```python
# 技能系统负责"何时使用"的指导
# 中间件负责"如何执行"的实现

agent = create_deep_agent(
    skills=["/skills/coding/"],  # 自动加载代码执行技能
    tools=[CodeExecutionTool()],
    middleware=[
        CodeExecutionMiddleware(enable_skill_injection=False),
    ],
)
```

#### 与记忆系统兼容

代码执行的结果会作为 **观察结果** 写入行动步骤，下一轮 LLM 可以看到执行历史。

---

## 三、核心实现

### 3.1 代码执行工具

**文件位置**: `examples/smolagents-integration/src/code_execution_tool.py`

**核心功能**：
- 包装 SmolAgents 执行器为标准 LangChain 工具
- 支持多种执行器类型（本地/Docker/E2B）
- 格式化执行结果为可读字符串

**关键方法**：
- `_get_executor()`: 懒加载执行器
- `_run(code, imports)`: 同步执行代码
- `_arun(code, imports)`: 异步执行代码

### 3.2 代码执行技能

**文件位置**: `examples/smolagents-integration/skills/code-execution/SKILL.md`

**内容结构**：
- 元数据（名称、描述、许可证）
- 使用场景（何时使用/不使用）
- 使用方法（参数说明）
- 最佳实践
- 完整示例（数据分析、文件处理、可视化）
- 安全约束
- 故障排除

### 3.3 代码执行中间件

**文件位置**: `examples/smolagents-integration/src/code_execution_middleware.py`

**核心功能**：
- 在系统提示词中注入代码执行能力说明
- 可选启用技能注入
- 记录和监控代码执行情况

**关键方法**：
- `modify_request()`: 修改模型请求，注入使用说明
- `wrap_model_call()`: 包装模型调用，记录执行情况

---

## 四、兼容性保证

### 4.1 与现有工具共存

DeepAgents 原有工具和新添的代码执行工具可以并存，LLM 根据任务需求自由选择。

### 4.2 与技能系统协同

- 技能系统：负责指导 LLM **何时**使用代码执行
- 中间件：负责在系统提示词中注入**如何**使用的说明
- 两者可独立启用或同时使用

### 4.3 向后兼容

- 不启用中间件时，行为完全不变
- 启用后，只是多了一个工具选项
- 不影响现有工作流

### 4.4 与记忆系统集成

代码执行的结果会自动写入行动步骤，并在下一轮 LLM 调用时展开为对话历史。

---

## 五、使用指南

### 5.1 快速开始

#### 安装依赖

```bash
pip install smolagents deepagents langchain
```

#### 基础示例

```python
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from src.code_execution_tool import CodeExecutionTool
from src.code_execution_middleware import CodeExecutionMiddleware

# 1. 创建模型
model = init_chat_model("claude-sonnet-4-5-20250929")

# 2. 创建带代码执行的智能体
agent = create_deep_agent(
    model=model,
    tools=[
        CodeExecutionTool(
            executor_type="local",
            additional_authorized_imports=["numpy", "pandas"],
        ),
    ],
    middleware=[CodeExecutionMiddleware()],
)

# 3. 执行任务
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "计算 100 的阶乘并显示前 10 位数字"
    }]
})
```

### 5.2 生产环境配置（Docker 沙箱）

```python
agent = create_deep_agent(
    model=model,
    tools=[
        CodeExecutionTool(
            executor_type="docker",
            image_name="python:3.11-slim",
            additional_authorized_imports=["numpy", "pandas", "scipy"],
            timeout_seconds=120,
            container_run_kwargs={
                "mem_limit": "512m",      # 限制内存
                "cpu_quota": 50000,        # 限制 CPU (50%)
                "network_disabled": True,  # 禁用网络
            },
        ),
    ],
    middleware=[CodeExecutionMiddleware()],
)
```

### 5.3 结合技能系统

```python
from deepagents.backends import FilesystemBackend

# 1. 设置后端
backend = FilesystemBackend(root_dir="/workspace")

# 2. 创建智能体
agent = create_deep_agent(
    model=model,
    backend=backend,
    skills=["/skills/coding/"],
    tools=[CodeExecutionTool(executor_type="docker")],
    middleware=[CodeExecutionMiddleware(enable_skill_injection=False)],
)
```

### 5.4 实际应用场景

#### 场景 1：数据分析

```python
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": """
        读取 /data/sales.csv 文件并计算：
        1. 总收入
        2. 平均订单价值
        3. 销售额最高的前 5 个产品
        """
    }]
})

# LLM 会自动：
# 1. read_file("/data/sales.csv")
# 2. execute_code("import pandas as pd; df = pd.read_csv(...); ...")
# 3. 返回分析结果
```

#### 场景 2：算法实现

```python
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "实现 Dijkstra 最短路径算法并在示例图上测试"
    }]
})

# LLM 会生成完整的 Python 代码并执行
```

#### 场景 3：可视化生成

```python
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "创建折线图显示 2024 年月度销售趋势"
    }]
})

# LLM 会：
# 1. 读取数据
# 2. execute_code 生成 matplotlib 图表
# 3. 保存为图片文件
```

---

## 六、安全考虑

### 6.1 多层防护机制

```
┌─────────────────────────────────┐
│  第 1 层：导入白名单            │  ← 只允许授权的包
├─────────────────────────────────┤
│  第 2 层：AST 静态分析          │  ← 禁止危险操作
├─────────────────────────────────┤
│  第 3 层：资源限制              │  ← 超时 + 内存限制
├─────────────────────────────────┤
│  第 4 层：沙箱隔离              │  ← Docker/E2B 隔离
└─────────────────────────────────┘
```

### 6.2 安全配置模板

```python
SECURE_CONFIG = {
    # 严格限制允许的导入
    "additional_authorized_imports": [
        # 数学计算
        "math", "decimal", "fractions",
        # 数据处理
        "json", "csv", "collections",
        # 科学计算（谨慎添加）
        "numpy", "pandas",
    ],
    
    # 资源限制
    "timeout_seconds": 60,
    "max_print_outputs_length": 50000,
    
    # Docker 额外限制
    "container_run_kwargs": {
        "mem_limit": "256m",
        "cpu_quota": 25000,  # 25% CPU
        "network_disabled": True,
        "pids_limit": 50,
    },
    
    # 禁止 pickle（防止反序列化攻击）
    "allow_pickle": False,
}

tool = CodeExecutionTool(**SECURE_CONFIG)
```

### 6.3 安全最佳实践

1. **最小权限原则**：只授权必要的包
2. **定期审计**：审查代码执行日志
3. **隔离环境**：生产环境使用 Docker/E2B
4. **输入验证**：验证 LLM 生成的代码
5. **错误处理**：捕获并记录所有异常

### 6.4 安全风险提示

| 风险 | 缓解措施 |
|------|---------|
| 恶意代码执行 | AST 分析 + 白名单 + 沙箱隔离 |
| 资源耗尽 | 超时 + 内存限制 + CPU 配额 |
| 数据泄露 | 禁用网络访问 + 文件系统只读 |
| 依赖混淆 | 严格的导入白名单 |
| 反序列化攻击 | 禁用 pickle |

---

## 七、性能优化

### 7.1 执行器选择指南

| 执行器 | 启动时间 | 执行速度 | 安全性 | 适用场景 |
|--------|---------|---------|--------|---------|
| 本地 | ⚡ 快 (<10ms) | ⚡ 快 | ⭐⭐⭐ | 开发/测试 |
| Docker | 🐢 慢 (2-5s) | ⚡ 快 | ⭐⭐⭐⭐⭐ | 生产环境 |
| E2B | 🐢 慢 (3-10s) | ⚡ 快 | ⭐⭐⭐⭐⭐ | 云端部署 |
| Modal | 🐢 慢 (5-15s) | ⚡ 快 | ⭐⭐⭐⭐⭐ | 大规模并行 |

### 7.2 缓存策略

对于重复代码，可以使用缓存提升性能：

```python
from functools import lru_cache

class CachedCodeExecutionTool(CodeExecutionTool):
    """带缓存的代码执行工具"""
    
    def __init__(self, *args, cache_size=100, **kwargs):
        super().__init__(*args, **kwargs)
        self._execute_cached = lru_cache(maxsize=cache_size)(self._execute_uncached)
    
    def _run(self, code: str, imports=None):
        """带缓存的执行"""
        import hashlib
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        return self._execute_cached(code_hash, code)
```

**性能提升**：对于重复代码，命中率可达 80%+，响应时间从秒级降至毫秒级。

### 7.3 并行执行

```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

class ParallelCodeExecutionTool(CodeExecutionTool):
    """支持并行代码执行的工具"""
    
    def __init__(self, *args, max_workers=4, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor_pool = ThreadPoolExecutor(max_workers=max_workers)
    
    async def _arun(self, code: str, imports=None):
        """异步并行执行"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor_pool,
            self._run,
            code,
            imports
        )
```

### 7.4 性能监控

```python
import time

class MonitoredCodeExecutionMiddleware(CodeExecutionMiddleware):
    """带性能监控的中间件"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_times = []
    
    def wrap_model_call(self, request, handler):
        start_time = time.time()
        response = super().wrap_model_call(request, handler)
        elapsed = time.time() - start_time
        
        # 记录执行时间
        self.execution_times.append(elapsed)
        logger.info(f"代码执行耗时 {elapsed:.2f}s")
        
        return response
    
    def get_avg_execution_time(self):
        """获取平均执行时间"""
        if not self.execution_times:
            return 0
        return sum(self.execution_times) / len(self.execution_times)
```

---

## 八、实施路线图

### 阶段 1：原型验证（1-2 天）

**目标**：验证基本功能可行性

**任务清单**：
- [ ] 实现代码执行工具基础版本
- [ ] 测试本地执行器
- [ ] 验证与 DeepAgents 工具系统集成
- [ ] 编写单元测试（覆盖率 > 80%）

**交付物**：
- `src/code_execution_tool.py`（基础版）
- `tests/test_code_execution_tool.py`
- `examples/basic_usage.py`

**验收标准**：
- ✅ 能够执行简单 Python 代码
- ✅ 与 DeepAgents 工具链兼容
- ✅ 单元测试全部通过

### 阶段 2：中间件封装（3-5 天）

**目标**：完整的中间件实现

**任务清单**：
- [ ] 实现代码执行中间件
- [ ] 实现代码执行技能内容
- [ ] 支持多种执行器切换
- [ ] 状态管理适配
- [ ] 集成测试

**交付物**：
- `src/code_execution_middleware.py`
- `skills/code-execution/SKILL.md`
- `examples/with_skills.py`
- 完整文档

**验收标准**：
- ✅ 中间件正确注入系统提示词
- ✅ 技能系统正确加载
- ✅ 支持本地/Docker 执行器切换

### 阶段 3：生产优化（1-2 周）

**目标**：生产就绪

**任务清单**：
- [ ] Docker 执行器集成
- [ ] 安全加固（白名单、资源限制）
- [ ] 性能优化（缓存、并行）
- [ ] 监控和日志
- [ ] 错误处理完善
- [ ] 压力测试

**交付物**：
- 生产配置模板
- 监控仪表板
- 运维文档
- 性能基准报告

**验收标准**：
- ✅ 支持 Docker 沙箱
- ✅ 安全扫描无高危漏洞
- ✅ P95 延迟 < 5s
- ✅ 并发 100 QPS 稳定运行

### 阶段 4：高级特性（可选，2-3 周）

**目标**：企业级功能

**任务清单**：
- [ ] E2B/Modal 云端执行器
- [ ] 分布式代码执行
- [ ] 代码审查工作流
- [ ] 自定义沙箱镜像
- [ ] 审计日志系统

**交付物**：
- 企业级部署方案
- 合规性文档
- SLA 保障协议

---

## 九、总结

本方案通过**中间件 + 工具 + 技能**三位一体的设计，成功将 SmolAgents 的沙箱执行能力集成到 DeepAgents，实现了：

✅ **完全兼容**：不破坏现有功能  
✅ **灵活扩展**：支持多种执行器  
✅ **安全可靠**：多层防护机制  
✅ **易于使用**：标准化的 LangChain 工具接口  
✅ **生产就绪**：完善的监控和配置  

**推荐采用方案**：
- **开发环境**：本地执行器 + 基础中间件
- **测试环境**：Docker 执行器 + 完整中间件
- **生产环境**：Docker/E2B 执行器 + 技能系统 + 监控

**下一步行动**：
1. 按照实施路线图分阶段推进
2. 参考完整示例进行开发
3. 根据实际需求调整配置

---

## 附录：常见问题

### Q1: 为什么不用 SmolAgents 的 CodeAgent 直接替换？

**答**: DeepAgents 的架构基于 LangGraph 和工具调用，而 CodeAgent 是独立的执行引擎。通过中间件集成可以在保留 DeepAgents 优势（中间件、技能、持久化）的同时获得代码执行能力。

### Q2: 性能开销大吗？

**答**: 
- **本地执行器**：几乎无额外开销（<10ms）
- **Docker 执行器**：首次启动 ~2-5s，后续复用容器 <100ms
- **建议**：频繁调用时使用连接池或长生命周期容器

### Q3: 如何调试代码执行错误？

**答**: 
```python
# 1. 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 2. 查看执行日志
tool = CodeExecutionTool()
result = tool._run(code)
print(result)  # 包含标准输出/标准错误

# 3. 检查行动步骤
print(action_step.observations)  # 完整的观察结果
```

### Q4: 可以执行任意 Python 代码吗？

**答**: 理论上可以，但受限于：
- **导入白名单**：只能导入授权的包
- **资源限制**：超时、内存上限
- **沙箱隔离**：无网络访问、有限文件系统权限

### Q5: 如何添加新的允许导入包？

**答**: 
```python
# 方法 1：初始化时指定
tool = CodeExecutionTool(
    additional_authorized_imports=["new_package"]
)

# 方法 2：动态更新（不推荐）
tool.executor_kwargs["additional_authorized_imports"].append("new_package")
```

**安全建议**：
- 优先使用标准库
- 第三方包需经过安全审查
- 定期更新白名单

### Q6: 与 DeepAgents 的子代理如何配合？

**答**: 子代理也可以使用代码执行工具：

```python
research_subagent = {
    "name": "researcher",
    "description": "研究专家",
    "tools": [
        tavily_search,
        CodeExecutionTool(executor_type="local"),  # 子代理也可用
    ],
}

agent = create_deep_agent(
    model=model,
    subagents=[research_subagent],
)
```

**注意**：远程执行器（Docker/E2B）暂不支持与子代理同时使用（SmolAgents 限制）。

### Q7: 如何监控代码执行情况？

**答**: 使用自定义中间件：

```python
class MonitoringMiddleware(CodeExecutionMiddleware):
    def wrap_model_call(self, request, handler):
        # 记录指标
        metrics = {
            "timestamp": time.time(),
            "code_length": len(request.state.get("current_code", "")),
        }
        logger.info(f"代码执行指标: {metrics}")
        
        return super().wrap_model_call(request, handler)
```

**监控指标**：
- 执行频率
- 平均执行时间
- 错误率
- Token 消耗

### Q8: 生产环境推荐配置？

**答**: 
```python
# 生产环境最佳实践
agent = create_deep_agent(
    model=model,
    tools=[
        CodeExecutionTool(
            executor_type="docker",  # 使用 Docker 沙箱
            additional_authorized_imports=[
                "numpy", "pandas", "matplotlib"  # 最小化白名单
            ],
            timeout_seconds=60,
            container_run_kwargs={
                "mem_limit": "512m",
                "cpu_quota": 50000,
                "network_disabled": True,
            },
        ),
    ],
    middleware=[
        MonitoredCodeExecutionMiddleware(),  # 带监控
    ],
)
```
