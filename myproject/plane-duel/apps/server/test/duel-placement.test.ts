import { describe, it, expect } from 'vitest'
import type { RuleSet } from '@plane-duel/shared'
import { DuelEngine } from '../src/duel-engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const mkRoom = () => new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0 })

describe('对局生命周期（摆放）', () => {
  it('初始 phase 是 placing，mode 是 duel', () => {
    const r = mkRoom()
    expect(r.phase).toBe('placing')
    expect(r.mode).toBe('duel')
    expect(r.result).toBeNull()
  })

  it('非成员的消息被忽略', () => {
    const r = mkRoom()
    expect(r.handle('stranger', { type: 'fire', row: 1, col: 1 }, 0)).toEqual([])
  })

  it('双方都摆好后进入 playing', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    expect(r.phase).toBe('placing')
    r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    expect(r.phase).toBe('playing')
  })

  it('合法摆放回 planeAccepted', () => {
    const r = mkRoom()
    const out = r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    expect(out).toContainEqual({
      to: 'a',
      msg: { type: 'planeAccepted', planes: [{ row: 2, col: 2 }] },
    })
  })

  it('越界摆放回 error 且不生效', () => {
    const r = mkRoom()
    const out = r.handle('a', { type: 'placePlane', planes: [{ row: 0, col: 0 }] }, 0)
    expect(out[0]!.msg).toMatchObject({ type: 'error', code: 'INVALID_PLACEMENT' })
    // 仍然可以重新摆
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    expect(r.phase).toBe('placing')
  })

  it('摆放阶段可以重摆', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    const out = r.handle('a', { type: 'placePlane', planes: [{ row: 3, col: 3 }] }, 0)
    expect(out).toContainEqual({
      to: 'a',
      msg: { type: 'planeAccepted', planes: [{ row: 3, col: 3 }] },
    })
  })

  it('进入 playing 的 phaseChanged 带上先手（客户端需要知道谁先开炮）', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    const out = r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    const pc = out.find((o) => o.msg.type === 'phaseChanged')!.msg as any
    expect(pc.phase).toBe('playing')
    expect(pc.turn).toBe(r.view('a').turn)
  })

  it('对方的机头永远不出现在我的视图里', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    const v = r.view('a')
    expect(JSON.stringify(v.others)).not.toContain('7')
    expect(v.you.planes).toEqual([{ row: 2, col: 2 }])
  })

  it('view：duel 形状（turn 有值、round 为 null、others 长度 1）', () => {
    const r = new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    r.handle('a', { type: 'fire', row: 6, col: 6 }, 10)
    const v = r.view('a')
    expect(v.mode).toBe('duel')
    expect(v.turn).toBe('b')
    expect(v.round).toBeNull()
    expect(v.others).toEqual([{ playerId: 'b', connected: true, alive: true, planesDestroyed: 0, submitted: false }])
    expect(v.you.shots).toEqual([{ targetId: 'b', row: 6, col: 6, result: 'body', planeId: 'p0' }])
    expect(r.view('b').you.incoming).toEqual([{ by: 'a', row: 6, col: 6, result: 'body', planeId: 'p0' }])
  })
})
