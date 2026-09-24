# OpenHands Software Agent SDK + OpenHands 项目深度分析

> **版本**: v1.0  
> **最后更新**: 2026-04-29  
> **分析对象**: software-agent-sdk（openhands-sdk 1.19.x）+ OpenHands（openhands-ai 1.6.x）  
> **源码路径**: `/Users/gqli/work/deepagents/software-agent-sdk/` + `/Users/gqli/work/deepagents/OpenHands/`  
> **核心特性**: 事件溯源架构、Condenser 记忆压缩、Sandbox-as-Runtime、MCP 集成、Hooks 系统

---

## 目录

**Part I: Software Agent SDK**
1. [SDK 架构总览](#1-sdk-架构总览)
2. [Agent 核心循环（step）](#2-agent-核心循环step)
3. [Event 事件体系](#3-event-事件体系)
4. [Conversation 状态管理](#4-conversation-状态管理)
5. [View 与 Condenser（记忆管理）](#5-view-与-condenser记忆管理)
6. [Tool 工具系统](#6-tool-工具系统)
7. [Prompt 提示词系统](#7-prompt-提示词系统)
8. [Hooks 钩子系统](#8-hooks-钩子系统)
9. [Skills 技能系统](#9-skills-技能系统)
10. [MCP 集成](#10-mcp-集成)
11. [Security 安全机制](#11-security-安全机制)

**Part II: OpenHands 主项目**
12. [OpenHands 架构总览](#12-openhands-架构总览)
13. [V0 Legacy 架构](#13-v0-legacy-架构)
14. [V1 App Server 架构](#14-v1-app-server-架构)
15. [EventStream 发布/订阅](#15-eventstream-发布订阅)
16. [Sandbox 沙箱系统](#16-sandbox-沙箱系统)
17. [V0 vs V1 对比](#17-v0-vs-v1-对比)

**Part III: 跨框架对比**
18. [与 smolagents / OpenAI Agents SDK 对比](#18-与-smolagents--openai-agents-sdk-对比)

---

# Part I: Software Agent SDK

## 1. SDK 架构总览

### 1.1 Monorepo 结构

software-agent-sdk 是一个 UV workspace monorepo，包含 4 个包：

```
software-agent-sdk/
├── openhands-sdk/          # 核心 SDK（Agent, LLM, Event, Conversation, Tools 抽象）
│   └── openhands/sdk/
│       ├── agent/          # Agent 实现 + Prompt 模板
│       ├── context/        # Condenser + View + Skills + Prompts
│       ├── conversation/   # 会话状态 + 事件存储 + 可视化
│       ├── critic/         # Critic 评估系统
│       ├── event/          # 事件类型定义
│       ├── hooks/          # 钩子系统
│       ├── io/             # 文件存储抽象
│       ├── llm/            # LLM 封装（LiteLLM）
│       ├── mcp/            # MCP 协议集成
│       ├── plugin/         # 插件系统
│       ├── secret/         # 密钥管理
│       ├── security/       # 安全分析器
│       ├── settings/       # 配置模型
│       ├── skills/         # 技能加载与执行
│       ├── subagent/       # 子代理注册
│       ├── tool/           # 工具抽象 + 内建工具
│       ├── utils/          # 工具函数
│       └── workspace/      # 工作区抽象
├── openhands-tools/        # 具体工具实现
│   └── openhands/tools/
│       ├── terminal/       # Shell 终端工具（tmux）
│       ├── file_editor/    # 文件编辑工具（str_replace/OH-ACI）
│       ├── apply_patch/    # 补丁应用工具
│       ├── browser_use/    # 浏览器自动化工具
│       ├── delegate/       # 子代理委派工具
│       ├── glob/           # 文件搜索工具
│       ├── grep/           # 内容搜索工具
│       ├── task/           # 任务管理工具
│       ├── task_tracker/   # 任务跟踪工具
│       ├── gemini/         # Gemini 专用工具集
│       ├── planning_file_editor/ # 规划文件编辑
│       ├── preset/         # 工具预设（default, gemini, gpt5, planning）
│       └── tom_consult/    # TOM 咨询工具
├── openhands-agent-server/ # Agent 执行服务器（FastAPI）
│   └── openhands/agent_server/
└── openhands-workspace/    # 远程工作区集成
```

### 1.2 核心设计原则

1. **事件溯源（Event Sourcing）**: 所有交互记录为不可变事件流，不维护独立的"消息列表"
2. **Agent 无状态**: Agent 配置是 frozen Pydantic 模型，运行时状态存于 `ConversationState`
3. **View 分离**: 原始事件流 → `View`（筛选/压缩后的 LLM 可见视图） → `Message` 列表
4. **工具即第一公民**: 所有能力通过统一 `ToolDefinition` 暴露，含 MCP 适配
5. **安全优先**: `SecurityRisk` 注入、确认策略、Hook 拦截、密钥隔离

### 1.3 依赖关系

```
openhands-tools ──depends──→ openhands-sdk
openhands-agent-server ──depends──→ openhands-sdk + fastapi
openhands-workspace ──depends──→ openhands-sdk + openhands-agent-server
```

核心外部依赖：`litellm`（LLM 统一接口）、`pydantic`（数据模型）、`fastmcp`（MCP 客户端）、`tenacity`（重试）

---

## 2. Agent 核心循环（step）

### 2.1 类继承体系

```
pydantic.BaseModel
  └── DiscriminatedUnionMixin    # 多态序列化（kind 字段做类型判别）
        └── AgentBase (ABC)       # 抽象基类：配置 + 工具初始化
              └── CriticMixin     # Critic 评估混入
                    └── ResponseDispatchMixin  # LLM 响应分发混入
                          └── Agent           # 具体实现
```

### 2.2 AgentBase 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `llm` | `LLM` | 语言模型配置 |
| `tools` | `list[Tool]` | 工具规格列表 |
| `mcp_config` | `dict` | MCP 服务器配置 |
| `include_default_tools` | `list[str]` | 内建工具（默认 `FinishTool` + `ThinkTool`） |
| `agent_context` | `AgentContext` | 技能、系统消息后缀 |
| `system_prompt` | `str \| None` | 内联系统提示（覆盖模板） |
| `system_prompt_filename` | `str` | Jinja2 模板文件名（默认 `system_prompt.j2`） |
| `condenser` | `CondenserBase \| None` | 历史压缩器 |
| `critic` | `CriticBase \| None` | 动作评估器 |
| `tool_concurrency_limit` | `int` | 工具并行度（默认 1） |

### 2.3 step() 完整流程

```
step(conversation, on_event, on_token)
  │
  ├── Phase 1: 待处理动作检查
  │   └── 有未匹配的 ActionEvent → 执行它们 → return
  │       （用于确认模式恢复 + 崩溃恢复）
  │
  ├── Phase 2: 被阻止的用户消息检查
  │   └── Hook 阻止了最后的用户消息 → FINISHED → return
  │
  ├── Phase 3: LLM 消息准备
  │   ├── View.from_events(state.events)  ← 将原始事件构建为视图
  │   ├── condenser.condense(view)        ← 可能触发压缩
  │   │   └── 返回 Condensation → 发射事件 → return（下一轮处理）
  │   └── events_to_messages()            ← 转换为 LLM Message 列表
  │
  ├── Phase 4: LLM 调用
  │   ├── make_llm_completion(llm, messages, tools)
  │   └── 异常处理:
  │       ├── FunctionCallValidationError → 注入错误消息 → return（重试）
  │       ├── LLMMalformedConversationHistory → 触发 CondensationRequest
  │       └── LLMContextWindowExceedError → 触发 CondensationRequest
  │
  └── Phase 5: 响应分类与分发
      │
      ├── classify_response(message) → LLMResponseType
      │
      ├── TOOL_CALLS:
      │   ├── 解析每个 tool_call → _get_action_event()
      │   │   ├── parse_tool_call_arguments()
      │   │   ├── normalize_tool_call()（别名：bash→terminal, str_replace→file_editor）
      │   │   ├── fix_malformed_tool_arguments()
      │   │   ├── 提取 security_risk, summary
      │   │   ├── tool.action_from_arguments()
      │   │   ├── critic 评估（可选）
      │   │   └── 发射 ActionEvent
      │   ├── 需要用户确认？ → WAITING_FOR_CONFIRMATION → return
      │   └── _execute_actions():
      │       ├── _ActionBatch.prepare():
      │       │   ├── _truncate_at_finish()（FinishTool 后截断）
      │       │   ├── 分离被阻止的动作
      │       │   └── ParallelToolExecutor.execute_batch()（含资源锁）
      │       ├── batch.emit()（按顺序发射事件）
      │       └── batch.finalize():
      │           ├── FinishTool + 迭代精炼未完 → 注入 followup → RUNNING
      │           └── FinishTool 最终 → FINISHED
      │
      ├── CONTENT:
      │   ├── 发射 MessageEvent（+ critic 评估）
      │   └── state.execution_status = FINISHED
      │
      └── REASONING_ONLY | EMPTY:
            ├── 发射 MessageEvent
            └── 注入纠正提示："请使用工具继续" → RUNNING（循环继续）
```

### 2.4 状态转换图

```
IDLE
  ↓ conversation.run()
RUNNING ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
  │                                                      ↑
  ├── 待处理动作 → 执行 → RUNNING 或 FINISHED             │
  ├── 用户消息被阻止 → FINISHED                           │
  ├── 需要压缩 → 发射 Condensation → RUNNING ────────────┘
  ├── LLM 错误 → 注入错误消息 → RUNNING ─────────────────┘
  ├── TOOL_CALLS:                                        │
  │   ├── 需要确认 → WAITING_FOR_CONFIRMATION             │
  │   │                 ↓ 用户确认/拒绝                    │
  │   │                 → RUNNING ──────────────────────┘
  │   ├── FinishTool + 迭代精炼继续 → RUNNING ────────────┘
  │   ├── FinishTool 最终 → FINISHED
  │   └── 普通工具 → 执行 → RUNNING ─────────────────────┘
  ├── CONTENT → FINISHED
  └── REASONING_ONLY/EMPTY → 纠正提示 → RUNNING ─────────┘

终态: FINISHED, ERROR, STUCK
```

### 2.5 _ActionBatch 批处理机制

```python
@dataclass(frozen=True, slots=True)
class _ActionBatch:
    action_events: list[ActionEvent]
    has_finish: bool
    blocked_reasons: dict[str, str]      # Hook 阻止的动作
    results_by_id: dict[str, list[Event]] # 执行结果

    @staticmethod
    def _truncate_at_finish(events): ...  # FinishTool 之后的调用全部丢弃

    @classmethod
    def prepare(cls, events, executor, tool_runner, tools):
        # 1. 截断到 FinishTool
        # 2. 分离被 Hook 阻止的动作
        # 3. ParallelToolExecutor 执行剩余动作
        ...

    def emit(self, on_event):
        # 按原始顺序发射所有事件（含 UserRejectObservation）
        ...

    def finalize(self, conversation, state, on_event, check_refinement):
        # 处理 FinishTool: 迭代精炼 或 最终完成
        ...
```

### 2.6 ParallelToolExecutor 并行执行

```python
class ParallelToolExecutor:
    def execute_batch(self, action_events, tool_runner, tools):
        # max_workers == 1 → 顺序执行
        # max_workers > 1 → ThreadPoolExecutor 并行
        ...

    def _run_safe(self, action, tool_runner, tool):
        # 1. 提取工具声明的资源
        # 2. 解析锁定键:
        #    - 未声明 → 退化为工具级互斥锁 "tool:<name>"
        #    - 声明但空键 → 无锁（安全并行）
        #    - 声明了键 → 锁定对应资源
        # 3. 带锁执行工具
        ...
```

---

## 3. Event 事件体系

### 3.1 设计理念

OpenHands SDK 采用**事件溯源（Event Sourcing）**模式：所有交互（用户消息、LLM 响应、工具调用、观察结果、系统状态）都记录为不可变事件。不维护独立的"消息列表"——LLM 输入通过遍历事件流动态生成。

### 3.2 事件类层次

```
Event (ABC, DiscriminatedUnionMixin)      # frozen=True, extra="forbid"
├── LLMConvertibleEvent (ABC)              # 有 to_llm_message() → Message
│   ├── SystemPromptEvent                  # role="system"
│   │   ├── system_prompt: TextContent     # 静态提示（可缓存）
│   │   ├── tools: list[ToolDefinition]    # 可用工具
│   │   └── dynamic_context: TextContent   # 动态上下文
│   │
│   ├── ActionEvent                        # role="assistant" + tool_calls
│   │   ├── thought: Sequence[TextContent] # Agent 推理文本
│   │   ├── reasoning_content: str         # 推理模型中间思考
│   │   ├── thinking_blocks: list          # Anthropic thinking
│   │   ├── action: Action | None          # 解析后的工具调用
│   │   ├── tool_name: str                 # 工具名
│   │   ├── tool_call_id: ToolCallID       # LLM 分配的调用 ID
│   │   ├── llm_response_id: EventID       # 分组并行调用
│   │   ├── security_risk: SecurityRisk    # 安全风险评估
│   │   ├── critic_result: CriticResult    # Critic 评估结果
│   │   └── summary: str                   # ~10 词动作摘要
│   │
│   ├── ObservationBaseEvent (ABC)         # role="tool"
│   │   ├── ObservationEvent               # 成功执行结果
│   │   ├── UserRejectObservation          # 用户/Hook 拒绝
│   │   └── AgentErrorEvent                # 框架错误
│   │
│   ├── MessageEvent                       # role="user" 或 "assistant"
│   │   ├── llm_message: Message           # 完整 LLM 消息
│   │   ├── activated_skills: list[str]    # 触发的技能
│   │   ├── extended_content: list         # AgentContext 注入内容
│   │   └── sender: str                    # 多代理溯源
│   │
│   └── CondensationSummaryEvent           # role="user"（注入的摘要）
│
├── Condensation                           # 压缩动作（非 LLM 可见）
│   ├── forgotten_event_ids: list[EventID] # 被遗忘的事件
│   ├── summary: str                       # 摘要文本
│   └── summary_offset: int               # 摘要插入位置
│
├── CondensationRequest                    # 压缩请求信号
├── ConversationStateUpdateEvent           # WebSocket 状态同步
├── HookExecutionEvent                     # Hook 执行记录
├── LLMCompletionLogEvent                  # LLM 调用日志
├── StreamingDeltaEvent                    # 流式响应增量
├── TokenEvent                             # Token 级事件
└── PauseEvent                             # 用户暂停
```

### 3.3 多态序列化机制

所有事件通过 `DiscriminatedUnionMixin` 实现自动多态序列化：

- **序列化**: `kind` 字段自动设为类名（如 `"ActionEvent"`）
- **反序列化**: `Event.model_validate_json(data)` 读取 `kind` 字段，解析到对应子类
- **子类发现**: 递归扫描所有非抽象子类，按类名匹配

### 3.4 events_to_messages() 批处理逻辑

```python
# LLMConvertibleEvent.events_to_messages(events) → list[Message]
#
# 核心算法: 合并同一 llm_response_id 的连续 ActionEvent
#
# 1. 顺序遍历事件
# 2. 遇到 ActionEvent 时，向前看连续的同 llm_response_id 的 ActionEvent
# 3. 合并为单条 Message:
#    - role="assistant"
#    - content = 第一个事件的 thought（共享）
#    - tool_calls = [所有事件的 tool_call]
#    - reasoning_content/thinking_blocks 来自第一个事件
# 4. 非 ActionEvent 直接调用 to_llm_message()
```

---

## 4. Conversation 状态管理

### 4.1 ConversationState

核心状态对象，管理会话生命周期和事件持久化：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `ConversationID` | 唯一会话 ID |
| `agent` | `AgentBase` | Agent 配置 |
| `workspace` | `BaseWorkspace` | 工作目录 |
| `execution_status` | `ConversationExecutionStatus` | 当前状态 |
| `max_iterations` | `int` | 最大迭代次数 |
| `confirmation_policy` | `ConfirmationPolicyBase` | 确认策略 |
| `security_analyzer` | `SecurityAnalyzerBase` | 安全分析器 |
| `secret_registry` | `SecretRegistry` | 密钥注册表 |
| `agent_state` | `dict[str, Any]` | Agent 运行时状态（如迭代精炼计数） |
| `hook_config` | `HookConfig` | Hook 定义 |

### 4.2 执行状态枚举

```
IDLE → RUNNING → FINISHED
                → ERROR
                → STUCK
                → PAUSED → RUNNING
                → WAITING_FOR_CONFIRMATION → RUNNING
                → DELETING
```

### 4.3 EventLog 持久化

```python
class EventLog(EventsListBase):
    # 文件命名: event-{idx:05d}-{event_id}.json
    # 例如: events/event-00003-a1b2c3d4.json
    #
    # 特性:
    # - 每个事件独立 JSON 文件
    # - 双向索引: id↔idx 查找
    # - 文件级锁（30 秒超时）保证线程/进程安全
    # - append 时同步磁盘状态（支持多进程写入）
```

### 4.4 Conversation 工厂

```python
class Conversation:
    def __new__(cls, workspace, ...):
        if isinstance(workspace, (str, Path, LocalWorkspace)):
            return LocalConversation(...)
        elif isinstance(workspace, RemoteWorkspace):
            return RemoteConversation(...)

# API:
# conversation.send_message(msg)     # 发送用户消息
# conversation.run()                 # 执行 Agent 循环
# conversation.pause()               # 暂停
# conversation.condense()            # 强制压缩
# conversation.fork(...)             # 深拷贝（新 ID）
# conversation.execute_tool(name, action)  # 直接工具调用
```

---

## 5. View 与 Condenser（记忆管理）

### 5.1 View 系统

`View` 是原始事件流和 LLM 输入之间的桥梁：

```
原始事件流                  View                    LLM 消息
[Event, Event, ...]  →  View.from_events()  →  events_to_messages()  →  list[Message]
                           │
                           ├── 应用 Condensation（移除被遗忘事件，插入摘要）
                           ├── 跳过非 LLMConvertible 事件
                           └── 追踪 unhandled_condensation_request
```

**manipulation_indices**: 计算安全的分割/移除位置，避免破坏工具调用/结果配对的原子性。

### 5.2 Condenser 层次

```
CondenserBase (ABC)
├── NoOpCondenser                    # 透传，不压缩
├── PipelineCondenser                # 串联多个 Condenser
│   └── condensers: list[PipelinableCondenserBase]
└── PipelinableCondenserBase (ABC)
    └── RollingCondenser (ABC)       # 滚动压缩策略
        └── LLMSummarizingCondenser  # LLM 智能摘要
```

### 5.3 LLMSummarizingCondenser 详解

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `llm` | — | 独立的摘要 LLM（与 Agent LLM 分离） |
| `max_size` | 240 | 触发压缩的最大事件数 |
| `max_tokens` | None | 基于 token 的阈值 |
| `keep_first` | 2 | 永不压缩的初始事件数 |
| `minimum_progress` | 0.1 | 每次至少遗忘 10% 的事件 |

**压缩算法：**

```
1. 计算每个活跃原因（REQUEST/TOKENS/EVENTS）应保留的后缀事件数
2. 取最严格的约束（min）
3. 尊重 manipulation_indices（不破坏工具调用/结果配对原子性）
4. 将要遗忘的事件渲染为字符串，发送给摘要 LLM
5. 返回 Condensation（forgotten_event_ids + summary + summary_offset）
```

**硬重置：** 当普通压缩失败但压缩需求为 HARD 时，尝试摘要**所有**事件，指数退避截断事件字符串长度（最多 5 次重试，每次 ×0.8）。

### 5.4 与 smolagents 的对比

| 维度 | OpenHands SDK | smolagents |
|------|--------------|-----------|
| **记忆模型** | 事件溯源（Event Sourcing） | 结构化步骤（MemoryStep） |
| **存储** | 独立 JSON 文件 + 双向索引 | 内存列表 |
| **持久化** | 内建（EventLog） | 无 |
| **压缩策略** | LLM 摘要 + Pipeline + 多种策略 | summary_mode 双轨 |
| **LLM 压缩调用** | 是（独立 LLM） | 无 |
| **原子性保证** | manipulation_indices | 无 |
| **复杂度** | 高 | 低 |

---

## 6. Tool 工具系统

### 6.1 工具抽象层次

```
Tool (spec)          # 轻量规格：name + params
  ↓ resolve_tool()
ToolDefinition       # 完整定义：schema + executor + annotations
  ├── FinishTool     # 内建：任务完成
  ├── ThinkTool      # 内建：推理/头脑风暴
  ├── InvokeSkillTool  # 内建：技能调用
  └── MCPToolDefinition  # MCP 工具适配
```

### 6.2 ToolDefinition 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `description` | `str` | 工具描述 |
| `action_type` | `type[Action]` | 输入 schema |
| `observation_type` | `type[Observation]` | 输出 schema |
| `annotations` | `ToolAnnotations` | MCP 兼容行为提示 |
| `executor` | `ToolExecutor` | 执行函数 |
| `meta` | `dict` | 元数据 |

### 6.3 动态 Schema 增强

```python
# 在工具 schema 中动态注入两个字段:
# 1. security_risk: SecurityRisk  # 安全风险评估（三级）
# 2. summary: str | None          # ~10 词动作摘要
#
# 这些字段被重排到 schema 顶部，防止 token 截断时丢失关键元数据
```

### 6.4 全局注册表

```python
_REG: dict[str, Resolver] = {}  # 工具名 → 解析函数

def register_tool(name, tool_or_class_or_factory):
    # 支持三种注册方式:
    # 1. 实例 (ToolDefinition) → 固定解析器
    # 2. 子类 (ToolDefinition subclass) → 调用 .create()
    # 3. 可调用工厂 → 直接包装

def resolve_tool(spec: Tool, state: ConversationState) -> list[ToolDefinition]:
    # 从注册表查找并实例化工具
```

### 6.5 openhands-tools 具体工具

| 工具 | 说明 | 资源声明 |
|------|------|---------|
| **TerminalTool** | tmux 终端执行 | 互斥锁（串行） |
| **FileEditorTool** | 文件查看/编辑（str_replace/OH-ACI） | 无锁（可并行） |
| **ApplyPatchTool** | 应用补丁 | — |
| **BrowserUseTool** | 浏览器自动化 | — |
| **DelegateTool** | 子代理委派 | — |
| **GlobTool** | 文件搜索 | — |
| **GrepTool** | 内容搜索 | — |
| **TaskTool** | 任务管理 | — |
| **TaskTrackerTool** | 任务跟踪 | — |

---

## 7. Prompt 提示词系统

### 7.1 Jinja2 模板体系

```
agent/prompts/
├── system_prompt.j2                 # 默认 Agent 人设
├── system_prompt_planning.j2        # 规划 Agent（4 阶段工作流）
├── system_prompt_interactive.j2     # 交互模式
├── system_prompt_long_horizon.j2    # 长任务模式
├── security_policy.j2               # 安全策略（三级）
├── self_documentation.j2            # 自文档化
├── in_context_learning_example.j2   # ICL 示例
└── model_specific/                  # 模型专用覆盖
    ├── anthropic_claude.j2
    ├── google_gemini.j2
    └── openai_gpt/
```

### 7.2 系统提示词结构（system_prompt.j2）

```xml
<ROLE>          <!-- 角色定义 + 问答 vs 修复指南 -->
<MEMORY>        <!-- AGENTS.md 持久记忆 -->
<EFFICIENCY>    <!-- 成本意识、命令合并 -->
<FILE_SYSTEM_GUIDELINES>  <!-- 文件处理规则 -->
<CODE_QUALITY>  <!-- 最小改动、代码质量 -->
<VERSION_CONTROL>  <!-- Git 安全、Co-authored-by -->
<PULL_REQUESTS> <!-- 一次会话一个 PR -->
<PROBLEM_SOLVING_WORKFLOW>  <!-- 5 阶段: 探索→分析→测试→实现→验证 -->
<SELF_DOCUMENTATION>  <!-- 包含 self_documentation.j2 -->
<SECURITY>      <!-- 条件包含 security_policy.j2 -->
<BROWSER_TOOLS> <!-- 条件包含浏览器工具说明 -->
<EXTERNAL_SERVICES>  <!-- API 优先、AI 披露 -->
<!-- 模型专用覆盖: model_specific/{family}.j2 -->
```

### 7.3 静态 vs 动态分离

```python
# AgentBase.static_system_message  → 可缓存的静态提示
#   来源: system_prompt 字段 或 Jinja2 模板渲染
#   缓存: LLM 层面可做 prompt caching

# AgentBase.dynamic_context  → 每次会话变化的动态内容
#   来源: AgentContext（技能、运行时信息、密钥）
#   注入时机: SystemPromptEvent 的 dynamic_context 字段
```

---

## 8. Hooks 钩子系统

### 8.1 Hook 事件类型

| 事件 | 时机 | 可阻止 | 说明 |
|------|------|--------|------|
| `PRE_TOOL_USE` | 工具执行前 | 是 | 可拦截危险操作 |
| `POST_TOOL_USE` | 工具执行后 | 否 | 信息通知 |
| `USER_PROMPT_SUBMIT` | 用户发送消息时 | 是 | 可注入上下文 |
| `SESSION_START` | 会话开始 | 否 | 初始化 |
| `SESSION_END` | 会话结束 | 否 | 清理 |
| `STOP` | Agent 尝试停止 | 是 | 可阻止停止 |

### 8.2 执行机制

```python
class HookExecutor:
    # Hook 通过 Shell 脚本执行:
    # - 同步: subprocess.run()，JSON stdin/stdout
    # - 异步: subprocess.Popen()，fire-and-forget
    #
    # 环境变量:
    # - OPENHANDS_PROJECT_DIR
    # - OPENHANDS_SESSION_ID
    # - OPENHANDS_EVENT_TYPE
    # - OPENHANDS_TOOL_NAME
    #
    # 返回协议:
    # - exit code 0 = 允许
    # - exit code 2 = 阻止
    # - JSON stdout: { decision, reason, additionalContext }
```

---

## 9. Skills 技能系统

### 9.1 两种技能格式

| 格式 | 文件 | 加载方式 |
|------|------|---------|
| **AgentSkills** | `SKILL.md` | 渐进披露：列表 → `invoke_skill` 按需加载 |
| **Legacy OpenHands** | 任意 | 有触发器：条件注入；无触发器：始终注入 |

### 9.2 加载优先级

```
公共技能 (lowest) → 用户技能 → 项目技能 (highest)

公共: github.com/OpenHands/extensions, marketplace 过滤
用户: ~/.agents/skills/, ~/.openhands/skills/
项目: .agents/skills/, .openhands/skills/, AGENTS.md, .cursorrules, claude.md
```

### 9.3 InvokeSkillTool

```python
class InvokeSkillExecutor:
    def __call__(self, action, conversation):
        # 1. 从 conversation.state 获取技能目录和工作目录
        # 2. 按 name 查找匹配技能
        # 3. render_content_with_commands() 执行内联 !`cmd` 块
        # 4. 追加技能位置信息
        # 5. 记录调用到 state.invoked_skills
        ...
```

### 9.4 动态内容执行

```python
def render_content_with_commands(content, working_dir):
    # 处理内联 !`command` 语法:
    # - 保留围栏代码块
    # - 保留转义的 \!`cmd`
    # - 执行 !`cmd`（10 秒超时，50KB 输出上限）
    ...
```

---

## 10. MCP 集成

### 10.1 MCPClient

```python
class MCPClient(fastmcp.Client):
    # 同步封装异步 MCP 客户端:
    # - AsyncExecutor 后台事件循环
    # - call_async_from_sync() 桥接同步→异步
    # - 生命周期管理（上下文管理器）
```

### 10.2 MCPToolDefinition

```python
class MCPToolDefinition(ToolDefinition[MCPToolAction, MCPToolObservation]):
    # 动态 Action 类型: 从 MCP schema 自动创建 Pydantic 模型
    # 缓存机制: _mcp_dynamic_action_type 避免重复创建
    # 转换路径: MCP tool → OpenHands ToolAnnotations → ToolDefinition
    # 执行: MCPToolExecutor → client.call_tool_mcp() → MCPToolObservation
```

---

## 11. Security 安全机制

### 11.1 安全层次

| 层 | 机制 | 说明 |
|----|------|------|
| **Schema 注入** | `security_risk` 字段 | 每次工具调用 LLM 自评风险 |
| **安全分析器** | `SecurityAnalyzerBase` | LLM 或规则引擎分析动作安全性 |
| **确认策略** | `ConfirmationPolicyBase` | 高风险动作需用户确认 |
| **Hook 拦截** | `PRE_TOOL_USE` | 自定义 Shell 脚本审核 |
| **密钥隔离** | `LookupSecret` | API 密钥不传递给 SDK 客户端，运行时按需获取 |
| **防御纵深** | `defense_in_depth/` | 规则匹配 + 策略轨道 |

---

# Part II: OpenHands 主项目

## 12. OpenHands 架构总览

OpenHands 是一个完整的 AI 软件工程平台。其"代理核心"已抽取为 software-agent-sdk，主项目承担**编排、沙箱、集成、前端**职责。

### 12.1 目录结构

```
OpenHands/
├── openhands/
│   ├── app_server/          # V1 应用服务器（FastAPI）← 活跃代码
│   │   ├── sandbox/         # 沙箱生命周期管理（Docker/进程/远程）
│   │   ├── app_conversation/ # 会话生命周期
│   │   ├── event/           # 事件存储（文件系统/S3/GCS）
│   │   ├── event_callback/  # Webhook 回调
│   │   ├── mcp/             # MCP 路由
│   │   ├── secrets/         # 密钥管理
│   │   └── services/        # DI（JWT, DB, httpx）
│   ├── core/                # V0 配置模型（标记 Legacy-V0）
│   ├── events/              # 事件类型定义（V0/V1 共享）
│   │   ├── action/          # 动作类型
│   │   ├── observation/     # 观察类型
│   │   ├── stream.py        # EventStream 发布/订阅
│   │   └── event_store.py   # 文件持久化
│   ├── integrations/        # SCM 集成（GitHub/GitLab/Bitbucket/Azure DevOps）
│   ├── server/              # V0 Web 服务器（已弃用）
│   ├── storage/             # 存储抽象（文件/S3/GCS/内存）
│   └── utils/               # 共享工具
├── frontend/                # React SPA
├── containers/              # Docker 构建配置
├── enterprise/              # 企业版功能
└── skills/                  # 内置技能
```

---

## 13. V0 Legacy 架构

V0 架构采用紧耦合的控制器→代理→运行时循环（已标记弃用）：

```
OpenHandsConfig → AgentController → CodeActAgent → LLM → Runtime (sandbox)
       ↑               ↑                                      ↓
       |          EventStream ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
       |               |
       └── ConversationMemory (condenser pipeline)
```

**特征：**
- 所有组件在同一进程内
- `AgentController` 拥有主循环
- EventStream 做进程内发布/订阅
- ConversationMemory 做历史压缩

---

## 14. V1 App Server 架构

V1 架构将拓扑从单体变为**客户端-服务器**模型：

```
┌──────────────────────────────────────────────┐
│          V1 App Server (FastAPI)              │
│                                              │
│  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Conversation  │  │   Event Service       │ │
│  │   Service     │  │ (FS/S3/GCS)           │ │
│  └──────┬────────┘  └───────────────────────┘ │
│         │                                     │
│  ┌──────┴────────┐  ┌───────────────────────┐ │
│  │   Sandbox     │  │  Event Callback       │ │
│  │   Service     │  │    Service             │ │
│  └──────┬────────┘  └───────────────────────┘ │
└─────────┼────────────────────────────────────┘
          │  HTTP / Docker API
          ▼
┌──────────────────────────────────────────────┐
│           Sandbox Container                   │
│  ┌──────────────────────────────────────┐    │
│  │  openhands-agent-server (SDK V1)     │    │
│  │  ├── Agent (openhands-sdk)           │    │
│  │  ├── LLM                            │    │
│  │  ├── Tools (openhands-tools)         │    │
│  │  └── Workspace                       │    │
│  └──────────────────────────────────────┘    │
│  + tmux, bash, python, browser, etc.         │
└──────────────────────────────────────────────┘
```

**关键设计：沙箱内运行完整 Agent Server**
- App Server 是纯编排层
- Agent 循环在沙箱内独立执行
- LLM API 密钥通过 `LookupSecret` 机制在运行时从 App Server 获取
- 事件通过 HTTP webhook 回传

---

## 15. EventStream 发布/订阅

V0 的 EventStream 仍存于主仓库（V1 使用 SDK 的事件系统）：

```python
class EventStream(EventStore):
    _subscribers: dict[str, dict[str, Callable]]  # 订阅者回调
    _queue: queue.Queue[Event]                     # 事件队列

    # 特性:
    # - 文件持久化（每事件一个 JSON）
    # - 页缓存（25 事件/页）
    # - 密钥脱敏（持久化前扫描替换）
    # - 每订阅者独立线程 + asyncio 事件循环
```

**V0 事件类层次（更丰富，面向编码任务）：**

```
Event (dataclass)
├── Action
│   ├── CmdRunAction           # Shell 命令
│   ├── IPythonRunCellAction   # Jupyter 执行
│   ├── FileReadAction         # 文件读取
│   ├── FileWriteAction        # 文件写入
│   ├── FileEditAction         # str_replace 编辑
│   ├── BrowseURLAction        # 网页浏览
│   ├── MCPAction              # MCP 调用
│   ├── MessageAction          # 用户/代理消息
│   ├── AgentFinishAction      # 任务完成
│   ├── AgentDelegateAction    # 多代理委派
│   ├── CondensationAction     # 记忆压缩标记
│   └── RecallAction           # 记忆检索
└── Observation
    ├── CmdOutputObservation
    ├── FileReadObservation
    ├── ErrorObservation
    └── ...
```

---

## 16. Sandbox 沙箱系统

### 16.1 服务层次

```
SandboxService (ABC)
├── DockerSandboxService    # 本地 Docker 容器
├── ProcessSandboxService   # 本地进程（无 Docker）
└── RemoteSandboxService    # 远程 API 沙箱
```

### 16.2 沙箱生命周期

```
创建 → 启动（等待健康检查） → 运行中
  │                              │
  │                              ├── 暂停 → 恢复 → 运行中
  │                              │
  │                              └── 删除
  └── 失败 → 错误
```

每个沙箱：
- 获取唯一 `session_api_key`（认证）
- 暴露 `agent-server` URL、`vscode` URL、worker 端口
- 可启动、暂停、恢复、删除
- 健康检查轮询确认就绪

---

## 17. V0 vs V1 对比

| 维度 | V0 (Legacy) | V1 (SDK) |
|------|-------------|----------|
| **Agent 位置** | 进程内（`openhands/agenthub/`） | 沙箱内（`openhands-agent-server`） |
| **控制器** | `AgentController`（同步步进） | Agent Server 自管理循环 |
| **LLM 调用** | 控制器进程直接调用 | 沙箱内，`LookupSecret` 获取 API 密钥 |
| **工具** | 隐式（动作类型映射到运行时） | 显式 `ToolDefinition`（`openhands-tools`） |
| **记忆** | `ConversationMemory` + condenser 管线 | SDK Agent 内建 condenser |
| **通信** | EventStream 进程内发布/订阅 | HTTP REST + Webhook |
| **配置** | `OpenHandsConfig`（TOML/env） | `AppServerConfig` + DI 注入 |
| **多租户** | 单会话 | 多沙箱/用户，分组策略 |
| **事件类型** | dataclass（V0 专用） | Pydantic frozen（SDK 通用） |

---

# Part III: 跨框架对比

## 18. 与 smolagents / OpenAI Agents SDK 对比

| 维度 | OpenHands SDK | smolagents | OpenAI Agents SDK |
|------|--------------|-----------|-------------------|
| **架构模式** | 事件溯源 + Sandbox | 结构化步骤 + ReAct | Agent-as-Config + Runner |
| **记忆模型** | EventLog（文件持久化） | AgentMemory（内存） | Session Protocol |
| **压缩策略** | LLMSummarizingCondenser + Pipeline | summary_mode 双轨 | Compaction Session（API 级） |
| **工具抽象** | ToolDefinition（Pydantic + 注册表） | Tool（dataclass + @tool） | Tool（FunctionTool/MCPTool） |
| **MCP 支持** | FastMCP + MCPToolDefinition | mcpadapt + MCPClient | 原生 MCP 模块 |
| **安全机制** | 多层（Schema + 分析器 + 确认策略 + Hook + 密钥隔离） | 白名单 + AST + 沙箱 | Guardrails（Input/Output/Tool） |
| **Hook/中间件** | Shell 脚本 Hooks（6 种事件） | CallbackRegistry | RunHooks / AgentHooks |
| **技能系统** | AgentSkills 格式 + 渐进披露 + invoke_skill | 无 | Skills Capability + 渐进披露 |
| **Critic/评估** | CriticBase + 迭代精炼 | 无 | 无 |
| **多代理** | DelegateTool + Subagent 注册 | ManagedAgent（工具伪装） | Handoff（特殊工具调用） |
| **持久化** | EventLog（JSON 文件） | 无 | SQLiteSession / Redis |
| **并行执行** | ParallelToolExecutor（资源锁） | ThreadPoolExecutor | 无内建并行 |
| **Prompt 系统** | Jinja2 模板 + 模型专用覆盖 | YAML + Jinja2 | 动态函数 + OpenAI Prompt API |
| **Sandbox** | Docker/进程/远程 + Agent Server 内置 | local/Docker/E2B/Modal/Blaxel/Wasm | 无内建（依赖外部） |
| **代码量** | ~15000+ 行（SDK） | ~2100 行（核心） | ~20000+ 行（核心） |
| **设计理念** | 企业级软件工程 Agent | 极简 ReAct 框架 | 通用 Agent 平台 |

---

**文档维护者**: Deep Agents Community  
**源码版本**: software-agent-sdk 1.19.x / openhands-ai 1.6.x  
**最后审查日期**: 2026-04-29
