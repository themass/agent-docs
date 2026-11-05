"""Conversational intake: the interview plan, and writing answers into a profile.

Two properties matter more than any individual question:

- **It terminates and it resumes.** Question ids are a stable function of the profile
  shape, so the same profile asked twice gets the same ids, and answered ids drop out.
- **It only writes what the user typed.** No model is in this path at all.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from jc.schemas.intake import IntakeAnswerInput  # noqa: F401  (contract smoke import)
from jc.schemas.profile_payload import (
    EvidenceAnswer,
    ProfileContact,
    ProfileExperience,
    ProfilePayload,
    ProfileProject,
)
from jc.services.intake_service import answered_question_ids, apply_answer
from jc.services.profile_intake import (
    NEW_EXPERIENCE_PATH,
    build_intake_plan,
    classify_mode,
    describe_path,
)


def _empty() -> ProfilePayload:
    return ProfilePayload()


def _skeleton() -> ProfilePayload:
    return ProfilePayload(
        contact=ProfileContact(name="张三", email="z@example.com"),
        experiences=[
            ProfileExperience(
                id="exp1",
                company="某某科技",
                title="后端技术专家",
                start_date="2021-03",
            )
        ],
    )


def _complete() -> ProfilePayload:
    return ProfilePayload(
        contact=ProfileContact(name="张三", email="z@example.com"),
        experiences=[
            ProfileExperience(
                id="exp1",
                company="某某科技",
                title="后端技术专家",
                start_date="2021-03",
                scope="带 8 人团队负责订单主链路",
                highlights=[
                    "主导订单服务拆分为 6 个微服务",
                    "搭建配置中心，覆盖 120 个服务",
                    "牵头容量保障，支撑日均 1200 万单",
                ],
            )
        ],
    )


def _answer_for(target_path: str) -> str:
    """A plausible answer for any path the plan can name."""
    fixed = {
        "contact.name": "张三",
        "contact.email": "z@example.com",
        "contact.phone": "13800000000",
        "contact.location": "杭州",
        "preferences.target_roles": "后端技术专家 / 架构师",
    }
    if target_path in fixed:
        return fixed[target_path]
    if target_path.endswith("]") and ".highlights[" not in target_path:
        return "某某科技 · 后端技术专家 · 2021-03 至今"
    if target_path.endswith(".scope"):
        return "带 8 人后端团队，负责订单与结算两条主链路"
    return "主导订单服务拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟"


# --- mode classification --------------------------------------------------------------


def test_modes_describe_what_the_interview_is_for() -> None:
    assert classify_mode(_empty()) == "empty"
    assert classify_mode(_skeleton()) == "skeleton"
    assert classify_mode(_complete()) == "complete"


def test_a_career_that_ended_in_the_past_is_stale_not_complete() -> None:
    """A profile whose latest role closed years ago describes someone else's career."""
    profile = _complete()
    profile.experiences[0].end_date = "2022-06"
    assert classify_mode(profile) == "stale"


# --- plan shape -----------------------------------------------------------------------


def test_an_empty_profile_is_asked_for_identity_before_achievements() -> None:
    """Identity first: it is quick, and it makes the page stop looking empty."""
    plan = build_intake_plan(_empty())
    ids = [q.id for q in plan.questions]
    assert ids[0] == "identity.name"
    assert "role.0.identity" in ids
    # Nothing is asked about accomplishments before we know which job they belong to.
    assert not any(i.startswith("role.0.highlight") for i in ids)


def test_an_empty_profile_cannot_generate_and_says_why() -> None:
    plan = build_intake_plan(_empty())
    assert plan.can_generate is False
    assert any("姓名" in b for b in plan.blocking)
    assert any("工作经历" in b for b in plan.blocking)


def test_a_complete_profile_can_generate_and_asks_nothing_required() -> None:
    plan = build_intake_plan(_complete())
    assert plan.can_generate is True
    assert plan.blocking == []


def test_answered_questions_are_not_asked_again() -> None:
    """Resumption is the whole reason ids are derived rather than generated."""
    first = build_intake_plan(_empty())
    answered = frozenset({first.questions[0].id})
    second = build_intake_plan(_empty(), answered_ids=answered)
    assert first.questions[0].id not in [q.id for q in second.questions]
    assert second.answered_count == 1


def test_question_ids_are_stable_for_the_same_profile() -> None:
    assert [q.id for q in build_intake_plan(_skeleton()).questions] == [
        q.id for q in build_intake_plan(_skeleton()).questions
    ]


def test_a_stored_scope_is_not_asked_for_twice() -> None:
    profile = _skeleton()
    assert any(q.id == "role.0.scope" for q in build_intake_plan(profile).questions)
    profile.experiences[0].scope = "带 8 人团队负责订单主链路"
    assert not any(q.id == "role.0.scope" for q in build_intake_plan(profile).questions)


def test_only_the_recent_roles_are_interviewed_in_detail() -> None:
    """Twenty questions about a 2012 internship trades patience for an unread line."""
    profile = _complete()
    for n in range(2, 6):
        profile.experiences.append(
            ProfileExperience(
                id=f"exp{n}", company=f"C{n}", title="工程师", start_date="2015-01"
            )
        )
    ids = [q.id for q in build_intake_plan(profile, limit=50).questions]
    assert not any(i.startswith("role.2.") for i in ids)
    assert not any(i.startswith("role.4.") for i in ids)


def test_the_plan_reports_progress_by_stage() -> None:
    plan = build_intake_plan(_empty())
    stages = {s.id: s for s in plan.stages}
    assert set(stages) == {
        "identity",
        "current_role",
        "achievements",
        "history",
        "direction",
    }
    assert stages["identity"].remaining > 0
    assert stages["identity"].done is False


def test_every_question_explains_why_it_is_being_asked() -> None:
    for profile in (_empty(), _skeleton()):
        for question in build_intake_plan(profile).questions:
            assert question.rationale, question.id
            assert question.target_path, question.id
            assert question.input_kind in {"text", "long_text", "list"}


# --- writing answers ------------------------------------------------------------------


def test_identity_answers_land_in_contact_fields() -> None:
    profile = _empty()
    assert apply_answer(profile, "contact.name", "张三") == "contact.name"
    assert profile.contact.name == "张三"
    assert apply_answer(profile, "contact.email", "z@example.com") == "contact.email"
    assert profile.contact.email == "z@example.com"


def test_a_phone_number_answered_to_the_email_question_lands_on_phone() -> None:
    """One question covers both; the shape of the answer decides where it goes."""
    profile = _empty()
    assert apply_answer(profile, "contact.email", "13800000000") == "contact.phone"
    assert profile.contact.phone == "13800000000"
    assert profile.contact.email is None


def test_a_role_line_is_split_into_company_title_and_dates() -> None:
    profile = _empty()
    apply_answer(profile, "experiences[0]", "某某科技 · 后端技术专家 · 2021-03 至今")
    exp = profile.experiences[0]
    assert exp.company == "某某科技"
    assert exp.title == "后端技术专家"
    assert exp.start_date == "2021-03"
    # "至今" means the role is current, which is what `classify_mode` reads.
    assert exp.end_date is None


def test_a_closed_role_keeps_both_dates() -> None:
    profile = _empty()
    apply_answer(profile, "experiences[0]", "某某科技 · 工程师 · 2018-05 — 2021-02")
    exp = profile.experiences[0]
    assert exp.start_date == "2018-05"
    assert exp.end_date == "2021-02"


def test_an_unparseable_role_line_is_kept_rather_than_discarded() -> None:
    """The user corrects it on the review step; losing it is not an option."""
    profile = _empty()
    apply_answer(profile, "experiences[0]", "一家还没公开的创业公司")
    assert profile.experiences[0].company == "一家还没公开的创业公司"


def test_scope_and_highlights_are_stored_verbatim() -> None:
    profile = _skeleton()
    scope = "带 8 人后端团队，负责订单与结算两条主链路"
    highlight = "主导订单服务拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟"
    assert apply_answer(profile, "experiences[0].scope", scope) == "experiences[0].scope"
    assert profile.experiences[0].scope == scope
    path = apply_answer(profile, "experiences[0].highlights[0]", highlight)
    assert path == "experiences[0].highlights[0]"
    assert profile.experiences[0].highlights == [highlight]


def test_answering_about_a_role_that_does_not_exist_yet_creates_it() -> None:
    """The "还有更早的经历吗" question legitimately targets an absent index."""
    profile = _skeleton()
    apply_answer(profile, "experiences[1]", "前一家公司 · 工程师 · 2018-01 — 2021-02")
    assert len(profile.experiences) == 2
    assert profile.experiences[1].company == "前一家公司"
    # The existing role is untouched.
    assert profile.experiences[0].company == "某某科技"


def test_target_roles_accept_several_values_in_one_answer() -> None:
    profile = _empty()
    apply_answer(profile, "preferences.target_roles", "后端技术专家 / 架构师")
    assert profile.preferences.target_roles == ["后端技术专家", "架构师"]


def test_an_unknown_target_path_writes_nothing() -> None:
    """A stale or malicious client must not be able to reshape the profile.

    The answer is still stored as evidence by the service, so nothing is lost — it
    simply cannot alter structure the plan did not name.
    """
    profile = _complete()
    before = profile.model_dump(mode="json")
    assert apply_answer(profile, "experiences[0].salary", "30k") is None
    assert apply_answer(profile, "meta.ingest_mode", "hacked") is None
    assert apply_answer(profile, "", "x") is None
    assert profile.model_dump(mode="json") == before


def test_answered_ids_are_recovered_from_the_profile_alone() -> None:
    """There is no server-side interview session, so closing the tab must lose nothing."""
    from datetime import UTC, datetime

    from jc.schemas.profile_payload import EvidenceAnswer

    profile = _skeleton()
    profile.evidence_answers = [
        EvidenceAnswer(
            field_path="contact.name",
            question="你的姓名是？",
            answer="张三",
            kind="intake:identity.name",
            answered_at=datetime.now(UTC),
        ),
        # A regular evidence answer must not be mistaken for an interview answer.
        EvidenceAnswer(
            field_path="experiences[0].highlights[0]",
            question="这条的结果是什么？",
            answer="耗时下降 85%",
            kind="missing_outcome",
        ),
    ]
    assert answered_question_ids(profile) == frozenset({"identity.name"})


def test_a_full_interview_reaches_a_generatable_profile() -> None:
    """End to end: an empty profile answered through the plan can produce a draft."""
    profile = _empty()
    answered: set[str] = set()
    for _ in range(12):
        plan = build_intake_plan(profile, answered_ids=frozenset(answered))
        pending = [q for q in plan.questions if q.required]
        if not pending:
            break
        question = pending[0]
        answers = {
            "contact.name": "张三",
            "contact.email": "z@example.com",
        }
        text = answers.get(
            question.target_path,
            "某某科技 · 后端技术专家 · 2021-03 至今"
            if question.target_path == "experiences[0]"
            else "主导订单服务拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟",
        )
        apply_answer(profile, question.target_path, text)
        answered.add(question.id)

    final = build_intake_plan(profile, answered_ids=frozenset(answered))
    assert final.can_generate is True, final.blocking
    assert profile.contact.name == "张三"
    assert profile.experiences[0].company == "某某科技"


def test_identity_answers_do_not_buy_their_way_past_the_viability_floor() -> None:
    """Answering 「姓名」「联系方式」「公司职位」 must not read as three pieces of evidence.

    The gate used to add `len(evidence_answers)` to the highlight count. Every interview
    answer lands in that list, including the name and the phone number, so a profile with
    **zero** highlights was told 「可以生成」 after three answers about nothing. The draft
    that came back was a name and a job title, and the user had no way to tell why.

    Asserted through `apply_answer` rather than by hand-building the payload, because the
    bug only appears once the answers are mirrored into `evidence_answers` the way the
    real flow mirrors them.
    """
    profile = _skeleton()
    now = datetime.now(UTC)
    for qid, path, question in (
        ("identity.name", "contact.name", "你的姓名是？"),
        ("identity.contact", "contact.email", "留一个联系方式。"),
        ("role.0.scope", "experiences[0].scope", "你负责什么？"),
    ):
        apply_answer(profile, path, _answer_for(path))
        profile.evidence_answers.append(
            EvidenceAnswer(
                field_path=path,
                question=question,
                answer=_answer_for(path),
                kind=f"intake:{qid}",
                answered_at=now,
            )
        )

    plan = build_intake_plan(profile)
    assert plan.can_generate is False, plan.blocking
    assert any("要点太少" in b for b in plan.blocking)
    assert any(q.id.startswith("role.0.highlight") for q in plan.questions)


def test_gap_answers_do_not_count_as_new_evidence() -> None:
    """A gap answer adds an outcome to an existing bullet; counting it credits it twice."""
    profile = _skeleton()
    profile.experiences[0].highlights = ["主导订单服务拆分"]
    profile.evidence_answers = [
        EvidenceAnswer(
            field_path="experiences[0].highlights[0]",
            question="这条的结果是什么？",
            answer="发布耗时下降 85%",
            kind="missing_outcome",
            answered_at=datetime.now(UTC),
        ),
        EvidenceAnswer(
            field_path="experiences[0].highlights[0]",
            question="规模多大？",
            answer="覆盖 120 个服务",
            kind="missing_scale",
            answered_at=datetime.now(UTC),
        ),
    ]

    assert classify_mode(profile) == "skeleton"
    assert build_intake_plan(profile).can_generate is False


def test_mode_and_the_generation_gate_never_disagree() -> None:
    """`complete` must imply generatable, and a refusal must imply a non-complete mode.

    These were two independently computed totals. One counted `evidence_answers` and the
    other did not, so a profile could be labelled 「资料齐全」 in the header while the
    generate button stayed disabled with no explanation.
    """
    profile = _empty()
    answered: set[str] = set()
    for _ in range(30):
        plan = build_intake_plan(profile, answered_ids=frozenset(answered))
        mode = classify_mode(profile)
        if mode == "complete":
            assert plan.can_generate is True, (mode, plan.blocking)
        if not plan.can_generate:
            assert mode != "complete", plan.blocking
        pending = [q for q in plan.questions if q.required]
        if not pending:
            break
        question = pending[0]
        apply_answer(profile, question.target_path, _answer_for(question.target_path))
        answered.add(question.id)


def _highlight_shapes(role_family: str) -> tuple[str, ...]:
    profile = _skeleton()
    profile.experiences[0].scope = "带 8 人团队"
    plan = build_intake_plan(profile, role_family=role_family)
    question = next(q for q in plan.questions if q.id.startswith("role.0.highlight"))
    return tuple(m.skeleton for m in question.metrics)


def test_achievement_questions_offer_fillable_shapes_not_bare_nouns() -> None:
    """「P99 延迟」 is a dimension; 「P99 延迟从 ___ 降到 ___」 is something to type into.

    Carried as structured metrics rather than as an 「例如：」 line, so the UI can insert
    one and put the caret on the blank — the same affordance the evidence panel already
    offers for the same question. Shared through `metric_prompts` so the two cannot
    disagree about how a figure is asked for.
    """
    from jc.services.metric_prompts import BLANK

    shapes = _highlight_shapes("backend")

    assert shapes
    assert all(BLANK in shape for shape in shapes)
    # No skeleton may arrive pre-filled. A digit followed by a unit is a value, while
    # "P99" is part of a dimension name, so the check is for the value shape rather than
    # for digits in general.
    assert not any(re.search(r"\d+\s*(?:ms|s|%|QPS|万|亿)", shape) for shape in shapes)


def test_achievement_shapes_follow_the_role_family() -> None:
    """A designer must not be shown QPS skeletons; that is the whole point of families."""
    backend = _highlight_shapes("backend")
    design = _highlight_shapes("design")

    assert backend != design
    assert not any("QPS" in shape for shape in design)


def _stale() -> ProfilePayload:
    profile = _complete()
    profile.experiences[0].end_date = "2022-06"
    return profile


def test_a_stale_profile_is_asked_about_now_not_about_earlier_jobs() -> None:
    """The point of classifying `stale` is to interview it differently.

    It used to be interviewed exactly like `complete`: the newest role already had a
    company, a title and three highlights, so every role question was satisfied and the
    only thing left to ask was 「在这之前还有别的工作经历吗」 — about the past, when what
    is missing is the present. The resume generated from that describes the job the user
    already left.
    """
    plan = build_intake_plan(_stale())
    ids = [q.id for q in plan.questions]

    assert "history.current" in ids
    assert "history.more" not in ids
    current = next(q for q in plan.questions if q.id == "history.current")
    assert "2022-06" in current.question, "the question must say which date looks stale"
    # Optional: the user may genuinely be between roles, and a resume that ends last year
    # beats refusing to generate one at all.
    assert current.required is False


def test_the_current_role_is_inserted_ahead_of_the_old_one_not_over_it() -> None:
    """Writing to `experiences[0]` here would delete the job the user actually held."""
    profile = _stale()
    written = apply_answer(profile, NEW_EXPERIENCE_PATH, "新云科技 · 后端架构师 · 2022-07 至今")

    assert written == "experiences[0]"
    assert [e.company for e in profile.experiences] == ["新云科技", "某某科技"]
    # The old role keeps its content; only its position changed.
    assert len(profile.experiences[1].highlights) == 3
    assert profile.experiences[0].end_date is None, "「至今」 must not become an end date"


def test_answering_the_stale_question_hands_off_to_the_ordinary_interview() -> None:
    """Once the current role exists it is just an empty newest role — no special case."""
    profile = _stale()
    apply_answer(profile, NEW_EXPERIENCE_PATH, "新云科技 · 后端架构师 · 2022-07 至今")

    assert classify_mode(profile) == "complete"
    ids = [q.id for q in build_intake_plan(profile).questions]
    assert "role.0.scope" in ids
    assert any(i.startswith("role.0.highlight") for i in ids)
    assert "history.current" not in ids, "the stale question must not repeat"


def test_the_insert_path_is_labelled_in_the_user_s_words() -> None:
    """`experiences[new]` is not an index, so the path regex would leak it to the UI."""
    label = describe_path(_stale(), NEW_EXPERIENCE_PATH)
    assert "[" not in label and label != NEW_EXPERIENCE_PATH


def test_projects_count_toward_viability() -> None:
    """A career whose evidence lives in projects must not be told it has nothing."""
    profile = ProfilePayload(
        contact=ProfileContact(name="张三", email="z@example.com"),
        experiences=[
            ProfileExperience(id="e1", company="A", title="工程师", start_date="2021-01")
        ],
        projects=[
            ProfileProject(
                id="p1",
                name="配置中心",
                highlights=["覆盖 120 个服务", "事故下降 70%", "灰度发布机制"],
            )
        ],
    )
    assert build_intake_plan(profile).can_generate is True


def test_the_plan_can_always_reach_viability() -> None:
    """Answering every required question must leave a profile that can generate.

    This is the invariant the first version broke: the lead role was asked for two
    highlights while generation required three, so a user who answered everything was
    still refused. Asserting the end state rather than the constants keeps the two
    thresholds from drifting apart again.
    """
    profile = _empty()
    answered: set[str] = set()
    asked: list[str] = []
    for _ in range(30):
        plan = build_intake_plan(profile, answered_ids=frozenset(answered))
        pending = [q for q in plan.questions if q.required]
        if not pending:
            break
        question = pending[0]
        asked.append(question.id)
        apply_answer(profile, question.target_path, _answer_for(question.target_path))
        answered.add(question.id)
    else:  # pragma: no cover - only runs if the plan fails to terminate
        raise AssertionError(f"interview did not terminate: {asked}")

    plan = build_intake_plan(profile, answered_ids=frozenset(answered))
    assert plan.can_generate is True, plan.blocking
    # And no question was asked twice under a shifting id.
    assert len(asked) == len(set(asked)), asked


def test_highlight_questions_keep_their_slot_as_answers_land() -> None:
    """Ids are absolute slots, so answering one reveals the next instead of repeating it."""
    profile = _skeleton()
    first = [q.id for q in build_intake_plan(profile, limit=50).questions]
    assert "role.0.highlight.0" in first

    apply_answer(profile, "experiences[0].highlights[0]", "主导订单服务拆分为 6 个微服务")
    second = [q.id for q in build_intake_plan(profile, limit=50).questions]
    assert "role.0.highlight.0" not in second
    assert "role.0.highlight.1" in second


# --- revising an answer ---------------------------------------------------------------


def test_a_revised_highlight_replaces_the_one_it_corrects() -> None:
    """Re-answering must overwrite the named slot, not append a second bullet.

    The write path used to `append` regardless of the path, while the plan keys highlight
    questions by absolute slot. So a user fixing a typo in their second highlight got a
    *third* highlight and kept the wrong text — the interview was effectively write-once.
    """
    profile = _skeleton()
    apply_answer(profile, "experiences[0].highlights[0]", "拆分订单服务")
    apply_answer(profile, "experiences[0].highlights[1]", "搭建配置中心")

    written = apply_answer(profile, "experiences[0].highlights[1]", "搭建配置中心，覆盖 120 个服务")

    assert written == "experiences[0].highlights[1]"
    assert profile.experiences[0].highlights == [
        "拆分订单服务",
        "搭建配置中心，覆盖 120 个服务",
    ]


def test_a_highlight_slot_past_the_end_appends_instead_of_leaving_a_hole() -> None:
    """An empty highlight renders as a bullet-shaped hole, so gaps are never padded."""
    profile = _skeleton()
    written = apply_answer(profile, "experiences[0].highlights[4]", "拆分订单服务")
    assert written == "experiences[0].highlights[0]"
    assert profile.experiences[0].highlights == ["拆分订单服务"]


def test_answered_questions_are_returned_so_they_can_be_reviewed() -> None:
    """Answered questions leave `questions` but must not leave the response entirely.

    Dropping them is what made the panel write-once: the user was told
    `experiences[0].scope` had been written and had no way to read it back or fix it.
    """
    profile = _skeleton()
    plan = build_intake_plan(profile, limit=50)
    question = next(q for q in plan.questions if q.id == "role.0.scope")

    apply_answer(profile, question.target_path, "带 8 人后端团队")
    profile.evidence_answers.append(
        EvidenceAnswer(
            field_path=question.target_path,
            question=question.question,
            answer="带 8 人后端团队",
            kind=f"intake:{question.id}",
            answered_at=datetime.now(UTC),
        )
    )

    after = build_intake_plan(profile, answered_ids=answered_question_ids(profile), limit=50)
    assert "role.0.scope" not in [q.id for q in after.questions]
    revisable = next(a for a in after.answered if a.question_id == "role.0.scope")
    assert revisable.answer == "带 8 人后端团队"
    assert revisable.target_path == "experiences[0].scope"


# --- paths in the user's words --------------------------------------------------------


def test_paths_are_described_in_terms_the_user_can_check() -> None:
    """A dotted path is not a confirmation: the user cannot verify what we recorded."""
    profile = _complete()

    assert describe_path(profile, "contact.name") == "姓名"
    assert describe_path(profile, "preferences.target_roles") == "目标岗位"
    assert describe_path(profile, "experiences[0].scope") == "某某科技 · 后端技术专家 · 负责范围"
    assert (
        describe_path(profile, "experiences[0].highlights[2]")
        == "某某科技 · 后端技术专家 · 第 3 条成果"
    )


def test_a_role_with_no_company_yet_is_still_named_something_readable() -> None:
    """Intake writes identity last for a brand new role, so labels must survive that."""
    profile = _empty()
    apply_answer(profile, "experiences[0].highlights[0]", "拆分订单服务")
    assert describe_path(profile, "experiences[0].highlights[0]") == "最近这份工作 · 第 1 条成果"
    assert describe_path(profile, "experiences[1].scope") == "第 2 段经历 · 负责范围"


def test_an_unknown_path_falls_back_to_itself_rather_than_inventing_a_name() -> None:
    """A wrong label is worse than an ugly one: the user would check the wrong field."""
    profile = _complete()
    assert describe_path(profile, "mystery.field") == "mystery.field"
