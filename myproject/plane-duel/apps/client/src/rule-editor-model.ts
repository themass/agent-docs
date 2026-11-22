/**
 * 规则编辑器的纯逻辑（spec §19.3）。.vue 只负责绑定控件，判断都在这里，因此可以单测。
 */

import { PRESETS, maxPlanes, planeDensity, type Capacity, type PresetId, type RuleSet } from '@plane-duel/shared'

/** 占比低于这个值就提示"对局会比较长"。 */
export const SPARSE_DENSITY = 0.05

/**
 * 改边长后飞机数可能超过新上限：降到上限，其余字段原样保留。
 * 反过来（升高上限）不做任何事——编辑器不会替玩家加飞机。
 */
export function clampPlanes(rules: RuleSet): RuleSet {
  const max = maxPlanes(rules.boardSize)
  if (rules.planeCount <= max) return rules
  return { ...rules, planeCount: max }
}

/** 等候室与专区卡片上的一行摘要："10×10 · 1 架 · 20 秒 · 可用提示" */
export function ruleSummary(rules: RuleSet): string {
  const hint = rules.hintAllowed ? '可用提示' : '无提示'
  return `${rules.boardSize}×${rules.boardSize} · ${rules.planeCount} 架 · ${rules.turnSeconds} 秒 · ${hint}`
}

/** 占比 < 5% 的规则不禁止，只是提醒一句。 */
export function densityWarning(rules: RuleSet): string | null {
  return planeDensity(rules) < SPARSE_DENSITY ? '棋盘很空，对局会比较长' : null
}

/** 一键创建好友房：标准档、默认公开到大厅列表（spec §20.6）。 */
export function defaultCreateRoom(capacity: Capacity): {
  type: 'createRoom'
  capacity: Capacity
  rules: RuleSet
  listed: boolean
} {
  return { type: 'createRoom', capacity, rules: PRESETS.standard, listed: true }
}

/** 人机练习请求（spec §20.4）：档位即电脑难度。 */
export function practiceRequest(capacity: Capacity, preset: PresetId): {
  type: 'createPractice'
  capacity: Capacity
  preset: PresetId
} {
  return { type: 'createPractice', capacity, preset }
}
