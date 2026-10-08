# OpenCode 插件：内置 vs 官方生态

> **安装与配置**： [opencode.ai — Plugins](https://opencode.ai/v2/docs/plugins) · `opencode.json(c)` 的 `plugins` 数组 · CLI：`opencode plugin list` / `add` / `update` / `remove`  
> **社区目录**（非官方维护）： [awesome-opencode](https://github.com/awesome-opencode/awesome-opencode) · [opencode.cafe](https://opencode.cafe)

---

## 1. 两类「插件」不要混谈

| 种类 | 是什么 | 典型 id / 包名 |
|------|--------|----------------|
| **Core 内置插件** | 随 `packages/core` 启动，用 `define({ id, effect })` 注册，改 Config / Agent / Provider | `agent`、`config-agent`、`models-dev`、`config-plugin`… |
| **用户安装的 npm/Git 插件** | 写在 `opencode.json` 的 `plugins`，或 `.opencode/plugins/*.{ts,js}` | `oh-my-opencode`、`opencode-worktree`… |

内置插件 **不会**出现在 `opencode plugin list` 的「全局 npm 插件」列表里；可用 `opencode plugin list --builtin`（见官方文档）查看内置项。

---

## 2. Core 内置插件（源码登记）

路径：`opencode/packages/core/src/config/plugin/` 与 `packages/core/src/plugin/`。

| id | 文件 | 作用 |
|----|------|------|
| `config-agent` | `config/plugin/agent.ts` | 扫描 `agent(s)/**/*.md`、`mode(s)/*.md`，合并进 `AgentV2` 注册表 |
| `config-provider` | `config/plugin/provider.ts` | 从配置合并 Provider / Model |
| `config-command` | `config/plugin/command.ts` | 自定义 slash command |
| `config-skill` | `config/plugin/skill.ts` | Skill 目录发现 |
| `config-plugin` | `config/plugin/external.ts` | 加载用户配置的 **外部** npm/Git 插件 |
| `config-reference` | `config/plugin/reference.ts` | Reference 文档注入 |
| `agent` | `plugin/agent.ts` | **内置 Agent 档案**：`build`、`plan`、`general`、`explore`、`compaction`、`title`、`summary` 的 system / permissions |
| `models-dev` | `plugin/models-dev.ts` | 定时拉取 models.dev，transform Config |
| `command` | `plugin/command.ts` | 内置 command 宿主 |
| `skill` | `plugin/skill.ts` | Skill 运行时 |
| 各 `*-provider` | `plugin/provider/*.ts` | OpenAI、Azure、Bedrock、Vertex… 的 Catalog 适配 |

外部插件通过 `config-plugin` 挂到同一 **Plugin Host**（`plugin/host.ts`），可注册 Hook、额外 Tool、Config transform。

---

## 3. 官方生态插件列表（GitHub / 官网登记）

来源：[Ecosystem | OpenCode](https://dev.opencode.ai/docs/ecosystem/)（社区贡献，**非**全部官方维护；以各仓库 README 为准）。

| 名称 | 功能摘要 |
|------|----------|
| opencode-daytona | Daytona 沙箱里跑 Session，git 同步与预览 |
| opencode-helicone-session | Helicone session 头注入 |
| opencode-type-inject | 读文件时自动附带 TS/Svelte 类型 |
| opencode-openai-codex-auth | ChatGPT Plus/Pro 订阅鉴权 |
| opencode-gemini-auth | Gemini 套餐鉴权 |
| opencode-antigravity-auth | Antigravity 免费模型 |
| opencode-devcontainers | 多分支 devcontainer 隔离 |
| opencode-google-antigravity-auth | Google Antigravity OAuth + Search |
| opencode-dynamic-context-pruning | 剪枝过时 tool 输出省 token |
| opencode-vibeguard | 出 LLM 前脱敏，本地还原 |
| opencode-websearch-cited | 带引用的联网搜索 |
| opencode-pty | 后台 PTY 进程与交互输入 |
| opencode-shell-strategy | 非交互 shell 策略，防挂起 |
| opencode-wakatime | Wakatime 统计 |
| opencode-md-table-formatter | 整理 LLM 输出的 Markdown 表格 |
| opencode-morph-fast-apply | Morph Fast Apply 编辑 |
| opencode-morph-plugin | Morph 编辑 + WarpGrep + 压缩 |
| oh-my-opencode | 后台 Agent、LSP/AST/MCP、预制 Agent |
| opencode-notificator / opencode-notifier / opencode-notify | 桌面通知（完成/权限/错误） |
| opencode-zellij-namer | Zellij 会话 AI 命名 |
| opencode-skillful | Skill 懒加载与注入 |
| opencode-supermemory | Supermemory 跨 Session 记忆 |
| @plannotator/opencode | 计划可视化批注与分享 |
| @openspoon/subtask2 | `/commands` 编排扩展 |
| opencode-scheduler | launchd/systemd 定时任务 |
| opencode-conductor | Context → Spec → Plan → Implement 协议流 |
| micode | Brainstorm → Plan → Implement |
| octto | 浏览器多问题表单脑暴 |
| opencode-background-agents | 异步后台 Agent 委派 |
| opencode-workspace | 多 Agent 编排套件（16 组件） |
| opencode-worktree | Git worktree 零摩擦 |
| opencode-sentry-monitor | Sentry AI 监控 |
| opencode-firecrawl | Firecrawl CLI 爬取/搜索 |
| opencode-jfrog-plugin | JFrog 平台集成 |
| opencode-goal-plugin | `/goal` 目标常驻并 auto-continue |
| opencode-tavily | Tavily CLI 搜索/深度研究 |

### 生态中的「项目 / Agent 配置包」（不是 npm 插件宿主）

官网 **Projects** / **Agents** 表（如 `opencode-agents`、`Agentic`）多为 **配置、Prompt、命令集合**，通过仓库拷贝或 `opencode.json` 引用，不等同于上表的 npm 插件包。

---

## 4. 与 Core 多 Agent 的边界

| 能力 | Core 原生 | 典型社区插件 |
|------|-----------|----------------|
| 子 Session 委派 | `task` 工具（`packages/opencode/src/tool/task.ts`） | oh-my-opencode、opencode-background-agents、opencode-workspace |
| 同 Session 换 Agent | `session.agent` + `session.next.agent.switched` 事件 | handoff / pi-subagent 类（增强编排，非 Core） |
| Plan 模式 | `plan` **Agent Profile** + `plan_exit` 工具 + 计划文件路径权限 | @plannotator/opencode、micode、opencode-conductor |

详见 [AGENT_AND_MULTI_AGENT.md](./AGENT_AND_MULTI_AGENT.md)。
