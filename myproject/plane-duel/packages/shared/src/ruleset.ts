// 对局规则参数、预设与校验。纯数据与纯函数；不得 import './types'（types.ts 会反向依赖本文件）。

export const BOARD_MIN = 6
export const BOARD_MAX = 16
export const PLANE_HARD_MAX = 6
export const MAX_DENSITY = 0.3
export const TURN_SECONDS = [10, 15, 20, 30, 45, 60] as const

export type TurnSeconds = (typeof TURN_SECONDS)[number]
export type RuleSet = { boardSize: number; planeCount: number; turnSeconds: TurnSeconds; hintAllowed: boolean }
export type Capacity = 2 | 3 | 4
export type PresetId = 'beginner' | 'standard' | 'advanced' | 'expert'

export const PRESETS: Readonly<Record<PresetId, RuleSet>> = {
  beginner: { boardSize: 8, planeCount: 1, turnSeconds: 30, hintAllowed: true },
  standard: { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true },
  advanced: { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false },
  expert: { boardSize: 14, planeCount: 3, turnSeconds: 15, hintAllowed: false },
}

export const PRESET_LABELS: Readonly<Record<PresetId, string>> = {
  beginner: '入门',
  standard: '标准',
  advanced: '进阶',
  expert: '高手',
}

/** 给定边长下允许的最大飞机数：每架占 9 格，总占比不超过 MAX_DENSITY。 */
export function maxPlanes(boardSize: number): number {
  return Math.min(PLANE_HARD_MAX, Math.floor((MAX_DENSITY * boardSize * boardSize) / 9))
}

type ValidateResult =
  | { ok: true; rules: RuleSet }
  | { ok: false; reason: 'shape' | 'boardSize' | 'planeCount' | 'turnSeconds' }

/**
 * 校验未知输入是否为合法 RuleSet，返回只含四个字段的新对象。
 * 'shape'：不是普通对象、缺少任一字段，或 hintAllowed 不是布尔值。
 * 其余字段类型或取值错误时，报告该字段自己的原因。检查顺序：shape → boardSize → planeCount → turnSeconds。
 */
export function validateRuleSet(input: unknown): ValidateResult {
  if (typeof input !== 'object' || input === null || Array.isArray(input)) return { ok: false, reason: 'shape' }
  const o = input as Record<string, unknown>
  if (!('boardSize' in o && 'planeCount' in o && 'turnSeconds' in o && 'hintAllowed' in o)) {
    return { ok: false, reason: 'shape' }
  }
  const { boardSize, planeCount, turnSeconds, hintAllowed } = o
  if (typeof hintAllowed !== 'boolean') return { ok: false, reason: 'shape' }
  if (typeof boardSize !== 'number' || !Number.isInteger(boardSize) || boardSize < BOARD_MIN || boardSize > BOARD_MAX) {
    return { ok: false, reason: 'boardSize' }
  }
  if (typeof planeCount !== 'number' || !Number.isInteger(planeCount) || planeCount < 1 || planeCount > maxPlanes(boardSize)) {
    return { ok: false, reason: 'planeCount' }
  }
  if (typeof turnSeconds !== 'number' || !(TURN_SECONDS as readonly number[]).includes(turnSeconds)) {
    return { ok: false, reason: 'turnSeconds' }
  }
  return { ok: true, rules: { boardSize, planeCount, turnSeconds: turnSeconds as TurnSeconds, hintAllowed } }
}

/** 布阵阶段时长（秒）：30 + 15 × 飞机数。 */
export function placeSeconds(rules: RuleSet): number {
  return 30 + 15 * rules.planeCount
}

/** 飞机格数占棋盘总格数的比例。 */
export function planeDensity(rules: RuleSet): number {
  return (rules.planeCount * 9) / (rules.boardSize * rules.boardSize)
}

export function isCapacity(n: unknown): n is Capacity {
  return n === 2 || n === 3 || n === 4
}
