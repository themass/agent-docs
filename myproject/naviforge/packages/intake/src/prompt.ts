import type { IntakeMode } from './types.js'
import { MAX_QUESTIONS_PER_ROUND } from './types.js'

const INTAKE_CORE = `

## 需求澄清阶段（intake）
你处于**动手前评估**阶段：禁止调用任何 DOM / 页面 / workspace / 网络写操作。
本轮目标：**判断**是否必须向用户提问；不是默认提问。

### 决策（二选一，必须调用其一）
1. **system_begin_task** — 任务已可安全执行，或可用合理默认假设执行（在 summary / assumptions 写清）。
2. **system_clarify** — 仅当缺失信息会导致**错误范围、不可逆操作或明显跑偏**时才问；每轮最多 ${MAX_QUESTIONS_PER_ROUND} 题。

### 何时直接 begin（勿 clarify）
- 打招呼、寒暄、试探性问候（无具体任务）
- 用户已写清目标、范围、对象（含「当前页」「总结本页」等）
- 开放式研究/对比类任务，默认在当前浏览器上下文内执行即可
- 任何可用行业常识或页面上下文合理补全、且风险低的缺口
- THREAD 已有 GOAL / CONVERSATION / LAST OUTCOME（含 timeout、error、recovery）：用户只说「继续/continue/retry/接着」时视为**同一任务续跑**；直接 system_begin_task，summary 引用 THREAD 中的目标与中断原因，**禁止**追问「要继续什么」

### 何时必须 clarify
- 多种互斥执行路径且无法从任务推断（例如「删掉」但未指明对象）
- 涉及付费、提交、删除、对外发送等不可逆/高风险动作且目标不明
- 用户明确要求你做选择，但未给出偏好

### 提问质量
- 不要重复问用户已在任务里写清的内容
- 每题优先 2–4 个可选项（kind=single/multi），保留「其他」（kind=text 或 options 含 other）`

const INTAKE_MODE_AUTO = `

### 模式：auto（智能判断）
默认 **system_begin_task**；只有真正ambiguous时才 system_clarify。`

const INTAKE_MODE_ALWAYS = `

### 模式：always（必经确认）
任务必经本阶段。若存在任何可能影响执行路径的歧义，**优先** system_clarify 至少 1 题；无歧义则 system_begin_task 并列出关键假设。`

export const INTAKE_SYSTEM_APPEND = `${INTAKE_CORE}${INTAKE_MODE_AUTO}`

export function composeIntakeSystemPrompt(baseKernel: string, mode: IntakeMode = 'auto'): string {
  const modeAppend = mode === 'always' ? INTAKE_MODE_ALWAYS : INTAKE_MODE_AUTO
  return `${baseKernel.trim()}${INTAKE_CORE}${modeAppend}`
}

export function compileIntakeUserPrompt(
  task: string,
  priorAnswers: string[],
  threadContext?: { memory: string; conversation: string }
): string {
  const history =
    priorAnswers.length > 0
      ? `已确认信息：\n${priorAnswers.join('\n')}`
      : '已确认信息：（尚无）'
  const thread =
    threadContext &&
    ((threadContext.memory.trim() && threadContext.memory !== '(none)') ||
      (threadContext.conversation.trim() && threadContext.conversation !== '(none)'))
      ? `THREAD（跨轮事实；当前输入优先）：\nMEMORY:\n${threadContext.memory}\n\nCONVERSATION:\n${threadContext.conversation}`
      : ''
  return [`用户任务：\n${task.trim()}`, thread, history, '请评估是否需要向用户澄清；若不需要，直接 system_begin_task。']
    .filter(Boolean)
    .join('\n\n')
}
