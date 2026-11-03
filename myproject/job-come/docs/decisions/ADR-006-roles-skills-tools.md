# ADR-006：角色、技能、工具的三层模型

- **状态**：Accepted（实施中，见文末进度）
- **日期**：2026-11-04

## Context

智能体的定义曾散落在十来处：角色表、技能表、工具表、模型名、子 agent 配置、片段表、
消息包装的 if 链、按技能名的任务描述表、按角色名的默认值。同一个含义出现多次，改一处漏一处，
测试只能抓到其中一部分。

审计还发现一个更严重的事实：**技能正文（SKILL.md 的契约部分）没有进入任何一次运行的系统提示。**
组合器对"默认技能"不注入正文，理由是"身份已在 config.yaml 里"，但 config.yaml 里没有这段文字；
子任务（评审官）走的主 agent 路径也不带正文。DeerFlow 的系统模板还会要求模型用 `read_file` 读技能，
而 JC 把 `read_file` 过滤掉了。模型实际拿到的只有 description、产品规则和部分片段。

Agent Skills 的标准定义（DeerFlow 同样遵循）：**技能是按需加载的工作方法（一个带 SKILL.md 的目录）；
工具是运行时可执行的函数；技能可以在 `allowed-tools` 里声明它需要哪些工具。** DeerFlow 解析并展示
`allowed-tools`，但不据此拦截调用，拦截由宿主完成。我们的做法与标准一致，但有两点需要明确：
技能正文由宿主组合进系统提示（不依赖模型去读），权限由宿主执行。

## Decision

### 1. 三个概念，各自只在一处定义

| 概念 | 是什么 | 定义在哪 | 它回答的问题 |
|---|---|---|---|
| **工具 tool** | 运行时可以执行的函数，有输入 schema | `jc.mcp.server`（FastMCP 的函数签名，就是模型看到的 schema） | 能做什么动作 |
| **技能 skill** | 一种工作方法：契约、方法论片段、它需要的工具 | `backend/agent/skills/public/<id>/SKILL.md` 及 `references/` | 怎样做这一类工作，用哪些工具 |
| **角色 role** | 一个对外或对内的智能体：它的产品、入口、运行方式、模型场景，以及它拥有哪些技能、如何切换 | `backend/agent/roles.yaml` | 它是谁，由哪些方法组成 |

依赖只向下：角色拥有技能，技能声明工具，工具只存在于服务端。反过来不成立。

### 2. 技能与工具的关系

- 技能在 SKILL.md 的标准字段 `allowed-tools` 里声明它需要的工具。这是**声明**。
- 一次运行的工具面 = 该技能的 `allowed-tools` ∩ 服务端注册的工具。这是**执行**，由宿主完成，不依赖模型自觉。
- 技能声明的工具必须存在于服务端，否则启动失败。服务端的工具必须至少被一个技能声明，否则测试失败。
  （`jc_resume_review` 曾是唯一的孤儿，因此它被改造，见第 5 条。）
- 技能的其它 JC 专属元数据放在标准字段 `metadata:` 下（DeerFlow 的 schema 允许该字段），
  目前有 `always-loaded`（常驻片段）、`borrow-family-from`（岗位族片段的借用来源）。

### 3. 一条规则：每次运行的系统层都包含技能正文

系统层 = 该技能的 SKILL.md 正文 + `always-loaded` 片段 + 按请求选择的岗位族与定性片段 + 会话任务框架（`references/framing.md`，如果有）。
不再有"默认技能不注入正文"的例外。这条规则对会话、单次调用、子任务都一样。

### 4. 角色的运行方式与工作流

每个角色有一种运行方式，决定它怎样被调用：

- **session**：用户与它来回对话。`skills` 是它能以之运行的技能，第一个是默认技能。`switch` 声明在一回合内切换技能的条件。
- **single**：一次模型调用，输入全部在 prompt 里，没有工具。服务代码调用 `run_single(skill_id, ...)`，场景从角色读取。
- **subtask**：由服务代码在确定的时机调用（例如模拟面试结束），在独立的运行里以该技能运行，结果由工具写回。

子任务的触发由服务决定，而不是由模型决定。原因：触发条件是一个状态变化（场次已结束、导出被请求），
不是需要判断的事情。模型自主委派（`task` 工具）在本设计里不使用，相关机制已删除；
它的离线验证结论（身份沿委派传递、子 agent 工具受白名单约束）记录在此，需要时可以恢复。

### 5. 删除的特殊逻辑，以及它们的去向

| 原先的特殊逻辑 | 去向 |
|---|---|
| 组合器的 `_ALWAYS_LOADED`、`_REGISTERED_AGENT_SKILL` | 技能的 `metadata.always-loaded`；身份规则统一为第 3 条 |
| 标准 `allowed-tools` 之外的工具表（`SKILL_TOOLS`） | 技能的 `allowed-tools` |
| `SKILL_SCOPE`、`_SKILL_MODEL`、`DELEGATES`、`_PLAN_MODE_SKILLS` | 角色与技能的声明；委派机制删除 |
| `config.yaml` 的 `custom_agents`、`resolve_subagent_prompts_in_config` | 删除。子任务不再依赖 DeerFlow 子 agent 定义 |
| `extensions_config.json` 的技能开关 | 删除。技能是否可用只由声明决定 |
| `agent_service` 按技能名的 if 链（消息包装） | 角色的 `turn` 字段，指向一个注册的上下文提供者 |
| `resume_task.coach_skill_for`（技能切换条件） | 角色的 `switch` 规则，`when` 指向一个注册的判定函数 |
| `standing_instructions._FRAMING` 表 | 技能的 `references/framing.md` |
| `jc_mock_review` 工具（教练调用评审） | 删除。模拟面试结束时服务调用评审子任务 |
| `jc_resume_review` 工具（导出前质检） | 改为 `resume-reviewer` 子任务，工具为 `jc_resume_review_write`，由它写回结论 |
| 七处写死的场景字符串（`"flash"`、`"writer"`…） | 角色的 `scenario`，由 `run_single` 读取 |
| 四个直接调用模型的服务各自的 `prompt_file()` | 对应的技能包正文（`fit-scorer`、`localize`、`profile-structurer`、`profile-vision`，以及已有的 `jd-parser`） |
| 工具的三份定义（schema、包装函数、处理函数映射） | schema 只来自 FastMCP 签名；`OPENAI_TOOLS` 删除，目录由服务端派生 |

### 6. 注册表与判定函数

`switch.when` 与 `turn` 只写名字。名字映射到 Python 里的函数，由一个注册表持有。
新增一个条件或上下文提供者 = 注册一个函数 + 在声明里写它的名字；**不再新增任何 `if skill == ...`**。

## Consequences

- 一个含义一个定义点。新增角色只需写 roles.yaml 与技能包，不需要改服务代码（除非需要新的判定或上下文提供者）。
- 技能正文进入每次运行。这会增加系统提示的长度；需要在真实模型上验证回复质量，而不能只看测试。
- 评审从子 agent 配置改为服务调用后，评审不再由教练的模型决定是否发生。
- 删除的委派机制是可恢复的，但在出现真实的模型自主协作需求之前不恢复。
- DeerFlow 的系统模板仍会提到 `read_file` 与技能目录。这是上游行为，JC 不开放该工具；它不会导致失败，但会让模型尝试一个不存在的调用。记为已知问题，见 `AGENT-ROLES.md`。

## 进度

- [ ] 技能元数据进入 SKILL.md（`allowed-tools`、`metadata`），roles.yaml 只保留角色字段
- [ ] 系统层统一注入技能正文，删除身份例外与 `_FRAMING` 表
- [ ] 角色的 `turn` 与 `switch` 改为注册表驱动，删除按技能名的分支
- [ ] `run_single` 统一单次调用；四个服务迁入技能包
- [ ] 删除子 agent 与委派机制；模拟面试结束时服务调用评审子任务；删除 `jc_mock_review`
- [ ] 导出质检改为子任务；`jc_resume_review` 改名为 `jc_resume_review_write`
- [ ] 面试记录（`coach-archive`）增加入口，由 `switch` 规则触发
- [ ] 删除扩展配置里的技能开关
- [ ] 工具目录由服务端派生；删除 `OPENAI_TOOLS`
- [ ] 真实模型的端到端验证（需要密钥环境，未完成）
