import { describe, it, expect } from 'vitest'
import type { RuleSet } from '@plane-duel/shared'
import { DuelEngine } from '../src/duel-engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const playing = () => {
  const r = new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  return r
}

describe('断线', () => {
  it('断线进入 paused 并通知对手', () => {
    const r = playing()
    const out = r.setConnected('b', false, 1000)
    expect(r.phase).toBe('paused')
    expect(out).toContainEqual({ to: 'a', msg: { type: 'presence', playerId: 'b', connected: false } })
    expect(r.view('a').others[0]!.connected).toBe(false)
  })

  it('暂停期间不代打（spec §二）', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    // 26000 已过回合 deadline(20000)，仍在 30 秒宽限内（1000+30000=31000）
    // ⇒ 若是普通回合超时会代打一炮，暂停时必须什么都不做
    expect(r.tick(26000)).toEqual([])
  })

  it('暂停期间对手不能开炮', () => {
    const r = playing()
    const turn = r.view('a').turn!
    r.setConnected(turn === 'a' ? 'b' : 'a', false, 1000)
    const out = r.handle(turn, { type: 'fire', row: 1, col: 1 }, 1500)
    expect(out[0]!.msg).toMatchObject({ type: 'error', code: 'PAUSED' })
  })

  it('重连恢复原阶段并顺延 deadline', () => {
    const r = playing()
    const before = r.view('a').deadlineAt!
    r.setConnected('b', false, 1000)
    const out = r.setConnected('b', true, 11000) // 断了 10 秒
    expect(r.phase).toBe('playing')
    expect(out).toContainEqual({ to: 'a', msg: { type: 'presence', playerId: 'b', connected: true } })
    expect(r.view('a').deadlineAt).toBe(before + 10000)
  })

  it('超过 30 秒未回判负', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    const out = r.tick(1000 + 30000)
    expect(r.phase).toBe('finished')
    const go = out.find((o) => o.msg.type === 'gameOver')!.msg as any
    expect(go.result.ranking[0].playerId).toBe('a')
    expect(go.result.reason).toBe('forfeit')
  })

  it('宽限期内重连不判负（Review Focus #3 边界）', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    const out = r.setConnected('b', true, 30999) // 只差 1 毫秒
    expect(r.phase).toBe('playing')
    expect(out.some((o) => o.msg.type === 'gameOver')).toBe(false)
  })

  it('恰好到 30 秒时先 tick 则判负，之后重连无效（Review Focus #3）', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    r.tick(31000) // 判负先生效
    expect(r.phase).toBe('finished')
    const out = r.setConnected('b', true, 31000)
    expect(out.some((o) => o.msg.type === 'gameOver')).toBe(false)
    expect(r.phase).toBe('finished')
  })

  it('摆放阶段断线也冻结', () => {
    const r = new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
    r.setConnected('a', false, 0)
    expect(r.phase).toBe('paused')
    // 若未暂停，宽限内 tick 到摆放 deadline 附近也不能自动落子
    expect(r.tick(29000)).toEqual([])
  })

  it('摆放阶段重连顺延摆放 deadline', () => {
    const r = new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
    r.setConnected('a', false, 1000)
    const out = r.setConnected('a', true, 21000)
    expect(r.phase).toBe('placing')
    expect(r.view('a').deadlineAt).toBe(45000 + 20000)
    expect(out.find((o) => o.to === 'b' && o.msg.type === 'phaseChanged')?.msg).toMatchObject({
      phase: 'placing',
      deadlineAt: 65000,
    })
    expect(r.tick(64999)).toEqual([])
    expect(r.tick(65000).some((o) => o.msg.type === 'planeAccepted')).toBe(true)
  })
})
