# Harness 选型结论

更新时间：2026-10-12

## V1 决定

V1 继续使用已深度接入的 DeerFlow harness，不在上线前切换底座。切换 harness 会重新验证 skill 加载、MCP 工具、SSE 事件、checkpoint、取消、鉴权上下文和前端协议，不能增加当前用户闭环价值。

## 分层原则

- Service/API/MCP 负责确定性业务：身份归属、权限、确认 token、版本 CAS、状态机、题库写入、审稿失败闭环。
- Prompt/skill 负责表达和编排，不负责授权或最终一致性。
- Harness 只负责多轮对话、工具编排和流式事件。
- V1 关闭 subagent，并限制工具白名单；不暴露 shell、文件、浏览器或通用网络工具。

## 当前限制与后续

嵌入式 DeerFlow 的 MCP 配置和缓存存在进程级全局状态，因此当前 adapter 使用完整 run 串行锁和每轮缓存/环境清理。这适合 V1 内测低并发，不等于生产多租户隔离。生产上线前应采用进程/worker 隔离或上游支持的请求级配置，并增加并发、取消、重启恢复和租户泄露测试。

本轮没有拿到足够的一手资料完成市场 harness 横向基准，因此不把 LangGraph、OpenAI Agents SDK 或其他 harness 写成已验证优胜者。后续若并发、可观测性或长流程恢复成为瓶颈，再以同一业务契约做小规模替换评估。

## 2026-10-13 选型复核

| 方案 | 擅长点 | 对 JobCome V1 的代价 | 结论 |
|---|---|---|---|
| DeerFlow | 已接入的 Skill/MCP/SSE/会话链路，适合快速交付对话式工作流 | 当前嵌入式配置/cache 的进程级全局状态需要串行锁和隔离改造 | **V1 保留** |
| LangGraph | 官方文档强调 checkpointer、store、持久化、恢复和 human-in-the-loop，适合显式状态图 | 需要重做当前 DeerFlow adapter、事件协议、skill 载入和前端集成 | V2/生产隔离评估候选 |
| OpenAI Agents SDK | 官方提供 agents、tools、guardrails、handoffs、sessions、MCP 和 tracing，适合轻量 Python 编排 | 会引入新的模型/运行时约束；现有业务权限和 MCP 仍需自行保留 | 不在 V1 切换 |

这不是性能基准或生产可靠性认证，而是基于官方能力说明与当前代码迁移成本的决策。后续替换评估必须复用同一组业务契约：权限、确认 token、题库写入、审稿门禁、SSE 事件、取消和恢复。

参考的一手文档（2026-10-13 复核）：

- LangGraph Persistence：<https://docs.langchain.com/oss/python/langgraph/persistence>
- OpenAI Agents SDK：<https://openai.github.io/openai-agents-python/>
