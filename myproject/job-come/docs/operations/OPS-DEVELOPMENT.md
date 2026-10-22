# OPS-RUNBOOK：本地启动、验证与排障

- **状态**：日常开发和联调操作手册
- **最后更新**：2026-10-15

## 1. 首次准备

```bash
cd /Users/gqli/work/deepagents/docs/myproject/job-come
cp backend/server/.env.example backend/server/.env
./scripts/dev.sh   # 首次启动会自动 uv sync；也可先单独跑 ./scripts/setup-venv.sh
```

Python 依赖使用 deepagents 根目录的共享 `venv`，不要在 JC 根目录再创建 `.venv`。迁移通过 `venv/bin/alembic` 执行（勿在 `backend/server` 下 `python -m alembic`，会与迁移目录 `alembic/` 冲突）。填写 `.env` 时只在本机/密钥管理系统中保存真实凭据。

## 2. 开发启动

```bash
cd /Users/gqli/work/deepagents/docs/myproject/job-come
./scripts/dev.sh
```

脚本会定位共享 Python 环境，启动：

- FastAPI：`http://127.0.0.1:8000`；
- Next.js：`http://127.0.0.1:3000`；
- DeerFlow Agent：内嵌在 FastAPI 进程。

常用变体：

```bash
JC_SKIP_DB_UPGRADE=1 ./scripts/dev.sh   # 不自动执行 Alembic migration
JC_API_RELOAD=false ./scripts/dev.sh    # 文件监听受限时关闭 reload
JC_WEB_CLEAN=false ./scripts/dev.sh     # 保留 .next 缓存
```

## 3. 单独运行

```bash
# API
set -a && source backend/server/.env && set +a
../../../venv/bin/uvicorn jc.main:app --app-dir backend/server/src --reload --host 0.0.0.0 --port 8000

# Web（另一终端）
cd frontend/web
npm install
npm run dev
```

## 4. 验证命令

```bash
# Python 测试
cd backend/server
../../../../../venv/bin/python -m pytest -q

# 前端生产构建
cd frontend/web
npm run build

# 本地综合检查（会生成 docs/evidence/document-evaluation.json）
cd /Users/gqli/work/deepagents/docs/myproject/job-come
./scripts/test-local.sh
```

### 版面与交互验收脚本

这几个脚本用真实 Chromium 打**构建产物**（不是 dev server），API 全部走夹具路由，
所以不需要后端和 LLM：

```bash
cd frontend/web && npm run build        # 必须先构建
npx next start -p 3138 &                # 换个没被占用的端口

# 等页面真的能打开再跑，见下面的注意事项
cd /Users/gqli/work/deepagents/docs/myproject/job-come
../../../venv/bin/python scripts/verify_ui.py           --base http://127.0.0.1:3138
../../../venv/bin/python scripts/verify_resume_steps.py  --base http://127.0.0.1:3138
../../../venv/bin/python scripts/verify_agent_rail.py    --base http://127.0.0.1:3138
```

两个注意事项，都踩过：

- **就绪探测要打真实页面并要求 200**，不要只探 `/auth/login`。超时被中断的
  `next start` 会留下一个占着端口的进程，它对所有路径返回 404；脚本于是跑在一个
  404 页面上，症状是定位器全部为空而不是报错。
- **改过 `globals.css` 或 `tailwind.config.ts` 必须重新 `npm run build`**，
  `tsc --noEmit` 不校验 CSS。dev server 占着 `.next` 时 build 会冲突
  （`Cannot find module './611.js'`），解法是停掉 dev server 后 `rm -rf .next && npm run build`。

## 5. 真实服务联调

启动本地服务后，使用统一入口：

```bash
export JC_E2E_EMAIL=...
export JC_E2E_PASSWORD=...
./scripts/test-live.sh smoke       # 核心流程 + PDF/DOCX 导出
./scripts/test-live.sh agent       # Agent/SSE/取消
./scripts/test-live.sh regression  # 回归样本
```

完整脚本说明见 [`../../scripts/README.md`](../../scripts/README.md)。

## 6. 常见问题

| 现象 | 排查顺序 |
|---|---|
| `No 'script_location' key found in configuration` | Alembic 工作目录必须是 `backend/server/`；配置文件为同目录的 `alembic.ini`（`script_location` 指向 `alembic/`）。用 `./scripts/db_upgrade.sh` 或 `./scripts/dev.sh`，不要从 JC 根目录裸跑 `alembic` |
| 数据库连接失败 | 检查 `JC_DB_*`、网络可达性、MySQL 用户权限与 migration 状态 |
| 会话/验证码不工作 | 检查 Redis URL、`jc:{env}:` 前缀、TTL 与 Redis 可用性 |
| 上传或导出失败 | 检查 TOS 配置、`jc/{env}/` 前缀、bucket 权限、签名下载/本地目录 |
| 简历解析提示「LLM 解析全部失败 / 占位数据」、`无可用渠道 (distributor)` | `JC_LLM_ENABLED=true` 且 `JC_LLM_API_KEY` 有效；在网关控制台确认 `routing.yaml` 里的模型 slug 已开通渠道。探测：`cd backend/server && set -a && source .env && set +a && JC_LLM_LIVE=1 PYTHONPATH=src pytest -q tests/test_llm_models_live.py` |
| LLM 返回异常 | 检查 `JC_LLM_ENABLED`、路由文件 `JC_LLM_ROUTING_PATH=../agent/llm/routing.yaml`、模型 slug、API key、Langfuse 错误 trace |
| Agent 无法调用能力 | 检查 `backend/agent/deerflow/config.yaml`、extensions 配置、skill 白名单和 `jc_*` tool 权限 |
| 前端请求 404/鉴权失败 | 检查 `/api/v1` 代理、cookie Secure/SameSite、Next 环境变量与登录态 |

## 7. 运行安全

不要为了排障临时开放通用浏览器、通用网络、宿主机文件系统或裸 SQL MCP。需要扩展能力时先按 [`../architecture/TECH-AGENT.md`](../architecture/TECH-AGENT.md) 的权限检查清单审查，再在隔离环境里验证。
