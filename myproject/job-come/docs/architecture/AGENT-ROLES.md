# 角色、技能与工具（现行设计）

状态：已实施，见 [ADR-006](../decisions/ADR-006-roles-skills-tools.md)。依据 2026-11-04 的代码。
上位文档：[AGENTS-DESIGN.md](AGENTS-DESIGN.md)（产品承诺与隔离规则）。
本文只回答三件事：每个 AI 步骤是哪个角色、角色由哪些技能组成、技能用哪些工具。

## 1. 三个概念，各自只在一处定义

| 概念 | 是什么 | 定义在哪 |
|---|---|---|
| 工具 tool | 运行时能执行的函数；签名就是模型看到的 schema | `backend/server/src/jc/mcp/server.py`（唯一定义） |
| 技能 skill | 一种工作方法：契约正文、常驻方法论片段、它允许用的工具 | `backend/agent/skills/public/<id>/SKILL.md` 与 `references/` |
| 角色 role | 一个智能体：产品、是否对外、运行方式、模型场景，以及它拥有的技能和切换规则 | `backend/agent/roles.yaml` |

依赖只向下：角色拥有技能，技能声明工具，工具只存在于服务端。

## 2. 三条运行规则

1. **每次运行的系统层都包含该技能的正文和常驻片段。** 由 `JCProductRulesMiddleware` 在每次模型调用时叠加到系统消息上，不写进历史。
2. **一次运行只以一个技能运行，只持有该技能的工具。** 技能在一轮里由角色的 `switch` 规则决定；会话的角色不变。
3. **子任务由服务在确定时机启动，模型不决定何时启动。** 没有模型自主委派（`task` 工具未启用）。

## 3. 运行方式

| 运行方式 | 怎样被调用 | 有工具 | 模型 |
|---|---|---|---|
| `session` | 用户与它来回对话（会话） | 是，按当前技能 | DeerFlow 模型 `jc-<scenario>` |
| `subtask` | 服务在确定时机启动一次独立运行（`jc.agent.subtask.run_subtask`），结论由工具写回 | 是 | DeerFlow 模型 `jc-<scenario>` |
| `single` | 一次模型调用，技能正文即提示词（`jc.agent.single.run_single`） | 否 | 路由场景 `scenario`（不经 DeerFlow） |

## 4. 角色

| 角色 | 产品 | 对外 | 运行方式 | 场景 | 技能（第一个为默认） | 切换 |
|---|---|---|---|---|---|---|
| `resume-coach` 简历顾问 | resume | 是（默认） | session | `coach` | `resume-coach`，`profile-interview` | 档案不足时 → `profile-interview`（`profile_cannot_generate`） |
| `coach-mock` 面试教练 | interview | 是 | session | `coach` | `coach-mock`，`coach-archive` | 页面意图为归档时 → `coach-archive`（`intent_archive`） |
| `apply-pipeline` 投递经理 | apply | 是 | session，计划模式 | `coach` | `apply-pipeline` | 无 |
| `interview-reviewer` 独立评审 | interview | 否 | subtask（预算 300 秒） | `reviewer` | `interview-reviewer` | 无 |
| `resume-reviewer` 导出质检 | resume | 否 | subtask（90 秒） | `flash` | `resume-reviewer` | 无 |
| `resume-writer` 简历撰写 | resume | 否 | single | `writer` | `resume-writer` | 无 |
| `jd-parser` JD 解析 | shared | 否 | single | `ingest_fast` | `jd-parser` | 无 |
| `fit-scorer` 匹配度评分 | shared | 否 | single | `flash` | `fit-scorer` | 无 |
| `localize` 档案互译 | resume | 否 | single | `flash` | `localize` | 无 |
| `profile-structurer` 文本结构化 | resume | 否 | single | `ingest_fast` | `profile-structurer` | 无 |
| `profile-vision` 图片识别 | resume | 否 | single | `vision` | `profile-vision` | 无 |

- 对外的三个角色是唯一可以开会话的角色（`entry: true`），其中简历顾问是默认角色（`default: true`）。
- 切换规则的判定函数与轮次上下文提供者都注册在 `backend/server/src/jc/agent/turn.py`；角色只写它们的名字。
- 面试记录（`coach-archive`）只在页面带 `intent=archive` 时启用，入口在面试记录页的「让面试教练帮我记」。

## 5. 技能与工具

技能的 `allowed-tools` 是它允许使用的工具（一次运行的工具面 = 该技能的 `allowed-tools`，由宿主执行）。
`metadata.always-loaded` 是每次组合都带上的 `references/` 片段，`metadata.borrow-family-from` 是岗位族片段的借用来源。

| 技能 | 工具（allowed-tools） | 常驻片段 | 备注 |
|---|---|---|---|
| `resume-coach` | `jc_profile_photo_set` `jc_profile_get` `jc_profile_patch` `jc_intake_plan` | `method` | 借用 `resume-writer` 的岗位族片段；`framing` 为会话任务 |
| `profile-interview` | 上面四个加 `jc_intake_record` | `method` | 同上 |
| `coach-mock` | `jc_profile_get` `jc_bank_search_questions` `jc_question_upsert` `jc_answer_save_attempt` `jc_mock_session_history` `jc_mock_plan` `jc_mock_ask` `jc_mock_end` | — | 不持有评分或报告工具 |
| `coach-archive` | `jc_profile_get` `jc_question_upsert` `jc_interview_save` | — | 记录真实面试 |
| `apply-pipeline` | `jc_profile_get` `jc_job_fetch` `jc_job_parse` `jc_fit_score` `jc_profile_patch` `jc_apply_pipeline` | — | 不持有简历工具；简历经 `jc_apply_pipeline` 在服务内完成 |
| `interview-reviewer` | `jc_profile_get` `jc_mock_session_history` `jc_mock_report_write` | `rubric`（五维量表，也由 `/coach/rubric/mock` 提供） | 不持有提问或结束工具 |
| `resume-reviewer` | `jc_resume_review_read` `jc_resume_review_write` | `severity` `method` `structure` `evidence` | 结论只能经 `jc_resume_review_write` 写入 |
| `resume-writer` | — | `structure` `method` `targeting` | 单次调用；岗位族与定性片段按请求选择 |
| `jd-parser` | — | — | 正文即提示词 |
| `fit-scorer` | — | — | 正文即提示词 |
| `localize` | — | — | 正文即提示词 |
| `profile-structurer` | — | — | 正文即提示词 |
| `profile-vision` | — | — | 正文即提示词 |

工具共 19 个，全部定义在 `jc.mcp.server`。`jc.agent.tool_catalog.catalog()` 从服务端派生目录（去掉身份参数），
管理端清单读的也是它。进程内调用（测试、评审子任务的单元测试）经 `jc.mcp.handlers.dispatch_tool`，
走的是同一个包装函数。

## 6. 子任务与导出质检

导出前质检是 `resume-reviewer` 子任务：

1. 服务对草稿的每条轨道做预检（档案缺失、未启用模型、输入超长等直接标为不可用，不启动子任务）；
2. 清空草稿上旧的结论，释放本次请求的数据库连接，启动子任务（预算 90 秒）；
3. 子任务用 `jc_resume_review_read` 读取各轨道，用 `jc_resume_review_write` 一次写入全部轨道的结论；
4. 服务重新读取草稿中的结论，与确定性的规则检查合并。

结论的契约、哪些问题阻断导出、以及"没有结论不等于不通过"的规则，都在 `backend/server/src/jc/services/resume_reviewer.py`。

面试评审与此相同：模拟面试的报告在第一次被读取时，由服务启动 `interview-reviewer` 子任务生成，结论经 `jc_mock_report_write` 写入。

## 7. 已删除的机制（不要恢复，除非有明确需求）

| 删除的内容 | 原因 |
|---|---|
| 子 agent 与 `task` 委派（`custom_agents`、`subagent_enabled`、`allowed_subagents`） | 没有需要模型自主协作的场景；子任务改由服务启动 |
| `jc_mock_review` 工具 | 评审由服务在报告被读取时启动，不再依赖教练记得调用 |
| `jc_resume_review` 工具 | 由 `jc_resume_review_read` 与 `jc_resume_review_write` 取代 |
| `coach-answer` 技能 | 没有入口，工具已在 `coach-mock` 中 |
| `coach/followups.py` 及其资料 | 没有调用方 |
| `backend/agent/prompts/` 目录 | 每个提示词都是技能包或已删除 |
| 扩展配置中的技能开关 | 技能是否可用由角色声明决定 |
| 会话的 `kind`（resume / coach） | 侧栏按智能体分组，`role_id` 已表达这一点（迁移 022 删除列） |
| `max_turns` | 没有任何运行时读取它 |
| 空实现的 MCP 拦截器 | 没有行为 |

## 8. 已决定的事项

- **会话的 `kind` 已删除**：侧栏与列表按智能体（`role_id`）分组。
- **不恢复模型自主委派**：子任务只由服务启动。
- **导出质检使用 `flash` 场景**（模型 `jc-flash`），与子任务化之前一致；延迟与成本以真实数据再评估。

## 9. 仍然开放的事项

- **真实模型的端到端验证**：委派之外的子任务（导出质检、面试报告）、切换（档案访谈、面试记录）、双语草稿的两条轨道。需要有密钥的环境。
- **智能体名称在前端与后端各有一份**：前端 `lib/agents.ts` 的 `roleId` 与后端 `roles.yaml` 的角色 id 需要保持一致；目前靠约定，尚无测试。
- **每轮的 `skill_hint`**（运行元数据与 LLM 调用日志）：名字来自 agentkit 的 `AgentRunMetadata`，保留。
