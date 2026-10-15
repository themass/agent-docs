# JC

独立 Web 主动跳槽工作流项目。**本目录是项目根**；服务端工程在 `backend/server/`，前端在 `frontend/web/`，Agent assets 在 `backend/agent/`。

当前在 deepagents monorepo 的 `docs/myproject/job-come/`。Python **只借用仓库根 `../../../venv`**，不建 `job-come/.venv`。

## Start

```bash
cd docs/myproject/job-come
./scripts/setup-venv.sh
cp backend/server/.env.example backend/server/.env
./scripts/dev.sh
```

测试：`./scripts/test-local.sh`。完整脚本说明：[`scripts/README.md`](scripts/README.md)。

DeerFlow 上游在 **`../../../libs/agentkit/vendor/deer-flow/`**（不是 monorepo 根的 `deer-flow/`）。生产使用锁定源码和非 editable 安装，见 ADR-002。

## Architecture contracts

- 文档导航：[`docs/README.md`](docs/README.md)
- 系统与目录：[`docs/architecture/TECH-SYSTEM.md`](docs/architecture/TECH-SYSTEM.md)
- API 契约：[`docs/architecture/TECH-API.md`](docs/architecture/TECH-API.md)
- Agent 权限边界：[`docs/architecture/TECH-AGENT.md`](docs/architecture/TECH-AGENT.md)
- 开发/部署/测试：[`docs/operations/`](docs/operations/)
- 已接受决策：[`docs/decisions/`](docs/decisions/)
- 组织工程标准：[`docs/standards/PROJECT_STANDARD.md`](../../../docs/standards/PROJECT_STANDARD.md)
