# companion-agent server

companion-agent 的 Python 服务：FastAPI + SQLAlchemy(async) + PostgreSQL，内嵌 DeerFlow 作为对话主脑，
语音经 LiveKit Agents。

本文件是 `pyproject.toml` 声明的 `companion-agent` 发行包的说明；构建与 `uv sync` 都依赖它存在。
项目整体布局、产品设计、部署见上一级 [`../README.md`](../README.md)。

## 目录

| 路径 | 内容 |
|---|---|
| `src/companion/` | 服务代码，分层见下 |
| `tests/` | 不依赖真实外部服务的单测与契约测试 |
| `migrations/` | Alembic 迁移（单基线 `0001_baseline`，表前缀 `ca_`） |
| `wheels/` | `deerflow-harness`、`deerflow-extension-api` 的本地 wheel（没有发布到任何索引，入库） |
| `.env` | 本机配置，不入库；模板见 `.env.example` |

Prompt、角色卡、skill、模型路由不在这里，在 [`../agent/`](../agent/)。文件位置由
`src/companion/paths.py` 统一计算，其它模块不要自己数 `parents[n]`。

## 分层（import-linter 守着，见 `.importlinter`）

```
api       HTTP / SSE / LiveKit 入口
app       用例编排
domain    领域规则，无 I/O
ports     接口（Protocol）
adapters  端口的具体实现（数据库、Redis、DeerFlow、火山、LiveKit ……）
bootstrap 组合根：只有它和进程入口可以把上面的东西接起来
memory    记忆模块：model / port / service / sql / recall 同在一处（见下）
voice     语音模块：同样五件套
```

**业务模块与分层的区别。** `memory/` 和 `voice/` 不按层切：同一个概念原来分散在
`domain/memory`、`app/memory`、`adapters/memory`、`ports/memory.py`、`store/sql/memory.py`
五处，改一个功能要进五个目录。现在它们各是一个目录，内部可以垂直依赖；跨模块和跨层
仍受契约约束（模块不得引 `api`/`app`/`bootstrap`/`products`，两个模块之间互不依赖）。
其余概念（时间线、角色、主动性、质检……）还在按层切，尚未收进模块。

进程入口：`companion.serve`（API）、`companion.worker`（语音）、`companion.worker_jobs`（可选的独立后台循环）。

## 运行与检查

统一用上一级的脚本，不要在本目录手搓命令：

```bash
cd ..
./run.sh check        # 配置齐不齐、库和 Redis 连不连得上
./run.sh api          # 启动 API
./run.sh test         # 全量测试
```

只跑后端测试：

```bash
cd server
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/lint-imports      # 分层契约
```

部分用例需要真实 Postgres / Redis（`COMPANION_TEST_DATABASE_URL`、`COMPANION_TEST_REDIS_URL`），
没配置时会失败或被跳过，属环境缺失而非代码缺陷。
