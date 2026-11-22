/**
 * Table + 真实引擎 + 真实电脑的集成（spec §20.2/§20.4，Review Focus #1/#2）。
 *
 * 不新增产品代码，只验证接缝：
 * - 电脑只拿到 engine.view(自己)；
 * - 电脑之间的结果永不下发给真人；
 * - 掉线暂停期间电脑不出手；真人全走 → 立即关桌；
 * - 电脑的每一炮都在截止前 ≥ 800 ms（引擎的超时代打不会替电脑开炮）。
 *
 * 时间与随机都是假的：tick 每次前进 200 ms；真人由脚本扮演（每轮打一个没打过的格子）。
 */
import { describe, expect, it } from 'vitest'
import { resolveShot } from '@plane-duel/shared'
import type { BotDifficulty, Cell, GameView, RuleSet } from '@plane-duel/shared'
import { Table } from '../src/table'
import { BotDriver } from '../src/bot/driver'
import type { BotBrainLike } from '../src/bot/driver'
import type { Outbound } from '../src/engine'
import { mulberry32 } from '../../../packages/shared/test/helpers'

const STEP = 200
const HUM = 'hum'
const HEAD: Cell = { row: 2, col: 2 } // 8×8 与 6×6 都合法
/** 真人的棋盘真值，用于验证发给他的每个 result 字段。 */
const humanPlanes = [{ id: 'p0', head: HEAD }]

const duelRules: RuleSet = { boardSize: 8, planeCount: 1, turnSeconds: 15, hintAllowed: false }
const meleeRules: RuleSet = { boardSize: 6, planeCount: 1, turnSeconds: 10, hintAllowed: false }

/** 包一层真实 BotDriver：记录每次 poll 的 view、同一时刻桌子引擎给该电脑的 view、开炮时距截止的余量。 */
class RecordingBot implements BotBrainLike {
  readonly polls: { view: GameView; engineView: GameView | null; now: number }[] = []
  readonly fireMargins: number[] = []
  placed: Cell[] | null = null

  private readonly inner: BotDriver

  constructor(
    private readonly getTable: () => Table,
    readonly playerId: string,
    difficulty: BotDifficulty,
    rng: () => number,
  ) {
    this.inner = new BotDriver(playerId, difficulty, rng)
  }

  poll(view: GameView, rules: RuleSet, now: number) {
    const engine = this.getTable().engine
    this.polls.push({ view, engineView: engine === null ? null : engine.view(this.playerId), now })
    const msg = this.inner.poll(view, rules, now)
    if (msg?.type === 'placePlane') this.placed = msg.planes
    if (msg?.type === 'fire' && view.deadlineAt !== null) this.fireMargins.push(view.deadlineAt - now)
    return msg
  }
}

function makePractice(capacity: 2 | 3 | 4, rules: RuleSet, seed: number, difficulty: BotDifficulty) {
  const holder: { table: Table | null } = { table: null }
  const bots: RecordingBot[] = []
  const table = new Table({
    roomCode: '777001',
    kind: 'practice',
    capacity,
    rules,
    now: 0,
    rng: mulberry32(seed),
    botFactory: (id, d, r) => {
      const b = new RecordingBot(() => holder.table as Table, id, d, r)
      bots.push(b)
      return b
    },
  })
  holder.table = table

  table.join(HUM, '真人', 0)
  const botIds: string[] = []
  while (table.members.length < capacity) {
    const before = new Set(table.members)
    table.addBot(difficulty, 0)
    for (const id of table.members) if (!before.has(id)) botIds.push(id)
  }
  return { table, botIds, bots }
}

/** 轮到（duel）或该交（melee）时，真人按行优先顺序打一个没打过的格子。 */
function humanFire(table: Table, now: number, size: number, fired: Set<string>, st: { next: number }): Outbound[] {
  const v = table.engine?.view(HUM)
  if (!v || v.phase !== 'playing' || !v.you.alive) return []
  if (v.mode === 'duel' ? v.turn !== HUM : v.you.submitted) return []
  while (st.next < size * size) {
    const n = st.next++
    const cell = { row: Math.floor(n / size), col: n % size }
    const k = `${cell.row},${cell.col}`
    if (fired.has(k)) continue
    fired.add(k)
    return table.handleGame(HUM, { type: 'fire', ...cell }, now)
  }
  return []
}

function runGame(table: Table, rules: RuleSet, maxTicks: number) {
  const out: Outbound[] = []
  const fired = new Set<string>()
  const st = { next: 0 }
  table.handleGame(HUM, { type: 'placePlane', planes: [HEAD] }, 0)
  let ticks = 0
  for (; ticks < maxTicks && table.phase === 'inGame' && !table.isClosed; ticks++) {
    const now = (ticks + 1) * STEP
    out.push(...table.tick(now))
    if (table.phase !== 'inGame') break
    out.push(...humanFire(table, now, rules.boardSize, fired, st))
  }
  return { out, fired, ticks, ended: table.phase !== 'inGame' || table.isClosed }
}

describe('Table + 真实引擎 + 真实电脑（练习桌）', () => {
  it('练习 2 人（高手电脑）：在 2000 次 tick 内打完，回到 waiting，lastResult.botIds 为电脑', () => {
    const { table, botIds } = makePractice(2, duelRules, 11, 'expert')
    const { ended, out } = runGame(table, duelRules, 2000)
    expect(ended).toBe(true)
    expect(table.phase).toBe('waiting')
    expect(table.engine).toBeNull()

    const res = table.view().lastResult
    expect(res).not.toBeNull()
    expect([...res!.botIds].sort()).toEqual([...botIds].sort())
    expect(res!.ranking).toHaveLength(2)
    expect(out.some((o) => o.to === HUM && o.msg.type === 'gameOver')).toBe(true)
  })

  it('电脑不会触发 duel 超时代打（电脑的每一炮都在截止前 ≥ 800 ms 发生）', () => {
    const { table, bots } = makePractice(2, duelRules, 11, 'expert')
    runGame(table, duelRules, 2000)
    const margins = bots[0]!.fireMargins
    expect(margins.length).toBeGreaterThan(0)
    for (const m of margins) expect(m).toBeGreaterThanOrEqual(800)
  })

  it('练习 4 人混战（1 真人 + 3 入门电脑）：在 3000 次 tick 内打完，ranking 长度 4 且至少一个 rank 1', () => {
    const { table, botIds } = makePractice(4, meleeRules, 5, 'beginner')
    const { ended } = runGame(table, meleeRules, 3000)
    expect(ended).toBe(true)
    expect(table.phase).toBe('waiting')

    const res = table.view().lastResult
    expect(res).not.toBeNull()
    expect(res!.ranking).toHaveLength(4)
    expect(res!.ranking.some((r) => r.rank === 1)).toBe(true)
    expect(res!.botIds).toHaveLength(3)
    expect([...botIds].sort()).toEqual([...res!.botIds].sort())
  })

  it('Review Focus #1：交给每个电脑的视图恒等于 engine.view(该电脑)', () => {
    const { table, bots } = makePractice(4, meleeRules, 5, 'beginner')
    runGame(table, meleeRules, 3000)
    let total = 0
    for (const b of bots) {
      expect(b.polls.length).toBeGreaterThan(10)
      for (const p of b.polls) {
        expect(p.engineView).not.toBeNull()
        expect(p.view).toEqual(p.engineView)
        // 视图里不含电脑自己
        expect(p.view.others.map((o) => o.playerId)).not.toContain(b.playerId)
        // 摆放结束之后，"你的飞机"就是它自己提交的摆放（不是别人的真值）
        if (p.view.phase !== 'placing') {
          expect(b.placed).not.toBeNull()
          expect(p.view.you.planes).toEqual(b.placed)
        }
      }
      total += b.polls.length
    }
    expect(total).toBeGreaterThan(0)
  })

  it('Review Focus #1：真人收到的消息里没有任何电脑之间的结果', () => {
    const { table } = makePractice(4, meleeRules, 9, 'beginner')
    const { out, fired } = runGame(table, meleeRules, 3000)
    expect(out.length).toBeGreaterThan(0)
    for (const o of out) {
      const m = o.msg
      if (m.type === 'roundResult') {
        // 我收到的 shots 只能是我自己打过的格子
        for (const s of m.shots) expect(fired.has(`${s.row},${s.col}`)).toBe(true)
        // 我收到的 incoming 必须与我的棋盘真值一致（别人打别人的结果混进来必然对不上）
        for (const inc of m.incoming) {
          expect(inc.result).toBe(resolveShot(humanPlanes, { row: inc.row, col: inc.col }).result)
        }
      }
      if (m.type === 'state' && m.game !== null) {
        for (const s of m.game.you.shots) expect(fired.has(`${s.row},${s.col}`)).toBe(true)
        for (const inc of m.game.you.incoming) {
          expect(inc.result).toBe(resolveShot(humanPlanes, { row: inc.row, col: inc.col }).result)
        }
        const json = JSON.stringify(m.game.others)
        expect(json).not.toContain('"row"')
        expect(json).not.toContain('"col"')
      }
    }
  })

  it('Review Focus #2：duel 练习中真人掉线 → 暂停期间电脑不出手；30 秒后真人判负', () => {
    const { table, botIds, bots } = makePractice(2, duelRules, 11, 'expert')
    table.handleGame(HUM, { type: 'placePlane', planes: [HEAD] }, 0)
    let now = 0
    for (let i = 0; i < 200 && table.engine?.phase !== 'playing'; i++) {
      now += STEP
      table.tick(now)
    }
    expect(table.engine?.phase).toBe('playing')

    const disconnectedAt = now
    expect(table.setConnected(HUM, false, now).length).toBeGreaterThan(0)
    expect(table.engine?.phase).toBe('paused')
    const firesBefore = bots[0]!.fireMargins.length

    for (let t = disconnectedAt + STEP; t < disconnectedAt + 30_000; t += STEP) {
      // 暂停期间引擎不产出任何东西（没有超时代打、没有回合推进）
      expect(table.tick(t)).toEqual([])
      expect(table.engine?.phase).toBe('paused')
    }
    // 暂停期间电脑一次都没出手
    expect(bots[0]!.fireMargins.length).toBe(firesBefore)

    const out = table.tick(disconnectedAt + 30_000)
    const go = out.find((o) => o.to === HUM && o.msg.type === 'gameOver')
    expect(go).toBeDefined()
    const result = (go as { msg: { type: 'gameOver'; result: { reason: string; ranking: { playerId: string; rank: number }[] } } }).msg.result
    expect(result.reason).toBe('forfeit')
    expect(result.ranking[0]).toMatchObject({ playerId: botIds[0], rank: 1 })
    expect(table.phase).toBe('waiting')
  })

  it('Review Focus #2：混战练习中真人离开 → 立即关桌，之后 tick 不再产出任何消息', () => {
    const { table } = makePractice(4, meleeRules, 5, 'beginner')
    table.handleGame(HUM, { type: 'placePlane', planes: [HEAD] }, 0)
    let now = 0
    for (let i = 0; i < 5; i++) {
      now += STEP
      table.tick(now)
    }
    expect(table.phase).toBe('inGame')
    expect(table.leave(HUM, now).every((o) => o.to === HUM)).toBe(true)
    expect(table.isClosed).toBe(true)
    for (let i = 0; i < 20; i++) {
      now += STEP
      expect(table.tick(now)).toEqual([])
    }
  })
})
