/** 端到端：2 人好友房自定义规则对决（12×12、2 架），真实 WebSocket，v2 协议。 */
import { describe, it, expect, afterAll } from 'vitest'
import { candidateHeads, cellKey, type Cell, type RuleSet } from '@plane-duel/shared'
import { createServer } from '../src/main'
import { wsClient } from './ws-client'

const srv = await createServer({ port: 0, devMode: false })
afterAll(() => srv.close())

const RULES: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 30, hintAllowed: true }

describe('完整对局（真实 WebSocket）', () => {
  it('两个客户端通过房间号用自定义规则打完一局，由推理击落全部飞机', async () => {
    const a = wsClient(srv.port)
    const b = wsClient(srv.port)
    await a.open()
    await b.open()
    a.send({ type: 'auth', playerId: 'alice' })
    b.send({ type: 'auth', playerId: 'bob' })
    await a.next('ready')
    await b.next('ready')

    a.send({ type: 'createRoom', capacity: 2, rules: RULES, listed: false })
    const created = (await a.next('tableState')).table
    expect(created.rules).toEqual(RULES)
    b.send({ type: 'joinRoom', roomCode: created.roomCode })
    await b.next('tableState')
    a.send({ type: 'setReady', ready: true, rulesVersion: 0 })
    b.send({ type: 'setReady', ready: true, rulesVersion: 0 })
    for (const c of [a, b]) {
      const st = await c.next('state', (m) => m.game !== null)
      expect(st.game).toMatchObject({ mode: 'duel', phase: 'placing' })
    }

    a.send({ type: 'placePlane', planes: [{ row: 2, col: 2 }, { row: 8, col: 8 }] })
    b.send({ type: 'placePlane', planes: [{ row: 2, col: 9 }, { row: 9, col: 3 }] })

    // 进入 playing 的 phaseChanged 带先手
    const started = await a.next('phaseChanged', (m) => m.phase === 'playing')
    expect(['alice', 'bob']).toContain(started.turn)

    const sock = { alice: a, bob: b } as const
    /** 开炮方 → 对方飞机 id → 机身命中 */
    const bodyHits: Record<string, Map<string, Cell[]>> = { alice: new Map(), bob: new Map() }
    const downed: Record<string, Set<string>> = { alice: new Set(), bob: new Set() }
    const fired: Record<string, Set<string>> = { alice: new Set(), bob: new Set() }
    let turn: 'alice' | 'bob' = started.turn
    let over: any = null

    // 搜索策略：有命中时打该架飞机的候选机头，否则按 3 格步长扫描（3×3 飞机必被扫到机身）
    const scan: Cell[] = []
    for (let r = 1; r < RULES.boardSize; r += 3) for (let c = 1; c < RULES.boardSize; c += 3) scan.push({ row: r, col: c })

    for (let i = 0; i < 200 && !over; i++) {
      const shooter = turn
      const fresh = (c: Cell) => !fired[shooter]!.has(cellKey(c))
      let pick: Cell | undefined
      for (const [planeId, hits] of bodyHits[shooter]!) {
        if (downed[shooter]!.has(planeId)) continue
        pick = candidateHeads(hits, RULES.boardSize).find(fresh)
        if (pick) break
      }
      pick ??= scan.find(fresh)!
      fired[shooter]!.add(cellKey(pick))
      sock[shooter].send({ type: 'fire', row: pick.row, col: pick.col })

      // 双方都会收到 shotResult；从开炮方的收件箱读
      const shot = await sock[shooter].next('shotResult')
      const other = shooter === 'alice' ? 'bob' : 'alice'
      await sock[other].next('shotResult')
      expect([shot.row, shot.col]).toEqual([pick.row, pick.col])

      if (shot.result === 'body') {
        const m = bodyHits[shooter]!
        m.set(shot.planeId, [...(m.get(shot.planeId) ?? []), pick])
      }
      if (shot.result === 'head') {
        downed[shooter]!.add(shot.planeId)
        if (downed[shooter]!.size === RULES.planeCount) over = await sock[shooter].next('gameOver')
      }
      turn = shot.nextTurn
    }

    expect(over).not.toBeNull()
    expect(over.result.reason).toBe('allPlanes')
    expect(over.result.ranking[0].rank).toBe(1)
    // 推理应很快收敛：每方 16 格扫描 + 每架 ≤ 8 个候选
    expect(fired.alice!.size + fired.bob!.size).toBeLessThan(100)

    // 结束后桌子回到等候室，带上局结果
    const ts = await b.next('tableState', (m) => m.table.phase === 'waiting' && m.table.lastResult !== null)
    expect(ts.table.lastResult).toEqual({ ...over.result, botIds: [] })
    a.close()
    b.close()
  }, 20000)
})
