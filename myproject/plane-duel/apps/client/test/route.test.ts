import { describe, it, expect } from 'vitest'
import type { GameView, RuleSet, TableView, TableResult } from '@plane-duel/shared'
import { createGameStore } from '../src/net/store'
import { leaveOnRoomClosed, routeView } from '../src/route'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const mkTable = (over: Partial<TableView> = {}): TableView => ({
  roomCode: '123456',
  kind: 'match',
  capacity: 2,
  rules,
  rulesVersion: 0,
  listed: false,
  hostId: null,
  phase: 'inGame',
  seats: [
    { seat: 0, playerId: 'me', nickname: '我', ready: false, connected: true, bot: false },
    { seat: 1, playerId: 'op', nickname: '他', ready: false, connected: true, bot: false },
  ],
  lastResult: null,
  ...over,
})

const forfeit: TableResult = {
  reason: 'forfeit',
  botIds: [],
  ranking: [
    { playerId: 'me', rank: 1, eliminatedRound: null, hits: 0 },
    { playerId: 'op', rank: 2, eliminatedRound: null, hits: 0 },
  ],
}

const game: GameView = {
  mode: 'duel',
  phase: 'playing',
  deadlineAt: 100,
  turn: 'me',
  round: null,
  you: { planes: [{ row: 3, col: 3 }], planesDestroyed: 0, alive: true, shots: [], incoming: [], submitted: false, pendingShot: null },
  others: [{ playerId: 'op', connected: true, alive: true, planesDestroyed: 0, submitted: false }],
}

const inGame = () => {
  const s = createGameStore()
  s.apply({ type: 'ready', playerId: 'me', token: 't', nickname: '我' })
  s.apply({ type: 'state', table: mkTable(), game: structuredClone(game) })
  return s
}

describe('routeView', () => {
  it('评审 C1：对手中途离开、匹配房关闭 → 留下的人看到结算页，而不是卡在对局里', () => {
    const s = inGame()
    s.apply({ type: 'gameOver', result: forfeit })
    s.apply({ type: 'tableState', table: mkTable({ phase: 'waiting', lastResult: forfeit, seats: [mkTable().seats[0]!, null] }) })
    s.apply({ type: 'roomClosed' })
    expect(s.state.game!.phase).toBe('finished')
    expect(routeView(s.state, null)).toBe('result')
    expect(leaveOnRoomClosed(s.state)).toBe(false)
  })

  it('评审 I5：关闭结算页（dismissResult）后进入等候室', () => {
    const s = inGame()
    s.apply({ type: 'gameOver', result: forfeit })
    s.apply({ type: 'tableState', table: mkTable({ kind: 'friend', phase: 'waiting', lastResult: forfeit }) })
    expect(routeView(s.state, null)).toBe('result')
    s.dismissResult()
    expect(s.state.resultDismissed).toBe(true)
    expect(routeView(s.state, null)).toBe('waiting')
  })

  it('评审 I5：不在 lastResult.ranking 里的人（上一局之后才入座）直接看等候室', () => {
    const s = createGameStore()
    s.apply({ type: 'ready', playerId: 'new', token: 't', nickname: '新人' })
    s.apply({ type: 'tableState', table: mkTable({ kind: 'friend', phase: 'waiting', lastResult: forfeit }) })
    expect(routeView(s.state, null)).toBe('waiting')
  })

  it('被踢后（kicked，table=null）回到大厅', () => {
    const s = createGameStore()
    s.apply({ type: 'ready', playerId: 'me', token: 't', nickname: '我' })
    s.apply({ type: 'tableState', table: mkTable({ kind: 'friend', phase: 'waiting' }) })
    expect(routeView(s.state, null)).toBe('waiting')
    s.apply({ type: 'kicked', roomCode: '123456' })
    expect(s.state.kicked).toBe(true)
    expect(routeView(s.state, null)).toBe('lobby')
    // 在专区里被踢：回到专区而不是牌桌
    expect(routeView(s.state, 3)).toBe('zone')
  })

  it('房间关闭且看不到结算页 → 回大厅', () => {
    const s = createGameStore()
    s.apply({ type: 'ready', playerId: 'new', token: 't', nickname: '新人' })
    s.apply({ type: 'tableState', table: mkTable({ phase: 'waiting', lastResult: forfeit }) })
    s.apply({ type: 'roomClosed' })
    expect(leaveOnRoomClosed(s.state)).toBe(true)
    const s2 = createGameStore()
    s2.apply({ type: 'tableState', table: mkTable({ phase: 'waiting' }) })
    s2.apply({ type: 'roomClosed' })
    expect(leaveOnRoomClosed(s2.state)).toBe(true)
  })

  it('其余路由：无牌桌 → lobby / zone；对局中按 game.phase', () => {
    const s = createGameStore()
    expect(routeView(s.state, null)).toBe('lobby')
    expect(routeView(s.state, 3)).toBe('zone')
    const g = inGame()
    expect(routeView(g.state, null)).toBe('play')
    g.state.game!.phase = 'placing'
    expect(routeView(g.state, null)).toBe('place')
    g.state.game = null
    expect(routeView(g.state, null)).toBe('waiting')
  })
})
