# Context projection（JSONL 真源 → 模型上下文）

## 真源

`Session.records[]` / 导出的 JSONL 是 **唯一 append-only 账本**。每条 `TraceRecord` 只追加，不原地修改 payload。

## 投影链路

```text
TraceRecord[]  (JSONL SSOT)
    ├─ 侧栏 / 审计：recordView(type, payload)
    ├─ run.context：一次 systemPrompt、tools、taskMode、skills（trace）
    └─ 模型每轮：
         projectTraceRecords(ledger) → CONTEXT 文本 → compileUserPrompt(..., taskMode)
         model.turn.io：审计当轮 user / assistant / toolCalls 全文
```

压缩（`context.compaction`）只追加一条记录；`coveredRecordIds` 内的 audit 行不再展开为 step/observation，但 JSONL 原文保留。

## CONTEXT 项类型

| kind | 来源 | pinned | 说明 |
|------|------|--------|------|
| `constraint` | `user.steer`, `run.ask`, `run.note` 的 GUIDANCE/CONSTRAINT/USER ANSWER 等 | 通常 yes | 运行时纠偏，模型必须服从 |
| `observation` | `tool.result` 投影、`run.note` 的 EVIDENCE/PREFLIGHT | 混合 | 已收集证据 |
| `step` | `model.turn`, 工具完成摘要 | no | 最近 N 步 |
| `error` | `run.error` | yes | |
| `compaction` | `context.compaction` | yes | L2 摘要 |

任务正文只在 `compileUserPrompt` 的 `任务：` 块出现一次，**不**在 CONTEXT 重复 TASK 行。

## run.note 前缀（运行时 → 模型）

| 前缀 | 写入方 | 投影 kind | 含义 |
|------|--------|-----------|------|
| `GUIDANCE:` | TaskHintHook、DedupeObservationHook、协议恢复 | constraint (pinned) | 建议换策略，软约束 |
| `CONSTRAINT:` | 重复工具硬闸 | constraint (pinned) | 必须 system_done 或换工具 |
| `EVIDENCE:` | Preflight、去重跳过时附带 | observation (pinned) | 已有页面/搜索结果摘要 |
| `PREFLIGHT:` | 确定性 preflight | observation | 预读/预提取记录 |

`tool.result.data` 全文仅在 JSONL 审计；模型侧只见 `safeToolObservation` 摘要。

## 任务模式（taskMode）

| 模式 | user prompt |
|------|-------------|
| `in_page` | 完整 snapshot + network |
| `research` | 壳页 URL/标题 + 无 snapshot body + network |
| `general` | 壳页提示 + 无 network |
| `list_detail` | 同 in_page |

见 `resolveTaskMode()`、`packages/runtime/src/prompt.ts`。
