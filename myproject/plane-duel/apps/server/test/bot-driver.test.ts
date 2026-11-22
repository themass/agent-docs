import { describe, it, expect } from 'vitest'
import { cellKey, cellsOfPlane, isPlacementValid, type GameView, type RuleSet } from '@plane-duel/shared'
import { BOT_DEADLINE_MARGIN_MS, BOT_THINK_MS, BotDriver } from '../src/bot/driver'
import { mulberry32 } from '../../../packages/shared/test/helpers'

const RULES: RuleSet = { boardSize: 10, planeCount: 2, turnSeconds: 20, hintAllowed: true }
const BOT = 'bot_1'

type V = Partial<Omit<GameView, 'you'>> & { you?: Partial<GameView['you']> }

function view(o: V = {}): GameView {
  const { you, ...rest } = o
  return {
    mode: 'duel',
    phase: 'playing',
    deadlineAt: null,
    turn: BOT,
    round: null,
    you: {
      planes: [{ row: 3, col: 3 }],
      planesDestroyed: 0,
      alive: true,
      shots: [],
      incoming: [],
      submitted: false,
      pendingShot: null,
      ...you,
    },
    others: [{ playerId: 'h', connected: true, alive: true, planesDestroyed: 0, submitted: false }],
    ...rest,
  }
}

const placing = (o: V = {}) => view({ phase: 'placing', turn: null, you: { planes: [] }, ...o })
const melee = (round: number, o: V = {}) => view({ mode: 'melee', turn: null, round, ...o })

const mk = (seed = 1) => new BotDriver(BOT, 'standard', mulberry32(seed))

/** 在 [from, to] 内以 step 步长不断 poll，返回第一次出手的时间；没有则 null。 */
function firstActionAt(d: BotDriver, v: GameView, from: number, to: number, step = 50) {
  for (let t = from; t <= to; t += step) {
    if (d.poll(v, RULES, t)) return t
  }
  return null
}

describe('BotDriver', () => {
  it('常量', () => {
    expect(BOT_THINK_MS).toEqual([1200, 3500])
    expect(BOT_DEADLINE_MARGIN_MS).toBe(1000)
  })

  it('摆放：思考时间内不出手，到点出 placePlane 且合法', () => {
    const d = mk()
    const v = placing()
    expect(d.poll(v, RULES, 10_000)).toBeNull()
    expect(d.poll(v, RULES, 10_000 + 1199)).toBeNull()
    const msg = d.poll(v, RULES, 10_000 + 3500)
    expect(msg?.type).toBe('placePlane')
    if (msg?.type !== 'placePlane') throw new Error('unreachable')
    expect(msg.planes).toHaveLength(RULES.planeCount)
    for (const h of msg.planes) expect(isPlacementValid(h, RULES.boardSize)).toBe(true)
    const cells = msg.planes.flatMap((h) => cellsOfPlane(h).map(cellKey))
    expect(new Set(cells).size).toBe(cells.length)
  })

  it('duel：非己回合返回 null；轮到自己后在 [1200, 3500] ms 内出 fire', () => {
    for (let seed = 1; seed <= 20; seed++) {
      const d = mk(seed)
      const theirs = view({ turn: 'h' })
      for (let t = 0; t <= 6000; t += 500) expect(d.poll(theirs, RULES, t)).toBeNull()
      const mine = view()
      const t0 = 10_000
      expect(d.poll(mine, RULES, t0)).toBeNull()
      const hit = firstActionAt(d, mine, t0 + 1, t0 + 3600, 1)
      expect(hit).not.toBeNull()
      expect(hit as number).toBeGreaterThanOrEqual(t0 + 1200)
      expect(hit as number).toBeLessThanOrEqual(t0 + 3500)
    }
  })

  it('duel：出的 fire 在棋盘内', () => {
    const d = mk()
    const v = view()
    d.poll(v, RULES, 0)
    const msg = d.poll(v, RULES, 3500)
    expect(msg?.type).toBe('fire')
    if (msg?.type !== 'fire') throw new Error('unreachable')
    expect(msg.row).toBeGreaterThanOrEqual(0)
    expect(msg.row).toBeLessThan(RULES.boardSize)
    expect(msg.col).toBeGreaterThanOrEqual(0)
    expect(msg.col).toBeLessThan(RULES.boardSize)
  })

  it('duel：paused 期间不出手；恢复后重新计时', () => {
    const d = mk()
    const live = view()
    expect(d.poll(live, RULES, 0)).toBeNull() // 计划 actAt ∈ [1200, 3500]
    const paused = view({ phase: 'paused' })
    for (let t = 100; t <= 20_000; t += 500) expect(d.poll(paused, RULES, t)).toBeNull()
    // 恢复：立即 poll 不出手（重新计时，至少 1200 ms 之后）
    expect(d.poll(live, RULES, 20_000)).toBeNull()
    expect(d.poll(live, RULES, 20_000 + 1199)).toBeNull()
    expect(d.poll(live, RULES, 20_000 + 3500)?.type).toBe('fire')
  })

  it('melee：已提交（you.submitted）后本轮不再出手；新一轮再出手一次', () => {
    const d = mk()
    const r1 = melee(1)
    expect(d.poll(r1, RULES, 0)).toBeNull()
    expect(d.poll(r1, RULES, 3500)?.type).toBe('fire')
    const r1done = melee(1, { you: { submitted: true, pendingShot: { row: 1, col: 1 } } })
    for (let t = 3600; t <= 30_000; t += 700) expect(d.poll(r1done, RULES, t)).toBeNull()
    const r2 = melee(2)
    expect(d.poll(r2, RULES, 40_000)).toBeNull()
    expect(d.poll(r2, RULES, 43_500)?.type).toBe('fire')
    expect(d.poll(r2, RULES, 50_000)).toBeNull()
  })

  it('melee：出局（you.alive=false）后永不出手', () => {
    const d = mk()
    const dead = melee(3, { you: { alive: false } })
    for (let t = 0; t <= 60_000; t += 500) expect(d.poll(dead, RULES, t)).toBeNull()
  })

  it('finished 后永不出手', () => {
    const d = mk()
    d.poll(view(), RULES, 0)
    const fin = view({ phase: 'finished', turn: null })
    for (let t = 0; t <= 60_000; t += 500) expect(d.poll(fin, RULES, t)).toBeNull()
    const finPlacing = placing({ phase: 'finished' })
    for (let t = 0; t <= 60_000; t += 500) expect(d.poll(finPlacing, RULES, t)).toBeNull()
  })

  it('截止保护：deadline 只剩 1500 ms 时，最晚在 deadline − 1000 出手', () => {
    for (let seed = 1; seed <= 30; seed++) {
      const d = mk(seed)
      const now = 100_000
      const v = view({ deadlineAt: now + 1500 })
      d.poll(v, RULES, now)
      const hit = firstActionAt(d, v, now + 1, now + 1500, 1)
      expect(hit).not.toBeNull()
      expect(hit as number).toBeLessThanOrEqual(now + 1500 - BOT_DEADLINE_MARGIN_MS)
    }
  })

  it('截止保护：deadline 已不足 1000 ms 时立即出手（不早于 now）', () => {
    const d = mk()
    const v = view({ deadlineAt: 5_500 })
    expect(d.poll(v, RULES, 5_000)?.type).toBe('fire')
  })

  it('同一键只出手一次（连续 poll 不重复返回动作）', () => {
    const d = mk()
    const v = view()
    d.poll(v, RULES, 0)
    expect(d.poll(v, RULES, 3500)?.type).toBe('fire')
    for (let t = 3501; t <= 30_000; t += 250) expect(d.poll(v, RULES, t)).toBeNull()
  })

  it('duel：自己再次轮到（shots 增加）是新的决策点', () => {
    const d = mk()
    const v1 = view()
    d.poll(v1, RULES, 0)
    expect(d.poll(v1, RULES, 3500)?.type).toBe('fire')
    const v2 = view({
      you: { shots: [{ targetId: 'h', row: 0, col: 0, result: 'miss', planeId: 'p0' }] },
    })
    expect(d.poll(v2, RULES, 10_000)).toBeNull()
    expect(d.poll(v2, RULES, 13_500)?.type).toBe('fire')
  })

  it('摆放：已有飞机（you.planes 非空）不再摆放', () => {
    const d = mk()
    const v = placing({ you: { planes: [{ row: 3, col: 3 }, { row: 6, col: 6 }] } })
    for (let t = 0; t <= 10_000; t += 500) expect(d.poll(v, RULES, t)).toBeNull()
  })

  it('摆放：同一键只出一次，即使引擎拒绝（planes 仍为空）', () => {
    const d = mk()
    const v = placing()
    d.poll(v, RULES, 0)
    expect(d.poll(v, RULES, 3500)?.type).toBe('placePlane')
    for (let t = 3501; t <= 30_000; t += 500) expect(d.poll(v, RULES, t)).toBeNull()
  })

  it('同 seed 同视图输出确定', () => {
    const run = () => {
      const d = mk(7)
      const v = view()
      d.poll(v, RULES, 0)
      return d.poll(v, RULES, 3500)
    }
    expect(run()).toEqual(run())
  })
})
