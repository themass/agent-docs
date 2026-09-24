# OpenHands 架构文档

> **分析时间**: 2026-05-17  
> **分析方法**: 源码深度阅读 + 架构图可视化  
> **维护者**: Deep Agents Team

---

## 📚 文档列表

### ✅ AGENT_SERVER.md（Agent Server 设计实现）
**`openhands-agent-server` 专篇**：ConversationService、EventService、路由、WebSocket、持久化、deferred init、租约与 run 路径。

---

### ✅ APPLICATION_LAYER.md（V1 应用层）
**SDK 之上的 OpenHands 封装**（Agent Server + React + 可选 App Server/Cloud）

- 分层图：表现层 → 编排层 → Agent Server → SDK
- `ConversationService` / `EventService` 职责
- `agent-server-adapter` 如何组装 `StartConversationRequest`
- 本地直连 vs Cloud 双路径
- 与 V0 Controller/agenthub 对照

建议：**读完 ENTITY_MODEL §11 后读本文**，再深入 PART1/PART2。

---

### ✅ ARCHITECTURE_PART1.md (已完成)
**核心架构与基础组件**

- 第1章: 项目概览与核心架构
  - 双服务器架构（App Server + Agent Server）
  - 数据流转全景图
  - 关键组件关系
  
- 第2章: App Server 架构
  - FastAPI 路由结构
  - 会话创建流程
  - Sandbox 生命周期管理
  - Webhook 处理机制
  - 用户与组织管理
  
- 第3章: Agent Runtime 系统
  - Agent Server 入口
  - 对话路由
  - 工具执行服务
  - 事件持久化与重放
  
- 第4章: Sandbox 沙箱管理
  - Sandbox 类型系统（Docker/Apptainer/Remote/Cloud）
  - Docker Sandbox 实现
  - 环境变量注入
  - Workspace 持久化
  - Sandbox 安全机制

**关键洞察**:
1. ✅ **双服务器架构** - App Server 负责编排，Agent Server 负责执行
2. ✅ **Sandbox 隔离** - Docker/Apptainer 提供安全执行环境
3. ✅ **事件驱动** - Webhook + WebSocket 实现实时更新
4. ✅ **灵活扩展** - 支持多种 Sandbox 类型和部署策略

---

### 📄 ARCHITECTURE_PART2.md (待创建)
**Event 处理、Integrations、Analytics**

计划内容:
- 第5章: Event 处理系统
- 第6章: Integrations 集成
- 第7章: Analytics 分析系统

---

### 📄 ARCHITECTURE_PART3.md (待创建)
**Enterprise 功能、Deployment、Advanced Topics**

计划内容:
- 第8章: Enterprise 功能
- 第9章: Deployment 部署
- 第10章: Advanced Topics

---

## 🎯 快速开始

### 阅读顺序
1. **先读 PART1** - 理解核心架构
2. **再读 PART2** - 掌握事件处理和集成
3. **最后读 PART3** - 了解企业功能和部署

### 查找信息
- 📍 **源码位置** - 每个章节都标注了文件和行号
- 💻 **代码示例** - 实际可运行的代码片段
- 📊 **架构图** - Mermaid 可视化图表

---

## 🔗 相关链接

- **官方文档**: https://docs.all-hands.dev/
- **GitHub**: /Users/gqli/work/deepagents/OpenHands
- **Software Agent SDK 文档**: ../software-agent-sdk/docs/

---

**最后更新**: 2026-05-17  
**文档状态**: PART1 已完成
