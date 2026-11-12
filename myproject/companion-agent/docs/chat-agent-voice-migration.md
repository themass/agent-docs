# 语音迁到新服务：让语音和文字共享一个会话

日期：2026-11-12
状态：第一步（语音共用会话）已实现，见 §9。第二步（模型调用与语音质检留档）为设计，见 §11。§1 的"现状"是改动前的描述，保留作对照。

## 1. 现状

语音走一条独立的旧链路，和新的文字对话完全分开：

```
LiveKit 房间 → worker（livekit agents）→ entrypoint 用旧 container.brain
  → TurnPipeline（进程内）→ llm_node 把文字流喂给 TTS
```

- 旧 container 的记忆是进程内的，提示词来自旧的 `container.prompts.build`，**不读新的按角色隔离的记忆、画像和时间线**，也不写 Postgres。
- 语音里说的话不会进新的消息表，也不进 checkpoint 对话线程。所以：在语音里说的事，文字里的角色不知道；反过来也一样。
- 房间里没有会话 id、没有围栏号，不经过会话锁，**和文字回合可能同时跑**。

## 2. 目标

用户在同一个角色下，语音和文字是**同一段对话**：同一个会话 id、同一个对话线程、同一份记忆和画像、历史里能看到语音说过的内容（转写文字）。

## 3. 为什么不能直接改

三个需要先定的问题，选错了会出现并发写坏对话线程或语音延迟变差：

1. **回合在哪里跑。** 新服务的回合在 API 进程里跑（`TurnRunner`），结果以 Redis 事件流推给客户端。语音 worker 是另一个进程，LiveKit 的 `llm_node` 要的是**同步拉取的文字流**。两种做法：
   - A. worker 订阅 Redis 事件流，把 `message.delta` 转成 TTS 的输入（回合仍在 API 进程，复用全部逻辑，延迟多一跳 Redis）。
   - B. worker 进程内直接运行 `TurnRunner`（延迟最低，但 worker 要有完整的 `build_platform` 装配和围栏、锁逻辑，进程职责变重）。
   **建议 A**：不复制回合逻辑，延迟多的一跳在毫秒级。
2. **会话和锁。** 语音说话要走 `SubmitService.submit`（拿会话锁、落库、判定合并 / 插话 / 排队）。用户边说边打字时，两个入口会竞争同一个会话：新的合并 / 插话 / 排队规则已经能处理，但语音的「打断」要映射到 `cancel`。
3. **语音转写的落库。** 用户的话来自 STT：要决定存最终转写还是中间结果，识别错了用户怎么改（现在编辑接口按文字消息设计）。建议只存最终转写，`kind` 标 `voice`，不开放编辑。

## 4. 建议的步骤

| 步骤 | 内容 | 能独立验证吗 |
|---|---|---|
| 1 | 客户端语音页创建会话时改用新服务的会话 id（和文字页同一个 `AgentSessionMemory`），房间 metadata 带上 `session_id` | 是（看 metadata） |
| 2 | worker 的 `llm_node`：收到一句转写 → `POST /sessions/{id}/messages`（`kind=voice`）→ 订阅该会话的 SSE，把 `message.delta` 作为 TTS 输入；`turn.cancelled` / 用户打断 → `POST cancel` | 需要真实 LiveKit 房间 |
| 3 | 提示词里标明当前是语音通道（`channel="voice"` 已在 `build_prompt_plan` 里有参数），回复要短、口语化 | 是（单元测试） |
| 4 | 去掉旧 container 的语音依赖，保留旧页面作为回退一版 | — |

## 5. 风险与未验证

- **全程没有真实 LiveKit 环境可测**，步骤 2 只能靠联调；延迟（首字到首音）是否可接受要实测。
- TTS 提供商、声音克隆的许可和肖像权 / 声音权问题（调研报告第 10 节「待核实」）与此无关但会影响上线。
- 语音转写文字进入记忆和画像抽取：语音里的口误、识别错误会被当成用户说过的话。需要在抽取提示词里加「可能有转写错误」的提醒，或对语音来源降低置信度。

## 6. 已确认的决定（2026-11-12）

1. **回合在哪里跑：A**。worker 订阅会话事件流，把文字增量喂给 TTS；回合逻辑只有一份，留在 API 进程。
2. **转写**：只存最终结果，进消息表，`kind=voice`，不开放编辑。
3. **STT + TTS：火山引擎**，配置由产品提供（账号与密钥到手后接插件）。
4. **LiveKit**：需要 `LIVEKIT_URL`、`LIVEKIT_API_KEY`、`LIVEKIT_API_SECRET` 三个值（LiveKit Cloud 项目控制台里取，或自建服务）。拿到后先跑一个最小房间验证连接与 token。

## 6.1 LiveKit 已就绪（2026-11-12）

凭据已写入本地 `.env`（不入库），实测可用：能签发入场 token，管理 API 能列出房间。
第一步（房间携带新服务会话 id）已实现：`POST /companion/sessions` 接受可选的 `chat_session_id`，写进房间 metadata；
entrypoint 解析它，写坏了拒绝入场（用错会话会写进别人的对话线程）。

## 7. 仍然待定

- 火山 STT / TTS 的具体接入方式（实时流式 STT、还是分段识别；音色选择）。
- 语音来源的转写在记忆与画像抽取里是否降置信度：口误与识别错误会被当成用户说过的话。
- 语音回合与文字回合并发时的合并策略（现有 submit 的合并 / 插话 / 排队规则可直接复用，但要验证语音打断映射到 cancel 的时机）。

---

## 8. 实现记录（2026-11-12）

**已跑通并验证的部分**

| 环节 | 状态 | 验证方式 |
|---|---|---|
| 火山流式 ASR | ✅ | 用阿里合成的「你好，我是林澈。」反过来识别，结果完全一致 |
| 火山 TTS | ✅ | 合成 3.56 秒音频（113,888 字节 PCM） |
| LiveKit 语音栈装配 | ✅ | `build_voice_stack()` 返回 TTS / STT / silero VAD |
| worker 连云端 | ✅ | 注册成功，region: Japan |
| 语音用 DeerFlow | ✅ | 日志确认 `voice brain: DeerFlow`，不再是 FakeBrain |

**为什么用插件 + 覆盖鉴权，而不是自己写协议**

社区插件 `livekit-plugins-volcengine` 已经实现了 URL、请求体、分包、响应解析、重连。它唯一的
问题是鉴权头写死成旧版控制台格式，而我们的凭据是新版控制台签发的。所以只覆盖
`get_ws_header`（STT）和 `get_http_header`（TTS），其余全部沿用插件。见
`adapters/voice/volcengine_livekit.py`。

**踩到并修掉的坑**

1. worker 启动报 `ws_url is required`：LiveKit CLI 读 `os.environ`，不读 pydantic 的 `.env`。
   已在 `worker._export_livekit_env()` 里把配置写回环境变量。
2. `build_session_options` 没传 `mode`，默认 `text`，导致 STT/TTS/VAD 全都没挂上——表现是
   agent 进了房间但一句话不说。已修。
3. worker 原本固定用 `FakeBrain`：能听能说，但回答是写死的。现在优先用 DeerFlow，配置不全才降级，
   并且降级时打警告。
4. 音色与资源 id 必须配对：`BV503_streaming` 是 1.0 音色，这组 key 没有 1.0 权限。
   可用组合是 `seed-tts-2.0` + `saturn_zh_female_keainvsheng_tob`。

**还没做的**

- ~~语音和文字共用会话~~：已在 §9 完成（代码层面，未经真实房间验证）。
- 手机上验证：需要手机能访问到后端 API（当前 `Constants.BASE_IP` 指向生产域名）。

**启动命令**

```bash
cd /Users/gqli/work/deepagents/docs/myproject/companion-agent
PYTHONPATH=src .venv/bin/python -m companion.worker dev
```

---

## 9. 第一步：语音共用会话（2026-11-12，已实现）

### 9.1 为什么要改

改动前，语音和文字是两条独立的路，同一个用户在同一个角色下有两份互不相干的历史：

| 环节 | 文字（`TurnRunner`） | 语音（旧 `TurnPipeline`） |
|---|---|---|
| 说的话落 `ca_chat_message` | 是 | **否** |
| 会话锁、围栏 | 有 | **无**，可与文字回合同时跑 |
| 对话线程（checkpoint） | 按 `session_id` 有 | **无**（`checkpointer=None`），每句新线程 |
| 回合后处理（记忆、画像、时间线） | 有 | **无** |
| 提示词 | 按会话组装（角色卡、技能、记忆、画像） | 房间建立时拼一次 |

### 9.2 现在的链路

```
语音识别出的文字
   → CompanionAgent.llm_node
   → TurnPipeline（只做分句、剥情绪标签、打断）
   → PlatformBrain.start_turn
        先记事件流游标 → SubmitService.submit(kind="voice", steerable=False)
        → TurnRunner 执行（落库、锁、checkpoint、after_turn）
        → 读同一 turn_id 的 message.delta 作为 token 流
   → TTS
```

要点：

- **游标在提交之前记下**，回合可能在 `submit` 返回前就开始吐字，晚记会漏掉开头几个字。
- **按 `turn_id` 过滤**事件，文字那边的回合事件不会串进语音。
- **会话正忙**（文字正在回复）时，这句话已落库排队，由当前回合结束后的 drain 处理；语音不挂等一个还没开始的回合。
- **输入被内容检查拒绝**时抛 `TurnRefused`，`llm_node` 读一句固定回复，不让房间沉默。
- **房间必须带 `chat_session_id`**，缺了就拒绝入场，不再退回独立的语音会话。
- 建房间时（`POST /v1/voice/sessions`）由 `resolve_chat_session` 决定会话：
  - 客户端带了会话号 → 必须属于当前用户且角色一致，否则 404（`SubmitService` 自己不校验归属）；
  - 没带 → 取该用户该角色最近的会话，从没聊过才新建（否则每通电话一段历史）。
- 响应多一个 `chat_session_id` 字段，客户端据此让文字页和语音页读同一段历史。

### 9.3 与 §6 已确认决定的出入（需要你看一眼）

§6 第 1 条确认的是 **A：回合留在 API 进程，worker 订阅事件流**。实际实现更接近 B 的一部分：

- worker 进程自己调 `build_platform`，**在 worker 里运行 `TurnRunner`**，不经过 API 进程。
- 原因：A 需要 worker 以用户身份回调 API 的 `POST /sessions/{id}/messages`，而 worker 手里没有用户的登录 token，要另开一条服务间鉴权。
- 代价：worker 要连数据库和 Redis，进程更重；两个进程都能跑同一会话的回合，**靠 Redis 会话锁和围栏互斥**（该机制本来就按多进程设计）。
- 没变的部分：回合逻辑仍然只有一份（`TurnRunner`），不是复制；对客户端的行为与 A 一致。

如果坚持 A，需要补一条服务间鉴权（例如 worker 用内部 token 代用户提交）。这一点没有擅自决定，列在 §12。

另一条已确认决定"转写 `kind=voice`"本次已补上（第一次提交遗漏，随后修正）。"不开放编辑"尚未做：编辑接口还没按 `kind` 拦截。

### 9.4 验证情况

- 新增单元测试 30 个（`PlatformBrain` 11、入口与 agent 11、会话解析 8）全过，不依赖外部服务。
- **没验证**：真实 LiveKit 房间端到端；worker 与 API 进程同时在同一会话上跑回合；首字到首音的延迟。

## 10. 现有存储盘点（回答"数据在哪"）

| 数据 | 位置 | 说明 |
|---|---|---|
| 给用户看的历史 | Postgres `ca_chat_message` | 可编辑、删除、清空；以它为准 |
| 模型的工作上下文 | Postgres，LangGraph 的 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`checkpoint_migrations` | `AsyncPostgresSaver.setup()` 启动时自建，**不在 `ca_` 前缀下，也不归 Alembic 管**。线程 id = `thread_id_for(session_id)` |
| 我们的长期记忆 | Postgres `ca_memory_item` | 按角色隔离，用户可删 |
| DeerFlow 自带长期记忆 | 本地 JSON 文件 `{base_dir}/users/{uid}/memory.json` | **功能已关闭**，没写过任何东西。误开会写部署机磁盘，多实例各写各的，用户删记忆也删不到 |
| 回合元数据 | `ca_chat_turn`（有 `model`、`usage` 列） | `usage` 目前**没有任何代码写入**；对外事件里 `usage` 也是写死的 `None` |
| 工具调用审计 | `ca_tool_call` | 只有工具名、参数指纹、耗时，没有参数和结果 |
| 向量记忆 | pgvector 已装 | 未使用，记忆召回目前是词法检索 |

两个数据源要保持一致：`ca_chat_message` 与 checkpoint。`clear` 已同步重置线程；**逐条编辑、删除消息时 checkpoint 是否同步，没有验证**。

## 11. 第二步：模型调用与语音质检留档（设计，未实现）

### 11.1 为什么要做

现在没有任何地方记录"模型这一次到底收到了什么、回了什么、花了多少"，也没有语音链路的任何留档。做质检、算成本、排查"为什么这句话这么回"都没有数据。语音还有一个额外需求：除了看模型的输出，还要判断 **TTS 念得对不对**。

### 11.2 `ca_llm_call`（每次模型调用一行）

| 列 | 说明 |
|---|---|
| `id`, `turn_id`, `session_id`, `owner_id`, `role_id` | 关联键 |
| `provider`, `model`, `prompt_version` | 调的是谁 |
| `input_messages` | 送进模型的完整消息（JSON） |
| `output_text`, `reasoning_text` | 输出与思考内容 |
| `input_tokens`, `output_tokens`, `cached_tokens` | 取自供应商返回的 usage |
| `first_token_ms`, `total_ms` | 延迟 |
| `finish_reason`, `error_code` | 结束原因与错误 |
| `created_at` | 时间 |

同时把 `ca_chat_turn.usage` 真正填上（汇总值），并让 `message.done` 事件带上它。

### 11.3 `ca_voice_turn`（每个语音回合一行）

| 列 | 说明 |
|---|---|
| `id`, `session_id`, `turn_id`, `owner_id`, `role_id`, `user_message_id` | 关联键，`user_message_id` 指向 `kind=voice` 的消息 |
| `stt_provider`, `stt_text`, `stt_confidence` | 用户说的被识别成了什么 |
| `llm_text` | 模型产出的原文（含情绪标签） |
| `tts_text` | **实际送进 TTS 的每一句**（已剥标签、已分句），JSON 数组 |
| `tts_provider`, `tts_voice` | 用的哪个合成服务和音色 |
| `audio_in_key`, `audio_out_key` | 音频在对象存储里的键，可空 |
| `stt_ms`, `tts_first_audio_ms` | 各段耗时 |
| `created_at` | 时间 |

**TTS 准确性的判断方式**：把 `audio_out_key` 的音频回灌 ASR，识别结果与 `tts_text` 比对（字错率）。这要求同时有"送进去的文本"和"出来的音频"，所以两者都要留。`stt_text` 与用户原音频比对同理，用来评估识别本身。

### 11.4 合规与留存

这两张表存的是用户原话与语音，属于敏感数据：

- `ca_user_consent` 增加"语音与对话质检留存"一项，**默认关**；未同意的用户不写 `audio_*_key` 和 `input_messages`（只写 token、耗时等不含内容的指标）。
- 保留期限做成配置项 `COMPANION_QA_RETENTION_DAYS`，默认 90 天（待你确认），到期由后台任务清理，音频对象同步删除。
- 账号注销（`AccountPurgeService`）要覆盖这两张表和对应音频对象。
- 查询入口走管理员 token，不对普通用户开放。

### 11.5 表怎么建

产品未上线，新表直接加进单一的 `0001_baseline` 迁移，不另写迁移文件。**迁移文件顺序**：改完 `schema.py` 后重新生成 baseline，并确认 `memory.py` 已被导入（否则 `ca_memory_item` 会被漏掉，这个坑踩过一次）。上线后才开始写增量迁移。

## 12. 重复实现盘点与待定事项

### 12.1 仍然并存的"两条路"

| 项 | 路径 A（新） | 路径 B（旧） | 状态 |
|---|---|---|---|
| 回合执行 | `TurnRunner` | 旧 `TurnPipeline` 直连大脑 | **语音已并入 A**；`/v1/voice/turns`（`bootstrap/app.py`）仍用旧容器 |
| 大脑构建 | `platform._build_brain` | `voice_brain.build_voice_brain` | **已删除 B** |
| 装配 | `build_platform` | `create_container`（FakeBrain、内存时间线、`InitiativeLoop`） | 并存，待清理 |
| 主动消息 | 新栈提醒与派发 | 旧 `InitiativeLoop` 在内存时间线上 | 并存，待清理 |
| 主聊天页后端 | agent `/v1` | testserverV `/api/chat/*` | 客户端未切换 |
| 角色目录 | 服务端 md 目录 | 客户端内置 14 个 `agency-*` | 客户端未改 |
| 角色接口 | agent `/v1/roles` | Java `/api/roles/v1`（线上 400，缺 `-parameters`） | 待下线 |
| 长期记忆 | `ca_memory_item` | DeerFlow 自带记忆（已关） | 保持关闭 |

### 12.2 待你确认

1. **回合在哪个进程跑**：保持现在的 worker 内运行（§9.3），还是回到 A 并补服务间鉴权。
2. **质检数据保留天数**：默认 90 天是否合适。
3. **`kind=voice` 的消息不开放编辑**：编辑接口尚未拦截，是否现在补上。
4. DeerFlow `subagent` 保持关闭：对话是一问一答，没有可拆分的任务，开了只增加延迟与成本；以后接入需要并行查询的外部工具时再评估。

---

## 附：Alembic 是什么

Alembic 是 SQLAlchemy 配套的**数据库结构版本管理工具**。它把"表结构怎么变"写成按顺序排列的迁移脚本（`migrations/versions/` 下的 Python 文件），用 `alembic upgrade head` 把任意一个库升级到最新结构，用 `alembic downgrade` 回退。

作用：开发、测试、生产三个库的表结构始终一致，而且每一次改动都有记录。没有它，只能手工在各个库里执行 SQL，很容易漏。

在这个项目里：

- 现在只有一个迁移 `0001_baseline`，一次建出全部 `ca_*` 表。产品没上线，没有旧数据要保留，所以新增表直接改这一个文件，不另写。
- 上线之后每次改表结构就新增一个迁移文件，不再改 baseline。
- 它**不管** LangGraph 的 checkpoint 表，那几张表由 `AsyncPostgresSaver.setup()` 在服务启动时自己创建。
