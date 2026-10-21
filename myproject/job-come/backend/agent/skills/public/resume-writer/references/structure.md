## Structure first: the document is read top-down, not bullet by bullet

Rewriting sentences one at a time produces a polished document that still reads weak,
because the decisions a recruiter actually responds to are above the sentence. Get these
four right before touching wording.

### 1. 结论先行 — `summary` states the conclusion, then proves it

Exactly three moves, in this order, 2–4 sentences total:

1. **定位** — years of experience plus what this person *is*. Not what they want.
2. **最硬的一条证据** — the single strongest supported fact in the whole profile,
   restated here. A number if the source has one, otherwise the largest scope or the most
   consequential outcome. This is the only legitimate repetition in a resume.
3. **方向** — what they are moving toward, stated in one clause.

Bad: `本人工作认真负责，有多年互联网经验，熟悉后端开发，希望找一份有挑战的工作。`
Good: `9 年后端与平台研发，主导过日均 1200 万单的订单链路微服务化，发布耗时从 40 分钟
压到 6 分钟。近三年带 8 人团队做基础服务治理，目标是继续承担平台级架构与团队负责。`

Never open with 本人 / 我是 / I am. Never list duties here.

### 2. 先总后分 — every role opens with one line of 角色与范围

`scope_line` is one sentence, under 90 characters, answering **what this person owned and
how big it was** — team size, system or business scope, budget, region, reporting line.
Then the bullets give the evidence. Without it the reader has to infer scope from the
accomplishments, which is work they will not do, and a strong career reads as a list of
tasks.

- `document_requirements.scope_line_must_state` names the dimensions this role family is
  read for. Cover the ones the source supports, in that order.
- When the source experience carries a `scope` field, **that is the user's own statement
  of their scope** — the one fact about mandate and team size that cannot be inferred
  from accomplishments. Use it as the basis of the line. You may tighten the wording; you
  may not broaden what it claims.
- Build it **only** from facts in the source: `scope`, titles, team sizes, system names,
  scale figures, the role's own `highlights`. If the source supports no scope statement at
  all, return `null` — an invented scope line is the worst possible place to put a false
  fact, because it frames everything under it.
- It is not a summary of the bullets and it is not a duty list. `负责后端开发工作` says
  nothing; `带 8 人后端团队，负责订单与结算两条主链路（日均 1200 万单）` is a scope line.
- Earlier, shorter roles may legitimately have `null`.

### 3. 项目叙事完整 — keep source units and order

Keep each source paragraph and the original order inside a role/project. A project's
background, actions and results form one narrative, not competing bullets. Highlight
supported outcomes within that paragraph; never rank individual sentences by metrics
or move a result away from the project that explains it. No count or length guideline
may override this boundary.

### 4. 节序 — put the section carrying the evidence first

`section_order` starts from the role playbook's priority. Deviate in one case: when the
candidate's real evidence lives in `project_blocks` rather than in employment history
(early career, one long employer, platform or contract work), put `projects` before
`experience`. Never reorder to hide something.

### 5. 分量 — the document must clear the family's bar

`document_requirements` contains a source-unit preservation contract and advisory
completeness references. The source boundaries take precedence over every count or
length reference. Diagnostics may suggest missing evidence, never quota-driven splitting.

- `lead_role_reference_bullets` and `other_roles_reference_bullets` are completeness
  references only, never minimum output quotas. Source unit count takes precedence.
- `min_outcome_ratio` — at least this share of all bullets must end in a result.
- `summary_formula` — the three parts of `summary`, in that order.

These counts are advisory completeness signals, not output quotas. Preserve the number
of source highlights and their boundaries. A role with two source paragraphs gets two
rewritten paragraphs even if the playbook suggests more. Never split one project or
separate its background, method and result to reach a count. If more independent work
is needed, ask the user to supply it; never manufacture it.

### Across the whole document

- **No duplicate claim.** The same achievement appears once, in the role that owned it —
  the only exception is the one strongest fact restated in `summary`.
- **Preserve each role's source units.** Do not inflate recent roles or compress earlier
  ones to satisfy a role-weighting formula.
- **One source unit per bullet.** Preserve original project grouping and paragraph order.
  A project may span several sentences; do not split it just because it covers several
  implementation details. Distinct source bullets remain distinct under their project.
