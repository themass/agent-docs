# Prime Agent：`/goal` 与 `/refine` 原理与示例

> **主指南**：[ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md) §6.6–6.7  
> **运行时桥接**：[RUNTIME_BRIDGES.md](./RUNTIME_BRIDGES.md)（`host.request` 中的 `goal.*` / `refine.run`）  
> **图解**：[compaction + Harness](./diagrams/prime-agent-compaction.html) · [Goals](./diagrams/prime-agent-goals.html)  
> **源码**：`packages/coding-agent/src/core/goals.ts` · `core/refinement/refinement.ts` · `AgentSession`

`/refine` 与 `/goal` 都在 **`AgentSession` 产品层**（不在 `pi-agent-core`），解决不同问题：

| | **`/refine`（Continual Harness）** | **`/goal`（Goals）** |
|--|-----------------------------------|----------------------|
| **解决什么** | 把会话里学到的 **可复用能力** 固化 | 让 Agent **跨多轮** 追同一总目标 |
| **类比** | 更新操作手册 / Skill / 记忆 | OKR / 任务单，不必每轮重复 |
| **改什么** | Harness：prompt 补充、memory、skill、subagent spec | `GoalState`：objective + 预算 + 进度 |
| **不改什么** | **Base system prompt 不可改** | 不改变 Pi 双环，只追加目标上下文 |

```text
┌─────────────────────────────────────────────────────────┐
│  AgentSession                                            │
│  /goal   →「现在要完成什么」→ GoalState → 每轮注入上下文   │
│  /refine →「以后怎么做得更好」→ Harness → 下轮 system 补充 │
│  Compaction →「历史太长」→ 压缩节点 → 短 messages[]       │
└─────────────────────────────────────────────────────────┘
```

---

## 一、`/refine` — Continual Harness 精炼

### 1.1 作用

在 **不覆写不可变 system prompt** 的前提下，根据轨迹证据 **小步更新**「持续 Harness」：

| `kind` | 存什么 |
|--------|--------|
| `prompt` | 补充行为策略（addendum） |
| `memory` | 事实、偏好、失败教训 |
| `skill` | 可重复 Python 过程（`reference` + `arguments`） |
| `subagent` | 可复用委派规格 |

**Compaction** 缩短 chat 历史；**Refine** 更新 Harness 寄存器；原始 JSONL 均保留可审计。

### 1.2 实现原理

```text
用户 /refine  或  cell 里 await refine.run()
        ↓
_planRefine（LLM 读轨迹 + 当前 Harness → RefinementProposal）
        ↓
等当前 turn 结束（与 compact 同套路，避免 turn 中途 abort 死锁）
        ↓
_applyRefine（写盘 + HarnessState + session custom entry）
        ↓
下一轮 buildSessionContext / system prompt 注入 Harness 概览
```

| 项 | 说明 |
|----|------|
| **存储** | `~/.prime/agent/harness/`（`refinements.jsonl`）+ JSONL `custom`（`prime-agent.refinement`） |
| **作用域** | 默认 **local**（本 session）；`global=True` 写跨 session 稳定经验 |
| **触发** | CLI `/refine`；Python `await refine.run()`（turn 边界 apply）；自动 `turn_interval` / `compact` 后可 `_maybeAutoRefine` |

### 1.3 示例：把重复踩坑写成 Harness

**场景**：修类型时，Agent **三次**都在「改了 shared 类型却只跑单包 test、全仓 `pnpm check` 仍失败」上翻车。希望 **后续轮次** 记得这条规矩。

**手动**：

```text
/refine 证据：三次在 packages/ui 改 ButtonProps 后只跑了 ui 单包 test，全仓 check 仍失败。请把「改 shared 类型后必须跑根目录 pnpm check」写成 memory。
```

**或在 cell 里**（turn 进行中，fire-and-forget）：

```python
await refine.run(
    instructions="Create a local memory: after editing shared types, run root pnpm check before claiming done."
)
# 立即返回；实际 apply 在当前 turn 结束后
```

**系统行为**：

1. `_planRefine` 产出例如一条 `create` / `kind: memory` 的 edit。
2. Turn 结束后 `_applyRefine` 写入 local harness + 审计 `refinements.jsonl`。
3. 下一轮 system 的 Harness 块出现该 memory；**base system prompt 不变**。
4. 若需所有未来 session 共享：`await refine.run(..., global=True)`（Python 侧用 `global_=True`）。

---

## 二、`/goal` — 跨 Turn 总目标

### 2.1 作用

设 **跨多轮持久** 的任务目标；配合 **Autonomous** 在预算内 **自动 follow-up**，直到 `complete` 或触顶。

### 2.2 实现原理

```text
用户 /goal [--budget N] <objective>
        ↓
GoalState（active + objective + tokenBudget…）
        ↓
JSONL custom entry（thread_goal_state，flush 立即可恢复）
        ↓
每轮 buildSessionContext 注入 <goal_context>
        ↓
runAgentLoop
        ↓
模型在 ipython 里 await goal.complete()（host.request goal.complete）
        ↓
Autonomous：goal 仍 active → 自动 admit continuation follow-up
```

`GoalState` 要点：

| 字段 | 含义 |
|------|------|
| `objective` | 目标文本（≤4000 字符） |
| `status` | `idle` / `active` / `paused` / `budget_limited` / `complete` / `error` |
| `tokenBudget` / `tokensUsed` | 可选 token 上限与已用 |
| `continuationsUsed` | Autonomous 续跑次数 |

| 入口 | 说明 |
|------|------|
| 用户 | `/goal`、`/goal clear\|pause\|resume\|status`、`--budget <tokens>` |
| 模型 | goal skill：`goal.get` / `goal.create` / `goal.complete` → `handleGoalHostRequest()` |
| 注入 | `createGoalContextMessage()` → `customType: goal_context` |

完成须模型在 cell 里 **`await goal.complete()`**，并对照 objective 审计，不能仅凭「感觉做完」。

### 2.3 示例：跨多轮修完类型错误

**场景**：monorepo 大量 TS 报错，希望 Agent **自己一轮轮修**，不必每轮重复「继续修类型错误」。

**命令**：

```text
/goal --budget 120000 修完整个仓库的 TypeScript 类型错误，并确保 pnpm check 通过
```

**系统行为**：

1. 写入 `GoalState`（`active` + objective + `tokenBudget`），落盘 JSONL。
2. 第一轮注入 `<goal_context>`：结束本轮 ≠ 任务完成。
3. Agent 在 ipython 里读文件、`pnpm check`、改类型；本轮结束 goal 仍 `active`。
4. **Autonomous**（若开启）：自动 admit continuation follow-up；若用了 `rlm.run()`，等子 agent quiet 后再续。
5. 全仓 `pnpm check` 通过后，模型执行 `await goal.complete()` → `status: complete`。
6. 若 `tokensUsed` 达 120000 → `budget_limited`，注入 budget 类 goal_context。

---

## 三、同一次任务里两者如何配合

以「修完全仓 TypeScript + check 通过」为例：

| 时刻 | `/goal` | `/refine` |
|------|---------|-----------|
| 开始时 | 设定总目标：修完 TS + check 通过 | — |
| 第 2 轮 | Autonomous 续跑，仍记得 objective | — |
| 第 3 轮踩坑 | 仍朝同一 objective 推进 | `refine.run()` 记下「改 shared 类型要全量 check」 |
| 第 4 轮起 | 继续修剩余文件 | system Harness 已有 memory，少犯同样错 |
| 结束时 | `goal.complete()` | Harness 留下可复用条目 |

**一句话**：**Goal = 这轮要办完什么事；Refine = 办完或办砸之后，下次怎么更聪明。**

---

## 四、与 Compaction 三分工

| 机制 | 问什么 | 存哪 | 模型何时看见 |
|------|--------|------|--------------|
| **Compaction** | 历史太长怎么办？ | JSONL `CompactionEntry` | 下次 `buildSessionContext` 截断 |
| **Harness / refine** | 可复用经验怎么沉淀？ | `~/.prime/agent/harness/` + custom | prompt 前合并 Harness 块 |
| **Goals** | 总任务是什么？ | `GoalState` custom entry | 每轮 `<goal_context>` |

---

## 五、延伸阅读

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE_GUIDE §6.6](./ARCHITECTURE_GUIDE.md#66-compaction-与-harness) | Compaction 与 Harness 流程图 |
| [ARCHITECTURE_GUIDE §6.7](./ARCHITECTURE_GUIDE.md#67-goals-与-autonomous) | Goals 与 Autonomous |
| [_archive/ARCHITECTURE_PART2 §4–5](./_archive/ARCHITECTURE_PART2.md#第4章continual-harness-与-refine) | refine / goal 深潜原文 |
| [EXTERNAL_ARTICLES_SYNTHESIS](./EXTERNAL_ARTICLES_SYNTHESIS.md) | 产品叙事与 `/refine` 校正 |
