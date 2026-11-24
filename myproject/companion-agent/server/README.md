# companion-agent server

companion-agent 的 Python 服务：FastAPI + SQLAlchemy(async) + PostgreSQL，内嵌 DeerFlow 作为对话主脑，
语音经 LiveKit Agents。

本文件是 `pyproject.toml` 声明的 `companion-agent` 发行包的说明；构建与 `uv sync` 都依赖它存在。
项目整体布局、产品设计、部署见上一级 [`../README.md`](../README.md)。

## 无会话拍照解题

`POST /v1/photosolve/solve?client_request_id=<1..128 字符非空标识>&subject=math`
复用 `current_user` 的 Bearer 登录态验证。body 是原始图片字节（不是 multipart / JSON），
`Content-Type: image/jpeg` 可用，但类型按文件头判定。`subject` 默认 `math`，仅支持数学。
声明长度与实际流式读取都限制为 **8 MiB**；图片按既有 uploads policy 解码、转正、
去 EXIF、长边缩到 2048、重编码 JPEG。PNG/JPEG/WebP/HEIC 的识别与解码能力沿用 uploads；
HEIC 仍取决于 Pillow 的解码支持。图片只在请求内存中使用，不写上传记录、聊天会话或数据库。

响应为普通 JSON（无 SSE、无外层 data 包装）：`requestId` 回传 `client_request_id`，
`providerUsed: "companion-agent"` 表示本服务处理（不承诺命中哪一个 fallback 模型），
`subject: "math"`，`questionFound`，`questions`。每题字段为 `index/text/latex/steps/
finalAnswer/finalAnswerLatex/thinking/confidence`，步骤为 `index/text/latex`，与 Android
`PhotoSolveApiResponse` 同名。`thinking` 可省略（服务端默认空字符串），无需模型提供私有思维链。
没有题目返回 HTTP 200、`questionFound: false, questions: []`，由客户端映射 40002。
模型 JSON 必须通过类型、长度、置信度范围和题目/答案一致性校验。

业务错误为 `{"detail":{"code":数字,"message":"安全提示"}}`：

| HTTP | code | 条件 |
|---|---|---|
| 400 | 40003 | 缺少/空白/过长 client_request_id、不支持的 subject、非法 Content-Length |
| 413 | 40003 | 图片 body 超过 8 MiB（包括没有 Content-Length 的流） |
| 422 | 40003 | 空图片、不支持的类型、无法解码、像素超限 |
| 429 | 42901 | 模型网关返回限流 |
| 502 | 50001 | 模型配置/调用失败、120 秒总调用超时、模型返回无效或过长结构 |

认证错误保持共用依赖的现有契约：HTTP 401（无效登录态）或 503（认证后端不可用），
`detail` 是字符串。提供商异常正文、图片和凭据不会回显给客户端。

旧 testserverV 的本地用户配额、费用预算和幂等去重**不会自动继承**到此直连接口。
当前 companion-agent 没有可直接复用的通用 HTTP 限流/配额依赖，此接口只映射网关 429，
没有新增配额子系统。`client_request_id` / `requestId` 仅用于客户端关联响应，不是幂等键，
也不承诺 exactly-once：同一标识重试仍会再次调用模型，可能重复计费。

模型在首次合法请求时惰性装配，经 `scenario_model(..., streaming=False).ainvoke` 发送
OpenAI-compatible `image_url` data URL。`COMPANION_LLM_MODEL_PHOTOSOLVE` 是**可选**模型链，
逗号分隔、按顺序故障转移；未设置/空字符串时沿用 `companion_chat` 的模型名，并应用
`photosolve` 自己的调优。每一跳都必须支持视觉 `image_url` 和结构化 JSON 文本回答；
若聊天模型是纯文本，必须显式配置视觉模型链。旧自定义 routing 文件未声明 photosolve 时沿用
companion_chat 场景，避免让现有部署因新增必填环境变量启动失败。无需新增网关凭据。

## 目录

| 路径 | 内容 |
|---|---|
| `src/companion/` | 服务代码，按业务模块分（见下） |
| `tests/` | 不依赖真实外部服务的单测与契约测试 |
| `migrations/` | Alembic 迁移（单基线 `0001_baseline`，表前缀 `ca_`） |
| `tools/` | 一次性/开发期工具：DDL 生成、角色目录拆分、TTS 往返质检 |
| `wheels/` | `deerflow-harness`、`deerflow-extension-api` 的本地 wheel（没有发布到任何索引，入库） |
| `.env` | 本机配置，不入库；模板见 `.env.example` |

Prompt、角色卡、skill、模型路由不在这里，在 [`../agent/`](../agent/)。文件位置由
`src/companion/paths.py` 统一计算，其它模块不要自己数 `parents[n]`。

## 两层：agent 与 service

**`agent/` 是可复用的能力，`service/` 是这个产品的业务流程。依赖只允许 `service → agent`。**

```
src/companion/
├── agent/                    可复用能力（不认识"角色扮演"这个产品）
│   ├── brain/                主脑端口 port.py + DeerFlow 实现 + 图内中间件 + 模型调用采集
│   ├── memory/               记忆：召回、抽取、写入、SQL 与内存实现
│   ├── tools/                工具框架：注册表、授权、确认、执行
│   ├── roles/                角色卡与角色目录的解析（纯逻辑）
│   ├── prompt/               提示词组装、RoleProfile（纯函数）
│   ├── lorebook/             世界书：条目、匹配、按深度注入
│   ├── text/                 断句、渲染、事件协议（纯逻辑）
│   ├── middleware/           输入侧安全检测（纯逻辑）
│   ├── skills/               Skill 包加载
│   ├── llm/                  模型路由（场景 → 模型链）
│   └── util/                 ULID
│
├── service/                  本产品的业务流程
│   ├── chat/                 回合引擎：提交、执行、排队排空、历史、摘要
│   ├── turn/                 回合状态机、控制面（Redis）、触发器
│   ├── turns/                把输入接到提交路径（语音、主动开口）
│   ├── voice/                语音：TTS/STT、火山与阿里、TTS 采集与质检
│   ├── room/                 语音房间：建房、入场 token、会话解析
│   ├── proactive/            主动性：调度、开口、提醒、投递
│   ├── timeline/  jobs/  trace/  uploads/  account/  compliance/
│   ├── tools_impl/           产品工具（recall_facts / create_reminder …）
│   ├── roles/  persona/  avatar/  auth/  history/
│
├── db/                       共享持久化：表结构、记录类型、端口、SQL 实现
├── api/                      HTTP / SSE / LiveKit 路由
├── bootstrap/                组合根
└── serve.py  worker.py  worker_jobs.py     进程入口
```

边界上的几个判断：

| 东西 | 归属 | 理由 |
|---|---|---|
| `BrainPort` / `TurnRequest` | `agent/brain/` | 描述"一次模型回合"，任何 agent 产品都有 |
| `Disposition` / 回合状态机 | `service/turn/` | "合并、插话、排队"是本产品的对话策略 |
| `PlatformBrain` | `service/turns/` | 它做的是把语音接到本产品的 SubmitService |
| `RoleProfile` | `agent/prompt/` | 提示词用的角色视图 |
| 角色卡解析 | `agent/roles/` | 纯解析；从哪读由 service 决定 |
| 产品工具 | `service/tools_impl/` | 用到时间线、提醒这些产品概念 |
| 工具框架 | `agent/tools/` | 与产品无关 |

## 契约（import-linter 守着，见 `.importlinter`）

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q   # 测试
PYTHONPATH=src .venv/bin/lint-imports          # 契约
```

6 条，守的是**层之间的方向**：

| 契约 | 含义 |
|---|---|
| `agent` 不得依赖 `service` | agent 要能被别的产品直接拿走 |
| `agent` 不得依赖 `api` 与 `bootstrap` | 组合与协议不属于能力 |
| `agent` 纯逻辑部分（prompt/text/lorebook/middleware/util）不得碰 I/O 与框架 | 这些要能在无库无网的测试里跑 |
| `db` 不依赖任何业务层 | 持久化不反向依赖调用方 |
| `service` 不得依赖 `api` | 路由在业务之外 |
| 只有组合根与入口可以 import `bootstrap` | 依赖注入只在一处发生 |

这些契约有效：写完它们时立刻抓到 10 条真实越界（`brain → turn`、`prompt → roles`、
`tools/builtin → proactive/timeline` 等），逐条修掉的。

## 运行与检查

统一用上一级的脚本，不要在本目录手搓命令：

```bash
cd ..
./run.sh check        # 配置齐不齐、库和 Redis 连不连得上
./run.sh api          # 启动 API
./run.sh test         # 全量测试
```

部分用例需要真实 Postgres / Redis（`COMPANION_TEST_DATABASE_URL`、`COMPANION_TEST_REDIS_URL`），
没配置时会失败或被跳过，属环境缺失而非代码缺陷。
