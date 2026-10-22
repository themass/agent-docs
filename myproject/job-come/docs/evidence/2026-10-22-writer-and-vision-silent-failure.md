# AI 写手与 vision 静默失败：根因、修复与边界

日期：2026-10-22（Asia/Shanghai）。证据来自用户导出的 PDF 与 session trace
`agsn_icwyxfb6w5gk4v8v`，未调用付费模型、未读写业务库。

## 根因：一个配置值，两条链路

`routing.yaml` 的 `defaults.max_tokens: 100000` 被所有 scenario 继承。
它的注释已经写明「只在核实过网关真实上限后才覆盖」，但 vision 没有覆盖。

trace `#20` 逐字记录了后果：

```
vision unavailable: litellm.BadRequestError - <400>
InvalidParameter: Range of max_tokens should be [1, 8192]. Received Model Group=vision-0
Available Model Group Fallbacks=None
```

两点让它无法自愈：

1. **这是 400，不是超时。** 请求在读取任何图片前就被网关拒绝，每次必然失败，
   不存在「偶发」。
2. **vision 链只有一个 endpoint。** `Fallbacks=None`，拒绝即终止。

因此用户连发三张截图说「你看看截图的内容」，agent 一张都没看到 —— 它诚实地说了
「截图本次未能读取」，但仍然基于文字猜测继续改档案。

## 为什么这件事看起来像「优化效果差」

导出的 PDF 里有三处规则回退的指纹，均可在本地复现：

- 范围行写成 `在网易担任财经频道/服务端TL` —— `_scope_line` 的硬编码模板，不是模型输出。
- 要点与档案原文逐字相同 —— `_elevate_bullet` 在三个强度下对「负责…」开头的句子均为恒等变换。
- `（待补充经历要点）` 直接印进交付文件。

即：**用户看到的「优化稿」就是自己写的原文**。`resume_elevator` 的
`except Exception` 捕获写手失败后回退到规则排版，只打一条
`Preview writer unavailable: <类型名>` 的 warning —— 不含消息体，
所以「网关拒绝参数」和「模型慢」在日志里无法区分。

## 修复

1. `routing.yaml` 的 vision endpoint 显式 `max_tokens: 8192`。
   不改 `defaults`：其余 scenario 的真实上限未核实，统一下调会凭猜测限制输出长度。
2. `resume_elevator` 的失败日志补上异常消息体。只有消息能区分「配置错」与「超时」。
3. `resume_elevator` 按链长推导每次尝试的预算（沿用 `resume_reviewer` 的既有做法）。
   原先总预算 90 秒而每个 endpoint 允许 180 秒，慢的主模型会吃掉整个预算，
   两个 fallback 永不被调用 —— 三模型链在主模型不健康时恰好退化成单模型链。

## 验证

- 后端全量：**1083 passed, 6 skipped**。新增 vision 上限与 writer 单次预算回归测试。
- 2 项与本次改动无关的失败在干净 HEAD 上同样复现：`test_chat_litellm_adapter`
  缺 `JC_LLM_API_KEY`；`test_launch_scripts` 断言 monorepo 根路径，worktree 下不成立。
- 未发起真实网关调用，因此**不能据此断言线上 vision 已恢复**：8192 是错误消息给出的
  上限，仍需在真实网关上发一次图片请求确认。

## 导出前的交付检查（本轮一并处理）

新增 `ResumeService._with_delivery_issues`，回答「这个文件**是什么**」，
与既有的 `_with_invariant_issues`（诚信）、`_with_structure_issues`（结构）并列：

1. `generation.mode` 为 `source_layout` / `structure_guarded` 时报
   `generation_not_optimized`，带上生成时写入的 warning 原文。
2. 正文里出现 `（待补充经历要点）` / `(Add experience highlights)` 时报
   `placeholder_bullet`，逐条给出 field path。

两条都是 `warning`，与此处所有确定性发现一致：结构性判断不得把用户锁在自己的文档之外
（`_has_blocking_issue` 已经为此修过一次）。改变的是**导出页不再对此沉默**。

三处接入点都覆盖：正常审稿、审稿超时、以及审稿整体不可用 —— 最后一处尤其重要，
「审稿挂了」恰恰是用户最需要知道「写手也挂了」的时刻，而这两条判断不需要模型。

前端 `ResumeExportStep` 按 code 单独渲染这两类发现，且**不受 `unavailable` 抑制**
（原逻辑在无结论时隐藏全部 issue）；`clean` 也把它们计入，否则标题会说「已完成内容检查」
而下方警告说「AI 写作未完成」。

## 上下文参数对齐 200k

`JC_MODEL_CONTEXT_WINDOW`、`JC_CONTEXT_TOKEN_LIMIT`、`config.yaml` 的 `context_window`
原本已是 200000；唯一低于它的是 `JC_TOKEN_BUDGET_MAX_TOKENS`（150000），现对齐为 200000。
预算低于上下文窗口时，一轮尚未填满窗口的对话会被预算先掐断，表现为 agent 中途停止。

**`max_tokens` 没有跟着调，这是有意的**：它是单次请求的**输出**上限，不是上下文窗口。
把它设成 200000 正是本文档开头那个 400 的成因。

## 生成后的定向修复：把已有的测量接回生成

此前五个质量信号（blueprint / structure / coverage / writing-invariants / reviewer）
**全部在生成之后计算，没有一条回流到生成**。系统能精确说出「这段开头偏弱、量化比例
不达标、这三条源要点丢了」，然后把这句话打印给用户，让用户自己想办法。写手是一次性盲写。

新增 `services/resume_repair.py`（纯函数，不碰模型）+ `resume_elevator._repair_once`
（唯一的不纯步骤）：测出明显缺口时，定向重写出问题的那几段**一次**。

**三种情况直接跳过，不花钱**：没有档案（无法验证）、写手本就失败
（`generation.mode == "source_layout"`，重试一条已失败的链路正是
`profile_ingest_service` 明文反对的）、测量没问题（常见情况，也是这件事成本可控的原因）。

**采纳三道闸，全过才替换第一稿**：
1. **诚信**：fabrication 集合按 `(kind, field_path, detail)` 比对，不得增长 ——
   按集合而非计数，所以「修好一个、又编造一个」会被抓到。这道闸是第二次模型调用
   能被接受的全部理由（`writing_invariants` 的「prompts are not enforcement」正是在说这个）。
2. **覆盖**：`covered` 不得减少。靠删事实读起来变好不算改进。
3. **改进**：分数必须严格上升。没有这条，第二次调用只是用一次随机换另一次随机。

**两处刻意的不触发**，比阈值更重要：
- **缺 scope（范围行）不修。** 范围行唯一来源是用户填的 `scope`；让模型补就是请它编造
  团队规模，而 `resume-writer/references/structure.md` 明说那是整份简历最不能放假事实
  的位置。正解是问用户，`evidence_gaps` 已经在做。英文轨 `scope_line` 恒为 `None`，
  若触发会让每份英文稿都白付一次调用。
- **身份字段不接受修复结果。** 公司名、职位、项目名、日期一律忽略 ——
  本文档上半部分那个「确认的 title 被改回去」就是这类静默覆盖。

合并校验沿用 `_preserve_source_units` 的不变量：按 `id` 匹配（绝不按数组位置）、
一段源段落仍是一段，唯一例外是被要求放回的丢失要点。

`generation.repair` 记录 `accepted` / `reason` / `plan`，否则这功能上线后无法判断
到底有没有用，而「闸门一直在拒绝」和「闸门从未触发」看起来完全一样。

预算独立（`JC_PREVIEW_REPAIR_TIMEOUT_SECONDS=40`），不从写手的 90 秒里切 ——
首轮要产出整篇文档。最坏 90+40=130 秒，低于 SSE 240 秒与前端 255 秒。
`JC_PREVIEW_REPAIR_ENABLED=false` 可不发版关掉。

### 顺带修掉的一个真实 bug

`resume_blueprint.py` 的 `strong_lead_bullets` 在 `experience + projects` 的拼接列表上
取索引，却无条件写成 `experience_blocks[...]`。实测：1 段经历 + 1 个弱开头项目报出
`experience_blocks[1]` —— 该下标不存在，真正的问题在 `project_blocks[0]`。
以前只是显示错字段名；一旦修复循环按它定位，就会去重写错误的段落。

## 失败的稿不再被当作有效缓存

`_is_stale_for_profile` 在版本比较之前早返回 `True`（仅 `source_layout`）。
选这里是因为它是唯一的 staleness 判定，且已覆盖 bilingual 的两个子轨 ——
写在 `preview()` 的 `cache_reason` 链里会漏掉它们，导致 zh 子轨一次失败后永久缓存。
`cache_reason` 另加 `writer_failed` 标签，否则日志无法区分「档案变了」和「上次写手挂了」。

不含 `structure_guarded`（那次写手确实工作了，重跑未必更好却必然再付钱）；
`JC_LLM_ENABLED=false` 的部署不受影响（确定性 builder 不设 `generation` 键），
否则那种部署会每次预览都无限重生成。

## 未处理

- 已缓存的旧优化稿未批量重新生成。
- `prepare_tracks()` 只做存在性检查、不调 `_is_stale_for_profile`，
  因此它写入的 `source_layout` 稿不受上述规则刷新（它默认 `conservative` 档、属后台预热）。
- `summarization.trigger` 仍是 32000（窗口 × 0.16），未随预算调整：它控制何时压缩历史，
  与上限是不同的权衡，调它应该有独立的理由。
- **修复是否真能提升质量，本轮无法验证**：全程未发起真实网关调用。
  `generation.repair.accepted` 与 `rejected_reason` 就是为了上线后回答这个问题。
