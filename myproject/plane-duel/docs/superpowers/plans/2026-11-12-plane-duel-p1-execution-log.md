# SDD ledger — plan: docs/superpowers/plans/2026-11-12-plane-duel-p1.md

Spec: docs/superpowers/specs/2026-11-11-plane-duel-design.md（§十九 为准；已读）
Branch: p1-zones（从 master decce2a 切出；P0 在 master 上）
MERGE_BASE: decce2a

## Pre-flight scan

### 共享接口（任务对）

| 产出 → 消费 | 内容 | 结论 |
|---|---|---|
| T1 → T2 | maxPlanes | 一致 |
| T1 → T3 | RuleSet/Capacity/PresetId/validateRuleSet/isCapacity；types.ts 从 ruleset.ts 引入，ruleset 不引 types | 一致，无循环 |
| T2 → T4/T7/T8/T9/T13 | 测试辅助 mulberry32 位于 packages/shared/test/helpers.ts，服务端测试也要用 | **R1** |
| T3 → T4..T17 | ErrorCode：NOT_YOUR_TURN/REPEAT_SHOT/OUT_OF_RANGE/WRONG_PHASE/INVALID_PLACEMENT/PAUSED/NOT_HOST/ROOM_IN_GAME/ROOM_FULL/NOT_IN_ROOM/ALREADY_IN_ROOM/BAD_TOKEN 均已定义 | 一致 |
| T4 → T5 | EngineOptions、Engine（phase/result/handle/tick/setConnected/view） | 一致；T5 用 FakeEngine，T4 工厂尚未实现不影响 |
| T4 → T6/T7 | PlacingPhase、DISCONNECT_GRACE_MS | 一致 |
| T5 ↔ T6/T7 | 对局中 leaveRoom 由 Table 转给引擎；引擎负责判负/出局，Table 负责关桌/释放座位 | 一致 |
| T5 → T12 | Table.join(playerId,nickname,now)/stateFor/members/isClosed/setNickname | 一致 |
| T5 规则 vs P0 ruling | spec §19.4 等候室掉线保留 60 秒；P0 曾为"房主切去微信发房间号"保留待加入房间 5 分钟 | **R2** |
| T11 → T12 | Matchmaking 不再生成房间号、constructor 无 makeRoomCode | 一致（过渡期 hub 失效，计划已约定） |
| T12 vs P0 hub 测试 | T12 说"保留 P0 hub 测试所有场景"，但 pendingRooms 的 5 分钟 TTL / 房主离线时朋友加入→暂停 在 Table 模型中语义改变 | **R3** |
| T14 → T15/T16/T17 | GameState.table/game；SEAT_COLORS | 一致 |
| T16 → T17 | T16 的 App 路由引用 ResultSheet、Place/DuelPlay/MeleePlay，但这些在 T17 才创建 | **R4** |

### 各任务自身一致性

| 任务 | 检查 | 结论 |
|---|---|---|
| T1 | `it.each([5,17,10.5,'10'])` 期望 reason=boardSize，但 Step 3 规定 shape 检查含类型检查 → '10' 会得到 shape | **R5** |
| T2 | 测试与接口一致 | 一致 |
| T3 | parser 用 validateRuleSet；rematch 移除测试 | 一致 |
| T4 | 工厂两分支先抛 not implemented，由测试断言 | 一致 |
| T5 | 测试列表与行为段落一致 | 一致（受 R2 修改常量） |
| T6 | I6 测试迁移已写明 | 一致 |
| T7 | 重复提交 → NOT_YOUR_TURN | 一致 |
| T8 | rankPlayers 规则与测试一致 | 一致 |
| T9 | "idle 计数为 0" 无外部接口，需以行为断言 | 交实现者：用"回来后再空 2 轮不出局"断言 |
| T10–T18 | 一致 | — |

### Rulings

Setup: Ruling: P1 在新分支 p1-zones 上开发（不建 worktree）— 单人本地仓库，分支已足够隔离，便于整体回滚 — cost if wrong: 无
Pre-flight: Ruling R1: 服务端测试通过相对路径 `../../../packages/shared/test/helpers` 引入 mulberry32，不进生产导出 — 测试辅助不该成为 shared 的公开 API — cost if wrong: 跨包相对路径，搬目录时要改
Pre-flight: Ruling R2: 等候室掉线座位保留时长按桌型区分：好友房 5 分钟、匹配房 60 秒（spec §19.4 写的是统一 60 秒）— 好友房的典型流程是房主切去微信发房间号，60 秒太短（P0 已据此定过 5 分钟）；陌生人桌不该占座久 — cost if wrong: 好友房里掉线者最多占座 5 分钟（开局需全员准备，不会误开局；P2 有踢人）
Pre-flight: Ruling R3: T12 把 P0 hub 测试中依赖 pendingRooms 的场景按 Table 语义改写：房主离线 → 座位保留 5 分钟后释放、桌空即关；房主离线时朋友加入 → 不会开局（需全员准备），不再有"暂停"；其余 P0 安全场景（token、顶号、旧消息过滤、关桌清理）原样保留 — cost if wrong: 无，属语义迁移
Pre-flight: Ruling R4: T16 只做大厅/专区/规则编辑器/等候室及其路由；inGame 分支先渲染占位"对局进行中…"，结算页与 Place/DuelPlay/MeleePlay 的路由由 T17 接上；T16 的浏览器验证到"全员准备后进入对局（占位）"为止 — cost if wrong: 无
Pre-flight: Ruling R5: validateRuleSet 的 'shape' 只表示"不是对象或缺少四个字段之一"；字段存在但类型/取值错误时报该字段（'10' → boardSize；hintAllowed 非布尔 → shape，因其无专属 reason）— 与 T1 测试一致 — cost if wrong: 只影响错误原因文案

## Tasks

Task 1: dispatched implementer (sonnet), BASE decce2a
Mode: Ruling: 用户要求取消评审（"不评审了，直接开始吧"）— 改为实现者按 TDD 完成后，控制者只核对测试与类型检查即进入下一任务；不做逐任务评审 — cost if wrong: 缺少独立评审，P0 的整分支评审曾发现 3 个 Critical，风险由测试与最终验证兜底
Task 1: complete (commits decce2a..9041f49, tests shared 62/62, no review per user)
Task 2: complete (commits 9041f49..fbfbf09, tests shared 70/70)
Task 3: complete (commits fbfbf09..41306d6, tests shared 74/74)
Task 4: complete (commits 41306d6..45d0c80, tests engine 11/11)
Task 4: Ruling: apps/server/tsconfig.json 去掉 rootDir — 服务端 noEmit，rootDir 无作用却阻止测试跨包引用 shared/test/helpers（TS6059）— 交 Task 5 实现者顺带修改 — cost if wrong: 无
Task 5: complete (commits 45d0c80..8017319, tests table+engine 48/48)
Task 5: Ruling: 开局时 Table 除广播 tableState 外，还要向每位玩家发 stateFor（含引擎 view 与摆放截止时间），否则客户端不知道 placing 的 deadline — 归入 Task 10（Table 与真实引擎接缝），在该任务内补测试与实现 — cost if wrong: 无
Task 6: complete (commits 8017319..3c10d86, tests duel+table+engine 98/98)
Task 6: note: 引擎不发 state；Hub 必须在每次 auth（含已在线者重连）后对所在桌发 stateFor — 已在 Task 12 计划内，派发时重申
Task 6: Ruling: 摆放时长由 P0 的 60 秒变为 placeSeconds（1 架 45 秒）— spec §19.3 明确公式，计划 Global Constraints 亦同 — cost if wrong: 只是常量
Task 7-9: Ruling: 三任务同改 melee-engine.ts 且逐步叠加，合并为一个实现者（opus）连续完成、各自提交 — 省去两次上下文重建 — cost if wrong: 无
Task 7: complete (commits 3c10d86..f76c79e)
Task 8: complete (commits f76c79e..f955f29)
Task 9: complete (commits f955f29..7eb655b, tests duel+table+engine+melee 129/129)
Task 7: Ruling: Review Focus #1 原文"发给 a 的消息不含 b 打 c 的坐标"不可满足——一炮同时落在所有存活对手上，b 的坐标作为 incoming 必然到达 a（spec 允许）；改为不变量"a 永远得不到 b 那一炮在 c 棋盘上的结果" — spec §19.6 的私有信息表正是此意 — cost if wrong: 无
Task 9: Ruling: 回合中途因离开/掉线超时出局，不立即广播，在下一次 roundResult.eliminated（或 gameOver）中公布；view() 立即反映 — 最多延迟一个回合时长，无需新消息类型 — cost if wrong: 客户端出局标记最多晚 turnSeconds 秒
Task 9: Ruling: 摆放阶段出局记为第 0 轮，排名最后 — cost if wrong: 无
Task 10: complete (commits 7eb655b..4f38f76, tests 136/136; start sends tableState + per-player state)
Task 11-13: Ruling: 匹配、Hub、端到端紧耦合，合并给一个实现者（opus）连续完成、各自提交 — cost if wrong: 无
Task 11: complete (commits 4f38f76..c78b61a)
Task 12: complete (commits c78b61a..74ea692)
Task 13: complete (commits 74ea692..e7b38c2, server 191/191, tsc clean; mutation check RED→revert OK)
Task 12: note: 离开等候桌不回复离开者、auth 不带昵称回退为"玩家" — 客户端 leave 自行回大厅、每次 auth 带昵称（Task 14/17）
Task 12: Ruling(实现者): joinRoom 先校验目标桌（不存在/对局中/已满）再离开当前等候桌，失败的加入不会让玩家丢座 — 合理，接受 — cost if wrong: 无
Task 14-15: Ruling: 两个客户端纯逻辑任务合并给一个实现者（sonnet）— cost if wrong: 无
Task 14: complete (commits e7b38c2..e6efe75)
Task 15: complete (commits e6efe75..285851a, client 39/39)
Task 15: Ruling(实现者): 推理提示按 planeId 分组各自推理后取并集、跳过已击落飞机 — 多机时把所有机身命中求交集会得到空集 — cost if wrong: 无
Task 16-17: Ruling: 两个界面任务合并给一个实现者（opus），浏览器验证步骤由控制者执行（实现者只保证单测与 vue-tsc）— 路由相互依赖；控制者持有 preview 工具 — cost if wrong: 无
Task 16: complete (commits 285851a..57702fc)
Task 17: complete (commits 57702fc..902ded9, client 51/51, vue-tsc clean; 实现者因 API 配额中断，控制者接续完成 place-model 之外的视图并在浏览器联调)
Task 17: Ruling: 结算页原本对"出局轮次为空且非第 1 名"（对决的输家）显示"存活"，改为显示"—" — 对决输家没有出局轮次但显然不是存活 — cost if wrong: 无
Task 17: 浏览器联调（控制者）：4 人混战打满一局并出排名（胜利/第1/出局轮次/命中数均正确，多色标记与对手标签正常，控制台无报错）；12×12 两步开炮选中→确认生效；2 人对决胜负正确。未做：手机真机与 375 视口截图（T18 补）
Task 18: complete (全量 shared 74 / server 191 / client 51 = 316 全绿；server tsc + client vue-tsc 干净；H5 build OK；APK 4.2MB 构建成功并已安装到华为 ADY-AL00（未注入点击：前台为其他应用，按 P0 约定不做）; 375×812 视口截图正常)
Review fix: Ruling R2（修订）: 等候室掉线座位保留时长改为按在座人数区分：掉线者是唯一在座者 → 5 分钟（FRIEND_SEAT_GRACE_MS），否则 60 秒（MATCH_SEAT_GRACE_MS），不再按桌型 — 好友房里有人在等时不该让掉线者占座 5 分钟 — cost if wrong: 只是常量与判定条件

## P1 遗留 Minor 的归宿（评审 M1–M6，P1 内按指示未处理；2026-11-20 随 P2 落账）

| 编号 | 内容 | 归宿 |
|---|---|---|
| M1 | 混战"已开炮"标记只在客户端本地（刷新/重连后丢） | **已修**：服务端把 submitted 广播给全桌（含本人），P2 提交 9e3984b 起 `view().you.submitted` 带出；客户端 store 以服务端消息为唯一来源（a41f997），浏览器复验通过（对局中刷新 → 仍显示"已开炮，等待其他人…"） |
| M2 | 中途离开/掉线判负者仍显示"思考中"最长一个回合 | **已修**：9e3984b 新增 `playerOut` 即时广播；客户端 store 立即标死并清提交态（a41f997），对局中离开 → 对手标签立刻变"出局"（浏览器复验通过） |
| M3 | 摆放阶段掉线 30 秒宽限先被摆放耗时吃掉 | **已修**：9e3984b——摆放阶段不因掉线出局，掉线者到时自动摆放；宽限从第 1 轮起算 |
| M4 | setReady 无规则版本号（改规则与准备之间的竞态窗口） | **已修**：协议 v3 `setReady.rulesVersion`（00d427d），Table 规则版本随 updateRules 递增（72948de），过期版本回 STALE_RULES 不落 ready；客户端准备按钮改规则后重置 |
| M5 | BAD_RULES 定义了但从未发出；sync 为 O(全体玩家) | **部分修**：BAD_RULES 现在真的会发出——协议解析器对形状合法但 validateRuleSet 不过的规则回 BAD_RULES（protocol.ts parseRulesField），createRoom/updateRules 均经过它；sync 仍是 O(桌成员集合)——已按 membersByTable 收窄到本桌，不再遍历全体玩家 |
| M6 | 同一 tick 内全员超时的胜者由 Map 插入顺序决定 | **不修（记录）**：混战按轮结算本就同时淘汰同轮所有挂机者，`finish()` 的排名由 rankPlayers 的确定性排序（轮次→命中→输入顺序）给出，不再有"随机胜者"；对决是 1v1，双方同超时只会判双方负、以命中数排名，顺序依赖不存在 |
