# NaviForge 架构优化清单

> **状态**：优化 backlog（基于 2026-08-16 架构审查；**2026-08-17 与代码同步**）  
> **读者**：Runtime / Extension 维护者、做结构重构前必读  
> **对照基线**：Pi、`hermes-dev/hermes-agent`、OpenHarness、MAF（Microsoft Agent Framework）  
> **叙事权威**：当前实现仍以 [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md) 为准  
> **执行勾选**：[OPTIMIZATION_PLAN.md](./OPTIMIZATION_PLAN.md) O-01～O-20（排期与验收以该文为准）

---

## 0. 如何使用本文

| 你的任务 | 建议阅读 |
|----------|----------|
| 排期一个季度内的结构刀 | §12 优先级路线图 |
| 改工具 / exec-turn | §2.1、§4.1 |
| 改侧栏 / 会话存储 | §2.4、§4.2、§5 |
| 删兼容层 | §6 兼容退役计划 |
| 确认「该不该拆新 package」 | §3.3、§12「明确不做」 |

**评级**：P0 = 应尽快做（维护成本 / 用户可见风险）；P1 = 高 ROI；P2 = 产品边界变长后再做。

---

## 1. 审查结论摘要

### 1.1 已对齐成熟框架的部分（保留，勿为「对齐」而推翻）

- **Plane 六边形**：`runtime` 不碰 Chrome API；DOM / Network 实现在 `extension`。
- **审计 ≠ 工作集**：`TraceRecord` 全量保留；`RunLedger` + `selectWorkingSet` 喂模型（Pi compaction / Hermes Compressor 同方向）。
- **运行中队列**：steer / followUp / HITL（Pi steer 同款）。
- **跨 Run 记忆**：`ThreadMemorySlots`（Hermes slots 同类）。
- **Skill L1/L2 渐进披露**（Hermes / MAF / agentskills 同构）。
- **工具目录单源**：`shared/agent-tools.ts`。
- **约束在执行层**：`policy` + `beforeTool`，不靠 prompt 自觉。
- **Host 外置 MCP**：MV3 下的正确切分。

### 1.2 核心短板（本文展开；**2026-08-17 进度见 OPTIMIZATION_PLAN §1**）

1. **胖文件**（已瘦身但未达标）：`content.ts` ~1574、`workspace-composition.ts` ~687；`exec-turn.ts` ~265、`builtin-handlers` registry ~391 ✅。
2. **模型协议**：原生 `tools[]` + `builtin-tool-resolver` 元工具（`dom_read` / `workspace` / `network_read`）✅。
3. **工具面**：catalog **39** 个（已从多读别名收敛；长期目标 ~15 正交 builtin）。
4. **Trace 投影**：`trace-view.ts` + `RecordView = TraceView` ✅；storage 旧字段迁移见 Phase 2 §6。
5. **观察层粗**（战略 P2）：列表 snapshot、250ms DOM↔Network 关联 — **未做**。
6. **Thread 记忆**：`thread-compaction` 已在 `@naviforge/session` ✅。
7. **内部 handler 别名**：resolver 层保留（非 catalog），Playbook/历史 trace 回放用。

---

## 2. 设计冗余与缺陷

### 2.1 工具面重叠（P1）

> **2026-08-17 状态**：✅ catalog 已收敛为 `dom_read` + `workspace` + `network_read` 元工具；`KERNEL_PROMPT` 决策表 + self-check。内部 handler（`dom_read_page` 等）仅 registry/resolver，不进 `AGENT_TOOL_CATALOG`。长期目标：model-facing ≤15。

**现象（审查时）**

`packages/shared/src/agent-tools.ts` 中 DOM「读/抽」类工具职责交叉：

| 工具 | 实际行为 | 重叠点 |
|------|----------|--------|
| `dom_read_page` | 正文/article 类可读文本 | 与 extract、to_markdown 都是「拿页面文字」 |
| `dom_extract_dom` | 链接/按钮/feed 结构化列表 | 与 `extract_content` 列表语义接近 |
| `dom_extract_content` | 列表记录（标题/链接/字段） | 模型常在介绍类任务反复试探读路径 |
| `page_to_markdown` | 写工作区 + 返回 path | 与 read_page「拿内容」目标重叠 |
| `dom_snapshot` | 可访问性快照 | 每步循环已 snapshot；模型仍可能误用 |

**影响**

- 模型 **工具选择方差大**，action-loop / observation dedupe 压力上升。
- `exec-turn.ts` 分发分支与 trace 格式化函数重复（`formatReadPageTrace`、`formatExtractDomTrace` 等）。
- Prompt 与 KERNEL 需反复解释「何时用哪个读工具」。

**方案**

1. **短期（文档 + prompt）**  
   - 在 `KERNEL_PROMPT` 增加决策表：「列表 → `extract_content`；长文阅读 → `read_page`；落盘归档 → `to_markdown`」。  
   - `self-check.ts` 断言 KERNEL 包含该表关键词。

2. **中期（API 收敛）**  
   - 引入 **`dom.read` 统一入口**，`mode` 枚举：`body | list | markdown | snapshot`。  
   - 旧 id 保留 **6–12 个月别名**：`dom_read_page` → `dom.read({ mode: 'body' })`，在 catalog 标 `deprecated`。  
   - `exec-turn` 内别名走同一 handler。

3. **长期**  
   - Catalog 对外只暴露 ~15 个正交工具；DOM 写操作保持细粒度（click/type 等不可合并）。

**验收**

- 单 tab 介绍类 live case 平均步数下降（对比 `tests/live` 基线）。
- `AGENT_TOOL_CATALOG` 条目数减少或别名集中在单一 handler 文件。
- 无回归：`tests/e2e/agent-policy.spec.ts`、`content-extract.spec.ts`。

**参考**：OpenHarness / smolagents 倾向更少、更正交的工具面；browser-use 用单一 `extract` + `navigate` 族。

---

### 2.2 `TraceRecord` 与 `TraceRecord` 同构双轨（P1）

**现象**

- Runtime 直播：`TraceRecord`（`packages/runtime/src/agent.ts`）。
- 持久化：`TraceRecord` / `TraceRecord`（`packages/session/src/types.ts`）。
- 桥接：`apps/extension/src/lib/agent-event-projection.ts` 的 `toTrace`。

两套 union 字段高度对应（`model_turn` ↔ `model.turn`，`tool_result` ↔ `tool.result`），任何新增字段需改 **三处**（Event 类型、PayloadMap、`toTrace`）。

**影响**

- 字段漂移风险（例如 `io` 块、`continued` 只在一侧更新）。
- 新人需理解「直播 vs 账本」实为同一语义的两个 TypeScript 类型。

**方案**

1. **单一真源类型**  
   - 在 `@naviforge/session` 定义 `TraceEnvelope`（`type` + `payload` + 元数据）。  
   - `TraceRecord` 改为 `TraceEnvelope & { live?: true }` 或直接用 `TraceEnvelope`，去掉平行 union。

2. **投影函数集中**  
   - 新建 `packages/session/src/project.ts`（或 `extension/lib/trace-projector.ts` 若暂不想 session 依赖 runtime）：  
     - `toPersisted(envelope)` — 补 `schema/id/at/kind/title/content`  
     - `toLive(envelope)` — runtime emit 用  
   - `agent-event-projection.ts` 只保留 UI 专用 `viewRecord`。

3. **增量迁移**  
   - 先让 `toTrace` 调用 `toPersisted`，旧 `TraceRecord` 类型标记 `@deprecated` 别名到 `TraceEnvelope`。  
   - `background.ts` 的 `AGENT_RUN_EVENT` 处理不改语义，只改类型导入。

**验收**

- 新增一种 `TraceType` 时，**单 PR 只改 session types + projector**，无需同步改 agent.ts union。  
- `packages/session/src/self-check.ts` 覆盖每种 type 的 round-trip。

**参考**：Pi 用 SessionManager 追加 + `messages.ts` 单一转换链；OpenHarness Envelope + 投影。

---

### 2.3 显示派生字段 `kind` / `title` / `content`（P2）

**现象**

`TraceRecord` 机器读 `type` + `payload`，同时强制携带 `kind`、`title`、`content`（`sealTrace` / `normalizeTraceRecord` 派生）。

文档已声明 **kind 不当判别器**，但：

- 旧 UI 路径、JSONL 导出、部分测试仍按 `kind` 过滤。  
- 派生逻辑与 `payload` 可能不一致（例如 `run.recovery` 标题本地化 vs payload.category）。

**方案**

1. **新代码纪律**：ESLint 或 `self-check` 禁止在 `runtime` / `hooks` 用 `kind` 分支。  
2. **UI 全面改用 `type`**：`chat-events.ts`、`viewRecord` 的 CSS class 映射表 `type → cardVariant`。  
3. **退役**：存储迁移完成后，`kind/title/content` 改为 **可选**，导出 JSONL 时由 projector 即时计算，不落盘。

**验收**

- `grep 'message.kind' apps/extension` 仅出现在 projector / 迁移代码。  
- 旧 `LegacyTraceRecord` 迁移后，新记录可不写 `kind`。

---

### 2.4 Plane 接口膨胀与文档滞后（P2）

**现象**

除 `dom-plane`、`network-plane` 外，runtime 还依赖：

- `tabs-plane`、`search-plane`、`script-plane`、`workspace-plane`

`MODULES.md` 长期目标表未完整列出；Plane 与工具 group 的对应关系靠读 `exec-turn.ts`。

**方案**

1. 更新 `MODULES.md` §当前实际模块，补全 Plane 表。  
2. 在 `agent-ctx.ts` 的 `AgentPlanes` 旁加注释表：`Plane → 工具 id 前缀 → 实现文件`。  
3. 不新增 package；若某 Plane 仅 1–2 个工具且长期不变，可考虑 **合并进 `workspace-plane`**（例如 `script.*` 与 workspace 同属 Host 文件能力）——**仅当**合并后测试仍清晰。

**验收**

- `MODULES.md` 与 `AgentPlanes` 注释一致。  
- 新贡献者无需打开 `exec-turn.ts` 即可知道「工具落在哪个 Plane」。

---

### 2.5 胖文件结构债（P0）

> **2026-08-17 状态**：`use-agent-workspace.ts` 已变为 **6 行 shim** → `workspace-composition.ts`（~687）。`exec-turn.ts` **~265**；`agent.ts` **~628**。子模块：`workspace-run-wire.ts`、`workspace-queue.ts`、`workspace-restore.ts`、`agent-run-controller.ts`、`live-session.ts`。验收未达标项见 OPTIMIZATION_PLAN O-02/O-11。

**现象（审查时）**

| 文件 | 约行数 | 混杂职责 |
|------|--------|----------|
| `apps/extension/src/chat/workspace-composition.ts` | ~687 | React 组合；原 `use-agent-workspace` 已 shim 化 |
| `packages/runtime/src/exec-turn.ts` | ~265 | ToolRegistry 分发（已从 ~1620 瘦身） |
| `packages/runtime/src/agent.ts` | ~628 | 主循环 orchestrate（`model-turns` / hooks 已拆） |

`AGENT_SYSTEM_DESIGN.md` §11.3 已承认；`exec-turn` 已拆出，但热点仍在。

**影响**

- 单功能 PR 冲突率高。  
- 单测难以针对「循环阶段」与「工具执行」隔离。  
- Code review 难以验证边界（例如 policy 检查是否重复）。

**方案（按文件）**

#### A. Extension workspace → Facade 拆分（P0）

> **现状**：`use-agent-workspace.ts` 仅 re-export `useWorkspaceComposition()`；逻辑在 `workspace-composition.ts` 及子模块（见上表）。目标 composition <300 行仍待 O-02。

在 `apps/extension/src/chat/` 已有 / 计划：

| 新模块 | 职责 | 从 workspace 迁出 |
|--------|------|-------------------|
| `thread-store.ts` | `loadThread` / `persistThread` / `compactThreadMemory` / slot 读写 | thread-model、thread-summary 调用链 |
| `session-controller.ts` | `appendTraceRecord` / `capTraceRecords` / runId 绑定 | session-store 交互 |
| `agent-run-controller.ts` | `startRun` / `pause` / `stop` / steer/followUp 队列对接 background | `AGENT_RUN` 消息 |
| `playbook-bridge.ts` | Forge / 重放 / `observeFromPlaybook` | playbook 相关 |
| `use-agent-workspace.ts` | 仅 React hooks + 组合上述模块 | 目标 **< 600 行** |

**接口示例**

```ts
// agent-run-controller.ts
export type AgentRunController = {
  start(opts: StartRunOpts): Promise<void>
  steer(text: string): void
  followUp(text: string): void
  pause(): void
  stop(): void
  readonly events: AsyncIterable<TraceEnvelope>
}
```

**验收**

- `use-agent-workspace.ts` 行数 < 600。  
- 现有 e2e 全绿；`chat-events.self-check.ts` 仍通过。  
- Thread 记忆逻辑可通过 **无 React** 的单元 self-check 调用 `thread-store`。

#### B. `exec-turn.ts` → ToolRegistry（P0）

1. 新建 `packages/runtime/src/tools/registry.ts`：

```ts
export type ToolContext = ExecContext // 现有类型
export type ToolHandler = (ctx: ToolContext, args: Record<string, unknown>) => Promise<ToolResult>

export function createToolRegistry(handlers: Record<string, ToolHandler>): {
  dispatch(tool: string, args: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>
}
```

2. 按 group 拆文件（每文件 < 300 行）：

- `tools/dom-actions.ts` — click/type/scroll/…  
- `tools/dom-read.ts` — read/extract/snapshot（收敛后单 handler）  
- `tools/network.ts`  
- `tools/system.ts` — done/ask_user/spawn  
- `tools/mcp.ts` — 委托 `mcp-tools.ts`  
- `tools/tabs-search-workspace.ts`

3. `exec-turn.ts` 保留：`snapshotWithRetry`、对外 `execTurn` 入口、共享 formatter（或迁到 `tools/format.ts`）。

**验收**

- `exec-turn.ts` < 400 行。  
- 新增工具 = catalog + 单 handler 文件 + registry 注册，**不修改** 巨型 switch。  
- `runtime/src/self-check.ts` 对每个 builtin tool 至少一次 dispatch mock。

#### C. `agent.ts` → 循环阶段下沉（P1）

1. 将 deterministic preflight（`isPageReadTask`、`shouldHintListThenDetail`、list-then-detail hint）注册为 **stock `beforeModel` hook**，与 `HOOK_MIDDLEWARE.md` 一致。  
2. 将 `drainSteer` / `drainFollowUp` 抽到 `queue-controller.ts`。  
3. `agent.ts` 只保留：`while` 骨架、`hooks.runPhase`、`execTurn` 调用、`emit`。

**验收**

- `agent.ts` < 700 行。  
- `hooks.self-check.ts` 覆盖迁移后的 preflight 行为。

**参考**：OpenHarness `HookExecutor` 单入口；Pi `agent-loop.ts` 无状态循环文件。

---

### 2.6 观察层粗粒度（P2）

**现象**

- DOM：交互元素 **截断列表**（`observe/compact.ts`），非稳定 element ref / 增量 diff。  
- Network↔DOM：`MODULE_REVIEW.md` 记载 **250ms 固定窗口** 关联，无法证明因果。  
- Playbook 锻造只能生成启发式 `network_wait` 候选。

**影响**

- 复杂 SPA（虚拟列表、懒加载）上 index 漂移快。  
- Forge 的 selector 依赖 `page-agent` 私有 `selectorMap`（见 §2.7）。

**方案**

1. **短期**：snapshot 增加 `revision` 与 `staleIndex` 标记；工具返回明确 `index_invalid` + 建议 `dom_snapshot`。  
2. **中期**：`dom-plane` 增加可选 **`elementRef`**（selector + index + framePath）稳定字段；click 优先 ref，index 仅 fallback。  
3. **长期**：Network 侧记录 `requestId`；content script 在 click 时打 `correlationId`，CDP 事件匹配（需 Host/debugger 升级，见 `MODULE_REVIEW.md`）。

**验收**

- `tests/live` 中 index 失效站点有自动 snapshot+重试路径。  
- Playbook 锻造优先 selector 字段占比上升。

---

### 2.7 `page-agent` 私有 API 耦合（P1）

> **2026-08-17 状态**：✅ `apps/extension/src/lib/selector-resolver.ts` 为 `selectorMap` 唯一访问点；`page-control-listener.ts` 抽路由。上游 PR / fallback 行为仍见下文。

**现象（审查时）**

`content.ts` 通过非公开 `selectorMap` 生成 Playbook selector；`MODULE_REVIEW.md` 要求每次 page-agent 升级前回归。

**方案**

1. 新建 `apps/extension/src/lib/selector-resolver.ts`（**唯一** 访问 `selectorMap` 的文件）。  
2. `dom-plane` Adapter 暴露 `resolveSelector(index) → string | null`。  
3. `OPEN_SOURCE.md` 记录：上游无稳定 API 时的 fallback 行为。  
4. 向 page-agent 提 PR 或 fork 补丁：公开 `getSelectorForIndex` 等价 API。

**验收**

- `grep selectorMap` 仅出现在 `selector-resolver.ts`。  
- page-agent 版本升级 CI 跑 `tests/e2e/extension-content.spec.ts` + playbook forge case。

---

### 2.8 子 Agent 审计不透明（P2）

**现象**

`system_spawn_readonly_tasks` → `runReadonlySubAgents`：每个 leaf 复用 canonical Agent/AgentCtx/hook 管线，并以唯一 `runId` 和父 `parentRunId` 写入共享 TraceRecord ledger。只读 profile 不持有可写 DomPlane，最多三个 leaf 并行，父仍是唯一 DOM writer。

**方案**

1. 子 trace 使用 canonical records（含 `model.turn` 和 `tool.result`），通过 `parentRunId` 供侧栏折叠。  
2. 父 tool result 聚合每个 leaf 的 `runId`、状态和结果，保留成功 sibling。  
3. 不做通用嵌套 subagent 框架（无产品需求）。

**验收**

- 审计 JSONL 可还原子 Agent 逐步工具名。  
- 主 tab 仍单写者；子 Agent 无 DomPlane 写权限。

---

### 2.9 单条 `user` blob vs message list（P2，战略项）

**现象**

每轮 LLM 调用为 `system + 一条 user`（`compileUserPrompt`），非 Chat Completions 多轮 `messages[]`。

**理由（保留）**：浏览器每步页面变，全量 assistant 历史易过期且贵。

**问题**

- `model.turn.io.user` 存整轮编译结果 → **审计体积大**。  
- 难对接 Responses API / 多 part message（图片 + 文本分离演进）。  
- 与 Pi `convertToLlm`、OpenHarness message projection 路径不同，跨框架评测需额外适配。

**方案（分阶段）**

1. **Phase A（不改 API 形状）**  
   - `compileUserPrompt` 拆为 **命名块** 写入 `io.user`：`{ blocks: [{ name, text }] }` 内部结构，对外仍拼成 string。  
   - 便于审计页按块折叠。

2. **Phase B（可选）**  
   - `RunLedger` 存 **结构化 TraceLine** `{ tag, text, pinned? }`，`selectWorkingSet` 输出仍 string[]。  
   - 为将来 `messages[]` 投影留接口。

3. **Phase C（产品需要时）**  
   - LLM 层支持 `messages[]`；system 固定，user 仅「当前页块 + 工作集块」，历史 assistant 仍不进列表。

**验收**

- Phase A 不改变 token 数；审计页可折叠「DOM / Network / 轨迹」块。  
- `self-check` 断言 compile 块顺序稳定。

---

### 2.10 圈内无 LLM 摘要（P2）

**现象**

圈内仅 L0/L1 确定性 `selectWorkingSet`；跨 Run 才有 LLM slot merge。

若 `maxSteps` 从 30 提高或长任务增多，L1 折叠后模型仍可能丢关键钉住行上下文。

**方案**

- 当 `steps > 20` 且 `project()` 仍触发 `fold_context` 两次以上时，可选 **L2 摘要**（单次 LLM，输入仅工作集折叠块，输出 `#compact summary` 钉住行）。  
- 实现放在 `working-set.ts` 旁 `summarize-fold.ts`，由 `WorkingSetHook` 触发，**默认关闭**，设置项 `enableLoopSummarize`。

**参考**：Pi `compaction/`；Hermes `ContextCompressor`。

---

## 3. 模型协议（已完成）

Provider response is accepted only when it contains exactly one native function call. Runtime translates that call to the internal `ToolCall` / `ModelDecision` pair, and `execTurn` executes it directly. `system_done` owns final answers and `system_ask_user` owns questions.

No-call completions emit one `protocol_retry` recovery and are retried once. A second consecutive no-call completion or any completion with multiple calls ends the run with `protocol_error`; protocol violations never trigger HITL.

---

### 3.2 `TraceRecord` / `TraceRecord` / `ChatEvent` 命名（P2）

**方案**

- 文档与类型统一对外名：**TraceRecord**（持久化）。  
- `TraceRecord` 保留为 **类型别名** `@deprecated`，指向 `TraceRecord`。  
- `ChatEvent` 明确标注 **仅 React 渲染期**，禁止 `JSON.stringify` 进 storage。

---

### 3.3 `Thread` 实体与实现错位（P1）

**现象**

- 类型：`ThreadMemorySlots` 在 `@naviforge/session`。  
- 逻辑：`thread-memory.ts`、`thread-summary.ts`、`compactThreadMemory` 在 `extension`。

Host / 评测若要离线 compact，需复制逻辑。

**方案**

1. 新建 `packages/session/src/thread-memory.ts`（**纯函数**，无 `chrome.storage`）：  
   - `memoryPatchFromRun`  
   - `shouldCompactThread`  
   - `formatThreadMemory` / `mergeSlotsWithLlm` 的 **输入输出类型**  
2. Extension 只负责 IO：`loadThread` → 调用 session 纯函数 → `saveThread`。  
3. Host workspace 导出 JSONL 时可选附带 compact 后的 slots。

**验收**

- `packages/session/src/self-check.ts` 覆盖 slot merge 纯函数。  
- Extension 无 compact 算法重复。

---

### 3.4 `ToolResult` 与 trace 文本双份（P2）

**现象**

- 审计：`tool.result` payload 含完整 `data`。  
- 工作集：`formatReadPageTrace` 等再生成截断文本。

**方案**

- `RunLedger.append` 接受 `{ tool, args, result, traceLine? }`；  
- 若 handler 返回 `ToolResult` + 可选 `traceSummary`，formatter **只写一份**；  
- `ingestTrace` 优先用 `traceSummary`，否则 fallback 通用 `tool ok/err`。

---

### 3.5 `AgentGates` 隐式状态机（P2）

**现象**

`AgentCtx.gates` 与 `loop-gates.ts`、`builtin-hooks` 分散。

**方案**

- 合并为 `LoopGateState` 类，方法：`recordObservation`、`checkActionLoop`、`issueTaskHint`。  
- `beforeTool` stock hook 只调 `gates.evaluate(tool, args)`。

---

## 4. 边界与简洁性

### 4.1 Extension 过胖（P0）

见 §2.5A。原则：**MV3 适配层可以胖，但 Agent 胶水不应与 React 绑死**。

### 4.2 Agent vs Toolkit 双产品面（P2）

**现象**

工具箱（翻译/OCR/改头）不走 `runAgent`，但共享隐私开关（`allowDomInject` 等），无共享类型。

**方案**

- `packages/shared/src/capability-gates.ts`：

```ts
export type CapabilityGates = {
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  captureNetworkBodies: boolean
  allowMainProbe: boolean
}
```

- Agent `AgentPolicy` 与 Toolkit settings 共用该类型；Options 单源写入。

---

### 4.3 Hook 与循环内启发式双轨（P1）

**现象**

`HOOK_MIDDLEWARE.md` 定义 hook 相位，但 `agent.ts` 仍有 list-then-detail、page-read preflight。

**方案**

- 全部迁入 `builtin-hooks.ts` 的 stock hook，命名 `preflight-page-read`、`preflight-list-detail`。  
- `agent.ts` 禁止新增 `if (isPageReadTask)` 类分支；CI `grep` 门禁。

---

### 4.4 MCP 配置与 Host 生命周期（P2）

**现象**

- `shared/mcp-servers-json.ts`：Cursor 兼容解析。  
- 连接/白名单：Host + extension settings。

**方案**

- 文档 `AGENT_MCP_RUNTIME_DESIGN.md` 增 §配置真源：`chrome.storage` 用户配置 + Host 运行时连接状态。  
- `parseMcpServersJson` 返回 `NormalizedMcpServer[]`，Host 启动时校验，extension 只存 normalized 结果（避免双解析）。

---

## 5. 设计模式重构映射

| 模式 | 应用点 | 具体动作 | 优先级 |
|------|--------|----------|--------|
| **Facade** | `workspace-composition` + shim | §2.5A 子模块（run-wire/queue/restore） | P0 ~ |
| **Registry + Command** | `exec-turn` | §2.5B ToolRegistry | P0 ✅ |
| **Chain of Responsibility** | hooks | preflight / task-hint 已迁入 | P1 ✅ |
| **Projection** | trace | §2.2 `trace-view` + `RecordView=TraceView` | P1 ✅ |
| **Strategy** | compaction | L2 summarize 可选策略 | P2 |
| **Adapter** | page-agent | §2.7 selector-resolver | P1 ✅ |
| **State Machine** | run status | `RunState` 枚举 + 转换表文档化 | P2 |
| **Mediator** | background | 保持；禁止 UI 直连 runtime | — |

**明确不引入**

- Cordis / `next()` 洋葱中间件（`HOOK_MIDDLEWARE.md` 已排除）。  
- MAF 三层 middleware 类继承树。  
- LangGraph 子图（无多 Agent 产品需求）。

---

## 6. 兼容层退役计划

| 兼容层 | 位置 | 退役条件 | 退役动作 |
|--------|------|----------|----------|
| `LegacyTraceRecord` | `session/types.ts` | 所有用户 storage 迁移完成 | 删除 normalize 推断分支；一次性 migration 脚本 |
| `kind/title/content` 落盘 | `sealTrace` | UI 全用 `type` | 改为导出时计算；storage 新记录可选省略 |
| `dom_read_page` 等内部 handler | registry / resolver | catalog 已用 `dom_read` ✅ | **保留** registry；不进 `AGENT_TOOL_CATALOG` |
| `parseLegacyConnection` | `mcp-servers-json.ts` | 文档声明仅支持 Cursor 格式 | 旧数组格式读时 warning + 自动转换 |
| `run.context.continued` | 审计 | 审计 UI 能折叠 system | 续跑仍写 `run.context` 但 `systemPrompt` 哈希引用 |
| `normalizeScrollArgs` 多形状 | `exec-turn.ts` | tool schema 固定后 | schema 层 `.strict()` 拒绝旧字段 |
| `Agent.run` 运行时挂载 | `agent-ctx.ts` | 解决循环 import 后 | `agent.ts` 导出 `runAgent` 唯一入口 |
| `audioDataUrl` 不持久化 | `user.task` | 无 | 永久：直播字段，写入 `trace.ts` 注释 |

**迁移脚本建议**

- Extension 启动时 `migrateSessionSchemaV1()`：  
  - 无 `schema` 的消息 → `normalizeTraceRecord` → 写回。  
  - 完成后 `localStorage` 标记 `traceSchemaMigrated=1`。

---

## 7. 与成熟框架差距对照（优化后目标）

| 维度 | 当前（2026-08-17） | 优化后目标 | 参照 |
|------|---------------------|------------|------|
| 主循环文件 | `agent.ts` ~628 行 | orchestrate only + hook | Pi `agent-loop.ts` |
| 工具分发 | `exec-turn` ~265 行 | Registry + 分文件 | OpenHarness registry ✅ |
| UI 胶水 | `workspace-composition` ~687 行 | compose < 300 行 | Pi `AgentSession` 薄层 |
| 消息真源 | `TraceRecord` + `TraceView` 投影 | 投影单源（已达成） | Pi SessionManager |
| 工具数量 | catalog 39 | ≤15 正交 + resolver 内部 | smolagents |
| 子 Agent 审计 | UI `<details>` 分组 | 结构化 JSONL 导出（可选） | Hermes child trace |
| 压缩 | L0/L1 | L0/L1 + 可选 L2 | Pi compaction |
| 观察 | 列表 snapshot | ref + revision | browser-use / CDP 演进 |

**不追求对齐**

- Hermes Gateway 多租户 / IM 渠道。  
- OpenHarness 全并行 tool `gather`（浏览器单写者限制）。  
- MAF Hosting 多副本 Session 外置。

---

## 8. 测试与门禁

每次结构刀附带：

| 门禁 | 命令 / 位置 |
|------|-------------|
| 单元 self-check | `npm run check`（naviforge 根） |
| E2E | `npm run test:e2e` |
| Live（可选） | `npm run test:live` nightly |
| 新增工具 | `runtime/src/self-check.ts` dispatch 一条 |
| 禁止 kind 分支 | `scripts/check-trace-kind.sh`（建议新增） |
| page-agent 升级 | `extension-content.spec.ts` |

---

## 9. 风险与回滚

| 改动 | 风险 | 缓解 |
|------|------|------|
| ToolRegistry | 漏注册工具 | self-check 扫描 catalog id ⊆ registry |
| 工具合并 | 破坏 Playbook / 旧 prompt | 别名期 + deprecated 日志 |
| storage 迁移 | 用户丢历史 | 迁移前 export 备份；失败保留旧记录 |
| Facade 拆分 | React 状态 bug | 小步 PR；每步 e2e 全绿 |
| 删 LegacyTraceRecord | 旧用户打不开历史 | 迁移脚本 + 版本门控 |

回滚策略：**行为开关**（`featureFlags.toolRegistry`）仅在第一阶段 Registry 使用；稳定后删开关。

---

## 10. 优先级路线图

### 2026-08-17 已落地（本轮架构刀）

| 类别 | 落地项 |
|------|--------|
| §2.1 工具重叠 | `dom_read` 统一入口 + `dom-read-resolver` 别名；`workspace` / `network_read` meta 工具 |
| §2.2 双轨 trace | `@naviforge/session` `trace-view.ts` + `appendUniqueRecords`；extension 投影瘦身 |
| §4 Pipeline | `model-turns.ts`（`runModelTurns`）；`PreflightHook` / `TaskHintHook`；`loop-gate-state.ts` |
| §5 Facade | `live-session.ts` + `chrome-session-manager.ts`（M6）；TabWorkspace 仅 UI 草稿 |
| §6 兼容退役 | 删 `session-controller`、extension `thread-memory` shim、`followUps: string[]`、catalog DOM 读别名 |
| §8 门禁 | `check-boundaries.mjs`；`check-trace-kind.sh` |
| Extension MV3 | `selector-resolver.ts`；`page-control-listener.ts`；`workspace-run-wire.ts` |
| Runtime 拆分 | `handlers/dom.ts`；`format-tool-trace.ts`；`builtin-handlers` registry ~391 行 |
| UI / 提示 | `partitionChildTraceViews`；`compileUserPromptBlocks` |
| Toolkit | `loadToolkitCapabilityGates` 与 Agent 同源；background 截图/翻译走 gate |

**仍待（非方向性债，见 OPTIMIZATION_PLAN O-11/O-08/O-13 部分完成项）**：`content.ts` / `workspace-composition.ts` 行数仍高；战略 backlog（elementRef、L2 summarize、LegacyTraceRecord 迁移）见 Phase 2。

| 建议后续 | 状态 |
|----------|------|
| `runModelTurns` 从 `agent.ts` 抽出 | ✅ 见 `model-turns.ts` |
| `dom_read` 收敛（别名不进 model tools[]） | ✅ `modelFacingToolIds` |
| 删 `session-controller` | ✅ |
| `builtin-handlers` 按 plane 拆分 | ✅ `handlers/dom.ts` + registry 聚合 |
| `selector-resolver` 单点隔离 | ✅ |
| Toolkit gates 端到端 | ✅ background + options toolkit-panel |
| 框架对照审查文档 | ✅ [FRAMEWORK_COMPARISON_REVIEW.md](./FRAMEWORK_COMPARISON_REVIEW.md) |

### Phase 0（1–2 周，P0）

- [x] §2.5B ToolRegistry + `exec-turn` 瘦身  
- [~] §2.5A `thread-store` + `agent-run-controller` 初拆（controller 已有；store 端口类型待收敛）  
- [x] §2.7 `selector-resolver` 单点隔离  
- [x] §8 `check-trace-kind` 门禁

### Phase 1（2–4 周，P1）

- [x] §2.2 TraceEnvelope 单类型 + projector（`trace-view` + `agent-event-projection` 委托）
- [x] §3.1 原生 function call 协议收敛
- [x] §3.3 `thread-compaction` 迁至 `@naviforge/session`；extension shim 已删
- [x] §4.3 preflight 迁入 `PreflightHook`（`pipeline.runTaskPreflight`）
- [x] §2.1 工具收敛设计 + KERNEL 决策表（`dom_read` + `workspace` / `network_read`）

### Phase 2（1–2 月，P2）

- [x] §2.1 `dom.read` 统一 + 别名退役（catalog）  
- [x] §2.8 子 Agent 审计 steps（UI 分组；结构化 JSONL 导出待产品）  
- [x] §2.9 compile user 命名块  
- [ ] §6 LegacyTraceRecord 迁移与退役  
- [ ] §2.10 可选 L2 summarize  
- [ ] §2.6 elementRef / revision 增强
- [~] §2.11 `content.ts` 完全拆分（路由已抽；helpers 仍集中）

### 明确不做（与 AGENT_SYSTEM_DESIGN §12 一致）

- 同 tab 多 Agent 并行写 DOM  
- 全量 TraceRecord 回灌 LLM  
- 新 package：`prompt-compiler`、`ui`、`mcp-bridge`  
- 通用嵌套 subagent 框架  
- Cloud 控制面依赖

---

## 11. 相关文档

| 文档 | 关系 |
|------|------|
| [OPTIMIZATION_PLAN.md](./OPTIMIZATION_PLAN.md) | **执行清单**：O-01～O-20 问题→方案→排期 |
| [FRAMEWORK_COMPARISON_REVIEW.md](./FRAMEWORK_COMPARISON_REVIEW.md) | 五类问题 + 框架对照 + 本轮落地记录 |
| [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md) | 当前实现权威 |
| [MODULES.md](./MODULES.md) | 拆包节奏；Plane 表已更新（O-16） |
| [MODULE_REVIEW.md](./MODULE_REVIEW.md) | 2026-08-10 包级结论仍成立 |
| [HOOK_MIDDLEWARE.md](./HOOK_MIDDLEWARE.md) | Hook 相位；preflight 迁入依据 |
| [AGENT_MCP_RUNTIME_DESIGN.md](./AGENT_MCP_RUNTIME_DESIGN.md) | MCP 与 Host |
| `OpenHarness/docs/framework-comparison/` | Pi / Hermes / OpenHarness 横向对照 |

---

**维护**：完成某项优化后，在对应 § 打 `[x]` 并链接 PR；若实现与方案分歧，先改 [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md)，再回写本文状态列。
