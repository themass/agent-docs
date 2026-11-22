/**
 * P6 手感：震动反馈（spec 无专节——纯客户端增强）。
 * navigator.vibrate 只在 Android Chrome/WebView 生效；iOS 全系不支持，静默降级。
 * 纯函数 vibratePlan 把"事件→模式"解耦出来可测，DOM 层只做转发。
 */

export type HapticEvent =
  | 'fire' // 开炮
  | 'miss' // 未中（轻）
  | 'body' // 命中机身（中）
  | 'head' // 击落机头（重）
  | 'inbound' // 被打中（我方视角）
  | 'win'
  | 'lose'
  | 'tick' // 倒计时最后 3 秒
  | 'ui' // 普通按钮

/** 毫秒模式数组，喂给 navigator.vibrate */
export function vibratePlan(event: HapticEvent): number[] {
  switch (event) {
    case 'fire':
      return [12]
    case 'miss':
      return [8]
    case 'body':
      return [18]
    case 'head':
      return [40, 30, 60]
    case 'inbound':
      return [25]
    case 'win':
      return [30, 40, 30]
    case 'lose':
      return [80]
    case 'tick':
      return [6]
    case 'ui':
      return [5]
  }
}

export type HapticsHandle = { vibrate: (e: HapticEvent) => void }

export function createHaptics(nav: { vibrate?: (p: number[]) => boolean } | null = null): HapticsHandle {
  const target = nav ?? (typeof navigator !== 'undefined' ? (navigator as unknown as { vibrate?: (p: number[]) => boolean }) : null)
  return {
    vibrate(e) {
      try {
        target?.vibrate?.(vibratePlan(e))
      } catch {
        // 权限/不支持：静默
      }
    },
  }
}
