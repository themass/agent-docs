## What counts as source evidence

`source_profile.evidence_answers` is part of the source, not model output. Each entry is a fact
the candidate typed themselves when we asked about a specific bullet. A number or outcome that
appears in `evidence_answers` is **supported** — do not raise `unsupported_fact` for it.

Two things still block export:

- A figure that appears in neither the bullets nor `evidence_answers`, and nowhere else in the
  profile. Inventing from a hint is still invention.
- A draft that inflates a user-supplied figure (answer says "约 3000 QPS", draft says "万级 QPS";
  answer says "15%–20%", draft says "20%+"). Report it as an unsupported fact and quote both.

## Verification procedure

1. Check contact and date integrity first.
2. For each bullet, locate its supporting evidence in `source_profile`, including
   `evidence_answers`. No evidence → `error`.
3. Compare the claimed ownership verb against the source's own wording.
4. Only then judge writing quality and report `warning` items.

Do not reward confident writing. A polished bullet with no source backing is the most
dangerous output you can pass.

`passed` only when zero `error` severity issues remain.
