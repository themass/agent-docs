/**
 * P2 端到端（Task 16）：真实 WebSocket + 假时钟。
 *
 * 覆盖：人机练习混战（含 Review Focus #1 隐私不变量）、匹配补位成局、
 * 公开房间列表 + 踢人 + 封禁重进、P0 安全回归（bot 前缀与顶号关闭码）。
 *
 * devMode: false → 服务端不自带定时器，时间只由测试推进（srv.tick()）。
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import WebSocket from 'ws'
import {
  PRESETS,
  autoPlace,
  cellsOfPlane,
  candidateHeads,
  cellKey,
  type Cell,
  type RuleSet,
} from '@plane-duel/shared'
import { createServer, type ServerHandle } from '../src/main'
import { mulberry32 } from '../../../packages/shared/test/helpers'
import { wsClient, type WsClient } from './ws-client'

// ---------------------------------------------------------------- 假时钟与驱动

let fakeNow = 1_700_000_000_000
const fake = { now: (): number => fakeNow }
let srv: ServerHandle

const sleep = (ms = 0) => new Promise<void>((r) => setTimeout(r, ms))

/**
 * 注册等待 → 推进假时钟直到命中。
 * 电脑的出手时机挂在假时钟上，所以「等对手行动」= 「推进服务端时间」。
 */
async function driven(
  c: WsClient,
  type: string,
  pred: (m: any) => boolean = () => true,
  maxTicks = 120,
  stepMs = 500,
): Promise<any> {
  const p = c.next(type, pred, 60_000)
  for (let i = 0; i < maxTicks; i++) {
    const r = await Promise.race([p.then((m) => ({ hit: m as any })), sleep(1).then(() => ({ hit: null }))])
    if (r.hit !== null) return r.hit
    fakeNow += stepMs
    srv.tick()
  }
  return p // 仍未命中：让 next 的超时把失败报出来
}

/** 递归找出所有「射击结果」记录（带字符串 result 字段的对象）的路径 */
function resultPaths(obj: unknown, path = ''): string[] {
  const out: string[] = []
  if (Array.isArray(obj)) {
    obj.forEach((v, i) => out.push(...resultPaths(v, `${path}[${i}]`)))
    return out
  }
  if (obj !== null && typeof obj === 'object') {
    const o = obj as Record<string, unknown>
    if (typeof o.result === 'string' && ['hit', 'miss', 'body', 'head'].includes(o.result)) out.push(path)
    for (const [k, v] of Object.entries(o)) if (k !== 'result') out.push(...resultPaths(v, `${path}.${k}`))
  }
  return out
}

/** 射击结果允许出现的路径：本人本轮 shots / 打在我身上的 incoming / state 里我自己的两份 */
const ALLOWED = [
  /^\.shots\[\d+\]$/,
  /^\.incoming\[\d+\]$/,
  /^\.game\.you\.shots\[\d+\]$/,
  /^\.game\.you\.incoming\[\d+\]$/,
]

beforeAll(async () => {
  srv = await createServer({ port: 0, devMode: false, clock: fake, botFillMs: 30_000 })
})
afterAll(() => srv.close())

// ---------------------------------------------------------------- 1. 人机练习混战

describe('P2 端到端', () => {
  it('人机练习：1 真人 + 3 电脑打完一局；射击结果只出现在允许的位置', async () => {
    const me = 'p2-practice'
    const c = wsClient(srv.port)
    await c.open()
    c.send({ type: 'auth', playerId: me, nickname: '练习者' })
    await c.next('ready')

    c.send({ type: 'createPractice', capacity: 4, preset: 'standard' })
    const st = await c.next('state', (m) => m.game !== null)
    expect(st.game).toMatchObject({ mode: 'melee', phase: 'placing' })
    const rules = st.table.rules as RuleSet
    expect(rules).toEqual(PRESETS.standard)

    const heads = autoPlace(rules.boardSize, rules.planeCount, mulberry32(42))
    const planeCells = new Set(heads.flatMap(cellsOfPlane).map(cellKey))
    c.send({ type: 'placePlane', planes: heads })

    await driven(c, 'phaseChanged', (m) => m.phase === 'playing' && m.round === 1)

    // 3 格步长扫描，保证打遍全场（只打自己没打过的格子）
    const scan: Cell[] = []
    for (let r = 1; r < rules.boardSize; r += 3) for (let cc = 1; cc < rules.boardSize; cc += 3) scan.push({ row: r, col: cc })
    const fired = new Set<string>()
    const firedByRound = new Map<number, Cell>()
    let round = 1
    for (; round < 80; round++) {
      const cell = scan.find((x) => !fired.has(cellKey(x))) ?? { row: 1, col: round % (rules.boardSize - 1) }
      fired.add(cellKey(cell))
      firedByRound.set(round, cell)
      c.send({ type: 'fire', row: cell.row, col: cell.col })
      await driven(c, 'roundResult', (m) => m.round === round)
      if (c.log.some((m) => m.type === 'gameOver')) break
      await driven(c, 'phaseChanged', (m) => m.phase === 'playing' && m.round === round + 1)
    }

    const go = await driven(c, 'gameOver', () => true, 5)
    expect(go.result.ranking).toHaveLength(4)

    const ts = await driven(c, 'tableState', (m) => m.table.phase === 'waiting' && m.table.lastResult !== null, 5)
    expect(ts.table.lastResult.botIds).toHaveLength(3)

    // —— Review Focus #1（端到端）：含 result 的对象只允许出现在 4 个位置，且内容自洽
    for (const m of c.log) {
      const paths = resultPaths(m)
      for (const path of paths) {
        expect(ALLOWED.some((re) => re.test(path)), `${m.type} 出现了不该有结果的路径 ${path}`).toBe(true)
      }
      if (m.type === 'roundResult') {
        const mine = firedByRound.get(m.round)
        for (const s of m.shots) {
          expect(s.targetId).not.toBe(me)
          expect({ row: s.row, col: s.col }).toEqual(mine) // 本人本轮所打的格
        }
        for (const s of m.incoming) {
          expect(s.by).not.toBe(me)
          if (s.result !== 'miss') expect(planeCells.has(cellKey(s))).toBe(true) // 与我飞机一致
        }
      }
      if (m.type === 'state' && m.game !== null) {
        for (const s of m.game.you.shots) expect(fired.has(cellKey(s))).toBe(true)
        for (const s of m.game.you.incoming) {
          expect(s.by).not.toBe(me)
          if (s.result !== 'miss') expect(planeCells.has(cellKey(s))).toBe(true)
        }
      }
    }
    // 混战里绝不允许出现对决的单发结果消息
    expect(c.log.some((m) => m.type === 'shotResult')).toBe(false)
    c.close()
  }, 60_000)

  // ---------------------------------------------------------------- 2. 补位成局

  it('两名真人排 3 人区，30 秒后由电脑补位成局（混战），打完标注 botIds', async () => {
    // MIN_HUMANS=2：单人排队只收"等待真人"（humansNeeded>0），永不补位——
    // 所以补位场景必须是 2 真人 + 3 人区：缺的 1 座由电脑补。
    const a = wsClient(srv.port)
    const b = wsClient(srv.port)
    await a.open()
    await b.open()
    a.send({ type: 'auth', playerId: 'p2-qa', nickname: '排队甲' })
    b.send({ type: 'auth', playerId: 'p2-qb', nickname: '排队乙' })
    await a.next('ready')
    await b.next('ready')

    a.send({ type: 'queueJoin', capacity: 3, preset: 'beginner' })
    await a.next('queueStatus')
    b.send({ type: 'queueJoin', capacity: 3, preset: 'beginner' })
    const qa = await a.next('queueStatus', (m) => m.waiting === 2)
    expect(qa).toMatchObject({ capacity: 3, preset: 'beginner', humansNeeded: 0 })
    expect(qa.botFillAt).not.toBeNull()

    // 推进到补位点（超过 30 秒）
    fakeNow += 31_000
    srv.tick()

    // 真人先入座、电脑座位随后到达：等含 bot 座位的快照
    const tsA = await a.next('tableState', (m) => m.table.kind === 'match' && m.table.seats.some((s: any) => s?.bot))
    const tsB = await b.next('tableState', (m) => m.table.kind === 'match' && m.table.seats.some((s: any) => s?.bot))
    expect(tsB.table.roomCode).toBe(tsA.table.roomCode)
    const botSeats = tsA.table.seats.filter((s: any) => s?.bot)
    expect(botSeats).toHaveLength(1)
    expect(tsA.table.rules).toEqual(PRESETS.beginner)

    a.send({ type: 'setReady', ready: true, rulesVersion: tsA.table.rulesVersion })
    b.send({ type: 'setReady', ready: true, rulesVersion: tsA.table.rulesVersion })
    const st = await driven(a, 'state', (m) => m.game !== null)
    expect(st.game).toMatchObject({ mode: 'melee', phase: 'placing' })
    b.send({ type: 'placePlane', planes: [{ row: 2, col: 2 }] })
    const rules = tsA.table.rules as RuleSet
    a.send({ type: 'placePlane', planes: autoPlace(rules.boardSize, rules.planeCount, mulberry32(7)) })

    const scan: Cell[] = []
    for (let r = 1; r < rules.boardSize; r += 3) for (let cc = 1; cc < rules.boardSize; cc += 3) scan.push({ row: r, col: cc })
    const fired = { 'p2-qa': new Set<string>(), 'p2-qb': new Set<string>() }
    const alive: Record<string, boolean> = { 'p2-qa': true, 'p2-qb': true }
    let round = 0
    let over: any = null
    for (let i = 0; i < 60 && over === null; i++) {
      const pc = await driven(a, 'phaseChanged', (m) => m.phase === 'playing' && m.round !== round)
      round = pc.round
      for (const [id, c] of [['p2-qa', a], ['p2-qb', b]] as const) {
        if (!alive[id]) continue
        const pick = scan.find((x) => !fired[id]!.has(cellKey(x))) ?? { row: 1, col: 1 }
        fired[id]!.add(cellKey(pick))
        c.send({ type: 'fire', row: pick.row, col: pick.col })
      }
      for (const c of [a, b]) {
        const rr = await driven(c, 'roundResult', (m) => m.round === round, 60)
        for (const id of rr.eliminated) if (id in alive) alive[id] = false
      }
      // 只剩 1 人时服务端直接 gameOver（不再有下一轮 phaseChanged）
      over = a.log.find((m) => m.type === 'gameOver') ?? null
    }

    expect(over).not.toBeNull()
    expect(over.result.ranking).toHaveLength(3)
    const ts1 = await driven(a, 'tableState', (m) => m.table.phase === 'waiting' && m.table.lastResult !== null, 5)
    expect(ts1.table.lastResult.botIds).toHaveLength(1)
    a.close()
    b.close()
  }, 120_000)

  // ---------------------------------------------------------------- 3. 列表 + 踢人

  it('公开列表可加入；被踢后房间号与列表都进不来（BANNED）', async () => {
    const A = wsClient(srv.port)
    const B = wsClient(srv.port)
    const C = wsClient(srv.port)
    await Promise.all([A.open(), B.open(), C.open()])
    A.send({ type: 'auth', playerId: 'p2-host', nickname: '房主甲' })
    B.send({ type: 'auth', playerId: 'p2-guest', nickname: '路人乙' })
    C.send({ type: 'auth', playerId: 'p2-other', nickname: '路人丙' })
    await Promise.all([A.next('ready'), B.next('ready'), C.next('ready')])

    A.send({ type: 'createRoom', capacity: 3, rules: { ...PRESETS.standard }, listed: true })
    const created = (await A.next('tableState')).table
    const roomCode = created.roomCode as string

    // B 订阅：拿到快照；JSON 里没有房间号（只给 tableId）
    B.send({ type: 'roomListSubscribe', capacity: 3 })
    const rl = await B.next('roomList', (m) => m.entries.length === 1)
    const entry = rl.entries[0]
    expect(entry).toMatchObject({ capacity: 3, hostNickname: '房主甲', seated: 1 })
    expect(JSON.stringify(rl.entries)).not.toContain('"roomCode"')
    for (const e of rl.entries) expect(Object.values(e)).not.toContain(roomCode)

    // B 从列表加入
    B.send({ type: 'joinListed', tableId: entry.tableId })
    await B.next('tableState', (m) => m.table.seats.some((s: any) => s?.playerId === 'p2-guest'))
    await A.next('tableState', (m) => m.table.seats.filter(Boolean).length === 2)

    // A 踢掉 B；B 收到 kicked
    A.send({ type: 'kick', playerId: 'p2-guest' })
    const kicked = await B.next('kicked')
    expect(kicked.roomCode).toBe(roomCode)

    // B 用房间号或列表都进不来
    B.send({ type: 'joinRoom', roomCode })
    await B.next('error', (m) => m.code === 'BANNED')
    B.send({ type: 'joinListed', tableId: entry.tableId })
    await B.next('error', (m) => m.code === 'BANNED')

    // C 订阅：看到座位回到 1
    C.send({ type: 'roomListSubscribe', capacity: 3 })
    const rl2 = await C.next('roomList', (m) => m.entries.length === 1)
    expect(rl2.entries[0]).toMatchObject({ hostNickname: '房主甲', seated: 1 })

    for (const c of [A, B, C]) c.close()
  }, 30_000)

  // ---------------------------------------------------------------- 4. P0 安全回归

  it('auth 用 bot 前缀被拒（BAD_SHAPE）；顶号关闭旧连接码 4000', async () => {
    const spoof = wsClient(srv.port)
    await spoof.open()
    spoof.send({ type: 'auth', playerId: 'bot:x', nickname: '假电脑' })
    await spoof.next('error', (m) => m.code === 'BAD_SHAPE')
    spoof.close()

    // 顶号：第二个连接认证成功，第一个被服务端以 4000 关闭
    const first = wsClient(srv.port)
    await first.open()
    first.send({ type: 'auth', playerId: 'p2-dup', nickname: '同一人' })
    const rdy = await first.next('ready')

    const closed = new Promise<number>((res) => {
      const ws = new WebSocket(`ws://127.0.0.1:${srv.port}`)
      ws.on('open', () => ws.send(JSON.stringify({ type: 'auth', playerId: 'p2-dup', token: rdy.token })))
      ws.on('close', (code) => res(code))
    })
    const second = wsClient(srv.port)
    await second.open()
    second.send({ type: 'auth', playerId: 'p2-dup', token: rdy.token, nickname: '同一人' })
    await second.next('ready')

    expect(await closed).toBe(4000)
    first.close()
    second.close()
  }, 15_000)
})
