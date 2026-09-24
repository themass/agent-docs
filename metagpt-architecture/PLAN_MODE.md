# 默认 MetaGPT 的 Plan、Message 与 Loop（一篇读完）

> **范围**：`metagpt "你的需求"` / `software_company` 默认路径——**MGX + RoleZero** 下的 **`schema.Plan` + `Plan.*` 命令（③）**。  
> **不用单独开启**；不是模式开关，是每人自带的 **待办表 + 改表命令**。  
> **不是** [REACT_THINK_ACT_AND_WRITEPRD.md](./REACT_THINK_ACT_AND_WRITEPRD.md)（think/act/WritePRD）；**不是** [TEAMLEADER_E2E…](./TEAMLEADER_E2E_SOFTWARE_COMPANY.md)（可作 MGX 路由补充）。  
> 其它三种「Plan」名字见 [附录 A](#附录-a-其它名字里的-plan)。  
> **全局 Message 流水**：[`env.history` §3.2](#32-全局-messageenvhistory你要找的那一股) · **`_think` / `_act`**：[§4.5](#45-rolezero_think-与-_act内层-react默认-cli-核心) · **五角色走查**：[§5](#5-完整示例贪吃蛇五角色--全局-history--每人-plan--l3)

---

## 0. 三十秒版

1. **`env.run()`** 转圈；只有 **信箱里有新消息** 的 Role 本轮 `run()`。  
2. 用户 idea → **先到 Mike**；组员靠 **`publish_team_message` 点名** 才开工，**不是** Plan 里写 `assignee`。  
3. **每人一张私有的 `planner.plan`**；全队进度 = **Mike 的表 + 消息派活**。  
4. Plan 在 **think** 里当 `plan_status` 给 LLM 看，在 **act** 里用 `Plan.*` 命令改 **自己的表**。  
5. **全场消息时间线**只有一份：**`env.history`**（`Team.run()` 返回值）；**不进 think**——LLM 看的是 **各自 `memory` + 自己的 `plan_status`**。

---

## 1. 角色与 Plan 分工

| 名字 | 是谁 | Plan |
|------|------|------|
| **Mike** | TeamLeader | 常维护 **全队步骤表**（1→2→3…） |
| **Alice / Bob / Alex / David** | PM / 架构 / 工程 / 数据 | **各一张私表**，多数时候空或 1～3 条本地步；**看不见 Mike 的表** |
| **用户** | 提需求 | 无 Plan |

**不是全局一张表**；**不会**多人改同一张 `schema.Plan`。

---

## 2. 三层 Loop

| Loop | 代码 | 一步是什么 |
|------|------|------------|
| **L1** | `Team.run` → `n_round` | 多次 `env.run()`，idle/预算则停 |
| **L2** | `env.run()` | **并行**所有非 idle 的 `role.run()` **各一次** |
| **L3** | `RoleZero._react` | 最多 `max_react_loop` 次 **observe → think → act** |

**Plan 只在 L3**：think 读 **自己的** `plan_status`；act 执行 `Plan.*` 等命令。

```text
Role.run()（因有 news）
  observe → react: think(memory + plan_status) → act(Plan.* / Editor / 派活…) → publish_message
```

---

## 3. Message：存哪儿？全局吗？

**不是一份全局 `memory`。**

| 存储 | 作用域 | think 是否用 |
|------|--------|--------------|
| `role.rc.msg_buffer` | 每 Role 私有 | `_observe` 取用 |
| `role.rc.memory` | 每 Role 私有 | `_think` 的 `memory.get(k)` |
| `role.planner.plan` | 每 Role 私有 | `get_plan_status` → prompt |
| `env.history` | 环境一份 | **仅调试**，不进 think |

```text
publish_message
      ├─► Mike.buffer / memory / plan
      ├─► Alice.buffer / memory / plan   （互不读对方的 plan）
      └─► env.history（日志）
```

### 3.1 谁会进 buffer？谁会 react？

- 投递：`send_to` 匹配 Role 的 **addresses**；含 **`<all>`** 时 **人人 buffer 可收到**（公开聊天默认加 `<all>`）。  
- **react** 看 `_observe` 筛出的 **`rc.news`**：`自己的名字 ∈ send_to` 或 `cause_by ∈ watch`（默认组员 **watch 空** → 只靠 **点名**）。  
- RoleZero **`observe_all_msg_from_buffer=True`**：buffer 里本轮消息可能 **都进 memory**（「听说过」），但 **无 news 仍可不 react**。  
- MGX 改 **content**：`[Message] from Mike to Alice: …`；组员出站常 **`send_to += Mike`**；Leader **派活** 走 `publicer=Team Leader` 直达。

| 误解 | 实际 |
|------|------|
| Plan 里 assignee=Alice → Alice 自动动 | **否**，要 `publish_team_message` |
| 人人 buffer 有信 → 人人 react | **否**，看 **send_to 是否含自己名字** |
| 共享一份 memory | **否**，各 append 各的列表 |

### 3.2 全局 Message：`env.history`（你要找的「那一股」）

框架里 **没有** 叫 `global_memory` 的对象；**唯一按时间追加、全队共用的一份 Message 列表** 是 **`Environment.history`**（MGX 下仍是 `MGXEnv` 继承的这份）。

| 问题 | 答案 |
|------|------|
| 谁写入？ | 每次 `Environment.publish_message`（含 MGX 包装后）都会 **`history.add(message)`** |
| 谁读取做 think？ | **谁也不读**（不进 `_think` / `llm_aask` 的默认 history 组装） |
| 和 `Team.run()` 返回值？ | **`return self.env.history`** — 跑完公司拿到的就是这份「全局流水」 |
| 和组员 `memory` 关系？ | **平行**：同一条广播可能同时进 `env.history` + 若干 Role 的 `msg_buffer` → `_observe` 后进 **各自** `memory`（条数、顺序、内容前缀可不同，见 MGX `move_message_info_to_content`） |

```text
                    publish_message（任意 Role / User）
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   env.history          role.msg_buffer       （路由匹配才投递）
   【全局一条时间线】      【每人收件箱】
         │                    │
         │                    └──► _observe → rc.news? → memory（私有上下文）
         │
         └──► 调试 / Team.run 返回值 / 人类复盘「全场发生了什么」
```

**和 `msg_buffer` 的差别**：`history` **从不 pop**，只追加；`buffer` 在 `_observe` 里被消费。因此复盘时：**看全场用 `env.history`；看某角色 LLM 当时看见什么用该 Role 的 `memory.get(k)`**。

下面完整示例里，列 **`H#`** = 该步结束后 `env.history` 里 **新增一条** 的语义摘要（真实 `content` 在 MGX 下常带 `[Message] from … to …:` 前缀）。

### 3.3 三存储对照（速记）

| 存储 | 全局？ | 会增长？ | LLM think 用？ |
|------|--------|----------|----------------|
| `env.history` | **是**（环境一份） | 每条 publish +1 | **否** |
| `role.rc.memory` | 否 | 该 Role observe/工具输出 | **是**（`memory.get(k)`） |
| `role.planner.plan` | 否 | `Plan.*` 改本 Role 表 | **是**（`plan_status` 文本） |

### 3.4 调用大模型时的 message 列表：各 Role **不继承**对方上下文

**结论**：没有「全队共用一个 ChatCompletion messages 数组」。每次 `llm.aask` / `llm_cached_aask` 都是 **当前这个 Role 自己** 拼出来的列表；**Alice 不会带上 Mike 上一轮 think 的完整对话**，除非那些内容已经以 **Message 形式写进 Alice 的 `memory`**（或她自己去读文件）。

**RoleZero `_think` 典型拼装**（与 [EXTERNAL_AND_COGNITIVE_MODULES §2.1](./EXTERNAL_AND_COGNITIVE_MODULES.md#21-memory--在-observe--think--act-之间) 一致）：

```text
system_msgs ≈ SYSTEM_PROMPT + 岗位 instruction + plan_status + 工具 schema + 经验 few-shot …
user/对话侧 ≈ memory.get(memory_k)   # 默认最近 200 条，来自【本 Role】的 memory.storage
```

| 来源 | 是否跨 Role 共享 |
|------|------------------|
| `role.rc.memory` → `get(k)` | **否**，每人自己的 `storage` 列表 |
| `planner.plan` → `plan_status` | **否**，每人自己的表 |
| `env.history` | **不进**默认 LLM 请求 |
| 对方 Role 内部的工具输出 | **默认不进**你的 memory，除非对方 `publish_message` 或你 `Editor.read` 了产物 |

**间接「对齐」只靠协作面，不靠继承上下文**：

1. **消息总线**：`publish_message` → 匹配地址的 Role 在 `_observe` 时 **拷贝进自己的 memory**（MGX 下 content 常带 `from … to …` 前缀）。这是 **复制**，不是共享引用；之后 Mike 多记一条、Alice 的列表 **不会自动变**。  
2. **`observe_all_msg_from_buffer=True`**：buffer 里抄送（含 `<all>`）可能 **更早进 memory**，但仍是 **本 Role 私有列表**；且 **无 news 可以不 react**。  
3. **仓库文件**：`docs/prd.md` 等 — 下游 Role 通过 **工具读盘** 拿到全文，不是继承上游 LLM 的 hidden chain-of-thought。  
4. **Action 内二次 LLM**（如 `WritePRD.run`）：用 **该 Role 当时** 的 `history` 参数（多来自同一 Role 的 memory 子集），仍 **不**合并其他 Role 的 storage。

```text
Mike 调用 LLM          Alice 调用 LLM
     │                      │
     ▼                      ▼
Mike.memory[-200:]    Alice.memory[-200:]
+ Mike.plan_status    + Alice.plan_status
+ Mike 的 system      + Alice 的 system

        ╳ 没有「把 Mike 的 messages 数组 append 给 Alice」这一步
```

同一 Role **内部**：`_react` 多轮里 `_act` 写的 `UserMessage(tool output)` 会 **追加到本 Role memory**，所以 **下一轮 `_think` 能看见上一轮工具结果** — 这只是 **单 Role 内** 的 ReAct 观测链。

可选 **`RoleZeroLongTermMemory`**：超长时把旧条迁入 RAG，仍 **按 Role 实例** 检索拼接，不是全队共享脑。

---

## 4. MGX 协作（消息流）

```text
用户 idea ──► Mike ── publish_team_message ──► Alice 写产物
                  ▲                              │
                  └──────── 完成消息 ────────────┘
```

**改 Plan 表** 与 **派活** 可在 Mike 同一次 act 里连续做；**框架调度只认 Message 的 `send_to`**。

---

## 4.5 RoleZero：`_think` 与 `_act`（内层 ReAct，默认 CLI 核心）

默认五人组 **不是** 经典 `Role._think`「LLM 选一个 Action 下标 → `WritePRD.run(history)`」。而是 **`react_mode=react` + `set_actions([RunCommand])` 占位**：真正的「Act」= **解析 LLM 输出的命令 JSON，顺序调 `tool_execution_map`**。详见 [REACT_THINK_ACT_AND_WRITEPRD §4](./REACT_THINK_ACT_AND_WRITEPRD.md#4-rolezero默认-cli)。

### 4.5.1 和经典 Role 对照

| 阶段 | 经典 SOP（`use_fixed_sop=True`） | RoleZero（默认） |
|------|----------------------------------|------------------|
| **Thought** | `_think`：LLM 输出 **state 编号** → `rc.todo = actions[i]` | `_think`：LLM 输出 **自然语言 + 一个 JSON 命令数组** → 存 **`command_rsp`** |
| **Action** | `_act`：`await rc.todo.run(rc.history)`（业务在 Action 内再调 LLM） | `_act`：**`parse_commands(command_rsp)` → `_run_commands`**，**不** `RunCommand.run()` |
| **Observation** | Action 返回值 → `memory` + `AIMessage` | 每个工具返回字符串 → **`UserMessage(..., cause_by=RunCommand)`** 进 **本 Role** `memory` |
| **出站** | `cause_by=WritePRD` 等 → 别人可 `watch` | `cause_by=RunCommand` → 默认 **不** 触发组员 watch 链 |

### 4.5.2 `_react` 内层循环（在单次 `Role.run()` 里）

```text
_react()  # role_zero.py
  _set_state(0)  →  rc.todo = RunCommand（占位，保证 _think 会继续）
  可选 _quick_think()  # 仅 UserRequirement 首条；Mike 等可短路 QUICK/SEARCH

  actions_taken = 0
  while actions_taken < max_react_loop:   # Mike 默认 3；多数组员默认更大（如 50）
      await _observe()                    # 内层可再吃 buffer
      if not await _think(): break        # RoleZero：todo 被清掉时结束（见下）
      rsp = await _act()                  # 执行本轮 command_rsp
      actions_taken += 1
      # 若 _act 里调了 end / 派活后 _set_state(-1) 等，下轮 _think 可能 False → 跳出

  _set_state(-1)
  return 最后一轮 _act 的 AIMessage（或空）
```

**内层会跑几轮 think/act？**

- **常见 1 轮**：模型在一次 JSON 里塞满 `Plan.*` + `Editor.*` + `end`，或 Mike **派活后** `publish_team_message` 内 **`_set_state(-1)`** → `rc.todo=None` → **下一轮 `_think` 直接 False**，不再调 LLM。
- **2～3 轮**：上一轮工具报错、只做了 Plan 没派活、或模型主动拆步（先 `append_task` 再下一轮 `publish_team_message`）。

### 4.5.3 `_think()`：拼什么、产出什么

**源码**：`roles/di/role_zero.py` `_think`；Prompt 资产见 [ROLE_PROMPTS_ZH §1](./ROLE_PROMPTS_ZH.md#1-rolezero-共享底座)。

| 输入块 | 内容 |
|--------|------|
| **system_msgs** | `SYSTEM_PROMPT`：`{role_info}`、`{instruction}`（岗位，如 `TL_INSTRUCTION`）、`recommend_tools()` 得到的 **`{available_commands}`** JSON schema、经验 **`{example}`** |
| **对话侧 req** | `CMD_PROMPT`：`{plan_status}`、`{current_task}`、`{current_state}`、语言；并要求按 `THOUGHT_GUIDANCE` 先想再输出 |
| **历史** | `memory.get(memory_k)` 转成 API messages（**仅本 Role**）；可选 LTM retrieve  prepend |

**`plan_status` / `current_task`** 来自 **`get_plan_status(self.planner.plan)`**（`utils/role_zero_utils.py`）— 是 **本 Role** 的 `schema.Plan` 打印成文字，**不是** Mike 帮 Alice 维护的表。

**调用**：`llm_cached_aask(...)`（可命中 `exp_pool` 缓存）→ 整段文本写入 **`self.command_rsp`**。

**模型被要求输出的形状**（`CMD_PROMPT`）：

```text
（简短思考，对应 THOUGHT_GUIDANCE 几条）

[
  {"command_name": "Plan.append_task", "args": { ... }},
  {"command_name": "Editor.write", "args": { "path": "...", "content": "..." }},
  {"command_name": "end", "args": {}}
]
```

**返回值**：只要 **`rc.todo` 仍存在**（`RunCommand` 占位），`_think` 通常 **`return True`** → 紧接进入 `_act`。  
**例外**：`_set_state(-1)` 后 `todo=None` → `_think` **`return False`** → 结束内层 while（**不再执行新一轮 _act**）。

### 4.5.4 `_act()`：parse → 顺序执行 → 写 memory

```text
_act()  # RoleZero
  commands ← parse_commands(self.command_rsp)   # 从文本里抠 JSON 数组
  outputs ← []
  for cmd in commands:
      fn ← tool_execution_map[cmd.command_name]
      out ← await fn(**cmd.args)   # 或同步；视工具而定
      outputs.append(out)
      rc.memory.add(UserMessage(content=out, cause_by=RunCommand))  # Observation
      # 副作用工具：
      #   Plan.*     → 改 self.planner.plan（同进程对象）
      #   TeamLeader.publish_team_message → env.publish_message（立刻进别人 buffer）
      #   RoleZero.reply_to_human → Reporter / 用户通道
  return AIMessage(content=拼接 outputs, cause_by=RunCommand)
```

| 命令类型 | `_act` 里发生什么 | 是否再调 LLM |
|----------|-------------------|--------------|
| `Plan.append_task` / `finish_current_task` | 改 **本 Role** `planner.plan`；返回确认字符串进 memory | **否** |
| `Editor.write` / `Terminal.run_command` | 写盘 / 跑 shell；输出进 memory | **否** |
| `WritePRD.run`（PM 注册为工具时） | 调经典 Action：内部 **多段** `ActionNode.fill` | **是**（在工具内部，不算又一次 `_think`） |
| `Engineer2.write_new_code` | 专用写码 prompt 调 LLM | **是**（工具内部） |
| `TeamLeader.publish_team_message` | **同步**发 `UserMessage` 给组员；Leader 常 **`_set_state(-1)`** | **否** |
| `end` | 标记结束；配合下一轮 `_think` False 或 break | **否** |

**关键**：**一轮 `_think` 只调一次路由 LLM**；`_act` 里可以 **0～N 个命令**；其中某个命令 **内部** 可以再调 LLM（写 PRD/写码），那是 **「工具内的子 LLM」**，不会出现在 `_think` 的 `command_rsp` 里。

### 4.5.5 单次 `Role.run()` 末尾（L3 外壳最后一脚）

```text
react() 返回 AIMessage
rc.todo = None
publish_message(AIMessage)   # → env.history + 匹配地址的 buffer
```

组员经 MGX 出站时 **`send_to += Mike`**，所以 **完成汇报** 的 AIMessage 会唤醒 Leader；**工具输出的细节** 大多只在 **自己 memory**，AIMessage 往往是 **较短总结**。

### 4.5.6 术语：L1 / L2 / L3

| 层 | 名称 | 含不含 think/act |
|----|------|------------------|
| L1 | `Team.run` 轮次 | 不含；只反复 `env.run()` |
| L2 | `env.run` 一轮 tick | 不含；并行调度 `role.run()` |
| L3 | 单次 `role.run()` | **含** 整段 `_react`（多轮 **think→act**）+ 末尾 `publish_message` |

---

## 5. 完整示例：贪吃蛇（五角色 + 全局 history + 每人 Plan + L3）

> **读法**：先 **§4.5** 弄清 think/act；本节用 **Mike run#1**、**Alice run#2** 写实；其余 run 仍用总览表。


**需求**：`做一个贪吃蛇`（默认 `software_company`：`Mike` / `Alice`(PM) / `Bob`(架构) / `Alex`(工程) / `David`(数据)）。  
**David**：纯 CLI 游戏需求时 Leader 通常 **不派 David** → 全程 **idle**（buffer 可能有 `<all>` 抄送，但 `rc.news` 空、不跑 L3）。  
**下文 Plan 表**：只列 **Mike 全队表** + 各员 **自己的** `planner.plan`（互相看不见对方表）。

### 5.0 L3 外壳（与 §4.5 衔接）

```text
Role.run()
  _observe() → 无 news 则 return
  react() = §4.5.2 整段 _react（think/act 内层环）
  publish_message(AIMessage)  →  env.history + 路由 buffer
```

**要点**：**一次 env.run 里某个 Role 被唤醒** = 跑完 **整段** L3（可能 **多轮** think/act，但通常 1～2 轮）+ **一条**出站 AIMessage（派活工具触发的 UserMessage **额外**算 H#）。

### 5.1 总览表（`env.run` × 五角色）

| run# | 并行 `role.run()` | **H# 全局 history 新增** | Mike.plan（全队） | Alice | Bob | Alex | David |
|------|-------------------|---------------------------|-------------------|-------|-----|------|-------|
| 0 | （`run_project` 未进 run） | H1 用户需求 | 空 | 空 | 空 | 空 | 空 |
| 1 | **Mike** | H2 Mike 派活 UserMsg；H3 Mike AIMessage 总结 | T1→T2→T3，`current=T1` | 空 | 空 | 空 | 空 |
| 2 | **Alice** | H4 Alice 完成 AIMessage | 仍 T1 未完成 | 可空或本地 1～2 步 | 空 | 空 | 空 |
| 3 | **Mike** | H5 派 Bob；H6 Mike 总结 | `finish` T1，`current=T2` | — | 空 | 空 | 空 |
| 4 | **Bob** | H7 Bob 完成 | T2 未完成 | — | 可本地步 | 空 | 空 |
| 5 | **Mike** | H8 派 Alex；H9 Mike 总结 | `finish` T2，`current=T3` | — | — | 空 | 空 |
| 6 | **Alex** | H10 Alex 完成 | T3 未完成 | — | — | 可本地步 | 空 |
| 7 | **Mike** | H11 `finish` T3 + `reply_to_human`；H12 可选 AIMessage | 三步皆 done | — | — | — | 空 |

「—」= 该轮未调度（idle）。**H1…H12** 是语义序号；真实条数因 Mike 是否合并命令、是否多轮内层 loop 而 ±1，但 **每条出站 publish 都会进 `env.history`**。

### 5.2 run#0：`run_project`（尚未 `env.run`）

| 项 | 内容 |
|----|------|
| 消息 | `Message(content=idea)`，`cause_by=UserRequirement`，`send_to=<all>`+**Mike** |
| 投递 | **五人 buffer 均可有**；**仅 Mike** `name in send_to` → 下轮 run#1 只有 Mike 非 idle |
| **H1** | 全局 history：**第 1 条**用户 idea |
| 全员 plan | 空 |

### 5.3 run#1：仅 **Mike** — L3 + think/act 写实

**前置**：`rc.news` = 用户 idea（`UserRequirement`）；`planner.plan` 空。

#### A. `_observe`（L3 入口，在 `_react` 外还有一次）

- buffer → memory：用户消息（MGX 前缀 `[Message] from User to Mike: 做一个贪吃蛇`）。

#### B. `_react` 内 — **内层第 1 轮**

| 步 | 函数 | 输入（Mike 视角） | 输出 / 副作用 |
|----|------|-------------------|---------------|
| B1 | `_quick_think` | `news[-1].cause_by==UserRequirement` | 小 LLM → **TASK**（要做软件），不 `reply_to_human` 短路 |
| B2 | **`_think`** | `CMD_PROMPT` 里 **`plan_status`: No plan**；`memory` 含用户句 + `TL_INSTRUCTION`（Alice/Bob/Alex 职责表） | **`llm_cached_aask` → `command_rsp`**（示意）： |
| | | | ```text |
| | | | 思考：软件需求，PRD→设计→编码，先建计划再派 Alice。 |
| | | | [ |
| | | |   {"command_name":"Plan.append_task","args":{"task_id":"1","instruction":"…PRD…","assignee":"Alice"}}, |
| | | |   {"command_name":"Plan.append_task","args":{"task_id":"2","assignee":"Bob",...}}, |
| | | |   {"command_name":"Plan.append_task","args":{"task_id":"3","assignee":"Alex",...}}, |
| | | |   {"command_name":"TeamLeader.publish_team_message","args":{"content":"<全文需求+上下文>","send_to":"Alice"}}, |
| | | |   {"command_name":"RoleZero.reply_to_human","args":{"content":"已安排 Alice 撰写 PRD。"}} |
| | | | ] |
| | | | ``` |
| B3 | **`_act`** | 解析上表 JSON，**顺序**执行： | |
| B3a | | `Plan.append_task` ×3 | **`Mike.planner.plan`**：goal 设好，tasks 1→2→3，`current_task=1`；每条返回确认串 → **memory** |
| B3b | | `publish_team_message` | **`env.publish_message`**（`publicer=Team Leader`）→ **H2** 进 history + **Alice buffer**；工具内 **`_set_state(-1)`** → `rc.todo=None` |
| B3c | | `reply_to_human` | 用户侧一句进度（Reporter） |
| B3d | | （本轮无 `end` 也可） | 再 **memory** += 各工具输出（`cause_by=RunCommand`） |
| B4 | **`_act` return** | | `AIMessage(cause_by=RunCommand)` 短摘要 |

#### C. `_react` 内 — **是否还有第 2 轮？**

- 若 B3b 已 `_set_state(-1)`：**下一轮** `_think()` 见 `todo=None` → **`return False`** → **while 结束**（Mike 默认 **只 1 次** 路由 LLM）。
- 若模型没派活只建了 Plan：第 2 轮 `_think` 会看到 **更新后的 `plan_status`** + 上一轮 Plan 工具 Observation，再输出 `publish_team_message`。

#### D. `_react` 结束 + L3 末尾

- `_set_state(-1)`（再次确保 idle 态）
- **`Role.run` → `publish_message(AIMessage)`** → **H3**（常 `send_to` 含 `<all>`+Mike，**不**含 Alice 名）

**Mike.plan 此时**：T1 进行中（**未** `finish_current_task`）。  
**Alice**：本轮未 `run()`；**H2** `send_to={Alice}` → 下轮 run#2 **news 非空**。

### 5.4 run#2：仅 **Alice** — L3 + think/act 写实

**前置**：`rc.news` = Mike 派活（`cause_by=RunCommand`，正文含完整需求）。

#### A. `_observe`

- 派活进 **Alice.memory**（她 **看不见** Mike 的 plan 表，只见消息里的字）。

#### B. `_react` 内层（示意 **1 轮**）

| 步 | 函数 | 输入 | 输出 / 副作用 |
|----|------|------|---------------|
| B1 | `_quick_think` | `cause_by=RunCommand` | **不跑** |
| B2 | **`_think`** | `plan_status` 常为 **No plan** 或她自建的 1 条本地 task；`memory` 含派活 + `PRODUCT_MANAGER` 的 Editor/Search 说明 | **`command_rsp`**（示意）： |
| | | | ```text |
| | | | 思考：按派活写 PRD，路径 docs/prd.md。 |
| | | | [ |
| | | |   {"command_name":"Editor.write","args":{"path":".../docs/prd.md","content":"# PRD …"}}, |
| | | |   {"command_name":"end","args":{}} |
| | | | ] |
| | | | ``` |
| | | | 若模型选 **`WritePRD.run`**：同一 `_act` 内走 Action，**内部**多轮 fill LLM 写 JSON PRD 再 `repo.docs.prd.save`，**Observation** 仍是工具返回的一段文字进 memory。 |
| B3 | **`_act`** | `Editor.write` 或 `WritePRD.run` | 磁盘 **`docs/prd.md`**；memory += 工具输出 |
| B4 | return | | `AIMessage` 摘要（「PRD 已写入 …」） |

#### C. L3 末尾 `publish_message`

- **H4** → MGX **`send_to += Mike`** → run#3 只唤醒 Mike。

**Alice.plan**：可选她自己 `append_task` 过；**Mike.plan 的 T1 仍未完成**（Alice **没有** `Plan.finish_current_task` 权限去勾 Mike 的行）。  
**Bob**：`watch WritePRD` 但出站是 **`RunCommand`** → **不自动接棒**。

### 5.5 run#3：仅 **Mike**（think/act 摘要）

| 步 | 说明 |
|----|------|
| `_think` | `memory` 含 **H4**（Alice AIMessage 摘要）；`plan_status` 仍显示 **task1 未完成**（assignee 只是表上备注，不会自动勾） |
| `_act` | 典型 JSON：`Plan.finish_current_task` → **`Mike.plan` T1✓、`current=T2`** → `publish_team_message(Bob, …)` → **H5**；`reply_to_human` 可选 |
| 内层环 | 派活后 again `_set_state(-1)`，常 **1 轮** LLM |
| L3 末尾 | **H6** AIMessage |

### 5.6 run#4：仅 **Bob**（同 Alice 模式）

写 `docs/system_design.md` 等 → **H7** → Mike 的 `send_to` 再次命中 → run#5。

### 5.7 run#5–#6：Mike 派 **Alex** → Alex 编码

与上对称：**H8–H10**；Alex `Editor` / `Engineer2.write_new_code` / `Deployer` 等。

### 5.8 run#7：Mike 收尾

| act | Mike.plan | history |
|-----|-----------|---------|
| `Plan.finish_current_task`（T3） | 全队三步皆完成 | — |
| `reply_to_human` | — | 用户可见总结（路径经 Reporter/MGX） |
| `publish_message` | — | **H11–H12** |

此后全员 idle 或 `n_round` 用尽 → `Team.run` **`return env.history`**（**H1…Hn 全在**）。

### 5.9 五角色 **memory** 与 **全局 history** 同一步对照（run#2 后示意）

| 视角 | 能看见什么 |
|------|------------|
| **env.history** | H1 用户 → H2 派活 → H3 Mike 总结 → H4 Alice 完成 → … **按时间全量** |
| **Mike.memory** | 用户 idea、自己的 Plan 工具输出、派活记录、Alice H4 摘要、… **不含** Bob 表里字 |
| **Alice.memory** | 抄送的用户 idea（若 observe_all）、**派活全文**、自己写 PRD 的工具输出、… **看不到** Mike 的 `plan_status` 原文表 |
| **Bob.memory** | 多数只有 `<all>` 抄送（若 observe_all）；**在 run#4 之前常无「该我写设计」的正文**，直到 Mike H5 派活 |

### 5.10 简图：一轮里「全局 vs 私有」

```text
run#3 只有 Mike 动：

  env.history:  [H1..H4 已在] ──publish──► H5,H6
  Mike.memory:  … + H4 内容 + finish/plan 工具输出
  Alice.memory: … + 自己 earlier 派活/PRD（不自动同步 Mike 的 finish）
  Mike.plan:    T1✓ T2● T3○   （Bob/Alex 各自 plan 仍与这张表无关）
```

更细的 MGX 路由与 `quick_think` 见 [TEAMLEADER_E2E_SOFTWARE_COMPANY.md](./TEAMLEADER_E2E_SOFTWARE_COMPANY.md)。

---

## 6. 机制详解：`hello.py`（XS，逐事件）

仅 Mike 建 **1 步** 派 **Alex**。

### 6.0 初始

全员 buffer/memory 空；`Mike.plan` / `Alex.plan` 皆空。

### 6.A `run_project("用 Python 写 hello.py")`

- `send_to`：`<all>` + **Mike**；`cause_by`：`UserRequirement`  
- 人人 **buffer 可能有**；通常 **仅 Mike react**

### 6.B 第 1 次 `env.run()` — Mike

| 步骤 | Mike.plan | 对外 |
|------|-----------|------|
| think | No Plan | — |
| act | goal=需求；tasks=[{1→Alex, 写 hello}] | `publish_team_message`→Alex |

派活：`UserMessage`，`sent_from=Mike`，`send_to={Alex}`，`cause_by=RunCommand`。

| 之后 | Alex.buffer | Alex.plan |
|------|-------------|-----------|
| +派活 | **仍常为空** | |

### 6.C 第 2 次 `env.run()` — Alex

observe：派活进 memory；act：`Editor.write` → `hello.py`；publish → MGX **+Mike**。

| Mike.plan | Alex.plan |
|-----------|-----------|
| **task1 仍未 finish** | 可有可无本地步 |

### 6.D 第 3 次 `env.run()` — Mike

`Plan.finish_current_task` → task1 完成 → `reply_to_human`。

### 6.1 第 2 次 env.run 后「五视图」

| | Mike.plan | Alex.plan | Mike.memory | Alex.memory | **env.history** |
|--|-----------|-----------|-------------|-------------|-----------------|
| 用户原话 | goal✓ | 可能刚设 | ✓ | ✓（抄送+派活） | H1 |
| Mike 全队表 | 1 步 | **看不到** | plan_status 在 prompt 里 | **看不到** | 无 Plan 字段 |
| 派活 / 编码 | — | — | 派活记录 | 派活+工具 | H2,H3,… |
| hello.py | — | — | 可能 | ✓（工具输出） | 仅 AIMessage 摘要，非文件全文 |

XS 路径 **不经过 Alice/Bob**；全局 history 条数 **少于** §5 完整贪吃蛇，但 **`history` 仍是唯一全场追加列表**。

### 6.2 hello 路径按 run 的 L3（Mike + Alex）

| run# | Role | L3 摘要 |
|------|------|---------|
| 1 | Mike | observe(用户) → quick(TASK) → think → act：`Plan` 1 步 + `publish_team_message(Alex)` → publish → **H2,H3** |
| 2 | Alex | observe(派活) → think → act：`Editor.write(hello.py)` → publish → **H4**（+Mike） |
| 3 | Mike | observe(H4) → act：`finish_current_task` + `reply_to_human` → **H5+** |

---

---

## 7. Plan 与 LLM、与 agent loop

| 概念 | 关系 |
|------|------|
| **LLM** | think 时读 `plan_status`（表的文字版）；act 时可选输出 `Plan.*` JSON **改表** |
| **经典 agent loop** | 仍是 observe→think→act；Plan **不替代** loop |
| **plan-and-execute** | 默认公司 **不是** 严格两阶段；`plan_and_act`+`WritePlan` 是 **另一条路**（如 DataInterpreter），见附录 A |

**表的目的**：给 **本 Role 的 LLM** 结构化「做到哪了」；Mike 表≈项目甘特（仅 Mike 用）；组员表≈可选本地拆解。

---

## 8. 命令对照

| 命令 | 作用 | 不作用 |
|------|------|--------|
| `Plan.append_task` | 改 **自己** 表 | 不通知别人 |
| `Plan.finish_current_task` | 勾当前行 | 不自动派下一棒 |
| `TeamLeader.publish_team_message` | **send_to 点名** | — |
| `end` | 结束本轮 react | 不等于全公司结束 |

---

## 9. 源码锚点

| 机制 | 文件 |
|------|------|
| 默认组队 | `software_company.py` |
| Plan 绑定 think/act | `roles/di/role_zero.py` |
| 派活 | `roles/di/team_leader.py` |
| plan_status | `utils/role_zero_utils.py` |
| 投递 / env.run | `environment/base_env.py` |
| MGX | `environment/mgx/mgx_env.py` |
| observe / news | `roles/role.py` `_observe` |
| Plan 模型 | `schema.py` `Plan`, `Task` |

---

## 10. 速查

| 问题 | 答案 |
|------|------|
| Plan 要单独开？ | **不要**，RoleZero 自带 |
| 全局 Plan 表？ | **否**，每人一份 `planner.plan` |
| 全局 Message？ | **`env.history`**（think 不用；`Team.run` 返回） |
| LLM 的 messages 全队共用？ | **否**，各 Role **`memory.get(k)` + 自己的 system/plan**（§3.4） |
| 别人能看见我的 plan 表？ | **否**，只见 **消息** + 自己 memory |
| 谁该动？ | **`send_to` 点名**，不是 assignee |
| 完整五角色示例？ | **§5**（贪吃蛇）；XS 见 **§6** |

---

## 附录 A：其它名字里的「Plan」

| 名字 | 默认五人公司 |
|------|----------------|
| ③ `Plan.*` + `schema.Plan` | **本文** |
| ① `plan_and_act` | 否（DI 等） |
| ② `WritePlan` | 否 |
| ④ `WriteTasks` 文件 | 否（无 Eve） |

[CLASS_DIAGRAM §2.7](./CLASS_DIAGRAM_AND_RUNTIME.md#27-plan-模式辨析最容易混在一起的四件事)

---

**维护**：默认 `software_company` / MGX / RoleZero Plan 行为变更时更新本文。
