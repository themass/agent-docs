/**
 * 端到端：4 人好友房混战，真实 WebSocket（Review Focus #1 的端到端版）。
 *
 * 隐私不变量（Task 7 裁定）：玩家可以看到别人开炮的坐标（那一炮也落在他自己的棋盘上），
 * 但永远看不到某一炮在第三人棋盘上的**结果**。因此这里断言的是结果的归属，而不是坐标。
 */
import { describe, it, expect, afterAll } from 'vitest'
import { autoPlace, candidateHeads, cellKey } from '@plane-duel/shared'
import type { Cell, RuleSet } from '@plane-duel/shared'
import { createServer } from '../src/main'
import { mulberry32 } from '../../../packages/shared/test/helpers'
import { wsClient, type WsClient } from './ws-client'

const srv = await createServer({ port: 0, devMode: false })
afterAll(() => srv.close())

const RULES: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

type Bot = {
  id: string
  c: WsClient
  alive: boolean
  /** 我打过的格子 */
  fired: Set<string>
  /** 每轮我打的格子 */
  firedByRound: Map<number, Cell>
  /** 对手 → 飞机 → 我在其机身上的命中 */
  hits: Map<string, Map<string, Cell[]>>
  /** 对手 → 被我（或别人）击落的飞机 */
  downed: Map<string, Set<string>>
}

/** 3 格步长扫描：3×3 飞机必被扫到 */
function scanCells(size: number): Cell[] {
  const out: Cell[] = []
  for (let r = 1; r < size; r += 3) for (let c = 1; c < size; c += 3) out.push({ row: r, col: c })
  return out
}

/** 有命中则打该架飞机的候选机头（交集），否则扫描；只选自己没打过的格子（一炮打所有对手）。 */
function pick(bot: Bot, alive: Set<string>): Cell {
  const fresh = (c: Cell) => !bot.fired.has(cellKey(c))
  for (const [target, planes] of bot.hits) {
    if (!alive.has(target)) continue
    for (const [planeId, hits] of planes) {
      if (bot.downed.get(target)?.has(planeId)) continue
      const cand = candidateHeads(hits, RULES.boardSize).find(fresh)
      if (cand) return cand
    }
  }
  const scan = scanCells(RULES.boardSize).find(fresh)
  if (scan) return scan
  for (let r = 0; r < RULES.boardSize; r++)
    for (let c = 0; c < RULES.boardSize; c++) if (fresh({ row: r, col: c })) return { row: r, col: c }
  throw new Error('no cell left')
}

describe('混战（真实 WebSocket）', () => {
  it('4 人好友房：建房 → 加入 → 准备 → 自动摆放 → 推理开炮直到 gameOver；结果私有', async () => {
    const ids = ['m-alice', 'm-bob', 'm-carol', 'm-dave']
    const bots: Bot[] = ids.map((id) => ({
      id,
      c: wsClient(srv.port),
      alive: true,
      fired: new Set(),
      firedByRound: new Map(),
      hits: new Map(),
      downed: new Map(),
    }))
    await Promise.all(bots.map((b) => b.c.open()))
    for (const b of bots) b.c.send({ type: 'auth', playerId: b.id, nickname: b.id.slice(2) })
    for (const b of bots) expect((await b.c.next('ready')).nickname).toBe(b.id.slice(2))

    const [host, ...guests] = bots
    host!.c.send({ type: 'createRoom', capacity: 4, rules: RULES, listed: false })
    const roomCode = (await host!.c.next('tableState')).table.roomCode as string
    for (const g of guests) {
      g.c.send({ type: 'joinRoom', roomCode })
      await g.c.next('tableState', (m) => m.table.seats.some((s: any) => s?.playerId === g.id))
    }
    for (const b of bots) b.c.send({ type: 'setReady', ready: true, rulesVersion: 0 })
    for (const b of bots) {
      const st = await b.c.next('state', (m) => m.game !== null)
      expect(st.game).toMatchObject({ mode: 'melee', phase: 'placing' })
    }

    bots.forEach((b, i) => {
      b.c.send({ type: 'placePlane', planes: autoPlace(RULES.boardSize, RULES.planeCount, mulberry32(100 + i)) })
    })
    for (const b of bots) await b.c.next('planeAccepted')
    for (const b of bots) expect(await b.c.next('phaseChanged', (m) => m.round === 1)).toMatchObject({ phase: 'playing' })

    const alive = new Set(ids)
    let round = 1
    let over: any[] = []
    for (; round < 60; round++) {
      for (const b of bots) {
        if (!alive.has(b.id)) continue
        const cell = pick(b, alive)
        b.fired.add(cellKey(cell))
        b.firedByRound.set(round, cell)
        b.c.send({ type: 'fire', row: cell.row, col: cell.col })
      }
      for (const b of bots) {
        const rr = await b.c.next('roundResult', (m) => m.round === round)
        // 私有：shots 只能是我这一炮的结果，incoming 只能是别人打在我身上的
        const mine = b.firedByRound.get(round)
        for (const s of rr.shots) {
          expect(s.targetId).not.toBe(b.id)
          expect({ row: s.row, col: s.col }).toEqual(mine)
        }
        for (const s of rr.incoming) expect(s.by).not.toBe(b.id)
        for (const s of rr.shots) {
          if (!b.hits.has(s.targetId)) b.hits.set(s.targetId, new Map())
          const planes = b.hits.get(s.targetId)!
          if (s.result === 'body') planes.set(s.planeId, [...(planes.get(s.planeId) ?? []), { row: s.row, col: s.col }])
          if (s.result === 'head') {
            if (!b.downed.has(s.targetId)) b.downed.set(s.targetId, new Set())
            b.downed.get(s.targetId)!.add(s.planeId)
          }
        }
        for (const id of rr.eliminated) alive.delete(id)
      }
      if (alive.size <= 1) break
      for (const b of bots) await b.c.next('phaseChanged', (m) => m.round === round + 1)
    }

    over = await Promise.all(bots.map((b) => b.c.next('gameOver')))
    const result = over[0].result
    for (const o of over) expect(o.result).toEqual(result)
    expect(result.reason).toBe('lastStanding')
    expect(result.ranking).toHaveLength(4)
    expect(result.ranking.some((r: any) => r.rank === 1)).toBe(true)
    expect(round).toBeLessThan(60)

    for (const b of bots) {
      const ts = await b.c.next('tableState', (m) => m.table.phase === 'waiting' && m.table.lastResult !== null)
      expect(ts.table.roomCode).toBe(roomCode)
      expect(ts.table.lastResult).toEqual({ ...result, botIds: [] })
    }

    // Review Focus #1：每人每轮只收到一份 roundResult（自己的那份），且从未收到对决的 shotResult
    for (const b of bots) {
      const rounds = b.c.log.filter((m) => m.type === 'roundResult').map((m) => m.round)
      expect(new Set(rounds).size).toBe(rounds.length)
      expect(b.c.log.some((m) => m.type === 'shotResult')).toBe(false)
      for (const m of b.c.log.filter((x) => x.type === 'roundResult')) {
        for (const s of m.shots) expect({ row: s.row, col: s.col }).toEqual(b.firedByRound.get(m.round))
        for (const s of m.incoming) expect(s.by).not.toBe(b.id)
      }
    }

    for (const b of bots) b.c.close()
  }, 30000)
})
