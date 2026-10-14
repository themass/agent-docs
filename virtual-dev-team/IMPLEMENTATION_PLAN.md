# 虚拟开发团队 · 实施与集成方案

> **状态更新（2026-10-10）：本文降级为 Plan B。**
> 经核实，`paperclipai/paperclip`（MIT、TypeScript、活跃）已经提供了本文描述的控制平面能力：
> 工单、父子任务、依赖唤醒、审批与 signoff 策略、adapter（Codex/Cursor/Claude Code/OpenCode…）、
> 执行环境、预算、artifacts、插件。优先走集成路线，见
> [OSS_INTEGRATION_DECISION.md](./OSS_INTEGRATION_DECISION.md)。
> 仅当 Paperclip 实测无法满足门禁或数据模型要求时，才按本文自建。


> 本文是对 `PROCESS.md`、`SURVEY.md`、`SETUP.md` 的工程化落地补充。附件中的文档视为当前设计草稿和背景材料，不视为不可修改的实现指令。

## 1. 结论

当前项目已经完成了「团队协作流程设计」和「开源组件选型」，但还没有完成真正的产品实现。现在缺少的不是更多 Agent 人设，而是一个可运行的 **控制平面（control plane）**：

- 接收一条需求并创建一次运行（Run）；
- 让产品、架构、开发、评审、QA 等角色按状态机推进；
- 将分析结果和拆解结果落成可追踪的卡片；
- 让 Codex、Cursor Agent 等不同 CLI 通过统一协议认领卡片；
- 在隔离 worktree 中执行；
- 自动运行测试、静态检查、浏览器验收和安全检查；
- 只有满足门禁并完成归档后，任务才进入 Done；
- 所有过程都可重放、审计、恢复和人工接管。

建议不要继续扩充选型，也不要把多个「完整 Agent Team 产品」叠在一起。应建设一个很薄的编排层，复用 Git、GitHub/Gitea、现有 CLI、Playwright 和 CI，把业务规则放在本项目中。

## 2. 建议的目标形态

```text
用户提交需求
    │
    ▼
Run Controller
    ├── Product Analyst     → brief / acceptance scenarios
    ├── Architect           → design / dependency graph / task DAG
    ├── Card Planner         → executable cards
    ├── Dispatcher           → lease / WIP / agent assignment
    ├── Worker Adapter       → Codex / Cursor Agent / 其他 CLI
    ├── Review Gate          → diff / architecture / security
    ├── QA Runner            → unit / integration / Playwright
    └── Archive Manager      → merge / spec archive / final report
    │
    ├── PostgreSQL or SQLite: runs, cards, leases, events, artifacts
    ├── Git provider: branches, worktrees, commits, PRs
    ├── Object storage: logs, screenshots, traces, reports
    └── Web UI / CLI: timeline, board, card details, approvals
```

核心原则：

1. **规格、任务、执行记录分离**：规格是合同，卡片是执行单元，事件日志是事实记录。
2. **数据库是运行时真源，Git 是代码和规格真源**；看板只是数据库事件的视图，不再依赖某个特定看板产品才能运行。
3. **Agent 不是拥有系统权限的管理员**：Agent 只能通过受限工具和卡片租约操作。
4. **所有自动化都可暂停并由人接管**。
5. **先支持单仓库、单项目、单机部署，再扩展多仓库和团队部署**。

## 3. 与现有草稿的关键调整

### 3.1 Multica 不应成为核心依赖

现有设计把 Multica 作为唯一看板，但产品目标其实是「任务编排、认领、执行、验证、交付」。看板是界面，不应成为核心协议。第一版应提供内置 Board API/UI，并增加可选适配器：

- 内置 SQLite/PostgreSQL Board：默认、可测试、可审计；
- GitHub Issues/Projects：同步适配器；
- Multica：外部看板适配器；
- Buzz：消息/房间适配器，不拥有任务状态。

这样即使某个外部项目变更、不可用或不适合自动化，主流程仍能运行。

### 3.2 OpenSpec 不应承担编排

OpenSpec 工件继续作为需求规格合同，但 Run Controller 负责：

- 阶段状态；
- 卡片 DAG；
- Agent 租约；
- 重试、超时、取消；
- 测试结果；
- 归档条件。

不要通过解析聊天记录来判断任务是否完成；必须读取结构化 artifact 和执行结果。

### 3.3 不要把角色实现成常驻人格

角色应是可配置的执行策略，而不是一组永远加载的 prompt：

```yaml
role: architect
capabilities:
  - read_repository
  - read_specs
  - write_artifacts
  - inspect_dependency_graph
forbidden:
  - merge_to_main
  - mark_done
```

角色配置只声明输入、输出、权限、工具和质量门禁。具体提示词按阶段加载，避免所有 Agent 读取全部技能。

## 4. MVP 范围（必须先做完）

### MVP-1：单机、单仓、CLI 优先

- 一个项目配置文件；
- SQLite 持久化；
- CLI 创建 Run；
- 产品分析、架构拆解、卡片生成；
- 卡片状态机和依赖 DAG；
- Codex 与 Cursor Agent 两个 Adapter；
- worktree 隔离；
- Agent 只能领取一张卡（WIP=1）；
- 运行单测、lint、构建；
- 人工批准 G1/G2/Review/QA；
- 生成最终交付报告。

### MVP-2：Web 控制台与自动 QA

- 运行时间线；
- Kanban；
- 卡片详情和 artifact 预览；
- Agent 日志和命令输出；
- Playwright 场景执行；
- 截图、trace、测试报告归档；
- 失败后重试或打回；
- 任务暂停、恢复、取消。

### MVP-3：团队化

- PostgreSQL；
- GitHub/Gitea 集成；
- 多项目；
- 用户、角色、权限；
- webhook；
- 并行卡片；
- 预算、token 和超时控制；
- 外部看板、Buzz、team skill 分发适配器。

## 5. 推荐技术栈

优先选择一个容易被 Codex/Cursor 修改和验证的单仓库：

| 层 | 推荐 | 说明 |
|---|---|---|
| 后端 | TypeScript + Fastify | CLI、API、Worker 共用类型和校验 |
| 数据库 | SQLite + Drizzle；生产 PostgreSQL | MVP 无需 Docker 即可启动 |
| Schema | Zod + JSON Schema | Agent 输出必须结构化校验 |
| 队列 | SQLite lease；后续 BullMQ/Redis | 不把 Redis 放进 MVP 前置依赖 |
| 前端 | React + Vite | 看板、时间线、卡片详情 |
| Git | `simple-git` + 原生 git | worktree、branch、diff、commit |
| Agent | Adapter + JSONL event protocol | Codex/Cursor 命令可插拔 |
| 测试 | Vitest + Playwright | 单测、集成、浏览器验收 |
| 打包 | pnpm workspace | `apps/console`、`apps/api`、`packages/*` |
| 部署 | 本机进程 + Docker Compose 可选 | 不要求 MVP 依赖 Docker |

如果目标仓库已经有明确语言栈，可以保留其栈，只需实现相同的领域模型和 Adapter 接口。

## 6. 核心领域模型

### 6.1 Run

```ts
Run {
  id: string
  projectId: string
  request: string
  mode: "feature" | "bug" | "hotfix" | "spike"
  status: "intake" | "planning" | "awaiting_approval" | "executing" |
          "verifying" | "archiving" | "completed" | "failed" | "cancelled"
  currentGate: "G1" | "G1.5" | "G2" | "READY" | "REVIEW" | "QA" | "ARCHIVE"
  createdAt: string
  updatedAt: string
}
```

### 6.2 Card

```ts
Card {
  id: string
  runId: string
  title: string
  type: "analysis" | "design" | "implementation" | "review" | "qa" | "archive"
  status: "backlog" | "ready" | "claimed" | "in_progress" | "review" |
          "qa" | "blocked" | "passed" | "failed" | "done"
  dependsOn: string[]
  assignee?: string
  lease?: { owner: string; expiresAt: string }
  changePath: string
  acceptance: AcceptanceScenario[]
  artifacts: ArtifactRef[]
  attempts: number
}
```

### 6.3 Agent Adapter

```ts
interface AgentAdapter {
  id: string
  capabilities(): Promise<CapabilitySet>
  start(input: StartAgentInput): Promise<AgentSession>
  interrupt(sessionId: string): Promise<void>
  collect(sessionId: string): AsyncIterable<AgentEvent>
  stop(sessionId: string): Promise<void>
}
```

Adapter 不直接修改看板状态。它只产生事件和 artifact，由 Controller 根据策略转移状态。

### 6.4 事件

至少定义：

- `run.created`
- `artifact.created`
- `gate.requested`
- `gate.approved`
- `card.ready`
- `card.claimed`
- `lease.expired`
- `agent.started`
- `agent.output`
- `commit.created`
- `review.requested`
- `check.completed`
- `card.failed`
- `card.passed`
- `run.paused`
- `run.completed`

事件必须带 `runId`、`cardId`、`actor`、`timestamp`、`correlationId`，并且幂等写入。

## 7. 任务拆解与 Agent 领卡协议

### 7.1 分析输出必须结构化

产品 Agent 不只输出 Markdown，还必须输出：

```json
{
  "problem": "…",
  "users": ["…"],
  "inScope": ["…"],
  "outOfScope": ["…"],
  "acceptanceScenarios": [
    { "id": "AC-001", "given": "…", "when": "…", "then": ["…"] }
  ],
  "risks": ["…"],
  "openQuestions": ["…"]
}
```

未解决的 open question 不允许自动进入 Ready，除非用户明确选择“带假设继续”。

### 7.2 架构 Agent 输出 DAG

架构 Agent 生成任务卡，而不是只写一份长 plan：

```json
{
  "cards": [
    {
      "key": "C-001",
      "title": "实现领域模型",
      "kind": "implementation",
      "dependsOn": [],
      "files": ["packages/domain/**"],
      "verification": ["pnpm test domain"],
      "acceptanceRefs": ["AC-001"]
    }
  ]
}
```

Controller 做静态检查：循环依赖、无验收条件、文件范围重叠、无验证命令、卡片过大，都要在 Ready 前拦截。

### 7.3 认领必须是租约

Agent 领卡不是简单写 assignee：

1. Controller 原子地将 `ready` 改为 `claimed`；
2. 创建短期 lease；
3. 创建 worktree 和分支；
4. 向 Agent 注入卡片、依赖、允许路径、验证命令和禁止事项；
5. Agent 定期 heartbeat；
6. 超时自动回收 lease，保留日志和 worktree 快照；
7. 只有 Controller 能把卡推进到 Review/QA/Done。

## 8. 验证和交付门禁

### G1 产品

- 需求、用户、范围、不做项明确；
- 至少一条可执行验收场景；
- 没有 unresolved blocking question。

### G1.5 视觉

- 仅 UI 需求触发；
- 有原型、状态、响应式和可访问性约束；
- 设计 artifact 已挂到 Run。

### G2 架构

- 卡片 DAG 无环；
- 每张实现卡有文件范围、依赖和验证命令；
- 数据/API/权限变更明确；
- 回滚或失败处理明确。

### Review

- diff 在允许范围内；
- 测试和 lint 通过；
- 无高危安全问题；
- 未修改无关文件；
- Agent 没有自行伪造通过结果。

### QA

- 单元/集成检查通过；
- UI 场景由独立 QA 会话执行；
- 产出原始日志、截图、trace、报告；
- 失败时关联缺陷卡并回到 In Progress。

### Archive

- 所有卡通过；
- PR/commit 已合并；
- OpenSpec change 已归档；
- 生成交付摘要和变更清单；
- Run 才能变为 completed。

## 9. 安全边界

第一版必须从一开始就做，而不是上线后补：

- 每个 Agent 使用独立工作目录和分支；
- 默认禁止访问项目目录以外的文件；
- 命令采用 allowlist，危险命令需要人工批准；
- 网络访问默认关闭或按项目配置；
- secrets 不注入 prompt 和日志；
- 日志脱敏；
- Agent 无法直接写数据库状态；
- Agent 无法把卡标为 Done；
- 代码合并必须经过 Controller gate；
- 所有人工批准记录 actor、时间和理由。

## 10. 分阶段开发计划

### Phase 0：可运行骨架（1–2 天）

- 建立 monorepo；
- 定义 domain schema、状态机和事件；
- SQLite migration；
- CLI：`run create/list/show`、`card list/show`；
- 用 fake adapter 跑通一条 happy path；
- 单测覆盖状态转移和租约。

**出口**：不启动任何真实 Agent，也能模拟“需求→拆卡→认领→验证→完成”。

### Phase 1：真实 CLI 工人（2–4 天）

- 实现 Codex Adapter；
- 实现 Cursor Agent Adapter；
- JSONL 输出解析；
- worktree 创建/回收；
- 命令超时、取消、重试；
- 采集 commit/diff/test report。

**出口**：一个真实 Agent 能领取一张卡并提交可验证变更。

### Phase 2：审批与 QA（2–4 天）

- G1/G1.5/G2/Review/QA 审批 API；
- Playwright runner；
- 独立 QA session；
- 失败回退和缺陷卡；
- archive 流程。

**出口**：完成一张带 UI 的真实需求卡，并保留完整证据。

### Phase 3：Web 控制台（3–5 天）

- Run 列表；
- 需求分析和卡片 DAG；
- Kanban；
- Agent session/log viewer；
- Gate approval；
- QA 报告和最终交付页。

**出口**：用户只提交一条任务，就能观察全流程和人工介入点。

### Phase 4：外部集成（按需）

- GitHub/Gitea；
- Multica；
- Buzz；
- team skill 分发；
- PostgreSQL/Redis；
- 多用户与多项目。

## 11. 第一批可直接创建的开发卡

1. `C-001` 初始化 monorepo、CLI、测试框架和本地启动脚本。
2. `C-002` 定义 Run/Card/Artifact/Event 数据模型和迁移。
3. `C-003` 实现状态机、门禁和幂等事件存储。
4. `C-004` 实现任务 DAG 校验和卡片生成器。
5. `C-005` 实现 lease、WIP=1、heartbeat、超时回收。
6. `C-006` 实现 fake Agent Adapter 和端到端 happy path。
7. `C-007` 实现 Codex Adapter。
8. `C-008` 实现 Cursor Agent Adapter。
9. `C-009` 实现 Git worktree、diff 和验证命令执行器。
10. `C-010` 实现 Review/QA/Archive gate。
11. `C-011` 实现 Playwright QA runner 和证据归档。
12. `C-012` 实现 Web 控制台的 Run/Board/Card 页面。
13. `C-013` 添加权限、命令 allowlist、secret 脱敏和审计。
14. `C-014` 添加 GitHub/Multica 同步适配器。

建议先只做 `C-001` 至 `C-006`，不要在真实 Codex/Cursor 集成之前并行建设所有 UI 和外部服务。

## 12. 第一个验收任务

用一个很小的示例仓库验证：

> “给一个现有 Web 项目增加健康检查接口 `/health`，包含单测、README 说明和 CI 验证。”

必须观察到：

1. 用户提交一句话；
2. 生成产品分析、范围和验收场景；
3. 生成架构说明和 2–3 张卡；
4. 卡片按依赖进入 Ready；
5. Codex 或 Cursor Agent 自动认领一张卡；
6. Agent 在隔离 worktree 中修改代码；
7. Controller 执行测试并保存日志；
8. Review/QA 由独立会话完成；
9. 失败时卡片回退，而不是假装 Done；
10. archive 后输出 commit、测试报告、变更摘要和未解决风险。

## 13. 需要立即决定的产品问题

以下问题不解决，工程实现会反复返工：

- 是否只支持本机 CLI，还是第一版就支持远程 Worker？建议：本机优先。
- 是否允许 Agent 自主决定拆卡？建议：可以提议，必须经过 G2 才能生效。
- 是否允许并行卡？建议：MVP 先串行，卡 DAG 稳定后再开放并行。
- 是否使用 GitHub 作为任务真源？建议：MVP 使用内置 DB，GitHub 作为同步视图。
- 是否默认自动合并？建议：默认人工批准；稳定后按项目策略开启自动合并。
- 是否需要多 Agent 对话？建议：先用 artifact/event 协作，不做自由群聊。
- 是否支持远程模型供应商？建议：Adapter 预留，MVP 只实现 Codex/Cursor。

## 14. 完成标准

当以下条件满足时，才认为这个项目从“流程草稿”进入“可交付产品”：

- 有可启动的 API、CLI、Worker 和 Web 控制台；
- 不依赖 Multica 也能完成端到端流程；
- Codex/Cursor 通过统一 Adapter 领取卡片；
- 卡片、租约、事件、artifact 可恢复和审计；
- Agent 无法伪造 QA、Review 或 Done；
- 至少一个真实需求完成过完整闭环；
- CI 能从干净环境重跑核心测试；
- 有失败、取消、超时、人工接管的测试；
- 文档中的流程与实际状态机、API、CLI 保持一致。
