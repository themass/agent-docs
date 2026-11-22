# P3 执行日志（账号 · 段位 · 战绩 · 排行榜）

日期：2026-11-20 · 分支：`p3-ranks` → `master`
规格：spec §廿一（docs/superpowers/specs/2026-11-11-plane-duel-design.md）

## 一、交付内容

### shared（纯规则 + 协议）
- `rank.ts`：段位纯函数——8 档段位（列兵→元帅）、星数上限 [3,3,5,5,5,5,5,∞]、
  升段/降段/保星（连败 ≥3 免掉星）/列兵 0 星垫底保护、隐藏 Elo MMR（K=32，±400 截断）、
  赛季（4 周一季，epoch 2026-11-23）、`mmrBucket`/`matchRelaxGate` 分桶匹配闸。
- 协议 v4：C→S `profileRequest` / `rankListRequest`；
  S→C `profile` / `rankChanged{delta,rank,reason}` / `rankList{season,entries}`。
  段位变动只走 `rankChanged`，不塞进 `TableResult`。

### 服务端
- `profile.ts`：`ProfileStore` 接口 + `MemoryProfileStore` + `JsonFileProfileStore`
  （5 秒防抖落盘、退出 flush、损坏文件空启动）；`record()` 按
  `id = tableId:gamesPlayed` 幂等，重放返回原 delta 不重复加星。
- `hub.ts`：auth 即推 profile；gameOver 投递后、sync 前 `scoreTable`；
  计分局判定（匹配成局且零电脑才动段位；补位/练习只记结果；好友桌完全不记）；
  赛季跨季 tick 推送 `rankChanged(season-reset)`；榜单 50 名上限、条目不含 playerId。
- `table.ts`：`afterEngine` 当场快照 `humanMembers` → `lastGame.humans`（竞态修复，见下）。
- `matchmaking.ts`：入队携带 MMR；同桶即配、相邻桶等 15 秒放宽、更远永不；
  满员但被闸住的队列不电脑补位（补位局本就不计分，走原倒计时）。
- `main.ts`：默认 `data/profiles.json` 持久化（`profileFile: null` 可切内存）。

### 客户端
- `store.ts`：profile / rankChanged（仅 scoring 落 rankFlash）/ rankList 接入；
  进 inGame 清 rankFlash；resetToLobby 保留档案与榜单。
- 新组件：`RankCard`（大厅段位卡）、`ProfileSheet`（战绩页）、`RankListSheet`（段位榜，
  打开即拉 + 30s TTL）；`ResultSheet` 显示段位变动（+1 / −1 / 保星）。
- 弹层置于 App.vue `v-if/v-else-if` 链之外（链内插入会把 `v-else` 接错）。

## 二、过程中抓到并修掉的真实缺陷

| # | 缺陷 | 发现途径 | 修复 |
|---|------|----------|------|
| 1 | **座位快照竞态**：match 桌有人中途离开会立刻关桌清座，Hub 计分读 `humanIds()` 得空数组——真人赢了 0 分 | 浏览器实测（探测 WebSocket 认输链路）：结算页正确但段位卡停在 0 胜 | `afterEngine` 当场快照 `humanMembers`（c87bd51），e2e 回归（6f1e7bd） |
| 2 | `rankFlash` 已入 store 但界面无渲染点 | 走查 | ResultSheet 增加段位变动行 |
| 3 | 段位榜打开后永不加载（`refresh()` 无人调） | 浏览器快照 | `onMounted` 判 stale 自动拉一次 |
| 4 | P3 弹层插进 `v-if/v-else-if` 链导致大厅常驻"对局进行中"占位段 | 浏览器快照 | 弹层移出链外并留注释 |
| 5 | 满员但 MMR 闸住的队列被电脑补位，真人计分局被污染成补位局 | 评审自查 | `tick()` 满员被闸 `continue`，永不零电脑强补 |
| 6 | `afterSeat` 旧调用残留 4 参 `formGroup` | tsc TS2554 | 统一签名 |

## 三、验证

- 单测/集成：shared 109 · server 360（新增 profile 13、hub-p3 10、
  matchmaking 分桶 6、p3.e2e 真实 socket 3）· client 88。全绿。
- 类型：server `tsc --noEmit`、client `vue-tsc --noEmit` 干净。
- 浏览器实测（桌面 + 375×812）：实时匹配 → 摆放 → 探测端认输 →
  结算页"段位 +1 星 · 列兵 2★" → 段位卡"第 1 赛季 · 2 胜" →
  战绩页两局"胜 +1" → 段位榜"1 神秘的白鹭 列兵 2★ 2 胜"；控制台无报错。

## 四、整枝评审（合并前，子代理独立评审 master..p3-ranks）

结论"需修复后合并"，全部按裁定处理（提交 3f5f150）：

| 级别 | 发现 | 处置 |
|------|------|------|
| blocker | 满员且分桶互不兼容的队列被闸门卡死：既不成组也跳过补位，永久排队 | 跨桶改按桶距逐级放宽（gap×15s），去掉"永不放行"；补回归测试 |
| major | 晋级 +40 MMR 微调（spec 明文）漏实现 | 补进 applyOutcome + 单测 |
| minor | 直启进程无 SIGINT/SIGTERM，落盘只在程序化 close | main 挂信号 → close() |
| minor | profiles.json 非原子写 + 损坏静默空启动 | temp+rename 原子写；非 ENOENT 记 console.error |
| minor | 练习桌没传 preset，战绩档位恒"标准" | newTable 补传 |
| minor | view 下发 recent 截 10 条（spec 20 条） | 改 RECENT_MAX |
| minor | 入队 MMR 快照跨季不刷新 | 接受：影响一轮匹配，语义一致性问题，P4 匹配优化时一并处理 |
| 口径 | epoch UTC、保星提前一场、rankChanged 字段、rankListRequest 命名、元帅降满星 | spec §廿一 回写实现裁定 |

评审确认无问题：隐私不变量（榜单无 playerId、档案只回本人）、协议校验面
（新消息零参数 + auth 门禁）、幂等键服务端生成、客户端 store 无跨局泄漏。

## 五、已知边界（P3 首版口径，均写入 spec）

- 中途离开者不计分也不记战绩。
- 胜负按名次判（duel 即 1/2 名），不看击落细节。
- 好友桌完全不进档案；补位局 record 但 delta 0。
- 账号绑定（微信）仅留 `bindAccount` 接口位，P4 接入。
