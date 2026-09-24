# JobCome 运行手册（RUNBOOK）

JobCome 以 **本目录为项目根**；在 deepagents monorepo 内开发时 Python 用 **`../venv`**（见 `scripts/setup-venv.sh`）。

## 1. 环境准备

| 步骤 | 说明 |
|------|------|
| Python 3.12 | `deerflow-harness` 要求 |
| `./scripts/setup-venv.sh` | 把依赖装进 `deepagents/venv` |
| `cp .env.example .env` | MySQL、Redis、`YUAI_API_KEY` |
| DeerFlow 源码 | `../libs/agentkit/vendor/deer-flow/`（脚本可同步上游） |

```bash
cd job-come
./scripts/setup-venv.sh
cp .env.example .env
```

同步 DeerFlow：`./scripts/sync-deerflow-upstream.sh`

## 2. 启动

**后端**

```bash
set -a && source .env && set +a
../venv/bin/uvicorn jobcome.main:app --reload --host 0.0.0.0 --port 8000
```

**前端**

```bash
cd apps/web
npm install
npm run dev   # http://localhost:3000
```

确认：`curl http://127.0.0.1:8000/health` → `{"status":"ok"}`

## 3. LLM（litellm 库，非独立进程）

```bash
JOB_COME_LLM_ENABLED=true
YUAI_API_BASE=https://newapi.yuaiweiwu.com/v1
YUAI_API_KEY=<your-key>
JOB_COME_LLM_ROUTING_PATH=deploy/llm/routing.yaml
```

## 4. E2E

```bash
../venv/bin/pytest tests/test_regression_fixtures.py tests/test_export_pdf.py tests/test_e2e_openapi_routes.py -q
# 或：./scripts/ci_regression.sh
```

**数据库迁移**

```bash
./scripts/db_upgrade.sh
```

**Agent E2E**（需登录账号 + LLM Key）

```bash
export JOB_COME_E2E_EMAIL=... JOB_COME_E2E_PASSWORD=...
./scripts/agent_e2e.sh
```

**导出冒烟**

```bash
./scripts/export_smoke.sh
```

**Langfuse**（可选）：在 `.env` 配置 `LANGFUSE_*`，API 启动时自动注册 LiteLLM callback。

## 5. 相关文档

- [DeerFlow接入.md](./DeerFlow接入.md)
- [DEPLOY.md](./DEPLOY.md)
