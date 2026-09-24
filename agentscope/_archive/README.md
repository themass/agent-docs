# 实现索引归档

本目录保存 **2026-09-08 之前** 的章节全文（路径表、源码 walkthrough、v0.x 历史、超长合并版）。

| 归档文件 | 行数级 | 替代阅读（设计导读） |
|----------|--------|----------------------|
| `ARCHITECTURE.md` | ~3150 | [ARCHITECTURE.md](../ARCHITECTURE.md) + 各专题文档 |

### 归档 `ARCHITECTURE.md` 里还有什么

- FLOW + PART1–3 完整合并（Agent 方法索引、Model 类图、Tool 源码级、v0.x MsgHub/A2A/Evaluate）
- 竞品对比、部署 Dockerfile 片段
- 与当前 main **部分过时** 的模块表（以导读 + 专题为准）

### 专题文档（已拆分出现有体系）

| 主题 | 文档 |
|------|------|
| App 服务 | [APP_ARCHITECTURE.md](../APP_ARCHITECTURE.md) |
| Memory | [MEMORY_SYSTEM.md](../MEMORY_SYSTEM.md) |
| Pipeline | [PIPELINE_AND_GOALS.md](../PIPELINE_AND_GOALS.md) |
| Workspace | [WORKSPACE_AND_SANDBOX.md](../WORKSPACE_AND_SANDBOX.md) |
| Middleware | [MIDDLEWARE_CATALOG.md](../MIDDLEWARE_CATALOG.md) |
| RAG | [RAG_AND_KNOWLEDGE.md](../RAG_AND_KNOWLEDGE.md) |

**查某个函数在哪个文件** → 用归档全文搜索。  
**理解框架为何这样设计** → 从 [ARCHITECTURE.md](../ARCHITECTURE.md) 导读开始，不要从归档开始。
