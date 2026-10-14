# AgentScope v2 一页速查

> 完整导读与崩溃/持久化：**[AgentScopev2.md](./AgentScopev2.md)** · 文档地图：**[README.md](./README.md)**

| 问题 | 答案 |
|------|------|
| 核心循环 | 单 `Agent`，`reply_stream` = reasoning ↔ acting |
| 记忆在哪 | `AgentState.context` + `summary`（无 `MemoryBase`） |
| 多 Agent（库） | `GoalPipeline`（executor + verifier） |
| 多 Agent（生产） | `app` Team 工具 + inbox（≠ GoalPipeline） |
| HTTP / 飞书 | `create_app` → `ChatService.run` |
| 持久化真源 | `app/storage`（消息 upsert + `SessionRecord.state`） |
| 实时事件 | `MessageBus` replay + SSE（可丢，Storage 恢复） |
| RAG | `rag.KnowledgeBase` + `RAGMiddleware` |
| 旧名 | Harness/Session 快照/`memory/` → 见 [AgentScopev2 附录 A](./AgentScopev2.md#附录-a与-main-分支源码命名对照) |
