/**
 * 评审发现的对局生命周期问题回归测试（C1, I1, I2, I5, I6）。
 * 重连快照（state）由 Table 发送；引擎只保证 view() 反映恢复后的状态。
 */
import { describe, it, expect } from 'vitest'
import type { RuleSet } from '@plane-duel/shared'
import { DuelEngine } from '../src/duel-engine'
import type { Outbound } from '../src/engine'

const T = 1_000_000
const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const fresh = () => new DuelEngine({ rules, playerIds: ['a', 'b'], rng: () => 0, now: T })

const playing = () => {
  const r = fresh()
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, T)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, T)
  return r // 先手 a
}

const types = (out: Outbound[], to: string) => out.filter((o) => o.to === to).map((o) => o.msg.type)
const msg = (out: Outbound[], to: string, type: string) =>
  out.find((o) => o.to === to && o.msg.type === type)?.msg as any
const winner = (go: any) => go.result.ranking[0].playerId

describe('C1：恰好在宽限到期时重连（tick 尚未运行）', () => {
  it('判掉线方负，而不是判掉线方胜', () => {
    const r = playing()
    r.setConnected('a', false, T + 1000)
    const out = r.setConnected('a', true, T + 31000) // 恰好 30 秒
    expect(r.phase).toBe('finished')
    const go = msg(out, 'b', 'gameOver')
    expect(winner(go)).toBe('b')
    expect(go.result.reason).toBe('forfeit')
    expect(types(out, 'a')).toContain('gameOver') // 重连方能看到结局
    expect(types(out, 'a')).not.toContain('state') // 快照由 Table 发
    expect(r.view('a').phase).toBe('finished')
    expect(r.tick(T + 31200)).toEqual([]) // 不会再判一次
  })
})

describe('I5/C3：在线一方能看到暂停与恢复', () => {
  it('掉线时在线方收到 phaseChanged paused', () => {
    const r = playing()
    const out = r.setConnected('b', false, T + 1000)
    expect(msg(out, 'a', 'phaseChanged')).toMatchObject({ phase: 'paused', deadlineAt: null })
    expect(types(out, 'a')).toContain('presence')
    expect(r.view('a')).toMatchObject({ phase: 'paused', deadlineAt: null })
  })

  it('恢复时双方收到带顺延 deadline 与 turn 的 phaseChanged', () => {
    const r = playing()
    const before = r.view('a').deadlineAt!
    r.setConnected('b', false, T + 1000)
    const out = r.setConnected('b', true, T + 11000)
    for (const p of ['a', 'b']) {
      expect(msg(out, p, 'phaseChanged')).toMatchObject({ phase: 'playing', deadlineAt: before + 10000, turn: 'a' })
    }
  })
})

describe('I1：双方都掉线', () => {
  it('只有一方回来时仍保持暂停、不代打', () => {
    const r = playing()
    r.setConnected('a', false, T + 1000)
    r.setConnected('b', false, T + 2000)
    r.setConnected('a', true, T + 3000)
    expect(r.phase).toBe('paused')
    expect(r.tick(T + 25000)).toEqual([])
  })

  it('第二个人回来时恢复，view 反映恢复后的阶段与 deadline', () => {
    const r = playing()
    const before = r.view('b').deadlineAt!
    r.setConnected('a', false, T + 1000)
    r.setConnected('b', false, T + 2000)
    r.setConnected('a', true, T + 3000)
    const out = r.setConnected('b', true, T + 4000)
    expect(r.phase).toBe('playing')
    expect(types(out, 'b')).toContain('phaseChanged')
    expect(types(out, 'b')).not.toContain('state')
    expect(r.view('b')).toMatchObject({ phase: 'playing', deadlineAt: before + 3000, turn: 'a' })
  })

  it('都超时未回：先掉线的一方判负', () => {
    const r = playing()
    r.setConnected('b', false, T + 1000)
    r.setConnected('a', false, T + 2000)
    const out = r.tick(T + 31000)
    const go = msg(out, 'a', 'gameOver')
    expect(winner(go)).toBe('a')
    expect(go.result.reason).toBe('forfeit')
  })

  it('各自宽限独立计算：后掉线者未超时时不判', () => {
    const r = playing()
    r.setConnected('b', false, T + 1000)
    r.setConnected('a', false, T + 20000)
    r.setConnected('a', true, T + 25000)
    // b 已断 30 秒 → b 负
    const out = r.tick(T + 31000)
    expect(winner(msg(out, 'a', 'gameOver'))).toBe('a')
  })
})

describe('I2：未检测到断开就重连（半开连接）', () => {
  it('已在线时再 setConnected(true) 不产生消息、不改变状态', () => {
    const r = playing()
    const before = JSON.stringify(r.view('a'))
    const out = r.setConnected('a', true, T + 500)
    expect(out).toEqual([])
    expect(r.phase).toBe('playing')
    expect(JSON.stringify(r.view('a'))).toBe(before)
  })
})

describe('I6：对局中途主动离开 = 认输', () => {
  it('playing 时离开：对手获胜', () => {
    const r = playing()
    const out = r.handle('a', { type: 'leaveRoom' }, T + 500)
    expect(r.phase).toBe('finished')
    const go = msg(out, 'b', 'gameOver')
    expect(winner(go)).toBe('b')
    expect(go.result.reason).toBe('forfeit')
    expect(r.result).toEqual(go.result)
  })

  it('placing 时离开：同样判负', () => {
    const r = fresh()
    const out = r.handle('b', { type: 'leaveRoom' }, T + 500)
    const go = msg(out, 'a', 'gameOver')
    expect(winner(go)).toBe('a')
    expect(go.result.reason).toBe('forfeit')
  })

  it('paused 时离开：同样判负', () => {
    const r = playing()
    r.setConnected('b', false, T + 100)
    const out = r.handle('a', { type: 'leaveRoom' }, T + 500)
    expect(winner(msg(out, 'b', 'gameOver'))).toBe('b')
    expect(r.phase).toBe('finished')
  })
})
