# SDD ledger — plan: docs/superpowers/plans/2026-11-11-plane-duel-p0.md

Spec: docs/superpowers/specs/2026-11-11-plane-duel-design.md（已读）

## Setup rulings

Setup: Ruling: 不建 worktree，直接在 plane-duel/ 目录开发并 git init — 这是全新项目，无既存代码可隔离保护，worktree 无收益 — cost if wrong: 无（无他人协作分支）
Setup: Ruling: 使用 executing-plans（inline）而非 subagent-driven — spec 与 plan 全在上下文内，20 个任务共享同一套接口，每任务派新 agent 的交接损耗大于收益 — cost if wrong: 少一层 per-task 独立评审，由最终整分支评审兜底

## Pre-flight 接口冲突扫描

| 产出方 | 消费方 | 一个产出 / 另一个消费 | 结论 |
|---|---|---|---|
| Task 1 `RoomSnapshot.opponent` | Task 8 `snapshotFor` | 无 `planes` 字段 | 一致（已明确为硬约束） |
| Task 1 `RoomSnapshot.you.shots` | Task 16 store / Task 17 Play | `shots` 是我打出去的；另有 `incomingShots` | **已修正**：原稿只有 `shots`，Play 会在自己棋盘上误用。补 `incomingShots` |
| Task 1 `GameOverReason` | Task 9 gameOver 判定 | 只有 head/allPlanes/forfeit | 一致 |
| Task 7 `createServer(port, clock, devMode)` | Task 18 e2e | `port: 0` 需返回真实端口 | 一致（Task 7 Step 3 已写明） |
| Task 8 `Room` 构造签名 | Task 9/10/11/14 复用 | 含 `rng?` | 一致（Task 8 Step 4 前置说明） |
| Task 2 `checkPlacement` | Task 8 placePlane 校验 | 返回 PlacementCheck | 一致 |
| Task 13 `Hub` | Task 7 `main.ts` | Hub 在 Task 13 才出现，Task 7 只用裸 ws | 一致（Task 13 Step 5 接线） |
| Task 15 `buildBoardCells` | Task 17 Play | 签名含 `boardSize`/`showPlane` | 一致 |
| Task 5 `isAllPlanesDestroyed` | Task 9 | 参数 `(planes, destroyedIds)` | 一致 |

Pre-flight: 1 处需修正的共享接口（`incomingShots`），已在计划中就地修正。其余无冲突。

## Tasks

Task 1: complete (commits be1759f..c47905b, tests: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared exec vitest run` → tsc exit 0, 2/2 pass)
Task 2: complete (commits c47905b..30f451e, tests: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared exec vitest run` → tsc exit 0, 13/13 pass)
Task 2: Ruling: Task 2 实现里误把 Task 3/4/5 的函数（resolveShot/candidateHeads/isAllPlanesDestroyed/isRepeatShot/unshotCells）一并写出，导致 Task 3 测试一次通过 — 按 TDD 铁律删除这些函数，重跑确认 Task 3 的 6 个测试确实失败，再最小实现回补 — cost if wrong: 若删除时误伤 Task 2 依赖，Task 2 的 13 个测试会立刻红，可即时发现
Task 3: complete (commits 30f451e..1177a11, tests: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared exec vitest run` → tsc exit 0, 19/19 pass)
Task 4: Ruling: 计划的 H(c) 公式 `{ h | valid(h) && c ∈ cellsOfPlane(h) }` 漏了 `h ≠ c`，实现返回 9 个候选（含命中格自身）而非 8 个 — 按 spec §二「机头必然在该格的 8 邻域内」修正为排除命中格自身 — cost if wrong: 候选集多算 1 个，机器人/AI 会多打一炮无效格，P0 无 AI 因此只影响可选提示开关的准确性
Task 4: complete (commits 1177a11..5bedbde, tests: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared exec vitest run` → tsc exit 0, 24/24 pass)
Task 5: complete (commits 5bedbde..c20ff94, tests: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared exec vitest run` → tsc exit 0, 30/30 pass)
Task 6: complete (commits c20ff94..0fefc5c, tests: `pnpm -C packages/shared exec tsc --noEmit && pnpm -C packages/shared exec vitest run` → tsc exit 0, 46/46 pass)
Task 7: complete (commits 0fefc5c..4316904, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 3/3 pass)
Task 8: complete (commits 4316904..37c6595, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run room-placement` → tsc OK, 7/7 pass)
Task 9: Ruling: Task 8 的 Room 实现里已包含 handlePlaying/applyShot，导致 Task 9 测试一次通过 — 按 TDD 铁律临时剥离 handlePlaying 实现（保留签名与 leaveRoom 分支），确认 7 个测试变红，再从 /tmp 备份恢复 — cost if wrong: 剥离期间若误改其他分支会被 room-placement 的 7 个测试当场抓住
Task 9: complete (commits 37c6595..043b8da, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 18/18 pass)
Task 10: Ruling: tick 实现同样在 Task 8 已存在，Task 10 测试一次通过 — 剥离 tick 为 return []，确认 5 个测试变红（3 个空断言仍绿属预期），再恢复 — cost if wrong: 剥离可能连带断开 autoPlace/autoFire 引用，tsc 会报未使用符号，已通过 tsc 验证
Task 10: complete (commits 043b8da..5853610, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 26/26 pass)
Task 11: Ruling: 计划中两个「暂停期间不代打」测试用 `tick(1000+60000)` 与 `tick(120000)`，这两个时刻都已超过 30 秒宽限，实现判负是正确行为 — 改为宽限期内的时刻（26000 / 29000），使其刚好越过回合或摆放 deadline 但仍在宽限内，才真正验证「暂停抑制代打」而非「暂停后判负」 — cost if wrong: 若实现真的在暂停中代打，宽限期内的时刻同样会暴露
Task 11: complete (commits 5853610..850a85e, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 34/34 pass)
Task 12: complete (commits 850a85e..501709f, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 41/41 pass)
Task 13: Ruling: 计划的 createRoom 是先构造 Room 再登记，但 Room 构造签名要求两名玩家已确定，建房时第二人未知 — 改为 pendingRooms 表：建房只登记房主，加入时才真正 new Room — cost if wrong: 房主建房后若不刷新页面就换设备，pending 房间会残留（无 TTL），P0 可接受
Task 13: complete (commits 501709f..beff997, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 47/47 pass)
Task 14: Ruling: handleFinished 在 Task 8 已实现，Task 14 测试一次通过 — 剥离为仅处理 leaveRoom 的桩，确认 4 个测试变红，再恢复 — cost if wrong: 同前两次，恢复前 tsc 与全量测试都会验证
Task 14: complete (commits beff997..bb67fc9, tests: `pnpm -C apps/server exec tsc --noEmit && pnpm -C apps/server exec vitest run` → tsc OK, 54/54 pass)
Task 15: Ruling: 计划写的是 uni-app，但 uni-app 的 CLI 脚手架（@dcloudio/*）版本矩阵复杂、需要 HBuilderX 才能 App 打包，与 Vitest 集成也不顺 — 改用 Vite + Vue 3 实现 H5 客户端，组件只用标准 DOM/CSS，后续迁入 uni-app 时 BoardGrid 的 <div>/<button> 换 <view> 即可；board-model.ts 与 net 层不变 — cost if wrong: Task 19（App 打包）需要先做一次 uni-app 迁移，约半天工作量；这是本次最大的偏离，需向用户说明
Task 15: Ruling: 原配色 `--sea #1b3150` 与 `--grid-line #22364f` 对比度过低，格子融成一片 — 网格线改为更深的 `#0a1422`，海面提亮到 `#1f3a5f` — cost if wrong: 纯视觉，无功能影响
Task 15: Ruling: preview 工具读取会话根目录 ai-math/.claude/launch.json（属于用户其他项目），而非 plane-duel/.claude/ — 在该文件追加 plane-duel-client / plane-duel-server 两条配置，未改动原有 trace-repro — cost if wrong: 用户需要知道该共享文件被追加了两条
Task 15: complete (commits bb67fc9..327d0e0, tests: `pnpm -C apps/client exec vitest run && vue-tsc --noEmit` → 6/6 pass, vue-tsc OK; preview 截图验证点击 E5 后机头+8 格机身正确渲染)

Task 16: Ruling: 计划只给手测，但 store 归约是纯逻辑 — 补 test/store.test.ts（6 测试），锁住 shots/incomingShots 不混用、rematch 清盘、重连快照替换 — cost if wrong: 无，只多了测试
Task 16: Ruling: playerId 用 localStorage + crypto.randomUUID（因 Task 15 改为 Vite H5，无 uni.getStorageSync）— 迁 uni-app 时换存储 API 即可 — cost if wrong: 一处函数替换
Task 16: complete (tests: `pnpm -C apps/client exec vitest run && vue-tsc --noEmit` → 12/12 pass, vue-tsc OK)
Task 17: Ruling: 发现真 bug——Room 摆放 deadline 被设为常量 60000（相对 epoch），真实时钟下建房后首次 tick 即判摆放超时 — RoomOptions 加 now，Hub 传 clock.now()，rematch 用请求时刻；回归测试 2 个 RED→GREEN — cost if wrong: 无，属必修
Task 17: Ruling: 进入 playing 时客户端无法得知先手（phaseChanged 不带 turn，store 只从 shotResult 更新 turn）— phaseChanged 加可选 turn 字段（协议向后兼容），RED→GREEN — cost if wrong: 协议多一个可选字段
Task 17: Ruling: Node 原生 ESM 不解析无扩展名导入，server dev 改用 tsx；入口拆到 src/index.ts（main.ts 只导出 createServer，测试 import 不会起服务）；createServer 加 host 参数（部署用 0.0.0.0）— cost if wrong: 多一个 devDependency
Task 17: complete (tests: pnpm test → shared 46/46, server 57/57, client 12/12; tsc + vue-tsc OK; 浏览器实测：建房→对手 ws 加入→摆放→命中机身→击落→胜利/失败页→再来一局回到摆放，手机视口截图正常，控制台无 warn/error)
Task 18: Ruling: 计划中的探测先手（先让 alice 试打一炮）已不需要——phaseChanged 现在带 turn；搜索策略改为无命中时按 3 格步长扫描（保证扫到 3×3 机身），有命中时打 candidateHeads — cost if wrong: 无
Task 18: Ruling: 测试写在已有代码之后，无法自然 RED — 改用变异验证：临时把 resolveShot 的 head 改为 body，测试变红；恢复后 git diff 为空 — cost if wrong: 无
Task 18: complete (tests: pnpm test → shared 46, server 58, client 12 全绿)
Task 19: Ruling: 本机无 HBuilderX、无完整 Xcode，uni-app App 打包走不通 — 用 Capacitor 8 把 H5 包成 Android 原生壳；iOS 用同一工程，装 Xcode 后 `cap add ios` — cost if wrong: 将来上微信小游戏仍需迁 uni-app，Capacitor 壳那时可保留做 App 或弃用
Task 19: complete (APK 4.0MB 编译成功；装到华为 ADY-AL00 / Android 12 真机，启动后大厅正常、已连上局域网服务端。手机前台随后切到其他应用，停止注入点击，未完成手机端完整对局——对局逻辑由浏览器实测与 e2e 覆盖)
Task 20: Ruling: H5 部署时 WS 地址改为同源 /ws（Caddy 反代），开发时仍连 :8080 — cost if wrong: 无
Task 20: complete-unverified (Dockerfile/compose/Caddyfile 已写；Docker 守护进程未运行，`docker compose up` 未实际执行，镜像未构建验证)

## Final review
Final review: fresh reviewer (opus), 3 Critical / 6 Important / 7 Minor, verdict "Ready to merge: No"
Final: Ruling: M5 maxPayload 由 Minor 上调为 Important — 服务面向公众，ws 默认 100MB 单帧是内存型 DoS 入口 — cost if wrong: 无
Final: Ruling: I6 中途 leaveRoom（spec 未明确）判为认输 — spec 仅允许"超时/掉线判负"作为非击落结局，主动离开等同故意掉线；离开方对手胜 + roomClosed — cost if wrong: 若用户希望中途离开不计胜负，需改 leave() 一处
Final: Ruling: 待加入房间在房主掉线时保留 5 分钟而非立即删除 — 典型流程是房主切去微信发房间号，立即删除会让朋友加入失败 — cost if wrong: 无人加入的房间号最多占用 5 分钟
Final: fixed C1 — room-lifecycle "判掉线方负，而不是判掉线方胜" RED→GREEN
Final: fixed C2 — hub-lifecycle C2 ×5（冒充被拒/错 token/正确 token 重连并关旧 socket/旧 socket 断开无影响/同 socket 换身份）RED→GREEN
Final: fixed C3 — store "opponentLeft 只表示临时掉线" + room "掉线时在线方收到 phaseChanged paused" RED→GREEN；浏览器复验摆放中掉线不再回大厅
Final: fixed I1 — room-lifecycle I1 ×4 RED→GREEN
Final: fixed I2 — room "已在线时再 setConnected(true) 也补发快照" + hub 半开重连 RED→GREEN；心跳 15s
Final: fixed I3 — hub-lifecycle I3 ×7 RED→GREEN
Final: fixed I4 — hub-lifecycle I4 ×3 RED→GREEN
Final: fixed I5 — room "恢复时双方收到带顺延 deadline 与 turn 的 phaseChanged" + store ×2 RED→GREEN
Final: fixed I6 — room-lifecycle I6 ×3 RED→GREEN
Final: fixed M5 — auth "超过 4KB 的消息直接断开连接" RED→GREEN
Final: suite shared 46/46, server 86/86, client 17/17
Final: minor (deferred): M1 撤回再来一局请求未实现（重复发 rematchRequest 不会撤回）
Final: minor (deferred): M3 匹配房间号已改走 uniqueRoomCode，碰撞已消除（顺带修复，无单独测试）
Final: minor (deferred): M4 createRoom 静默忽略非默认 boardSize/planeCount（应回错误）
Final: minor (deferred): M6 部分错误码（OUT_OF_RANGE/WRONG_PHASE/NOT_IN_ROOM/BAD_*）客户端只显示"操作失败"
