# MetaGPT：ReAct 与 `_think` / `_act`，以及 WritePRD 模型

> **本篇不是 `schema.Plan` / `Plan.append_task` 专题**（那是默认 MGX 的待办表，见 [PLAN_MODE.md](./PLAN_MODE.md)）。  
> 本篇讲：**经典 Role 的 think/act 分工**、**RoleZero 命令环**、**WritePRD 是否嵌套 ReAct**。

> **源码**: [`MetaGPT/metagpt/`](../../MetaGPT/metagpt/)  
> **关联**: [ARCHITECTURE.md](./ARCHITECTURE.md) · [PLAN_MODE.md](./PLAN_MODE.md) · [ROLE_PROMPTS_ZH.md](./ROLE_PROMPTS_ZH.md) · [TEAMLEADER_E2E_SOFTWARE_COMPANY.md](./TEAMLEADER_E2E_SOFTWARE_COMPANY.md)

---

## 1. 标准 ReAct 与 MetaGPT 的映射

| ReAct 段 | 含义 |
|----------|------|
| **Thought** | 根据历史决定「下一步干什么」 |
| **Action** | 在环境里执行一步 |
| **Observation** | 结果回到上下文，进入下一轮 Thought |

MetaGPT：**`_think` ≈ Thought（或决策子步）**，**`_act` ≈ Action**；**Observation** 主要靠 `memory` 追加（工具输出、Action 结果、`observe` 收到的新消息）。

---

## 2. 经典 `react_mode=REACT`（多个 Action）

| ReAct | MetaGPT | 是否 LLM | 作用 |
|--------|---------|----------|------|
| Thought | `_think()` | **是** | `aask` + `STATE_TEMPLATE` → 输出 **状态编号** `0/1/…/-1`，选择 **第几个 Action** |
| Action | `_act()` → `todo.run(history)` | **通常在 Action 内再调** | `WritePRD.run` 等里的 `ActionNode.fill` / `aask` |
| Observation | `memory` + `publish_message` | — | 文本、路径、`instruct_content` |

**两层 LLM**：

1. **路由 LLM**（think）：选 Action 列表中的哪一项。  
2. **执行 LLM**（act → `Action.run`）：完成该步业务生成。

**不是**「think 里就把 PRD 写完」；think 只选步。

---

## 3. `BY_ORDER` 与 PM 规则 `_think`

| ReAct | MetaGPT | LLM |
|--------|---------|-----|
| Thought | `_think()`：`state++` 或 PM 规则（git 有无 → 0/1） | **否** |
| Action | `Action.run` | **是**（业务在 Action 内） |

---

## 4. RoleZero（默认 CLI）

| ReAct | RoleZero | LLM |
|--------|----------|-----|
| Thought | `_think()` → `command_rsp` | **是**（`llm_cached_aask`：memory + plan + 工具 schema） |
| Action | `parse_commands` → `_run_commands` | **执行侧通常不再写长文** |
| Observation | `UserMessage(outputs, cause_by=RunCommand)`；循环内可再 `_observe` | — |

与经典 REACT 对比：

| | 经典 REACT `_think` | RoleZero `_think` |
|--|---------------------|-------------------|
| 输出 | Action **下标** | **命令 JSON / 工具调用文本** |
| `_act` | `Action.run`（内层业务 LLM） | `tool_execution_map` |
| 粒度 | 一步 = 一个 Action 类 | 一步可含多个 Editor/Terminal 命令 |

`_quick_think`：简单问答短路，**不是**完整 ReAct 环。

---

## 5. 对照图

```text
经典 REACT (多 Action)
  Thought: LLM 选 action#i
  Action:  Action[i].run() → 业务 LLM
  Obs:     memory / 消息总线

经典 BY_ORDER
  Thought: 无 LLM（state++）
  Action:  Action.run() → 业务 LLM

RoleZero
  Thought: LLM → command_rsp
  Action:  tool_execution_map
  Obs:     UserMessage(tool outputs)
```

---

## 6. WritePRD：有没有「工具」？是不是 ReAct？

### 6.1 结论

| 问题 | 答案 |
|------|------|
| 调 LLM 时有没有 RoleZero 那种 **Tool**？ | **没有**。不走 `tool_execution_map`，不调用 `Editor.write` 等。 |
| 怎么改文件？ | **`ProjectRepo` + 普通 Python 写盘**（`repo.docs.save`、`awrite` 等）。 |
| WritePRD 是不是一个 ReAct Agent？ | **不是**。它是 **单次 Action 内的多段 LLM + 确定性代码**，**没有** `_think`/`_act` 内层循环。 |

### 6.2 执行路径（`WritePRD.run(with_messages=...)`）

```text
加载 requirement / 历史 PRD 路径（instruct_content）
  → 可选：WP_ISSUE_TYPE_NODE.fill（是否 BUG）— 小 LLM
  → 分支：
       bugfix → 写 BUGFIX 文件，cause_by=FixBug
       相关 PRD → REFINED_PRD_NODE.fill — LLM
       新需求 → WRITE_PRD_NODE.fill — LLM（主 PRD）
  → ProjectRepo.docs.prd.save(json)
  → mermaid 竞品图、resources PDF
  → git_repo.rename_root(项目名)
  → AIMessage(cause_by=WritePRD, instruct_content=WritePRDOutput)
```

主 PRD 生成：

```python
# write_prd.py
node = await WRITE_PRD_NODE.fill(req=context, llm=self.llm, schema=self.prompt_schema)
await self.repo.docs.prd.save(..., content=node.instruct_content.model_dump_json())
```

`ActionNode.fill` = **一次（或 simple 模式下合并的）结构化 LLM 调用** + 解析为 Pydantic 字段，**不是** Thought→Tool→Obs 循环。

### 6.3 与两种「写文件」方式对比

| 方式 | 谁写文件 | 何时 |
|------|----------|------|
| **WritePRD（经典 Action）** | `ProjectRepo` / `FileRepository` API | `Action.run` 内 Python |
| **RoleZero PM** | `Editor.write` 等 **工具** | `_act` → `_run_commands` |
| **PM 注册 WritePRD 为工具** | 仍执行 `WritePRD.run` 内部 ProjectRepo | 工具入口，语义同 Action |

### 6.4 何时算「两层 ReAct」

- **外层**：Role 的 `_react` → `_think` / `_act`（公司级或岗位级循环）。  
- **WritePRD**：只占外层 **一次 `_act`**（经典 SOP 时）；**内部不是 ReAct**。  
- 若 PM 用 RoleZero 写 PRD：外层是 RoleZero ReAct，**一步命令**可能触发 `WritePRD.run` 工具，工具内部仍是 **fill + save**，不是嵌套 ReAct。

---

## 7. 源码锚点

| 主题 | 文件 |
|------|------|
| `_think` / `_act` | `roles/role.py` |
| RoleZero | `roles/di/role_zero.py` |
| WritePRD | `actions/write_prd.py`, `actions/write_prd_an.py` |
| MGX | `environment/mgx/mgx_env.py` |
