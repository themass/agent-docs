# Message 体系设计（冷启动 / 热执行 / 投影）

> 状态：**当前实现**  
> 关联：[AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md) · [CONTEXT_PROJECTION.md](./CONTEXT_PROJECTION.md) · [CONTEXT_COMPRESSION.md](./CONTEXT_COMPRESSION.md)

本文回答三个容易混在一起的「message」分别是什么、何时读写、能否原地修改。

---

## 1. 与 DSH 的关系：同一套事件真源 + 投影

**设计意图与 DSH 一致：**

```text
JSONL / TraceRecord[]     append-only，一份真源（SSOT）
        │
        │  冷启动：从 JSONL / Session.records 恢复 ledger，再投影
        │  热执行：append 新 event → 重新投影
        ▼
投影器（纯函数，只读账本）   有 event 不进模型；有 event 可展开 0/1/N 条「模型可见项」
        ▼
LLM 输入（当前实现）        system + 单条 user（user 内嵌 CONTEXT）+ tools[]
```

| 问题 | 答案 |
|------|------|
| 事件与 JSONL 一致？ | **是**。内存 `RunLedger` 与持久化 `Session.records` 同一 `TraceRecord` 模式；导出行 = `stringifyJsonlLine(record)`。 |
| 只 append？ | **是**（逻辑契约）。`emit` / `append` 不写回 payload；L2 压缩也是 **append** `context.compaction`。 |
| 冷启动能从 JSONL 恢复？ | **是**。Session 恢复 = 读 `records[]` → 新 Run 的 ledger 从 `user.task` 起 append；跨 Run 用 `buildThreadContext(records)` 投影 slots。 |
| 大模型输入也是投影？ | **是**。不是把 JSONL 原文塞给模型，而是 `projectTraceRecords` + `compileUserPrompt`。 |
| 与 DSH 差在哪？ | **仅差投影目标的 API 形态**：DSH 常投影为 `messages[]`（user/assistant/tool role）；**当前代码**投影进 **一条 user 字符串**里的 `CONTEXT` 块。架构不变，换投影器即可对齐 role 数组。 |

### 1.1 三层命名（避免和 DSH 的「messages」混淆）

| 层 | 是什么 | 能否原地改 |
|----|--------|----------|
| **A. 事件 / JSONL `TraceRecord[]`** | SSOT | **否，只 append** |
| **B. 投影结果** | `ContextItem[]` → 格式化为 `CONTEXT` 文本（存 `ctx.messages`） | 每轮 **整段替换**（不写回 A） |
| **C. LLM 请求** | `system` + `user` + `tools[]` | 每轮由 B + snapshot/thread **重新 compile** |

DSH 里的「给模型的 messages 数组」≈ 本设计的 **B→C**；本仓库 **A** 与 DSH 的 event log / JSONL **同构**。

```text
  A. TraceRecord[]  (JSONL SSOT, append-only)
        │ projectTraceRecords (只读)
        ▼
  B. ContextItem[] → CONTEXT 文本  (ctx.messages，每轮重建)
        │ compileUserPrompt (+ snapshot, thread, taskMode)
        ▼
  C. chatCompletion(system, user, tools)
        │ append model.turn / tool.result
        └──────────► 回到 A
```

---

## 2. 冷启动（Cold Start）

从用户点 Run 到第一次 `chatCompletion` 之前。

```text
UI startRun
  → background run-supervisor
      → append run.context（一次：systemPrompt, tools, taskMode, skills, mcpNote）
      → runAgent(opts)
          → dom_snapshot
          → new AgentCtx
              → ledger.append(user.task)     // 账本第一条业务记录
              → 可选：threadContext 注入（跨 Run slots + PAGE EVIDENCE）
          → PreflightHook.runTaskPreflight  // 确定性 dom_read / extract / skill preflight
              → ledger.append(tool.result)  // 全文进账本
              → recordNote(PREFLIGHT/EVIDENCE) → ledger.append(run.note)
          → TaskHintHook.beforeStep（一次）
              → recordNote(GUIDANCE: …) → run.note
          → [若 intake] runIntakeLoop …
          → 进入热执行循环
```

**冷启动写入账本的典型记录：**

| type | 时机 | 模型是否直接看到 |
|------|------|------------------|
| `run.context` | Run 开始 | 不进每轮 prompt；审计/侧栏一份 |
| `user.task` | AgentCtx 构造 | 在 `compileUserPrompt` 的 `任务：` 块 |
| `tool.result` | Preflight 确定性工具 | 经投影 → `OBSERVATION:` |
| `run.note` | Preflight / TaskHint | 经投影 → `CONSTRAINT:` / `OBSERVATION:` |
| `run.mode` | 首次进模型循环 | 侧栏；不进 CONTEXT 除非另有投影 |

**冷启动不做的：**

- 不把上一 Run 的完整 JSONL 回灌模型  
- 不在账本里写「当前 system prompt 全文」（只在 `run.context` 存一份）

---

## 3. 热执行（Hot Loop）

每一轮模型步（`turn` = 0, 1, 2…）：

```text
for step in maxSteps:
  beforeStep     steer 注入 → user.steer；pause；TaskHint（仅首轮）
  refreshNetwork / 更新 snap（工具后）

  beforeModel    WorkingSetHook:
                   projected = projectTraceRecords(ledger.all())
                   ctx.messages = [projected.prompt]   // B 层整段替换
                   ctx.prompt.user = compileUser(...)    // C 层 user 组装

  chatCompletion(system, user, tools)

  afterModel     解析恰好一个 tool_call；协议失败 → run.recovery + retry

  append         model.turn { status, summary, io: { user, assistant, reasoning, toolCalls } }

  beforeTool       hooks：去重 / CSP / allowlist / NoProgress …

  execTurn         执行工具 → ledger.append(tool.result)  // arguments + data 全文

  afterTool        ToolStateHook：更新 gates、stepsWithoutNewObs

  terminal?        system_done → run.result；ask_user → run.ask + HITL
```

**热执行关键点：**

1. **`ledger` 只增不改** — `RunLedger.append` 无 update/delete。  
2. **`ctx.messages` 每轮丢弃重建** — 来自投影，不是账本子串。  
3. **`model.turn.io.user`** — 当轮发给模型的 user **全文快照**（审计用）；与下一轮的 user 可以完全不同（snapshot/DOM 变了）。  
4. **工具调用压缩** — 账本里 `tool.result` 保持完整；投影里 `safeToolObservation()` 只出一行摘要。

---

## 4. 文件格式（JSONL 真源）

### 4.1 行格式

- **NDJSON**：一行一个 JSON 对象，`\n` 分隔（`@naviforge/session` `stringifyJsonlLine`）。  
- **`schema: 1`** 固定；`validateTraceRecord` 在边界校验。  
- 导出样本：`naviforge/tests/message.txt`。

### 4.2 信封字段

```ts
{
  schema: 1,
  id: string,           // UUID，全库唯一；重复 id append 时丢弃（appendUniqueRecords）
  at: number,           // ms 时间戳
  runId: string,
  taskId?: string,
  turn?: number,        // 模型步 0-based；preflight/intake 无 turn
  channel: 'conversation' | 'trace' | 'telemetry',
  type: TraceRecordType,
  payload: { ... }      // 按 type 判别，不用 kind/title 当 SSOT
}
```

### 4.3 与「工具调用」相关的类型

| type | payload 要点 | 审计 | 投影 |
|------|--------------|------|------|
| `tool.result` | `{ tool, arguments, ok, data?, error? }` | **全文** | `safeToolObservation` 摘要 |
| `model.turn` | `{ status, summary, call?, io? }` | `io.toolCalls` 完整 | `step: Model act: …` |
| `run.note` | `{ text, topic? }` | 全文 | `GUIDANCE/CONSTRAINT/EVIDENCE/PREFLIGHT` 映射 |
| `context.compaction` | `{ summary, coveredRecordIds[], preservedConstraints[], openWork[] }` | 全文 | `compaction` + 钉住约束 |

**`tool.result` 示例（账本）：**

```json
{
  "type": "tool.result",
  "payload": {
    "tool": "web_search",
    "arguments": { "query": "loopx github" },
    "ok": true,
    "data": { "results": [{ "title": "…", "url": "…", "snippet": "…" }] }
  }
}
```

**投影后（模型 CONTEXT）：**

```text
OBSERVATION: web_search "loopx github"
1. loopx — https://github.com/…
   snippet…
STEP: web_search: completed
```

### 4.4 `run.context`（冷启动快照）

每 Run **一条**（钉住，cap 时不丢）：

```json
{
  "type": "run.context",
  "payload": {
    "systemPrompt": "…KERNEL + Skill L1…",
    "taskMode": "research",
    "tools": ["dom_click", "…", "mcp__host__fetch"],
    "skills": ["page-read", "…"],
    "skillGuidance": "…",
    "mcpNote": "…"
  }
}
```

不在每轮 `model.turn.io` 里重复 system。

---

## 5. 压缩体系（三层，都不删账本行）

| 层 | 机制 | 写入账本 | 影响下一 prompt |
|----|------|----------|-----------------|
| **L0** | 投影时 `clipLine` 截断 | 无 | observation ≤1200 字等 |
| **L1** | `projectTraceRecords` 合并/丢弃投影项 | 无 | 同 URL 的 `dom_read body` 只留最新 observation |
| **L2** | `context.compaction` **append 一条** | **是** | `coveredRecordIds` 内记录不再展开；summary 钉住 |

L2 触发：`WorkingSetHook` 估算 `system+user` ≥ `maxInputTokens`，或连续投影压力。

```text
压缩前 ledger:  [task, tool×20, model.turn×20, …]
压缩操作:       append context.compaction { coveredRecordIds: [全部旧 id] }
压缩后 ledger:  […旧行仍在…, compaction]   // 行数只增不减
下一投影:       compaction.summary + 未覆盖的新 tool.result
```

**跨 Run（Thread slots）** — 另一路径：`thread.memory` facts/constraints 合并，不是 Run ledger 的一部分。见 AGENT_SYSTEM_DESIGN §5.2。

---

## 6. 投影设计（L1 详表）

实现：`packages/runtime/src/working-set.ts` — `projectTraceRecords` / `projectRunNote` / `safeToolObservation`。

| ContextItem.kind | 来源 record | pinned | 合并规则 |
|------------------|-------------|--------|----------|
| `constraint` | `user.steer`, `run.ask`, `run.note`(GUIDANCE/CONSTRAINT/USER ANSWER…) | 通常 yes | 累积 |
| `observation` | `tool.result` 投影, `run.note`(EVIDENCE/PREFLIGHT) | 混合 | 同 key 保留最新 |
| `step` | `model.turn`, tool 完成一行 | no | 最近 6 条 |
| `error` | `run.error` | yes | 最近 4 条 |
| `compaction` | `context.compaction` | yes | 最新一条 |

**任务正文**只在 `compileUserPrompt` 的 `任务：` 出现，**不在** CONTEXT 里重复 `TASK:` 行。

**`run.note` 前缀语义** — 见 [CONTEXT_PROJECTION.md](./CONTEXT_PROJECTION.md)。

---

## 7. 内存中的读写与「能否修改」

### 7.1 Run 内（`AgentCtx`）

| 字段 | 读 | 写 | 是否 SSOT |
|------|----|----|-----------|
| `ledger` | `all()` | **仅 `append`（via `emit`）** | **是** |
| `messages` | `compileUser` | `WorkingSetHook` 每轮 `=` 替换 | 否（投影缓存） |
| `prompt.system/user` | `chatCompletion` | `beforeModel` / `syncFromAgent` | 否 |
| `tools` | API | `syncTools` / hooks | 否 |
| `gates` | hooks | hooks 更新 Set/Map | 否（运行时态） |

Hook 可以改 `ctx.messages` / `ctx.prompt`（见 `hooks.ts` 注释），**不得**改已 append 的 `TraceRecord.payload`。

### 7.2 Session 持久化（extension）

| 操作 | 行为 |
|------|------|
| `appendUniqueRecords` | 新 id → 追加；**同 id 忽略**（幂等） |
| `capSessionRecords` | 保留 `run.context` + `user.task` + 最近非 telemetry；**从数组移除旧行**（存储容量策略，不是改 payload） |
| 恢复会话 | 读 `records[]` → `viewRecord` 渲染；**不**把 records 当 LLM messages 数组 |

存储 cap **删掉的是 Session 数组里的引用**，与 DSH「逻辑上 append-only 审计」的折中：本地 chrome.storage 有上限。完整审计应依赖 JSONL 导出 / Host workspace。

### 7.3 与 DSH 设计对照

| 原则 | NaviForge |
|------|-----------|
| 事件 = JSONL 真源，只 append | ✅ `TraceRecord` / `RunLedger` |
| 模型输入 = 事件投影，非全文回灌 | ✅ `projectTraceRecords` + `compileUserPrompt` |
| 部分 event 不进模型 | ✅ `run.log` / `metrics.*`（telemetry）；未映射的 `run.note` |
| 一个 event 可投影多条 | ✅ 例：`user.steer` → 多条 `constraint`；`tool.result` → `observation` + `step` |
| 压缩不删事件 | ✅ `context.compaction` 只 append，`coveredRecordIds` 仅影响投影 |
| 冷启动从 JSONL 恢复 | ✅ Session.records → 新 Run / `buildThreadContext` |
| 投影目标形态 | **当前**：单 `user` 内嵌 CONTEXT；**可演进**：同一 SSOT 投影为 `messages[]` role 链（AGENT_SYSTEM_DESIGN §11.3 已留口子） |

**禁止**：原地改账本里某条 `payload`（破坏 SSOT）。  
**允许**：每轮重建 B/C——这是投影层刷新，不是改真源。

---

## 8. `compileUserPrompt` 块（C 层 user 组装）

按 `taskMode` 裁剪（`packages/runtime/src/prompt.ts`）：

| 块 | in_page | research | general |
|----|---------|----------|---------|
| `任务` / `TASK_MODE` | ✓ | ✓ | ✓ |
| `thread`（slots） | ✓ | ✓ | ✓ |
| snapshot body | ✓ | ✗（仅壳页提示） | ✗ |
| network | ✓ | ✓ | ✗ |
| `近期轨迹`（CONTEXT） | ✓ | ✓ | ✓ |

---

## 9. 观测与调试

| 想看什么 | 去哪 |
|----------|------|
| 完整工具参数/返回 | JSONL `tool.result` |
| 某轮模型实际输入 | `model.turn.io.user` |
| 冷启动 system | `run.context.systemPrompt` |
| 投影是否合理 | 对比 `tool.result` vs 同轮 `io.user` 里的 CONTEXT 段 |
| 死循环 | 查 `run.note` GUIDANCE 是否进 CONTEXT、`OBSERVATION` 是否空 |

---

## 10. 代码索引

| 模块 | 路径 |
|------|------|
| 账本 | `packages/runtime/src/ledger.ts` |
| 投影 | `packages/runtime/src/working-set.ts` |
| 每轮编译 | `packages/runtime/src/prompt.ts`, `agent-ctx.ts` |
| WorkingSetHook | `packages/runtime/src/hooks.ts` |
| 模型循环 | `packages/runtime/src/model-turns.ts` |
| 类型/JSONL | `packages/session/src/types.ts`, `trace.ts`, `jsonl.ts` |
| Session 追加/cap | `packages/session/src/session-records.ts` |
| Run 启动写 context | `apps/extension/src/lib/run-supervisor.ts` |
| 跨 Run 上下文 | `packages/session/src/thread-context.ts` |
