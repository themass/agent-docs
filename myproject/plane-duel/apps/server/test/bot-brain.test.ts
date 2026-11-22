import { describe, it, expect } from 'vitest'
import {
  autoPlace,
  cellKey,
  resolveShot,
  type Cell,
  type GameView,
  type PresetId,
  type RuleSet,
  type TargetShot,
} from '@plane-duel/shared'
import { BOT_MISTAKE_RATE, PART_WEIGHT, chooseShot, opponentModel, scoreCells } from '../src/bot/brain'
import { mulberry32 } from '../../../packages/shared/test/helpers'

const R10: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

type OtherSpec = string | { id: string; alive?: boolean; planesDestroyed?: number }

function viewWith(o: { rules: RuleSet; shots: TargetShot[]; others: OtherSpec[]; planesDestroyed?: number }): GameView {
  return {
    mode: o.others.length > 1 ? 'melee' : 'duel',
    phase: 'playing',
    deadlineAt: null,
    turn: null,
    round: null,
    you: {
      planes: [],
      planesDestroyed: o.planesDestroyed ?? 0,
      alive: true,
      shots: o.shots,
      incoming: [],
      submitted: false,
      pendingShot: null,
    },
    others: o.others.map((s) => {
      const x = typeof s === 'string' ? { id: s } : s
      return {
        playerId: x.id,
        connected: true,
        alive: (x as { alive?: boolean }).alive ?? true,
        planesDestroyed: (x as { planesDestroyed?: number }).planesDestroyed ?? 0,
        submitted: false,
      }
    }),
  }
}

const body = (targetId: string, row: number, col: number, planeId = 'p0'): TargetShot => ({
  targetId,
  row,
  col,
  result: 'body',
  planeId,
})
const head = (targetId: string, row: number, col: number, planeId = 'p0'): TargetShot => ({
  targetId,
  row,
  col,
  result: 'head',
  planeId,
})
const miss = (targetId: string, row: number, col: number): TargetShot => ({
  targetId,
  row,
  col,
  result: 'miss',
  planeId: 'p0',
})

const seq = (values: number[]) => {
  let i = 0
  return () => values[Math.min(i++, values.length - 1)] as number
}

const CORNER = viewWith({ rules: R10, shots: [body('b', 0, 0)], others: ['b'] })

describe('bot brain: 常量', () => {
  it('失误率表与部位权重', () => {
    expect(BOT_MISTAKE_RATE).toEqual({ beginner: 0.4, standard: 0.25, advanced: 0.1, expert: 0 })
    expect(PART_WEIGHT).toBe(0.3)
  })
})

describe('bot brain: 推理', () => {
  it('角上一格是机身 → 唯一候选机头 (1,1)，高手必打', () => {
    expect(chooseShot(CORNER, R10, 'expert', mulberry32(1))).toEqual({ row: 1, col: 1 })
  })

  it('未命中格排除候选：机身 (4,4) + 周围未命中只留一个候选 (5,5)', () => {
    const v = viewWith({
      rules: R10,
      shots: [body('b', 4, 4), miss('b', 3, 3), miss('b', 3, 4), miss('b', 3, 5), miss('b', 4, 3), miss('b', 5, 3)],
      others: ['b'],
    })
    const m = opponentModel(v.you.shots, 0, R10)
    expect(m.active).toHaveLength(1)
    expect(m.active[0]!.candidates).toEqual([{ row: 5, col: 5 }])
    expect(chooseShot(v, R10, 'expert', mulberry32(7))).toEqual({ row: 5, col: 5 })
  })

  it('miss 的 planeId 恒为 p0，但不参与机身分组', () => {
    const m = opponentModel([miss('b', 8, 8), miss('b', 7, 8)], 0, R10)
    expect(m.active).toHaveLength(0)
    expect(m.unlocated).toBe(1)
  })

  it('空棋盘：中心格的分数高于角格（找机身倾向中心）', () => {
    const s = scoreCells(viewWith({ rules: R10, shots: [], others: ['b'] }), R10)
    expect(s.get('5,5')!).toBeGreaterThan(s.get('0,0')!)
  })

  it('scoreCells 只含未打过的格子', () => {
    const s = scoreCells(CORNER, R10)
    expect(s.has('0,0')).toBe(false)
    expect(s.size).toBe(99)
    expect(s.get('1,1')!).toBeCloseTo(1 + PART_WEIGHT * 1, 9)
  })

  it('混战求和：同时是 b、c 候选机头的格子优先于只是 b 的候选', () => {
    // b: 机身 (0,1) → 候选 {(1,1),(1,2)}；c: 机身 (0,3) → 候选 {(1,2),(1,3),(1,4)}
    const onlyB = viewWith({ rules: R10, shots: [body('b', 0, 1), body('c', 0, 3)], others: ['b'] })
    const both = viewWith({ rules: R10, shots: [body('b', 0, 1), body('c', 0, 3)], others: ['b', 'c'] })
    const sb = scoreCells(onlyB, R10)
    expect(sb.get('1,1')!).toBeCloseTo(sb.get('1,2')!, 9) // 只看 b：打平
    const s = scoreCells(both, R10)
    expect(s.get('1,2')!).toBeGreaterThan(s.get('1,1')!)
    expect(chooseShot(both, R10, 'expert', mulberry32(3))).toEqual({ row: 1, col: 2 })
  })

  it('混战只算存活对手：已出局对手身上的线索不影响打分', () => {
    const shots = [body('b', 0, 1), body('c', 0, 3)]
    const dead = viewWith({ rules: R10, shots, others: ['b', { id: 'c', alive: false }] })
    const absent = viewWith({ rules: R10, shots, others: ['b'] })
    expect([...scoreCells(dead, R10)]).toEqual([...scoreCells(absent, R10)])
  })

  it('多机：两架活跃飞机分别推理，不把两架的机身命中求交集', () => {
    const rules: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false }
    const v = viewWith({
      rules,
      shots: [body('b', 3, 3, 'p0'), body('b', 8, 8, 'p1')],
      others: ['b'],
    })
    const m = opponentModel(v.you.shots, 0, rules)
    expect(m.active).toHaveLength(2)
    expect(m.unlocated).toBe(0)
    const s = scoreCells(v, rules)
    expect(s.get('2,2')!).toBeGreaterThanOrEqual(1 / 8)
    expect(s.get('9,9')!).toBeGreaterThanOrEqual(1 / 8)
    expect(s.get('0,11')!).toBe(0)
    const pick = chooseShot(v, rules, 'expert', mulberry32(5))!
    const near = (c: Cell, r: number, k: number) => Math.abs(c.row - r) <= 1 && Math.abs(c.col - k) <= 1
    expect(near(pick, 3, 3) || near(pick, 8, 8)).toBe(true)
  })

  it('未定位飞机数 = 总数 − 已击落 − 活跃数', () => {
    const rules: RuleSet = { boardSize: 12, planeCount: 3, turnSeconds: 20, hintAllowed: false }
    const m = opponentModel([body('b', 3, 3, 'p1'), head('b', 8, 8, 'p0')], 1, rules)
    expect(m.active.map((a) => a.planeId)).toEqual(['p1'])
    expect(m.unlocated).toBe(1)
  })

  it('已击落飞机的 9 格不再作为别的飞机的可能位置', () => {
    const rules: RuleSet = { boardSize: 10, planeCount: 2, turnSeconds: 20, hintAllowed: false }
    // p0 机头 (4,4) 已击落，占 3..5 × 3..5；p1 机身 (4,6) 的候选 (3..5, 5..7) 里，只有 col 7 不碰已击落的格
    const v = viewWith({
      rules,
      shots: [head('b', 4, 4, 'p0'), body('b', 4, 6, 'p1')],
      others: [{ id: 'b', planesDestroyed: 1 }],
    })
    const m = opponentModel(v.you.shots, 1, rules)
    expect(m.active[0]!.candidates).toEqual([
      { row: 3, col: 7 },
      { row: 4, col: 7 },
      { row: 5, col: 7 },
    ])
    expect(m.unlocated).toBe(0)
    expect(scoreCells(v, rules).get('4,5')!).toBe(0)
    expect(chooseShot(v, rules, 'expert', mulberry32(9))).toEqual({ row: 4, col: 7 })
  })

  it('同分时用 rng 均匀选择', () => {
    const rules: RuleSet = { boardSize: 6, planeCount: 1, turnSeconds: 20, hintAllowed: true }
    const v = viewWith({ rules, shots: [], others: ['b'] })
    // 并列最高的 4 格（行优先）：(2,2) (2,3) (3,2) (3,3)
    expect(chooseShot(v, rules, 'expert', seq([0.5, 0]))).toEqual({ row: 2, col: 2 })
    expect(chooseShot(v, rules, 'expert', seq([0.5, 0.5]))).toEqual({ row: 3, col: 2 })
    expect(chooseShot(v, rules, 'expert', seq([0.5, 0.999999]))).toEqual({ row: 3, col: 3 })
  })

  it('无未打过的格子 → null', () => {
    const rules: RuleSet = { boardSize: 6, planeCount: 1, turnSeconds: 20, hintAllowed: true }
    const shots: TargetShot[] = []
    for (let r = 0; r < 6; r++) for (let c = 0; c < 6; c++) shots.push(miss('b', r, c))
    expect(chooseShot(viewWith({ rules, shots, others: ['b'] }), rules, 'expert', mulberry32(1))).toBeNull()
  })
})

describe('bot brain: 失误', () => {
  const deviation = (difficulty: PresetId, n = 2000) => {
    let off = 0
    for (let i = 0; i < n; i++) {
      const c = chooseShot(CORNER, R10, difficulty, mulberry32(i))!
      if (c.row !== 1 || c.col !== 1) off++
    }
    return off / n
  }

  it('入门在 2000 次决策中偏离最优的比例 ∈ [0.33, 0.47]', () => {
    // 期望 = 0.4 × (1 − 1/99) ≈ 0.396
    const r = deviation('beginner')
    expect(r).toBeGreaterThanOrEqual(0.33)
    expect(r).toBeLessThanOrEqual(0.47)
  })

  it.each([
    ['standard', 0.25],
    ['advanced', 0.1],
  ] as const)('%s 的偏离率在失误率 ±5 个百分点内', (d, rate) => {
    const expected = rate * (98 / 99)
    expect(Math.abs(deviation(d) - expected)).toBeLessThanOrEqual(0.05)
  })

  it('高手从不偏离（任何种子）', () => {
    expect(deviation('expert', 1000)).toBe(0)
  })

  it('失误时只用到第一次 rng 判定：rng 恒为 0 → 入门必失误并选第一个未打格', () => {
    expect(chooseShot(CORNER, R10, 'beginner', () => 0)).toEqual({ row: 0, col: 1 })
  })

  it('确定性：同一种子同一结果', () => {
    for (let i = 0; i < 50; i++) {
      expect(chooseShot(CORNER, R10, 'beginner', mulberry32(i))).toEqual(
        chooseShot(CORNER, R10, 'beginner', mulberry32(i)),
      )
    }
  })
})

describe('bot brain: 合法性与性能', () => {
  const randomShots = (rules: RuleSet, target: string, n: number, rng: () => number): TargetShot[] => {
    const planes = autoPlace(rules.boardSize, rules.planeCount, rng).map((h, i) => ({ id: `p${i}`, head: h }))
    const seen = new Set<string>()
    const out: TargetShot[] = []
    while (out.length < n) {
      const cell = { row: Math.floor(rng() * rules.boardSize), col: Math.floor(rng() * rules.boardSize) }
      if (seen.has(cellKey(cell))) continue
      seen.add(cellKey(cell))
      const r = resolveShot(planes, cell)
      out.push({ targetId: target, ...cell, result: r.result, planeId: r.result === 'miss' ? 'p0' : r.planeId })
    }
    return out
  }

  it('从不选已打过的格子、总在棋盘内（随机 200 个局面）', () => {
    const rng = mulberry32(2024)
    const diffs: PresetId[] = ['beginner', 'standard', 'advanced', 'expert']
    for (let i = 0; i < 200; i++) {
      const boardSize = 6 + Math.floor(rng() * 11)
      const planeCount = 1 + Math.floor(rng() * Math.min(3, Math.floor((0.3 * boardSize * boardSize) / 9)))
      const rules: RuleSet = { boardSize, planeCount, turnSeconds: 20, hintAllowed: true }
      const n = Math.floor(rng() * (boardSize * boardSize * 0.6))
      const shots = [
        ...randomShots(rules, 'b', n, rng),
        ...randomShots(rules, 'c', Math.floor(n / 2), rng),
      ]
      const used = new Set(shots.map((s) => cellKey(s)))
      const v = viewWith({ rules, shots, others: ['b', 'c'] })
      const pick = chooseShot(v, rules, diffs[i % 4]!, rng)
      if (used.size >= boardSize * boardSize) {
        expect(pick).toBeNull()
        continue
      }
      expect(pick).not.toBeNull()
      expect(used.has(cellKey(pick!))).toBe(false)
      expect(pick!.row).toBeGreaterThanOrEqual(0)
      expect(pick!.row).toBeLessThan(boardSize)
      expect(pick!.col).toBeGreaterThanOrEqual(0)
      expect(pick!.col).toBeLessThan(boardSize)
    }
  })

  it('性能：16×16、6 架、3 个对手、每人 60 炮，单次 chooseShot < 20ms', () => {
    const rules: RuleSet = { boardSize: 16, planeCount: 6, turnSeconds: 20, hintAllowed: false }
    const rng = mulberry32(77)
    const shots = ['b', 'c', 'd'].flatMap((t) => randomShots(rules, t, 60, rng))
    const v = viewWith({ rules, shots, others: ['b', 'c', 'd'] })
    chooseShot(v, rules, 'expert', mulberry32(1)) // 预热
    const t0 = performance.now()
    chooseShot(v, rules, 'expert', mulberry32(1))
    expect(performance.now() - t0).toBeLessThan(20)
  })
})
