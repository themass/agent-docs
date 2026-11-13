# companion-agent

角色扮演（Her）的 agent 服务。独立部署，不与 job-come 共用代码或部署。

不是「一个能聊天的角色」，是每个用户自己的 her：懂这个人、有存在感、能替他做事、始终是同一个「人」。
对话只是 agent 的一个入口，文字和语音共用同一个会话、同一条对话线程、同一份记忆。

- 运行时：Python 3.12；对话主脑 **DeerFlow**（嵌入式 harness）；语音 LiveKit Agents + 火山引擎。
- 存储：PostgreSQL（业务表前缀 `ca_`，对话线程用 LangGraph checkpoint）、Redis（会话锁、事件流、登录态）。
- 账号与登录：复用 App 现有的 Java 登录态，本服务只校验 token（`redis_token`）。
- 设计文档：[`docs/`](docs/)；运行与部署：[`docs/RUNBOOK.md`](docs/RUNBOOK.md)。

## 目录

```text
server/      Python 工程：代码、测试、迁移、依赖锁、.env
agent/       Agent 资源（不是 Python，当数据发布）：角色卡、角色目录、skill、模型路由
scripts/     发布与部署：publish.sh deploy.sh process.sh、nginx 片段
docs/        设计、运维、决策
run.sh       本地统一入口：api / voice / jobs / migrate / check / test
```

```text
server/
  src/companion/    agent/ 可复用能力 + service/ 本产品业务（见 server/README.md）
  tests/            不依赖真实外部服务的单测与契约测试
  migrations/       Alembic（单基线 0001_baseline）
  tools/            一次性/开发期工具：gen_ddl、角色目录拆分、TTS 往返质检
  wheels/           deerflow-harness 等本地 wheel（未发布到任何索引，入库）
  pyproject.toml  uv.lock  .env.example  .importlinter

agent/
  characters/       角色卡（SillyTavern V2）
  roles/catalog/    系统角色目录（一个角色一个 md）
  skills/public/    skill 包：方法论，由宿主组装进提示词
  llm/routing.yaml  模型路由：场景 → 模型链，只引用环境变量名
```

文件位置由 `server/src/companion/paths.py` 统一计算；其它模块不要自己数 `parents[n]`。

## 换模型

在 `server/.env` 里改场景变量，逗号分隔、按顺序故障转移，`routing.yaml` 不用动：

```bash
COMPANION_LLM_MODEL_COMPANION_CHAT=模型A,模型B
```

可用场景：`COMPANION_CHAT`、`MEMORY_EXTRACT`、`SESSION_SUMMARIZE`、`COMPANION_REWRITE`。
变量名拼错会在启动时报错，不会静默继续跑旧模型。

## 本地运行

```bash
cd server
uv sync --frozen --extra livekit --extra dev     # 首次或依赖变更
cp .env.example .env                              # 填网关、数据库、Redis、LiveKit
cd ..
./run.sh check                                    # 配置齐不齐、库和 Redis 连不连得上
./run.sh api                                      # 启动 API（后台循环默认跟着它跑）
./run.sh voice                                    # 语音 worker（需要 LiveKit 凭据）
./run.sh test                                     # 全量测试
```

## 接口

统一前缀 `/v1`，用 `Authorization: Bearer <登录 token>`。

| 路径 | 内容 |
|---|---|
| `/v1/sessions`、`/v1/sessions/{id}/messages`、`/v1/sessions/{id}/events` | 会话、发消息、SSE 事件流（取消、重试、队列、重新生成） |
| `/v1/roles`、`/v1/divisions`、`/v1/characters` | 角色目录与角色卡 |
| `/v1/memory/*`、`/v1/reminders`、`/v1/inbox`、`/v1/prefs` | 记忆、提醒、主动消息、偏好 |
| `/v1/voice/sessions` | 建语音房间（返回 LiveKit 入场 token） |
| `/v1/uploads`、`/v1/consent`、`/v1/export`、`/v1/me` | 上传、同意、导出、账号 |
| `/health`、`/readyz` | 探针 |

完整列表以运行中的 `/openapi.json` 为准。

## 约定

- 密钥只放环境变量，不写入代码、配置文件或文档。`.env` 不入库。
- 对话流式为默认；主脑中途失败时先交付已生成的句子再结束。
- 新增角色放 `agent/characters/`；需要新方法论的建 skill 包，并在角色卡 `extensions.vvv.skill` 引用。
- 新增动作必须给 `ActionSpec` 定权限与可撤销性。
- 提交前跑 `server/` 里的 `lint-imports`：分层契约是设计的一部分。

## 已知未完成

- 真实 LiveKit 房间里的 `tts_node` / `llm_node` 联跑没有验证过（单测用假实现驱动）。
- 用户侧音频（STT 输入）没有采集；`ca_voice_turn.audio_in_key` 列在，没有代码写入。
- 所有语音 worker 满载时，用户进房间会静音（建房间接口不知道容量）。
- 需要 alembic 的测试在 SQLite 下无法执行。
