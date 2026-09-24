# Content Studio 服务与端口

## 端口一览

| 服务 | 默认端口 | URL | 启动方式 |
|------|---------|-----|----------|
| **OpenInspector Proxy** | **8080** | http://127.0.0.1:8080/v1 | `openinspector/scripts/dev-local.sh start` |
| OpenInspector Dashboard API | 8081 | http://127.0.0.1:8081/api/logs | 同上 |
| OpenInspector UI | 5173 | http://127.0.0.1:5173 | 同上 |
| Hermes Gateway | 8642 | http://127.0.0.1:8642/health | `hermes-dev/start-dev.sh` 或全栈脚本 |
| Hermes Dashboard | 9119 | http://127.0.0.1:9119/chat | 同上 |
| Hermes Workspace | 3000 | http://127.0.0.1:3000 | 同上 |
| SurrealDB | 8000 | ws://127.0.0.1:8000 | 全栈脚本自动启动 |
| Open Notebook API | 5055 | http://127.0.0.1:5055/docs | 全栈脚本 |
| Open Notebook Web UI | 3001 | http://127.0.0.1:3001 | 全栈脚本 |
| **MoneyPrinterTurbo API** | **8082** | http://127.0.0.1:8082/docs | 全栈脚本 |
| MoneyPrinterTurbo WebUI | 8501 | http://127.0.0.1:8501 | 全栈脚本 |

> **8080 专用于 OpenInspector**（LLM 追踪）。MPT 已从 8080 迁到 **8082**，避免与 Proxy 冲突。

## 调用链

```txt
Workspace (:3000)
    └─► Hermes Gateway (:8642)
            └─► OpenInspector Proxy (:8080)   ← 记录 request_body / tools / reasoning
                    └─► newapi 上游 (config 里 BASE_URL)

MoneyPrinterTurbo (:8082)   ← 独立 HTTP 服务，不走 OpenInspector
Content Studio 脚本通过 MONEYPRINTER_BASE_URL 访问
```

**Workspace 不需要改 LLM base_url**，只需 `HERMES_API_URL=http://127.0.0.1:8642`（Gateway 读 `~/.hermes/profiles/content-studio/config.yaml` 里的 `model.base_url`）。

## 一键启动

### 仅 Hermes（Gateway + Dashboard + Workspace 前台）

```bash
cd hermes-dev
./start-dev.sh
```

OpenInspector 需另开终端：

```bash
openinspector/scripts/dev-local.sh start
```

### Content Studio 全栈（推荐，含 OpenInspector + MPT + Notebook）

```bash
cd hermes-dev
./start-content-studio-stack.sh
```

默认 `WORKSPACE_BACKGROUND=1`，Workspace 在后台运行，终端不会阻塞。

停止：

```bash
./stop-content-studio-stack.sh
# OpenInspector 也会一并停止（若由全栈脚本启动）
openinspector/scripts/dev-local.sh stop   # 或单独停 OpenInspector
```

## 环境变量

所有默认端口集中在 `hermes-dev/ports.env`，可被 shell 环境覆盖：

```bash
source hermes-dev/ports.env
MPT_API_PORT=8088 ./start-content-studio-stack.sh
START_OPENINSPECTOR=0 ./start-content-studio-stack.sh   # 跳过 OpenInspector
WORKSPACE_FOREGROUND=1 ./start-content-studio-stack.sh # Workspace 占前台
```

| 变量 | 默认 | 说明 |
|------|------|------|
| `OPENINSPECTOR_PROXY_PORT` | 8080 | LLM 代理；Hermes `model.base_url` 应指向此端口 |
| `MPT_API_PORT` | 8082 | MoneyPrinterTurbo API |
| `MONEYPRINTER_BASE_URL` | `http://127.0.0.1:8082` | content-studio 脚本 / Skill 使用 |
| `GATEWAY_PORT` | 8642 | Hermes Gateway |
| `WORKSPACE_PORT` | 3000 | Hermes Workspace |

## Hermes 配置要点

`~/.hermes/profiles/content-studio/config.yaml`:

```yaml
model:
  base_url: http://127.0.0.1:8080/v1   # OpenInspector Proxy
```

OpenInspector **上游 Target URL**（`.env` / UI Settings / SQLite）— **不要带 `/v1`**：

```env
BASE_URL=https://newapi.yuaiweiwu.com
```

Hermes 的 `base_url` 已含 `/v1`，Proxy 会把 `/v1/chat/completions` 拼到上游根域名上。若上游也写 `/v1`，会变成 `/v1/v1/...` 并全部 404。

`~/.hermes/profiles/content-studio/.env`:

```env
MONEYPRINTER_BASE_URL=http://127.0.0.1:8082
```

MoneyPrinterTurbo `config.toml` 的 **根级**（不是 `[app]` 段）需包含：

```toml
listen_host = "127.0.0.1"
listen_port = 8082
```

全栈启动脚本会在首次启动时自动写入（若仍为 8080 或误写在 `[app]` 下）。

## 密钥集中管理（推荐）

改 LLM key 或上游地址时，**只改一个文件**，再同步到各子项目：

| 类型 | 单一来源 | 说明 |
|------|----------|------|
| **LLM key + 上游** | `~/.hermes/profiles/content-studio/secrets.env` | 模板：`hermes-dev/config/secrets.env.example` |
| **TTS（阿里）** | `~/.hermes/profiles/content-studio/config/tts-providers.yaml` | 不走 OpenInspector；播客经 `ali-tts-proxy` 读同一文件 |

```bash
# 首次：从现有 .env 生成 secrets.env
hermes-dev/scripts/sync-content-studio-secrets.sh --init

# 以后：只编辑 secrets.env，再同步
vim ~/.hermes/profiles/content-studio/secrets.env
hermes-dev/scripts/sync-content-studio-secrets.sh --notebook
```

同步目标：

- `~/.hermes/profiles/content-studio/.env` → `CUSTOM_API_KEY`
- `open-notebook/.env` → `OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8080/v1`（走 Proxy，不直连 newapi）
- `openinspector/.env` → `BASE_URL`（上游根域名，**不带** `/v1`）
- **`MoneyPrinterTurbo/config.toml`** → `[app] openai_api_key` + `openai_base_url`（走 Proxy）
- Open Notebook 数据库内 `openai_compatible` 凭据（`--notebook` 或全栈启动后自动）

审计所有落点：

```bash
hermes-dev/scripts/audit-llm-config.sh
```

**OpenInspector 做什么、不做什么**

- ✅ 统一 **上游 URL**（换 newapi / OpenRouter 只改 `LLM_UPSTREAM_BASE_URL` + sync）
- ✅ 记录请求日志、工具调用、推理轨迹
- ❌ **不**代理 TTS（`/v1/audio/speech` 用 `ali-tts-proxy :8969`）
- ❌ **不**替客户端注入 API key（Authorization 由 Hermes / Notebook 传入并透传）

因此「只改一处」对 LLM 指 **secrets.env**；对 TTS 指 **tts-providers.yaml**。全栈脚本在存在 `secrets.env` 时会自动 `sync`（`SECRETS_SYNC=0` 可关闭）。
