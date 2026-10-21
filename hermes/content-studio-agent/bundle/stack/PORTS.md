# Content Studio 服务与端口

## 端口一览

| 服务 | 默认端口 | URL | 启动方式 |
|------|---------|-----|----------|
| **FreeLLMAPI** | **3011** | http://127.0.0.1:3011/v1 | 全栈 `start-content-studio-stack.sh` 或 `start-freellmapi.sh` |
| TencentDB Memory Proxy | 8096 | http://127.0.0.1:8096 | 全栈（`START_TDAI_MEMORY=1`） |
| Hermes Gateway | 8642 | http://127.0.0.1:8642/health | `hermes-dev/start-dev.sh` 或全栈脚本 |
| Hermes Dashboard | 9119 | http://127.0.0.1:9119/chat | 同上 |
| Hermes Workspace | 3000 | http://127.0.0.1:3000 | 同上 |
| SurrealDB | 8000 | ws://127.0.0.1:8000 | 全栈脚本自动启动 |
| Open Notebook API | 5055 | http://127.0.0.1:5055/docs | `START_OPEN_NOTEBOOK=1`（默认在 `ports.env` 为 **0**） |
| Open Notebook Web UI | 3001 | http://127.0.0.1:3001 | 同上（含 SurrealDB :8000） |
| **MoneyPrinterTurbo API** | **8082** | http://127.0.0.1:8082/docs | 全栈脚本 |
| MoneyPrinterTurbo WebUI | 8501 | http://127.0.0.1:8501 | 全栈脚本 |
| OpenInspector Proxy（可选） | 8080 | http://127.0.0.1:8080/v1 | `START_OPENINSPECTOR=1` |
| OpenInspector Dashboard API | 8081 | http://127.0.0.1:8081/api/logs | 同上 |
| OpenInspector UI | 5173 | http://127.0.0.1:5173 | 同上 |

> **3011** 为默认 LLM 聚合（FreeLLMAPI），与 Notebook Web **3001** 错开。MPT API 在 **8082**。

## 调用链（默认）

```txt
Workspace (:3000)
    └─► Hermes Gateway (:8642)
            └─► TencentDB Proxy (:8096)   [CONTENT_STUDIO_LLM_VIA_TDAI_PROXY=1]
                    └─► FreeLLMAPI (:3011/v1)
                            └─► 各免费 provider（Keys 在 FreeLLMAPI UI 配置）

不经 TDAI 时 Gateway/profile 可直接指向 :3011/v1（secrets sync 写入 config.yaml）。
```

**Workspace 不需要改 LLM base_url**，只需 `HERMES_API_URL=http://127.0.0.1:8642`（Gateway 读 profile `config.yaml` 的 `model.base_url`）。

## 一键启动

### 仅 Hermes（Gateway + Dashboard + Workspace 前台）

```bash
cd hermes-dev
./start-dev.sh
```

LLM 需另起 FreeLLMAPI 或跑全栈。

### Content Studio 全栈（推荐）

```bash
cd docs/hermes/content-studio-agent/bundle/stack
./start-content-studio-stack.sh
```

停止：`./stop-content-studio-stack.sh`（含 FreeLLMAPI pid/端口）

## 环境变量

默认端口在 `bundle/stack/ports.env`：

```bash
source bundle/stack/ports.env
START_TDAI_MEMORY=0 ./start-content-studio-stack.sh   # 省 CPU，直连 FreeLLMAPI
START_OPENINSPECTOR=1 ./start-content-studio-stack.sh # 可选 LLM 追踪（与 FreeLLMAPI 二选一为主出口）
FREELLMAPI_PORT=3012 ./start-content-studio-stack.sh
```

| 变量 | 默认 | 说明 |
|------|------|------|
| `FREELLMAPI_PORT` | 3011 | LLM 聚合；`LLM_PROXY_URL` 默认指向此端口 |
| `START_FREELLMAPI` | 1 | 全栈是否启动 FreeLLMAPI |
| `START_OPENINSPECTOR` | 0 | 是否启动 OpenInspector（追踪） |
| `MPT_API_PORT` | 8082 | MoneyPrinterTurbo API |
| `GATEWAY_PORT` | 8642 | Hermes Gateway |

## Hermes 配置要点

`~/.hermes/profiles/content-studio/config.yaml`（由 sync 写入）：

```yaml
model:
  base_url: http://127.0.0.1:8096/hermes/default   # 或直连 http://127.0.0.1:3011/v1
  default: auto
```

密钥：`secrets.env` → `sync-content-studio-secrets.sh`。详见 `bundle/config/LLM_CONFIG.md`。
