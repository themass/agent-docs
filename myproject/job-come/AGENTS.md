# JobCome

独立 Web 求职工作流项目。**本目录即项目根**（`pyproject.toml`、`.env`、`apps/web` 均在此）。当前在 deepagents monorepo 里开发时，**只借用上级 `../venv` 的 Python**，不建 `job-come/.venv`。

## 一次性环境

```bash
cd job-come
./scripts/setup-venv.sh      # 依赖装进 ../venv（Python 3.12）
cp .env.example .env           # MySQL / Redis / YUAI_API_KEY
```

DeerFlow 上游在 **`../libs/agentkit/vendor/deer-flow/`**（不是 monorepo 根的 `deer-flow/`）。首次缺失时见 `libs/agentkit/vendor/README.md`。

## 启动

```bash
cd job-come
set -a && source .env && set +a
../venv/bin/uvicorn jobcome.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd apps/web && npm install && npm run dev   # :3000 → API 反代 :8000
```

测试：`../venv/bin/pytest -q`（在 `job-come/` 目录）

VS Code / Cursor 解释器：`../venv/bin/python`

## 硬标准

- 组织工程标准：[`docs/standards/PROJECT_STANDARD.md`](../docs/standards/PROJECT_STANDARD.md)
- AgentKit：[`../libs/agentkit/`](../libs/agentkit/)
- DeerFlow 接入：[`docs/DeerFlow接入.md`](docs/DeerFlow接入.md)
- 运行手册：[`docs/RUNBOOK.md`](docs/RUNBOOK.md)
