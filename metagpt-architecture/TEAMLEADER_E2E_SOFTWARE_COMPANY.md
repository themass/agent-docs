# MetaGPT 默认 `software_company` 端到端流程（含 TeamLeader 细节）

> **范围**：`metagpt software_company` / `generate_repo()` 默认配置（`Team.use_mgx=True` → `MGXEnv`），**不是** `use_fixed_sop=True` 的经典 watch 链。  
> **Plan 概念与命令**：见 [PLAN_MODE.md](./PLAN_MODE.md)（本文侧重 Mike 消息路由与轮次）。  
> **示例需求**：`做一个贪吃蛇`（与文档时序图一致，便于对照）。  
> **关联**：[ARCHITECTURE.md](./ARCHITECTURE.md) · [REACT_THINK_ACT_AND_WRITEPRD.md](./REACT_THINK_ACT_AND_WRITEPRD.md)

---

## 1. 启动时静态配置（跑起来之前）

| 项 | 值 / 行为 | 源码 |
|----|-----------|------|
| Team 环境 | `MGXEnv(context)` | `team.py` `use_mgx=True` 默认 |
| 雇佣角色 | `TeamLeader`(Mike)、`ProductManager`(Alice)、`Architect`(Bob)、`Engineer2`(Alex)、`DataAnalyst`(David) | `software_company.py` `hire()` |
| 预算 | `invest()` → `cost_manager.max_budget = investment`（默认 3.0） | `team.py` |
| 轮次上限 | `asyncio.run(company.run(n_round=5, idea=...))` | `software_company.py` |
| PM / Architect / Engineer2 | `RoleZero` 子类，`react_mode="react"`，`observe_all_msg_from_buffer=True` | `role_zero.py` |
| PM 默认 | **`use_fixed_sop=False`** → **不**走 `PrepareDocuments`+`WritePRD` Action 顺序；工具环 + Editor 等 | `product_manager.py` |
| Architect | `_watch({WritePRD})` 仍配置，但默认 **不会**因 `UserRequirement` 自动开工 | `architect.py` |
| TeamLeader | `max_react_loop=3`；工具 `Plan`、`RoleZero`、`TeamLeader`；`publish_team_message` 注册为工具 | `team_leader.py` |
| 公开群聊 | `MGXEnv.is_public_chat=True` → 发布时 `send_to` 加 `MESSAGE_ROUTE_TO_ALL` | `mgx_env.py` |

每个 Role `set_env` 后，`member_addrs[role]` 包含其 `name`、`profile` 等，用于 `is_send_to` 投递到 `msg_buffer`。

---

## 2. 阶段 A：用户需求进入系统

### A.1 CLI → Team

```text
metagpt "做一个贪吃蛇"
  → generate_repo(idea, investment=3.0, n_round=5, ...)
  → Team(context).hire([...]).invest(3.0)
  → company.run(n_round=5, idea="做一个贪吃蛇")
```

### A.2 `run_project` 构造首条消息

`team.run` 若带 `idea` 会调用：

```python
self.env.publish_message(Message(content=idea))
```

| 字段 | 首条用户需求上的值 |
|------|-------------------|
| `content` | `做一个贪吃蛇` |
| `role` | 默认 `user` |
| `cause_by` | 空 → 校验为 **`UserRequirement`** |
| `send_to` | 默认 **`{MESSAGE_ROUTE_TO_ALL}`** |
| `sent_from` | 空 |

### A.3 `MGXEnv.publish_message`（非 Leader 发布）

走 `else` 分支（`publicer` 不是 Team Leader，`user_defined_recipient` 为空）：

1. `attach_images`（纯文本无图则跳过）
2. **`message.send_to.add("Mike")`** — 强制 Leader 为显式收件人
3. `_publish_message`：
   - `is_public_chat` → **`send_to` 再含 `<all>`**（与 Mike 并存）
   - `move_message_info_to_content`：把 content 改成  
     `[Message] from User to Mike: 做一个贪吃蛇`（公开聊天时展示收件人逻辑见 `mgx_env.py` 注释）
4. `super().publish_message`：对每个 Role，若 `is_send_to(message, addrs)` 为真 → **`put_message` 进该 Role 的 `msg_buffer`**
5. `history.add(message)`（MGX 层历史）

**投递 vs 反应（关键）**

- **投递**：`<all>` 使 **所有角色** 的 buffer 里都能收到这条消息（`is_send_to` 为真）。
- **是否进入 `_react`**：由 `_observe` 过滤 `rc.news`：

```python
n.cause_by in self.rc.watch or self.name in n.send_to
```

对首条用户需求：

| 角色 | `watch` | `name in send_to`? | 进入 `rc.news`? |
|------|---------|-------------------|----------------|
| Mike | （空） | **是**（Mike） | **是** → 会 `react` |
| Alice | 仅 fixed SOP 时 watch `UserRequirement` | 否（send_to 是 `<all>`+`Mike`，不含 `Alice`） | **否** |
| Bob | `WritePRD` | 否 | **否** |
| Alex | （空） | 否 | **否** |
| David | （空） | 否 | **否** |

因此：**不是「订阅了就能干」**；默认配置下 **只有 TeamLeader 会对用户首条需求产生 react**。这就是 Leader 的第一层作用：**门控首响**。

---

## 3. 阶段 B：`env.run()` 第一轮（仅 Mike 非 idle）

`Environment.run(k=1)`：

```python
for role in self.roles.values():
    if role.is_idle: continue
    futures.append(role.run())
await asyncio.gather(*futures)
```

此时仅 Mike 的 `msg_buffer` 有未处理消息 → **并行池里只有 `TeamLeader.run()`**。

### B.1 `Role.run()` 标准壳（Mike）

```text
_observe()  → 从 buffer 取消息，筛出 rc.news，写入 memory（RoleZero 常 observe_all）
react()     → RoleZero 走 _react()，不是经典多 Action 下标
publish_message(rsp) → TeamLeader 覆写见下
```

### B.2 Mike：`RoleZero._react()` 细节

1. **`_set_state(0)`**，`todo` = `RunCommand`
2. **`_quick_think()`**（仅当 `rc.news[-1].cause_by == UserRequirement`）  
   - LLM 分类：`QUICK` / `SEARCH` / `TASK` / `AMBIGUOUS`  
   - 「做一个贪吃蛇」→ 通常为 **`TASK`**（要做软件）→ 不短路，继续正式环  
   - 若是「1+1等于几」类 → `QUICK` 时 Mike **直接 `reply_to_human`**，可能 **不再派组员**（Leader 兼前台）
3. **内层循环**（最多 `max_react_loop=3` 次）：
   - `_observe()`：本轮若 buffer 又有新消息会再并入
   - **`_think()`**：
     - `instruction = TL_INSTRUCTION.format(team_info=...)`（含 Alice/Bob/Alex/David 职责表）
     - 组装 `SYSTEM_PROMPT` + `CMD_PROMPT`（plan 状态、当前任务、工具 schema、经验样例）
     - **`llm_cached_aask`** → 得到 **`command_rsp`**（自然语言 + **一个** JSON 命令数组）
   - **`_act()`**：
     - `parse_commands` → 执行 `tool_execution_map`
     - 典型命令（贪吃蛇、非 XS 时，**示意**，实际以模型输出为准）：
       - `Plan.append_task` × N：一次性列出 PRD / 设计 / 编码等任务与 assignee
       - 和/或 **`TeamLeader.publish_team_message`**：`content` 含 **完整原文需求**，`send_to="Alice"`
     - 工具输出写入 memory：`UserMessage(..., cause_by=RunCommand)`
     - 返回 `AIMessage(..., cause_by=RunCommand)`（给 `Role.run` 末尾 `publish_message`）

4. **`publish_team_message` 内部（派活瞬间）**

```python
self._set_state(-1)   # 派活后暂停，等组员反馈
self.publish_message(
    UserMessage(content=..., sent_from="Mike", send_to="Alice", cause_by=RunCommand),
    send_to="Alice",
)
```

`TeamLeader.publish_message` → `env.publish_message(msg, publicer="Team Leader")`：

- 走 **`publicer == tl.profile`** 分支 → **直接 `_publish_message`**，**不再** `send_to.add(Mike)`
- 消息 `send_to={"Alice"}`（+ 公开模式可能仍带 `<all>`，见 `_publish_message`）
- **Alice 的 `name in send_to`** → 下一轮 Alice 会 `react`

5. Mike 本轮 `Role.run` 末尾还会 `publish_message` 那条 **`AIMessage`（RunCommand 总结）**  
   - 默认 `send_to` 常为 `<all>`，MGX **再次** `send_to.add(Mike)`  
   - 其他组员仍 **不因 `cause_by=RunCommand` 且未 watch** 而开工（除非名字在 send_to）

---

## 4. 阶段 C：`env.run()` 第二轮（Alice 写 PRD / 文档）

Alice `ProductManager`：

- `_observe`：`send_to` 含 `Alice` → **news 非空**
- `_quick_think`：`cause_by` 为 `RunCommand`（来自 Mike 的派活）→ **跳过** quick 路径
- `_think` / `_act`：PM 的 `PRODUCT_MANAGER_INSTRUCTION`（Editor、SearchEnhancedQA、Browser…）
- 可能调用 **`WritePRD.run` 工具**（`tool_execution_map`）或 **`Editor.write`** 写 `docs/prd.md` 等 — **不是**固定 SOP 里无 LLM 路由的 `BY_ORDER` 两步

完成后 `Role.run` → `publish_message(AIMessage, cause_by=RunCommand)`：

- 再次经 MGX：**先加 Mike**
- Bob **watch 的是 `WritePRD` Action 类名**，不是 `RunCommand` → **通常不会因 watch 自动写设计**
- **Mike** 仍在 `send_to` → **Leader 再次 react**（读 `[Message] from Alice to ...`）

**Leader 第二层作用：组员产出默认回 Leader，由 Leader 决定下一棒**（`Plan.finish_current_task`、`publish_team_message` → Bob，或 XS 直接 → Alex）。

---

## 5. 阶段 D：后续轮次（Bob → Alex → 可能 David）

重复模式：

```text
env.run() 一轮
  → 所有非 idle Role 并行 run()
  → 每个 Role：observe → react(think/act) → publish_message
  → MGX：组员消息多数再次带上 Mike
  → Mike：跟踪 Plan、finish task、派下一 assignee
```

| 角色 | 典型触发 | 典型工具/动作 |
|------|----------|----------------|
| Bob | Mike `publish_team_message(..., send_to="Bob")` | `Editor.write` system_design、`Terminal` 看模板树 |
| Alex | Mike 派活 + 附带 `system_design` / 排期路径 | `Editor`、`Terminal`、`Engineer2.write_new_code`、`Deployer` |
| David | 需求被 Leader 判为数据/爬虫类，**整包**派给 David | `write_and_exec_code`、`Browser`、`SearchEnhancedQA` |

`Team.run` **每轮** `_check_balance()`；`n_round` 减到 0 或 **`env.is_idle`**（全员 `is_idle`）停止。

`is_idle` 定义（每个 Role）：

```text
not rc.news and not rc.todo and msg_buffer.empty()
```

RoleZero 在 `_react` 结束会 `_set_state(-1)`；若 buffer 已空且无 todo → idle。

### E. 结束：`archive`

`team.run` 结束后 `env.archive(auto_archive)` → 有 `project_path` 时 `GitRepository.archive()`。

---

## 6. 完整时序（多轮 `env.run`，不省略 MGX/Leader）

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant SC as software_company
    participant T as Team
    participant E as MGXEnv
    participant M as Mike TeamLeader
    participant A as Alice PM
    participant B as Bob Architect
    participant X as Alex Engineer2

    U->>SC: idea = 做一个贪吃蛇
    SC->>T: hire + invest(3.0) + run(n_round=5)
    T->>E: publish_message(Message content=idea)
    Note over E: send_to += Mike + all<br/>content 前缀 [Message] from User to Mike
    E->>M: put_message buffer
    E->>A: put_message buffer 仅投递
    E->>B: put_message buffer 仅投递
    E->>X: put_message buffer 仅投递

    Note over A,B,X: _observe: 非 Mike 名且未 watch UserRequirement<br/>rc.news 为空 → is_idle

    T->>E: run k=1
    E->>M: run observe+react
    M->>M: quick_think → TASK
    M->>M: think LLM → Plan.append_task / publish_team_message
    M->>E: publish_team_message publicer=TL send_to=Alice
    E->>A: put_message 派活正文含完整需求
    M->>E: publish_message AIMessage RunCommand
    Note over E: 组员产出 send_to += Mike

    T->>E: run k=2
    E->>A: run PRD Editor或 WritePRD 工具
    A->>E: publish_message 完成
    E->>M: Mike 在 send_to → run
    M->>E: publish_team_message send_to=Bob

    T->>E: run k=3
    E->>B: run 写 system_design
    B->>E: publish_message
    E->>M: run 派 Alex

    T->>E: run k=4..n
    E->>X: run 编码部署
    X->>E: publish_message
    M->>M: finish_current_task / reply_to_human / end

    T->>T: is_idle 或 n_round=0
    T->>E: archive ProjectRepo
```

---

## 7. 不是 pub/sub：传输 vs 唤醒（Hub-and-spoke）

| 层 | 行为 | 默认 MGX + RoleZero |
|----|------|---------------------|
| 传输 | `put_message` → `msg_buffer` | 常带 `<all>`，**buffer 里大家都能收到** |
| 唤醒 | `rc.news` 非空才 `react` | **仅** `name in send_to`（Leader 派活）或 `cause_by in watch`（默认 PM/Eng **不** watch 链） |
| 组员完成 | `publish_message` | MGX **`send_to += Mike`** → **只唤醒 Leader**，不唤醒下一岗 |
| 下一岗 | `TeamLeader.publish_team_message` | Leader **显式** `send_to=Bob/Alex/...` |

**结论**：协作语义是 **Mike 处理并转发**；除非 `use_fixed_sop=True` + 经典 `Environment` + `_watch(WritePRD)` 等，才是 **Role A 产出 → Role B 自动接棒** 的 pub/sub 式 SOP。

## 8. TeamLeader 作用对照表（相对经典 watch 链）

| 机制 | 无 Leader（经典 `Environment` + fixed SOP） | 有 Leader（默认 MGX） |
|------|---------------------------------------------|------------------------|
| 用户首条需求 | PM `_watch(UserRequirement)` 直接 react | **仅 Mike** react |
| 下一棒 | `cause_by=WritePRD` → Architect watch | **Mike** `publish_team_message` 点名 + Plan |
| 任务拆分/跳过 PRD | 写死在 Action 顺序 | **TL_INSTRUCTION**（XS/S、数据 vs 软件） |
| 组员完成汇报 | 消息广播 + watch 链 | 先 **回到 Mike**（send_to 加 Mike） |
| 用户对话 | 各 Role 可能抢答 | **reply_to_human / ask_human** 以 Leader 为枢纽 |
| `@` 直连某 Role | N/A | `user_defined_recipient` 可绕过 Leader 处理 |

---

## 9. 与 ARCHITECTURE §7.1 旧图差异（必读）

旧图「`observe → WritePRD` → `cause_by=WritePRD` → Architect」描述的是 **`use_fixed_sop=True` + 经典 Action 链**。

**默认 CLI** 应是：

```text
UserRequirement →（仅 Mike react）→ Leader 规划/派活
→ PM RoleZero 工具环（未必出现 WritePRD Action）
→ 回到 Mike → 派 Architect → … → Engineer2
```

若要跑 **无 Leader 的 watch 链**，需显式：`Team(use_mgx=False)` + 各 Role `use_fixed_sop=True` + 经典 `Engineer` 等（见 `tests/metagpt/environment/mgx_env/run_mgx_env.py`）。

---

## 10. 本地复现建议

| 目的 | 命令/入口 |
|------|-----------|
| 默认全链路 | `cd MetaGPT && metagpt "做一个贪吃蛇"` |
| **Team 调试 demo**（同 `software_company` hire，可 IDE 断点） | `python examples/software_company_team_demo.py --idea "…" --n-round 3` |
| 只看 MGX 门控 | `examples/write_game_code.py`（Mike+Alex，手写 `MGXEnv`，轮次更少） |
| 对比 fixed SOP | `run_mgx_env.py` 中 `use_fixed_sop=True` |

调试时开 MetaGPT 日志，搜：`publish_message`、`observed`、`Commands:`、`publish_team_message`。

---

**维护**：`MGXEnv.publish_message`、`TeamLeader`、`software_company.hire` 变更时请同步本节与 [ARCHITECTURE.md](./ARCHITECTURE.md) §6.4 / §7。
