# QA 第三轮：全面验证 —— 监控面板 + 生产可用性

- **状态**：待执行
- **目标读者**：Cursor（执行）、项目负责人（验收结论）
- **前序**：[`QA-PERF-PATHS.md`](QA-PERF-PATHS.md)、[`QA-ROUND2.md`](QA-ROUND2.md)
- **生产**：`http://127.0.0.1:8000`（API）、`:3001`（Web），当前 `API=200 WEB=200`

## 0. 这一轮为什么必须做

监控面板**从来没被人真正打开过**。已确认的事实：

- 后端 `/metrics/snapshot` 有数据（5 个指标族）
- 前端 `/admin/metrics` 返回 200
- **但没有任何一次「用管理员身份登录后看页面」的验证**
- 面板要求 `User.role == admin`，而用来产生数据的测试账号 `usr_jy5hibag3ea04p77`
  是普通用户 —— 也就是说：**产生数据的人没有权限看面板，能看面板的人还没看过**

所以「页面 200」只证明路由存在，不证明它渲染正确、数据对得上、切换可用。

已核实的面板数据源（`page.tsx` 只读这 6 个族，全部 JC 有记录）：

```
llm_calls  llm_call_duration_seconds  llm_attempts_per_call
agent_turns  agent_turns_in_flight  agent_phase_duration_seconds
```

但有两个**已经能看出来的缺口**，本轮要确认它们的实际后果：

- `llm_tokens` **有记录但没有任何面板展示**（`record_llm_metrics` 收了
  prompt/completion tokens 并累加它）—— 也就是说 token 用量和成本在面板上看不见
- `method_duration_seconds` / `method_calls_total` 在 agentkit 有定义，但 JC
  **从未调用 `@method_metrics`**（全仓无一处）—— 这两个族永远是空的

- `agent_turns_in_flight` 在多 worker 下是 `livesum`，需要确认合并后的值对不对

## 1. 基线

```bash
cd docs/myproject/job-come/backend/server
PYTHONPATH=../../../../libs/agentkit/src JC_BOOTSTRAP_SKIP_REEXEC=1 \
  /Users/gqli/work/deepagents/venv/bin/python -m pytest tests -q      # 997 passed

cd ../../../../libs/agentkit && PYTHONPATH=src \
  /Users/gqli/work/deepagents/venv/bin/python -m pytest tests -q      # 41 passed
```

生产：`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health` → 200

## 2. 任务（按优先级）

### V1（最高）面板真的能显示数据

这是本轮的核心，**必须截图或输出真实 DOM 文本作为证据**，不能只说「返回 200」。

步骤：
1. 需要一个 admin 账号。生产上把现有测试账号提权：
   `UPDATE jc_user SET role='admin' WHERE id='usr_jy5hibag3ea04p77'`
   （**只在生产库执行这一条，执行完记录并保留**；不要改其他行）
2. 用这个账号登录，打开 `/admin/metrics`
3. 跑一轮真实对话（发一条 agent 消息）
4. 回到面板刷新，确认：

| 面板 | 期望 | 实际是否出现 |
|---|---|---|
| 模型调用 | 次数 > 0 | |
| 模型失败 | 有值 | |
| 回合数 | > 0 | |
| 在途回合 | 回到 0 | |
| 模型调用耗时分布 | 有柱子 | |
| 回合分段耗时 | ttft / generate / turn 至少一个 | |
| 按场景的模型耗时 | `coach` 出现 | |
| 按模型的调用次数 | `gpt-6-luna` 或 `glm-5.3-flash` | |
| 故障转移次数 | 有桶 | |
| 失败原因 | 无失败时显示「没有失败记录」 | |

**每一项都要记录「有数据 / 空 / 报错」**，空的要说明是「本来就没数据」还是「代码没接上」。

### V2（最高）该显示但没显示的东西

面板只渲染 6 个族，已核实全部有记录。所以本轮要问的不是「哪个面板会空」，
而是**有没有重要的东西被做出来却没人看**：

1. **`llm_tokens` 有数据、没有面板**。发一条长消息后再看 `snapshot()`：
   `llm_tokens` 里的 `direction="input"/"output"` 是否有值？
   如果有，说明 token 用量是**可得的但没有展示** —— 这是一个功能缺口，不是 bug，
   请如实记录，不要自己加面板。
2. **`method_*` 永远是空的**。确认全仓确实没有 `@method_metrics`，并说明
   这意味着什么（agentkit 提供了能力，JC 没用）。
3. 逐个面板确认「空状态」与「有数据」在界面上**确实不同**：把某个族从
   `snapshot()` 里过滤掉（不要改产品代码，用假数据构造），确认渲染出 `emptyLabel`
   而不是一根零长度的柱子 —— 零长度柱子会被误读成「很健康」。

第 3 点最重要：面板区分不了「没有数据」和「数值是 0」，就是会骗人。

### V3（高）多 worker 合并是不是真的

生产是 `--workers 2`。两个 worker 各有独立 registry，靠
`PROMETHEUS_MULTIPROC_DIR` 合并。

要验证：
1. `/metrics/snapshot` 里的 `sharing_across_processes` 是 `true`
2. `.data/metrics-multiprocess/` 里能看到**两个不同 pid** 的文件
3. 连续发两条消息（可能落到不同 worker），`llm_calls` 总数 = 2，不是 1
4. 杀掉一个 worker，`agent_turns_in_flight` 不长留（`livesum` 生效）

### V4（高）面板的安全边界

- 普通用户（非 admin）访问 `/admin/metrics` → 必须 403，且错误文案是中文可读
- 未登录 → 401
- `/metrics/snapshot` 是**公开**的（无鉴权），确认它**不含**任何用户数据：
  - 不能出现 user_id、session_id、prompt 文本、错误消息
  - 只能有 scenario / model / phase / status 这类闭集标签
  这一条要真的 grep 输出，不能推断。

### V5（中）生产健康

连续发若干条消息，确认：
- `agent_turns_in_flight` 每次都回 0（不会因异常泄漏）
- 有失败回合时，`agent_turns{status="error"}` 增长，且面板「失败原因」有内容
- 进程用户是 `web`（不是 root）：`ps -eo user,cmd | grep uvicorn`
- `.data` 下无 root 属主文件：`find .data -user root | wc -l` → 0

### V6（中）上一轮遗留

| 项 | 要回答 |
|---|---|
| `stream_message` 重排后分支完整性 | 面试回合（`interview_turn`）分支是否还能走通 |
| `asyncio.shield` 取消时 flush | 取消回合，已产生的行是否落库 |
| `DEERFLOW_SOURCE.txt` 写错 | 改错 SHA 一位，`build-release.sh --check` 是否明确失败 |

## 3. 不要做的事

- **不要改生产 `.env`**（`JC_METRICS_PEERS` 保持空）
- **不要重启生产服务**，除非为了恢复你弄坏的东西
- 除了 V1 那一条 `UPDATE jc_user`，**不要改生产数据库**
- 不要为了让面板「看起来有数据」而伪造指标
- 发现真 bug 单独列，别顺手修

## 4. 交付物

1. **面板每个 Pane 的实际状态表**（有数据 / 空 / 错），带证据
2. V2 的结论：**哪些面板的数据源 JC 永远不会产生**（这可能是设计缺陷）
3. V3 的多进程证据（文件里的两个 pid）
4. V4 的 snapshot 输出，证明无用户数据
5. 一份「能上线 / 不能上线」的判断，说明依据

## 5. 已知、不必再报

- `backend.sh` 已加防 root 检查（`af2a128`）
- `vendor/deer-flow` 落后上游 101 commit，升级是独立决定
- 生产测试账号 `usr_jy5hibag3ea04p77` 是刻意保留的
- `/metrics/snapshot` 无鉴权是刻意的（Prometheus 抓不到 cookie），
  但凡它含用户数据就是 bug —— 见 V4
