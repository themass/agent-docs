# JC API Server

JC 的后端服务：FastAPI + SQLAlchemy(async) + aiomysql，内嵌 DeerFlow Agent 运行时。

本包为 `pyproject.toml` 中声明的 `jc` 发行包提供项目说明；构建与 `uv sync` 都依赖本文件存在。

## 职责范围

- `src/jc/api/`：HTTP 路由，统一前缀 `/api/v1`。
- `src/jc/services/`：业务编排（档案解析、简历优化、JD 解析、匹配评分、导出）。
- `src/jc/stores/`：数据访问层，不含业务判断。
- `src/jc/agent/`、`src/jc/adapters/`：Agent 任务与 DeerFlow 接入。
- `alembic/`：数据库 migration。
- `tests/`：不依赖真实外部服务的单测与契约测试。

Prompt、Skill 与模型路由配置不在本目录，位于 `../agent/`。

## 本地运行

统一通过仓库脚本启动，不要在本目录手搓命令：

```bash
cd ../..                       # 回到 job-come/
./scripts/setup-venv.sh        # 首次或依赖变更
cp backend/server/.env.example backend/server/.env
./scripts/dev.sh               # 启动 API + Web
```

API 默认 `http://127.0.0.1:8000/api/v1`，健康检查 `http://127.0.0.1:8000/health`。

## 测试与检查

```bash
cd ../..
./scripts/test-local.sh        # 本地全量检查，不调用真实外部服务
```

仅跑后端测试：

```bash
cd backend/server
PYTHONPATH=src pytest -q
```

PDF 导出与公开页动态渲染测试需要 Playwright Chromium；未安装时这些用例会失败，属环境缺失而非代码缺陷。

## 相关文档

- 系统设计：`../../docs/architecture/TECH-SYSTEM.md`
- API 约定：`../../docs/architecture/TECH-API.md`
- 数据与存储：`../../docs/architecture/TECH-DATA.md`
- 本地开发：`../../docs/operations/OPS-DEVELOPMENT.md`
