# 第七章 · 产品表面、包地图、数据目录与对照

> **阅读顺序第 8 步**｜先读 [00](./00-顶层设计与实体边界.md)、[ARCHITECTURE_PART1](./ARCHITECTURE_PART1.md)–[PART2](./ARCHITECTURE_PART2.md)  
> 本章把「代码仓库怎么切包」「CLI/Web/Desktop/SDK 怎么接到同一引擎」「数据落在哪」「和 DeepSeek Harness / Pi 差在哪」「怎么扩展、什么是反模式」写成可学习的长文。  
> 写作标准：[DOC_QUALITY.md](./DOC_QUALITY.md)。

### 本章要回答的问题

1. 每个 `packages/*` **拥有**什么事实来源、**禁止** import 什么？
2. Web/CLI/Desktop/SDK 各自可以调用哪些 API，绝不能把引擎搬进 UI？
3. `PENGUIN_HOME` 树里，哪些是可编辑定义、哪些是追加历史、哪些是索引？
4. 为什么删了 SQLite 对话还在，删了 Trace 对话就没了？
5. DSH 的 Profile/Bundle/Inbox/Waterfall 在 Penguin 里分别对应什么——或**明确不存在**？
6. 和 Pi（最小 agent-core）比，Penguin 更接近哪一侧？
7. 扩展 cookbook 与反模式：最短正确路径是什么？

---

## §0 设计目标与非目标

### 0.1 要解决什么

| 目标 | 落点 |
|------|------|
| 一面引擎、多表面 | `penguin-core` 被 CLI 内嵌、被 Server 托管、被 Desktop 壳复用 |
| 事实来源可备份 | 文件层：`agent_state/` + `traces/` + `.project_config.toml` |
| 列表页要快 | Server SQLite：**索引与聚合**，永不与 Trace 争真源 |
| 可教、可对照 | 与 DSH/Pi 显式对照，禁止把 Cordis 词汇当 Penguin 概念 |
| 扩展有菜谱 | Skill / MCP / ApproveFn / 配置优先于改内核 |

### 0.2 故意不做什么

| 不做 | 原因 |
|------|------|
| 在 Web 包实现第二套 ReAct | 行为必须以 core 为准 |
| 用 SQLite 存对话正文 | Trace JSONL 才是 resume 真源 |
| 提供 DSH 式 `setFactory` 换 loop | 产品选择固定 ContextEngine |
| 把 Desktop 做成另一份数据根默认 | 同源 `PENGUIN_HOME`，避免「装了应用却丢历史」的心智分裂 |

### 0.3 分层一句话

```text
能编辑的与被记录的在文件层；
让消息流动起来的在 SDK（core）；
需要常驻与多用户的在 Server；
其余是渲染（Web/Desktop UI）。
```

---

## §1 完整包地图与依赖规则

### 1.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **`@prismshadow/penguin-core`** | 引擎与 SDK：Agent/Session/Engine/Env/Trace | library spine | 多用户 HTTP 服务 |
| **`@prismshadow/penguin-server`** | Hono + SQLite：Web Human 后端 | BFF | 第二套引擎 |
| **`@prismshadow/penguin-web`** | React SPA：订 OmniMessage 渲染 | 前端 | 业务状态真源 |
| **`@prismshadow/penguin-cli`** | `penguin` bin：终端 Human + 拉起 web/server | CLI | 单独的数据格式 |
| **`@prismshadow/penguin-skills`** | 内置 SKILL.md 库 | content pack | 运行时插件宿主 |
| **`PENGUIN_HOME`** | 数据根 env | `XDG_DATA_HOME` 类角色 | 安装目录（bin 在 `~/.penguin` 其它处） |

### 1.2 仓库树（部署视角）

```text
penguin-harness/
└── packages/
    ├── core/       @prismshadow/penguin-core      ← 引擎与 SDK
    ├── cli/        @prismshadow/penguin-cli       ← bin: penguin
    ├── server/     @prismshadow/penguin-server    ← HTTP + SSE + SQLite
    ├── web/        @prismshadow/penguin-web       ← SPA
    ├── desktop/    @prismshadow/penguin-desktop   ← Electron 壳
    ├── skills/     @prismshadow/penguin-skills    ← 内置 Skill 库
    ├── docs/       @prismshadow/penguin-docs      ← 官方文档站内容
    └── landing/    @prismshadow/penguin-landing   ← 官网落地页
```

官方 architecture 文档的分层图与上表一致（概念对齐 `packages/docs/content/architecture.zh.md`）。

### 1.3 包级「拥有 / 不拥有 / 依赖 / 禁止」

| 包 | **拥有** | **不拥有** | 允许依赖 | **禁止渗入** |
|----|----------|------------|----------|--------------|
| **core** | ContextEngine、OmniMessage、LLM/Env 接口、Agent/Session、State 路径、Trace Writer/resume、Goal/Subagent/Compaction 组装 | 多用户鉴权、React、Electron、产品级用量报表 UI | `@prismshadow/agenthub`、`penguin-skills` | `server`/`web`/`desktop` 反向依赖 |
| **skills** | 库内 `skills/*/SKILL.md` 与分组清单 | 已安装态；执行引擎 | （无 penguin 运行时依赖） | import core 引擎去「跑 Skill」 |
| **cli** | 终端 I/O、`--approve`、子命令（chat/run/config/web/server…） | ReAct 实现；SQLite schema | core、server、skills、agenthub | 在 CLI 里复制一套 Trace 格式 |
| **server** | HTTP/SSE、鉴权、Session 锁（409）、调度、SQLite 索引/用量、把 ApproveFn 接到 API | ContextEngine 源码分叉 | core、skills | 把对话正文只写 DB 不写 Trace |
| **web** | 按 OmniMessage 渲染、审批 UI、模型/Skill 管理页、Trace 视图 | 本地直接 `session.run` 当生产路径（生产走 Server） | **协议/目录面**：`penguin-core` 的 omnimessage、markers、model-catalog 等 | import `ContextEngine` / `Environment.executeTool` 抄近路改行为 |
| **desktop** | Electron 壳、进程托管、可复用本机 server | 独立数据语义 | cli、core、server | 默认另起一套 `PENGUIN_HOME` 而不文档化 |
| **docs** | 官方中英文档 | 学习向中文长文（那是 `doc-sn/`） | — | 与 core 行为矛盾而不改源码 |
| **landing** | 营销页 | 引擎 | — | — |

### 1.4 真实 package.json 依赖方向（摘录）

| 包 | 依赖的 penguin / prism 包 |
|----|---------------------------|
| core | agenthub, penguin-skills |
| cli | agenthub, penguin-core, penguin-server, penguin-skills |
| server | penguin-core, penguin-skills |
| web | penguin-core（主要用于 **类型与纯函数**：omnimessage / markers / model-catalog） |
| desktop | penguin-cli, penguin-core, penguin-server |
| skills / docs / landing | 无 penguin 运行时依赖 |

```text
skills ──► (被 core state 安装时读取)
core   ──► agenthub
cli    ──► core, server, skills
server ──► core, skills
web    ──► core（协议面）──HTTP/SSE──► server ──► core
desktop──► cli / server / core
```

**依赖规则（纪律）**：

1. **向下依赖**：表面 → core；不要 core → web。  
2. **web 可依赖 core 的「无副作用协议模块」**（类型、markers、catalog 纯函数），**不可**在浏览器里直接驱动 Environment 副作用作为产品主路径。  
3. **server 不得重新实现** runTurn / MergeQueue / Compaction。  
4. **skills 包保持内容包**：不依赖 server。

### 1.5 各包职责散文

**core**  
改 ReAct、改工具收尾、改 resume、改 Goal 协议、改压缩——都在这里。对外稳定面是 `createAgent` / `Session.run` / OmniMessage。内部目录直觉：`engine/`、`environment/`、`goal/`、`llm/`、`omnimessage/`、`state/`、`trace/`、`session.ts`、`agent.ts`、`interfaces.ts`。

**cli**  
进程内嵌入 core：适合 CI、无 UI 自动化、本地调试。`penguin web` / `penguin server` 负责拉起常驻面。审批四种模式见 PART2 §7。

**server**  
Web Human 的后端：认证、Project 成员、同 Session 互斥（并发 Task/压缩 → 409）、定时任务读 `agent_state/schedule/*.toml`、用量与错误入库、Trace 目录的**派生缓存**表。schema 文件头写得很直白——见 §4。

**web**  
刷新页面丢的是前端状态，不是文件层真源。聊天、审批、Trace、模型、Skill、用量页都是渲染与编排 HTTP。

**desktop**  
「装成应用」的壳；数据目录仍与 CLI/Web 同源约定。可内嵌 server，也可复用已在跑的实例，避免双开抢端口。

**docs / landing / doc-sn**  
docs = 产品说明权威；doc-sn = 学习向中文架构长文（本系列）；landing = 官网。

### 1.6 本节小结

切包标准是**事实来源**，不是「文件多了就新建包」。新功能先问：协议/执行、常驻多用户、可编辑文件，还是纯 UI？

---

## §2 四条产品表面：可调用什么、禁止 import 什么

### 2.1 表面对照总表

| 表面 | 如何接到引擎 | 可调用（应） | 禁止 |
|------|--------------|--------------|------|
| **SDK** | 直接 `createAgent` → `createSession` → `session.run` | core 公开 API | 依赖 server 才能跑单机脚本（除非你真要多用户） |
| **CLI** | 进程内 core；旗标注入 ApproveFn | 同上 + 子命令改 Project/拉起 server | 在 CLI 维护第二份「会话 DB」当真源 |
| **Web** | HTTP 输入/审批 + SSE OmniMessage | Server API；core 协议模块 | 浏览器内 `new Environment` 跑生产任务 |
| **Desktop** | 托管/复用 server（或等价本地桥） | 与 Web 相同的数据根与 API | 静默使用另一 data root 导致「历史失踪」 |

### 2.2 CLI 流（写入归属）

| 步骤 | 谁 | 落何处 |
|------|----|--------|
| `penguin chat` / `run` | CLI | 终端渲染；ApproveFn 由 `--approve` 编译 |
| `session.run` | core | Trace JSONL；Workspace 副作用 |
| `penguin config model …` | CLI → Project 文件 API | `.project_config.toml` |
| `penguin web` / `server` | CLI 拉起 server | 常驻进程 + SQLite 文件 |

默认 Web 地址：**http://127.0.0.1:7364**（不要和 DSH 文档里常见的 3080 混记）。首次 `admin` + 终端打印的初始密码。

Goal 模式下 `run`：仅目标完成时退出码 0（产品约定，以 CLI 实现为准）。

### 2.3 Web + Server 流（写入归属）

```text
浏览器 Web SPA
  │  HTTP：Prompt / 人工审批决策 / 配置 CRUD
  │  SSE：OmniMessage 流
  ▼
Server (Hono)
  │  鉴权、Session 锁、把请求变成 session.run / approve
  │  SQLite：用户、成员、session 索引、usage、trace_files 缓存…
  ▼
penguin-core
  │
  ▼
PENGUIN_HOME 文件层（Agent State + Trace + scratchpad…）
```

| 步骤 | 执行实体 | 写入归属 |
|------|----------|----------|
| 登录 | server auth | `users` / `auth_sessions` |
| 发消息 | server runtime → Session | Trace +（可选）usage_records |
| 审批 | server 把 UI 决策变成 ApproveFn 结果 | `approval_decision` 进流/Trace；模式可持久在 session/UI prefs |
| 列表 Sessions | server 读 SQLite 索引 + 必要时对账磁盘 | **不以 DB 缺行冒充磁盘无 Trace**（见 trace_files 注释） |
| 渲染气泡 | web | 仅内存/React 状态 |

同 Session 并发 Task/压缩：**409**。这是 Server 产品锁，不是 Engine 内部锁的替代叙事。

### 2.4 Desktop 流

| 模式 | 行为 | 注意 |
|------|------|------|
| 内嵌 server | 应用启动带上后端 | 端口占用；关闭应用 ≠ 删 `PENGUIN_HOME` |
| 复用已运行 CLI web/server | 避免双开 | 确认指向同一 data root |

### 2.5 SDK 最小样例（心智）

```ts
const agent = await createAgent({ agentId: "default_agent" });
const session = await agent.createSession({ workspaceDir: process.cwd() });
for await (const msg of session.run([userText("...")], { approve, signal })) {
  // 渲染 OmniMessage
}
```

SDK 调用方与 CLI 一样站在 Human 边界上：只认 `run` 的入出，不认 Engine 私有方法。

### 2.6 Web 对 core 的合法 import（现状）

生产代码常见模式（示例路径）：

- `@prismshadow/penguin-core/omnimessage` — 类型与谓词  
- `@prismshadow/penguin-core/markers` — `[use_skills]` 等块  
- `@prismshadow/penguin-core/model-catalog` — 展示与分组  

这是**协议对齐**，不是把引擎搬进浏览器。测试里偶尔 import `defaultSystemConfig` 做占位符对齐，同理。

### 2.7 本节小结

所有表面最终都调用（或等价调用）`session.run`，历史都进同一套 Trace。端口 **7364**、admin 初始密码、开发 data 与生产 data 分离，是日常踩坑点。

---

## §3 `PENGUIN_HOME` 完整布局

### 3.1 根解析

```17:25:packages/core/src/state/paths.ts
/**
 * Resolves the local data root directory.
 * Prefers the `PENGUIN_HOME` environment variable, otherwise falls back to `~/.penguin/data`
 * (under the hidden `~/.penguin` home so it never collides with unrelated folders, and in a
 * `data/` subdir kept separate from the installer's binaries under `~/.penguin`).
 */
export function resolveRoot(): string {
  return process.env.PENGUIN_HOME ?? path.join(os.homedir(), ".penguin", "data");
}
```

开发常用独立根（如 `~/.penguin/dev-data`），避免污染日常数据——以你的脚本/`pnpm dev` 约定为准。

### 3.2 完整树（与 paths.ts 对齐）

```text
<root>/                                      # PENGUIN_HOME，默认 ~/.penguin/data
└── <project>/                               # 默认 default_project
    ├── .project_config.toml                 # 模型表与凭据（隐藏，宜 0600）
    └── agents/
        └── <agent>/                         # 默认 default_agent
            ├── agent_state/                 # 可编辑行为定义
            │   ├── system_config.yaml       # 工具、thinking、compaction、skills 段…
            │   ├── AGENTS.md                # 身份与指令
            │   ├── .vault.toml              # Agent 密钥（宜 0600）
            │   ├── skills/<name>/SKILL.md   # 已安装 Skill
            │   ├── schedule/*.toml          # 定时任务定义（Server 执行）
            │   ├── tools/                   # 预留用户工具配置
            │   └── memory/                  # user/ + 每 Workspace 一份 MEMORY.md
            ├── traces/
            │   └── <yyyy-mm-dd>/<sessionId>_<index3>.jsonl
            ├── scratchpad/<session-id>/     # 图、GOAL.yaml、截断 recovery…
            ├── shared_env/                  # 共享解释器/工具环境（按需）
            ├── workspaces/tmp-<8hex>/       # 未指定 workspace 时的临时目录
            ├── benchmarks/                  # 评测题库与得分
            └── snapshots/                   # Agent State 版本快照 v*.tar.gz
```

路径函数一览（均在 `paths.ts`）：`projectDir`、`agentsDir`、`agentDir`、`agentStateDir`、`tracesDir`、`scratchpadDir`、`sessionScratchpadDir`、`goalFilePath`、`projectConfigPath`、`systemConfigPath`、`agentsMdPath`、`agentVaultPath`、`toolsDir`、`memoryDir`、`memoryScopeDir`、`skillsDir`、`scheduleDir`、`benchmarksDir`、`snapshotsDir`。

### 3.3 子树「拥有 / 不拥有」

| 路径 | **拥有** | **不拥有** | 谁读写 |
|------|----------|------------|--------|
| `.project_config.toml` | 模型表与凭据 | Trace | CLI/Web/SDK Project API |
| `agent_state/` | 人设、技能、系统配置、vault、schedule、memory | 某次对话正文 | Agent 加载；模型可用文件工具改（除安全敏感策略外） |
| `traces/` | 追加式会话真源 | 用户密码 | Writer / resume |
| `scratchpad/<session>/` | 会话副产物（图路径、GOAL、recovery） | 长期记忆权威 | Session/Env/Goal；删 Session 时常一并清 |
| `benchmarks/` / `snapshots/` | 评测与状态快照 | 引擎循环 | 产品自进化路径 |
| Server SQLite（常在 server 数据路径） | 用户/授权/索引/用量 | 对话逐条正文权威 | server only |

### 3.4 Workspace 规则

| 规则 | 行为 |
|------|------|
| 显式 `workspaceDir` | 必须已存在；缺失则失败（resume 同样） |
| 未指定 | 建临时 `workspaces/tmp-<8hex>` |
| Session id | 形如 `session-YYYY-MM-DD-HH-mm-ss-<8hex>` |
| 锁定 | 模型与 Workspace 在创建时锁定 |

### 3.5 Vault

`.vault.toml`：键名可进系统 Prompt（`{{VAULT_KEYS}}`），**值不进模型上下文**；注入子进程环境。权限宜 0600。与 Project 模型凭据分工：vault 偏 Agent 级密钥；模型 api_key 偏 Project 模型表（也可空回落环境变量）。

### 3.6 备份 / 迁移优先级

1. `agent_state/`  
2. `traces/`  
3. `.project_config.toml`  
4. （可选）`benchmarks/`、`snapshots/`、scratchpad  
5. SQLite：只拷它 = 只拷索引与账号；**救不回**丢了的 JSONL

### 3.7 本节小结

备份灵魂是 **agent_state + traces + project_config**。Server DB 回答「列表怎么快」「这个月花多少」，不回答「第 37 轮模型说了什么」。

---

## §4 持久化：Trace vs SQLite

### 4.1 新词对照

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **Trace JSONL** | Session 恢复唯一事实来源 | event log / WAL | 「缓存」 |
| **Writer** | 追加与 rotate | log appender | 审批策略 |
| **SQLite（server）** | 索引、鉴权、用量、派生缓存 | 控制面 DB | messages 表真源 |
| **`trace_files` 表** | 磁盘 Trace 树的派生缓存 | search index | 权威「无此会话」证明 |

### 4.2 边界表

| 存储 | **拥有** | **不拥有** | 失败含义 |
|------|----------|------------|----------|
| Trace 分片 | 完整可重放历史（含事件） | 用户密码哈希 | 丢文件 ≈ 丢该上下文段 |
| SQLite `sessions` | 列表元数据、标题等索引字段 | 模型逐字输出权威 | 丢行可扫描磁盘重建（视实现） |
| SQLite `usage_records` | 聚合成本 | 工具 stdout 全文 | 报表空洞，对话仍在 |
| SQLite `goal_state` | UI 读的 goal 运行态 | 取代 GOAL.yaml 协议 | UI 不准；模型信箱仍在 YAML |
| SQLite `trace_files` | 加速列目录 | 断言磁盘不存在 | 注释要求 miss 时 reconcile，禁止假 404 |

### 4.3 schema 文件头（权威表述）

```1:13:packages/server/src/db/schema.ts
/**
 * SQLite table-creation SQL.
 *
 * SQLite stores only indexes and aggregates: users / login sessions / Project authorization /
 * Agent & Session indexes / usage summaries / error records / UI preferences. Agent State,
 * Trace, and Workspace still follow the local directory-based storage rules.
 * Product not yet released: no migration branches — everything is CREATE IF NOT EXISTS, formed
 * once. The one exception: columns added to an existing table after release of a web.db are
 * ALTERed in by the idempotent per-column guard in database.ts (ensureColumn), since CREATE
 * TABLE IF NOT EXISTS never touches an existing table. A *reshaped* index follows the same
 * rule under a new name, with the superseded one dropped on open (idx_usage_session →
 * idx_usage_session_ts): CREATE INDEX IF NOT EXISTS never rebuilds an existing index either.
 */
```

`trace_files` 表注释（派生缓存纪律）：

```131:131:packages/server/src/db/schema.ts
CREATE TABLE IF NOT EXISTS trace_files (       -- DERIVED CACHE of the on-disk Trace tree (services/trace-index.ts): the directories stay the single source of truth, every row is rebuildable from disk, and a row is never authority for absence — consumers reconcile + retry on a miss, so a stale index costs one extra scan, never a false 404
```

主要表职责速查：

| 表 | 职责 |
|----|------|
| `users` / `auth_sessions` | 账号与登录 |
| `projects` / `project_members` | 项目与授权（owner 不在 members） |
| `agents` | Agent **索引**（name/description 在 yaml） |
| `sessions` | Session 索引 |
| `usage_records` / `error_records` | 成本与错误 |
| `schedule_state` | 调度运行态（文件是声明意图） |
| `goal_state` | Goal UI 态 |
| `ui_prefs` / `server_settings` | UI 与管理员设置 |
| `trace_files` / `trace_sessions` | Trace 树派生缓存 |

### 4.4 Trace 分段与压缩

- 路径：`traces/<date>/<sessionId>_<index3>.jsonl`  
- 压缩成功 → index+1 新文件（PART2 §6）  
- resume：读最新 index；若文件以完成的 compaction 收尾，按 resume 规则重建空上下文 + summary  

**一个分片文件 = 一份完整模型上下文**——不要手工把两个分片拼成「假连续」却不走 resume。

### 4.5 写入归属对照

| 事件 | Trace | SQLite |
|------|-------|--------|
| 用户一句话 | 是 | 可能更新 session 索引/标题 |
| tool_call_output | 是 | 否（全文） |
| token_usage | 是（事件） | 常同步进 usage_records |
| 登录 | 否 | 是 |
| 改 Skill 文件 | 否（除非模型用工具改且当轮记录了工具 I/O） | 否 |

### 4.6 本节小结

问「当时说了什么」→ Trace。问「谁有权、花了多少、列表怎么排」→ SQLite。两者争真源时，**文件层赢**。

---


## §5 与 DeepSeek Harness（DSH）实体对照

### 5.1 一句话总差

| | **PenguinHarness** | **DeepSeek Harness（典型心智）** |
|--|--------------------|----------------------------------|
| 定位 | Agent 构建与自进化产品（Skill/Benchmark/Snapshot） | 可逆、可插拔的 harness 外壳 |
| 扩展 | **无**插件运行时；Skill 文件 + MCP + 配置 | Cordis：**一切皆插件** |
| 主循环 | `ContextEngine` **固定**在 core | 默认可替换的 loop 插件 / waterfall |
| 消息 | OmniMessage 一币三用 | SessionEvent + deriveMessages 投影 |
| 插话 | `session.steer` → `[user_steering]` | Inbox 桶 + splice/claim |
| 真源 | Trace JSONL | 事件日志（与插件态交织程度更高） |
| Web 端口 | **7364** | 文档示例常见 **3080**（勿混记） |

### 5.2 实体对照表（翻译用，不是功能打分）

| DSH 概念 | Penguin 近似 | **明确不存在 / 不要硬套** |
|----------|--------------|---------------------------|
| Cordis 插件 | — | **无**插件运行时 |
| Profile / Bundle / patch 组装 | `createAgent` + 可编辑 `agent_state/` | 无 Bundle 安装层 |
| Loop 插件 / `setFactory` | 固定 `ContextEngine` | 换循环 = 源码级 / fork |
| Waterfall（`next()` 链） | — | 无合并扩展 waterfall |
| SessionEvent | OmniMessage（含 event 类 payload） | 不是「再 derive 一层 messages 才喂模型」的主叙事 |
| deriveMessages | GenerativeModel/AgentHub 边界转换 | 引擎热路径不维护第二套私有 UI 模型 |
| Inbox splice/claim | `steer` + carry-over | **无**持久 Inbox 事件类型 |
| Skill 插件包 | `SKILL.md` 文件 | 无 skill provider 插件树（有文件库） |
| 工具随插件集膨胀 | 极简 9 内置 + MCP | 不把「多工具」当核心卖点 |
| 远程 BFF / Typert 等 | server HTTP API（更窄） | 无对等大型 API 生成栈 |

### 5.3 散文：为什么「没有插件」不是残缺

把领域知识放进 `SKILL.md`，把执行放进工具/MCP，把编排留在固定引擎——调试栈更浅：出问题先看 Trace 与 `runTurn`，而不是先猜哪个 plugin 改写了 loop。代价：不能在不改 core 的前提下换掉整个 ReAct。换来的是可教性、可测性与「开箱即 Agent 产品」路径（Benchmark / Snapshot / 自进化 Skill）。

### 5.4 散文：协议

OmniMessage 让「前端渲染的那条」和「resume 读回来的那条」同构。DSH 路线里事件与模型消息的派生更灵活，也更依赖你理解 derive 规则。Penguin 用灵活性换可教性：学习成本集中在一种信封。加事件类型 = **协议变更**（引擎、Writer、Web、文档一起动）。

### 5.5 散文：插话

`steer` 绑定「当前 Task 窗口」；没有 Task 就返回 false，让宿主改发普通 `run`。这和 Inbox「先囤着再由 loop 策略消费」不同——移植时不要假设第二套收件箱；`run` 的 `finally` 会清空队列，Task 结束后不要指望还能捞到旧 steer。

### 5.6 使用对照表的正确姿势

- **可以**：翻译「DSH 里的 X 在 Penguin 叫 Y / 不存在」。  
- **不可以**：当功能清单打分表。两边优化目标不同。  
- 写 doc-sn 或迁移评审时，**主动禁用** Cordis / Profile / Bundle / Inbox 词汇，除非在做显式对照。

### 5.7 本节小结

最大差异：无插件树、固定 ContextEngine、Skill/产品化自进化、OmniMessage + Trace 真源。端口与词汇混用是高频事故源。

---

## §6 与 Pi 简要对照

> Pi 指可嵌入的最小 agent-core + coding harness 一路（对照材料见 deepseek-harness 的 `doc-sn/05-对照-Pi-与-DSH.md` 对 Pi↔DSH 的分析）。本节把 **Penguin** 放进同一三角。

### 6.1 三角一览

| 维度 | **Pi** | **DSH** | **Penguin** |
|------|--------|---------|-------------|
| 定位 | 最小可嵌入 agent-core | 插件平台 + 可换 Driver | 固定引擎的 Agent 产品 |
| Loop | `runLoop` 同步跑完一段 ReAct | 常驻 Driver：wake/kick/idle | `Session.run`：一段 Task（Goal 则外环多 Task） |
| 热路径工作集 | 常以 `AgentMessage[]` 为主 | 事件日志为真源，messages 是投影 | OmniMessage 流 + Trace；引擎持运行态 |
| 插话 | steering / followUp 内存队列 | Inbox 持久桶 | `steer` 队列（随 Task） |
| 扩展 | 回调钩子 + Extensions | Cordis 插件 + waterfall | Skill 文件 + MCP + ApproveFn + 配置 |
| 换整套循环 | 多在钩子/外层 | **一等公民** | **非目标**（改 Engine） |

### 6.2 Penguin ↔ Pi 近似翻译

| Pi | Penguin 近似 | 注意 |
|----|--------------|------|
| 一次 `prompt`/`runLoop` | 一次 `session.run`（无 Goal） | Goal 是外环多次 runTask |
| turn（LLM+tools） | 一次 Request / `runTurn` | 命名别和 DSH Turn 混 |
| steering | `steer` → `[user_steering]` | 都非 DSH Inbox |
| Session JSONL/树（harness 层） | Trace JSONL | Penguin 把 Trace 提到产品真源中心 |
| Extensions | Skill/MCP/表面回调 | 不是同一套扩展 API |

### 6.3 选型直觉

| 你更想要… | 更靠近 |
|-----------|--------|
| 嵌进自己的应用、最小核心、自己管存储 | Pi |
| 可逆插件外壳、可换 loop、事件可投影 | DSH |
| 开箱 Agent 产品、文件 Skill、固定引擎好教好测 | **Penguin** |

Penguin 与 Pi 都偏「固定 ReAct 内核 + 端口/钩子」，与 DSH「Loop 是插件」距离更远。Penguin 比典型 Pi harness 更强调：**产品级数据目录、Goal、Benchmark/Snapshot、Web/Server 多用户面**。

### 6.4 本节小结

三角中 Penguin ≈「产品化的固定引擎」，不是「Cordis 平台」，也不是「最小 embed-only core」。对照时用翻译表，不用打分表。

---

## §7 扩展 cookbook 与反模式

### 7.1 Cookbook：按目标选最短路径

#### A. 加领域能力（最常见）

1. 在 `packages/skills/skills/<name>/` 或直接写到某 Agent 的 `agent_state/skills/<name>/SKILL.md`。  
2. 填好英文 `description`（进索引）。  
3. 正文写清步骤、边界、验收；需要时加 `reference/`。  
4. 用对话或 `[use_skills]` 验证模型会 `read_file` 并遵循。  
5. （可选）Benchmark / Snapshot 做回归。

**不要**：为了「加知识」去改 ContextEngine。

#### B. 加外部工具

1. 跑 MCP server。  
2. 写入 Agent `system_config.yaml` 的 `tools.mcpServers`。  
3. 首次 run 看 `mcp_connect_*` 事件。  
4. 确认审批模式对 `rw` MCP 工具合理。

**不要**：把 MCP 结果在 Web 里「本地再执行一遍」。

#### C. 加内置工具（最后手段）

1. `environment/tools/<name>.ts` 实现 BuiltinTool。  
2. 登记 `BUILTIN_TOOL_FACTORIES`。  
3. `defaultBuiltinTools()` 加默认 config（permission/timeout/maxOutput）。  
4. 同步 `packages/docs/content/tools.{zh,en}.md`。  
5. 单测：失败收敛、截断、超时。

**不要**：工具里 throw 到引擎；不要在工具里做产品审批 UI。

#### D. 换/加模型

1. `penguin config model add` 或 Web 模型页。  
2. 成对填写 `(provider, model_id)`。  
3. 填真实 `context_window`；OpenAI 兼容端点开工具调用。  
4. 新 Session 验证；不要期望旧 Session 热切换模型。

#### E. 自定义审批

1. CLI：`--approve` 或自写 `ApproveFn`。  
2. Server/Web：改 Session 审批模式持久化与 UI。  
3. 依赖 `session.toolPermission(name)`（或等价）实现 read-only。

**不要**：在 Environment 内硬编码 allow-all。

#### F. 长目标任务

1. `session.run(msgs, { goal: { budget } })`。  
2. 教模型维护 `GOAL.yaml` status。  
3. 监控 `goal_finished`。  

**不要**：在 Skill 里用「无限 while」伪造成 Goal。

#### G. 派生子任务

1. 确保深度允许（默认仅 1 层）。  
2. 用 `run_subagent` / `input_subagent`。  
3. UI 认 `origin`；父 Trace 认指针。

#### H. 压缩调参

1. 先改 `system_config.compaction`。  
2. 再考虑 prompt 文案。  
3. 源码级改 summarize 逻辑属于引擎变更，配测试。

### 7.2 反模式清单（禁止重演）

| 反模式 | 为什么坏 | 正确做法 |
|--------|----------|----------|
| 在 Web 改「循环哲学」 | 表面当内核 | 改 core Engine 或接受产品边界 |
| 只写 SQLite 当历史 | resume 失败 | 写 Trace |
| 把 DSH Profile 文档抄成 Penguin 教程 | 心智错位 | 用 Skill + agent_state |
| 拼接 `provider/model` 单字符串当主键 | 凭据发错 | 二元组到底 |
| 压缩失败自动 discard | 丢可恢复历史 | 保留原上下文 |
| 假定存在 Inbox | API 对不上 | 用 steer/run |
| 混记端口 7364/3080 | 连错产品 | 文档写死 7364 |
| 开发用生产 `PENGUIN_HOME` | 污染真数据 | 独立 dev-data |
| Skill 当插件 hook | 没有运行时 | 读文件执行 |
| 子 Agent 不传 approve | 审批模式分裂 | 透传父 callback |
| 手工编辑 Trace 「修数据」 | 破坏上下文不变式 | 新 Session 或正式 resume 工具 |
| web import Environment 跑工具 | 绕过 Server 锁与审计 | 走 API |

### 7.3 扩展点 vs 固定内核（总表）

| 层次 | 内容 | 可换方式 |
|------|------|----------|
| **固定** | ContextEngine ReAct；OmniMessage 主契约；Trace 真源地位 | 改源码 / fork |
| **端口** | LLM / Environment 实现 | 配置、MCP、工具集 |
| **文件** | Skill、AGENTS.md、GOAL.yaml、system_config、schedule | 丢文件 |
| **表面** | ApproveFn、UI、CLI | 注入回调与渲染 |
| **外环** | Goal、Subagent、Compaction 触发 | 仍回调同一 Session/Engine |

### 7.4 本节小结

最短正确路径几乎总是：**Skill → MCP → 配置 → ApproveFn →（很少）内置工具 →（极罕）Engine**。反模式的共同点是「把表面当内核」或「把索引当真源」。

---

## §8 本章总结

1. **包按事实来源切**：core 流动消息；server 常驻多用户与索引；web/desktop 渲染与壳；skills 是内容库；cli 是终端 Human + 拉起器。  
2. **依赖纪律**：表面 → core；web 只用协议面；server 不复制 Engine；skills 保持内容包。  
3. **四表面共数据根**：最终都落到 `session.run` 与 Trace；Web 默认 **http://127.0.0.1:7364**。  
4. **`PENGUIN_HOME` 灵魂**：`agent_state/` + `traces/` + `.project_config.toml`；scratchpad 随 Session；vault 0600。  
5. **Trace vs SQLite**：正文 vs 索引；`trace_files` 是派生缓存，不能假 404。  
6. **vs DSH**：无 Cordis/Profile/Bundle/Inbox/waterfall-loop；用 Skill + 固定 Engine + OmniMessage。  
7. **vs Pi**：都偏固定内核；Penguin 更产品化（数据目录、Goal、多表面、自进化）。  
8. **扩展**：cookbook 自上而下；反模式表当作 code review 清单。

### 8.1 读完本系列应能回答

| 问题 | 答案指向 |
|------|----------|
| 谁封装 ReAct？ | ContextEngine（core） |
| 谁封装副作用？ | Environment |
| 谁封装审批？ | 表面 ApproveFn |
| 历史真源？ | Trace JSONL |
| 加领域知识？ | SKILL.md |
| 和 DSH 最大不同？ | 无插件树 + 固定引擎 |
| 改气泡？ | web，订 OmniMessage |

---

## §9 相关链接

| 目的 | 文档 |
|------|------|
| 顶层边界 | [00-顶层设计与实体边界.md](./00-顶层设计与实体边界.md) |
| 主干细讲 | [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) |
| 能力扩展 | [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) |
| 术语 | [GLOSSARY.md](./GLOSSARY.md) |
| 写作标准 | [DOC_QUALITY.md](./DOC_QUALITY.md) |
| 官方架构 | `packages/docs/content/architecture.zh.md` |
| 官方数据布局 | `packages/docs/content/sessions-and-traces.zh.md` |

源码入口：`packages/core/src/{agent,session,engine,environment,goal,state,trace}.ts`；Server schema：`packages/server/src/db/schema.ts`。



---

## §10 补遗：Server 运行时与锁

### 10.1 实体边界

| 实体 | **拥有** | **不拥有** |
|------|----------|------------|
| **Session 锁（server）** | 同 Session 同时仅一个 Task/压缩；冲突 409 | Engine 内 MergeQueue |
| **调度器** | 读 `schedule/*.toml`，到点开 Session 或向已有 Session 投递 | 在 DB 里重写 toml 意图 |
| **初始密码** | 首次 admin 种子 | 模型上下文 |

### 10.2 写入归属：一次 Web 对话

| 步骤 | 谁 | 磁盘 |
|------|----|------|
| POST 消息 | server | 开始 run；Trace append |
| SSE 推送 | server | 无额外真源 |
| 工具审批等待 | server 挂起 ApproveFn | 决策后写 approval 事件 |
| 结束 | engine | request_end 等；usage 入库 |

### 10.3 定时任务文件 vs `schedule_state`

- **文件**：声明意图（prompt、enabled、period…）——模型也可用文件工具改。  
- **DB `schedule_state`**：运行态（上次触发等）——系统不把运行态写回 toml。  
- Prompt 段 `{{SCHEDULES}}` 教模型「目录即注册表」，见 PART2 对 `DEFAULT_SCHEDULES_PROMPT` 的引用链。

---

## §11 补遗：Desktop 与安装边界

### 11.1 拥有 / 不拥有

| **拥有** | **不拥有** |
|----------|------------|
| 窗口、自动拉起/附着 server、桌面认证 via 标记（schema 中 `auth_sessions.via`） | 另一套 Trace 格式 |
| 打包与更新体验 | 改变 `(provider, model_id)` 语义 |

### 11.2 反模式

- 卸载应用时让用户误以为数据已删（实际 `PENGUIN_HOME` 仍在）——文档与 UI 需说清。  
- 与 CLI `penguin web` 双开抢 7364——优先复用或显式改端口配置。

---

## §12 补遗：从「改需求」反查包

```text
改 OmniMessage 字段
  → core/omnimessage + Writer 兼容 + web 渲染 + docs
  → 视作协议版本变更

改默认系统 Prompt 模板
  → core/state/default-config.ts
  → 已有 Agent 不会自动升级（物化在 yaml）；reset API/文档要说清

改模型目录预设
  → core/state/model-catalog.ts + web models 页

改登录与成员
  → server/db + auth 路由
  → 不动 Trace

改 Skill 预装集合
  → penguin-skills 包 + builtin-agents / loadPreinstalledSkills
```

### 12.1 包职责再压缩成四句

1. **core**：让 OmniMessage 正确地流、存、恢复。  
2. **server**：让多人安全地调用 core，并把索引做快。  
3. **web/desktop**：让人看见并操作 OmniMessage。  
4. **skills/docs**：让人（与模型）学会怎么用。

---

## §13 补遗：与 00 章边界表的交叉引用

读者若只读本章，仍须能回答 00 里的问题。交叉索引：

| 00 实体 | 本章何处加深 |
|---------|--------------|
| Agent / Session | §1 core；§2 表面；§3 目录 |
| ContextEngine | PART1/PART2；本章强调「不要在 web 复制」 |
| Environment | PART2；本章依赖规则 |
| Trace / Writer | §4 |
| Skill | PART2；本章 cookbook A |
| Goal | PART2；§4 goal_state vs YAML |
| ApproveFn | PART2；§2 CLI/Web |
| Project / Vault | §3 |

若源码变更导致路径或表结构变化：**先改 00 与 paths/schema，再改本篇**。

---

## §14 终章检查清单（对照 DOC_QUALITY）

- [x] 包与表面均有拥有/不拥有表  
- [x] Web/CLI/Server 流有写入归属  
- [x] 新词有对照（包名、PENGUIN_HOME、Trace vs SQLite、DSH/Pi 术语）  
- [x] 固定内核 vs 扩展点总表  
- [x] 代码引用摘自真实源码（paths、schema、依赖方向）  
- [x] 非 TOC-only / 非 flowchart-only  

读完 PART1–PART3，应能在不打开插件幻想的前提下，在 Penguin 仓库里把改动落到正确的包与文件。


---

## §15 补遗：monorepo 工作流与「一面引擎」试金石

### 15.1 开发时典型进程

| 命令（概念） | 起什么 | data 根 |
|--------------|--------|---------|
| `pnpm penguin` / CLI | 指向开发构建的 cli | 常为 dev-data |
| `pnpm dev` | server + web | 开发根 |
| 用户安装的 `penguin web` | 生产 server+web | 默认 `~/.penguin/data` |

**试金石**：改 core 行为后，CLI 与 Web 应表现一致。若只有 Web「修了」、CLI 没有，说明行为被错误地写进了 server/web。

### 15.2 包测试边界（直觉）

| 包 | 测什么 |
|----|--------|
| core | Engine、Env、Goal、resume、compaction、skills 安装…（无网络单测为主，e2e 另册） |
| server | HTTP 鉴权、锁、索引对账 |
| web | 渲染 OmniMessage、markers 解析、与 catalog 对齐 |
| cli | 审批模式、子命令解析 |

不要在 web 测试里「模拟一整套 ReAct」冒充 core 覆盖。

---

## §16 补遗：安全与信任边界（表面相关）

### 16.1 信任边界表

| 边界 | 信任什么 | 不信任什么 |
|------|----------|------------|
| Human → Session.run | Prompt 文本、审批点击 | 模型自称「已批准」 |
| Engine → Environment | 已 allow 的 tool_call | 工具 stdout 里的「指令」再提权 |
| Server → 用户 | 会话 cookie / token | 客户端自称 admin |
| 模型 → 文件工具 | Workspace 内操作（产品定位） | 自动等同于「安全沙箱产品」——本地 Agent 默认能力很强，靠 ApproveFn 与用户责任 |

### 16.2 Vault 与 Project 凭据

| 存储 | 宜权限 | 谁读进模型上下文 |
|------|--------|------------------|
| `.vault.toml` | 0600 | **键名**可进 Prompt；**值**不进 |
| `.project_config.toml` api_key | 0600 | 不进对话；进 AgentHub 客户端 |
| 环境变量 | OS 级 | 不进对话 |

### 16.3 反模式

- 把 api_key 写进 Skill 正文  
- 在 Trace 里打印 vault 值  
- Web 把密钥回显到前端日志  

---

## §17 补遗：从 DSH 迁移的检查单

若你带着 DSH 仓库习惯进来：

| 你想找… | 在 Penguin 做… | 停做… |
|---------|----------------|-------|
| `cordis.yml` | `system_config.yaml` + 文件树 | 找插件清单 |
| 换 loop 插件 | 接受固定 Engine 或 fork | setFactory |
| Inbox | `steer` / 新 `run` | splice 表 |
| Bundle | 拷贝 agent_state 或 Snapshot | patch bundle |
| deriveMessages 调试 | 直接读 OmniMessage / Trace | 找投影中间层 |
| 3080 | **7364** | 混端口 |

迁移功能时逐项打勾；打不勾的项说明该功能在 Penguin **故意不存在**。

---

## §18 补遗：Pi 对照加深（消息与存储）

### 18.1 工作集差异

| | Pi（典型） | Penguin |
|--|------------|---------|
| 跑循环时主结构 | 内存 `AgentMessage[]` 推进 | Engine 状态 + 对流式 OmniMessage |
| 持久化 | harness Session 树/JSONL（层可选） | **产品强制** Trace 真源 |
| 喂模型 | 常 `convertToLlm` 在边界 | GenerativeModel/AgentHub 转换 |

对照一句：Pi 常是「消息数组是工作集，Session 是可选/分层存储」；Penguin 是「OmniMessage 贯穿流/存/调度，Trace 是恢复合同」。

### 18.2 扩展差异

| Pi Extensions / hooks | Penguin |
|-----------------------|---------|
| 回调改循环边缘行为 | ApproveFn、steer、表面 |
| 深 Session/compaction Entry 规格 | Compaction + Trace rotate（规格在 engine/trace） |
| 自己嵌应用 | `penguin-core` SDK 同样可嵌；产品还多了 Server/Web |

---

## §19 补遗：数据生命周期场景

### 19.1 删除 Session

| 应清理 | 可能保留 |
|--------|----------|
| 该 session 的 Trace 分片 | Project 模型表 |
| `scratchpad/<sessionId>/`（含 GOAL、recovery、图） | 其它 Session |
| server sessions 索引行 | usage 历史策略（实现可保留聚合） |

### 19.2 删除 Agent

| 应理解 | |
|--------|--|
| 整个 `agents/<agent>/` 树 | 含所有 Trace 与 agent_state |
| 不可恢复除非备份 | SQLite agents 索引行也应删 |

### 19.3 移动 `PENGUIN_HOME`

1. 停 server  
2. 搬迁整个 data 根  
3. 导出 `PENGUIN_HOME`  
4. 启动后必要时重建 trace 索引（派生缓存可重建）  

---

## §20 补遗：Cookbook 场景矩阵

| 场景 | 包 | 关键文件/API | 禁止 |
|------|----|--------------|------|
| 新办公流程 | skills 或 agent_state | SKILL.md | 改 Engine |
| 接 Jira MCP | agent_state yaml | mcpServers | web 直连 Jira 当工具真源 |
| 只读演示 | cli/server | approve=read-only/deny-all | 改工具 permission 绕过 |
| 夜间巡检 | schedule toml + server | schedule/*.toml | 在 DB 造「假调度文件」 |
| 换 DeepSeek→本地 vLLM | project config | client_type/base_url/context_window | 改 AgentHub 调用方拼串 |
| 长科研目标 | Goal | run + GOAL.yaml | 单 Task 里手动 while |
| 并行调研 | Subagent | run_subagent | 深度帽设无穷 |
| 上下文爆了 | compaction | system_config / compact() | 手工删 JSONL 半截 |
| 美化气泡 | web | omni 渲染组件 | 改 payload 语义「图省事」 |
| 多租户 | server | auth + members | 共享同一 Trace 目录不隔离 |

---

## §21 补遗：反模式详解（评审用语）

### 21.1 「表面当内核」

症状：在 React 组件里实现「若有 tool_call 则…」的第二套循环。  
评审用语：*行为必须在 core 可测；UI 只订信封。*

### 21.2 「索引当真源」

症状：只查 SQLite sessions 就对用户说「对话不存在」，而磁盘上 JSONL 还在。  
评审用语：*trace_files 是派生缓存；miss 要对账磁盘。*

### 21.3 「DSH 词汇污染」

症状：PR 描述写「加一个 Bundle 挂到 Profile」。  
评审用语：*Penguin 无此实体；请改写为 agent_state/Skill/MCP。*

### 21.4 「半个模型引用」

症状：API 只传 model_id。  
评审用语：*身份是二元组；半个引用必须 4xx/抛错，禁止猜测 provider。*

### 21.5 「压缩失败丢弃」

症状：summarize 失败后调用 discard「清场」。  
评审用语：*失败保留原上下文与 Trace index；与 engine 契约相反。*

---

## §22 包地图再展开：目录级直觉

### 22.1 core/src

| 目录/文件 | 职责 |
|-----------|------|
| `agent.ts` | createAgent、Session 工厂、SubagentRunner、createLLM |
| `session.ts` | Human 边界、ensureReady、Goal 分流、compact |
| `engine/context-engine.ts` | ReAct、steer、compaction |
| `environment/` | executeTool、MCP、builtin tools |
| `goal/` | GOAL.yaml、runGoalLoop |
| `llm/` | GenerativeModel、context limits |
| `omnimessage/` | 信封、builders、markers |
| `state/` | paths、agent_state、project、skills、defaults |
| `trace/` | Writer、resume |
| `interfaces.ts` | LLM/Env/ApproveFn 契约 |

### 22.2 server/src（直觉）

| 区域 | 职责 |
|------|------|
| `http/` / `api/` | 路由 |
| `db/` | schema + repos |
| `auth/` | 登录 |
| `runtime/` / `services/` | 把 HTTP 接到 core Session |
| `lock.ts` | Session 互斥 |

### 22.3 web/src（直觉）

| 区域 | 职责 |
|------|------|
| `features/chat` | 流式聊天、技能/Goal 输入辅助 |
| `features/traces` | Trace 查看 |
| `features/models` | 模型表 UI |
| `lib/omni` | OmniMessage 流模型 |

---

## §23 终章：把 PART1–3 串成一条故事

```text
人类在 Web/CLI 输入
  → Session.run（Human 边界）
  → ensureReady（工具表 + 懒 MCP + LLM）
  → 若 goal：外环多 Task；否则单 Task
  → ContextEngine：LLM ↔ ApproveFn ↔ Environment
  → 需要时 Subagent / Compaction
  → Writer 追加 Trace；Server 更新索引与用量
  → Web 渲染同一 OmniMessage
```

扩展时插入点：

- 知识 → Skill 文件  
- 工具 → MCP / 极少 builtin  
- 策略 → ApproveFn  
- 长目标 → Goal  
- 长上下文 → Compaction  
- 委派 → Subagent  

**不要**插入的点：Cordis 插件槽、第二套 Web Engine、SQLite messages 真源。

---

## §24 本章自检（DOC_QUALITY）复述

读者应能指出：

1. 状态 X（例如某次 assistant 文本）由实体 Y（Trace）独占。  
2. 需求 Z（例如加领域知识）该动 Skill 文件，不该动 ContextEngine。  
3. DSH 的 Bundle/Inbox 在 Penguin **不存在**。  
4. Pi 与 Penguin 都偏固定内核，但 Penguin 数据与产品面更重。  
5. `PENGUIN_HOME` 备份优先顺序。  

若不能，回到 §1–§4 的边界表，而不是只看 mermaid。


---

## §25 补遗：SDK 嵌入方与 Server 宿主的责任分割

### 25.1 两种宿主

| 宿主类型 | 例子 | 必须自己做的事 | 可交给 core 的事 |
|----------|------|----------------|------------------|
| **嵌入式 SDK** | 脚本、内部工具、CLI | 提供 ApproveFn、signal、渲染/日志、选择 workspace 与模型 | ReAct、工具收尾、Trace 写入（若传入 TraceSink）、Goal/Subagent |
| **Server 宿主** | `penguin-server` | 鉴权、多租户隔离、Session 锁、把 HTTP 审批桥到 ApproveFn、用量入库、SSE 帧 | 同上（全部委托 Session） |

### 25.2 嵌入式最小责任清单

1. `createAgent` / `createSession` 参数合法（二元组或默认）。  
2. `approve` 永不挂死（超时策略属于宿主）。  
3. 消费 async generator 直到结束或 abort。  
4. 决定 Trace 根是否使用默认 `PENGUIN_HOME`。  
5. 不要在宿主里复制 `runTurn`。

### 25.3 Server 额外责任清单

1. 认证与 Project 成员检查先于 run。  
2. 同 Session 互斥。  
3. 将用量事件投影到 SQLite（**附加**，不替代 Trace）。  
4. Trace 索引 miss 时对账磁盘。  
5. 调度器只解释 toml，不把 DB 运行态写回声明文件。

### 25.4 拥有表：宿主 vs core

| 对象 | 宿主拥有 | core 拥有 |
|------|----------|-----------|
| 用户身份 | 是（server） | 否 |
| OmniMessage 语义 | 否 | 是 |
| 审批 UX | 是 | 否（只认回调结果） |
| 工具副作用 | 否 | Environment |
| 对话真源 | 否 | Trace |

### 25.5 协作：Server 审批一轮（写入归属）

| 步骤 | 谁 | 写哪里 |
|------|----|--------|
| SSE 已推送 tool_call | server←engine | Trace 已有 tool_call |
| 浏览器点允许 | web→HTTP | server 唤醒等待中的 ApproveFn |
| 返回 allow | ApproveFn resolve | Engine 继续 |
| executeTool | Environment | 工具输出 → 流/Trace |
| usage | engine 事件 | server 可写 usage_records |

### 25.6 反模式：宿主「帮忙」过度

- 宿主在调用 `run` 前「预执行」MCP 并注入假 tool_call_output。  
- 宿主改写 OmniMessage 类型字段以「兼容旧前端」，导致 resume 不对称。  
- 宿主把 Goal 做成纯前端 while 调多次 run，却不走 `{ goal }`——丢失 GOAL.yaml 协议与 goal_finished。

### 25.7 小结

SDK 嵌入与 Server 托管是同一 Human 边界的两种实现密度：前者薄，后者厚在**多用户与索引**，薄在**绝不复制引擎**。


---

## §26 源码锚点附录（PART3 强制引用）

> 本节把本章关键断言钉回真实文件，避免「只有表格没有出处」。

### 26.1 数据根与 Goal 路径

```17:25:packages/core/src/state/paths.ts
/**
 * Resolves the local data root directory.
 * Prefers the `PENGUIN_HOME` environment variable, otherwise falls back to `~/.penguin/data`
 * (under the hidden `~/.penguin` home so it never collides with unrelated folders, and in a
 * `data/` subdir kept separate from the installer's binaries under `~/.penguin`).
 */
export function resolveRoot(): string {
  return process.env.PENGUIN_HOME ?? path.join(os.homedir(), ".penguin", "data");
}
```

```50:63:packages/core/src/state/paths.ts
/** `<agentDir>/agent_state`. */
export function agentStateDir(root: string, projectId: string, agentId: string): string {
  return path.join(agentDir(root, projectId, agentId), "agent_state");
}

/** `<agentDir>/traces`. */
export function tracesDir(root: string, projectId: string, agentId: string): string {
  return path.join(agentDir(root, projectId, agentId), "traces");
}

/** `<agentDir>/scratchpad`, the Agent's temporary/draft file directory (the model creates a subdirectory per Session id). */
export function scratchpadDir(root: string, projectId: string, agentId: string): string {
  return path.join(agentDir(root, projectId, agentId), "scratchpad");
}
```

```98:119:packages/core/src/state/paths.ts
/**
 * `<projectDir>/.project_config.toml`, the Project's single config file (a hidden file, not
 * shown by default `ls`, written with mode 0600; model entries are inlined with their credential,
 * see state/project-config.ts).
 */
export function projectConfigPath(root: string, projectId: string): string {
  return path.join(projectDir(root, projectId), ".project_config.toml");
}

/** `<agentStateDir>/system_config.yaml`. */
export function systemConfigPath(root: string, projectId: string, agentId: string): string {
  return path.join(agentStateDir(root, projectId, agentId), "system_config.yaml");
}

/** `<agentStateDir>/AGENTS.md`. */
export function agentsMdPath(root: string, projectId: string, agentId: string): string {
  return path.join(agentStateDir(root, projectId, agentId), "AGENTS.md");
}

/** `<agentStateDir>/.vault.toml`, the Agent-level environment-variable vault (see state/agent-vault.ts). */
export function agentVaultPath(root: string, projectId: string, agentId: string): string {
  return path.join(agentStateDir(root, projectId, agentId), ".vault.toml");
}
```

### 26.2 SQLite 只做索引（文件头 + sessions 表起头）

```1:13:packages/server/src/db/schema.ts
/**
 * SQLite table-creation SQL.
 *
 * SQLite stores only indexes and aggregates: users / login sessions / Project authorization /
 * Agent & Session indexes / usage summaries / error records / UI preferences. Agent State,
 * Trace, and Workspace still follow the local directory-based storage rules.
 * Product not yet released: no migration branches — everything is CREATE IF NOT EXISTS, formed
 * once. The one exception: columns added to an existing table after release of a web.db are
 * ALTERed in by the idempotent per-column guard in database.ts (ensureColumn), since CREATE
 * TABLE IF NOT EXISTS never touches an existing table. A *reshaped* index follows the same
 * rule under a new name, with the superseded one dropped on open (idx_usage_session →
 * idx_usage_session_ts): CREATE INDEX IF NOT EXISTS never rebuilds an existing index either.
 */
```

```41:50:packages/server/src/db/schema.ts
CREATE TABLE IF NOT EXISTS agents (           -- index only; name/description live in system_config.yaml
  project_id TEXT NOT NULL,
  agent_id   TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, agent_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  session_id    TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL,
  agent_id      TEXT NOT NULL,
```

### 26.3 Human 边界在 interfaces（与表面分工对齐）

```1:16:packages/core/src/interfaces.ts
/**
 * Internal SDK interface contracts: LLM, Environment.
 *
 * `context_engine` only handles OmniMessage; protocol conversion and concrete implementations
 * are each interface's own responsibility.
 * Human is not an "interface/class with methods" but the SDK's input/output boundary itself:
 * output is streamed by `Session.run()` as an async generator, and input is delivered via
 * `run`'s `RunOptions` — approvals are requested one at a time through the injected `approve`
 * callback, and interruption goes through `signal`. Hence no Human interface is defined here.
 *
 * These types form the foundational contract shared by all units; implementing units integrate
 * against them.
 *
 * Docs: packages/docs/content/interfaces.{zh,en}.md (site path /docs/interfaces) explains each
 * contract and its extension seams — keep the page in sync when changing signatures here.
 */
```

### 26.4 CLI 审批模式是表面策略编译器

```13:23:packages/cli/src/approval.ts
/** Valid string values for the `--approve` option (includes the default allow-all, so scripts can specify it explicitly and get the default behavior). */
const APPROVE_MODES = ["allow-all", "deny-all", "read-only", "always-ask"] as const;

/**
 * Approval mode (derived from APPROVE_MODES, the single source of truth):
 *   - `allow-all`: auto-approve every tool (default mode);
 *   - `deny-all`: auto-reject every tool;
 *   - `read-only`: auto-approve read-only tools (permission === "r"), defer the rest to a human;
 *   - `always-ask`: interactive approval for each call.
 */
export type ApprovalMode = (typeof APPROVE_MODES)[number];
```

### 26.5 新词对照（本章补强）

| 名词 | 一句话 | 接近的旧知识 | **不是**什么 |
|------|--------|--------------|--------------|
| **派生缓存（trace_files）** | 可由磁盘重建的加速表 | search index | 权威否定来源 |
| **Human 边界** | `Session.run` 入出约定 | 端口 / use-case API | `class Human` |
| **一面引擎** | CLI/Web/Desktop 行为同源 | single core | 各表面私有 loop |
| **内容包（skills）** | 只提供文件、不执行 | npm content module | Cordis 插件宿主 |
| **控制面 DB** | 用户/授权/用量/索引 | 运营库 | transcript 库 |

### 26.6 写入归属速查卡（钉在墙上）

| 动作 | 主语 | 宾语（写哪里） |
|------|------|----------------|
| 安装 Skill | `installSkill` | `agent_state/skills/` |
| 跑一轮对话 | ContextEngine + Writer | `traces/...jsonl` |
| 登录 | server auth | SQLite users/auth_sessions |
| 列表 Session | server | 读 SQLite；miss 对账 traces/ |
| 渲染气泡 | web | 仅前端状态 |
| Goal 完成 | runGoalLoop | 流上 `goal_finished`；YAML 保持模型最后写入 |

### 26.7 与 PART2 的分工（防重复误解）

| 问题 | 去哪篇 |
|------|--------|
| Skill 渐进加载、九工具、Goal、Subagent、Compaction、Approve 细节 | PART2 |
| 包依赖、表面、目录树、SQLite、DSH/Pi、cookbook | **本篇 PART3** |
| OmniMessage / runTurn / Trace resume 主干 | PART1 |
| 谁拥有什么（总表） | 00 |

---

## §27 收束

PART3 写完后，仓库地图、数据合同、对照与扩展菜谱应足够支撑 code review 对话。若源码漂移，优先更新 `paths.ts` / `schema.ts` / `interfaces.ts` 注释，再改本篇与 00。
