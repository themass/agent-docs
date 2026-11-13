# companion-agent server

companion-agent 的 Python 服务：FastAPI + SQLAlchemy(async) + PostgreSQL，内嵌 DeerFlow 作为对话主脑，
语音经 LiveKit Agents。

本文件是 `pyproject.toml` 声明的 `companion-agent` 发行包的说明；构建与 `uv sync` 都依赖它存在。
项目整体布局、产品设计、部署见上一级 [`../README.md`](../README.md)。

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

## 按业务模块分包

一个概念的全部代码在**同一个目录**里：领域规则、端口、用例、存储实现放在一起。
改一个功能只进一个目录，不再横跨四层。

```
src/companion/
├── api/          HTTP / SSE / LiveKit 入口（路由，不含业务规则）
├── bootstrap/    组合根：把各模块的实现接起来。只有它和进程入口可以 import 它
│
├── chat/         回合引擎：提交、执行、排队、历史、摘要、停机排空
├── turn/         回合状态机、管线（token 流 → 可朗读整句）、控制面（Redis）
├── brain/        主脑：端口 + DeerFlow 实现、图内中间件、模型调用追踪
├── memory/       记忆：召回、抽取、写入、SQL 与内存实现
├── voice/        语音：TTS/STT 端口、火山与阿里实现、TTS 采集与质检
├── room/         语音房间：建房、入场 token、会话绑定
│
├── prompt/       提示词组装（纯函数）
├── roles/        角色卡与系统目录
├── persona/      用户画像
├── avatar/       形象包
├── lorebook/     世界书
├── text/         断句、渲染、事件协议（纯逻辑）
├── middleware/   输入侧安全检测（纯逻辑）
│
├── timeline/     事件时间线：抽取、存储、每日整理
├── proactive/    主动性：调度、开口、提醒、投递
├── jobs/         后台任务队列
├── tools/        工具：注册表、授权、确认、执行
├── trace/        质检留档：回合追踪与旁路写入
├── uploads/      上传：校验、处理、对象存储
├── account/      账号注销
├── compliance/   合规：同意、导出、总开关
│
├── store/        共享持久化：会话/消息/队列/角色/上传/确认的 SQL 实现与表结构
├── auth/         登录态校验（读 Java 的 Redis token）
├── llm/          模型路由（场景 → 模型链，模型名只在 .env）
├── skills/       Skill 包加载
├── history/      历史窗口与摘要的纯函数
└── util/         ULID 等无依赖工具
```

进程入口：`companion.serve`（API）、`companion.worker`（语音）、`companion.worker_jobs`（可选的独立后台循环）。

## 契约（import-linter 守着，见 `.importlinter`）

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q   # 测试
PYTHONPATH=src .venv/bin/lint-imports          # 契约
```

4 条，守的是**模块之间的方向**，不是模块内部的形状：

| 契约 | 含义 |
|---|---|
| 只有组合根与入口可以 import bootstrap | 依赖注入只在一处发生 |
| 业务模块不得依赖 `api` | 路由层在模块之外，不能反过来被业务依赖 |
| 纯逻辑模块（`prompt`/`text`/`lorebook`/`middleware`/`util`）不得碰 I/O 与框架 | 这几块要能在没有数据库和网络的测试里跑 |
| `store` 是底座，不依赖任何业务模块 | 持久化不反向依赖调用方 |

模块内部（同一个目录里的 `model.py` / `port.py` / `service.py` / `sql.py`）**允许互相依赖**，
这是分包的意义；跨模块仍然要有方向。

### 已知的双向依赖（未拆）

这 4 处是真的双向，没有靠放宽契约掩盖。拆它们要改接口，属于下一轮的事：

```
brain <-> turn                  pipeline 用 BrainPort；deerflow 用 lc_user_id / steer 渲染
prompt <-> roles                roleplay 提示词用 RoleProfile；profile 用 prompt 的 plan 常量
chat <-> jobs <-> proactive     chat 用 JobStore；jobs 装配 proactive；proactive 用 chat 提交回合
brain -> tools -> proactive -> brain
```

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
