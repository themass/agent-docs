# 虚拟开发团队流程（讨论稿）

| 项 | 内容 |
|---|---|
| 状态 | **v0.3 讨论稿** — 未定稿。v0.2 补设计/Headroom；v0.3 按日榜补 Multica / teamai-cli / Buzz，并拍板 H/I/J/C |
| 日期 | 2026-09-19 |
| 范围 | 用开源件搭一条「产品 → **设计** → 架构 → 看板 → 开发 → 评审 → QA → 收口规格」的团队环 |
| 热度分析 | [SURVEY.md](./SURVEY.md)（含日榜虚拟团队产品匹配：Buzz / Multica / TeamAI） |
| 图解 | [系统架构](./diagrams/virtual-dev-team-stack.architecture.html) · [主循环设计](./diagrams/virtual-dev-team-loop.workflow.html) |
| 落地 | **先跑起来：** [SETUP.md](./SETUP.md)（能不能落地、今晚装什么、本机有什么） |
| 不包含 | 任何内部工作台、SSO、企业网盘；不把 deep-code / `ya` 当运行时 |

本文是我们一起改到「最终版」的工作副本。改流程、改门禁、改工具，都直接改这一份。

---

## 0. 先回答：要不要区分新项目和迭代？

**要。** 不是两套团队，是 **同一条主循环，入口不同**。

| | 新项目（greenfield） | 迭代（brownfield，已有仓） |
|---|---|---|
| 缺什么 | 没有规格库、没有栈约定、没有可测的行走骨架 | 有代码，可能还没有 `openspec/specs/` |
| 第一件事 | **项目一次初始化**（§2），再切第一张卡 | 补 `openspec init`（若还没有），然后按变更类型分流（§3） |
| 产品 | 必须 brainstorm：用户、范围、MVP 不做清单 | 多数从 `/opsx:explore` 开始；只有需求糊才 brainstorm |
| 架构 | 先定栈和模块边界，再写第一个 change | 对着现有代码 + CodeGraph impact 写 **delta** |
| 危险 | `propose` 没有任何锚点，Agent 会凭空造架构 | 不 archive，规格库和代码会分叉 |

「新功能」≠「新项目」。在已有产品上加登录，走 **迭代主循环**。只有仓库还不存在、或还没有可运行的骨架时，才走 §2。

第三次分流是 **变更类型**（功能 / 缺陷 / 热修），见 §3。这和「新项目 / 迭代」正交：新项目的第一张卡几乎总是功能；迭代三种都有。

```text
收到一句话需求
    │
    ├─ 还没有可运行的仓库 / 规格库？ ──► §2 项目初始化，再进入 §4
    └─ 已有仓库 ──► §3 变更类型
                        ├─ 行为变化 ──► §4 主循环
                        ├─ 生产缺陷 ──► §5 Bug 旁路
                        └─ ≤2 文件且无 API/schema ──► §6 Hotfix
```

---

## 1. 原则（定稿前尽量少改）

1. **聊天不是合同。** 合同是 Git 里的 OpenSpec 工件 + 看板上的一张卡。
2. **一块看板。** 不允许再出现第二套任务真源（聊天 todo、另一块板、另一套 Issue）。默认板是 **Multica**。Buzz 频道不是卡。
3. **1 个 OpenSpec spec（capability）= 1 张卡 = 1 个 change 目录。** 再大也先在一张卡里用 tasks / waves 消化；只有认定需要 **多个 capability** 才拆多张卡。
4. **人签字：** G1 产品场景；有 UI 则 **G1.5 视觉**（原型 + `DESIGN.md`）；G2 架构边界。其余看看板列。
5. **实现者不能把自己的卡标 Done。** Done 的前提是 QA 通过 **且** `opsx:archive` 完成。
6. **WIP = 1。** 每个开发工人同时只领一张卡。
7. **QA 必须新会话。** 不复用开发上下文，只对照 OpenSpec 场景。
8. **Skill 渐进加载；always-on 规则要瘦。** 手册、ECC/agency-agents 整包、ui-ux 风格库禁止常驻。
9. OpenSpec 自称 artifacts 是 enabler 不是硬门——**本团队用 G1 / G1.5 / G2 和 Ready 列把「没签字不许领卡」补硬。**
10. **Token 分三层，不互相替代：** 行为（少瞎读）+ Headroom 压缩工具输出 + CodeGraph 结构检索。

---

## 2. 新项目：只做一次的初始化

与仓库里已有的工程启动清单互补：那边管应用骨架（`docs/standards/新项目启动清单.md`），这里管 **Agent 团队怎么开始干活**。两边都要做完，才允许进入 §4 的第一张功能卡。

| 序号 | 谁 | 做什么 | 产物 | 出门 |
|---|---|---|---|---|
| N1 | 你 + 产品 | Superpowers `brainstorming`：用户、场景、MVP 做/不做。新产品可用 `/last30days` 看用户近况，不当每卡必经 | `docs/product-brief.md` | 你确认范围 |
| N2 | 你 + 设计 | OpenDesign：`DESIGN.md` 品牌合同；有参照站则 brand-extract | `DESIGN.md` | 你确认视觉语言 |
| N3 | 你 + 架构师 | brainstorm：栈、模块、测试策略 | `docs/architecture.md` | 你确认栈 |
| N4 | 架构师 | `openspec init` + `openspec/config.yaml` | `openspec/` | 文件进 Git |
| N5 | 架构师 | `teamai init` 把 OpenSpec/Superpowers/DESIGN 技能分发到 Cursor 与 Codex；CodeGraph 首建索引；工人侧 `headroom wrap` 两边 | 团队仓 + 图库 + 压缩代理 | 两边 session start 能 pull 到同一套 harness |
| N6 | 架构师 | 根 `AGENTS.md`：测试命令、红线、specs 路径、**token 五条**。**短。** culture 细节放 teamai `culture.md`，不要复制进 AGENTS.md | `AGENTS.md` | 不含手册全文 |
| N7 | 项目经理 | 自托管或桌面 **Multica**；六列；Agent 名 = Codex 工人 / Cursor 工人 | 板可指派 | 实现者不能自 Done |
| N8 | 开发 | 行走骨架。**这是第一张功能卡**，走 §4 | 最小可运行提交 | CI 绿 |

新项目 **不要** 用一次 `propose` 把整个产品写成一个巨型 change。第一张卡应是可演示的薄切片（例如「能注册并看到空首页」），规格库从这张卡的 archive 开始累积。

**待决 A：** 新项目第一张卡是否强制 E2E（Playwright）还是单测即可？建议：有 UI 则要一条 Playwright 场景，无 UI 则 API 测试即可。

---

## 3. 迭代：变更类型分流

已有仓库（含刚做完 §2 的新项目）之后，每次进来的需求只问两个问题：

1. 这是不是行为变化？（用户可感知的 what）
2. 范围有多大？

| 类型 | 判据 | 走 | 跳过 |
|---|---|---|---|
| **功能** | 新行为、改行为、删行为 | §4 主循环 | 无 |
| **缺陷** | 已承诺的场景在生产/主干上失败 | §5 | 长 explore、长 design；仍要补场景并 archive |
| **热修** | ≤2 个任务、≤2 个文件、无 API/schema/新模块 | §6 | propose 全套；仍要测试与 Review |

说不清就当 **功能**。Agent 不得自行把功能降级成热修。

**待决 B：** 「内部工具、不上线」是否增加第四档 `spike`（只产出笔记、不 archive）？建议：要。超时（例如 1 天）必须要么升格为功能，要么关掉并留下 `docs/spikes/`。

---

## 4. 主循环（功能 / 行为变化）

一条 OpenSpec change 走完 1→12。角色是责任人，不是必须换人；人少时你可兼项目经理，但 **开发与 QA 不得同会话**。

### 4.1 步骤

| # | 角色 | 动作 | 产物 | 出门条件 |
|---|---|---|---|---|
| 1 | 产品 | 需求糊：brainstorm + `/opsx:explore`。新产品可先 `/last30days` | 纪要 | 能写清为什么做、给谁、不做什么 |
| 2 | 产品 | `/opsx:propose` | `proposal.md` + delta specs（含场景） | **G1 你签字** |
| 2.5 | 设计 | **有 UI 才走。** OpenDesign 出可点击原型；复杂交互另出 `frontend-design-ui-ux` handoff；评审时加载 `ui-ux-pro-max`（a11y/触控），用完即卸 | 原型 + 更新 `DESIGN.md` / 组件 brief | **G1.5 你点头视觉**；无 UI 则跳过 |
| 3 | 架构师 | `design.md` + CodeGraph impact；有 UI 时设计产物是输入不是灵感 | `design.md` | **G2 你签字** |
| 4 | 架构师 | `tasks.md` = 范围合同。工人需要冷启动时再 Superpowers `writing-plans` → `plan.md` | `tasks.md`；可选 `plan.md` | 1 spec = 1 卡；卡上挂 change 路径 |
| 5 | 项目经理 | 上 **Multica** Ready；assignee = 指定 Agent（Codex 或 Cursor），不是人名口号 | 看板 Ready | 满足 §7.1 DoR |
| 6 | 开发 | 一卡一 worktree / 一分支；按 `plan.md`（无则按 `tasks.md`）TDD；用 CodeGraph 查 callers | 提交 + 单测绿 | `tasks.md` 对应项勾完；自检无 CRITICAL |
| 7 | 开发 | Superpowers `requesting-code-review`（对照场景 + 代码质量） | 自检记录 | HIGH/CRITICAL 修完才能进 Review；**不能 Done** |
| 8 | 架构师 | PR diff + CodeGraph blast radius；有安全面则 **新会话** 跑 `security-audit-skill` | 批准或打回 | 越界/高危 finding 不进 QA |
| 9 | 测试经理 | **新会话**；只跑 OpenSpec 场景（单测 + Playwright；登录态站点可用 BrowserSkill） | 通过或缺陷卡 | 失败打回或开 bug 卡 |
| 10 | 开发 | Superpowers `finishing-a-development-branch`：测绿、PR、合入、回收 worktree | 主干提交 | PR 描述必须引用 `openspec/changes/<id>` |
| 11 | 架构师 / 产品 | `/opsx:apply` 核对任务勾完；`/opsx:archive` 把 delta 合并进 `openspec/specs/` | 规格库 = 新真相 | **未 archive 不算结束** |
| 12 | 架构师 | 把本次踩坑写进 `AGENTS.md` 与 `openspec/config.yaml` | 更准的下次上下文 | 下一张卡开工前做完 |

OpenSpec 官方一天是 `explore → propose →（你读）→ apply → archive`。本表把 propose 拆成产品/架构两道签字，把 apply 拆成领卡、TDD、三层评审、合入，这是团队层，不是另做一套规格工具。

### 4.2 两份清单

| 工件 | 读者 | 粒度 | 谁维护 |
|---|---|---|---|
| OpenSpec `tasks.md` | 你、项目经理、看板 | 一组一句，「做完没有」 | 步骤 4 架构师；步骤 11 apply 核对 |
| Superpowers `plan.md` | Codex / 子 Agent | 每步：路径、先写失败测试、命令、期望输出、commit | 领卡后 `writing-plans`；人可不读全文 |

不要把 `plan.md` 贴进看板正文。看板上只留 change 路径、场景摘要、DoR。

### 4.3 看板六列

| 列 | 对应步骤 | 谁推进 |
|---|---|---|
| Backlog | 1–3，未过 G2 | 产品 / 架构师 |
| Ready | 5 | 项目经理 |
| In Progress | 6–7 | 开发；WIP=1 |
| Review | 8 | 架构师 |
| QA | 9 | 测试经理 |
| Done | 10–12 都完成 | 项目经理在 **archive 之后** |

**已拍板 C：** 看板用 [Multica](https://github.com/multica-ai/multica)（自托管或桌面）。不选 Octop。Vibe 仅作历史对照（Bloop 已关）。Hermes Kanban / GitHub Issues 不再并列默认。

---

## 5. Bug 旁路

```text
复现（写成失败场景）→ 最小修复（worktree + TDD）→ 架构快速看 diff
    → QA 用该场景（新会话）→ 合入 → 把场景补进 openspec（小 delta）→ archive
```

不走长 explore。若修复时发现「行为定义本身错了」，升格为 §4 功能卡，关掉 bug 卡并互链。

---

## 6. Hotfix 旁路

判据：≤2 任务、≤2 文件、不改 API/schema、不新模块。

```text
worktree → 红绿测试 → Review 列（可与 QA 合并成同一次抽检）→ 合入
```

仍禁止实现者自 Done。若热修过程中范围膨胀，项目经理 **强制升格** 为 §4，不在热修里继续加料。

---

## 7. 检查单（可直接贴到卡上）

### 7.1 Definition of Ready（G2 之后，步骤 5）

- [ ] G1：proposal 与场景已签字
- [ ] 有 UI：G1.5 原型 + `DESIGN.md` 已点头；无 UI：跳过
- [ ] G2：design 已签字
- [ ] `openspec/changes/<id>/` 存在，且卡上写了该路径
- [ ] 场景可测（Given/When/Then 或等价）
- [ ] 无未完成的前置卡
- [ ] 指定模块 / 有界上下文；跨模块已在 design 写明接口
- [ ] 有 `tasks.md`；若卡将派给无仓上下文的 Codex，还有 `plan.md`

### 7.2 Definition of Done（步骤 12 之前）

- [ ] `tasks.md` 全勾，`/opsx:apply` 通过
- [ ] 单测绿；有 UI 的场景 Playwright 绿（若待决 A 选了必须）
- [ ] 架构 Review 通过
- [ ] QA 新会话通过
- [ ] 已合入主干，PR 引用 change id
- [ ] `/opsx:archive` 完成
- [ ] 新踩坑已写入 `AGENTS.md` 或 `openspec/config.yaml`
- [ ] worktree 已删

### 7.3 卡片正文模板

```markdown
## Change
`openspec/changes/<id>/`

## 类型
功能 | 缺陷 | 热修

## 场景（验收）
- Given … When … Then …

## 不做
- …

## 依赖
- 前置卡：无 | #<n>

## 工人
未指派

## 禁止
实现者不得将本卡标为 Done。
```

---

## 8. 工具组合（讨论稿默认）

分析过程与落选理由见 [SURVEY.md](./SURVEY.md)。系统怎么拼在一起见 [架构图](./diagrams/virtual-dev-team-stack.architecture.html)；签字到收口见 [主循环图](./diagrams/virtual-dev-team-loop.workflow.html)。这里只列 **进主循环的槽**。

| 槽位 | 默认 | 备注 |
|---|---|---|
| 人机入口 | **默认 Cursor IDE** | Codex / OpenCode 也可写同一份 OpenSpec，不作第二套流程。G1.5 仍建议在 Cursor 看原型 |
| 领卡工人 | **默认 Codex**；难模块 `cursor-agent` | 可扩 OpenCode / Hermes / Claude。OpenHands 不当板工人。WIP=1，一张卡一个 assignee。详见 [SETUP §2.1](./SETUP.md) |
| 团队 harness | [Tencent/teamai-cli](https://github.com/Tencent/teamai-cli) | push→MR→pull；用 roles 按角色发 skill，禁止全员 always-on |
| 规格生命周期 | [OpenSpec](https://github.com/Fission-AI/OpenSpec) | explore / propose / apply / archive |
| 执行纪律 | [Superpowers](https://github.com/obra/superpowers) | TDD、worktree、review、收枝 |
| UI 设计 | [OpenDesign](https://github.com/nexu-io/open-design) + `DESIGN.md` | **G1.5 有 UI 强制** |
| UX 评审 | `ui-ux-pro-max` **按需** | 禁止 always-on |
| 交互 handoff | `frontend-design-ui-ux` **按需** | 出状态机/组件 brief，不写代码 |
| 工具输出压缩 | [Headroom](https://github.com/headroomlabs-ai/headroom) | **Cursor 与 Codex 都 wrap**；不要和 headroom-skill 叠两层 |
| 结构检索 | CodeGraph MCP（live）+ teamai codebase/recall（团队 wiki） | 不叠第三套图 |
| 安全审计 | [security-audit-skill](https://github.com/cloudflare/security-audit-skill) | **仅 auth/支付/权限卡 + 发布前全量** |
| 用户近况（可选） | last30days | 仅新产品/新市场，非每卡 |
| 看板 | [Multica](https://github.com/multica-ai/multica) | Agent 上板认领；Review 门；本机 daemon 拉起 Cursor/Codex |
| 人机房间（可选） | [block/buzz](https://github.com/block/buzz) | 不当任务真源；需要「分支当房间 / Agent 成员身份」时再开 |
| QA | Playwright MCP；登录态用 BrowserSkill | 新会话 |

明确不整装：ECC、OPC、three-man-team、agency-agents 目录、**BMAD-METHOD / BMM**、MetaGPT、CrewAI、spec-kit、Octop、oh-my-codex 默认安装、addyosmani 全套、eigent/PI-Desktop/deer-flow/superset。可偷单条规则，见 SURVEY。

---

## 9. 角色与会话隔离

| 角色 | 默认宿主 | 可与谁同会话 | 不可 |
|---|---|---|---|
| 产品 | Cursor（默认可改 Codex 入口） | 设计（G1 前后） | 开发实现会话 |
| 设计 | OpenDesign + Cursor | 产品 | 不得在开发会话里改实现充作「调一下样式」 |
| 架构师（方案/拆卡/评审） | Cursor | 产品 | 不得在开发 worktree 里直接改业务充作评审 |
| 开发 | Multica 拉起的 **某一个** CLI 工人 | 无 | QA、产品入口会话 |
| 项目经理 | Multica | 只读规格与卡 | 不写业务代码 |
| 测试经理 | 新会话 | 无 | 开发会话、实现 worktree 的「接着改」 |

人少时：你 = 产品 + 设计点头 + 架构签字 + 项目经理。开发 Agent 与 QA Agent 仍然必须拆开。设计会话不要接着写业务代码。

---

## 10. 失败与打回

| 现象 | 动作 |
|---|---|
| G1 不通过 | 停在 Backlog；改 proposal/场景，不进设计 |
| G1.5 不通过 | 停在 Backlog；改原型/`DESIGN.md`，不写架构 |
| G2 不通过 | 停在 Backlog；改 design，不打 Ready |
| 自检 CRITICAL | 留在 In Progress |
| 架构越界 | 打回 In Progress，必要时改 design（OpenSpec 允许回改工件） |
| QA 失败且场景仍正确 | 打回 In Progress |
| QA 失败且场景错了 | 产品改 spec，**重新 G1**（小改可由产品+架构口头确认后改文件） |
| 热修膨胀 | 项目经理升格为功能卡 |
| archive 时发现代码与 delta 不一致 | 不准 archive；打回 Review |

---

## 11. 待决清单（最终版要全部勾掉或改写成决定）

- [ ] **A** 有 UI 的功能卡是否强制一条 Playwright 场景？
- [ ] **B** 是否增加 `spike` 类型（有时限、不 archive）？
- [x] **C** 看板：默认 **Multica**。不选 Octop。Vibe/Hermes/GitHub Issues 不再并列。
- [ ] **D** 一张卡并行两个 Codex（同 spec 不同 tasks）是否允许？默认否（WIP=1，且易撞文件）。
- [ ] **E** `plan.md` 是否进 Git？建议进 change 目录，archive 时可留在 `changes/archive/`。
- [ ] **F** 多仓产品用 OpenSpec Stores，还是 workspace 并排 clone（可见不耦合）？
- [ ] **G** always-on 规则预算：建议合计 < 6k token，是否写进最终版硬限制？
- [x] **H** 有 UI 的卡 **强制 G1.5**（OpenDesign 原型 + DESIGN.md）。
- [x] **I** Headroom：**Cursor 与 Codex 都 wrap**。
- [x] **J** `security-audit-skill`：**仅 auth/支付/权限卡 + 发布前全量**，不是每张卡。
- [ ] **K** Buzz 是否现在就开人机房间，还是 Multica 跑稳后再试点？建议：后。
- [ ] **L** teamai `codebase` 能否替代 CodeGraph？建议：先并存，live impact 仍用 CodeGraph。

改最终版时：把本节清空，决定写进正文对应段落，版本改为 v1.0。

---

## 12. 建议的讨论顺序

1. 先拍 §0–§1（新项目 vs 迭代、原则）——若这里不一致，后面步骤都会漂。
2. 拍 SURVEY 日榜匹配：Multica 当板、teamai 当分发、Buzz 不当第二块板——不认就改 §8。
3. 再拍 §3 分流和待决 B（有没有 spike）。
4. 过一遍 §4 主循环，只改「出门条件」里不认的句子。
5. 待决 K/L（Buzz 试点时机、图谱是否合并）。
6. 把 §7 检查单试贴到一次真实小需求上，用一次来改文档，而不是先把文档写完美。试点步骤见 [SETUP.md](./SETUP.md)。

---

## 13. 参考（只读，不是栈）

- [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) overview：agree first；`explore → propose → apply → archive`；archive 才更新真相
- [obra/superpowers](https://github.com/obra/superpowers) Basic Workflow
- [Austin Xu, Stacking OpenSpec and Superpowers](https://austinxyz.github.io/blogs/blog/openspec-superpowers-combined)（2026-04）：`tasks.md` vs `plan.md`；教训写回 `config.yaml`
- [Veath/openspec-spec-driven-superpowers](https://github.com/Veath/openspec-spec-driven-superpowers)
- 本仓库 [docs/standards/新项目启动清单.md](../standards/新项目启动清单.md)（应用骨架，不是本流程的替代）
- 本目录 [SURVEY.md](./SURVEY.md)：日榜匹配（Buzz / Multica / TeamAI）与 token / UI / 质量 skill 的进与不进；含 BMAD 对照（不整装）
- [block/buzz](https://github.com/block/buzz) · [multica-ai/multica](https://github.com/multica-ai/multica) · [Tencent/teamai-cli](https://github.com/Tencent/teamai-cli)
