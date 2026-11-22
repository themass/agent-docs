/**
 * 顶层路由决策（纯函数，便于单测）：App.vue 只按返回值选择视图。
 */
import type { Capacity } from '@plane-duel/shared'
import type { GameState } from './net/store'

export type View = 'lobby' | 'zone' | 'waiting' | 'result' | 'place' | 'play'

type RouteState = Pick<GameState, 'table' | 'game' | 'playerId' | 'resultDismissed' | 'kicked'>

/** 结算页可见：刚打完一局、本人在排名里、尚未关闭结算页。 */
export function resultVisible(s: RouteState): boolean {
  const t = s.table
  if (t === null || t.phase !== 'waiting' || t.lastResult === null || s.resultDismissed) return false
  return t.lastResult.ranking.some((r) => r.playerId === s.playerId)
}

export function routeView(s: RouteState, zone: Capacity | null): View {
  const t = s.table
  // 被踢后 store 已复位（table=null），这里显式锁定：绝不回牌桌
  if (s.kicked || t === null) return zone === null ? 'lobby' : 'zone'
  if (t.phase === 'waiting') return resultVisible(s) ? 'result' : 'waiting'
  if (s.game === null) return 'waiting'
  return s.game.phase === 'placing' ? 'place' : 'play'
}

/** 收到 roomClosed：正在看结算页就留在那里（只剩"返回大厅"）；否则直接回大厅。 */
export function leaveOnRoomClosed(s: RouteState): boolean {
  return !resultVisible(s)
}
