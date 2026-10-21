# 运维与联调

## 1. 环境变量

| 变量 | 典型值 | 说明 |
|------|--------|------|
| `HERMES_HOME` | `~/.hermes/profiles/content-studio` | Profile 根；Gateway/Cron/脚本必须一致 |
| `HERMES_API_URL` | `http://127.0.0.1:8642` | Workspace → Gateway |
| `LLM_API_KEY` | 见 `secrets.env` | FreeLLMAPI `freellmapi-...` 或 TDAI `sk-mem-*` |
| `MONEYPRINTER_BASE_URL` | `http://127.0.0.1:8082` | MPT API（非 8080） |

模型路由：**单一来源** `secrets.env` + `bundle/config/llm.defaults.env`（默认 FreeLLMAPI `:3011`），运行 `bundle/ops/scripts/sync-content-studio-secrets.sh` 传播到 Hermes / Notebook / MPT。详见 `bundle/config/LLM_CONFIG.md`。

---

## 2. 启动栈

### 全栈 Content Studio

```bash
# 推荐（bundle 内副本，路径已适配 monorepo）
cd docs/hermes/content-studio-agent/bundle/stack
./start-content-studio-stack.sh
```

或 monorepo 原件：`cd hermes-dev && ./start-content-studio-stack.sh`

停止：对应目录下的 `stop-content-studio-stack.sh`（可选 `STOP_SURREALDB=1`）

端口表：`bundle/stack/PORTS.md` 或 `hermes-dev/PORTS.md`

### 仅 Hermes + Workspace

```bash
cd hermes-dev
./start-dev.sh    # Gateway + Dashboard + Workspace 前台
```

FreeLLMAPI 由全栈脚本自动起（`START_FREELLMAPI=1`）。可选追踪：`START_OPENINSPECTOR=1` + `openinspector/scripts/dev-local.sh start`

---

## 3. 密钥同步

1. 主 secrets：`~/.hermes/profiles/content-studio/secrets.env`  
2. 模板：`bundle/config/secrets.env.example`  
3. 分发：

```bash
docs/hermes/content-studio-agent/bundle/ops/scripts/sync-content-studio-secrets.sh
docs/hermes/content-studio-agent/bundle/ops/scripts/audit-llm-config.sh
```

Open Notebook / MPT 单独脚本见 `SCRIPTS_AND_COMMANDS.md`。

---

## 4. Cron

```bash
export HERMES_HOME=~/.hermes/profiles/content-studio
"$HERMES_HOME/scripts/setup-cron.sh"
```

或使用 Hermes 内置 Cron（`hermes cron create --profile content-studio`），交付物在 `cron/output/` 与 Jobs UI。

---

## 5. 日常检查

```bash
export HERMES_HOME=~/.hermes/profiles/content-studio

# Gateway
curl -s http://127.0.0.1:8642/health

# 今日 SOP 状态
"$HERMES_HOME/scripts/content-studio.sh" sop-status

# FreeLLMAPI（LLM 聚合）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3011/v1/models
```

---

## 6. UI 选型（聊天 vs 编排）

| 场景 | 推荐 |
|------|------|
| 与 Content Studio Agent 聊天、跟手 SSE | `hermes-webui` 或 `hermes chat` / TUI |
| Swarm、Conductor、文件、全栈 | Workspace `:3000` |
| Kanban / Skills / Jobs | Dashboard `:9119` |

详见：`hermes-dev/hermes-agent/docs/WORKSPACE_VS_WEBUI.md`

---

## 7. 将 Profile 镜像回 Git（推荐流程）

```bash
DEST=hermes-dev/profiles/content-studio
SRC="$HOME/.hermes/profiles/content-studio"

mkdir -p "$DEST"
rsync -a --exclude reports --exclude state.db --exclude secrets.env \
  "$SRC/SOUL.md" "$SRC/scripts/" "$SRC/skills/content-studio/" \
  "$DEST/"
```

然后在 `hermes-dev/profiles/content-studio/install.sh` 中仿照 `github/install.sh` 安装到 `~/.hermes`（尚未在仓库落地时可按此执行一次性 rsync）。
