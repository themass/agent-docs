# NaviForge 架构优化清单与方案

> **日期**：2026-08-17（**状态同步**：2026-08-17 末）  
> **对照**：Pi、MAF、Hermes、OpenHarness  
> **详细 backlog**：[ARCHITECTURE_OPTIMIZATION.md](./ARCHITECTURE_OPTIMIZATION.md)（战略 + Phase 路线图）  
> **审查记录**：[FRAMEWORK_COMPARISON_REVIEW.md](./FRAMEWORK_COMPARISON_REVIEW.md)（框架对照快照）  
> **实现权威**：[AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md)（行为叙事）  
> **本文角色**：**O-01～O-20 执行清单** — 排期、验收、勾选以本文为准；ARCHITECTURE 中历史「现象」段落保留作背景，**当前状态见 §1 总表与 §3 排期**。

---

## 0. 先读这句：问题多，但方向已对

表面「问题很多」，多数是**收敛型技术债**（胖文件、历史兼容 handler、工具面仍偏宽），不是架构方向错误。

| 已对齐成熟框架（勿推翻） | 仍欠收敛（见 §1 状态列） |
|--------------------------|--------------------------|
| Plane 六边形、单 tab 单写者 | Extension 编排层仍厚（composition ~687 行） |
| 审计 ≠ 工作集（RunLedger + compaction） | 模型可见 builtin **39** 个（长期目标 ~15） |
| RunSupervisor + HookPipeline | `content.ts` 仍 ~1574 行（路由已抽） |
| AgentSession facade + `dom_read` / `workspace` / `network_read` | 内部 handler 别名层（resolver，非 catalog） |
| 原生 function call 协议 | **本文与 ARCHITECTURE §10 已同步代码** |

**原则**：每刀可独立 PR、`npm run check` 全绿、有明确验收；删兼容前先 grep 清零。

### 0.1 三份文档怎么读（避免「对不上」）

| 文档 | 回答什么问题 | 何时更新 |
|------|--------------|----------|
| **本文 OPTIMIZATION_PLAN** | O-xx 做没做、下一步做什么 | 每完成 O-xx 改 §1 状态 + §3 勾选 |
| **ARCHITECTURE_OPTIMIZATION** | 为什么、Phase 0～2、战略项（elementRef、L2） | 方案变更或 Phase 勾选 |
| **FRAMEWORK_COMPARISON_REVIEW** | 与 Pi/Hermes 差距、胖文件实测行数 | 与本文同步发版时改 §1.1 表 |

**规则**：代码落地后 **先改本文 §1 状态列**，再改 ARCHITECTURE §10 与 FRAMEWORK §1.1；勿只勾排期不改总表。

---

## 1. 优化总表（按优先级）

| ID | 状态 | 优先级 | 主题 | 问题一句话 | 方案一句话 | 估时 |
|----|------|--------|------|------------|------------|------|
| O-01 | ✅ | P0 | 文档同步 | 做了的写「未做」，排期失真 | 三份文档状态列 + §10 勾选 | 0.5d |
| O-02 | ~ | P0 | Extension 编排 | `workspace-composition` ~687 行 | 拆 queue / run-wire / restore；目标 composition <300 | 2–3d |
| O-03 | ✅ | P0 | Toolkit gates | Toolkit 与 Agent 隐私开关不一致 | `loadToolkitCapabilityGates` 全路径 | 1d |
| O-04 | ✅ | P1 | 工具别名退役 | catalog 曾有多读工具别名 | `dom_read` + resolver；catalog 无 `dom_read_page` | 1–2d |
| O-05 | ✅ | P1 | builtin-handlers | 曾 ~1690 行单文件 | `handlers/dom.ts` 等；registry ~391 行 | 3–5d |
| O-06 | ✅ | P1 | 工具面收敛 | 模型工具偏多 | `workspace` + `network_read` meta；catalog **39** | 1–2w |
| O-07 | ✅ | P1 | 双 preflight 命名 | UI vs runtime 易混 | UI → `run-readiness.ts` | 0.5d |
| O-08 | ~ | P1 | RunPhase 统一 | UI 字符串 vs session `RunPhase` | `run-phase.ts` 映射；待 UI 单源 | 2d |
| O-09 | ✅ | P1 | TabWorkspace 瘦身 | workspace 与 session 双轨 | 仅 UI 草稿；恢复走 `live-session` | 2–3d |
| O-10 | ✅ | P1 | Hook 启发式 | TaskHint 与 Preflight 重叠 | `task-classifier.ts` + hooks | 1d |
| O-11 | ~ | P2 | content.ts | ~1574 行 MV3 内容脚本 | 路由已抽；helpers 待按域拆 | 3–5d |
| O-12 | ✅ | P2 | AgentGates | gates 分散 | `loop-gate-state.ts` 封装 | 2–3d |
| O-13 | ✅ | P2 | RecordView.kind | 与 `variant` 重复 | `RecordView = TraceView`；UI 用 `variant` | 1d |
| O-14 | ✅ | P2 | trace 格式化 | 每工具一个 formatter | `formatToolTrace` 表驱动 | 1–2d |
| O-15 | ✅ | P2 | compileUserPrompt | 单函数拼装 | `compileUserPromptBlocks` | 2d |
| O-16 | ✅ | P2 | MODULES.md | Plane 表滞后 | tabs/search/script/workspace 已补 | 0.5d |
| O-17 | ✅ | P2 | selector-resolver | selectorMap 分散 | 唯一 `selector-resolver.ts` | 2d |
| O-18 | ✅ | P2 | 子 Agent 审计 | 子 run 步骤难读 | `partitionChildTraceViews` + UI | 1–2d |
| O-19 | ✅ | P2 | LEGACY 设置 | 80k token 迁移分支 | 分支已删 | 0.5d |
| O-20 | ~ | P2 | MCP 配置 | 双解析路径 | 共享 `parseMcpServersJson`；extension 读 `loadNormalizedMcpServers` | 1w |

**图例**：✅ 验收达标　~ 部分完成（见 §3）　⬜ 未开始（无）

**仍待下一刀（~）**：O-02、O-08、O-11、O-20（行数/类型统一/MCP 编辑层收敛）。

---

## 2. 分主题方案

### 2.1 设计冗余与缺陷

#### O-05 / O-06 工具执行与工具面

**现象（历史）**

- `tools/builtin-handlers.ts` 曾 ~1690 行；**现状** registry ~391 行 + `handlers/dom.ts` 等。
- 模型 `tools[]`：**39** 个 catalog id（`AGENT_TOOL_CATALOG`）；内部 handler 经 `builtin-tool-resolver` 解析（如 `dom_read` → `dom_read_page`），**不进 catalog**。

**方案**

1. **短期**：按 group 拆文件，registry 只做 `register()` 聚合：
   ```
   tools/handlers/dom-actions.ts
   tools/handlers/dom-read.ts      # dom_read 单 handler
   tools/handlers/network.ts
   tools/handlers/workspace.ts
   tools/handlers/system.ts
   ```
2. **中期**：`workspace_*` 合并为 `workspace({ action, ... })`；network 读合并为 `network_read({ mode })`。
3. **长期**：model-facing ≤15；写操作保持细粒度（click/type 不可并）。

**验收**

- 单文件 handler 模块 <400 行。
- `tool-names.self-check` + `tool-registry.self-check` 绿。
- live case 平均步数不升（对比基线）。

---

#### O-11 content.ts 巨石

**现象**：DOM 执行、消息路由、部分工具逻辑全在一个 content script。

**方案**

- 拆 `content/messages.ts`（路由）、`content/tool-dispatch.ts`（与 runtime 契约对齐）、保留薄 `content.ts` 入口。
- 不新增 package；仍在 extension 内。

**验收**：`content.ts` <300 行；e2e `content-extract` / `agent-policy` 绿。

---

#### O-12 AgentGates 状态机

**现象**：`AgentCtx.gates`、`loop-gates.ts`、`builtin-hooks` 分散维护 observation dedupe、action loop、list hints。

**方案**

```ts
// packages/runtime/src/loop-gate-state.ts
class LoopGateState {
  recordObservation(tool, url, trace): void
  checkActionLoop(tool, url, args): ActionLoopDecision
  issueTaskHint(task): string | null  // 从 TaskHintHook 迁入
}
```

`AgentCtx.gates` 改为 `LoopGateState` 实例；hooks 只调方法。

**验收**：`hooks.self-check` + `action-loop.self-check` 绿；无 `gates.seenObs` 外部直接写。

---

### 2.2 模型实体

#### O-08 RunPhase 单源

**现象**：`workspace-composition` 用 `'IDLE'|'PREPARING'|...` 字符串；`@naviforge/session` 已有 `RunPhase`。

**方案**

- extension 导出 `useRunPhase()`：`RunPhase` + `transition(event)`。
- UI 文案用 `runPhaseLabel(phase, locale)`，禁止散落字符串比较。

**验收**：`grep "PREPARING" workspace` 仅出现在 phase 模块。

---

#### O-09 TabWorkspace vs Session

**现象**：`workspaceRef` 镜像 `task/events/tab`；与 `live-session.records` 重叠。

**方案**

| 数据 | 唯一真源 |
|------|----------|
| 审计 records | `AgentSession` / `live-session` |
| 输入框 task 草稿 | React `useState`（不写入 workspaceRef） |
| 目标 tab | `targetTab` state + `tabRef` |
| 恢复 | `workspace-restore` 只 hydrate session + thread |

删除 `TabWorkspace.events`；`tab-workspace.ts` 仅保留 playbook 恢复所需字段。

**验收**：`TabWorkspace` 无 `events`/`logs` 字段；restore self-check 绿。

---

#### O-13 RecordView.kind

**现象**：`RecordView = TraceView & { kind: string }`，`kind` === `variant`。

**方案**：组件 CSS/分组改用 `variant`；删 `localizeView` 中的 kind 映射。

**验收**：`RecordView` 类型别名到 `TraceView`；`chat-events.self-check` 绿。

---

### 2.3 边界与简洁性

#### O-02 workspace-composition 拆分

**目标结构**

```
workspace-composition.ts    # <250 行：只 compose hooks
workspace-privacy-state.ts  # ✅ 已有
workspace-queue-state.ts    # queue / pendingTasks / processLock
workspace-run-wire.ts       # wire.startRun、agentRun、liveSession 绑定
workspace-restore-hooks.ts  # restore effects 聚合（或扩展现有 restore）
```

**验收**：composition <300 行；行为回归 self-check 全绿。

---

#### O-03 Toolkit CapabilityGates

**方案**

```ts
// toolkit-panel / toolkit-actions 入口
const gates = await loadStoredCapabilityGates()
if (!gates.allowDomInject) { /* block inject paths */ }
```

与 Agent `workspace-run.ts` 共用 `capabilityGatesFromPrivacy`。

**验收**：Options 关 DOM inject 后，Toolkit 与 Agent 同时生效；单测覆盖。

---

#### O-07 双 Preflight 消歧

| 层 | 现名 | 新名 | 职责 |
|----|------|------|------|
| Extension UI | `preflight.ts` | `run-readiness.ts` | tab/ping/MCP/模型配置阻塞检查 |
| Runtime | `PreflightHook` | 保持 | 列表提取/读页/ skill 预加载 |

**验收**：全库 grep `preflight` 分类清晰；HOOK_MIDDLEWARE 更新一节。

---

### 2.4 设计模式补强

| 模式 | 落地项 | 关联 ID |
|------|--------|---------|
| Pipeline | 已有；补 `TurnContext` 类型贯穿 model-turns | O-08 |
| Projector | JSONL/Markdown 导出走 `projectTraceViews` | O-01 文档 |
| Registry | 拆 builtin-handlers | O-05 |
| State Machine | RunPhase | O-08 |
| Strategy | dom-read 已完成；扩 workspace/network | O-06 |
| Repository | `thread-store` 接口迁入 session 端口类型 | O-09 |

---

### 2.5 兼容层退役（最后一刀）

| 兼容层 | 退役步骤 | ID |
|--------|----------|-----|
| DOM 读别名 catalog 行 | Preflight/trace 用 `dom_read`；catalog 已删；resolver 保留内部 handler | O-04 ✅ |
| `LEGACY_TOKEN_BUDGET` | 分支已删 | O-19 ✅ |
| `tokenBudget` 字段 | Agent options 统一 `runTokenBudget` | O-19 ✅ |
| MCP 双解析 | 共享 `parseMcpServersJson`；extension 存储读 `loadNormalizedMcpServers` | O-20 ~ |
| `RecordView.kind` | `RecordView = TraceView` | O-13 ✅ |

**永久保留（非债）**：`dom-read-resolver.ts`（历史 trace / Playbook 回放）。

---

### 2.6 流程冗余与重复代码

| 冗余 | 方案 | ID |
|------|------|-----|
| Preflight emit `dom_read_page` | 统一 `dom_read({mode:'body'})` | O-04 |
| `formatReadPageTrace` 等三分 | `formatToolTrace` 表驱动 | O-14 |
| privacy 三处 merge | `useWorkspacePrivacyState` + Options 共用 `upgradePrivacySettings` | O-03 |
| 恢复多路径 | restore 单入口 `applyResumeSession` | O-09 |
| TaskHint vs Preflight 规则重叠 | 合并到 hook 或共享 `task-classifier.ts` | O-10 |

---

## 3. 推荐排期（约 4–6 周）

### Sprint 1（第 1 周）— 低风险、立刻减负

- [x] **O-01** 文档同步（ARCHITECTURE §10 + FRAMEWORK 状态列 + 本文 §4）
- [x] **O-07** preflight 重命名 → `run-readiness.ts`
- [x] **O-03** Toolkit gates 接入（`loadToolkitCapabilityGates`；截图 `visionEnabled`、翻译 `allowDomInject`）
- [x] **O-04** Preflight emit 改 `dom_read`；catalog 别名已删

### Sprint 2（第 2 周）— Extension 瘦身

- [x] **O-02** workspace-composition 拆三块（`workspace-run-wire.ts`、`workspace-queue.ts`、`workspace-restore.ts`；composition 仍 ~687 行，未达 <300）
- [~] **O-08** RunPhase 单源（`run-phase.ts` 映射；UI 仍 `RUN_STATUS` 常量）
- [x] **O-13** RecordView.kind 删除（`RecordView = TraceView`，UI 用 `variant`）

### Sprint 3（第 3–4 周）— Runtime 收敛

- [x] **O-05** builtin-handlers 拆分（`handlers/dom.ts` + tabs/system 留在 registry 聚合；registry ~391 行）
- [x] **O-14** trace 格式化表驱动（`format-tool-trace.ts`）
- [x] **O-10** TaskHint 与 Preflight 去重（`task-classifier.ts` + `taskGuidanceNotes`）
- [x] **O-04** 完成：删 catalog 别名

### Sprint 4（第 5–6 周）— 工具面与 MV3

- [x] **O-06** workspace/network 工具合并（`workspace` + `network_read`）
- [~] **O-11** content.ts 拆分（`page-control-listener.ts` + `selector-resolver.ts`；入口仍 ~1574 行，helpers 待继续拆）
- [x] **O-12** LoopGateState（`loop-gate-state.ts` + hooks 封装）
- [x] **O-09** TabWorkspace 瘦身

### Backlog（本轮已推进）

- [x] **O-15** compileUserPrompt 命名块（`compileUserPromptBlocks` / `UserPromptBlock`）
- [x] **O-16** MODULES.md Plane 表补全
- [x] **O-17** selector-resolver（`grep selectorMap` 仅 resolver + 文档）
- [x] **O-18** 子 Agent 审计 UI（`partitionChildTraceViews` + message-list `<details>`）
- [~] **O-20** MCP 单入口（`parseMcpServersJson` 共享解析；extension `loadNormalizedMcpServers`；Options 编辑仍直调 parse）
- [x] **O-19** LEGACY 设置分支删除（前序 PR）

---

## 4. 已完成项（不必重复做）

| 项 | 落点 |
|----|------|
| `runModelTurns` 抽出 | `model-turns.ts` |
| Preflight 迁入 hook | `PreflightHook` + `pipeline.runTaskPreflight` |
| `dom_read` 统一入口 + resolver | `builtin-tool-resolver.ts`（catalog 无旧读 id） |
| Trace 投影单源 | `trace-view.ts` |
| Session facade | `live-session.ts`, `chrome-session-manager.ts` |
| 禁 extension 直调 `runAgent` | `check-boundaries.mjs` |
| `session-controller` / `followUps: string[]` 删除 | — |
| `thread-compaction` 迁入 session | `@naviforge/session` |
| ToolRegistry + exec-turn 瘦身 | `tools/registry.ts`, exec-turn ~323 行 |
| kind/title/content **不落盘** | `AGENT_SYSTEM_DESIGN.md` §2 |
| `network_read` 合并 6 个读网工具 | `agent-tools.ts`, `handlers/network.ts`, resolver |
| `loop-gate-state` + `task-classifier` | `AgentGates` / `taskGuidanceNotes` 单源 |
| TabWorkspace 仅 UI 草稿字段 | `tab-workspace.ts`（无 `events`/`pendingTasks`） |
| `formatToolTrace` 表驱动 | `tools/format-tool-trace.ts` |
| DOM handlers 独立模块 | `tools/handlers/dom.ts`；`builtin-handlers.ts` ~391 行 |
| run-wire 从 composition 抽出 | `workspace-run-wire.ts` |
| Toolkit capability gates | `toolkit-gates.ts` + background `toolkitGateOrAbort` |
| selector-resolver 单点 | `apps/extension/src/lib/selector-resolver.ts` |
| PAGE_CONTROL 路由抽出 | `content/page-control-listener.ts` |
| 子 run 审计分组 | `partitionChildTraceViews` + `message-list.tsx` |
| compileUserPrompt 命名块 | `compileUserPromptBlocks()` in `prompt.ts` |
| MCP storage 读单入口 | `loadNormalizedMcpServers()` in `settings.ts` |
| trace-kind 门禁 | `scripts/check-trace-kind.sh`（CI `npm run check`） |

---

## 5. 每项通用验收

```bash
cd naviforge && npm run check
node scripts/check-boundaries.mjs
bash scripts/check-trace-kind.sh
# 结构刀后可选
npm run test:e2e
```

- 单 PR 单主题（或紧密相关的 2–3 项）。
- 删兼容层前：grep 旧符号 = 0（测试/fixture 除外）。
- 文档：完成即在 ARCHITECTURE §10 打 `[x]` 并链 PR。

---

## 6. 明确不做

与 [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md) §12 一致：

- 同 tab 多 Agent 并行写 DOM
- 全量 TraceRecord 回灌 LLM
- 为对齐新建 `prompt-compiler` / `ui` / `mcp-bridge` package
- 通用无限嵌套 subagent 框架
- Cloud 控制面

---

**维护**：完成 O-xx 后在本表打 `[x]` 并注明 PR/日期；方案变更先改 AGENT_SYSTEM_DESIGN，再回写本文。
