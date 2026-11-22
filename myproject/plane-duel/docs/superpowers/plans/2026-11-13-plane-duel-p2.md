# 飞机对决 P2 实施计划：人机练习、电脑补位、公开房间列表、房主踢人

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让大厅热闹：人少时能马上开局（人机练习、快速匹配 30 秒后电脑补位，均明确标注 🤖），人多时能找到别人开的桌子（公开房间列表，按 id 加入），房主能清理占座者（踢人）；同时吸收 P1 遗留的 M1–M5。

**Architecture:** 电脑是 `Table` 上带 `bot` 标记的座位，没有 socket，由 `Table.tick` 驱动：`BotDriver` 决定何时出手，纯函数 `brain` 决定打哪一格，二者的唯一输入是 `engine.view(电脑自己)`，动作只走 `engine.handle`——引擎与 Hub 都不知道电脑的存在。补位由 `Matchmaking.tick` 产出"带空座的成组"，Hub 建匹配桌后补电脑。公开列表是 `Table.listing()` 的投影，Hub 按专区订阅、合并推送完整快照。踢人是 `Table.kick`，被踢者记入本桌禁入表。

**Tech Stack:** TypeScript 5、pnpm workspace、Vitest、Node 22 + `ws` + `tsx`、Vite + Vue 3、Capacitor 8

**Spec:** `docs/superpowers/specs/2026-11-11-plane-duel-design.md`，**以 §二十 为准**（§十九 的桌子、混战、匹配规则仍有效）

**前置：** P1 已合并到 master，316 个测试全绿（shared 74 / server 191 / client 51）。P1 执行记录：`docs/superpowers/plans/2026-11-12-plane-duel-p1-execution-log.md`。

## Global Constraints

- 人机练习：独立入口，明确标注"练习"，不计段位、不进匹配池（spec §18.3）；练习桌不上公开列表、不能用房间号加入（spec §20.4）。
- 机器人用现成的 `candidateHeads` 推理，按档位加入随机失误率（入门 40%、高手 0%）（spec §18.3）；标准 25%、进阶 10%（spec §20.3）。
- 不让机器人冒充真人（spec §18.8）：电脑座位在等候室、对局、结算页一律显示 🤖；🤖 标记只来自 `seat.bot`，不来自昵称（spec §20.2、§20.5）。
- 电脑补位：队列里**真人 ≥ `minHumans = 2`** 后开始倒计时（2/3 人 30 秒、4 人 45 秒），到时当前队列全部真人成桌、空座补电脑，电脑难度 = 队列档位；不足 2 人时永远不补位，界面显示"等待真人 1/2"（spec §20.5）。
- 有电脑的局不计段位：`TableResult.botIds` 非空即不计（P3 落地，spec §20.5）。
- 电脑思考时间 1.2–3.5 秒（`BOT_THINK_MS = [1200, 3500]`），最晚截止前 1 秒出手（`BOT_DEADLINE_MARGIN_MS = 1000`）（spec §20.3）。
- 混战：一炮落在每个存活对手棋盘上；**结果私有**——任何玩家（真人或电脑）永远得不到 Y 的一炮在 Z 棋盘上的结果（spec §19.6）。电脑的决策输入只有 `engine.view(自己)`（spec §20.2）。
- 对方机头坐标任何时刻不下发给其他玩家（spec §八）。
- 公开列表只含：`kind === 'friend'`、`listed`、`phase === 'waiting'`、有空座、未关闭；每专区最多 50 条（`ROOM_LIST_MAX`），推送完整快照，每专区每秒最多一次（`ROOM_LIST_MIN_INTERVAL_MS = 1000`）；条目不含房间号与 playerId（spec §20.6）。
- 敏感词过滤：P2 开放公开房间列表前必须做（spec §19.8）；昵称 1–12 字符，服务端去首尾空白与控制字符，不合法或命中屏蔽词回退（spec §19.8、§20.6）。
- 踢人：好友房、房主、等候中、目标为在座真人且未准备且非自己；被踢者本桌禁入直到桌子关闭（spec §20.8）。
- 好友房：人满且全员准备才开局；房主改规则清空所有人的准备（spec §19.4）；`setReady` 必带 `rulesVersion`，不一致 → `STALE_RULES`（spec §20.7 M4）。
- 匹配房有人离开即解散（spec §19.4）；桌上没有真人即关桌（spec §20.5）。
- 等候室掉线保留座位：唯一在座**真人** 5 分钟，否则 60 秒（P1 裁定 R2；spec §20.4 规定只数真人）。
- 已在桌上（非结束状态）不能排队；快速匹配 60 秒仍未凑满提示一次（不踢出队列）——仅在补位关闭时出现（spec §19.7、§20.5）。
- 规则层（`rules.ts`、`ruleset.ts`、`placement.ts`）不改；引擎规则逻辑只做 Task 3 列出的三处改动（spec §20.10）。
- playerId + token 身份校验、顶号、同 socket 不可换身份、重认证补快照、出站按桌过滤、关桌清理保持不变；`auth.playerId` 以 `bot:` 开头 → `BAD_SHAPE`（spec §20.2、§20.10）。
- 所有用户可见文案为简体中文。

## Review Focus

计划里各任务的测试不会自然覆盖、但最可能伤到真实玩家的五类情况，已逐条把对应测试加进负责的任务：

1. **电脑破坏隐私不变量**：电脑若读到别人的视图，玩家会被"开天眼"的电脑针对；真人若从电脑相关消息里拿到第三方结果，混战的私有信息就破了。→ Task 9 断言"交给电脑 X 的视图恒等于 `engine.view(X)`"并扫描真人收到的全部消息；Task 16 端到端再扫一遍，并做变异验证。
2. **电脑卡住对局或空转**：电脑在 duel 暂停时出手、截止后出手、出局后出手、对局结束后出手，或者真人全走光后电脑之间一直打下去。→ Task 5（驱动器各阶段不出手、截止前 1 秒必出手）、Task 6（无真人即关桌）、Task 9（练习局在有限 tick 内打完）。
3. **踢人竞态**：房主踢一个刚点了准备的人（`TARGET_READY`）、最后一人准备同步开局后再踢（`ROOM_IN_GAME`）、被踢者用房间号或列表回来（`BANNED`）、被踢者之后仍收到这张桌子的消息。→ Task 7、Task 11。
4. **补位竞态**：同一 tick 内真人刚离队、刚加入好友房，补位不能建出没有真人的桌子，也不能让一个人同时坐两张桌子。→ Task 10、Task 11。
5. **公开列表泄漏或过期**：列表出现匹配房、练习房、对局中、已满、未公开的桌子，或泄漏房间号 / playerId / 被屏蔽的昵称；玩家点了一条刚过期的条目后丢掉了自己原来的座位。→ Task 8、Task 12。

**测试写法约定**（沿用 P1）：只写了 `it('名称', ...)` 的测试，其断言由该任务的"行为 / 规则 / 算法"段落唯一确定；判断容易出错的地方计划里已直接给出断言代码。

**过渡期约定（Task 1 → Task 12 / 15）**：Task 1 换成协议 v3 后，服务端 `tsc --noEmit` 允许报错，Task 12 结束时必须清零；客户端 `vue-tsc` 允许报错，Task 15 结束时必须清零。服务端各任务只跑本任务列出的测试文件与已经迁移的测试；`hub-*`、`auth`、`*.e2e` 在 Task 11 / 12 / 16 恢复为全绿。客户端单测（纯函数）始终可运行。

---

## File Structure

```
packages/shared/src/
  types.ts               改：协议 v3（TableKind、SeatView.bot、TableView.rulesVersion/listed、TableResult、RoomListEntry、GameView.you.submitted/pendingShot、新消息、新错误码）
  protocol.ts            改：解析新消息；bot: 前缀拒绝；BAD_RULES（M5）
  nickname.ts            改：sanitizeNickname 接入屏蔽词
  nickname-blocklist.ts  新：保留字 + 种子脏词表 + 归一化
  rules.ts / ruleset.ts / placement.ts   不变

apps/server/src/
  bot/brain.ts           新：纯函数打分与选格（chooseShot、scoreCells、opponentModel）
  bot/driver.ts          新：BotDriver（决策点、思考时间、截止保护）
  melee-engine.ts        改：view 增加 you.submitted/pendingShot（M1）、playerOut（M2）、摆放阶段掉线宽限（M3）
  duel-engine.ts         改：view 增加 you.submitted=false / pendingShot=null（仅类型对齐）
  table.ts               改：电脑座位、practice 桌、无真人关桌、rulesVersion、listed、listing()、kick、banned、canJoin
  matchmaking.ts         改：补位（botFillMs、botFillAt、tick 返回成组）
  hub.ts                 改：createPractice、补位建桌、kick、setListed、joinListed、列表订阅与推送、按桌成员集合（M5）
  main.ts                改：ServerOptions.botFillMs；ServerHandle.tick()（测试用）

apps/client/src/
  net/store.ts           改：roomList、kicked、playerOut、botFillAt、新错误文案
  lobby-model.ts         新：列表条目展示、补位倒计时文案、座位标签
  rule-editor-model.ts   改：defaultCreateRoom（默认公开）、practiceRequest
  route.ts               改：被踢后回大厅（锁定行为）
  components/
    SeatList.vue         改：🤖 标记、房主踢人按钮
    RoomList.vue         新：公开房间列表
    ResultSheet.vue      改：🤖 标记
  views/
    Zone.vue             改：人机练习、公开列表、补位倒计时
    WaitingRoom.vue      改：公开开关、踢人、rulesVersion、"本局有电脑"
    MeleePlay.vue        改：以服务端 submitted 为准（M1）、playerOut（M2）
  App.vue                改：kicked 处理
```

**拆分理由：** `brain` 是纯函数（视图进、格子出），可以离开引擎做大量确定性与统计测试；`driver` 只管"何时出手"，可用假视图与假时间测试；`Table` 只负责把二者接到引擎上。列表投影 `listing()` 放在 `Table`，因为"是否上榜"完全由桌子自身状态决定；订阅与节流放在 Hub，因为它跨桌。

---

### Task 1: 协议 v3

**Files:**
- Modify: `packages/shared/src/types.ts`, `packages/shared/src/protocol.ts`
- Modify: `packages/shared/test/protocol.test.ts`, `packages/shared/test/types.test.ts`

**Interfaces:**
- Consumes: `RuleSet`, `Capacity`, `PresetId`, `validateRuleSet`, `isCapacity`
- Produces（未列出的 P1 类型保持不变）：

```ts
export type TableKind = 'friend' | 'match' | 'practice'
export type BotDifficulty = PresetId
export type SeatView = { seat: number; playerId: string; nickname: string; ready: boolean; connected: boolean; bot: boolean }
export type TableResult = GameResult & { botIds: string[] }
export type TableView = {
  roomCode: string; kind: TableKind; capacity: Capacity; rules: RuleSet; rulesVersion: number; listed: boolean
  hostId: string | null; phase: TablePhase; seats: (SeatView | null)[]; lastResult: TableResult | null
}
export type RoomListEntry = {
  tableId: string; capacity: Capacity; rules: RuleSet; hostNickname: string; seated: number
  seats: ({ seat: number; nickname: string } | null)[]; createdAt: number
}
// GameView.you 增加 submitted: boolean; pendingShot: Cell | null

// ClientMessage 新增 / 修改
| { type: 'createRoom'; capacity: Capacity; rules: RuleSet; listed: boolean }
| { type: 'setReady'; ready: boolean; rulesVersion: number }
| { type: 'createPractice'; capacity: Capacity; preset: PresetId }
| { type: 'kick'; playerId: string }
| { type: 'setListed'; listed: boolean }
| { type: 'roomListSubscribe'; capacity: Capacity }
| { type: 'roomListUnsubscribe' }
| { type: 'joinListed'; tableId: string }

// ServerMessage 新增 / 修改
| { type: 'queueStatus'; capacity: Capacity; preset: PresetId; waiting: number; botFillAt: number | null }
| { type: 'roomList'; capacity: Capacity; entries: RoomListEntry[] }
| { type: 'kicked'; roomCode: string }
| { type: 'playerOut'; playerId: string; round: number }

// ErrorCode 新增
| 'TARGET_NOT_FOUND' | 'TARGET_READY' | 'BANNED' | 'STALE_RULES'
// ParseCode 新增 'BAD_RULES'
export const BOT_ID_PREFIX = 'bot:'
```

- [ ] **Step 1: 更新测试**

在 `protocol.test.ts` 新增（并把 P1 的 `createRoom … planeCount: 9 → 'BAD_SHAPE'` 改为 `'BAD_RULES'`，所有 `createRoom` / `setReady` 用例补上 `listed` / `rulesVersion`）：

```ts
it('auth：playerId 以 bot: 开头被拒', () => expect(bad({ type: 'auth', playerId: 'bot:123456:1:1' })).toBe('BAD_SHAPE'))
it('M5：形状正确但规则不合法 → BAD_RULES', () => {
  expect(bad({ type: 'createRoom', capacity: 2, rules: { ...PRESETS.standard, planeCount: 9 }, listed: true })).toBe('BAD_RULES')
  expect(bad({ type: 'updateRules', rules: { ...PRESETS.standard, boardSize: 30 } })).toBe('BAD_RULES')
  expect(bad({ type: 'createRoom', capacity: 5, rules: PRESETS.standard, listed: true })).toBe('BAD_SHAPE')
})
it('createRoom 需要布尔 listed', () => {
  expect(parse({ type: 'createRoom', capacity: 3, rules: PRESETS.advanced, listed: false })).toMatchObject({ ok: true })
  expect(bad({ type: 'createRoom', capacity: 3, rules: PRESETS.advanced })).toBe('BAD_SHAPE')
})
it('M4：setReady 必带非负整数 rulesVersion', () => {
  expect(parse({ type: 'setReady', ready: true, rulesVersion: 0 })).toMatchObject({ ok: true })
  expect(bad({ type: 'setReady', ready: true })).toBe('BAD_SHAPE')
  expect(bad({ type: 'setReady', ready: true, rulesVersion: -1 })).toBe('BAD_SHAPE')
})
it('createPractice 需要合法 capacity 与 preset', () => {
  expect(parse({ type: 'createPractice', capacity: 4, preset: 'beginner' })).toMatchObject({ ok: true })
  expect(bad({ type: 'createPractice', capacity: 1, preset: 'beginner' })).toBe('BAD_SHAPE')
})
it('kick / setListed / joinListed / roomListSubscribe / roomListUnsubscribe', () => {
  expect(parse({ type: 'kick', playerId: 'p2' })).toMatchObject({ ok: true })
  expect(bad({ type: 'kick', playerId: '' })).toBe('BAD_SHAPE')
  expect(parse({ type: 'setListed', listed: true })).toMatchObject({ ok: true })
  expect(parse({ type: 'joinListed', tableId: '0123456789abcdef' })).toMatchObject({ ok: true })
  expect(bad({ type: 'joinListed', tableId: 'x'.repeat(65) })).toBe('BAD_SHAPE')
  expect(parse({ type: 'roomListSubscribe', capacity: 3 })).toMatchObject({ ok: true })
  expect(parse({ type: 'roomListUnsubscribe' })).toMatchObject({ ok: true })
})
```

`types.test.ts`：错误码集合断言补上四个新码；`TableKind` 三个值。

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C packages/shared exec vitest run protocol types` → Expected: FAIL
- [ ] **Step 3: 改 `types.ts` 与 `protocol.ts`**。`tableId` 校验：非空字符串、长度 ≤ 64。`kick.playerId`：非空字符串、长度 ≤ 64。`rules` 字段存在但 `validateRuleSet` 失败（任何 reason，含 `shape`）→ `BAD_RULES`；`rules` 字段缺失 → `BAD_SHAPE`。
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C packages/shared exec vitest run` → Expected: 全部 PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(shared): protocol v3 for bots, practice, room list and kick"`

---

### Task 2: 昵称屏蔽词

**Files:**
- Create: `packages/shared/src/nickname-blocklist.ts`
- Modify: `packages/shared/src/nickname.ts`, `packages/shared/src/index.ts`, `packages/shared/test/nickname.test.ts`

**Interfaces:**
- Produces:
```ts
export function normalizeForBlocklist(s: string): string     // NFKC → 小写 → 去空白与 ·._-* 及全角空格
export function isNicknameBlocked(nickname: string): boolean
// sanitizeNickname(input, fallback) 不变签名：命中屏蔽词 → fallback
```
词表结构：`RESERVED_PREFIXES = ['电脑', '机器人', '系统', '官方', '管理员', 'admin', 'gm']`、`RESERVED_CONTAINS = ['🤖']`、`PROFANITY: string[]`（种子表，至少含 `傻逼`、`操你`、`fuck`、`shit`）。

- [ ] **Step 1: 写失败的测试**

```ts
it('保留字前缀回退（防止冒充电脑与官方）', () => {
  for (const n of ['电脑1', '机器人', '管理员小王', 'Admin', 'GM01']) expect(sanitizeNickname(n, '玩家')).toBe('玩家')
})
it('含 🤖 回退', () => expect(sanitizeNickname('小🤖', '玩家')).toBe('玩家'))
it('脏词包含匹配，绕过分隔符与全角', () => {
  for (const n of ['傻逼', '大傻·逼', 'ＦＵＣＫ', 'f u c k', 'f.u.c.k']) expect(sanitizeNickname(n, '玩家')).toBe('玩家')
})
it('正常昵称不受影响', () => { for (const n of ['敏捷的海鸥', '沉默的狐狸', '电工老李']) expect(sanitizeNickname(n, 'x')).toBe(n) })
it('保留字只按前缀：中间出现"电脑"不拦', () => expect(sanitizeNickname('我的电脑', 'x')).toBe('我的电脑'))
```

再在 `apps/client/test/nickname-gen.test.ts` 加一条：`generateNickname` 用 1000 个种子生成，全部 `!isNicknameBlocked`。

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C packages/shared exec vitest run nickname` → Expected: FAIL
- [ ] **Step 3: 实现**（保留字前缀匹配作用于归一化后的字符串开头；`PROFANITY` 与 `RESERVED_CONTAINS` 为包含匹配）
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C packages/shared exec vitest run && pnpm -C apps/client exec vitest run nickname-gen` → Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(shared): nickname blocklist with reserved words before public room list"`

---

### Task 3: 引擎的三处 P1 遗留修复（M1、M2、M3）

本任务**明确授权**修改 `melee-engine.ts` / `duel-engine.ts`，范围仅限下列三点；结算、排名、挂机、代打逻辑不得改动。

**Files:**
- Modify: `apps/server/src/melee-engine.ts`, `apps/server/src/duel-engine.ts`
- Create: `apps/server/test/melee-p2.test.ts`

**Interfaces:**
- Produces: `GameView.you.submitted / pendingShot`；melee 广播 `{ type: 'playerOut', playerId, round }`

**行为：**
- **M1**：melee `view(p).you.submitted = phase === 'playing' && p.pending !== null`；`you.pendingShot = p.pending`（只出现在本人视图）；duel 恒为 `false / null`。
- **M2**：`eliminateNow`（离开 / 掉线超时）在当场向**全体**广播 `playerOut { playerId, round: 当前轮次 }`；之后的 `roundResult.eliminated` 仍列出该玩家（不变）。
- **M3**：`phase === 'placing'` 时 `tick` 不因掉线出局；`startRound` 首轮开始时，对仍掉线的存活者把 `disconnectedAt` 置为该轮开始时刻；`setConnected(true)` 在 placing 阶段不判出局。

- [ ] **Step 1: 写失败的测试**

```ts
it('M1：提交后本人视图 submitted=true 且 pendingShot 为所提交格；他人视图里看不到该坐标', ...)
  // a fire (6,6) → view('a').you.submitted === true、pendingShot 等于 {row:6,col:6}；JSON.stringify(view('b')) 不含 '"row":6,"col":6'
it('M1：结算后 submitted 复位为 false、pendingShot 为 null', ...)
it('M1：duel 视图 submitted=false、pendingShot=null', ...)
it('M2：回合中途离开 → 立即广播 playerOut，下一条 roundResult.eliminated 仍含该玩家', ...)
it('M2：掉线满 30 秒出局 → playerOut 当场广播', ...)
it('M3：摆放阶段掉线 40 秒（摆放 45 秒）不出局，到时被自动摆放并进入第 1 轮', ...)
it('M3：首轮开始时仍掉线 → 从第 1 轮开始再过 30 秒才出局', ...)
  // 0 时掉线，45_000 进入第 1 轮；tick(74_999) 仍存活；tick(75_000) 出局并广播 playerOut
```

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C apps/server exec vitest run melee-p2` → Expected: FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过且引擎回归不变** — Run: `pnpm -C apps/server exec vitest run melee duel engine` → Expected: 全部 PASS（P1 的 `melee-presence` 中"摆放阶段掉线不暂停"一条照旧通过）
- [ ] **Step 5: Commit** — `git commit -m "fix(server): melee own-submitted in view, immediate playerOut, placing disconnect grace (M1-M3)"`

---

### Task 4: 电脑大脑（纯函数）

**Files:**
- Create: `apps/server/src/bot/brain.ts`, `apps/server/test/bot-brain.test.ts`

**Interfaces:**
- Consumes: `candidateHeads`, `cellsOfPlane`, `isPlacementValid`, `cellKey`, `GameView`, `RuleSet`, `TargetShot`, `BotDifficulty`
- Produces:
```ts
export const BOT_MISTAKE_RATE: Readonly<Record<BotDifficulty, number>>   // { beginner: 0.4, standard: 0.25, advanced: 0.1, expert: 0 }
export const PART_WEIGHT = 0.3
export type OpponentModel = { feasible: Cell[]; active: { planeId: string; candidates: Cell[] }[]; unlocated: number }
export function opponentModel(shotsOnTarget: readonly TargetShot[], planesDestroyed: number, rules: RuleSet): OpponentModel
export function scoreCells(view: GameView, rules: RuleSet): Map<string, number>   // 键 cellKey，只含未打过的格子
export function chooseShot(view: GameView, rules: RuleSet, difficulty: BotDifficulty, rng: () => number): Cell
```

**算法**：完全按 spec §20.3。要点：
- 目标集合 = `view.others` 中 `alive` 的对手（duel 即唯一对手）；`shotsOnTarget` = `view.you.shots.filter(s => s.targetId === t)`。
- 分组只看 `body` / `head` 的 `planeId`；`miss` 的 `planeId`（恒 `p0`）忽略。
- `cand(P)` 为空（理论上不会发生，防御）→ 该飞机按未定位处理。`feasible` 为空 → 该对手贡献 0。
- `chooseShot`：**第一次** `rng()` 决定是否失误（`< BOT_MISTAKE_RATE[difficulty]`）；失误 → 再用 `rng()` 从全部未打过格子中均匀选；否则取 `scoreCells` 最大值（差值 ≤ 1e-9 视为同分），同分用 `rng()` 均匀选。

- [ ] **Step 1: 写失败的测试**

辅助：`viewWith({ boardSize, planeCount, shots, others })` 构造只含必要字段的 `GameView`。

```ts
const R10: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }
it('角上一格是机身 → 唯一候选机头 (1,1)，高手必打', () => {
  const v = viewWith({ rules: R10, shots: [{ targetId: 'b', row: 0, col: 0, result: 'body', planeId: 'p0' }], others: ['b'] })
  expect(chooseShot(v, R10, 'expert', mulberry32(1))).toEqual({ row: 1, col: 1 })
})
it('未命中格排除候选：机身 (4,4) + 周围未命中只留一个候选', ...)
  // body (4,4)；miss (3,3)(3,4)(3,5)(4,3)(5,3)：其余 7 个候选或已被打过、或 9 格含未命中格，cand 只剩 (5,5)；expert 选 (5,5)
it('从不选已打过的格子、总在棋盘内（随机 200 个局面）', ...)
it('空棋盘：中心格的分数高于角格（找机身倾向中心）', () => {
  const s = scoreCells(viewWith({ rules: R10, shots: [], others: ['b'] }), R10)
  expect(s.get('5,5')!).toBeGreaterThan(s.get('0,0')!)
})
it('混战求和：同时是 b、c 候选机头的格子优先于只是 b 的唯一候选', ...)
it('混战只算存活对手：已出局对手身上的线索不影响打分', ...)
it('多机：两架活跃飞机分别推理，不把两架的机身命中求交集', ...)
it('已击落飞机的 9 格不再作为别的飞机的可能位置', ...)
it('失误率：入门在 2000 次决策中偏离最优的比例 ∈ [0.33, 0.47]；高手为 0', ...)
  // 局面：唯一最优格已知（上面"角上"局面），统计 chooseShot(…, mulberry32(i)) !== (1,1) 的比例
  // 注意均匀随机也可能恰好选中 (1,1)，期望偏离率 = 0.4 × (1 − 1/99) ≈ 0.396
it('确定性：同一种子同一结果', ...)
it('性能：16×16、6 架、3 个对手、每人 60 炮，单次 chooseShot < 20ms', ...)
```

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C apps/server exec vitest run bot-brain` → Expected: FAIL（模块不存在）
- [ ] **Step 3: 实现 `brain.ts`**（不引入任何 server 模块；只依赖 `@plane-duel/shared`）
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C apps/server exec vitest run bot-brain` → Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(server): bot brain scoring cells with candidateHeads and mistake rates"`

---

### Task 5: 电脑驱动器（何时出手）

**Files:**
- Create: `apps/server/src/bot/driver.ts`, `apps/server/test/bot-driver.test.ts`

**Interfaces:**
- Consumes: `chooseShot`, `autoPlace`, `GameView`, `RuleSet`, `ClientMessage`
- Produces:
```ts
export const BOT_THINK_MS: readonly [number, number]      // [1200, 3500]
export const BOT_DEADLINE_MARGIN_MS = 1000
export interface BotBrainLike { poll(view: GameView, rules: RuleSet, now: number): ClientMessage | null }
export class BotDriver implements BotBrainLike {
  constructor(readonly playerId: string, readonly difficulty: BotDifficulty, rng: () => number)
  poll(view: GameView, rules: RuleSet, now: number): ClientMessage | null
}
```

**行为：**
- 决策点键：`placing` 且 `you.planes.length === 0` → `place`；duel `playing` 且 `turn === playerId` → `turn:<you.shots.length>`；melee `playing` 且 `you.alive` 且 `!you.submitted` → `round:<round>`；其余（`paused`、`finished`、出局、非己回合、已提交）→ 无决策点，返回 `null` 并清除计划。
- 遇到新键：`actAt = now + think`，`think` 在 `BOT_THINK_MS` 内均匀取；若 `deadlineAt !== null`，`actAt = min(actAt, deadlineAt − BOT_DEADLINE_MARGIN_MS)`，且不早于 `now`。
- `now >= actAt` 且键未变 → 返回动作（`placePlane: autoPlace(...)` 或 `fire: chooseShot(...)`），并把该键标记为已完成（同一键不再出手，即使引擎拒绝——duel 由引擎超时代打兜底）。
- 键变化（例如 duel 暂停后恢复、deadline 改变）→ 重新计划。

- [ ] **Step 1: 写失败的测试**

```ts
it('摆放：思考时间内不出手，到点出 placePlane 且合法', ...)
it('duel：非己回合返回 null；轮到自己后在 [1200, 3500] ms 内出 fire', ...)
it('duel：paused 期间不出手；恢复后重新计时', ...)
it('melee：已提交（you.submitted）后本轮不再出手；新一轮再出手一次', ...)
it('melee：出局（you.alive=false）后永不出手', ...)
it('finished 后永不出手', ...)
it('截止保护：deadline 只剩 1500 ms 时，最晚在 deadline − 1000 出手', ...)
it('同一键只出手一次（连续 poll 不重复返回动作）', ...)
```

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C apps/server exec vitest run bot-driver` → Expected: FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C apps/server exec vitest run bot-` → Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(server): bot driver with think time and deadline margin"`

---

### Task 6: Table 的电脑座位与练习桌

**Files:**
- Modify: `apps/server/src/table.ts`
- Create: `apps/server/test/table-bots.test.ts`
- Modify: `apps/server/test/table.test.ts`（仅适配 `SeatView.bot`、`TableView.rulesVersion/listed`、`lastResult.botIds` 的新字段）

**Interfaces:**
- Consumes: `BotDriver`、`BotBrainLike`、`BOT_ID_PREFIX`
- Produces:
```ts
export type TableOptions = { /* P1 字段 */ kind: TableKind; botFactory?: (playerId: string, d: BotDifficulty, rng: () => number) => BotBrainLike }
class Table {
  addBot(difficulty: BotDifficulty, now: number): Outbound[]   // 等候中且有空座；否则 [] 
  get humanMembers(): string[]
  get hasHumans(): boolean
}
```

**行为：**
- 电脑座位：`playerId = \`bot:${roomCode}:${seat}:${n}\``（n 为本桌递增序号），昵称 `电脑${seat + 1}`，`ready = true`、`connected = true`；`startGame` 清空准备后电脑立即恢复 `ready = true`。
- `addBot` 与 `join` 共用开局判定：`match` / `practice` 且首局且人满 → 开局。
- `tick`：引擎存在时，先 `engine.tick`，再依座位顺序对每个电脑 `poll(engine.view(botId), rules, now)`，有动作则 `engine.handle(botId, msg, now)`；每次调用后 `afterEngine`，引擎结束即停止本轮轮询。
- **出站过滤**：`Table` 返回的 `Outbound` 中 `to` 为电脑的一律丢弃。
- `practice`：没有房主（`hostId = null`）；`updateRules` → `NOT_HOST`；其余同 `match`（首局自动开，之后全体真人准备才开）。
- **无真人即关桌**：等候中释放座位后、对局中 `leaveInGame` 后、`afterEngine` 释放离开者后，若 `hasHumans === false` → `close(false)`（丢弃引擎，不广播）。
- 座位保留时长：`humanMembers.length === 1` 且掉线者是该真人 → `FRIEND_SEAT_GRACE_MS`，否则 `MATCH_SEAT_GRACE_MS`（R2 改为只数真人）。
- `lastResult = { ...engine.result, botIds }`，`botIds` 为开局时的电脑 playerId。

- [ ] **Step 1: 写失败的测试**（引擎用 P1 的 `FakeEngine`；电脑用记录调用的 `FakeBot`）

```ts
it('练习桌：真人入座 + addBot 补满 → 自动开局；电脑座位 bot=true、ready=true', ...)
it('开局清空准备后电脑仍为已准备；再来一局只等真人准备', ...)
it('tick 时把 engine.view(电脑自己) 交给电脑，并把其动作转交引擎', ...)
  // FakeBot 记录收到的 view；断言其与 engine.view(botId) 深相等，且 FakeEngine.handle 收到 (botId, msg)
it('发给电脑的 Outbound 被丢弃', ...)
it('练习桌：真人离开 → isClosed；对局中真人离开 → isClosed 且引擎被丢弃', ...)
it('匹配桌 2 真人 + 2 电脑：一名真人对局中离开 → 本局结束后关桌（P1 规则不变）', ...)
it('座位保留只数真人：练习桌真人掉线保留 5 分钟', ...)
it('lastResult.botIds 列出本局电脑', ...)
it('addBot：对局中或满座 → 返回 []，座位不变', ...)
```

（好友房不能加电脑：Hub 从不对 friend 桌调用 `addBot`，由 Task 11 的路由保证，这里不测。）

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C apps/server exec vitest run table-bots` → Expected: FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C apps/server exec vitest run table engine` → Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(server): bot seats and practice tables driven from Table.tick"`

---

### Task 7: Table 的规则版本（M4）与踢人

**Files:**
- Modify: `apps/server/src/table.ts`
- Create: `apps/server/test/table-kick.test.ts`

**Interfaces:**
- Produces:
```ts
class Table {
  get rulesVersion(): number
  setReady(playerId: string, ready: boolean, rulesVersion: number, now: number): Outbound[]   // 签名改
  kick(hostId: string, targetId: string, now: number): Outbound[]
  canJoin(playerId: string): ErrorCode | null     // ROOM_NOT_FOUND（已关 / practice）/ BANNED / ROOM_IN_GAME / ROOM_FULL / null
}
```

**行为：**
- `rulesVersion` 初值 0，每次成功 `updateRules` +1；`setReady` 的 `rulesVersion` 不等于当前值 → 回 `STALE_RULES` 给本人，外加一条本人的 `tableState`，准备状态不变。
- `kick`：按 spec §20.8 的错误码表依次判定（不在桌 → `NOT_IN_ROOM`；非 friend 或非房主 → `NOT_HOST`；对局中 → `ROOM_IN_GAME`；目标不在 / 是自己 / 是电脑 → `TARGET_NOT_FOUND`；目标已准备 → `TARGET_READY`）。成功：先产出 `{ to: target, msg: { type: 'kicked', roomCode } }`，再释放座位（同 `release`，可能触发房主转移 / 关桌），把 target 加入 `banned`，向其余人广播 `tableState`。
- `join` 改为先调用 `canJoin`。

- [ ] **Step 1: 写失败的测试**

```ts
it('M4：房主改规则后，带旧 rulesVersion 的准备 → STALE_RULES，准备不生效，回发 tableState', ...)
it('M4：带当前 rulesVersion 的准备正常生效', ...)
it('房主踢未准备者：被踢者收到 kicked，其余人 tableState 中座位空出', ...)
it('Review Focus #3：目标已准备 → TARGET_READY，座位不变', ...)
it('Review Focus #3：最后一人准备同步开局后再踢 → ROOM_IN_GAME', ...)
it('Review Focus #3：被踢者再 join → BANNED；canJoin 返回 BANNED', ...)
it('可以踢掉线中的未准备者', ...)
it('非房主 / 匹配房 / 练习房 踢人 → NOT_HOST', ...)
it('踢自己 / 踢不在桌的人 / 踢电脑 → TARGET_NOT_FOUND', ...)
it('kicked 只发给被踢者，且排在释放之后的 tableState 不发给被踢者', ...)
```

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C apps/server exec vitest run table-kick` → Expected: FAIL
- [ ] **Step 3: 实现**（`table.test.ts` 中 `setReady` 调用补上版本参数）
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C apps/server exec vitest run table` → Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(server): rules version on ready and host kick with per-table ban"`

---

### Task 8: Table 的公开列表投影

**Files:**
- Modify: `apps/server/src/table.ts`
- Create: `apps/server/test/table-listing.test.ts`

**Interfaces:**
- Produces:
```ts
export type TableOptions = { /* … */ tableId: string; listed?: boolean; createdAt?: number }   // listed 默认 false
class Table {
  readonly tableId: string
  get listed(): boolean
  setListed(playerId: string, listed: boolean): Outbound[]   // 非 friend 或非房主 → NOT_HOST；成功广播 tableState
  listing(): RoomListEntry | null
}
```

**行为：**`listing()` 只在 `kind === 'friend' && listed && phase === 'waiting' && !isClosed && 有空座` 时返回条目；`hostNickname` 取房主座位昵称；`seats` 只含 `{ seat, nickname }`；`createdAt` 取构造时的 `now`。

- [ ] **Step 1: 写失败的测试**

```ts
it('公开、等候中、有空座的好友房 → 条目字段正确', ...)
it('Review Focus #5：匹配房 / 练习房 / 未公开 / 对局中 / 满座 / 已关闭 → null', ...)
it('Review Focus #5：条目 JSON 不含 roomCode 与任何 playerId', () => {
  const json = JSON.stringify(t.listing())
  expect(json).not.toContain(t.roomCode)
  for (const id of t.members) expect(json).not.toContain(id)
})
it('房主转移后 hostNickname 随之改变', ...)
it('setListed：非房主 → NOT_HOST；房主关闭公开后 listing() 为 null，view().listed=false', ...)
```

- [ ] **Step 2: 运行确认失败** — Run: `pnpm -C apps/server exec vitest run table-listing` → Expected: FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过** — Run: `pnpm -C apps/server exec vitest run table` → Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(server): public listing projection for friend tables"`

---

### Task 9: Table + 真实引擎 + 真实电脑的集成（隐私不变量）

**Files:**
- Create: `apps/server/test/table-bots-integration.test.ts`

**Interfaces:**
- Consumes: `Table`（默认 `createEngine`、默认 `BotDriver`）

本任务不新增产品代码，只验证接缝；发现的缺陷在本任务内修复。所有测试用 `mulberry32` 种子与假时间（每次 `tick` 前进 200 ms），真人一方由测试脚本扮演（每轮打一个自己没打过的格子）。

- [ ] **Step 1: 写测试**

```ts
it('练习 2 人（高手电脑）：在 2000 次 tick 内打完，回到 waiting，lastResult.botIds 为电脑', ...)
it('练习 4 人混战（1 真人 + 3 入门电脑）：在 3000 次 tick 内打完，ranking 长度 4 且至少一个 rank 1', ...)
it('Review Focus #1：交给每个电脑的视图恒等于 engine.view(该电脑)', ...)
  // botFactory 包一层真实 BotDriver：记录每次 poll 的 view，与同一时刻 table.engine!.view(botId) 深相等；
  // 并断言 view.others 不含该电脑自己、view.you.planes 是该电脑的飞机
it('Review Focus #1：真人收到的消息里没有任何电脑之间的结果', ...)
  // 收集 to === 真人 的全部 Outbound：任何含 result 字段的对象只能出现在
  //   roundResult.shots（且该格是真人本轮打的格）或 roundResult.incoming（且 resolveShot(真人飞机, 该格) 与 result 一致）
  //   或 state.game.you.shots / you.incoming 中；state.game.others 不含 row/col
it('Review Focus #2：duel 练习中真人掉线 → 暂停期间电脑不出手；30 秒后真人判负', ...)
it('Review Focus #2：混战练习中真人离开 → 立即关桌，之后 tick 不再产出任何消息', ...)
it('电脑不会触发 duel 超时代打（电脑的每一炮都在截止前 ≥ 800 ms 发生）', ...)
```

- [ ] **Step 2: 运行**；失败则按 systematic-debugging 修复产品代码。
- [ ] **Step 3: 变异验证**：临时把 `Table` 轮询改为 `engine.view(第一个真人的 id)`，第三条必须变红；恢复后 `git diff --stat` 只剩测试文件。
- [ ] **Step 4: 运行已迁移的服务端测试** — Run: `pnpm -C apps/server exec vitest run engine table duel melee bot-` → Expected: 全部 PASS
- [ ] **Step 5: Commit** — `git commit -m "test(server): table with real engines and bots, privacy invariant"`

---

### Task 10: 匹配补位

**Files:**
- Modify: `apps/server/src/matchmaking.ts`, `apps/server/test/matchmaking.test.ts`

**Interfaces:**
- Produces:
```ts
export const BOT_FILL_AFTER_MS = { 2: 30_000, 3: 30_000, 4: 45_000 } as const
export const MIN_HUMANS = 2
export type MatchGroup = { key: QueueKey; playerIds: string[]; botSeats: number }   // 凑满时 botSeats = 0
export type MatchmakingOptions = { enqueueWaitMs?: number; botFillMs?: number | null }   // 默认 null（关闭）
class Matchmaking {
  tick(now: number): { out: Outbound[]; groups: MatchGroup[] }   // 签名改
}
```

**行为：**
- `queueStatus` 同时携带 `botFillAt: number | null` 与 `humansNeeded: number`（`max(0, MIN_HUMANS − 当前真人数)`）；入队、离队、成组后都向剩余者重发。
- `botFillAt` = 补位开启且 `entries.length >= MIN_HUMANS` 时，`entries[MIN_HUMANS − 1].since + botFillMs(capacity)`；否则 `null`。
- `tick`：补位开启且 `entries.length >= MIN_HUMANS` 且 `now − entries[MIN_HUMANS − 1].since >= botFillMs(capacity)` → 该队列**全部**条目成组（`botSeats = capacity − n`），移出队列，不再给他们发队列消息。
- 未达 `MIN_HUMANS` 时**永不**补位，也不发 `queueTimeout`（界面已用"等待真人"表达），队列可以无限等。
- `queueTimeout` 只在补位关闭时发。

- [ ] **Step 1: 写失败的测试**（P1 的 6 条保留，`tick` 的返回值改为解构 `out`）

```ts
it('补位关闭（默认）：行为与 P1 相同，botFillAt 为 null', ...)
it('只有 1 人：botFillAt 为 null，humansNeeded = 1，等多久都不补位', ...)
it('补位开启：第 2 人入队后 botFillAt = 第 2 人的入队时刻 + 30000', ...)
it('第 2 人离队后 botFillAt 回到 null（只剩 1 人不补位）', ...)
it('29 999 ms 不成组；30 000 ms 时 3 名真人成组，botSeats = 1（4 人队列）', ...)
it('4 人队列倒计时为 45 秒', ...)
it('第 3、4 人入队不重置倒计时（以第 2 人的入队时刻为准）', ...)
it('人够（4 名真人）时立即成组，botSeats = 0', ...)
it('Review Focus #4：同一 tick 之前已离队的人不在成组里；队列空则不成组', ...)
it('成组者从 queueOf 中移除，且不再收到 queueStatus / queueTimeout', ...)
it('补位开启时不发 queueTimeout', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN** — Run: `pnpm -C apps/server exec vitest run matchmaking`
- [ ] **Step 5: Commit** — `git commit -m "feat(server): matchmaking bot fill after 30s with visible countdown"`

---

### Task 11: Hub：练习、补位、踢人、列表加入、按桌成员集合

**Files:**
- Modify: `apps/server/src/hub.ts`, `apps/server/test/hub-helpers.ts`（`mkHub` 默认 `botFillMs: null`；`createRoom` 辅助带 `listed: false`；测试里所有 `setReady` 带上 `tableOf(sid).rulesVersion`）
- Create: `apps/server/test/hub-p2.test.ts`
- Modify: 已有 `hub-e2e.test.ts`、`hub-lifecycle.test.ts`、`auth.test.ts` **只做协议 v3 字段适配**（`listed`、`rulesVersion`），场景与断言不变

**Interfaces:**
- Produces: `HubOptions.botFillMs?: number | null`（默认 `BOT_FILL_AFTER_MS`）；`HubOptions.makeTableId?: () => string`（默认 `randomUUID().replace(/-/g,'').slice(0,16)`）
- Consumes: `Table.addBot / kick / canJoin / setListed / humanMembers / tableId`、`Matchmaking.tick` 新签名

**路由：**
- `createPractice {capacity, preset}`：`leaveCurrent`（对局中 → `ALREADY_IN_ROOM`）→ 建 `practice` 桌（`rules = PRESETS[preset]`）→ 真人 `join` → `capacity − 1` 次 `addBot(preset)`。
- `createRoom {…, listed}`：建 `friend` 桌时传 `listed`。
- `setListed`：转给所在桌；不在桌 → `NOT_IN_ROOM`。
- `kick {playerId}`：转给所在桌；派发后被踢者归属解除（`sync`）。
- `joinListed {tableId}`：按 `tableId` 查桌；桌不存在 / `listing() === null` 且原因不是满座或对局中 → `ROOM_NOT_FOUND`；否则 `canJoin` 的错误照回；**全部检查通过后**才 `leaveCurrent` 并入座（与 P1 的 `joinRoom` 相同顺序）。
- `joinRoom`：预检改用 `target.canJoin(playerId)`（练习桌 → `ROOM_NOT_FOUND`、被踢 → `BANNED`）。
- `setReady`：把 `msg.rulesVersion` 传给 `table.setReady`。
- `tick`：`matchmaking.tick` 返回的每个成组：建 `match` 桌 → 按顺序真人 `join`（只登记仍然在线、且不在任何桌上的真人；被跳过的位置改由电脑补）→ `botSeats` 次 `addBot(preset)`；若最终没有任何真人入座 → 关桌并丢弃。
- **M5**：Hub 维护 `membersByTable: Map<roomCode, Set<playerId>>`（只含真人）；`sync(table)` 只遍历该集合，不再遍历全部玩家。
- 电脑 id 永远不进 `tableByPlayer`，`deliver` 找不到会话即丢弃（`Table` 已过滤，这是第二道保险）。

- [ ] **Step 1: 写失败的测试**

```ts
it('createPractice {4, beginner}：真人入座、3 个电脑、立即进入 placing；tableState 中 kind=practice、3 个 bot 座位', ...)
it('练习桌不能用房间号加入 → ROOM_NOT_FOUND', ...)
it('补位：两人排 {4, standard}，45 秒后进入 match 桌，空座 bot=true，规则为 PRESETS.standard', ...)
it('单人排 {4, standard} 等 120 秒也不建桌（不足 MIN_HUMANS）', ...)
it('Review Focus #4：排队时用房间号加入好友房 → 出队，30 秒后不被补位进第二张桌', ...)
it('Review Focus #4：补位成组时某真人已断线 → 只登记在线者，空位由电脑补；全部断线 → 不建桌', ...)
it('Review Focus #3：房主踢人 → 被踢者收到 kicked；之后该桌的 tableState 不再投给被踢者', ...)
it('Review Focus #3：被踢者用房间号再加入 → BANNED，且不会离开自己当前所在的桌', ...)
it('joinListed：按 tableId 加入成功；未公开 → ROOM_NOT_FOUND；满座 → ROOM_FULL', ...)
it('Review Focus #5：joinListed 失败时玩家仍坐在原桌（座位与 tableByPlayer 不变）', ...)
it('M4：setReady 带旧 rulesVersion → STALE_RULES', ...)
it('P0 回归：auth playerId=bot:… → BAD_SHAPE；冒充 / 顶号 / 旧消息过滤测试原样通过', ...)
it('M5：一张桌的成员变化只解除该桌成员的归属（其它桌的玩家不受影响）', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN** — Run: `pnpm -C apps/server exec vitest run hub auth matchmaking table` → Expected: 全部 PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(server): hub routes practice, bot fill, kick and listed joins"`

---

### Task 12: Hub：公开列表订阅与推送

**Files:**
- Modify: `apps/server/src/hub.ts`, `apps/server/src/main.ts`
- Create: `apps/server/test/hub-room-list.test.ts`

**Interfaces:**
- Produces:
```ts
export const ROOM_LIST_MAX = 50
export const ROOM_LIST_MIN_INTERVAL_MS = 1000
// main.ts
export type ServerOptions = { /* … */ botFillMs?: number | null }
export type ServerHandle = { close(): Promise<void>; port: number; tick(): void }   // tick 供测试推进时间
```

**行为：**
- `roomListSubscribe {capacity}`：记录订阅（覆盖旧订阅），**立即**发送该专区快照并记下 `lastSentJson[capacity]`、`lastSentAt[capacity]`。
- 快照：所有 `capacity` 相同的桌子的 `listing()` 非空者，按 `seated` 降序、`createdAt` 降序，截取前 50。
- 变化检测：任何 `kind === 'friend'` 桌子的派发、建桌、关桌 → 标记该专区 dirty。`tick` 中对 dirty 且有订阅者、且距上次推送 ≥ 1000 ms 的专区重算；JSON 与上次不同才推送给该专区全部订阅者；不足 1000 ms 的保持 dirty 到下一次 `tick`。
- 自动退订：`createRoom`、`joinRoom`、`joinListed`、`createPractice`、`queueJoin` 成功后，以及 `disconnect`；`roomListUnsubscribe` 显式退订（未订阅时静默）。
- 未认证不能订阅（`NOT_AUTHED`，已有逻辑）。

- [ ] **Step 1: 写失败的测试**

```ts
it('订阅立即收到快照；只含本专区', ...)
it('Review Focus #5：快照不含匹配房 / 练习房 / 未公开 / 对局中 / 满座的桌子', ...)
it('有人入座 → 1 秒内收到新快照；同一秒内多次变化合并为一次推送', ...)
it('内容未变（例如对局中的桌子在打）不推送', ...)
it('排序：在座多者在前，同数新建者在前；最多 50 条', ...)
it('加入任何桌 / 开始排队 / 断线 → 自动退订，不再收到 roomList', ...)
it('Review Focus #5：被屏蔽昵称的房主 → 条目 hostNickname 为回退值', ...)
it('roomListUnsubscribe 后不再收到推送', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN**；`pnpm -C apps/server exec tsc --noEmit` 必须通过（Task 1 遗留的服务端类型错误到此全部消除）
- [ ] **Step 5: 运行服务端全量** — Run: `pnpm -C apps/server test` → Expected: 全部 PASS（含 P1 的 `hub-*`、`auth`、`*.e2e`，后两者仅做 v3 字段适配）
- [ ] **Step 6: Commit** — `git commit -m "feat(server): pushed public room list per zone with coalescing"`

---

### Task 13: 客户端状态仓库 v3 与大厅模型

**Files:**
- Modify: `apps/client/src/net/store.ts`, `apps/client/test/store.test.ts`
- Create: `apps/client/src/lobby-model.ts`, `apps/client/test/lobby-model.test.ts`

**Interfaces:**
- Produces:
```ts
// store
export type GameState = { /* P1 字段 */
  queue: { capacity: Capacity; preset: PresetId; waiting: number; botFillAt: number | null; humansNeeded: number } | null
  roomList: { capacity: Capacity; entries: RoomListEntry[] } | null
  kicked: boolean
}
// lobby-model.ts
export function roomListRows(entries: readonly RoomListEntry[]): { tableId: string; title: string; summary: string; seatsText: string; full: boolean }[]
  // title = `${hostNickname} 的房间`；summary = ruleSummary(rules)；seatsText = `${seated}/${capacity}`
/** 未达 MIN_HUMANS 时返回"等待真人 1/2"；否则返回倒计时文案；补位关闭时 null */
export function botFillText(q: { waiting: number; humansNeeded: number; botFillAt: number | null }, now: number): string | null
  // null → null；剩余 > 0 → `${秒数} 秒后由电脑补位（对局会标注 🤖）`；≤ 0 → '正在由电脑补位…'
export function seatLabel(seat: SeatView): string       // bot → `🤖 ${nickname}`；否则 nickname
export function hasBots(table: TableView): boolean
```

**store 行为：**`roomList` 写入 `state.roomList`；`kicked` → `resetToLobby()` 后置 `kicked = true`、`error = '你已被房主移出房间'`；`playerOut` → 对应 `others[i].alive = false, submitted = false`；`roundResult.eliminated` 照旧（幂等）；`state` 整体替换时 `game.you.submitted` 来自服务端；新错误码文案：`TARGET_NOT_FOUND: '该玩家不在房间中'`、`TARGET_READY: '对方已准备，不能移出'`、`BANNED: '你已被移出该房间，不能再加入'`、`STALE_RULES: '房主刚修改了规则，请确认后再准备'`；`BAD_RULES` 文案已存在。

- [ ] **Step 1: 写失败的测试**

```ts
it('roomList 写入 state.roomList', ...)
it('kicked：回到大厅（table/game 为 null）并给出提示', ...)
it('M2：playerOut 把对应对手标为出局且清除已开炮标记；随后的 roundResult.eliminated 不重复出错', ...)
it('M1：state 中 you.submitted=true 时 game.you.submitted 为 true（不依赖本地标记）', ...)
it('queueStatus 带 botFillAt 写入 queue', ...)
it('新错误码有中文文案', ...)
it('roomListRows：标题、摘要、座位数、满座标记', ...)
it('botFillText：30 秒倒计时取整、过点、null', ...)
it('seatLabel / hasBots', ...)
```

- [ ] **Step 2–4: RED → 实现 → GREEN** — Run: `pnpm -C apps/client exec vitest run store lobby-model`
- [ ] **Step 5: Commit** — `git commit -m "feat(client): store v3 and lobby model for room list, bots and kick"`

---

### Task 14: 客户端：专区页（人机练习、公开列表、补位倒计时）

**Files:**
- Modify: `apps/client/src/views/Zone.vue`, `apps/client/src/components/RuleEditor.vue`（"公开到房间列表"开关，默认开）
- Create: `apps/client/src/components/RoomList.vue`
- Modify: `apps/client/src/rule-editor-model.ts`, `apps/client/test/rule-editor-model.test.ts`

**Interfaces:**
- Produces（`rule-editor-model.ts`）：
```ts
export function defaultCreateRoom(capacity: Capacity): { type: 'createRoom'; capacity: Capacity; rules: RuleSet; listed: boolean }
  // rules = PRESETS.standard，listed = true（spec §20.6：默认公开）
export function practiceRequest(capacity: Capacity, preset: PresetId): { type: 'createPractice'; capacity: Capacity; preset: PresetId }
```

**界面：**
- Zone 顶部保留"快速匹配"四档；排队中显示"排队中 n/人数"与 `botFillText` 倒计时（每秒刷新）。
- 新增"人机练习"区：四档按钮，标注"练习 · 不计段位"，点击发 `createPractice { capacity, preset }`。
- 新增"公开房间"区（`RoomList.vue`）：进入 Zone 时 `roomListSubscribe { capacity }`，离开（`onUnmounted`）时 `roomListUnsubscribe`；列表行 = `roomListRows`；点击 → `joinListed { tableId }`；空列表文案"暂时没有公开的房间，创建一个吧"。
- 创建好友房：`createRoom` 带 `listed`（RuleEditor 开关值）。

- [ ] **Step 1: 写失败的测试**（`rule-editor-model.test.ts`）

```ts
it('defaultCreateRoom：标准档、默认公开', () => expect(defaultCreateRoom(3)).toEqual({ type: 'createRoom', capacity: 3, rules: PRESETS.standard, listed: true }))
it('practiceRequest', () => expect(practiceRequest(4, 'beginner')).toEqual({ type: 'createPractice', capacity: 4, preset: 'beginner' }))
```

- [ ] **Step 2: 实现模型与视图**；Run: `pnpm -C apps/client exec vitest run rule-editor-model` → Expected: PASS；`pnpm -C apps/client exec vitest run` 全绿
- [ ] **Step 3: 浏览器验证**（preview）：3 人专区 → 列表为空 → 用脚本 WebSocket 建一张公开 3 人房 → 列表 1 秒内出现该房（房主昵称、1/3、规则摘要）→ 点击加入 → 进入等候室；回到专区 → 点"人机练习 · 入门" → 直接进入摆放，座位显示 🤖。截图：专区页（含列表与练习区）、排队倒计时。
- [ ] **Step 4: Commit** — `git commit -m "feat(client): zone page with practice, public room list and bot-fill countdown"`

---

### Task 15: 客户端：等候室、对局、结算页的电脑与踢人

**Files:**
- Modify: `apps/client/src/views/WaitingRoom.vue`, `apps/client/src/components/SeatList.vue`, `apps/client/src/views/MeleePlay.vue`, `apps/client/src/views/DuelPlay.vue`, `apps/client/src/components/ResultSheet.vue`, `apps/client/src/App.vue`
- Modify: `apps/client/src/lobby-model.ts`, `apps/client/test/lobby-model.test.ts`, `apps/client/src/route.ts`, `apps/client/test/route.test.ts`

**Interfaces:**
- Produces:
```ts
// lobby-model.ts
export function peerStatus(o: { alive: boolean; submitted: boolean; connected: boolean }): '出局' | '✓' | '思考中' | '掉线'
export function canKick(table: TableView, me: string, seat: SeatView): boolean   // 好友房 && 我是房主 && waiting && 非自己 && !bot && !ready
// route.ts：GameState.kicked 为 true 时 routeView 返回 'lobby'（table 已为 null，本条锁定该行为）
```

**界面：**
- SeatList：座位名用 `seatLabel`；`canKick` 为真的座位显示"移出"按钮 → 确认后发 `kick { playerId }`。
- WaitingRoom：房主可见"公开到房间列表"开关（发 `setListed`）；`hasBots(table)` 时顶部显示"本桌有电脑 🤖"；练习桌标题显示"人机练习 · 不计段位"并隐藏房间号与分享；"准备"发 `setReady { ready, rulesVersion: table.rulesVersion }`。
- MeleePlay：删除本地 `submitted` ref，改用 `game.you.submitted`（M1）；对手状态用 `peerStatus`（M2）；电脑对手标签带 🤖。
- DuelPlay：对手名用 `seatLabel`；有电脑时顶部"本局有电脑补位"（match）或"人机练习"（practice）。
- ResultSheet：排名行中 `lastResult.botIds` 内的玩家带 🤖；有电脑时底部注明"本局有电脑参与，不计段位"。
- App：`state.kicked` → 回大厅并 toast `state.error`。

- [ ] **Step 1: 写失败的测试**

```ts
// lobby-model.test.ts
it('M2：peerStatus 出局优先于其它状态', () => expect(peerStatus({ alive: false, submitted: true, connected: true })).toBe('出局'))
it('peerStatus：✓ / 思考中 / 掉线', ...)
it('canKick：只对好友房房主、等候中、非自己、非电脑、未准备的座位为真', ...)
// route.test.ts
it('被踢后（table=null）回到大厅', ...)
```

- [ ] **Step 2: 实现模型与视图**；Run: `pnpm -C apps/client exec vitest run lobby-model route` → Expected: PASS；`pnpm -C apps/client exec vue-tsc --noEmit` 通过（Task 1 遗留的客户端类型错误到此全部消除）；`pnpm -C apps/client exec vitest run` 全绿
- [ ] **Step 3: 浏览器验证**：
  - 4 人练习（入门）打满一局：对手标签 🤖、开炮后刷新页面仍显示"已开炮，等待其他人"（M1）、结算页 🤖 与"不计段位"；
  - 好友房：本页为房主 + 2 个脚本玩家（一个准备、一个未准备）→ 只有未准备者有"移出"→ 移出后脚本收到 `kicked`、再用房间号加入收到 `BANNED`；
  - 混战中脚本玩家离开 → 本页立刻显示其"出局"（M2）；
  - 375×812 视口截图：等候室（含 🤖 与移出按钮）、结算页；控制台无 warn/error。
- [ ] **Step 4: Commit** — `git commit -m "feat(client): bot badges, host kick, listed toggle and server-side submitted"`

---

### Task 16: 端到端与全量验证

**Files:**
- Create: `apps/server/test/p2.e2e.test.ts`

- [ ] **Step 1: 写测试**——真实 WebSocket，`createServer({ port: 0, devMode: false, clock: 假时钟, botFillMs: 30_000 })`，用 `srv.tick()` 推进：
  - **练习混战**：1 个真人客户端 `createPractice {4, standard}` → 摆放 → 每轮打一个自己没打过的格子 → 直到 `gameOver`。断言：`ranking` 长度 4；结束后 `tableState.table.phase === 'waiting'` 且 `lastResult.botIds` 长度 3；**Review Focus #1 端到端**：真人收到的所有消息中，含 `result` 的对象只出现在其 `roundResult.shots`（本人本轮所打的格）/ `roundResult.incoming`（与其飞机一致）/ `state.game.you` 中。
  - **补位**：1 个客户端 `queueJoin {2, beginner}` → 收到 `queueStatus.botFillAt` → 推进 30 秒 → 收到 `tableState`（kind=match，对手 `bot: true`）→ 打完一局。
  - **列表 + 踢人**：A 建公开 3 人房；B `roomListSubscribe {3}` 收到含该房的快照（JSON 不含房间号）→ `joinListed` → A `kick` B → B 收到 `kicked` → B 用房间号与 `joinListed` 都得到 `BANNED`；C 订阅后看到 `seated: 1`。
  - **P0 安全回归**：`auth { playerId: 'bot:x' }` → `BAD_SHAPE`；被顶掉的旧连接收到关闭码 4000。
- [ ] **Step 2: 运行通过**；变异验证：临时把 `MeleeEngine` 的 `roundResult` 改为把全部射击结果发给所有人，练习混战用例必须变红；恢复后 `git diff` 只剩本测试文件。
- [ ] **Step 3: 全量测试与类型检查** — Run: `pnpm test && pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/client exec vue-tsc --noEmit` → Expected: 三包全绿、两项类型检查无输出
- [ ] **Step 4: H5 构建** — Run: `pnpm -C apps/client build` → Expected: 构建成功
- [ ] **Step 5: Commit** — `git commit -m "test(server): P2 end-to-end practice, bot fill, room list and kick"`

---

## 与 spec 的对应

| spec | 任务 |
|---|---|
| §19.1 P2：人机练习 | 4, 5, 6, 9, 11, 14, 15, 16 |
| §19.1 P2：电脑补位 | 10, 11, 14, 16 |
| §19.1 P2：公开房间列表 | 2（前置：屏蔽词）, 8, 11, 12, 13, 14, 16 |
| §19.1 P2：房主踢人 | 7, 11, 13, 15, 16 |
| §20.2 电脑的表示 | 1, 6, 11 |
| §20.3 决策与失误率 | 4, 5 |
| §20.4 人机练习 | 6, 9, 11, 14 |
| §20.5 补位与标注 | 6（botIds）, 10, 11, 15 |
| §20.6 公开列表与屏蔽词 | 2, 8, 12, 13, 14 |
| §20.7 M1 / M2 / M3 | 3, 13, 15 |
| §20.7 M4 | 1, 7, 11, 15 |
| §20.7 M5 | 1, 11 |
| §20.8 踢人 | 7, 11, 15 |
| §20.9 协议 v3 | 1 |
| §20.10 不变量（隐私、P0 安全） | 9, 11, 16 |

## 执行顺序与并行

```
1 ─┬─ 2 ───────────────────────────────────────────┐
   ├─ 3 ──────────────┐                            │
   ├─ 4 → 5 ──────────┴→ 6 → 7 → 8 → 9 ─┐          │
   ├─ 10 ───────────────────────────────┴→ 11 → 12 ┴─┐
   └─ 13 ───────────────────────────────────────────┴→ 14 → 15 → 16
```

- Task 2、3、4、10、13 只依赖 Task 1，可以并行。
- Task 6 需要 Task 3（视图里的 `you.submitted`）与 Task 5（驱动器）。
- Task 6 → 7 → 8 顺序修改 `table.ts`，同一实现者连续完成为宜。
- Task 11 依赖 Task 9（Table 全部就绪）与 Task 10（补位成组）；Task 12 依赖 Task 11 与 Task 2——公开列表在屏蔽词就位前不得合并（spec §19.8）。
- Task 14 依赖 Task 12（服务端可联调）与 Task 13（store 与模型）。
- Task 14–15 需要服务端 Task 12 才能在浏览器联调；Task 16 在全部完成后进行。

## 不在本计划范围（spec §20.1）

好友房由房主手动加电脑；观战；按规则筛选 / 搜索房间；举报与全局封禁；账号、段位、战绩、好友（P3）；金币、门票、道具（P4）；完整敏感词库、上架与 uni-app 迁移（P5）。
