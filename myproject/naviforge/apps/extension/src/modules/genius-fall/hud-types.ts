/** Compact payload for the on-page HUD (content script safe). */
export type GeniusFallHudState = {
  ok: boolean
  loading?: boolean
  error?: string
  label: string
  spentUsd: number | null
  limitUsd: number | null
  percentUsed: number | null
  remainingUsd: number | null
  cycleEnd: string | null
  teamPercent: number | null
  updatedAt: string | null
  /** Shown in YOU ring when percent is unknown but spend exists. */
  personalDisplay?: 'percent' | 'money'
}

export type GeniusFallHudPrefs = {
  x: number
  y: number
  collapsed: boolean
  /** Visual scale 0.55 – 1.35 */
  scale: number
  /** Vertical scale 0.65 – 1.35 */
  heightScale: number
  /** Background hex color */
  bgColor: string
  /** Background opacity 0.2 – 1 */
  bgOpacity: number
  /** HUD headline (user-facing). */
  title: string
}

export const DEFAULT_HUD_PREFS: GeniusFallHudPrefs = {
  x: 24,
  y: 96,
  collapsed: false,
  scale: 0.72,
  heightScale: 0.82,
  bgColor: '#2c2824',
  bgOpacity: 0.9,
  title: '天才程序员陨落倒计时',
}

export const HUD_BASE_WIDTH = 296
