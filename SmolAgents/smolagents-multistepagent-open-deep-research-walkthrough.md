# MultiStepAgent 执行流程深度分析 + `open_deep_research/custom_model.py` 推演

本文基于 `smolagents/src/smolagents/agents.py` 中 **`MultiStepAgent`** 的实现，并结合 **`smolagents/examples/open_deep_research/custom_model.py`** 中的 **Manager `CodeAgent` + 子 `ToolCallingAgent`（`search_agent`）** 配置，用一条具体研究问题推演 **调用栈、记忆（memory）与 LLM 的联动、各组件数据如何变化**。

---

## 一、`MultiStepAgent` 执行模型（源码级）

### 1.1 职责边界

- **`MultiStepAgent`**：实现 **ReAct 外环**——**`run` → `_run_stream`**，负责 **记忆**、**可选规划**、**行动步调度**、**异常分类**、**最大步数兜底**、**子代理注册**、**回调/监控**。
- **子类**（`CodeAgent` / `ToolCallingAgent`）只实现 **`initialize_system_prompt()`** 与 **`_step_stream(action_step)`**：即 **「这一轮如何调 LLM、如何解析输出、如何执行」**。

### 1.2 `run()`：入口与「记事本」初始化

```text
run(task, stream=False, reset=True, images=None, additional_args=None, max_steps=None)
```

| 顺序 | 代码行为 | 数据变化 |
|------|----------|----------|
| 1 | `self.task = task`；若有 `additional_args`：`state.update` + 任务字符串追加变量说明 | `self.state`、`self.task` |
| 2 | `memory.system_prompt = SystemPromptStep(system_prompt=self.system_prompt)` | `system_prompt` property → 子类 `initialize_system_prompt()`，写入 **系统人设** |
| 3 | `reset` 时 `memory.reset()`、`monitor.reset()` | `memory.steps` 清空（仅保留后续再写的 system 步对象在逻辑上由 2 覆盖） |
| 4 | `memory.steps.append(TaskStep(task=..., task_images=...))` | 记事本第一条业务记录：**用户任务** |
| 5 | **仅 `CodeAgent`**：`python_executor.send_variables(state)`、`send_tools({**tools, **managed_agents})` | 沙箱内可见 **变量** 与 **可调用对象**（含 `search_agent`） |
| 6 | 非流式：`list(_run_stream(...))`；断言最后为 `FinalAnswerStep` | 得到最终 `output` |

### 1.3 `_run_stream()`：外环状态机

初始化 **`step_number = 1`**，**`returned_final_answer = False`**。

**每次循环**（条件：`not returned_final_answer and step_number <= max_steps`）：

1. **可选规划**  
   - 条件：`planning_interval is not None` 且（`step_number == 1` 或 `(step_number - 1) % planning_interval == 0`）。  
   - 调用 **`_generate_planning_step(task, is_first_step=len(memory.steps)==1, step=step_number)`**。  
   - 产出 **`PlanningStep`** → **`memory.steps.append(planning_step)`**。  
   - **LLM**：`generate` / `generate_stream`，**无 tools**，`stop=<end_plan>`。

2. **行动步**  
   - 新建 **`ActionStep(step_number=...)`**。  
   - **`for output in _step_stream(action_step): yield ...`**  
   - 若出现 **`ActionOutput(is_final_answer=True)`**：校验 **`final_answer_checks`**，**`returned_final_answer = True`**。  
   - **`finally`**：**`_finalize_step`**（补 timing、触发 callbacks）、**`memory.steps.append(action_step)`**、**`yield action_step`**、**`step_number += 1`**。  
   - **`AgentGenerationError`**：直接抛出；其它 **`AgentError`**：写入 **`action_step.error`**，循环继续。

3. **退出 while 后**  
   - 若仍未 **`final_answer`** 且步数用尽：**`_handle_max_steps_reached`** → **`provide_final_answer`**（又一次 **无 tools** 的 LLM）。  
   - **`FinalAnswerStep(output)`** → yield。

### 1.4 `write_memory_to_messages()`：记忆 → LLM 输入

```python
messages = memory.system_prompt.to_messages(summary_mode)
for step in memory.steps:
    messages.extend(step.to_messages(summary_mode))
```

这是 **所有「行动步」里拼 LLM 上下文** 的统一来源（规划步另有一套独立消息，见 `_generate_planning_step`）。

---

## 二、`custom_model.py` 中的组件映射

| 组件 | 类型 | 关键参数 | 作用 |
|------|------|----------|------|
| **`model`** | `LiteLLMModel` | `model_id`、`api_base`、`api_key`、`custom_role_conversions` | **主、子代理共用**同一模型实例 |
| **`text_webbrowser_agent`** | `ToolCallingAgent` | `name="search_agent"`，`planning_interval=4`，`max_steps=20`，`tools=WEB_TOOLS`，`provide_run_summary=True` | 负责搜索/浏览；被注册为 **managed agent** |
| **`manager_agent`** | `CodeAgent` | `planning_interval=4`，`max_steps=12`，`tools=[visualizer, TextInspectorTool]`，`managed_agents=[search_agent]`，`additional_authorized_imports=["*"]` | 写代码协调研究；代码里可调用 **`search_agent(...)`** |

**主代理 `CodeAgent` 的 `python_executor`** 在 **`run()`** 时注入：

```text
send_tools({**manager.tools, **manager.managed_agents})
```

因此生成代码中 **`search_agent(task="...", additional_args=...)`** 等价于调用子代理的 **`__call__`**。

**注意**：子代理 **`search_agent`** 自己也是 **`MultiStepAgent`**，被父级调用时走 **`__call__` → run(full_task)**，拥有 **独立的 `AgentMemory`**，与 **manager 的 memory 完全分离**。

---

## 三、推演场景：`agent.run("广州和上海，哪个城市的人口更多")`

以下按时间顺序说明 **manager 侧**发生了什么；当代码调用 **`search_agent`** 时插入 **子代理侧**流程。

### 阶段 A — `create_agent()`（无 LLM）

- 构造 **`LiteLLMModel`**、**`search_agent`**、**`manager_agent`**。  
- **`_setup_managed_agents`**：给 **`search_agent`** 写上 **`inputs`（task + additional_args）**、**`output_type="string"`**，以便若用 **ToolCalling** 模式暴露（本例 manager 是 CodeAgent，主路径是 **代码里调用**）。  
- **`manager.memory`** 初始仅有 **`SystemPromptStep` 占位**（构造时传入 `system_prompt` 字符串；**`run` 时会替换**）。

### 阶段 B — `manager.run(question)` 开始

1. **`self.task`** = 人口对比问题（字符串）。  
2. **`memory.system_prompt`** = 新 **`SystemPromptStep`**（**CodeAgent** 的 `code_agent.yaml` 展开：工具列表、`authorized_imports`、代码块标签等）。  
3. **`memory.reset()`** → **`steps = []`**。  
4. **`memory.steps.append(TaskStep(task=...))`**  
   - 此时 **`memory.steps`**：`[TaskStep]`。

5. **`python_executor.send_variables(self.state)`**（通常 `{}`）、**`send_tools({**tools, **managed_agents})`**  
   - 沙箱内可调：**`visualizer`**、**`inspect_file_as_text`**（`TextInspectorTool` 名依实现而定）、**`final_answer`**、**`search_agent`**（**callable**）。

### 阶段 C — `_run_stream`：第 1 轮（`step_number == 1`）

**C1. 规划（`planning_interval=4`，且 `step_number==1`）**

- **`is_first_step`** = `len(memory.steps)==1` → **True**（只有 `TaskStep`）。  
- **消息**：单条 **user**，内容为 **`initial_plan` 模板**（注入 `task`、`tools`、`managed_agents`）。  
- **LLM#M-P1**：**无 tools**，`stop=<end_plan>`。  
- **结果**：**`PlanningStep`** 写入 **`plan`**（事实梳理 + 步骤草案）。  
- **`memory.steps`**：`[TaskStep, PlanningStep]`。

**C2. 行动步 1 — `CodeAgent._step_stream`**

- **`write_memory_to_messages()`** ≈ **system（Code 人设）** + **TaskStep（New task…）** + **PlanningStep（plan 文本 + “Now proceed…”）**。  
- **LLM#M-A1**：**无 `tools_to_call_from`**（CodeAgent），带 **stop**（含代码闭合标签等）。  
- 模型输出 **Thought + 代码块** → 解析 → **`python_executor(code)`**。  
- **典型代码逻辑**：调用 **`search_agent(task="请检索并对比广州与上海常住人口或最新人口数据…", additional_args=None)`**。

**C3. 进入子代理：`search_agent.__call__(...)`**

- **`full_task`** = **`managed_agent.task` 模板**（经理包装 + 用户子任务）。  
- **`search_agent.run(full_task, ...)`** —— **子代理自己的 `run`**。

**子代理 `search_agent` 内部（独立 memory）**

- **`search_agent.memory`**：**新的 `SystemPromptStep`（toolcalling 模板）** + **`TaskStep(full_task)`**。  
- **`ToolCallingAgent` 无 `python_executor`**（不执行 `send_tools` 那段）。  
- **`_run_stream`**：  
  - **子 step_number=1**：同样 **`planning_interval=4`** → **LLM#S-P1**（子规划）。  
  - **子行动步**：**`write_memory_to_messages()`** → **LLM#S-Ax**，**`tools_to_call_from` = 子 tools**（`google_search`、`visit_page` 等），**非** manager 的工具。  
  - 多轮 **Action/Observation** 直至 **`final_answer` 工具** 或 **max_steps**。  
- **`provide_run_summary=True`**：**`__call__` 返回** 的字符串 = **report 模板** + 可选 **子记忆摘要**。  
- 返回到 **manager 的 `execute`**：该字符串进入 **manager 当前 `ActionStep.observations`**（若 manager 走 Code 路径，则是 **代码执行打印/返回合并进 observation** 的逻辑，见 `CodeAgent._step_stream` 里对 executor 输出的拼接）。

**C4. 结束 manager 行动步 1**

- **`memory.steps.append(manager ActionStep 1)`** —— 内含 **model_output（代码/思考）**、**code_action**、**observations（含 search_agent 的长报告）** 等。  
- **`step_number`** → 2。

### 阶段 D — 后续 manager 轮次（示意）

- **`step_number` 2,3,4**：**不满足** `(step_number-1) % 4 == 0` 且 **非第一步** → **不跑规划**。  
- 每轮：**`write_memory_to_messages()`** 已包含 **此前所有 ActionStep** → LLM 能看到 **search 报告**，再生成代码（例如 **`visualizer`** 画图、**`inspect_file_as_text`**、或再次 **`search_agent`**）。  
- **`step_number == 5`**：**(5-1) % 4 == 0** → **再次 `PlanningStep`（更新计划）** —— 使用 **`summary_mode=True` 的 memory 片段** + **update_plan_*** 模板。

### 阶段 E — 结束

- 某轮代码执行 **`final_answer(...)`** → **`ActionOutput(is_final_answer=True)`** → **`FinalAnswerStep`** → **`run` 返回** 最终答案字符串。  
- 若 **12 步内未 `final_answer`**：**`provide_final_answer`** 兜底 LLM。

---

## 四、数据变化小结表（经理 vs 子代理）

| 数据 | Manager `CodeAgent` | 子 `search_agent` `ToolCallingAgent` |
|------|---------------------|--------------------------------------|
| **`AgentMemory.steps`** | Task、Planning、Action… **不含**子内部步骤 | 仅 **子任务** 相关的 Task、Planning、Action |
| **LLM `tools` 参数** | 行动步通常 **不传 tools** | 每步行动 **传 WEB_TOOLS 的 schema** |
| **执行动作** | **`python_executor`** 跑代码 | **`process_tool_calls` → execute_tool_call`** |
| **与父交互** | 代码里 **`search_agent(...)`** 的返回值 → 进 **当前步 observation** | **`__call__` → report 字符串** |

---

## 五、`custom_model.py` 中与调试相关的额外行为

若设置 **`DEBUG_PRINT_PROMPT=true`**（默认），脚本注册 **LiteLLM `CustomLogger`**，在 **每次 HTTP 调用前后**打印 **messages 条数、内容、tool 参数**等。这发生在 **`LiteLLMModel.generate` / `generate_stream`** 内部，**不经过** `MultiStepAgent` 额外分支——便于对照 **`write_memory_to_messages`** 产出的逻辑与 **实际发往网关的 payload**（经 `get_clean_message_list` 角色转换后）。

---

## 六、延伸阅读（仓库内文档）

- **Memory / Step / LLM 联动导读**：`examples/smolagents-architecture-analysis.md` **§2.0**  
- **函数级 + LLM 清单**：同文档 **§2.8**  
- **子代理 demo**：`examples/smolagents_managed_agent_demo.py`（若存在）

---

*文档随 `agents.py` 与 `custom_model.py` 结构编写；若你本地修改了 `planning_interval` / `max_steps`，仅时间线上规划次数与步数上限会变，控制流不变。*
