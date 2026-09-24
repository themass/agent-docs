# 仓库与 Profile 路径对照

Content Studio 的代码分散在 **monorepo**、**Hermes 上游树** 和 **本机 Hermes Profile** 三处。开发前先确认改的是哪一层。

---

## 1. 总览

| 类别 | Git 内（可 PR） | 仅本机（需备份/镜像） |
|------|-----------------|------------------------|
| Hermes 引擎 | `hermes-dev/hermes-agent/` | — |
| 栈脚本 / 端口 | `hermes-dev/start-content-studio-stack.sh`、`PORTS.md`、`ports.env` | — |
| 联调脚本 | `hermes-dev/scripts/*.sh`、`*.py` | — |
| GitHub Analyst 基线 | `hermes-dev/profiles/github/` | 安装到 `~/.hermes/profiles/github` |
| **Content Studio 完整可分享包** | **`docs/hermes/content-studio-agent/bundle/`** ✅ | `profile/` + `ops/` + `stack/` |
| **Profile 开发镜像** | `hermes-dev/profiles/content-studio/` | 与 `bundle/profile/` 同步 |
| Open Notebook / MPT | `open-notebook/`、`MoneyPrinterTurbo/` | 各服务 `.env` |
| 本套说明 | **`docs/hermes/content-studio-agent/`** | — |

---

## 2. `hermes-dev/`（本工程）

```text
hermes-dev/
├── hermes-agent/              # Hermes 完整源码（Gateway、skills 平台、docs）
├── hermes-workspace/          # Workspace UI（Content Studio 默认 :3000）
├── hermes-webui/              # 轻量聊天 WebUI（实时性更好）
├── hermes-studio/             # 多 Agent 桌面/控制台（生态产品，非 CS 必需）
├── profiles/github/           # ★ Git 内 Analyst 基线（install.sh → ~/.hermes）
├── scripts/                   # ★ 全栈联调脚本（见 SCRIPTS_AND_COMMANDS.md）
├── start-content-studio-stack.sh
├── stop-content-studio-stack.sh
├── ports.env
└── PORTS.md
```

---

## 3. `~/.hermes/profiles/content-studio/`（运行真相源）

当前 **Content Studio Agent** 的 SOUL、Skills、编排器主要在这里：

```text
~/.hermes/profiles/content-studio/
├── SOUL.md                    # 人设与 Skill 路由表（摘要）
├── config.yaml                # 模型、base_url（常指向 OpenInspector :8080/v1）
├── secrets.env                # LLM/TTS 等（勿提交 git）
├── config/tts-providers.yaml
├── scripts/
│   ├── content-studio.sh      # ★ 主编排器（~50k 行级 bash）
│   ├── content-studio-*.sh    # 薄包装：daily / weekly / radar / …
│   └── setup-cron.sh
├── skills/
│   ├── content-studio/        # ★ 自研能力包（见 SKILLS_CATALOG.md）
│   └── …                      # 其它已安装 Hermes skills（社区/官方）
├── reports/YYYY/MM/           # 日报、脚本、视频、yaml
├── logs/                      # sop-latest.log、MPT 渲染日志
└── docs/TTS_CONFIG.md
```

**同步密钥模板**（git 内）：`hermes-dev/config/secrets.env.example`  
**同步脚本**：`hermes-dev/scripts/sync-content-studio-secrets.sh`（将密钥分发到 Notebook/MPT 等）

---

## 4. 建议的版本化策略

1. **已在 git**：`hermes-dev/profiles/github/` — 用 `install.sh` 部署。
2. **已在 git**：`hermes-dev/profiles/content-studio/` — `install.sh` / `sync-from-live.sh`
3. **一次性导出清单**（本机）：

```bash
export HERMES_HOME="$HOME/.hermes/profiles/content-studio"
find "$HERMES_HOME/skills/content-studio" -name SKILL.md | sort
wc -l "$HERMES_HOME/scripts/content-studio.sh"
```

4. **不要**把 `reports/`、`state.db`、`secrets.env` 提交进 monorepo。

---

## 5. 相关 monorepo 路径

| 路径 | 说明 |
|------|------|
| `docs/hermes/` | Hermes 架构文档副本/索引 |
| `docs/hermes/GITHUB_ANALYST_DESIGN.md` | 分析师 v1 设计 |
| `docs/hermes/MULTI_AGENT_PROFILES.md` | 多 Profile（github/coder/stocks） |
| `docs/plans/2026-06-14-hybrid-video-midterm-plan.md` | Hybrid 视频计划 |
| `scripts/deepagents-python.env.sh` | Content Studio 栈用的 Python 环境 |
