# OpenManus Plan 模式源码导读

> **一句话**：Plan 模式不是 Agent 内部开关，而是 `run_flow.py` 把 **PlanningFlow** 套在 Agent 外面——Flow 先让自己的 LLM 调 `PlanningTool` 写出步骤表，再对每一步调用某个 executor 的完整 `BaseAgent.run()`。  
> **对照**：[ARCHITECTURE_DESIGN.md §8](./ARCHITECTURE_DESIGN.md#8-flow-与-plan-设计) · [Part 1 §6](./ARCHITECTURE_PART1.md#6-planningflow--外层编排) · [Part 2 §3](./ARCHITECTURE_PART2.md#3-planningflow-深潜)  
> **图解**：[plan-mode 时序](./diagrams/openmanus-plan-mode-example.sequence.html) · [三本账数据流](./diagrams/openmanus-plan-message-stores.dataflow.html) · [外环工作流](./diagrams/openmanus-plan-mode-loop.workflow.html)  
> **源码**：`OpenManus/run_flow.py` · `app/flow/planning.py` · `app/tool/planning.py` · `app/agent/base.py` · `app/agent/toolcall.py`

读完应能回答：

1. 用户敲下一句 prompt 之后，**哪几次 LLM 调用**发生、各自带什么 messages。
2. **`Memory.messages` 和 `PlanningTool.plans` 是两本账**，规划器的对话甚至不进任何 Memory。
3. 同一个 `Manus()` 实例会跨 plan step **复用**，内层消息会累积——这和若干概览文档里「每 step 新 Memory」的说法不一致，以源码为准。

---

## 目录

- [0. 先建立心智模型](#0-先建立心智模型)
- [1. 入口装配：`run_flow.py`](#1-入口装配run_flowpy)
- [2. 三本账：消息到底住在哪](#2-三本账消息到底住在哪)
- [3. 完整示例：分析 sales.csv 并写报告](#3-完整示例分析-salescsv-并写报告)
  - [3.1 Phase 0 创建计划](#31-phase-0创建计划planner-llm-一次性不进-memory)
  - [3.2 Phase 1 取当前步骤](#32-phase-1取当前步骤并标-in_progress)
  - [3.3 Phase 2 执行 step 0](#33-phase-2执行-step-0manus-读-csv)
  - [3.4 Phase 3 执行 step 1](#34-phase-3执行-step-1dataanalysis-画图)
  - [3.5 Phase 4 执行 step 2](#35-phase-4执行-step-2manus-写报告memory-已有-step-0)
  - [3.6 Phase 5 总结](#36-phase-5finalize-plan)
- [4. 调用链与状态总表](#4-调用链与状态总表)
- [5. 源码级易错点](#5-源码级易错点)
- [6. 对照默认 Manus](#6-对照默认-manus)
- [7. 建议阅读顺序](#7-建议阅读顺序)

---

## 0. 先建立心智模型

OpenManus 的「Plan 模式」走的是 **Plan-and-Execute 外环**，不是 deepagents / deer-flow 那种在同一个 ReAct loop 里 `write_todos` 的交织式 Plan。

```text
外环  PlanningFlow.execute()          ← 拆步、选人、勾完成、写总结
  ├─ Flow.llm.ask_tool(PlanningTool)  ← 只在建计划时用一次
  ├─ while 还有 not_started/in_progress:
  │     executor.run(step_prompt)     ← 内环：完整 ReAct，最多 20 step
  │     mark_step(completed)
  └─ Flow.llm.ask(总结)               ← 再一次，同样不写 Memory
```

两层 step 不要混：

| 名字 | 谁在数 | 一次是什么 | 上限 |
|------|--------|------------|------|
| **plan step** | `PlanningFlow.current_step_index` | 计划表里的一行 | 计划有几步就几步 |
| **agent step** | `BaseAgent.current_step` | 一次 `think()` + 可能的 `act()` | Manus / DataAnalysis 默认 20 |

一个 plan step 里面可以跑十几轮 tool calling。外环只看见 `executor.run()` 返回的那一大段字符串。

---

## 1. 入口装配：`run_flow.py`

```24:35:OpenManus/run_flow.py
        flow = FlowFactory.create_flow(
            flow_type=FlowType.PLANNING,
            agents=agents,
        )
        logger.warning("Processing your request...")

        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                flow.execute(prompt),
                timeout=3600,  # 60 minute timeout for the entire execution
            )
```

装配顺序：

```text
run_flow()
  1. agents = {"manus": Manus()}                         # 注意：不是 Manus.create()
  2. 若 config.runflow.use_data_analysis_agent:
        agents["data_analysis"] = DataAnalysis()
  3. FlowFactory.create_flow(PLANNING, agents)
       → PlanningFlow(agents)
            executor_keys = ["manus", "data_analysis"]
            primary_agent_key = "manus"                  # dict 插入顺序的第一个
            planning_tool = PlanningTool()
            active_plan_id = f"plan_{int(time.time())}"
            llm = LLM()                                  # Flow 自己的规划/总结模型
  4. await flow.execute(prompt)
```

和 `main.py` 的关键差别：

| | `main.py` | `run_flow.py` |
|--|-----------|---------------|
| 创建 Agent | `await Manus.create()`，先连 MCP | `Manus()`，MCP 推迟到第一次 `think()` |
| 谁驱动 | `agent.run(prompt)` | `flow.execute(prompt)` |
| 用户原句去哪 | 直接进 `Manus.memory` | **不进** Memory；只给规划 LLM 看，再改写成 `step_prompt` |

`FlowFactory` 目前只有一种类型：

```9:30:OpenManus/app/flow/flow_factory.py
class FlowType(str, Enum):
    PLANNING = "planning"
...
        flows = {
            FlowType.PLANNING: PlanningFlow,
        }
```

---

## 2. 三本账：消息到底住在哪

Plan 模式同时存在 **三份互不自动同步的状态**。搞清这一点，后面的 message 快照才读得懂。

```text
┌──────────────────────────────────────────────────────────┐
│ A. 规划器瞬时消息（不落盘、不进 Memory）                    │
│    _create_initial_plan / _finalize_plan                   │
│    每次现场拼 [system, user]，调完即丢                      │
└──────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────┐
│ B. PlanningTool.plans[plan_id]  （结构化计划，不是 Message） │
│    {title, steps[], step_statuses[], step_notes[]}         │
│    Flow 用 mark_step / get 读写；executor 只通过 step_prompt │
│    里的「CURRENT PLAN STATUS」间接看见                      │
└──────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────┐
│ C. executor.memory.messages  （真正的对话账）               │
│    Manus 一份、DataAnalysis 一份，实例级、进程内             │
│    同一 executor 跨 plan step **不会 clear()**              │
└──────────────────────────────────────────────────────────┘
```

`system_prompt` 也不在 Memory 里。`LLM.ask_tool()` 每次调用时把 `system_msgs` **临时拼到最前面**：

```684:688:OpenManus/app/llm.py
            if system_msgs:
                system_msgs = self.format_messages(system_msgs, supports_images)
                messages = system_msgs + self.format_messages(messages, supports_images)
            else:
                messages = self.format_messages(messages, supports_images)
```

所以「模型实际看到的 messages」= `[system_prompt] + Memory.messages`。下文快照会分开写 **Memory** 和 **on-the-wire**。

---

## 3. 完整示例：分析 sales.csv 并写报告

约定一次真实可对照的运行：

```text
配置: [runflow] use_data_analysis_agent = true
入口: python run_flow.py
用户: 分析 workspace/sales.csv 并写一份 markdown 报告
plan_id: plan_1710000000          # Flow 构造时用 time.time()
```

两个 executor：

| key | 类 | description（会写进规划 system prompt） | 工具 |
|-----|-----|------------------------------------------|------|
| `manus` | `Manus` | A versatile agent that can solve various tasks... | `python_execute` / `str_replace_editor` / `ask_human` / `terminate` + 懒加载 MCP |
| `data_analysis` | `DataAnalysis` | An analytical agent that utilizes python and data visualization... | `normal_python_execute` / `visualization_prepare` / `data_visualization` / `terminate` |

下面 LLM 回复是 **协议正确的示意**，用来把每一步的 messages 钉死；真实模型措辞会变，字段结构不会。

---

### 3.1 Phase 0：创建计划（planner LLM，一次性，不进 Memory）

`PlanningFlow.execute()` 一进来就走 `_create_initial_plan(input_text)`。

```136:176:OpenManus/app/flow/planning.py
    async def _create_initial_plan(self, request: str) -> None:
        """Create an initial plan based on the request using the flow's LLM and PlanningTool."""
        ...
        response = await self.llm.ask_tool(
            messages=[user_message],
            system_msgs=[system_message],
            tools=[self.planning_tool.to_param()],
            tool_choice=ToolChoice.AUTO,
        )
```

#### 3.1.1 发给规划 LLM 的 on-the-wire messages

这些对象只存在于这一次函数调用的局部变量，**不会** `memory.add_message()`。

```text
system_msgs[0]  role=system
  "You are a planning assistant. Create a concise, actionable plan with clear steps.
   Focus on key milestones rather than detailed sub-steps.
   Optimize for clarity and efficiency.
   Now we have [{name: MANUS, description: ...}, {name: DATA_ANALYSIS, ...}] agents.
   The infomation of them are below: <json>
   When creating steps in the planning tool, please specify the agent names
   using the format '[agent_name]'."

messages[0]     role=user
  "Create a reasonable plan with clear steps to accomplish the task:
   分析 workspace/sales.csv 并写一份 markdown 报告"

tools           [ PlanningTool.to_param() ]     # name = "planning"
tool_choice     "auto"
```

多 executor 时，system 里会拼上 agent 清单。单 `manus` 时这段 **整段不出现**（`len(agents_description) > 1` 才追加）。

#### 3.1.2 规划 LLM 的返回（不写回任何 Memory）

模型按 OpenAI tool calling 返回一条 assistant message，但 Flow **不把它存下来**，只取出 `tool_calls`：

```json
{
  "role": "assistant",
  "content": "I'll create a three-step plan.",
  "tool_calls": [
    {
      "id": "call_plan_1",
      "type": "function",
      "function": {
        "name": "planning",
        "arguments": "{
          \"command\": \"create\",
          \"title\": \"Analyze sales.csv and write a report\",
          \"steps\": [
            \"[MANUS] 读取 sales.csv，确认列名与行数\",
            \"[DATA_ANALYSIS] 可视化销售额趋势并给出结论\",
            \"[MANUS] 把分析结论写成 markdown 报告\"
          ]
        }"
      }
    }
  ]
}
```

#### 3.1.3 Flow 亲手执行 PlanningTool，并强行覆盖 plan_id

```179:198:OpenManus/app/flow/planning.py
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call.function.name == "planning":
                    args = tool_call.function.arguments
                    ...
                    args["plan_id"] = self.active_plan_id
                    result = await self.planning_tool.execute(**args)
                    ...
                    return
```

注意三件源码事实：

1. **没有 tool message 回写**。规划对话在这里结束，模型看不到 `Plan created successfully...`。
2. **`plan_id` 以 Flow 为准**。模型填什么都会被覆盖成 `plan_1710000000`。
3. 若模型没调 `planning`，走 fallback 三步：`Analyze request / Execute task / Verify results`。

#### 3.1.4 账本 B 此刻的样子

`PlanningTool._create_plan()` 写入：

```python
self.plans["plan_1710000000"] = {
    "plan_id": "plan_1710000000",
    "title": "Analyze sales.csv and write a report",
    "steps": [
        "[MANUS] 读取 sales.csv，确认列名与行数",
        "[DATA_ANALYSIS] 可视化销售额趋势并给出结论",
        "[MANUS] 把分析结论写成 markdown 报告",
    ],
    "step_statuses": ["not_started", "not_started", "not_started"],
    "step_notes": ["", "", ""],
}
self._current_plan_id = "plan_1710000000"
```

| 账本 | Phase 0 结束 |
|------|----------------|
| A 规划器 messages | 已丢弃 |
| B `plans[...]` | 3 步全是 `not_started` |
| C `Manus.memory` | `[]` |
| C `DataAnalysis.memory` | `[]` |

---

### 3.2 Phase 1：取当前步骤并标 `in_progress`

外环进入 `while True`：

```111:125:OpenManus/app/flow/planning.py
            result = ""
            while True:
                self.current_step_index, step_info = await self._get_current_step_info()

                if self.current_step_index is None:
                    result += await self._finalize_plan()
                    break

                step_type = step_info.get("type") if step_info else None
                executor = self.get_executor(step_type)
                step_result = await self._execute_step(executor, step_info)
```

`_get_current_step_info()` 线性扫描，取 **第一个** `not_started` 或 `in_progress`（`blocked` 会被永久跳过）：

```text
i=0  status=not_started  → 命中
  step_info = {
      "text": "[MANUS] 读取 sales.csv，确认列名与行数",
      "type": "manus",          # re.search(r"\[([A-Z_]+)\]") → .lower()
  }
  planning_tool.execute(command="mark_step", step_index=0, step_status="in_progress")
  return (0, step_info)
```

`get_executor("manus")`：`step_type in self.agents` → 返回 `agents["manus"]`。

路由规则（脆弱但就是这么写的）：

```77:92:OpenManus/app/flow/planning.py
    def get_executor(self, step_type: Optional[str] = None) -> BaseAgent:
        if step_type and step_type in self.agents:
            return self.agents[step_type]
        for key in self.executor_keys:
            if key in self.agents:
                return self.agents[key]
        return self.primary_agent
```

标签必须是 `[A-Z_]+`。写成 `[Manus]`、`[data_analysis]`、`（MANUS）` 都匹配失败，会落到 `executor_keys[0]`，也就是 `manus`。

账本 B 变为：`step_statuses = ["in_progress", "not_started", "not_started"]`。

---

### 3.3 Phase 2：执行 step 0（Manus 读 CSV）

#### 3.3.1 构造 `step_prompt`（这才是 executor 看到的「用户请求」）

```277:296:OpenManus/app/flow/planning.py
    async def _execute_step(self, executor: BaseAgent, step_info: dict) -> str:
        plan_status = await self._get_plan_text()
        step_text = step_info.get("text", f"Step {self.current_step_index}")

        step_prompt = f"""
        CURRENT PLAN STATUS:
        {plan_status}

        YOUR CURRENT TASK:
        You are now working on step {self.current_step_index}: "{step_text}"

        Please only execute this current step using the appropriate tools. When you're done, provide a summary of what you accomplished.
        """

        step_result = await executor.run(step_prompt)
```

`_get_plan_text()` 调用 `planning_tool.execute(command="get")`，得到带勾选符号的纯文本。用户的原始中文请求 **已经不在这段 prompt 里**——executor 只看见计划状态 + 当前步骤。

示意：

```text
CURRENT PLAN STATUS:
Plan: Analyze sales.csv and write a report (ID: plan_1710000000)
================================================================

Progress: 0/3 steps completed (0.0%)
Status: 0 completed, 1 in progress, 0 blocked, 2 not started

Steps:
0. [→] [MANUS] 读取 sales.csv，确认列名与行数
1. [ ] [DATA_ANALYSIS] 可视化销售额趋势并给出结论
2. [ ] [MANUS] 把分析结论写成 markdown 报告

YOUR CURRENT TASK:
You are now working on step 0: "[MANUS] 读取 sales.csv，确认列名与行数"
Please only execute this current step ...
```

#### 3.3.2 `BaseAgent.run()` 把 step_prompt 写成第一条 user message

```116:132:OpenManus/app/agent/base.py
    async def run(self, request: Optional[str] = None) -> str:
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        if request:
            self.update_memory("user", request)
```

`Manus` 继承 `ToolCallAgent.run()`，后者 `try/finally` 里会 `cleanup()`。`run_flow` 用的是 `Manus()` 而不是 `create()`，所以 `_initialized` 仍是 `False`，第一次 `think()` 才会连 MCP。

**Memory C（Manus）此时：**

```text
[0] user  |  CURRENT PLAN STATUS: ... YOUR CURRENT TASK: step 0 ...
```

`state`: IDLE → RUNNING（`state_context`）。`current_step`: 0。

#### 3.3.3 内环 agent step 1：think

`ReActAgent.step()` = `think()` + 可能的 `act()`。

Manus.think() 若尚未初始化，先 `initialize_mcp_servers()`，可能往 Memory 里塞一条 MCP instruction 的 **system** message，然后调用 `ToolCallAgent.think()`：

```39:43:OpenManus/app/agent/toolcall.py
    async def think(self) -> bool:
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]
```

Manus 的 `next_step_prompt`（`app/prompt/manus.py`）每次 think **都追加一条 user message**，不会去重：

```text
Based on user needs, proactively select the most appropriate tool ...
If you want to stop the interaction at any point, use the `terminate` tool/function call.
```

**Memory C 在 ask_tool 之前：**

```text
[0] user      |  step_prompt（计划状态 + 当前任务）
[1] user      |  NEXT_STEP_PROMPT          ← think() 刚追加
```

**on-the-wire（Manus.llm.ask_tool）：**

```text
[S] system    |  "You are OpenManus, an all-capable AI assistant... The initial directory is: <workspace>"
                ↑ 来自 Manus.system_prompt，不在 Memory 里
[0] user      |  step_prompt
[1] user      |  NEXT_STEP_PROMPT
tools         |  python_execute, str_replace_editor, ask_human, terminate, (+ MCP)
tool_choice   |  auto
```

模型返回（示意）：调用 `python_execute` 看文件。

think() 把 assistant（带 `tool_calls`）写入 Memory，返回 `True`。

**Memory C 在 think 之后：**

```text
[0] user       |  step_prompt
[1] user       |  NEXT_STEP_PROMPT
[2] assistant  |  content="先看一下 CSV 结构。"
                 tool_calls=[{id:"call_py1", name:"python_execute",
                              arguments:"{\"code\": \"import pathlib; p=pathlib.Path('workspace/sales.csv'); print(p.read_text()[:500])\"}"}]
```

#### 3.3.4 内环 agent step 1：act

```131:172:OpenManus/app/agent/toolcall.py
    async def act(self) -> str:
        ...
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            ...
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=command.id,
                name=command.function.name,
            )
            self.memory.add_message(tool_msg)
```

observation 统一包一层：

```text
Observed output of cmd `python_execute` executed:
date,product,amount
2024-01-01,Widget,120
...
```

若这是 `terminate`，`_handle_special_tool` 会把 `state = FINISHED`。这里还不是。

**Memory C 在 act 之后：**

```text
[0] user       |  step_prompt
[1] user       |  NEXT_STEP_PROMPT
[2] assistant  |  python_execute(...)
[3] tool       |  name=python_execute  tool_call_id=call_py1
                 content="Observed output of cmd `python_execute` executed:\n..."
```

`run()` 把这一轮结果记成 `"Step 1: Observed output of cmd ..."`. `current_step = 1`。循环继续，因为 `state` 仍是 RUNNING。

#### 3.3.5 内环 agent step 2：think + terminate

think() **再次**追加 NEXT_STEP_PROMPT：

```text
[0] user       |  step_prompt
[1] user       |  NEXT_STEP_PROMPT          ← 第 1 轮留下的
[2] assistant  |  python_execute
[3] tool       |  csv 预览
[4] user       |  NEXT_STEP_PROMPT          ← 第 2 轮又来一条
```

on-the-wire = `[system_prompt] + 上面 5 条`。

模型决定结束，调用 `terminate`：

```text
[5] assistant  |  content="列名 date/product/amount，约 N 行。本步完成。"
                 tool_calls=[{id:"call_term1", name:"terminate", arguments:"{\"status\":\"success\"}"}]
```

act() → `Terminate.execute("success")` → `"The interaction has been completed with status: success"` → `_handle_special_tool` → `state = FINISHED`。

```text
[6] tool       |  name=terminate  tool_call_id=call_term1
                 content="Observed output of cmd `terminate` executed:\nThe interaction has been completed with status: success"
```

while 条件 `self.state != FINISHED` 失败，跳出内环。

#### 3.3.6 `state_context` 把 FINISHED 改回 IDLE（外环几乎看不见 FINISHED）

```58:82:OpenManus/app/agent/base.py
    async def state_context(self, new_state: AgentState):
        previous_state = self.state          # IDLE
        self.state = new_state               # RUNNING
        try:
            yield                            # 内环里 terminate 曾把 state 设为 FINISHED
        except Exception as e:
            self.state = AgentState.ERROR
            raise e
        finally:
            self.state = previous_state      # 回到 IDLE
```

因此 `executor.run()` **返回之后** `executor.state` 几乎总是 `IDLE`。PlanningFlow 里这段基本是死代码：

```127:129:OpenManus/app/flow/planning.py
                if hasattr(executor, "state") and executor.state == AgentState.FINISHED:
                    break
```

同时 `ToolCallAgent.run()` 的 `finally: await self.cleanup()` 会走 `Manus.cleanup()`。因为这次 think 已经把 `_initialized` 设为 True，**MCP 会在每个 plan step 结束时被断开**。下一个 plan step 的第一次 think 会再连一次。

`current_step` **不会**因为 terminate 清零（只有撞上 `max_steps` 才置 0）。step 0 用了 2 个 agent step，所以 Manus.current_step 停在 **2**。

#### 3.3.7 外环标记 completed

无论内层是 terminate 还是撞满 20 步，只要 `run()` 没抛异常，Flow 都 `_mark_step_completed()`。

账本 B：`["completed", "not_started", "not_started"]`。

`execute()` 把内环返回的 `"Step 1: ...\nStep 2: ..."` 拼进 `result`，继续 while。

---

### 3.4 Phase 3：执行 step 1（DataAnalysis 画图）

`_get_current_step_info()` 命中 i=1，`type=data_analysis`，`get_executor` 返回 **另一个实例** `agents["data_analysis"]`。

它有自己的 Memory，从空开始。`max_steps=20`，`current_step=0`，`system_prompt` 是可视化专用的。

**DataAnalysis Memory 从空到结束（压缩示意）：**

```text
# run() 写入
[0] user       |  CURRENT PLAN STATUS:（此时 step0 已是 [✓]，step1 是 [→]）
                   YOUR CURRENT TASK: step 1 "[DATA_ANALYSIS] 可视化..."

# agent step 1 think+act
[1] user       |  DataAnalysis NEXT_STEP_PROMPT   # 「Each step ... ONLY ONE」
[2] assistant  |  tool_calls=[visualization_prepare / python_execute]
[3] tool       |  数据准备结果

# agent step 2 think+act
[4] user       |  NEXT_STEP_PROMPT                # 又一条
[5] assistant  |  tool_calls=[data_visualization]
[6] tool       |  图表路径 / 结论摘要

# agent step 3 terminate
[7] user       |  NEXT_STEP_PROMPT
[8] assistant  |  tool_calls=[terminate status=success]
[9] tool       |  terminate observation
```

Manus 的 Memory **原样保留**，DataAnalysis 碰不到它。计划状态是通过新的 `step_prompt` 注入的，不是通过共享对话。

账本 B：`["completed", "completed", "not_started"]`。

---

### 3.5 Phase 4：执行 step 2（Manus 写报告，Memory 已有 step 0）

这是整份导读最容易读错的一步。

`get_executor("manus")` 返回 **同一个** `Manus()` 实例。源码没有任何 `memory.clear()`，也没有 new 一个 Agent。

**Manus.memory 在 step 2 的 `run()` 开始时已经有 step 0 的 7 条消息。** `update_memory("user", step_prompt)` 只是再 append。

```text
—— 来自 plan step 0（还在）——
[0] user       |  step_prompt #0（读 CSV）
[1] user       |  NEXT_STEP_PROMPT
[2] assistant  |  python_execute
[3] tool       |  csv 预览
[4] user       |  NEXT_STEP_PROMPT
[5] assistant  |  terminate
[6] tool       |  terminate observation

—— plan step 2 新写入 ——
[7] user       |  step_prompt #2（写报告；CURRENT PLAN STATUS 里 0/1 已是 [✓]，2 是 [→]）
```

然后 think 再追加 NEXT_STEP_PROMPT，模型在 **含有上一步 CSV 观察** 的上下文里写 `report.md`。这是实例复用带来的「意外跨步记忆」，不是 Flow 设计出来的摘要注入。

同时 `current_step` 从 2 接着往上加，还剩 `20 - 2 = 18` 个内环配额，不是重新 20。

示意继续：

```text
[8]  user       |  NEXT_STEP_PROMPT
[9]  assistant  |  str_replace_editor(command=create, path=.../report.md, file_text=...)
[10] tool       |  写入成功
[11] user       |  NEXT_STEP_PROMPT
[12] assistant  |  terminate
[13] tool       |  terminate observation
```

账本 B：`["completed", "completed", "completed"]`。

下一轮 `_get_current_step_info()` 扫完全表，没有 active status，返回 `(None, None)` → 离开 while，进入 finalize。

---

### 3.6 Phase 5：finalize plan

```406:424:OpenManus/app/flow/planning.py
    async def _finalize_plan(self) -> str:
        plan_text = await self._get_plan_text()
        try:
            system_message = Message.system_message(
                "You are a planning assistant. Your task is to summarize the completed plan."
            )
            user_message = Message.user_message(
                f"The plan has been completed. Here is the final plan status:\n\n{plan_text}\n\nPlease provide a summary of what was accomplished and any final thoughts."
            )
            response = await self.llm.ask(
                messages=[user_message], system_msgs=[system_message]
            )
            return f"Plan completed:\n\n{response}"
```

又是账本 A：现场拼两条消息，调 `Flow.llm.ask()`（**纯文本，不带工具**），结果不写进任何 executor Memory。

规划 LLM **看不到** Manus / DataAnalysis 的 tool observation，只看得到 `PlanningTool` 格式化出来的步骤表（标题、勾选、notes——默认 notes 全空）。所以总结经常很空，只能复述「三步都 completed」。

失败时 fallback：`primary_agent.run(summary_prompt)`——这会 **再次**往已经很长的 Manus Memory 里追加一条 user message，再跑一整轮 ReAct。

最终 `flow.execute()` 返回的字符串是：

```text
<step0 的 "Step 1: ...\nStep 2: ...">
<step1 的内环结果>
<step2 的内环结果>
Plan completed:

<规划 LLM 的一段总结>
```

用户在 CLI 上看到的是这整坨，不是某一次 Memory。

---

## 4. 调用链与状态总表

### 4.1 端到端调用链

```text
run_flow.py
  FlowFactory.create_flow(PLANNING)
  PlanningFlow.execute(prompt)
    ├─ _create_initial_plan
    │     Flow.llm.ask_tool(messages=[user], system_msgs=[system], tools=[planning])
    │     PlanningTool.execute(command="create", plan_id=强制覆盖)
    │     或 fallback 三步计划
    ├─ while True
    │     _get_current_step_info
    │       扫描第一个 not_started/in_progress
    │       解析 [AGENT_NAME] → step_info["type"]
    │       PlanningTool.execute(mark_step, in_progress)
    │     get_executor(type)
    │     _execute_step
    │       _get_plan_text() → PlanningTool.get
    │       executor.run(step_prompt)
    │         BaseAgent.update_memory("user", step_prompt)
    │         while current_step < max_steps and state != FINISHED:
    │           ReActAgent.step()
    │             ToolCallAgent.think()
    │               Memory += user(NEXT_STEP_PROMPT)
    │               llm.ask_tool(system_prompt + Memory, tools)
    │               Memory += assistant(/tool_calls)
    │             ToolCallAgent.act()
    │               ToolCollection.execute
    │               Memory += tool(observation)
    │               terminate → state=FINISHED
    │         state_context.finally → state=IDLE
    │         ToolCallAgent.cleanup()  → Manus 断开 MCP
    │       _mark_step_completed()
    │     （FINISHED 检查几乎永不成立）
    └─ _finalize_plan
          Flow.llm.ask(system + plan_text)
```

### 4.2 三本账随时间变化

| 时刻 | 账本 A 规划 messages | 账本 B statuses | Manus Memory 条数（示意） | DataAnalysis Memory | Manus.current_step | Manus.state（run 返回后） |
|------|----------------------|-----------------|---------------------------|---------------------|--------------------|---------------------------|
| 进程启动 | 无 | 无 plan | 0 | 0 | 0 | IDLE |
| create 成功 | 已丢弃 | `[ ] [ ] [ ]` | 0 | 0 | 0 | IDLE |
| 取 step 0 | 无 | `[→] [ ] [ ]` | 0 | 0 | 0 | IDLE |
| step 0 内环中 | 无 | 同上 | 2 → 4 → 7 | 0 | 1 → 2 | RUNNING / FINISHED |
| step 0 结束 | 无 | `[✓] [ ] [ ]` | 7 | 0 | **2（不清零）** | **IDLE** |
| step 1 结束 | 无 | `[✓] [✓] [ ]` | 7（不动） | ~10 | 2 | IDLE |
| step 2 结束 | 无 | `[✓] [✓] [✓]` | 7 + 新 step_prompt + 内环 | ~10 | 2 + n | IDLE |
| finalize | 又一次现场拼，再丢 | 不变 | 不变（除非 fallback `agent.run`） | 不变 | 不变 | IDLE |

### 4.3 一次内环 think/act 的 Memory 增量

对任意 executor，每一轮 agent step 固定追加：

```text
+ user(next_step_prompt)                          # think 开头，必有
+ assistant(content?, tool_calls?)                # think 成功
+ tool(observation) × N                           # act，每个 tool_call 一条
+ user(image...)                                  # 仅当 ToolResult 带 base64_image
```

`system_prompt` 永不进这条列表。MCP server instructions 是例外：`Manus.connect_mcp_server()` 会 `add_message(system_message(...))`，出现在 Memory 头部附近。

---

## 5. 源码级易错点

这些都是对照源码得到的行为，若干概览文档为了好记做过简化。

### 5.1 「每 step 新 Memory」在实现里不成立

`run_flow.py` 只 `Manus()` 一次。`_execute_step` 反复 `executor.run()`。`Memory.clear()` 从未被调用。

结果：

- 同一 executor 的后一步能看见前一步的 tool observation。
- 不同 executor（Manus vs DataAnalysis）互相看不见，只能靠 `step_prompt` 里的计划文本。
- `next_step_prompt` 作为 user message 会在 Memory 里重复出现，步数一多就会占掉 `max_messages=100` 的配额。

若要「每 plan step 干净上下文」，需要在 `_execute_step` 前自行 `executor.memory.clear()` 并重置 `current_step`。当前代码没做。

### 5.2 `executor.state == FINISHED` 几乎砍不掉后续步骤

`terminate` 确实把 state 设成 FINISHED，但 `state_context.finally` 会恢复为进入 `run()` 前的 IDLE。外环那句 `break` 基本走不到。三步计划会跑完，即使某步模型调用了 terminate。

### 5.3 `current_step` 跨 plan step 累加

只有 `current_step >= max_steps` 时才复位。前面的 plan step 把配额用掉，后面的 Manus 步骤可用内环次数变少。两个 plan step 若都撞满 20，第二次 `run()` 会立刻因为 `current_step < max_steps` 失败而「No steps executed」，但 Flow 仍会标 completed。

### 5.4 规划对话没有 tool 回写，总结看不到执行细节

`_create_initial_plan` 执行完 `PlanningTool` 就 `return`，没有第二轮 LLM。`_finalize_plan` 只喂计划勾选表。想让总结提到「销售额环比 -12%」，必须让 executor 把结论写进 `step_notes`（当前 Flow **从不**调 `mark_step(..., step_notes=...)`），或改 finalize 去读 executor Memory。

### 5.5 原始用户 prompt 进不了 executor

用户原句只出现在规划 LLM 的那条 user message 里。executor 看见的是 LLM 改写后的步骤文本。若规划模型把约束丢掉（路径、格式、语言），执行器无法从 Memory 里找回来。

### 5.6 失败会原地重试，成功则过于乐观

| `executor.run()` | Flow 行为 |
|------------------|-----------|
| 抛异常 | 不 mark completed；while 下一圈还会取到 **同一** `in_progress` 步，等于无限重试 |
| 正常返回（含撞 max_steps） | 一律 mark completed |

没有 blocked 处理、没有人工确认、没有 checkpoint。

### 5.7 `PlanningTool.plans` 是可变类默认值

```69:70:OpenManus/app/tool/planning.py
    plans: dict = {}  # Dictionary to store plans by plan_id
    _current_plan_id: Optional[str] = None  # Track the current active plan
```

Pydantic v1 对 `dict = {}` 不会做 `default_factory`。多个 `PlanningTool()` 可能共享同一份 `plans`。单进程单 Flow 时不明显；测试或重复建 Flow 时会串 plan。

### 5.8 每步结束断开 MCP

`ToolCallAgent.run()` 的 `finally: cleanup()` → `Manus.cleanup()` 在 `_initialized` 为 True 时 `disconnect_mcp_server()`。Plan 模式每个 Manus plan step 都会拆掉 MCP，下一步 `think()` 再连。这和 `main.py`「整个 `run()` 只用一次 cleanup」不同。

---

## 6. 对照默认 Manus

| | `main.py` Manus | `run_flow.py` PlanningFlow |
|--|-----------------|----------------------------|
| 用户原句 | 第一条 Memory user message | 只给规划 LLM；executor 看 step_prompt |
| LLM 实例 | 一个 `Manus.llm` | `Flow.llm`（规划/总结）+ 各 executor.llm |
| 工具面 | Manus 工具 + MCP | 规划阶段只有 `planning`；执行阶段是 executor 自己的工具（**没有** PlanningTool） |
| 计划结构 | 无 | `PlanningTool.plans` |
| 多 Agent | 无 | `[AGENT]` 文本路由 |
| 结束 | terminate 或 max_steps | 计划扫完 + finalize；内层 terminate 不停止外环 |
| MCP | `create()` 连一次，最后 cleanup | 每个 Manus plan step 连/断一次 |

规划阶段的模型 **不能** 调 `python_execute`。执行阶段的 Manus **不能** 调 `planning` 去改步骤表——`PlanningTool` 不在它的 `available_tools` 里。计划和执行是切断的。

---

## 7. 建议阅读顺序

按一次运行的时间顺序读，而不是按包名：

```text
1. run_flow.py                         装配 agents / FlowFactory
2. app/flow/base.py                    agents dict 与 primary_agent
3. app/flow/planning.py
     execute → _create_initial_plan    账本 A + 账本 B 诞生
     _get_current_step_info            扫描 + [AGENT] 路由
     _execute_step                     step_prompt 的唯一来源
     _finalize_plan                    总结也是账本 A
4. app/tool/planning.py                create / mark_step / get / _format_plan
5. app/agent/base.py                   run() / state_context / update_memory
6. app/agent/toolcall.py               think 追加 NEXT_STEP_PROMPT、act 写 tool message
7. app/schema.py                       Message / Memory / AgentState
8. app/llm.py  ask_tool / format_messages   system 临时前置
```

对照本页第 3 节，把 `sales.csv` 例子的每一条 message 在对应文件里找写入点，Plan 模式就算读通了。
