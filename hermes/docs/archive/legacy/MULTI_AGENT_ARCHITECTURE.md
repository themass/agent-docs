# 多 Agent 架构

<!-- legacy-review:start -->
> **2026-10-15 校订导航**：同一引擎怎样生成独立子代理。\
> **核对范围**：校正独立预算、构造默认与 delegation 的 250 默认；旧性能/token 数仅为样例。\
> **适用基线**：本地源码 `60d00c5633ad`；不是最新发布版本声明。原稿版本、行号、性能数字与长代码块若未在校订范围内，仍按历史示例阅读。
> **先读当前结论**：[当前实现导读](CURRENT_IMPLEMENTATION.md#current-delegation) · **现行分卷**：[07-multi-agent-and-kanban.md](../../volumes/07-multi-agent-and-kanban.md) · [具体改动与未验证项](REVIEW_AND_CHANGES.md) · [返回全目录](README.md)

<!-- legacy-review:end -->
<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 概述](#section-1)
  - [1.1 为什么需要多 Agent 架构?](#section-1-1)
  - [1.2 核心概念](#section-1-2)
- [2. 主代理 vs 子代理对比](#section-2)
  - [2.1 完整对比表](#section-2-1)
  - [2.2 关键差异总结](#section-2-2)
- [3. Agentic Loop 共享机制](#section-3)
  - [3.1 核心设计原则](#section-3-1)
  - [3.2 架构示意图](#section-3-2)
  - [3.3 为什么这样设计？](#section-3-3)
  - [3.4 隔离机制详解](#section-3-4)
  - [3.5 执行流程对比](#section-3-5)
  - [3.6 并行执行模型](#section-3-6)
  - [3.7 设计哲学总结](#section-3-7)
- [4. 子代理创建流程](#section-4)
  - [4.1 完整时序图](#section-4-1)
  - [4.2 关键代码片段](#section-4-2)
- [5. delegate_task：创建、调度、执行与结果回收](#section-5)
  - [5.1 delegate_task - 任务委派工具](#section-5-1)
- [6. Prompt 差异详解](#section-6)
  - [6.1 主代理 System Prompt 结构](#section-6-1)
  - [6.2 子代理 System Prompt 结构 (双路径)](#section-6-2)
  - [6.3 设计哲学](#section-6-3)
- [7. 工具集隔离机制](#section-7)
  - [7.1 Blocked Toolsets](#section-7-1)
  - [7.2 默认子代理工具集](#section-7-2)
  - [7.3 Orchestrator 特权](#section-7-3)
  - [7.4 工具集对比表](#section-7-4)
- [8. 迭代预算系统](#section-8)
  - [8.1 预算对比](#section-8-1)
  - [8.2 关键设计](#section-8-2)
  - [8.3 Refund 机制](#section-8-3)
- [9. 会话持久化](#section-9)
  - [9.1 Session ID 层次结构](#section-9-1)
  - [9.2 数据库查询](#section-9-2)
  - [9.3 持久化对比](#section-9-3)
- [10. 回调中继机制](#section-10)
  - [10.1 Progress Callback 中继](#section-10-1)
  - [10.2 CLI 输出示例](#section-10-2)
  - [10.3 线程间通信机制详解](#section-10-3)
  - [10.4 TUI 集成](#section-10-4)
- [11. 深度限制与角色控制](#section-11)
  - [11.1 深度限制机制](#section-11-1)
  - [11.2 Role 语义](#section-11-2)
  - [11.3 使用示例](#section-11-3)
- [12. 并行执行模型](#section-12)
  - [12.1 Batch Mode 实现](#section-12-1)
  - [12.2 性能对比](#section-12-2)
  - [12.3 活跃子代理注册表](#section-12-3)
- [13. 中断与 Human-in-the-Loop](#section-13)
  - [13.1 概念：Interrupt vs HITL](#section-13-1)
  - [13.2 Hermes 多层中断](#section-13-2)
  - [13.3 HITL：审批（Approval）](#section-13-3)
  - [13.4 HITL：澄清（Clarify）](#section-13-4)
  - [13.5 与 §9 反向控制的衔接](#section-13-5)
- [14. 设计哲学与实践](#section-14)
  - [14.1 设计哲学](#section-14-1)
  - [14.2 最佳实践](#section-14-2)
  - [14.3 故障排查](#section-14-3)
- [15. 子代理与通用压缩的边界](#section-15)
- [16. 0.19 增量：Live-viewable 子 Agent transcript](#section-16)
- [17. 附录：跨框架中断 / HITL 对照](#section-17)
  - [17.1 总览表](#section-17-1)
  - [17.2 Hermes 在对比中的位置（摘要）](#section-17-2)
  - [17.3 实践原则（摘录）](#section-17-3)
  - [17.4 HITL设计模式](#section-17-4)
<!-- visible-toc:end -->




> **原稿文档状态（历史标签）**: Canonical（合并去重版）\
> **原稿版本锚点（历史）**: 0.19.0 · **核对**: 2026-07-31 · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)\
> **合并自**: `MULTI_AGENT_ARCHITECTURE.md`（Part 1）+ `SUBAGENT_INTERRUPT_AND_HITL_COMPARISON.md`  
> **已删除**: 历史 Part 2 伪代码（`coordinator/` / `AgentScheduler` 等非源码）；跨框架长代码 dump 改为摘要表。  
> **源码**: `tools/delegate_tool.py`, `run_agent.py` / `agent/conversation_loop.py`, `tools/approval.py`, `tools/clarify_tool.py`

---

<a id="1-概述"></a>
<a id="section-1"></a>
## 1. 概述

<a id="11-为什么需要多-agent-架构"></a>
<a id="section-1-1"></a>
### 1.1 为什么需要多 Agent 架构?

**问题空间**:

| 问题 | 说明 | 影响 |
|------|------|------|
| **上下文污染** | 复杂任务的中间推理会污染父对话 | 后续响应质量下降 |
| **预算失控** | 单个子任务可能耗光父代理的全部迭代预算 | 父任务无法完成 |
| **并行需求** | 某些任务天然可并行 (如同时研究多个主题) | 串行执行效率低 |
| **专业化分工** | 不同子任务可能需要不同的工具集或技能 | 单一代理难以胜任 |
| **可观测性** | 需要清晰的任务分解视图和进度追踪 | 用户无法了解进展 |

**解决方案**:
- ✅ 子代理拥有**干净上下文** (无父对话历史)
- ✅ 子代理有**独立预算** (不吞噬父预算)
- ✅ 支持**并行执行** (ThreadPoolExecutor)
- ✅ **受限工具集** (防止滥用)
- ✅ **进度中继** (父代理可见子代理活动)

<a id="12-核心概念"></a>
<a id="section-1-2"></a>
### 1.2 核心概念

**delegate_task 工具**:
```python
# registry.register(...) 显式调用（非装饰器）
def delegate_task(
    goal: str,                    # 任务目标
    context: Optional[str] = None, # 可选上下文
    toolsets: Optional[List[str]] = None, # 工具集
    tasks: Optional[List[Dict]] = None,   # Batch mode
    role: str = "leaf",           # leaf/orchestrator
    parent_agent=None,            # 注入的父代理引用
) -> str:
    """Spawn child agents with isolated context and restricted toolsets."""
```

**两种模式**:
1. **Single Mode**: `goal` + 可选参数
2. **Batch Mode**: `tasks` 数组,每个元素是一个任务对象

---

<a id="2-主代理-vs-子代理对比"></a>
<a id="section-2"></a>
## 2. 主代理 vs 子代理对比

<a id="21-完整对比表"></a>
<a id="section-2-1"></a>
### 2.1 完整对比表

| 维度 | 主代理 (Parent) | Leaf 子代理 | Orchestrator 子代理 |
|------|----------------|------------|-------------------|
| **System Prompt** | `_build_system_prompt()` 全14层 (~2000-5000 tokens) | `_build_system_prompt()` 部分层 + `_build_child_system_prompt()` ephemeral (~600-1400 tokens) | 同 Leaf + 委派能力说明 (~800-1600 tokens) |
| **Memory 注入** | ✅ `<memory-context>` | ❌ skip_memory=True | ❌ skip_memory=True |
| **Context Files** | ✅ AGENTS.md/SOUL.md | ❌ skip_context_files=True | ❌ skip_context_files=True |
| **Skills 索引** | ✅ 渐进披露 | ✅ (skills工具集未被blocked, `build_skills_system_prompt()` 正常执行) | ✅ 同Leaf |
| **core 工具** | ✅ | ✅ | ✅ |
| **web 工具** | ✅ | ✅ | ✅ |
| **memory 工具** | ✅ | ❌ blocked | ❌ blocked |
| **clarify 工具** | ✅ | ❌ blocked | ❌ blocked |
| **execute_code** | ✅ | ❌ blocked | ❌ blocked |
| **delegate_task** | ✅ | ❌ blocked | ✅ (重新添加) |
| **迭代预算** | 构造器默认 `sys.maxsize`，入口可覆盖 | 独立；delegation 未配置时 250 | 独立；delegation 未配置时 250 |
| **Session ID** | `sess-abc123` | `sess-abc123:sub:uuid` | `sess-abc123:sub:uuid` |
| **Parent Session ID** | N/A | `sess-abc123` | `sess-abc123` |
| **Memory Sync** | ✅ sync_all() | ❌ | ❌ |
| **quiet_mode** | False (CLI 显示) | True (静默) | True (静默) |
| **Progress Callback** | CLI spinner / Gateway | 中继到父代理 | 中继到父代理 |

<a id="22-关键差异总结"></a>
<a id="section-2-2"></a>
### 2.2 关键差异总结

**Prompt 差异**:
- 主代理: ~2000-5000 tokens (完整14层: 人格 + Skills索引 + 项目知识 + Memory + 环境)
- 子代理: ~600-1400 tokens (`_cached_system_prompt` 部分层 + ephemeral 任务指令)
  - 保留: 默认身份、Hermes帮助指引、Skills索引、工具使用强制、时间戳、环境提示、平台提示
  - 跳过: SOUL.md、Context Files、Memory
  - 追加: ephemeral 任务目标+上下文 (由 `_build_child_system_prompt()` 生成)

**工具集差异**:
- 主代理: 全部工具 (包括 delegation/memory/clarify)
- 子代理: 受限工具集 (blocked: delegation/clarify/memory/code_execution; 保留: skills/session_search 等)

**预算差异**:
- 主代理: 构造器默认 `sys.maxsize`，实际入口可覆盖
- 子代理: 未配置时 250 轮 (独立,不与父共享)

**记忆差异**:
- 主代理: 读写 MEMORY.md,预取外部记忆
- 子代理: skip_memory=True,无记忆访问

---

<a id="3-agentic-loop-共享机制"></a>
<a id="section-3"></a>
## 3. Agentic Loop 共享机制

<a id="31-核心设计原则"></a>
<a id="section-3-1"></a>
### 3.1 核心设计原则

**关键发现**: **子 Agent 和主 Agent 共用同一套 `run_conversation` 实现**（`agent/conversation_loop.py`；`AIAgent.run_conversation` 为转发）。

这不是通过不同的代码实现，而是通过**配置隔离**来实现行为差异。

```python
    # tools/delegate_tool.py:L1491-1494
def _run_with_thread_capture():
    _worker_thread_holder["t"] = threading.current_thread()
    return child.run_conversation(  # ← 调用的是同一个方法
        user_message=goal,
        task_id=child_task_id,
    )
```

<a id="32-架构示意图"></a>
<a id="section-3-2"></a>
### 3.2 架构示意图

```mermaid
graph TB
    subgraph "Main Thread"
        MainAgent[AIAgent Instance<br/>Main Task]
        MainAgent -->|run_conversation| MainLoop[Agentic Loop]
    end
    
    subgraph "ThreadPool Worker 1"
        Child1[AIAgent Instance<br/>Child Task 1]
        Child1 -->|run_conversation| ChildLoop1[Same Agentic Loop]
    end
    
    subgraph "ThreadPool Worker 2"
        Child2[AIAgent Instance<br/>Child Task 2]
        Child2 -->|run_conversation| ChildLoop2[Same Agentic Loop]
    end
    
    MainAgent -->|delegate_task| Child1
    MainAgent -->|delegate_task| Child2
    
    style MainAgent fill:#e1f5ff
    style Child1 fill:#fff4e1
    style Child2 fill:#fff4e1
    style MainLoop fill:#e8f5e9
    style ChildLoop1 fill:#e8f5e9
    style ChildLoop2 fill:#e8f5e9
```

**图例说明**：
- 🔵 蓝色：主 Agent 实例（完整配置）
- 🟡 黄色：子 Agent 实例（受限配置）
- 🟢 绿色：相同的 Agentic Loop 逻辑

<a id="33-为什么这样设计"></a>
<a id="section-3-3"></a>
### 3.3 为什么这样设计？

<a id="优势对比"></a>
<a id="section-3-3-1"></a>
#### 3.3.1 **优势对比**

| 方案 | 优点 | 缺点 |
|------|------|------|
| **共享 Loop + 配置隔离**<br/>(当前方案) | ✅ 代码复用<br/>✅ 行为一致<br/>✅ 易于维护<br/>✅ 简化调试 | - |
| **独立 Loop 实现**<br/>(替代方案) | - | ❌ 代码重复<br/>❌ 行为不一致<br/>❌ 维护成本高<br/>❌ 容易出 bug |

<a id="核心优势"></a>
<a id="section-3-3-2"></a>
#### 3.3.2 **核心优势**

**1. 代码复用**

不需要维护两套 agentic loop 逻辑；所有 Agent 都走相同路径：LLM 调用 → 工具选择 → 工具执行 → 结果处理 → 迭代控制。


**2. 一致性保证**
```python
    # 子 Agent 的行为与主 Agent 完全一致：
    # - 相同的错误处理机制
    # - 相同的重试逻辑
    # - 相同的超时控制
    # - 相同的中断响应
    # - 相同的进度回调
```

**3. 可预测性**
```python
    # 子 Agent 的行为可以通过配置精确控制：
child = AIAgent(
    enabled_toolsets=child_toolsets,      # ← 受限工具集
    ephemeral_system_prompt=child_prompt, # ← 专用 prompt
    skip_memory=True,                     # ← 禁用记忆
    skip_context_files=True,              # ← 跳过上下文文件
    iteration_budget=None,                # ← 独立预算
)
```

**4. 简化调试**
```python
    # 所有 Agent 都走相同的代码路径
    # Bug 修复一次，所有 Agent 受益
    # 日志格式统一，便于追踪
```

<a id="34-隔离机制详解"></a>
<a id="section-3-4"></a>
### 3.4 隔离机制详解

虽然使用同一个 `run_conversation`，但通过以下配置实现隔离：

<a id="a-system-prompt-隔离-双路径机制"></a>
<a id="section-3-4-1"></a>
#### 3.4.1 **A. System Prompt 隔离 (双路径机制)**

子 Agent 的有效 system prompt 由两部分组成:

1. **`_cached_system_prompt`** — 由 `_build_system_prompt()` 构建 (与主 Agent 同一函数, 但因 `skip_context_files=True` / `skip_memory=True` 跳过部分层)
2. **`ephemeral_system_prompt`** — 由 `_build_child_system_prompt()` 构建 (任务专用指令)

```python
    # run_agent.py — API 调用时的拼接逻辑
effective_system = self._cached_system_prompt or ""
if self.ephemeral_system_prompt:
    effective_system = (effective_system + "\n\n" + self.ephemeral_system_prompt).strip()
```

```python
    # 主 Agent: 完整14层 (~2000-5000 tokens)
    # _build_system_prompt() 输出全部层:
    #   SOUL.md / DEFAULT_AGENT_IDENTITY
    #   HERMES_AGENT_HELP_GUIDANCE
    #   Skills 索引 + SKILLS_GUIDANCE
    #   Context Files (AGENTS.md 等)
    #   Memory (<memory-context>)
    #   TOOL_USE_ENFORCEMENT_GUIDANCE
    #   Timestamps
    #   Environment Hints
    #   PLATFORM_HINTS
    #   Nous subscription prompt

    # 子 Agent: _cached_system_prompt (~400-800 tokens) + ephemeral (~200-600 tokens)
    # _build_system_prompt() 部分层 (因 skip_context_files/skip_memory):
    #   DEFAULT_AGENT_IDENTITY (SOUL.md不加载, 因 load_soul_identity=False 且 skip_context_files=True)
    #   HERMES_AGENT_HELP_GUIDANCE
    #   Skills 索引 + SKILLS_GUIDANCE  ← 注意: skills 工具集未被 blocked, 所以仍然注入
    #   TOOL_USE_ENFORCEMENT_GUIDANCE
    #   Timestamps
    #   build_environment_hints()
    #   PLATFORM_HINTS
    #   跳过: SOUL.md, Context Files, Memory

child_prompt = _build_child_system_prompt(
    goal=goal,
    context=context,
    role=role,
    child_depth=child_depth,
    max_spawn_depth=max_spawn_depth,
)
    # 输出示例:
    # """
    # You are a focused assistant tasked with:
    # Goal: Research Python async patterns
    # 
    # Important rules:
    # - Be thorough but concise
    # - Your response is returned to parent as summary
    # - Do NOT use memory or clarify tools
    # """
```

<a id="b-工具集隔离-toolset-级别过滤"></a>
<a id="section-3-4-2"></a>
#### 3.4.2 **B. 工具集隔离 (Toolset 级别过滤)**

```python
    # 主 Agent: 全部 toolsets
toolsets = ["core", "web", "browser", "vision", "skills",
            "session_search", "memory", "delegation", "clarify",
            "code_execution", ...]

    # 子 Agent: 通过 _strip_blocked_tools() 过滤整个 toolset
def _strip_blocked_tools(toolsets: List[str]) -> List[str]:
    blocked_toolset_names = {
        "delegation",      # delegate_task
        "clarify",         # clarify
        "memory",          # memory 管理工具
        "code_execution",  # execute_code
    }
    return [t for t in toolsets if t not in blocked_toolset_names]

    # 注意: "skills" 和 "session_search" 不在 blocked 列表中, 子代理可以使用

    # Orchestrator 特殊处理: 重新添加 delegation toolset
if role == "orchestrator":
    if "delegation" not in child_toolsets:
        child_toolsets.append("delegation")
```

<a id="c-记忆系统隔离"></a>
<a id="section-3-4-3"></a>
#### 3.4.3 **C. 记忆系统隔离**

```python
    # 主 Agent: 完整记忆访问
child = AIAgent(
    skip_memory=False,  # 默认值
    # ...
)
    # → 加载 MEMORY.md
    # → 预取外部记忆 (GitHub/GitLab issues)
    # → 每次迭代后 sync_all()

    # 子 Agent: 完全禁用记忆
child = AIAgent(
    skip_memory=True,  # ← 关键配置
    # ...
)
    # → 不加载 MEMORY.md
    # → 不预取外部记忆
    # → 不调用 sync_all()
```

<a id="d-上下文文件隔离"></a>
<a id="section-3-4-4"></a>
#### 3.4.4 **D. 上下文文件隔离**

```python
    # 主 Agent: 加载项目知识
child = AIAgent(
    skip_context_files=False,  # 默认值
    # ...
)
    # → 读取 AGENTS.md, SOUL.md, README.md 等
    # → 注入到 system prompt

    # 子 Agent: 跳过上下文文件
child = AIAgent(
    skip_context_files=True,  # ← 关键配置
    # ...
)
    # → 不读取任何上下文文件
    # → 保持 prompt 简洁
```

<a id="e-会话-id-隔离"></a>
<a id="section-3-4-5"></a>
#### 3.4.5 **E. 会话 ID 隔离**

```python
    # 主 Agent: 主会话 ID
parent.session_id = "sess-abc123"

    # 子 Agent: 派生会话 ID
child_session_id = f"{parent.session_id}:sub:{uuid.uuid4().hex[:8]}"
    # 例如: "sess-abc123:sub:f7a3b2c1"

    # 作用:
    # 1. 独立的对话历史存储
    # 2. 独立的文件状态追踪 (file_state)
    # 3. 独立的终端会话 (task_id)
```

<a id="f-迭代预算隔离"></a>
<a id="section-3-4-6"></a>
#### 3.4.6 **F. 迭代预算隔离**

```python
    # 示意：父预算是对象，不是直接赋值为整数
parent.iteration_budget = IterationBudget(parent_max_iterations)

    # 子 Agent: 独立预算，读取 delegation 配置
child_max_iterations = config.get("delegation", {}).get(
    "max_iterations", 250
)

    # 关键：子代理的预算是独立的，不会吞噬父代理的预算
    # 父代理调用 delegate_task 后，自己的 iteration_budget 不变
```

<a id="g-用户交互隔离"></a>
<a id="section-3-4-7"></a>
#### 3.4.7 **G. 用户交互隔离**

```python
    # 主 Agent: 支持澄清问题
parent.clarify_callback = interactive_clarify_callback
    # → 可以问用户 "你指的是哪个文件？"

    # 子 Agent: 禁用澄清
child = AIAgent(
    clarify_callback=None,  # ← 关键配置
    # ...
)
    # → 不能问用户问题
    # → 必须自主决策
```

<a id="h-静默模式"></a>
<a id="section-3-4-8"></a>
#### 3.4.8 **H. 静默模式**

```python
    # 主 Agent: CLI 显示输出
parent.quiet_mode = False
    # → 打印思考过程、工具调用等

    # 子 Agent: 静默运行
child = AIAgent(
    quiet_mode=True,  # ← 关键配置
    # ...
)
    # → 不直接打印到终端
    # → 通过 progress callback 中继到父代理
```

<a id="35-执行流程对比"></a>
<a id="section-3-5"></a>
### 3.5 执行流程对比

```python
    # ===== 主 Agent 执行 =====
result = parent_agent.run_conversation(
    user_message=user_input,
    task_id=main_task_id,
)
    # 内部执行:
    # 1. 加载完整 system prompt (~3000 tokens)
    # 2. 加载全部工具集 (20+ tools)
    # 3. 预取记忆 (MEMORY.md + external)
    # 4. 加载上下文文件 (AGENTS.md, etc.)
    # 5. ReAct 循环 (最多 90 轮)
    # 6. 每次迭代后 sync_all()


    # ===== 子 Agent 执行 =====
child = _build_child_agent(...)  # 创建新的 AIAgent 实例
result = child.run_conversation(  # ← 调用同一个方法
    user_message=goal,
    task_id=child_task_id,  # ← 但使用独立的 task_id
)
    # 内部执行:
    # 1. _build_system_prompt() 构建 _cached_system_prompt (部分层, ~400-800 tokens)
    #    包含: DEFAULT_AGENT_IDENTITY, Skills索引, TOOL_USE_ENFORCEMENT_GUIDANCE, 时间戳, 环境提示
    #    跳过: SOUL.md, Context Files, Memory
    # 2. ephemeral_system_prompt 已由 _build_child_system_prompt() 设置 (~200-600 tokens)
    # 3. effective_system = _cached_system_prompt + "\n\n" + ephemeral_system_prompt
    # 4. 加载受限工具集 (10-15 tools, 移除 blocked toolsets)
    # 5. 跳过记忆 (skip_memory=True)
    # 6. 跳过上下文文件 (skip_context_files=True)
    # 7. ReAct 循环 (最多 50 轮)
    # 8. 不调用 sync_all()
```

<a id="36-并行执行模型"></a>
<a id="section-3-6"></a>
### 3.6 并行执行模型

子 Agent 在 **ThreadPoolExecutor** 中并行执行：

```python
    # tools/delegate_tool.py:L1476-1496
_timeout_executor = ThreadPoolExecutor(
    max_workers=1,
    initializer=_set_subagent_approval_cb,
    initargs=(_get_subagent_approval_callback(),),
)

def _run_with_thread_capture():
    _worker_thread_holder["t"] = threading.current_thread()
    return child.run_conversation(
        user_message=goal,
        task_id=child_task_id,
    )

_child_future = _timeout_executor.submit(_run_with_thread_capture)
result = _child_future.result(timeout=child_timeout)
```

**Batch Mode 并行**：

```python
    # 多个子 Agent 同时运行
with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
    futures = [
        executor.submit(_run_single_child, task_idx, task_data)
        for task_idx, task_data in enumerate(tasks)
    ]
    results = [f.result() for f in futures]
```

**线程安全**：
- ✅ 每个子 Agent 有独立的 `messages` 列表
- ✅ 每个子 Agent 有独立的 `task_id`
- ✅ 通过 `_active_subagents_lock` 保护共享状态
- ✅ 文件状态通过 `file_state` 模块隔离

<a id="37-设计哲学总结"></a>
<a id="section-3-7"></a>
### 3.7 设计哲学总结

> **“用配置而非代码分支来实现差异化”**

这种设计符合软件工程的最佳实践：

1. **DRY (Don't Repeat Yourself)**: 不重复 agentic loop 逻辑
2. **单一职责**: `run_conversation` 只负责执行，不负责区分主/子
3. **开闭原则**: 新增隔离维度只需添加配置参数，无需修改核心逻辑
4. **可测试性**: 可以用不同配置测试同一套代码
5. **可维护性**: Bug 修复一次，所有 Agent 受益

---


<a id="4-子代理创建流程"></a>
<a id="section-4"></a>
## 4. 子代理创建流程

<a id="31-完整时序图"></a>
<a id="section-4-1"></a>
### 4.1 完整时序图

```mermaid
sequenceDiagram
    participant Parent as 父 AIAgent
    participant Delegate as delegate_task handler
    participant Builder as _build_child_agent
    participant Child as 子 AIAgent
    participant Registry as ToolRegistry
    
    Parent->>Delegate: delegate_task(goal, context, ...)
    
    Note over Delegate: === 阶段 1: 验证 ===
    Delegate->>Delegate: 检查 spawn pause flag
    Delegate->>Delegate: 检查 depth limit (默认 max=2)
    alt 超过深度限制
        Delegate-->>Parent: error: "Depth limit reached"
    end
    
    Note over Delegate: === 阶段 2: 构建子代理 ===
    Delegate->>Builder: _build_child_agent(...)
    
    Builder->>Builder: 解析 role (leaf/orchestrator)
    Builder->>Builder: 计算 child_depth = parent_depth + 1
    Builder->>Builder: 确定 toolsets (过滤 blocked tools)
    
    alt role='orchestrator'
        Builder->>Builder: 重新添加 delegation toolset
    end
    
    Builder->>Builder: _build_child_system_prompt(goal, context, role)
    Builder->>Builder: 继承父代理配置 (model/provider/base_url)
    Builder->>Builder: 应用 config 覆盖 (override_*)
    
    Builder->>Child: AIAgent(__init__)
    Note right of Child: quiet_mode=True<br/>skip_memory=True<br/>skip_context_files=True
    
    Child->>Registry: 加载受限 toolsets
    Registry-->>Child: 过滤后的工具列表
    
    Child-->>Builder: 子代理实例
    Builder-->>Delegate: child agent
    
    Note over Delegate: === 阶段 3: 注册与运行 ===
    Delegate->>Delegate: 生成 subagent_id (UUID)
    Delegate->>Delegate: _register_subagent(record)
    Delegate->>Delegate: 设置 _delegate_depth, _delegate_role
    
    Delegate->>Child: child.run_conversation(goal, task_id=subagent_id)
    
    Note over Child: 子代理独立执行
    Child->>Child: 自己的 iteration_budget (未配置时 250)
    Child->>Child: 自己的 messages 列表 (干净上下文)
    Child->>Child: 受限的工具集 (blocked tools 移除)
    
    loop 子代理 ReAct 循环
        Child->>Child: API 调用 + 工具执行
        Child->>Delegate: tool_progress_callback (实时反馈)
    end
    
    Child-->>Delegate: result dict
    Delegate->>Delegate: _unregister_subagent(subagent_id)
    Delegate->>Delegate: 提取 summary + tool_trace
    Delegate-->>Parent: JSON result
```

<a id="32-关键代码片段"></a>
<a id="section-4-2"></a>
### 4.2 关键代码片段

**_build_child_agent 核心逻辑**:

```python
def _build_child_agent(
    task_index: int,
    goal: str,
    context: Optional[str],
    toolsets: Optional[List[str]],
    model: Optional[str],
    max_iterations: int,
    task_count: int,
    parent_agent,
    role: str = "leaf",
):
    """Build a child AIAgent on the main thread (thread-safe construction)."""
    from run_agent import AIAgent
    
    # 1. Role resolution
    effective_role = _normalize_role(role)
    child_depth = getattr(parent_agent, "_delegate_depth", 0) + 1
    max_spawn = _get_max_spawn_depth()
    
    if child_depth >= max_spawn and effective_role == "orchestrator":
        effective_role = "leaf"  # 强制降级为 leaf
    
    # 2. Toolset filtering
    if toolsets:
        child_toolsets = _strip_blocked_tools(toolsets)
    else:
        child_toolsets = _strip_blocked_tools(DEFAULT_TOOLSETS)
    
    # Orchestrators retain delegation toolset
    if effective_role == "orchestrator" and "delegation" not in child_toolsets:
        child_toolsets.append("delegation")
    
    # 3. System prompt
    workspace_hint = _resolve_workspace_hint(parent_agent)
    child_prompt = _build_child_system_prompt(
        goal, context,
        workspace_path=workspace_hint,
        role=effective_role,
        max_spawn_depth=max_spawn,
        child_depth=child_depth,
    )
    
    # 4. Inherit parent config
    effective_model = model or parent_agent.model
    effective_provider = override_provider or getattr(parent_agent, "provider", None)
    effective_base_url = override_base_url or parent_agent.base_url
    effective_api_key = override_api_key or parent_api_key
    
    # 5. Create child agent
    child = AIAgent(
        base_url=effective_base_url,
        api_key=effective_api_key,
        model=effective_model,
        provider=effective_provider,
        max_iterations=max_iterations,
        enabled_toolsets=child_toolsets,
        quiet_mode=True,
        ephemeral_system_prompt=child_prompt,
        platform=parent_agent.platform,
        skip_context_files=True,
        skip_memory=True,
        clarify_callback=None,
        session_db=getattr(parent_agent, "_session_db", None),
        parent_session_id=getattr(parent_agent, "session_id", None),
        iteration_budget=None,  # fresh budget per subagent
    )
    
    # 6. Set delegation metadata
    child._delegate_depth = child_depth
    child._delegate_role = effective_role
    child._subagent_id = subagent_id
    child._parent_subagent_id = parent_subagent_id
    
    return child
```

---

<a id="delegate-task-design"></a>
<a id="delegate_task创建调度执行与结果回收"></a>
<a id="section-5"></a>
## 5. delegate_task：创建、调度、执行与结果回收

> **主题归位**：本节从 `TOOLS_SYSTEM.md` 的「13. 深潜：delegate_task」迁入；保留原有图表、示例和讨论。

<a id="23-delegate_task---任务委派工具"></a>
<a id="section-5-1"></a>
### 5.1 delegate_task - 任务委派工具

**文件**: `tools/delegate_tool.py`\
**行号**: L1898-2289\
**作用**:  spawn子Agent并行处理任务，支持Leaf和Orchestrator两种角色

<a id="231-功能概览"></a>
<a id="section-5-1-1"></a>
#### 5.1.1 功能概览

```python
def delegate_task(
    goal: Optional[str] = None,           # 单个任务目标
    context: Optional[str] = None,        # 任务上下文
    toolsets: Optional[List[str]] = None, # 自定义工具集
    tasks: Optional[List[Dict]] = None,   # 批量任务列表
    max_iterations: Optional[int] = None, # 最大迭代次数 (被忽略，使用config值)
    acp_command: Optional[str] = None,    # ACP命令 (可选)
    acp_args: Optional[List[str]] = None, # ACP参数 (可选)
    role: Optional[str] = None,           # 角色: "leaf"或"orchestrator"
    parent_agent=None,                    # 父Agent实例 (必需)
) -> str:
    """
    Spawn one or more child agents to handle delegated tasks.

    Supports two modes:
      - Single: provide goal (+ optional context, toolsets, role)
      - Batch:  provide tasks array [{goal, context, toolsets, role}, ...]

    The 'role' parameter controls whether a child can further delegate:
    'leaf' (default) cannot; 'orchestrator' retains delegation toolset.

    Returns JSON with results array, one entry per task.
    """
```

<a id="232-实现逻辑详解"></a>
<a id="section-5-1-2"></a>
#### 5.1.2 实现逻辑详解

<a id="1-暂停标志检查"></a>
<a id="section-5-1-2-1"></a>
##### 5.1.2.1 (1) 暂停标志检查

```python
if parent_agent is None:
    return tool_error("delegate_task requires a parent agent context.")

## Operator-controlled kill switch
if is_spawn_paused():
    return tool_error(
        "Delegation spawning is paused. Clear the pause via the TUI "
        "(`p` in /agents) or the `delegation.pause` RPC before retrying."
    )
```

**用途**: TUI检测到失控的委派树时，可以暂停新的spawn

<a id="2-深度限制检查"></a>
<a id="section-5-1-2-2"></a>
##### 5.1.2.2 (2) 深度限制检查

```python
## Normalise the top-level role once
top_role = _normalize_role(role)

## Depth limit — configurable via delegation.max_spawn_depth
depth = getattr(parent_agent, "_delegate_depth", 0)
max_spawn = _get_max_spawn_depth()  # 从config.yaml读取，默认1
if depth >= max_spawn:
    return json.dumps({
        "error": (
            f"Delegation depth limit reached (depth={depth}, "
            f"max_spawn_depth={max_spawn}). Raise "
            f"delegation.max_spawn_depth in config.yaml if deeper "
            f"nesting is required (cap: {_MAX_SPAWN_DEPTH_CAP})."
        )
    })
```

**配置**:
```yaml
delegation:
  max_spawn_depth: 1  # 1=flat, 2=orchestrator→leaf, 3=three-level
  orchestrator_enabled: true  # 全局开关
```

<a id="3-凭证解析"></a>
<a id="section-5-1-2-3"></a>
##### 5.1.2.3 (3) 凭证解析

```python
## Load config
cfg = _load_config()
default_max_iter = cfg.get("max_iterations", DEFAULT_MAX_ITERATIONS)

## Model-supplied max_iterations is ignored — config value is authoritative
if max_iterations is not None and max_iterations != default_max_iter:
    logger.debug(
        "delegate_task: ignoring caller-supplied max_iterations=%s; "
        "using delegation.max_iterations=%s from config",
        max_iterations, default_max_iter,
    )
effective_max_iter = default_max_iter

## Resolve delegation credentials (provider:model pair)
try:
    creds = _resolve_delegation_credentials(cfg, parent_agent)
except ValueError as exc:
    return tool_error(str(exc))
```

**关键设计**:
- ✅ **配置驱动**: max_iterations由config.yaml控制，模型无法覆盖
- ✅ **独立凭证**: 子Agent可以使用不同的provider/model

<a id="4-任务列表标准化"></a>
<a id="section-5-1-2-4"></a>
##### 5.1.2.4 (4) 任务列表标准化

```python
## Normalize to task list
max_children = _get_max_concurrent_children()  # 默认3
recovered_tasks, tasks_error = _recover_tasks_from_json_string(tasks)
if tasks_error:
    return tool_error(tasks_error)
if recovered_tasks is not None:
    tasks = recovered_tasks

if tasks and isinstance(tasks, list):
    if len(tasks) > max_children:
        return tool_error(
            f"Too many tasks: {len(tasks)} provided, but "
            f"max_concurrent_children is {max_children}. "
            f"Either reduce the task count, split into multiple "
            f"delegate_task calls, or increase "
            f"delegation.max_concurrent_children in config.yaml."
        )
    task_list = tasks
elif goal and isinstance(goal, str) and goal.strip():
    task_list = [
        {"goal": goal, "context": context, "toolsets": toolsets, "role": top_role}
    ]
else:
    return tool_error("Provide either 'goal' (single task) or 'tasks' (batch).")

## Validate each task has a goal
for i, task in enumerate(task_list):
    if not isinstance(task, dict):
        return tool_error(f"Task {i} must be an object, got {type(task).__name__}.")
    if not task.get("goal", "").strip():
        return tool_error(f"Task {i} is missing a 'goal'.")
```

<a id="5-保存父agent工具名"></a>
<a id="section-5-1-2-5"></a>
##### 5.1.2.5 (5) 保存父Agent工具名

```python
overall_start = time.monotonic()
results = []

n_tasks = len(task_list)
task_labels = [t["goal"][:40] for t in task_list]

## Save parent tool names BEFORE any child construction mutates the global
import model_tools as _model_tools
_parent_tool_names = list(_model_tools._last_resolved_tool_names)
```

**关键修复**: `_build_child_agent()`会修改全局`_last_resolved_tool_names`，必须在构建子Agent前保存

<a id="6-构建子agent"></a>
<a id="section-5-1-2-6"></a>
##### 5.1.2.6 (6) 构建子Agent

```python
## Build all child agents on the main thread (thread-safe construction)
children = []
try:
    for i, t in enumerate(task_list):
        task_acp_args = t.get("acp_args") if "acp_args" in t else None
        # Per-task role beats top-level
        effective_role = _normalize_role(t.get("role") or top_role)
        child = _build_child_agent(
            task_index=i,
            goal=t["goal"],
            context=t.get("context"),
            toolsets=t.get("toolsets") or toolsets,
            model=creds["model"],
            max_iterations=effective_max_iter,
            task_count=n_tasks,
            parent_agent=parent_agent,
            override_provider=creds["provider"],
            override_base_url=creds["base_url"],
            override_api_key=creds["api_key"],
            override_api_mode=creds["api_mode"],
            override_acp_command=t.get("acp_command") or acp_command or creds.get("command"),
            override_acp_args=(
                task_acp_args
                if task_acp_args is not None
                else (acp_args if acp_args is not None else creds.get("args"))
            ),
            role=effective_role,
        )
        # Override with correct parent tool names
        child._delegate_saved_tool_names = _parent_tool_names
        children.append((i, t, child))
finally:
    # Authoritative restore: reset global to parent's tool names
    _model_tools._last_resolved_tool_names = _parent_tool_names
```

**线程安全**:
- ✅ **主线程构建**: 避免多线程并发修改全局状态
- ✅ **try/finally保证恢复**: 即使构建失败也能恢复全局状态

<a id="7-单任务直接执行"></a>
<a id="section-5-1-2-7"></a>
##### 5.1.2.7 (7) 单任务直接执行

```python
if n_tasks == 1:
    # Single task -- run directly (no thread pool overhead)
    _i, _t, child = children[0]
    result = _run_single_child(0, _t["goal"], child, parent_agent)
    results.append(result)
```

**性能优化**: 单任务无需线程池，减少开销

<a id="8-批量并行执行"></a>
<a id="section-5-1-2-8"></a>
##### 5.1.2.8 (8) 批量并行执行

```python
else:
    # Batch -- run in parallel with per-task progress lines
    completed_count = 0
    spinner_ref = getattr(parent_agent, "_delegate_spinner", None)

    with ThreadPoolExecutor(max_workers=max_children) as executor:
        futures = {}
        for i, t, child in children:
            future = executor.submit(
                _run_single_child,
                task_index=i,
                goal=t["goal"],
                child=child,
                parent_agent=parent_agent,
            )
            futures[future] = i

        # Poll futures with interrupt checking
        _child_by_index = {i: child for (i, _, child) in children}
        pending = set(futures.keys())

        while pending:
            # 检查父Agent中断
            if getattr(parent_agent, "_interrupt_requested", False) is True:
                # Parent interrupted — collect finished, abandon rest
                for f in pending:
                    idx = futures[f]
                    if f.done():
                        try:
                            entry = f.result()
                        except Exception as exc:
                            entry = {
                                "task_index": idx,
                                "status": "error",
                                "summary": None,
                                "error": str(exc),
                                "api_calls": 0,
                                "duration_seconds": 0,
                                "_child_role": getattr(
                                    _child_by_index.get(idx), "_delegate_role", None
                                ),
                            }
                    else:
                        entry = {
                            "task_index": idx,
                            "status": "interrupted",
                            "summary": None,
                            "error": "Parent agent interrupted — child did not finish in time",
                            "api_calls": 0,
                            "duration_seconds": 0,
                            "_child_role": getattr(
                                _child_by_index.get(idx), "_delegate_role", None
                            ),
                        }
                    results.append(entry)
                    completed_count += 1
                break

            # Wait with timeout for interrupt responsiveness
            from concurrent.futures import wait as _cf_wait, FIRST_COMPLETED
            done, pending = _cf_wait(
                pending, timeout=0.5, return_when=FIRST_COMPLETED
            )

            for future in done:
                try:
                    entry = future.result()
                except Exception as exc:
                    idx = futures[future]
                    entry = {
                        "task_index": idx,
                        "status": "error",
                        "summary": None,
                        "error": str(exc),
                        "api_calls": 0,
                        "duration_seconds": 0,
                        "_child_role": getattr(
                            _child_by_index.get(idx), "_delegate_role", None
                        ),
                    }

                results.append(entry)
                completed_count += 1

                # Print per-task completion line above the spinner
                idx = entry["task_index"]
                label = task_labels[idx] if idx < len(task_labels) else f"Task {idx}"
                dur = entry.get("duration_seconds", 0)
                status = entry.get("status", "?")
                icon = "✓" if status == "completed" else "✗"
                remaining = n_tasks - completed_count
                completion_line = f"{icon} [{idx+1}/{n_tasks}] {label}  ({dur}s)"

                if spinner_ref:
                    try:
                        spinner_ref.print_above(completion_line)
                    except Exception:
                        print(f"  {completion_line}")
                else:
                    print(f"  {completion_line}")

                # Update spinner text to show remaining count
                if spinner_ref and remaining > 0:
                    try:
                        spinner_ref.update_text(
                            f"🔀 {remaining} task{'s' if remaining != 1 else ''} remaining"
                        )
                    except Exception as e:
                        logger.debug("Spinner update_text failed: %s", e)

    # Sort by task_index so results match input order
    results.sort(key=lambda r: r["task_index"])
```

**关键特性**:
- ✅ **中断传播**: 父Agent中断时，收集已完成的结果，放弃未完成的
- ✅ **进度显示**: 实时更新spinner显示剩余任务数
- ✅ **非阻塞等待**: 使用`wait(timeout=0.5)`而非`as_completed()`，确保及时响应中断

<a id="85-子-agent-执行机制详解"></a>
<a id="section-5-1-2-9"></a>
##### 5.1.2.9 (8.5) 子 Agent 执行机制详解

**问题 1：子 Agent 创建是在独立线程中执行么？**

**❌ 不是！** 子 Agent 的**创建**（construction）是在**主线程**中串行完成的：

```python
## delegate_tool.py:L2031-2069
## Build all child agents on the main thread (thread-safe construction)
children = []
try:
    for i, t in enumerate(task_list):
        child = _build_child_agent(...)  # 在主线程中构建
        children.append((i, t, child))
finally:
    # 恢复全局状态
    _model_tools._last_resolved_tool_names = _parent_tool_names
```

**原因**：
- `_build_child_agent()` 会调用 `AIAgent()` 构造函数
- 这会触发 `get_tool_definitions()`，修改全局变量 `_last_resolved_tool_names`
- 如果在多线程中并发构建，会导致全局状态竞争
- 所以采用 **try/finally** 保证即使构建失败也能恢复全局状态

---

**问题 2：创建完成之后执行子 Agent，并同步等待么？**

这取决于任务数量：

**情况 A：单个任务（n_tasks == 1）**

**✅ 同步执行，阻塞等待**

```python
## delegate_tool.py:L2071-2075
if n_tasks == 1:
    # Single task -- run directly (no thread pool overhead)
    _i, _t, child = children[0]
    result = _run_single_child(0, _t["goal"], child, parent_agent)
    results.append(result)
```

- 直接在当前线程调用 `_run_single_child()`
- **阻塞等待**子 Agent 完成
- 无额外线程开销

---

**情况 B：批量任务（n_tasks > 1）**

**✅ 并行执行 + 同步等待所有结果**

```python
## delegate_tool.py:L2081-2193
else:
    # Batch -- run in parallel with per-task progress lines
    with ThreadPoolExecutor(max_workers=max_children) as executor:
        futures = {}
        for i, t, child in children:
            future = executor.submit(
                _run_single_child,  # 提交到线程池
                task_index=i,
                goal=t["goal"],
                child=child,
                parent_agent=parent_agent,
            )
            futures[future] = i

        # 轮询等待，支持中断检查
        pending = set(futures.keys())
        while pending:
            # 检查父 Agent 是否被中断
            if getattr(parent_agent, "_interrupt_requested", False):
                break  # 收集中断信号前的结果，放弃未完成的

            # 非阻塞等待：每 0.5 秒检查一次
            done, pending = _cf_wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)

            # 处理已完成的任务
            for future in done:
                entry = future.result()  # 获取结果
                results.append(entry)
```

**关键特性**：
1. **并行执行**：使用 `ThreadPoolExecutor`，最多 `max_children` 个线程（默认 3）
2. **同步等待**：父 Agent **阻塞**直到所有子 Agent 完成或被中断
3. **非阻塞轮询**：使用 `wait(timeout=0.5)` 而非 `as_completed()`，确保及时响应中断
4. **中断传播**：父 Agent 被中断时，立即停止等待，收集已完成的结果

---

**子 Agent 内部执行机制**

每个子 Agent 在 `_run_single_child()` 中还有一个**内部的超时保护线程**：

```python
## delegate_tool.py:L1476-1498
_timeout_executor = ThreadPoolExecutor(max_workers=1)

def _run_with_thread_capture():
    _worker_thread_holder["t"] = threading.current_thread()
    return child.run_conversation(
        user_message=goal,
        task_id=child_task_id,
    )

_child_future = _timeout_executor.submit(_run_with_thread_capture)
result = _child_future.result(timeout=child_timeout)  # 硬超时保护
```

**作用**：
- 防止子 Agent 的 API 调用或工具执行无限挂起
- 默认超时时间由 `delegation.child_timeout_seconds` 配置（默认 300 秒）
- 超时后会调用 `child.interrupt()` 强制终止

---

**总结表**：

| 阶段 | 执行方式 | 线程模型 | 是否阻塞 |
|------|---------|---------|----------|
| **创建子 Agent** | 主线程串行构建 | 单线程 | ✅ 是 |
| **执行单个任务** | 直接调用 `_run_single_child()` | 当前线程 | ✅ 是 |
| **执行批量任务** | `ThreadPoolExecutor` 并行 | 多线程（最多 `max_children`） | ✅ 是（等待所有完成） |
| **子 Agent 内部** | 额外的超时保护线程 | 每个子 Agent 1 个 worker 线程 | - |

**核心设计原则**：
1. **创建串行化**：避免全局状态竞争
2. **执行并行化**：提高吞吐量
3. **等待同步化**：简化父 Agent 的逻辑，确保结果完整性
4. **中断可响应**：通过短超时轮询实现优雅中断

<a id="9-通知记忆提供者"></a>
<a id="section-5-1-2-10"></a>
##### 5.1.2.10 (9) 通知记忆提供者

```python
## Notify parent's memory provider of delegation outcomes
if (
    parent_agent
    and hasattr(parent_agent, "_memory_manager")
    and parent_agent._memory_manager
):
    for entry in results:
        try:
            _task_goal = (
                task_list[entry["task_index"]]["goal"]
                if entry["task_index"] < len(task_list)
                else ""
            )
            parent_agent._memory_manager.on_delegation(
                task=_task_goal,
                result=entry.get("summary", "") or "",
                child_session_id=(
                    getattr(children[entry["task_index"]][2], "session_id", "")
                    if entry["task_index"] < len(children)
                    else ""
                ),
            )
        except Exception:
            pass
```

**用途**: 外部记忆系统 (如Honcho/Mem0) 可以记录委派历史

<a id="10-触发subagent_stop钩子"></a>
<a id="section-5-1-2-11"></a>
##### 5.1.2.11 (10) 触发subagent_stop钩子

```python
## Fire subagent_stop hooks once per child
_parent_session_id = getattr(parent_agent, "session_id", None)
try:
    from hermes_cli.plugins import invoke_hook as _invoke_hook
except Exception:
    _invoke_hook = None

_children_cost_total = 0.0
for entry in results:
    child_role = entry.pop("_child_role", None)
    child_cost = entry.pop("_child_cost_usd", 0.0)

    try:
        if child_cost:
            _children_cost_total += float(child_cost)
    except (TypeError, ValueError):
        pass

    if _invoke_hook is None:
        continue

    try:
        _invoke_hook(
            "subagent_stop",
            parent_session_id=_parent_session_id,
            child_role=child_role,
            child_summary=entry.get("summary"),
            child_status=entry.get("status"),
            duration_ms=int((entry.get("duration_seconds") or 0) * 1000),
        )
    except Exception:
        logger.debug("subagent_stop hook invocation failed", exc_info=True)
```

**插件集成**: Python插件和shell钩子可以监听子Agent完成事件

<a id="11-成本汇总"></a>
<a id="section-5-1-2-12"></a>
##### 5.1.2.12 (11) 成本汇总

```python
## Fold the aggregated child cost into the parent's session total
if _children_cost_total > 0.0:
    try:
        current = float(getattr(parent_agent, "session_estimated_cost_usd", 0.0) or 0.0)
        parent_agent.session_estimated_cost_usd = current + _children_cost_total

        # Upgrade the cost_source so UI doesn't label as "none"
        if getattr(parent_agent, "session_cost_source", "none") in (None, "", "none"):
            parent_agent.session_cost_source = "subagent"
        if getattr(parent_agent, "session_cost_status", "unknown") in (None, "", "unknown"):
            parent_agent.session_cost_status = "estimated"
    except Exception:
        logger.debug("Subagent cost rollup failed", exc_info=True)

total_duration = round(time.monotonic() - overall_start, 2)

return json.dumps({
    "results": results,
    "total_duration_seconds": total_duration,
}, ensure_ascii=False)
```

**成本追踪**: 子Agent的成本累加到父Agent，嵌套委派自然rollup

<a id="233-blocked-tools"></a>
<a id="section-5-1-3"></a>
#### 5.1.3 Blocked Tools

```python
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",   # 禁止递归委派
    "clarify",         # 禁止向用户提问
    "memory",          # 禁止写入共享记忆
    "send_message",    # 禁止跨平台副作用
    "execute_code",    # 子Agent应逐步推理，不写脚本
])
```

**阻止原因**:
- ✅ **防止无限递归**: delegate_task被block
- ✅ **用户体验**: 子Agent不应直接与用户交互 (clarify被block)
- ✅ **数据竞争**: 多个子Agent并发写入MEMORY.md会导致冲突
- ✅ **安全风险**: 防止向Telegram/Slack发送垃圾消息
- ✅ **可审计性**: 子Agent应逐步推理，而非直接执行代码

<a id="234-角色机制"></a>
<a id="section-5-1-4"></a>
#### 5.1.4 角色机制

**Leaf角色** (默认):
- ❌ 不能再次委派 (delegate_task被block)
- ✅ 专注执行单一任务
- ✅ 适用于研究、代码编写等

**Orchestrator角色**:
- ✅ 可以再次委派 (重新添加delegation toolset)
- ✅ 协调多个worker + 合成结果
- ✅ 受`max_spawn_depth`限制

```python
## Orchestrator特殊处理: 重新添加delegation
if effective_role == "orchestrator" and "delegation" not in child_toolsets:
    child_toolsets.append("delegation")
```

<a id="235-使用示例"></a>
<a id="section-5-1-5"></a>
#### 5.1.5 使用示例

**示例1: 单个Leaf任务**

```python
## 委派一个简单的研究任务
delegate_task(
    goal="Research Python async/await patterns for FastAPI",
    context="Focus on practical implementation, not theory",
    role="leaf"
)
```

**返回结果**:
```json
{
  "results": [
    {
      "task_index": 0,
      "status": "completed",
      "summary": "研究了FastAPI中的async模式:\n- 使用async def定义端点\n- asyncio.gather并行请求\n- 异步数据库查询\n- 常见陷阱: 阻塞同步调用",
      "error": null,
      "api_calls": 12,
      "duration_seconds": 45.3
    }
  ],
  "total_duration_seconds": 45.3
}
```

**示例2: 批量并行任务**

```python
## 并行执行3个研究任务
delegate_task(
    tasks=[
        {
            "goal": "Research async/await patterns",
            "role": "leaf",
            "context": "Focus on FastAPI use cases"
        },
        {
            "goal": "Research concurrency models",
            "role": "leaf",
            "context": "Compare threading vs multiprocessing vs asyncio"
        },
        {
            "goal": "Synthesize findings from both research tasks",
            "role": "orchestrator",
            "context": "Combine insights and provide recommendations"
        }
    ]
)
```

**执行流程**:
```
Depth 0: Parent Agent
├─ Depth 1: Task 1 (leaf) - Research async/await
├─ Depth 1: Task 2 (leaf) - Research concurrency
└─ Depth 1: Task 3 (orchestrator)
   ├─ Depth 2: Worker 1 (leaf) - Analyze Task 1 result
   └─ Depth 2: Worker 2 (leaf) - Analyze Task 2 result
   └─ Synthesize → Parent
```

**示例3: Orchestrator模式**

```python
## 委派一个复杂任务，需要进一步分解
delegate_task(
    goal="Analyze entire codebase architecture and propose improvements",
    role="orchestrator",
    context="Break down into: API layer, DB layer, business logic, tests"
)
```

**Orchestrator的职责**:
1. 分析任务，识别可并行的子任务
2. 调用`delegate_task` spawn workers
3. 等待所有workers完成
4. 合成结果，返回给父Agent

---

<a id="5-prompt-差异详解"></a>
<a id="section-6"></a>
## 6. Prompt 差异详解

<a id="41-主代理-system-prompt-结构"></a>
<a id="section-6-1"></a>
### 6.1 主代理 System Prompt 结构

主代理的 `_build_system_prompt()` 按条件逐层拼接 ~14 个层:

```python
    # run_agent.py: _build_system_prompt() 简化逻辑
parts = []

    # Layer 1: 身份 (SOUL.md 优先, 否则 DEFAULT_AGENT_IDENTITY)
if self.load_soul_identity or not self.skip_context_files:
    soul = load_soul_md()
    if soul: parts.append(soul)
if not soul_loaded:
    parts.append(DEFAULT_AGENT_IDENTITY)

    # Layer 2: Hermes 帮助指引 (HERMES_AGENT_HELP_GUIDANCE)
    # Layer 3: Skills 索引 (当 skills_list/skill_view/skill_manage 工具可用时)
if has_skills_tools:
    parts.append(build_skills_system_prompt(...))
    parts.append(SKILLS_GUIDANCE)

    # Layer 4: Context Files (AGENTS.md 等, 仅当 skip_context_files=False)
    # Layer 5: Memory (<memory-context>, 仅当 skip_memory=False)
    # Layer 6: TOOL_USE_ENFORCEMENT_GUIDANCE
    # Layer 7: Timestamps (当前时间)
    # Layer 8: build_environment_hints() (CWD, 终端后端等)
    # Layer 9: PLATFORM_HINTS (平台相关提示, CLI/Gateway)
    # Layer 10: Nous subscription prompt (如适用)
```

<a id="42-子代理-system-prompt-结构-双路径"></a>
<a id="section-6-2"></a>
### 6.2 子代理 System Prompt 结构 (双路径)

子代理的有效 system prompt = `_cached_system_prompt` + `ephemeral_system_prompt`

**Part 1: `_cached_system_prompt`** (由 `_build_system_prompt()` 构建, 但部分层被跳过):
```python
    # 因 skip_context_files=True, skip_memory=True, load_soul_identity=False:
    # ✅ 包含: DEFAULT_AGENT_IDENTITY, HERMES_AGENT_HELP_GUIDANCE
    # ✅ 包含: Skills 索引 + SKILLS_GUIDANCE (skills 工具集未被 blocked)
    # ✅ 包含: TOOL_USE_ENFORCEMENT_GUIDANCE, Timestamps, Environment Hints, PLATFORM_HINTS
    # ❌ 跳过: SOUL.md (load_soul_identity=False 且 skip_context_files=True)
    # ❌ 跳过: Context Files (skip_context_files=True)
    # ❌ 跳过: Memory (skip_memory=True)
```

**Part 2: `ephemeral_system_prompt`** (由 `_build_child_system_prompt()` 构建):
```python
    # delegate_tool.py: _build_child_system_prompt()
parts = [
    "You are a focused subagent working on a specific delegated task.",
    "",
    f"YOUR TASK:\n{goal}",
]

if context and context.strip():
    parts.append(f"\nCONTEXT:\n{context}")

if workspace_path and str(workspace_path).strip():
    parts.append(
        f"\nWORKSPACE PATH:\n{workspace_path}\n"
        "Use this exact path for local repository/workdir operations..."
    )

parts.append(
    "\nComplete this task using the tools available to you. "
    "When finished, provide a clear, concise summary of:\n"
    "- What you did\n"
    "- What you found or accomplished\n"
    "- Any files you created or modified\n"
    "- Any issues encountered\n\n"
    "Be thorough but concise -- your response is returned to the "
    "parent agent as a summary."
)

    # If role='orchestrator', add delegation capability block
if role == "orchestrator":
    parts.append("\n## Subagent Spawning (Orchestrator Role)...")

return "\n".join(parts)
```

**示例输出 (Leaf)**:
```markdown
You are a focused subagent working on a specific delegated task.

YOUR TASK:
Research Python async patterns

CONTEXT:
The parent agent is analyzing a codebase that uses asyncio extensively.

WORKSPACE PATH:
/home/user/project

Complete this task using the tools available to you. When finished, 
provide a clear, concise summary of:
- What you did
- What you found or accomplished
- Any files you created or modified
- Any issues encountered

Be thorough but concise -- your response is returned to the parent 
agent as a summary.
```

**示例输出 (Orchestrator)**:
```markdown
You are a focused subagent working on a specific delegated task.

YOUR TASK:
Analyze codebase architecture

### Subagent Spawning (Orchestrator Role)

You have access to the `delegate_task` tool and CAN spawn your own 
subagents to parallelize independent work.

WHEN to delegate:
- The goal decomposes into 2+ independent subtasks that can run in parallel
- A subtask is reasoning-heavy and would flood your context

WHEN NOT to delegate:
- Single-step mechanical work — do it directly
- Trivial tasks you can execute in one or two tool calls

Coordinate your workers' results and synthesize them before reporting 
back to your parent. You are responsible for the final summary, not 
your workers.

NOTE: You are at depth 1. The delegation tree is capped at 
max_spawn_depth=2. Your own children MUST be leaves (cannot delegate 
further) because they would be at the depth floor.
```

<a id="43-设计哲学"></a>
<a id="section-6-3"></a>
### 6.3 设计哲学

**为什么这样设计?**

| 设计决策 | 原因 | 优势 |
|---------|------|------|
| **子代理 prompt 简短** | 减少 token 消耗,聚焦任务 | 成本低,响应快 |
| **包含 Skills 索引** | skills 工具集未被 blocked, 子代理仍可使用技能系统 | 能力一致 |
| **不包含 Context Files** | 子代理是短期的,不需要项目知识 | 减少 I/O |
| **ephemeral_system_prompt** | 不影响父代理缓存 | 隔离性好 |
| **动态构建** | 每次委派可以不同 | 灵活性高 |

---

<a id="6-工具集隔离机制"></a>
<a id="section-7"></a>
## 7. 工具集隔离机制

<a id="51-blocked-toolsets"></a>
<a id="section-7-1"></a>
### 7.1 Blocked Toolsets

注意: 实际过滤是在 **toolset 级别** (`_strip_blocked_tools`)，不是单个工具名。

```python
    # delegate_tool.py: _strip_blocked_tools()
def _strip_blocked_tools(toolsets: List[str]) -> List[str]:
    blocked_toolset_names = {
        "delegation",      # 包含 delegate_task
        "clarify",         # 包含 clarify
        "memory",          # 包含 memory 相关工具
        "code_execution",  # 包含 execute_code
    }
    return [t for t in toolsets if t not in blocked_toolset_names]
```

**阻止原因**:

| Blocked Toolset | 包含的工具 | 风险 | 场景 |
|----------------|-----------|------|------|
| `delegation` | `delegate_task` | 指数级资源消耗 | 无限递归委派 |
| `clarify` | `clarify` | 用户体验混乱 | 子代理问用户问题 |
| `memory` | memory 管理工具 | 数据竞争/污染 | 多个子代理同时写 MEMORY.md |
| `code_execution` | `execute_code` | 安全风险/刷屏 | 子代理生成并执行任意代码 |

<a id="52-默认子代理工具集"></a>
<a id="section-7-2"></a>
### 7.2 默认子代理工具集

```python
    # 从父代理的 toolsets 中移除 blocked toolsets 后, 保留的工具集包括:
    # (具体列表取决于父代理的 enabled_toolsets)
child_toolsets = _strip_blocked_tools(parent_toolsets)
    # 典型结果:
    # ✅ "core"            — read_file, write_file, patch, terminal, ...
    # ✅ "web"             — web_search, web_extract
    # ✅ "browser"         — browser_navigate, browser_click, ...
    # ✅ "vision"          — vision_analyze
    # ✅ "skills"          — skills_list, skill_view, skill_manage
    # ✅ "session_search"  — session_search
    # ✅ "ha"              — Home Assistant (只读)
    # ❌ "delegation"      — blocked
    # ❌ "memory"          — blocked
    # ❌ "clarify"         — blocked
    # ❌ "code_execution"  — blocked
```

**过滤逻辑**:

```python
def _strip_blocked_tools(toolsets: List[str]) -> List[str]:
    """Remove toolsets that contain only blocked tools."""
    blocked_toolset_names = {
        "delegation",   # delegate_task
        "clarify",      # clarify
        "memory",       # memory
        "code_execution", # execute_code
    }
    return [t for t in toolsets if t not in blocked_toolset_names]
```

<a id="53-orchestrator-特权"></a>
<a id="section-7-3"></a>
### 7.3 Orchestrator 特权

```python
if effective_role == "orchestrator" and "delegation" not in child_toolsets:
    child_toolsets.append("delegation")  # 重新添加委派能力
```

**Orchestrator 工具集**:
- ✅ 包含所有 Leaf 工具
- ✅ 额外添加 `delegate_task`
- ❌ 仍然不能访问 `clarify/memory/send_message/execute_code`

<a id="54-工具集对比表"></a>
<a id="section-7-4"></a>
### 7.4 工具集对比表

| 工具类别 | 主代理 | Leaf 子代理 | Orchestrator 子代理 |
|---------|--------|------------|-------------------|
| core (文件/终端) | ✅ | ✅ | ✅ |
| web (搜索/提取) | ✅ | ✅ | ✅ |
| browser (自动化) | ✅ | ✅ | ✅ |
| vision (视觉) | ✅ | ✅ | ✅ |
| skills (技能管理) | ✅ | ✅ | ✅ |
| session_search (会话搜索) | ✅ | ✅ | ✅ |
| ha (Home Assistant) | ✅ | ✅ | ✅ |
| memory (记忆管理) | ✅ | ❌ blocked | ❌ blocked |
| clarify (澄清问题) | ✅ | ❌ blocked | ❌ blocked |
| code_execution (执行代码) | ✅ | ❌ blocked | ❌ blocked |
| delegation (委派) | ✅ | ❌ blocked | ✅ (重新添加) |

---

<a id="7-迭代预算系统"></a>
<a id="section-8"></a>
## 8. 迭代预算系统

<a id="61-预算对比"></a>
<a id="section-8-1"></a>
### 8.1 预算对比

| 属性 | 主代理 | 子代理 |
|------|--------|--------|
| **默认上限** | 构造器 `sys.maxsize`；入口可覆盖 | delegation 未配置时 250 |
| **独立性** | 独立预算 | 独立预算 (不与父共享) |
| **总迭代数** | 90 | 可以是 90 + 50*N (N=子代理数) |
| **Refund 机制** | ✅ execute_code 退款 | ✅ 同样支持 |
| **Grace Call** | ✅ 预算耗尽时最后一次机会 | ✅ 同样支持 |

<a id="62-关键设计"></a>
<a id="section-8-2"></a>
### 8.2 关键设计

**父子预算相加可以超过父的上限**:

```python
    # 设计意图: 委派工作不应简单吞噬父轮数
parent = AIAgent(max_iterations=90)       # 父 90 轮
child1 = AIAgent(max_iterations=50)       # 子1 50 轮
child2 = AIAgent(max_iterations=50)       # 子2 50 轮
    # 总迭代数: 90 + 50 + 50 = 190 (允许!)
```

**配置示例**:

```yaml
    # config.yaml
delegation:
  max_iterations: 50        # 每个子代理的预算上限
  max_spawn_depth: 2        # 最大嵌套深度
  max_concurrent_children: 3 # 最大并发子代理数
```

<a id="63-refund-机制"></a>
<a id="section-8-3"></a>
### 8.3 Refund 机制

**用途**: `execute_code` 内部可能有程序化工具循环,这些循环不应该消耗主迭代预算。

```python
    # 在 code_execution_tool.py 中
def execute_code(code: str, ...):
    """执行程序化代码，可能包含多次工具调用"""
    initial_remaining = agent.iteration_budget.remaining
    
    # 执行代码（内部可能调用多次工具）
    result = run_code_in_sandbox(code)
    
    # 计算实际消耗的迭代数
    actual_consumed = initial_remaining - agent.iteration_budget.remaining
    
    # 如果代码内部做了额外工作，退回多扣的轮数
    if actual_consumed > 1:
        refund_count = actual_consumed - 1
        for _ in range(refund_count):
            agent.iteration_budget.refund()
    
    return result
```

**效果**:
- ✅ 程序化工具循环不浪费预算
- ✅ 父代理有更多轮次处理其他任务
- ✅ 线程安全 (Lock 保护)

---

<a id="8-会话持久化"></a>
<a id="section-9"></a>
## 9. 会话持久化

<a id="71-session-id-层次结构"></a>
<a id="section-9-1"></a>
### 9.1 Session ID 层次结构

```
sess-parent-001 (parent_session_id=null)
├─ sess-parent-001:sub:uuid-1 (parent_session_id=sess-parent-001)
│  ├─ sess-parent-001:sub:uuid-1:sub:uuid-1a (depth=2)
│  └─ sess-parent-001:sub:uuid-1:sub:uuid-1b (depth=2)
└─ sess-parent-001:sub:uuid-2 (parent_session_id=sess-parent-001)
```

<a id="72-数据库查询"></a>
<a id="section-9-2"></a>
### 9.2 数据库查询

```sql
-- 查找所有子会话
SELECT * FROM sessions WHERE parent_session_id = 'sess-parent-001';

-- 查找深层嵌套 (depth >= 2)
SELECT * FROM sessions 
WHERE parent_session_id LIKE '%:sub:%:sub:%';

-- 统计子会话数量
SELECT COUNT(*) FROM sessions WHERE parent_session_id IS NOT NULL;
```

<a id="73-持久化对比"></a>
<a id="section-9-3"></a>
### 9.3 持久化对比

| 特性 | 主代理 | 子代理 |
|------|--------|--------|
| **Session ID** | `session_id` | `{parent_session_id}:sub:{uuid}` |
| **Parent Session ID** | N/A | `parent_session_id` (指向父) |
| **消息持久化** | ✅ 保存到 state.db | ✅ 同样保存 (但标记为子会话) |
| **Memory Sync** | ✅ sync_all() 写入 MEMORY.md | ❌ skip_memory=True |
| **Trajectory Export** | ✅ ShareGPT 格式 | ✅ 同样导出 (带 parent_session_id) |
| **Title Generation** | ✅ 自动生成会话标题 | ❌ 通常不生成 |

---

<a id="9-回调中继机制"></a>
<a id="section-10"></a>
## 10. 回调中继机制

<a id="81-progress-callback-中继"></a>
<a id="section-10-1"></a>
### 10.1 Progress Callback 中继

**问题**: 子代理在独立线程中运行,父代理如何知道进度?

**解决方案**: Progress Callback 中继

```python
def _build_child_progress_callback(task_index, goal, parent_agent, ...):
    """构建子代理进度回调,中继到父代理显示"""
    
    def _callback(event_type, tool_name, preview, args, **kwargs):
        if event_type == "subagent.start":
            # CLI: 打印树形视图
            spinner.print_above(f" {prefix}├─ 🔀 {goal[:55]}...")
            # Gateway: 中继事件
            parent_cb("subagent.start", preview=goal, subagent_id=...)
        
        elif event_type == DelegateEvent.TASK_TOOL_STARTED:
            # CLI: 显示工具 emoji + 名称
            emoji = get_tool_emoji(tool_name)
            spinner.print_above(f" {prefix}├─ {emoji} {tool_name}")
            # Gateway: 批量中继 (每 5 个工具 flush 一次)
            _batch.append(tool_name)
            if len(_batch) >= 5:
                parent_cb("subagent.progress", preview=\", \".join(_batch))
                _batch.clear()
        
        elif event_type == "subagent.complete":
            # 完成时 flush 剩余批次
            if _batch:
                parent_cb("subagent.progress", preview=\", \".join(_batch))
    
    return _callback
```

<a id="82-cli-输出示例"></a>
<a id="section-10-2"></a>
### 10.2 CLI 输出示例

```
🤖 正在分析代码库...
 ├─ 🔀 Research Python async patterns
 │  ├─ 📖 read_file  "async_utils.py"
 │  ├─ 🔍 search_files  "*.py"
 │  └─ 🌐 web_search  "Python asyncio best practices"
 ├─ 🔀 Review test coverage
 │  ├─ 📖 read_file  "tests/test_main.py"
 │  └─ 📊 session_search  "coverage report"
 ✓ delegate_task completed (2 subagents, 12s)
```

<a id="83-线程间通信机制详解"></a>
<a id="section-10-3"></a>
### 10.3 线程间通信机制详解

子Agent 在独立的工作线程 (`ThreadPoolExecutor`) 中运行，主Agent 在主线程中阻塞等待。
进度上报本质上是一个**线程间通信**问题。Hermes 采用了最轻量的方式：**闭包捕获 + 共享可变引用**，
不依赖消息队列、事件总线或序列化。

<a id="831-机制原理"></a>
<a id="section-10-3-1"></a>
#### 10.3.1 机制原理

```
主线程 (创建阶段)                          工作线程 (运行阶段)
┌────────────────────┐                    ┌────────────────────┐
│ parent_agent        │                    │ child_agent         │
│  .tool_progress_cb ─┼── CLI/Gateway回调  │  .tool_progress_cb ─┼── 注入的闭包
│  ._delegate_spinner ┼── 终端spinner对象  │                     │
│                     │                    │  run_conversation()  │
│ _build_child_       │                    │    ↓ 工具调用        │
│  progress_callback()│                    │    callback(...)     │
│  闭包捕获:          │                    │      ↓ 闭包执行      │
│   spinner = parent  ├─ 同一对象引用 ────>│   spinner.print()   │
│   parent_cb = parent├─ 同一对象引用 ────>│   parent_cb(...)    │
└────────────────────┘                    └────────────────────┘
```

核心思路：在主线程中创建闭包时，捕获父Agent的 `spinner` 和 `parent_cb` **对象引用**（不是拷贝）。
闭包注入子Agent后，子Agent 在工作线程中调用它，实际操作的是同一块内存中的父对象。

<a id="832-实现三步走"></a>
<a id="section-10-3-2"></a>
#### 10.3.2 实现三步走

**Step 1: 创建闭包，捕获父对象引用** (主线程)

```python
    # delegate_tool.py: _build_child_progress_callback()
spinner = getattr(parent_agent, "_delegate_spinner", None)   # 捕获 spinner 引用
parent_cb = getattr(parent_agent, "tool_progress_callback", None)  # 捕获 callback 引用

if not spinner and not parent_cb:
    return None  # 无显示通道 → 不创建回调

_batch: List[str] = []  # 闭包内部变量，每个子Agent独立

def _callback(event_type, tool_name=None, preview=None, args=None, **kwargs):
    # 直接跨线程调用父对象
    if event_type == "subagent.start":
        spinner.print_above(f" ├─ 🔀 {goal[:55]}")  # ← 跨线程写终端
        parent_cb("subagent.start", preview=goal)     # ← 跨线程通知Gateway
    elif event == DelegateEvent.TASK_TOOL_STARTED:
        spinner.print_above(f" ├─ {emoji} {tool_name}")
        _batch.append(tool_name)          # ← 闭包局部变量，无竞争
        if len(_batch) >= 5:
            parent_cb("subagent.progress", preview=", ".join(_batch))
            _batch.clear()
    ...

return _callback
```

**Step 2: 注入闭包到子Agent** (主线程)

```python
    # delegate_tool.py: _build_child_agent()
child = AIAgent(
    tool_progress_callback=child_progress_cb,  # ← 将闭包传给子Agent
    ...
)
```

**Step 3: 子Agent运行时自动触发** (工作线程)

```python
    # run_agent.py: AIAgent 工具执行流程
    # 每次调用工具时，自动触发 tool_progress_callback:
if self.tool_progress_callback:
    preview = _build_tool_preview(name, args)
    self.tool_progress_callback("tool.started", name, preview, args)
    # ↑ 这里 self.tool_progress_callback 就是那个闭包
    #   闭包内部操作的 spinner/parent_cb 是父Agent的对象
    #   跨线程直接调用，无需序列化或消息传递
```

<a id="833-线程安全分析"></a>
<a id="section-10-3-3"></a>
#### 10.3.3 线程安全分析

| 操作 | 安全性 | 原因 |
|------|--------|------|
| `spinner.print_above(text)` | ✅ | `sys.stdout.write()` 在 CPython GIL 下单次调用原子 |
| `parent_cb(event, ...)` | ✅ | 只读调用父Agent回调，不修改父Agent状态 |
| `_batch.append()` / `_batch.clear()` | ✅ | 闭包内部局部变量，每个子Agent的闭包有独立的 `_batch` |
| `_active_subagents[id]` 读写 | 需要锁 | 多个子Agent并发注册/注销，需显式保护 |

**唯一需要显式加锁的场景** —— 活跃子代理注册表：

```python
    # delegate_tool.py: 模块级共享状态
_active_subagents_lock = threading.Lock()
_active_subagents: Dict[str, Dict[str, Any]] = {}

def _register_subagent(record):
    with _active_subagents_lock:
        _active_subagents[sid] = record

def _unregister_subagent(subagent_id):
    with _active_subagents_lock:
        _active_subagents.pop(subagent_id, None)

    # 子Agent回调内也用锁更新工具计数:
with _active_subagents_lock:
    rec = _active_subagents.get(subagent_id)
    if rec is not None:
        rec["tool_count"] = _tool_count[0]
        rec["last_tool"] = tool_name
```

<a id="834-反向控制通道-主→子"></a>
<a id="section-10-3-4"></a>
#### 10.3.4 反向控制通道 (主→子)

进度上报是子→父方向，但主Agent也需要**反向控制**子Agent（如中断）。
实现方式是通过 `_active_subagents` 注册表持有子Agent的实例引用：

```python
    # 注册时保存子Agent实例引用
_active_subagents[subagent_id] = {
    "agent": child,        # ← 子Agent AIAgent实例
    "subagent_id": subagent_id,
    "goal": goal,
    "started_at": time.time(),
    ...
}

    # 主线程通过注册表中断子Agent
def interrupt_subagent(subagent_id: str) -> bool:
    with _active_subagents_lock:
        record = _active_subagents.get(subagent_id)
    if not record:
        return False
    agent = record.get("agent")
    if agent:
        agent.interrupt(f"Interrupted via TUI ({subagent_id})")
        # ↑ 跨线程设置子Agent的中断标志
        # 子Agent在下一个迭代边界检查到标志后停止
        return True
    return False
```

<a id="835-同步原语总结"></a>
<a id="section-10-3-5"></a>
#### 10.3.5 同步原语总结

```
┌─────────────────────────────────────────────────────┐
│                   同步原语                            │
│                                                      │
│  CPython GIL ──────── stdout.write 原子性            │
│  _active_subagents_lock ── 保护注册表并发读写         │
│  _spawn_pause_lock ─────── 保护暂停标志              │
│  Future.result(timeout) ── 主线程阻塞等待子线程完成   │
│  agent.interrupt() ─────── 设置子Agent中断标志(bool)  │
│                                                      │
│  不需要的:                                            │
│  ❌ 消息队列 (Queue)                                  │
│  ❌ 事件总线 (Event bus)                              │
│  ❌ 序列化/反序列化                                   │
│  ❌ 共享内存 / mmap                                   │
│  ❌ 条件变量 (Condition)                              │
└─────────────────────────────────────────────────────┘
```

<a id="84-tui-集成"></a>
<a id="section-10-4"></a>
### 10.4 TUI 集成

- `/agents` 命令显示活跃子代理树 (通过 `list_active_subagents()` 读取注册表快照)
- `p` 键暂停新子代理生成 (通过 `toggle_spawn_pause()` 设置 `_spawn_paused` 标志)
- `i` 键中断指定子代理 (通过 `interrupt_subagent(id)` 跨线程设中断标志)
- 实时显示每个子代理的工具调用进度 (通过闭包回调跨线程写 spinner)

---

<a id="10-深度限制与角色控制"></a>
<a id="section-11"></a>
## 11. 深度限制与角色控制

<a id="91-深度限制机制"></a>
<a id="section-11-1"></a>
### 11.1 深度限制机制

```python
MAX_DEPTH = 1  # 默认扁平: parent(0) -> child(1)
_MAX_SPAWN_DEPTH_CAP = 3  # 硬性上限

def delegate_task(..., parent_agent=None):
    depth = getattr(parent_agent, "_delegate_depth", 0)
    max_spawn = _get_max_spawn_depth()  # 从 config.yaml 读取
    
    if depth >= max_spawn:
        return json.dumps({
            "error": (
                f"Delegation depth limit reached (depth={depth}, "
                f"max_spawn_depth={max_spawn})."
            )
        })
    
    # 创建子代理时递增深度
    child._delegate_depth = depth + 1
```

**深度层级**:

```
Depth 0: Parent (max_spawn_depth=2)
├─ Depth 1: Child (role='leaf', 不能再委派)
├─ Depth 1: Child (role='orchestrator', 可以再委派)
│  ├─ Depth 2: Grandchild (role='leaf', 强制叶子)
│  └─ Depth 2: Grandchild (role='leaf', 强制叶子)
└─ Depth 1: Child (role='leaf')
```

<a id="92-role-语义"></a>
<a id="section-11-2"></a>
### 11.2 Role 语义

**Leaf 角色 (默认)**:
- ❌ 不能调用 `delegate_task`
- ❌ 不能向用户提问 (`clarify` 被阻止)
- ✅ 专注执行单一任务
- ✅ 返回简洁摘要

**Orchestrator 角色**:
- ✅ 可以调用 `delegate_task` (受深度限制)
- ✅ 可以进一步分解任务
- ✅ 协调多个 worker 的结果
- ✅ 负责最终总结 (不是 workers)

<a id="93-使用示例"></a>
<a id="section-11-3"></a>
### 11.3 使用示例

```python
    # Single mode - leaf (默认)
delegate_task(
    goal="Research Python async patterns",
    role="leaf"  # 或省略
)

    # Single mode - orchestrator
delegate_task(
    goal="Analyze codebase architecture",
    role="orchestrator"  # 可以再委派
)

    # Batch mode - mixed roles
delegate_task(
    tasks=[
        {"goal": "Research A", "role": "leaf"},
        {"goal": "Research B", "role": "leaf"},
        {"goal": "Synthesize results", "role": "orchestrator"},
    ]
)
```

---

<a id="11-并行执行模型"></a>
<a id="section-12"></a>
## 12. 并行执行模型

<a id="101-batch-mode-实现"></a>
<a id="section-12-1"></a>
### 12.1 Batch Mode 实现

```python
def delegate_task(tasks: List[Dict], ...):
    """并行委派多个子任务"""
    
    # 1. 预建所有子代理 (主线程,线程安全)
    children = []
    for idx, task in enumerate(tasks):
        child = _build_child_agent(
            task_index=idx,
            goal=task["goal"],
            context=task.get("context"),
            role=task.get("role", "leaf"),
            ...
        )
        children.append(child)
    
    # 2. 并发执行 (ThreadPoolExecutor)
    max_concurrent = _get_max_concurrent_children()  # 默认 3
    results = []
    
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(_run_single_child, idx, task["goal"], child): idx
            for idx, child in enumerate(children)
        }
        
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result(timeout=child_timeout)  # 默认 600s
                results.append(result)
            except TimeoutError:
                results.append({
                    "task_index": idx,
                    "status": "timeout",
                    "error": f"Subagent timed out after {child_timeout}s",
                })
    
    # 3. 汇总结果
    return json.dumps({
        "results": results,
        "total_tasks": len(tasks),
        "completed": sum(1 for r in results if r["status"] == "completed"),
        "failed": sum(1 for r in results if r["status"] != "completed"),
    })
```

<a id="102-性能对比"></a>
<a id="section-12-2"></a>
### 12.2 性能对比

- 串行执行 3 个子任务: ~30秒 (假设每个 10秒)
- 并行执行 3 个子任务: ~12秒 (overhead + 最长任务)
- **加速比**: ~2.5x

<a id="103-活跃子代理注册表"></a>
<a id="section-12-3"></a>
### 12.3 活跃子代理注册表

```python
    # delegate_tool.py 模块级状态
_active_subagents_lock = threading.Lock()
_active_subagents: Dict[str, Dict[str, Any]] = {}

def list_active_subagents() -> List[Dict]:
    """快照当前活跃子代理树"""
    with _active_subagents_lock:
        return [
            {k: v for k, v in r.items() if k != "agent"}
            for r in _active_subagents.values()
        ]

def interrupt_subagent(subagent_id: str) -> bool:
    """中断指定子代理"""
    with _active_subagents_lock:
        record = _active_subagents.get(subagent_id)
    if not record:
        return False
    agent = record.get("agent")
    if agent:
        agent.interrupt(f"Interrupted via TUI ({subagent_id})")
        return True
    return False
```

---

<a id="12-中断与-human-in-the-loop"></a>
<a id="section-13"></a>
## 13. 中断与 Human-in-the-Loop

> 与 Agent 循环级 interrupt 的关系见 [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md)。  
> **危险命令 / 插件审批的源码级时序与闸门**见 [HITL_APPROVAL_FLOW.md](HITL_APPROVAL_FLOW.md)（Canonical）。本节保留 interrupt vs HITL 概念与子 Agent 反向控制。

<a id="121-概念interrupt-vs-hitl"></a>
<a id="section-13-1"></a>
### 13.1 概念：Interrupt vs HITL

这两个概念虽然相关，但解决的是不同层面的问题：

| 维度 | 中断（Interrupt） | Human-in-the-Loop（HITL） |
|------|------------------|---------------------------|
| **触发方** | 用户主动终止 | Agent主动请求或系统预设检查点 |
| **目的** | 停止正在执行的任务 | 获取人类反馈、确认、指导 |
| **时机** | 任意时刻（通常在工具执行间隙） | 预定义的决策点/检查点 |
| **实现方式** | 标志位检测、线程中断 | 审批工作流、交互式对话、权限控制 |
| **恢复策略** | 冷启动恢复、状态回滚 | 继续执行、参数调整后重试 |
| **典型场景** | 任务失控、方向错误、紧急停止 | 敏感操作审批、不确定性澄清、质量检查 |

<a id="12-中断的层次分类"></a>
<a id="section-13-1-1"></a>
#### 13.1.1 中断的层次分类

根据中断发生的粒度和位置，可以分为：

<a id="l1---会话级中断"></a>
<a id="section-13-1-1-1"></a>
##### 13.1.1.1 L1 - 会话级中断
- **粒度**: 整个Agent会话
- **实现**: 设置全局标志位 `_interrupt_requested`
- **恢复**: 通常无法精确恢复，需要重新开始或从checkpoint恢复
- **代表**: hermes-agent, OpenHands

<a id="l2---工具级中断"></a>
<a id="section-13-1-1-2"></a>
##### 13.1.1.2 L2 - 工具级中断
- **粒度**: 单个工具调用
- **实现**: 在工具执行前后检查中断标志
- **恢复**: 可以重试失败的工具调用
- **代表**: hermes-agent的tool execution循环

<a id="l3---迭代级中断"></a>
<a id="section-13-1-1-3"></a>
##### 13.1.1.3 L3 - 迭代级中断
- **粒度**: ReAct循环的单次迭代
- **实现**: 在主循环开始/结束时检查中断标志
- **恢复**: 可以从下一个迭代继续
- **代表**: hermes-agent, AutoGen

<a id="l4---代码执行级中断"></a>
<a id="section-13-1-1-4"></a>
##### 13.1.1.4 L4 - 代码执行级中断
- **粒度**: 代码块执行过程中的中断
- **实现**: Jupyter kernel中断、进程信号
- **恢复**: 部分执行状态可能丢失
- **代表**: OpenHands, hermes-agent (通过execute_code)

---

<a id="122-hermes-多层中断"></a>
<a id="section-13-2"></a>
### 13.2 Hermes 多层中断

<a id="31-多层中断检测架构"></a>
<a id="section-13-2-1"></a>
#### 13.2.1 多层中断检测架构

Hermes Agent实现了多层次的中断检测机制：

```python
# Layer 1: 主循环级别 (run_agent.py:L6269)
async def run_conversation(self):
    while not self.should_terminate():
        # Check interrupt at start of each iteration
        if self._interrupt_requested:
            logger.info("Interrupt requested, stopping...")
            break
            
        # Execute one iteration
        await self.step()

# Layer 2: 工具执行前后 (run_agent.py:L7142)
async def execute_tool_call(self, tool_call):
    # Pre-execution check
    if self._interrupt_requested:
        return ToolResult(error="Interrupted before execution")
    
    # Execute tool
    result = await self.call_tool(tool_call)
    
    # Post-execution check
    if self._interrupt_requested:
        # Cleanup partial results
        await self.cleanup_partial_execution(result)
        return ToolResult(error="Interrupted after execution")
    
    return result

# Layer 3: 代码执行内部 (code_execution_tool.py)
async def execute_code_in_isolated_env(self, code):
    """Execute code with interrupt support"""
    session_id = self.isolated_python_session_id
    
    # Send code to isolated kernel
    await self.kernel_manager.execute(session_id, code)
    
    # Poll for results with interrupt checking
    while not self.kernel_manager.is_done(session_id):
        if self._interrupt_requested:
            # Interrupt the kernel
            await self.kernel_manager.interrupt(session_id)
            return ToolResult(error="Code execution interrupted")
        
        await asyncio.sleep(0.5)  # Poll interval
    
    return await self.kernel_manager.get_result(session_id)
```

<a id="32-中断传播机制"></a>
<a id="section-13-2-2"></a>
#### 13.2.2 中断传播机制

```mermaid
sequenceDiagram
    participant User
    participant MainThread
    participant SubagentThread
    participant ToolExecutor
    participant ExternalResource
    
    User->>MainThread: Ctrl+C / Interrupt Button
    MainThread->>MainThread: Set _interrupt_requested=True
    MainThread->>SubagentThread: Signal interrupt
    
    Note over SubagentThread: Next iteration check
    SubagentThread->>SubagentThread: Check _interrupt_requested
    SubagentThread->>ToolExecutor: Cancel pending operations
    
    alt Tool is running
        ToolExecutor->>ExternalResource: Abort operation
        ExternalResource-->>ToolExecutor: Acknowledge
        ToolExecutor-->>SubagentThread: Return error
    end
    
    SubagentThread->>SubagentThread: Cleanup resources
    SubagentThread->>MainThread: Return control
    
    MainThread->>MainThread: Clear _interrupt_requested
    MainThread->>User: Show interrupted status
```

<a id="33-资源清理策略"></a>
<a id="section-13-2-3"></a>
#### 13.2.3 资源清理策略

```python
def interrupt(self, message: str = None) -> None:
    """Comprehensive resource cleanup on interrupt"""
    self._interrupt_requested = True
    
    # 1. Close browser sessions
    try:
        if hasattr(self, 'browser_tool'):
            self.browser_tool.close()
            logger.info("Browser sessions closed")
    except Exception as e:
        logger.error(f"Error closing browser: {e}")
    
    # 2. Shutdown isolated Python environments
    try:
        import code_execution_service
        if self.isolated_python_session_id:
            code_execution_service.shutdown_isolated_session_sync(
                self.isolated_python_session_id
            )
            logger.info("Isolated Python session shutdown")
    except Exception as e:
        logger.error(f"Error shutting down Python session: {e}")
    
    # 3. Save conversation state
    try:
        if self.session_db:
            self.session_db.save_checkpoint()
            logger.info("Session checkpoint saved")
    except Exception as e:
        logger.error(f"Error saving checkpoint: {e}")
    
    # 4. Log interrupt reason
    if message:
        logger.warning(f"Interrupt reason: {message}")
```

<a id="34-子agent中断的特殊处理"></a>
<a id="section-13-2-4"></a>
#### 13.2.4 子Agent中断的特殊处理

```python
# delegate_tool.py:_run_single_child
def _run_single_child(task_index, goal, child, parent_agent):
    """Run a single child agent with interrupt propagation"""
    
    # Register child for interrupt tracking
    subagent_id = child._subagent_id
    _register_subagent({
        "subagent_id": subagent_id,
        "parent_id": parent_agent.session_id,
        "goal": goal,
        "agent": child,
        "started_at": time.time()
    })
    
    try:
        # Run child agent
        result = child.run_conversation()
        
        # Check if child was interrupted
        if child._interrupt_requested:
            logger.info(f"Subagent {subagent_id} was interrupted")
            return {
                "task_index": task_index,
                "status": "interrupted",
                "summary": "Task interrupted by user",
                "error": "User interrupt"
            }
        
        return {
            "task_index": task_index,
            "status": "completed",
            "summary": result.summary
        }
        
    finally:
        # Always unregister
        _unregister_subagent(subagent_id)
```

---


<a id="123-hitl审批approval"></a>
<a id="section-13-3"></a>
### 13.3 HITL：审批（Approval）

<a id="411-工具级审批hermes-agent"></a>
<a id="section-13-3-1"></a>
#### 13.3.1 工具级审批（Hermes Agent）

```python
# tools/approval.py
def prompt_dangerous_approval(
    command: str, 
    description: str,
    auto_approve_config: dict
) -> str:
    """
    Prompt user for approval before executing dangerous commands.
    
    Returns: "approve", "deny", or "once"
    """
    # Check auto-approval rules
    if should_auto_approve(command, auto_approve_config):
        logger.info(f"Auto-approved: {command}")
        return "approve"
    
    # Interactive approval in CLI mode
    if is_interactive_mode():
        print(f"\n⚠️  Dangerous command detected:")
        print(f"   {description}")
        print(f"   Command: {command}\n")
        
        while True:
            choice = input("[approve/deny/once/all]: ").lower()
            if choice in ["approve", "once", "all", "deny"]:
                return choice
            print("Invalid choice. Please try again.")
    
    # Non-interactive mode: deny by default
    logger.warning(f"Dangerous command denied (non-interactive): {command}")
    return "deny"

# Usage in terminal tool
async def execute_command(self, command: str):
    approval = prompt_dangerous_approval(
        command=command,
        description=self.analyze_risk(command),
        auto_approve_config=self.config.auto_approve
    )
    
    if approval == "deny":
        return {"error": "Command denied by user"}
    
    # Execute with approved permission
    return await self._run_command(command)
```

**配置文件示例**:
```yaml
# ~/.hermes/config.yaml
approval:
  auto_approve:
    safe_commands:
      - "ls"
      - "cat"
      - "grep"
      - "pwd"
    patterns:
      - "^git status.*"
      - "^find . -name.*"
    require_approval:
      - "rm -rf*"
      - "sudo.*"
      - "chmod 777.*"
      - "mkfs.*"
  
  interactive_mode: true  # false for batch/cron jobs
```

<a id="412-工作流级审批langgraph"></a>
<a id="section-13-3-2"></a>
#### 13.3.2 工作流级审批（LangGraph）

```python
# langgraph workflow with human approval
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

class ReviewState(TypedDict):
    document: str
    review_status: str
    feedback: str
    revised_document: str

def review_node(state: ReviewState):
    """Human review node"""
    
    # Pause and wait for human input
    decision = interrupt({
        "question": "Review the generated document",
        "document": state["document"],
        "options": {
            "approve": "Accept as-is",
            "revise": "Request revisions",
            "reject": "Reject completely"
        }
    })
    
    if decision == "approve":
        return {"review_status": "approved"}
    elif decision == "revise":
        feedback = interrupt({
            "question": "Provide feedback for revision"
        })
        return {"review_status": "needs_revision", "feedback": feedback}
    else:
        return {"review_status": "rejected"}

# Build workflow
workflow = StateGraph(ReviewState)
workflow.add_node("generate", generate_document)
workflow.add_node("review", review_node)
workflow.add_node("revise", revise_document)

workflow.set_entry_point("generate")
workflow.add_edge("generate", "review")
workflow.add_conditional_edges(
    "review",
    lambda s: s["review_status"],
    {
        "approved": END,
        "needs_revision": "revise",
        "rejected": END
    }
)
workflow.add_edge("revise", "review")

app = workflow.compile()
```


<a id="124-hitl澄清clarify"></a>
<a id="section-13-4"></a>
### 13.4 HITL：澄清（Clarify）

```python
# tools/clarify_tool.py
async def clarify(question: str, options: list = None) -> str:
    """
    Ask user for clarification when requirements are ambiguous.
    
    Args:
        question: The clarification question
        options: Optional list of suggested answers
    
    Returns:
        User's response
    """
    
    # Format the question
    print(f"\n❓ Clarification needed:")
    print(f"   {question}\n")
    
    if options:
        print("   Suggested answers:")
        for i, opt in enumerate(options, 1):
            print(f"   {i}. {opt}")
        print(f"   Or type your own answer\n")
    
    # Get user response
    if is_interactive_mode():
        response = input("Your answer: ")
        return response
    else:
        # Non-interactive mode: use default or fail
        if options:
            default = options[0]
            logger.info(f"Non-interactive mode, using default: {default}")
            return default
        else:
            raise ClarificationError(
                "Clarification required but not in interactive mode"
            )

# Usage in agent
async def handle_ambiguous_task(self, task: str):
    """Handle task with ambiguous requirements"""
    
    # Detect ambiguity
    ambiguities = self.detect_ambiguities(task)
    
    if ambiguities:
        # Ask for clarification
        clarifications = []
        for ambiguity in ambiguities:
            answer = await clarify(
                question=ambiguity.question,
                options=ambiguity.suggested_answers
            )
            clarifications.append((ambiguity, answer))
        
        # Refine task with clarifications
        refined_task = self.refine_task(task, clarifications)
        return await self.execute(refined_task)
    
    return await self.execute(task)
```

<a id="125-与-9-反向控制的衔接"></a>
<a id="section-13-5"></a>
### 13.5 与 §9 反向控制的衔接

父→子中断通道（`_active_subagents` / `interrupt_subagent`）见 [§9](#9-回调中继机制)。Approval 回调经 `initializer=_set_subagent_approval_cb` 注入子进程/线程。Steer ≠ interrupt：转向注入下轮用户消息，不设中断标志。

<a id="13-设计哲学与实践"></a>
<a id="section-14"></a>
## 14. 设计哲学与实践

<a id="设计哲学"></a>
<a id="section-14-1"></a>
### 14.1 设计哲学

<a id="111-为什么-blocked-tools-这样设计"></a>
<a id="section-14-1-1"></a>
#### 14.1.1 为什么 Blocked Tools 这样设计?

| Blocked Tool | 原因 | 风险 |
|-------------|------|------|
| `delegate_task` | 防止无限递归 | 指数级资源消耗 |
| `clarify` | 子代理不能问用户 | 用户体验混乱 |
| `memory` | 不能写共享记忆 | 数据竞争/污染 |
| `send_message` | 不能跨渠道发消息 | 副作用不可控 |
| `execute_code` | 避免脚本生成器 | 安全风险/刷屏 |

**例外**: `role='orchestrator'` 重新添加 `delegate_task`,允许有限嵌套

<a id="112-为什么-skip_memory-和-skip_context_files"></a>
<a id="section-14-1-2"></a>
#### 14.1.2 为什么 skip_memory 和 skip_context_files?

**skip_memory=True**:
- ✅ 避免子代理写入父代理的 MEMORY.md
- ✅ 防止记忆污染 (子任务的知识不一定适合全局)
- ✅ 减少 I/O 开销 (子代理通常是短期的)

**skip_context_files=True**:
- ✅ 避免加载 AGENTS.md/SOUL.md 等大文件
- ✅ 减少 token 消耗 (子代理 prompt 更轻量)
- ✅ 聚焦任务目标 (不需要项目级知识)

**权衡**:
- ❌ 子代理无法访问项目约定 (AGENTS.md)
- ❌ 子代理无法利用长期记忆 (MEMORY.md)
- ✅ 但可以通过 `context` 参数手动传递必要信息

<a id="113-为什么默认-max_depth=1"></a>
<a id="section-14-1-3"></a>
#### 14.1.3 为什么默认 MAX_DEPTH=1?

**设计哲学**: **扁平优于嵌套**

**理由**:
1. **复杂度控制**: 深层嵌套难以调试和理解
2. **资源管理**: 每层嵌套都增加预算和延迟
3. **错误传播**: 深层嵌套的错误难以追溯
4. **可观测性**: TUI 显示扁平树更清晰

**例外情况**:
- 需要更深嵌套时,提高 `delegation.max_spawn_depth` (上限 3)
- 使用 `role='orchestrator'` 显式声明需要再委派

<a id="114-为什么子代理使用-ephemeral_system_prompt"></a>
<a id="section-14-1-4"></a>
#### 14.1.4 为什么子代理使用 ephemeral_system_prompt?

```python
child = AIAgent(
    ephemeral_system_prompt=child_prompt,  # 临时 system prompt
    quiet_mode=True,                       # 静默模式
    ...
)
```

**原因**:
1. **不污染缓存**: ephemeral prompt 不影响父代理的 `_cached_system_prompt`
2. **生命周期短**: 子代理通常只运行一轮,不需要持久化 prompt
3. **灵活性高**: 每次委派可以动态构建不同的 prompt
4. **隔离性好**: 子代理 prompt 变化不会影响父代理的 Anthropic 缓存

---

<a id="最佳实践"></a>
<a id="section-14-2"></a>
### 14.2 最佳实践

<a id="✅-推荐做法"></a>
<a id="section-14-2-1"></a>
#### 14.2.1 推荐做法

1. **明确任务边界**: 每个子代理应该有清晰、独立的目标
2. **使用 Batch Mode**: 多个独立子任务用 `tasks` 数组并行
3. **控制深度**: 默认 `max_spawn_depth=2`,避免过深嵌套
4. **传递必要 Context**: 通过 `context` 参数提供子代理需要的背景
5. **监控进度**: 使用 TUI `/agents` 查看活跃子代理树
6. **设置合理预算**: `delegation.max_iterations=50` 通常足够

<a id="section-14-2-2"></a>
#### 14.2.2 ❌ 避免做法

1. **不要过度委派**: 简单任务直接执行,不要拆分成子代理
2. **不要透传整个目标**: 委派应该添加价值 (分解/并行/隔离)
3. **不要忽略深度限制**: 超过 `max_spawn_depth` 会失败
4. **不要在子代理中写记忆**: 使用 `context` 返回结果给父代理
5. **不要假设工作区路径**: 子代理需要通过 `context` 或工具发现路径

<a id="📝-示例模式"></a>
<a id="section-14-2-3"></a>
#### 14.2.3 示例模式

**模式 1: 并行研究**
```python
delegate_task(
    tasks=[
        {"goal": "Research Python async patterns"},
        {"goal": "Research Rust concurrency models"},
        {"goal": "Compare performance characteristics"},
    ]
)
```

**模式 2: 分阶段处理**
```python
    # 阶段 1: 并行收集信息
info_result = delegate_task(
    tasks=[
        {"goal": "Read all .py files in src/"},
        {"goal": "Read all test files"},
        {"goal": "Read documentation"},
    ]
)

    # 阶段 2: 综合分析 (orchestrator)
analysis_result = delegate_task(
    goal="Synthesize findings from previous research",
    context=info_result,
    role="orchestrator"  # 可能需要再委派
)
```

**模式 3: 专业化分工**
```python
delegate_task(
    tasks=[
        {"goal": "Review code for security issues", "toolsets": ["core", "web"]},
        {"goal": "Check test coverage", "toolsets": ["core"]},
        {"goal": "Analyze performance bottlenecks", "toolsets": ["core", "ha"]},
    ]
)
```

---

<a id="故障排查"></a>
<a id="section-14-3"></a>
### 14.3 故障排查

<a id="常见问题"></a>
<a id="section-14-3-1"></a>
#### 14.3.1 常见问题

**Q1: 子代理立即失败,返回 "Depth limit reached"**

**A**: 检查 `delegation.max_spawn_depth` 配置:
```yaml
    # config.yaml
delegation:
  max_spawn_depth: 2  # 增加到 2 或 3
```

**Q2: 子代理看不到父代理的文件修改**

**A**: 子代理有干净上下文,不会自动看到父代理的操作。通过 `context` 传递:
```python
delegate_task(
    goal="Process the file I just created",
    context="Parent created /path/to/file.txt with content: ..."
)
```

**Q3: 子代理耗时过长**

**A**: 调整超时和预算:
```yaml
delegation:
  max_iterations: 30      # 降低预算
  child_timeout: 300      # 降低超时 (秒)
```

**Q4: TUI 看不到子代理进度**

**A**: 确保父代理有 `tool_progress_callback`:
```python
agent = AIAgent(
    tool_progress_callback=cli_spinner_callback,  # 必须有
    ...
)
```

**Q5: 子代理无法访问某些工具**

**A**: 检查 `DELEGATE_BLOCKED_TOOLS` 和 `enabled_toolsets`:
```python
    # 子代理只能访问非 blocked 的工具
    # 如果需要额外工具,通过 toolsets 参数指定
delegate_task(
    goal="...",
    toolsets=["core", "web", "browser"]  # 显式指定
)
```

---

<a id="14-上下文压缩完整流程"></a>
<a id="141-压缩触发时机"></a>
<a id="142-完整压缩时序图"></a>
<a id="143-压缩策略详解"></a>
<a id="144-与其他框架对比"></a>
<a id="145-最佳实践"></a>
<a id="146-故障排查"></a>
<a id="1四层渐进压缩"></a>
<a id="2会话分裂机制"></a>
<a id="3双层记忆同步"></a>
<a id="4todo-注入机制"></a>
<a id="5异步预取优化"></a>
<a id="✅-推荐配置"></a>
<a id="❌-避免做法"></a>
<a id="📊-监控指标"></a>
<a id="14-子代理与通用压缩的边界"></a>
<a id="section-15"></a>
## 15. 子代理与通用压缩的边界

子代理复用运行时压缩能力，不拥有另一套通用压缩引擎。多代理篇只关心子任务目标、上下文隔离和结果回收；通用压缩与旧设计对照放到运行时篇。

完整设计、图表与代码解读已移至 [历史压缩设计与现行链路对照（非当前执行合约）](AGENT_LOOP_ARCHITECTURE.md#historical-compaction-design)。本处只保留与本篇主题直接相关的边界。

---

<a id="15-019-增量live-viewable-子-agent-transcript"></a>
<a id="section-16"></a>
## 16. 0.19 增量：Live-viewable 子 Agent transcript

父会话可在子 Agent 运行时 **tail** 其实况（不再只等 `delegate_task` 最终 summary）：

- 事件：`subagent.thinking` / `subagent.text` / `subagent.tool` / `subagent.complete`
- `tui_gateway` 镜像到 watch session 的 `reasoning.delta` / `message.delta` / `tool.*`
- 设计要点：仅镜像进 **未升级为完整 agent** 的 live watch 窗；已有 native stream 的 session 不双重镜像

详述：[AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) §10.3 · [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md)

---

<a id="16-附录跨框架中断--hitl-对照"></a>
<a id="section-17"></a>
## 17. 附录：跨框架中断 / HITL 对照

<a id="总览表"></a>
<a id="section-17-1"></a>
### 17.1 总览表

| 框架 | 中断支持 | HITL支持 | 中断粒度 | 恢复机制 | 实现复杂度 |
|------|---------|----------|---------|---------|-----------|
| **hermes-agent** | ✅ 完善 | ✅ 中等 | 会话/工具/迭代 | Checkpoint + SessionDB | 高 |
| **OpenHands** | ✅ 完善 | ✅ 完善 | 会话/工具/代码行 | EventStream重放 | 非常高 |
| **AutoGen** | ⚠️ 基础 | ✅ 完善 | 会话级 | Context重建 | 中 |
| **LangGraph** | ✅ 完善 | ✅ 完善 | 节点级 | State持久化 | 高 |
| **crewAI** | ❌ 无内置 | ⚠️ 基础 | N/A | N/A | 低 |
| **smolagents** | ❌ 无内置 | ❌ 无 | N/A | N/A | 极低 |
| **AgentScope** | ⚠️ 基础 | ⚠️ 基础 | 会话级 | Memory回放 | 中 |


<a id="hermes-在对比中的位置摘要"></a>
<a id="section-17-2"></a>
### 17.2 Hermes 在对比中的位置（摘要）

- **中断**: 主循环 + 工具前后 + 子 Agent 注册表 fan-out；冷停为主，checkpoint 非一等公民。
- **HITL**: `tools/approval.py` 危险命令门闩；`clarify` 交互澄清；无 LangGraph 式图内 `interrupt()` 工作流原语。
- **选型提示**: 要图状态机式人工审核 → LangGraph；要 IDE 安全策略网 → OpenHands；要本地优先委托子 Agent → Hermes。

<a id="实践原则摘录"></a>
<a id="section-17-3"></a>
### 17.3 实践原则（摘录）

<a id="多层检测点"></a>
<a id="section-17-3-1"></a>
#### 17.3.1 多层检测点

**不要依赖单一的中断检查点**，在关键位置都要设置检测：

```python
# ❌ Bad: 只在主循环检查
async def run(self):
    while not self._interrupt_requested:
        result = await self.heavy_computation()  # 无法中断
        return result

# ✅ Good: 多处检查
async def run(self):
    while not self._interrupt_requested:
        # Check before heavy operation
        if self._interrupt_requested:
            break
        
        result = await self.heavy_computation(
            interrupt_check=lambda: self._interrupt_requested
        )
        
        # Check after heavy operation
        if self._interrupt_requested:
            await self.cleanup_partial_result(result)
            break
```

**推荐检查点**:
- 主循环开始/结束
- 工具调用前/后
- 长时间计算任务的内部轮询
- 网络请求的超时回调
- 文件I/O操作间隙

<a id="原则2-优雅降级graceful-degradation"></a>
<a id="section-17-3-2"></a>
#### 17.3.2 原则2: 优雅降级（Graceful Degradation）

中断时尽量保存已完成的工作：

```python
async def execute_with_graceful_interrupt(self, tasks):
    """Execute tasks with graceful interrupt handling"""
    results = []
    
    for i, task in enumerate(tasks):
        try:
            if self._interrupt_requested:
                # Save partial results
                await self.save_intermediate_results(results)
                logger.info(f"Interrupted at task {i}/{len(tasks)}")
                return {
                    "status": "partial",
                    "completed": len(results),
                    "total": len(tasks),
                    "results": results
                }
            
            result = await self.execute_task(task)
            results.append(result)
            
        except Exception as e:
            logger.error(f"Task {i} failed: {e}")
            # Continue with next task
            continue
    
    return {
        "status": "completed",
        "results": results
    }
```

<a id="原则3-资源清理resource-cleanup"></a>
<a id="section-17-3-3"></a>
#### 17.3.3 原则3: 资源清理（Resource Cleanup）

确保中断时释放所有占用的资源：

```python
async def cleanup_on_interrupt(self):
    """Comprehensive resource cleanup"""
    
    cleanup_tasks = [
        self.close_browser_sessions(),
        self.shutdown_code_executors(),
        self.release_file_locks(),
        self.close_database_connections(),
        self.save_session_state()
    ]
    
    # Run all cleanup tasks concurrently
    results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
    
    # Log any cleanup failures
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Cleanup task {i} failed: {result}")
```

<a id="62-hitl设计模式"></a>
<a id="section-17-4"></a>
### 17.4 HITL设计模式

<a id="模式1-预防式hitlpreventive-hitl"></a>
<a id="section-17-4-1"></a>
#### 17.4.1 模式1: 预防式HITL（Preventive HITL）

在执行危险操作**之前**请求审批：

```python
class PreventiveHITL:
    """Request approval BEFORE executing sensitive operations"""
    
    SENSITIVE_OPERATIONS = {
        "file_delete": {"risk": "HIGH", "requires_approval": True},
        "database_drop": {"risk": "CRITICAL", "requires_approval": True},
        "api_call": {"risk": "MEDIUM", "requires_approval": False},
    }
    
    async def execute_with_approval(self, operation: str, params: dict):
        """Execute operation with preventive approval"""
        
        op_config = self.SENSITIVE_OPERATIONS.get(operation, {})
        
        if op_config.get("requires_approval"):
            # Request human approval
            approval = await self.request_approval(
                operation=operation,
                params=params,
                risk_level=op_config["risk"]
            )
            
            if not approval.approved:
                raise ApprovalDeniedError(
                    f"Operation {operation} denied: {approval.reason}"
                )
        
        # Execute approved operation
        return await self.execute(operation, params)
```

**适用场景**:
- 删除重要文件/数据库
- 修改系统配置
- 执行高风险命令
- 发送敏感信息

<a id="模式2-检查点式hitlcheckpoint-hitl"></a>
<a id="section-17-4-2"></a>
#### 17.4.2 模式2: 检查点式HITL（Checkpoint HITL）

在任务的关键阶段设置审查点：

```python
class CheckpointHITL:
    """Pause at predefined checkpoints for human review"""
    
    CHECKPOINTS = [
        "after_research",
        "before_implementation",
        "before_deployment"
    ]
    
    async def execute_with_checkpoints(self, task: Task):
        """Execute task with checkpoint reviews"""
        
        state = TaskState(task=task)
        
        for stage in task.stages:
            # Execute stage
            state = await self.execute_stage(stage, state)
            
            # Check if there's a review checkpoint
            checkpoint_name = f"after_{stage.name}"
            if checkpoint_name in self.CHECKPOINTS:
                review_result = await self.review_checkpoint(
                    checkpoint=checkpoint_name,
                    state=state
                )
                
                if review_result.action == "APPROVE":
                    continue  # Continue to next stage
                
                elif review_result.action == "REVISE":
                    # Go back and revise current stage
                    state = await self.revise_stage(
                        stage, 
                        state, 
                        review_result.feedback
                    )
                    # Re-review
                    continue
                
                elif review_result.action == "ABORT":
                    # Stop execution
                    return TaskResult(
                        status="aborted",
                        reason=f"Aborted at checkpoint: {checkpoint_name}"
                    )
        
        return TaskResult(status="completed", state=state)
```

**适用场景**:
- 多阶段工作流（研究→设计→实现→测试）
- 需要质量保证的关键任务
- 合规性要求的流程

<a id="模式3-按需式hitlon-demand-hitl"></a>
<a id="section-17-4-3"></a>
#### 17.4.3 模式3: 按需式HITL（On-Demand HITL）

Agent主动请求人类帮助：

```python
class OnDemandHITL:
    """Agent proactively requests human assistance"""
    
    async def handle_uncertainty(self, situation: UncertainSituation):
        """Handle situations where agent is uncertain"""
        
        confidence = self.assess_confidence(situation)
        
        if confidence < self.confidence_threshold:
            # Low confidence - ask for help
            clarification = await self.request_cla

> …（原对比文档后半案例/选型长文已省略，避免与架构正文重复。）

---

**相关文档**: [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) · [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md)（`delegate_task` 深潜）· [PROMPT_SYSTEM_ARCHITECTURE.md](PROMPT_SYSTEM_ARCHITECTURE.md) · [KANBAN_MULTIAGENT_DEEP_ANALYSIS.md](KANBAN_MULTIAGENT_DEEP_ANALYSIS.md)

```

```
```

```

```

<!-- 旧目录与迁移章节锚点兼容；完整内容入口见文首目录及主题迁移表。 -->
<a id="toolsclarify_toolpy"></a>
<a id="usage-in-agent"></a>
<a id="❌-避免做法-1"></a>
