# DeerFlow 接入（JobCome）

| 更新 | 2026-09-04 |
| 上游 | [bytedance/deer-flow](https://github.com/bytedance/deer-flow) |

## 源码位置（唯一）

```text
libs/agentkit/vendor/deer-flow/     ← JobCome 使用这份
deepagents/deer-flow/               ← 忽略，不参与 JobCome 构建
```

Path 依赖（`job-come/pyproject.toml`）：

```toml
deerflow-harness = { path = "../libs/agentkit/vendor/deer-flow/backend/packages/harness", editable = true }
deerflow-extension-api = { path = "../libs/agentkit/vendor/deer-flow/backend/packages/extension-api", editable = true }
```

## 同步上游

```bash
job-come/scripts/sync-deerflow-upstream.sh
# 然后重装依赖
job-come/scripts/setup-venv.sh
```

## 运行时

- 默认 `JOB_COME_DEERFLOW_BACKEND=harness`（嵌入 `DeerFlowClient`）
- 配置：`deploy/deerflow/config.yaml`、`extensions_config.json`
- Skills：`job-come/skills/`

## 独立部署时

带走整个 `job-come/` + `libs/agentkit/`（含 `vendor/deer-flow`），或改为 git submodule / 私有镜像。`pyproject.toml` 路径相对 monorepo 布局；拆仓后把 `../libs/agentkit` 放在同级目录即可。

## 硬边界

- 不用 `deer-flow/app/channels`（IM）
- 业务写库只走 `jobcome_*` MCP
