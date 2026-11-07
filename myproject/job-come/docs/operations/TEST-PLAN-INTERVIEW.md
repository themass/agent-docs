# TEST-PLAN-INTERVIEW：模拟面试与站点的测试方案

- **版本**：2026-11-08
- **适用**：模拟面试（面试教练）、报告、登录与站点页面。面向线上的实测也用这份方案。
- **原则**：每个场景都有编号。能用代码验证的，必须有自动化测试；只能靠真实模型或真人判断的，写成实测步骤，并写明通过标准和证据。

## 一、层次

| 层 | 跑什么 | 在哪跑 | 何时跑 |
|---|---|---|---|
| L1 单元/服务 | 守卫、记录、验收检查、提示词、报告计算 | `backend/server`，`pytest` | 每次提交 |
| L2 接口/路由 | 消息路由的参数传递、SSE 结束规则 | `pytest` | 每次提交 |
| L3 前端逻辑 | 重试、请求体、导出流程 | `frontend/web`，`node --test` | 每次提交 |
| L4 构建 | 类型检查、生产构建 | `tsc --noEmit`、`npm run build` | 每次提交 |
| L5 实测（线上） | 真浏览器、真模型、真数据 | Cursor 或 Playwright，按第四节执行 | 每次发布后 |
| L6 人工判断 | 面试官的语气、追问质量、报告的建议是否具体 | 人读记录 | 每次发布后抽查 |

## 二、自动化场景（L1–L4）

每条都标了对应的测试文件。改动相关代码时，这些测试必须全部通过。

### 2.1 面试守卫（服务端）

| 编号 | 场景 | 期望 | 测试 |
|---|---|---|---|
| G-01 | 同一档案再开一场，旧的进行中场次被结束 | 旧场次状态 completed，`ended_reason=superseded`，`ended_early=True` | `test_mock_supersede.py::test_a_new_round_ends_the_running_one_of_the_same_profile` |
| G-02 | 任何时候同一档案最多一场进行中 | 连开三场，只有一场 active | `test_mock_supersede.py::test_only_one_session_of_a_profile_is_ever_running` |
| G-03 | 其它档案的进行中场次不受影响 | 另一档案的 active 保持 | `test_mock_supersede.py::test_another_profiles_running_session_is_left_alone` |
| G-04 | 被取代的场次保留已问的题 | `asked` 不丢失 | `test_mock_supersede.py::test_the_superseded_session_keeps_what_was_said` |
| G-05 | 完整模拟每月只能一次，被拒时不留下场次 | 403，场次数不变 | `test_mock_quota_creation.py` |
| G-06 | 热身不受额度限制 | 三场热身都能开 | `test_mock_quota_creation.py` |
| G-07 | 级别必填，无推荐也未传则拒绝 | 409 `mock_level_required` | `test_mock_level.py` |
| G-08 | 当前题只能是最后一道、未跳过、未回答的题 | 跳过/换题只对它生效 | `test_mock_guard.py` |
| G-09 | 跳过的题不计入覆盖，但计入主问题上限 | 覆盖数不增，上限照算 | `test_mock_guard.py::test_a_skipped_question_still_counts_toward_the_main_limit` |
| G-10 | 换题每场最多三次 | 第四次被拒 `swap_limit` | `test_mock_guard.py::test_swap_takes_the_question_back_and_is_limited_to_three` |
| G-11 | 换题后不记录后续话到旧题 | 换题后 `table_closed` | `test_mock_answer_recorder.py::test_nothing_is_recorded_after_a_swap` |
| G-12 | 结束前必须问完必备项，或被明确拒绝 | `uncovered` 拒绝 | `test_mock_guard.py::test_end_is_refused_while_a_must_have_is_unasked_and_under_the_limit` |
| G-13 | 候选人提问环节开启后不再出新题 | 拒绝 `candidate_qa_open` | `test_mock_stages.py` |
| G-14 | 候选人说“结束”时，若已到提问环节，按完成处理 | `completed` | `test_mock_stages.py::test_the_candidate_pressing_end_after_their_own_turn_has_finished_the_interview` |
| G-15 | 长时间无新题（24 小时）自动以未完成结束 | `timeout` | `test_mock_guard.py::test_session_idle_for_a_day_is_ended_as_timeout_and_refuses_more_questions` |

### 2.2 回答记录

| 编号 | 场景 | 期望 | 测试 |
|---|---|---|---|
| R-01 | 候选人的话记到当前题上 | 一条回答，挂在该题 | `test_mock_answer_recorder.py::test_the_first_message_after_a_question_becomes_its_answer` |
| R-02 | 同一题的连续消息追加到同一条回答 | 文字拼接 | `test_mock_answer_recorder.py` |
| R-03 | 闲聊、“下一题”“结束”这类操控语不记为回答 | 不写入 | `test_mock_answer_recorder.py::test_a_message_that_only_steers_the_interview_is_not_an_answer` |
| R-04 | 自我介绍（没有当前题时）不记为回答 | 不写入 | `test_mock_answer_recorder.py::test_a_turn_before_any_question_records_nothing_but_still_runs` |
| R-05 | 同一条消息重发（同一 `client_message_id`）只记一次 | 一条 | `test_mock_answer_recorder.py::test_a_message_sent_again_with_the_same_id_is_recorded_once` |
| R-06 | 不同 id 的相同文字是两条消息 | 两段 | `test_mock_answer_recorder.py::test_two_messages_with_different_ids_are_both_the_answer_even_if_the_words_match` |
| R-07 | 恢复历史会话（上下文不带场次）时，仍记到所属面试 | 记到当前题 | `test_mock_answer_recorder.py::test_a_reopened_chat_without_the_interview_in_its_context_still_records_the_answer` |
| R-08 | 恢复的会话若面试已结束，不记录 | 无记录，无报错 | `test_mock_answer_recorder.py::test_a_reopened_chat_does_not_record_into_an_interview_that_has_ended` |
| R-09 | 其它角色的聊天不会被匹配到面试 | 无记录 | `test_mock_answer_recorder.py::test_a_chat_of_another_role_is_never_matched_to_an_interview` |
| R-10 | 消息路由把 `client_message_id` 传到服务 | 传递正确 | `test_mock_answer_recorder.py::test_the_message_route_hands_the_clients_message_id_to_the_service` |

### 2.3 面试官的规则（验收检查）

| 编号 | 场景 | 期望 | 测试 |
|---|---|---|---|
| I-01 | 开场问候、说明安排、请自我介绍 | 通过 | `test_acceptance_checks.py::test_a_good_interview_passes_every_check` |
| I-02 | 开场没请自我介绍 | 未通过 | `test_acceptance_checks.py::test_not_greeting_and_asking_for_a_self_introduction_is_caught` |
| I-03 | 开场没报公司名（岗位有公司时） | 未通过 | `test_acceptance_checks.py::test_the_opening_must_name_the_company_when_the_job_has_one` |
| I-04 | 一条消息两个问号 | 未通过 | `test_acceptance_checks.py::test_two_question_marks_in_one_reply_is_already_two_questions` |
| I-05 | 问之前没有先登记 | 未通过 | `test_acceptance_checks.py::test_asking_before_registering_is_caught` |
| I-06 | 追问没有引用候选人的话 | 未通过 | `test_acceptance_checks.py::test_a_follow_up_that_does_not_use_the_candidates_words_is_caught` |
| I-07 | 评价候选人（“很好”“不错”） | 未通过 | `test_acceptance_checks.py::test_judging_the_answer_out_loud_is_caught` |
| I-08 | 面试官的规则写进了技能说明 | 三条规则存在 | `test_interview_prompts.py::test_the_interviewer_must_name_the_company_and_quote_only_what_was_said` |
| I-09 | 提示词里要求一次一题 | 存在 | `test_interview_prompts.py` |

### 2.4 报告

| 编号 | 场景 | 期望 | 测试 |
|---|---|---|---|
| P-01 | 结束后进入后台生成队列 | `queued`，之后 `ready` | `test_mock_report_queue.py` |
| P-02 | 没有任何提问的场次，报告直接失败且不运行评审 | `failed`，不可重试 | `test_mock_report_queue.py` |
| P-03 | 报告有、旧场次补齐状态 | `ready` / `failed` 正确 | `a48221d` 的迁移测试，`test_mock_report_queue.py` |
| P-04 | 报告状态接口：待定、失败、可重试、已生成 | 与状态一致 | `test_mock_report_status.py` |
| P-05 | 重试次数用尽时拒绝 | 409 | `test_mock_report_status.py` |
| P-06 | 各维度均分只计有分的维度 | 未评分不计入 | `test_mock_report_service.py`、`test_report_insights.py` |
| P-07 | 准备度由代码计算，不由模型决定 | 与分数一致 | `test_report_conclusion.py::test_the_tier_follows_the_mean_with_the_lower_bound_included` |
| P-08 | 报告页：结束原因标签、各维度标题、未评分说明 | 显示中文正确 | 前端实测（见第四节 E6） |

### 2.5 流式输出与长时间无回复

| 编号 | 场景 | 期望 | 测试 |
|---|---|---|---|
| S-01 | 正常的事件流原样输出 | 不被改动 | `test_sse_silence_limit.py::test_a_finished_run_passes_through_untouched` |
| S-02 | 运行长时间没有实际事件，以错误结束 | 出现“模型长时间没有回复”错误 | `test_sse_silence_limit.py::test_a_run_silent_past_the_limit_ends_with_an_error_not_a_hang` |
| S-03 | 心跳不会让挂起的运行保持存活 | 最终仍以错误结束 | `test_sse_silence_limit.py::test_pings_from_the_heartbeat_do_not_keep_a_hung_run_alive` |
| S-04 | 正常但较慢的事件不被误杀 | 正常完成 | `test_sse_silence_limit.py::test_a_slow_but_real_event_within_the_limit_is_not_cut_off` |

### 2.6 前端

| 编号 | 场景 | 期望 | 测试 |
|---|---|---|---|
| F-01 | 重试沿用原消息的 id | 同一 id | `agent-retry.test.cjs` |
| F-02 | 请求体带上 `client_message_id` | 正确 | `agent-message-id.test.cjs` |
| F-03 | 导出流程：审查、确认、导出、错误、进度 | 11 项通过 | `resume-quality-flow.test.cjs` |
| F-04 | 类型检查 | 无错误 | `npx tsc --noEmit` |

## 三、运行方式

```bash
# L1–L2：后端
cd myproject/job-come/backend/server && python -m pytest -q

# L3：前端逻辑
cd myproject/job-come/frontend/web && node --test tests/*.cjs tests/*.mjs

# L4：类型检查与构建
cd myproject/job-come/frontend/web && npx tsc --noEmit && npm run build
```

破坏性检查（确认测试真的在守护规则）：对每条规则，临时把实现改坏，确认对应测试变红，再恢复。这次修复中每一条都做过。

## 四、实测（L5，线上或测试环境）

每条要有证据：页面原文、截图或接口返回。以下对应上一轮 Cursor 的报告编号。

| 编号 | 场景 | 步骤 | 通过标准 | 上一轮结果 |
|---|---|---|---|---|
| E-01 | 开场报公司名 | 开始一场热身，发送“你好，我准备好了…” | 第一条回复含公司名和岗位名 | 未通过（缺公司名） |
| E-02 | 一次一题 | 每条回复数问号 | 每条最多一个问号 | 未通过（两个问号） |
| E-03 | 追问引用原话，不编造 | 发送三段回答，检查追问 | 追问含候选人本场的词，不说“你提过的”引用未说过的事 | 未通过（引用题库旧题） |
| E-04 | 跳过 | 面试官提问后点“跳过” | 当前题被标记跳过，面试官出下一题 | 未通过 |
| E-05 | 换一题 | 面试官提问后点“换一题” | 按钮可用，次数减一，出新题 | 未通过（按钮禁用） |
| E-06 | 候选人提问环节 | 按热身题数答完，等面试官进入提问 | 面试官问“你有什么想问我的吗”；JD 内的问题按 JD 答，JD 外说“需要和团队确认” | 未测（上一轮未走完） |
| E-07 | 结束面试 | 任意时刻点“结束面试”并确认 | 面试官给出结束语，说明报告由独立评审生成；页面出现报告入口 | 未通过（缺结束语，按钮时机） |
| E-08 | 恢复历史会话后回答仍被记录 | 同一页开场，回答两段，刷新，从历史选中，再回答一段，结束 | 报告里有刷新前后的回答 | 已通过 |
| E-09 | 长时间无回复 | 如出现转圈，记录开始时间 | 10 分钟内以错误结束，或正常回复 | 未出现，未验证 |
| E-10 | 同一档案只有一场进行中 | 开一场，不结束，再开一场 | 旧场次被结束，新场次可用 | 未通过（叠加多场） |
| E-11 | 报告的级别表述 | 打开热身报告 | 准备度文字与级别的说明一致 | 设计如此，需决定（见第五节） |
| E-12 | 报告各维度 | 打开报告 | 标题为“各维度得分”；未评分的维度为“—”并有说明 | 未通过（已改，待实测） |
| E-13 | 404 页面 | 打开不存在的地址 | 中文页面，有回首页入口 | 未通过（已改，待实测） |
| E-14 | 登录与账号 | 错误密码、正确登录、登出、重发验证邮件（最多 2 次） | 提示正确，状态正确 | 通过 |
| E-15 | 公开页面 | 首页、登录、条款、隐私、会员、联系、关于 | 都能打开，无报错 | 通过 |
| E-16 | 岗位与匹配 | 已有岗位列表；粘贴新 JD | 解析成功，分数与说明一致 | 通过 |
| E-17 | 档案 | 打开档案 | 内容完整；占位文字如实显示 | 通过 |
| E-18 | 归档与题库 | 面试归档、题库 | 场次状态正确，题库可打开 | 通过 |
| E-19 | 反馈表单 | 打开，不提交 | 表单结构正确 | 通过 |

### 4.1 实测的数据与边界

- 测试账号：通过环境变量提供，不写入文件或报告。
- 每次实测最多 3 场面试，都要以“结束面试”收尾，不留下进行中的场次。
- 不做支付、会员、退款；不修改他人数据；管理后台只读；验证邮件最多 2 次。
- 模型服务返回 503 时，停止面试相关用例，记录原文。

### 4.2 每次实测后要检查的数据

- 测试账号下没有进行中的场次（只有一场可以留着，并说明）。
- 本次新开的场次都是“提前结束”或“正常结束”，没有遗留。
- 报告状态都到了 ready 或 failed。

## 五、需要决定的事项

1. **E-11 准备度的级别表述**：目前写“按专家的要求：还需大量准备”。SPEC §3.5 设计上让级别影响准备度的措辞，但测试者读起来会以为级别改变了判断。需要决定：保留，还是改成中性措辞。
2. **E-06 候选人提问环节**：实测时必须走完热身题数，不能提前“结束本轮”。
3. **E-09 长时间无回复**：根本原因未确定。上限只是兜底，不是修复。

## 六、变更与复核

- 每次修改面试相关代码，先更新本方案对应的编号，再写测试，最后跑通第三节的命令。
- 每次发布后，至少跑 E-01 到 E-10 这几条实测。
- 本方案中“上一轮结果”一列在每次实测后更新，不删除旧结果。
