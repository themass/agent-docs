# OpenAI Agents SDK 架构文档 PART2 - 阅读指南

## 📚 文档结构

PART2 文档分为两个文件：

### 1. **主文档** - `OPENAI_AGENTS_SDK_ARCHITECTURE_PART2.md`
- ✅ **第7章** - Session 持久化与会话管理（深度分析）
- 🔗 **第8-12章** - 快速导航链接（指向补充文档）

### 2. **补充文档** - `PART2_CHAPTERS_8-12.md`
- ✅ **第8章** - Guardrails 护栏系统
- ✅ **第9章** - Tracing 追踪与监控
- ✅ **第10章** - Sandbox 沙箱环境
- ✅ **第11章** - 扩展能力
- ✅ **第12章** - 最佳实践与设计模式

---

## 🎯 为什么分成两个文件？

1. **文件大小优化** - 第7章的 Session 分析非常详细（~750行），单独存放便于维护
2. **模块化设计** - 第8-12章相对独立，可以单独更新
3. **加载性能** - 避免单个文件过大导致编辑器卡顿

---

## 📖 推荐阅读顺序

### 方案A：完整阅读
1. 先读 `OPENAI_AGENTS_SDK_ARCHITECTURE_PART2.md`（第7章）
2. 再读 `PART2_CHAPTERS_8-12.md`（第8-12章）

### 方案B：按需阅读
- **关注会话管理** → 只读第7章
- **关注安全护栏** → 直接跳到第8章
- **关注沙箱隔离** → 直接跳到第10章
- **关注最佳实践** → 直接跳到第12章

---

## 🔗 相关文档

- **PART1** - Agent 核心、Tools、Handoffs（待创建）
- **PART2** - Session、Guardrails、Tracing、Sandbox（本文档）
- **PART3** - 多 Agent 协作、RunItem 类型系统、Agent Loop（已存在）

---

## 📝 章节概览

### 第7章：Session 持久化与会话管理
- ✅ RunItem → TResponseInputItem 转换机制
- ✅ save_result_to_session() 完整流程
- ✅ prepare_input_with_session() 完整流程
- ✅ Session vs Rollout vs Memory 对比
- ✅ 会话分支、压缩、自定义回调

### 第8章：Guardrails 护栏系统
- ✅ Input/Output/Tool Guardrails
- ✅ 并行/串行执行策略
- ✅ Tripwire 触发机制
- ✅ 与 Session 的交互

### 第9章：Tracing 追踪与监控
- ✅ Span 类型系统
- ✅ ContextVar 上下文管理
- ✅ Trace 导出器（Console、OTLP）
- ✅ 性能监控示例

### 第10章：Sandbox 沙箱环境
- ✅ Docker/E2B/Vercel/Local 后端
- ✅ Capabilities 能力系统
- ✅ Workspace 持久化（TAR/Snapshot）
- ✅ 安全隔离机制

### 第11章：扩展能力
- ✅ Hook 系统（生命周期回调）
- ✅ Model 适配器
- ✅ 自定义存储后端
- ✅ 自定义 Guardrail/Exporter

### 第12章：最佳实践与设计模式
- ✅ Agent 设计原则（单一职责、防御性编程）
- ✅ Session 管理最佳实践
- ✅ Error Handling 策略
- ✅ Performance Optimization
- ✅ Testing 最佳实践
- ✅ Security Checklist

---

## 💡 使用建议

1. **代码示例** - 所有章节都包含完整的代码示例，可以直接复制使用
2. **源码引用** - 所有结论都基于真实源码分析，标注了具体文件和行号
3. **Mermaid 图表** - 关键流程都有可视化图表
4. **对比表格** - 重要概念都有对比说明

---

## 🐛 问题反馈

如果发现文档错误或需要补充内容，请：
1. 检查对应的源码文件
2. 提交 Issue 或 PR
3. 注明具体的章节和行号

---

**最后更新**: 2026-05-17  
**维护者**: Deep Agents Team
