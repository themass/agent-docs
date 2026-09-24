# Hermes 多 Agent Profile 与定时任务指南

本文档说明 `hermes-dev` 环境下如何用 **方案 A（三个 Profile）** 扮演不同 Agent，以及如何用 **Cron** 让 `github` 专员定时拉取排行榜并在 **Hermes Workspace** 查看结果。

---

## 1. SOUL.md 在哪里？（重要）

三个专员的 `SOUL.md` **不在** 仓库里的 `openhuman/app/src/SOUL.md`，也 **不在** `hermes-dev/` 目录下。

| 角色 | SOUL 实际路径 |
|------|----------------|
| GitHub 分析专员 | `~/.hermes/profiles/github/SOUL.md` |
| **Content Studio（内容生成）** | `~/.hermes/profiles/content-studio/SOUL.md` — 文档见 [content-studio-agent/README.md](content-studio-agent/README.md) |
| Coding 专员 | `~/.hermes/profiles/coder/SOUL.md` |
| 股票研究专员 | `~/.hermes/profiles/stocks/SOUL.md` |
| 默认（default） | `~/.hermes/SOUL.md` |

`openhuman/app/src/SOUL.md` 是 **另一个项目** 的文件，与本次创建的 Hermes Profile **无关**。

修改角色行为：编辑对应 Profile 下的 `SOUL.md`，然后 **重启 Gateway**。

---

## 2. 已创建的三个 Profile

| Profile | 命令别名 | 用途 | 已启用工具（CLI） |
|---------|----------|------|-------------------|
| `github` | `github chat` | GitHub 仓库 / PR / Issue | web, terminal, file, skills, todo |
| `coder` | `coder chat` | 本地编码、测试 | terminal, file, code_execution, skills, todo |
| `stocks` | `stocks chat` | 公开信息研究（非投资建议） | web, file, skills, todo |

查看列表：

```bash
hermes profile list
hermes profile describe github
```

切换当前 Profile（Gateway / Workspace 跟随）：

```bash
hermes profile use github    # 或 coder / stocks / default
cd hermes-dev && ./stop-dev.sh && ./start-dev.sh
```

独立调试（不切换全局 Profile）：

```bash
github chat
coder chat
stocks chat
```

---

## 3. 模型与 API

三个 Profile 已从 `default` 克隆 `~/.hermes/config.yaml` 中的模型配置（如 `gemini-3.1-pro-preview` + 自定义 `base_url`）。  
各 Profile 目录下也有 `.env`（含 `API_SERVER_KEY` 等，与 Workspace 联调相关）。

---

## 4. GitHub 专员：每小时拉排行榜 → Workspace

### 4.1 原理

1. 使用 **`github` Profile** 创建 **Cron 定时任务**（`hermes cron create --profile github`）。
2. Gateway 内置调度器按 `1h` 执行；Agent 用 **web / skills** 访问 GitHub Trending 并整理报告。
3. 结果写入 **`~/.hermes/profiles/github/cron/output/<job_id>/`**（`deliver=local`）。
4. 在 **Hermes Workspace → Jobs**（`http://localhost:3000/jobs`）查看各 Profile 的定时任务与输出（需 Dashboard / Jobs API 可用）。

> Hermes **没有** 单独的「推送到 Workspace 聊天窗口」投递目标；`deliver=local` 表示结果落盘 + 在 **Jobs 页** 查看，这是零改代码的标准做法。

### 4.2 前置条件

1. **Gateway 在跑**（`./start-dev.sh` 或 `github gateway run`）。
2. **`API_SERVER_KEY` / `HERMES_API_TOKEN`** 已配对（见 `hermes-dev/README.md`）。
3. 本机已安装 **`gh`**（可选，便于部分 GitHub 操作；Trending 主要靠 web）。

### 4.3 创建定时任务（推荐命令）

在 **`github` Profile** 下创建（注意 `HERMES_HOME` 或 `--profile github`）：

```bash
cd hermes-dev/hermes-agent
source .venv/bin/activate

export HERMES_HOME="$HOME/.hermes/profiles/github"

hermes cron create \
  --name "github-hourly-trending" \
  --profile github \
  --deliver local \
  --skill github-repo-management \
  "every 1h" \
  "你是 GitHub 分析专员。请访问 GitHub Trending（今日/本周热门仓库），整理 Top 15 项目：排名、仓库名、Star 数、主要语言、一句话说明。输出 Markdown 表格，顶部写 3 条今日要点。仅基于公开页面，不要投资建议。报告面向 Hermes Workspace 用户在 Jobs 页阅读。"
```

等价写法（不设置 `HERMES_HOME`，只靠 `--profile`）：

```bash
hermes cron create \
  --name "github-hourly-trending" \
  --profile github \
  --deliver local \
  "1h" \
  "（同上 prompt）"
```

### 4.4 管理任务

```bash
HERMES_HOME=~/.hermes/profiles/github hermes cron list
HERMES_HOME=~/.hermes/profiles/github hermes cron run github-hourly-trending   # 立即跑一次
HERMES_HOME=~/.hermes/profiles/github hermes cron pause github-hourly-trending
HERMES_HOME=~/.hermes/profiles/github hermes cron resume github-hourly-trending
HERMES_HOME=~/.hermes/profiles/github hermes cron remove github-hourly-trending
hermes cron status    # 调度器是否在跑（随 Gateway）
```

任务定义文件：`~/.hermes/profiles/github/cron/jobs.json`  
输出目录：`~/.hermes/profiles/github/cron/output/<job_id>/`

### 4.5 在 Workspace 查看

1. 打开 **http://localhost:3000/jobs**
2. 找到 Profile 为 **`github`**、名称为 **`github-hourly-trending`** 的任务
3. 点开 **最近一次运行** 查看 Markdown 报告

若 Jobs 页显示不可用：先启动 **Dashboard**（`hermes dashboard`，`:9119`），并确认 `HERMES_DASHBOARD_URL` 正确。

### 4.6 调度表达式说明

| 写法 | 含义 |
|------|------|
| `every 1h` | **每 1 小时（循环）** — 推荐 |
| `1h` | 仅 **一次**，1 小时后跑完即结束（不要误用） |
| `every 2h` | 每 2 小时 |
| `0 * * * *` | 每小时整点（cron 表达式，需 `croniter`） |

---

## 5. 可选：用脚本 + Agent 分工

若希望先 **脚本抓取** 再让 Agent 总结，可把脚本放到 `~/.hermes/profiles/github/scripts/`，例如仓库内示例：

`hermes-dev/scripts/github_trending_snapshot.py`（见同目录，可复制到 Profile）

```bash
mkdir -p ~/.hermes/profiles/github/scripts
cp hermes-dev/scripts/github_trending_snapshot.py ~/.hermes/profiles/github/scripts/

hermes cron create \
  --name "github-hourly-trending-script" \
  --profile github \
  --script scripts/github_trending_snapshot.py \
  --deliver local \
  "1h" \
  "根据下面脚本输出的 GitHub Trending 原始列表，整理 Top 15 Markdown 表格与 3 条要点，供 Workspace Jobs 阅读。"
```

---

## 6. 常见问题

### Q: 改了 `SOUL.md` 没生效？

重启 Gateway：`./stop-dev.sh && ./start-dev.sh`。

### Q: Cron 不执行？

- `hermes cron status` 应为运行中（Gateway 启动后）
- 看日志：`tail -f ~/.hermes/logs/gateway.log` 与 `~/.hermes/profiles/github/cron/` 下输出

### Q: Workspace 聊天仍报 API 403？

确认 `~/.hermes/.env` 与 `hermes-workspace/.env` 中 `API_SERVER_KEY` / `HERMES_API_TOKEN` 一致，并重启 Gateway。

### Q: 能否把报告推到某条 Chat 会话？

标准 Cron 的 `deliver` 支持 `telegram`、`discord` 等，**不直接支持 Workspace Chat**。变通：在 Jobs 页查看，或自行用 `send_message` 类集成（需额外配置）。

---

## 7. 报告库（无 Obsidian GUI）

已配置 `obsidian` skill + `markitdown` MCP，报告目录即 vault：

`~/.hermes/profiles/github/reports/`

终端浏览、Chat 话术、验证步骤见 **[GITHUB_REPORTS_KB.md](./GITHUB_REPORTS_KB.md)**。

改 `~/.hermes/config.yaml` 或 `.env` 后执行 `./stop-dev.sh && ./start-dev.sh`。

---

## 8. 相关路径速查

```txt
hermes-dev/
├── docs/MULTI_AGENT_PROFILES.md    # 本文档
├── docs/GITHUB_REPORTS_KB.md       # 报告库 + markitdown MCP
├── scripts/github_trending_snapshot.py
└── README.md

~/.hermes/
├── profiles/github/     # GitHub 专员
├── profiles/coder/      # Coding 专员
├── profiles/stocks/     # 股票研究专员
└── active_profile       # 当前激活 Profile 名
```
