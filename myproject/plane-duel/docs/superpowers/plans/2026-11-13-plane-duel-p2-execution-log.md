# SDD ledger — plan: docs/superpowers/plans/2026-11-13-plane-duel-p2.md

Spec: docs/superpowers/specs/2026-11-11-plane-duel-design.md（§二十 为准；已读）
Plan: docs/superpowers/plans/2026-11-13-plane-duel-p2.md（P2：人机练习 / 电脑补位 / 公开房间列表 / 房主踢人）
Branch: p2-lobby（从 master 38c03be 切出）
MERGE_BASE: 38c03be

## 执行模式

Mode: Ruling: 沿用 P1 决定（用户："不评审了，直接开始吧"）— 实现者按 TDD 完成后，控制者只核对测试与类型检查即进入下一任务；不做逐任务评审；整分支评审在合并前进行一次 — cost if wrong: 缺少独立逐任务评审，风险由全量测试 + e2e 变异验证 + 整分支评审兜底
Mode: Ruling: Task 1–11 派发实现者（sonnet/opus 交替）；Task 12–16 由控制者直接实现（实现者配额中断后接续，且这些任务全部需要 preview 浏览器联调，控制者持有 preview 工具）— cost if wrong: 无

## 决策记录（执行中变更计划处）

- T2: Ruling: 屏蔽词与 sanitizeNickname 分离——新增 `isNicknameAllowed(input)`，sanitizeNickname 保持纯清洗；服务端组合"清洗→检查→回退" — 职责清晰、不动 P1 语义 — cost if wrong: 调用点漏调 isAllowed 即漏过滤（T11 已覆盖）
- T2: note: 保留前缀 `gm` 会误伤 "gmail" 类昵称，可接受
- T3: Ruling: 混战出局（离开/掉线判负）立即以 `playerOut` 广播（推翻 P1 Task 9 "下一轮 roundResult 才公布"的裁定）— P2 客户端要即时反映对手出局（评审 M2）— cost if wrong: 无
- T6: note: `humanMembers` 不含已离开座位；关桌判定按此计数，Task 7/11 一致
- T8: 测试夹具缺陷（实现者遗留）：昵称断言用 id 'a'/'b' 会命中昵称里的字母，改 pid-alpha/pid-blue + 合法档位名 — 只改测试写法
- T10/T11: Ruling: 测试夹具默认 `botFillMs=null`（保持 P1 排队语义不被补位污染），产品默认 BOT_FILL_AFTER_MS（2/3 人 30s、4 人 45s）；顺带修 `??` 对显式 null 回落默认值的配置 bug
- T12: Ruling: 房间列表推送 = 脏区标记 + 合并窗口（≥1000ms）+ 内容 JSON 比对抑制；订阅时以当前内容作基线（"内容没变就不推"从订阅那一刻起成立）；好友桌每次 dispatchTable 标脏；createRoom/joinRoom/joinListed/createPractice/queueJoin/断线时自动退订（退订静默）；列表上限 50，按在座降序、开房时间降序
- T13: 发现真实协议漂移：服务端 queueStatus 已发 `humansNeeded`，shared 的 ServerMessage 类型漏了该字段（消息是无类型对象，服务端测试抓不到）— 补类型 + 测试
- T15: **真实产品缺陷（浏览器复验发现）**：混战开炮后"已开炮"不显示——服务端把 submitted 也广播给本人，store 却只写给对手；本地乐观标记在刷新/重连后无处可寻。修复：store 以服务端广播为唯一来源写 `game.you.submitted`，补回归测试，浏览器复验（对局中刷新 → 仍显示"已开炮，等待其他人…"）— 即 P1 遗留 M1 的客户端侧闭环
- T15: Ruling: 踢人二次确认用页面内两步按钮（点"移出"→变"确认移出？"再点），不用原生 confirm — 部分内嵌 webview 会卡住原生弹窗 — cost if wrong: 无
- T16: Ruling: 补位 e2e 场景从"1 人排队"改写为"2 真人排 3 人区"——MIN_HUMANS=2 语义下单人排队只收 humansNeeded>0 的等待状态、永不补位（初稿按直觉写了 1 人，被实现打回）；补位桌首帧 tableState 不含 bot 座位（真人先入座、addBot 随后广播），等待条件须含 `seats.some(bot)`
- T16: note: 客户端构建脚本名为 `build:h5`（非 `build`）

## Tasks

Task 1: complete (commit 00d427d, shared 84/84) — 协议 v3
Task 2: complete (commit a3f9454, shared 93/93, client nickname-gen 4/4) — 昵称屏蔽词
Task 3: complete (commit 9e3984b, server engine/table/duel/melee 149 passed) — 评审 M1–M3 服务端修复（playerOut 即时广播、view.you.submitted、摆放掉线宽限）
Task 4: complete (commit ccbb969, bot-brain 21/21) — 电脑大脑（档位失误率 + 候选机头推理）
Task 5: complete (commit 35297b2, bot-driver+brain 36/36) — 思考时间与截止时间余量
Task 6: complete (commit 4ea0b4b, server 197 passed) — 电脑座位 + 练习桌（Table.tick 驱动）
Task 7: complete (commit 72948de, server 172 passed) — rulesVersion + 房主踢人与按桌封禁
Task 8: complete (commit de81de0, table-listing 13/13) — 公开列表投影 + setListed
Task 9: complete (commit 8864e56, server 228 passed) — Table 接真引擎与电脑；变异验证（轮询视图→真人视图使 Review Focus #1 变红）
Task 10: complete (commit 6854723, server 297 passed) — 匹配补位（倒计时对全队可见）
Task 11: complete (commit 87b4d20, server 315 passed, tsc clean) — Hub 路由 v3（练习/补位/踢人/列表加入）
Task 12: complete (commit b06cfa4, server 323 passed) — 房间列表推送（合并窗口/内容比对/自动退订），控制者实现；hub-room-list 新增 8 测试
Task 13: complete (commit ed5893e, client 69 passed) — store v3 + lobby-model（roomList/kicked/playerOut/botFillText/canKick/peerStatus），修 humansNeeded 类型漂移
Task 14: complete (commit cc63f0e, client 76 passed + vue-tsc 0) — 专区页：练习入口（档位 chips）、公开房间列表（RoomList 组件 + 订阅/退订）、补位倒计时文案；浏览器联调：探针 WS 建公开房 →1 秒内出现"测试房主 的房间 / 1/3 / 规则摘要"→点击进等候室；练习入门档 → 混战 vs 🤖电脑；排队倒计时"30 秒后由电脑补位（对局会标注 🤖）"；空列表文案
Task 15: complete (commit a41f997, client 83 passed + vue-tsc 0) — 🤖 徽标、房主踢人（两步确认）、公开开关、server-side submitted（M1）、playerOut 即时出局（M2）；浏览器复验：4 人练习局结算页 🤖 + "本局有电脑参与，不计段位"；练习等候室"人机练习/不计段位"、隐藏房间号；踢人全流程（仅未准备者有按钮→二次确认→被踢方收 kicked 回大厅→重进收 BANNED→座位释放）；M2（对手对局中 leaveRoom → 标签立刻"出局"）；375×812 截图（等候室含移出按钮、结算页）；控制台无 warn/error
Task 16: complete (commit 3aa0b47, server 327 passed) — p2.e2e 四条：人机练习混战（Review Focus #1 路径白名单：含 result 的对象只出现在本人 shots/incoming/state.you；botIds=3）、2 真人排 3 人区 30 秒补位成局（1 bot 座位、botIds=1）、列表+踢人+封禁重进（列表 JSON 不含房间号）、P0 回归（bot: 前缀 BAD_SHAPE、顶号关闭码 4000）；变异验证（roundResult 全量广播 → 练习用例变红，恢复后全绿，diff 只剩测试文件）

## 全量验证（Task 16 Step 3–4）

- pnpm test：shared 93 + server 327 + client 83 = **503 全绿**
- apps/server `tsc --noEmit` 干净；apps/client `vue-tsc --noEmit` 干净
- `pnpm run build:h5`：dist 107.63 kB JS / 19.68 kB CSS，构建成功

## 与 spec 的对应

spec §二十 全部落地：§20.1 范围、§20.2 电脑表示、§20.3 决策与失误率、§20.4 人机练习、§20.5 补位与标注、§20.6 公开列表与屏蔽词、§20.7 M1–M5、§20.8 踢人、§20.9 协议 v3、§20.10 隐私与 P0 不变量。P1 遗留 M1–M6 处置见 p1-execution-log 末节。

## 整分支评审（合并前，子代理全量 diff 评审）

发现 4 项，处置如下（提交 fcaf4c3，全量 94+328+84=506 全绿、双端类型检查干净）：

| # | 级别 | 内容 | 处置 |
|---|---|---|---|
| 1 | **阻塞** | store 的 roundResult 只清 `others[].submitted` 不清 `you.submitted`（M1 改动引入）：混战第二轮起 canFire 恒 false，真人整局再也开不了炮；503 项测试全绿却漏网，因为没有任何测试驱动客户端 store 走完混战回合循环 | **已修**：roundResult 同时 `g.you.submitted = false`；补 store 回归测试；浏览器复验练习混战连打 4 轮无卡死、控制台干净 |
| 2 | 应修 | 昵称保留前缀缺 `bot`："bot1号 / bot:9527" 可冒充电脑出现在公开列表与座位表（playerId 侧的 BAD_SHAPE 挡不住昵称路径） | **已修**：RESERVED_PREFIXES 补 `bot`，测试覆盖分隔符/全角变体 |
| 3 | 小 | joinListed 缺"已在该桌"短路：对自己已在的桌发 joinListed 会离开再进，触发房主自己让位 | **已修**：与 joinRoom 同样补发快照短路；补 hub-p2 测试 |
| 4 | 小 | 结算页在桌子关闭后（match 房有人离开→close）把 bot 渲染成"🤖 玩家"、座位色取不到 | **记录不修**：纯外观，只发生在"结算页停留期间桌子恰好关闭"的窄窗口；P3 战绩页重做结算数据源时一并处理 |

评审确认成立的不变量：混战结果私有（roundShots/roundIncoming 按收件人切分）、P0 auth（bot: 前缀 BAD_SHAPE、顶号 4000、bot id 仅服务端铸造）、踢人/封禁谓词与服务端逐条一致且封禁按桌隔离、房间列表无 roomCode/playerId、STALE_RULES 恰好拒绝一次并补发、练习桌不可外部加入。
