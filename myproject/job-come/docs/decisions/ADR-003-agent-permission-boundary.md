# ADR-003：Agent 采用最小权限工具边界与人工确认

- **状态**：Accepted
- **日期**：2026-10-15

## Context

JC Agent 会接触用户职业档案、职位信息、面试记录和导出物。泛化的浏览器、网络、文件系统或数据库能力会放大数据泄露、提示注入和越权修改风险。

## Decision

- 不向 Agent 开放通用浏览器、通用网络、任意宿主机文件系统或裸 SQL。
- 仅开放经服务端身份、资源归属、输入校验和审计保护的 `jc_*` 工具。
- 任何档案事实 patch 均须用户明确确认；模型不得自行确认。
- 公开 JD 读取仅通过任务专用的 `jc_job_fetch`，并执行 DNS/IP、私网、重定向、方法、大小和超时限制。

## Consequences

- 功能扩展需先设计窄工具，不能以“方便”为由暴露泛化能力。
- 第三方 Skill/MCP 必须通过准入审查，见 [`../discussions/DISCUSSION-INTEGRATIONS.md`](../discussions/DISCUSSION-INTEGRATIONS.md)。
- 实时会议辅助进入下一个版本前需要专门完成授权、隐私、合规和音频安全评审。
