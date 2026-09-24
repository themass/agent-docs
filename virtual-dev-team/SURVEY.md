# 热度项目怎么进栈（分析稿）

上一版组合几乎只围着对话里点过名的 OpenSpec / Superpowers / Vibe Kanban / CodeGraph 转，这是选型偏差：GitHub 上为 Agent Team、token、前端设计做的项目没有被系统过一遍。本文补上 **看过什么、为什么进、为什么不进**。流程正文仍以 [PROCESS.md](./PROCESS.md) 为准；这里只改「槽位里放谁」。今晚怎么装、本机缺什么见 [SETUP.md](./SETUP.md)。

热度 ≠ 进栈。进栈条件：填一个空槽、能被 Cursor 与 Codex 共用、不抢指挥权、不当 always-on 手册。

---

## 1. Agent Team / 一人公司类（编排层）

这类项目想当「整支虚拟公司」。我们的指挥权已经给了 OpenSpec change + 一块看板，所以它们多数是 **人设包或第二编排器**，不能整仓安装。

| 项目 | 信号 | 它解决什么 | 结论 |
|---|---|---|---|
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | ~247k stars，跨 Cursor/Codex 适配 | 68 agents / 286 skills、token 课、hooks、AgentShield、验证环 | **不整装。** 会变成第三套流程。偷：按语言勾选的 standards、verification loop、token 课里的「skill 里有就别再读文件」 |
| [iamtouchskyer/opc](https://github.com/iamtouchskyer/opc) | One Person Company，16 角色、机械门禁 | 从一句话到 build-verify；独立 review / test-design / gate | **不整装。** 与 OpenSpec 主循环抢阶段。偷：评审必须独立角色；test-design 与 test-execute 分会话（我们 QA 新会话已经对齐） |
| [pie/three-man-team](https://github.com/pie/three-man-team) | Architect / Builder / Reviewer | 三人、token-optimizer 五条规则、禁止跳步 | **不整装。** 角色比我们少（没产品、没测试经理）。偷：五条 token 规则可写进 AGENTS.md 短节 |
| [agency-agents](https://github.com/msitarzewski/agency-agents) / 本仓 `agency-agents-zh` | ~150k，上百人设 | UI 设计师、UX、安全、架构师 prompt | **不当运行时。** 需要某一人设时按文件加载一篇，禁止把目录 always-on |
| **[bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)**（BMM v6） | ~53k；四阶段 + Analyst/PM/Architect/SM/Dev/QA；PRD / epics / stories / `sprint-status.yaml` | 模拟完整敏捷团队；deep-code **只借了它的模块安装器**（每 module 一个完整插件、不合并） | **不整装。** 与 OpenSpec 抢合同，与 Multica 抢板。映射与可偷项见下节 |
| [XiaoDuoYa/codex-with-chatgpt](https://github.com/XiaoDuoYa/codex-with-chatgpt) | 日榜常见 | 对话脑 + Codex 手 | **模式已采用**（Cursor 谈、Codex 领卡），不必再装这个仓 |
| [TencentCloud/Octop](https://github.com/TencentCloud/Octop) | 日榜自托管多 Agent | 第二办公室 | **不进。** 看板只能有一块 |
| OpenCrew 系 | 人审批才合入 | HQ + Claude Code 工人 | **仅当看板改选它。** 与 Vibe/Hermes 互斥 |

deep-code 对 BMAD 的用法容易误读。README 写的是「借鉴 BMAD-METHOD 的**模块管理思路**」：交互勾选模块、每个 module 是独立 Cursor/Codex 插件（`ya-prd`、`ya-dev`…），安装时不合并。它没有把 BMM 的 `/bmad-bmm-*`、PRD 脊柱、sprint-status 当运行时。deep-code 的开发环走的是自己的 `dev` 模块（spec-superflow），不是 `npx bmad-method`。

我们也不装 BMM。槽位对照：

| BMAD / BMM | 我们已有的对应 |
|---|---|
| Analyst / PM 人设 | Cursor 入口 + OpenSpec `explore`/`propose` + Superpowers brainstorming |
| UX 工作流 | OpenDesign + `DESIGN.md` + G1.5 |
| Architect + implementation-readiness | OpenSpec `design.md` / `tasks.md` + G2 + DoR |
| SM / `sprint-status.yaml` | **Multica**（任务真源只能有一块板） |
| Dev story | Codex/`cursor-agent` + Superpowers TDD / worktree |
| Code review / TEA | 新会话 review；QA 新会话 + Playwright |
| 模块勾选、插件不合并 | Multica **按 Agent 绑 skill**；OpenSpec `--tools` 只开真用的宿主；禁止 `--tools all` |

可偷：模块不合并、实现前有硬门、测试设计与执行分会话。不偷：命名人设 always-on、第二套 `/bmad-*` 命令、用 sprint yaml 当第二块板。BMM 自己还在讨论加 OpenSpec 式 Change Set（discussion #1064），说明「项目级 PRD 脊柱」对迭代不够用——我们选 OpenSpec 就是因为这条团队要同时跑 brownfield。

---

## 2. Token 优化（上一版几乎没写）

CodeGraph 是 **少盲搜**，不是压缩。Token 至少三层，上一版只写了检索层。

| 层 | 项目 | 做什么 | 结论 |
|---|---|---|---|
| 0 行为 | ECC / three-man-team 的 token 课；deep-code 规则预算 | 不该读的不读、能并行就并行、长输出丢给子 Agent | **进 AGENTS.md 一小节（<40 行）**，不是再装 286 skill |
| 1 压缩 | [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | 工具输出/日志/JSON/RAG 进模型前压缩；`wrap codex\|cursor`；官方宣称 coding ~20%、JSON 60–95% | **进栈。** Codex/Cursor 工人默认 wrap。压缩发生在本机 |
| 1b 无代理时 | [headroom-skill](https://github.com/roman-ryzenadvanced/headroom-skill) | 把同一套手法写成 skill，无 binary | **仅当不能装 proxy 时的退路。** 不要和 Headroom 代理叠两层 |
| 2 结构检索 | CodeGraph MCP | callers / impact，少 grep 整仓 | **保留。** Headroom 文档也写：检索 MCP 在上游，它在下游压输出 |
| 不做 | claude-context 默认云向量；GitNexus 非商用；Serena 与 Cursor 索引重叠且 GPL | 第三套检索 | **默认不装** |

Headroom 建议搭配 Serena；我们用 CodeGraph 填同一槽，不再加 Serena。

---

## 3. 代码质量 / 优化 skill

| 项目 | 槽位 | 结论 |
|---|---|---|
| Superpowers TDD / code-review | 开发内圈、自检 | **已在主循环** |
| [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) | 架构 Review 或发布前 | **进。** 独立会话、机器可读 finding；日榜热、且不抢主循环 |
| ECC AgentShield / 安全 skill | 与上重叠 | 有 security-audit-skill 就够 |
| Ponytail（本仓 `.cursor/skills/ponytail*`） | 实现时「最少代码」 | **开发按需加载**，不当 always-on |
| agency-agents `engineering-code-reviewer` 等 | 人设 | 需要时加载一篇，不替代 Superpowers review |
| 前端性能 / a11y | 见下一节 ui-ux-pro-max | 设计评审和 QA 用，不进开发 always-on |

---

## 4. 前端设计（上一版完全空）

产品签字只覆盖「做什么」，没有「长什么样」。有 UI 的卡必须加设计槽，否则 Codex 会自行审美。

| 项目 | 它是什么 | 结论 |
|---|---|---|
| [nexu-io/open-design](https://github.com/nexu-io/open-design) | Agent 原生设计工作室：brief → 生成 HTML/原型 → `DESIGN.md`；本机已有 MCP | **进。** 有 UI 的功能：G1 之后、G2 之前出可点击原型和 DESIGN.md，工人只实现不发明视觉 |
| `design-md` / `design-brief` / `brand-extract` | OpenDesign 配套 skill | **进。** 新项目初始化写 `DESIGN.md`；抄参照站用 brand-extract |
| `ui-ux-pro-max` | 50 风格 / a11y / 触控 / 间距的检索式指南 | **进，仅评审时。** 禁止 always-on（整库会炸 token） |
| `frontend-design-ui-ux` | 出实现向 UX spec（流程、状态、组件 brief），明确 **不写代码** | **进，有交互复杂度时。** 与 OpenDesign 分工：一个出画面，一个出状态机/handoff |
| Superpowers Visual Companion | brainstorm 时的 HTML mock | OpenDesign 能出更完整制品时 **降为备选** |
| agency-agents 设计部 9 个人设 | prompt 包 | 不整装；OpenDesign 不够用再点名一篇 |
| Archify / diagram-design | 架构图不是 UI | 技术方案附图时用，不进 UI 槽 |

设计出门条件建议升为 **G1.5**：你点头原型 + `DESIGN.md` 存在，G2 才能签。无 UI 的卡跳过。

---

## 5. 调研 / 浏览器（产品前和 QA）

| 项目 | 槽位 | 结论 |
|---|---|---|
| [last30days-skill](https://github.com/mvanhorn/last30days-skill) | 新产品/新市场：看用户最近在抱怨什么 | **产品澄清可选。** 不当每张卡的必经 |
| [alphaXiv/OpenResearch](https://github.com/alphaXiv/OpenResearch) | 把 coding agent 当研究 agent | 与 last30days 重叠，先用一个 |
| [Tencent/BrowserSkill](https://github.com/Tencent/BrowserSkill) | 登录态真实浏览器 | **QA 登录态站点用。** 普通页 Playwright MCP 即可 |
| Playwright MCP | E2E | **已在 QA** |

---

## 6. 进栈后的完整槽位

| 槽位 | 上一版（对话点名） | 对照日榜之后 |
|---|---|---|
| 规格合同 | OpenSpec | 不变。合同仍是 Git 里的 change，不是聊天 |
| 执行纪律 | Superpowers | 不变。addyosmani/agent-skills 不整装（会变成第二套 SDLC） |
| 人机入口 | Cursor | 不变 |
| 领卡工人 | Codex | Codex + `headroom wrap`；oh-my-codex **不默认装**（`$team`/`$ultraqa` 会抢主循环） |
| **团队 harness 分发** | （手拷 `.agents/skills`） | **[Tencent/teamai-cli](https://github.com/Tencent/teamai-cli)**：Git 仓同步 skills/rules/hooks/MCP 到 Cursor 与 Codex |
| **看板 / 认领** | Vibe / Hermes / Issues 三选一 | **[multica-ai/multica](https://github.com/multica-ai/multica)**：Agent 作为 assignee 上板；驱动 Cursor/Codex；Review 门；本机 daemon |
| **人机同房间（可选）** | （无） | **[block/buzz](https://github.com/block/buzz)**：Agent 是成员不是 bot；分支当房间；Codex ACP。任务真源仍是 Multica，Buzz 不当第二块板 |
| 结构检索 | CodeGraph | 保留 live impact；teamai `codebase`/`recall` 管团队 wiki。不要再叠第三套图 |
| 工具输出压缩 | Headroom | 两边 wrap（已拍板 I） |
| UI 设计 | OpenDesign + DESIGN.md | 不变；G1.5 强制（已拍板 H） |
| UX / 交互 | ui-ux-pro-max、frontend-design-ui-ux 按需 | 另可按需偷 impeccable / hallmark，不当 always-on |
| 安全审计 | security-audit-skill | 仅 auth/支付/权限卡 + 发布前全量（已拍板 J） |
| Agent 全家桶 | 拒 MetaGPT | 继续拒 ECC/OPC/deer-flow/eigent/PI-Desktop/superset 当第二 HQ |

---

## 7. 日榜虚拟团队产品：需求匹配（这次才做）

上一轮的错：把「虚拟团队开源」一律判成「第二套 HQ」然后跳过。日榜上大量项目填的是 **办公层 / 上板认领 / 双宿主同步**，不是再写一套 OpenSpec。

对照需求：产品签字 → 设计 → 架构拆卡 → **Agent 认领** → 实现 → 评审 → QA → archive。空槽是后半段的「团队怎么一起干活」，不是前半段规格工具。

| 日榜项目 | 它实际是什么 | 对应我们的缺口 | 结论 |
|---|---|---|---|
| **[block/buzz](https://github.com/block/buzz)**（Jul 日榜 #1；~33k） | 自托管人机同房间：频道、Git 事件、YAML workflow、`buzz-acp` 接 Codex/Goose/Claude；Agent 有独立密钥与审计 | 没有「人和 Agent 同一身份模型」的办公室 | **进，作房间层，不作任务真源。** 和 Multica 叠两块板就违反原则 2 |
| **[multica-ai/multica](https://github.com/multica-ai/multica)**（分析报告 17 次；~50k） | 「Agents that show up on the board」：issue 指派 Agent；26 种 CLI（含 Cursor、Codex）；本机 daemon；Review 门；token 账 | Vibe 公司已关；原 C 的三选一都不「Agent 当同事上板」 | **进，作唯一看板。** 六列用 Multica issue 状态表达 |
| **[Tencent/teamai-cli](https://github.com/Tencent/teamai-cli)**（2026-09-11 日榜 #5） | 团队 harness：skills/rules/hooks/MCP Git 分发到 Cursor+Codex；摩擦学习；`recall`；`teamai codebase` 图谱 | 「两边读同一套 skill」之前是口头约定 | **进。** 角色用 `teamai roles` 映射产品/设计/开发/QA，避免人人 always-on 全库 |
| **[Yeachan-Heo/oh-my-codex](https://github.com/Yeachan-Heo/oh-my-codex)**（分析 8 次；~33k） | Codex 工作流层：`$plan` `$team` `$code-review` `$ultraqa`、worktree、HUD | Codex 工人增强 | **不默认装。** 会变成第二套 SDLC。需要 HUD/hooks 时再点名，不启用 `$team` 链 |
| **addyosmani/agent-skills**（分析 21 次；~41k） | `/spec`→`/plan`→`/build`→`/test`→`/review`→`/ship` | 与 OpenSpec+Superpowers 同构 | **不整装。** 按需偷 `code-review-and-quality` / TDD / frontend-ui |
| **eigent / openwork / PI-Desktop / AionUi** | Cowork 桌面，再开一个办公室 | 与 Cursor+Multica 抢壳 | **不进** |
| **deer-flow / orca / superset-sh / yc-software/qm** | 舰队 HQ / 多人 harness | 第二指挥权 | **不进；可偷并行舰队 UX** |
| **volcengine/OpenViking**、TencentDB-Agent-Memory | Agent 记忆库 | 会话记忆 | 有 teamai recall 先用；OpenViking 仅当 recall 不够 |
| **alibaba/OpenSandbox**、daytona | 工人沙箱 | 隔离执行 | 本机 daemon（Multica）已给执行面；需要硬隔离再加 OpenSandbox |
| **DeusData/codebase-memory-mcp**、graphify | 另一套代码图 | 与 CodeGraph / teamai codebase 重叠 | **不叠第三套图** |
| **Nutlope/hallmark**、pbakaus/impeccable | 反 slop / harness 设计语言 | 设计质量 | **G1.5 评审按需加载** |
| **chidiwilliams/buzz** | Whisper 转写 | 名字撞车 | **不是** Block Buzz |

匹配原则（修正后）：

1. 规格合同只有 OpenSpec；聊天、频道、看板评论都不是合同。
2. 任务真源只有一块板 = Multica。
3. 双宿主同步用 teamai-cli，不要靠手拷。
4. Buzz 解决「Agent 是成员」，不解决「哪张卡 Ready」。
5. 日榜 Cowork 桌面 / SuperAgent harness = 第二 HQ，仍然不装。

---

## 8. 明确仍不进

日榜热但填不了本流程空槽：hypit（视频克隆）、hister（搜索引擎）、tinycast（启动器）、ever-gauzy（ERP 大盘）、Bonsai-demo、TradingAgents、CloddsBot。

Skill 目录再大（ECC 286、agency-agents 上百、addyosmani 25）也 **按任务加载一篇**。这是 token 原则，不是嫌弃那些项目。
