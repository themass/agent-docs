# Content Studio Agent — 文档索引

> **定位**：基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent) + 开源组件（Open Notebook、MoneyPrinterTurbo、OpenInspector 等）的 **内容生成 Agent** 工程说明。  
> **核对日期**：2026-09-24  
> **Hermes 源码**：`hermes-dev/hermes-agent/`（本 monorepo）  
> **可分享完整包（推荐）**：[`bundle/`](./bundle/) — Agent + 运维脚本 + 启停栈，约 100 个文件  
> **开发镜像**：[`hermes-dev/profiles/content-studio/`](../../../hermes-dev/profiles/content-studio/)（与 `bundle/profile/` 同步）  
> **本机运行**：`HERMES_HOME=~/.hermes/profiles/content-studio`（`bundle/install.sh` 安装）

---

## 一句话

**Content Studio Agent** 由 Hermes Profile（`SOUL.md` + `skills/content-studio/*` + `scripts/content-studio.sh`）驱动，把 GitHub 趋势、社区脉搏、口播脚本、三条视频链路（SOP / MPT / Hybrid）和报告库同步到 Open Notebook，并在 **Content Studio 全栈**（Gateway + Workspace + 周边服务）上联调。

它由早期的 **GitHub Analyst**（仓库内 `hermes-dev/profiles/github/`）演进而来；生产环境使用更完整的 **`content-studio`** Profile。

---

## 文档地图

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 系统架构、数据流、三条视频链路、与开源项目边界 |
| [REPOSITORY_MAP.md](./REPOSITORY_MAP.md) | **什么在 git 里、什么在 `~/.hermes`** |
| [SKILLS_CATALOG.md](./SKILLS_CATALOG.md) | 自研 `skills/content-studio/*` 与周边 Skill 目录 |
| [SCRIPTS_AND_COMMANDS.md](./SCRIPTS_AND_COMMANDS.md) | `content-studio.sh` 命令表 + `hermes-dev/scripts` |
| [PROMPTS_AND_ROUTING.md](./PROMPTS_AND_ROUTING.md) | `SOUL.md`、`playbook` 意图路由、Agent 行为契约 |
| [OPERATIONS.md](./OPERATIONS.md) | 启动栈、密钥同步、Cron、日常运维 |
| [RELATED_DOCS.md](./RELATED_DOCS.md) | 仓库内其它 Hermes / 计划文档链接 |
| **[HERMES_HOME_GUIDE.md](./HERMES_HOME_GUIDE.md)** | **`.hermes` 里哪些是 Agent 代码、哪些是运行时垃圾** |

---

## 分享给别人（最短路径）

```bash
cd docs/hermes/content-studio-agent/bundle
./install.sh
cp config/secrets.env.example ~/.hermes/profiles/content-studio/secrets.env
# 编辑密钥后
./ops/scripts/sync-content-studio-secrets.sh
./stack/start-content-studio-stack.sh   # 需完整 monorepo（hermes-agent、open-notebook 等）
```

目录说明见 **[bundle/README.md](./bundle/README.md)**。

---

## 快速开始

```bash
# 1. 全栈（Hermes + Open Notebook + MPT + OpenInspector）
cd hermes-dev
./start-content-studio-stack.sh

# 2. 使用 Content Studio Profile
export HERMES_HOME="$HOME/.hermes/profiles/content-studio"
"$HERMES_HOME/scripts/content-studio.sh" help

# 3. 在 Workspace 对话（需 Gateway 已起）
#    http://127.0.0.1:3000  — 编排 / Swarm / Conductor
#    纯聊天延迟更低可选 hermes-webui（见 hermes-agent/docs/WORKSPACE_VS_WEBUI.md）
```

---

## 与 Hermes 官方文档的关系

| 主题 | 本目录 | Hermes 上游 Canonical |
|------|--------|------------------------|
| Agent 内核 / 循环 | 仅引用 | `hermes-dev/hermes-agent/docs/ARCHITECTURE.md` |
| Surface / Gateway | 仅引用 | `SURFACE_ARCHITECTURE.md`、`CLI_GATEWAY_SYSTEM.md` |
| Skills 机制 | `SKILLS_CATALOG.md` | `SKILLS_SYSTEM.md` |
| 版本 | Content Studio 栈 | `VERSION_HISTORY.md`（Agent **0.21** 本地 HEAD 可能领先文档锚点） |

---

## 维护约定

1. **自研 Skill / 脚本**：优先在 `~/.hermes/profiles/content-studio` 开发；成熟后 **镜像回** `hermes-dev/profiles/`（见 [REPOSITORY_MAP.md](./REPOSITORY_MAP.md)）。
2. **本目录只写「产品与编排」**；Hermes 内核行为变更跟 upstream `hermes-agent/docs`。
3. 新增 pipeline 命令时：同步更新 `SCRIPTS_AND_COMMANDS.md`，并在 `playbook` / `help-manual` Skill 中改 SOP（勿把长命令表写进 `SOUL.md`）。
