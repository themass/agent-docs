# Content Studio — 统一 LLM 配置

默认 LLM 出口为 **FreeLLMAPI**（OpenAI 兼容聚合，`:3011`）。可选 **TencentDB Memory Proxy**（`:8096`）做记忆注入；可选 **OpenInspector**（`:8080`）仅用于请求追踪（`START_OPENINSPECTOR=1`）。

## 单一来源（改这里，再 sync）

| 文件 | 作用 |
|------|------|
| **`~/.hermes/profiles/content-studio/secrets.env`** | `LLM_API_KEY`（FreeLLMAPI unified `freellmapi-...` 或经 TDAI 时的 `sk-mem-*`）、`LLM_PROXY_URL` / `LLM_MODEL` |
| **`bundle/config/llm.defaults.env`** | 仓库默认：`http://127.0.0.1:3011/v1` + `auto` |

```bash
# 编辑密钥后传播到 Hermes / Notebook / MPT
cd docs/hermes/content-studio-agent/bundle
./ops/scripts/sync-content-studio-secrets.sh --notebook
```

全栈启动脚本在存在 `secrets.env` 时也会自动跑 sync（`SECRETS_SYNC=1`）。

## 首次使用 FreeLLMAPI

1. **需要 Docker Desktop**（npm 上的 `freellmapi` 只是配置 CLI，不是网关）。全栈会跑 `bundle/stack/start-freellmapi.sh`（默认 **3011**，避免与 Notebook `:3001` 冲突）；数据目录默认 `~/freellmapi`。
2. 打开 **http://127.0.0.1:3011** → **Keys**：为各免费 provider 填 key，复制 Dashboard 的 **unified key**（`freellmapi-...`）。
3. 写入 `secrets.env` 的 `LLM_API_KEY`，再跑 `sync-content-studio-secrets.sh`。

## 默认值

| 变量 | 默认 | 含义 |
|------|------|------|
| `LLM_PROXY_URL` | `http://127.0.0.1:3011/v1` | 未启用 TencentDB 时，Hermes/Notebook/MPT 的 `base_url` |
| `CONTENT_STUDIO_LLM_VIA_TDAI_PROXY` | `1`（`ports.env`） | 为 `1` 且 Memory Proxy 已起：Hermes → `8096/hermes/<space>`，Notebook/MPT → `8096/codebuddy/<space>`，客户端密钥为 `TDAI_USER_KEY`（`sk-mem-*`） |
| `LLM_MODEL` | `auto` | Hermes `model.default`、MPT `openai_model_name` |
| `LLM_UPSTREAM_BASE_URL` | `http://127.0.0.1:3011` | FreeLLMAPI 根 URL（无 `/v1`）；TencentDB 上游也指向此处 |

## 各组件读什么

| 组件 | 配置位置 | sync 是否写入 |
|------|----------|----------------|
| Hermes Agent | `profiles/content-studio/config.yaml` | `model.base_url`、`model.default`、`providers.manifest`、`custom_providers`、`auxiliary.*.base_url` |
| Hermes keys | `profiles/content-studio/.env` | `CUSTOM_API_KEY`（TDAI 时为 `sk-mem-*`） |
| Open Notebook | `open-notebook/.env` | `OPENAI_COMPATIBLE_*` |
| MoneyPrinterTurbo | `config.toml` `[app]` | `openai_base_url`、`openai_model_name` |
| TencentDB Proxy | `tdai-memory.env` / compose | 上游 `TDAI_LLM_BASE_URL` → FreeLLMAPI `/v1` |

TTS、Embedding 不走 LLM 代理，不在此 sync 范围内。

## Desktop / Custom provider

| 模式 | base_url | API key |
|------|----------|---------|
| 直连 FreeLLMAPI | `http://127.0.0.1:3011/v1` | `freellmapi-...` from secrets |
| 经 TencentDB Memory | `http://127.0.0.1:8096/hermes/<space>/v1`（或 sync 后的 profile URL） | `sk-mem-*` from `tdai-memory.env` |

## TencentDB Memory Hub

完整步骤见 **[TDAI_MEMORY_INTEGRATION.md](../TDAI_MEMORY_INTEGRATION.md)**（`tdai-proxy-headers` 插件 + Gateway 重启）。

## 审计

```bash
./ops/scripts/audit-llm-config.sh
```
