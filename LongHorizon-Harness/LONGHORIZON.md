# LongHorizon-Harness 设计

> **阅读顺序：** 总览 → [设计深化与工程边界](#设计深化与工程边界) → 历史架构正文。历史四篇原文保留；新增章节区分已实现行为与设计建议。  
> 源码：`LongHorizon-Harness/src/lh_harness/`  
> 源码走读另见 [SOURCE.md](SOURCE.md)

## 一句话

不改 Claude Code / Codex 内部怎么调工具。在外面固定一轮：**Manager 规划 → Executor 换新上下文去干 → Auditor 独立验收 → 只把验过的进度留下来 → 再来一轮。**

## 谁看见什么

```mermaid
flowchart LR
    TASK["原始任务 每轮都在"]
    M["Manager<br/>只看任务 + 审计报告 + 自己的状态"]
    E["Executor<br/>只看本轮要做的事"]
    A["Auditor<br/>看结果，不信执行者口述"]
    DISK["rounds/ + events.jsonl + report.json"]
    TASK --> M
    M -->|本轮指令| E
    E -->|产物| A
    A -->|报告| M
    M --> DISK
    E --> DISK
    A --> DISK
```

| 角色 | 看得到 | 看不到 |
|------|--------|--------|
| Manager | 原始任务、Auditor 报告、task_state | Executor 的原始轨迹 |
| Executor | 本轮 prompt | 别的角色的完整历史 |
| Auditor | 工作区变化和约定的验收格式 | 不能替 Manager 宣布完成 |

完成只能由 Manager 说 `Next: done`，并且上一轮 Auditor 是干净完成。自报完成会被挡回去。

## 目录

1. [核心运行时](#原文--core_runtimemd) — 公理、模块图、端到端时序  
2. [架构 · 闭环与门禁](#原文--architecture_part1md) — 信息隔离、伪完成、落盘  
3. [架构 · Adapter 与 Auditor](#原文--architecture_part2md) — 一集生命周期、预算、插件  
4. [架构 · CLI / Web / Supervisor](#原文--architecture_part3md) — 组装、ControlBus、评测
5. [设计深化与工程边界](#设计深化与工程边界) — 缺口评审、信任模型、证据时效、恢复协议、资源治理、评测与演进  
6. [源码还原：整体架构与模块设计](#源码还原整体架构与模块设计) — 当前模块、进程边界、后端差异、Supervisor、Web 与真实缺口



---

# 原文 · CORE_RUNTIME.md

> 原文 `CORE_RUNTIME.md` 全文并入，Mermaid 与表格未改。

# LongHorizon-Harness — 核心运行时（架构层）

> 逐函数走读见 [SOURCE.md](SOURCE.md)。本文件：设计公理、模块图、E2E。  
> 源码根：`src/lh_harness/`

---

## §0 架构思考：这个 Harness 在解决什么？

### 0.1 问题

单次 Agent（Claude Code / Codex）在长任务上会：

- 上下文爆掉 → 遗忘目标与已完成项  
- 自报「完成」但桌面/文件实际未达标  
- GUI 与 CLI 混用时状态分裂  

**LongHorizon-Harness（LHH）** 不改 Agent 内部 Tool Loop，而是在外层固定：

> **规划（Manager）→ 执行（Executor，全新上下文）→ 独立验证（Auditor）→ 只保存通过验证的进度 → 重复。**

### 0.2 核心公理

| # | 公理 | 操作化 |
|---|------|--------|
| 1 | **可信进度 = Auditor 报告，不是 Executor 口述** | Manager 下一轮读的是报告/任务状态，不是 raw trajectory |
| 2 | **完成必须有证据** | `Next: done` 且上一轮 Auditor `clean + complete`，否则合成 invalid 反馈 |
| 3 | **每角色 episode 独立** | `AgentAdapter.run_episode(prompt, env, budget)`；默认全新上下文 |
| 4 | **Harness 状态落盘** | `~/.lh-harness` 账本 + 每 round 目录；崩溃也要有 terminal `report.json` |
| 5 | **后端可换** | Protocol：`AgentAdapter` + `Environment`；角色可绑不同模型/后端 |

### 0.3 与 DeepSeek Harness 的差（对照）

| | DeepSeek Harness | LongHorizon-Harness |
|--|------------------|---------------------|
| 内核 | 自研 Turn/Step + SessionEvent | **编排外环**；内环是外部 CLI Agent |
| 真源 | SessionEvent 日志投影 | **Manager 维护的 task_state + Auditor 报告** + events.jsonl |
| 扩展 | Cordis 插件 / Seam | Adapter / Env / Plugin（computer-use） |
| 语言 | TypeScript | Python + TS 前端 |

两者都是「Harness」，但 LHH 是 **MEA（Manager–Executor–Auditor）外环工程**，不是可替换的自研 Tool Loop。

---

## §1 模块设计图

```mermaid
flowchart TB
  subgraph Ingress["入口"]
    CLI["lh-harness CLI"]
    WEB["lh-harness web · FastAPI"]
  end

  subgraph Super["进程监督"]
    RS["RunSupervisor"]
    BUS["ControlBus"]
  end

  subgraph Kernel["编排内核"]
    M["manager.run / _run_impl"]
    RP["role_prompts"]
    AU["auditor_agent 解析"]
  end

  subgraph Backends["可替换后端"]
    AD["AgentAdapter<br/>claude_code / codex / CommandAgent"]
    ENV["Environment<br/>local · Protocol"]
  end

  subgraph Disk["落盘"]
    LOG["log_dir / role_orchestration"]
    RPT["report.json"]
  end

  CLI --> M
  WEB --> RS --> BUS
  RS -->|spawn worker| M
  M --> RP
  M --> AD
  M --> ENV
  M --> AU
  M --> LOG
  M --> RPT
  BUS -.->|stop / instruct / approve| M
```

### 包职责（`src/lh_harness/`）

| 模块 | 职责 |
|------|------|
| `manager.py` | **四角色闭环内核**（约 2.2k 行） |
| `role_prompts.py` | 构造/解析 Manager·Executor·Auditor Prompt |
| `auditor_agent.py` | 报告文本 → `AuditReport`、只读违规、删除账本 |
| `adapters/` | 把 prompt 变成 `claude`/`codex` 等 CLI 进程 |
| `environment/` | `exec` / `screenshot` / upload·download |
| `supervisor/` | Web/多 run：创建、信号、幂等、生命周期 |
| `webapi/` | FastAPI + 事件推送 |
| `dashboard/` | 人机门禁状态机（审批/追问） |
| `plugins/` | computer-use 插件安装与配置 |
| `cli.py` | 命令行与 doctor / plugin / run |

---

## §2 端到端：一轮 Round

```mermaid
sequenceDiagram
  participant Op as Operator
  participant M as manager._run_impl
  participant Mgr as Manager Adapter
  participant Ex as Executor Adapter
  participant Aud as Auditor Adapter
  participant Env as Environment
  participant Disk as round_NNN /

  Op->>M: task + agents + env
  loop round_index < budget
    M->>Mgr: run_episode(manager_prompt)
    Mgr->>Env: exec(claude/codex …)
    Mgr-->>M: EpisodeResult
    M->>Disk: manager_plan / task_state
    alt next=done 且审计干净
      M-->>Op: completion gate
    else next=gui|cli
      M->>Ex: run_episode(executor_prompt)
      Ex->>Env: 操作桌面/终端
      Ex-->>M: output
      M->>Aud: run_episode(auditor_prompt)
      Aud->>Env: 只读检查
      Aud-->>M: report
      M->>Disk: auditor_report + ManagedRound
      M->>M: human_gate(progress)?
    end
  end
  M->>Disk: report.json
```

---

## §3 状态机（Manager `next_step`）

```mermaid
stateDiagram-v2
  [*] --> ManagerEpisode
  ManagerEpisode --> Done: next:done + clean auditor
  ManagerEpisode --> Blocked: next:blocked / runtime fail
  ManagerEpisode --> Ask: next:ask
  ManagerEpisode --> Invalid: 解析失败 / 伪完成
  ManagerEpisode --> Executor: next:gui|cli
  Executor --> Auditor
  Auditor --> ManagerEpisode: 写入 rounds，下一轮
  Done --> [*]: human stop 或结束
  Blocked --> ManagerEpisode: human continue
  Ask --> ManagerEpisode: 答案注入 carryover
  Invalid --> ManagerEpisode: harness_feedback
```

路由解析：`parse_role_manager_next_step`（`role_prompts.py`）——只认显式 `Next: gui|cli|done|blocked|ask`（中英），否则 `invalid`。

---

## §4 可信状态流

```text
原始 task（不变）
  + current_task_state / task_contract（从 Manager 计划抽取，跨轮保留）
  + rounds[].auditor_report（仅被引用的报告进 Executor/Auditor 上下文）
  + harness_feedback（无效完成 / 无效计划 / 运行时失败）
  ≠ Executor raw trajectory（Manager 刻意不看）
```

磁盘侧每轮还有完整轨迹供人审；**编排决策面**刻意收窄。

---

## §5 权衡

| 选择 | 得到 | 付出 |
|------|------|------|
| 外环三角色 | 长程可恢复、验收独立 | 每轮 2–3 次完整 Agent 启动，成本高 |
| 自然语言控制头 | 任意后端只要能出文本 | 解析脆弱 → format repair / invalid 路径 |
| 文件系统账本 | 崩溃可查、Supervisor 可判终态 | 路径/权限/符号链接需硬化 |
| Adapter 薄封装 | 保留原生 Agent 能力 | 依赖外部 CLI 版本与权限模型 |

---

## §6 读源码地图

1. `types.py` — `ManagedRound` / `AuditReport` / `HarnessConfig`  
2. `manager.py` — `run` → `_run_impl` while 循环  
3. `role_prompts.py` — build + `parse_role_manager_next_step`  
4. `adapters/cli_agent.py` — prompt 文件 + `env.exec`  
5. `auditor_agent.py` — `audit_report_from_episode_result`  
6. `supervisor/service.py` — `create_run` / stop / resume  

详细走读：[SOURCE.md · Manager 闭环](SOURCE.md#原文--01-manager-loopmd)



---

# 原文 · ARCHITECTURE_PART1.md

> 原文 `ARCHITECTURE_PART1.md` 全文并入，Mermaid 与表格未改。

# LongHorizon-Harness — 架构文档（第1部分）

> **主题**：为什么 MEA 外环成立 · 状态真源如何流动 · Prompt/路由契约 · 落盘与事件 · 完成门禁  
> **配套源码走读**：[SOURCE.md · Manager 闭环](SOURCE.md#原文--01-manager-loopmd)（逐行 `_run_impl`）  
> 仓库：`src/lh_harness/` · 语言：**Python**  
> 2026-08-14

---

## §0 本卷要回答的问题

1. 为什么「换模型/换 Agent」解决不了长程 computer-use，而要在外层做 Loop Engineering？  
2. Manager / Executor / Auditor 各自看见什么、看不见什么？信息隔离如何用代码强制？  
3. 「任务完成了」在系统里由谁说了算？伪完成如何被挡回？  
4. 磁盘上的 round 目录、events.jsonl、report.json 各自服务哪一层消费者？

---

## §1 产品命题与架构公理

### 1.1 一句话

**LongHorizon-Harness（LHH）** = 在 Claude Code / Codex 等 **现有 Agent CLI 之外**，用固定的 **Manager → Executor → Auditor** 轮次，把「规划、执行、真实验收、可信进度」工程化。

不训练模型；不替换 Agent 内部 Tool Loop；不自研 SessionEvent 内核（那是 DeepSeek Harness 路线）。

### 1.2 失败模式 → 对策

| 单 Agent 长跑常见失败 | LHH 对策（代码落点） |
|----------------------|----------------------|
| 上下文爆掉，忘记目标 | 每角色 `run_episode` 全新进程；跨轮只传 `task` + 压缩后的 state/报告 |
| 自报完成但桌面/文件未达标 | `Next: done` 必须 `_latest_auditor_is_clean_complete` |
| 执行口述被当成进度 | Manager prompt **不含** raw trajectory；只含 auditor 报告 |
| GUI/CLI 混用状态乱 | `next: gui\|cli` 分绑不同 adapter/budget/auditor |
| Worker 崩溃无终态 | `manager.run` 捕获一切异常写 terminal `report.json` |

### 1.3 五条公理（操作化）

1. **原始 `task` 不变**——每轮 Manager 都重新看见它。  
2. **可信中间状态 = Auditor 自然语言报告**（再加 Manager 维护的 `task_state`/`task_contract`）。  
3. **完成权威 = Manager 路由 + 干净审计**，权威字段写在 `report.json` 的 `completion_authority`。  
4. **Harness 反馈 ≠ 审计**——invalid plan/completion 进 `harness_feedback`，prompt 里单独一节标明。  
5. **落盘先于信任 UI**——Supervisor/Web 读文件与进程身份，不读内存里的「我觉得完成了」。

---

## §2 模块全景（决策面 vs 执行面）

```mermaid
flowchart TB
  subgraph Decision["编排决策面 — manager._run_impl"]
    LOOP[while round_index < budget]
    ROUTER[parse_role_manager_next_step]
    GATE[_human_gate / completion]
    STATE[task_state · task_contract · rounds]
  end

  subgraph Prompt["契约文本 — role_prompts"]
    BM[build_role_manager_prompt]
    BE[build_role_executor_prompt]
    BA[build_role_auditor_prompt]
  end

  subgraph Exec["执行面 — 每角色一集"]
    AD[AgentAdapter.run_episode]
    ENV[Environment.exec/screenshot]
  end

  subgraph Trust["验收结构化 — auditor_agent"]
    PARSE[parse_audit_report / control headers]
    MUT[workspace mutation fail-closed]
  end

  subgraph Disk["落盘"]
    EV[events.jsonl]
    RD[rounds/round_NNN]
    RP[report.json]
  end

  LOOP --> BM --> AD
  AD --> ENV
  AD --> ROUTER
  ROUTER -->|gui/cli| BE --> AD
  BE --> BA --> AD
  AD --> PARSE
  PARSE --> STATE
  LOOP --> GATE
  LOOP --> EV
  LOOP --> RD
  GATE --> RP
  MUT --> PARSE
```
```mermaid
flowchart TB
subgraph Decision["编排决策面 — manager._run_impl"]
LOOP[while round_index < budget]
ROUTER[parse_role_manager_next_step]
GATE[_human_gate / completion]
STATE[task_state · task_contract · rounds]
end
subgraph Prompt["契约文本 — role_prompts"]
BM[build_role_manager_prompt]
BE[build_role_executor_prompt]
BA[build_role_auditor_prompt]
end
subgraph Exec["执行面 — 每角色一集"]
AD[AgentAdapter.run_episode]
ENV[Environment.exec/screenshot]
end
subgraph Trust["验收结构化 — auditor_agent"]
PARSE[parse_audit_report / control headers]
MUT[workspace mutation fail-closed]
end
subgraph Disk["落盘"]
EV[events.jsonl]
RD[rounds/round_NNN]
RP[report.json]
end

%% 修正后的连线，符合LongHorizon真实流转
LOOP --> BM
BM --> ROUTER
ROUTER --> BE
ROUTER --> BA
BE --> AD
BA --> AD
AD --> ENV
AD --> PARSE
PARSE --> MUT
MUT --> STATE
STATE --> LOOP
STATE --> GATE
STATE --> EV
STATE --> RD
GATE --> RP
```

**读图要点**：右边 Exec 可以换 Claude/Codex；左边 Decision 的门禁与状态机不应随 Adapter 分叉复制。

---

## §3 三角色：信息隔离（架构核心）

### 3.1 职责表（带「禁止」）

| 角色 | 负责 | 允许看见 | **禁止看见/做** |
|------|------|----------|-----------------|
| **Manager** | 恢复目标、维护契约、选下一步 | 原始 task、task_state/contract、历史 auditor 报告、harness_feedback、轮次预算 | Executor/Auditor 的 raw JSONL 轨迹；替用户「假装验收」 |
| **Executor** | 只做一项边界明确的子任务 | 本轮 plan、state/contract、**Manager 点名的** related reports、workspace | 全局改规划；把 harness 日志当交付物 |
| **Auditor** | 独立检查真实环境 | 子任务契约、executor 可见输出、related reports | 默认写改工作区；无控制头的胡言当 complete |

### 3.2 代码如何强制「Manager 不看轨迹」

构造 Manager prompt 时显式组装的块（英文路径，`role_prompts.py`）：

```62:94:src/lh_harness/role_prompts.py
        return f"""\
{MANAGER_INSTRUCTIONS[lang].strip()}

Original task:
{task.rstrip()}
...
Previous current-task state:
{task_state.strip() or "(No maintained state yet. ...)"}

Historical auditor reports by round (authority for trusted intermediate state):
{auditor_reports or "(No auditor reports yet.)"}

Harness management feedback (not an audit; only for protocol/completion correction):
{harness_feedback or "(No harness feedback.)"}

Round budget:
- Current management round: {round_index}
...
Output only the next management result.
"""
```

`auditor_reports` 来自 `format_verified_intermediate_context(rounds, ...)`——只抽取过去 round 里存下的 **auditor_report 文本**，不是 `*_raw_trajectory.jsonl`。

轨迹仍会通过 `_save_role_result` 落盘供人审 / Dashboard，但 **不进入下一轮 Manager 的决策输入**。这是「操作员面」与「决策面」分离。

### 3.3 Executor 只拿「点名」的报告

```561:572:src/lh_harness/manager.py
        # Task prompts receive the manager-maintained state plus only the
        # auditor reports explicitly referenced by the current subtask contract.
        executor_prompt = build_role_executor_prompt(
            ...
            related_auditor_reports=related_auditor_reports,
            ...
        )
```

`related_report_refs` 从 Manager 计划里解析；`format_related_auditor_reports` 按 round id 裁剪。  
**未引用的历史报告默认不进 Executor**——防止上下文膨胀，也防止「随便翻旧报告当新证据」。

---

## §4 一轮 Round 的完整控制流

```mermaid
flowchart TD
  A[round_index++] --> B[build manager prompt]
  B --> C[_run_role_episode Manager]
  C -->|cancelled / runtime fail| Z[abort · break]
  C --> D[抽取 plan · state · contract · refs]
  D --> E{parse next_step}
  E -->|done| F{_latest_auditor_is_clean_complete?}
  F -->|是| G[completion_satisfied · human_gate]
  F -->|否| H[invalid_completion feedback · continue]
  E -->|blocked / ask / invalid| I[记 round · human_gate]
  E -->|gui / cli| J[Executor episode]
  J -->|fail/cancel| Z
  J --> K[Auditor episode]
  K -->|fail/cancel| Z
  K --> L[format repair?]
  L --> M[ManagedRound + parse_audit_report]
  M --> N[human_gate progress]
  N -->|stop| END[_final_report]
  N -->|continue| A
  G -->|stop| END
  I -->|stop| END
```

对应源码主循环：`manager.py` `_run_impl` 约 L285–L890。  
取消与 provider 失败在 **每个角色阶段** 都有对称分支（写 `ManagedRound`、events、`abort_reason`/`failure_reason`）。

---

## §5 路由契约：`Next:` 是控制面，不是散文

### 5.1 合法取值

| 解析结果 | Manager 意图 | 编排行为 |
|----------|--------------|----------|
| `gui` | 需要桌面/视觉操作 | GUI executor + GUI auditor |
| `cli` | 需要终端/文件/代码 | CLI executor + CLI auditor |
| `done` | 宣称总任务完成 | **仅当**存在干净 complete 审计才收工 |
| `blocked` | 无法继续 | human_gate；无 hook 则停 |
| `ask` | 必须问人 | 抽 question/choices；无 hook → `needs_human_input` |
| `invalid` | 控制行不合规 | 注入 `_invalid_plan_feedback`，当审计信号 |

### 5.2 解析器行为（严格）

```481:499:src/lh_harness/role_prompts.py
def parse_role_manager_next_step(text: str) -> RoleNextStep:
    for line in str(text or "").splitlines():
        normalized = ...
        normalized = re.split(r"(?:—|–|--|//|#|[（(])", normalized, maxsplit=1)[0]
        ...
    return MANAGER_NEXT_INVALID
```

- `Next: done — all passed` → **done**（破折号后当注释）  
- `Next: done later` → **invalid**（later 不是 delimited 后缀）  
- 中英同义集合（`下一步:完成` / `next:complete` 等）  

架构含义：控制面靠 **行级协议**，不是靠 LLM JSON schema。代价是脆弱 → 用 invalid + harness_feedback 闭环修正，而不是静默猜。

---

## §6 完成门禁（最重要的业务不变量）

### 6.1 干净审计判定

```1397:1409:src/lh_harness/manager.py
def _latest_auditor_is_clean_complete(rounds, *, language="en") -> bool:
    for item in reversed(rounds):
        if item.auditor_status.get("invalid_completion") or item.auditor_status.get("invalid_plan"):
            continue
        if not item.auditor_report.strip():
            continue
        report = parse_audit_report(item.auditor_report, item.round_index, language=language)
        return (
            report.status == "complete"
            and report.integrity_status == "clean"
            and report.contract_audit_status == "aligned"
        )
    return False
```

三条件缺一不可：`complete` ∧ `clean` ∧ `aligned`。  
跳过「伪完成/伪计划」合成轮，避免用 harness_feedback 冒充审计。

### 6.2 伪完成路径

当 `next_step == done` 但判定失败：写入 `_invalid_completion_feedback`，`ManagedRound.next_step = invalid`，带 `auditor_status.invalid_completion=True`，然后 `human_gate("progress")` 并 **continue** 下一轮。

**Manager 不能单方面结束任务。**

### 6.3 终态 `report.json` 状态机

```1426:1439:src/lh_harness/manager.py
    status = (
        "complete" if completion_satisfied
        else "cancelled" if abort_reason == "user_cancelled"
        else "failed" if abort_reason.startswith("provider_")
        else "blocked" if abort_reason == "manager_blocked"
        else "incomplete"
    )
```

`completion_authority: "manager_with_role_auditors"` 写死在报告里——评测/Supervisor 应读这个字段，而不是读最后一轮 Executor 自称。

---

## §7 Human gate：无人 / 有 Dashboard 两条路径

`_GateContext` 打包：hook、rounds、budget、carryover、final_response、failure_reason…

`_human_gate` 返回 `True` = **停止** while：

| 场景 | 无 `human_hook` | 有 hook |
|------|-----------------|---------|
| 已 `completion_satisfied` | 停 | hook 可 continue 再开 |
| `blocked` | abort=`manager_blocked`，停 | 可注入指令后 continue |
| `ask` | abort=`needs_human_input`，停 | 答案写入 carryover |
| 达 max rounds | abort=`max_rounds_exhausted` | 可 `extra_rounds` 延期 |
| 普通 progress | **不停**（return False） | hook 决定 |

Carryover 在 **下一轮 Manager prompt 开头**以高优先级注入（中英不同 heading），并写入 `human_instructions.txt` + event。

无 Dashboard 的纯 CLI：progress 轮连续跑到 done/blocked/max；ask 会硬停——因为没有答题通道。

---

## §8 落盘：三层消费者

### 8.1 目录树（单 run）

```text
{log_dir}/                          # 常在 ~/.lh-harness/... 或 ./.lh-harness/runs/<id>
  report.json                       # Supervisor/评测读的终态
  role_orchestration/
    events.jsonl                    # 实时事件（role_start/done、cancel、runtime_failed）
    report.json                     # 同终态副本
    orchestration_transcript.txt
    rounds/round_001/
      manager_input.txt             # 决策面输入（可审计「Manager 看见了什么」）
      manager_plan.txt
      task_state.txt / task_contract.txt
      executor_prompt.txt / executor_output.txt
      auditor_input.txt / auditor_report.txt
      harness_feedback.txt          # 可选
      {role}_raw_trajectory.jsonl   # 操作员面；决策面不用
      {role}_metadata.json
      screenshots / artifacts…
  manager_episodes/ …
```

### 8.2 `_save_role_result` 的轨迹语义

注释写明：超时取消时 stdout 可能空，但 live tee 已写入 JSONL——优先 **保留 live 更长前缀**，避免擦掉已刷轨迹。  
另：`persist_trajectory_artifacts` 抽截图清单；GUI 还可挂 final screenshot。

### 8.3 事件流

`_append_event(events_path, event, payload)` → JSONL。  
关键 event：`role_harness_start`、`manager_round_*`、`executor_role_*`、`auditor_role_*`、`agent_runtime_failed`、`role_harness_cancelled`、`role_harness_done`、`human_instructions_injected`。

`progress` 回调与 events **并行**：CLI 打印用人话；机器跟跑用 JSONL。

---

## §9 与 DeepSeek Harness 对照（本卷视角）

| | LHH | DSH |
|--|-----|-----|
| 循环单位 | **Round**（Manager±Executor±Auditor） | **Turn/Step**（LLM+tools） |
| 真源 | task_state + auditor 报告 + 文件 | SessionEvent 日志 |
| 「完成」 | 外环门禁 | 通常无独立 Auditor；工具结果即事实 |
| 扩展 | 换 Adapter/Env | 换 Cordis 插件 / Seam |

两者都叫 Harness，但 LHH 解决的是 **长程 computer-use 的验收与状态恢复**；DSH 解决的是 **可替换的自研 Agent 运行时**。

---

## §10 本卷小结

编排内核的灵魂不是某个 Prompt 字符串，而是：

> **决策面只吃审计过的状态；执行面每集清空上下文；完成必须三条件干净审计；一切异常也要留下 report.json。**

下一卷展开 Adapter/Env/插件/只读守卫；源码级 while 分支继续看 [SOURCE.md · Manager 闭环](SOURCE.md#原文--01-manager-loopmd)。



---

# 原文 · ARCHITECTURE_PART2.md

> 原文 `ARCHITECTURE_PART2.md` 全文并入，Mermaid 与表格未改。

# LongHorizon-Harness — 架构文档（第2部分）

> **主题**：AgentAdapter / Environment 如何承载内环 · Claude 角色隔离 · Auditor 结构化与只读守卫 · 预算与 runtime 信号 · Computer-use 插件  
> 源码：[SOURCE.md · Adapter](SOURCE.md#原文--02-adapters-env-auditormd)  
> 2026-08-14

---

## §0 本卷问题

1. Manager 调的「Agent」到底是什么？一次 episode 在 OS 上发生了什么？  
2. 为什么 Auditor 用 Claude 时要 snapshot 工作区？mutation 后编排如何 fail-closed？  
3. 控制头 / acceptance guard / format repair 如何串成「可解析的验收」？  
4. 超时、鉴权失败如何从 CLI stderr 变成编排可消费的 abort？

---

## §1 Protocol 边界：薄，但是硬

### 1.1 `AgentAdapter`

```python
async def run_episode(prompt, env, budget, live_trajectory_path=None) -> EpisodeResult
```

契约：

- **输入**：完整自然语言 prompt（已由 role_prompts 拼好）  
- **副作用**：通过 `env` 改世界（Executor）或尽量只读（Auditor）  
- **输出**：`EpisodeResult(status, actions_log, error, duration_ms, metadata)`  
- **取消**：抛 `CancelledError` 或返回 `status=cancelled`——manager 用 `_run_role_episode` 归一化

Harness **从不**直接调 Anthropic/OpenAI HTTP；密钥与模型都在 CLI 环境变量 / 命令行里。

### 1.2 `Environment`

`exec` / `screenshot` / `upload` / `download`。  
本地实现要点（`local.py`）：

- stdout/stderr **有界尾部**（防截图 base64 撑爆内存）  
- `tee_path`：锚定目录 + `O_NOFOLLOW` 打开轨迹文件，防 symlink 劫持把轨迹写到 run 外  
- 进程组追踪：stop/abort 时能杀整棵 CLI 子进程树  

评测可换 Docker/SSH Environment，**manager 循环零改动**。

---

## §2 `CommandAgentAdapter`：通用「写文件 → 跑命令」路径

```mermaid
sequenceDiagram
  participant M as manager
  participant A as CommandAgentAdapter
  participant E as Environment

  M->>A: run_episode(prompt, budget, tee)
  A->>E: write_remote_text(unique prompt.md)
  A->>A: template.replace prompt_path/timeout
  A->>E: exec("cd workspace && …", tee_path)
  E-->>A: ExecResult
  A->>A: visible_output_parser · detect_runtime_signals · redact
  A-->>M: EpisodeResult
```

关键实现细节：

| 点 | 代码意图 |
|----|----------|
| prompt 文件名含 uuid | 并发 run/角色不互盖 |
| `replace` 非 `format` | Codex `-c '{…}'` 花括号 |
| `hidden_paths` notice | 禁止 Agent 读 harness 账本当证据 |
| `redact_secrets` | 日志与 metadata 脱敏 |
| timeout → `status=timeout` | 与 exit_code 错误分开 |

`assistant_visible_output` 进 metadata；manager 的 `_visible_output` 优先用它，避免把整段 stream-json 塞进 Auditor prompt。

---

## §3 Claude Code Adapter：角色策略 + Auditor 只读快照

### 3.1 构造：权限减工具，而不是换循环

`ClaudeCodeAdapter` 继承 `CommandAgentAdapter`，按 `ClaudeRole`（manager / gui_executor / cli_executor / gui_auditor / cli_auditor…）取 `policy_for_role`：

- `disallowedTools` + path deny（hidden_paths）  
- 可选 MCP computer-use（`--mcp-config`，`--strict-mcp-config` 防用户全局 MCP 漏进）  
- **禁止** `add_dirs`：角色隔离要求任务文件在 workspace 内  
- 环境变量：`CLAUDE_CODE_DISABLE_AUTO_MEMORY`、`SKIP_PROMPT_HISTORY`、`LH_HARNESS_CLAUDE_ROLE=…`  

命令形态：`claude --print --output-format stream-json … < {prompt_path}`。

### 3.2 Auditor 特有：workspace snapshot

```116:159:src/lh_harness/adapters/claude_code.py
    async def run_episode(...):
        before = snapshot_workspace(...) if is_auditor_role(self.role) else None
        result = await super().run_episode(...)
        ...
        if before is not None:
            after = snapshot_workspace(...)
            diff = workspace_snapshot_diff(before, after)
            result.metadata.update(diff)
            if snapshot_errors:
                result.status = "error"  # fail-closed
```

若 Auditor 改了工作区文件：`verifier_workspace_mutation_detected` 等 metadata 进入 `auditor_agent.audit_report_from_episode_result`，通常升级为 **integrity violation + blocked**，并附「必须由 Executor 修复」文案。  
快照检查失败本身也会把 episode 标 error——**宁可不信审计，也不收污染证据**。

Codex 路径有平行的 computer-use / 配置插件（`plugins/codex_*`），原则相同：能力在 Adapter/Plugin，纪律在 Manager/Auditor。

---

## §4 Auditor 结构化管道

```mermaid
flowchart TD
  R[EpisodeResult] --> H{status!=done 或 hard runtime signals?}
  H -->|是| B[AuditReport blocked · runtime_failure 文案]
  H -->|否| E[extract + compact report text]
  E --> C{valid control header?}
  C -->|否| I[合成 invalid header 报告]
  C -->|是| P[infer status / integrity / contract]
  P --> G[acceptance constraint guard]
  G --> M{workspace mutation?}
  M -->|非法| V[violation + blocked + ledger]
  M -->|否| OK[AuditReport]
```

### 4.1 控制头（前三行协议）

典型要求（中英）：状态行、完整性行、契约审计行。  
`_parse_status_control_header` 只看第一非空行；缺头 → 整份作废为「格式错误」类报告，触发 manager 的 format repair。

### 4.2 Acceptance guard

```351:364:src/lh_harness/auditor_agent.py
def _apply_acceptance_constraint_guard(...):
    if status != "complete" or not _has_blocking_acceptance_constraints(report_text):
        return report_text, status, contract_audit_status
    # 降级为 incomplete，并可能撤销 aligned
```

防止模型一边写「还有 blocking acceptance」，一边控制头标 `complete`。

### 4.3 Format repair（manager）

主 Auditor episode 后 `_auditor_report_with_format_repair`：

- 判定是否需要修（`_should_repair_auditor_format`）  
- 再用（默认同）auditor adapter 跑 `build_role_auditor_format_repair_prompt`  
- 缩短预算 `_format_repair_budget`  
- 仍失败则带着不合格文本继续——下一轮 Manager 会看见不干净状态，不会误 complete  

---

## §5 预算、失败分类、runtime signals

### 5.1 预算

`HarnessConfig` 四分预算：manager / gui_executor / cli_executor / auditor。  
默认 manager/auditor 更短（规划与验收不应跑半小时 tool loop），executor 默认 1800s 级。

### 5.2 Runtime signals

`detect_runtime_signals(stdout)` 扫 CLI 输出，识别鉴权失败、配额、明显崩溃模式等。  
硬信号 → Auditor 直接 blocked；Manager/Executor 侧 `classify_agent_runtime_failure` → 编排 `abort_reason` 常以 `provider_` 前缀 → `_final_report` 映射为 `failed`。

**设计意图**：把「供应商挂了」与「任务做不完」分开，Web 才能展示真实错误（`failure_reason`）。

---

## §6 Computer-use 插件层

`plugins/`：安装 npm 包、写 Codex/Claude 配置、社区 computer-use 变体。  
`lh-harness doctor` 检查 Node、CLI、插件健康。  

插件 **只增强 Executor 桌面能力**；不改变：

- `parse_role_manager_next_step`  
- `_latest_auditor_is_clean_complete`  
- `run()` 崩溃护栏  

若插件导致 Auditor 误改文件，仍靠 snapshot fail-closed 兜住。

---

## §7 端到端：一集 GUI Executor 在机器上发生了什么

```text
manager
  → ClaudeCodeAdapter(role=gui_executor).run_episode
       → 写 /tmp/.../round_003_executor_<uuid>.md
       → env.exec:
            cd $WORKSPACE &&
            ANTHROPIC_API_KEY=… CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 …
            claude --print --output-format stream-json
              --disallowedTools … --mcp-config … --model …
              < prompt.md
       → LocalEnvironment:
            进程组启动、stdout tee 到 round_003/executor_raw_trajectory.jsonl
            有界捕获、timeout 杀组
       → 解析 visible_output、runtime_signals
  → _save_role_result（保留 tee、抽截图）
  → 拼 auditor prompt（塞入 executor_output 裁剪后文本）
```

同一模式替换 `codex` 命令模板即可换后端；Manager 无分支。

---

## §8 本卷小结

> **Adapter 负责「如何启动一种 Agent」；Environment 负责「命令跑在哪」；Auditor 管道负责「文本如何变成可门禁的结构」；mutation/snapshot 负责「验收角色不能污染世界」。**

下一卷：CLI/Supervisor/Web 如何把上述内核变成可运营的多 run 系统。



---

# 原文 · ARCHITECTURE_PART3.md

> 原文 `ARCHITECTURE_PART3.md` 全文并入，Mermaid 与表格未改。

# LongHorizon-Harness — 架构文档（第3部分）

> **主题**：CLI 与 Web 入口 · RunSupervisor 进程模型 · ControlBus/人机 · 终态合并 · 评测仓 · 扩展食谱  
> 源码：[SOURCE.md · Supervisor](SOURCE.md#原文--03-supervisor-webmd)  
> 2026-08-14

---

## §0 本卷问题

1. `lh-harness run` 与 `lh-harness web` 如何共用同一 `manager.run`？  
2. Supervisor 为什么必须「读 report.json + 进程身份」，而不能只看 exit code？  
3. 审批/注入指令如何进入下一轮 Manager，而不破坏 MEA 隔离？  
4. 改完成条件时，要同步改哪些边界？

---

## §1 入口与组装

```mermaid
flowchart TB
  subgraph CLI["cli.py"]
    RUN[run 子命令]
    WEB[web 子命令]
    DOC[doctor / plugin / init]
  end

  subgraph Assemble["组装层"]
    CFG[config.toml / flags]
    ADP[ClaudeCodeAdapter / CodexAdapter × 角色]
    ENV[LocalEnvironment]
  end

  subgraph Kernel["内核"]
    M[manager.run]
  end

  subgraph Ops["多 run 运营"]
    RS[RunSupervisor]
    API[webapi FastAPI]
    BUS[ControlBus]
  end

  RUN --> Assemble --> M
  WEB --> API --> RS
  RS -->|spawn worker 命令| Assemble
  Assemble --> M
  M <-->|human_hook| BUS
  API --> BUS
```

**原则**：Web 不重新实现 MEA；它 spawn 的 worker 最终仍进 `manager.run`。  
角色模型/后端在组装层分叉，内核只收 `AgentAdapter` 实例。

### CLI `run` 典型组装

1. 解析 task、workspace（默认启动 cwd）、log_dir、max rounds、每角色 model/agent  
2. 构造最多 5+ 个 adapter（manager / gui·cli executor / gui·cli auditor），可全部指向同一后端  
3. `LocalEnvironment(workspace=…)`  
4. 可选 attach ControlBus（与 Web 同语义）  
5. `await manager.run(task=…, env=…, config=…, agents…, human_hook=…, progress=print)`  

`progress`：把 `round_start` / `role_done` / `run_done` 打到控制台——与 events.jsonl 互补。

---

## §2 RunSupervisor：进程与证据

### 2.1 职责清单

| 职责 | 非职责 |
|------|--------|
| create/list/status/stop/abort/resume | 解析 `Next: gui` |
| 幂等键防双 worker | 写 Auditor 控制头 |
| 合并 lifecycle（活着吗 + report 说什么） | 替换 Adapter |
| 把控制命令写入 Bus | 维护 task_state |

### 2.2 为什么 exit code 不够

历史问题（manager 注释）：内核崩溃若无 `report.json`，Supervisor 可能误报完成。  
因此：

1. **所有路径**经 `manager.run` 写 terminal 记录  
2. `_refresh` / `_terminal_status_for_exit` 读 report：`completion_satisfied`、`abort_reason`、是否缺 evidence  
3. `_missing_completion_evidence`：status 像完成但证据不足 → 降级  

### 2.3 进程安全细节（架构相关）

- run_id 校验防路径穿越  
- PID + start time / command fingerprint：防 PID 复用误杀  
- process group 信号：Claude/Codex 子进程一起收  
- idempotency 文件：同键冲突抛 `IdempotencyConflict`  

这些与 MEA 无关，但对「长跑 + Web」是生产正确性。

---

## §3 ControlBus 与 human_hook 时序

```mermaid
sequenceDiagram
  participant UI as Dashboard
  participant API as webapi
  participant Bus as ControlBus
  participant W as worker
  participant G as _human_gate
  participant Mgr as next Manager prompt

  Note over W: MEA round 进行中…
  W->>G: human_gate(outcome)
  G->>Bus: 经 human_hook 等待/读取
  UI->>API: approve / inject / answer ask
  API->>Bus: 写入命令
  Bus-->>G: {action, instructions, extra_rounds}
  alt stop
    G-->>W: True → 出 while → report.json
  else continue
    G->>G: carryover_instructions / round_budget+=
    G-->>W: False
    W->>Mgr: 下一轮注入 carryover
  end
```

**隔离仍然成立**：人话进入的是 **下一轮 Manager 输入**，不是直接改 `rounds[].auditor_report`。  
操作员不能「手改审计通过」；只能影响规划与是否续跑。

`ask` 路径：Manager 计划含 `问题:` / `Question:`；gate 把答案放进 instructions。  
无 hook 的 CLI：ask → 停，abort=`needs_human_input`。

---

## §4 Web 事件投影

```text
磁盘 events.jsonl + 轨迹 tee + status
  → webapi/events · snapshot
  → websocket/HTTP
  → frontend/core runFeed（纯 TS）
  → frontend/web UI
```

前端 **重建**应依赖 run 目录，不依赖浏览器内存。  
`frontend/core` 可单测，避免 UI 与协议缠死。

打包：CI 建 `lh_harness/_frontend/web/dist`，wheel `artifacts` 带上；无 Node 的源码安装可跳过。

---

## §5 评测仓关系

```text
LongHorizon-Harness/src/lh_harness   ← 产品内核
eval/WeaveBench-harness              ← 基准 + 可能独立 cua_harness 变体
eval/OSWorldv2-harness
eval/TB-harness
```

读评测 README 时拆开：

- **任务定义 / 评分**（基准自有）  
- **编排是否复用本仓 manager**（有的嵌套了类似 MEA 的 cua_harness）  

论文数字（WeaveBench / OSWorld / TB）论证的是：**同模型同后端，换 Harness 外环** 的增益——与 PART1 公理一致。

---

## §6 对照表（系统级）

| 维度 | LHH | DeepSeek Harness | MAF 类框架 |
|------|-----|------------------|------------|
| 内环所有权 | 外部 CLI Agent | 自研 loop | SDK Agent |
| 外环 | **强制 MEA** | 可选 Goal/Workflow | Workflow/Orchestrator |
| 验收 | **独立 Auditor + 门禁** | 工具结果/插件 | 应用自定 |
| 多 run | Supervisor + 文件账本 | Profile/进程内多 Agent | 视托管 |
| 语言 | Python + TS UI | TypeScript | 多语言 |

---

## §7 扩展食谱（带「改哪里」）

| 需求 | 改 | 别改 |
|------|----|------|
| 支持新 CLI Agent | 新 `AgentAdapter` 或扩 command_template | `_run_impl` 状态机 |
| 远程执行机 | 新 `Environment` | role_prompts 路由集合 |
| 更严完成条件 | `_latest_auditor_is_clean_complete` + `_final_report` + Supervisor `_missing_completion_evidence` | 只改前端文案 |
| 新审批种类 | ControlBus 命令 + dashboard + human_hook 契约 | 让 UI 直接写 auditor_report |
| 调角色提示 | `prompt_texts.py` / `role_prompts.py` | Adapter 里硬编码长提示 |
| 新评测 | eval 仓 + Environment | fork 一份 manager「评测专用逻辑」除非必要 |

---

## §8 故障联排清单

| 症状 | 决策面 | 执行面 | 运营面 |
|------|--------|--------|--------|
| 一直跑不完 | next_step 是否总 gui/cli；max_rounds | executor 是否 timeout | budget / extra_rounds |
| 误报完成 | clean complete 三条件 | — | Supervisor 是否忽略 evidence |
| 审计总 blocked | 控制头/repair | Auditor mutation | — |
| Web 停不掉 | — | 进程组 | `_signal` / pid identity |
| 注入无效 | carryover 是否进 manager_input.txt | — | Bus 是否写入该 run |

---

## §9 本卷小结

> **组装层选后端；内核跑 MEA；Supervisor 管进程与证据；Bus 只把人话送回 Manager；前端只做投影。**

三卷 + 上文核心运行时 + [SOURCE.md](SOURCE.md) 构成完整说明。改行为以源码与测试为准。



---

# 设计深化与工程边界

> **评审基线：** 本地源码提交 `b498162fc1b96ff469146f04a698c829c89e3eab`；核对工作区日期为 2026-10-15。源码根为 `/Users/gqli/work/deepagents/LongHorizon-Harness`。本次核对的运行时文件未显示本地修改；源码仓库另有 `doc-sn/ARCHITECTURE_PART1.md` 的已有修改，本次未修改它。
>
> **证据纪律：**「现有」表示在该版本的源码中观察到；「推论」表示由已观察边界推导的风险，未等同于已复现缺陷；「建议」是待实现、待评测的设计。本章不是宣布实现了新能力。原文代码行号是历史定位，当前定位以 [SOURCE.md 的补充索引](SOURCE.md#当前源码校准与验证索引) 为准。

## D1. 总体评审：从运行说明走向工程契约

现有文档的强项是 MEA 闭环、角色可见性、控制头解析、Adapter 和 Supervisor 分工。欠缺的是跨模块不变量、证据有效期、外部副作用、恢复边界与可证伪的验收标准。增加深度不应继续重复“规划—执行—验证”，而应回答“什么条件下这一轮的验证还有效”。

| 优先级 | 现有基础 | 尚需补足 | 若缺失的后果 | 本章位置 |
|---|---|---|---|---|
| P0 | `complete/clean/aligned` 门禁 | 审计绑定哪版任务、哪版产物、哪次环境观察 | 旧证据支持新完成声明 | D4–D5 |
| P0 | `rounds.jsonl` + resume | 执行后、记账前崩溃的副作用对账 | 重发消息、重复提交、重复上传 | D6 |
| P0 | Auditor 权限与快照检查 | 信任边界、检测覆盖、隔离等级 | 将事后检测误称为安全沙箱 | D3、D8 |
| P1 | 最大轮次、角色超时 | 总成本预算、停滞判定、重试分类 | 能一直跑，却不能经济地收敛 | D7 |
| P1 | 文件事件与 Web 投影 | 账本一致性、消息确认、UI 缺口恢复 | 页面状态与实际执行状态分裂 | D6、D9 |
| P1 | 多后端 Protocol | 语义能力矩阵和契约测试 | 接口可调用，但权限或结果语义不一致 | D10 |
| P1 | 基准入口说明 | 等预算对照、假阳性与消融 | 增益可能来自更多计算而非外环 | D11 |
| P2 | 模块职责图 | 决策记录、阶段验收、数据留存策略 | 演进引入第二套事实源 | D12 |

P0/P1/P2 是本次设计评审建议，不是对现有项目缺陷的已确认严重性分级。

## D2. 长程系统的目标、不变量与非目标

### D2.1 不只“能跑更久”，而是四个目标

1. **目标连续性：** 任务拆分、上下文刷新、续跑后，原始要求仍可逐项追溯。
2. **证据连续性：** 每项可信进度有来源、适用范围和失效条件，而不是只保留一句总结。
3. **副作用可解释性：** 崩溃后能区分“没有执行”和“可能已执行但没有记录”。
4. **资源可控性：** 在预算或风险边界处停止，而不是靠无限轮次掩盖失败。

当前源码直接支撑角色闭环、落盘、轮级续跑等基础；后两项的完整保证还需要工程协议。

### D2.2 应明确写进测试的不变量

| 编号 | 不变量 | 当前情况 / 建议 |
|---|---|---|
| I1 | Executor 自称完成不能成为完成授权 | 现有完成门禁支撑 |
| I2 | 最新有效审计不通过，不能退回更旧的通过审计 | 当前 `_latest_auditor_is_clean_complete` 在首个有效非空报告处返回；需保持此行为 |
| I3 | 契约或产物版本变化，相关通过结论失效 | 建议增加版本绑定；当前门禁未显式比较版本 |
| I4 | 账本完整性未知时，不能依据缺损历史宣布完成 | 建议补充恢复完整性检查 |
| I5 | 取消后没有新动作获授权；已发出的动作必须对账 | 建议明确授权截点；取消不能撤销已发生的副作用 |
| I6 | Final response 只能解释终态，不能制造完成证据 | 现有职责应保持；见源码校准 |
| I7 | 同一共享可写环境同一时刻只有一个动作授权主体 | 建议增加 workspace/desktop 级所有权；run 级幂等不能替代它 |
| I8 | 不可信任务数据不能修改验收门禁或控制账本 | 建议按权限边界保证，不能仅靠 Prompt |

### D2.3 非目标

- MEA 不是模型正确性的证明；Auditor 也可能遗漏、误判或被注入。
- 全新 episode 不是全新世界：文件、浏览器登录态、桌面进程、远程服务仍然共享。
- 轮级 resume 不是指令级回放，也不表示从上一次 GUI 点击精确继续。
- `events.jsonl` 可观察，不自动等于完整的事件溯源系统。
- “只保留验过的进度”是**认知状态**纪律，不意味着撤销未通过审计的物理改动。

最后一条尤其重要：Executor 做坏了文件、发送了消息或改变了远程状态，审计失败不会自动把真实世界恢复到上一轮。

## D3. 信息隔离不等于权限隔离

### D3.1 两种隔离必须分开描述

**现有：** Prompt 构建器不把 raw trajectory 装入下一轮 Manager 输入，Executor 只接收点名的历史报告。这是输入组装约束。

**推论：** 如果 Adapter 仍能读取同一个磁盘，Prompt 中“看不到”不代表 OS 权限上“读不到”。隐藏路径、工具限制、文件权限应单独核对。角色名称、三个独立 episode、三个不同模型，也都不能单独保证安全独立性。

建议将“谁看见什么”解释为**默认 Prompt 信息流**；真正权限保证采用以下矩阵，逐个后端验证，不从一个后端类推其他后端：

| 对象 | Manager | Executor | Auditor | Supervisor |
|---|---|---|---|---|
| 原始任务与冻结契约 | 读 | 读相关部分 | 读完整验收要求 | 读 |
| 工作区产物 | 默认限制，只用于规划必要观察 | 授权范围内写 | 默认只读；动态验证用隔离副本 | 不作为任务执行者 |
| raw trajectory | 操作员可查，不装入默认决策输入 | 不作为事实授权 | 仅作待核验线索 | 展示/存档 |
| canonical ledger / completion 字段 | 不直接写 | 不直接写 | 不直接写 | 编排内核与监督协议负责 |
| 人工控制指令 | 通过受控输入接收 | 经 Manager 分配 | 不改验收事实 | 鉴权、记录、送达 |
| 外部网络与桌面状态 | 按需最小授权 | 逐类动作授权 | 默认拒绝写副作用 | 不继承任务任意权限 |

该表是目标权限设计，**不是当前全部后端已经满足的清单**。

### D3.2 审计报告应是“带来源的断言”

建议将一条事实表示为：

```text
Assertion = requirement_id + verdict + evidence_refs
          + subject_version + verification_method
          + observed_at + validity_conditions
```

三类内容不能混为一谈：

- Executor 输出：“我已上传” → **待核验声明**。
- Auditor 观察：“服务端列表存在对应对象，内容摘要匹配” → **有范围的验证结论**。
- Manager 总结：“下一轮可以做发布说明” → **规划派生状态**。

可信状态的层级应是：原始要求/授权变更 → 可重查证据 → 审计结论 → 规划摘要。摘要可以压缩，证据引用和未满足项不应在压缩中丢失。

### D3.3 “独立 Auditor”的真实收益与上限

收益来自执行与验收解耦：执行者不负责裁定自己的输出。但二者可能共享模型偏见、任务材料、机器环境和提示注入入口。因此不能把多个角色误当成多个统计独立的验证器。

建议优先增加**验证方法多样性**：结构校验、测试、文件内容摘要、服务端状态查询、GUI 观察，最后才是追加一个 LLM 意见。通过多个来源也应标注共享依赖，避免同一份错误输出被重复引用后看起来“证据很多”。

## D4. 任务契约：从自由文本变成版本化验收对象

**现有：** `current_task_state` 和 `current_task_contract` 从 Manager 文本提取并跨轮传递。文本灵活，但缺少机器可比较的需求覆盖与版本关系。

**建议：** 原始任务保持不变；另建需求条目和授权变更记录，Manager 可以提出契约修订，却不能通过改写文本降低验收标准。

```json
{
  "schema_version": 1,
  "contract_id": "C-001",
  "revision": 2,
  "original_task_digest": "sha256:<task-bytes>",
  "requirements": [
    {
      "id": "R-001",
      "description": "交付可在目标环境打开的最终文件",
      "acceptance": "存在、格式有效、目标应用成功打开",
      "verification_methods": ["file_check", "application_open_check"],
      "risk": "normal"
    }
  ],
  "authorized_change_refs": ["H-003"]
}
```

这是示意契约，不是现有 `HarnessConfig` 或 `AuditReport` 字段。摘要算法应对确定的编码和规范化规则计算；仅记录摘要不能证明内容真实。

### D4.1 总任务契约与本轮子任务契约分层

- **总任务契约**：包含所有要求、允许动作、禁止动作和终态验收条件。
- **本轮契约**：本轮要改变哪些对象、前置条件、成功观察、可用工具、失败处理。
- **审计范围**：本轮通过不等于全局完成，必须标明 `subtask` 或 `global`。

最终审计需要覆盖所有 R-id；存在 `unknown`、未执行或证据过期的条目时，不应 complete。

### D4.2 契约变更的失效规则

1. 人工追加要求形成新 revision，并保留旧要求与变更来源。
2. 对发生变化的要求、依赖它的产物和审计结论标记 `stale`。
3. Manager 重新规划必要工作，Auditor 重新验收受影响条目。
4. 未受影响的证据可复用，但必须给出复用理由。

反例：旧任务“生成 PDF”已通过，用户追加“每页加水印”，Manager 直接 `done`。旧审计只验证了旧契约，不能支撑新任务完成。

## D5. 完成门禁：状态合法之外，还要证据适用

### D5.1 当前门禁的精确边界

**现有：** `_latest_auditor_is_clean_complete(rounds, language=...)` 逆序寻找有效非空报告，解析并检查 `complete ∧ clean ∧ aligned`。它不接收当前契约摘要、当前工作区摘要或环境代次参数。

**推论：** 仅从该函数和调用路径，无法得到“审计之后环境未变化”“审计绑定当前要求”的保证。这是待验证的设计缺口，**本次未实际复现误完成**。特别是 resume、人工追加要求、共享工作区被其他进程修改时，需要额外规则。

### D5.2 建议完成谓词

```text
eligible(audit, current) =
    valid_schema(audit)
    AND audit.status == complete
    AND audit.integrity == clean
    AND audit.contract_alignment == aligned
    AND audit.scope == global
    AND audit.contract_revision == current.contract_revision
    AND every_requirement_has_valid_pass_evidence(audit)
    AND evidence_subjects_match_current_artifacts(audit, current)
    AND no_unreconciled_side_effects(current)

complete = manager_requests_done AND eligible(latest_applicable_audit, current)
```

`latest_applicable` 不能解释为“跳过较新失败，找到旧通过”；较新失败或相关环境变化必须撤销旧结论。无可用证据时降级，不凭模型推断补齐。

### D5.3 时效不是统一 TTL

| 证据 | 推荐有效性判据 |
|---|---|
| 本地文件格式/内容 | 内容摘要、路径身份、必要依赖一致 |
| 测试通过 | 代码/依赖/配置版本一致；测试对象范围明确 |
| GUI 窗口或页面观察 | 目标应用/文档身份 + 观察时间；相关动作发生后重查 |
| 远程对象上传成功 | 服务端对象 ID、版本、内容查询；不能只看客户端日志 |
| 发消息/提交订单等副作用 | 服务端回执 + 动作意图绑定；未知状态须对账 |

“所有证据有效 10 分钟”会同时过严和过松：不变文件可以长期复用，远程易变状态可能立即失效。

### D5.4 审计格式修复不能升级事实

**现有：** format repair 用于把报告修成可解析格式。

**建议：** 将“格式转换”与“重新验证”标成不同事件。纯转换必须保留原始证据引用、范围和结论，不能把 `unknown` 修成 `pass`。如果 repair Agent 重新运行验证，则记录新的验证来源与预算，不再将它统计成纯格式修复。

### D5.5 审计到完成之间的竞态窗口

即使审计绑定了摘要，验证后再次修改产物仍可能使它失效。建议在最终验收阶段获取目标资源的独占授权，核对版本并提交完成；Final response 使用只读能力，不能在解释结果时又修改交付物。

```mermaid
flowchart LR
    C[当前契约 revision] --> G{全局完成门禁}
    A[审计状态与逐项证据] --> G
    V[当前产物版本] --> G
    X[副作用对账状态] --> G
    G -->|匹配且覆盖完整| F[提交完成摘要]
    G -->|过期或未知| R[补验或重新规划]
    F --> P[只读生成最终回复]
```

独占只能约束参与协议的写者；外部服务仍可能被其他用户修改，因此远程结论需注明“在何时、对哪个版本验证成立”。需要持续保证时另设监测，不把一次完成验收包装成永不失效的承诺。

## D6. 持久化与恢复：账本、产物和真实世界不是同一个事务

### D6.1 当前可恢复什么

**现有：** `resume=True` 读取 `role_orchestration/rounds.jsonl`，恢复 `rounds`、最后计划、task state、task contract 和轮号；新的轮次从已有历史继续。配置中的轮次预算在 resume 时作为**新增预算**使用。

**不应夸大：** 这不恢复 CLI 内部上下文、浏览器 DOM、桌面窗口布局，也不把远程动作回滚。历史干净审计可以参与恢复后的完成判定；是否仍适用需要 D5 的证据规则。

### D6.2 事实源必须有明确优先级

| 对象 | 建议角色 | 不应承担的角色 |
|---|---|---|
| round ledger | 轮级编排事实源 | 外部服务实际成功的唯一证明 |
| 产物与服务端回执 | 任务结果事实源 | 自动授权完成 |
| events | 实时投影、诊断、因果关联 | 缺完整提交协议时替代 ledger |
| `report.json` | 可重建的终态摘要 | 凭单个文件覆盖互相矛盾的执行证据 |
| UI 状态 | 只读投影 | 修改审计或完成条件 |

**现有：** `_record_round` 先追加本地 ledger，再写环境侧 `round.json`，再发事件。这几个步骤不能仅因“都写文件”就视为原子事务。

### D6.3 必须覆盖的崩溃窗口

| 崩溃位置 | 已知状态 | 恢复策略建议 |
|---|---|---|
| 动作未启动前 | 无副作用 | 重建规划并执行 |
| 动作运行中 | 副作用未知 | 先探测，禁止直接重复不可逆动作 |
| 动作成功、审计前 | 可能有产物，无验收 | 重新审计产物，不默认重做执行 |
| 审计成功、ledger 提交前 | 有审计文件，提交状态未知 | 检查文件完整性与版本，再对账提交 |
| ledger 已写、远程镜像或事件失败 | 本地已有记录，其他投影缺口 | 从事实源补齐投影，不再执行动作 |
| 终态生成后、回复或 UI 更新前 | 任务状态与展示分离 | 重建回复/展示，不改变验收事实 |
| 账本损坏、缺轮、重复轮或被截断 | 恢复历史不完整 | 标记 degraded；保留诊断，不默认 complete |

源码读账本会跳过部分不合法记录；这有容错收益，但“读取到合法行”不等于“完整恢复了历史”。建议记录跳过数量、重复索引、截断情况，并禁止在恢复完整性未知时复用旧完成授权。

### D6.4 最小提交协议，而非立即上分布式系统

建议先采用单写者、本地 manifest 和版本化记录：

```text
prepared → executor_finished → audit_finished → committed
               ↓ 副作用未知
          reconciliation_required
```

- 每轮有 `run_id/round_id/attempt_id`；retry 是新 attempt，不覆盖原始证据。
- 完成产物文件先写临时路径，再原子替换；若要求掉电持久性，还需明确文件/目录同步策略。
- `committed` manifest 指向已写完的输入、产物和审计摘要；重建时先验证引用。
- `events` 和终态摘要允许重建；canonical ledger 丢失或篡改则 fail-closed。
- 停止、续跑、重试保存同一因果链，不能用新进程 PID 替代逻辑身份。

以上是演进建议；原子替换单个文件也不能使多个文件与远程服务成为同一事务。

### D6.5 外部副作用采用意图—回执—对账

```text
Intent(action_id, target, payload_digest, approval_ref)
  → Execute
  → Receipt(remote_id, status, observed_at)
  → Reconcile
```

支持幂等键的服务可传 `action_id`；不支持时先查询目标状态或要求人工确认。只能提供至少一次执行时，应说明重复风险，不能宣称跨 GUI、文件系统和网络实现 exactly-once。

例：点击“发送”后机器断电。恢复先查询已发送记录与目标收件人；不知道是否发送就停在 `reconciliation_required`，而不是让新 Executor 再点一次。

## D7. 长程收敛与预算治理

### D7.1 当前预算的边界

**现有：** `EpisodeBudget` 按角色限制时间，运行受轮次预算约束，可由 human gate 增加轮次。它们是基本运行限制，不等同于全局费用、Token、磁盘或总墙钟预算。

**建议：** 设置四层预算，使用逻辑 run 累计值，不能被 resume 重置：

1. 角色 episode 时间/Token/费用上限。
2. 单 round 的合计资源上限，包含 repair 和重试。
3. 整个 run 的累计时间、费用、动作数、日志容量上限。
4. 共享机器的并发、桌面占用、磁盘余量和后台进程上限。

后端没有 usage 时记录 `unknown`；估算费用不能冒充服务商真实账单。

### D7.2 明确 round 与 episode 的区别

一轮可能含 Manager、Executor、Auditor、format repair；完成或阻塞门禁还可能生成 Final response。只用轮数比较成本会漏计这些调用。`max_total_episodes` 的名字尤其容易误导，应在外部配置说明中标出其实际轮次语义，并计划兼容迁移到 `max_rounds` 等明确名称。

设路由执行轮有 N 轮、管理/终态轮有 D 轮、修复调用 F 次、最终回复调用 Q 次，则基本角色调用近似为 `3N + D + F + Q`，不包括额外重试；各角色费用必须分别累计，而不能乘一个平均每轮价格。

### D7.3 停滞检测以验证结果为依据

建议定义 verified progress vector：`(有效通过需求集合, 未解决阻塞集合, 产物版本, 重复失败签名)`。

- 文本 plan/state 改变不算实质进度。
- 同一缺口重复出现时减少盲目 retry，要求改变执行或验证策略。
- 若产物反复修改又回退，识别振荡，而不是只看“有修改”。
- 使用可配置观察窗口；窗口阈值是待实验的策略，不在文档里伪装成普适常数。

不要为满足“单调进度”把已失效的通过条目锁死；相关产物变化后撤销通过才是正确行为。

### D7.4 重试必须分类

| 失败类型 | 推荐策略 |
|---|---|
| 格式错误 | 限次格式修复；不改变事实 |
| 临时网络错误/限流 | 有界退避；先判断副作用是否已发生 |
| 密钥错误/权限不足 | 停止并请求行动；避免重复消耗 |
| Executor timeout | 保留部分结果，下一轮先查实际环境 |
| Auditor timeout | 没有通过证据；可补审计，不默认重做执行 |
| 审计发现契约缺口 | 重规划，不能只重试同一 Prompt |
| 快照/账本完整性失败 | 降级或阻塞，不回退到“相信执行者” |

## D8. 安全与验收可执行性的冲突

### D8.1 威胁模型

| 入口 | 风险 | 建议控制 |
|---|---|---|
| 网页、文档、日志、依赖说明 | Prompt injection，诱导改契约或泄露凭据 | 标为不可信数据；控制面和任务内容分区 |
| 共享工作区 | Executor 改写测试、验收脚本或审计报告 | 可信验证器置于独立只读区；校验摘要 |
| CLI 模板和配置 | 命令注入、错误权限继承 | 明确模板可信来源；新增配置先校验再运行 |
| 控制目录与 run 路径 | 链接置换、越权读取/写入 | 延续 nofollow 硬化；按用户与 run 鉴权 |
| 远程动作和 GUI | 删除、发送、提交等不可逆副作用 | 动作级授权与回执；关键动作人工审批 |
| trajectory、截图与 Prompt | 凭据/个人信息进入日志 | 源头最小化、脱敏、访问控制、留存期限 |

现有脱敏和路径硬化是基础；不能从“用了 redact”推导所有截图、编码秘密和文件内容均已安全。

### D8.2 快照是检测，不是阻止

**现有：** Claude Auditor 路径在 episode 前后采集 workspace snapshot，并将变化放入 metadata；异常和违规进入审计失败路径。

**边界：** 文件前后差异未必覆盖工作区外文件、浏览器状态、远程服务、副作用发生后又恢复原样等情况。实际覆盖应按 snapshot 实现与配置验证，不能据此宣称 Auditor 对整台机器只读。

建议按风险分级：本机受信 Agent → 工具权限 + 快照检测；不可信输入 → 更强 OS 隔离；远程写风险 → 代理策略和网络权限。不可撤销动作不应只依赖事后发现。

### D8.3 Auditor 要运行测试，怎么办？

测试、编译、打开文档可能写缓存或生成输出，完全拒绝写可能让验收不可执行。建议提供 **ValidationEnvironment**：

- 原始交付物保持只读，在临时副本/隔离环境执行动态验证。
- 显式列出可写 scratch、缓存目录和允许网络范围。
- 验证前后对原始产物做身份检查，验证输出作为单独证据保存。
- 只能观察本机 GUI 的任务标注验证限制，不能假装与文件副本验证等价。

## D9. 人机控制、状态投影与可观测性

### D9.1 路由状态、任务状态、进程状态分离

`Next: ask` 是 Manager 路由；等待人工是运行状态；worker 是否存活是进程状态；`incomplete/complete` 是验收状态。这四者不应压缩成一个 UI 字符串。

建议状态 API 返回分别命名的字段，并说明恢复动作：例如等待人工时进程可以活着，但没有新动作在执行；进程退出而 report 缺失时状态是“终态未知/需诊断”，不是 completed。

### D9.2 控制指令的建议最小协议

```text
command_id + run_id + expected_generation
+ kind + created_at + authorization_ref
→ accepted → applied / rejected / expired
```

- UI “已发送”不等于 Manager “已应用”。应用轮号与结果应可查。
- 现有 Supervisor 已有 resume epoch 生命周期基础；建议将审批的作用域绑定到对应代次和动作，避免旧审批授权新一代 worker 的不同动作。
- 指令内容和审计事实分开：人工可以改任务或批准风险，不能靠点按钮让未知验证变通过。
- stop 是终止未来授权，不是回滚；abort 后必须展示未对账副作用。

上述字段是建议协议，需与现有 ControlBus 的送达/消费机制适配，不另造第二套控制总线。

### D9.3 从“日志很多”变成“能定位原因”

建议事件共用：`run_id/round_id/episode_id/attempt_id/parent_event_id`、事件序号、角色、schema version、持续时间、失败分类、证据引用。跨机器时间戳用于展示，因果排序以序号和父关系为准。

关键指标：

- **完成可靠性：** completion rejection、失效证据使用、独立复验不通过。
- **收敛效率：** 每个有效通过需求的费用/时间、停滞轮比例、repair 比例。
- **恢复质量：** 对账耗时、重复副作用、ledger gap、恢复后再次审计失败。
- **操作体验：** 指令接受到应用的延迟、停止到进程退出的延迟、待审批时长。

GUI 用户数据、路径、任务文本不宜直接作为高基数 metric label。需要诊断时通过受控 trace 引用。

UI 重连建议带 cursor；出现事件序列缺口时取 snapshot 重建。投影必须幂等，允许补发，不得因为事件重复而启动第二个动作。

### D9.4 数据留存是长程运行的一部分

建议为 Prompt、审计证据、trajectory、截图分别规定保存期限、容量上限、访问者和删除方式。优先保留可复验交付物及必要回执；体积很大的 raw trajectory 可按策略归档，但不能删掉门禁唯一引用的证据后仍保持“可复验”的声明。人工导出和共享也应脱敏；删除策略须能解释会失去哪些诊断或复验能力。

## D10. Adapter 与 Environment 的语义契约

**现有：** Protocol 让编排依赖统一的 `run_episode` 与环境操作，但 Python 签名兼容并不保证“done”“timeout”“只读”在不同 CLI 中语义一致。

建议每个 Adapter 声明能力，启动时根据角色需求校验：

| 能力 | 启动前需要回答的问题 |
|---|---|
| 结果归一化 | 哪些后端字段代表真实退出？流中最后一条是不是最终结果？ |
| 生命周期 | 超时/取消是否收回整个子进程树？如何证明没有残留？ |
| 权限 | 可否禁止工作区外写入、读控制账本、外网或 GUI 写动作？ |
| 使用量 | usage 是实测、估算还是 unavailable？ |
| 轨迹与脱敏 | 哪些 channel 会保存？是否可能在脱敏前 tee 到磁盘？ |
| computer-use | GUI 是否真可用？会不会仅 CLI 可用却路由到 GUI？ |
| CLI 兼容性 | 测试了哪些版本、输出格式和配置参数？不支持如何报错？ |

契约测试使用 fake CLI/fixture，而不是必须消耗真实模型调用：覆盖空输出、乱码、流截断、多结果、非零退出、超时、取消、provider 错误、含秘密日志、并发 prompt 文件隔离和子进程残留。

Environment 的后续演进应先承认文件、GUI、网络的差异，再增加可选能力（状态探测、隔离验证、回执查询）；不要仅向通用 `exec` 添加更多含糊约定。

## D11. 可证伪的评测设计

### D11.1 主张与观测对应

| 主张 | 必须观测 | 对照/消融 |
|---|---|---|
| 外环提升真实成功率 | 独立外部验收，不以自身 Auditor 为唯一评分器 | 同模型同任务、原生 Agent vs MEA |
| 上下文刷新改善长程任务 | 完成率、遗忘要求、上下文成本 | 保留历史 vs 新 episode |
| Auditor 减少伪完成 | 假阳性、假阴性和独立复验结果 | 无 Auditor / 同角色自验 / 独立 Auditor |
| 可信状态压缩减少漂移 | 原始需求覆盖、失效证据、复用正确率 | 全轨迹 / 审计摘要 / 带证据引用摘要 |
| 续跑节省成本 | 恢复后成功率、增量成本、重复副作用 | 从头重跑 vs ledger resume |

不将 README 或论文中的数字当作本地已复现实验。具体成绩应注明原始来源、任务数、模型/后端版本、环境和预算；本次补充未复现论文结果。

### D11.2 两种公平预算都要报告

- **等资源预算：** 限定总 Token/费用/墙钟资源，检验收益是否仍存在。
- **等任务目标：** 允许各方案跑到终态，但报告总成本、尾延迟和失败风险。

MEA 多调用几次模型可能本身提高成功率；只比较“同模型”而不控制预算，不能把所有增益归因于外环。

建议报告：任务成功率、假完成率、每任务费用/时间、成功任务条件成本、恢复成功率、重复副作用率、P50/P95 时延。成本须同时包含失败任务，避免只展示成功任务而低估成本。

统计时以任务/环境条件作为分层，做配对比较并给出不确定性区间；评测重复次数和排除规则事先登记。使用固定任务版本、独立验收脚本和隔离机器状态，防止前一次运行污染后一次。

### D11.3 最低故障注入矩阵

1. 在 Executor 返回后、Auditor 启动前终止 worker。
2. 在审计完成与 ledger 提交之间终止 worker。
3. 截断 JSONL 尾行、插入重复轮号、移走已引用产物。
4. 在 resume 前修改交付文件或追加用户要求。
5. 令 Auditor 写原文件、写工作区外文件、修改远程对象，检查检测范围。
6. 同一 run 重复 stop/resume；两个 run 竞争同一 desktop/workspace。
7. 最终回复生成失败、事件推送失败、report 两份副本不一致。
8. 上传/发送请求超时但服务端实际成功，恢复不允许盲目重发。

每项明确期望终态、禁止行为、证据位置与预算；缺少执行证据则记录“未验证”，不能通过读代码宣布测试通过。

## D12. 演进路线与待决策事项

### D12.1 分阶段落地，不一口气重写内核

| 阶段 | 交付 | 验收门槛 |
|---|---|---|
| A：校准与回归 | 准确状态语义、源码定位、Adapter 契约测试 | 当前行为不变；现有回归测试仍通过 |
| B：证据绑定 | 需求 ID、契约 revision、产物引用、失效规则 | 变契约/变产物后旧 complete 被拒绝；不相关证据可复用 |
| C：恢复对账 | 轮级 manifest、attempt、恢复完整性、外部动作意图 | 崩溃窗口测试；重复副作用检测；坏账本不得 complete |
| D：经济性与运营 | 全局预算、停滞检测、能力矩阵、控制确认 | resume 不重置累计预算；停止与指令应用可追踪 |
| E：评测 | 等预算对照、消融与故障注入报告 | 可复现数据，收益与代价同时呈现 |

B/C 是值得优先投入的核心增强；增加更多 Agent 角色或更长 Prompt 并不能替代它们。

### D12.2 建议形成 ADR 的选择

以下全部为 **Proposed**，不是已经通过的架构决策：

| 议题 | 推荐方向 | 替代方案与代价 |
|---|---|---|
| 文本控制 vs 结构化控制 | 保留文本兼容；引入带版本的结构化中间对象 | 强制所有后端 JSON 会增加适配与迁移成本 |
| 文件 ledger vs 数据库 | 先补单写者与一致性协议；达到并发需求后再评估数据库 | 立即上数据库也无法事务化 GUI/远程副作用 |
| 审计权限 | 隔离验证副本 + 最小授权 | 仅 Prompt 限制便宜但弱；绝对只读可能使测试不可运行 |
| 完成证据 | 按需求、契约、产物版本绑定 | 固定 TTL 简单但不符合不同证据的失效条件 |
| 状态压缩 | 可再生摘要 + 持久证据引用 | 纯自然语言省上下文，但容易丢范围和未满足项 |
| 并行 Executor | 暂保串行 MEA；独立资源时才引入并行 | 同桌面或共享可写产物并行会放大审计竞态 |

每份正式 ADR 应补充负责人、约束、迁移方案、撤销条件和验收测试。只有明确接受后，才写成“项目决定”。

## D13. 贯穿案例：把成功路径与不确定路径讲完整

任务：生成报告 PDF，上传到指定远程目录，追加要求后继续修改。

| 步骤 | 环境事实 | 可信状态与下一步 |
|---|---|---|
| 1. Manager 分配生成 | 无产物 | R1 未满足；本轮契约只覆盖生成 |
| 2. Executor 生成 PDF | 本地文件存在 | 执行声明待验；不能 global complete |
| 3. Auditor 检查内容与打开 | 版本 H1 通过 R1 | 保存 R1 的证据，R2 上传仍未满足 |
| 4. Executor 上传后超时 | 服务端可能已接受 | 记录 intent，状态未知；恢复先查询 |
| 5. 对账获得服务端对象 U1 | U1 内容与 H1 匹配 | R2 通过，global audit 才有机会完成 |
| 6. 用户追加水印要求 | 契约 v2 | 旧 global audit 失效；上传旧对象不能满足新版本 |
| 7. 新 PDF H2 重新验收/更新上传 | U2 与 H2 匹配 | R1/R2 在 v2 下重新验证 |
| 8. Manager done | 最新有效全局审计通过 | 完成；Final response 引用 H2/U2，不再执行任务 |

当前闭环提供执行与审计骨架；版本绑定、上传对账、全局证据覆盖属于本章建议的增强。该案例的价值是把“长程可靠”展开成可以逐步实现、逐步测试的协议，而不是把它当作口号。

---

# 源码还原：整体架构与模块设计

> **本章性质：现有实现说明。** 基于源码提交 `b498162fc1b96ff469146f04a698c829c89e3eab` 和当前本地运行时文件核对；不把未来设计画成已经存在的模块。所有源码相对路径均以 `/Users/gqli/work/deepagents/LongHorizon-Harness/` 为根。新增图是文档中的 Mermaid 源码，不要求项目部署图形服务。
>
> 与上一章关系：D1–D13 讨论工程边界与演进建议；本章 A1–A14 解释**当前代码实际上如何组成系统**。历史正文不删除，出现不一致时先看本章校准与源码符号。

## 本章大纲与目录

| 章节 | 阅读问题 | 主要图形 |
|---|---|---|
| [A1 缺失内容地图](#a1-缺失内容地图) | 旧文档漏的是设计还是实现？ | 覆盖矩阵 |
| [A2 系统分层与进程部署](#a2-系统分层与进程部署) | 哪些代码在 API、worker、Agent 进程？ | 架构图、部署图 |
| [A3 类型模型与对象关系](#a3-类型模型与对象关系) | 数据如何跨模块传递？ | 类图 |
| [A4 配置与依赖组装](#a4-配置与依赖组装) | 谁决定角色、模型和运行环境？ | 组装流程图 |
| [A5 四后端实现差异](#a5-四后端实现差异) | 哪些能力相同，哪些不能类推？ | 后端类图、策略矩阵 |
| [A6 执行与进程生命周期](#a6-执行与进程生命周期) | shell、流输出、超时如何闭环？ | 时序图 |
| [A7 日志与失败归一化](#a7-日志与失败归一化) | 工具报错为何不一定终止任务？ | 数据流图、判定流程图 |
| [A8 审计与只读守卫](#a8-审计与只读守卫) | 谁解析证据，谁检测写入？ | 审计流程图 |
| [A9 Supervisor 与运行所有权](#a9-supervisor-与运行所有权) | 创建、监督、续跑如何衔接？ | 时序图、生命周期图 |
| [A10 控制总线与人工门禁](#a10-控制总线与人工门禁) | 命令怎样防重复、确认、进入下一轮？ | 类图、时序图 |
| [A11 Web API 与事件投影](#a11-web-api-与事件投影) | 页面如何恢复状态、处理旧响应？ | 数据流图、重同步时序图 |
| [A12 插件与产物链路](#a12-插件与产物链路) | GUI 能力与截图如何接入和落盘？ | 插件流程图、产物流图 |
| [A13 横切边界与扩展地图](#a13-横切边界与扩展地图) | 改一个功能需要同步哪些模块？ | 影响矩阵 |
| [A14 本章结论与改动总结](#a14-本章结论与改动总结) | 已补什么、仍缺什么？ | 分层结论 |

## A1. 缺失内容地图

旧文档对 Manager 循环的篇幅较多，但“外环之外的后端工程”分解不足。源码核对后，应将缺失分为三类，而不是一律写成待实现建议。

| 主题 | 源码现状 | 旧文档缺口 | 本次处理 |
|---|---|---|---|
| 后端注册与 CLI 探测 | `agent_registry.py` 已有 AgentSpec、三态可用性、推理配置 | 容易把后端列表视为散落的字符串 | A4/A5 还原事实源与能力边界 |
| 模型发现 | `model_catalog.py` 已区分来源和发现结果 | 模型下拉框如何得到候选值不清楚 | A4 解释发现与执行的区别 |
| CLI 组装 | `cli.py` 显式构造多个角色 Adapter | “可换后端”缺少实际工厂与参数流 | A4/A5 + SOURCE C2 |
| Environment | 实际入口仅接受 local，Protocol 预留可扩展性 | 把接口可扩展误读为已支持远程后端 | A6 明确当前范围 |
| 结果归一化 | `agent_logs.py` 已解析多类流日志 | raw、visible、runtime、tool views 混在一起 | A7 拆分数据管道 |
| 副作用隔离 | 不同 Adapter 实现不对称 | 只用 Claude 路径解释全部后端 | A5/A8 明确差异 |
| 控制总线 | 已有 revision、幂等 command、receipt、锁和路径硬化 | 上次 D9 的目标协议容易遮住已有基础 | A10 精确补齐，不另造总线 |
| 人工门禁 | 已有连续失败规则和不同审批触发 | “有 Dashboard”不等于同一种阻塞 | A10 说明优先级与状态 |
| 事件重同步 | EventTailer、snapshot、前端 reducer 已处理缺口 | 只讲“WebSocket 推送”太薄 | A11 还原恢复与合并协议 |
| 产物与截图 | 有流式规范化、截图 manifest、受控下载 | raw trajectory 到 UI 的链路漏讲 | A12 说明两套轨迹的用途 |
| 版本化证据/外部动作对账 | 已读路径未见完整协议 | 是真正待建设的设计能力 | 保留 D4–D6，不假装已实现 |

**修正上一章可能造成的印象：** D9 的控制确认、游标重同步，以及 D10 的能力矩阵不是“从零开始”。当前已经存在相当一部分协议基础；更进一步的缺口是**角色级权限一致性、确认语义的粒度、任务证据与外部动作状态绑定**。

## A2. 系统分层与进程部署

### A2.1 六层职责：入口、组装、编排、执行、监督、展示

```mermaid
flowchart TB
    Entry[CLI / Web 请求] --> Assembly[配置与角色组装]
    Assembly --> Kernel[manager.py 编排内核]
    Kernel --> Adapters[四类 Agent Adapter]
    Adapters --> Env[LocalEnvironment]
    Env --> Native[外部 CLI 与工具子进程]
    Kernel --> Evidence[轮账本 / 审计 / 终态]
    Native --> Logs[原始日志 / 规范化轨迹]
    Super[RunSupervisor] -->|启动和监督| Entry
    Super -->|读终态与进程身份| Evidence
    Evidence --> Projection[DashboardState / snapshot / EventTailer]
    Logs --> Projection
    Projection --> Web[FastAPI / React 工作台]
    Web -->|控制命令| Bus[ControlBus]
    Bus -->|人工 hook 消费| Kernel
```

图中不是简单的层层调用：Supervisor 与编排内核是**两个不同责任中心**。前者决定哪个 worker 活着、谁有权控制它；后者决定本轮做什么、审计是否可接受。UI 只投影，不能替代任一中心。

### A2.2 独立 Web 模式的进程边界

```mermaid
flowchart LR
    subgraph Browser[浏览器进程]
      React[React / useRunFeed]
    end
    subgraph Service[Web 服务进程]
      API[FastAPI]
      Registry[StateRegistry / DashboardState]
      Supervisor[RunSupervisor]
      API --> Registry
      API --> Supervisor
    end
    subgraph Worker[受监督 Python worker]
      CLI[python -m lh_harness run --supervised]
      Manager[manager.run]
      Local[LocalEnvironment]
      CLI --> Manager --> Local
    end
    subgraph Agent[独立进程组]
      Shell[shell]
      AgentCLI[claude / codex / dsh / opencode]
      Tool[工具与子进程]
      Shell --> AgentCLI --> Tool
    end
    React <-->|HTTP / WebSocket| API
    Supervisor -->|subprocess| CLI
    Local -->|新 session| Shell
    Worker --> Disk[(run 目录)]
    Registry --> Disk
    Supervisor --> Disk
```

来源：`supervisor/service.py::_worker_command/_launch_worker`、`environment/local.py::exec`、`webapi/server.py::create_app`。

### A2.3 同样是 Dashboard，所有权可能不同

| 模式 | 谁启动任务 | Web 能力边界 |
|---|---|---|
| 普通 CLI | CLI 本进程进入 `manager.run` | 不强制启动 Web |
| `run --dashboard` | CLI 已启动当前任务，再附着控制能力 | 附着模式不应任意创建/重启自己无法拥有的 worker |
| 独立 `web` 工作台 | Supervisor 启动受监督 worker | 可以按能力暴露 create、resume、stop 等 |
| 历史日志查看 | 不启动 worker | 只读投影，不能因为看得到日志就取得控制权 |

`can_control`、run scope、`attached_only` 和 `/api/meta` capabilities 共同限制行为。**能读文件不等于拥有进程**，这是多入口不互相误杀的基础。

## A3. 类型模型与对象关系

### A3.1 核心领域对象类图

```mermaid
classDiagram
    class HarnessConfig {
      +int max_total_episodes
      +EpisodeBudget manager_budget
      +EpisodeBudget gui_executor_budget
      +EpisodeBudget cli_executor_budget
      +EpisodeBudget auditor_budget
      +str workspace_path
      +str harness_dir
      +str log_dir
    }
    class EpisodeBudget {
      +int max_duration_seconds
    }
    class ExecResult {
      +str stdout
      +str stderr
      +int exit_code
      +int duration_ms
      +str termination_reason
    }
    class EpisodeResult {
      +str status
      +str actions_log
      +str error
      +int duration_ms
      +dict metadata
    }
    class ManagedRound {
      +int round_index
      +str next_step
      +str plan_text
      +str task_state
      +str task_contract
      +str executor_output
      +str auditor_report
      +dict auditor_status
    }
    class AuditReport {
      +str round_id
      +str status
      +str integrity_status
      +str contract_audit_status
      +str report_text
      +list completed
      +list missing
      +list artifact_actions
    }
    HarnessConfig *-- EpisodeBudget
    ExecResult ..> EpisodeResult : Adapter 归一化
    EpisodeResult ..> AuditReport : Auditor 解析
    EpisodeResult ..> ManagedRound : 提取可见输出与状态
    AuditReport ..> ManagedRound : 保存文本与状态
```

这是字段节选，不是完整类型声明；箭头分别表示组合和数据转换，**不表示 `ManagedRound` 实际持有一个 `AuditReport` 对象**。它存的是审计文本和状态字典，完成门禁会再解析文本。

### A3.2 三种 result 不能混用

| 对象 | 产生者 → 消费者 | 成功语义 |
|---|---|---|
| `ExecResult` | Environment → Adapter | shell/进程退出信息；0 不等于任务完成 |
| `EpisodeResult` | Adapter → Manager/Auditor 逻辑 | 一次 Agent episode 的 done/timeout/error/cancelled |
| `AuditReport` | 审计解析器 → 编排决策 | 结果是否 complete、integrity 是否 clean、contract 是否 aligned |

此外还有 `_final_report` 返回的字典：它聚合整次 run 的完成授权与终态。Supervisor 再将该结果与进程退出状态合并，得到公开 lifecycle status。

### A3.3 存储模型为什么值得单独解释

`ManagedRound` 通过 `asdict` 落入 JSONL；恢复时再经过字段清洗重建。这样兼容自由文本和可读日志，但弱点是 metadata 字典、审计文本与终态字段可能出现语义重复。后续若增加版本化证据，优先扩展**统一中间对象与兼容解析**，而不是在 UI、Manager 和 Supervisor 各自解析一套新字段。

## A4. 配置与依赖组装

### A4.1 组装中心在 CLI，不在 Manager

```mermaid
flowchart TD
    TOML[项目 TOML run 配置] --> Parse[load_run_defaults / 参数解析]
    Flags[显式 CLI 参数] --> Parse
    Parse --> Resolve[按角色解析 agent / model / effort]
    Registry[AgentSpec / model catalog] --> Resolve
    Plugin[插件状态与 MCP 配置] --> Resolve
    Resolve --> Env[_build_env local]
    Resolve --> Factory[_build_agent]
    Factory --> Roles[Manager / GUI与CLI Executor / Auditor / Reply]
    Env --> Run[manager.run]
    Roles --> Run
```

`config.py::_flatten_run_table` 把 `[run.roles.<role>]` 的嵌套项变为参数默认值；未知根字段、角色、timeout 字段会报错，不静默接受拼写错误。显式参数再参与 `_resolve_role_option/_resolve_role_model/_resolve_role_reasoning_effort` 的角色解析。

`manager._run_impl` 负责缺省 Adapter fallback 和编排，不负责每轮重新发现二进制或重建 CLI 配置。该设计把“入口配置变化”与“状态机变化”隔开。

### A4.2 注册、探测、模型发现是三种事实

| 模块/对象 | 回答什么 | 不回答什么 |
|---|---|---|
| `AgentSpec` | 已知后端 ID、二进制名、默认模型、声明能力 | 此机器当前是否可运行 |
| `AgentProbe` / `probe_agents` | usable / found_but_broken / missing | 该模型账户一定有权限 |
| `discover_model_catalog` | 候选模型、发现来源、配置推理选项 | 下一次真实请求一定成功 |
| Adapter + provider error | 运行时是否被后端接受 | 声明 capability 就能代替真实权限测试 |

“PATH 能找到”与“可用”分成三态是已有设计价值：例如一个可解析路径可能不是可执行的真实 CLI。模型候选表也可能来自本地缓存或声明，不应把下拉框选项当成已验证的调用权限。

### A4.3 推理强度是后端特性，不是通用字符串语义

- Claude：注册表声明 CLI flag 传输，实际 `--effort`；未知值可能被 CLI 警告后忽略，不能显示成“已验证生效”。
- Codex：通过 `-c model_reasoning_effort=...` 传输；模型目录记录 per-model 选项。
- DeepSeek 集成：当前不支持该配置；不应静默吞掉。
- OpenCode：`--variant`，语义随 provider；声明选项不等于统一强度刻度。

这些是本项目基线的适配策略，不是对任意最新 CLI 版本的永久保证。

## A5. 四后端实现差异

### A5.1 后端继承与协议关系

```mermaid
classDiagram
    class AgentAdapter {
      <<Protocol>>
      +run_episode(prompt, env, budget, live_trajectory_path)
    }
    class CommandAgentAdapter {
      +str command_template
      +str prompt_dir
      +str workspace_path
      +visible_output_parser
      +run_episode()
    }
    class ClaudeCodeAdapter {
      +ClaudeRolePolicy policy
      +run_episode()
    }
    class CodexAdapter {
      +constructor_config_overrides
    }
    class DeepSeekHarnessAdapter {
      +str permission_mode
      +str dsh_home
    }
    class OpenCodeAdapter {
      +str role
      +run_episode()
    }
    class Environment {
      <<Protocol>>
      +exec()
      +screenshot()
      +upload()
      +download()
    }
    AgentAdapter <|.. CommandAgentAdapter
    CommandAgentAdapter <|-- ClaudeCodeAdapter
    CommandAgentAdapter <|-- CodexAdapter
    CommandAgentAdapter <|-- DeepSeekHarnessAdapter
    CommandAgentAdapter <|-- OpenCodeAdapter
    CommandAgentAdapter --> Environment : 委托实际执行
```

`AgentAdapter` 是结构协议，不要求显式继承；虚线表示满足接口。四类具体 Adapter 共用命令执行管道，但权限、日志格式和配置生成不等价。

### A5.2 实际后端矩阵

| 维度 | ClaudeCodeAdapter | CodexAdapter | DeepSeekHarnessAdapter | OpenCodeAdapter |
|---|---|---|---|---|
| 启动方式 | `claude --print` 流式 JSON | `codex exec --json` | Python runner → `dsh --profile headless` | `opencode run --format json` |
| Prompt 传入 | stdin 文件重定向 | stdin 文件重定向 | runner 读文件，再传给 dsh | stdin 文件重定向 |
| 角色策略 | `ClaudeRolePolicy` deny-list | 构造器可收 sandbox_mode；当前 `_build_agent` 不传 role/sandbox_mode | role → read-only / workspace-write | 保存 role 标签；当前此类未生成角色级 deny-list |
| 默认自动授权 | 跳过交互权限，叠加 deny-list | 未指定 sandbox 时 bypass approvals/sandbox | 通过 DSH_PERMISSION_MODE 约束 | `--yolo` |
| Auditor 文件变化检测 | 前后 workspace snapshot | 本类无同等 snapshot 守卫 | 本类无同等 snapshot 守卫 | 本类无同等 snapshot 守卫 |
| 配置/端点 | 环境变量，Anthropic URL 处理 | provider TOML overrides，Responses URL 处理 | 隔离 DSH_HOME + 模型 patch | provider 端点 JSON 文件 |
| GUI/MCP | 支持按策略加载 MCP | MCP TOML overrides / 插件 | 注册能力当前仅 CLI | 注册能力当前仅 CLI |
| 额外目录 | 角色隔离下拒绝 | 支持 add-dir | 当前拒绝 | 本组装路径未传额外目录 |

**重要：** 默认 bypass 是当前源码事实，不是本章建议用户开启的部署方案。尤其不能因为源码注释假定“外层环境已隔离”，就推导 `LocalEnvironment` 自身提供了 OS 沙箱；它并没有创建容器或虚拟机。

### A5.3 三个具体实现细节

1. **Claude 权限是 deny-list，不是 native sandbox。** `policy_for_role` 的 docstring 已明确这一点。Manager/Final response 禁 Bash、写工具、Agent 和 MCP；Auditor 禁写工具与 Agent，但为了验收仍允许其他观察/执行能力，再通过快照检测文件变化。
2. **Codex CLI 工厂存在角色语义缺口。** `_build_agent` 接收 role，却不向 CodexAdapter 传 role；该构造器本身也没有该参数。修改时必须区分“库调用者手工指定 sandbox_mode”和“默认 CLI 路径”。
3. **DeepSeek runner 是协议桥，不是普通透传。** 它生成模型 YAML patch，调用 dsh 后包装为 `dsh.result`；stdout 是进程结束后集中包装，不应向读者承诺与其他后端同等细粒度的实时轨迹。它还把读取后的 Prompt 作为 dsh 命令参数传递，因此不能把通用 stdin 路径的进程表隐私性质类推到该 runner。

## A6. 执行与进程生命周期

### A6.1 一次 Episode 的真实调用链

```mermaid
sequenceDiagram
    participant M as Manager
    participant A as CommandAgentAdapter
    participant F as remote_files
    participant E as LocalEnvironment
    participant P as shell / Agent CLI
    participant D as trajectory 文件
    M->>A: run_episode(prompt, env, budget, live_path)
    A->>F: 写唯一 prompt 文件
    F->>E: 通过环境写文件
    A->>E: exec(cd workspace && command, timeout, tee_path)
    E->>P: create_subprocess_shell(start_new_session=True)
    par 同时排空输出
      P-->>E: stdout
      E->>D: tee + 规范化轨迹
    and
      P-->>E: stderr
    end
    alt 正常退出
      P-->>E: returncode
    else 超时或取消
      E->>P: 终止进程组，必要时强杀
      E->>E: 收集已接收的部分输出
    end
    E-->>A: ExecResult
    A->>A: visible parser + runtime signals
    A-->>M: EpisodeResult
```

### A6.2 实现中的可靠性选择

- 每集唯一 Prompt 文件名防止并发互相覆盖；不是复用一个 `prompt.md`。
- 模板替换用 `.replace`，避免 CLI 内联 TOML 大括号被 `.format` 误解析。
- workspace 与 Prompt 路径做 shell quoting；模板本身仍应是受信配置。
- stdout/stderr 并发排空，避免某一管道塞满后子进程卡死。
- 超时保留已读输出，返回 `termination_reason="timeout"`；取消/异常先清理进程再向上抛。
- 进程组分离后 Ctrl+C 不会自然传递给子进程，所以 cleanup 不能遗漏异常路径。
- `LH_HARNESS_WEB_TOKEN` 从 Agent 子进程环境移除，避免控制面凭据泄入执行面。

### A6.3 Environment 的实际边界

`Environment` 定义 exec、screenshot、upload、download；当前 `_build_env` 只接受 `local`。它提供适配面，并不意味着远程机器、容器、检查点恢复已经实现。

本地 screenshot 有平台实现与失败条件；不能将接口方法存在解释为所有操作系统均有可用 GUI。跨机器扩展还要处理远程文件、CLI 可执行位置、日志传输和进程身份，而不仅新增一个 hostname。

## A7. 日志与失败归一化

### A7.1 一份原始日志，四种消费视图

```mermaid
flowchart LR
    Raw[Agent stdout JSONL] --> Detect[agent_logs.detect_format]
    Detect --> Visible[visible_output 最终可见文本]
    Detect --> Steps[parse_trajectory 规范化步骤]
    Detect --> Runtime[runtime_event_view 运行时事件]
    Detect --> Tool[tool_output_view 工具结果]
    Visible --> Plan[Manager 路由 / Auditor 控制头]
    Steps --> Artifact[轨迹卡片 / 截图产物]
    Runtime --> Signals[detect_runtime_signals]
    Tool --> Signals
    Signals --> Failure[classify_agent_runtime_failure]
```

这解释了为什么不能直接把整个 stdout 当 Manager 的决策文本：其中混有工具输出、图片、错误事件和非最终 assistant 消息。`actions_log_diagnostics_only` 也用于避免“解析不到最终回答时就拿原始诊断日志当回答”。

### A7.2 失败分类不是搜索任意 Error 字符串

```mermaid
flowchart TD
    Result[EpisodeResult] --> Trigger{error / timeout 或 hard signal?}
    Trigger -->|否| Task[保留为任务证据，不判 provider 失败]
    Trigger -->|是| Timeout{本地 timeout?}
    Timeout -->|是| Recover[保留 timeout 分类，允许后续轮恢复]
    Timeout -->|否| Guard[剥离本地 snapshot guard 拒绝文案]
    Guard --> Provider{还有真实 provider 证据?}
    Provider -->|有| Terminal[auth / quota / model / network 等终止原因]
    Provider -->|仅 guard 导致| Round[轮级失败，不冒充 provider 故障]
```

工具运行 Python 抛 Traceback，可以是需要 Executor 修复的任务错误；Agent provider 身份验证失败，则继续同一个任务 Prompt 通常没有意义。`runtime_signals.py` 区分 runtime 与 tool view，`provider_errors.py` 再分类，Manager 据类型选择恢复或终止。

**仍有边界：** 该分类包含文本模式匹配，依赖后端输出约定；新版本 CLI 的错误形状必须用 fixture 补测试，而不是认为统一类型已经消灭兼容风险。

## A8. 审计与只读守卫

### A8.1 两条不同的验证管道

```mermaid
flowchart TD
    Episode[Auditor EpisodeResult] --> RunOK{运行成功且无 hard signal?}
    RunOK -->|否| Block[blocked 运行失败报告]
    RunOK -->|是| Text[提取 / 压缩审计正文]
    Text --> Header{控制头合法?}
    Header -->|否| Repair[无效报告 / 有界格式修复]
    Header -->|是| Semantic[状态 / integrity / contract 解析]
    Semantic --> Acceptance[阻塞验收约束 guard]
    Acceptance --> Mutation[合并 workspace mutation metadata]
    Mutation --> Reconcile[删除声明与实际删除对账]
    Reconcile --> Report[AuditReport / round 状态]
    Snapshot[Claude 前后快照] --> Mutation
```

**内容验收**回答任务是否满足；**只读守卫**回答 Auditor 是否改变了被验证对象。两个维度相互独立：报告说 complete 但写坏产物，仍不能成为可信完成。

### A8.2 快照的精确覆盖

`claude_permissions.py::snapshot_workspace` 对工作区遍历，记录文件类型、mode、size、mtime、符号链接目标；小文件计算内容摘要。`_small_file_digest` 只对不超过 **4 MiB** 的文件算 SHA-256，较大文件的摘要为 None。

因此本机制不是“全工作区所有文件内容的完整哈希”。大文件仍有元数据比较，但若内容变化未体现在比较字段，检测能力有限。`hidden_paths` 与 `guard_exclude_paths` 也不同：前者参与角色可见性限制；后者仅排除快照扫描，**不会因此禁止 Agent 访问**。

### A8.3 删除账本与例外不能泛化为写授权

`auditor_agent.py` 有候选产物路径、删除原因提取、允许删除路径计算和实际删除对账。用途是将特殊清理行为显式记入审计并核对，不能把“报告里声明删除”当成删除已发生，也不能把例外解释为 Auditor 可任意修复工作区。

新增后端时，若只实现可见文本解析，不提供相同 metadata 与守卫语义，则统一 Auditor 解析器也无法凭空检测其写副作用。

## A9. Supervisor 与运行所有权

### A9.1 创建 run 的事务边界

```mermaid
sequenceDiagram
    participant U as Web 请求
    participant S as RunSupervisor
    participant B as ControlBus / run metadata
    participant P as Python worker
    participant M as Manager
    U->>S: create_run(task, role_configs, idempotency_key)
    S->>S: 校验配置 / workspace / 幂等 fingerprint
    S->>B: 预留目录与 creating 状态
    S->>B: 持久化 owner reservation
    S->>P: 用当前 sys.executable 启动 --supervised
    P->>B: 校验 reservation / claim owner
    P->>M: manager.run
    S->>B: 保存 worker 身份与运行状态
    U->>S: status(run_id)
    S->>S: _refresh 检查进程身份
    S->>B: 读 report / lifecycle / pending commands
    S-->>U: 生命周期 + 验收结果 + 控制能力
```

上图是协作概览；具体 owner 提升与子进程退出存在竞态，代码用 launch 失败落盘、身份检查和 refresh 协调，不应解释为跨进程原子数据库事务。

### A9.2 公开生命周期与 resume epoch

```mermaid
stateDiagram-v2
    [*] --> creating
    creating --> starting: 启动 worker
    creating --> failed: 启动失败
    starting --> running: 身份确认
    running --> waiting_approval: 门禁
    waiting_approval --> running: continue
    running --> stopping: stop 请求
    stopping --> cancelled: 终止后收敛
    running --> completed: report 授权且进程成功
    running --> incomplete: 未验收完成而结束
    running --> blocked: 无法自动继续
    running --> failed: 崩溃或协议失败
    completed --> starting: continue / epoch 增加
    incomplete --> starting: continue / epoch 增加
    blocked --> starting: continue / epoch 增加
    failed --> starting: continue / epoch 增加
    cancelled --> starting: continue / epoch 增加
```

这是根据生命周期词汇整理的说明图，不是源码内存在同名状态机类。各入口还会校验是否 alive、是否拥有控制权、是否 attached-only、是否达到 resume 次数上限。

### A9.3 四个容易忽略的正确性机制

1. **当前解释器启动 worker：** 避免 PATH 上旧 console script 不理解私有 supervised 协议。
2. **参数采用 `--key=value`：** 防止 HTTP 传入以 `-` 开头的值被 argparse 解析为新选项。
3. **进程身份不只 PID：** PID 复用时不能误杀其他程序，需结合启动时间/命令身份。
4. **终态不只 returncode：** 退出 0 但 report 缺失，或 claimed completed 缺 `completion_satisfied is True`，都不能报成功。

`continue` 重用目录和账本、增加 epoch；`retry` 新建 run。两者是不同产品语义，也有不同的幂等记录处理。

## A10. 控制总线与人工门禁

### A10.1 已实现的持久控制模型

```mermaid
classDiagram
    class ControlBus {
      +append(kind, payload, expected_revision, command_id)
      +revision()
      +pending()
      +receipt(command, status)
      +read_status()
      +read_owner()
    }
    class DashboardState {
      +add_injection()
      +drain_injections()
      +create_approval()
      +resolve_approval()
      +snapshot()
    }
    class Approval {
      +str approval_id
      +str status
      +str action
      +str user_input
      +int extra_rounds
    }
    class ApprovalRules {
      +evaluate(round_index, rounds)
    }
    class HumanHook {
      <<Callable>>
      +context_to_decision()
    }
    DashboardState --> ControlBus : 持久命令 / 回执
    DashboardState --> Approval : 管理审批状态
    HumanHook --> DashboardState : 消费注入与等候审批
    HumanHook --> ApprovalRules : 触发连续失败门禁
```

### A10.2 指令送达时序

```mermaid
sequenceDiagram
    participant U as UI
    participant API as Web API
    participant D as DashboardState
    participant B as ControlBus
    participant H as human_hook
    participant M as Manager
    U->>API: inject(text, command_id, expected_revision)
    API->>D: add_injection
    D->>B: append(inject_instruction)
    B->>B: 锁内校验幂等 ID 与 revision
    B-->>API: 持久命令或冲突
    M->>H: end_of_round context
    H->>D: drain_injections
    D->>B: pending + receipt
    H-->>M: continue + instructions
    M->>M: 下一轮组装 carryover
```

锁内的检查顺序有意义：同 command_id 同 kind/payload 的重试复用旧命令；同 ID 不同内容报 CommandConflict；新命令才检查 expected_revision 并分配下一 revision。receipt 也按 command_id 幂等。

**语义边界：** receipt 证明这个控制命令被控制层消费/处理，不等于追加要求已完成、已通过审计。它也不是远程上传、发消息等**任务副作用**的回执；D6 的外部对账依然是独立缺口。

### A10.3 门禁优先级和连续失败

`dashboard/gate.py::_classify` 的顺序是：

```text
completed → ask → reached_max → blocked → repeated_failure → 普通 progress
```

这保证最后一轮即使同时 blocked，也优先告诉用户“预算耗尽，可增加轮次”。`rule_repeated_failure` 从后往前数连续失败：invalid plan、invalid completion、executor/auditor/repair 的 error/timeout。默认阈值来自环境变量，缺省为 3。

因此“停滞检测完全没有”是不准确的；当前已有**错误连续性检测**。但反复输出合法计划、审计总 incomplete、没有实际进展，未必触发此规则，仍需要 D7 的 verified progress 判定。

## A11. Web API 与事件投影

### A11.1 API 不直接把所有磁盘文件暴露给浏览器

```mermaid
flowchart TB
    HTTP[HTTP / WS 请求] --> Auth[Host / Token / Origin 与输入校验]
    Auth --> Registry[StateRegistry 选定 run]
    Registry --> State[DashboardState 安全读取]
    State --> Snap[build_snapshot / build_run_summary]
    State --> Art[受控 artifact / trajectory 读取]
    Tail[EventTailer + normalize_event] --> Stream[事件 replay / WS]
    Snap --> Client[前端协议对象]
    Art --> Client
    Stream --> Client
    Auth --> Control[Supervisor / 审批 / 注入入口]
```

来源：`webapi/server.py`、`snapshot.py`、`events.py`、`dashboard/state.py`。

### A11.2 后端能力与安全边界

| 机制 | 当前作用 | 注意点 |
|---|---|---|
| `/api/meta` | api/protocol 版本、运行能力、后端与模型信息 | UI 应按能力而不是按钮位置假设可控 |
| HTTP Bearer token | 配置 token 后保护 API，包括产物读取 | 不是内建多租户 RBAC 系统 |
| Host 检查 | loopback 绑定时拒绝不匹配的 Host | 不代替对外部署的边界防护 |
| JSON content type / body 上限 | 控制命令请求先校验再解析 | 输入限额与 Agent 总预算不同 |
| WebSocket auth / Origin | 独立握手校验 | 不能假设 HTTP middleware 自动覆盖 WS |
| run/path 检查 | 产物只能从受控 run/round 中解析 | 文件下载也属于权限面 |

### A11.3 事件缺口已经有协议，不只是未来建议

`EventTailer` 有大小/条数上限、坏行诊断、event_id 去重、cursor_gap 和 resync_required。找不到 after cursor 时，不把它当成“从头读就行”。日志过大时用 retained tail 并发出告警；ID 还可能基于文件 offset 生成，**不能用字符串大小比较游标新旧**。

```mermaid
sequenceDiagram
    participant U as useRunFeed
    participant R as REST snapshot/replay
    participant W as WebSocket
    participant F as reduceRunFeed
    U->>R: 并行请求 snapshot 与 replay
    U->>W: 建立实时订阅
    R-->>U: snapshot / events
    W-->>U: snapshot / delta
    U->>F: 按 run_id 合并并去重
    alt cursor gap / resync
      U->>U: feedEpoch 增加，旧请求失效
      U->>F: reset
      U->>R: 获取新 snapshot
      R-->>U: 最新 snapshot
      U->>F: 重建投影
    else 正常续流
      U->>F: 累积有限事件与最新状态
    end
```

### A11.4 前端 reducer 的架构价值

`frontend/core/src/runFeed.ts` 不只是展示工具，它解决 REST/WS 的竞争：

- run guard 防止旧 run 响应污染新选择。
- event 去重与有界缓冲，避免长任务浏览器无限增长。
- resume epoch 新的一代可以覆盖旧 terminal status。
- 相同 cursor 的较稀疏快照不能抹掉已取得的角色输出、审批决定和最终回复。
- approvals、operator_messages 等持久交互并不完全由事件条数决定；event_count 不是单调版本号。
- `useRunFeed` 用本地 feedEpoch 废弃缺口重同步前的异步返回。

注意区分 **服务端 resume epoch** 和 **浏览器 feedEpoch**：前者是 worker 生命周期代次；后者是当前订阅的数据请求代次，不是同一个字段。

## A12. 插件与产物链路

### A12.1 插件是控制台能力的安装适配，不是 Manager 插件系统

```mermaid
flowchart LR
    Install[plugin install] --> Native[官方运行时 / 社区 MCP 安装适配]
    Native --> State[用户级 installed.json]
    Native --> Config[后端原生配置 JSON / TOML]
    State --> Select[active_plugin_for_agent]
    Config --> Select
    Select --> Assembly[CLI 启动组装]
    Assembly --> Adapter[对应 Adapter]
    Adapter --> Tools[CLI 内部 computer-use 工具]
```

`plugins/state.py` 将安装状态置于用户级 plugins 目录，可由 `LH_HARNESS_STATE_ROOT` 调整。多个已安装插件按优先级选择，Codex 官方插件优先；Claude 无法使用该官方路径时走适用的社区插件。生成后端原生配置，减少每次运行时格式翻译。

不要把 `plugins/` 理解为可以随意插入新 Manager 状态转换的业务插件框架；当前它主要解决 computer-use 的安装、激活、配置、状态查询与卸载。

### A12.2 原始轨迹、规范化步骤、截图三层存储

```mermaid
flowchart TD
    Out[Agent stdout] --> Raw[role_raw_trajectory.jsonl]
    Out --> Writer[StreamingTrajectoryArtifactWriter]
    Writer --> Parse[agent_logs.parse_trajectory]
    Parse --> Step[role_trajectory.jsonl]
    Parse --> Image[解码图片为本地产物]
    Image --> Manifest[role_screenshots.json]
    Step --> View[Dashboard 规范化轨迹]
    Manifest --> View
    Raw --> Debug[诊断与兼容回放]
    End[episode 结束保存] --> Persist[persist_trajectory_artifacts]
    Persist --> Step
    Persist --> Manifest
```

writer 按 tool ID 去重工具调用，避免 Codex started/completed 两条记录产生两张工具调用卡片；结果记录仍保留。图片提取有步数、大小等限制，manifest 描述可用截图，避免把巨大 base64 反复塞进页面状态。

展示产物不能当成验收证据本身：规范化器会裁剪、去重、去内联图片，用途是观察与调试；需要原始依据时仍应检查 raw 和真实任务产物。

### A12.3 打包也是模块设计的一部分

`pyproject.toml` 通过 hatchling 打包 Python；`_frontend/web/dist` 作为构建产物进入 wheel/sdist。源码安装缺少构建资源时不代表后端本身无法安装，但工作台静态资源可用性需要单独检查。部署问题应区分“API 能启动”和“前端资源已正确构建”。

## A13. 横切边界与扩展地图

### A13.1 安全设施分布，而非单一 security.py

| 边界 | 主要源码 | 设计理由 |
|---|---|---|
| workspace/run/round 路径身份 | `utils/run_boundary.py` | 文件读与进程控制均需受目录范围约束 |
| 锁、nofollow、原子 JSON 与控制目录 | `supervisor/control_bus.py` | 降低符号链接置换与并发写冲突 |
| owner、PID identity、scope | `supervisor/service.py` | 防止不拥有的 worker 被接管或误杀 |
| shell 与子进程树 | `environment/local.py`、`utils/process_group.py` | timeout/cancel 后收尾 |
| 后端工具能力 | 各 Adapter、`claude_permissions.py` | 角色语义需实际后端执行 |
| HTTP/WS 访问 | `webapi/server.py` | 网络入口独立防护 |
| 产物下载 | `dashboard/state.py` + API artifact 路由 | 展示通道不能变任意文件读取 |

这些是已读代码中的机制，不是完整安全审计结论。OS 隔离、敏感图像脱敏、外部动作对账不能靠这些模块名称自动成立。

### A13.2 功能变更影响矩阵

| 新需求 | 主改点 | 必须联查 | 不应绕过 |
|---|---|---|---|
| 新 Agent 后端 | registry + Adapter + `_build_agent` | config choices、模型发现、日志解析、Web meta、测试 | 只给 UI 增加一个选项 |
| 更强 Auditor 权限 | Adapter/role policy | snapshot/metadata、动态验证 scratch、测试 | 仅在 Prompt 写“只读” |
| 新事件 | Manager/事件生产者 + normalize_event | EventEnvelope、snapshot、frontend core reducer | 直接让 React 解析原始 CLI JSON |
| 新人工门禁 | dashboard gate/rules/state | ControlBus revision、审批 receipt、UI 文案 | 手改 auditor_report |
| 新 resume 行为 | Supervisor + lifecycle + Manager 恢复 | epoch、终态覆盖、指令队列、预算 | 把 retry 偷换成 continue |
| 新完成证据字段 | types + Auditor + Manager gate | final report、Supervisor、Web snapshot、frontend status | 只改页面 completed 文案 |
| 远程 Environment | Environment 实现与入口 | 文件传输、执行身份、GUI、日志、取消清理 | 假定 local 路径远端同样有效 |

### A13.3 当前仍值得保留的真实缺口

1. **角色权限不一致：** 后端统一协议不提供统一隔离语义。
2. **证据适用性：** 当前完成谓词未显式绑定契约 revision、需求覆盖和产物版本。
3. **世界状态恢复：** ControlBus receipt 不等于业务动作 receipt，不能防重复上传或发送。
4. **停滞与总资源：** 连续错误检测不等于验证进度检测；每集时间与轮次预算不等于整个逻辑 run 的费用治理。
5. **恢复完整性：** 容错跳过坏账本行适合恢复可用性，但缺损历史的完成授权还应有独立约束。

## A14. 本章结论与改动总结

本次新增的不是又一份 Manager 循环介绍，而是把此前压缩成“Adapter / Web / Supervisor”的后端体系展开为：

- **配置层：** 项目配置 → 注册与发现 → 角色组装。
- **执行层：** Adapter → LocalEnvironment → 进程组 → 流式输出。
- **解释层：** 多后端日志 → 可见回答/工具/运行时视图 → 失败和审计分类。
- **运营层：** Supervisor 所有权与 epoch → ControlBus revision/receipt → 人工门禁。
- **投影层：** 安全文件读取 → snapshot/replay → REST/WS 竞争合并 → UI。
- **扩展层：** 原生插件配置、轨迹产物、安全设施与跨模块变更清单。

最重要的修正是：**项目已经有较完整的运行监督和前端重同步机制；真正下一步的架构投入，应聚焦证据与世界状态之间的绑定，而不是重复建设已有控制协议。**

代码注释版走读见 [SOURCE.md · 模块源码精读](SOURCE.md#模块源码精读与注释)。测试范围和本轮新增统计见文档入口的“本轮改动记录”。
