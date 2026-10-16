# JC Scripts

> **日常开发只需要两个入口：** `./scripts/dev.sh` 启动本地服务，`./scripts/test-local.sh` 运行不依赖真实外部服务的本地检查。

## 常用入口

| 命令 | 何时使用 | 是否需要真实外部依赖 |
|---|---|---|
| `./scripts/setup-venv.sh` | 首次准备开发环境或依赖变更后 | 需要本机 Python/包安装 |
| `./scripts/dev.sh` | 启动本地 API、Web 和内嵌 Agent | MySQL/Redis/LLM/TOS 按 `.env` 配置 |
| `./scripts/test-local.sh` | 提交前、本地回归、候选版本代码检查 | 否；不会调用真实 API/Agent/TOS/邮件 |
| `./scripts/test-live.sh smoke` | 本地或 staging 的核心 API + PDF/DOCX 导出联调 | 是，需 API、账号及相关服务 |
| `./scripts/test-live.sh agent` | Agent/DeerFlow、SSE、消息持久化、取消联调 | 是 |
| `./scripts/test-live.sh regression` | 回归样本的简历、JD、双语预览联调 | 是 |
| `./scripts/db_upgrade.sh` | 明确执行数据库 migration | MySQL |
| `./scripts/seed_demo.py` | 创建本地演示账号/数据 | MySQL/Redis |

## 本地开发推荐流程

```bash
cd /Users/gqli/work/deepagents/docs/myproject/job-come
./scripts/setup-venv.sh                # 首次或依赖变更时
cp backend/server/.env.example backend/server/.env  # 首次时
./scripts/dev.sh                        # 终端 1：启动 API + Web
./scripts/test-local.sh                 # 终端 2：代码、测试、构建检查
```

`dev.sh` 默认启动 Web `http://127.0.0.1:3000`、API `http://127.0.0.1:8000/api/v1`。DeerFlow Agent 内嵌在 API Python 进程内，不需要单独启动第三个 Agent 服务。

## 按职责分类

### 运行与部署

- `dev.sh`：开发启动入口。
- `db_upgrade.sh`：在 `backend/server/` 执行 Alembic migration（使用同目录 `alembic.ini`）。
- `install-production.sh`：以锁定依赖安装生产运行时。
- `sync-deerflow-upstream.sh`：**维护动作**，同步 vendored DeerFlow；不是日常开发或生产部署步骤。
- `lib/project_paths.sh`：供 shell 脚本 `source` 的路径工具，不直接执行。

### 本地质量检查

- `test-local.sh`：Python 全量测试、前端生产构建、文档评测输出、脚本语法检查；可选 UI 验收开关。
- `verify_ui.py`：独立 UI 夹具/浏览器验收，`test-local.sh` 中以 `RUN_UI_ACCEPTANCE=1` 显式启用。
- `audit_visual.py`：真实浏览器里的机械视觉审计（对比度、失效 Tailwind class、横向溢出、字号标尺）。
  需要先起好前端生产构建，用 `--base` 指定地址；发现问题以非 0 退出。详见
  `docs/architecture/TECH-DESIGN-SYSTEM.md` 第 10 节。
- `verify_exports.py`：导出物视觉/结构证据的专用检查工具。
- `evaluate_documents.py`：轻量文档解析质量评测，输出 `docs/evidence/document-evaluation.json`。
- `evaluate_docling.py`：使用本地 Docling 源码的隔离评测，不默认纳入常规本地测试。

### 真实服务联调

- `test-live.sh`：**唯一的用户入口**；用参数选择 `smoke`、`agent`、`regression` 或 `all`。
- `e2e_smoke.sh`、`agent_e2e.sh`、`regression_smoke.sh`：由 `test-live.sh` 调度的分项实现，通常无需直接运行。

## 已移除的重复脚本

- `ci_regression.sh`：仅重复 `test-local.sh` 中已有的测试子集。
- `export_smoke.sh`：其 PDF 导出验证已并入 `test-live.sh smoke`。

## 常用环境变量

```bash
# dev.sh
JC_SKIP_DB_UPGRADE=1
JC_API_RELOAD=false
JC_WEB_CLEAN=false

# test-live.sh
JC_E2E_BASE=http://127.0.0.1:8000/api/v1
JC_E2E_EMAIL=...
JC_E2E_PASSWORD=...

# test-local.sh 的可选额外门禁
RUN_UI_ACCEPTANCE=1 UI_BASE_URL=http://127.0.0.1:3107
```

真实凭据只写入本地 `backend/server/.env` 或密钥管理系统，绝不写入脚本、README 或 Git。
