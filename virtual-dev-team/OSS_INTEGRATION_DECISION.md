# 开源组合决策：用现成项目搭「虚拟开发团队」

> 本文核实了候选开源项目的真实状态（2026-10-10 通过 GitHub API 抓取），并给出可直接落地的组合方案。
> 结论会覆盖 `IMPLEMENTATION_PLAN.md` 中「从零自建控制平面」的部分：自建降级为 Plan B。

## 1. 直接回答

**是的，这个领域已经有完整方案，不需要自己写编排内核。**

- `paperclipai/paperclip` —— MIT、TypeScript（Node server + React UI）、当天还在推送。它就是「一人公司 / Agent 团队」的控制平面：组织架构、任务工单、父子任务、依赖、审批与 signoff 策略、预算、执行环境、adapter 插件（Codex / Cursor / Claude Code / Gemini CLI / OpenCode / Hermes / Pi / OpenClaw）、artifacts、routines、pipelines（阶段 + review queue）、CLI、MCP server、OpenTelemetry。
- `multica-ai/multica` —— source-available（Apache-2.0 + 对托管服务和商业嵌入的附加条件）、Go、当天在推送。看板优先：Agent 作为 assignee 上板、runtime daemon、执行日志回放、review gate、失败重试与超时、Slack/飞书等渠道。自托管要 Docker。
- `AionUi` 和这一类 Cowork 桌面壳**不适合做核心**。它是多 CLI 的本地聊天客户端（33k star，最近推送 2026-09-09，自定义许可），没有工单真源、没有门禁状态机、没有租约和审计。它能当「你本地的聊天入口」，不能当团队骨架。

所以你要的东西——**发任务 → 看到分析 → 看到拆卡 → Agent 自己领卡 → 完成 → 验证 → 交付**——现在是一个**集成与配置问题**，不是一个从零造框架的问题。

## 2. 核实过的项目清单

| 项目 | Star（API 返回） | 语言 | 最近推送 | 许可 | 它到底是什么 | 在本方案中的位置 |
|---|---|---|---|---|---|---|
| `paperclipai/paperclip` | 99,415 | TypeScript | 2026-10-10 | **MIT** | Agent 公司控制平面：org / 工单 / 委派 / 依赖 / 审批 / 预算 / adapter / 环境 / 插件 / artifacts | **首选核心** |
| `multica-ai/multica` | 52,368 | Go | 2026-10-10 | Apache-2.0 + 附加条件 | Agent 上板认领、runtime daemon、执行日志、review gate、重试超时 | 备选核心 / 或只做看板 |
| `Fission-AI/OpenSpec` | 71,522 | TypeScript | 2026-10-09 | **MIT** | 规格生命周期：explore / propose / apply / archive | **规格合同层，保留** |
| `obra/superpowers` | 297,028 | Shell | 2026-10-10 | — | TDD、worktree、code review、收枝等执行纪律 skill | **开发纪律层，保留** |
| `bmad-code-org/BMAD-METHOD` | 54,002 | Python | 2026-10-10 | NOASSERTION | Analyst/PM/Architect/SM/Dev/QA 的敏捷工作流与模板 | **只借角色提示词与模板**，不当运行时 |
| `headroomlabs-ai/headroom` | 74,875 | Python | 2026-10-10 | — | 压缩工具输出 / 日志 / RAG | 可选，省 token |
| `nexu-io/open-design` | 100,304 | TypeScript | 2026-10-10 | — | 本地设计插件 + DESIGN.md | UI 需求的 G1.5 |
| `Tencent/teamai-cli` | 5,210 | TypeScript | 2026-10-10 | — | 把 skills/rules/MCP 分发到多个宿主 | 多机器 / 第二人时再用 |
| `iOfficeAI/AionUi` | 33,412 | TypeScript | 2026-09-09 | Custom | 多 CLI Cowork 桌面客户端 | **不进核心**，可作本地聊天壳 |
| `BloopAI/vibe-kanban` | 28,315 | Rust | 2026-09-19 | Apache-2.0 | Agent 任务看板（未归档，但节奏变慢） | 不需要；草稿里「已关」的说法不准确 |
| `smtg-ai/claude-squad` | 8,585 | Go | 2026-08-20 | — | 多终端 Agent 会话管理 | 不需要 |
| `stravu/crystal`（已改名 Nimbalyst） | 3,126 | TypeScript | 2026-02-26 | — | worktree 并行会话 | 不需要 |
| `humanlayer/humanlayer` | 11,681 | TypeScript | 2026-06-19 | — | human-in-the-loop 审批 SDK | Paperclip 自带审批，不叠 |

说明：上面的 star 数是本机环境下 GitHub API 的返回值，用于判断相对量级和活跃度；许可证字段中 `—` 表示本次请求超时未取到，集成前请再确认。

## 3. 最佳实践方案（推荐）

一句话：**Paperclip 当公司，OpenSpec 当合同，Superpowers 当工艺，Git/PR 当交付，BMAD 只贡献角色提示词。**

```text
你发一条需求
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│ Paperclip（MIT，自托管）= 控制平面                        │
│  · Goal / Project / Task（工单真源）                     │
│  · Org chart：产品 / 架构 / 开发 / QA 都是 agent 记录      │
│  · 父子任务 + 依赖 + 唤醒 → 这就是「拆卡」                 │
│  · 审批与 signoff 策略 → 这就是 G1 / G2 / Review / QA     │
│  · Adapter：Codex / Cursor / Claude Code / OpenCode …     │
│  · 执行环境：local / SSH / sandbox                        │
│  · 预算、超时、暂停、artifacts、执行日志                   │
└───────┬──────────────────────┬──────────────────────────┘
        │ skill 调用            │ adapter 拉起
        ▼                      ▼
   OpenSpec（MIT）         Codex / cursor-agent
   proposal / design       Superpowers：TDD、worktree、review
   tasks / delta / archive  Playwright：UI 场景
        │                      │
        └──────────┬───────────┘
                   ▼
              Git 仓库 / PR / CI = 代码与交付真源
```

### 三个真源，边界清楚

| 真源 | 放什么 | 由谁管 |
|---|---|---|
| 运行时真源 | 任务、依赖、认领、审批、运行记录、成本 | Paperclip 数据库 |
| 规格真源 | proposal、design、场景、delta、archive | Git 中的 OpenSpec |
| 交付真源 | 代码、commit、PR、CI 结果 | Git / GitHub |

聊天、频道、桌面壳都不是真源。

### 角色怎么落到 Paperclip

Paperclip 的 agent 记录本身就带标题、职责描述、上级、权限、预算和 adapter，所以角色不是常驻 prompt，而是配置：

| 角色 | adapter 建议 | 职责（写进 job description） | 权限红线 |
|---|---|---|---|
| 产品 | Cursor 或 Claude Code | 跑 `openspec explore/propose`，产出场景 | 不写实现代码 |
| 设计（有 UI 才启用） | Cursor + OpenDesign | 原型 + `DESIGN.md` | 不改业务逻辑 |
| 架构师 | Cursor | 写 `design.md`，把 change 拆成子任务和依赖 | 不能合并主干 |
| 开发 | Codex（难模块用 cursor-agent） | 领卡、worktree、TDD、提交 | **不能给自己 signoff** |
| 评审 | 另一个 agent 记录 | diff + 越界检查 + 安全面 | 不在开发 worktree 里改代码 |
| QA | 独立 agent 记录 | 只跑 OpenSpec 场景 + Playwright | 不改实现 |

关键点：**用 Paperclip 的 signoff 策略把「实现者不能自己 Done」变成系统约束**，而不是写在文档里靠自觉。它的 `task-coordination` 明确区分 review 完成事件和任务完成事件，这正是你需要的那道门。

### 拆卡怎么自动发生

Paperclip 仓库里已经有现成 skill：

- `skills/paperclip-converting-plans-to-tasks` —— 把计划转成任务
- `skills/paperclip-board` —— 操作看板
- `skills/paperclip-create-agent` —— 招人

所以链路是：架构师 agent 读 OpenSpec 的 `design.md` / `tasks.md`，调用 converting-plans-to-tasks 生成子任务和依赖关系，Paperclip 负责在前置任务完成时唤醒后续任务。你在界面上看到的就是「需求 → 分析 → 拆卡 → 领卡」。

## 4. 落地步骤（按天）

### Day 1：把公司立起来

1. 自托管 Paperclip（Node + pnpm，仓库有 Dockerfile 和 docker 目录，但也能直接跑 server + ui；本机无 Docker 时走本地进程）。
2. 配置 adapter：先只接 **Codex** 和 **Cursor**，确认 `test-environment` 探测通过。
3. 建一个公司、一个项目、一个 Goal，仓库挂上你的试点仓。
4. 招 5 个 agent：产品、架构、开发、评审、QA。先只给开发 agent 写权限。
5. 发一条小需求（例如「加 `/health` 接口」），观察任务、run、artifacts、成本是否都落盘。

出门条件：一条任务能被真实 Codex 领取并产生 commit，运行日志可回放。

### Day 2：把门禁打硬

1. 配置 signoff / 审批策略：实现完成后必须由评审 agent 给出结果，QA 独立任务通过后才允许完成。
2. 在项目仓里 `openspec init --tools codex,cursor`，让产品和架构 agent 的产物进 Git。
3. 装 Superpowers，让开发 agent 走 TDD + worktree + requesting-code-review。
4. 配置预算上限和超时，避免跑飞。

出门条件：故意让开发 agent 想直接结束任务——系统拒绝。

### Day 3：验证闭环与证据

1. QA agent 用独立任务 + Playwright 跑场景，产物进 artifacts。
2. 失败路径演练：QA 不通过 → 任务回到实现 → 重跑 → 再评审。
3. 归档：`openspec archive` 把 delta 合进 `specs/`，PR 描述引用 change id。
4. 把这次踩的坑写进 agent 的 job description 和 `AGENTS.md`。

出门条件：你只发一句话，能看到分析、拆卡、领卡、实现、评审、QA、归档的完整证据链。

### 之后按需加

- Headroom：工具输出压缩（token 高了再上）。
- OpenDesign：第一张有 UI 的卡。
- 远程执行：Paperclip 的 SSH / sandbox 环境。
- teamai-cli：第二台机器或第二个人加入时。

## 5. 两个核心怎么选

| 维度 | Paperclip | Multica |
|---|---|---|
| 许可 | MIT，可商业嵌入 | Apache-2.0 + 附加条件（托管服务、商业嵌入、品牌受限） |
| 语言 | TypeScript（你和 Codex 都好改） | Go（后端）|
| 心智模型 | 公司 / 组织 / 目标 / 工单 | 看板 / issue / runtime |
| 角色与层级 | 原生 org chart、委派、上下级 | squads + leader 路由 |
| 门禁 | 可配置 review/approval/signoff 策略 | review gate |
| 扩展 | 插件 + adapter plugin（可自己加 adapter 和 UI 页面） | CLI / API |
| 自托管 | Node 进程，Docker 可选 | Docker Compose / Helm（需要 Docker） |
| 适合你 | **更贴「产品/架构/开发/QA 的公司」隐喻，且 MIT** | 偏「Agent 上板干活」，轻一些 |

你的本机没有 Docker，而且你要的是「像真正的工程团队」，带角色、职责、签字和交付——**选 Paperclip**。如果后面你更想要纯看板体验，Multica 可以作为视图接上，但不要同时让两边都当任务真源。

## 6. 需要自己写的部分（很少）

集成后仍然缺的，是你的业务规则，不是基础设施：

1. **OpenSpec 桥接 skill**：让产品/架构 agent 的产物写进 `openspec/`，并把 change 路径回填到 Paperclip 任务。
2. **DoR / DoD 校验**：在任务进入 Ready 前检查场景可测、依赖无环、文件范围不重叠；可做成 Paperclip 插件或一个校验 skill。
3. **QA 证据归档**：Playwright 报告、截图、trace 统一挂到 artifacts 并在任务上可见。
4. **角色 job description 模板**：从 BMAD 的 Analyst/PM/Architect/Dev/QA 模板里抄，裁剪成几十行，不要整包装。
5. **归档守门**：代码与 delta 不一致时拒绝完成。

这五件加起来是几百行 TypeScript 加若干 Markdown skill，而不是一个新框架。

## 7. 和原草稿的差异

| 原草稿 | 修正 |
|---|---|
| Multica 作唯一看板 | 改为 Paperclip 作控制平面；Multica 降为备选 / 视图 |
| 自己造控制平面（IMPLEMENTATION_PLAN.md） | 降为 Plan B，仅当 Paperclip 实测不满足时启用 |
| AionUi / eigent / PI-Desktop「不进」 | 结论保留，理由更准确：它们是客户端壳，不是团队骨架 |
| BMAD「不整装」 | 结论保留，但明确要借它的角色模板和阶段门 |
| Vibe Kanban「公司已关」 | 不准确：仓库未归档，Apache-2.0，只是节奏变慢；无论如何不需要 |
| 「实现者不能自己 Done」靠约定 | 改为由 Paperclip signoff 策略强制 |

## 8. 下一步

建议现在只做一件事：**自托管一个 Paperclip，接上 Codex + Cursor，招 5 个 agent，发一条 `/health` 的小需求跑通闭环。**

跑通之后再决定是否需要 OpenSpec 以外的任何东西。如果你同意，我可以直接开始：拉起 Paperclip、写 agent 的职责配置、写 OpenSpec 桥接 skill，并用一个最小试点仓做端到端验证。
