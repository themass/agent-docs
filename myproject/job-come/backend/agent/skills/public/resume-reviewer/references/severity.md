## error — must block export

These are factual or integrity failures. Any one of them forces `status: "failed"`.

- **Unsupported fact**: a company, school, title, date, metric, team size or technology in the
  draft that `source_profile` does not support. Quote the unsupported part in the message.
- **Inflated ownership**: the draft claims 主导 / 负责 / 从 0 到 1 / led / owned where the source
  only supports 参与 / 协助 / involved.
- **Missing contact essentials**: no name, or neither email nor phone.
- **Date integrity**: end before start, overlapping full-time roles, or an unexplained gap the
  draft silently hides by altering a source date.
- **Placeholder text**: 待确认 / TBD / lorem / XXX / sample left in the output.
- **Empty experience**: a role with no bullets at all.

## warning — does not block export

Quality problems the candidate should know about but can reasonably ship with.

- **No object**: a bullet with a verb but no concrete system, product, process or metric
  (`深入研究相关技术`, `主导优化工作`).
- **No outcome where evidence exists**: the source contains a result or scale number that the
  bullet dropped.
- **Vague quantities**: 多项 / 若干 / various / several used where the source has a real number.
- **Weak lead verb**: a bullet whose main verb is 参与 / 协助 / 了解 / 熟悉 / helped with, when the
  source supports something stronger.
- **Self-praise without evidence**: 优秀的 / 资深的 / passionate / results-driven.
- **First-person summary opening**: 本人 / 我是 / I am.
- **Unfocused paragraph**: unrelated work mixed without clear ownership. Length alone
  is not a defect when a complete project needs its background, actions and outcome.
- **Duplicate claim**: the same achievement asserted under two different roles.
- **Buried highlight**: supported impact is unclear within a source paragraph; never demand moving a result away from its project context.
- **Dropped source content**: a `highlights` entry in `source_profile` with no counterpart
  anywhere in the draft, or an empty `project_blocks` on a profile that has `projects`. Name the
  dropped text. This is the most common real complaint about a generated resume — the document
  reads thinner than the career. Preserve original source units and project ownership;
  do not recommend merging or splitting them without an explicit user request.
