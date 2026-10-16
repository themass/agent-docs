# ADR-002：生产使用锁定的 vendored DeerFlow 源码

- **状态**：Accepted
- **日期**：2026-10-15

## Context

JC 的 Agent 工作流依赖 DeerFlow 的 Skill、MCP 和会话能力。直接依赖浮动远程包版本会造成构建不可重现，也不利于审查上游变更。

## Decision

使用 `/Users/gqli/work/deepagents/libs/agentkit/vendor/deer-flow/` 中锁定的源码，并以非 editable 方式安装：

```bash
uv sync --frozen --no-dev --no-editable
```

业务配置、prompt 与 skill 保持在 JC 的 `backend/agent/`，不修改业务逻辑来适配上游目录。

## Consequences

- 生产构建可复现，上游升级成为显式维护动作。
- 需通过 `scripts/sync-deerflow-upstream.sh` 审查、测试并记录上游同步。
- V1 不因追求框架替换而延迟上线；替换评估条件见 [`../discussions/DISCUSSION-HARNESS.md`](../discussions/DISCUSSION-HARNESS.md)。
