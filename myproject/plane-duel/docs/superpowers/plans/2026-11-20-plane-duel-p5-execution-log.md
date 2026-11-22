# P5 执行日志：工程线部署加固（2026-11-20）

设计见 spec §廿三。分支 `p5-deploy`，合并于 75d90af。
范围决策：资质线（uni-app/商店/真广告 SDK）等凭据，出界；本轮做工程线——目标"重启不丢玩家金币"。
用户指示本机不用 Docker，验收改用生产进程直跑（行为与容器内一致）。

## 交付内容

| 块 | 内容 | 验证 |
|---|---|---|
| 优雅停机 | `Hub.shutdown()`：排队 + 已记桌门票全退（§廿二.3 流局同语义，根治 P4 已知限制 1）；close() 时序=退款→1001 断连→1s terminate 残留→最后 flush | p5.deploy 4 例 + 实跑 |
| 信号入口修复 | 信号处理+8s 看门狗挪到 index.ts——**实跑发现 P4 的优雅停机从未生效**（挂在 main.ts isEntrypoint 块，生产走 index.ts 永不执行；测试自调 close() 所以全绿） | 实跑 SIGTERM |
| 探活 | `GET /healthz` → 200 ok（容忍查询串） | p5.deploy 1 例 + curl |
| 配置 | `PROFILES_FILE` env；compose：`./data` 卷、healthcheck(wget/busybox 可用)、stop_grace_period 15s、web 等 healthy | 评审确认 |
| 部署文档 | deploy/README（三步半 + 数据卷权限）+ deploy/smoke.mjs（queue/check/play 冒烟） | 实跑使用 |

## 关键发现

1. **P4 优雅停机是死代码**：SIGTERM 落默认处理器直接杀进程。测试全绿的原因是 e2e 用
   `srv.close()` 而不是真信号。教训：进程生命周期行为要在真进程真信号下验。
2. **flush 时序**（评审 #1 major）：ws 断开会派生 `hub.disconnect → melee 判负 → scoreTable`
   写盘；flush 放在断连之前会把那批金币/段位丢在防抖窗口里。现在 flush 收尾。
3. **ws.close 不等于断开**（评审 #2 major）：半开僵尸不 ACK，`wss.close` 要等 30s
   closeTimeout。加 1s `terminate()` 强杀，close() 有界、退出码 0。

## 整枝评审处置（7 项，0456043）

| # | 级别 | 处置 |
|---|---|---|
| 1 | major | flush 挪到全部连接关闭之后（见"关键发现 2"） |
| 2 | major | 1s 后 terminate 残留连接（见"关键发现 3"）；测试用的活客户端覆盖不到半开路径，强杀定时器保证有界 |
| 3 | minor | 新增档案写盘回环测试（close→flush→重装载余额 50，"重启不丢金币"上 CI） |
| 4 | minor | `flush()` 包 try/catch：卷权限/磁盘满留痕不崩服（防抖回调里未捕获异常会带走进程） |
| 5 | minor | 停机/流局白占日配额：与既有 sync() 口径一致，记录不改 |
| 6 | minor | main.ts 头注释：生产入口必须 index.ts |
| 7 | minor | /healthz 容忍 `?` |

评审明确干净：双退/漏退（两 Map 互斥 + 快照遍历）、shutdown 与 tick 竞态（clearInterval 先行）、
shutdown 抢在 sync() 前收口不重复退、/healthz 与 ws upgrade 共存、busybox wget、重复 close() 安全。

## 测试与实跑

- shared **123** / server **384**（34 文件）/ client **95**；tsc×3 干净；server 3× 全套无 flake。
- 生产进程直跑（NODE_ENV=production tsx src/index.ts + PROFILES_FILE + SIGTERM）：
  - 排队付票 → SIGTERM：客户端收 1001，档案 `login,ticket-fee,ticket-refund` 齐账余额 50 ✔
  - 两人打完一局（各 +5）→ SIGTERM → 重启 → 重连档案各 55 ✔（含同日登录礼不重发）
  - /healthz 200、404 正常 ✔
- compose（卷/healthcheck/停期）配置就绪，待部署机 `docker compose ps` 见 healthy（本机按指示未跑 Docker）。

## 已知限制

1. 在途对局跨重启不恢复（§九 既定，§廿三.4 有意不做）。
2. compose 编排未在本机实跑（用户指示不用 Docker）；healthcheck 命令、卷路径经评审静态确认。
3. 广告 mock、JSON 单进程存储不变（P4 口径）。

## 提交链

spec §廿三 → dbcdddd server+compose → 191969b README → dcf6c48 smoke → 3622cae 信号入口修复 → 06099c6 验收记录 → 0456043 评审 7 项 → 75d90af merge master。
