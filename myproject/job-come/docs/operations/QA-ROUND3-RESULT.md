# QA-ROUND3 执行结论

- **状态**：已执行（2026-11-14 / 15）
- **任务书**：`docs/operations/QA-ROUND3.md`（commit `f169259`）
- **证据目录**：`/tmp/jc-validation/2026-11-14-round3/`
- **结论（go/no-go）**：**不能把监控面板当可用能力上线**。核心 API/Web 仍 `200`，但 `/api/v1/admin/metrics` 对管理员直接 `500`，面板第一次真看就是「服务暂时不可用」；且 `agent_turns_in_flight` 已粘在 `3.0`、死 worker 的 livesum 文件不清理。修 `settings` 未导入 + inflight/livesum 泄漏前，面板不可信。

## 0. 基线

| 项 | 结果 |
|---|---|
| 生产 `http://127.0.0.1:8000/health` | `200` |
| 生产 Web `:3001` | `200` |
| server pytest | **996 passed / 1 failed**（`test_export_lifecycle[pdf]`，与本轮无关） |
| agentkit pytest（`docs/libs/agentkit`） | **41 passed** |
| 提权 | `UPDATE jc_user SET role='admin' WHERE id='usr_jy5hibag3ea04p77'` — 执行前已是 admin / ROWCOUNT 1（`admin-promote.txt`） |
| 会话 | `sess_ef61fd70ca181b5a9a8257878cf11e3c` → `usr_jy5hibag3ea04p77` |

## 1. V1 面板真看一眼（核心）

### 生产实态（未改代码）

管理员 cookie 打开 `https://jc.sspacee.com/admin/metrics`：

- 页面壳 `200`，文案：**「服务暂时不可用，请稍后重试。」**
- `/api/v1/admin/metrics` → **500**
- 根因（部署文件与本地一致）：`admin_router.admin_metrics` 使用 `settings.jc_metrics_*`，**文件顶部没有** `from jc.config import settings` → `NameError`
- 证据：`r3-metrics-natural-500.png`、`panel-natural.txt`、部署源码片段（`admin_metrics` L329/L331）

### 用真实 snapshot 验证「面板会不会画对」（route fulfill，未伪造指标数值）

因 API 500，按约定把公开 `/metrics/snapshot` **原样 reshape** 成 admin 响应，用 Playwright `page.route` fulfill（`admin-metrics-fulfilled.json`）。数值来自生产，不是手编。

| 面板 | 期望 | 实际（fulfill + 真实 snapshot） | 证据 |
|---|---|---|---|
| 模型调用 | >0 | **有数据：2**（随后生产对话涨到 6+） | `panel-filled.txt` / `r3-metrics-filled.png` |
| 模型失败 | 有值 | **0**（无 error 序列） | 同上 |
| 回合数 | >0 | **2** | 同上 |
| 在途回合 | 回到 0 | **1（粘住）** → 后升到 **3.0** | 同上 + snapshot |
| 模型调用耗时分布 | 有柱子 | **有：8s–10s / 10s–15s** | 同上 |
| 回合分段耗时 | ttft/generate/turn | **有：首字 13s / 整回合 12s / 生成 2.7s** | 同上 |
| 按场景的模型耗时 | coach | **coach 11s** | 同上 |
| 按模型的调用次数 | gpt-6-luna / glm | **gpt-6-luna 2** | 同上 |
| 故障转移次数 | 有桶 | **有：0ms–1s ×2** | 同上 |
| 失败原因 | 无失败时 emptyLabel | **「没有失败记录」** | 同上 |

**V1 判定**：UI 组件能正确吃 6 个族；**生产链路却因 500 从未把数据送到浏览器**。第一次真看 = 失败页。

## 2. V2 该显示却没显示 / 空 vs 零

1. **`llm_tokens`**
   - 生产 snapshot **始终无** `llm_tokens` 族（发长消息后仍 ABSENT）。
   - SSE `usage` 事件是 `prompt_tokens=0, completion_tokens=0`（`chat4.txt`）→ 即使面板加了 token 图，当前生产也收不到用量。
   - 代码路径：`record_llm_metrics` / audit_hook 会累加 tokens；**面板 page.tsx 只读 6 族，本来就不展示** → 功能缺口（任务书已点名）+ 当前采集值为 0。
2. **`method_duration_seconds` / `method_calls_total`**
   - 全仓除 `tests/test_observability.py` 外 **无** `@method_metrics` / `method_metrics(` 调用。
   - agentkit 有能力，JC 业务路径未接 → **这两族永远空**（设计缺口，不是面板 bug）。
3. **空状态 vs 零**
   - `families={}` fulfill（`r3-metrics-empty.png`）：柱状图均 **「暂无数据」**；StatTile 模型调用/回合/在途为 **「—」**；失败原因 **「没有失败记录」**。
   - **例外**：「模型失败」在无 `llm_calls` 时仍显示 **`0`**（`llmFailures` 找不到 error → 写死 `"0"`），会被读成「很健康」。这是任务书警告的骗人形态，只影响这一格。

## 3. V3 多 worker 合并

| 检查 | 结果 |
|---|---|
| `sharing_across_processes` | **true** |
| multiproc 目录 | `/home/web/webroot/job-come/.data/metrics-multiprocess` |
| 存活 worker | 父 `3495695` + 两 spawn（曾为 `3517899`/`3518019`） |
| 目录内 pid | **多于 2**：残留 `3495700/3495701/3501654/3511857/...` 的 counter/gauge/histogram |
| 连续两条消息 | `llm_calls` **4→6**（合并计数生效，不是卡在单 worker） |
| kill 一个 worker | 父进程立刻拉起新 worker；**`agent_turns_in_flight` 仍为 3.0**；死 pid 的 `gauge_livesum_*.db` **未删**（`v3-kill.txt`） |

**V3 判定**：counter 合并大体可用；**livesum / mark_worker_exit 在生产未兑现**（与 PERF-PATHS 已记 bug 一致）。

## 4. V4 安全边界

| 场景 | 结果 | 证据 |
|---|---|---|
| 未登录 `/api/v1/admin/metrics` | **401** `login_required` / 「请先登录后再继续。」 | `v4-unauth.txt` |
| 普通用户（新注册 `role=user`） | **403** `admin_role_required` / 「需要管理员权限才能访问此页面。」 | `v4-403.txt` |
| 普通用户打开 `/admin/metrics` 页 | HTML `200`，前端落到简历顾问（无管理壳） | `v4-page-nonadmin.txt` / `r3-metrics-nonadmin.png` |
| 公开 `/metrics/snapshot` | 无鉴权；标签闭集 `application/env/error_type/le/model/outcome/phase/role/scenario/status`；grep **无** `usr_`/`sess_`/`agsn_` | `snap-post.json` / `v2-v3-v5-probe.txt` |

## 5. V5 生产健康

| 项 | 结果 |
|---|---|
| `agent_turns_in_flight` 回 0 | **否** — 粘在 **3.0**（成功对话后仍不降） |
| 失败回合 / 失败原因面板 | 本轮未人为制造 error；现有失败原因 emptyLabel 正常 |
| 进程用户 | **web**（uvicorn / next-server） |
| `.data` root 属主 | **0** |
| 杀 worker 后 health | 仍 **200** |

## 6. V6 上一轮遗留

| 项 | 结论 |
|---|---|
| `stream_message` 面试分支 | 代码仍完整：`interview_turn` → `record_mock_answer` / `run_mock_turn`（`agent_service.py` ~379–483）。本轮未再跑完整 mock 面试 E2E。 |
| `asyncio.shield` 取消 flush | `test_exception_mid_turn_still_persists_accumulated_rows` **PASS**（不再是 xfail）— mid-turn 异常会 flush pending soft rows。 |
| `DEERFLOW_SOURCE.txt` 改错一位 | `--check` **仍 exit 0 且全部 ok**。原因：`ensure_deerflow_source` 在 vendor 目录已存在时 **直接 return**，不核对文件里的 SHA。**改错 SHA 不会失败** — 仍是真 bug。 |

## 7. 真 bug / 缺口清单（未顺手修）

1. **`admin_metrics` 未导入 `settings` → 管理员面板 500**（P0，本轮核心）。
2. **`agent_turns_in_flight` 生产粘住 >0**（泄漏 / 未 dec；与死 worker livesum 残留叠加）。
3. **死 worker 的 multiproc 文件不清理**；kill 后 livesum 不降（`mark_worker_exit` 无效/未调用）。
4. **「模型失败」空数据时显示 0 而非 —**（empty vs zero）。
5. **`llm_tokens` 无面板 + 生产 usage 常为 0**（缺口 + 采集疑点）。
6. **`method_*` JC 从未接线**（能力闲置）。
7. **`build-release.sh --check` 不校验 `DEERFLOW_SOURCE.txt` SHA**（vendor 已在即跳过）。

## 8. 本轮做过 / 没做

- 做过：提权（仅允许的一条）、mint admin session、真实对话、fulfill 面板截图、非管理员注册验 403、杀一 worker、DEERFLOW SHA 翻转试验。
- 没做：改产品代码 / 部署 / 重启整站 / 改 `.env` / 伪造指标数值。
- 杀单个 uvicorn worker 仅用于 V3 livesum 验证；父进程已自动补齐，health 仍 200。
