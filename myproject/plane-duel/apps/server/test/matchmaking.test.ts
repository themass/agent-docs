import { describe, it, expect } from 'vitest'
import { INITIAL_MMR } from '@plane-duel/shared'
import { BOT_FILL_AFTER_MS, MIN_HUMANS, Matchmaking } from '../src/matchmaking'
import type { QueueKey } from '../src/matchmaking'

const K2: QueueKey = { capacity: 2, preset: 'standard' }
const K3: QueueKey = { capacity: 3, preset: 'standard' }
const K4: QueueKey = { capacity: 4, preset: 'standard' }
const K2B: QueueKey = { capacity: 2, preset: 'beginner' }

const statusTo = (out: { to: string; msg: any }[], to: string) =>
  out.filter((o) => o.to === to && o.msg.type === 'queueStatus').map((o) => o.msg)

/** 补位参数（spec §20.5）：2/3 人桌 30 秒，4 人桌 45 秒。 */
const fill = { botFillMs: BOT_FILL_AFTER_MS }

describe('多队列匹配', () => {
  it('不同 (人数, 档位) 的队列互不干扰', () => {
    const m = new Matchmaking({})
    expect(m.join('a', K2, 0).group).toBeNull()
    expect(m.join('b', K2B, 0).group).toBeNull()
    expect(m.join('c', K4, 0).group).toBeNull()
    expect(m.size(K2)).toBe(1)
    expect(m.size(K2B)).toBe(1)
    expect(m.size(K4)).toBe(1)
    const r = m.join('d', K2, 10)
    expect(r.group).toEqual({ key: K2, playerIds: ['a', 'd'], botSeats: 0 })
    expect(m.size(K2B)).toBe(1)
    expect(m.size(K4)).toBe(1)
    expect(m.queueOf('b')).toEqual(K2B)
  })

  it('4 人队列凑满 4 人才成组，按入队顺序', () => {
    const m = new Matchmaking({})
    expect(m.join('p1', K4, 0).group).toBeNull()
    expect(m.join('p2', K4, 1).group).toBeNull()
    expect(m.join('p3', K4, 2).group).toBeNull()
    const r = m.join('p4', K4, 3)
    expect(r.group).toEqual({ key: K4, playerIds: ['p1', 'p2', 'p3', 'p4'], botSeats: 0 })
  })

  it('入队/离队时向该队列全体推送 queueStatus { waiting, botFillAt, humansNeeded }', () => {
    const m = new Matchmaking({})
    m.join('x', K2B, 0)
    const s = (waiting: number) => ({
      type: 'queueStatus',
      capacity: 4,
      preset: 'standard',
      waiting,
      botFillAt: null,
      humansNeeded: Math.max(0, MIN_HUMANS - waiting),
    })
    const r1 = m.join('a', K4, 0)
    expect(statusTo(r1.out, 'a')).toEqual([s(1)])
    const r2 = m.join('b', K4, 1)
    expect(statusTo(r2.out, 'a')).toEqual([s(2)])
    expect(statusTo(r2.out, 'b')).toEqual([s(2)])
    expect(r2.out.some((o) => o.to === 'x')).toBe(false)
    const out = m.leave('a', 2)
    expect(out).toEqual([{ to: 'b', msg: s(1) }])
    expect(m.queueOf('a')).toBeNull()
    expect(m.leave('a', 3)).toEqual([])
  })

  it('加入另一个队列会自动离开原队列', () => {
    const m = new Matchmaking({})
    m.join('a', K4, 0)
    m.join('b', K4, 0)
    const r = m.join('a', K2, 5)
    expect(m.queueOf('a')).toEqual(K2)
    expect(m.size(K4)).toBe(1)
    expect(statusTo(r.out, 'b')).toEqual([
      { type: 'queueStatus', capacity: 4, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 },
    ])
    // 重复加入同一队列不产生第二个自己
    m.join('a', K2, 6)
    expect(m.size(K2)).toBe(1)
  })

  it('成组后这些人从队列移除，其余人收到新的 queueStatus', () => {
    const m = new Matchmaking({})
    m.join('a', K3, 0)
    m.join('b', K3, 1)
    const r = m.join('c', K3, 2)
    expect(r.group?.playerIds).toEqual(['a', 'b', 'c'])
    expect(m.size(K3)).toBe(0)
    for (const p of ['a', 'b', 'c']) expect(m.queueOf(p)).toBeNull()
    // 成组的人不再收到 queueStatus
    expect(r.out.filter((o) => o.msg.type === 'queueStatus')).toEqual([])
    const r2 = m.join('d', K3, 3)
    expect(r2.out).toEqual([
      { to: 'd', msg: { type: 'queueStatus', capacity: 3, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 } },
    ])
  })

  it('成组不影响其它队列的人', () => {
    const m = new Matchmaking({})
    m.join('x', K4, 0)
    m.join('a', K2, 0)
    const r = m.join('b', K2, 1)
    expect(r.group?.playerIds).toEqual(['a', 'b'])
    expect(r.out.some((o) => o.to === 'x')).toBe(false)
    expect(m.size(K4)).toBe(1)
  })

  it('60 秒提示一次 queueTimeout，不出队（补位关闭＝默认）', () => {
    const m = new Matchmaking({ enqueueWaitMs: 60_000 })
    m.join('a', K4, 0)
    expect(m.tick(59_999).out).toEqual([])
    expect(m.tick(60_000).out).toEqual([{ to: 'a', msg: { type: 'queueTimeout' } }])
    expect(m.tick(61_000).out).toEqual([])
    expect(m.queueOf('a')).toEqual(K4)
    expect(m.size(K4)).toBe(1)
  })

  // ---------------- P2 补位（spec §20.5） ----------------

  it('补位关闭（默认）：行为与 P1 相同，botFillAt 恒为 null', () => {
    const m = new Matchmaking({})
    const r1 = m.join('a', K4, 0)
    const r2 = m.join('b', K4, 100)
    expect(statusTo([...r1.out, ...r2.out], 'b')[0].botFillAt).toBeNull()
    expect(m.tick(10_000).groups).toEqual([])
    expect(m.size(K4)).toBe(2)
  })

  it('只有 1 人：botFillAt 为 null，humansNeeded = 1，等多久都不补位', () => {
    const m = new Matchmaking(fill)
    const r = m.join('a', K4, 0)
    expect(statusTo(r.out, 'a')).toEqual([
      { type: 'queueStatus', capacity: 4, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 },
    ])
    expect(m.tick(10_000_000).groups).toEqual([])
    expect(m.tick(10_000_000).out).toEqual([])
    expect(m.size(K4)).toBe(1)
  })

  it('补位开启：第 2 人入队后 botFillAt = 第 2 人的入队时刻 + 30000（3 人桌）', () => {
    const m = new Matchmaking(fill)
    m.join('a', K3, 1000)
    const r = m.join('b', K3, 5000)
    const expected = {
      type: 'queueStatus',
      capacity: 3,
      preset: 'standard',
      waiting: 2,
      botFillAt: 5000 + 30_000,
      humansNeeded: 0,
    }
    expect(statusTo(r.out, 'a')).toEqual([expected])
    expect(statusTo(r.out, 'b')).toEqual([expected])
  })

  it('第 2 人离队后 botFillAt 回到 null（只剩 1 人不补位）', () => {
    const m = new Matchmaking(fill)
    m.join('a', K3, 0)
    m.join('b', K3, 100)
    const out = m.leave('b', 200)
    expect(statusTo(out, 'a')).toEqual([
      { type: 'queueStatus', capacity: 3, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 },
    ])
    expect(m.tick(100_000).groups).toEqual([])
  })

  it('29 999 ms 不成组；30 000 ms 时 3 名真人成组，botSeats = 1（4 人队列，自定义 30 秒）', () => {
    const m = new Matchmaking({ botFillMs: 30_000 })
    m.join('a', K4, 0)
    m.join('b', K4, 10)
    m.join('c', K4, 20)
    expect(m.tick(10 + 29_999).groups).toEqual([])
    const r = m.tick(10 + 30_000)
    expect(r.groups).toEqual([{ key: K4, playerIds: ['a', 'b', 'c'], botSeats: 1 }])
    expect(m.size(K4)).toBe(0)
  })

  it('4 人队列倒计时为 45 秒', () => {
    const m = new Matchmaking(fill)
    m.join('a', K4, 0)
    const r = m.join('b', K4, 100)
    expect(statusTo(r.out, 'a')[0].botFillAt).toBe(100 + 45_000)
    expect(m.tick(100 + 44_999).groups).toEqual([])
    expect(m.tick(100 + 45_000).groups).toEqual([{ key: K4, playerIds: ['a', 'b'], botSeats: 2 }])
  })

  it('第 3、4 人入队不重置倒计时（以第 2 人的入队时刻为准）', () => {
    const m = new Matchmaking(fill)
    m.join('a', K4, 0)
    m.join('b', K4, 100)
    const r = m.join('c', K4, 20_000)
    expect(statusTo(r.out, 'c')[0].botFillAt).toBe(100 + 45_000)
    // 4 名真人在倒计时到点前入队 → 立即凑满，走正常成组（botSeats 0）
    expect(m.join('d', K4, 30_000).group).toEqual({ key: K4, playerIds: ['a', 'b', 'c', 'd'], botSeats: 0 })
  })

  it('人够（4 名真人）时立即成组，botSeats = 0，不等补位', () => {
    const m = new Matchmaking(fill)
    m.join('a', K4, 0)
    m.join('b', K4, 0)
    m.join('c', K4, 0)
    expect(m.join('d', K4, 1).group).toEqual({ key: K4, playerIds: ['a', 'b', 'c', 'd'], botSeats: 0 })
  })

  it('Review Focus #4：同一 tick 之前已离队的人不在成组里；队列空则不成组', () => {
    // 4 座队列只来了 3 人（不足容量才不会立即成组）；b 在倒计时到点前离队
    const m = new Matchmaking({ ...fill, botFillMs: 30_000 })
    m.join('a', K4, 0)
    m.join('b', K4, 10)
    m.join('c', K4, 20)
    m.leave('b', 30)
    // 锚点变成第 2 人 c（入队于 20）
    const r = m.tick(20 + 30_000)
    expect(r.groups).toEqual([{ key: K4, playerIds: ['a', 'c'], botSeats: 2 }])
    // 队列已空：再 tick 不产出任何东西
    expect(m.tick(100_000)).toEqual({ out: [], groups: [] })
  })

  it('补位成组者从 queueOf 中移除，且不再收到 queueStatus / queueTimeout', () => {
    const m = new Matchmaking({ botFillMs: 30_000, enqueueWaitMs: 1 })
    m.join('a', K3, 0)
    m.join('b', K3, 0)
    const r = m.tick(30_000)
    expect(r.groups).toHaveLength(1)
    for (const p of ['a', 'b']) {
      expect(m.queueOf(p)).toBeNull()
      expect(r.out.filter((o) => o.to === p)).toEqual([])
    }
    // 之后他们也不在任何队列里：leave 不再广播
    expect(m.leave('a', 30_100)).toEqual([])
  })

  it('补位开启时不发 queueTimeout（界面用"等待真人/补位倒计时"表达）', () => {
    const m = new Matchmaking({ ...fill, enqueueWaitMs: 1 })
    m.join('a', K4, 0)
    expect(m.tick(10_000).out).toEqual([])
    m.join('b', K4, 10)
    expect(m.tick(20_000).out.filter((o) => o.msg.type === 'queueTimeout')).toEqual([])
  })
})

describe('P3：MMR 分桶匹配（spec §21.2）', () => {
  // 桶边界：mmrBucket = round(mmr/120)。1200→10，1330→11（相邻），1450→12（隔两桶）
  const NEAR = INITIAL_MMR + 130 // 相邻桶（bucket 11）
  const FAR = INITIAL_MMR + 250 // 隔 ≥2 桶（bucket 12）

  it('同桶立即成组（默认 mmr 即同桶）', () => {
    const m = new Matchmaking({})
    expect(m.join('a', K2, 0).group).toBeNull()
    expect(m.join('b', K2, 1, INITIAL_MMR + 10)!.group).not.toBeNull()
  })

  it('相邻桶：等待 <15s 不成组，满 15s 后 tick 成组', () => {
    const m = new Matchmaking({})
    m.join('a', K2, 0, INITIAL_MMR)
    expect(m.join('b', K2, 0, NEAR).group).toBeNull()
    expect(m.tick(14_999).groups).toEqual([])
    expect(m.tick(15_000).groups).toEqual([{ key: K2, playerIds: ['a', 'b'], botSeats: 0 }])
  })

  it('隔 ≥2 桶：等待按桶距升级后放行（gap=2 → 30s），不兼容队列不会永久饿死', () => {
    const m = new Matchmaking({})
    m.join('a', K2, 0, INITIAL_MMR)
    expect(m.join('b', K2, 0, FAR).group).toBeNull()
    expect(m.tick(29_999).groups).toEqual([])
    expect(m.tick(30_000).groups).toEqual([{ key: K2, playerIds: ['a', 'b'], botSeats: 0 }])
  })

  it('满员但分桶未放行时不硬凑零电脑真人群；放行时限到了照常成组，也不许补位越闸', () => {
    const m = new Matchmaking({ ...fill })
    m.join('a', K2, 0, INITIAL_MMR)
    m.join('b', K2, 0, FAR)
    // 2 人满 capacity=2：闸门未放行 → 不建组，也不许补位成 botSeats=0 的组
    expect(m.tick(14_999).groups).toEqual([])
    expect(m.size(K2)).toBe(2)
    // 等待到 gap×15s：正常成组（不是补位局）
    expect(m.tick(30_000).groups).toEqual([{ key: K2, playerIds: ['a', 'b'], botSeats: 0 }])
  })

  it('补位倒计时照常：2 人（不同桶但相邻、未满员 capacity=3）等到点带电脑成组', () => {
    const m = new Matchmaking({ ...fill })
    m.join('a', K3, 0, INITIAL_MMR)
    m.join('b', K3, 0, NEAR)
    // 补位局不参与分桶闸门（不计段位，spec §21.2）：到点即组
    expect(m.tick(29_999).groups).toEqual([])
    expect(m.tick(30_000).groups).toEqual([{ key: K3, playerIds: ['a', 'b'], botSeats: 1 }])
  })

  it('4 人满员时贪心挑互相放行的三人先走（同桶优先），剩下的继续等', () => {
    const m = new Matchmaking({})
    m.join('a', K4, 0, INITIAL_MMR) // 桶 10
    m.join('b', K4, 1, INITIAL_MMR + 5) // 桶 10
    m.join('c', K4, 2, INITIAL_MMR + 9) // 桶 10
    m.join('d', K4, 3, FAR) // 桶 12：谁都带不动它
    const r = m.join('e', K4, 4, INITIAL_MMR + 8) // 桶 10 → 满 4 个同桶者
    expect(r.group).toEqual({ key: K4, playerIds: ['a', 'b', 'c', 'e'], botSeats: 0 })
    expect(m.size(K4)).toBe(1) // 只剩 d
  })
})
