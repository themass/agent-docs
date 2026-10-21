## Method: write every bullet as Action + Object + Outcome

This is the XYZ pattern ("accomplished **X** as measured by **Y** by doing **Z**") stated in the
order Chinese and English resumes actually read best:

1. **Action** — a strong, specific verb describing what the person did.
2. **Object** — the concrete system, product, team, process or metric they acted on.
3. **Outcome** — what changed as a result, quantified when the source supports it.

Bad: `深入研究分布式系统，主导相关优化工作。` (no object, no outcome, unverifiable)
Good: `主导看点快报后台从 PHP 单体迁移到 tRPC-Go 微服务，解决发布耗时与资源损耗问题，实现成本优化 20%。`

A bullet missing the Outcome is still acceptable when the source has no result data — a precise
Action + Object beats an invented number. A bullet missing the Object is never acceptable.

### Verb strength

Prefer verbs that encode ownership and scope. Choose the strongest verb the **evidence** supports;
do not upgrade `参与` to `主导` unless the source says so.

- Ownership: 主导 / 负责 / 搭建 / 设计并实现 / 从 0 到 1 落地 — lead, own, architect, build, launch
- Improvement: 重构 / 优化 / 治理 / 收敛 / 提升 — refactor, optimize, reduce, scale, streamline
- Collaboration: 推动 / 协同 / 牵头 — drive, partner, coordinate
- Weak, avoid as the main verb: 参与 / 协助 / 了解 / 熟悉 / 接触 — involved in, helped with, familiar with

### Quantification ladder

Use the highest rung the source actually supports, and never fabricate a rung:

1. Direct metric from the source (`成本优化 20%`, `Lead Time 25 天 → 8 天`)
2. Scale or scope from the source (`全量推送 4kw`, `服务 6 个业务线`, `管理 8 人团队`)
3. Qualitative outcome from the source (`支撑跨业务一致性事务`, `解决模块耦合问题`)
4. No outcome — state Action + Object precisely and stop

Prefer before/after pairs and absolute scale over bare percentages: `从 25 天缩短至 8 天` is more
credible than `提升 68%`.

### Coverage: match the document to the career

A senior profile rendered as a handful of short bullets reads as a thin career, not a concise
resume. Under-writing is the more common and more damaging failure — the reader cannot infer scope
that is not on the page.

- Cover **every `highlights` entry** in the source with one corresponding rewritten
  paragraph, in source order. Do not split, merge or silently drop source units.
- Scale bullet count to the role, not to a fixed target: a 5-year role with 9 source highlights
  should not come out shorter than a 1-year role with 3.
- The most recent and most senior role carries the most bullets. Earlier roles compress, but a
  multi-year senior role never drops below 4 bullets when the source supports them.
- **Always populate `project_blocks` when `profile.projects` is non-empty.** Each project gets its
  `name`, its `role` and `date_range` when known, and **one bullet per entry in that project's
  `highlights`** — projects are written to the same density as experiences, not summarized into a
  single line. When a project has no `highlights`, build one bullet from its `description`. An
  empty `project_blocks` on a profile that has projects is a defect.
- Preserve project boundaries: background, implementation and results of one source
  paragraph remain together. Separate original bullets remain separate within their project.
- If the source is genuinely thin, the resume is short — do not pad with invented scope. Thin
  source and dropped source look identical on the page, so never create the second case.

### Making real work read as substantial

The most common complaint about a generated resume is that it feels thinner than the career behind
it. That is almost never because the career was thin — it is because the bullet kept only the
action and threw away everything that made the action hard. A bullet has room for more true
material than a one-line paraphrase uses.

For each bullet, check whether the source already contains any of these and is simply not showing
it:

1. **The constraint** — what made this hard: legacy system, deadline, no budget, regulatory limit,
   a team that did not report to them, traffic that could not go down.
2. **The method** — how it was actually done, named specifically: the pattern, the framework, the
   process they introduced, the alternative they rejected.
3. **The surface** — how much of the organisation it touched: how many services, teams, markets,
   customers, SKUs, the time span it ran over.
4. **The outcome** — what changed, at the highest rung of the quantification ladder the source
   supports.

A bullet carrying three of the four reads as senior work. A bullet carrying only the action reads
as a job description, no matter how strong the verb is. **Every one of the four must come from the
source.** Writing a constraint the profile does not mention is fabrication, exactly like inventing
a metric — it is just harder to spot, which makes it worse.

Remove filler inside a source paragraph, but retain its complete project context.
Length guidance never licenses splitting one project's background, implementation or results.
Do not force an intact source paragraph into several short disconnected bullets.

### Ordering within an experience

Preserve source paragraph order and project grouping. Improve the clarity of supported
outcomes inside each paragraph; never detach an outcome from its context to promote it.
Reorganizing independent projects requires an explicit user request, not a score-based default.

### Summary

Three elements, two to three sentences, no first-person pronoun:
positioning (years + domain + role) → strongest proof (one concrete achievement from the source)
→ direction (the kind of role being targeted, when `job_title` is supplied).

Never open with `本人` / `我是` / `I am a`. No subjective self-praise (`优秀的`, `资深的`,
`passionate`, `results-driven`) — the evidence must carry it.
