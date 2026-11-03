"""The reviewer's report is checked before it is stored: evidence must be the candidate's own words,
facts must have a profile source, averages come from the server, and only a completed session of the
caller's own profile can receive a report."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.mock_report_service import validate_report, write_report

ANSWERS = {"q1": "我负责把结算接口从单表拆成两张表，耗时三周。", "q2": "没有做压测。"}
PROFILE = '{"experience": "结算接口从单表拆成两张表"}'


def test_score_with_a_quote_from_the_answer_is_kept():
    raw = {"questions": [{"question_id": "q1", "scores": {"structure": 6},
                          "evidence": {"structure": "拆成两张表"}}]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    assert report["questions"][0]["scores"]["structure"] == 6
    assert report["checks"]["rejected_evidence"] == 0


def test_score_whose_quote_is_not_in_the_answer_is_dropped_and_counted():
    raw = {"questions": [{"question_id": "q1", "scores": {"depth": 9},
                          "evidence": {"depth": "我们用了分布式事务"}}]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    assert report["questions"][0]["scores"]["depth"] is None
    assert report["checks"]["rejected_evidence"] == 1


def test_quote_matches_across_whitespace_differences():
    raw = {"questions": [{"question_id": "q1", "scores": {"depth": 4},
                          "evidence": {"depth": "拆成  两张表"}}]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    assert report["questions"][0]["scores"]["depth"] == 4


def test_score_without_any_quote_is_dropped():
    raw = {"questions": [{"question_id": "q1", "scores": {"depth": 4}, "evidence": {}}]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    assert report["questions"][0]["scores"]["depth"] is None


def test_skipped_question_can_only_be_unscored():
    raw = {"questions": [{"question_id": "q2", "scores": {"depth": 5},
                          "evidence": {"depth": "没有做压测"}}]}
    report = validate_report(raw, answers={"q2": ""}, profile_text=PROFILE)
    assert report["questions"][0]["scores"]["depth"] is None
    assert report["checks"]["rejected_evidence"] == 1


def test_reference_fact_without_profile_source_is_pending():
    raw = {"questions": [{"question_id": "q1", "reference": [
        {"text": "拆表前先做了双写", "source": "双写迁移"},
        {"text": "拆表后吞吐翻倍", "source": "吞吐翻倍"},
    ]}]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    statuses = [r["status"] for r in report["questions"][0]["reference"]]
    assert statuses == ["pending", "pending"]
    assert report["checks"]["pending_facts"] == 2


def test_reference_fact_with_profile_source_is_sourced():
    raw = {"questions": [{"question_id": "q1", "reference": [
        {"text": "拆成两张表", "source": "结算接口从单表拆成两张表"},
    ]}]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    assert report["questions"][0]["reference"][0]["status"] == "sourced"
    assert report["checks"]["pending_facts"] == 0


def test_overall_averages_are_computed_from_kept_scores_only():
    raw = {"questions": [
        {"question_id": "q1", "scores": {"depth": 6, "structure": 4},
         "evidence": {"depth": "拆成两张表", "structure": "拆成两张表"}},
        {"question_id": "q2", "scores": {"depth": 8}, "evidence": {"depth": "没有做压测"}},
    ]}
    report = validate_report(raw, answers=ANSWERS, profile_text=PROFILE)
    assert report["overall"]["depth"] == 7.0
    assert report["overall"]["structure"] == 4.0
    assert report["overall"]["reflection"] is None


@pytest.mark.parametrize("bad", [0, 11, 3.5, "7", True])
def test_out_of_range_or_non_integer_score_is_refused(bad):
    raw = {"questions": [{"question_id": "q1", "scores": {"depth": bad},
                          "evidence": {"depth": "拆成两张表"}}]}
    with pytest.raises(ValueError):
        validate_report(raw, answers=ANSWERS, profile_text=PROFILE)


def test_question_outside_the_session_is_refused():
    raw = {"questions": [{"question_id": "qX", "scores": {}}]}
    with pytest.raises(ValueError, match="not part of this session"):
        validate_report(raw, answers=ANSWERS, profile_text=PROFILE)


def test_duplicate_question_is_refused():
    raw = {"questions": [{"question_id": "q1"}, {"question_id": "q1"}]}
    with pytest.raises(ValueError, match="appears twice"):
        validate_report(raw, answers=ANSWERS, profile_text=PROFILE)


def test_bad_fix_severity_is_refused():
    raw = {"questions": [{"question_id": "q1", "fixes": [{"severity": "critical", "text": "x"}]}]}
    with pytest.raises(ValueError, match="severity"):
        validate_report(raw, answers=ANSWERS, profile_text=PROFILE)


def test_empty_report_is_refused():
    with pytest.raises(ValueError, match="non-empty"):
        validate_report({"questions": []}, answers=ANSWERS, profile_text=PROFILE)


# --- write path: ownership and session state --------------------------------------------------


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/report.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        session.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user",
                            payload={"experience": "结算"}, version=1))
        session.add(Profile(id="p2", user_id="u2", owner_kind="user",
                            payload={"experience": "其它"}, version=1))
        await session.commit()
    yield maker
    await engine.dispose()


def _answered_question() -> list:
    question = InterviewQuestion(
        id="q1", profile_id="p1", stem="讲一个你拆分数据的经历", question_type="behavioral",
    )
    attempt = AnswerAttempt(
        id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
        user_answer=ANSWERS["q1"], coach_feedback={}, reference_answer=None,
    )
    return [question, attempt]


def _mock(status: str, profile_id: str = "p1") -> MockSession:
    return MockSession(
        id="ms1", profile_id=profile_id, user_id="u1", mode="full",
        question_ids=["q1"], bank_draw_count=0, generated_count=0,
        status=status, started_at=datetime(2026, 11, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_report_is_stored_only_after_the_session_completes(db):
    async with db() as s:
        s.add(_mock("completed"))
        s.add_all(_answered_question())
        await s.commit()
    async with db() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")
        out = await write_report(
            scope, mock_session_id="ms1",
            raw={"questions": [{"question_id": "q1", "scores": {"depth": 5},
                                "evidence": {"depth": "拆成两张表"}}]},
        )
    assert out["overall"]["depth"] == 5.0
    assert out["checks"]["rejected_evidence"] == 0
    async with db() as s:
        stored = (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()
        assert stored.report["overall"]["depth"] == 5.0


@pytest.mark.asyncio
async def test_report_on_an_active_session_is_refused(db):
    async with db() as s:
        s.add(_mock("active"))
        await s.commit()
    async with db() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")
        with pytest.raises(ValueError, match="after the session has ended"):
            await write_report(
                scope, mock_session_id="ms1", raw={"questions": [{"question_id": "q1"}]}
            )


@pytest.mark.asyncio
async def test_report_for_another_users_profile_is_refused(db):
    async with db() as s:
        s.add(_mock("completed", profile_id="p2"))
        await s.commit()
    async with db() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")
        with pytest.raises(PermissionError):
            await write_report(
                scope, mock_session_id="ms1", raw={"questions": [{"question_id": "q1"}]}
            )
