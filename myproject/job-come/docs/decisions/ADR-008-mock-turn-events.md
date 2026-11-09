# ADR-008：模拟面试的每一回合是“事件 → 状态转移 → 输出”，不再是补丁链

- **状态**：Proposed（待审阅；审阅通过后按“实施步骤”推进）
- **日期**：2026-11-09
- **取代**：ADR-007 中关于回合处理的部分（`run_turn` 的分支结构与状态写入）。ADR-007 的决策（服务器决定流程、模型只做两件窄任务）保留。

## Context

ADR-007 落地后，每一轮真实测试都发现新的分支问题：回指题、跳过追问后又判定追问、“没听清”复述、慢模型回合。这些问题的共同原因是：

1. **候选人输入没有统一的解释。** `run_turn` 用 `answered`、`last_skip`、`wants_skip`、`just_introduced`、`candidate_qa` 等标志的组合做判断。同一种输入在不同标志组合下走不同分支，前缀文案在多个分支里各自拼接。没有任何地方能列出“某种输入在某种状态下应该发生什么”。
2. **状态分散且多次写入。** 一个回合内 `_save` 被调用多次，每次都从 JSON 列重新读取再写回。写入顺序一变就可能丢字段。标志位（`opening_sent`、`intro_done`、`answered_upto`、`closed_mains`、`candidate_qa`、`last_text`……）没有统一的定义。
3. **旧路径仍在。** 看门狗、回复改写（`_one_question_again`）、开场注入（`BRIEF_AFTER_OPENING`）、守卫的拒绝码（`parent_not_asked` 等）按模型调用工具的旧设计存在，与新流程叠加。
4. **测试只测单回合。** 线上出问题的是连续回合的序列（跳过主问题后复述再提问），单回合断言覆盖不到。

## Decision

### 1. 候选人输入先解释为事件

| 事件 | 判定（纯函数，输入为文本与状态） |
|---|---|
| `Intro` | 开场已发、自我介绍未做，且输入不是指令 |
| `Answer` | 有题在台上，输入不是指令，不是空白 |
| `Skip` | 有题在台上，输入是跳过指令（“下一题”“跳过”“换一题”） |
| `Repeat` | 有题在台上，输入是复述指令（“没听清”“再说一遍”） |
| `End` | 输入是结束指令（“结束”“终止”） |
| `CandidateQuestion` | 提问环节已开，输入不是指令 |
| `Empty` | 空白或只有语气词 |

指令判定只有一处（`classify(text)`），由现有的 `is_steering_message` 与关键词表合并而来。

### 2. 状态转移是唯一的状态写入点

```
apply(state, event, context) -> (state', outputs)
```

- `state` 为不可变的 dataclass，字段固定：`opening_sent`、`intro_done`、`table` (当前台上的题，含 id、kind、parent、skipped)、`answered`（台上的题是否已有回答）、`closed_mains`、`followups_by_main`、`candidate_qa`、`ended`、`last_said`（最后一次输出的原文）。
- 一个回合只调用一次 `apply`，结果一次性写入账本。
- `outputs` 是一组“要说的话”，每条带类型（`intro_ack`、`skip_ack`、`question`、`followup`、`closing`、`qa_open`、`refer`、`repeat`），由事件与状态决定，不再由标志拼接。

### 3. 事件 × 状态 → 输出的表是唯一的规则来源

规则写成一张表（测试直接遍历这张表）。例：

| 事件 | 状态 | 转移 | 输出 |
|---|---|---|---|
| Skip | 台上是主问题 | 关闭该主问题，选下一题 | `skip_ack` + `question` |
| Skip | 台上是追问 | 关闭其主问题，选下一题 | `skip_ack` + `question` |
| Repeat | 有题在台上 | 无状态变化 | `repeat`（上一次原文） |
| Answer | 台上是主问题，追问未达上限 | 判定是否追问 | `followup` 或下一题 |
| CandidateQuestion | 提问环节已开 | 无状态变化 | `answer_candidate`（模型，校验） |
| End | 任何 | 结束 | `closing` |

### 4. 模型只做两件窄任务，结果经校验后才能输出

同 ADR-007：追问判定、主问题改写、岗位题生成、候选人提问的回答。模型的每个输出由 `apply` 之前的校验函数过滤，失败则使用服务器的固定文案。超时统一为 20 秒。

### 5. 旧路径删除

以下在剧本全部通过后删除：`_interview_events`、`_one_question_again`、`REWRITE_MESSAGE`、`needs_one_question`、`held_tokens`、`BRIEF_AFTER_OPENING`、`brief_note`、`WATCHDOG_SEC` / `TOOL_WAIT_SEC` / `HOLDING_TEXT`、`records_mock_answer` 的旁路写入、守卫中按工具调用设计的拒绝码（`parent_not_asked`、`followup_limit`、`too_similar`、`already_asked`、`swap_limit`、`refers_to_earlier_talk` 在回合层的使用）、`coach-mock` 中与流程重复的规则。

## Consequences

- 规则只有一张表，新问题的修复是给表加一行和一个剧本，不再是新分支。
- 测试以剧本为单位：每个剧本是一组候选人输入，断言整段输出与最终账本。
- 旧路径删除前，两套流程并存期间要保证新路径是唯一被开关打开的路径（本次开关不再新增，沿用 `JC_MOCK_STATE_MACHINE`）。

## 实施步骤

1. 写事件分类 `classify` 与表驱动测试（纯函数，不碰数据库）。
2. 写 `apply` 与状态结构，覆盖表中每一行。
3. 把 `run_turn` 替换为 `classify` → `apply` → 一次写入，旧的 `run_turn` 分支删除。
4. 剧本测试（见下），用假模型跑完整会话，断言整段输出与账本。
5. 真实模型跑 3 场剧本（主流程、跳过与复述、提问环节）；通过后删除旧路径（第 5 节清单）。
6. 更新 `coach-mock/SKILL.md`，只保留人设与语气。

## 剧本清单（第 4 步的最小集合）

| 编号 | 候选人输入序列 | 断言 |
|---|---|---|
| S1 | 你好 → 自我介绍 → 作答 → 作答 … 至主问题上限 → 提问环节 → 结束 | 问题数等于上限；提问环节开启一次；收尾；账本 `completed` |
| S2 | 介绍 → 作答 → 下一题 | 输出以“换一题”开头；台上主问题被关闭；下一题是新题 |
| S3 | 介绍 → 主问题 → 作答 → 追问 → 下一题 | 追问被跳过的同时其主问题被关闭；之后不再对该主问题追问 |
| S4 | 介绍 → 没听清 | 原样重复上一次输出；账本无新回答 |
| S5 | 介绍 → 作答 → 结束 | 收尾；不再出题 |
| S6 | 题库中有“上一题你提到…”类题 | 该题永不被提出 |
| S7 | 模型追问返回的引用不在回答中 | 不追问，关闭主问题，下一题 |
| S8 | 模型超时 | 使用服务器固定文案；不等待超过 20 秒 |
| S9 | 提问环节说“下一题” | 结束，不出题 |
| S10 | 候选人提问，模型回答含问号 | 使用“需要和团队确认”的固定文案 |

## Open questions

- 追问上限沿用 2 次，是否需要按级别区分（当前两个级别共用）。
- 候选人提问的回答是否需要知道档案的信息，还是只用岗位描述（当前只用岗位描述，产品需确认）。
