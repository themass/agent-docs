# Her Companion · Phase 0 技术样机

> 产品基线：[../HER_COMPANION_PRODUCT_BRIEF.md](../HER_COMPANION_PRODUCT_BRIEF.md)  
> 目标：验证 **LiveKit 语音管道** + **Hermes Core 记忆注入** + **知心姐姐 persona**

## 架构（Phase 0）

```text
用户麦克风
  → LiveKit AgentSession (STT / VAD / TTS / 打断)
  → CompanionAgent (persona + ~/.hermes/memories 注入)
  → LLM（二选一）
       ├─ inference（默认，低延迟联调）
       └─ hermes：Hermes Gateway /v1/chat/completions（全 agent，较慢，Phase 1+）
```

| 文件 | 作用 |
|------|------|
| `persona.py` | 小棠人格与语音约束 |
| `memory.py` | 读取 `USER.md` / `MEMORY.md` |
| `llm_factory.py` | STT/LLM/TTS 工厂 |
| `companion_agent.py` | LiveKit 入口 |

## 前置

1. **LiveKit Cloud** 账号与 API Key（[cloud.livekit.io](https://cloud.livekit.io)）
2. **Python 环境**：使用 monorepo 内 `hermes-dev/agents`（已含 `livekit-agents`）
3. **可选**：Hermes 记忆文件 `~/.hermes/memories/USER.md`、`MEMORY.md`
4. **可选**：Hermes Gateway（仅 `HERMES_COMPANION_LLM=hermes` 时需要）

## 快速开始

```bash
# 1. 配置环境
cp agent-research/her-companion/.env.example agent-research/her-companion/.env
# 编辑 .env 填入 LIVEKIT_* 

# 2. 本地控制台模式（麦克风 + 扬声器，无需另开 room）
cd hermes-dev/agents
uv run python ../../agent-research/her-companion/companion_agent.py console

# 3. 或 dev 模式（连接 LiveKit 房间，可配 playground）
uv run python ../../agent-research/her-companion/companion_agent.py dev
```

## Hermes 记忆联调

在 `~/.hermes/memories/USER.md` 写入例如：

```text
用户叫小明，喜欢简短回复，讨厌被说教。
```

重启 agent 后，小棠会在 system 里带上这段（不会逐字念出）。

验证记忆加载：

```bash
python agent-research/her-companion/memory.py
```

## Hermes Gateway 模式（实验）

```bash
# ~/.hermes/.env
API_SERVER_ENABLED=true
API_SERVER_KEY=change-me-local-dev

hermes gateway run
```

```bash
# her-companion/.env
HERMES_COMPANION_LLM=hermes
```

注意：Gateway 会跑**完整 Hermes agent（含工具）**，延迟高，不适合最终伴侣形态；Phase 1 应改为「轻量 chat + session_search / hindsight」。

## 下一步（Phase 1）

- [ ] 会话级 `session_id` 写回 Hermes（跨房间记忆）
- [ ] `session_search` / hindsight `auto_recall` HTTP 桥
- [ ] 倾听 / 解惑双模式分类
- [ ] Web 客户端进房
- [ ] 危机关键词话术

## 相关路径

- LiveKit 示例：`hermes-dev/agents/examples/voice_agents/basic_agent.py`
- Hermes API：`hermes-dev/hermes-agent/website/docs/user-guide/features/api-server.md`
