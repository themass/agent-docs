# TanStack AI 开源项目架构文档

> 本目录按本地源码快照整理，重点说明模块边界、运行时调用链、流协议、状态归属和扩展入口，不替代项目自带的使用文档与 API Reference。
>
> **源码位置**：`../ai`（相对本目录为 `../../ai`）
> **仓库提交**：`6aebc8fa987e6283113ddcd0664dce9a6b975f28`
> **核心包版本**：`@tanstack/ai 0.67.0`
> **提交日期 / 整理日期**：2026-10-09 / 2026-10-10
>
> 这是固定提交的源码分析，不代表 2026-10-10 之后的仓库状态。讨论行为时以这个提交的实现和测试为准。

## 文档目录

| 文档 | 解决的问题 |
|---|---|
| [01-系统架构总览.md](./01-系统架构总览.md) | TanStack AI 的定位、分层、主链路和核心概念边界 |
| [02-仓库与包地图.md](./02-仓库与包地图.md) | pnpm/Nx monorepo 结构、包族、源码导航与依赖方向 |
| [03-Chat运行时与中间件.md](./03-Chat运行时与中间件.md) | `chat()` 如何把输入、模型流、工具循环和 middleware 串起来 |
| [04-消息协议与传输.md](./04-消息协议与传输.md) | `StreamChunk`、AG-UI 事件、SSE/HTTP/WebSocket 和恢复语义 |
| [05-工具中断与Agent组合.md](./05-工具中断与Agent组合.md) | 工具执行位置、审批/通用中断、MCP、子 Agent、Code Mode 与沙箱 |
| [06-客户端与框架集成.md](./06-客户端与框架集成.md) | `ChatClient`、消息状态、连接适配器、框架 Hook 和客户端持久化 |
| [07-Provider与多模态活动.md](./07-Provider与多模态活动.md) | Adapter 契约、类型安全来源、模型能力、多模态活动与 BYOK |
| [08-持久化记忆与可观测性.md](./08-持久化记忆与可观测性.md) | Transcript 持久化、流交付恢复、Memory、Compaction、Devtools 和 OTel 的分工 |
| [09-测试发布与变更指南.md](./09-测试发布与变更指南.md) | 测试分层、构建/发布流程、常见改动的源码落点与风险 |
| [10-源码索引与场景决策.md](./10-源码索引与场景决策.md) | 按问题定位入口文件，避免跨层乱改 |

## 一句话定位

TanStack AI 是一个 **TypeScript AI 应用 SDK 与 monorepo**：核心包把模型厂商的协议适配成统一的活动接口和 AG-UI 流事件；客户端用同一套事件驱动无头状态机，再由 React、Vue、Solid、Svelte、Preact、Angular 等绑定接入各自 UI。

它不是一个必须使用的 UI 组件库，也不是只封装单一模型 API 的 HTTP 客户端。它把模型适配、Agentic 工具循环、流协议、客户端状态和可选能力拆为可组合的包。

```mermaid
flowchart LR
  UI[React / Vue / Solid / Svelte / Preact / Angular / Headless] --> C[ChatClient]
  C --> T[Connection Adapter\nSSE / HTTP / JSON / WS / RPC / in-process]
  T --> R[应用服务端路由]
  R --> E[chat() / TextEngine]
  E --> M[Middleware chain]
  E --> A[Provider TextAdapter]
  A --> P[Provider SDK / HTTP API]
  E --> O[AG-UI StreamChunk]
  O --> T
  O --> C
  C --> UI
  E -. 可选 .-> S[(Persistence stores)]
  T -. 可选 .-> D[(Stream durability)]
  E -. 可选 .-> X[Tools / MCP / Subagents]
```

## 先建立这五个边界

1. **Activity 与 Adapter 不同**：`chat()`、`embed()`、`generateImage()` 是面向应用的统一活动；OpenAI、Anthropic 等 Adapter 承担供应商协议差异。
2. **模型流与应用流不同**：Provider Adapter 产生内部 `AdapterYieldChunk`；`chat()` 正规化后输出对外的 `StreamChunk`（AG-UI 事件）。客户端只需处理后者。
3. **消息与事件不同**：`ModelMessage` / `UIMessage` 表示对话快照；`StreamChunk` 表示一次运行中的增量事件。持久化和 UI 消费两者的方式也不同。
4. **状态持久化与流恢复不同**：`@tanstack/ai-persistence` 保存对话、Run、Interrupt 等业务状态；`StreamDurability` 保存/重放事件交付。一个不能自动替代另一个。
5. **Agent 能力是可选组合**：基础 `chat()` 可以只生成文字；Tools、Middleware、MCP、Memory、Subagents、Code Mode 和 Sandbox 按需组合。

## 推荐阅读顺序

1. 先读 [01-系统架构总览](./01-系统架构总览.md)，建立所有权和边界。
2. 再读 [03-Chat运行时](./03-Chat运行时与中间件.md) 与 [04-消息协议](./04-消息协议与传输.md)，理解主请求路径。
3. 按需求读 [05-工具和Agent组合](./05-工具中断与Agent组合.md)、[06-客户端](./06-客户端与框架集成.md)、[08-状态与持久化](./08-持久化记忆与可观测性.md)。
4. 要改代码时查 [02-包地图](./02-仓库与包地图.md) 和 [09-变更指南](./09-测试发布与变更指南.md)。
5. 需要按场景定位文件时查 [10-源码索引与场景决策](./10-源码索引与场景决策.md)。
6. 要核实某个具体 API 时回到源码仓库的 [`ai/docs`](../../ai/docs/) 和 [`ai/packages`](../../ai/packages/)。

## 源码入口

- 核心公共导出：[`packages/ai/src/index.ts`](../../ai/packages/ai/src/index.ts)
- Chat 类型与运行时：[`packages/ai/src/activities/chat/`](../../ai/packages/ai/src/activities/chat/)
- 对外事件与公共类型：[`packages/ai/src/types.ts`](../../ai/packages/ai/src/types.ts)
- 编码/恢复传输：[`packages/ai/src/stream-to-response.ts`](../../ai/packages/ai/src/stream-to-response.ts)、[`stream-to-websocket.ts`](../../ai/packages/ai/src/stream-to-websocket.ts)
- 无头客户端：[`packages/ai-client/src/`](../../ai/packages/ai-client/src/)
- Provider adapters：[`packages/ai-openai/src/`](../../ai/packages/ai-openai/src/) 等 `packages/ai-*`
- 本地开发规范：[`AGENTS.md`](../../ai/AGENTS.md)、[`CONTRIBUTING.md`](../../ai/CONTRIBUTING.md)

---

下一步：从 [01-系统架构总览](./01-系统架构总览.md) 开始，沿图追一遍服务端到客户端的主链路。
