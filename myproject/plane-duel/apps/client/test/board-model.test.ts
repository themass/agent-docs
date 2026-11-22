import { describe, it, expect } from 'vitest'
import { candidateHeads, cellKey, cellsOfPlane, type TargetShot } from '@plane-duel/shared'
import { buildBoardCells, buildTargetCells, duelHintKeys, hintHeads, SEAT_COLORS } from '../src/board-model'

describe('buildBoardCells', () => {
  it('10x10 生成 100 格，行优先', () => {
    const cells = buildBoardCells({ boardSize: 10, shots: [], planes: [], showPlane: false })
    expect(cells).toHaveLength(100)
    expect(cells[0]).toEqual({ row: 0, col: 0, state: 'unknown' })
    expect(cells[1]).toEqual({ row: 0, col: 1, state: 'unknown' })
    expect(cells[10]).toEqual({ row: 1, col: 0, state: 'unknown' })
  })

  it('打过的格子显示对应结果', () => {
    const cells = buildBoardCells({
      boardSize: 10,
      showPlane: false,
      planes: [],
      shots: [
        { row: 3, col: 4, result: 'body' },
        { row: 0, col: 0, result: 'miss' },
      ],
    })
    expect(cells[3 * 10 + 4]!.state).toBe('body')
    expect(cells[0]!.state).toBe('miss')
  })

  it('showPlane 为真时自己的飞机 9 格可见，机头单独标记', () => {
    const cells = buildBoardCells({
      boardSize: 10,
      shots: [],
      planes: [{ row: 5, col: 5 }],
      showPlane: true,
    })
    expect(cells[5 * 10 + 5]!.state).toBe('head')
    expect(cells[4 * 10 + 4]!.state).toBe('body')
    expect(cells[4 * 10 + 5]!.state).toBe('body')
  })

  it('showPlane 为假时飞机不可见', () => {
    const cells = buildBoardCells({
      boardSize: 10,
      shots: [],
      planes: [{ row: 5, col: 5 }],
      showPlane: false,
    })
    expect(cells.every((c) => c.state === 'unknown')).toBe(true)
  })

  it('棋盘尺寸变化时格子数跟随', () => {
    expect(
      buildBoardCells({ boardSize: 8, shots: [], planes: [], showPlane: false }),
    ).toHaveLength(64)
    expect(
      buildBoardCells({ boardSize: 12, shots: [], planes: [], showPlane: false }),
    ).toHaveLength(144)
  })

  it('机头优先级高于机身命中记录', () => {
    const cells = buildBoardCells({
      boardSize: 10,
      showPlane: true,
      planes: [{ row: 5, col: 5 }],
      shots: [{ row: 5, col: 5, result: 'head' }],
    })
    expect(cells[5 * 10 + 5]!.state).toBe('head')
  })
})

describe('buildTargetCells', () => {
  const opponents = [
    { playerId: 'a', color: '#aaa', alive: true },
    { playerId: 'b', color: '#bbb', alive: true },
    { playerId: 'c', color: '#ccc', alive: false },
  ]
  const shot = (targetId: string, row: number, col: number, result: TargetShot['result'] = 'miss', planeId = 'p0'): TargetShot => ({
    targetId, row, col, result, planeId,
  })
  const at = <T extends { row: number; col: number }>(cells: T[], row: number, col: number, size = 10): T =>
    cells[row * size + col]!

  it('合并视图：一格可有多个对手的标记，按对手顺序', () => {
    // 先打 b 再打 a，标记顺序仍应是 a, b（对手数组顺序）
    const cells = buildTargetCells({
      boardSize: 10,
      shots: [shot('b', 2, 2, 'body'), shot('a', 2, 2, 'miss'), shot('a', 5, 5, 'head')],
      opponents,
      focus: null,
      hintFor: null,
    })
    expect(at(cells, 2, 2).marks).toEqual([
      { playerId: 'a', color: '#aaa', result: 'miss', dim: false },
      { playerId: 'b', color: '#bbb', result: 'body', dim: false },
    ])
    expect(at(cells, 5, 5).marks).toEqual([{ playerId: 'a', color: '#aaa', result: 'head', dim: false }])
    expect(at(cells, 0, 0).marks).toEqual([])
  })

  it('focus 视图：只含该对手的标记', () => {
    const cells = buildTargetCells({
      boardSize: 10,
      shots: [shot('b', 2, 2, 'body'), shot('a', 2, 2, 'miss'), shot('a', 5, 5, 'head')],
      opponents,
      focus: 'a',
      hintFor: null,
    })
    expect(at(cells, 2, 2).marks.map((m) => m.playerId)).toEqual(['a'])
    expect(at(cells, 5, 5).marks.map((m) => m.playerId)).toEqual(['a'])
    const onlyB = buildTargetCells({
      boardSize: 10, shots: [shot('b', 1, 1)], opponents, focus: 'a', hintFor: null,
    })
    expect(at(onlyB, 1, 1).marks).toEqual([])
  })

  it('已出局对手的标记 dim=true', () => {
    const cells = buildTargetCells({
      boardSize: 10, shots: [shot('c', 3, 3, 'body'), shot('a', 3, 3, 'miss')], opponents, focus: null, hintFor: null,
    })
    expect(at(cells, 3, 3).marks.map((m) => [m.playerId, m.dim])).toEqual([['a', false], ['c', true]])
  })

  it('fired：我打过的格子（对任一对手）为 true', () => {
    const shots = [shot('a', 4, 4), shot('b', 6, 6)]
    const merged = buildTargetCells({ boardSize: 10, shots, opponents, focus: null, hintFor: null })
    expect(at(merged, 4, 4).fired).toBe(true)
    expect(at(merged, 6, 6).fired).toBe(true)
    expect(at(merged, 0, 0).fired).toBe(false)
    // focus 视图里别的对手打过的格子，对"我"来说也算打过
    const focus = buildTargetCells({ boardSize: 10, shots, opponents, focus: 'a', hintFor: null })
    expect(at(focus, 6, 6).fired).toBe(true)
    expect(at(focus, 6, 6).marks).toEqual([])
  })

  it('hint：只在 focus 且 hintFor 等于 focus 时标出 candidateHeads', () => {
    const shots = [shot('a', 5, 5, 'body')]
    const expected = new Set(candidateHeads([{ row: 5, col: 5 }], 10).map((c) => `${c.row},${c.col}`))
    expect(expected.size).toBeGreaterThan(0)
    const hinted = (focus: string | null, hintFor: string | null) =>
      new Set(
        buildTargetCells({ boardSize: 10, shots, opponents, focus, hintFor })
          .filter((c) => c.hint)
          .map((c) => `${c.row},${c.col}`),
      )
    expect(hinted('a', 'a')).toEqual(expected)
    expect(hinted(null, 'a').size).toBe(0)
    expect(hinted('a', null).size).toBe(0)
    expect(hinted('a', 'b').size).toBe(0)
  })

  it('hint：只用该对手的机身命中；已击落的飞机不再参与推理', () => {
    const shots = [
      shot('a', 5, 5, 'body', 'p0'),
      shot('b', 1, 1, 'body', 'p0'), // 别的对手，不得影响
      shot('a', 8, 8, 'body', 'p1'),
      shot('a', 8, 7, 'head', 'p1'), // p1 已击落
    ]
    const cells = buildTargetCells({ boardSize: 10, shots, opponents, focus: 'a', hintFor: 'a' })
    const got = new Set(cells.filter((c) => c.hint).map((c) => `${c.row},${c.col}`))
    const expected = new Set(candidateHeads([{ row: 5, col: 5 }], 10).map((c) => `${c.row},${c.col}`))
    expect(got).toEqual(expected)
  })

  it('16×16 生成 256 格，行优先', () => {
    const cells = buildTargetCells({ boardSize: 16, shots: [], opponents, focus: null, hintFor: null })
    expect(cells).toHaveLength(256)
    expect(cells[17]).toMatchObject({ row: 1, col: 1, fired: false, hint: false, marks: [] })
  })
})

describe('SEAT_COLORS', () => {
  it('4 个互不相同的颜色', () => {
    expect(SEAT_COLORS).toHaveLength(4)
    expect(new Set(SEAT_COLORS).size).toBe(4)
  })
})

describe('评审 I6：对决的推理提示（多架飞机）', () => {
  const bodyOf = (head: { row: number; col: number }) =>
    cellsOfPlane(head).find((c) => c.row !== head.row || c.col !== head.col)!
  const h0 = { row: 2, col: 2 }
  const h1 = { row: 6, col: 6 }
  const b0 = bodyOf(h0)
  const b1 = bodyOf(h1)
  const shots: TargetShot[] = [
    { targetId: 'op', row: b0.row, col: b0.col, result: 'body', planeId: 'p0' },
    { targetId: 'op', row: b1.row, col: b1.col, result: 'body', planeId: 'p1' },
  ]

  it('两架飞机各中一格机身 → 提示为两架各自候选的并集（非空）', () => {
    // 旧实现把所有机身命中放在一起求交集 → 空集
    expect(candidateHeads([b0, b1], 10)).toEqual([])
    const keys = duelHintKeys(shots, 10)!
    expect(keys.size).toBeGreaterThan(0)
    for (const b of [b0, b1]) {
      for (const h of candidateHeads([b], 10)) expect(keys.has(cellKey(h))).toBe(true)
    }
  })

  it('已击落的飞机不参与推理；没有机身命中时不显示提示', () => {
    const downed: TargetShot[] = [...shots, { targetId: 'op', row: h0.row, col: h0.col, result: 'head', planeId: 'p0' }]
    const keys = duelHintKeys(downed, 10)!
    expect(keys).toEqual(new Set(candidateHeads([b1], 10).map(cellKey)))
    expect(duelHintKeys([], 10)).toBeUndefined()
  })

  it('hintHeads 被导出供对决复用', () => {
    expect(hintHeads(shots, 10).length).toBeGreaterThan(0)
  })
})
