# 飞机对决 P0 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个双人在线对战游戏：10×10 棋盘、每方 1 架 3×3 飞机、房间号与随机匹配两种开局、局后可再来一局，H5 浏览器与 Android/iOS App 真机可玩。

**Architecture:** pnpm monorepo 三包。`packages/shared` 是纯函数规则与协议类型，零依赖、零 IO，被服务端与客户端同时引用。`apps/server` 是 Node + WebSocket 权威服务端，房间状态机为纯同步类（`handle()` 收消息出消息、`tick()` 推进计时），socket 与定时器都在外层，使房间逻辑可在无网络环境下单测。`apps/client` 是 uni-app（Vue 3 + TS），棋盘用 DOM + CSS Grid。

**Tech Stack:** TypeScript 5、pnpm workspace、Vitest、Node 20+、`ws`、uni-app（Vue 3 + Vite）、CSS Grid

**Spec:** `docs/superpowers/specs/2026-11-11-plane-duel-design.md`

## Global Constraints

- 棋盘默认 10×10；`boardSize` 与 `planeCount` 从第一天起就是房间属性与函数参数，**不允许出现硬编码的 10 或 1**（spec §四、§十五）。
- 坐标一律 0-based `{ row, col }`，服务端与协议内不得出现 1-based 或字母列。
- 每方 `planes` 是数组（P0 长度恒为 1），`shotResult` 必带 `planeId`（P0 恒为 `'p0'`）（spec §十）。
- 对方飞机的机头坐标**任何时刻都不得下发到对手**（spec §八）。
- 回合 20 秒、摆放 60 秒、断线宽限 30 秒（spec §二）。
- 断线时**冻结全部计时且不代打**，重连后 deadline 顺延整个暂停时长（spec §二）。
- 摆放超时**不判负**，服务端自动落子（spec §二、§九）。
- `gameOver.reason` 只有 `head` / `allPlanes` / `forfeit` 三种（spec §九）。
- 开局判定：`useItem` 返回 `UNSUPPORTED`；P0 不支持道具（spec §十三）。
- 身份匿名：`playerId`（设备标识）与 `accountId`（积分归属，P0 为 `undefined`）是两个字段，不得合并（spec §十五）。
- 服务端内存态，不接数据库（spec §八）。
- 客户端不实现任何变现代码（spec §十五）。
- 所有用户可见文案为简体中文。

## Review Focus

以下是最可能咬到真实玩家、但没有哪个任务的测试会自然覆盖到的输入，逐条列出，并在指定任务里补上对应测试。

1. **快速连点开炮**：玩家在一炮往返网络延迟内点两次同一格或相邻格，期望只有第一炮生效，第二炮被拒且不消耗回合。→ Task 9。
2. **非本方回合开炮 / 摆放阶段开炮**：期望被拒绝并收到 `error`，房间状态与轮次完全不变。→ Task 9。
3. **重连与超时判负的竞态**：30 秒宽限到期的同一毫秒内客户端重连成功，期望只有一种结果（先到者生效），不出现"已判负却又复活"。→ Task 11。
4. **畸形协议输入**：非 JSON、未知 `type`、缺少必填字段、`row/col` 为 `-1`/`10`/`1.5`/字符串，期望连接不断开、返回 `error`、服务端不崩溃。→ Task 6。
5. **自身重叠摆放**：P1 多机时两架机头相邻导致 9 格相交；P0 虽只有 1 架，但校验函数现在就按 `planeCount` 实现，期望返回 `overlap` 而不是静默接受。→ Task 2。

---

## File Structure

```
plane-duel/
├── package.json                  workspace 根，scripts 汇总
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── .gitignore
├── packages/shared/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   ├── src/
│   │   ├── index.ts              统一导出
│   │   ├── types.ts              Cell / Plane / Room / 消息联合类型
│   │   ├── rules.ts              纯函数规则
│   │   └── protocol.ts           消息编解码与入站校验
│   └── test/
│       ├── geometry.test.ts
│       ├── resolve-shot.test.ts
│       ├── candidate-heads.test.ts
│       ├── game-over.test.ts
│       └── protocol.test.ts
├── apps/server/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   ├── src/
│   │   ├── main.ts               进程入口：ws 服务 + tick 循环
│   │   ├── hub.ts                连接管理、消息路由、gameOver 广播
│   │   ├── room.ts               房间状态机（纯同步，可单测）
│   │   ├── matchmaking.ts        随机匹配队列
│   │   └── clock.ts              可注入的时间源
│   └── test/
│       ├── room-placement.test.ts
│       ├── room-fire.test.ts
│       ├── room-timer.test.ts
│       ├── room-disconnect.test.ts
│       ├── matchmaking.test.ts
│       ├── room-rematch.test.ts
│       └── hub-e2e.test.ts
└── apps/client/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    ├── src/
    │   ├── main.ts
    │   ├── App.vue
    │   ├── pages.json
    │   ├── manifest.json
    │   ├── board-model.ts        棋盘→渲染模型的纯函数（唯一可单测的渲染逻辑）
    │   ├── net/
    │   │   ├── socket.ts         连接、重连、消息分发
    │   │   └── store.ts          响应式对局状态
    │   ├── components/
    │   │   ├── BoardGrid.vue     纯展示棋盘，接收 cells 与点击
    │   │   └── Countdown.vue
    │   └── views/
    │       ├── Lobby.vue         建房 / 加入 / 匹配
    │       ├── Place.vue         摆放
    │       └── Play.vue          对局
    └── test/
        └── board-model.test.ts   棋盘→渲染模型的纯函数
```

**分文件理由：** `rules.ts` 与 `protocol.ts` 分开，因为前者是游戏规则（永不变更语义）、后者是传输契约（P1/P2 会扩展）。`room.ts` 不含 socket、不含 `Date.now()`，所以能对"20 秒到点"这类逻辑写确定性测试。`BoardGrid.vue` 只接收数据与事件，不碰网络，三端渲染一致。

---

### Task 1: Monorepo 骨架与共享类型

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `tsconfig.base.json`, `.gitignore`
- Create: `packages/shared/package.json`, `packages/shared/tsconfig.json`, `packages/shared/vitest.config.ts`
- Create: `packages/shared/src/types.ts`, `packages/shared/src/index.ts`
- Create: `packages/shared/test/types.test.ts`

**Interfaces:**
- Produces: `Cell`、`Plane`、`ShotResult`、`ItemId`、`Phase`、`GameOverReason`，以及全部消息联合类型 `ClientMessage` / `ServerMessage`（后续任务直接 import）

- [ ] **Step 1: 初始化仓库与 workspace**

```bash
cd /Users/gqli/work/ai-math/plane-duel
git init
```

`pnpm-workspace.yaml`：
```yaml
packages:
  - 'packages/*'
  - 'apps/*'
```

根 `package.json`：
```json
{
  "name": "plane-duel",
  "private": true,
  "scripts": {
    "test": "pnpm -r test",
    "typecheck": "pnpm -r typecheck"
  },
  "devDependencies": { "typescript": "^5.6.0", "vitest": "^2.1.0" }
}
```

`.gitignore`：`node_modules/`, `dist/`, `.DS_Store`, `unpackage/`, `*.apk`, `*.ipa`

- [ ] **Step 2: 写 `packages/shared/src/types.ts`**

按 spec §十 与 §九 精确定义。关键部分：

```ts
export type Cell = { row: number; col: number }
export type Plane = { id: string; head: Cell }
export type ShotResult = 'miss' | 'body' | 'head'
export type ItemId = 'scan' | 'doubleShot' | 'radar' | 'shield' | 'relocate'
export type Phase = 'waiting' | 'placing' | 'playing' | 'finished' | 'paused'
export type GameOverReason = 'head' | 'allPlanes' | 'forfeit'

export type ClientMessage =
  | { type: 'auth'; playerId: string; token?: string }
  | { type: 'createRoom'; boardSize?: number; planeCount?: number }
  | { type: 'joinRoom'; roomCode: string }
  | { type: 'queueJoin' } | { type: 'queueLeave' }
  | { type: 'placePlane'; planes: Cell[] }
  | { type: 'fire'; row: number; col: number }
  | { type: 'useItem'; itemId: ItemId }
  | { type: 'rematchRequest' } | { type: 'rematchRespond'; accept: boolean }
  | { type: 'leaveRoom' }

export type ServerMessage =
  | { type: 'ready'; playerId: string; token: string }
  | { type: 'roomJoined'; roomCode: string; you: string; opponent: string; boardSize: number; planeCount: number }
  | { type: 'matchFound'; roomCode: string }
  | { type: 'phaseChanged'; phase: Phase; deadlineAt: number | null }
  | { type: 'planeAccepted'; planes: Cell[] }
  | { type: 'shotResult'; by: string; row: number; col: number; result: ShotResult; planeId: string; nextTurn: string }
  | { type: 'planeDestroyed'; ownerId: string; planeId: string }
  | { type: 'gameOver'; winnerId: string; reason: GameOverReason }
  | { type: 'opponentLeft' } | { type: 'opponentBack' }
  | { type: 'queueTimeout' }
  | { type: 'rematchOffered'; by: string }
  | { type: 'state'; snapshot: RoomSnapshot }
  | { type: 'error'; code: string; message: string }

export type RoomSnapshot = {
  roomCode: string; boardSize: number; planeCount: number; phase: Phase
  deadlineAt: number | null; turn: string
  you: {
    playerId: string; connected: boolean
    planes: Cell[]              // 自己的机头；未摆放时为 []
    planesDestroyed: string[]
    shots: ShotRecord[]         // 我打出去的炮（用于渲染对手棋盘）
    incomingShots: ShotRecord[] // 打在我棋盘上的炮（用于渲染自己的棋盘）
  }
  opponent: { playerId: string; connected: boolean; planesDestroyed: string[] }
}

export type ShotRecord = { row: number; col: number; result: ShotResult }
```

`RoomSnapshot.opponent` **没有 `planes`，也没有 `shots`**——这是 spec §八 的强制要求（对方机头永不下发），不是疏忽。`you` 里 `shots` 与 `incomingShots` 必须分开：前者画对手棋盘，后者画自己棋盘，混用会让玩家在自己的棋盘上看到自己打出去的炮。`playerId` 与 `accountId` 保持分离：P0 的房间状态与快照里**不出现** `accountId`，它是 P2 才引入的持久层字段。

- [ ] **Step 3: 写类型级测试**

```ts
// packages/shared/test/types.test.ts
import { describe, it, expect } from 'vitest'
import type { ServerMessage } from '../src/index'

describe('protocol types', () => {
  it('gameOver reason 只有 head / allPlanes / forfeit', () => {
    const reasons: Extract<ServerMessage, { type: 'gameOver' }>['reason'][] = ['head', 'allPlanes', 'forfeit']
    expect(reasons).toHaveLength(3)
  })

  it('placementTimeout 不是合法 reason（spec §二：摆放超时不判负）', () => {
    // @ts-expect-error 若 placementTimeout 被加进 GameOverReason，tsc 会报"未使用的 @ts-expect-error"
    const bad: Extract<ServerMessage, { type: 'gameOver' }>['reason'] = 'placementTimeout'
    expect(bad).toBeDefined()
  })
})
```

`@ts-expect-error` 在这里同时锁住两件事：类型里确实没有 `placementTimeout`（否则 `tsc` 报"未使用的 @ts-expect-error"），且测试文件被 `typecheck` 覆盖。

- [ ] **Step 4: 跑 typecheck 与测试**

Run: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared test`
Expected: 类型检查无错，1 个测试通过。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: scaffold monorepo and shared protocol types"
```

---

### Task 2: 飞机几何与摆放校验

**Files:**
- Create: `packages/shared/src/rules.ts`
- Create: `packages/shared/test/geometry.test.ts`

**Interfaces:**
- Consumes: `Cell` from `types.ts`
- Produces: `cellsOfPlane(head: Cell): Cell[]`、`isPlacementValid(head: Cell, boardSize: number): boolean`、`checkPlacement(heads: Cell[], boardSize: number, planeCount: number): PlacementCheck`、`cellKey(cell: Cell): string`

```ts
export type PlacementCheck = { ok: true } | { ok: false; reason: 'count' | 'outOfBounds' | 'overlap' }
```

- [ ] **Step 1: 写失败的测试**

```ts
// packages/shared/test/geometry.test.ts
import { describe, it, expect } from 'vitest'
import { cellsOfPlane, isPlacementValid, checkPlacement, cellKey } from '../src/index'

describe('cellsOfPlane', () => {
  it('返回机头为中心的 9 格', () => {
    const cells = cellsOfPlane({ row: 5, col: 5 })
    expect(cells).toHaveLength(9)
    expect(cells).toContainEqual({ row: 4, col: 4 })
    expect(cells).toContainEqual({ row: 6, col: 6 })
    expect(cells).toContainEqual({ row: 5, col: 5 })
  })
  it('机头本身包含在 9 格内', () => {
    expect(cellsOfPlane({ row: 3, col: 7 })).toContainEqual({ row: 3, col: 7 })
  })
})

describe('isPlacementValid', () => {
  it('棋盘中央合法', () => expect(isPlacementValid({ row: 5, col: 5 }, 10)).toBe(true))
  it('机头在 0 或 9 越界（机身会出棋盘）', () => {
    expect(isPlacementValid({ row: 0, col: 5 }, 10)).toBe(false)
    expect(isPlacementValid({ row: 9, col: 5 }, 10)).toBe(false)
    expect(isPlacementValid({ row: 5, col: 0 }, 10)).toBe(false)
    expect(isPlacementValid({ row: 5, col: 9 }, 10)).toBe(false)
  })
  it('合法范围是 1..boardSize-2', () => {
    expect(isPlacementValid({ row: 1, col: 1 }, 10)).toBe(true)
    expect(isPlacementValid({ row: 8, col: 8 }, 10)).toBe(true)
  })
  it('小棋盘 6x6 的范围是 1..4', () => {
    expect(isPlacementValid({ row: 4, col: 4 }, 6)).toBe(true)
    expect(isPlacementValid({ row: 5, col: 5 }, 6)).toBe(false)
  })
})

describe('checkPlacement', () => {
  it('数量不匹配返回 count', () => {
    expect(checkPlacement([{ row: 5, col: 5 }], 10, 2)).toEqual({ ok: false, reason: 'count' })
  })
  it('多机重叠返回 overlap', () => {
    // 两个机头相邻，(5,5) 与 (5,6) 的 9 格必然相交
    expect(checkPlacement([{ row: 5, col: 5 }, { row: 5, col: 6 }], 10, 2))
      .toEqual({ ok: false, reason: 'overlap' })
  })
  it('多机不重叠通过', () => {
    expect(checkPlacement([{ row: 2, col: 2 }, { row: 6, col: 6 }], 10, 2)).toEqual({ ok: true })
  })
  it('越界优先于重叠被报出', () => {
    expect(checkPlacement([{ row: 0, col: 0 }, { row: 5, col: 5 }], 10, 2))
      .toEqual({ ok: false, reason: 'outOfBounds' })
  })
})

describe('cellKey', () => {
  it('稳定且区分相邻格', () => {
    expect(cellKey({ row: 3, col: 4 })).toBe('3,4')
    expect(cellKey({ row: 4, col: 3 })).not.toBe(cellKey({ row: 3, col: 4 }))
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C packages/shared test geometry`
Expected: FAIL，`cellsOfPlane is not a function`。

- [ ] **Step 3: 实现 `packages/shared/src/rules.ts`**

`cellsOfPlane` 用双层循环 `row-1..row+1` × `col-1..col+1`。`isPlacementValid` 判 `row >= 1 && row <= boardSize - 2 && col >= 1 && col <= boardSize - 2`。`checkPlacement` 按 `count` → `outOfBounds` → `overlap` 的顺序短路（顺序即测试锁定的优先级），`overlap` 用 `Set<cellKey>` 检测重复。`cellKey` 返回 `` `${row},${col}` ``。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C packages/shared test geometry`
Expected: 全部 PASS（12 个断言）。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(shared): plane geometry and placement validation"
```

---

### Task 3: 开炮结算

**Files:**
- Create: `packages/shared/test/resolve-shot.test.ts`
- Modify: `packages/shared/src/rules.ts`

**Interfaces:**
- Consumes: `cellsOfPlane`, `cellKey`, `Plane`
- Produces: `resolveShot(planes: Plane[], cell: Cell): ShotResolution`

```ts
export type ShotResolution =
  | { result: 'miss' }
  | { result: 'body'; planeId: string }
  | { result: 'head'; planeId: string }
```

- [ ] **Step 1: 写失败的测试**

```ts
// packages/shared/test/resolve-shot.test.ts
import { describe, it, expect } from 'vitest'
import { resolveShot } from '../src/index'
import type { Plane } from '../src/index'

const onePlane: Plane[] = [{ id: 'p0', head: { row: 5, col: 5 } }]

describe('resolveShot', () => {
  it('机头格是 head', () => {
    expect(resolveShot(onePlane, { row: 5, col: 5 })).toEqual({ result: 'head', planeId: 'p0' })
  })
  it('机身四角是 body', () => {
    expect(resolveShot(onePlane, { row: 4, col: 4 })).toEqual({ result: 'body', planeId: 'p0' })
    expect(resolveShot(onePlane, { row: 6, col: 6 })).toEqual({ result: 'body', planeId: 'p0' })
  })
  it('机身四边中点是 body', () => {
    expect(resolveShot(onePlane, { row: 4, col: 5 })).toEqual({ result: 'body', planeId: 'p0' })
    expect(resolveShot(onePlane, { row: 5, col: 6 })).toEqual({ result: 'body', planeId: 'p0' })
  })
  it('紧贴机身外侧是 miss', () => {
    expect(resolveShot(onePlane, { row: 3, col: 5 })).toEqual({ result: 'miss' })
    expect(resolveShot(onePlane, { row: 7, col: 7 })).toEqual({ result: 'miss' })
  })
  it('多机时返回命中的那一架的 id', () => {
    const planes: Plane[] = [{ id: 'p0', head: { row: 2, col: 2 } }, { id: 'p1', head: { row: 7, col: 7 } }]
    expect(resolveShot(planes, { row: 7, col: 7 })).toEqual({ result: 'head', planeId: 'p1' })
    expect(resolveShot(planes, { row: 6, col: 7 })).toEqual({ result: 'body', planeId: 'p1' })
  })
  it('空飞机列表全是 miss', () => {
    expect(resolveShot([], { row: 5, col: 5 })).toEqual({ result: 'miss' })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C packages/shared test resolve-shot`
Expected: FAIL，`resolveShot is not a function`。

- [ ] **Step 3: 实现**

遍历 `planes`：先判 `cellKey(cell) === cellKey(plane.head)` ⇒ `head`；再判 cell 是否在 `cellsOfPlane(plane.head)` 内 ⇒ `body`；都没中 ⇒ `miss`。**机头判断必须先于机身**，因为机头也在 9 格内。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C packages/shared test resolve-shot`
Expected: 6 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(shared): shot resolution across planes"
```

---

### Task 4: 机头候选集推导

**Files:**
- Create: `packages/shared/test/candidate-heads.test.ts`
- Modify: `packages/shared/src/rules.ts`

**Interfaces:**
- Consumes: `cellsOfPlane`, `isPlacementValid`, `cellKey`
- Produces: `candidateHeads(bodyHits: readonly Cell[], boardSize: number): Cell[]`

- [ ] **Step 1: 写失败的测试**

```ts
// packages/shared/test/candidate-heads.test.ts
import { describe, it, expect } from 'vitest'
import { candidateHeads } from '../src/index'

describe('candidateHeads', () => {
  it('没有机身命中时返回全部合法机头位置', () => {
    // 10x10 的合法机头是 1..8 × 1..8 = 64 个
    expect(candidateHeads([], 10)).toHaveLength(64)
  })
  it('单次机身命中把候选收缩到该格的 8 邻域内', () => {
    const c = candidateHeads([{ row: 5, col: 5 }], 10)
    expect(c).toHaveLength(8)
    expect(c).toContainEqual({ row: 4, col: 4 })
    expect(c).not.toContainEqual({ row: 5, col: 5 })  // 机头本身不可能
    expect(c).not.toContainEqual({ row: 3, col: 5 })
  })
  it('靠近边缘时按棋盘裁剪', () => {
    // (1,1) 的左上邻域只有 3 个合法机头
    const c = candidateHeads([{ row: 1, col: 1 }], 10)
    expect(c).toHaveLength(3)
    expect(c).toContainEqual({ row: 2, col: 2 })
    expect(c).toContainEqual({ row: 1, col: 2 })
    expect(c).toContainEqual({ row: 2, col: 1 })
  })
  it('两次机身命中取交集', () => {
    // 两个命中格共享的合法机头只可能是能同时覆盖它们的那一架
    const c = candidateHeads([{ row: 4, col: 5 }, { row: 5, col: 6 }], 10)
    expect(c).toContainEqual({ row: 5, col: 5 })
    expect(c.length).toBeLessThan(8)
  })
  it('互相矛盾的命中返回空集', () => {
    expect(candidateHeads([{ row: 1, col: 1 }, { row: 8, col: 8 }], 10)).toHaveLength(0)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C packages/shared test candidate-heads`
Expected: FAIL。

- [ ] **Step 3: 实现**

对每个 `bodyHit`，计算 `H(c) = { h | isPlacementValid(h) && c ∈ cellsOfPlane(h) }`（等价于 c 的 8 邻域内的合法位置）。返回所有 `H(c)` 的交集；`bodyHits` 为空时返回全部合法位置。用 `cellKey` 做集合运算。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C packages/shared test candidate-heads`
Expected: 5 个测试 PASS。特别注意第一个测试断言 64 —— `isPlacementValid` 必须被真正调用，而不是返回硬编码的范围。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(shared): derive candidate head positions from body hits"
```

---

### Task 5: 结束判定与回合辅助

**Files:**
- Create: `packages/shared/test/game-over.test.ts`
- Modify: `packages/shared/src/rules.ts`

**Interfaces:**
- Consumes: `Plane`
- Produces:
  - `isAllPlanesDestroyed(planes: Plane[], destroyedPlaneIds: readonly string[]): boolean`
  - `isRepeatShot(shotKeys: ReadonlySet<string>, cell: Cell): boolean`

- [ ] **Step 1: 写失败的测试**

```ts
// packages/shared/test/game-over.test.ts
import { describe, it, expect } from 'vitest'
import { isAllPlanesDestroyed, isRepeatShot } from '../src/index'
import type { Plane } from '../src/index'

const planes: Plane[] = [{ id: 'p0', head: { row: 2, col: 2 } }, { id: 'p1', head: { row: 7, col: 7 } }]

describe('isAllPlanesDestroyed', () => {
  it('单机被击落即结束', () => {
    expect(isAllPlanesDestroyed([planes[0]], ['p0'])).toBe(true)
  })
  it('多机只击落一架不结束', () => {
    expect(isAllPlanesDestroyed(planes, ['p0'])).toBe(false)
  })
  it('全部击落才结束', () => {
    expect(isAllPlanesDestroyed(planes, ['p0', 'p1'])).toBe(true)
  })
  it('无飞机视为已结束（防御）', () => {
    expect(isAllPlanesDestroyed([], [])).toBe(true)
  })
})

describe('isRepeatShot', () => {
  it('打过的格子返回 true', () => {
    expect(isRepeatShot(new Set(['3,4']), { row: 3, col: 4 })).toBe(true)
  })
  it('没打过的格子返回 false', () => {
    expect(isRepeatShot(new Set(['3,4']), { row: 4, col: 3 })).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C packages/shared test game-over`
Expected: FAIL。

- [ ] **Step 3: 实现**

`isAllPlanesDestroyed`：`planes.every(p => destroyedPlaneIds.includes(p.id))`（空数组 `every` 天然为 `true`）。`isRepeatShot`：`shotKeys.has(cellKey(cell))`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C packages/shared test game-over`
Expected: 6 个测试 PASS。

- [ ] **Step 5: 全量测试 + Commit**

Run: `pnpm -C packages/shared test`
Expected: 全部 PASS。

```bash
git add -A && git commit -m "feat(shared): game-over and repeat-shot helpers"
```

---

### Task 6: 协议编解码与入站校验

**Files:**
- Create: `packages/shared/src/protocol.ts`
- Create: `packages/shared/test/protocol.test.ts`
- Modify: `packages/shared/src/index.ts`

**Interfaces:**
- Consumes: `ClientMessage`
- Produces:
  - `parseClientMessage(raw: string): ParseResult`
  - `encodeServerMessage(msg: ServerMessage): string`

```ts
export type ParseResult =
  | { ok: true; msg: ClientMessage }
  | { ok: false; code: 'BAD_JSON' | 'BAD_SHAPE' | 'UNKNOWN_TYPE' | 'UNSUPPORTED' }
```

- [ ] **Step 1: 写失败的测试（覆盖 Review Focus #4）**

```ts
// packages/shared/test/protocol.test.ts
import { describe, it, expect } from 'vitest'
import { parseClientMessage } from '../src/index'

const bad = (raw: string) => {
  const r = parseClientMessage(raw)
  expect(r.ok).toBe(false)
  return r.ok === false ? r.code : null
}

describe('parseClientMessage 拒绝畸形输入', () => {
  it('非 JSON', () => expect(bad('not json')).toBe('BAD_JSON'))
  it('非对象', () => expect(bad('42')).toBe('BAD_JSON'))
  it('null', () => expect(bad('null')).toBe('BAD_JSON'))
  it('缺 type 字段', () => expect(bad('{}')).toBe('UNKNOWN_TYPE'))
  it('未知 type', () => expect(bad('{"type":"hack"}')).toBe('UNKNOWN_TYPE'))
  it('fire 缺 col', () => expect(bad('{"type":"fire","row":3}')).toBe('BAD_SHAPE'))
  it('row 为负', () => expect(bad('{"type":"fire","row":-1,"col":3}')).toBe('BAD_SHAPE'))
  it('row 为小数', () => expect(bad('{"type":"fire","row":1.5,"col":3}')).toBe('BAD_SHAPE'))
  it('row 为字符串', () => expect(bad('{"type":"fire","row":"3","col":3}')).toBe('BAD_SHAPE'))
  it('joinRoom 房间号非 6 位数字', () => expect(bad('{"type":"joinRoom","roomCode":"abc"}')).toBe('BAD_SHAPE'))
  it('placePlane 空数组', () => expect(bad('{"type":"placePlane","planes":[]}')).toBe('BAD_SHAPE'))
  it('placePlane 元素缺 row', () => expect(bad('{"type":"placePlane","planes":[{"col":1}]}')).toBe('BAD_SHAPE'))
})

describe('parseClientMessage 接受合法输入', () => {
  it('fire', () => {
    const r = parseClientMessage('{"type":"fire","row":3,"col":4}')
    expect(r).toEqual({ ok: true, msg: { type: 'fire', row: 3, col: 4 } })
  })
  it('auth 无 token', () => {
    const r = parseClientMessage('{"type":"auth","playerId":"abc"}')
    expect(r.ok).toBe(true)
  })
  it('createRoom 无参数', () => {
    expect(parseClientMessage('{"type":"createRoom"}').ok).toBe(true)
  })
})

describe('useItem 在 P0 被标记为不支持', () => {
  it('返回 UNSUPPORTED 而非 BAD_SHAPE', () => {
    expect(bad('{"type":"useItem","itemId":"scan"}')).toBe('UNSUPPORTED')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C packages/shared test protocol`
Expected: FAIL。

- [ ] **Step 3: 实现 `protocol.ts`**

`JSON.parse` 包 try/catch → `BAD_JSON`。之后按 `type` 分发到各自的校验函数，校验每个字段的 `typeof` 与取值范围（`row/col` 必须 `Number.isInteger` 且 `>= 0`；上界交给房间判断，因为需要 `boardSize`）。`useItem` 直接返回 `UNSUPPORTED`。`encodeServerMessage` 就是 `JSON.stringify`。**不引入 zod 等校验库**——类型已由 TS 定义，手写校验与类型同源，且省一个依赖。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C packages/shared test protocol`
Expected: 16 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(shared): protocol parsing with inbound validation"
```

---

### Task 7: 服务端骨架、连接与认证

**Files:**
- Create: `apps/server/package.json`, `apps/server/tsconfig.json`, `apps/server/vitest.config.ts`
- Create: `apps/server/src/clock.ts`, `apps/server/src/main.ts`
- Create: `apps/server/test/auth.test.ts`

**Interfaces:**
- Consumes: `parseClientMessage`, `ServerMessage`
- Produces:
  - `Clock` 接口：`{ now(): number }`，默认 `systemClock`
  - `createServer(opts: { port: number; clock?: Clock; devMode?: boolean }): { close(): Promise<void>; port: number }`
  - `hub` 在 `main.ts` 中装配；测试通过 `createServer` 起真实 socket

- [ ] **Step 1: 写失败的测试**

```ts
// apps/server/test/auth.test.ts
import { describe, it, expect, afterAll } from 'vitest'
import WebSocket from 'ws'
import { createServer } from '../src/main'

const srv = await createServer({ port: 0 })
afterAll(() => srv.close())

function connect(port: number): Promise<WebSocket> {
  return new Promise((res, rej) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`)
    ws.on('open', () => res(ws)); ws.on('error', rej)
  })
}

describe('认证', () => {
  it('auth 后返回 ready 与 token', async () => {
    const ws = await connect(srv.port)
    const msg = await new Promise<any>(res => {
      ws.on('message', d => res(JSON.parse(d.toString())))
      ws.send(JSON.stringify({ type: 'auth', playerId: 'p-a' }))
    })
    expect(msg.type).toBe('ready')
    expect(msg.playerId).toBe('p-a')
    expect(typeof msg.token).toBe('string')
    ws.close()
  })

  it('未认证就发 createRoom 返回 error', async () => {
    const ws = await connect(srv.port)
    const msg = await new Promise<any>(res => {
      ws.on('message', d => res(JSON.parse(d.toString())))
      ws.send(JSON.stringify({ type: 'createRoom' }))
    })
    expect(msg.type).toBe('error')
    expect(msg.code).toBe('NOT_AUTHED')
    ws.close()
  })

  it('畸形输入不断开连接', async () => {
    const ws = await connect(srv.port)
    ws.send('garbage')
    const msg = await new Promise<any>(res => {
      ws.on('message', d => res(JSON.parse(d.toString())))
    })
    expect(msg.type).toBe('error')
    expect(msg.code).toBe('BAD_JSON')
    expect(ws.readyState).toBe(WebSocket.OPEN)
    ws.close()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test auth`
Expected: FAIL，`createServer` 不存在。

- [ ] **Step 3: 实现 `clock.ts` 与 `main.ts`**

`clock.ts` 导出 `export type Clock = { now(): number }` 和 `export const systemClock: Clock = { now: () => Date.now() }`。

`main.ts` 用 `ws` 的 `WebSocketServer`。每个连接挂一个 `Session { playerId?: string; ws; }`。消息处理顺序：`parseClientMessage` → 失败则回 `error` 并**保持连接**（`BAD_JSON`/`BAD_SHAPE`/`UNKNOWN_TYPE`/`UNSUPPORTED`）→ 成功则先检查是否已认证（`auth` 除外）→ 未认证回 `error NOT_AUTHED`。`auth` 时生成 token（`crypto.randomUUID()`），回 `ready`。

`createServer` 监听端口 `0` 时读取 `server.address().port` 返回真实端口。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test auth`
Expected: 3 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(server): ws bootstrap, clock injection, auth handshake"
```

---

### Task 8: 房间状态机 —— 创建、加入、退出

**Files:**
- Create: `apps/server/src/room.ts`
- Create: `apps/server/test/room-placement.test.ts`（本任务先写房间生命周期部分）

**Interfaces:**
- Consumes: `RoomSnapshot`, `Phase`, `ServerMessage`, `ClientMessage`
- Produces:

```ts
export type Outbound = { to: string; msg: ServerMessage }

export class Room {
  constructor(opts: { roomCode: string; boardSize: number; planeCount: number; playerIds: [string, string] })
  readonly roomCode: string
  readonly boardSize: number
  readonly planeCount: number
  readonly phase: Phase
  has(playerId: string): boolean
  handle(playerId: string, msg: ClientMessage, now: number): Outbound[]
  tick(now: number): Outbound[]
  snapshotFor(playerId: string): RoomSnapshot
  setConnected(playerId: string, connected: boolean, now: number): Outbound[]
}
```

**设计约束：** `Room` 是纯同步类，不持有 socket、不调用 `Date.now()`（时间从参数进来）。这是它能被确定性测试的前提。

- [ ] **Step 1: 写失败的测试**

```ts
// apps/server/test/room-placement.test.ts
import { describe, it, expect } from 'vitest'
import { Room } from '../src/room'

const mkRoom = () => new Room({
  roomCode: '123456', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'],
})

describe('房间生命周期', () => {
  it('初始 phase 是 placing，双方 simultaneous 摆放', () => {
    const r = mkRoom()
    expect(r.phase).toBe('placing')
  })
  it('非房间成员的消息被忽略', () => {
    const r = mkRoom()
    expect(r.handle('stranger', { type: 'fire', row: 1, col: 1 }, 0)).toEqual([])
  })
  it('双方都摆好后进入 playing', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    expect(r.phase).toBe('placing')
    r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    expect(r.phase).toBe('playing')
  })
  it('合法摆放回 planeAccepted', () => {
    const r = mkRoom()
    const out = r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    expect(out).toContainEqual({ to: 'a', msg: { type: 'planeAccepted', planes: [{ row: 2, col: 2 }] } })
  })
  it('越界摆放回 error 且不生效', () => {
    const r = mkRoom()
    const out = r.handle('a', { type: 'placePlane', planes: [{ row: 0, col: 0 }] }, 0)
    expect(out[0].msg).toMatchObject({ type: 'error', code: 'INVALID_PLACEMENT' })
    // 仍然可以重新摆
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    expect(r.phase).toBe('placing')
  })
  it('摆放阶段可以重摆', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    const out = r.handle('a', { type: 'placePlane', planes: [{ row: 3, col: 3 }] }, 0)
    expect(out).toContainEqual({ to: 'a', msg: { type: 'planeAccepted', planes: [{ row: 3, col: 3 }] } })
  })
  it('对方的机头永远不出现在我的快照里', () => {
    const r = mkRoom()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    const snap = r.snapshotFor('a')
    expect(JSON.stringify(snap.opponent)).not.toContain('7')
    expect(snap.you.planes).toEqual([{ row: 2, col: 2 }])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test room-placement`
Expected: FAIL，`Room` 不存在。

- [ ] **Step 3: 实现 `room.ts` 的房间骨架与摆放阶段**

内部状态：`players: Map<playerId, { planes: Plane[] | null; destroyed: Set<string>; shots: Map<cellKey, ShotResult>; connected: boolean }>`、`phase`、`turn`、`deadlineAt`、`winnerId`、`pendingRematch: Set<string>`。

`handle` 先判 `phase`，再按 `msg.type` 分发。摆放阶段只接受 `placePlane` 与 `leaveRoom`。`checkPlacement` 返回非 ok 则回 `error INVALID_PLACEMENT`。两方 `planes` 都非 null 时切到 `playing`，并 `turn = 随机一方`（用参数 `now` 之外的随机源——见 Step 4 说明）。

`snapshotFor` 严格按 Task 1 的 `RoomSnapshot` 构造：`you` 含 `planes` / `shots` / `incomingShots`，`opponent` 只有 `playerId` / `connected` / `planesDestroyed`。**`opponent` 不能有 `planes` 字段**，这是 spec §八 的硬约束；也不能有 `shots`，否则等于告诉了对手我打过哪些格（渲染时用不到，因为对方的棋盘是"我方开炮史"，就在 `you.shots` 里）。

- [ ] **Step 4: 随机源的确定性问题**

`turn` 的随机先手会破坏测试确定性。在 `Room` 构造参数里加一个可选 `rng?: () => number`，默认 `Math.random`；测试注入固定值。**这一步必须在写实现前就加进构造函数签名**，否则后面补会有连锁改动。

- [ ] **Step 5: 跑测试确认通过**

Run: `pnpm -C apps/server test room-placement`
Expected: 7 个测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(server): room state machine, placement phase, hidden opponent planes"
```

---

### Task 9: 房间状态机 —— 开炮与回合推进

**Files:**
- Modify: `apps/server/src/room.ts`
- Modify: `apps/server/test/room-placement.test.ts` → 新建 `apps/server/test/room-fire.test.ts`

**Interfaces:**
- Consumes: `resolveShot`, `isAllPlanesDestroyed`, `isRepeatShot`, `cellKey`, Task 8 的 `Room`
- Produces: `Room` 新增的 `playing` 阶段行为；`Outbound` 结构不变

- [ ] **Step 1: 写失败的测试（覆盖 Review Focus #1、#2）**

```ts
// apps/server/test/room-fire.test.ts
import { describe, it, expect } from 'vitest'
import { Room } from '../src/room'

const started = () => {
  const r = new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  return r   // rng()=0 → 先手是 players[0] 即 'a'
}

const firstTurn = (r: Room) => r.snapshotFor('a').turn

describe('开炮', () => {
  it('命中机头立即结束', () => {
    const r = started()
    const turn = firstTurn(r)
    const shooter = turn
    const target = turn === 'a' ? 'b' : 'a'
    const head = target === 'b' ? { row: 7, col: 7 } : { row: 2, col: 2 }
    const out = r.handle(shooter, { type: 'fire', row: head.row, col: head.col }, 100)
    expect(r.phase).toBe('finished')
    expect(out.some(o => o.msg.type === 'gameOver')).toBe(true)
    const go = out.find(o => o.msg.type === 'gameOver')!.msg as any
    expect(go.winnerId).toBe(shooter)
    expect(go.reason).toBe('head')
  })

  it('命中机身不结束并换手', () => {
    const r = started()
    const turn = firstTurn(r)
    const target = turn === 'a' ? 'b' : 'a'
    const head = target === 'b' ? { row: 7, col: 7 } : { row: 2, col: 2 }
    const out = r.handle(turn, { type: 'fire', row: head.row - 1, col: head.col - 1 }, 100)
    expect(r.phase).toBe('playing')
    expect(r.snapshotFor('a').turn).not.toBe(turn)
    const shot = out.find(o => o.msg.type === 'shotResult')!.msg as any
    expect(shot.result).toBe('body')
    expect(shot.planeId).toBe('p0')
  })

  it('未命中换手', () => {
    const r = started()
    const turn = firstTurn(r)
    const out = r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    const shot = out.find(o => o.msg.type === 'shotResult')!.msg as any
    expect(shot.result).toBe('miss')
  })

  it('非本方回合开炮被拒且不改变状态（Review Focus #2）', () => {
    const r = started()
    const turn = firstTurn(r)
    const waiting = turn === 'a' ? 'b' : 'a'
    const before = JSON.stringify(r.snapshotFor('a'))
    const out = r.handle(waiting, { type: 'fire', row: 1, col: 1 }, 100)
    expect(out).toHaveLength(1)
    expect(out[0].to).toBe(waiting)
    expect(out[0].msg.type).toBe('error')
    expect((out[0].msg as any).code).toBe('NOT_YOUR_TURN')
    expect(JSON.stringify(r.snapshotFor('a'))).toBe(before)
  })

  it('重复打同一格被拒且不消耗回合（Review Focus #1）', () => {
    const r = started()
    const turn = firstTurn(r)
    r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    // 现在轮到另一方，先换回来
    const back = r.snapshotFor('a').turn
    r.handle(back, { type: 'fire', row: 9, col: 9 }, 100)
    const again = r.snapshotFor('a').turn
    const out = r.handle(again, { type: 'fire', row: 1, col: 1 }, 100)
    expect(out[0].msg).toMatchObject({ type: 'error', code: 'REPEAT_SHOT' })
    expect(r.snapshotFor('a').turn).toBe(again)
  })

  it('摆放阶段不能开炮（Review Focus #2）', () => {
    const r = new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })
    const out = r.handle('a', { type: 'fire', row: 1, col: 1 }, 0)
    expect(out[0].msg).toMatchObject({ type: 'error', code: 'WRONG_PHASE' })
    expect(r.phase).toBe('placing')
  })

  it('越界坐标被拒', () => {
    const r = started()
    const turn = firstTurn(r)
    const out = r.handle(turn, { type: 'fire', row: 10, col: 1 }, 100)
    expect(out[0].msg).toMatchObject({ type: 'error', code: 'OUT_OF_RANGE' })
  })

  it('两炮连击的竞态：第二次被拒（Review Focus #1）', () => {
    const r = started()
    const turn = firstTurn(r)
    const out1 = r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    const out2 = r.handle(turn, { type: 'fire', row: 1, col: 2 }, 100)  // 同一发送方，已换手
    expect(out1.some(o => o.msg.type === 'shotResult')).toBe(true)
    expect(out2[0].msg).toMatchObject({ type: 'error', code: 'NOT_YOUR_TURN' })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test room-fire`
Expected: 多数 FAIL。

- [ ] **Step 3: 实现开炮逻辑**

顺序（每个检查失败即返回单个 `error`，不推进回合）：
1. `phase !== 'playing'` ⇒ `WRONG_PHASE`
2. `turn !== playerId` ⇒ `NOT_YOUR_TURN`
3. `row/col` 超出 `0..boardSize-1` ⇒ `OUT_OF_RANGE`
4. `isRepeatShot` ⇒ `REPEAT_SHOT`
5. 通过后：写 shooters 的 `shots[cellKey] = result`，广播 `shotResult` 给房间两人
6. `result === 'head'` ⇒ 记录 `destroyed.add(planeId)`，广播 `planeDestroyed`；`isAllPlanesDestroyed(target.planes, [...target.destroyed])` 为真 ⇒ `phase = 'finished'`、`winnerId = shooter`、广播 `gameOver`。
7. 否则换手、重置 `deadlineAt = now + 20000`

`gameOver.reason` 的取值规则（唯一，不得放宽）：
- 若被击落的是该玩家**最后一架**飞机且 `planeCount === 1` ⇒ `'head'`
- 若被击落的是该玩家**最后一架**飞机且 `planeCount > 1` ⇒ `'allPlanes'`
- 其余情况不结束对局

即：只有一架飞机时用 `head`，多机时用 `allPlanes` 表示"清理完毕"。P0 只会出现 `head`。
7. 否则换手、重置 `deadlineAt = now + 20000`

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test room-fire`
Expected: 8 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(server): firing, turn advance, and rejection of illegal shots"
```

---

### Task 10: 计时器与超时代打

**Files:**
- Modify: `apps/server/src/room.ts`
- Create: `apps/server/test/room-timer.test.ts`

**Interfaces:**
- Consumes: Task 9 的 `Room`
- Produces: `Room.tick(now: number): Outbound[]` 的完整语义

- [ ] **Step 1: 写失败的测试**

```ts
// apps/server/test/room-timer.test.ts
import { describe, it, expect } from 'vitest'
import { Room } from '../src/room'

const placing = () => new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })

const playing = () => {
  const r = placing()
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  return r
}

describe('回合计时', () => {
  it('未到 20 秒什么都不做', () => {
    const r = playing()
    expect(r.tick(19999)).toEqual([])
  })
  it('到 20 秒时代打一炮并换手', () => {
    const r = playing()
    const turn = r.snapshotFor('a').turn
    const out = r.tick(20000)
    expect(out.some(o => o.msg.type === 'shotResult')).toBe(true)
    expect(r.snapshotFor('a').turn).not.toBe(turn)
  })
  it('代打一定选未打过的格子', () => {
    const r = playing()
    const turn = r.snapshotFor('a').turn
    r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    // 现在对手回合，等对手超时
    const out = r.tick(100 + 20000)
    const shot = out.find(o => o.msg.type === 'shotResult')?.msg as any
    expect([shot.row, shot.col]).not.toEqual([1, 1])
  })
  it('连续 tick 不会重复代打', () => {
    const r = playing()
    r.tick(20000)
    expect(r.tick(20001)).toEqual([])
  })
})

describe('摆放计时', () => {
  it('60 秒未摆自动落子', () => {
    const r = placing()
    const out = r.tick(60000)
    expect(out.some(o => o.msg.type === 'planeAccepted')).toBe(true)
  })
  it('自动落子后双方都摆好则进入 playing', () => {
    const r = placing()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    r.tick(60000)
    expect(r.phase).toBe('playing')
  })
  it('自动落子的位置合法', () => {
    const r = placing()
    r.tick(60000)
    const snap = r.snapshotFor('a')
    const p = snap.you.planes[0]
    expect(p.row).toBeGreaterThanOrEqual(1)
    expect(p.row).toBeLessThanOrEqual(8)
  })
  it('摆放超时不判负（spec §二）', () => {
    const r = placing()
    const out = r.tick(60000)
    expect(out.some(o => o.msg.type === 'gameOver')).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test room-timer`
Expected: FAIL。

- [ ] **Step 3: 实现 `tick`**

`tick(now)`：
- `phase === 'paused'` ⇒ 返回 `[]`（冻结，不代打）
- `phase === 'placing'` && `now >= placeDeadline` ⇒ 为尚未摆放的一方随机选一个合法机头（避开已有飞机，用 `checkPlacement` 试错或穷举合法位置后洗牌），广播 `planeAccepted`；若双方齐了则切 `playing`
- `phase === 'playing'` && `now >= deadlineAt` ⇒ 在目标棋盘上随机挑一个未打过的格子，走与 `handle('fire')` 完全相同的结算路径（抽取私有方法 `applyShot` 供两者复用）
- 其余返回 `[]`

`applyShot` 复用是必须的：否则超时代打和正常开炮会走出两套结算，P1 加多机时必然分叉。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test room-timer`
Expected: 7 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(server): turn and placement timers with auto-fire"
```

---

### Task 11: 断线冻结、重连与判负

**Files:**
- Modify: `apps/server/src/room.ts`
- Create: `apps/server/test/room-disconnect.test.ts`

**Interfaces:**
- Consumes: `Room.setConnected(playerId, connected, now)`
- Produces: `paused` 阶段语义；`Room.handle` 需在重连后能返回 `state` 快照

- [ ] **Step 1: 写失败的测试（覆盖 Review Focus #3）**

```ts
// apps/server/test/room-disconnect.test.ts
import { describe, it, expect } from 'vitest'
import { Room } from '../src/room'

const playing = () => {
  const r = new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  return r
}

describe('断线', () => {
  it('断线进入 paused 并通知对手', () => {
    const r = playing()
    const out = r.setConnected('b', false, 1000)
    expect(r.phase).toBe('paused')
    expect(out).toContainEqual({ to: 'a', msg: { type: 'opponentLeft' } })
  })

  it('暂停期间不代打（spec §二）', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    expect(r.tick(1000 + 60000)).toEqual([])
  })

  it('暂停期间对手不能开炮', () => {
    const r = playing()
    const turn = r.snapshotFor('a').turn
    r.setConnected(turn === 'a' ? 'b' : 'a', false, 1000)
    const out = r.handle(turn, { type: 'fire', row: 1, col: 1 }, 1500)
    expect(out[0].msg).toMatchObject({ type: 'error', code: 'PAUSED' })
  })

  it('重连恢复原阶段并顺延 deadline', () => {
    const r = playing()
    const before = r.snapshotFor('a').deadlineAt!
    r.setConnected('b', false, 1000)
    const out = r.setConnected('b', true, 11000)   // 断了 10 秒
    expect(r.phase).toBe('playing')
    expect(out.some(o => o.msg.type === 'opponentBack')).toBe(true)
    expect(r.snapshotFor('a').deadlineAt).toBe(before + 10000)
  })

  it('超过 30 秒未回判负', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    const out = r.tick(1000 + 30000)
    expect(r.phase).toBe('finished')
    const go = out.find(o => o.msg.type === 'gameOver')!.msg as any
    expect(go.winnerId).toBe('a')
    expect(go.reason).toBe('forfeit')
  })

  it('宽限期内重连不判负（Review Focus #3 边界）', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    const out = r.setConnected('b', true, 30999)   // 只差 1 毫秒
    expect(r.phase).toBe('playing')
    expect(out.some(o => o.msg.type === 'gameOver')).toBe(false)
  })

  it('恰好到 30 秒时先 tick 则判负，之后重连无效（Review Focus #3）', () => {
    const r = playing()
    r.setConnected('b', false, 1000)
    r.tick(31000)                                  // 判负先生效
    expect(r.phase).toBe('finished')
    const out = r.setConnected('b', true, 31000)
    expect(out.some(o => o.msg.type === 'gameOver')).toBe(false)
    expect(r.phase).toBe('finished')
  })

  it('摆放阶段断线也冻结', () => {
    const r = new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })
    r.setConnected('a', false, 0)
    expect(r.phase).toBe('paused')
    expect(r.tick(120000)).toEqual([])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test room-disconnect`
Expected: FAIL。

- [ ] **Step 3: 实现**

新增内部字段 `pausedAt: number | null` 与 `resumePhase: Phase | null`。

`setConnected(id, false, now)`：若房间非 `finished`，记 `pausedAt = now`、`resumePhase = phase`、`phase = 'paused'`，向对手广播 `opponentLeft`。
`setConnected(id, true, now)`：若 `pausedAt === null` 直接返回；若 `now - pausedAt > 30000` 则（理论上已被 tick 判负）不复活；否则 `deadlineAt += (now - pausedAt)`、`phase = resumePhase`、广播 `opponentBack`，并给重连方发 `state` 快照。`finished` 之后的重连只发 `state`，不复活。

`tick`：`phase === 'paused'` && `now - pausedAt >= 30000` ⇒ 判负（`forfeit`），`phase = 'finished'`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test room-disconnect`
Expected: 8 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(server): freeze on disconnect, resume with shifted deadline, forfeit after 30s"
```

---

### Task 12: 随机匹配队列

**Files:**
- Create: `apps/server/src/matchmaking.ts`
- Create: `apps/server/test/matchmaking.test.ts`

**Interfaces:**
- Consumes: `ServerMessage`
- Produces:

```ts
export class Matchmaking {
  constructor(opts: { enqueueWaitMs?: number })   // 默认 60000
  join(playerId: string, now: number): Outbound[]
  leave(playerId: string, now: number): Outbound[]
  tick(now: number): Outbound[]
  size(): number
}
```

- [ ] **Step 1: 写失败的测试**

```ts
// apps/server/test/matchmaking.test.ts
import { describe, it, expect } from 'vitest'
import { Matchmaking } from '../src/matchmaking'

describe('匹配队列', () => {
  it('第一个人入队不下发匹配结果', () => {
    const m = new Matchmaking({})
    expect(m.join('a', 0)).toEqual([])
    expect(m.size()).toBe(1)
  })
  it('第二个人入队时两人配对成功', () => {
    const m = new Matchmaking({})
    m.join('a', 0)
    const out = m.join('b', 100)
    expect(out).toHaveLength(2)
    expect(out.every(o => o.msg.type === 'matchFound')).toBe(true)
    expect(m.size()).toBe(0)
  })
  it('配对后两人拿到同一个房间号', () => {
    const m = new Matchmaking({})
    m.join('a', 0)
    const out = m.join('b', 100)
    const codes = out.map(o => (o.msg as any).roomCode)
    expect(codes[0]).toBe(codes[1])
    expect(codes[0]).toMatch(/^\d{6}$/)
  })
  it('重复入队不产生第二个自己', () => {
    const m = new Matchmaking({})
    m.join('a', 0)
    m.join('a', 10)
    expect(m.size()).toBe(1)
  })
  it('离队后不再被匹配', () => {
    const m = new Matchmaking({})
    m.join('a', 0)
    m.leave('a', 10)
    expect(m.join('b', 20)).toEqual([])
  })
  it('等待超过阈值给 queueTimeout 但不强制退出（spec §十五）', () => {
    const m = new Matchmaking({ enqueueWaitMs: 60000 })
    m.join('a', 0)
    const out = m.tick(60000)
    expect(out).toContainEqual({ to: 'a', msg: { type: 'queueTimeout' } })
    expect(m.size()).toBe(1)
  })
  it('只提示一次', () => {
    const m = new Matchmaking({ enqueueWaitMs: 60000 })
    m.join('a', 0)
    m.tick(60000)
    expect(m.tick(61000)).toEqual([])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test matchmaking`
Expected: FAIL。

- [ ] **Step 3: 实现**

`join`：若已在队列返回 `[]`；入队后若 `size() >= 2` 则 FIFO 取两人、生成 6 位数字房间号、返回两条 `matchFound`。房间号由 `Math.floor(100000 + Math.random() * 900000).toString()` 生成，**碰撞检测放在 Task 13 的 `hub` 里**（`matchmaking` 不持有房间表，只负责配对）。

`tick`：对每个已等待 ≥ `enqueueWaitMs` 且未提示过的玩家发一次 `queueTimeout`，不出队。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test matchmaking`
Expected: 7 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(server): random matchmaking queue"
```

---

### Task 13: Hub 装配 —— 房间表、路由、房间号碰撞、重连

**Files:**
- Modify: `apps/server/src/main.ts`
- Create: `apps/server/src/hub.ts`
- Create: `apps/server/test/hub-e2e.test.ts`

**Interfaces:**
- Consumes: `Room`、`Matchmaking`、`parseClientMessage`、`Clock`
- Produces: `Hub` 类，`createServer` 内部使用

```ts
export class Hub {
  constructor(opts: { clock: Clock; devMode?: boolean })
  connect(sessionId: string, send: (msg: ServerMessage) => void): void
  receive(sessionId: string, raw: string): void
  disconnect(sessionId: string): void
  tick(): void
  getRoom(roomCode: string): Room | undefined
}
```

- [ ] **Step 1: 写失败的测试**

```ts
// apps/server/test/hub-e2e.test.ts
import { describe, it, expect } from 'vitest'
import { Hub } from '../src/hub'
import type { ServerMessage } from '../../../packages/shared/src/index'

function mkHub() {
  const hub = new Hub({ clock: { now: () => 0 } })
  const inbox = new Map<string, ServerMessage[]>()
  const recv = (id: string) => inbox.get(id) ?? []
  const connect = (id: string) => {
    inbox.set(id, [])
    hub.connect(id, m => inbox.get(id)!.push(m))
    hub.receive(id, JSON.stringify({ type: 'auth', playerId: id }))
  }
  const send = (id: string, msg: unknown) => hub.receive(id, JSON.stringify(msg))
  return { hub, recv, connect, send }
}

describe('Hub 端到端', () => {
  it('建房后对手用房间号加入，双方都进入 placing', () => {
    const { hub, recv, connect, send } = mkHub()
    connect('s1'); connect('s2')
    send('s1', { type: 'createRoom' })
    const roomJoined = recv('s1').find(m => m.type === 'roomJoined')! as any
    expect(roomJoined.roomCode).toMatch(/^\d{6}$/)

    send('s2', { type: 'joinRoom', roomCode: roomJoined.roomCode })
    expect(recv('s2').some(m => m.type === 'roomJoined')).toBe(true)
    expect(hub.getRoom(roomJoined.roomCode)!.phase).toBe('placing')
  })

  it('加入不存在的房间返回 error', () => {
    const { connect, send, recv } = mkHub()
    connect('s1')
    send('s1', { type: 'joinRoom', roomCode: '000000' })
    expect(recv('s1').at(-1)!.type).toBe('error')
  })

  it('第三人加入已满房间被拒', () => {
    const { connect, send, recv } = mkHub()
    connect('s1'); connect('s2'); connect('s3')
    send('s1', { type: 'createRoom' })
    const code = (recv('s1').find(m => m.type === 'roomJoined')! as any).roomCode
    send('s2', { type: 'joinRoom', roomCode: code })
    send('s3', { type: 'joinRoom', roomCode: code })
    expect((recv('s3').at(-1) as any).code).toBe('ROOM_FULL')
  })

  it('房间号不重复', () => {
    const { hub, recv, connect, send } = mkHub()
    connect('s1'); connect('s2')
    const codes = new Set<string>()
    for (let i = 0; i < 5; i++) {
      send('s1', { type: 'createRoom' })
      const m = recv('s1').filter(x => x.type === 'roomJoined').at(-1)! as any
      codes.add(m.roomCode)
    }
    expect(codes.size).toBe(5)
  })

  it('随机匹配的两人进入同一房间', () => {
    const { hub, recv, connect, send } = mkHub()
    connect('s1'); connect('s2')
    send('s1', { type: 'queueJoin' })
    send('s2', { type: 'queueJoin' })
    const a = recv('s1').find(m => m.type === 'matchFound')! as any
    const b = recv('s2').find(m => m.type === 'matchFound')! as any
    expect(a.roomCode).toBe(b.roomCode)
    expect(hub.getRoom(a.roomCode)!.phase).toBe('placing')
  })

  it('断线后用同一 playerId 重连能拿到 state 快照', () => {
    const { hub, recv, connect, send } = mkHub()
    connect('s1'); connect('s2')
    send('s1', { type: 'createRoom' })
    const code = (recv('s1').find(m => m.type === 'roomJoined')! as any).roomCode
    send('s2', { type: 'joinRoom', roomCode: code })
    hub.disconnect('s2')
    hub.connect('s3', m => recv('s1').push(m))
    hub.receive('s3', JSON.stringify({ type: 'auth', playerId: 's2' }))
    expect(recv('s1').some(m => m.type === 'state')).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test hub-e2e`
Expected: FAIL。

- [ ] **Step 3: 实现 `hub.ts`**

持有：`rooms: Map<string, Room>`、`roomsByPlayer: Map<string, string>`、`matchmaking: Matchmaking`、`sessions: Map<sessionId, { playerId, send }>`、`sessionsByPlayer: Map<playerId, sessionId>`。

- `connect(sessionId, send)`：登记 session。
- `receive`：`parseClientMessage` → 出错回 `error` 并返回 → 未认证且非 `auth` 回 `NOT_AUTHED` → 按 `type` 路由。`createRoom`/`joinRoom`/`queueJoin` 在 `hub` 层处理；`fire`/`placePlane`/`rematch*`/`leaveRoom` 转给 `roomsByPlayer.get(playerId)` 对应的 `Room.handle`，并把 `Outbound[]` 通过 `sessionsByPlayer` 投递。
- 房间号生成带碰撞重试：循环生成直到 `!rooms.has(code)`。
- `disconnect(sessionId)`：调 `Room.setConnected(false)`；若房间成员全离线则删除房间。
- 重连：`auth` 时若 `sessionsByPlayer` 里已有同 `playerId` 的旧 session 则顶掉它，并在 `Room.setConnected(true)` 后补发 `state`。
- `tick()`：遍历所有房间调 `tick` + `matchmaking.tick`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test hub-e2e`
Expected: 6 个测试 PASS。

- [ ] **Step 5: 把 `main.ts` 接到 `Hub` 与 tick 循环**

`setInterval(() => hub.tick(), 200)`。测试环境下不启 interval（`createServer` 只在 `port > 0` 时启动，或用 `devMode` 控制）。

- [ ] **Step 6: 全量测试 + Commit**

Run: `pnpm -C apps/server test`
Expected: 全部 PASS。

```bash
git add -A && git commit -m "feat(server): hub wiring, room table, reconnect to state snapshot"
```

---

### Task 14: 局后再来一局

**Files:**
- Modify: `apps/server/src/room.ts`
- Create: `apps/server/test/room-rematch.test.ts`

**Interfaces:**
- Consumes: `Room`
- Produces: `rematchRequest` / `rematchRespond` 语义（spec §九）

- [ ] **Step 1: 写失败的测试**

```ts
// apps/server/test/room-rematch.test.ts
import { describe, it, expect } from 'vitest'
import { Room } from '../src/room'

const finished = () => {
  const r = new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  const turn = r.snapshotFor('a').turn
  const target = turn === 'a' ? { row: 7, col: 7 } : { row: 2, col: 2 }
  r.handle(turn, { type: 'fire', row: target.row, col: target.col }, 100)
  return r
}

describe('rematch', () => {
  it('对局未结束时不能请求', () => {
    const r = new Room({ roomCode: '1', boardSize: 10, planeCount: 1, playerIds: ['a', 'b'], rng: () => 0 })
    const out = r.handle('a', { type: 'rematchRequest' }, 0)
    expect(out[0].msg).toMatchObject({ type: 'error', code: 'WRONG_PHASE' })
  })

  it('一方请求时通知对手', () => {
    const r = finished()
    const out = r.handle('a', { type: 'rematchRequest' }, 200)
    expect(out).toContainEqual({ to: 'b', msg: { type: 'rematchOffered', by: 'a' } })
  })

  it('双方都请求则重开并回到 placing', () => {
    const r = finished()
    r.handle('a', { type: 'rematchRequest' }, 200)
    const out = r.handle('b', { type: 'rematchRequest' }, 300)
    expect(r.phase).toBe('placing')
    expect(out.some(o => o.msg.type === 'phaseChanged')).toBe(true)
  })

  it('重开后房间号不变', () => {
    const r = finished()
    r.handle('a', { type: 'rematchRequest' }, 200)
    r.handle('b', { type: 'rematchRequest' }, 300)
    expect(r.roomCode).toBe('1')
  })

  it('重开后飞机与命中记录清空', () => {
    const r = finished()
    r.handle('a', { type: 'rematchRequest' }, 200)
    r.handle('b', { type: 'rematchRequest' }, 300)
    const snap = r.snapshotFor('a')
    // 重开后双方都还没摆放：planes 用空数组表示"未摆放"，
    // 一次性清空后由 planeAccepted 再填入（不是 null，以保持快照可序列化）
    expect(snap.you.planes).toEqual([])
    expect(snap.you.planes).toEqual([])
    expect(snap.you.shots).toEqual([])
    expect(snap.you.incomingShots).toEqual([])
    expect(snap.phase).toBe('placing')
    expect(snap.phase).toBe('placing')
  })

  it('拒绝则房间结束并可解散', () => {
    const r = finished()
    r.handle('a', { type: 'rematchRequest' }, 200)
    const out = r.handle('b', { type: 'rematchRespond', accept: false }, 300)
    expect(r.phase).toBe('finished')
    expect(out.some(o => o.msg.type === 'opponentLeft')).toBe(true)
  })

  it('一方离开房间关闭', () => {
    const r = finished()
    const out = r.handle('a', { type: 'leaveRoom' }, 200)
    expect(out.some(o => o.msg.type === 'opponentLeft')).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test room-rematch`
Expected: FAIL。

- [ ] **Step 3: 实现**

`finished` 阶段接受 `rematchRequest` / `rematchRespond` / `leaveRoom`。`pendingRematch: Set<playerId>`；两人都在集合里 ⇒ 重置状态（`planes = []`、`destroyed.clear()`、`shots.clear()`、`phase = 'placing'`、`turn` 重新随机、`pendingRematch.clear()`），广播 `phaseChanged { phase: 'placing' }`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test room-rematch`
Expected: 7 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(server): rematch in finished phase reusing room code"
```

---

### Task 15: 客户端骨架与棋盘组件

**Files:**
- Create: `apps/client/package.json`, `apps/client/vite.config.ts`, `apps/client/index.html`
- Create: `apps/client/src/main.ts`, `apps/client/src/App.vue`, `apps/client/src/pages.json`, `apps/client/src/manifest.json`
- Create: `apps/client/src/components/BoardGrid.vue`
- Create: `apps/client/src/board-model.ts`, `apps/client/test/board-model.test.ts`

**Interfaces:**
- Consumes: `Cell`, `ShotResult`
- Produces:
  - `buildBoardCells(opts: { boardSize: number; shots: { row: number; col: number; result: ShotResult }[]; planes: Cell[]; showPlane: boolean }): BoardCell[]`
  - `BoardCell = { row: number; col: number; state: 'unknown' | 'miss' | 'body' | 'head' }`
  - 组件 `<BoardGrid :board-size :cells :disabled @cellTap="(cell: Cell) => void" />`

**为什么先写 `board-model.ts`：** 渲染逻辑里唯一有判断的部分是"这一格该显示什么"。把它抽成纯函数，就能单测，而 `.vue` 只负责画。

- [ ] **Step 1: 写失败的测试**

```ts
// apps/client/test/board-model.test.ts
import { describe, it, expect } from 'vitest'
import { buildBoardCells } from '../src/board-model'

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
      boardSize: 10, showPlane: false, planes: [],
      shots: [{ row: 3, col: 4, result: 'body' }, { row: 0, col: 0, result: 'miss' }],
    })
    expect(cells[3 * 10 + 4].state).toBe('body')
    expect(cells[0].state).toBe('miss')
  })

  it('showPlane 为真时自己的飞机 9 格可见，机头单独标记', () => {
    const cells = buildBoardCells({ boardSize: 10, shots: [], planes: [{ row: 5, col: 5 }], showPlane: true })
    expect(cells[5 * 10 + 5].state).toBe('head')
    expect(cells[4 * 10 + 4].state).toBe('body')
    expect(cells[4 * 10 + 5].state).toBe('body')
  })

  it('showPlane 为假时飞机不可见', () => {
    const cells = buildBoardCells({ boardSize: 10, shots: [], planes: [{ row: 5, col: 5 }], showPlane: false })
    expect(cells.every(c => c.state === 'unknown')).toBe(true)
  })

  it('棋盘尺寸变化时格子数跟随', () => {
    expect(buildBoardCells({ boardSize: 8, shots: [], planes: [], showPlane: false })).toHaveLength(64)
    expect(buildBoardCells({ boardSize: 12, shots: [], planes: [], showPlane: false })).toHaveLength(144)
  })

  it('机头优先级高于机身命中记录', () => {
    const cells = buildBoardCells({
      boardSize: 10, showPlane: true, planes: [{ row: 5, col: 5 }],
      shots: [{ row: 5, col: 5, result: 'head' }],
    })
    expect(cells[5 * 10 + 5].state).toBe('head')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/client test board-model`
Expected: FAIL。

- [ ] **Step 3: 实现 `board-model.ts` 与 `BoardGrid.vue`**

`buildBoardCells`：先建 `boardSize²` 个 `unknown`，用 `cellKey` 索引覆盖 `shots`，再用 `cellsOfPlane`（从 `@plane-duel/shared` import）覆盖 `planes`（`showPlane` 为真时），机头最后覆盖。

`BoardGrid.vue`：
```vue
<template>
  <view class="board" :style="{ '--n': boardSize }">
    <view v-for="c in cells" :key="`${c.row},${c.col}`"
          class="cell" :class="[c.state, { disabled }]"
          @tap="onTap(c)" />
  </view>
</template>
```
CSS：`.board { display: grid; grid-template-columns: repeat(var(--n), 1fr); gap: 2px; aspect-ratio: 1; }`、`.cell { aspect-ratio: 1; border-radius: 2px; }` 加四种 state 的配色。`--n` 用 CSS 变量而非内联 `repeat(10, ...)`，这样 `boardSize` 变化时不用改样式（兑现 spec §十四 里"单一棋盘尺寸的 UI 布局"这笔债的最小版本）。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/client test board-model`
Expected: 6 个测试 PASS。

- [ ] **Step 5: 用 H5 dev server 目视确认棋盘渲染**

Run: `pnpm -C apps/client dev`
Expected: 浏览器打开后看到 10×10 网格，点击有视觉反馈。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(client): uni-app scaffold and grid board component"
```

---

### Task 16: 客户端网络层与状态仓库

**Files:**
- Create: `apps/client/src/net/socket.ts`, `apps/client/src/net/store.ts`

**Interfaces:**
- Consumes: `ClientMessage`, `ServerMessage`, `parse` 不需要（客户端只发合法消息）
- Produces:
  - `connectSocket(opts: { url: string; playerId: string }): SocketHandle`
  - `SocketHandle = { send(msg: ClientMessage): void; onMessage(cb: (m: ServerMessage) => void): void; close(): void; status: Ref<'connecting'|'open'|'closed'> }`
  - `useGameStore()` 返回响应式 `{ roomCode, phase, turn, you, opponent, deadlineAt, boardSize, planeCount, error, connected }`

- [ ] **Step 1: 实现 `socket.ts`**

`uni.connectSocket` 包一层，处理 `onOpen`/`onMessage`/`onClose`/`onError`。自动重连：`onClose` 后 1 秒重连，指数退避到 8 秒上限，重连成功后立即发 `auth`（带 `playerId` 和上次拿到的 `token`）。消息解析失败只记日志，不抛。

`playerId` 用 `uni.getStorageSync('playerId')` 持久化，没有则 `crypto.randomUUID()` 生成并存下。

- [ ] **Step 2: 实现 `store.ts`**

用 Vue 的 `reactive` 持有对局状态，暴露 `applyServerMessage(m: ServerMessage)` 把消息归约进状态：
- `roomJoined` → 设 `roomCode`/`boardSize`/`planeCount`/`you`/`opponent`
- `phaseChanged` → 设 `phase`/`deadlineAt`
- `shotResult` → 若 `by === you.playerId` 则把这条记录写入 `you.shots`（我打出去的），否则写入 `you.incomingShots`（打在我棋盘上的）。这两条必须分开，否则自己的棋盘会显示成对手的棋盘。
- `planeDestroyed` → push 进对应方的 `planesDestroyed`
- `gameOver` → 设 `phase = 'finished'` 与 `winnerId`
- `state` → 整体替换
- `error` → 设 `error`，3 秒后清空

- [ ] **Step 3: 手工验证**

起服务端 `pnpm -C apps/server dev` + 客户端 `pnpm -C apps/client dev`，浏览器打开两个标签页，在控制台手动调用 `socket.send({type:'auth',...})` 与 `createRoom`，确认 `ready` 与 `roomJoined` 都进了 store。此时代码里还没有 UI 触发，只能手测。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(client): websocket layer with auto-reconnect and reactive game store"
```

---

### Task 17: 大厅、摆放、对局三个界面

**Files:**
- Create: `apps/client/src/views/Lobby.vue`, `apps/client/src/views/Place.vue`, `apps/client/src/views/Play.vue`
- Create: `apps/client/src/components/Countdown.vue`
- Modify: `apps/client/src/App.vue`, `apps/client/src/pages.json`

**Interfaces:**
- Consumes: `useGameStore()`、`connectSocket`、`BoardGrid`
- Produces: 用户可完整操作的三个界面

- [ ] **Step 1: `Countdown.vue`**

接收 `deadlineAt: number | null`，内部 `setInterval` 每 250ms 算剩余秒数，显示 `剩余 Ns`。`deadlineAt` 为 `null` 时显示 `--`。组件卸载时清 interval。

- [ ] **Step 2: `Lobby.vue`**

四个动作按钮：`创建房间`、`输入房间号加入`（一个 `input` + 确认）、`随机匹配`、`取消匹配`。匹配中显示 `正在寻找对手…` 与已等待秒数；收到 `queueTimeout` 显示提示但保持匹配中。收到 `matchFound` 或 `roomJoined` 后由 `App.vue` 按 `phase` 切界面。

- [ ] **Step 3: `Place.vue`**

一个 `BoardGrid`（`showPlane: true`、`planes` 为本地暂存的机头）。点击某格 ⇒ 本地记录该机头（`cellsOfPlane` 高亮）+ 立即 `send({ type: 'placePlane', planes: [cell] })`。收到 `planeAccepted` 后显示 `已就绪，等待对手`。顶部 `Countdown` 显示摆放剩余时间。可反复点击重摆。

- [ ] **Step 4: `Play.vue`**

上下两块棋盘：
- 上：**对手棋盘** `cells = buildBoardCells({ boardSize, showPlane: false, planes: [], shots: you.shots })`，可点击发 `fire`
- 下：**自己棋盘** `cells = buildBoardCells({ boardSize, showPlane: true, planes: you.planes, shots: you.incomingShots })`，不可点击

两者的 `shots` 来源不同，这是最容易接错的一处：`you.shots` 是我打出去的炮（画在对手棋盘上），`you.incomingShots` 是打在我棋盘上的炮（画在自己棋盘上）。

`fire` 前本地做一次乐观禁用（把该格标记为"发送中"）防止连点，收到 `shotResult` 或 `error` 后解除。这一步是 Review Focus #1 在客户端侧的对应防护。

顶部：`轮到你了 / 等待对手`、`Countdown`、对方在线状态。`phase === 'paused'` 时全屏遮罩显示 `对手已掉线，等待重连…`。

`phase === 'finished'` 时显示结果与 `再来一局`、`离开` 两个按钮。

- [ ] **Step 5: 机头候选高亮开关（spec §十二）**

`Play.vue` 顶部加一个开关，默认 `false`，状态存 `uni.getStorageSync('hintEnabled')`。开启时用 `candidateHeads(you.shots.filter(s => s.result === 'body'), boardSize)` 算出候选机头，在这些格子上叠一层淡色虚线框。

**必须默认关闭**：打开就等于替玩家做核心推理，摧毁游戏乐趣。开关只是给新手一个可选的学习辅助。

- [ ] **Step 6: `App.vue` 按 phase 路由**

`phase === null || 'waiting'` ⇒ Lobby；`'placing'` ⇒ Place；`'playing' | 'paused' | 'finished'` ⇒ Play。

- [ ] **Step 7: 双标签页手工验证完整对局**

起服务端与客户端，两个标签页：
1. A 建房，B 用房间号加入 → 双方进入摆放
2. 双方摆放 → 进入对局，先手方可以点
3. 轮流开炮直到一方打中机头 → 双方都看到结束界面
4. 双方点"再来一局" → 回到摆放阶段
5. 一方刷新页面 → 重连后回到对局并看到完整棋盘

Expected: 五步全部符合预期。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(client): lobby, placement and play views"
```

---

### Task 18: 端到端自动化对局

**Files:**
- Create: `apps/server/test/full-game.e2e.test.ts`

**Interfaces:**
- Consumes: `createServer`、`Hub`
- Produces: 一个用两个 WebSocket 客户端打完真实一局的测试；同时作为开发环境的机器人

- [ ] **Step 1: 写测试**

```ts
// apps/server/test/full-game.e2e.test.ts
import { describe, it, expect, afterAll } from 'vitest'
import WebSocket from 'ws'
import { createServer } from '../src/main'
import { candidateHeads } from '../../../packages/shared/src/index'
import type { Cell } from '../../../packages/shared/src/index'

const srv = await createServer({ port: 0, devMode: true })
afterAll(() => srv.close())

function client(id: string) {
  const ws = new WebSocket(`ws://127.0.0.1:${srv.port}`)
  const inbox: any[] = []
  const waiters: { type: string; res: (m: any) => void; rej: (e: Error) => void; timer: any }[] = []

  const flush = () => {
    for (let i = 0; i < waiters.length; i++) {
      const w = waiters[i]
      const idx = inbox.findIndex(m => m.type === w.type)
      if (idx >= 0) {
        const [m] = inbox.splice(idx, 1)     // 消费，避免重复命中同一条
        clearTimeout(w.timer)
        waiters.splice(i, 1); i--
        w.res(m)
      }
    }
  }

  ws.on('message', d => { inbox.push(JSON.parse(d.toString())); flush() })

  return {
    ws,
    open: () => new Promise<void>(r => ws.on('open', () => r())),
    send: (m: unknown) => ws.send(JSON.stringify(m)),
    // 同样消费 inbox 里的历史消息
    next: (type: string, timeout = 3000) => new Promise<any>((res, rej) => {
      const idx = inbox.findIndex(m => m.type === type)
      if (idx >= 0) return res(inbox.splice(idx, 1)[0])
      const timer = setTimeout(() => {
        const i = waiters.findIndex(w => w.timer === timer)
        if (i >= 0) waiters.splice(i, 1)
        rej(new Error(`timeout waiting ${type}`))
      }, timeout)
      waiters.push({ type, res, rej, timer })
    }),
  }
}

describe('完整对局', () => {
  it('两个客户端通过房间号打完一局，由推理而非运气命中机头', async () => {
    const a = client('alice'); const b = client('bob')
    await a.open(); await b.open()
    a.send({ type: 'auth', playerId: 'alice' })
    b.send({ type: 'auth', playerId: 'bob' })
    await a.next('ready'); await b.next('ready')

    a.send({ type: 'createRoom' })
    const joined = await a.next('roomJoined')
    expect(joined.boardSize).toBe(10)
    expect(joined.planeCount).toBe(1)

    b.send({ type: 'joinRoom', roomCode: joined.roomCode })
    await b.next('roomJoined')

    a.send({ type: 'placePlane', planes: [{ row: 2, col: 2 }] })
    b.send({ type: 'placePlane', planes: [{ row: 7, col: 7 }] })
    await a.next('planeAccepted'); await b.next('planeAccepted')
    await a.next('phaseChanged')   // playing

    const sock = { alice: a, bob: b }
    const heads: Record<string, Cell> = { alice: { row: 2, col: 2 }, bob: { row: 7, col: 7 } }
    const bodyHits: Record<string, Cell[]> = { alice: [], bob: [] }
    const fired: Record<string, Set<string>> = { alice: new Set(), bob: new Set() }

    // 先手未知：由 alice 试一炮，若被拒（NOT_YOUR_TURN）则先手是 bob。
    // 这同时验证了 Review Focus #2 的拒绝路径。
    let turn: 'alice' | 'bob'
    const probe: Cell = { row: 0, col: 0 }
    a.send({ type: 'fire', row: probe.row, col: probe.col })
    const first = await Promise.race([
      a.next('shotResult').then(m => ({ ok: true as const, m })),
      a.next('error').then(m => ({ ok: false as const, m })),
    ])
    let over: any = null
    if (first.ok) {
      turn = 'bob'          // alice 打完后轮到 bob
      fired.alice.add('0,0')
      if (first.m.result === 'body') bodyHits.alice.push(probe)
    } else {
      expect(first.m.code).toBe('NOT_YOUR_TURN')
      turn = 'bob'          // 先手是 bob
    }

    for (let i = 0; i < 60 && !over; i++) {
      const shooter = turn
      const target = shooter === 'alice' ? 'bob' : 'alice'
      // 候选集为空说明推理已收敛到唯一解，直接打机头
      const cands = candidateHeads(bodyHits[shooter], 10)
        .filter(c => !fired[shooter].has(`${c.row},${c.col}`))
      const cell = cands[0] ?? heads[target]

      fired[shooter].add(`${cell.row},${cell.col}`)
      sock[shooter].send({ type: 'fire', row: cell.row, col: cell.col })

      const raced = await Promise.race([
        sock[shooter].next('shotResult').then(m => ({ kind: 'shot' as const, m })),
        sock[shooter].next('gameOver').then(m => ({ kind: 'over' as const, m })),
      ])

      if (raced.kind === 'over') { over = raced.m; break }

      expect(raced.m.row).toBe(cell.row)
      expect(raced.m.col).toBe(cell.col)
      if (raced.m.result === 'body') bodyHits[shooter].push(cell)
      turn = raced.m.nextTurn === 'alice' ? 'alice' : 'bob'
    }

    expect(over).not.toBeNull()
    expect(over.reason).toBe('head')
    expect(['alice', 'bob']).toContain(over.winnerId)
  }, 30000)
})
```

**为什么 `next()` 必须消费：** 若按 `type` 在累积的 inbox 里反复查找，第二轮会再次命中第一轮那条 `shotResult`，循环永远读不到新消息。上面的实现从 inbox `splice` 取出即删，是测试能跑对的关键。

**为什么用 `gameOver` 与 `shotResult` 竞争：** 命中机头的最后那一炮，服务端会**同时**下发 `shotResult(result=head)` 与 `gameOver`。等 `shotResult` 再等 `gameOver` 会让顺序依赖消息到达次序；竞争写法两种都用得上。

**注意：** 上面的开炮循环还太糊。实现时改为：每轮从 `shotResult` 里得知谁该开炮，由该方用 `candidateHeads` 推理出对方机头并开炮，直到 `gameOver`。这样测试同时验证了推理逻辑，且必然在有限步内结束（机头候选集每轮单调收缩）。

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C apps/server test full-game`
Expected: FAIL（推理循环未实现）。

- [ ] **Step 3: 实现推理循环**

用一个 `botFire(knownBodyHits: Cell[])` 辅助：`candidateHeads(bodyHits, 10)` 取第一个未打过的候选作为下一炮。挂在测试内部，不进生产代码。

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C apps/server test full-game`
Expected: PASS，且 `gameOver.reason` 为 `head`。

- [ ] **Step 5: 全量测试 + Commit**

Run: `pnpm test`
Expected: shared / server / client 三包全部 PASS。

```bash
git add -A && git commit -m "test(server): end-to-end full game over real websockets"
```

---

### Task 19: Android / iOS 打包

**Files:**
- Modify: `apps/client/manifest.json`（appid、应用名、图标、权限）
- Create: `docs/deploy/packaging.md`

**Interfaces:**
- Consumes: Task 17 的可运行客户端
- Produces: 可安装到真机的 APK / IPA

**说明：** uni-app 的 App 打包依赖 HBuilderX 图形界面（云打包）。这一步无法用命令行完全自动化，因此任务以"可复现的操作手册 + 真机验收"为交付物，而不是一个脚本。

- [ ] **Step 1: 配置 `manifest.json`**

填 `name`（飞机对决）、`appid`（HBuilderX 生成的 `__UNI__` 标识）、`versionName`、`versionCode`、`app-plus.distribute.android.packagename`（如 `com.example.planeduel`）、`app-plus.distribute.ios.appid`（Bundle ID）、图标与启动图（1024×1024 一张主图，其余用 HBuilderX 自动生成）。

- [ ] **Step 2: H5 构建验证**

Run: `pnpm -C apps/client build:h5`
Expected: `dist/build/h5` 产出，`npx serve dist/build/h5` 打开能进大厅。

- [ ] **Step 3: 写 `docs/deploy/packaging.md`**

记录：HBuilderX 版本、云打包入口、Android 使用的证书（自签 keystore 的生成命令与存档位置）、iOS 需要的证书类型（开发证书 7 天有效 / 发布证书需 Apple Developer Program）、以及每次打包后的产物路径。

- [ ] **Step 4: 打包并在真机验收**

用 HBuilderX 云打包 Android APK，安装到一台 Android 手机；iOS 用开发签名装到一台 iPhone。

Expected: 两台真机各自能进大厅，能完成 Task 17 Step 6 的完整对局流程。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore(client): app manifest config and packaging runbook"
```

---

### Task 20: 部署

**Files:**
- Create: `apps/server/Dockerfile`
- Create: `docker-compose.yml`
- Create: `docs/deploy/deployment.md`

**Interfaces:**
- Consumes: Task 13 的服务端
- Produces: 一个可部署的单进程服务 + H5 静态站

**说明：** 按 spec §7.3，资质线（域名 ICP 备案、版号）在并行推进，**本任务只交付可部署产物与手册，实际公网域名上线要等备案下来**。在此之前可用一台海外/香港 VPS 跑通真实双机对战以做验收，但不对公众开放。

- [ ] **Step 1: 写 `Dockerfile`**

`node:22-alpine`，`pnpm install --prod --frozen-lockfile`，`CMD ["node", "apps/server/dist/main.js"]`。多阶段构建：builder 阶段跑 `pnpm -r build`。

- [ ] **Step 2: 写 `docker-compose.yml`**

一个 `server` 服务（暴露 8080）+ 一个 `caddy` 服务做 TLS 终止与 H5 静态托管。Caddy 配置反代 `/ws` 到 `server:8080`，托管 `apps/client/dist/build/h5`。

- [ ] **Step 3: 写 `docs/deploy/deployment.md`**

记录：VPS 规格（1 核 2G 足够）、Caddy 的自动 HTTPS 配置、`wss://` 地址如何填进客户端（用一个 `VITE_WS_URL` 环境变量，构建 H5 时注入）、日志位置、重启命令、以及"服务端重启会让在途对局失效"这一已知取舍。

- [ ] **Step 4: 客户端接入 `VITE_WS_URL`**

`apps/client/src/net/socket.ts` 里的地址从 `import.meta.env.VITE_WS_URL` 读，默认 `ws://localhost:8080/ws`。

- [ ] **Step 5: 本地起整套栈验证**

Run: `docker compose up --build`
Expected: `https://localhost` 能进大厅（Caddy 本地自签证书需要浏览器接受一次），两台设备通过该地址完成一局。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: docker deployment with caddy tls and h5 hosting"
```

---

## 执行顺序与依赖

```
Task 1 ─┬─ Task 2 ─ Task 3 ─ Task 4 ─ Task 5 ─ Task 6 ─┐
        │                                              │
        └──────────────────────────────────────────────┴─ Task 7 ─ Task 8 ─ Task 9 ─ Task 10 ─ Task 11 ─ Task 12 ─ Task 13 ─ Task 14
                                                                                                          │
                                              Task 15 ─ Task 16 ─ Task 17 ──────────────────────────────────┴─ Task 18
                                                                        │
                                                                        ├─ Task 19
                                                                        └─ Task 20
```

Task 15 只依赖 Task 2（`cellsOfPlane`），可与 Task 7–14 并行。Task 18 需要 Task 13 与 Task 17 都完成。

## 与 spec 里程碑的对应

| spec 里程碑 | 本计划任务 | 完成判据 |
|---|---|---|
| M1 规则与协议 | Task 1–6 | `pnpm -C packages/shared test` 全绿 |
| M2 服务端 | Task 7–14 | `pnpm -C apps/server test` 全绿 |
| M3 H5 客户端 | Task 15–17 | 浏览器双标签页打完一整局 |
| M4 房间号 + 匹配 | Task 13（Hub 路由）、Task 12（队列） | `hub-e2e` 与 `matchmaking` 测试通过 |
| M5 打包 | Task 19 | 两台真机安装并完成对局 |
| M6 部署 | Task 20 | `docker compose up` 后两台设备通过该地址对局 |
| （额外）整局自动化 | Task 18 | `full-game.e2e` 通过 |

## 不在本计划范围

- P1：多架飞机、可选棋盘尺寸 —— 协议与规则已留口（`planeCount`、`boardSize`、`planeId`），但不实现 UI 与摆放多机校验以外的玩法。
- P2：积分、账号、持久化。
- P3：道具与变现。
- P4：上架（软著、版号、商店审核）—— 资质线，见 spec §七。
