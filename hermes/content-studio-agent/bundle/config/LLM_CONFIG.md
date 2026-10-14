# Content Studio — 统一 LLM 配置

所有走 **OpenAI 兼容 Chat Completions** 的服务应共用同一套出口，便于 OpenInspector 记录 trace。

## 单一来源（改这里，再 sync）

| 文件 | 作用 |
|------|------|
| **`~/.hermes/profiles/content-studio/secrets.env`** | 密钥 + 可选覆盖 `LLM_PROXY_URL` / `LLM_MODEL` / `LLM_UPSTREAM_BASE_URL` |
| **`hermes-dev/config/llm.defaults.env`**（或 bundle 内同名） | 仓库默认：`8080/v1` + `gpt-5-6-luna` |

```bash
# 编辑密钥后传播到 Hermes / Notebook / MPT / OpenInspector 上游
cd hermes-dev
./scripts/sync-content-studio-secrets.sh --notebook
```

全栈启动脚本在存在 `secrets.env` 时也会自动跑 sync（`SECRETS_SYNC=1`）。

## 默认值

| 变量 | 默认 | 含义 |
|------|------|------|
| `LLM_PROXY_URL` | `http://127.0.0.1:8080/v1` | 未启用 TencentDB 时，客户端 `base_url`（OpenInspector） |
| `CONTENT_STUDIO_LLM_VIA_TDAI_PROXY` | `1`（`ports.env`） | 为 `1` 且 Memory Proxy 已起：Hermes → `8096/hermes/<space>`，Notebook/MPT → `8096/codebuddy/<space>`，密钥为 `TDAI_USER_KEY` |
| `LLM_MODEL` | `gpt-5-6-luna` | Hermes `model.default`、MPT `openai_model_name` |
| `LLM_UPSTREAM_BASE_URL` | `https://newapi.yuaiweiwu.com` | **仅** OpenInspector 转发的真实上游（无 `/v1`） |

## 各组件读什么

| 组件 | 配置位置 | sync 是否写入 |
|------|----------|----------------|
| Hermes Agent | `profiles/content-studio/config.yaml` | `model.base_url`、`model.default`、`providers.manifest.base_url` |
| Hermes keys | `profiles/content-studio/.env` | `CUSTOM_API_KEY` |
| Open Notebook | `open-notebook/.env` | `OPENAI_COMPATIBLE_*` |
| MoneyPrinterTurbo | `config.toml` `[app]` | `openai_base_url`、`openai_model_name` |
| OpenInspector | `openinspector/.env` | `BASE_URL` = 上游根域名 |

TTS、Embedding 不走 OpenInspector，不在此 sync 范围内。

## TencentDB Memory Hub（Hermes Desktop / Workspace）

完整步骤见 **[TDAI_MEMORY_INTEGRATION.md](../TDAI_MEMORY_INTEGRATION.md)**（Proxy 模式 + `tdai-proxy-headers` 插件，不改 Hermes 核心）。

## 审计

```bash
./scripts/audit-llm-config.sh
```
