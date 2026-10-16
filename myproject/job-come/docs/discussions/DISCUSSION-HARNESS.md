# DISCUSSION-HARNESS：Agent Harness 选型

- **状态**：V1 已决策；后续替换仍待证据驱动评估
- **最后更新**：2026-10-15

## 当前决定

V1 继续使用 **DeerFlow**，以 vendored 源码、受限 skill/MCP 和嵌入式服务端集成为基础。选择原因是现有会话、Skill、MCP、SSE 与业务权限链路已接入，继续替换会扩大 V1 发布风险。

## 不变的分层原则

Harness 只负责 Agent 循环和工具调度；身份、资源归属、档案确认、数据写入、网络边界、审计与业务规则仍由 JC 服务端控制。任何 Harness 都不能绕开 `jc_*` 工具和服务层。

## 未来评估触发条件

只有出现下列明确问题，才启动替换/并行 PoC：

- 多用户并发下的隔离、进程级状态或 checkpoint 恢复成为可复现瓶颈；
- 长工作流的持久化、人审、重试与可观测性无法以合理代价补足；
- 运行成本、延迟或运维复杂度无法满足上线指标。

候选方向：LangGraph（显式状态和持久化）与 OpenAI Agents SDK（轻量 Agent、tools、guardrails、sessions、MCP、tracing）。它们均不是 V1 切换事项；比较需基于同一权限边界、同一测试集和真实成本数据。
