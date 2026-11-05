"""The report leads with a conclusion: how the interview went, how ready the candidate is, what they
did well and what to fix first.

The readiness tier is computed here, by rules, and not by the model: the same scores must always
give the same tier, and a tier must never claim more than the evidence behind it. What the reviewer
writes is the words, and every quote in them has to be something the candidate said."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.coach.readiness import readiness
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.interview_service import InterviewService
from jc.services.mock_report_service import validate_report

DIMS = ("structure", "relevance", "depth", "communication", "reflection")


def _overall(**values):
    base = {dim: 7.0 for dim in DIMS}
    base.update(values)
    return base


def _all(value):
    return {dim: value for dim in DIMS}


FULL = {"total": 4, "asked": 4, "meet": 4}


# --- the tier ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "tier"),
    [(3.5, "need_more"), (4.4, "need_more"), (4.5, "targeted"), (5.9, "targeted"),
     (6.0, "ready"), (7.4, "ready"), (7.5, "solid"), (9.0, "solid")],
)
def test_the_tier_follows_the_mean_with_the_lower_bound_included(score, tier):
    assert readiness(_all(score), FULL, level="mid", ended_early=False)["tier"] == tier


def test_the_labels_are_the_four_agreed_phrases():
    labels = {
        readiness(_all(s), FULL, level="mid", ended_early=False)["tier"]:
        readiness(_all(s), FULL, level="mid", ended_early=False)["label"]
        for s in (3.0, 5.0, 6.5, 8.5)
    }
    assert labels == {"need_more": "还需大量准备", "targeted": "需针对性补强",
                      "ready": "基本可以上场", "solid": "表现稳定"}


def test_one_dimension_at_three_or_below_keeps_a_good_mean_from_reading_as_ready():
    out = readiness(_overall(depth=3.0), FULL, level="mid", ended_early=False)
    assert out["tier"] == "targeted"
    assert any("深度" in line and "3" in line for line in out["basis"])


def test_a_dimension_just_above_three_does_not_cap():
    assert readiness(_overall(depth=3.1, structure=9, relevance=9, communication=9,
                              reflection=9), FULL, level="mid", ended_early=False
                     )["tier"] == "solid"


def test_an_interview_that_was_ended_early_is_never_rated_above_targeted():
    out = readiness(_all(9.0), FULL, level="mid", ended_early=True)
    assert out["tier"] == "targeted"
    assert any("提前结束" in line for line in out["basis"])


def test_a_cap_never_raises_a_tier():
    assert readiness(_all(3.0), FULL, level="mid", ended_early=True)["tier"] == "need_more"


def test_few_must_haves_asked_about_caps_the_tier():
    out = readiness(_all(9.0), {"total": 4, "asked": 1, "meet": 1}, level="mid",
                    ended_early=False)
    assert out["tier"] == "targeted"
    assert any("必备项" in line and "1" in line and "4" in line for line in out["basis"])


def test_half_the_must_haves_asked_about_is_enough():
    assert readiness(_all(9.0), {"total": 4, "asked": 2, "meet": 2}, level="mid",
                     ended_early=False)["tier"] == "solid"


@pytest.mark.parametrize("coverage", [None, {"total": 0, "asked": 0, "meet": 0}])
def test_no_must_haves_means_no_coverage_cap(coverage):
    assert readiness(_all(9.0), coverage, level="mid", ended_early=False)["tier"] == "solid"


def test_nothing_scored_gives_no_tier():
    assert readiness({dim: None for dim in DIMS}, FULL, level="mid", ended_early=False) is None
    assert readiness({}, FULL, level="mid", ended_early=False) is None


def test_the_statement_names_the_level_it_was_judged_against():
    out = readiness(_all(5.0), FULL, level="mid", ended_early=False)
    assert out["statement"] == "按中级的要求：需针对性补强"
    assert any("5.0" in line for line in out["basis"])


def test_a_session_with_no_level_still_has_a_statement():
    out = readiness(_all(5.0), FULL, level=None, ended_early=False)
    assert out["statement"] == "需针对性补强"


def test_missing_dimensions_are_left_out_of_the_mean_not_counted_as_zero():
    scores = {"structure": 8.0, "relevance": 8.0, "depth": None, "communication": None,
              "reflection": None}
    assert readiness(scores, FULL, level="mid", ended_early=False)["tier"] == "solid"


# --- what the reviewer writes ------------------------------------------------------------------

ANSWERS = {"q1": "我把结算接口拆成了两张表，耗时三周。上线后没有回滚。"}
PROFILE = "结算接口拆表"


def _report(summary):
    return {"questions": [{"question_id": "q1", "scores": {"depth": 6},
                           "evidence": {"depth": "拆成了两张表"}}], "summary": summary}


def _validate(summary):
    return validate_report(_report(summary), answers=ANSWERS, profile_text=PROFILE)


def test_a_summary_with_quotes_from_the_candidate_is_kept():
    out = _validate({
        "verdict": "整体思路清楚，但缺少结果的数字。",
        "strengths": [{"text": "动作讲得具体", "quote": "拆成了两张表"}],
        "priorities": [{"text": "补上结果", "quote": "没有回滚"}],
    })
    summary = out["summary"]
    assert summary["verdict"] == "整体思路清楚，但缺少结果的数字。"
    assert summary["strengths"] == [{"text": "动作讲得具体", "quote": "拆成了两张表"}]
    assert summary["priorities"] == [{"text": "补上结果", "quote": "没有回滚"}]
    assert out["checks"]["rejected_quotes"] == 0


def test_a_quote_the_candidate_never_said_is_dropped_and_counted_but_the_words_stay():
    out = _validate({
        "verdict": "不错。",
        "strengths": [{"text": "有量化意识", "quote": "性能提升了三倍"}],
        "priorities": [],
    })
    assert out["summary"]["strengths"] == [{"text": "有量化意识", "quote": None}]
    assert out["checks"]["rejected_quotes"] == 1


def test_a_quote_may_differ_from_the_answer_in_spacing():
    out = _validate({"verdict": "ok", "strengths": [{"text": "x", "quote": "拆成了 两张表"}],
                     "priorities": []})
    assert out["summary"]["strengths"][0]["quote"] == "拆成了 两张表"


def test_no_more_than_three_strengths_and_three_priorities_are_kept():
    items = [{"text": f"第{i}条", "quote": "拆成了两张表"} for i in range(5)]
    out = _validate({"verdict": "ok", "strengths": items, "priorities": items})
    assert [s["text"] for s in out["summary"]["strengths"]] == ["第0条", "第1条", "第2条"]
    assert len(out["summary"]["priorities"]) == 3


def test_an_item_with_no_text_is_dropped():
    out = _validate({"verdict": "ok", "strengths": [{"text": "  ", "quote": "拆成了两张表"},
                                                    {"text": "有内容"}], "priorities": []})
    assert out["summary"]["strengths"] == [{"text": "有内容", "quote": None}]
    assert out["checks"]["rejected_quotes"] == 0


def test_a_report_with_no_summary_is_still_valid_and_has_none():
    out = validate_report(_report(None), answers=ANSWERS, profile_text=PROFILE)
    assert out["summary"] is None
    out = validate_report({"questions": _report(None)["questions"]}, answers=ANSWERS,
                          profile_text=PROFILE)
    assert out["summary"] is None


def test_a_summary_that_says_nothing_is_none():
    assert _validate({"verdict": "  ", "strengths": [], "priorities": []})["summary"] is None


def test_a_summary_of_the_wrong_shape_is_an_error_the_reviewer_can_read():
    with pytest.raises(ValueError, match="summary"):
        _validate("整体不错")
    with pytest.raises(ValueError, match="strengths"):
        _validate({"verdict": "ok", "strengths": "动作具体", "priorities": []})


def test_a_very_long_verdict_is_cut():
    out = _validate({"verdict": "好" * 900, "strengths": [], "priorities": []})
    assert len(out["summary"]["verdict"]) <= 400


# --- on the report page ------------------------------------------------------------------------

OWNER = UserActor(user_id="u1", session_id="s")


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/conclusion.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        db.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲一个你拆分数据的经历",
                                 question_type="behavioral"))
        db.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
                             user_answer=ANSWERS["q1"], coach_feedback={}, reference_answer=None))
        await db.commit()
    yield makers
    await engine.dispose()


async def _page(maker, *, report, level="mid", quota=True, ended="completed"):
    async with maker() as db:
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", question_ids=["q1"],
            bank_draw_count=0, generated_count=0, status="completed", level=level,
            started_at=datetime(2026, 11, 5, tzinfo=UTC), completed_at=datetime(2026, 11, 5, 1,
                                                                               tzinfo=UTC),
            quota_counted=quota, report=report, report_status="ready",
            coverage={"asked": [{"question_id": "q1", "kind": "main"}], "ended_reason": ended,
                      "ended_early": ended != "completed"},
        ))
        await db.commit()
    async with maker() as db:
        return await InterviewService(db).get_mock_report("ms1", actor=OWNER)


STORED = {
    "overall": {dim: 6.5 for dim in DIMS},
    "questions": [{"question_id": "q1", "scores": {"depth": 6}, "evidence": {}}],
    "checks": {"rejected_evidence": 0, "pending_facts": 0, "rejected_quotes": 0},
    "summary": {"verdict": "整体思路清楚。",
                "strengths": [{"text": "动作具体", "quote": "拆成了两张表"}],
                "priorities": [{"text": "补结果", "quote": None}]},
}


@pytest.mark.asyncio
async def test_the_report_page_carries_the_summary_and_the_readiness(maker):
    page = await _page(maker, report=STORED)
    assert page.summary.verdict == "整体思路清楚。"
    assert page.summary.strengths[0].quote == "拆成了两张表"
    assert page.readiness.tier == "ready"
    assert page.readiness.statement == "按中级的要求：基本可以上场"
    assert page.readiness.basis


@pytest.mark.asyncio
async def test_an_early_end_shows_on_the_report_as_a_cap(maker):
    page = await _page(maker, report=STORED, ended="user_ended")
    assert page.readiness.tier == "targeted"


@pytest.mark.asyncio
async def test_a_warm_up_gets_the_conclusion_too(maker):
    page = await _page(maker, report=STORED, quota=False)
    assert page.brief is True and page.readiness.tier == "ready" and page.summary is not None


@pytest.mark.asyncio
async def test_a_report_stored_before_summaries_existed_still_opens(maker):
    old = {k: v for k, v in STORED.items() if k != "summary"}
    page = await _page(maker, report=old, level=None)
    assert page.summary is None
    assert page.readiness.statement == "基本可以上场"


# --- a cap is only the reason when it changed the tier ----------------------------


def test_a_cap_that_changed_nothing_is_stated_as_a_fact_not_as_the_reason():
    # The mean already puts this at "targeted"; no must-have was asked about, which is worth saying,
    # but it did not lower anything, and the page must not read as if it did.
    out = readiness(_all(5.0), {"total": 4, "asked": 0, "meet": 0}, level="mid", ended_early=False)
    assert out["tier"] == "targeted"
    line = next(line for line in out["basis"] if "必备项" in line)
    assert "0" in line and "4" in line
    assert "最多评到" not in line


def test_a_cap_that_lowered_the_tier_says_so():
    out = readiness(_all(9.0), {"total": 4, "asked": 0, "meet": 0}, level="mid", ended_early=False)
    assert out["tier"] == "targeted"
    assert any("必备项" in line and "最多评到" in line for line in out["basis"])


def test_an_early_end_that_changed_nothing_is_stated_without_the_cap_wording():
    out = readiness(_all(3.0), FULL, level="mid", ended_early=True)
    assert out["tier"] == "need_more"
    line = next(line for line in out["basis"] if "提前结束" in line)
    assert "最多评到" not in line


def test_a_weak_dimension_that_changed_nothing_is_stated_without_the_cap_wording():
    scores = _overall(depth=3.0, structure=3.0, relevance=3.0, communication=3.0, reflection=3.0)
    out = readiness(scores, FULL, level="mid", ended_early=False)
    assert out["tier"] == "need_more"
    assert all("最多评到" not in line for line in out["basis"])
