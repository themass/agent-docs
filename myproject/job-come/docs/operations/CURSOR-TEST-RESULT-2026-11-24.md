# Cursor 测试执行结果 — 2026-11-24（重新部署后 3 轮）

在 2026-11-24 部署（repo `058912c`，含 push 的 `441faf8`）后的 prod 上重跑 3 轮：
R journey（档案修改）+ M/X（mock 面试）+ E 系列（图片/语音直传）+ E1b（真实 JPEG 视觉）。
账号前缀 `cursor-r3-*`，合成简历/JD，测后 purge（dry 预览 → apply）。

## 结论

**产品侧 0 失败。** 三轮全部通过（R5 无自然失败、未做故障注入，记 N/A）。

| 轮 | 用例 | 结果 |
|---|---|---|
| R | R1 确认后改 P99（上轮 FAIL 的 P0：非目标经历被抹掉） | **PASS**（修复确认） |
| R | R2 拒绝确认卡不落库 | PASS |
| R | R3 version 冲突不被旧确认卡静默覆盖 | PASS |
| R | R4 禁虚构（虚构 B 轮融资不落库） | PASS |
| R | R5 故障注入 | N/A |
| R | R6 刷新后历史/确认对账（cmid 唯一、确认事件在案） | PASS |
| M/X | M1 最短全路径（开场引用 JD、逐题、报告 ready）+ M2–M8（拒答 skip、配额等） | 全部 PASS |
| M/X | X1/X2 异常路径 | 全部 PASS |
| E | E1 sign→PUT→绑定+助手回复、历史无 data:image | PASS |
| E | E2 download_url 可打开 | PASS |
| E | E3 未上传 key 绑定被拒（4xx） | PASS |
| E | E4 声明 jpeg 实为 png：错 CT PUT 拒 / 魔数绑定拒 | PASS |
| E | E7 语音直传 + transcript 落附件 | PASS |
| E | E8 跨用户 key 绑定被拒 | PASS |
| E | E9 4×7MB 总量超限 4xx、无半态 | PASS |
| E1b | 真实 JPEG（PIL 生成「JC VISION 42」）→ 助手原样读出图中文字 | **PASS** |

对比 2026-11-19 R3 那轮的失败：R1 P0 与 P1-1（超限附件 200+断流，已在 `agent_router` 前置校验修掉）本轮均复验为 PASS。

## 未闭环项（不在本轮范围）

- 验收 pilot（2026-11-24，backend 一族，见 [CURSOR-TEST-RESULT-2026-11-19-R3.md](CURSOR-TEST-RESULT-2026-11-19-R3.md) 「验收 pilot」节）的 2 条 machine 失败
  `follow_up_quotes_the_candidate`、`no_questions_after_candidate_turn`：未复测、仍未分类（模型行为 vs 清单过严）。
- 广告 key 相关工作（用户单独决定节奏）。

## 测试工具自身的问题（如实记录）

1. **purge 脚本对象删除 bug**：对同步的 `agentkit.storage.ObjectStore.delete_object(key)` 误用 `await`，11 个对象全部
   `OBJ_DEL_FAIL TypeError`（`OBJ_DELETED 0`）。DB 行删除不受影响。改用同步调用后 11 个对象确认删除
   （`jc/prod/uploads/` 前缀 LISTED 0）。`/tmp/jcw/jc-purge.py` 尚未修——下次用前先修。
2. **探针语义坑**：`ObjectStore.head_object_size` 对不存在的 key 返回 `None` 而非抛异常——「删除后 HEAD 探测」不能当存在性判据，
   要用 `list_object_keys`。
3. R3 驱动（`run_setup_and_r.py`）从 transcript 恢复时 R3 尾部/R4/R5 块缺失，按 2026-11-19 结果文档口径重写补全。

## 清理

- purge：TARGETS 3（usr_vqqrkrh43mh8e88g / usr_7dtwpc2yt6mg0x0w / usr_jn5qk1obu8f3vwcy），
  12 agent_session / 131 trace / 9 mock_session / 116 llm_call / 3 profile / 5 patch_confirm 删除；
  `TEST_USERS_LEFT 0`；对象 11 个（首轮删除失败后补删成功，bucket `jc/prod/uploads/` 已空）。
- prod 暂存 `/tmp/jcw3`、`/tmp/jcw-purge.py`、`/tmp/jcw-dropobj.py`、`/tmp/jcw3-bundle.tgz` 已删除。
- 证据中的预签名 URL 全部 redact（ADR-011 §7.4）；无真实简历，无面试录音文本入库。
