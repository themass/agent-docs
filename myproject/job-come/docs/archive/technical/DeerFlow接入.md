# DeerFlow 接入（JC）

| 更新 | 2026-10-15 |
| 上游 | [bytedance/deer-flow](https://github.com/bytedance/deer-flow) |

## 源码位置（唯一）

```text
libs/agentkit/vendor/deer-flow/     ← JC 使用这份
deepagents/deer-flow/               ← 忽略，不参与 JC 构建
```

Path 依赖（`docs/myproject/job-come/backend/server/pyproject.toml`）：

```toml
deerflow-harness = { path = "../../../libs/agentkit/vendor/deer-flow/backend/packages/harness", editable = true }
deerflow-extension-api = { path = "../../../libs/agentkit/vendor/deer-flow/backend/packages/extension-api", editable = true }
```

## 线上部署策略（V1 固定）

**结论：线上采用“锁定的 vendored 源码 + 非 editable 安装”，而不是运行时下载或浮动依赖包。**

| 环境 | DeerFlow 形态 | 原因 |
|---|---|---|
| 本地开发 | `pyproject.toml` 的 editable path source | 修改 adapter / skill 接入时可快速验证 |
| CI / 生产 | 同一份 vendored 源码按 `uv.lock` 安装为非 editable wheel | 可复现、可审计，运行容器不依赖工作区热更新 |

生产构建必须满足：

1. 把 `libs/agentkit/vendor/deer-flow/` 连同指定 Git commit 一起纳入构建上下文；不得在构建时跟踪上游 `main` 或执行无版本约束的 `pip install deerflow...`。
2. 使用 `./scripts/install-production.sh`，其执行 `uv sync --frozen --no-dev --no-editable`；`uv.lock` 是唯一依赖版本依据。
3. 构建镜像/发布包时记录 DeerFlow vendor commit、`uv.lock` digest 与镜像 digest；升级先在 CI 跑完整 JC 回归。
4. 不修改 DeerFlow harness 核心来承载业务逻辑；JC 只通过 Adapter、Skill、MCP 与 Middleware 扩展。

这样“源码”是受控供应链输入，“依赖包”是部署产物：两者兼得，但线上不使用 editable path，也不接受未经验证的上游自动升级。

## 同步上游

```bash
cd docs/myproject/job-come
./scripts/sync-deerflow-upstream.sh
# 然后重装依赖
./scripts/setup-venv.sh
```

## 运行时状态与 Skills

- JC 以**同一个 API 进程**嵌入 `DeerFlowClient`；V1 不额外运行一个 DeerFlow 服务进程。
- 配置：`backend/agent/deerflow/config.yaml`、`backend/agent/deerflow/extensions_config.json`。
- 业务 Skill 的唯一源是 `backend/agent/skills/`，启动时通过 `DEER_FLOW_SKILLS_PATH` 显式传给 Harness。
- 所有 Harness 生成状态（Skill projection、线程和用户视图）固定写入 `JC_DEERFLOW_RUNTIME_HOME`，默认 `.data/deerflow/runtime/`。
- 项目根 `.deer-flow/` 是旧的本地生成缓存：**不作为 JC 的配置、Skill 或 inventory 输入**，也不会被新运行时读取。它可在所有旧本地运行停止后由开发者自行删除；不应搬到生产发布包。

## 独立部署时

带走整个 `docs/myproject/job-come/`（含 `backend/server/` 与 `backend/agent/`）+ `libs/agentkit/`（含 `vendor/deer-flow`），或改为 git submodule / 私有镜像。当前 `pyproject.toml` 假定两者相隔三级目录（`../../../libs/agentkit`）；拆仓时必须同步调整该相对路径与锁文件。

## 硬边界

- 不用 `deer-flow/app/channels`（IM）
- 业务写库只走 `jc_*` MCP
