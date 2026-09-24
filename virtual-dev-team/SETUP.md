# 虚拟开发团队 · 落地搭建（先跑起来）

| 项 | 内容 |
|---|---|
| 状态 | **试点手册** — 配合 [PROCESS.md](./PROCESS.md) v0.3 |
| 日期 | 2026-09-20 |
| 本机快照 | Cursor Agent `cursor-agent`、Codex CLI `0.134.0` **已装**；`openspec` / `headroom` / `multica` / `teamai` **未装**；**没有 Docker** |
| 图 | [架构](./diagrams/virtual-dev-team-stack.architecture.html) · [主循环](./diagrams/virtual-dev-team-loop.workflow.html) |

流程文档讲「应该怎样」。本文讲 **今晚怎么装、怎么验证、什么先别碰**。

---

## 1. 能不能落地？

**能。** 但一次装齐会失败：本机没有 Docker，Multica 自托管、Headroom 的 Docker 安装器都走不通；Buzz 会变成第二块板；teamai-cli 和 OpenSpec 都会往 Cursor/Codex 写 skill，叠在一起容易抢命令。

正确策略是 **三条波次**。第一波只证明：一张卡能从签字走到 archive，工人不能自己 Done。

| 判定 | 结论 |
|---|---|
| 双宿主 | **已具备。** `cursor-agent` 与 `codex` 都在 PATH |
| 规格合同 | **今晚可装。** OpenSpec 是 npm CLI，不依赖 Docker |
| 执行纪律 | **今晚可装。** Superpowers：Cursor 插件 + Codex 符号链接 |
| 看板 | **用 Multica 桌面（托管），不要自托管。** 自托管要 Docker |
| 压缩 | **本周用 Python 版 Headroom。** `uv tool install`，不要 curl Docker 安装器 |
| 设计 | **已有。** 本机 `~/.agents/skills` 里已有 `design-md` / `design-brief` / `brand-extract` / `frontend-design-ui-ux`；Cursor 已接 OpenDesign MCP |
| 图谱 | **第一张卡先不用。** 需要时用 `headroom wrap --code-graph`（codebase-memory-mcp），不要再装第三套 |
| Buzz | **试点期不装。** 待决 K：Multica 跑稳再说 |
| 试点仓 | **不要在 `deepagents/` 根目录 `openspec init`。** 这是大 monorepo，会把 workflow 文件摊进根目录。用一个新的小仓 |

---

## 2. 集成方案（谁连谁）

三件东西不要混：

```text
你 ──签字──► Cursor（产品/架构/G1–G2）
                 │
                 ├─ /opsx:* 读写 ──► 试点仓 openspec/     ← 合同（Git）
                 ├─ OpenDesign MCP ──► DESIGN.md / 原型   ← 有 UI 才走
                 └─ 卡 Ready 后 ──► Multica 桌面
                                      │
                                      ├─ assignee = Codex-worker  ──► headroom wrap 后的 `codex`
                                      └─ assignee = Cursor-worker ──► `cursor-agent`（难模块）
                                      两边都读同一份 openspec/ 与 AGENTS.md

QA = 新开一个 Cursor 会话，只跑场景，不复用开发聊天
```

| 项目 | 角色 | 连到哪 | 第一波 |
|---|---|---|---|
| Cursor / `cursor-agent` | 人机入口 + 难模块工人 | 读 `openspec/`、OpenDesign MCP | **必装（已有）** |
| Codex CLI | 领卡工人 | 读同一仓；Multica daemon 调 `codex` | **必装（已有）** |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | 规格生命周期 | `openspec init --tools cursor,codex` | **今晚** |
| [Superpowers](https://github.com/obra/superpowers) | TDD / worktree / review | Cursor `/plugin-add`；Codex 符号链接 | **今晚** |
| [Multica](https://github.com/multica-ai/multica) 桌面 | 唯一看板 | 本机 daemon 发现 `codex` 与 `cursor-agent` | **今晚（托管桌面）** |
| OpenDesign + DESIGN.md | G1.5 | 已有 MCP / skills | **今晚用现成的** |
| [Headroom](https://github.com/headroomlabs-ai/headroom) | 压缩工具输出 | `uv tool install`；`wrap codex`；Cursor 按打印出的配置改 | **本周** |
| [teamai-cli](https://github.com/Tencent/teamai-cli) | 团队 skill 分发 | 另开一个 team 仓，**不要**把 `/opsx:*` 再拷一遍 | **第二人加入时** |
| Playwright MCP | QA | Cursor 已有 | 有 UI 的卡才开新会话 |
| `security-audit-skill` | 安全评审 | 按需加载 | auth/支付卡才装 |
| Headroom `--code-graph` | live callers | wrap 时加开关 | 盲搜痛了再开 |
| [block/buzz](https://github.com/block/buzz) | 人机房间 | 不当任务真源 | **不装** |

skill 所有权（避免互相覆盖）：

| 谁写 | 写什么 | 不要写 |
|---|---|---|
| OpenSpec `init` | 项目内 `openspec/` + `/opsx:*` | 产品手册、风格库 |
| Superpowers | 怎么写码（TDD、worktree、review） | 规格阶段 |
| 根 `AGENTS.md` | 测试命令、红线、token 五条（<40 行） | 整本规范 |
| teamai（后装） | `culture.md`、角色过滤的额外 skill | 再发布一套 propose/apply |

### 2.1 工人、入口、插件、skill（答常见混淆）

**工人（领卡执行）和入口（你坐下来谈需求）不是同一件事。** 能被 Multica 拉起 ≠ 适合当你的签字台。

#### 谁能当工人

Multica 驱动的是 **本机已登录的 CLI**，官方表里包括 `cursor-agent`、`codex`、`hermes`、`opencode`、`claude` 等约 26 种。领卡条件只有四条：PATH 上有二进制、已登录、能读同一份 `openspec/` + `AGENTS.md`、**不能自己把卡标 Done**。

| CLI | 当工人 | 说明 |
|---|---|---|
| `codex` | **默认工人** | 无头好、Headroom `wrap codex` 成熟 |
| `cursor-agent` | **难模块工人** | 和 IDE 不是同一个进程；skill 要以仓库文件为准，不要只靠 IDE 插件 |
| `opencode` | 可加 | OpenSpec `--tools opencode`；Headroom 可 `wrap opencode` |
| `hermes` | 可加 | OpenSpec 有 `hermes` adapter；Headroom wrap 还不稳定，先裸跑 |
| `claude` | 可加 | 和 Codex 同类工人；不要再当第二套 HQ |
| OpenHands | **不当 Multica 工人** | 官方 provider 表没有它；它是带沙箱的另一套调度。硬接会变成第二块板 |

不要同时雇五个工人抢同一张卡。WIP=1：一张卡一个 assignee。多宿主的意义是 **按卡选人**（默认 Codex，难模块 Cursor，开源栈可试 OpenCode），不是并行舰队。

#### 谁能当人机入口

**都能聊，不该对等。**

| 宿主 | 当入口 | 原因 |
|---|---|---|
| **Cursor IDE** | **默认签字台** | 斜杠命令、MCP（OpenDesign / Playwright）、看得见原型，G1.5 必须人眼看 |
| Codex CLI / IDE | **可以，作第二入口** | 终端里 `$openspec-propose` 一样写合同；弱项是看原型、点 MCP、和设计师对着屏幕改 |
| OpenCode TUI | 可作个人入口 | 条件：写进同一个 `openspec/`，卡仍上 Multica |
| Hermes / OpenHands UI | **不作团队入口** | 容易在各自 UI 里另开流程；Hermes 作工人即可 |

规则：入口可以有多个窗口，**合同和看板各只有一份**。你在 Codex 里 propose 的 change，Cursor 里必须能看见；禁止「Cursor 走 OpenSpec、Codex 另写一份 plan」。

试点默认：**人坐 Cursor，卡派 Codex。** Codex 当入口是熟练以后的事，不是 Wave 0。

#### 用没用到 plugin

用了，但是 **按宿主各用各的分发面**，不要理解成「装一个 Cursor 插件，所有工人都会」。

| 层 | Cursor IDE | `cursor-agent` 工人 | Codex | OpenCode |
|---|---|---|---|---|
| 规格命令 | OpenSpec 写入 `.cursor/commands` + `.cursor/skills`（`/opsx-propose`） | 读仓库 `.cursor/skills` / `.agents/skills` | OpenSpec 写入 `.agents/skills`（`$openspec-*`，**不生成 command 文件**） | `.opencode/skills` + commands |
| 写码纪律 | **`/plugin-add superpowers`**（Cursor plugin） | 不要只靠 IDE 插件；把同一套 skill **文件**放到 `.agents/skills` 或 `.cursor/skills` | 官方做法是 clone + 链到 `~/.agents/skills/superpowers`；Codex 也有 plugin 市场，试点不走市场 |
| 压缩 | `headroom wrap cursor` 打印代理配置（不自动改 IDE） | 跟 IDE 配置走 | `headroom wrap codex` 真启动 | `headroom wrap opencode` |
| 看板注入 | — | Multica 跑前把 **绑在这个 Agent 上的 skill** 写进 `.cursor/skills/` | 写入该次 run 的 `$CODEX_HOME/skills/`（不污染全局） | `.opencode/skills/` |

Cursor 的 plugin 是 **IDE 分发单位**（skill + command + MCP + hook 打成包）。Codex 的 plugin 是另一套市场，用来分发 skill，和 Cursor 插件 **不互通**。跨工人真正能共用的是仓库里的 `SKILL.md`（`.agents/skills/` 被 Cursor / Codex / OpenCode 交叉读取）。

因此 Wave 0 的做法是：**IDE 用 plugin 图省事；工人用文件 skill 保命。** Superpowers 两边都要有文件可见；不要假设 `/plugin-add` 之后 `cursor-agent` 一定看得到。

#### 预装哪些 skill 才合理

角色 = **会话 + 允许加载的 skill**，不是再装一套「产品 Agent / 架构 Agent」人设包。agency-agents、ECC 68 agents、addyosmani 全套 SDLC **不预装**。

按角色拆（always-on 越少越好）：

| 角色 | 宿主 | 预装 / always 可见 | 按需加载 | 不要给这个角色 |
|---|---|---|---|---|
| 产品 | Cursor 入口 | OpenSpec `explore` / `propose`；Superpowers **brainstorming**；短 `AGENTS.md` | 新产品才 `last30days-skill` | TDD、worktree、实现类 skill |
| 设计 | Cursor + OpenDesign | `design-md` | `design-brief`、`brand-extract`、`frontend-design-ui-ux`、`ui-ux-pro-max` | 写业务代码的 skill |
| 架构 | Cursor 入口 | OpenSpec `propose` 后半 / 拆 `tasks.md` | CodeGraph MCP；auth 卡才 `security-audit-skill` | Superpowers 实现循环（评审另开会话） |
| 开发工人 | Codex / `cursor-agent` / 可选 OpenCode | **仓库** `AGENTS.md` + Superpowers **TDD / worktree / finishing-branch** + OpenSpec **apply**（只读规格去实现） | `ponytail` 一类「少写代码」；语言 standards 按栈点名 | brainstorming、产品探索、整本 UX |
| 架构评审 | **新会话** | Superpowers **review** | 安全面才 security-audit | 实现 worktree |
| QA | **新会话** | Playwright MCP（有 UI） | 登录态 BrowserSkill | 任何实现 skill |
| 项目经理 | Multica | 无编码 skill | 可选 [Multica CLI skill](https://github.com/multica-ai/multica-cli)，让入口 Agent 能改卡状态 | 不要让工人绑定「自己标 Done」 |

绑定方式（比「全局预装」更重要）：

1. **仓库文件**：`.agents/skills/` 放跨宿主共用的（OpenSpec、Superpowers 实现子集）。
2. **OpenSpec init**：只对 **真会用的宿主** 开 `--tools`。Wave 0：`cursor,codex`。加 OpenCode/Hermes 工人时再补对应 id，不要 `--tools all`。
3. **Multica 按 Agent 绑 skill**：产品 skill 只绑 Cursor-PM；TDD 只绑 Codex-worker。这是防止「工人开始做产品探索」的机制。
4. **Cursor plugin**：Superpowers 给 **坐在 IDE 里的你**；工人侧另有文件副本。
5. **teamai roles**：第二人加入后再按角色过滤，不在 Wave 0 做。

Wave 0 预装清单（就这些）：

- OpenSpec（`--tools cursor,codex`）
- Superpowers（IDE plugin + `~/.agents/skills` 文件）
- 短 `AGENTS.md`
- 已有的 OpenDesign 相关 skill（有 UI 才调用）

Wave 1 再加：Headroom（wrap，不是 skill）、teamai。  
按卡再加：`security-audit-skill`、`last30days`、UX 三件套。

---

## 3. 今晚：Wave 0（约 60–90 分钟）

目标：新仓里走完 **一张最小卡**（无 UI 也行）：propose → 你点头 → Multica 指派 Codex → 实现 → 你当 QA 新会话 → archive。

### 3.1 新建试点仓（不要用 deepagents 根）

```bash
mkdir -p ~/work/vdt-pilot && cd ~/work/vdt-pilot
git init
printf '%s\n' '# vdt-pilot' '虚拟开发团队试点：一张卡走通主循环。' > README.md
```

把下面保存为 `AGENTS.md`（保持短）：

```markdown
# vdt-pilot

- 合同：`openspec/`。聊天不是规格。
- 看板：Multica。实现者不得把卡标 Done。
- WIP=1。QA 必须新会话。
- 测试：先保证能跑项目里写明的那条命令；没有测试就先补一条。
- Token：skill 里有的别再读文件；先查再读；长日志不要原样贴进对话。
```

```bash
git add README.md AGENTS.md && git commit -m "chore: pilot repo stub"
```

### 3.2 安装 OpenSpec（全局 CLI，只装一次）

需要 Node ≥ 20.19（本机已是 25）。

```bash
npm install -g @fission-ai/openspec@latest
cd ~/work/vdt-pilot
openspec init --tools cursor,codex
```

Cursor 里命令是 `/opsx-propose` 这类连字符形式；Codex 用 skills（init 结束时终端会打印确切写法）。**重启 Cursor 窗口** 后再用斜杠命令。

验证：

```bash
openspec --version
ls openspec/config.yaml openspec/specs openspec/changes
```

### 3.3 Superpowers

**Cursor（Agent 聊天里执行，不是终端）：**

```text
/plugin-add superpowers
```

然后新开一个 Agent 会话。

**Codex（终端）：**

```bash
git clone https://github.com/obra/superpowers.git ~/.codex/superpowers
mkdir -p ~/.agents/skills
ln -sfn ~/.codex/superpowers/skills ~/.agents/skills/superpowers
```

下一轮 `codex` 启动会扫到 skills。

### 3.4 Multica 桌面（无 Docker）

不要跑 `install.sh --with-server`（要 Docker）。

1. 打开 [multica.ai/download](https://multica.ai/download)，装桌面端。
2. 登录。桌面会把 **这台电脑** 注册成 runtime，并扫描 PATH 上的 `codex`、`cursor-agent`。
3. 若 Agents 列表是空的：新开终端确认 `which codex`、`which cursor-agent`，然后重启桌面或 `multica daemon restart`（若已装 CLI）。
4. 建两个 Agent：`Codex-worker`（provider = Codex）、`Cursor-worker`（provider = Cursor Agent）。
5. 建六个状态，对应流程列：**Backlog / Ready / In Progress / Review / QA / Done**。
6. 项目绑到 `~/work/vdt-pilot`。

规则写在每张卡上：**只有你可以把卡移到 Done，且必须已经 `opsx:archive`。**

### 3.5 第一张卡（无 UI，降低变量）

在 Cursor 打开 `~/work/vdt-pilot`：

1. 产品：`/opsx-explore` 或自然语言「帮我 explore：加一个 `hello` 脚本，打印 `vdt-ok`」。
2. `/opsx-propose` → 你读 `openspec/changes/<id>/` → **G1 点头**（无 UI，跳过 G1.5）→ 架构把 `design.md` / `tasks.md` 写完 → **G2 点头**。
3. Multica：建 issue，贴 change 路径，状态 **Ready**，assignee = `Codex-worker`。
4. 等 Codex 提交；你把卡打到 **Review**，看 diff 是否越界。
5. **新开** Cursor 会话（不要接着开发对话）：只跑场景（例如 `./hello.sh` 输出 `vdt-ok`）。通过 → 开发会话里 `/opsx-archive`（或 Codex 文档里对应 skill）。
6. archive 完成后，**你** 把 Multica 卡移到 Done。

出门：`openspec/specs/` 里有了第一条能力；`changes/archive/` 里有这次 change；Git 有提交。

失败就停在这一张卡上修流程，不要加 Headroom / teamai。

---

## 4. 本周：Wave 1

第一张卡 archive 成功后再做。

### 4.1 Headroom（无 Docker）

```bash
brew install python@3.13    # 若还没有
uv tool install --python 3.13 "headroom-ai[all]"
uv tool update-shell        # 若 which headroom 找不到
headroom --version
```

工人始终从 wrap 启动：

```bash
headroom wrap codex
```

Cursor：`headroom wrap cursor` **不会**替你改 IDE，它会打印要填进 Cursor 设置的代理 URL。按打印操作。不要同时再装 `headroom-skill`。

### 4.2 teamai-cli（仅当需要「两边自动 pull 团队规则」）

一个人、一个试点仓：**可以不做。** `openspec init --tools cursor,codex` 已经把合同命令装到两边。

第二人加入，或要把 token 五条 / culture 推到多台机器时：

```bash
npm install -g teamai-cli
# 另建一个空仓当 team repo，不要用业务仓当 team 仓
teamai init https://github.com/<you>/vdt-team
```

`teamai.yaml` 里用 **roles** 分发 skill。禁止把 OpenSpec 的 propose/apply 再塞进 team 仓。

### 4.3 有 UI 的第二张卡

1. Cursor 里用 OpenDesign 出原型，写入 `DESIGN.md`。
2. 你点头 = G1.5，然后才写 `design.md`。
3. QA 新会话用 Playwright MCP；登录态站点再用 BrowserSkill。

---

## 5. 以后再装（Wave 2）

| 件 | 何时 |
|---|---|
| `headroom wrap codex --code-graph` | 工人开始整仓 grep |
| `npx skills add cloudflare/security-audit-skill` | 第一张 auth/支付/权限卡 |
| Buzz | Multica 用顺了、真的需要「分支当房间」 |
| Multica 自托管 | 本机有 Docker，且不想用托管桌面 |
| ECC / oh-my-codex / deer-flow | **不装** |

---

## 6. 验证清单

Wave 0 完成当且仅当：

- [ ] `openspec --version` 有输出
- [ ] 试点仓存在 `openspec/config.yaml`
- [ ] Cursor 能调出 OpenSpec 命令（重启后）
- [ ] `ls ~/.agents/skills/superpowers` 能列出 TDD 等 skill
- [ ] Multica 里能看到 `codex` 或 `cursor-agent` runtime
- [ ] 一张卡：Ready → 工人提交 → 你 QA 新会话 → archive → **你** 标 Done
- [ ] 实现者没有权限（或约定上不会）把卡标 Done

Wave 1：

- [ ] `headroom --version` 有输出
- [ ] 下一次 Codex 领卡是通过 `headroom wrap codex` 起的

---

## 7. 失败时怎么退

| 现象 | 处理 |
|---|---|
| `openspec init` 写进了 `deepagents/` 根 | 不要继续。把根上误生成的 `.agents` / 命令文件按 git 还原；改去 `~/work/vdt-pilot` |
| Multica 发现不了工人 | `which codex cursor-agent`；重启 daemon；不要为了发现工人去装 Claude Code |
| Headroom wrap 搞挂 Codex | `headroom unwrap codex`，先退回裸 `codex` |
| teamai pull 覆盖了 `/opsx:*` | 停 pull；从 OpenSpec 再 `openspec update`；team 仓删掉重复 workflow |
| 想加快就再装一套 HQ | 停。那是 deer-flow / ECC 的坑 |

---

## 8. 和本机现状的对照

| 二进制 | 本机 2026-09-20 |
|---|---|
| `node` / `npm` | 有（25.6 / 11.8） |
| `uv` | 有 |
| `cursor-agent` | 有 |
| `codex` | 有 0.134.0 |
| Docker | **无 → 禁止 Wave 0 自托管 Multica / Headroom Docker 安装器** |
| `openspec` `headroom` `multica` `teamai` | 无，按上文装 |

下一步不是再讨论选型，而是：**建 `~/work/vdt-pilot`，跑 §3，把第一张卡 archive。**
