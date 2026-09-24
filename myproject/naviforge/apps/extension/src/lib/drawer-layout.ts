export const DRAWER_WIDTH_MIN = 480
export const DRAWER_WIDTH_DEFAULT = 920

/** Clamp toolkit drawer width to viewport (right-side panel). */
export function clampDrawerWidth(width: number, viewportWidth: number): number {
  const max = Math.max(DRAWER_WIDTH_MIN, viewportWidth)
  return Math.min(Math.max(width, DRAWER_WIDTH_MIN), max)
}
