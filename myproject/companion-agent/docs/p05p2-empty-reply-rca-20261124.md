# 服务端空回复（`said=''`）取证与 cue 守卫修复（2026-11-24）

对应线：Android 仓 `docs/design/p05p2-proc-table-20261123.md` 「服务端空回复」类。
状态：**取证闭环；守卫泄漏已修并已部署 104（2026-11-25 逐文件 sha256 取证，见下）；报告归因一处更正**。

## 结论先行

104 `voice.log`（2026-11-18 17:02 → 11-24 05:00 UTC，1085 条 `voice reply`）按日志字段拆开：

| 形态 | 条数 | 定性 |
|---|---|---|
| `interrupted=True said=''` | 853 | 用户插话关闭生成器（barge-in），设计语义、非缺陷，是指标噪声 |
| `interrupted=False said=''` | 52 | 真·服务端空回复候选，机制 A/B/C 见下 |
| 非空 | 180 | 正常；含 1 条残片 `']}'` —— 机制 B 的生产样本 |

### 机制 B（本次修复）：cue 片段闭合后的 `]}` 残尾被当正文朗读

生产样本 AJ_BcdK2kYZvAzf 05:07:23：`voice reply … interrupted=False said=']}'` →
`tts start` → 3× `volcengine tts server error: No readable text!` →
`tts done … frames=0`。用户听到的就是静默；日志上的「空回复」实为残片。
全日志残片 `said` 仅此一种（`']}'`）；「No readable text」8 条、分布在 2 个 job。

路径：模型在 cue JSON 行之后吐出未配平的 `]}`（收尾污染）。`CueJsonGuard` 交付
完整片段后，把闭合后的尾巴原样放给断句器——`]}` 成了正文，进字幕、`speech.seg`
与 TTS。对 HEAD 版守卫做逐 chunk 切分模糊测试（8 blob × 36000 切分）稳定复现。

修复：片段闭合后置 `_after_close` 位，紧随其后的「空白 + `]`/`}`」残尾直接丢弃；
其余正文（含 `，然后。` 这类真文本）原样放行。RED 3 → GREEN（第 4 条跨 chunk
用例随修复设计补入）；重跑 36k 模糊切分零泄漏。

### 机制 A（已修已部署，B2 线）：零输出回合不收流

provider 空 completion → `turn_runner._finish` else 分支不发收尾事件 → 语音
`tokens()` 熬满 120s 超时。全日志确证 **1** 例：AJ_r5CAD 11-20 12:39，
`total_ms=122012` + 唯一一条 `voice turn timed out`。9292391 已修（发
`error(empty_completion)` 两端立即收流），已随 11-24 部署在 104 生效。

### 机制 C（未修，待下次拨测计数）：merged 跟随者拿不到游标前的 delta

`PlatformBrain` 的事件游标在**本条消息** submit 前取（`tail_event_id`）：MERGED
进活跃回合的语音订阅天然看不到此前已飞过的 delta——去重设计，首发订阅者念。
当该回合的首发订阅者被 barge-in 关闭（`interrupted=True said=''`）、末位订阅者
游标后又没有 delta，这条回合的回复**谁都没念过**，日志形状正是
`interrupted=False said=''`。AJ_jMmvz 13:50:10（merged 链尾，7892ms）是这个形状。
52 条里除去 A/B 的余下部分大概率是它；现存日志无法与 A/B 区分。
21db8a2 的 `voice turn stream end … event=… deltas=N`（已部署）下次拨测可直接
计数。**未修**——机械地修等于重放已念内容（复读风险），属产品决策，留给
P0.5/P2 owner。

## 报告归因更正（proc-table 第 10 行）

`b3a67d32`（job `AJ_r2VuLzGL8Dj6`，22:51:02–22:53:09）尾部 70s remote 全零
**不是**服务端空回复样本：14:51:53（UTC）之后该 job **没有任何
`voice turn`/`voice reply` 行**——用户 `inbound user_state=speaking` 跳变在、
`volc asr push summary` 在（frames=2500 peak_max=1.0），但没有 ASR final →
无回合 → 无 TTS → 远端全零。应归 F16「无 ASR final」类（与同表第 77 行
AJ_npFDTG/AJ_jMmvz 同型）。报告里「↔ 104 后续 `said=''`」所引的行属于
**另一个 job**（AJ_kbC6MhFCJTtY，14:30–14:32），且那三条全是
`interrupted=True` 的 barge-in 行。

## 验证

- 新守卫用例 4 条：`test_closer_tail_after_a_fragment_is_not_spoken`、
  `test_closed_fragment_followed_by_junk_then_real_prose`、
  `test_closer_tail_after_a_rejected_object_is_dropped_too` 在 HEAD 守卫下
  RED 且复现生产值 `']}'`；`test_closer_junk_spanning_chunk_boundary_is_dropped`
  随修复设计补入（未单独跑 HEAD）。修复后 GREEN（`test_json_guard.py` 38 passed）。
- `test_turns.py`（TurnPipeline 全套）同跑：51 passed。
- 模糊切分（8 blob × 8~9 段 × 500 随机切点 = 36000）：修复前复现 `']}'`，
  修复后零泄漏。
- 全套件（`COMPANION_TEST_REDIS_URL=redis://127.0.0.1:6399/0`）：见提交时记录。

## 边界

- 取证只读：只引用现存 `voice.log`，未取新生产数据、未做生产重放。
- `_gate` 与 speech 语义未动；`interrupted=True` 的计数语义未动（其噪声身份
  已在表里列明）。

## 部署取证（2026-11-25，机制 B 守卫已上 104）

原「随下一次 publish 上车」的口径已被更强的取证取代：

- 104 `agent-docs-stage5` 克隆 `git fetch` 后 `origin/main`=当时 tip；**逐文件 sha256**
  把 `origin/main:myproject/companion-agent/server/src/**` 与
  `/home/web/webroot/companion-agent/server/src/**` 全量比对 —— 零 DIFF、零 MISS，
  即生产源码内容 == main tip（publish 走文件级拷贝，克隆 HEAD 落后不代表内容落后）。
- `.../agent/text/json_guard.py` 里 `_strip_closer_junk` 命中 2 处（定义 + 调用）——
  机制 B 的守卫代码确在生产文件里。
- `companion-voice.service`：active，MainPID=1415288，`ExecMainStart` 2026-11-24
  19:44:17 UTC（同刻 `capacity.py` mtime 19:44）——守卫随那次发布+重启已进运行进程。

**待验证（不等同于已生效）**：上车后「`No readable text!`」应归零、残片 `said`（`']}'`）
不应再出现——这两条按 11-24 19:44 UTC 之后的 `voice.log` grep 才算实锤，本次取证只证
「代码已在生产进程」，不证「生产已复现消失」。
