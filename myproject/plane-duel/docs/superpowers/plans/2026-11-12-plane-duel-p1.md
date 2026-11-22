# 飞机对决 P1 实施计划：专区、自定义规则、多人混战

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 P0 的 2 人对战基础上，交付三个专区（2 人对决 / 3 人混战 / 4 人混战）、可自定义棋盘与飞机数的好友房、按（人数, 档位）分队列的快速匹配，以及可反复开局的"桌子"式房间。

**Architecture:** 服务端把 P0 的 `Room` 拆成 `Table`（座位、准备、房主、规则、开局与回等候室）和两个实现同一 `Engine` 接口的对局引擎：`DuelEngine`（2 人轮流制，即 P0 行为）与 `MeleeEngine`（3–4 人同时制）。规则参数收拢为 `RuleSet`，校验与预设放在 `packages/shared`，三端共用。客户端新增专区大厅、规则编辑器、等候室、多机摆放和混战合并棋盘。

**Tech Stack:** TypeScript 5、pnpm workspace、Vitest、Node 22 + `ws` + `tsx`、Vite + Vue 3、Capacitor 8

**Spec:** `docs/superpowers/specs/2026-11-11-plane-duel-design.md`，**以 §十九 为准**（§二 的 2 人规则、§九 的断线原则仍有效）

**前置：** P0 已完成，149 个测试全绿（shared 46 / server 86 / client 17）。P0 执行记录：`docs/superpowers/plans/2026-11-11-plane-duel-p0-execution-log.md`。

## Global Constraints

- 棋盘边长 6–16；飞机数 1 到 `min(6, ⌊0.3 × 边长² ÷ 9⌋)`；回合时长 ∈ {10, 15, 20, 30, 45, 60} 秒；摆放时长 = 30 + 15 × 飞机数 秒（spec §19.3）。
- 四档预设（三个专区通用）：入门 8/1/30s/提示允许；标准 10/1/20s/允许；进阶 12/2/20s/禁止；高手 14/3/15s/禁止（spec §19.3）。
- 自定义规则只用于好友房；快速匹配只用四档预设（spec §19.3）。
- 人数 2 → `DuelEngine`（轮流制，P0 行为不变）；人数 3–4 → `MeleeEngine`（同时制）（spec §19.5–19.6）。
- 混战：一炮落在每个存活对手棋盘上；**结果私有**——任何发给玩家 X 的消息都不得含有 Y 打 Z 的坐标（spec §19.6）。
- 混战：超时不代打；连续 3 轮在线未开炮出局；掉线不暂停、不计挂机、30 秒未回出局（spec §19.6）。
- 2 人局：断线暂停 30 秒、超时代打、中途离开判负，全部沿用 P0（spec §二、§19.5）。
- 对方机头坐标任何时刻不下发给其他玩家（spec §八）。
- 等候室掉线保留座位 60 秒；房主离开转给最小座位号；匹配房有人离开即解散（spec §19.4）。
- 好友房：人满且全员准备才开局；房主改规则清空所有人的准备（spec §19.4）。
- 昵称 1–12 字符，服务端去首尾空白与控制字符，不合法回退为"玩家 N"（spec §19.8）。
- 边长 ≥ 12 或混战时两步开炮（选中 → 确认）（spec §19.3）。
- playerId + token 身份校验（P0 C2 修复）保持不变。
- 所有用户可见文案为简体中文。

## Review Focus

计划里各任务的测试不会自然覆盖、但最可能伤到真实玩家的五类情况，已逐条把对应测试加进负责的任务：

1. **混战私有信息泄漏**：任何发给玩家 X 的消息（`roundResult`、`state`、`gameOver`、`submitted`）里，都不应出现 Y 打 Z 的坐标。→ Task 7 的 `no-leak` 测试会扫描 X 收到的全部出站消息。
2. **最后两人同轮互相击落**：排名必须有第 1 名（按命中数决出，或并列第 1），`gameOver.ranking` 不能出现"没有赢家"。→ Task 8。
3. **准备与改规则的竞态**：最后一人点准备时，同步就会开局；之后房主的 `updateRules` 必须被 `ROOM_IN_GAME` 拒绝，对局不能用旧规则开、也不能用新规则开。→ Task 10。
4. **同时出现在两张桌子**：玩家在 A 桌等候时用房间号加入 B 桌，或排队时加入好友房，必须先离开 A 桌或队列，绝不能同时占两个座位。→ Task 12。
5. **混战中开炮后立刻掉线**：已提交的那一炮仍然有效，在本轮结算；掉线只影响之后的轮次。→ Task 9。

**测试写法约定**：各任务里只写了 `it('名称', ...)` 的测试，其断言由该任务的"行为 / 规则 / 算法"段落唯一确定（段落中给出了全部具体数值与错误码），实现者按名称写出断言即可；凡是判断容易出错的地方（Review Focus、排名、预设数值、上限表），计划里已直接给出断言代码。

---

## File Structure

```
packages/shared/src/
  ruleset.ts        新：RuleSet、预设、校验、上限、摆放时长
  placement.ts      新：autoPlace（随机 + 保底整齐排列）
  nickname.ts       新：sanitizeNickname（服务端与客户端共用）
  types.ts          改：协议 v2（桌子、混战消息、排名）
  protocol.ts       改：解析 v2 客户端消息
  rules.ts          不变

apps/server/src/
  engine.ts         新：Engine 接口 + createEngine 工厂 + 共用的摆放阶段辅助
  duel-engine.ts    新：从 room.ts 抽出，2 人轮流制
  melee-engine.ts   新：3–4 人同时制
  table.ts          新：座位、准备、房主、规则、开局、回等候室
  matchmaking.ts    改：多队列 + queueStatus
  hub.ts            改：以 Table 为中心重写路由
  room.ts           删除（Task 6 末尾）

apps/client/src/
  nickname-gen.ts   新：随机昵称生成
  board-model.ts    改：新增 buildTargetCells（混战合并棋盘）
  net/store.ts      改：桌子 + 两种对局状态
  components/
    BoardGrid.vue   改：支持选中态、2×2 小槽标记
    RuleEditor.vue  新
    SeatList.vue    新
    ResultSheet.vue 新：排名结算（两种模式共用）
  views/
    Lobby.vue       改：专区入口 + 昵称
    Zone.vue        新：档位快速匹配 + 好友房
    WaitingRoom.vue 新
    Place.vue       改：多机摆放 + 就绪
    DuelPlay.vue    新：由 Play.vue 改名改造
    MeleePlay.vue   新
```

**拆分理由：** `Table` 只关心"谁坐在哪、是否准备、何时开局"，引擎只关心"一局怎么打"，两者通过 `Engine` 接口交互，于是 2 人与多人引擎可以独立测试、互不影响。`ruleset.ts` 放在 shared，是因为规则编辑器（客户端）与 `createRoom` 校验（服务端）必须使用同一套边界。

---

### Task 1: RuleSet、预设与校验

**Files:**
- Create: `packages/shared/src/ruleset.ts`, `packages/shared/test/ruleset.test.ts`
- Modify: `packages/shared/src/index.ts`

**Interfaces:**
- Produces:
```ts
export const BOARD_MIN = 6, BOARD_MAX = 16, PLANE_HARD_MAX = 6, MAX_DENSITY = 0.3
export const TURN_SECONDS = [10, 15, 20, 30, 45, 60] as const
export type TurnSeconds = (typeof TURN_SECONDS)[number]
export type RuleSet = { boardSize: number; planeCount: number; turnSeconds: TurnSeconds; hintAllowed: boolean }
export type Capacity = 2 | 3 | 4
export type PresetId = 'beginner' | 'standard' | 'advanced' | 'expert'
export const PRESETS: Readonly<Record<PresetId, RuleSet>>
export const PRESET_LABELS: Readonly<Record<PresetId, string>>   // 入门/标准/进阶/高手
export function maxPlanes(boardSize: number): number
export function validateRuleSet(input: unknown): { ok: true; rules: RuleSet } | { ok: false; reason: 'shape' | 'boardSize' | 'planeCount' | 'turnSeconds' }
export function placeSeconds(rules: RuleSet): number
export function planeDensity(rules: RuleSet): number
export function isCapacity(n: unknown): n is Capacity
```

- [ ] **Step 1: 写失败的测试**

```ts
describe('maxPlanes', () => {
  it('与 spec §19.3 表格一致', () => {
    const table: Record<number, number> = { 6: 1, 7: 1, 8: 2, 9: 2, 10: 3, 11: 4, 12: 4, 13: 5, 14: 6, 15: 6, 16: 6 }
    for (const [n, max] of Object.entries(table)) expect(maxPlanes(Number(n))).toBe(max)
  })
  it('上限总能被 3×3 整齐排列放下', () => {
    for (let n = BOARD_MIN; n <= BOARD_MAX; n++) expect(maxPlanes(n)).toBeLessThanOrEqual(Math.floor(n / 3) ** 2)
  })
})
describe('validateRuleSet', () => {
  it('四档预设全部合法', () => { for (const r of Object.values(PRESETS)) expect(validateRuleSet(r).ok).toBe(true) })
  it('预设数值', () => {
    expect(PRESETS.beginner).toEqual({ boardSize: 8, planeCount: 1, turnSeconds: 30, hintAllowed: true })
    expect(PRESETS.standard).toEqual({ boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true })
    expect(PRESETS.advanced).toEqual({ boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false })
    expect(PRESETS.expert).toEqual({ boardSize: 14, planeCount: 3, turnSeconds: 15, hintAllowed: false })
  })
  it.each([5, 17, 10.5, '10'])('边长 %s 非法', (b) => expect(validateRuleSet({ ...PRESETS.standard, boardSize: b })).toEqual({ ok: false, reason: 'boardSize' }))
  it('飞机数超上限非法（10×10 最多 3 架）', () => expect(validateRuleSet({ ...PRESETS.standard, planeCount: 4 })).toEqual({ ok: false, reason: 'planeCount' }))
  it('飞机数 0 非法', () => expect(validateRuleSet({ ...PRESETS.standard, planeCount: 0 })).toEqual({ ok: false, reason: 'planeCount' }))
  it('回合时长不在列表中非法', () => expect(validateRuleSet({ ...PRESETS.standard, turnSeconds: 25 })).toEqual({ ok: false, reason: 'turnSeconds' }))
  it('缺字段或非对象', () => { expect(validateRuleSet(null)).toEqual({ ok: false, reason: 'shape' }); expect(validateRuleSet({ boardSize: 10 })).toEqual({ ok: false, reason: 'shape' }) })
  it('多余字段被丢弃', () => {
    const r = validateRuleSet({ ...PRESETS.standard, cheat: true })
    expect(r.ok && Object.keys(r.rules).sort()).toEqual(['boardSize', 'hintAllowed', 'planeCount', 'turnSeconds'])
  })
})
describe('placeSeconds / planeDensity', () => {
  it('30 + 15 × 飞机数', () => { expect(placeSeconds(PRESETS.standard)).toBe(45); expect(placeSeconds(PRESETS.expert)).toBe(75) })
  it('占比', () => expect(planeDensity(PRESETS.standard)).toBeCloseTo(0.09))
})
```

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C packages/shared exec vitest run ruleset` → Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `ruleset.ts`**

`maxPlanes(n) = Math.min(PLANE_HARD_MAX, Math.floor((MAX_DENSITY * n * n) / 9))`。`validateRuleSet` 的检查顺序：shape（四个字段都在且类型正确：boardSize/planeCount 为 number、turnSeconds 为 number、hintAllowed 为 boolean）→ boardSize（整数且在范围内）→ planeCount（整数、≥1、≤ maxPlanes）→ turnSeconds（在列表中）。返回只含四个字段的新对象。

- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C packages/shared exec vitest run` → Expected: 全部 PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(shared): RuleSet presets and validation"`

---

### Task 2: 自动摆放与昵称清洗

**Files:**
- Create: `packages/shared/src/placement.ts`, `packages/shared/src/nickname.ts`
- Create: `packages/shared/test/placement.test.ts`, `packages/shared/test/nickname.test.ts`

**Interfaces:**
- Consumes: `checkPlacement`（P0）、`maxPlanes`（Task 1）
- Produces:
```ts
export function autoPlace(boardSize: number, planeCount: number, rng: () => number): Cell[]   // 返回机头数组
export function sanitizeNickname(input: unknown, fallback: string): string
```

- [ ] **Step 1: 写失败的测试**

```ts
describe('autoPlace', () => {
  it('每个边长、每个合法飞机数都摆得下且合法（含上限）', () => {
    for (let n = BOARD_MIN; n <= BOARD_MAX; n++)
      for (let k = 1; k <= maxPlanes(n); k++) {
        const heads = autoPlace(n, k, mulberry32(n * 100 + k))
        expect(checkPlacement(heads, n, k)).toEqual({ ok: true })
      }
  })
  it('随机源恒返回 0.999 时（随机尝试最容易失败）仍有解', () => {
    expect(checkPlacement(autoPlace(16, 6, () => 0.999), 16, 6)).toEqual({ ok: true })
  })
  it('同一随机种子结果确定', () => expect(autoPlace(12, 2, mulberry32(7))).toEqual(autoPlace(12, 2, mulberry32(7))))
})
describe('sanitizeNickname', () => {
  it('去首尾空白', () => expect(sanitizeNickname('  海鸥 ', 'x')).toBe('海鸥'))
  it('去控制字符', () => expect(sanitizeNickname('海\u0000鸥\n', 'x')).toBe('海鸥'))
  it('超过 12 个字符回退', () => expect(sanitizeNickname('一二三四五六七八九十一二三', '玩家 1')).toBe('玩家 1'))
  it('12 个字符按码点计（emoji 算 1 个）', () => expect(sanitizeNickname('🐟'.repeat(12), 'x')).toBe('🐟'.repeat(12)))
  it('空串与非字符串回退', () => { expect(sanitizeNickname('   ', '玩家 2')).toBe('玩家 2'); expect(sanitizeNickname(42, '玩家 2')).toBe('玩家 2') })
})
```

`mulberry32` 是测试内的 6 行确定性随机函数（写在 `test/helpers.ts`，供后续任务复用）。

- [ ] **Step 2: 运行确认失败**

- [ ] **Step 3: 实现**

`autoPlace`：最多 200 次随机尝试——每次从全部合法机头里洗牌后贪心挑选不重叠的位置，凑满 `planeCount` 即返回。全部失败时走**保底**：机头取 `(1 + 3i, 1 + 3j)` 的整齐网格，按行优先取前 `planeCount` 个（Task 1 已证明容量足够）。`sanitizeNickname`：删除 `\p{Cc}`，trim，按 `[...str].length` 判断 1–12。

- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit** — `feat(shared): autoPlace with guaranteed fallback, nickname sanitizing`

---

### Task 3: 协议 v2

**Files:**
- Modify: `packages/shared/src/types.ts`, `packages/shared/src/protocol.ts`, `packages/shared/test/protocol.test.ts`, `packages/shared/test/types.test.ts`

**Interfaces:**
- Consumes: `RuleSet`, `Capacity`, `PresetId`, `validateRuleSet`, `isCapacity`
- Produces（替换 P0 的对应定义；未列出的 P0 类型保持不变）：

```ts
export type Mode = 'duel' | 'melee'
export type TablePhase = 'waiting' | 'inGame'
export type GamePhase = 'placing' | 'playing' | 'paused' | 'finished'
export type GameOverReason = 'head' | 'allPlanes' | 'forfeit' | 'lastStanding'

export type SeatView = { seat: number; playerId: string; nickname: string; ready: boolean; connected: boolean }
export type RankEntry = { playerId: string; rank: number; eliminatedRound: number | null; hits: number }
export type GameResult = { ranking: RankEntry[]; reason: GameOverReason }
export type TableView = {
  roomCode: string; kind: 'friend' | 'match'; capacity: Capacity; rules: RuleSet
  hostId: string | null; phase: TablePhase; seats: (SeatView | null)[]; lastResult: GameResult | null
}
export type TargetShot = { targetId: string; row: number; col: number; result: ShotResult; planeId: string }
export type IncomingShot = { by: string; row: number; col: number; result: ShotResult; planeId: string }
export type OtherPlayerView = { playerId: string; connected: boolean; alive: boolean; planesDestroyed: number; submitted: boolean }
export type GameView = {
  mode: Mode; phase: GamePhase; deadlineAt: number | null
  turn: string | null          // duel：当前开炮者；melee：null
  round: number | null         // melee：当前轮次（从 1 起）；duel：null
  you: { planes: Cell[]; planesDestroyed: number; alive: boolean; shots: TargetShot[]; incoming: IncomingShot[] }
  others: OtherPlayerView[]
}

export type ClientMessage =
  | { type: 'auth'; playerId: string; token?: string; nickname?: string }
  | { type: 'setNickname'; nickname: string }
  | { type: 'createRoom'; capacity: Capacity; rules: RuleSet }
  | { type: 'joinRoom'; roomCode: string }
  | { type: 'updateRules'; rules: RuleSet }
  | { type: 'setReady'; ready: boolean }
  | { type: 'queueJoin'; capacity: Capacity; preset: PresetId }
  | { type: 'queueLeave' }
  | { type: 'placePlane'; planes: Cell[] }
  | { type: 'fire'; row: number; col: number }
  | { type: 'useItem'; itemId: ItemId }
  | { type: 'leaveRoom' }

export type ServerMessage =
  | { type: 'ready'; playerId: string; token: string; nickname: string }
  | { type: 'tableState'; table: TableView }
  | { type: 'queueStatus'; capacity: Capacity; preset: PresetId; waiting: number }
  | { type: 'queueTimeout' }
  | { type: 'phaseChanged'; phase: GamePhase; deadlineAt: number | null; turn?: string; round?: number }
  | { type: 'planeAccepted'; planes: Cell[] }
  | { type: 'shotResult'; by: string; row: number; col: number; result: ShotResult; planeId: string; nextTurn: string }  // duel
  | { type: 'submitted'; playerId: string; round: number }                                                               // melee，无坐标
  | { type: 'roundResult'; round: number; shots: TargetShot[]; incoming: IncomingShot[]; destroyed: { playerId: string; planesDestroyed: number }[]; eliminated: string[] }  // melee，按人私有
  | { type: 'planeDestroyed'; ownerId: string; planeId: string }                                                          // duel
  | { type: 'presence'; playerId: string; connected: boolean }
  | { type: 'gameOver'; result: GameResult }
  | { type: 'roomClosed' }
  | { type: 'state'; table: TableView; game: GameView | null }
  | { type: 'error'; code: ErrorCode; message: string }
```

删除：`rematchRequest`、`rematchRespond`、`roomJoined`、`matchFound`、`rematchOffered`、`opponentLeft`、`opponentBack`、`RoomSnapshot`（分别由 `setReady`、`tableState`、`presence`、`state` 取代）。`ErrorCode` 新增 `'NOT_HOST' | 'ROOM_IN_GAME' | 'BAD_RULES' | 'NOT_IN_QUEUE'`。

- [ ] **Step 1: 更新测试**

在 `protocol.test.ts` 删除 rematch 相关用例，新增：

```ts
it('createRoom 需要合法 capacity 与 rules', () => {
  expect(parse({ type: 'createRoom', capacity: 3, rules: PRESETS.advanced })).toMatchObject({ ok: true })
  expect(bad({ type: 'createRoom', capacity: 5, rules: PRESETS.standard })).toBe('BAD_SHAPE')
  expect(bad({ type: 'createRoom', capacity: 2, rules: { ...PRESETS.standard, planeCount: 9 } })).toBe('BAD_SHAPE')
})
it('queueJoin 需要合法 capacity 与 preset', () => {
  expect(parse({ type: 'queueJoin', capacity: 4, preset: 'expert' })).toMatchObject({ ok: true })
  expect(bad({ type: 'queueJoin', capacity: 4, preset: 'godmode' })).toBe('BAD_SHAPE')
})
it('auth 的 nickname 可选、为字符串', () => {
  expect(parse({ type: 'auth', playerId: 'p', nickname: '海鸥' })).toMatchObject({ ok: true })
  expect(bad({ type: 'auth', playerId: 'p', nickname: 3 })).toBe('BAD_SHAPE')
})
it('setReady / updateRules / setNickname', () => {
  expect(parse({ type: 'setReady', ready: true })).toMatchObject({ ok: true })
  expect(bad({ type: 'setReady', ready: 'yes' })).toBe('BAD_SHAPE')
  expect(parse({ type: 'updateRules', rules: PRESETS.beginner })).toMatchObject({ ok: true })
  expect(parse({ type: 'setNickname', nickname: '狐狸' })).toMatchObject({ ok: true })
})
it('rematchRequest 已移除', () => expect(bad({ type: 'rematchRequest' })).toBe('UNKNOWN_TYPE'))
```

`types.test.ts`：把 `gameOver` 原因的断言改成 `['head','allPlanes','forfeit','lastStanding']`。

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 改 `types.ts` 与 `protocol.ts`**（parser 中的 rules 校验直接调用 `validateRuleSet`；昵称长度在 parser 层只校验类型，清洗交给服务端）
- [ ] **Step 4: 运行 shared 全量测试确认通过**。

**过渡期约定（Task 3 → Task 12）**：协议已换成 v2，而 `hub.ts`、`room.ts` 及其测试要到 Task 6 / Task 12 才迁移。在此期间：
- 服务端 `tsc --noEmit` 允许报错，Task 12 结束时必须清零；
- 服务端各任务只跑**本任务的测试文件 + 已迁移的测试**（`engine-*`、`table*`、`duel-*`、`melee-*`、`matchmaking`），命令写为 `pnpm -C apps/server exec vitest run <文件名前缀>`；`hub-*`、`auth`、`full-game` 在 Task 12 / 13 恢复为全绿；
- 客户端 `vue-tsc` 允许报错，Task 17 结束时必须清零；客户端单测（只测纯函数）应始终可运行。
- [ ] **Step 5: Commit** — `feat(shared): protocol v2 for tables, melee and rankings`

---

### Task 4: Engine 接口与共用摆放阶段

**Files:**
- Create: `apps/server/src/engine.ts`, `apps/server/test/engine-placing.test.ts`

**Interfaces:**
- Consumes: `RuleSet`, `placeSeconds`, `autoPlace`, `checkPlacement`, `GameView`, `GameResult`, `ClientMessage`
- Produces:
```ts
export type Outbound = { to: string; msg: ServerMessage }
export const DISCONNECT_GRACE_MS = 30_000
export type EngineOptions = { rules: RuleSet; playerIds: string[]; now: number; rng?: () => number }
export interface Engine {
  readonly mode: Mode
  readonly phase: GamePhase
  readonly result: GameResult | null            // phase === 'finished' 时非空
  handle(playerId: string, msg: ClientMessage, now: number): Outbound[]  // 只处理 placePlane / fire / leaveRoom
  tick(now: number): Outbound[]
  setConnected(playerId: string, connected: boolean, now: number): Outbound[]
  view(playerId: string): GameView
}
export function createEngine(opts: EngineOptions): Engine     // 2 人 → DuelEngine，3–4 人 → MeleeEngine

/** 两种引擎共用的摆放阶段：同时摆放、可重摆、到时自动摆放 */
export class PlacingPhase {
  constructor(rules: RuleSet, playerIds: string[], now: number, rng: () => number)
  readonly deadlineAt: number
  place(playerId: string, heads: Cell[]): Outbound[]    // 合法 → planeAccepted 给本人；非法 → INVALID_PLACEMENT
  autoPlaceMissing(): Outbound[]                        // 给未摆放者 autoPlace，各发 planeAccepted
  get allPlaced(): boolean
  planesOf(playerId: string): Cell[] | null
  extend(ms: number): void                              // duel 暂停顺延用
}
```

`createEngine` 在本任务内先只实现 `PlacingPhase`，工厂的两个分支在 Task 6 / Task 7 接上（本任务里工厂对 2 人和 3–4 人都抛出 `not implemented`，并由测试断言这一点）。

- [ ] **Step 1: 写失败的测试**

```ts
const rules = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false } as const
it('deadline = now + placeSeconds', () => expect(new PlacingPhase(rules, ['a','b','c'], 1000, () => 0).deadlineAt).toBe(1000 + 60_000))
it('合法摆放只回给本人', () => {
  const p = new PlacingPhase(rules, ['a','b','c'], 0, () => 0)
  expect(p.place('a', [{row:2,col:2},{row:6,col:6}])).toEqual([{ to:'a', msg:{ type:'planeAccepted', planes:[{row:2,col:2},{row:6,col:6}] } }])
})
it('飞机数不对 / 重叠 → INVALID_PLACEMENT', () => {
  const p = new PlacingPhase(rules, ['a','b'], 0, () => 0)
  expect(p.place('a', [{row:2,col:2}])[0]!.msg).toMatchObject({ type:'error', code:'INVALID_PLACEMENT' })
  expect(p.place('a', [{row:2,col:2},{row:2,col:3}])[0]!.msg).toMatchObject({ code:'INVALID_PLACEMENT' })
})
it('autoPlaceMissing 只补未摆放者，且结果合法', () => {
  const p = new PlacingPhase(rules, ['a','b','c'], 0, mulberry32(1))
  p.place('a', [{row:2,col:2},{row:6,col:6}])
  const out = p.autoPlaceMissing()
  expect(out.map(o => o.to).sort()).toEqual(['b','c'])
  expect(p.allPlaced).toBe(true)
  for (const id of ['b','c']) expect(checkPlacement(p.planesOf(id)!, 12, 2)).toEqual({ ok: true })
})
it('自动摆放的结果只发给其本人', () => {
  const p = new PlacingPhase(rules, ['a','b','c'], 0, mulberry32(2))
  const out = p.autoPlaceMissing()
  expect(out).toHaveLength(3)
  for (const o of out) expect((o.msg as any).planes).toEqual(p.planesOf(o.to))
  expect(new Set(out.map(o => o.to)).size).toBe(3)
})
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(server): engine interface and shared placing phase`

---

### Task 5: Table（桌子）

**Files:**
- Create: `apps/server/src/table.ts`, `apps/server/test/table.test.ts`

**Interfaces:**
- Consumes: `Engine`、`createEngine`（通过构造参数注入，测试用假引擎）、`TableView`、`sanitizeNickname`
- Produces:
```ts
export const WAITING_SEAT_GRACE_MS = 60_000
export type TableOptions = {
  roomCode: string; kind: 'friend' | 'match'; capacity: Capacity; rules: RuleSet; now: number
  engineFactory?: (o: EngineOptions) => Engine     // 默认 createEngine
}
export class Table {
  readonly roomCode: string; readonly kind: 'friend' | 'match'; readonly capacity: Capacity
  get rules(): RuleSet
  get phase(): TablePhase
  get isClosed(): boolean
  get members(): string[]                          // 在座的 playerId
  get engine(): Engine | null
  join(playerId: string, nickname: string, now: number): Outbound[]       // 失败返回给本人的 error
  leave(playerId: string, now: number): Outbound[]
  setReady(playerId: string, ready: boolean, now: number): Outbound[]
  updateRules(playerId: string, rules: RuleSet, now: number): Outbound[]
  setNickname(playerId: string, nickname: string): Outbound[]
  handleGame(playerId: string, msg: ClientMessage, now: number): Outbound[]  // 转发给引擎；无引擎 → WRONG_PHASE
  tick(now: number): Outbound[]
  setConnected(playerId: string, connected: boolean, now: number): Outbound[]
  view(): TableView
  stateFor(playerId: string): Outbound                                   // { type:'state', table, game }
}
```

**行为（全部来自 spec §19.4）：**
- 每次座位/准备/规则/房主变化都向全体在座者广播 `tableState`。
- `friend`：首个 `join` 者为房主；人满且全员 `ready` → 新建引擎，`phase = 'inGame'`，并清空所有人的 ready。
- `match`：人满即开局（首局不需准备）；之后同 friend 的准备规则。
- 引擎 `phase` 变为 `finished` 时（在 `handleGame`/`tick`/`setConnected` 之后检查）：记录 `lastResult`，`phase = 'waiting'`，丢弃引擎，广播 `tableState`。
- `leave`：等候中 → 释放座位；`match` 类型且已经打过至少一局 → 关桌并向其余人发 `roomClosed`；对局中 → 先转给引擎（引擎负责判负/出局）、座位在本局结束时释放。房主离开 → 房主转给最小座位号。无人在座 → `isClosed = true`。
- `updateRules`：非房主 → `NOT_HOST`；`match` → `NOT_HOST`；对局中 → `ROOM_IN_GAME`；否则更新并清空所有 ready。
- `join`：对局中 → `ROOM_IN_GAME`；满 → `ROOM_FULL`；已在座 → 只回 `stateFor`。
- 等候中掉线：座位保留 `WAITING_SEAT_GRACE_MS`，超时由 `tick` 释放（效果同 `leave`）。

- [ ] **Step 1: 写失败的测试**（用 `FakeEngine`：`phase` 可由测试设置，`handle` 记录调用）

```ts
it('好友房：人满且全员准备才开局，开局后清空准备', ...)        // join a,b,c,d → 只有 3 人 ready 时 engine 为 null；第 4 人 ready → engine 非空、所有 seat.ready=false
it('匹配房：人满自动开局', ...)
it('房主改规则清空所有人准备并广播', ...)
it('非房主改规则 → NOT_HOST；匹配房改规则 → NOT_HOST', ...)
it('Review Focus #3：最后一人准备即同步开局，之后改规则 → ROOM_IN_GAME，引擎用的是开局时的规则', ...)
  // factory 捕获 EngineOptions.rules，断言等于准备时的规则
it('对局中加入 → ROOM_IN_GAME；满员加入 → ROOM_FULL', ...)
it('引擎结束 → 回到 waiting、记录 lastResult、丢弃引擎', ...)
it('房主在等候室离开 → 房主转给最小座位号', ...)
it('匹配房打完一局后有人离开 → 其余人收到 roomClosed，isClosed', ...)
it('好友房打完一局后有人离开 → 只释放座位，不关桌', ...)
it('等候室掉线 60 秒后让出座位；59 秒内回来保留', ...)
it('所有人离开 → isClosed', ...)
it('对局中 leave 转发给引擎，座位到本局结束才释放', ...)
```

每条测试写全断言（例如第一条：`expect(t.engine).toBeNull()` → 第四人 ready 后 `expect(t.engine).not.toBeNull()`、`expect(t.view().seats.every(s => s && !s.ready)).toBe(true)`、`expect(t.phase).toBe('inGame')`）。

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(server): table with seats, ready, host and rematch lifecycle`

---

### Task 6: DuelEngine（从 Room 抽出）

**Files:**
- Create: `apps/server/src/duel-engine.ts`
- Rename & adapt tests: `room-placement/fire/timer/disconnect/lifecycle.test.ts` → `duel-*.test.ts`
- Delete: `apps/server/src/room.ts`, `apps/server/test/room-rematch.test.ts`（再来一局职责移到 Table，Task 5 已覆盖）
- Modify: `apps/server/src/engine.ts`（工厂接上 2 人分支）

**Interfaces:**
- Consumes: `Engine`、`PlacingPhase`、`DISCONNECT_GRACE_MS`
- Produces: `class DuelEngine implements Engine`（`mode = 'duel'`）

**迁移规则：**
- P0 的 `Room` 中关于摆放、开炮、计时、暂停/重连、判负的逻辑全部保留；摆放改用 `PlacingPhase`；回合时长取 `rules.turnSeconds * 1000`；摆放时长取 `placeSeconds(rules)`。
- 删除：rematch、`close`、`roomCode`（属于 Table）。`leaveRoom` → 判负（`gameOver.result.reason = 'forfeit'`），不再发 `roomClosed`（由 Table 决定）。
- `opponentLeft/opponentBack` → `presence`；暂停仍通过 `phaseChanged paused` 告知。
- `gameOver` 改为 `{ result: { ranking, reason } }`：胜者 `rank 1`、负者 `rank 2`；`eliminatedRound: null`；`hits` = 该玩家累计命中机身 + 机头的格数。
- 快照改为 `view(playerId): GameView`：`turn` 有值、`round = null`、`you.shots` 的 `targetId` 为对手、`others` 长度 1。

- [ ] **Step 1: 改测试**——`room-lifecycle.test.ts` 中 I6 的三条：引擎只负责 `gameOver { reason: 'forfeit' }`，删除对 `roomClosed` 与 `isClosed` 的断言（这部分已由 Task 5 的 Table 测试覆盖）；"结束后离开"那条整条删除（引擎在 finished 后不再处理 leave）。其余：把旧测试里的 `new Room({...})` 换成 `new DuelEngine({ rules, playerIds: ['a','b'], now, rng })`，`rules` 取 `{ boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }`，使 P0 的所有时间常量保持不变；把 `opponentLeft` 断言换成 `presence`、`snapshotFor` 换成 `view`、`gameOver.winnerId` 换成 `result.ranking[0].playerId`。新增：

```ts
it('回合时长取自 rules（15 秒）', ...)            // turnSeconds:15 → 15000 时代打
it('多架飞机：击落一架不结束，全部击落才结束且 reason=allPlanes', ...)
it('gameOver.ranking：胜者 rank 1，负者 rank 2，hits 为累计命中格数', ...)
```

- [ ] **Step 2: 运行确认失败**（`DuelEngine` 不存在）
- [ ] **Step 3: 实现**，并删除 `room.ts`
- [ ] **Step 4: 运行 `duel-*` 与 `table` 测试全部通过**
- [ ] **Step 5: Commit** — `refactor(server): extract DuelEngine from Room behind Engine interface`

---

### Task 7: MeleeEngine —— 回合与私有结算

**Files:**
- Create: `apps/server/src/melee-engine.ts`, `apps/server/test/melee-round.test.ts`
- Modify: `apps/server/src/engine.ts`（工厂接上 3–4 人分支）

**Interfaces:**
- Produces: `class MeleeEngine implements Engine`（`mode = 'melee'`）

**本任务范围**：摆放 → `playing`；`fire` = 提交本轮并锁定；同一轮重复提交 → `NOT_YOUR_TURN`（含义"本轮你已开过炮"，沿用已有错误码）；已打过的格子 → `REPEAT_SHOT`；越界 → `OUT_OF_RANGE`；全员（在线存活者）已提交或到时 → 结算。出局/排名/超时/掉线在 Task 8–9。

**结算算法（一轮）：**
```
对每个本轮已提交的射手 s、每个本轮开始时存活的对手 t（t ≠ s）：
  r = resolveShot(t 的飞机, s 的坐标)
  记入 s.shots（targetId = t）与 t.incoming（by = s）
  r 为 head → t.destroyed.add(planeId)；s.hits += 1；r 为 body → s.hits += 1
然后向每个玩家 p 发一条私有的 roundResult：
  shots = p 本轮的 TargetShot[]；incoming = 本轮打在 p 身上的 IncomingShot[]
  destroyed = 本轮有变化的所有玩家的 planesDestroyed 数（公开信息）
  eliminated = []（Task 8 填充）
再广播 phaseChanged { phase:'playing', deadlineAt: now + turnSeconds*1000, round: round+1 }
```

- [ ] **Step 1: 写失败的测试**

```ts
// 3 人：a(2,2) b(6,6) c(2,7)；10×10、1 架、20 秒
it('提交只广播 submitted，不含坐标', ...)          // out 里 submitted 发给 a,b,c，且 JSON 不含提交的 row/col
it('全员提交后立即结算，不等到时', ...)
it('一炮落在每个存活对手棋盘上', ...)             // a 打 (6,6)：对 b 是 head，对 c 是 miss；a 的 roundResult.shots 有两条
it('roundResult 按人私有：b 只看到打在自己身上的 incoming', ...)
it('Review Focus #1：发给 a 的所有消息里都没有 b 打 c 的坐标', ...)
  // 连打 5 轮，收集所有 to==='a' 的消息 JSON，断言不包含 b→c 每一炮的 `"row":R,"col":C` 组合（b、c 的坐标特意选成 a 未打过的格子）
it('同一轮重复提交 → NOT_YOUR_TURN，第一次的坐标不变', ...)
it('打过的格子 → REPEAT_SHOT', ...)
it('到时结算：只结算已提交者，未提交者本轮无炮', ...)
it('view：others 含 submitted 标记与 planesDestroyed，不含任何坐标', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(server): melee engine simultaneous rounds with private results`

---

### Task 8: MeleeEngine —— 出局与排名

**Files:**
- Modify: `apps/server/src/melee-engine.ts`
- Create: `apps/server/test/melee-ranking.test.ts`

**Interfaces:**
- Produces（内部纯函数，导出以便单测）:
```ts
export function rankPlayers(players: { playerId: string; eliminatedRound: number | null; hits: number }[]): RankEntry[]
```
排序：`eliminatedRound` 为 null（存活）最前，其余按轮次降序；同轮按 `hits` 降序；`hits` 也相同 → 同名次（名次跳号：1,1,3）。

- [ ] **Step 1: 写失败的测试**

```ts
describe('rankPlayers', () => {
  it('存活者第 1，越晚出局越靠前', () => expect(rankPlayers([
    { playerId:'a', eliminatedRound:2, hits:3 }, { playerId:'b', eliminatedRound:null, hits:1 }, { playerId:'c', eliminatedRound:5, hits:0 },
  ]).map(r => [r.playerId, r.rank])).toEqual([['b',1],['c',2],['a',3]]))
  it('同轮出局按命中数', ...)            // 同轮 hits 4 vs 2 → 名次 2、3
  it('同轮同命中 → 并列，名次跳号', ...)   // → [1,2,2,4]
  it('Review Focus #2：最后两人同轮出局，命中数高者第 1', ...)
  it('Review Focus #2：最后两人同轮出局且命中相同 → 并列第 1，ranking 里至少一个 rank 1', ...)
})
describe('出局流程', () => {
  it('飞机全灭者在本轮结算后出局，roundResult.eliminated 列出', ...)
  it('出局者之后不再是任何人的目标（下一轮对其的 roundResult.shots 不含其 targetId）', ...)
  it('出局者的提交被拒（WRONG_PHASE）', ...)
  it('仅剩 1 人 → gameOver，reason=lastStanding', ...)
  it('同轮全部出局 → gameOver，reason=lastStanding，按命中数决出第 1', ...)
  it('多架飞机：击落一架不出局', ...)
})
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(server): melee elimination and ranking with tie-breaks`

---

### Task 9: MeleeEngine —— 超时、挂机、掉线、离开

**Files:**
- Modify: `apps/server/src/melee-engine.ts`
- Create: `apps/server/test/melee-presence.test.ts`

**规则（spec §19.6）：** 在线未提交 → 本轮无炮、`idleStreak++`；提交 → `idleStreak = 0`；`idleStreak` 达 3 → 本轮结算时出局。掉线 → 广播 `presence`，**不暂停**，掉线期间不累计 `idleStreak`；掉线满 `DISCONNECT_GRACE_MS` → 出局（在下一次 `tick` 结算时）。摆放阶段掉线不暂停，到时 `autoPlaceMissing`。`leaveRoom` → 当场出局（记为当前轮次出局），若因此只剩 1 人 → `gameOver`。

- [ ] **Step 1: 写失败的测试**

```ts
it('超时未提交：本轮无炮，不代打', ...)
it('连续 3 轮在线未提交 → 出局；中间提交一次则重新计数', ...)
it('掉线不暂停：其他人照常进行，phase 仍为 playing', ...)
it('掉线期间不计挂机：掉线 25 秒（跨 2 轮）后回来，idle 计数为 0', ...)
it('掉线满 30 秒 → 出局', ...)
it('Review Focus #5：提交后立刻掉线，本轮那一炮仍然结算', ...)
it('本轮所有在线存活者都已提交、掉线者未提交 → 立即结算，不等掉线者', ...)
it('摆放阶段掉线不暂停，到时自动摆放', ...)
it('leaveRoom → 当场出局；只剩 1 人 → gameOver', ...)
it('重连收到 state（view），其中 round 与 deadlineAt 为当前值', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(server): melee timeouts, idle elimination, non-pausing disconnects`

---

### Task 10: Table + 真实引擎的集成

**Files:**
- Create: `apps/server/test/table-integration.test.ts`

**Interfaces:**
- Consumes: `Table`（默认 `createEngine`）、`DuelEngine`、`MeleeEngine`

本任务不新增产品代码，只验证 Table 与两种真实引擎之间的接缝；发现的缺陷在本任务内修复。

- [ ] **Step 1: 写测试**

```ts
it('好友房 2 人：打完一局 → waiting、lastResult 有值 → 双方准备 → 第二局用当前规则', ...)
it('好友房 4 人混战：打完回等候室；房主改为 12×12/2 架 → 全员准备 → 新局 view.you.planes 需 2 架', ...)
it('Review Focus #3：准备与改规则竞态（真实引擎）', ...)
it('混战中有人 leaveRoom：对局继续；本局结束后其座位被释放', ...)
it('2 人对局中 leaveRoom：对手胜（forfeit），回到 waiting', ...)
```

- [ ] **Step 2: 运行；失败则按 systematic-debugging 修复产品代码**
- [ ] **Step 3: 运行已迁移的服务端测试全部通过**：`pnpm -C apps/server exec vitest run engine table duel melee`（`hub-*` 由 Task 12 恢复）
- [ ] **Step 4: Commit** — `test(server): table integration with duel and melee engines`

---

### Task 11: 多队列匹配

**Files:**
- Modify: `apps/server/src/matchmaking.ts`, `apps/server/test/matchmaking.test.ts`

**Interfaces:**
- Produces:
```ts
export type QueueKey = { capacity: Capacity; preset: PresetId }
export type MatchGroup = { key: QueueKey; playerIds: string[] }
export class Matchmaking {
  constructor(opts: { enqueueWaitMs?: number })
  join(playerId: string, key: QueueKey, now: number): { out: Outbound[]; group: MatchGroup | null }
  leave(playerId: string, now: number): Outbound[]
  tick(now: number): Outbound[]
  queueOf(playerId: string): QueueKey | null
  size(key: QueueKey): number
}
```
房间号生成移出 Matchmaking（由 Hub 统一生成，消除 P0 Minor M3 的来源）。

- [ ] **Step 1: 写失败的测试**

```ts
it('不同 (人数, 档位) 的队列互不干扰', ...)
it('4 人队列凑满 4 人才成组，按入队顺序', ...)
it('入队/离队时向该队列全体推送 queueStatus { waiting }', ...)
it('加入另一个队列会自动离开原队列', ...)
it('成组后这些人从队列移除，其余人收到新的 queueStatus', ...)
it('60 秒提示一次 queueTimeout，不出队', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(server): matchmaking queues keyed by capacity and preset`

---

### Task 12: Hub v2

**Files:**
- Modify: `apps/server/src/hub.ts`
- Rewrite: `apps/server/test/hub-e2e.test.ts`, `apps/server/test/hub-lifecycle.test.ts`

**Interfaces:**
- Consumes: `Table`、`Matchmaking`、`sanitizeNickname`、`PRESETS`
- Produces（对外不变）：`Hub.connect / disconnect / receive / tick`；`getRoom` 改名 `getTable(roomCode): Table | undefined`

**保留 P0 的全部安全修复**：token 绑定、顶号关闭旧 socket、同 socket 不可换身份、重认证必补快照、出站按桌过滤、关桌清理。删除 `pendingRooms`（由 Table 的 waiting 取代）。

**路由：**
- `auth`：昵称 = `sanitizeNickname(msg.nickname, '玩家')`，存于 Hub；`ready` 回带昵称。
- `setNickname`：更新 Hub 中的昵称；若在桌上 → `table.setNickname`。
- `createRoom {capacity, rules}`：先离开当前等候桌/队列（对局中 → `ALREADY_IN_ROOM`），建 `friend` 桌并 `join`。
- `joinRoom`：同上先离开，再 `table.join`。
- `queueJoin {capacity, preset}`：先离开当前等候桌（对局中 → `ALREADY_IN_ROOM`）；成组 → 建 `match` 桌（`rules = PRESETS[preset]`），按组顺序 `join`。
- `updateRules / setReady / leaveRoom`：转给所在 Table；不在桌 → `NOT_IN_ROOM`（`leaveRoom` 在队列中时 = `queueLeave`）。
- `placePlane / fire`：`table.handleGame`。
- 断线/重连：`table.setConnected`；重连后补 `table.stateFor`。
- `tick`：各桌 `tick` + 匹配 `tick`；`isClosed` 的桌删除。

- [ ] **Step 1: 重写测试**——保留 P0 hub 测试的所有场景，改用 v2 消息；新增：

```ts
it('建 3 人好友房 → 另两人用房间号加入 → 全员准备 → 进入 placing，engine 为 melee', ...)
it('Review Focus #4：在 A 桌等候时加入 B 桌 → 自动离开 A，A 桌其余人收到 tableState（座位空出）', ...)
it('Review Focus #4：排队时加入好友房 → 自动出队', ...)
it('对局中加入别的房间 → ALREADY_IN_ROOM', ...)
it('4 人快速匹配：4 个会话 queueJoin {4, standard} → 同一张 match 桌、规则为 PRESETS.standard、自动开局', ...)
it('昵称清洗：auth 带 13 字昵称 → ready.nickname 为回退值', ...)
it('冒充（无 token / 错 token）仍被拒（P0 C2 回归）', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**；`pnpm -C apps/server exec tsc --noEmit` 必须通过（Task 3 遗留的类型错误到此全部消除）
- [ ] **Step 5: Commit** — `feat(server): hub v2 routing tables, zones and multi-queue matchmaking`

---

### Task 13: 端到端：混战与自定义对决

**Files:**
- Create: `apps/server/test/melee.e2e.test.ts`
- Modify: `apps/server/test/full-game.e2e.test.ts`（改用 v2 协议，规则改为 12×12、2 架）

- [ ] **Step 1: 写测试**——真实 WebSocket，4 个机器人客户端：好友房建房 → 加入 → 准备 → 各自 `autoPlace` → 每轮按"有命中则打 `candidateHeads` 交集，否则 3 格步长扫描"选一个**对所有对手都没打过**的格子 → 直到 `gameOver`。断言：
  - `gameOver.result.ranking` 长度 4，至少一个 `rank === 1`，`reason === 'lastStanding'`；
  - 每个机器人收到的所有消息里，不存在另外两人之间的射击坐标（Review Focus #1 的端到端版）；
  - 结束后 `tableState.table.phase === 'waiting'` 且 `lastResult` 非空；
  - 总轮数 < 60。
- [ ] **Step 2: 运行通过**；用变异验证（临时把私有 `roundResult` 改为广播给所有人，测试必须变红；恢复后 `git diff` 为空）
- [ ] **Step 3: Commit** — `test(server): end-to-end 4-player melee and custom-rule duel`

---

### Task 14: 客户端状态仓库 v2 与昵称生成

**Files:**
- Modify: `apps/client/src/net/store.ts`, `apps/client/test/store.test.ts`, `apps/client/src/net/socket.ts`
- Create: `apps/client/src/nickname-gen.ts`, `apps/client/test/nickname-gen.test.ts`

**Interfaces:**
- Produces:
```ts
export type GameState = {
  playerId: string | null; nickname: string
  table: TableView | null
  game: GameView | null                 // 由 phaseChanged/shotResult/roundResult/submitted/presence 增量维护，由 state 整体替换
  queue: { capacity: Capacity; preset: PresetId; waiting: number } | null
  queueTimedOut: boolean
  resultDismissed: boolean              // 结算页是否已关闭（table.lastResult 变化时重置为 false）
  roomClosed: boolean
  error: string | null
}
export function createGameStore(): { state: GameState; apply(m: ServerMessage): void; resetToLobby(): void }
export function generateNickname(rng?: () => number): string    // "形容词的名词"，长度 ≤ 12
```
`socket.ts`：`connectSocket` 新增 `nickname` 参数随 `auth` 发送；昵称存 `localStorage['plane-duel:nickname']`。

- [ ] **Step 1: 写失败的测试**

```ts
it('tableState 替换 table；lastResult 变化时 resultDismissed 重置', ...)
it('duel：shotResult 写入 game.you.shots（targetId=对手）或 game.you.incoming，并更新 turn', ...)
it('melee：roundResult 追加本人的 shots/incoming，更新 others 的 planesDestroyed 与 alive，清空所有 submitted', ...)
it('melee：submitted 只把对应玩家标记为已开炮', ...)
it('presence 更新 others[i].connected', ...)
it('phaseChanged 更新 game.phase/deadlineAt/turn/round；paused 不清 game', ...)
it('state 整体替换 table 与 game', ...)
it('gameOver 后 game.phase = finished', ...)
it('queueStatus 写入 queue；tableState 到来时清空 queue', ...)
it('generateNickname 长度 1–12 且通过 sanitizeNickname', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(client): store v2 for tables, duel and melee`

---

### Task 15: 混战合并棋盘模型与组件

**Files:**
- Modify: `apps/client/src/board-model.ts`, `apps/client/test/board-model.test.ts`, `apps/client/src/components/BoardGrid.vue`

**Interfaces:**
- Produces:
```ts
export type SeatColor = string
export type TargetMark = { playerId: string; color: SeatColor; result: ShotResult; dim: boolean }
export type TargetCell = { row: number; col: number; fired: boolean; marks: TargetMark[]; hint: boolean }
export function buildTargetCells(opts: {
  boardSize: number
  shots: readonly TargetShot[]
  opponents: readonly { playerId: string; color: SeatColor; alive: boolean }[]
  focus: string | null                 // null = 合并视图；否则只显示该对手
  hintFor: string | null               // 叠加该对手的 candidateHeads（仅 focus 模式且 hintAllowed）
}): TargetCell[]
export const SEAT_COLORS: readonly SeatColor[]   // 4 色，与座位号对应
```
`BoardGrid.vue` 新增：`selectedKey` prop（两步开炮的选中高亮）、`marks` 渲染（合并视图 2×2 小槽；focus 视图单个大标记）。

- [ ] **Step 1: 写失败的测试**

```ts
it('合并视图：一格可有多个对手的标记，按对手顺序', ...)
it('focus 视图：只含该对手的标记', ...)
it('已出局对手的标记 dim=true', ...)
it('fired：我打过的格子（对任一对手）为 true', ...)
it('hint：只在 focus 且 hintFor 等于 focus 时标出 candidateHeads', ...)
it('16×16 生成 256 格', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**
- [ ] **Step 5: Commit** — `feat(client): merged target board model and multi-mark grid`

---

### Task 16: 大厅专区、规则编辑器、等候室

**Files:**
- Modify: `apps/client/src/views/Lobby.vue`, `apps/client/src/App.vue`
- Create: `apps/client/src/views/Zone.vue`, `apps/client/src/views/WaitingRoom.vue`, `apps/client/src/components/RuleEditor.vue`, `apps/client/src/components/SeatList.vue`
- Create: `apps/client/src/rule-editor-model.ts`, `apps/client/test/rule-editor-model.test.ts`

**Interfaces:**
- Produces:
```ts
// rule-editor-model.ts（编辑器的纯逻辑，可单测）
export function clampPlanes(rules: RuleSet): RuleSet          // 改边长后飞机数超上限 → 降到上限
export function ruleSummary(rules: RuleSet): string           // "10×10 · 1 架 · 20 秒 · 可用提示"
export function densityWarning(rules: RuleSet): string | null // 占比 < 5% → "棋盘很空，对局会比较长"
```

**界面（spec §19.2、§19.9）：**
- Lobby：三个专区大卡片（2 人对决 / 3 人混战 / 4 人混战）+ "输入房间号"入口 + 昵称（点击可改）。
- Zone：四档卡片（显示规则摘要、点击即排队，排队中显示"排队中 n/人数"与取消）+ "创建好友房"（展开 RuleEditor，默认值为标准档）。
- RuleEditor：边长步进器（6–16）、飞机数步进器（上限随边长变化，用 `clampPlanes`）、回合时长分段选择、推理提示开关、占比与 `densityWarning`。
- WaitingRoom：房间号（大字 + 复制）、SeatList（座位色、昵称、准备 ✓、掉线标记、房主标记、空座"等待加入"）、规则摘要（房主可点"修改规则"）、准备/取消准备、离开。
- App 路由：`table === null` → Lobby/Zone；`table.phase === 'waiting'` → `lastResult && !resultDismissed` ? ResultSheet : WaitingRoom；`inGame` → `game.phase === 'placing'` ? Place : (`mode === 'duel'` ? DuelPlay : MeleePlay)。

- [ ] **Step 1: 写 `rule-editor-model` 的失败测试**

```ts
it('边长从 14 改到 8 时，6 架降为 2 架', () => expect(clampPlanes({ boardSize: 8, planeCount: 6, turnSeconds: 20, hintAllowed: true }).planeCount).toBe(2))
it('摘要', () => expect(ruleSummary(PRESETS.advanced)).toBe('12×12 · 2 架 · 20 秒 · 无提示'))
it('16×16 1 架给出提示，10×10 1 架不提示', ...)
```

- [ ] **Step 2–4: RED → 实现模型 → GREEN**
- [ ] **Step 5: 实现四个视图/组件**；`pnpm -C apps/client exec vue-tsc --noEmit` 通过
- [ ] **Step 6: 浏览器验证**（preview）：大厅 → 3 人专区 → 创建好友房（改成 12×12、2 架）→ 等候室显示房间号与规则；另开两个脚本 WebSocket 用房间号加入 → 座位变为 3/3 → 三人准备 → 进入摆放。截图：专区页、规则编辑器、满员等候室。
- [ ] **Step 7: Commit** — `feat(client): zones lobby, rule editor and waiting room`

---

### Task 17: 多机摆放与两种对局界面

**Files:**
- Modify: `apps/client/src/views/Place.vue`
- Rename: `apps/client/src/views/Play.vue` → `DuelPlay.vue`（接 v2 store）
- Create: `apps/client/src/views/MeleePlay.vue`, `apps/client/src/components/ResultSheet.vue`
- Create: `apps/client/src/place-model.ts`, `apps/client/test/place-model.test.ts`

**Interfaces:**
- Produces:
```ts
// place-model.ts
export function togglePlane(heads: readonly Cell[], tap: Cell, rules: RuleSet):
  { heads: Cell[]; error: 'edge' | 'overlap' | 'full' | null }
  // 点已有飞机的任一格 → 移除该架；点空处 → 新增（越界 edge / 与已有重叠 overlap / 已满 full）
export function needsTwoStep(rules: RuleSet, mode: Mode): boolean   // mode==='melee' || boardSize >= 12
```

**界面：**
- Place：显示"已放 k / 飞机数"；点格子用 `togglePlane`；错误时 toast（"机头不能放在边缘一圈" / "飞机不能重叠" / "已放满，点已有飞机可移除"）；放满后"就绪"按钮发送 `placePlane`；倒计时；收到 `planeAccepted` 显示"已就绪"。
- DuelPlay：P0 Play 改接 v2；`needsTwoStep` 时点格子只选中，底部"开炮"按钮确认。
- MeleePlay：对手标签栏（全部 + 每人：昵称、座位色、剩余飞机、✓/思考中/掉线/出局）；合并目标棋盘（`buildTargetCells`）；选中 + "开炮"；本轮已提交后按钮变"已开炮，等待其他人"；我方小棋盘；轮次与倒计时；我出局后显示"你已出局，可继续观看"与"返回大厅"。
- 推理提示开关：`table.rules.hintAllowed === false` 时 DuelPlay / MeleePlay 都不显示开关，且不计算提示。
- ResultSheet：排名列表（名次、座位色、昵称、出局轮次、命中数），按钮"再来一局"（`setReady true`）/"返回大厅"（`leaveRoom`）；`roomClosed` 时隐藏"再来一局"。

- [ ] **Step 1: 写 `place-model` 的失败测试**

```ts
it('新增合法飞机', ...)
it('边缘 → edge，heads 不变', ...)
it('重叠 → overlap', ...)
it('放满后点空处 → full；点已有飞机任一机身格 → 移除该架', ...)
it('needsTwoStep：melee 恒为真；duel 边长 ≥ 12 为真', ...)
```

- [ ] **Step 2–4: RED → 实现模型 → GREEN**
- [ ] **Step 5: 实现视图**；`vue-tsc` 通过
- [ ] **Step 6: 浏览器验证**：
  - 4 人混战（本页 + 3 个脚本机器人）：摆放 2 架 → 打满一局 → 合并棋盘出现多色标记 → 切换对手标签 → 出局提示 → 结算排名 → 再来一局回到等候室；
  - 2 人 12×12 好友房：两步开炮生效；
  - 手机视口（375×812）截图：混战对局页、结算页；控制台无 warn/error。
- [ ] **Step 7: Commit** — `feat(client): multi-plane placement, duel and melee play views, result sheet`

---

### Task 18: 收尾：全量验证与 Android 包

**Files:**
- Modify: `docs/deploy/packaging.md`（如有变化）

- [ ] **Step 1: 全量测试与类型检查**

Run: `pnpm test && pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/client exec vue-tsc --noEmit`
Expected: 三包全绿、两项类型检查无输出

- [ ] **Step 2: 重新构建调试 APK**

Run: `cd apps/client && VITE_WS_URL=ws://<局域网IP>:8080 pnpm android:dev`
Expected: `app-debug.apk` 生成

- [ ] **Step 3: 若手机已连接且处于本 App 前台**，安装并截图大厅专区页；否则记录"未做真机验证"及原因（不向前台为其他应用的手机注入点击——P0 执行记录中的约定）。

- [ ] **Step 4: Commit** — `chore: P1 verification`

---

## 与 spec 的对应

| spec | 任务 |
|---|---|
| §19.2 大厅结构 | 16 |
| §19.3 RuleSet、上限、预设、两步开炮 | 1, 2, 16, 17 |
| §19.4 桌子模型 | 5, 10, 12 |
| §19.5 2 人对决 | 6 |
| §19.6 混战规则 | 7, 8, 9, 13 |
| §19.7 快速匹配 | 11, 12 |
| §19.8 昵称 | 2, 12, 14 |
| §19.9 界面 | 15, 16, 17 |
| §19.10 架构调整 | 4, 5, 6, 12 |

## 执行顺序与并行

```
1 → 2 → 3 → 4 → 5 ─┬─ 6 ─┐
                   └─ 7 → 8 → 9 ─┴─ 10 → 11 → 12 → 13
3 → 14 → 15 ─────────────────────────────────────┐
                                    12 + 15 → 16 → 17 → 18
```

- Task 6 与 Task 7–9 互不依赖（都只依赖 Task 4 的接口）。
- 客户端 Task 14–15 只依赖 Task 3 的协议类型，可与服务端 Task 4–13 并行。
- Task 16–17 需要服务端 Task 12 才能在浏览器中联调。

## 不在本计划范围（spec §19.1）

人机练习、电脑补位、公开房间列表、房主踢人（P2）；账号、段位、好友（P3）；金币、门票、道具（P4）；上架与 uni-app 迁移（P5）。
