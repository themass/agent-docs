# OpenAI Agents Python SDK 架构文档索引

> **版本**: v0.17.2  
> **创建时间**: 2026-05-13  
> **分析方法**: 源码深度阅读（非官方文档推测）

> **与 Claude Agent SDK 对比**：[OPENAI_VS_CLAUDE_AGENT_SDK_COMPARISON.md](../../docs/OPENAI_VS_CLAUDE_AGENT_SDK_COMPARISON.md)（monorepo `docs/`）

---

## 📖 文档结构

**图解导读（推荐先读）**：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) · 跨项目 [索引](../../docs/CROSS_AGENT_DESIGN_INDEX.md)

本架构文档分为三个部分，涵盖 OpenAI Agents Python SDK 的完整设计：

### [第一部分：核心架构](./OPENAI_AGENTS_SDK_ARCHITECTURE_PART1.md)

**内容概览**：
- ✅ 第1章：核心设计理念
- ✅ 第2章：整体架构
- ✅ 第3章：运行时流程
- ✅ 第4章：核心模块详解
- ✅ 第5章：多Agent协作机制
- ✅ 第6章：工具系统

**关键图表**：
- 三层抽象架构图
- 模块依赖图
- 完整执行流程图（Mermaid时序图）
- 单轮执行详细流程（Mermaid流程图）
- NextStep决策逻辑图
- Handoff架构总览图
- Tool类型层次图

**核心源码文件**：
- `run.py` - Runner主入口
- `run_internal/run_loop.py` - 运行时循环（1921行）
- `agent.py` - Agent定义
- `items.py` - RunItem类型系统
- `handoffs/__init__.py` - Handoff机制
- `tool.py` - Tool定义（2000行）

---

### [第二部分：高级特性](./OPENAI_AGENTS_SDK_ARCHITECTURE_PART2.md)

**内容概览**：
- ✅ 第7章：Session持久化与会话管理（含 **§7.2a**：发给 LLM 的 input = Session/`RunItem`→`TResponseInputItem`；tool call/output 会持久化）
- ✅ 第8章：Guardrails护栏系统
- ✅ 第9章：Tracing追踪与监控
- ✅ 第10章：Sandbox沙箱环境
- ✅ 第11章：扩展能力（Memory、Voice、Realtime、MCP）
- ✅ 第12章：最佳实践与设计模式

**关键图表**：
- Session持久化流程图
- Guardrails执行时序图
- Tracing架构图
- Span层次结构图
- Sandbox架构图

**核心源码文件**：
- `run_internal/session_persistence.py` - 会话持久化（838行）
- `guardrail.py` - 护栏系统（344行）
- `tracing/spans.py` - 追踪Span（400行）
- `sandbox/local_shell.py` - 本地沙箱
- `memory/session.py` - 会话接口

---

## 🔍 快速查找指南

### 按功能查找

| 功能 | 章节 | 文档 |
|------|------|------|
| Agent定义 | 第4.1节 | Part 1 |
| 运行时循环 | 第3章 | Part 1 |
| Handoff机制 | 第5章 | Part 1 |
| 工具系统 | 第6章 | Part 1 |
| Session管理 | 第7章 | Part 2 |
| Guardrails | 第8章 | Part 2 |
| Tracing | 第9章 | Part 2 |
| Sandbox | 第10章 | Part 2 |
| MCP集成 | 第11.4节 | Part 2 |

### 按源码文件查找

| 源码文件 | 相关章节 | 文档 |
|----------|----------|------|
| `run.py` | 第3章 | Part 1 |
| `run_loop.py` | 第3.3节 | Part 1 |
| `agent.py` | 第4.1节 | Part 1 |
| `items.py` | 第4.2节 | Part 1 |
| `tool.py` | 第6章 | Part 1 |
| `handoffs/__init__.py` | 第5章 | Part 1 |
| `session_persistence.py` | 第7章 | Part 2 |
| `guardrail.py` | 第8章 | Part 2 |
| `tracing/spans.py` | 第9章 | Part 2 |

### 按设计模式查找

| 设计模式 | 说明 | 章节 |
|----------|------|------|
| Run-based Execution | 基于运行的执行模型 | 第1章 |
| Event Sourcing | 事件溯源模式 | 第1.1节 |
| Weak Reference | 弱引用避免内存泄漏 | 第4.2节 |
| Streaming-first | 流式优先架构 | 第3章 |
| NextStep Decision | 下一步决策系统 | 第4.3节 |
| Handoff Routing | Handoff路由机制 | 第5章 |
| Guardrail Pattern | 护栏验证模式 | 第8章 |
| Span Hierarchy | Span层次追踪 | 第9章 |

---

## 📊 架构要点总结

### 核心设计哲学

1. **Run-based Execution Model**
   - 所有交互封装为 `Run` 对象
   - 支持中断、恢复、审计
   - 事件溯源模式记录完整历史

2. **三层抽象架构**
   ```
   Runner (执行驱动层)
     ↓
   Agent (智能体层)
     ↓
   Tool (工具执行层)
   ```

3. **流式优先**
   - 原生支持 streaming
   - 通过 `asyncio.Queue` 实时推送事件
   - 三种事件类型：`RawResponsesStreamEvent`, `RunItemStreamEvent`, `AgentUpdatedStreamEvent`

4. **弱引用模式**
   - `RunItemBase._agent_ref: weakref.ReferenceType[Agent]`
   - 避免循环引用导致内存泄漏
   - 长时间运行服务的必要优化

### 关键数据结构

#### RunItem 类型系统

```python
RunItemBase[T]
├─ MessageOutputItem          # LLM输出的消息
├─ ToolCallItem               # 工具调用请求
├─ ToolCallOutputItem         # 工具调用结果
├─ HandoffCallItem            # Handoff调用请求
├─ HandoffOutputItem          # Handoff调用结果
├─ ReasoningItem              # 推理过程
├─ CompactionItem             # 压缩摘要
└─ ToolApprovalItem           # 工具审批
```

#### NextStep 决策系统

```python
NextStep
├─ NextStepRunAgain           # 继续执行（再次调用LLM）
├─ NextStepHandoff            # 转移到其他Agent
├─ NextStepFinalOutput        # 生成最终输出
└─ NextStepInterruption       # 暂停等待人工干预
```

#### StreamEvent 事件系统

```python
StreamEvent
├─ RawResponsesStreamEvent    # 原始LLM响应
├─ RunItemStreamEvent         # RunItem包装事件
│  ├─ message_output_created
│  ├─ handoff_requested
│  ├─ tool_called
│  ├─ tool_output
│  └─ ...
└─ AgentUpdatedStreamEvent    # Agent切换事件
```

### 执行流程概览

```
用户输入
  ↓
Runner.run()
  ↓
start_streaming()  ← 主循环入口
  ↓
┌─────────────────────────────┐
│  run_single_turn()          │
│  ├─ Phase 1: 准备输入       │
│  ├─ Phase 2: 收集工具       │
│  ├─ Phase 3: 调用LLM        │
│  ├─ Phase 4: 解析响应       │
│  └─ Phase 5: 执行动作       │
│     ├─ NextStepRunAgain     │
│     ├─ NextStepHandoff      │
│     ├─ NextStepFinalOutput  │
│     └─ NextStepInterruption │
└─────────────────────────────┘
  ↓
返回 RunResult
```

---

## 🎯 使用场景推荐

### 场景1：简单问答机器人

```python
from agents import Agent, Runner

assistant = Agent(
    name="Assistant",
    instructions="你是有帮助的AI助手",
)

result = await Runner.run(assistant, "你好")
```

**参考章节**：第4.1节（Agent定义）、第3章（运行时流程）

---

### 场景2：多Agent协作系统

```python
researcher = Agent(name="Researcher", instructions="...")
writer = Agent(name="Writer", handoffs=[researcher])
editor = Agent(name="Editor", handoffs=[writer])

result = await Runner.run(editor, "写一篇技术文章")
```

**参考章节**：第5章（Handoff机制）、第12.2节（多Agent协作模式）

---

### 场景3：带工具的智能体

```python
@function_tool
def search_web(query: str) -> str:
    """搜索网络"""
    ...

agent = Agent(
    name="ResearchAssistant",
    tools=[search_web],
)
```

**参考章节**：第6章（工具系统）、第12.3节（工具使用最佳实践）

---

### 场景4：会话持久化

```python
from agents.memory import InMemorySession

session = InMemorySession(session_id="chat_001")

# 第一轮
result1 = await Runner.run(agent, "你好", session=session)

# 第二轮（自动加载历史）
result2 = await Runner.run(agent, "继续刚才的话题", session=session)
```

**参考章节**：第7章（Session持久化）

---

### 场景5：内容安全检查

```python
@input_guardrail
def check_profanity(context, agent, input):
    """检查不当语言"""
    ...

@output_guardrail
def detect_pii(context, agent, output):
    """检测PII泄露"""
    ...

agent = Agent(
    name="PublicBot",
    input_guardrails=[check_profanity],
    output_guardrails=[detect_pii],
)
```

**参考章节**：第8章（Guardrails护栏系统）

---

### 场景6：安全的代码执行

```python
from agents.sandbox import DockerSandbox

sandbox = DockerSandbox(
    image="python:3.12-slim",
    memory_limit="256m",
    network_mode="none",
)

shell_tool = ShellTool(sandbox=sandbox)
agent = Agent(name="CodeExecutor", tools=[shell_tool])
```

**参考章节**：第10章（Sandbox沙箱环境）

---

## ⚠️ 常见陷阱与解决方案

### 陷阱1：无限循环

**症状**：Agent反复调用同一工具，无法结束

**原因**：工具返回的信息不足以让LLM做出决策

**解决方案**：
```python
result = await Runner.run(
    agent,
    input,
    max_turns=10,  # 设置最大轮次限制
)
```

**参考**：第3章（运行时流程）、第12.6节（常见陷阱）

---

### 陷阱2：Token超限

**症状**：API返回 `400 Request too large`

**原因**：对话历史过长

**解决方案**：
```python
# 方案1：限制历史长度
session = InMemorySession(
    session_id="chat_001",
    session_settings=SessionSettings(limit=20),
)

# 方案2：启用压缩
session = OpenAIConversationsSession(
    conversation_id="conv_long",
    session_settings=SessionSettings(
        compaction_args=OpenAIResponsesCompactionArgs(
            max_tokens=10000,
        )
    ),
)
```

**参考**：第7.6节（会话压缩）

---

### 陷阱3：工具参数错误

**症状**：LLM生成的工具调用参数不符合预期

**原因**：JSON Schema定义不清晰

**解决方案**：
```python
@function_tool
def my_tool(param1: str, param2: int = 10) -> str:
    """清晰的描述
    
    Args:
        param1: 详细的参数说明
        param2: 默认值说明
    """
    ...
```

**参考**：第6.2节（FunctionTool详解）、第12.3节（最佳实践）

---

### 陷阱4：内存泄漏

**症状**：长时间运行后内存持续增长

**原因**：循环引用未正确清理

**解决方案**：
```python
# SDK内部已使用弱引用，确保不要手动持有Agent强引用
# ❌ 错误做法
self.agent = agent  # 强引用

# ✅ 正确做法
self._agent_ref = weakref.ref(agent)  # 弱引用
```

**参考**：第4.2节（RunItem类型系统）、第1.3节（关键设计决策）

---

## 📈 性能优化建议

### 建议1：限制历史长度

```python
session = InMemorySession(
    session_settings=SessionSettings(limit=20),
)
```

**效果**：减少每次请求的Token消耗

**参考**：第7章（Session管理）

---

### 建议2：使用小模型做预处理

```python
preprocessor = Agent(
    name="Preprocessor",
    model="gpt-4o-mini",  # 便宜且快速
)
```

**效果**：降低总体成本

**参考**：第12.4节（性能优化技巧）

---

### 建议3：并行执行Guardrails

```python
agent = Agent(
    input_guardrails=[
        check_profanity(run_in_parallel=True),
        check_rate_limit(run_in_parallel=True),
    ],
)
```

**效果**：减少延迟

**参考**：第8.2节（Input Guardrail）

---

### 建议4：缓存工具结果

```python
from functools import lru_cache

@lru_cache(maxsize=100)
@function_tool
def get_exchange_rate(currency: str) -> float:
    ...
```

**效果**：避免重复调用外部API

**参考**：第12.4节（性能优化技巧）

---

## 🔧 调试技巧

### 技巧1：启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### 技巧2：检查RunItem历史

```python
result = await Runner.run(agent, input)
for item in result.items:
    print(f"{item.type}: {item.agent_name}")
```

---

### 技巧3：导出Trace

```python
trace = get_current_trace()
if trace:
    with open("trace.json", "w") as f:
        json.dump(trace.export(), f, indent=2)
```

---

### 技巧4：使用REPL交互式调试

```python
from agents import repl
repl.run(agent)
```

**参考**：第12.5节（调试技巧）

---

## 📚 附录

### A. 版本信息

- **SDK版本**: v0.17.2
- **Python要求**: >=3.10
- **分析时间**: 2026-05-13
- **源码路径**: `/Users/gqli/work/deepagents/openai-agents-python/src/agents`

### B. 源码统计

| 模块 | 文件数 | 总行数 | 核心文件 |
|------|--------|--------|----------|
| 运行时 | 22 | ~15,000 | `run_loop.py`, `turn_resolution.py` |
| 工具系统 | 18 | ~8,000 | `tool.py`, `tool_execution.py` |
| 追踪系统 | 15 | ~3,000 | `spans.py`, `processors.py` |
| 沙箱环境 | 18 | ~4,000 | `local_shell.py`, `daytona.py` |
| 其他 | 50+ | ~10,000 | 各种辅助模块 |
| **总计** | **123+** | **~40,000** | - |

### C. 关键文件速查

| 文件 | 行数 | 职责 |
|------|------|------|
| `run.py` | ~500 | Runner主入口 |
| `run_loop.py` | 1921 | 运行时循环 |
| `turn_resolution.py` | 1965 | 响应解析 |
| `tool_execution.py` | 2376 | 工具执行 |
| `agent.py` | ~300 | Agent定义 |
| `items.py` | ~400 | RunItem类型系统 |
| `tool.py` | ~2000 | Tool定义 |
| `session_persistence.py` | 838 | 会话持久化 |
| `guardrail.py` | 344 | 护栏系统 |
| `tracing/spans.py` | 400 | 追踪Span |

### D. 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 运行 | Run | 一次完整的Agent执行过程 |
| 轮次 | Turn | 一轮LLM调用+工具执行 |
| 事件溯源 | Event Sourcing | 所有交互记录为不可变事件列表 |
| Handoff | Handoff | Agent之间的转移机制 |
| 护栏 | Guardrail | 输入/输出验证机制 |
| Span | Span | 追踪中的一个操作单元 |
| 沙箱 | Sandbox | 隔离的执行环境 |

### E. 参考资料

- **官方文档**: https://openai.github.io/openai-agents-python/
- **GitHub仓库**: https://github.com/openai/openai-agents-python
- **示例代码**: `examples/` 目录
- **API参考**: `docs/ref/` 目录

---

## 📝 文档更新记录

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-05-13 | v0.17.2 | 初始版本，基于源码深度分析 |

---

## ✨ 文档特点

✅ **基于源码实证**：所有结论均有源码依据，无猜测或臆测  
✅ **完整覆盖**：涵盖核心架构、高级特性、最佳实践  
✅ **图表丰富**：包含架构图、时序图、流程图（Mermaid格式）  
✅ **实例充足**：每个概念都配有代码示例  
✅ **实用导向**：提供最佳实践、调试技巧、性能优化建议  

---

**文档结束**

如需了解具体实现细节，请查阅：
- [第一部分：核心架构](./OPENAI_AGENTS_SDK_ARCHITECTURE_PART1.md)
- [第二部分：高级特性](./OPENAI_AGENTS_SDK_ARCHITECTURE_PART2.md)
