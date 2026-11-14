# QA 第二轮：两个 bug 修复、依赖重构、上一轮未跑的部分

- **状态**：待执行
- **目标读者**：Cursor（执行）、项目负责人（验收结论）
- **上一轮**：[`QA-PERF-PATHS.md`](QA-PERF-PATHS.md) / [`QA-PERF-PATHS-RESULT.md`](QA-PERF-PATHS-RESULT.md)
- **本轮部署版本**：`d1211a5`，生产已验证 `API=200 PAGE=200 SHARING=True`

## 0. 这一轮为什么值得测

上一轮交了 5 项证据和 2 个真 bug。这两个 bug **已经修了**，但修复方式本身引入了新的风险：

1. **`stream_message` 被程序化重排了缩进**（整个回合体包进 `try/finally`）。
   缩进错了能编译、能过测试，但可能让某一分支永不执行。这是本轮最该盯的地方。
2. **DeerFlow 从 submodule 改成了「wheel 依赖 + 按需拉取源码」**。
   依赖声明动了，`--check` 的语义也动了。

另外上一轮 **T6 端到端没跑**，本轮补上。

## 1. 基线

```bash
cd docs/myproject/job-come/backend/server
PYTHONPATH=$(cd ../../../.. && pwd)/libs/agentkit/src \
  JC_BOOTSTRAP_SKIP_REEXEC=1 /Users/gqli/work/deepagents/venv/bin/python \
  -m pytest tests -q                     # 997 passed

cd ../../../../libs/agentkit
PYTHONPATH=src /Users/gqli/work/deepagents/venv/bin/python -m pytest tests -q   # 41 passed
```

## 2. 任务

### T1（最高）两个 bug 修复必须「能红」

**1a. 在途回合计数器**

`agent_turns_in_flight` 现在声明为 `multiprocess_mode="livesum"`。原来的 `all` 模式
下，`mark_process_dead` 不删文件，死 worker 的值永远留在合并结果里。

测法：一个进程把 gauge 抬到 3 后调 `mark_worker_exit()` 退出，另一个进程留 1 个在途，
第三个进程读合并快照 → 必须是 **1**，不是 4。

变异验证：把 `livesum` 改回 `{}`（默认 `all`），测试必须红。

**1b. 流中异常不丢 pending_rows**

`stream_message` 回合体已包进 `try/finally`，flush 走 `_flush_pending_rows`。

变异验证（至少两个）：
- 把 `finally` 里的 flush 删掉 → `test_exception_mid_turn_still_persists_accumulated_rows` 必须红
- 把 `finally` 里的 `_turn_span.__exit__` 删掉 → 在途 gauge 必须不归零

**1c. 取消场景**

`_flush_pending_rows` 用了 `asyncio.shield`，声称任务被取消时仍能写入。
这条**没有测试**。要证明：一个已被 `cancel()` 的任务在 `finally` 里 flush，
行仍然落库（或者明确记录它确实会丢，并说明为什么可接受）。

### T2（最高）`stream_message` 重排后行为没变

整个回合体被加了 4 空格缩进。请**逐分支确认**：
- 面试回合（`interview_turn=True`）走 `run_mock_turn` 分支，不是模型分支
- `flow_reply is None` 仍抛 `AppError`
- `done` 事件仍被 `continue` 掉，不发给客户端
- `system_prompt_rendered` 仍不发给客户端
- `terminal_done` 仍在所有事务提交**之后**才 yield
- `pending_rows` 的声明位置在 `try` 之前（否则 `finally` 看不到它）

建议用覆盖率工具确认这些行真的被执行到，而不是只看测试通过。

### T3（高）依赖重构：新 clone 能构建吗

这是本轮的结构性改动，必须实测，不能推理。

```bash
# 全新目录，模拟别人第一次 clone
git clone <repo> /tmp/jc-fresh && cd /tmp/jc-fresh
# 期望：uv sync 可用（wheel 已在仓库里），不需要源码
# 期望：不要出现 "Please run git submodule update"
```

要验证：
1. `uv sync` 能装完，**不联网拉 DeerFlow 源码**
2. `./scripts/build-release.sh --check` 会自动拉源码到 `.data/vendor/`
3. 拉到的 commit == `backend/server/wheels/DEERFLOW_SOURCE.txt` 里记录的那个
4. `.data/vendor` 不在 git 里（`git status` 干净）
5. 把 `DEERFLOW_SOURCE.txt` 的 SHA 改错一位 → 必须**明确报错**，不是静默用错版本
6. 断网时 `--check` 失败信息说清是网络问题，不是「文件不存在」

**不要**在没有网络的环境下硬跑完整个流程——记录失败点在哪即可。

### T4（高）配置文件被误改的防护

`DEERFLOW_SOURCE.txt` 是纯文本，格式错（少一列、多空格、注释混进去）会怎样？
`ensure_deerflow_source` 里是 `read -r url sha < <(grep -vE '^\s*(#|$)' ... | tail -1)`。

请测：空文件、只有注释、只有 URL 没 SHA、URL 非 http(s)、SHA 是垃圾字符串。
每种都要**明确失败**并说清楚哪里错，不能"拉了个奇怪的 commit 然后继续构建"。

### T5（中）端到端真实回合（上一轮欠的）

本地起服务（sqlite 即可），跑一轮带工具调用的对话：

1. 发消息 → 收完整 SSE 流
2. 查 `jc_agent_trace`：**同一回合 seq 连续、无重复、无空洞**
3. 查 `jc_llm_call`：有对应记录（证明审计队列真的落库）
4. 中途 abort → 已产生的行仍可读到
5. 对比：批量写之后，一个回合约几次 `commit()`（给数字，不是"少了"）

### T6（中）上一轮结论复核

上一轮报的 3 条「仍然看起来对」现在状态如何：

| 项 | 上轮结论 | 本轮要回答 |
|---|---|---|
| T2 并发 seq | sqlite 上撞 UNIQUE，生产靠 Postgres 行锁 | **仍未连生产库验证**，如实写 |
| `mark_worker_exit` | 对 histogram 无效 | 已改为只承诺 live gauge；确认注释与行为一致 |
| T6 端到端 | 未跑 | 由 T5 补 |

## 3. 不要做的事

- **不要连生产数据库**。所有测试用 sqlite 或 fake。
- **不要改生产 `.env`，不要重启生产服务**。
- **不要为了让测试通过而放宽断言**。写不出「能红」的版本就说明原因。
- 不要为了适配测试而改 `libs/agentkit` 的公开 API。
- **不要动 `.data/vendor/`**（那是按需拉取的构建输入，删了会自动重拉，但别手动改内容）。

## 4. 交付物

1. 新增/修改的测试文件清单
2. **T1、T2 每一项的变异测试记录**（改坏 → 红 → 改回）
3. T3 的完整命令与输出（fresh clone 能不能构建，要有原始日志）
4. 一份结论：**哪几条真的验证过，哪几条仍然只是「看起来对」**
5. 真 bug 单独列，别顺手修完再一起报

## 5. 已知、不必再报

- `backend.sh` 每次启动清空 mmap 目录 —— 有意
- ADR-010 里 `enable_multiprocess` 的描述 —— 已加修正说明，保留原文是刻意的
- `vendor/deer-flow` 落后上游 101 个提交 —— 已知，升级是独立决定
