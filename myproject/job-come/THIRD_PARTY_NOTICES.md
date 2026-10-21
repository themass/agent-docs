# Third-party methodology acknowledgements

## MadsLorentzen/ai-job-search

- Repository: https://github.com/MadsLorentzen/ai-job-search
- Reviewed revision: `64a6c90ec32438742ca62f8f30f55afea4435172`
- License: MIT; copyright (c) 2026 Mads Lorentzen.
- License text: `docs/third-party/ai-job-search.LICENSE`.

JC's PDF text-layer diagnostics and additions to application/writer/reviewer/coach guidance
are inspired by `tools/verify_pdf.py`, `.claude/commands/apply.md`,
`.claude/agents/application-reviewer.md`, and the candidate-evidence/integrity-gate methodology.
The implementation uses JC's existing PyMuPDF renderer, domain/services and database contracts;
it does not vendor the upstream tool, run its shell commands, install its Agent permissions,
or import job-source adapters. The JD diagnostics are independently implemented advisory
heuristics, not an injection firewall. No claim of universal ATS compatibility is made.

## career-ops-hq/career-ops

- Repository: https://github.com/career-ops-hq/career-ops
- Methodology reviewed from `main` on 2026-10-20 (README, shared Skill router,
  evaluation mode and interview module conventions; not a pinned vendored release).
- License: MIT; copyright (c) 2026 Santiago Fernández de Valderrama.
- License text: `docs/third-party/career-ops.LICENSE`.

JC independently implements task-sized context reads, scoped user-retracted claims,
and verified requirement citations using its existing database, confirmation and
version contracts. These are methodology adaptations, not a vendored CLI, local-file
memory system, job scraper, or use of the upstream product name as JC branding.
