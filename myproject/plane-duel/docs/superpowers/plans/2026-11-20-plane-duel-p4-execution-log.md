# P4 执行日志：金币经济（2026-11-20）

设计见 spec §廿二（docs/superpowers/specs/2026-11-11-plane-duel-design.md）。
分支 `p4-coins`（自 a26bfc5），合并于 88cd30d。

## 交付内容

| 块 | 内容 | 测试 |
|---|---|---|
| shared 账本 | `packages/shared/src/coins.ts`：applyCoin（幂等/余额拒绝/净增封顶/分 reason 日限）、每日计数器、门票定价固定额、赛季发币 | coins.test 13 例 |
| 协议 v5 | `coinRequest`/`coins`/`coinsChanged`/`adRewardRequest`；`queueJoin.ticket?`；ProfileView.coins；错误码 NOT_ENOUGH_COINS/DAILY_TICKET_LIMIT/AD_LIMIT。v4 兼容：不带 ticket 走无 ticket 队列键，queueStatus 不回显 | protocol/hub-e2e 深比较锁定 |
| 服务端账本 | 登录礼 50/日（auth 内先记账再推 profile）、完成局 +5、广告 mock +30×5/日、赛季发币 (tier+1)×50 | hub-p4 10+3 例 |
| 门票对局 | queueJoin 预付 → 离队/换队/断线/补位退款（豁免净增）→ 纯真人满局记桌 → 首局胜者固定奖励；rematch 免费 | hub-p4 + p4.e2e |
| 客户端 | 大厅金币条、账本页（流水倒序、当日配额、余额实时跟涨）、专区三档门票卡（余额不足置灰）、结算金币行 | store P4 7 例 |
| 端到端 | p4.e2e 真实 socket：门票局全链路（85/5、reason 顺序）、取消退款、掉线退款（重连带 token）、v4 兼容无 ticket 字段 | 4 例 |

## 关键口径

- **余额是权威**：profile 总在账变之后推最终值（scoreTable 先记账后推 profile→rankChanged→coinsChanged），客户端两路都写同一个 `state.coins`。
- **门票生命周期恰好一次**：`ticketQueue`（排队中）→ `ticketByTable`（已记桌，连入座名单）→ 删除。退款先认领（Map delete）再入账；关桌兜底按名单退（防御网，正常路径都先经 scoreTable）。
- **幂等键带单调序号**：`ticket-fee:p:T:n` / `ticket-refund:p:T:n`——只用时刻会在同毫秒双消息下互相吞并（见评审 #1）。
- **广告只留接口**（§廿二.4）：`adRewardRequest` 服务端可用，客户端不露 UI，P5 换真 SDK verifier。

## 整枝评审处置（8 项，全部处理于 f307fe2）

| # | 级别 | 发现 | 处置 |
|---|---|---|---|
| 1 | blocker | 门票费/退款幂等键只含 `now`：同毫秒 standard→advanced 互切，第二笔撞 id 被幂等吞（applied=0 未拦），按高档退款白赚 50/轮，退款豁免净增上限 → 无限刷币 | 键加单调序号 `ticketSeq`；`applied===0 && !insufficient` 视为扣费失败报错。回归测试锁 reason 序列与余额 |
| 2 | major | `ticketByTable` 只记档位：首局没打完就关桌 → Map 孤儿 + 双方票款被吞，违反 §廿二.3 流局退款 | 值改 `{ticket, ids}`；`sync()` 关桌时对未结算票桌全额退。实测现网路径（入座即开打、离席判负）都先经 scoreTable 结算，故新增锁行为测试防双退/双发 |
| 3 | major | DAILY_GAME_MAX=20 只计数不检查，21 局起照发 +5 | applyCoin 对 reason==='game' 检查 `gameGrants >= DAILY_GAME_MAX` → applied=0 capped。shared 与 hub-p4 各 1 例回归 |
| 4 | major | 跨季懒路径 `get()` 重置段位不发赛季币，且随后 `resetSeasonAll` 跳过 → 在线玩家 (tier+1)×50 无声蒸发 | 两路共用 `crossSeason()`；幂等键 `season-grant:赛季` 天然防双发。顺带删掉永不触发的 insufficient 死分支 |
| 5 | minor | 重启窗口：`ticketQueue`/`ticketByTable` 纯内存，重启时排队/桌上门票既不退款也无恢复 | **记为已知限制**（见下）。P4 单进程部署可接受；P5 上 Redis/Postgres 时随存储一并解决 |
| 6 | minor | applied=0 也推 coinsChanged → 结算页"+0"空条并覆盖有效提示；退款空推 | `applied===0` 不推账变；扣费路径视为失败 |
| 7 | minor | 账本页开着时 coinsChanged 不更新 `coinLedger.balance`，页头与金币条互相矛盾 | reducer 同步（若账本已拉取）。store 回归 1 例 |
| 8 | minor | joinTable 签名行折叠（格式回归） | 已修复 |

评审明确干净的方面：v4 兼容无回归；§18.4 法规红线成立（无玩家间流转，奖励固定额）；成组/结算无竞态。

## 测试与验证

- shared **123** / server **377**（32 文件）/ client **95**（8 文件）；tsc×3 干净。
- ws-client 默认超时 3s→15s：并行套件抢 CPU 时 p3.e2e 跨季用例偶发翻车（潜伏于 P3，本轮压测 3 连翻 1 次定位）。修复后 3×全套 377 无 flake。
- 浏览器 375×812 实链路：金币条 → 账本页（登录 +50、配额三项）→ 专区三档卡（高级场置灰 opacity 0.45）→ 标准场排队（ticket 回显"·标准场"）→ 探针真人门票局：预付 −50 → 胜利结算「金币 +80 · 门票胜利」→ 回大厅余额 85。console 零错误。

## 已知限制（出界项）

1. **重启窗口**（评审 #5）：排队中/已记桌的门票在内存，服务重启后票款留在账本无退款路径。缓解：账本可审计（fee 条目在），客服可人工补；根治在 P5 持久化门票状态。
2. 广告为服务端 mock（§廿二.4），无 SDK、无客户端入口。
3. JSON 文件档案为单进程存储；多实例部署前换 Redis/Postgres（接口不变）。

## 提交链

a26bfc5 docs(§廿二) → fde311e server 账本+门票 → 447e726 client UI → 0bb876e p4.e2e → f307fe2 评审 8 项处置 → 88cd30d merge master。
