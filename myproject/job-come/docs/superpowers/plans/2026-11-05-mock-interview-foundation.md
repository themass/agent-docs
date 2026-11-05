# Mock Interview Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The system records the candidate's answers itself, the user picks an interview level (with a resume-based recommendation), and the report is generated in the background with a visible status and a retry.

**Architecture:** Answers are written by `AgentService` before the model runs, onto the question currently on the table, scoped to the mock session. The level is a pure function of the profile plus a static table, stored on `jc_mock_session`. The report moves from "generated when the page is first opened" to a database-backed queue (`report_status`) drained by a dispatcher in the API process, because the `jc_mock_end` tool runs in a separate stdio process that cannot start work in the API process.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic (head `022_drop_agent_session_kind`), pytest with SQLite, Next.js.

**Spec:** [docs/product/SPEC-MOCK-INTERVIEW-V2.md](../../product/SPEC-MOCK-INTERVIEW-V2.md) §3.3, §3.4, §3.5, §5.3, §6.1 (level cards), §7 steps 1 and 2.

## Global Constraints

- Level keys: `junior`, `mid`, `senior`, `expert`. Years: 应届到3年 / 3到6年 / 6到10年 / 10年以上. Benchmarks (对照): P5 / P6 / P7 / P8. Not an Alibaba standard; the UI says "对照" only.
- Recommendation is plain code (no model call). Date format in profiles is `YYYY-MM`. A title adjusts at most one level; unparsable dates give no recommendation.
- Scoring anchors do not depend on level. Level changes question depth and follow-up direction only.
- A report may be regenerated at most 3 times (4 runs in total including the first).
- Migrations continue after `022_drop_agent_session_kind`; revision ids follow the `0NN_snake_case` form.
- Backend tests: `cd backend/server && /Users/gqli/work/deepagents/venv/bin/python -m pytest <path> -q`. Frontend check: `cd frontend/web && npx tsc --noEmit`.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push; the user decides.
- Deliberately not in this plan (YAGNI until a consumer exists): `turn_index` on attempts (one row per question per session is enough, later messages are appended), `stage` and timestamps on `asked` entries (step 5 blueprint), nested follow-ups in the report view (step 4; the data already carries `parent_question_id`).

## Review Focus

Each line is pinned by a test in the task named in brackets.

1. A user message when no question is on the table (greeting, self-introduction, a message right after a skip) is not recorded and raises nothing. [Task 5]
2. A bank question answered in one session never shows up as an answer, or as "already answered", in another session. [Task 1]
3. Messy profile dates (missing, "至今"/no end, reversed range, overlapping jobs, text that is not `YYYY-MM`) never raise from the recommendation. [Task 2]
4. Two dispatcher workers racing for one queued report: exactly one claims it. A run that died is picked up again after the lease, and never beyond 4 runs. [Task 7]
5. A refused `jc_mock_ask` that carried a new question stem leaves no question row and no change to the session. [Task 6]

---

### Task 1: Scope answers to the mock session

An existing bug found while reading: `get_latest_attempt_for_question` ignores the mock session, so a bank question reused across sessions shows the earlier session's answer in a new session's transcript and makes `_open_question` think it is answered.

**Files:**
- Modify: `backend/server/src/jc/stores/interview_store.py` (add method beside `get_latest_attempt_for_question`, line ~133)
- Modify: `backend/server/src/jc/services/mock_report_service.py:128`, `backend/server/src/jc/services/mock_guard_service.py:119-128,163-172`, `backend/server/src/jc/services/question_bank_service.py:135`
- Create: `backend/server/tests/test_mock_attempt_scope.py`

**Interfaces:**
- Produces: `InterviewStore.get_latest_attempt_in_session(question_id: str, mock_session_id: str) -> AnswerAttempt | None`; `_open_question(store, asked, mock_session_id: str) -> str | None` (new third parameter).

- [ ] **Step 1: Write the failing tests.** Fixture: sqlite engine as in `test_mock_flow.py`, profile `p1`, question `q1`, sessions `ms1` (active, `asked=[{question_id:"q1",kind:"main"}]`) and `ms2`, one `AnswerAttempt` on `q1` with `mock_session_id="ms2"`. Tests:
  - `test_an_answer_from_another_session_is_not_this_sessions_answer`: `get_latest_attempt_in_session("q1","ms1") is None` and `get_latest_attempt_in_session("q1","ms2")` is the attempt.
  - `test_the_report_transcript_of_a_session_ignores_other_sessions_answers`: `session_transcript(store, ms1)` has `answer == ""` for `q1`.
  - `test_a_question_answered_elsewhere_is_still_open_here`: `plan(scope_for_ms1, mock_session_id="ms1")["current_question_id"] == "q1"`.
- [ ] **Step 2: Run** `tests/test_mock_attempt_scope.py` and confirm all three fail (method missing / wrong answer).
- [ ] **Step 3: Implement** the store method (same query plus `AnswerAttempt.mock_session_id == mock_session_id`), pass the session id at the three call sites, and add the `mock_session_id` parameter to `_open_question` and its two callers. Keep `get_latest_attempt_for_question` for non-session callers.
- [ ] **Step 4: Run** the new tests and `tests/test_mock_guard.py tests/test_mock_report_service.py tests/test_mock_flow.py`; all pass.
- [ ] **Step 5: Commit** `fix(coach): answers belong to the mock session they were given in`.

### Task 2: Interview levels and the recommendation

**Files:**
- Create: `backend/server/src/jc/coach/level.py`, `backend/server/tests/test_coach_level.py`

**Interfaces:**
- Produces:
  - `LEVELS: tuple[str, ...] = ("junior", "mid", "senior", "expert")`
  - `@dataclass(frozen=True) LevelSpec(key, label, benchmark, years, requirement, depth, follow_up)` all `str`; `LEVEL_SPECS: dict[str, LevelSpec]` with the spec §3.5 text (labels 初级/中级/高级/专家; `depth` and `follow_up` from the "问题深度" column and the follow-up direction list).
  - `@dataclass(frozen=True) LevelRecommendation(level: str, years: float, reason: str)`
  - `level_for_profile(experiences: Sequence[ProfileExperience], *, today: date) -> LevelRecommendation | None`

- [ ] **Step 1: Write the failing tests** (build `ProfileExperience` with `id`, `company`, `title`, `start_date`, `end_date`):
  - `test_five_years_of_backend_work_recommends_mid`: `2019-01`→`2024-01`, title 后端工程师 → `level == "mid"`, `years == 5.0`.
  - band edges: 2.9 years → `junior`, 3.0 → `mid`, 6.0 → `senior`, 10.0 → `expert` (boundary side is my call: lower bound inclusive).
  - `test_overlapping_jobs_are_counted_once`: `2020-01`→`2022-01` and `2021-01`→`2023-01` → `years == 3.0`.
  - `test_no_end_date_runs_to_today`.
  - `test_a_senior_title_raises_one_level_and_an_intern_title_lowers_one`: 专家/架构师/负责人/总监 up, 实习/助理 down, only the most recent job's title counts (latest end date; no end date counts as latest), and the result is clamped to the four levels; a title with both kinds of word adjusts nothing.
  - `test_unusable_dates_never_raise` (parametrized: missing `start_date` text `""`, `"至今"`, `"2020"`, end before start, `"abc"`) → returns `None` when nothing parses, otherwise the parsable jobs only.
  - `test_the_reason_names_years_title_and_level`: contains `约 5 年`, the title, and `中级`; when a title moved the level the reason says so.
- [ ] **Step 2: Run** and confirm failure (module missing).
- [ ] **Step 3: Implement.** Months as `year*12+month`; interval length is `end_idx - start_idx`; merge intervals before summing; `years = round(months/12, 1)`; the end of an open job is `today`'s month. Skip a job whose dates do not parse as `YYYY-MM`.
- [ ] **Step 4: Run** the file; passes.
- [ ] **Step 5: Commit** `feat(coach): interview levels and a recommendation from the profile`.

### Task 3: Level on the session and a recommendation endpoint

**Files:**
- Create: `backend/server/alembic/versions/023_mock_session_level.py`
- Modify: `backend/server/src/jc/models/interview.py` (MockSession), `backend/server/src/jc/schemas/coach.py` (`MockSessionCreateRequest`, `MockSessionResponse`, new `LevelOption`, `LevelRecommendationResponse`), `backend/server/src/jc/services/interview_service.py` (`create_mock_session`, `_to_mock_response`, new `level_recommendation`), `backend/server/src/jc/api/coach_router.py`
- Test: `backend/server/tests/test_mock_level.py`

**Interfaces:**
- Consumes: `level_for_profile`, `LEVEL_SPECS`, `LEVELS` from Task 2.
- Produces: column `jc_mock_session.level String(16) NULL`; `MockSessionCreateRequest.level: Literal["junior","mid","senior","expert"] | None = None`; `MockSessionResponse.level: str | None`; `GET /coach/mock/level-recommendation?profile_id=` → `LevelRecommendationResponse(recommended: str | None, years: float | None, reason: str | None, levels: list[LevelOption])` where `LevelOption(key, label, benchmark, years, requirement)`; `InterviewService.level_recommendation(profile_id: str, *, actor: UserActor) -> LevelRecommendationResponse`.

- [ ] **Step 1: Write the failing tests** using the service fixtures from `test_mock_quota_creation.py`:
  - `test_a_session_created_without_a_level_gets_the_recommended_one`
  - `test_an_explicit_level_wins_over_the_recommendation`
  - `test_no_level_and_no_recommendation_is_refused` → `ConflictError`, message `请先选择面试级别。`, no session row and no quota claimed.
  - `test_the_recommendation_endpoint_lists_all_four_levels_and_names_the_reason`.
- [ ] **Step 2: Run** and confirm failure.
- [ ] **Step 3: Implement** the migration (add nullable column; downgrade drops it), model field, schemas and service. Load the profile payload the way `_ResumeProfile.gather` in `jc/agent/turn.py` does and call `level_for_profile(payload.experiences, today=date.today())`. Resolve the level before `claim_full_run`, so a refused creation claims nothing.
- [ ] **Step 4: Run** the new tests plus `tests/test_mock_quota_creation.py`.
- [ ] **Step 5: Commit** `feat(coach): a mock session has a level, recommended from the profile`.

### Task 4: The level reaches the interviewer

**Files:**
- Modify: `backend/server/src/jc/agent/coach_task.py` (`wrap_coach_mock_message`), `backend/server/src/jc/agent/turn.py` (`_MockSession.gather/message`), `backend/server/tests/test_turns.py`

**Interfaces:**
- Consumes: `LEVEL_SPECS` (Task 2); `MockSession.level` (Task 3).
- Produces: `wrap_coach_mock_message(..., level: str | None = None)`; `_MockSession.gather` also returns `"level"`.

- [ ] **Step 1: Write the failing tests** in `test_turns.py`:
  - `test_the_interview_message_states_level_depth_and_follow_up_direction`: with `level="mid"` the text contains `中级`, the `depth` and `follow_up` strings of `LEVEL_SPECS["mid"]`.
  - `test_a_session_without_a_level_adds_no_level_line` (older sessions).
- [ ] **Step 2: Run** and confirm failure.
- [ ] **Step 3: Implement.** Add one line to the task text: `面试级别：{label}（对照 {benchmark}）。出题深度：{depth}。追问方向：{follow_up}。评分标准不随级别变化。`
- [ ] **Step 4: Run** `tests/test_turns.py tests/test_prompt_layers.py`.
- [ ] **Step 5: Commit** `feat(coach): the interviewer asks at the level the user chose`.

### Task 5: The system records the answers

**Files:**
- Create: `backend/server/src/jc/services/mock_answer_recorder.py`, `backend/server/tests/test_mock_answer_recorder.py`
- Modify: `backend/server/src/jc/services/agent_service.py` (`stream_message`, right after `agent_message = await flatten_task` and before `provider.message(...)` wraps it)

**Interfaces:**
- Produces:
  - `async record_mock_answer(db: AsyncSession, *, profile_id: str, mock_session_id: str, text: str) -> str | None` — returns the attempt id, or `None` when nothing is on the table. Commits.
  - `records_mock_answer(*, turn: str | None, runtime_skill: str, default_skill: str, mock_session_id: str | None) -> bool`

- [ ] **Step 1: Write the failing tests** (sqlite fixture as in `test_mock_flow.py`; `ms1` active with `asked` entries set directly in `coverage`):
  - `test_the_first_message_after_a_question_becomes_its_answer`: returns an attempt id; attempt has `mock_session_id="ms1"`, the question's `attempt_count == 1`.
  - `test_more_messages_on_the_same_question_extend_one_answer`: two calls → one attempt row, text joined by a newline.
  - `test_a_follow_up_gets_its_own_answer`: after a follow-up is asked, the next message does not touch the main question's attempt.
  - `test_nothing_is_recorded_when_no_question_has_been_asked` (greeting/self-introduction) → `None`, zero attempt rows, no error.
  - `test_nothing_is_recorded_after_a_skip` → `None`.
  - `test_nothing_is_recorded_for_a_closed_session`.
  - `test_records_mock_answer_only_for_the_practice_skill_of_the_interview_turn`: true for `("mock_session","coach-mock","coach-mock","ms1")`; false for skill `coach-archive`, other turn, or no session id.
- [ ] **Step 2: Run** and confirm failure.
- [ ] **Step 3: Implement.** The question on the table is the last `asked` entry that is not skipped. Create the attempt through `InterviewStore.add_attempt` with empty `coach_feedback`, `question.attempt_count += 1`; extend by appending `"\n" + text` to `user_answer`. In `AgentService.stream_message`, call it when `records_mock_answer(...)` is true, with the flattened text captured before the provider wraps it. A recording error propagates (the user sees the failed turn and can resend); it is not swallowed.
- [ ] **Step 4: Run** the new tests and `tests/test_mock_flow.py`.
- [ ] **Step 5: Commit** `feat(coach): the system records the candidate's answers`.

### Task 6: `jc_mock_ask` takes the question itself

**Files:**
- Modify: `backend/server/src/jc/services/question_bank_service.py` (`question_upsert` gets `commit: bool = True`), `backend/server/src/jc/services/mock_guard_service.py` (`ask`), `backend/server/src/jc/mcp/handlers.py` (`mock_ask`), `backend/server/src/jc/mcp/server.py` (`jc_mock_ask`), `backend/agent/skills/public/coach-mock/SKILL.md`, `backend/server/src/jc/agent/coach_task.py`, `backend/server/tests/test_agent_isolation.py` if it lists the old set
- Test: `backend/server/tests/test_mock_ask_stem.py`

**Interfaces:**
- Produces: `ask(scope, *, mock_session_id, question_id: str | None = None, stem: str | None = None, question_type: str = "behavioral", tags: list[str] | None = None, kind="main", parent_question_id=None, experience=None)`; exactly one of `question_id` / `stem` must be given (`ValueError` otherwise). The same parameters on `mock_ask` and `jc_mock_ask`.

- [ ] **Step 1: Write the failing tests:**
  - `test_asking_by_stem_creates_the_question_and_registers_it_once`: one new `InterviewQuestion`, appended to the session's `question_ids`, `generated_count` +1, response `accepted`.
  - `test_asking_a_stem_already_in_the_bank_reuses_that_question` (no second row).
  - `test_a_refused_ask_leaves_no_new_question_behind`: with the session at `main_limit`, asking a new stem returns `code == "main_limit"`; zero rows for that stem; session unchanged.
  - `test_giving_both_or_neither_of_id_and_stem_is_an_error`.
- [ ] **Step 2: Run** and confirm failure.
- [ ] **Step 3: Implement.** In `ask`, run the existing session/limit/parent checks first, then resolve the question (existing id, or `question_upsert(..., commit=False)`), then the `already_asked` check; every refusal after an upsert calls `scope.db.rollback()` before returning. Remove `jc_question_upsert` and `jc_answer_save_attempt` from `coach-mock`'s `allowed-tools`, and rewrite the "每一题" section and the task text so the interviewer registers a question with a single `jc_mock_ask(stem=...)` and no longer saves answers. Keep both tools registered; `coach-archive` still uses `jc_question_upsert`.
- [ ] **Step 4: Run** the new tests, `tests/test_mock_guard.py tests/test_mock_flow.py tests/test_agent_isolation.py tests/test_roles.py tests/test_turns.py`.
- [ ] **Step 5: Commit** `feat(coach): the interviewer registers a question in one call`.

### Task 7: The report queue

**Files:**
- Create: `backend/server/alembic/versions/024_mock_report_queue.py`, `backend/server/src/jc/services/mock_report_queue.py`, `backend/server/tests/test_mock_report_queue.py`
- Modify: `backend/server/src/jc/models/interview.py`, `backend/server/src/jc/services/mock_guard_service.py` (`_close`)

**Interfaces:**
- Produces: columns `report_status String(16) NULL`, `report_attempts Integer NOT NULL default 0`, `report_claimed_at UTCDateTime NULL`, `report_error String(255) NULL`; states `queued | generating | ready | failed`; in `mock_report_queue.py`:
  - `MAX_REPORT_RUNS = 4`, `CLAIM_LEASE = timedelta(seconds=600)`
  - `async claim_next_report(db: AsyncSession, *, now: datetime | None = None) -> str | None`
  - `async generate_report(session_id: str) -> bool` (opens its own DB session; runs `review_session`)
  - `async requeue_failed(db: AsyncSession, session_id: str) -> bool`
  - `async run_mock_report_dispatcher(*, poll_seconds: float = 5) -> None`

- [ ] **Step 1: Write the failing tests** (use `FakeReviewerAgent` / `FakeClientFactory` as `test_mock_flow.py` does):
  - `test_ending_a_session_queues_its_report` (via `end`, and via the 24-hour timeout close).
  - `test_a_queued_report_is_claimed_by_exactly_one_of_two_workers`: `asyncio.gather` of two `claim_next_report` → one id, one `None`; `report_attempts == 1`.
  - `test_a_generating_report_is_reclaimed_after_the_lease_and_not_before`.
  - `test_a_report_that_used_all_its_runs_is_failed_not_reclaimed`.
  - `test_a_successful_run_marks_the_report_ready` and `test_a_run_that_stores_nothing_marks_it_failed_with_a_short_reason`; `report_error` never contains a traceback or more than 255 characters.
  - `test_requeue_failed_is_allowed_until_four_runs_have_been_used`.
  - `test_the_migration_backfill_rule`: assert the rule as a small pure helper, `legacy_report_state(has_report: bool) -> tuple[str, str | None]` → `("ready", None)` / `("failed", "历史场次，未生成报告")` (no automatic model cost on deploy).
- [ ] **Step 2: Run** and confirm failure.
- [ ] **Step 3: Implement.** Claim with a conditional `UPDATE ... WHERE id = :id AND (report_status = 'queued' OR (report_status = 'generating' AND report_claimed_at < :cutoff))` and treat `rowcount == 1` as the win; `_close` sets `report_status = "queued"`. The migration backfills completed sessions per `legacy_report_state`; check how `JSONLongText` stores "no report" (SQL NULL vs JSON `null`) before writing the `UPDATE`.
- [ ] **Step 4: Run** the new file plus `tests/test_mock_guard.py`.
- [ ] **Step 5: Commit** `feat(coach): a finished session queues its report for the background reviewer`.

### Task 8: The report endpoint only reads; retry; dispatcher wiring

**Files:**
- Modify: `backend/server/src/jc/services/interview_service.py` (`get_mock_report`, new `retry_mock_report`), `backend/server/src/jc/schemas/coach.py` (`MockReportResponse`), `backend/server/src/jc/api/coach_router.py`, `backend/server/src/jc/main.py` (lifespan), `backend/server/tests/test_mock_report_view.py`, `backend/server/tests/test_mock_flow.py`, `backend/server/tests/test_interview_reviewer.py`
- Test: `backend/server/tests/test_mock_report_status.py`

**Interfaces:**
- Consumes: Task 7 functions.
- Produces: `MockReportResponse.status: Literal["active","pending","failed","ready"]` and `can_retry: bool = False`; `InterviewService.retry_mock_report(session_id: str, *, actor: UserActor) -> MockReportResponse`; `POST /coach/mock/sessions/{session_id}/report/retry`.

- [ ] **Step 1: Write the failing tests** (`test_mock_report_status.py`):
  - `test_opening_the_report_of_a_queued_session_does_not_call_the_reviewer` → `status == "pending"`, fake agent `runs == []`.
  - `test_a_failed_report_says_so_and_offers_a_retry_until_the_runs_are_used`.
  - `test_retry_requeues_a_failed_report_and_refuses_after_four_runs` (409-style `ConflictError`).
  - `test_retry_of_another_users_session_is_not_found`.
- [ ] **Step 2: Run** and confirm failure.
- [ ] **Step 3: Implement.** `get_mock_report` maps `queued`/`generating` to `pending` with the message `报告正在生成，通常需要一两分钟。`, `failed` to `failed` plus `report_error` and `can_retry`, and builds the full view only for `ready`. Start `run_mock_report_dispatcher()` in `lifespan` next to the parse dispatcher, cancelled on shutdown the same way. Update the three existing tests that relied on the report being generated on first read so they call `claim_next_report` and `generate_report` instead.
- [ ] **Step 4: Run** the full backend suite; all pass.
- [ ] **Step 5: Commit** `feat(coach): the report is generated in the background and can be retried`.

### Task 9: Level cards in the setup panel

**Files:**
- Modify: `frontend/web/lib/api/coach.ts` (`getLevelRecommendation`, `level` on the create body and `MockSession`), `frontend/web/components/coach/CoachFlywheel.tsx`, `frontend/web/app/coach-agent/page.tsx` only if the start signature changes

**Interfaces:**
- Consumes: `GET /coach/mock/level-recommendation` (Task 3).
- Produces: `getLevelRecommendation(profileId: string): Promise<{ recommended: string | null; years: number | null; reason: string | null; levels: LevelOption[] }>`.

- [ ] **Step 1:** Add the API function and types.
- [ ] **Step 2:** In `CoachFlywheel`, add a "面试级别" section with four selectable cards (name, 对照, 年限, one-line requirement). The recommended card is preselected and marked 推荐 with the `reason` under the list; when there is no recommendation nothing is preselected and the start button is disabled with the hint "请先选择面试级别". The chosen level is sent in `createMockSession`.
- [ ] **Step 3: Verify:** `npx tsc --noEmit` exits 0. In the browser at desktop and 375px width: recommendation shown with its reason, switching cards changes the sent `level` (check the request body), the start button is blocked with no level. Note in the report that the interviewer's reply was not exercised (model disabled locally).
- [ ] **Step 4: Commit** `feat(coach): the user chooses the interview level, the profile recommends one`.

### Task 10: Report page shows generation status

**Files:**
- Modify: `frontend/web/lib/api/coach.ts` (`retryMockReport`, `MockReport.status` adds `"failed"`, `can_retry`), `frontend/web/app/mock-reports/[id]/page.tsx`

- [ ] **Step 1:** Add `retryMockReport(sessionId)` and the new fields.
- [ ] **Step 2:** On `pending`, poll `getMockReport` every 5 seconds (stop on unmount and once the status is not `pending`) and show "报告正在生成…". On `failed`, show the reason and a "重新生成" button when `can_retry`, otherwise "多次生成失败，请联系我们"; clicking calls `retryMockReport` and resumes polling.
- [ ] **Step 3: Verify:** `npx tsc --noEmit` exits 0. In the browser, seed a local session in each state (`queued`, `failed` with `can_retry`, `failed` out of runs, `ready`) and check each renders; confirm the poll stops when leaving the page (no requests after navigation).
- [ ] **Step 4: Commit** `feat(coach): the report page follows generation and can retry`.

### Task 11: Close the loop

**Files:**
- Modify: `docs/product/SPEC-MOCK-INTERVIEW-V2.md` (§3.4 and §7 status), `docs/architecture/TECH-API.md` for the two new routes and the changed report status values

- [ ] **Step 1:** Update §3.4 to say `turn_index` and `stage` are deferred (reasons in Global Constraints), and add an implementation-status table for steps 1 and 2.
- [ ] **Step 2: Verify migrations on a real database.** Start a throwaway MariaDB (`mariadb-install-db` in `/tmp`, port 3307, database `jc_local`), run `./scripts/db_upgrade.sh`, confirm head is `024_mock_report_queue`, run `alembic downgrade 022_drop_agent_session_kind` then `upgrade head` again. Remove the instance afterwards.
- [ ] **Step 3: Run** the whole backend suite and `npx tsc --noEmit`; report the pass counts as they are.
- [ ] **Step 4: Commit** `docs: record the mock interview foundation`.

---

## Self-review

- **Spec coverage:** §3.3 recording (Tasks 5, 6), §3.4 data (Tasks 3, 7, deferral noted), §3.5 level (Tasks 2, 3, 4, 9), §5.3 async report and retry cap (Tasks 7, 8, 10), §6.1 level cards (Task 9). Not covered, by design: §3.1 stages, §3.2 behaviour rules beyond the opening already shipped, §4.2 blueprint, §5.1/5.2 report structure, seed bank; they belong to steps 3 to 6.
- **Type consistency:** `get_latest_attempt_in_session`, `_open_question(..., mock_session_id)`, `level_for_profile`, `LEVEL_SPECS`, `claim_next_report`, `generate_report`, `requeue_failed` are named identically wherever they are used.
- **Proportion:** the plan has no code bodies; each task gives signatures, test names with their assertions, and the values the spec fixes, and leaves the bodies to the implementer.
- **Calls I made that the spec leaves open:** band boundaries are lower-inclusive; a title with both senior and junior words adjusts nothing; "most recent job" means the latest end date; legacy reportless sessions become `failed` rather than being queued, to avoid an unexpected model bill on deploy; a recording error is surfaced to the user instead of swallowed.
