# 🚀 架构文档快速参考

## 📂 文档位置

| 项目 | PART1 (已完成) | README |
|------|---------------|--------|
| **Software Agent SDK** | [`software-agent-sdk/docs/ARCHITECTURE_PART1.md`](file:///Users/gqli/work/deepagents/software-agent-sdk/docs/ARCHITECTURE_PART1.md) | [`software-agent-sdk/docs/README.md`](file:///Users/gqli/work/deepagents/software-agent-sdk/docs/README.md) |
| **OpenHands** | [`OpenHands/docs/ARCHITECTURE_PART1.md`](file:///Users/gqli/work/deepagents/OpenHands/docs/ARCHITECTURE_PART1.md) | [`OpenHands/docs/README.md`](file:///Users/gqli/work/deepagents/OpenHands/docs/README.md) |
| **AgentScope** | [`agentscope/docs/ARCHITECTURE_PART1.md`](file:///Users/gqli/work/deepagents/agentscope/docs/ARCHITECTURE_PART1.md) | [`agentscope/docs/README.md`](file:///Users/gqli/work/deepagents/agentscope/docs/README.md) |
| **AgentMemory** | [`agentmemory/docs/ARCHITECTURE_PART1.md`](file:///Users/gqli/work/deepagents/agentmemory/docs/ARCHITECTURE_PART1.md) | [`agentmemory/docs/README.md`](file:///Users/gqli/work/deepagents/agentmemory/docs/README.md) |

---

## 🎯 核心内容速览

### Software Agent SDK PART1

#### 第1章: 项目概览
- **定位**: 企业级 Agent 开发框架
- **核心功能**: 本地/远程对话、插件系统、安全机制
- **架构图**: 5个组件关系图 + 数据流程序列图

#### 第2章: Agent 核心
- **关键机制**: 延迟初始化（首次 run() 时加载工具）
- **性能优化**: ThreadPoolExecutor 并行解析工具
- **源码位置**: `openhands/sdk/agent/base.py:506-550`

#### 第3章: Conversation
- **执行流程**: run() → _step() → LLM → Tool → Observation
- **确认模式**: Confirmation Policy（Always/Never/Selective）
- **Forking**: 深拷贝对话，支持分支实验
- **源码位置**: `openhands/sdk/conversation/impl/local_conversation.py:746-850`

#### 第4章: Tool 系统
- **内置工具**: Bash、File Editor、Grep
- **自定义工具**: 继承 Tool 类，实现 executor
- **安全机制**: Security Analyzer + Confirmation Mode
- **源码位置**: `openhands/tools/terminal/bash.py`

---

### OpenHands PART1

#### 第1章: 项目概览
- **定位**: 开源 AI Agent 平台
- **架构**: 双服务器（App Server + Agent Server）
- **前端**: React + TypeScript
- **架构图**: 完整数据流程序列图

#### 第2章: App Server
- **技术栈**: FastAPI + PostgreSQL + Redis
- **核心路由**: conversation、sandbox、event、webhook
- **Sandbox 策略**: Grouped（共享）vs Isolated（隔离）
- **源码位置**: `openhands/app_server/app_conversation/live_status_app_conversation_service.py:1216-1540`

#### 第3章: Agent Runtime
- **Agent Server**: FastAPI + SDK LocalConversation
- **事件流**: Server-Sent Events（SSE）
- **持久化**: FileEventStore（JSON 文件）
- **源码位置**: `openhands-agent-server/openhands/agent_server/conversation_router.py`

#### 第4章: Sandbox
- **类型**: Docker、Apptainer、Remote API、Cloud
- **Docker 实现**: 拉取镜像 → 启动容器 → 健康检查
- **环境变量**: 自动转发 LLM_*/LMNR_* 前缀
- **安全机制**: 网络隔离、资源限制、文件系统只读
- **源码位置**: `openhands-workspace/openhands/workspace/docker/`

---

### AgentScope PART1

#### 第1章: 项目概览
- **定位**: 阿里巴巴多智能体开发框架
- **核心功能**: ReAct Agent、Multi-Agent Pipeline、Long-term Memory
- **架构图**: 组件关系图 + 数据流程序列图

#### 第2章: Agent 核心
- **ReActAgent**: 推理-行动循环（max_iters 控制）
- **RealtimeAgent**: WebSocket 流式音频/视频
- **UserAgent**: 人类用户代理（多智能体对话）
- **源码位置**: `src/agentscope/agent/_react_agent.py`

#### 第3章: Pipeline 编排
- **MsgHub**: 消息中心，广播机制
- **ChatRoom**: 动态加入/退出的聊天室
- **SequentialPipeline**: 顺序执行（规划 → 执行 → 审核）
- **ParallelPipeline**: 并行执行（投票、多样性生成）
- **源码位置**: `src/agentscope/pipeline/_msghub.py`

#### 第4章: Memory 系统
- **WorkingMemory**: 短期记忆（FIFO 淘汰）
- **LongTermMemory**: 长期记忆（向量检索）
- **CompressionMemory**: LLM 摘要压缩
- **支持的向量数据库**: FAISS、Chroma、Tablestore、Milvus
- **源码位置**: `src/agentscope/memory/_working_memory/`

---

### AgentMemory PART1

#### 第1章: 项目概览
- **定位**: 智能体长期记忆系统
- **核心功能**: 自动捕获、混合检索、记忆整合
- **架构图**: 完整数据流程序列图

#### 第2章: Memory 核心
- **Memory Store**: SQLite 数据库（raw_memories、consolidated_memories、lessons）
- **Hooks 系统**: Session Start/Prompt Submit/Tool Use/Session End
- **捕获策略**: 重要性评分算法（长度、代码块、文件路径等）
- **源码位置**: `src/state/memory-store.ts`

#### 第3章: Search & Retrieval
- **Hybrid Search**: BM25 + Vector 加权融合
- **BM25 Index**: FlexSearch 关键词检索
- **Vector Index**: 多种 Embedding 模型（Xenova、OpenAI、Cohere）
- **Recall MCP 工具**: recall/remember/forget
- **源码位置**: `src/functions/smart-search.ts`

#### 第4章: Consolidation
- **Pipeline**: 聚类 → 摘要 → 模式识别
- **聚类算法**: 层次聚类（AGNES）
- **摘要生成**: LLM 自动化总结
- **模式识别**: 经验教训提取
- **调度任务**: Cron 定时 + 会话结束触发
- **源码位置**: `src/functions/consolidate.ts`

---

## 🔍 快速查找

### 想找某个功能的实现？

| 功能 | Software Agent SDK | OpenHands |
|------|-------------------|-----------|
| **Agent 初始化** | PART1 第2章 | PART1 第3章 |
| **对话执行** | PART1 第3章 | PART1 第3章 |
| **工具执行** | PART1 第4章 | PART1 第3章 |
| **事件持久化** | PART1 第3章 | PART1 第3章 |
| **沙箱管理** | - | PART1 第4章 |
| **Webhook** | - | PART1 第2章 |
| **安全机制** | PART1 第4章 | PART1 第4章 |

---

## 💡 关键洞察对比

| 维度 | Software Agent SDK | OpenHands |
|------|-------------------|-----------|
| **架构风格** | 单体库（SDK） | 微服务（双服务器） |
| **执行环境** | 本地进程或远程 HTTP | Docker 沙箱隔离 |
| **适用场景** | 嵌入式集成、CLI 工具 | Web 平台、多租户 SaaS |
| **扩展方式** | Plugin 系统（Skills/MCP/Hooks） | Integrations（Git/Jira/Slack） |
| **安全模型** | Confirmation + Security Analyzer | Sandbox 隔离 + 资源限制 |

---

## 📊 统计数据

| 指标 | Software Agent SDK | OpenHands | AgentScope | AgentMemory | 总计 |
|------|-------------------|-----------|------------|-------------|-------|
| **文档行数** | 774 | 764 | 813 | 1,108 | 3,459 |
| **章节数** | 4 | 4 | 4 | 4 | 16 |
| **Mermaid 图表** | 5 | 5 | 5 | 6 | 21 |
| **代码示例** | 15+ | 12+ | 14+ | 16+ | 57+ |
| **源码标注** | 10+ 处 | 10+ 处 | 10+ 处 | 12+ 处 | 42+ 处 |

---

## 🎓 阅读建议

### 如果你想学习 Agent 开发
1. 先读 **Software Agent SDK PART1** - 理解核心概念
2. 重点关注第2章（Agent）和第4章（Tool）
3. 尝试运行代码示例

### 如果你想部署生产环境
1. 先读 **OpenHands PART1** - 理解架构设计
2. 重点关注第2章（App Server）和第4章（Sandbox）
3. 参考官方部署文档

### 如果你想贡献代码
1. 两个项目的 PART1 都要读
2. 查看源码标注的位置
3. 理解设计决策的原因

---

## 🔗 相关链接

- **完整报告**: [`ARCHITECTURE_ANALYSIS_REPORT.md`](file:///Users/gqli/work/deepagents/ARCHITECTURE_ANALYSIS_REPORT.md)
- **OpenAI Agents SDK 文档**: `/Users/gqli/work/deepagents/openai-agents-python/docs/`
- **官方文档**: 
  - Software Agent SDK: https://docs.all-hands.dev/modules/sdk/
  - OpenHands: https://docs.all-hands.dev/

---

**最后更新**: 2026-05-17  
**文档版本**: 1.0
