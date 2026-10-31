# ADR-002：生产使用预编译的 DeerFlow / AgentKit wheel

- **状态**：Accepted（2026-10-31 修订，取代 2026-10-15 原版）
- **日期**：2026-10-15，修订 2026-10-31

## Context

JC 的 Agent 工作流依赖 DeerFlow 的 Skill、MCP 和会话能力。原决策是：生产从
`libs/agentkit/vendor/deer-flow/` 的锁定源码以非 editable 方式安装，理由是构建可复现、
上游升级必须是显式动作。

理由成立，但实现方式错了。`backend/server/pyproject.toml` 把这几个包声明成
`{ path = "../../../../../libs/agentkit", editable = true }`，于是**部署机必须拥有整个
monorepo 源码树**（含 200MB+ 的 vendored DeerFlow）才能完成 `uv sync`：

```
uv sync → Distribution not found at: file:///.../libs/agentkit
```

这不是"可复现"的代价，而是把一个**构建期**输入当成了**运行期**依赖。项目因此无法作为
一个正常 Python 项目部署——而这正是实际部署时踩到的第一个坑。

## Decision

三个包在开发机上预编译成 wheel，**提交进仓库**，pyproject 从这些 wheel 取源：

```
backend/server/wheels/
  agentkit-0.1.0-py3-none-any.whl
  deerflow_harness-2.3.0.dev0-py3-none-any.whl
  deerflow_extension_api-0.2.9-py3-none-any.whl
```

```toml
[tool.uv.sources]
agentkit = { path = "wheels/agentkit-0.1.0-py3-none-any.whl" }
```

于是 `uv sync --frozen --no-dev --no-editable` 在任何只有这个项目目录的机器上都能装完，
不再依赖 `libs/`、不依赖目录深度、不需要 monorepo checkout。

wheel 进版本库（约 2.8MB）是刻意的：不进版本库，`uv.lock` 里那三条 `path = wheels/...`
在别的机器上就是悬空的。`backend/server/wheels/.gitignore` 默认 `*` 忽略一切，只放行
`*.whl`。

## Consequences

- **部署机不再需要源码树**，也不再有"必须 clone 到第几层目录"的隐性约束。
- **上游升级仍是显式动作**，而且现在有工具强制它显式：
  `./scripts/build-release.sh --update` 重新构建 wheel、改写版本 pin、重新 lock；
  `--check` 比对源码版本与 wheel 版本，不一致直接失败（`-dev` → `.dev0` 这类
  PEP 440 归一化已处理）。建议接进 CI，让"同步了上游但没重建 wheel"无法进发布。
- **陈旧 wheel 是这套方案唯一的静默故障**：装得上、import 得通，但跑的是旧代码。
  因此 `--update` 不是可选项——改过 vendored DeerFlow 或 agentkit 就必须跑。
- 二进制产物进 git 会让 diff 变大，但 2.8MB 的规模（其中 2.8MB 全在 harness）可以接受，
  换来的是部署路径与普通 Python 项目完全一致。
- V1 不因追求框架替换而延迟上线；替换评估条件见
  [`../discussions/DISCUSSION-HARNESS.md`](../discussions/DISCUSSION-HARNESS.md)。

## 关于"依赖最新版本"

上游 DeerFlow 与 LangGraph 都在持续发版，但"追新"要分清是哪一个：

- **DeerFlow**：vendor 目录本身带 `.git`，`scripts/sync-deerflow-upstream.sh` 可以
  fetch 并显示落后多少 commit。实测 2026-10-31 落后 10 个 commit / 不到 24 小时，
  9 个是 bugfix、1 个中等功能改动——不是"积压重大变更"。同步后必须重跑测试并
  `build-release.sh --update`。
- **LangGraph**：它是普通 PyPI 包，不是源码依赖。版本上限由 DeerFlow 自己的
  `pyproject.toml` 决定（`>=1.2.9,<1.3`）——上游尚未验证 1.3，JC 跟着这个上限走，
  在 1.2.x 线内取最新（当前 `1.2.19`，同步带动 `langgraph-checkpoint 4.3.1`、
  `langgraph-sdk 0.4.11`）。越过上游上限去追 1.3 属于自行承担未验证风险。
