# Mock Interview Flow Implementation Plan

> **For agentic workers:** execute task by task with TDD; steps use checkbox syntax.

**Goal:** Finish the certain parts of SPEC-MOCK-INTERVIEW-V2 §7.2 (A to F, H, and the question-quality guard of I), with the question bank and the profile library left as extension points only.

**Spec:** [SPEC-MOCK-INTERVIEW-V2.md](../../product/SPEC-MOCK-INTERVIEW-V2.md) §3.1, §5.1 to §5.3, §6.1, §6.2, §7.2.

## Global constraints

- Desktop only. No phone layout.
- The question bank and the profile library are not built. They get interfaces (`jc.coach.sources`) with the personal bank as the only implementation; a future source registers itself and needs no change to the interviewer, the reviewer or the report.
- Scoring anchors do not depend on level or style. The readiness tier is computed by code, never by the model.
- Backend tests: `cd backend/server && /Users/gqli/work/deepagents/venv/bin/python -m pytest -q`. Frontend: `cd frontend/web && npx tsc --noEmit` and `node --test tests/`.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit on the worktree branch, fast-forward `main`. Do not push.
- Deferred, stated up front: real-model acceptance (needs an API key), the question blueprint, the seed bank, the profile library, resend de-duplication.

## Review Focus

1. A legacy session with no `asked` list still produces a transcript and a report (every question is then a main question).
2. A reviewer that scores a follow-up's id, or quotes a follow-up's answer as evidence for its main question, is handled (the second works, the first is told what to do).
3. A summary quote that is not in the candidate's words is dropped and counted, never shown as evidence.
4. A session that ended early or covered few must-haves is never rated above "需针对性补强".
5. Candidate Q&A: the candidate's questions are never recorded as an answer, and ending without opening it is refused with a reason (user-ended and timeout are not).

## Tasks

1. **Shared turns.** `jc.services.mock_turns.session_turns(store, session) -> list[Turn]` (question_id, stem, answer, kind, parent_question_id, skipped), ordered as asked. Used by `session_transcript` and `mock_session_history`. Report validation accepts a main question's evidence from its own or its follow-ups' answers.
2. **Reviewer inputs.** `mock_session_history` also returns the job (company, title, must_have, nice_to_have, raw text clipped), the level spec, the style, and each turn's kind/parent/skipped. Question reference sources: `jc.coach.sources.QuestionSource` / `QuestionReference`, a registry, the personal bank as the default source; `jc_bank_search_questions` aggregates registered sources; history attaches a reference per turn when a source has one.
3. **Report conclusion.** Reviewer writes `summary` (verdict, up to 3 strengths and 3 priorities, each with a quote). `validate_report` normalises it. `jc.coach.readiness.readiness(...)` computes the tier. `MockReportResponse` gains `summary`, `readiness`, and nested `follow_ups`. Report page leads with them.
4. **Stages and guards.** `jc_mock_plan` returns `stage`, `suggested_stage`, `stage_counts`, `candidate_qa`. New tool `jc_mock_open_qa`. `end(reason="completed")` refuses until it has been opened. `ask` takes an optional `stage`, and refuses a stem that is empty, too long, or a near-duplicate of one already asked.
5. **Panel and bar (web).** One progress hook; `MockBar` above the chat (question n of N, stage, elapsed, skip, swap, end); the panel follows an interviewer-ended session and shows a report notice under the chat.
6. **Docs and checklist.** `jc.coach.acceptance` pure checks over a transcript for the real-model run; TECH-API and the spec.
