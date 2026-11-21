# Poetry Agent Platform

> 诗词时空（奇境）的 Agent 平台与配套前端。事实、接口与数据在 `/Users/gqli/work/testserverV`（`vvv-poetry` 模块）；本仓库不取代它的事实权威。

## 目录：一个项目一个目录，每个项目只有 4 类东西

```text
poetry-agent-platform/
  README.md  Makefile  pyproject.toml  uv.lock
  scripts/                启动与运维脚本，按项目分子目录；共用路径变量在 lib.sh
  docs/                   平台工程文档（ADR、API、运行手册）
  content-agent/          内容生产项目
    frontend/             Poetry Studio（React + Vite）
    agent/                agent-bff · agent-worker · poetry-domain-mcp · agent-authoring · deerflow-profile
    pipeline/             场景流水线：contracts · scene-runtime · tools · dist(生成物)
    deploy/               compose.yaml · .env(不入库) · .env.example · k8s · upstream(DeerFlow 源码)
  student-app/            学生端项目
    frontend/             学生端页面
    agent/                学生端讲诗 agent
    runtime/              contracts · scene-runtime · platform-web
```

约定：

- 新增一个 agent = 新增一个同级项目目录，内部同样是 `frontend/` + `agent/` + 流水线/运行时 + `deploy/`；启动脚本放进 `scripts/<项目名>/`。
- 两个项目各带一份 `scene-runtime` 与 bundle 契约（不设共用层），`make check-copies` 防止两份悄悄不一致。
- 顶层目录白名单见 `scripts/maintenance/layout-allowlist.txt`，`make check-layout` 检查；新增顶层目录要先登记。
- 密钥只放 `content-agent/deploy/.env` 之类被 git 忽略的文件，仓库里只有 `.env.example`。

## 边界

- Agent 不直连 MySQL、不执行 SQL；
- Agent 不发布、撤回、确认出处、把来源设为 `VERIFIED`、删除内容，只能产出 DRAFT 候选；
- DeerFlow 不是内容事实真源，Java Poetry API 才是；
- 学生端不调用内容生产 agent、不读 DRAFT，只消费已发布并编译好的 Scene Bundle。

```text
Poetry Studio → agent-bff → DeerFlow Gateway → poetry-domain-mcp → Java Poetry API → MySQL poetry_*
Java Poetry API → Scene Compiler → Immutable Bundle → student-app（Web / Android / iOS）
```

## 日常入口

`make help` 列出全部目标。

| 目的 | 命令 |
|---|---|
| 内容生产：首次准备 | `make content-bootstrap` |
| 内容生产：启动 / 停止 / 日志 | `make content-up` / `content-down` / `content-logs` |
| 内容生产：连通检查 | `make content-smoke`（先启动） |
| 内容生产：校验 Soul / Skill / MCP 策略 | `make content-profile-check` |
| 学生端：本地预览 | `make student-dev` |
| 学生端：自检（无需数据库、无需网络） | `make student-verify` |
| 两份副本是否一致 | `make check-copies` |
| 目录布局是否合规 | `make check-layout` |
| 统一测试（开发期间不跑，最后一次性） | `make test-all` |
| 构建镜像 | `make build-images` |
| 数据库迁移 | `make migrate-agent-domain` / `migrate-agent-orchestration`（会写真实库，见下） |

本地编排不启动 MySQL 和 Java Poetry API，用 `content-agent/deploy/.env` 里的 `POETRY_API_BASE_URL` 接入。没有配置真实 Java API 时，MCP 的依赖调用显式返回 `DOMAIN_API_UNAVAILABLE`，不会伪造成功。

**数据库迁移脚本会修改真实库**，只在你明确要求时运行，不要放进任何自动流程。

部署细节见 [docs/deployment.md](docs/deployment.md)，API 见 [docs/api/agent-bff.md](docs/api/agent-bff.md)。

## 目录整理记录

回退依据：`../_archive/` 下的 `pre-*.tar.gz` 备份与 `restructure-*.py/sh` 脚本、`migration-manifest-*.txt`。
