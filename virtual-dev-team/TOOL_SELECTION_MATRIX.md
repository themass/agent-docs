# 选型矩阵：监控 / 文档 / 卡片三问的横向对比

> 核实方式：2026-10-10 通过 GitHub API 抓取元数据，并读取各项目 README 与仓库内功能文档。
> 我读的是**项目自己的文档和源码目录结构**，不是宣传页。但没有逐个本地跑起来，所以下面标注的是「文档与代码结构层面的证据」，不是实测结论。

## 0. 先回答三个问题

| 你的问题 | 结论 |
|---|---|
| 1. Agent 监控，看哪些角色在干什么 | **有现成的**。最完整的是 Paperclip 的 `/dashboard/live` + `/activity/runs` + `/activity/timeline` + 审计中心；Orchestrator.inc 的实时 Kanban 把状态从「会话 + PR + CI + review 事实」推导出来，更贴工程视角 |
| 2. 各角色产出的文档怎么看 | **只有少数项目做对了**。Paperclip 有版本化任务文档、段落级批注、附件、work products、`/artifacts` 库。多数同类项目只有聊天记录，没有文档库 |
| 3. 技术卡片拆分 + worker 认领 + 进展展示 | **有卡片，而且有真正的认领语义**。Paperclip：父子任务 + 依赖唤醒 + signoff 策略；amux：认领是 compare-and-swap 原子操作，`done ≠ verified`；Orchestrator.inc：编排 agent 拆卡并派工，每张卡带分支/PR/CI |

## 1. 核实过的候选项目

| 项目 | Star | 语言 | 许可 | 最近推送 | 形态 | 一句话 |
|---|---|---|---|---|---|---|
| [paperclipai/paperclip](https://github.com/paperclipai/paperclip) | 99,415 | TypeScript | **MIT** | 2026-10-10 | Node server + React UI，自托管 | Agent 公司：org / 工单 / 文档 / 审批 / 预算 |
| [stablyai/orca](https://github.com/stablyai/orca) | 88,874 | TypeScript | MIT | 2026-10-10 | 桌面 ADE | 并行 worktree、终端、diff 批注、移动端 |
| [multica-ai/multica](https://github.com/multica-ai/multica) | 52,368 | Go | Apache-2.0 + 附加条件 | 2026-10-10 | 服务 + 桌面 | Agent 上板认领、runtime daemon |
| [getpaseo/paseo](https://github.com/getpaseo/paseo) | 20,343 | TypeScript | NOASSERTION | 2026-10-10 | 桌面 + 移动 | 多 agent 编排 |
| [gastownhall/gastown](https://github.com/gastownhall/gastown) | 18,318 | Go | MIT | 2026-10-08 | CLI + git worktree | Mayor/Polecat/Hook/Convoy，三层看护 |
| [OrchestratorInc/agent-orchestrator](https://github.com/OrchestratorInc/agent-orchestrator) | 13,018 | Go | Apache-2.0 | 2026-10-10 | 桌面 + 本机 daemon | 编排 agent 拆卡 + 实时 Kanban |
| [mvschwarz/openrig](https://github.com/mvschwarz/openrig) | 6,583 | TypeScript | Apache-2.0 | 2026-10-10 | CLI + TUI | YAML 定义 agent 团队，席位与角色 |
| [777genius/agent-teams-ai](https://github.com/777genius/agent-teams-ai) | 2,252 | TypeScript | **AGPL-3.0** | 2026-10-10 | Electron 桌面 | 角色团队 + Kanban + 互评 + token 分析 |
| [mixpeek/amux](https://github.com/mixpeek/amux) | 524 | Rust | MIT + Commons Clause | 2026-10-10 | 单 Rust 二进制 | 原子认领、`done`/`verified` 分离 |
| [iOfficeAI/AionUi](https://github.com/iOfficeAI/AionUi) | 33,412 | TypeScript | Custom | 2026-09-09 | Electron 客户端 | 多 CLI 聊天壳，无工单真源 |

同类但不解决你这三问的（并行会话 / IDE 壳）：`superset-sh/superset` 15,042、`openchamber` 11,371、`generalaction/emdash` 5,948、`Yeachan-Heo/oh-my-claudecode` 39,753。它们强在「多开 agent 不打架」，弱在「团队角色、文档、门禁」。

## 2. 三问能力矩阵

打分依据是项目文档中可指认的具体功能与路由，不是营销描述。

| 能力 | Paperclip | Orchestrator.inc | agent-teams-ai | amux | OpenRig | Gas Town | Multica |
|---|---|---|---|---|---|---|---|
| **Q1 角色在干什么** | | | | | | | |
| 实时总览页 | ✅ `/dashboard/live` | ✅ 实时 Kanban | ✅ 全局组织地图 | ✅ web 面板 | ✅ TUI 拓扑图 | ⚠️ CLI + 看护进程 | ✅ 看板 |
| 按角色/席位看状态 | ✅ org chart + 角色 | ⚠️ 按 worker 看 | ✅ 成员状态 + CPU/RAM | ✅ 谁在线/谁持有什么 | ✅ `rig ps --nodes` 含运行时/模型/context | ✅ Witness/Deacon/Dogs 三层 | ✅ squads |
| 运行记录可回放 | ✅ 运行事件 + 转录 + 成本 | ✅ 会话 + 终端 + PR + CI | ✅ 深度会话分析、工具调用 | ✅ 消息台账 | ✅ activity hooks 中继 | ✅ `.events.jsonl` + seance | ✅ 执行日志回放 |
| 审计流水 | ✅ 审计中心（actor/resource 事件） | ⚠️ 状态推导为主 | ⚠️ 任务时间线 | ✅ 事件日志 | ⚠️ | ⚠️ | ✅ |
| 成本/token | ✅ 公司/agent/项目预算 + 阈值暂停 | ⚠️ | ✅ 按团队/agent/任务/模型，含预测与 80%/100% 告警 | ⚠️ | ✅ 用量采集 | ⚠️ | ✅ 用量分析 |
| **Q2 角色产出文档** | | | | | | | |
| 版本化文档 | ✅ 任务文档 + 修订 + 恢复 | ❌ | ⚠️ 任务描述/评论 | ⚠️ `.mdai` 计算文件 | ⚠️ 队列产物 | ⚠️ beads 结构化数据 | ⚠️ |
| 段落级批注 | ✅ annotations + 解决状态 | ✅ diff 行批注 | ✅ 任务评论 | ❌ | ❌ | ❌ | ⚠️ |
| 交付物库 | ✅ `/artifacts` 搜索/分组/stack | ❌ | ⚠️ | ✅ 文件浏览器 | ⚠️ | ⚠️ | ⚠️ |
| 产物挂回源任务 | ✅ work products → task/review | ✅ 卡片带变更文件 | ✅ 日志/变更自动匹配任务 | ⚠️ | ⚠️ | ✅ bead 关联 | ✅ |
| **Q3 卡片拆分与认领** | | | | | | | |
| 自动拆卡 | ✅ 父子任务 + `converting-plans-to-tasks` skill | ✅ 编排 agent 拆计划为任务 | ✅ lead 自建任务并派发 | ⚠️ 手工建卡 | ⚠️ 队列 | ✅ Convoy 打包 beads | ⚠️ |
| 依赖关系 | ✅ 阻塞 + 前置完成后唤醒 | ⚠️ | ✅ 依赖与委派 | ⚠️ | ⚠️ | ✅ | ⚠️ |
| 认领有并发安全 | ⚠️ 指派为主 | ⚠️ 派工为主 | ⚠️ | ✅ **compare-and-swap，两个 worker 不可能抢到同一张卡** | ⚠️ | ✅ hook 隔离 | ✅ |
| 完成需要证据 | ✅ signoff 策略：review 完成 ≠ 任务完成 | ✅ PR + CI + review 事实驱动 | ✅ 互评工作流 | ✅ **`done` 要证据，`verified` 要同伴检查** | ✅ reviewer 席位 | ✅ Refinery 合并队列 + 验证门 | ✅ review gate |
| worktree 隔离 | ✅ 工作区 + 环境 | ✅ 每 worker 独立分支与 worktree | ✅ 可选按成员 worktree | ✅ 每 worker 目录 | ✅ 席位工作区 | ✅ git worktree hook | ✅ |
| 卡片上看进展 | ✅ 任务详情 + 运行 + 产物 | ✅ Working / Needs you / In review / Ready to merge | ✅ 状态自动流转 + 卡上快捷动作 | ✅ 看板 + 状态门 | ⚠️ TUI 表格 | ⚠️ CLI | ✅ |

## 3. 逐个回答你的三个问题

### Q1：怎么看哪些角色在干什么

**Paperclip 的做法**（文档里可指认的具体入口）：

| 入口 | 看到什么 |
|---|---|
| `/dashboard` | 公司健康度、任务与运行汇总 |
| `/dashboard/live` | 正在进行的工作摘要 |
| `/activity` | 按 actor / resource 过滤的事件流 |
| `/activity/runs` | 所有执行记录，可回到源任务和 agent |
| `/activity/timeline` | 按时间理解工作 |
| 审计中心 | actor、资源、变更的审计流水 |
| `/agents/:id/runs/:runId` | 单次运行的状态、事件、输出、成本、来源任务 |
| 角色花名册 + org chart | 谁向谁汇报、谁被暂停、谁在跑 |

它还有一个细节值得一提：agent 有持久化的视觉身份和**姿态**（rest / idle / listening / thinking / working / success / confused / sleepy / loading），所以在花名册上能直观看出谁在想、谁在跑、谁卡住了。这是表现层，但对「一眼看出团队状态」很有用。

**Orchestrator.inc 的做法更工程化**。它的 Kanban 四列不是人工拖动的，而是从事实推导：

```text
Working        正在实现，或等你下一条指令
Needs you      阻塞、缺输入、CI 失败、被要求修改、信号丢失
In review      PR 开着或草稿，等检查或评审
Ready to merge 已批准或可合并
```

本机 daemon 盯着 agent 活动和版本库状态，所以卡片位置来自「会话 + PR + CI + review」的真实状态。这是我见过最贴近「工程团队看板」的监控模型。

**agent-teams-ai 的监控最细**：每个成员的 CPU/RAM 历史、后台服务列表、按类别（用户消息、项目指令、工具输出、团队协调）拆解的 context 消耗、按团队/agent/任务/项目/模型/运行时/会话/命令的 token 分析，带趋势预测和 80%/100% 预算告警。缺点是 AGPL-3.0，而且是 Electron 桌面应用。

### Q2：各角色产出的文档怎么看

这一问把候选项目区分得最开。**大多数项目只有聊天记录，没有文档。**

Paperclip 是少数做了完整文档层的：

| 能力 | 具体行为 |
|---|---|
| 版本化任务文档 | 编辑段落、保存、重载、对比修订、恢复历史版本 |
| 段落级批注 | 对选中内容加批注，经过再次编辑后仍能定位，可解决 |
| 附件 | 上传、预览、下载，带公司级访问检查 |
| work products | agent 交回的交付物，链到源任务、资源和评审上下文 |
| `/artifacts` 库 | 搜索、过滤、分组、打开 artifact stack |

它的文档甚至明确提醒一个常见坑：**「本地路径不等于可被他人访问的已上传产物」**、**「预览截图不等于下载字节正确」**。这种克制说明文档层是真做过的，不是加个附件按钮。

但要注意：Paperclip 的文档是**它自己数据库里的文档**。产品 brief、架构设计、验收场景如果你想要「进 Git、可 diff、可 review」，还是要配 OpenSpec（MIT，71.5k star）把 `proposal.md` / `design.md` / `tasks.md` / delta spec 写进仓库。

所以 Q2 的完整答案是两层：

```text
Paperclip 文档层        → 过程产物、批注、交付物、附件、artifact 库
Git 里的 OpenSpec      → 规格合同，可 diff、可 PR、可 archive
```

### Q3：卡片拆分、worker 认领、工作进展

**拆卡**。Paperclip 仓库里已经带了现成 skill：

```text
skills/paperclip-converting-plans-to-tasks   把计划转成任务
skills/paperclip-board                       操作看板
skills/paperclip-create-agent                招人
```

架构师 agent 读设计文档 → 调用这个 skill 生成子任务和依赖 → Paperclip 在前置任务完成时**自动唤醒**后续任务。它的文档明确提到 dependency wakeups 有服务端测试覆盖。

Orchestrator.inc 的路径不同但同样完整：项目编排 agent 是一个持久的规划 agent，它保留目标、决策、约束和早先的推理，结合仓库上下文和实时状态（活跃 worker、归属、PR、CI、review），计划可执行时把它拆成聚焦任务、派生或重定向 worker、传递上下文、跟进后续工作。**编排 agent 负责规划和委派，worker 负责实现、测试、提交、PR。**

**认领**。这里要特别点出 amux，虽然只有 524 star，但它把认领语义做对了：

- 认领是 **compare-and-swap**，所以两个 worker 不可能抢到同一张卡；
- `done` 需要证据，`verified` 需要同伴检查；
- 每个 worker 能看到整个 fleet（谁在线、谁持有什么、在做什么），打断前可以先窥视同伴的终端；
- worker 之间 @ 消息带来源戳，**服务端记录真实发送者，所以来源是事实而非声明**。

这正是你草稿里「实现者不能自己 Done」想要的那种硬约束。如果最终选了 Paperclip，建议把这三条抄成配置：signoff 策略 + 认领原子性 + 完成需证据。

**进展展示**。有卡片，而且卡上信息是连着的：

- Paperclip：任务详情里有对话、计划、阻塞、文件、运行历史，父子关系和依赖可点开
- Orchestrator.inc：每张卡保留任务、agent、分支、活动、PR、状态；打开可看对话或终端、变更文件、PR 摘要、评审、预览
- agent-teams-ai：任务在 Kanban 上自动变状态，卡上有快捷动作，可以直接 DM 某个 agent 或在卡上留评论

## 4. 我的推荐

### 主选：Paperclip 作控制平面

理由按权重排：

1. **三问都覆盖**，而且 Q2（文档库）只有它做得完整。
2. **MIT**，可以随便改、随便嵌。相比之下 agent-teams-ai 是 AGPL-3.0，Multica 有托管与商业嵌入限制，amux 是 MIT + Commons Clause。
3. **TypeScript**，你让 Codex / Cursor 改它比改 Go 或 Rust 容易得多。
4. **原生角色概念**：org chart、汇报线、职责描述、权限、预算。你要的「产品、架构师、开发、QA」是一等公民，不是 prompt 里的人设。
5. **门禁可配置**：review 完成和任务完成是不同事件。
6. 不强依赖 Docker，你本机没有 Docker 也能跑。

### 配角

| 槽位 | 选择 | 为什么 |
|---|---|---|
| 规格合同 | OpenSpec（MIT，71.5k） | 文档进 Git，可 diff 可 PR，archive 才更新真相 |
| 开发纪律 | Superpowers | TDD、worktree、code review、收枝 |
| 角色提示词 | 从 BMAD-METHOD 裁剪 | 只抄 Analyst/PM/Architect/Dev/QA 模板，不装运行时 |
| UI 设计 | OpenDesign | 有 UI 的卡才启用 |
| token 压缩 | Headroom | token 高了再上 |

### 明确不选，以及为什么

| 项目 | 不选的理由 |
|---|---|
| AionUi | 多 CLI 聊天壳，没有工单真源、依赖图、门禁、审计 |
| Orca / Paseo / superset / emdash / openchamber | 它们是「并行跑 agent 的 IDE」，解决不打架的问题，不解决团队角色与交付门禁 |
| Gas Town | 概念自成一套（Mayor / Polecat / Hook / Convoy / Molecule / Wasteland），学习成本高，而且 Go + beads 生态，你要改它不如改 TS |
| OpenRig | YAML 定义团队很优雅，但它改你机器的东西很多（写 `~/.tmux.conf`、Codex `config.toml`、Claude settings、trust 记录、hooks），个人开发者单机试点风险偏高 |
| agent-teams-ai | 功能很对口，但 AGPL-3.0 + Electron，二次开发和分发都受约束 |
| Multica | 能力接近，但许可有附加条件、自托管要 Docker、Go 栈 |
| amux | star 太低、Commons Clause，但**它的认领语义值得照抄** |

### 如果你更想要「工程师视角」而不是「公司视角」

那就换成 **Orchestrator.inc**（Apache-2.0，Go + 桌面）。它的 Kanban 从 PR/CI/review 事实推导，对「我就是想看哪张卡卡在哪」更直接。代价是没有文档库和 org chart，Q2 要靠 Git + OpenSpec 完全兜住。

**不要两个都当任务真源。** 选一个，另一个最多当视图。

## 5. 集成后还缺什么

无论选 Paperclip 还是 Orchestrator.inc，你自己要写的只有业务规则，大概几百行加若干 Markdown skill：

1. **OpenSpec 桥接**：角色 agent 的产物写进 `openspec/`，change 路径回填到卡片。
2. **DoR 校验**：卡进 Ready 前检查场景可测、依赖无环、文件范围不重叠、有验证命令。
3. **认领原子性**：照抄 amux 的 compare-and-swap，避免两个 worker 抢同一张卡。
4. **完成需证据**：照抄 amux 的 `done` / `verified` 分离，接上 Paperclip 的 signoff 策略。
5. **QA 证据归档**：Playwright 报告、截图、trace 挂到 artifacts。
6. **角色职责模板**：从 BMAD 裁剪成几十行，写进每个 agent 的 job description。

## 6. 建议的验证动作

不要再比选型了，用一条真需求把候选打穿。建议按这个顺序花两个晚上：

**第一晚**：自托管 Paperclip，接 Codex + Cursor 两个 adapter，建公司和项目，招 5 个 agent（产品、架构、开发、评审、QA），发一条「加 `/health` 接口」的需求。重点看三件事：

- `/dashboard/live` 和 `/activity/runs` 能不能回答「谁在干什么」
- 架构 agent 的设计文档和产品 agent 的验收场景能不能在 `/artifacts` 和任务文档里查到
- 父子任务和依赖唤醒能不能把拆卡自动串起来

**第二晚**：配 signoff 策略，故意让开发 agent 想直接结束任务，确认系统拒绝。然后让 QA agent 在独立任务里跑场景，看证据能否落到 artifacts。

两晚之后你会有实测结论，比任何对比表都准。如果 Paperclip 在某一项上不行，这份矩阵里第二梯队是 Orchestrator.inc（Q1/Q3 更强）和 amux（认领语义最严）。

要我现在就按第一晚的清单动手吗？我可以拉起 Paperclip、写 5 个 agent 的职责配置和 OpenSpec 桥接 skill，用一个最小试点仓跑端到端。
