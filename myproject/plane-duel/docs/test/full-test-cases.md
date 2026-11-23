# 飞机对决 全量测试用例（交付 Cursor 执行版）

> 版本：2026-11-23 · 覆盖：账号/会话/Web 入口/大厅/匹配/好友房/摆放/决斗/混战/掉线重连/结算落库/经济/段位/限流/UI/基础设施/历史 bug 回归。
> 优先级：P0=阻断级（必须全绿）P1=核心体验 P2=边界与健壮性。
> 记法：期望都写成可断言的具体值；"两页"= 两个独立浏览器上下文/隐身会话（互不共享 localStorage）。

---

## 0. 环境与执行约定

| 项 | 值 |
|---|---|
| 页面/同源 API 入口 | `https://game.ok123find.top/`（页面 + `/vvv/api/game/v1/*` + `/vvv/api/game/ws` 同域） |
| API 专用域 | `https://api.ok123find.top/vvv/api/game/v1/*`（等价接口，用于纯接口用例） |
| WS 地址 | `wss://game.ok123find.top/vvv/api/game/ws?vpnToken=<token>` |
| HTTP 响应壳（游戏接口） | `{"errno":0,"data":…,"error":null}`；errno≠0 时 `error="GameErrorCode:消息"`，未鉴权 `errno=401, error="NOT_AUTHED"` |
| HTTP 响应壳（登录/注册等 legacy） | JsonResult `{errno,data,error,cost,ip,userIp}`；错误码 `11002` 参数、`11001` 凭据/存在/邮件失败/重置过期、`10000` 系统 |
| 游戏接口鉴权 | 请求头 `Vpn-Token: <完整token（可带 token_ 前缀，两种都接受）>` |
| 测试账号命名 | 一律 `qa<mmddHHMMSS>` 前缀（如 `qa1123153042`），便于清理；建议密码统一 `Qa!2026test#p` |
| 数据核对 | 方案 A：HTTP 读接口回读（默认）；方案 B：SSH 到应用服务器用应用 DB 账号查 `vpn` 库 `game_*` 表（本机直连无权限） |
| 纪律 | 这是生产环境：并发 ≤2、每组用例后清理账号与房间；不要压测级刷接口 |

**准备三件套账号**（后续用例复用）：`qaA`、`qaB`（已登录、各持有效 token）、`qaC`（备用）。

---

## 1. 注册 / 登录 / 找回密码（HTTP，POST JSON）

| ID | P | 用例 | 期望 |
|---|---|---|---|
| AUTH-01 | P0 | 注册 `POST /register {"name","pwd","rePwd","email":""}` | `errno=0` |
| AUTH-02 | P0 | 新用户 `POST /login {"name","pwd"}` | `errno=0`，`data.token` 非空（`token_` 前缀形态），`data.name`=用户名；**该 token 能通过注册→登录闭环（历史 bug 回归点：注册账号必须可登录）** |
| AUTH-03 | P0 | 重复注册同名 | `errno≠0`，文案含"用户名已存在"（11001） |
| AUTH-04 | P0 | 错误密码登录 | `errno=11001`（不泄露"用户存在/不存在"差异） |
| AUTH-05 | P1 | `pwd != rePwd` | `errno=11002` |
| AUTH-06 | P1 | 缺 name / 缺 pwd / 空 body | `errno=11002`（或 10000），不得 500 |
| AUTH-07 | P1 | 注册不带 email → 走 findpass 只传该用户邮箱 | 静默成功（`errno=0` 无 error），因为无法发信但不得泄露绑定状态 |
| AUTH-08 | P1 | 已绑邮箱用户 `POST /findpass {"email"}` | `errno=0`；邮件收到 6 位验证码（人工核验一次即可） |
| AUTH-09 | P1 | `POST /resetpass {email, code, pwd, rePwd}` 用正确码 | `errno=0`；旧密码登录失败、新密码登录成功 |
| AUTH-10 | P1 | resetpass 用错误码 | `errno=11001` |
| AUTH-11 | P2 | 同一验证码用 5 次后 | 第 6 次拒绝（尝试上限）；验证码 30 分钟过期后拒绝 |
| AUTH-12 | P2 | SQL 注入尝试 `name="a' OR '1'='1"` | 正常参数错误/注册失败，无 500，库里无异常行 |
| AUTH-13 | P2 | 超长输入（name 200 字符、pwd 200 字符） | `errno=11002` 或成功但截断策略一致；无 500 |

## 2. 会话与 token

| ID | P | 用例 | 期望 |
|---|---|---|---|
| SES-01 | P0 | 登录成功 → 打开页面 | 直接进大厅（token 在 localStorage `plane-duel:vpnToken`）；**URL 中不出现 vpnToken/token** |
| SES-02 | P0 | 无 token 直接访问 `/` | 显示登录页，**不发生任何 WS 连接**（DevTools Network 无 ws 请求） |
| SES-03 | P0 | 带 token 调 `GET /profile` | `errno=0`，`data.userId/nickname/rank` 齐 |
| SES-04 | P0 | 不带 `Vpn-Token` 调 profile | `errno=401, error="NOT_AUTHED"` |
| SES-05 | P1 | 每次游戏接口成功鉴权后 token 滑动续期 24h | 活跃账号不会中途被踢（长时间挂机对局 > 初始 TTL 的场景可跳过，代码审计替代：GameTokenResolver EXPIRE 重置） |
| SES-06 | P1 | 退出登录按钮 | localStorage token 清除 → 回登录页 → WS 断开 |
| SES-07 | P1 | token 失效场景：手动删 Redis key 后刷新页面 | 3 次重连失败后（从未认证成功）自动回登录页，提示"登录已过期" |
| SES-08 | P2 | 页面 URL 手动加 `?vpnToken=xxx` | **一律忽略**（产品红线），仍按 localStorage 判定 |
| SES-09 | P2 | 同账号两个浏览器上下文同时连 WS（顶号） | 旧连接被服务端关闭，新连接正常（旧 socket 掉线不影响新会话） |

## 3. WS 连接与鉴权

| ID | P | 用例 | 期望 |
|---|---|---|---|
| WS-01 | P0 | `wss://…/vvv/api/game/ws?vpnToken=<有效>` 握手 | `101 Switching Protocols` |
| WS-02 | P0 | 无 vpnToken / 无效 token 握手 | `401` |
| WS-03 | P0 | Origin 不在白名单（如 `http://evil.example`）握手 | `403`；白名单= `https://api.ok123find.top, https://game.ok123find.top, https://localhost` |
| WS-04 | P0 | 连上后服务端自动推 `profile.now`（含段位/金币） | 大厅无需点任何东西即显示正确数据 |
| WS-05 | P1 | 服务端每 25s 发 ping 帧（`game.ws.pingMs=25000`） | 浏览器自动 pong（抓包或代理观测）；连接不会被 nginx 300s 空闲超时掐死 |
| WS-06 | P1 | 发非法 JSON 帧 `{bad` | 收到 `error` 事件 code=`BAD_JSON`，连接不断 |
| WS-07 | P1 | 发未知命令 `{"cmd":"foo.bar"}` | `UNKNOWN_CMD` 错误帧，连接不断 |
| WS-08 | P2 | 发 `{"cmd":"game.item",…}` | `UNSUPPORTED`（道具未开放） |
| WS-09 | P2 | 命令频率 > ~20/s 持续（脚本刷） | 先 `RATE_LIMITED` 帧，连续违规 → 服务端断连 |

## 4. 大厅 / 个人资料 / 金币读接口

| ID | P | 用例 | 期望 |
|---|---|---|---|
| PROF-01 | P0 | `GET /profile` | `data.rank` 含 tier/stars/lossStreak/wins/losses/totalHits/bestTier/bestStars/streak/scoringGames；新用户全 0 |
| PROF-02 | P0 | `PUT /nickname {"nickname":"测试员"}` 后 profile | 昵称更新；所有对手视角显示新昵称 |
| PROF-03 | P0 | 昵称黑名单：`电脑`、`机器人2`、`admin_x`、`bot`、含 `🤖`、脏词 | 服务端拒绝（错误帧或错误码）；正常长昵称（1-12 码点）接受 |
| PROF-04 | P1 | 昵称 13 字符 / 纯空白 / 带 emoji（非 🤖） | 13 字符截断或拒绝，空白回退默认名 |
| PROF-05 | P0 | `GET /matches/recent` 新用户 | `data=[]` |
| PROF-06 | P1 | 打完一局（匹配局）后 recent | 出现 1 行：matchId/mode/preset/capacity/finalRank/hits/deltaStar/win/scoring 与实况一致 |
| PROF-07 | P1 | `GET /rank/list` | 按段位排序的名次列表，含昵称 |
| PROF-08 | P1 | `GET /coins/ledger` | `data.balance` 与大厅金币条一致；明细新在前 |
| PROF-09 | P0 | `POST /coins/ad-reward {}` | `errno=0, data.granted=30, data.balance` 增加；同日第 6 次起 `granted=0`（日上限 5 次，QUOTA 或 capped 表现一致） |
| PROF-10 | P1 | ad-reward 连点幂等 | 同请求重放不重复入账（幂等键 `AD:…`） |

## 5. 匹配队列与门票

| ID | P | 用例 | 期望 |
|---|---|---|---|
| Q-01 | P0 | 单人在"2 人对决/入门/免费场"排队 | 收到 `queue.status`（等待人数）；30s 后电脑补位成局（`BOT_FILL=30s for cap2/3, 45s for cap4`），开局带"本局有电脑补位"提示 |
| Q-02 | P0 | 两页各排"2 人对决/入门" | 服务端把两个真人配对成局（无电脑）；等待 ≤ 补位倒计时 |
| Q-03 | P0 | 排队中点"取消排队" | `queue.leave` 生效，回专区视图，无幽灵席位 |
| Q-04 | P1 | 排队中切换到另一个档位 | 自动退旧队列进新队列（一份等待） |
| Q-05 | P1 | 免费场成局（真人）→ 金币不变（门票 0 奖 0，完成局 +5） | 余额精确 +5 |
| Q-06 | P1 | 金币 ≥50 时排"标准场"（门票 50，胜 +80） | 排队即扣 50；胜则 +80，负则净 -50；**未成真人局（电脑补位）门票原路退回** |
| Q-07 | P1 | 金币 < 门票价 | 门票档按钮置灰（前端）/ `BALANCE_LOW` 或 `TICKET_DENIED`（接口层） |
| Q-08 | P2 | 同 capacity×preset×ticket 是同一队列；不同门票不互相配对 | 免费场 A 不和标准场 B 同桌 |
| Q-09 | P2 | 4 人区单人排队 | 45s 补位；3 人桌补 1 个电脑 |

## 6. 人机练习

| ID | P | 用例 | 期望 |
|---|---|---|---|
| PRA-01 | P0 | 专区"人机练习/入门" | 立刻成局（缺位由电脑补），房间视图显示练习标记 |
| PRA-02 | P0 | 练习局打完整局 | 结算页显示"本局有电脑参与，不计段位"；段位/星数 **不变**，金币 +5（完成局奖励，受日上限） |
| PRA-03 | P1 | 练习局中途"离开房间" | 回大厅；无门票损失（练习无门票） |
| PRA-04 | P1 | 电脑对手行为 | 每回合在截止前开炮（不会整局空转）；命中结果合法（不重复打同一格） |

## 7. 好友房

| ID | P | 用例 | 期望 |
|---|---|---|---|
| FR-01 | P0 | A 创建好友房（默认规则）→ 显示 6 位数字房间号 | 号码 ∈ [100000, 999999] |
| FR-02 | P0 | B 大厅输入房间号加入 | 双方等候室互见座位；A 为房主 |
| FR-03 | P0 | 双方点"准备" | 全员 ready → 进入摆放（`place` 视图） |
| FR-04 | P0 | 房主"修改规则"（如 10×10、1 架、30 秒、提示开）并保存，双方准备 | 按新规则开局（倒计时 30s 对局时钟验证） |
| FR-05 | P1 | 非法规则（boardSize 20 / planeCount 超密度上限 / turnSeconds 不在 10/15/20/30/45/60） | `BAD_RULES`；前端编辑器应禁止产生非法值 |
| FR-06 | P1 | 3 人房未坐满时房主 kick 空位 | 无错误；坐 1 人后 kick 该玩家：被踢者收到 kicked → 回大厅，不能再操作该房 |
| FR-07 | P1 | 非房主发 kick / 已准备玩家改规则 | `NOT_HOST` / `NOT_READY` 或 `STALE_RULES` |
| FR-08 | P1 | 打开"公开到房间列表"开关 → 第三者在专区"公开房间"列表可见并点击加入 | 加入成功，等候室 3 人 |
| FR-09 | P2 | 加入已满好友房 | `ROOM_FULL` |
| FR-10 | P2 | 对局进行中第三者加入 | `ROOM_IN_GAME` |
| FR-11 | P1 | 结算页"再来一局"（好友房） | 原班人马新摆新局；**rematch 为免费普通局** |
| FR-12 | P1 | **好友房不落账回归点**：打完一局好友房后查 recent/DB | `matches/recent` 不新增该 match；`game_match` 无该 friend 局（设计如此，不是 bug） |

## 8. 摆放阶段

| ID | P | 用例 | 期望 |
|---|---|---|---|
| PL-01 | P0 | 点内部格（非边缘一圈）→ 3×3 机身预览 → 点"就绪" | 收到 `game.planeAccepted`；等待对手 |
| PL-02 | P0 | 机头放边缘（A1/H8 类） | 前端提示"机头不能放在边缘一圈"；绕过前端直发 WS 也回 `INVALID_PLACEMENT` |
| PL-03 | P0 | 两架重叠 / 机身越界 | 拒绝并提示；WS 层 `INVALID_PLACEMENT` |
| PL-04 | P1 | 点已有机身任一格 = 移除该架 | 草稿回退；再点"就绪"前提交无效 |
| PL-05 | P0 | 摆放时限 = 30 + 15×planeCount 秒（入门 45s、进阶 60s、高手 75s） | 倒计时显示一致；超时未摆 → 服务端 **autoPlace 自动摆放**并 planeAccepted，游戏照常开始 |
| PL-06 | P2 | 多放一架（超过规则 planeCount） | 前端禁点/提示"已放满"；WS 回 count 错误 |

## 9. 决斗（2 人对决）规则

| ID | P | 用例 | 期望 |
|---|---|---|---|
| D-01 | P0 | 开局轮到 A（`status="轮到你开炮"`）；A 点一格 → `game.shot` 事件 | 结果 ∈ miss/hit/head；B 侧同步显示 |
| D-02 | P0 | **机头被击中 = 立即判胜** | 第一发命中对方机头 → `game.over`，结算"机头被击中 · 2 人" |
| D-03 | P0 | 轮流性：B 回合点击无效 | `NOT_YOUR_TURN`；前端格子禁用 |
| D-04 | P0 | 重复打同一格 | `REPEAT_SHOT`；前端已打格不可点 |
| D-05 | P0 | 越界坐标（row=-1/col=99 或 board 外） | `OUT_OF_RANGE` |
| D-06 | P1 | 回合超时（入门 30s/标准 20s）未开炮 | 服务端 **autoFire 随机补炮**，游戏继续 |
| D-07 | P0 | 小棋盘一点即射；`boardSize≥12` 或混战需两步（选中→"开炮 B7"按钮） | 交互形态正确 |
| D-08 | P1 | 推理提示勾选（仅 hintAllowed 档位） | 候选机头高亮变化；进阶/高手无此开关 |
| D-09 | P1 | 结算页元素 | 排名列表（胜者第 1 名）、金币 +5 完成奖励、"再来一局/查看等候室/返回大厅"按钮 |

## 10. 混战（3/4 人）规则

| ID | P | 用例 | 期望 |
|---|---|---|---|
| M-01 | P1 | 3 人局同时开炮（每回合所有人可射） | 每人每回合 1 发；`game.submitted` 全员提交后进下一轮 |
| M-02 | P1 | 一炮打所有人：每人的 shot 各算各的 | 三个射手同轮各自命中独立计算 |
| M-03 | P1 | 玩家出局（机头被击中或掉线超时）→ 下一 `roundResult.eliminated` 公布 | 出局者"你已出局"后续操作 `WRONG_PHASE`；最后存活者胜 |
| M-04 | P2 | 4 人局配对（队列 cap4） | 同桌 4 人；补位 45s |

## 11. 掉线 / 重连 / 暂停

| ID | P | 用例 | 期望 |
|---|---|---|---|
| RC-01 | P0 | 对局中 A 关闭页面（模拟掉线） | B 侧 status"对手掉线，等待重连"、棋盘暂停（倒计时冻结）、`player.presence` 更新；A 操作回 `PAUSED` |
| RC-02 | P0 | 掉线后 30s 内 B 重开页面登录 | 自动恢复到原桌原局（重连恢复），deadline 顺延，可继续打 |
| RC-03 | P0 | 掉线超过 30s（`DISCONNECT_GRACE_MS=30000`） | 判负/出局：对手直接 `game.over`（duel 判负；melee 出局） |
| RC-04 | P1 | 摆放阶段掉线重连 | 恢复草稿与倒计时 |
| RC-05 | P1 | WS 断网恢复（切 Wi-Fi 场景模拟 `socket.close`） | 客户端自动重连（指数退避），带同一 localStorage token 恢复会话；对局中的桌自动归位 |
| RC-06 | P2 | 慢客户端（脚本挂起消费） | 服务端装饰器缓冲溢出后主动断开该连接（不拖垮 Hub），客户端走重连 |

## 12. 结算与持久化（方案 B 需 SSH 到应用服务器）

| ID | P | 用例 | 期望 |
|---|---|---|---|
| DB-01 | P0 | 跑一局匹配局（两页真人，见 Q-02）到结算并"返回大厅" | `vpn.game_match` 新增 1 行：`finished=1, close_reason='finished', mode='duel'`，`started/ended_at_ms` 合理 |
| DB-02 | P0 | 同局 `game_shot` | 逐发明细行数=实发炮数；字段 seq 连续、by_user/target_user=row_no/col_no/result 正确（head 发 result='head'） |
| DB-03 | P0 | `game_match_player` | 每人 1 行：final_rank/hits/win/scoring（纯真人局 scoring=1；有电脑补位/练习局 scoring=0） |
| DB-04 | P0 | `game_progress` | 胜者 wins+1 stars+1；败者 losses+1（星数规则见 RK-02/03）；`matches/recent` 与之一致 |
| DB-05 | P1 | `game_wallet/game_coin_ledger` | 每完成局 +5（GAME 明细幂等键 `GAME:<matchRef>` 不重复） |
| DB-06 | P1 | 对局中途弃权/退款 | `game_match.close_reason` 盖对应原因；不重复结算（CAS：`finished=0→1` 抢占，双结算尝试只有一次生效） |

## 13. 金币经济细则

| ID | P | 用例 | 期望 |
|---|---|---|---|
| CO-01 | P0 | 常量核对 | 登录 +50/日、完成局 +5（≤20 局/日）、广告 +30（≤5 次/日）、每日净增封顶 **500**；门票 免费0 / 标准50→胜80 / 高级100→胜160 |
| CO-02 | P1 | 净增封顶触发 | 当日净收益达 500 后，后续产出 capped（granted 截断），账本仍留痕 |
| CO-03 | P0 | 金币永不在玩家间转移 | 胜者奖励固定额，与对手门票无关（两局不同门票组合验证） |
| CO-04 | P1 | 明细页翻页/条数 | 内存视图 ≤100 条，新在前 |
| CO-05 | P2 | 跨日 00:00（Asia/Shanghai）后计数翻转 | 次日登录/完成局奖励重新可得（可用修改系统时间不可行→代码审计） |

## 14. 段位与赛季

| ID | P | 用例 | 期望 |
|---|---|---|---|
| RK-01 | P0 | 段位名序列 | 列兵→新兵→少尉→上尉→少校→上校→准将→元帅；星数上限 3,3,5,5,5,5,5,5 |
| RK-02 | P0 | 胜 +1 星；满星升段（星数清零进下段） | profile 与大厅卡片一致 |
| RK-03 | P0 | 负：有星扣 1；0 星且非列兵 → 降段并满星；**连负 3 场 → 本局不扣星、连负计数清零** | 与 Rank.java 语义一致 |
| RK-04 | P0 | 有电脑参与（练习/补位局）不动段位 | tier/stars 不变（scoring=0） |
| RK-05 | P1 | 赛季号 | 第 1 赛季起算 2026-11-23 UTC，4 周一季；大厅"第 N 赛季"文案 |
| RK-06 | P2 | 段位榜 rank/list 与个人分匹配 | 名次单调、可复算 |

## 15. Web 入口与基础设施

| ID | P | 用例 | 期望 |
|---|---|---|---|
| INF-01 | P0 | `GET https://game.ok123find.top/` | 200 登录页/静态站；证书有效（Let's Encrypt，非过期） |
| INF-02 | P0 | `GET http://game.ok123find.top/` | 301 → https |
| INF-03 | P0 | `https://api.ok123find.top/plane/` | **404**（api 域不挂页面，红线回归） |
| INF-04 | P0 | `GET /vvv/api/game/v1/health` | `{"module":true,"redis":true,"mysql":true}` |
| INF-05 | P1 | 静态资源（js/css）加载来源 | 全部来自 game 域（不外链、不挂 api 域页面） |
| INF-06 | P1 | 页面调 API | 同源 `/vvv/api/game/v1`，无 CORS 预检失败；自定义头 `Vpn-Token` 放行 |
| INF-07 | P1 | 游戏接口固定打到本机 jar（上游 `vpn_game` 钉死 127.0.0.1:8888） | 连续 20 次请求无随机 10000 "System error"（历史 bug 回归：旧远端节点无 game 模块） |
| INF-08 | P1 | 重启演练：`systemctl restart vvv-link` | 服务 5s 自拉起恢复监听；期间请求 502（预期）；恢复后闭环复验通过 |
| INF-09 | P2 | certbot 续期演练或证书剩余天数检查 | >20 天；deploy hook 存在且可执行 |
| INF-10 | P2 | H5 构建产物发布脚本（服务器 `/root/work/deploy-plane-h5.sh`） | 跑通且自检 curl 200（非破坏性检查） |

## 16. 前端 UI 全流程（Playwright，两页 + 一页手机视口 375×812）

| ID | P | 用例 | 期望 |
|---|---|---|---|
| UI-01 | P0 | 登录页渲染：标题、登录/注册 tab、账号/密码框、"忘记密码？" | 无 console 报错（历史 bug 回归：Login 页曾整页 ReferenceError） |
| UI-02 | P0 | tab 切换登录↔注册；注册页四字段（用户名/密码/确认/邮箱可选） | 注册成功后**自动登录**进大厅 |
| UI-03 | P0 | 忘记密码 → 两步流（发码 + 60s 倒计时 → 验证码+新密码） | UI 状态机正确；重置成功预填用户名 |
| UI-04 | P0 | 大厅三档专区卡片、金币条、段位卡、改名入口 | 数据与 profile 一致 |
| UI-05 | P0 | 完整双页匹配局流程（Q-02 的 UI 版）：登录×2 → 排队 → 摆放 → 对弈 → 结算 → 返回大厅 | 全程 console 零 error；结算文案正确 |
| UI-06 | P1 | 改名：输入非法名（黑名单/超长） | 就地提示，不落库 |
| UI-07 | P1 | 房间号输入框只收数字、≤6 位；未满 6 位禁用"加入好友房" | 交互正确 |
| UI-08 | P1 | 静音按钮切换、音效图标 | 状态持久（localStorage） |
| UI-09 | P1 | 结算"再来一局/查看等候室/返回大厅"三按钮行为 | 分别进入：新一局摆放 / 原等候室 / 大厅并关房 |
| UI-10 | P2 | 375×812 与 768×1024 视口 | 棋盘/结算无溢出遮挡 |
| UI-11 | P2 | 退出登录 → 再登录同账号 | 会话全新（store/socket 重建），无脏状态 |

## 17. 历史 bug 回归清单（必须逐条点名）

1. **pwdHash**（commit f5ef1532）：注册的账号必须能登录（AUTH-02）。
2. **上游钉死**（vpn_game）：游戏接口无随机 10000（INF-07）。
3. **api 域不挂页面**：`/plane/` 404（INF-03）。
4. **token 不进页面 URL**：登录流/刷新/分享全程 URL 无 token（SES-01/08）。
5. **WS Origin 白名单生效且 game 域在内**（WS-03）。
6. **Login.vue 渲染异常**（defineProps 引用）：登录页加载零 console error（UI-01）。
7. **http-proxy WS Origin 钩子**（dev 预览用，仅本地 dev 回归，不涉线上）。

## 18. 测试数据清理（每组用例结束后）

- 记录本次所有 `qa*` 用户名与产生的 match_id。
- 服务器上（应用 DB 账号）：
  `DELETE FROM vpn.game_shot WHERE match_id IN (…);`
  `DELETE FROM vpn.game_match_player WHERE match_id IN (…);`
  `DELETE FROM vpn.game_match WHERE match_id IN (…);`
  `DELETE FROM vpn.game_progress/game_wallet/game_coin_ledger WHERE user_id IN (…);`
  `DELETE FROM vpn.user WHERE name LIKE 'qa%';`
- Redis db1 中已删用户的 `token_*` 会话可留待 24h 自然过期（不阻塞）。
- **红线：测试文档与脚本里不得写入任何真实 DB/Redis 连接串或生产口令。**

## 19. 验收汇总标准

- P0 全绿（预计 ~40 条）→ 可上线判定。
- P1 ≥90% 绿，剩余项附复现步骤与严重度评估。
- P2 允许已知限制，但必须记录（如登录接口暂无限流/验证码、WS 握手 URL 携带 token 属浏览器协议限制）。
- 所有"期望"若与实现不符：优先核对本文档 §0 契约与 `testserverV/docs/game/{protocol.md,api.md,data-model.md}`，文档与代码都一致而行为不符 → 报 bug；文档与代码互相矛盾 → 报契约漂移，不要静默改判。
