# OpenHuman 架构文档（中文）

> **版本**: 7.0 · 五文档体系 · 2026-09-04

## 文档地图

| 文档 | 读什么 |
|------|--------|
| **[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)** | **循序渐进导读**（~40min）：编排 vs harness、QueueMode、五本账 |
| **[diagrams/design-thinking-series.html](./diagrams/design-thinking-series.html)** | **浏览器图解速览**（可本地打开） |
| **[JSONL_TRANSCRIPT_GUIDE.md](./JSONL_TRANSCRIPT_GUIDE.md)** | 五本账、四层变换、QueueMode×账本矩阵 |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | **架构主文档** Part I：产品骨架、五本账、记忆双通路、多 Agent 三轨、长生命周期、tiny-* 映射；Part II：**仅** Memory/Plan/多 Agent 领域语义 |
| **[IMPLEMENTATION.md](./IMPLEMENTATION.md)** | **改代码图册**：QueueMode 五态、中间件全链、Agent 字段、RPC/Socket、委派、附录流程 |
| **[MODULES.md](./MODULES.md)** | **模块手册**（三合一）：分层流程 + `src/openhuman/` 域目录 + vendor `tiny-*` 对照 |
| **[PRODUCT.md](./PRODUCT.md)** | 陪伴产品用户视角：为什么、用户可感知行为 |
| **[OPENHUMAN_RUNTIME_PROMPTS.md](./OPENHUMAN_RUNTIME_PROMPTS.md)** | Prompt 中文全文 |

## 按任务找

| 我要… | 打开 |
|--------|------|
| 理解整体架构 / 五本账 | ARCHITECTURE Part I |
| 理解聊天/打断/Steer | IMPLEMENTATION §1 + ARCHITECTURE I.6 |
| 改中间件/审批/压缩 | IMPLEMENTATION §2 |
| 改 Agent 字段/工具可见性 | IMPLEMENTATION §3 |
| 对接前端 RPC/Socket | IMPLEMENTATION §4 |
| 改记忆注入/MEMORY.md | ARCHITECTURE Part II §4.1 |
| 改委派/Plan | ARCHITECTURE Part II §4.2–4.3 + IMPLEMENTATION §6 |
| 找某个目录/模块在哪 | MODULES 第二篇 |
| 对照 tiny-* 概念与源码 | MODULES 第三篇 |
| 产品叙事 / 用户旅程 | PRODUCT |

## 推荐阅读路径

```text
① DESIGN_THINKING_SERIES（循序渐进导读，~40min）
② ARCHITECTURE Part I（图表权威）
③ IMPLEMENTATION（改代码图册）
④ JSONL_TRANSCRIPT_GUIDE（五本账专题）
⑤ Part II / MODULES（按需）
```

## 旧文件名（跳转）

以下文件已合并，保留短 stub 避免外链断裂：

| 旧文件 | 新归宿 |
|--------|--------|
| `IMPLEMENTATION_REFERENCE.md` | [IMPLEMENTATION.md](./IMPLEMENTATION.md) |
| `MODULES_AND_FLOWS.md` | [MODULES.md](./MODULES.md) 第一篇 |
| `PACKAGE_MODULES.md` | [MODULES.md](./MODULES.md) 第二篇 |
| `sub_modle.md` | [MODULES.md](./MODULES.md) 第三篇 |
| `OpenHuman 长生命周期…md` | [PRODUCT.md](./PRODUCT.md) |
