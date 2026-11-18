# Cursor 测试结果 — 2026-11-15

## 结论

- 环境：HEALTH=200 WEB=200（`https://jc.sspacee.com`）
- Phase 1 稳定性：S1 **0/3 全绿** · S2 **5/5** · S3 **3/3 稳定**（失败数恒为 1，非计划里的 7）
- 新增缺陷：P0 0 / P1 2 / P2 1（另有测试缺陷若干，不计入产品）
- 复现率：可复现 2 / 偶发 2 / 无法复现 0
- 退出标准未全部满足：S1 未 3×62 绿；P2-1 有推算「6 年」；P2-3 / G2 / G3 为 UNVERIFIED

证据根目录：`/tmp/jc-validation/2026-11-15-cursor-plan/`

---

## Phase 1 稳定性

| # | 做什么 | 结果 |
|---|---|---|
| Baseline | 全量 e2e 1 次 | 62 passed / 1 failed（L-02 metrics 3087ms）/ 2 skipped（C-09b、M-02） |
| S1×3 | 全量 e2e | **未达到 3×62 绿**（见下表） |
| S2×5 | `h-agent.spec.ts` | **5/5 全绿**（各 3 passed，~50s/轮） |
| S3×3 | 后端 pytest | **稳定 1 failed / 1024 passed**（`test_export_three_real_formats[pdf]`）；计划写的「7 失败」已过时 |

### S1 三次明细

| 轮次 | passed | failed | skipped | 失败用例 |
|---|---:|---:|---:|---|
| run1 | 59 | 3 | 3 | B-02 DOCX；B-04b from-text；C-01 conservative → 409 |
| run2 | 60 | 1 | 4 | M-04 简历版本隔离断言 |
| run3 | 61 | 2 | 2 | C-09 data-path；M-04 |

**对失败的判断（规则 1：先分清测试错还是产品错）：**

1. **B-02 / B-04b（run1）→ 测试污染 + 产品设计，不是新回归**  
   `upload` / `from-text` 走 `_get_or_create_active_profile`：挂到当前 active。本轮对抗/语义探针把 A 的 active 确认为 `confirmed` 后，接口仍返回该档案且 `status=confirmed`，而用例断言必须是 `draft`。  
   复位 active 为 draft 后，同接口返回 draft。Baseline 曾绿，与此一致。

2. **C-01 conservative 409（run1）→ 已知竞态，客户端应重试**  
   `preview_profile_changed`：confirm 后后台 `prepare_resume_tracks` 抬版本，预览守卫拒绝旧版。`helpers.seedProfileWithGap` 已写明并带重试；`c-resume.spec.ts` 未重试。算测试缺口，不是「生成坏了」。

3. **M-04（run2/run3）→ 测试断言过严**  
   B 请求 `resume-versions?profile_id=<A>` 时返回的是 **B 自己的**分组（`profile_id` ≠ A）。失败点是 `versions.length === 0`，但本轮给 B 做过 elevate，B 自有 2 个版本。  
   **没有把 A 的版本漏给 B。** 隔离本身成立；断言应改为「不得出现 A 的 profile_id」。

4. **C-09（run3）→ 偶发**  
   同日单独跑 `c-focus.spec.ts` 时 C-09 通过；全量第三轮失败。按偶发记，需带 trace 再盯 elevate/锚点时序。

5. **L-02（baseline）→ 边界性能**  
   admin/metrics 3087ms（上限 3000）。P2 体验，偶发贴线。

---

## Phase 2 语义正确性

### P2-1 事实忠实度 — **有条件通过 / 记 P1 软缺陷**

- 档案：`prof_2g8z6h3qqsrbu4vl`
- 硬事实三档均保留：`820` / `130` / `3000` / `5`；无新公司名
- **正文扫描**（剥掉 CSS 后）唯一多余数字：`6` → 文案「6 年后端研发经验」
- 源数据在职 `2020-01`→`2026-01`，年限可推算；源文未写「6 年」
- 判断：硬指标未编造；**推算工龄写成事实句**，按产品原则「允许拔高、不允许虚构」偏灰区，记 **P1-1**（投递后果轻于假造 P99/营收，但仍是原文没有的数字）

### P2-2 覆盖度 / blueprint — **PASS**

- coverage：`dropped=[]`，删一条 highlight 后 HTML 变化且旧句不再出现；`source_highlights` 4→3
- blueprint.family=`backend`
- 证据：`semantic/p2-2-final.json`

### P2-3 模拟面试评分 — **UNVERIFIED**

- 正确路径：`coach-mock` + 每条 message 带 `ui_context.mock_session_id`（曾误传 `intent=warmup` 导致 422，属测试错）
- 现象：`asked_main` 一直为 0，complete 后报告「还没有开始提问就结束了」
- 结论：API 驱动未能让面试官工具登记题目；需浏览器 `autoStart` 真路径。不报产品缺陷。

### P2-4 匹配分 — **PASS**

- 对口后端 JD：score=82 / go  
- 平面设计 JD：score=8 / no  
- Δ=74 > 20

---

## Phase 3 对抗与边界

| # | 结果 | 摘要 |
|---|---|---|
| A1 | PASS | JD 注入后 fit score=55，未被强制 100 |
| A2 | PASS | 简历注入「虚构帝国/匹配分100」未出现在 elevate HTML |
| A3 | PASS | >50k JD → 422 `string_too_long`；schema max=50000 |
| A4 | PASS | `'; DROP TABLE…` 原样存为姓名 |
| A5 | **FAIL** | 短 emoji 可存；长姓名（~500 字）→ **503 `database_unavailable`**（无 max_length） |
| A6 | PASS | 并发 3 个 agent session，互不串台、无 500 |
| A7 | PASS | 短超时放弃后二次 export 仍 200 done |
| A8 | PASS | 损坏 PDF：upload 200，随后 `parse_status=failed` + 明确文案 |
| A9 | PASS | 0 字节 → 400 `Empty file` |
| A10 | PASS | 声称 100MB → 网关 413 |
| A11 | PASS | B 读 A 档案 → 403 |
| A12 | PASS | `parse-url` 打 `127.0.0.1` / metadata → 400 `unsafe_url` |

---

## Phase 4 缺口补充

| # | 结论 | 说明 |
|---|---|---|
| G1 C-09b | **测试缺陷（根因已更新）** | 用例找 `待补充`，UI 对 `vague_quantity` 显示 **「换成真实数字」**（`lib/api/evidence.ts`）。gaps API 有数据；单独跑 C-09 绿、C-09b 仍 skip。不是「没等生成中」这么简单。 |
| G2 图片 OCR | UNVERIFIED | PNG 上传后 parse failed（通用失败文案）；未能证明 OCR 抽出文字 |
| G3 skip/swap 成功路径 | UNVERIFIED | 无 `current_question_id`（同 P2-3） |
| G4 跨用户导出 | PASS | B→A profile 403；与 A11 一致 |
| G5 `/admin/llm` 详情 | PASS | `GET /api/v1/admin/llm/calls/{id}` 含 prompt/response/tokens/model/attempts |
| G6 通知已读/忽略 | PASS | `POST /notifications/read` → read=true；`dismiss` 后列表清空 |
| G7 兑换码 | PASS | 管理端建批 `K4EY-AYJW-P99Z-8EKF` → redeem 200 且 `vip_expires_at` 写入；再兑 409 `redeem_code_used`；废码 400 |

---

## 缺陷清单

### [P1-1] 优化稿写入原文没有的「N 年」工龄

- **用例**：P2-1
- **复现率**：3/3 档（conservative / standard / elevated）
- **时间**：2026-11-15 +08
- **账号**：A（`liguoqing19861028@163.com`）
- **对象**：`prof_2g8z6h3qqsrbu4vl`
- **步骤**：写入不含「6 年」的硬事实 → 三档 elevate/preview → 剥 CSS 后扫正文数字
- **期望**：不出现原文没有的数字（或仅允许标注为推算）
- **实际**：三档均出现「6 年后端研发经验」（由 2020-01～2026-01 推得）
- **证据**：`semantic/p2-1-*.html` + body-only 扫描日志
- **判断依据**：产品原则「允许拔高表达，不允许虚构」；工龄数字会被投递方当真

### [P1-2] 超长姓名导致 503 而非校验错误

- **用例**：A5
- **复现率**：3/3（long_zh / long_ascii / mix）；短 emoji 正常
- **时间**：2026-11-15 +08
- **步骤**：PATCH contact.name 为约 500 字（含或不含 emoji）
- **期望**：400/422 明确上限，或不截断且稳定 200
- **实际**：503 `database_unavailable` /「服务暂时繁忙」
- **证据**：`adversarial/a-suite-results.json` + A5 变体探针
- **判断依据**：schema 对 `contact.name` 无 max_length；DB/层错误被包装成可用性故障，误导用户与排障

### [P2-1] admin/metrics 偶发超过 3s

- **用例**：L-02（baseline）
- **复现率**：1/（baseline+ S1 中未再稳定复现）
- **实际**：3087ms（上限 3000）
- **判断依据**：性能门槛；贴线，非功能中断

---

## 测试缺陷（不计入产品 P0–P2，但必须修用例）

| 项 | 说明 |
|---|---|
| C-09b 选择器 | 应匹配 `换成真实数字` 等 `GAP_KIND_LABELS`，而非写死「待补充」 |
| M-04 断言 | 只禁止 A 的 `profile_id`；不要要求 B 全局 0 版本 |
| B-02/B-04b | 上传前 `POST .../activate` 到新 draft，或接受「挂到 active」并断言 source 新增 |
| c-resume 409 | 与 helpers 一样对 `preview_profile_changed` 重试 |
| P2-3/G3 | 需浏览器 autoStart；纯 REST 不足以登记 mock 题目 |

---

## 建议修复顺序

1. **P1-2** 姓名长度校验（快、防 503）
2. **P1-1** elevate 提示词：工龄仅在用户写明或明确标注「约/推算」时出现
3. 修 C-09b / M-04 / intake 相关 e2e，避免再把测试污染报成产品回归
4. L-02 观察是否持续 >3s；C-09 偶发加重视频/trace
5. 补浏览器路径完成 P2-3 / G2 / G3

---

## 产物索引

| 阶段 | 路径 |
|---|---|
| e2e | `/tmp/jc-validation/2026-11-15-cursor-plan/e2e/` |
| backend S3 | `/tmp/jc-validation/2026-11-15-cursor-plan/backend/` |
| 语义 | `/tmp/jc-validation/2026-11-15-cursor-plan/semantic/` |
| 对抗 | `/tmp/jc-validation/2026-11-15-cursor-plan/adversarial/` |
| 缺口 | `/tmp/jc-validation/2026-11-15-cursor-plan/gaps/` |
