# 运维与联调

## 1. 环境变量

| 变量 | 典型值 | 说明 |
|------|--------|------|
| `HERMES_HOME` | `~/.hermes/profiles/content-studio` | Profile 根；Gateway/Cron/脚本必须一致 |
| `HERMES_API_URL` | `http://127.0.0.1:8642` | Workspace → Gateway |
| `LLM_API_KEY` | 见 `secrets.env` | 客户端/OpenInspector 透传 |
| `MONEYPRINTER_BASE_URL` | `http://127.0.0.1:8082` | MPT API（非 8080） |

模型路由：Profile `config.yaml` 中 `base_url` 常设为 `http://127.0.0.1:8080/v1`（OpenInspector）。

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

OpenInspector 另开：`openinspector/scripts/dev-local.sh start`

---

## 3. 密钥同步

1. 主 secrets：`~/.hermes/profiles/content-studio/secrets.env`  
2. 模板：`hermes-dev/config/secrets.env.example`  
3. 分发：

```bash
hermes-dev/scripts/sync-content-studio-secrets.sh
hermes-dev/scripts/audit-llm-config.sh   # 校验各服务 LLM 配置
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

# OpenInspector
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/v1/models
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
