# TencentDB Agent Memory × Content Studio（推荐集成）

Content Studio 默认走 **Memory Proxy（8096）+ OpenInspector 追踪**，与「只装 Hermes、无 deepagents 源码」的用户路径一致。

## 两条官方集成（不要混用为同一件事）

| 模式 | 适用 | 安装 |
|------|------|------|
| **A. Proxy（本栈默认）** | LLM 经 `8096/hermes/default`，Hub 面板看 L0、注入在 Proxy | `tdai-hermes-ids.env` + secrets sync + **tdai-proxy-headers** 插件 |
| **B. Hermes Memory Provider** | LLM 直连上游，记忆走 Hermes `memory.provider` + Core `:8420` | TencentDB `MemoryCore/scripts/install-hermes-plugin.sh`（`memory_tencentdb`） |

本仓库 **Content Studio 全栈 = A**。Open Notebook / MPT 走 `8096/codebuddy/...`，不走 Hermes 插件。

## A 模式：你需要维护的唯一配置

1. 在 Memory Panel 注册 **team / agent / task**。
2. 写入 profile：

   `~/.hermes/profiles/content-studio/tdai-hermes-ids.env`（见 `bundle/profile/tdai-hermes-ids.env.example`）。

3. 运行 secrets sync（全栈启动会自动跑）：

   ```bash
   cd hermes-dev
   CONTENT_STUDIO_RUNTIME_DIR="$(pwd)/.runtime/content-studio-stack" \
   CONTENT_STUDIO_LLM_VIA_TDAI_PROXY=1 \
   HERMES_HOME="$HOME/.hermes/profiles/content-studio" \
   ./scripts/sync-content-studio-secrets.sh
   ```

   会写入：`config.yaml` 的 `model.default_headers`、`~/.hermes/.env` 的 `TDAI_*`（供插件读取）、`sk-mem` 密钥。

4. **Hermes 插件（不改 Agent 核心）**：`tdai-proxy-headers`  
   每轮 LLM 请求为 `/hermes/` 补上 `x-conversation-id`（= Hermes `session_id`）及 team/agent/task。

   ```bash
   ./docs/hermes/content-studio-agent/bundle/ops/scripts/install-tdai-proxy-headers-plugin.sh
   ```

   全栈 `start-content-studio-stack.sh` 在 `CONTENT_STUDIO_TDAI_INSTALL_PLUGIN=1`（默认）时自动安装到 `~/.hermes/plugins/`。

5. **重启 Hermes Gateway**（及 Desktop），新开会话聊天。

6. 在 Hub 看 **L0**；L1–L3 由抽取流水线异步产生，可能较慢。

## Proxy 侧（TencentDB 仓库）

Hermes 常只配 team/agent/task、不带 `x-conversation-id`。MemoryProxy 应对 **hermes / openclaw** 在 header 齐全时生成稳定会话 id（`preset:team:agent:task:keyId`）；**插件**会优先发真实 `session_id`，多会话更准确。

修改在 `TencentDB-Agent-Memory/MemoryProxy/src/session/session-key.ts`。更新 Proxy 镜像后需重建并重启 `tdai-proxy`：

```bash
cd /path/to/TencentDB-Agent-Memory/MemoryProxy
docker build -t agentmemory/memory-proxy:local .
# 在 deploy/global-images/.env 设 PROXY_IMAGE=agentmemory/memory-proxy:local 后
cd ../deploy/global-images && ./start-proxy.sh
```

## 校验

```bash
CONTENT_STUDIO_RUNTIME_DIR=hermes-dev/.runtime/content-studio-stack \
bash hermes-dev/ops/scripts/verify-content-studio-connectivity.sh
```

应看到 Proxy chat 成功、`tdai-recorder write-l0` 出现在 `docker logs tdai-proxy` 近期日志中，且 **Gateway 一发一收后** 最近一条 `injection-debug` **不是** `conversationId=null` / `injectedSkipped=true`。

### `conversationId=null` 是什么意思？

Proxy 日志里的 `conversationId` 是 **HTTP 请求上的记忆会话 id**，不是 Desktop 界面里的「会话名」。

| 日志 | 含义 |
|------|------|
| `conversationId=null` + `injectedSkipped=true` | 这次 LLM 请求 **没带** `x-team-id` / `x-agent-id` / `x-task-id`（`[identity]` 行通常没有 `custom=[x-team-id,…]`）→ **不写 L0** |
| `conversationId=preset:team:…:keyId` | 带了 team/agent/task，但 **没有** `x-conversation-id` → Proxy 兜底成一个固定会话 |
| `conversationId=<session_id>` | **推荐**：`tdai-proxy-headers` 已把 Hermes `session_id` 写入 `x-conversation-id` |

常见修复：跑 `sync-content-studio-secrets.sh` → `install-tdai-proxy-headers-plugin.sh` → **重启 Gateway（及 Desktop）** → 新开聊天。主模型必须走 `model.base_url` 的 `8096/.../hermes/...`；`auxiliary.*` 走 OpenInspector `:8080` 的旁路任务 **不会** 记入 Memory Hub（设计如此）。

## 不要做什么

- **不要**改 `hermes-agent/agent/*` 核心来带 header（升级会丢）。
- **不要**指望 OpenInspector 写入 Memory Hub（只追踪）。
- **不要**用 L3 是否为空判断「有没有记忆」；先看 L0。
