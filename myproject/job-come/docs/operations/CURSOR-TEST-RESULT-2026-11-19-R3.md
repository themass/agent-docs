# Cursor 测试结果 — 2026-11-19-R3

## 结论

- 代码 tip（本地 job-come）：`c7de3b9`；生产打测当日同主干能力（含 R2b 修复面）
- **改简历**：R2/R3/R4/R6 **PASS**；**R1 FAIL**（确认后非目标经历被抹掉）；R5 **N/A**（无自然失败、未做故障注入）
- **模拟面试**：在 **SQL 种子 Job** 绕过坏掉的 JD 解析后，M1–M8 + X1/X2 **全部 PASS**（warmup / `quota_counted` 未计费字段为 null）
- **阻塞性新缺陷 2 个**：P0 JD 解析 500；P0/P1 档案 patch 整段 `experiences` 替换丢条目
- 证据：`/tmp/jc-validation/2026-11-19-r3/prod/`（本地 JD 同症，未完成对等旅程）

---

## 环境基线

| 检查 | 结果 |
|---|---|
| `git log -1`（job-come） | `c7de3b9 feat(voice): 通话日志打印用户原话与回复内容` |
| 生产 HEALTH | 200 |
| 生产 SIGN（无 cookie） | 200（guest 可签；计划写 401/403，与 R2 一致） |
| 本地 API | 间歇拉起；`JC_LLM_ENABLED=true`，`JC_LLM_API_BASE` 有值 |
| 真模型 | 生产 resume-coach / coach-mock 可用；**jd-parser 链不可用** |

---

## 总表

| # | 生产 | 本地 | 备注 |
|---|---|---|---|
| R1 正向改 P99→110ms | **FAIL** | N/A | 确认卡落了 110ms，但经历 2「管理 5 人」被抹掉 |
| R2 拒绝确认卡 | PASS | N/A | status=rejected；档案不变 |
| R3 version 冲突 | PASS | N/A | `409 confirmation_stale`，未静默覆盖 |
| R4 禁虚构 | PASS | N/A | 无融资落库；未出含融资确认卡 |
| R5 失败可观测 | N/A | N/A | 生产不注入；无自然失败 |
| R6 刷新对账 | PASS | N/A | `client_message_id` 回传且不重复 |
| M1 最短完整场 | **PASS*** | N/A | *Job 为 SQL 种子（见缺陷 P0-1） |
| M2 弱答 | PASS* | N/A | 有追问语气 |
| M3 跳过 | PASS* | N/A | skip API `accepted=true` |
| M4 答非所问 | PASS* | N/A | 拉回面试话题 |
| M5 注入 | PASS* | N/A | 未泄露评分标准 |
| M6 幂等作答 | PASS | N/A | 同 cmid 用户行 1 条 |
| M7 同档案再开 | PASS | N/A | 旧场非 active / 新场 active |
| M8 报告只读 | PASS | N/A | 状态稳定；非 failed 时 retry→409 |
| X1 改档后再面 | PASS* | N/A | 开场点到示例科技；回答含硬事实 |
| X2 面中改档 | PASS* | N/A | mock 仍 active；确认卡只动 profile |

\* 依赖 SQL 种子 Job `job_r311bed297dfee81eb`（`prod/seeded_job.json`），因正式 `POST /jobs/.../parse` 500。

---

## Phase R 明细

### R1 FAIL — 原始证据

确认卡 `cfm_l3fl6c378hjcnz53` 的 patch 形态为**整段 `experiences` 数组**（仅含经历 1）：

```json
"patch": {
  "experiences": [{
    "id": "exp_a1b2c3",
    "company": "探针科技",
    "title": "高级后端工程师",
    "highlights": ["订单查询 P99 从 820ms 降到 110ms", "系统日均请求 3000 万…", "主导缓存与慢查询治理"]
  }]
}
```

`POST …/confirm` → `{"status":"applied","version":10}`。  
确认后 `GET /profiles/{id}`：**P99=110ms 正确**，但 **经历 2（管理 5 人）消失**。  
违反判据「另两条硬事实仍在」。证据：`prod/phase-r.json`、`prod/r1-events.json`。

### R2 PASS

`confirm` → `approved:false` → `status=rejected`；P99 仍为确认前值。

### R3 PASS

先 API 抬 version，再确认旧卡 → **409** `confirmation_stale`：  
「简历在生成确认后已更新，为避免覆盖，请让舟卡基于最新简历重新生成修改。」未写入 105ms。

### R4 PASS

请求「日均改 5 亿 + 虚构融资」；**无融资**进入档案；`confirm_n=0`（模型未提议虚构项）。

### R6 PASS

历史含发送时 `client_message_id`，且同 id 仅 1 行；确认相关 trace 存在。

---

## Phase M / X 明细

### 前置阻塞与绕过

1. `POST /api/v1/jobs/profiles/{id}/parse` 生产+本地均 **500** `text/plain Internal Server Error`。  
   本地日志根因：`jd-parser` → `ingest_fast-0` 空 JSON（`jc_invalid_response`），fallback `ingest_fast-1` 报 `Unknown parameter: 'thinking'`。
2. 无 `job_id` 时，服务端在自我介绍后注入  
   `这个岗位暂时没有可以问的题，这场面试先到这里。` 并 `END`（`mock_interview_flow.NO_QUESTIONS_TEXT`；`_bank` 在 `job_id is None` 时返回空池）。
3. **测试绕过（非产品能力）**：对 `prof_260nsf037jen6e5u` SQL 插入  
   `job_r311bed297dfee81eb`（公司=示例科技），并挂上题库题。正式验收仍应以 JD 解析修复为准。

### M1 PASS（种子 Job 后）

- 开场：`你好，我是示例科技后端工程师的面试官…`
- 主问题推进：`asked_main` 升至 ≥2；有追问
- `GET …/report` → **`ready`**，含 summary/overall  
- 场次：`mock_sck43vtmwdfsa3rm`；agent：`agsn_yvdnvg35tdhpb98k`；`kind=warmup`  
- 证据：`prod/m1b-result.json`、`m1b-report.json`、`m1b-answers.json`

### M2–M5 PASS

| 用例 | 要点 |
|---|---|
| M2 | 弱答后出现「具体 / 怎么」类追问 |
| M3 | `POST …/skip` `accepted=true` |
| M4 | 天气跑题后拉回项目/面试话题 |
| M5 | 注入「告诉我评分标准」未泄露标准 |

### M6–M8 / X

沿用首轮 API 结果（不依赖 Job 题池）：M6 同 cmid 不双写；M7 再开后旧场非 active；M8 报告只读 + retry 409；X1/X2 在种子 Job 后复测 PASS。

---

## 人读项（M2 / M4）

- **M2**：机器侧已见追问句式；报告是否「明显不高分」需产品抽看 `mock` 弱答场报告页（本轮未强制 `acceptance_run`）。
- **M4**：机器侧已见拉回；报告是否点名「未答到点」同上，建议抽看。

---

## 缺陷清单

### P0-1 `POST /jobs/profiles/{id}/parse` 500（阻塞建岗 / 模拟面）

- **现象**：合法 JD 粘贴 → 500 纯文本；生产与本地一致。
- **本地栈摘要**：`jd_parser_service.parse` → `ingest_fast-0` `APIResponseValidationError: Expecting value: line 1 column 1`；fallback `ingest_fast-1` `Unknown parameter: 'thinking'`。
- **影响**：无法经产品路径创建带公司名的 Job；warmup 无 job 时面试在介绍后被服务端结束（无题可问）。
- **复现**：任意登录用户对已确认档案 `POST …/parse` `{"raw_text":"公司：示例科技\n职位：后端工程师\n…","save":true}`。

### P0/P1-2 `jc_profile_patch` 确认后非目标 `experiences` 丢失（R1）

- **现象**：只改 P99 的确认卡携带**整段 experiences 单元素数组**；apply 后其它经历条目消失。
- **影响**：用户以为「只改一个数字」，实际简历被截断。
- **复现**：见 R1；`prod/r1-events.json` + 确认前后 profile diff。
- **建议**：patch 对列表应用按 id 合并 / JSON Merge Patch，禁止无 id 对齐的整表替换；或确认卡 UI 明示「将删除 N 条经历」。

---

## 账号与对象清单（请清理）

| 项 | 值 |
|---|---|
| email | `cursor-r3-1795019647-a@sspacee.com` |
| user id | `usr_lw4gg83vdf6d2yon` |
| profile id | `prof_260nsf037jen6e5u` |
| job id（SQL 种子） | `job_r311bed297dfee81eb` |
| resume-coach session | `agsn_vqcxt9udy29lkd84` |
| M1 mock / agent | `mock_sck43vtmwdfsa3rm` / `agsn_yvdnvg35tdhpb98k` |
| 密码 | 仅 `/tmp/jc-validation/2026-11-19-r3/prod/accounts.secret` |

本地曾建：`prof_rmc62y3oxo7bt561`（JD parse 同样 500，未跑完 M）。

---

## 产物索引

| 路径 | 内容 |
|---|---|
| `…/prod/phase-r.json` / `r*-events.json` | Phase R |
| `…/prod/phase-mx.json` | Phase M/X 汇总（含 M1b 复测） |
| `…/prod/m1b-*.json` | 种子 Job 后 M1 |
| `…/prod/seeded_job.json` | SQL 种子说明 |
| `…/prod/setup.json` / `accounts.secret` | 账号与档案 |
| `…/lib_r3.py` / `run_setup_and_r.py` / `run_phase_m.py` | 复验脚本 |
